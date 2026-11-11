"""Does a comparison of alternatives use what the deciding team could not know? A demonstration for section 9.3.

`known` is the only function here that reads a true World. `hypothesis` takes its result and a rollout index, so a
rollout world cannot depend on anything hidden from the deciding team. `position_only` is the design under review.
It moves one hidden enemy and keeps every other true field. This is not the M8 harness.
"""

import math
import pickle
from typing import NamedTuple

from riftgame.map import Pos
from riftgame.rng import Stream, keyed_uniform

from experiments.m7.kernel.lanes import StubLane
from experiments.m7.kernel.observe import encode, legal_mask, observe, run
from experiments.m7.kernel.policy import scripted
from experiments.m7.kernel.profiles import ROLES, STATS, UPGRADES, stats
from experiments.m7.kernel.world import (CAMPS, FOUNTAIN, HOLD, RIFT, E, Intent, Kind, LastSeen, Source, TeamMemory, V, World,
                                         fingerprint, in_sight)

BLUE_TOP, BLUE_JUNGLE, RED_JUNGLE = 0, 1, 6
BASE_SEED, ROLLOUTS, HORIZON_S, LAST_SEEN_AGO_S = 11, 16, 45.0, 6.0
ALTERNATIVES = {"farm": Intent(Kind.FARM, ("top", "last_hit")), "retreat": Intent(Kind.MOVE, RIFT.at("blue_top_t1"))}
SPEED = STATS.index("speed")
GRID = [Pos(e, step * 250.0) for e, edge in enumerate(RIFT.edges) for step in range(int(edge.length // 250.0) + 1)]

# Beliefs about what is hidden. Each is a stated guess from the team's own information, not an inference.
# (weight, healed to full, upgrades bought) for an enemy champion since it was last seen.
ENEMY_BELIEFS = ((0.5, False, 0), (0.25, True, 0), (0.25, True, 1))
CAMP_UP = 0.5   # chance that a camp is alive when the team has no current sight of it and knows no timer
ENEMY_KEY, CAMP_KEY = 1, 2


class Known(NamedTuple):
    """What one team may use at a decision: its own side, what it sees now, its memory, and public facts."""

    team: int
    dt: float
    decision_interval: int
    tick: int
    first_blood: bool
    own: list            # the team's five Champion objects
    public: list         # (kills, deaths, respawn_tick) of each enemy champion
    visible: tuple       # the enemy champions in view
    memory: TeamMemory   # last-seen records of enemies, and what the team knows of each camp
    lanes: dict          # per lane: its clock, the own minion groups, the enemy groups in view, own towers' state, and whether each enemy tower stands
    engaged: dict        # (hp, aggro) of each camp that an own champion is fighting
    sources: list        # own wards and shrines
    enemy_wards: tuple   # positions of the enemy wards in view


def known(world: World, team: int) -> Known:
    if not all(type(lane) is StubLane for lane in world.lanes.values()):
        raise NotImplementedError("the demonstration knows only the stub lane's state")
    src = world.watchers(team)[1]
    lanes = {}
    for name, lane in world.lanes.items():
        spots = [(group, RIFT.lane_pos(name, group[0])) for group in lane.groups[1 - team]]
        in_view = [group for group, pos in spots if in_sight(src, *RIFT.xy(pos), pos)]
        # an enemy tower is known only as standing or fallen, which is all that `observe` gives
        towers = [(t.hp, t.target, t.ramp) if t.team == team else t.hp > 0 for t in lane.towers]
        lanes[name] = (lane.tick, lane.next_spawn_s, lane.groups[team], in_view, towers)
    own, foes = world.champs[team * 5:team * 5 + 5], world.champs[5 - team * 5:10 - team * 5]
    info = Known(team, world.dt, world.decision_interval, world.tick, world.first_blood, own,
                 [(c.kills, c.deaths, c.respawn_tick) for c in foes], world.views[team].enemies, world.memory[team], lanes,
                 {name: (camp.hp, camp.aggro) for name, camp in world.camps.items() if camp.aggro >= 0 and camp.aggro // 5 == team},
                 [s for s in world.sources if s.team == team], world.views[team].wards)
    return pickle.loads(pickle.dumps(info))


def draw(k: int, *key: int) -> float:
    return keyed_uniform(0, Stream.HIDDEN_STATE, k, *key)


def last_seen(info: Known, cid: int) -> LastSeen:
    """The team's record of an enemy. One it has never seen was at its fountain, untouched, when the game began."""
    return info.memory.enemies.get(cid) or LastSeen(FOUNTAIN[cid // 5], 0, math.inf, 1, 0)


def belief(u: float) -> tuple[bool, int]:
    for weight, healed, bought in ENEMY_BELIEFS:
        if u < weight:
            return healed, bought
        u -= weight
    return ENEMY_BELIEFS[-1][1:]


def unseen_position(info: Known, src: list, cid: int, k: int) -> Pos:
    """A spot the enemy could have walked to since it was last seen, and that the team's vision does not cover."""
    seen = last_seen(info, cid)
    reach = stats(ROLES[cid % 5], seen.level, seen.upgrades)[SPEED] * (info.tick - seen.tick) * info.dt
    spots = [p for p in GRID if RIFT.distance(seen.pos, p) <= reach and not in_sight(src, *RIFT.xy(p), p)]
    if not spots:
        raise ValueError(f"champion {cid} has nowhere to be that its last-seen record and the team's vision both allow")
    return spots[int(draw(k, ENEMY_KEY, cid) * len(spots))]


def position_only(world: World, info: Known, cid: int, k: int) -> World:
    w = World.restore(world.snapshot())
    w.champs[cid].pos = unseen_position(info, w.watchers(info.team)[1], cid, k)
    w.see()
    return w


def hypothesis(info: Known, k: int) -> World:
    """Rollout world `k`: what the team knows, and one keyed guess at everything it does not."""
    info = pickle.loads(pickle.dumps(info))
    team, foe, now = info.team, 1 - info.team, info.tick * info.dt
    w = World(seed=k, dt=info.dt, decision_interval=info.decision_interval)
    w.tick, w.first_blood = info.tick, info.first_blood
    w.memory = tuple(info.memory if side == team else TeamMemory() for side in (0, 1))
    w.champs[team * 5:team * 5 + 5] = info.own
    expires = info.tick + round(V["ward_duration_s"][0] / info.dt)
    w.sources = info.sources + [Source(foe, p, *RIFT.xy(p), V["ward_sight_range"], expires, True) for p in info.enemy_wards]
    for name, (tick, next_spawn_s, own, in_view, towers) in info.lanes.items():
        lane = w.lanes[name]
        lane.tick, lane.next_spawn_s = tick, next_spawn_s
        lane.groups[team][:], lane.groups[foe][:] = own, in_view
        for tower, state in zip(lane.towers, towers):
            if tower.team == team:
                tower.hp, tower.target, tower.ramp = state
            elif not state:
                tower.hp = 0.0
    src = w.watchers(team)[1]

    for name, lane in w.lanes.items():
        # An enemy wave out of view has marched as far from its spawn as the own wave that spawned with it.
        for s, hp in info.lanes[name][2]:
            twin = lane.spawn_s[foe] + lane.spawn_s[team] - s
            pos = RIFT.lane_pos(name, twin)
            if not in_sight(src, *RIFT.xy(pos), pos):
                lane.groups[foe].append([twin, hp])
        lane.groups[foe].sort(key=lambda g: g[0], reverse=foe == 0)

    for i, (name, m) in enumerate(info.memory.camps.items()):
        camp, kind = w.camps[name], CAMPS[name]
        if name in info.engaged:
            camp.alive, (camp.hp, camp.aggro) = True, info.engaged[name]
            continue
        if m.respawn_s is not None and m.respawn_s > now:
            camp.alive, camp.respawn_s = False, m.respawn_s
        else:
            camp.alive = m.alive if m.seen_tick == info.tick else draw(k, CAMP_KEY, i, 0) < CAMP_UP
            # A team that sees a dead camp without learning its timer knows that the respawn is further off than the window.
            camp.respawn_s = now + kind.window_s + draw(k, CAMP_KEY, i, 1) * (kind.respawn_s - kind.window_s)
        camp.hp = kind.hp if camp.alive else 0.0

    passive = E["passive_gold_per_10s"] / 10 * max(0.0, now - E["passive_gold_start_s"])
    for c, (kills, deaths, respawn_tick) in zip(w.champs[foe * 5:foe * 5 + 5], info.public):
        seen = last_seen(info, c.id)
        c.kills, c.deaths, c.respawn_tick, c.level, c.upgrades, hp = kills, deaths, respawn_tick, seen.level, seen.upgrades, seen.hp
        if respawn_tick >= 0:
            hp = 0.0
        elif c.id in info.visible:
            c.pos = seen.pos
        else:
            c.pos = unseen_position(info, src, c.id, k)
            healed, bought = belief(draw(k, ENEMY_KEY, c.id, 1))
            hp = math.inf if healed else hp
            c.upgrades = min(c.upgrades + bought, len(UPGRADES[c.role]))
        c.refresh()
        c.hp = min(hp, c.max_hp)
        # Gold is never observed. The guess is passive income alone, less the upgrades the enemy is believed to own.
        c.gold = max(0.0, E["starting_gold"] + passive - sum(cost for cost, _ in UPGRADES[c.role][:c.upgrades]))
    w.see()
    return w


def team_sees(w: World, team: int) -> list:
    return [(encode(o).tobytes(), legal_mask(o).tobytes()) for o in (observe(w, i) for i in range(team * 5, team * 5 + 5))]


def total_xp(c) -> float:
    return c.xp + sum(E["xp_first_level_up"] + E["xp_level_up_step"] * (level - 1) for level in range(1, c.level))


def consequences(w: World, seat: int, action: Intent) -> tuple:
    """(survived, health, gold, XP) of the deciding champion after it holds `action` for the horizon. Everyone else is scripted."""
    me, deaths = w.champs[seat], w.champs[seat].deaths
    run(w, lambda o: action if o.me.id == seat else scripted(o), round(HORIZON_S / w.dt))
    return me.deaths == deaths, me.hp, me.gold, total_xp(me)


def report(rollout_world, source: World, seat: int) -> dict:
    """`rollout_world(k)` builds world k. Each alternative gets its consequences in every rollout."""
    before = team_sees(source, seat // 5)
    rows = {name: [consequences(rollout_world(k), seat, action) for k in range(ROLLOUTS)] for name, action in ALTERNATIVES.items()}
    return {"rows": rows, "deciding_team_sees_the_source_state_in_every_rollout_world":
            all(team_sees(rollout_world(k), seat // 5) == before for k in range(ROLLOUTS))}


def decision_point() -> tuple[World, World, dict]:
    """W1, a second world W2 that differs from it only in what blue cannot see, and the fields that were changed."""
    w1 = World(seed=BASE_SEED)
    run(w1, scripted, 240)
    laner, jungler = w1.champs[BLUE_TOP], w1.champs[RED_JUNGLE]
    laner.pos, laner.hp = RIFT.lane_pos("top", w1.views[0].fronts["top"][0]), 0.55 * laner.max_hp
    river, corner = RIFT.at("top_river"), RIFT.at("top_corner")
    jungler.pos, jungler.hp, jungler.gold = RIFT.advance(river, corner, 1500.0), 0.8 * jungler.max_hp, 100.0
    w1.see()
    w1.submit(RED_JUNGLE, HOLD)
    ago = round(LAST_SEEN_AGO_S / w1.dt)
    w1.memory[0].enemies[RED_JUNGLE] = LastSeen(RIFT.advance(river, corner, 2000.0), w1.tick - ago, jungler.hp, jungler.level,
                                                jungler.upgrades)
    staged = (laner.respawn_tick < 0 and jungler.respawn_tick < 0 and RED_JUNGLE not in w1.views[0].enemies
              and BLUE_TOP in w1.views[1].enemies and "red_raptors" not in w1.views[0].camps and w1.camps["red_raptors"].aggro < 0)
    if not staged:
        raise RuntimeError("the staged decision point no longer holds: the jungler and the camp must be hidden, the laner seen")

    w2 = World.restore(w1.snapshot())
    jungler, camp, now = w2.champs[RED_JUNGLE], w2.camps["red_raptors"], w2.tick * w2.dt
    changed = {"red_jungler_hp": (w1.champs[RED_JUNGLE].hp, 0.3 * jungler.max_hp), "red_jungler_gold": (100.0, 900.0),
               "red_jungler_upgrades": (jungler.upgrades, jungler.upgrades + 1), "red_raptors_alive": (camp.alive, not camp.alive),
               "red_memory_of_the_blue_jungler_tick": (getattr(w1.memory[1].enemies.get(BLUE_JUNGLE), "tick", None), 0)}
    tower = next(t for t in w2.lanes["bot"].towers if t.team == 1 and t.tier == "outer")
    changed["red_bot_outer_tower_hp"] = (tower.hp, tower.hp - 1000.0)
    tower.hp -= 1000.0
    jungler.upgrades += 1
    jungler.refresh()
    jungler.hp, jungler.gold = 0.3 * jungler.max_hp, 900.0
    if camp.alive:
        camp.alive, camp.hp, camp.cleared_tick, camp.respawn_s = False, 0.0, w2.tick - 1, now + 100.0
    else:
        camp.alive, camp.hp = True, CAMPS["red_raptors"].hp
    w2.memory[1].enemies[BLUE_JUNGLE] = LastSeen(FOUNTAIN[0], 0, 1.0, 1, 0)
    return w1, w2, changed


def summary(rows: list) -> dict:
    return {name: sum(row[i] for row in rows) / len(rows) for i, name in enumerate(("survived", "health", "gold", "xp"))}


def measure() -> dict:
    w1, w2, changed = decision_point()
    info1, info2 = known(w1, 0), known(w2, 0)
    out = {"decision": {"seat": BLUE_TOP, "game_s": w1.tick * w1.dt, "tick_s": w1.dt, "decision_every_s": w1.decision_interval * w1.dt,
                        "horizon_s": HORIZON_S, "rollouts": ROLLOUTS, "alternatives": list(ALTERNATIVES),
                        "red_jungler_last_seen_s_ago": LAST_SEEN_AGO_S, "laner_health_share": 0.55},
           "w1_w2": {"hidden_fields_changed_w1_to_w2": {name: list(pair) for name, pair in changed.items()},
                     "worlds_differ": w1.digest() != w2.digest(),
                     "blue_observations_and_masks_identical": team_sees(w1, 0) == team_sees(w2, 0),
                     "blue_knowledge_identical": fingerprint(info1) == fingerprint(info2)}}
    comparisons = {"a_position_only": lambda w, info: lambda k: position_only(w, info, RED_JUNGLE, k),
                   "b_truth_blind": lambda w, info: lambda k: hypothesis(info, k)}
    for name, rollout_world in comparisons.items():
        first, second = report(rollout_world(w1, info1), w1, BLUE_TOP), report(rollout_world(w2, info2), w2, BLUE_TOP)
        out[name] = {
            "w1": {alt: summary(rows) for alt, rows in first["rows"].items()},
            "w2": {alt: summary(rows) for alt, rows in second["rows"].items()},
            "reports_identical": first["rows"] == second["rows"],
            "rollouts_that_differ": {alt: sum(x != y for x, y in zip(first["rows"][alt], second["rows"][alt])) for alt in ALTERNATIVES},
            "deciding_team_sees_the_source_state_in_every_rollout_world":
                first["deciding_team_sees_the_source_state_in_every_rollout_world"]
                and second["deciding_team_sees_the_source_state_in_every_rollout_world"]}
    return out
