"""Measurements for M7 questions Q1 to Q4, the role duty, and the hindsight comparison.

Run as a module to write what this one invocation measured to results/scenarios.json.
"""

import json
from collections import Counter
from pathlib import Path

from experiments.m7.provenance import stamp

from experiments.m7.kernel import hindsight
from experiments.m7.kernel.lanes import TEAMS, RealLane, StubLane
from riftgame.rng import Stream, keyed_uniform

from experiments.m7.kernel.observe import MODES, actions, encode, legal_mask, observe, run
from experiments.m7.kernel.policy import scripted
from experiments.m7.kernel.profiles import ROAM_CAP_S, ROAM_REFILL, ROLE_LANE, ROLES
from experiments.m7.kernel.world import (CAMPS, FOUNTAIN, HOLD, KEEP, MAP, RECALL, RECALL_S, RIFT, TOWER_POS, Duty, Intent, Kind,
                                         Outcome, World, duty, fingerprint, on_lane)

RESULTS = Path(__file__).parent / "results" / "scenarios.json"
SEEDS = {"staged": 1, "interval": 3, "role_duty_soak": 4, "hidden_state": 5, "snapshot": 7, "hindsight_base_game": hindsight.BASE_SEED,
         "scripted_policy_noise": 0, "hindsight_draws": 0, "hindsight_rollout_worlds": list(range(hindsight.ROLLOUTS))}
TOWER_S = {t.name: t.s for t in MAP.towers}
BLUE_TOP, BLUE_JUNGLE, BLUE_MID, BLUE_SUPPORT, RED_TOP, RED_JUNGLE, RED_MID = 0, 1, 2, 4, 5, 6, 7
BOT_LANE_CHAMPS = (3, 4, 8, 9)


def top(s: float):
    return RIFT.lane_pos("top", s)


def fight(cid: int) -> Intent:
    return Intent(Kind.FIGHT, cid)


def staged(places: dict, dt: float = 1.0) -> World:
    """A world with the named champions moved to their marks. Everyone else holds at the fountain."""
    w = World(seed=SEEDS["staged"], dt=dt, decision_interval=1)
    for cid, pos in places.items():
        w.champs[cid].pos = pos
    w.see()
    return w


def dead(c) -> bool:
    return c.respawn_tick >= 0


def fixed_schedule(o) -> Intent:
    """Intents that depend only on the champion and the 30 s block of the clock, never on what it observes."""
    block, role, side = int(o.time // 30), o.me.id % 5, TEAMS[o.me.id // 5]
    if role == 1:
        return Intent(Kind.CAMP, f"{side}_{('blue', 'gromp', 'wolves', 'raptors')[block % 4]}")
    lane = ROLE_LANE[ROLES[role]]
    if block == 0:
        return Intent(Kind.MOVE, RIFT.at(f"{side}_{lane}_t1"))
    if block == 5 and role == 2:
        return RECALL
    return Intent(Kind.FARM, (lane, MODES[block % 3]))


def digests(w: World, policy, ticks: int, part=World.digest) -> list[str]:
    out = []
    for _ in range(ticks):
        run(w, policy, 1)
        out.append(part(w))
    return out


def steps_to_fountain(w: World, cid: int) -> int:
    for n in range(1, 400):
        w.step()
        if w.champs[cid].pos == FOUNTAIN[cid // 5]:
            return n
    raise RuntimeError("recall never completed")


def keep_between(policy, n: int, dt: float = 1.0):
    """`policy` on every n-th tick and KEEP on the others, for a world that asks on every tick."""
    return lambda o: policy(o) if round(o.time / dt) % n == 0 else KEEP


def interval_invariance(lane_factory=StubLane) -> dict:
    def trajectory(policy, interval: int) -> tuple[list[str], dict]:
        w = World(seed=SEEDS["interval"], decision_interval=interval, lane_factory=lane_factory)
        out, ended = [], Counter()
        for _ in range(300):
            run(w, policy, 1)
            out.append(w.digest())
            ended.update(c.outcome.name for c in w.champs if c.outcome_tick == w.tick - 1)
        return out, dict(sorted(ended.items()))

    every_tick = trajectory(scripted, 1)[0]
    at = {n: trajectory(scripted, n) for n in (2, 4, 10)}
    return {"a_ticks_compared": len(every_tick),
            "a_interval_n_equals_interval_1_with_keep": {n: trajectory(keep_between(scripted, n), 1)[0] == at[n][0] for n in at},
            "a_intents_ended_in_the_window": {n: ended for n, (_, ended) in at.items()},
            "a_reactive_policy_differs_between_interval_1_and_10": every_tick[-1] != at[10][0][-1],
            "a_fixed_orders_differ_between_interval_1_and_10":
                trajectory(fixed_schedule, 1)[0][-1] != trajectory(fixed_schedule, 10)[0][-1]}


def timing() -> dict:

    w = staged({BLUE_TOP: top(6000.0)})
    c = w.champs[BLUE_TOP]
    second = RIFT.at("red_fountain")
    w.submit(BLUE_TOP, Intent(Kind.MOVE, RIFT.at("top_river")))
    walked, trail = 0.0, c.pos
    for tick in range(30):
        if tick == 10:
            to_go = RIFT.distance(c.pos, second)
            w.submit(BLUE_TOP, Intent(Kind.MOVE, second))
        w.step()
        if tick == 10:
            reroute_gain = to_go - RIFT.distance(c.pos, second)
        walked += RIFT.distance(trail, c.pos)
        trail = c.pos

    def recall(dt: float, cancel_tick: int = -1, hit_tick: int = -1) -> dict:
        w = staged({BLUE_TOP: top(11000.0), RED_TOP: top(11050.0)}, dt)
        me = w.champs[BLUE_TOP]
        w.submit(BLUE_TOP, RECALL)
        for _ in range(max(cancel_tick, hit_tick, 0)):
            w.step()
        if cancel_tick >= 0:
            w.submit(BLUE_TOP, HOLD)
            w.submit(BLUE_TOP, RECALL)
        after = {}
        if hit_tick >= 0:
            w.submit(RED_TOP, fight(BLUE_TOP))
            w.step()
            w.submit(RED_TOP, HOLD)
            after = {"outcome": me.outcome.name, "outcome_s": me.outcome_tick * dt, "intent_after": me.intent.kind.name,
                     "channel_s": me.channel, "hp_lost": me.max_hp - me.hp}
            for _ in range(round(2 * RECALL_S / dt)):
                w.step()
            after |= {"at_fountain_after_17s_without_a_new_order": me.pos == FOUNTAIN[0], "recall_issued_again_s": w.tick * dt}
            w.submit(BLUE_TOP, RECALL)
        issued = w.tick
        fountain_s = (w.tick + steps_to_fountain(w, BLUE_TOP)) * dt
        return after | {"seconds_from_first_cast": fountain_s, "seconds_from_last_cast": fountain_s - issued * dt,
                        "outcome_at_fountain": me.outcome.name}

    return interval_invariance() | {
        "b_walked_units": walked, "b_speed_times_time": c.speed * 30 * w.dt, "b_first_step_on_new_route_units": reroute_gain,
        "c_uninterrupted": {"dt_0.5": recall(0.5), "dt_1.0": recall(1.0)},
        "c_cancelled_at_7s_then_restarted": recall(0.5, cancel_tick=14),
        "d_hit_once_at_5s": recall(0.5, hit_tick=10),
    }


def retreat(speed_edge: float, lockdown: bool, safety: float) -> dict:
    home = TOWER_S["blue_top_outer"]
    w = staged({BLUE_TOP: top(home + safety), RED_TOP: top(home + safety + 100.0)})
    runner, chaser = w.champs[BLUE_TOP], w.champs[RED_TOP]
    runner.speed += speed_edge
    if not lockdown:
        runner.slow_frac = chaser.slow_frac = 0.0
    w.submit(BLUE_TOP, fight(RED_TOP))
    w.submit(RED_TOP, fight(BLUE_TOP))
    lowest = runner.hp
    while w.tick < 120 and not dead(runner) and not dead(chaser) and runner.pos != FOUNTAIN[0]:
        if runner.hp <= 0.5 * runner.max_hp:
            w.submit(BLUE_TOP, Intent(Kind.MOVE, FOUNTAIN[0]))
        w.step()
        lowest = min(lowest, runner.hp)
    return {"runner_speed_edge": speed_edge, "lockdown": lockdown, "units_to_own_tower": safety,
            "outcome": "death" if dead(runner) else "escape", "runner_lowest_hp": round(max(lowest, 0.0)),
            "chaser_dead": dead(chaser), "seconds": w.tick * w.dt}


def reinforce(d: float | None) -> dict:
    spot = (TOWER_S["blue_top_outer"] + TOWER_S["red_top_outer"]) / 2
    w = staged({BLUE_TOP: top(spot), RED_TOP: top(spot + 100.0)} | ({} if d is None else {BLUE_JUNGLE: top(spot - d)}))
    a, ally, foe = w.champs[BLUE_TOP], w.champs[BLUE_JUNGLE], w.champs[RED_TOP]
    foe.level = 7
    foe.refresh()
    foe.hp = foe.max_hp
    w.submit(BLUE_TOP, fight(RED_TOP))
    w.submit(BLUE_JUNGLE, HOLD if d is None else fight(RED_TOP))
    w.submit(RED_TOP, fight(BLUE_TOP))
    while w.tick < 180 and not foe.deaths and not (a.deaths and (ally.deaths or d is None)):
        if a.deaths and d is not None and BLUE_JUNGLE in w.views[1].enemies:
            w.submit(RED_TOP, fight(BLUE_JUNGLE))
        w.step()
    return {"ally_start_units": d, "foe_dead": bool(foe.deaths), "a_dead": bool(a.deaths), "ally_dead": bool(ally.deaths)}


def tower_duel(under_tower: bool) -> dict:
    s = TOWER_S["blue_top_outer"] + (0.0 if under_tower else 2400.0)
    w = staged({BLUE_TOP: top(s), RED_TOP: top(s + 100.0)})
    defender, attacker = w.champs[BLUE_TOP], w.champs[RED_TOP]
    attacker.level = 2
    attacker.refresh()
    attacker.hp = attacker.max_hp
    w.submit(BLUE_TOP, fight(RED_TOP))
    w.submit(RED_TOP, fight(BLUE_TOP))
    while w.tick < 120 and not dead(defender) and not dead(attacker):
        w.step()
    return {"under_defender_tower": under_tower, "winner": "attacker" if dead(defender) else "defender",
            "attacker_hp": round(attacker.hp), "defender_hp": round(defender.hp), "seconds": w.tick * w.dt}


def gank(at_own_tower: bool, decision_interval: int, health: float) -> dict:
    s = TOWER_S["blue_top_outer"] + 600.0 if at_own_tower else TOWER_S["red_top_outer"] - 900.0
    w = staged({BLUE_TOP: top(s), RED_TOP: top(s + 1000.0), RED_JUNGLE: RIFT.at("top_river")})
    laner, jungler = w.champs[BLUE_TOP], w.champs[RED_JUNGLE]
    laner.hp = health * laner.max_hp
    w.submit(RED_JUNGLE, fight(BLUE_TOP))
    first_seen, lowest = None, laner.hp
    while w.tick < 120 and not dead(laner) and not dead(jungler) and laner.pos != FOUNTAIN[0]:
        spotted = any(e is not None and e.visible and e.id == RED_JUNGLE for e in observe(w, BLUE_TOP).enemies)
        if spotted and first_seen is None:
            first_seen = w.tick * w.dt
        if spotted and w.tick % decision_interval == 0:
            w.submit(BLUE_TOP, Intent(Kind.MOVE, FOUNTAIN[0]))
        if RIFT.distance(jungler.pos, laner.pos) < 1500 and BLUE_TOP in w.views[1].enemies:
            w.submit(RED_TOP, fight(BLUE_TOP))
        w.step()
        lowest = min(lowest, laner.hp)
    return {"laner_at": "own outer tower" if at_own_tower else "enemy outer tower", "decision_interval_ticks": decision_interval, "laner_start_hp": round(laner.max_hp * health),
            "jungler_first_seen_s": first_seen, "laner_survives": not dead(laner), "laner_lowest_hp": round(max(lowest, 0.0)),
            "jungler_survives": not dead(jungler), "seconds": w.tick * w.dt}


def fights() -> dict:
    sweep = [retreat(edge, lockdown, safety) for safety in (1000.0, 2500.0, 4000.0)
             for lockdown in (False, True) for edge in (-20.0, 0.0, 20.0)]
    walk_in = [reinforce(d) for d in range(0, 8001, 250)]
    wins = [r["ally_start_units"] for r in walk_in if r["foe_dead"] and not (r["a_dead"] and r["ally_dead"])]
    saves = [r["ally_start_units"] for r in walk_in if r["foe_dead"] and not r["a_dead"]]
    return {
        "a_retreat_at_half_hp": sweep,
        "a_escapes": sum(r["outcome"] == "escape" for r in sweep), "a_deaths": sum(r["outcome"] == "death" for r in sweep),
        "b_alone": reinforce(None),
        "b_largest_ally_distance_side_wins": max(wins, default=None),
        "b_largest_ally_distance_a_survives": max(saves, default=None),
        "c_same_duel": [tower_duel(False), tower_duel(True)],
        "d_gank": [gank(own, k, health) for health in (1.0, 0.6) for own in (True, False) for k in (1, 5)],
        "e_seat_order": seat_order(),
    }


def hidden_state() -> dict:
    game = World(seed=SEEDS["hidden_state"])
    run(game, scripted, 150)
    a, b = World.restore(game.snapshot()), World.restore(game.snapshot())
    now = a.tick * a.dt
    camp_name = next(n for n, c in a.camps.items() if n.startswith("red") and c.alive and c.aggro < 0)
    fog = next(CAMPS[n].pos for n in CAMPS if n.startswith("red") and n != camp_name
               and RIFT.distance(a.champs[RED_JUNGLE].pos, CAMPS[n].pos) > 1500)
    b.champs[RED_JUNGLE].pos = fog
    camp = b.camps[camp_name]
    camp.alive, camp.cleared_tick, camp.respawn_s = False, b.tick - 1, now + CAMPS[camp_name].respawn_s

    def blue(w: World) -> list:
        return [(encode(o).tobytes(), legal_mask(o).tobytes()) for o in (observe(w, i) for i in range(5))]

    def puppet(o) -> Intent:
        return HOLD if o.me.id == RED_JUNGLE else scripted(o)

    unseen, mismatches = True, 0
    for _ in range(31):
        for w in (a, b):
            w.see()
            unseen &= RED_JUNGLE not in w.views[0].enemies and camp_name not in w.views[0].camps
        mismatches += sum(x != y for x, y in zip(blue(a), blue(b)))
        for w in (a, b):
            run(w, puppet, 1)
    b.champs[RED_JUNGLE].pos = TOWER_POS["blue_mid_inner"]
    b.see()
    return {
        "hidden_camp": camp_name, "jungler_units_apart": RIFT.distance(a.champs[RED_JUNGLE].pos, fog),
        "worlds_differ": a.digest() != b.digest(), "hidden_things_stayed_unseen_by_blue": unseen,
        "ticks_compared": 31, "blue_observation_mismatches": mismatches,
        "blue_observations_differing_after_reveal": sum(x != y for x, y in zip(blue(a), blue(b))),
    }


def last_seen() -> dict:
    w = staged({BLUE_TOP: top(11000.0), RED_TOP: top(11300.0)})
    foe = w.champs[RED_TOP]
    w.submit(RED_TOP, Intent(Kind.MOVE, FOUNTAIN[1]))
    while RED_TOP in w.views[0].enemies:
        last_tick, last_pos = w.tick, foe.pos
        w.step()
    for _ in range(20):
        w.step()
    record, seen = w.memory[0].enemies[RED_TOP], observe(w, BLUE_TOP).enemies[0]
    return {"last_visible_tick": last_tick - 1, "record_tick_20s_later": record.tick,
            "record_pos_is_last_visible_pos": record.pos == last_pos, "units_moved_since": RIFT.distance(record.pos, foe.pos),
            "observation_visible": seen.visible, "observation_age_s": seen.age_s}


def fog_pursuit() -> dict:
    spot = top(11300.0)

    def chase(hideout: str, fog_ticks: int = -1) -> tuple[World, list]:
        w = staged({BLUE_TOP: top(10000.0), RED_TOP: spot})
        pursuer, target = w.champs[BLUE_TOP], w.champs[RED_TOP]
        w.submit(BLUE_TOP, fight(RED_TOP))
        w.step()
        target.pos = RIFT.at(hideout)
        w.see()
        path = []
        while pursuer.intent.kind == Kind.FIGHT and target.hp == target.max_hp and w.tick < 60:
            if len(path) == fog_ticks:
                target.pos = spot
                w.see()
            w.step()
            path.append(pursuer.pos)
        return w, path

    w, path = chase("red_gromp")
    pursuer, target, record = w.champs[BLUE_TOP], w.champs[RED_TOP], w.memory[0].enemies[RED_TOP]
    arrived = next(i for i, pos in enumerate(path) if RIFT.distance(pos, record.pos) <= pursuer.range + 1e-6)
    lost = {"target_visible": RED_TOP in w.views[0].enemies, "last_seen_pos_is_where_the_target_stood": record.pos == spot,
            "pursuer_attack_range": pursuer.range,
            "pursuer_units_from_last_seen_spot": RIFT.distance(pursuer.pos, record.pos),
            "pursuer_units_from_true_position": RIFT.distance(pursuer.pos, target.pos),
            "same_path_with_the_target_hidden_elsewhere": path == chase("red_base")[1],
            "arrived_s": (w.tick - len(path) + arrived) * w.dt, "outcome": pursuer.outcome.name,
            "outcome_s": pursuer.outcome_tick * w.dt, "intent_after": pursuer.intent.kind.name}
    w, path = chase("red_gromp", fog_ticks=2)
    pursuer, target = w.champs[BLUE_TOP], w.champs[RED_TOP]
    back = {"ticks_in_fog": 2, "units_from_last_seen_spot_when_the_target_reappeared": RIFT.distance(path[1], spot),
            "outcome": pursuer.outcome.name, "intent": pursuer.intent.kind.name, "target_hp_lost": target.max_hp - target.hp,
            "first_hit_s": (w.tick - 1) * w.dt}
    return {"target_stays_in_fog": lost, "target_reappears_before_arrival": back}


def camp_timer(name: str) -> dict:
    info = CAMPS[name]
    w = staged({BLUE_JUNGLE: info.pos})
    camp, enemy = w.camps[name], w.memory[1].camps[name]
    waited = 0
    while camp.cleared_tick < 0:
        w.submit(BLUE_JUNGLE, Intent(Kind.CAMP, name))
        w.step()
        waited += w.champs[BLUE_JUNGLE].outcome_tick == w.tick - 1 and w.champs[BLUE_JUNGLE].outcome == Outcome.ABSENT
    out = {"camp": name, "ticks_ended_absent_before_the_spawn": waited, "outcome_at_clear": w.champs[BLUE_JUNGLE].outcome.name, "clear_s": camp.cleared_tick * w.dt, "respawn_s": camp.respawn_s, "window_s": info.window_s,
           "clearing_team_knows_s": w.memory[0].camps[name].respawn_s, "enemy_believes_before_looking_s": enemy.respawn_s}
    w.submit(BLUE_JUNGLE, Intent(Kind.MOVE, FOUNTAIN[0]))
    w.champs[RED_MID].pos = info.pos
    w.step()
    out["enemy_knows_on_first_look_s"] = enemy.respawn_s
    while enemy.respawn_s is None and not camp.alive:
        w.step()
    return out | {"enemy_learns_at_s": (w.tick - 1) * w.dt, "enemy_learns_s": enemy.respawn_s}


def ward_reveal() -> dict:
    target = RIFT.at("red_raptors")
    w = staged({BLUE_SUPPORT: RIFT.at("red_mid_t1"), RED_MID: target})
    hidden_before = RED_MID not in w.views[0].enemies
    w.submit(BLUE_SUPPORT, Intent(Kind.WARD, target))
    while not w.sources:
        w.step()
    placed_tick = w.tick - 1
    w.champs[BLUE_SUPPORT].pos = FOUNTAIN[0]
    w.submit(BLUE_SUPPORT, HOLD)
    seen_ticks = []
    for _ in range(120):
        w.step()
        if RED_MID in w.views[0].enemies:
            seen_ticks.append(w.tick - 1)
    return {"hidden_before_ward": hidden_before, "ward_placed_s": placed_tick * w.dt,
            "revealed_until_s": (seen_ticks[-1] + 1) * w.dt, "revealed_for_s": (seen_ticks[-1] + 1 - placed_tick) * w.dt,
            "ticks_seen_with_ward_as_only_source": len(seen_ticks), "hidden_after_expiry": RED_MID not in w.views[0].enemies,
            "charges_left": w.champs[BLUE_SUPPORT].wards}


def information() -> dict:
    return {"a_hidden_state": hidden_state(), "b_last_seen": last_seen(),
            "c_camp_timers": [camp_timer("blue_gromp"), camp_timer("blue_blue")], "d_ward": ward_reveal(),
            "e_pursuit_of_a_target_in_fog": fog_pursuit()}


def seat_order() -> dict:
    """Each fight is staged twice with the two sides' seats exchanged, so the code visits the other side first."""
    river = RIFT.lane_s("mid", RIFT.at("mid_river"))
    top_role, jungle_role, mid_role = 0, 1, 2
    kite_to = Intent(Kind.MOVE, RIFT.at("top_river"))
    cases = {
        "duel": [(top_role, 0, -200.0, mid_role), (mid_role, 1, 200.0, top_role)],
        "kite": [(top_role, 0, -200.0, mid_role), (mid_role, 1, 200.0, kite_to)],
        "two_on_one": [(top_role, 0, -100.0, mid_role), (jungle_role, 0, -400.0, mid_role), (mid_role, 1, 200.0, top_role)],
        "both_die_on_one_tick": [(top_role, 0, -50.0, mid_role), (mid_role, 1, 50.0, top_role)],
    }

    def trace(name: str, first_side: int) -> list:
        cast = cases[name]
        seat = {role: (first_side ^ side) * 5 + role for role, side, _, _ in cast}
        w = staged({seat[role]: RIFT.lane_pos("mid", river + offset) for role, _, offset, _ in cast})
        fighters = [w.champs[seat[role]] for role, *_ in cast]
        for c, (_, _, _, order) in zip(fighters, cast):
            if name == "both_die_on_one_tick":
                c.hp = 1.0
            w.submit(c.id, order if isinstance(order, Intent) else fight(seat[order]))
        rows = []
        while w.tick < 40 and not any(dead(c) for c in fighters):
            w.step()
            rows.append([(None if dead(c) else c.pos, c.hp, c.gold, c.level, c.xp, dead(c)) for c in fighters])
        return rows

    out = {}
    for name, cast in cases.items():
        a, b = trace(name, 0), trace(name, 1)
        fields = ("pos", "hp", "gold", "level", "xp", "dead")
        differences = [{"tick": t, "role": ROLES[role], "field": field, "top_side_visited_first": str(x), "mid_side_visited_first": str(y)}
                       for t, (row_a, row_b) in enumerate(zip(a, b)) for (role, *_), ca, cb in zip(cast, row_a, row_b)
                       for field, x, y in zip(fields, ca, cb) if x != y]
        out[name] = {"ticks_compared": len(a), "same_length": len(a) == len(b), "ended_in_a_death": any(c[5] for c in a[-1]),
                     "differences": differences}
    return out


def nearest_exit(o, away: list) -> Intent:
    return min(away, key=lambda a: RIFT.distance(o.me.pos, a.target))


def anywhere(o, away: list) -> Intent:
    return away[int(keyed_uniform(0, Stream.POLICY, o.me.id, int(o.time)) * len(away))]


def abandoner(pick):
    """A policy that walks off its home lane whenever the mask lets it, and farms the home lane only when it must."""
    def policy(o) -> Intent:
        home = ROLE_LANE.get(ROLES[o.me.id % 5])
        away = [a for a, legal in zip(actions(o.me.id // 5), legal_mask(o))
                if legal and a.kind == Kind.MOVE and a.target not in FOUNTAIN and not (home and on_lane(home, a.target))]
        return pick(o, away) if away else Intent(Kind.FARM, (home, "last_hit"))
    return policy


class FlooredWorld(World):
    """The roam rule as first written: the allowance stops at zero. Kept to show why the kernel lets it go into debt."""

    def step(self) -> None:
        super().step()
        for c in self.champs:
            c.roam = max(0.0, c.roam)


def duty_soak(policy, seconds: float, dt: float, decision_interval: int, world=World) -> dict:
    """Per-champion duty bookkeeping over one game, measured from outside the kernel."""
    w = world(seed=SEEDS["role_duty_soak"], dt=dt, decision_interval=decision_interval)
    rows = [{"in_state_s": dict.fromkeys(Duty, 0.0), "off_lane_alive_s": 0.0, "roamed_since_lane_s": 0.0,
             "longest_roam_between_lane_visits_s": 0.0, "lowest_allowance_s": ROAM_CAP_S, "exhausted_at_s": None,
             "roamed_after_exhaustion_s": 0.0, "largest_step_over_speed": 0.0, "deaths_or_recalls": 0,
             "always_unrestricted": True, "illegal_choices": 0} for _ in w.champs]
    for _ in range(round(seconds / dt)):
        before = [c.pos for c in w.champs]
        if w.tick % decision_interval == 0:
            chosen = []
            for c, row in zip(w.champs, rows):
                o = observe(w, c.id)
                table, mask = actions(c.team), legal_mask(o)
                row["always_unrestricted"] &= all(legal for a, legal in zip(table, mask) if a.kind not in (Kind.FIGHT, Kind.WARD))
                chosen.append(policy(o))
                row["illegal_choices"] += not mask[table.index(chosen[-1])]
            for c, action in zip(w.champs, chosen):
                w.submit(c.id, action)
        w.step()
        for c, row, old in zip(w.champs, rows, before):
            state, home = duty(c), ROLE_LANE.get(c.role)
            row["in_state_s"][state] += dt
            if home and c.respawn_tick < 0 and not on_lane(home, c.pos):
                row["off_lane_alive_s"] += dt
            row["roamed_since_lane_s"] = 0.0 if state == Duty.IN_LANE else row["roamed_since_lane_s"] + dt * (state == Duty.ROAMING)
            row["longest_roam_between_lane_visits_s"] = max(row["longest_roam_between_lane_visits_s"], row["roamed_since_lane_s"])
            row["lowest_allowance_s"] = min(row["lowest_allowance_s"], c.roam)
            if row["exhausted_at_s"] is not None:
                row["roamed_after_exhaustion_s"] += dt * (state == Duty.ROAMING)
            elif c.roam <= 0:
                row["exhausted_at_s"] = w.tick * dt
            if c.outcome_tick == w.tick - 1 and c.outcome in (Outcome.DIED, Outcome.RECALLED):
                row["deaths_or_recalls"] += 1
            else:
                row["largest_step_over_speed"] = max(row["largest_step_over_speed"], RIFT.distance(old, c.pos) / (c.speed * dt))
    out = []
    for c, row in zip(w.champs, rows):
        window = None if row["exhausted_at_s"] is None else seconds - row["exhausted_at_s"]
        row |= {"seat": c.id, "role": c.role, "in_state_s": {state.name: s for state, s in row["in_state_s"].items()},
                "roaming_share": row["in_state_s"][Duty.ROAMING] / seconds, "off_lane_alive_share": row["off_lane_alive_s"] / seconds,
                "roaming_share_after_exhaustion": None if not window else row["roamed_after_exhaustion_s"] / window,
                "window_after_exhaustion_s": window, "final_allowance_s": c.roam}
        del row["roamed_since_lane_s"]
        out.append(row)
    return {"game_s": seconds, "tick_s": dt, "decision_every_s": decision_interval * dt, "champions": out}


def realistic_roam() -> dict:
    """A mid laner walks to the bot river, waits 15 s, and walks back, deciding every 2 s. Every choice is checked against the mask."""
    river = RIFT.lane_s("mid", RIFT.at("mid_river"))
    w = staged({BLUE_MID: RIFT.lane_pos("mid", river - 1500.0)}, dt=0.5)
    me, table = w.champs[BLUE_MID], actions(0)
    go, back = Intent(Kind.MOVE, RIFT.at("bot_river")), Intent(Kind.FARM, ("mid", "last_hit"))
    arrived_s, returned_s, roamed_s, legal, decisions = None, None, 0.0, 0, 0
    while returned_s is None and w.tick < 400:
        now = w.tick * w.dt
        if w.tick % 4 == 0:
            if arrived_s is None and me.outcome == Outcome.ARRIVED:
                arrived_s = me.outcome_tick * w.dt
            action = go if me.outcome != Outcome.ARRIVED else KEEP if now < arrived_s + 15.0 else back
            legal += bool(legal_mask(observe(w, BLUE_MID))[table.index(action)])
            decisions += 1
            w.submit(BLUE_MID, action)
        w.step()
        roamed_s += w.dt * (duty(me) == Duty.ROAMING)
        if arrived_s is not None and duty(me) == Duty.IN_LANE:
            returned_s = w.tick * w.dt
    return {"walk_units_each_way_off_the_lane": RIFT.distance(RIFT.at("mid_river"), RIFT.at("bot_river")), "arrived_s": arrived_s,
            "back_on_lane_s": returned_s, "decisions": decisions, "legal_decisions": legal, "seconds_charged_as_roaming": roamed_s,
            "allowance_left_s": me.roam, "allowance_cap_s": ROAM_CAP_S}


def role_duty() -> dict:
    clocks = {"tick_1.0_decision_5": (1.0, 5), "tick_0.5_decision_4": (0.5, 4)}
    policies = {"abandoner_nearest_exit": abandoner(nearest_exit), "abandoner_anywhere": abandoner(anywhere), "scripted": scripted}

    def floored(policy, dt: float, n: int) -> dict:
        laners = [c for c in duty_soak(policy, 1800.0, dt, n, FlooredWorld)["champions"] if c["role"] != "jungle"]
        return {key: [min(c[key] for c in laners), max(c[key] for c in laners)]
                for key in ("roaming_share_after_exhaustion", "off_lane_alive_share")}

    return {"roam_cap_s": ROAM_CAP_S, "roam_refill_per_s_on_lane": ROAM_REFILL, "share_limit": ROAM_REFILL / (1 + ROAM_REFILL),
            "a_soak": {clock: {name: duty_soak(policy, 1800.0, dt, n) for name, policy in policies.items()}
                       for clock, (dt, n) in clocks.items()},
            "a_lowest_and_highest_laner_share_if_the_allowance_stopped_at_zero":
                {clock: {name: floored(policy, dt, n) for name, policy in policies.items() if name != "scripted"}
                 for clock, (dt, n) in clocks.items()},
            "d_realistic_roam": realistic_roam()}


def snapshots(lane_factory=StubLane) -> dict:
    game = World(seed=SEEDS["snapshot"], lane_factory=lane_factory)
    run(game, scripted, 300)
    snap = game.snapshot()
    first, again = digests(game, scripted, 300), digests(World.restore(snap), scripted, 300)

    def pushing_top(o) -> Intent:
        return Intent(Kind.FARM, ("top", "push")) if o.me.id == BLUE_TOP else scripted(o)

    def lane(name: str):
        return lambda w: fingerprint(w.lanes[name])

    def bot_lane(w: World) -> str:
        return fingerprint((w.lanes["bot"], [w.champs[i] for i in BOT_LANE_CHAMPS]))

    def first_split(part) -> float | None:
        base, branch = World.restore(snap), World.restore(snap)
        pairs = zip(digests(base, scripted, 300, part), digests(branch, pushing_top, 300, part))
        return next((tick * base.dt for tick, (x, y) in enumerate(pairs) if x != y), None)

    return {"a_ticks_replayed": len(first), "a_ticks_matching": sum(x == y for x, y in zip(first, again)),
            "a_snapshot_bytes": len(snap), "b_window_s": 300.0,
            "b_top_lane_first_differs_after_s": first_split(lane("top")),
            "b_bot_lane_first_differs_after_s": first_split(bot_lane)}


def main() -> None:
    results = {"q1_timing": timing(), "q2_fights": fights(), "q3_information": information(), "q4_snapshot": snapshots(),
               "q1_timing_real_lane": interval_invariance(RealLane), "q4_snapshot_real_lane": snapshots(RealLane),
               "role_duty": role_duty(), "hindsight": hindsight.measure()}
    config = {"tick_s": 1.0, "decision_interval_ticks": 5, "exceptions": "staged scenes take orders by hand on any tick, "
              "recall and the realistic roam run at a 0.5 s tick, the role duty soak runs at both clocks, "
              "and the interval test runs at intervals 1, 2, 4, and 10",
              "lane_model": "stub, and real for the two *_real_lane sections", "interval_ticks_compared": 300,
              "roam_cap_s": ROAM_CAP_S, "roam_refill": ROAM_REFILL, "role_duty_soak_game_s": 1800.0,
              "hindsight_rollouts": hindsight.ROLLOUTS, "hindsight_horizon_s": hindsight.HORIZON_S, "seeds_by_use": SEEDS}
    results["run"] = stamp(sorted({s for v in SEEDS.values() for s in (v if isinstance(v, list) else [v])}), config)
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps(results, indent=1))
    print(f"wrote {', '.join(results)} to {RESULTS}")


if __name__ == "__main__":
    main()
