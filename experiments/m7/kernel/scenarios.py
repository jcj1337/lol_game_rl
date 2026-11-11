"""Measurements for M7 questions Q1 to Q4. Run as a module to write them to results/kernel.json."""

import json
from pathlib import Path

from experiments.m7.kernel.lanes import TEAMS, RealLane, StubLane
from experiments.m7.kernel.observe import MODES, encode, legal_mask, observe, run
from experiments.m7.kernel.policy import scripted
from experiments.m7.kernel.profiles import ROLE_LANE, ROLES
from experiments.m7.kernel.world import CAMPS, FOUNTAIN, HOLD, MAP, RECALL, RIFT, TOWER_POS, Intent, Kind, World, fingerprint

RESULTS = Path(__file__).parent / "results" / "kernel.json"
TOWER_S = {t.name: t.s for t in MAP.towers}
BLUE_TOP, BLUE_JUNGLE, BLUE_SUPPORT, RED_TOP, RED_JUNGLE, RED_MID = 0, 1, 4, 5, 6, 7
BOT_LANE_CHAMPS = (3, 4, 8, 9)


def top(s: float):
    return RIFT.lane_pos("top", s)


def fight(cid: int) -> Intent:
    return Intent(Kind.FIGHT, cid)


def staged(places: dict, dt: float = 1.0) -> World:
    """A world with the named champions moved to their marks. Everyone else holds at the fountain."""
    w = World(seed=1, dt=dt, decision_interval=1)
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


def interval_invariance(lane_factory=StubLane) -> dict:
    def trajectory(policy, k: int) -> list[str]:
        return digests(World(seed=3, decision_interval=k, lane_factory=lane_factory), policy, 300)

    base = trajectory(fixed_schedule, 1)
    return {"a_ticks_compared": len(base),
            "a_identical_to_interval_1": {k: trajectory(fixed_schedule, k) == base for k in (5, 10)},
            "a_reactive_policy_differs_between_interval_1_and_10": trajectory(scripted, 1)[-1] != trajectory(scripted, 10)[-1]}


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
        w.submit(BLUE_TOP, RECALL)
        for _ in range(max(cancel_tick, hit_tick, 0)):
            w.step()
        if cancel_tick >= 0:
            w.submit(BLUE_TOP, HOLD)
            w.submit(BLUE_TOP, RECALL)
        if hit_tick >= 0:
            w.submit(RED_TOP, fight(BLUE_TOP))
            w.step()
            w.submit(RED_TOP, HOLD)
        me = w.champs[BLUE_TOP]
        after = {"channel_s": me.channel, "hp_lost": me.max_hp - me.hp}
        return after | {"seconds_from_first_cast": (w.tick + steps_to_fountain(w, BLUE_TOP)) * dt}

    return interval_invariance() | {
        "b_walked_units": walked, "b_speed_times_time": c.speed * 30 * w.dt, "b_first_step_on_new_route_units": reroute_gain,
        "c_uninterrupted_s": {"dt_0.5": recall(0.5)["seconds_from_first_cast"], "dt_1.0": recall(1.0)["seconds_from_first_cast"]},
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
        if a.deaths:
            w.submit(BLUE_TOP, HOLD)
            w.submit(RED_TOP, HOLD if d is None else fight(BLUE_JUNGLE))
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
        if RIFT.distance(jungler.pos, laner.pos) < 1500:
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
    }


def hidden_state() -> dict:
    game = World(seed=5)
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
    w = staged({BLUE_TOP: top(11000.0), RED_TOP: top(11300.0)})
    pursuer, target = w.champs[BLUE_TOP], w.champs[RED_TOP]
    w.submit(BLUE_TOP, fight(RED_TOP))
    w.step()
    last_seen_pos = w.memory[0].enemies[RED_TOP].pos
    target.pos = RIFT.at("red_gromp")
    w.see()
    for _ in range(40):
        w.step()
    return {"target_visible": RED_TOP in w.views[0].enemies,
            "pursuer_units_from_last_seen_spot": RIFT.distance(pursuer.pos, last_seen_pos),
            "pursuer_units_from_true_position": RIFT.distance(pursuer.pos, target.pos)}


def camp_timer(name: str) -> dict:
    info = CAMPS[name]
    w = staged({BLUE_JUNGLE: info.pos})
    camp, enemy = w.camps[name], w.memory[1].camps[name]
    w.submit(BLUE_JUNGLE, Intent(Kind.CAMP, name))
    while camp.cleared_tick < 0:
        w.step()
    out = {"camp": name, "clear_s": camp.cleared_tick * w.dt, "respawn_s": camp.respawn_s, "window_s": info.window_s,
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


def snapshots(lane_factory=StubLane) -> dict:
    game = World(seed=7, lane_factory=lane_factory)
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
    results = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    results |= {"q1_timing": timing(), "q2_fights": fights(), "q3_information": information(), "q4_snapshot": snapshots(),
                "q1_timing_real_lane": interval_invariance(RealLane), "q4_snapshot_real_lane": snapshots(RealLane)}
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps(results, indent=1))
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
