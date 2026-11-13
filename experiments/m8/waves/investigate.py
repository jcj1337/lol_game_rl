"""M8 wave investigation: the lane without champions.

Each section answers one question with a run that this file reproduces. The questions about champions (stacking,
holding, bouncing, and the diagnostics on them) are in `capabilities.py`, which drives a full world.
  fights         How long does a placed minion fight last, and do the rule variants change it?
  natural_fight  How long does the untouched first-wave fight last on the natural clock, and what is left of it when wave 2 arrives?
  arrivals       When does each wave reach the centre and the tower edges?
  attack_timing  How many casts are cancelled and missiles lost in an untouched lane, and how often would bodies overlap?
  untouched      Where does a lane go when nobody touches it, and how large are its crashes?
  bends          Which bend of a lane tips an untouched lane under straight-line ranges: by its place, by its angle,
                 in pairs, mirrored, with red on a mirrored path, with the walk to the centre a little shorter or longer?
  drift          Where do the two waves of an untouched lane stop being mirror images, and which rule acted there?
  level_lead     What does the pushing advantage do to an untouched lane?

Run: python -m experiments.m8.waves.investigate
"""

import json
import math
import re
from dataclasses import asdict, replace
from pathlib import Path

from experiments.m8.provenance import stamp
from experiments.m8.waves import m7_tests
from experiments.m8.waves.harness import BLUE, RED, Crashes, Crowding, make_lane, offset, outer, rounded, run, second_wave, summarize, tower_damage
from riftgame.lanes import ACQUIRE, HOLD_MARGIN, M7_LANE, M8_LANE, RULESET_ID, TOWER_RANGE, LaneGeometry, LaneRules, LaneSim, MinionDeath, Team, lane_geometry
from riftgame.map import REFERENCE_MAP

SEEDS = range(5)
DT = 0.5
RESULTS = Path(__file__).parent / "results" / "investigation.json"
VARIANTS = {
    "m8 lane": M8_LANE,
    "m7 rules": M7_LANE,
    "M7's route graph": replace(M8_LANE, m7_map=True),
    "blows land at once": replace(M8_LANE, attack_timing=False),
    "ranges along the lane": replace(M8_LANE, straight_ranges=False),
    "melee cap 2": replace(M8_LANE, melee_cap=2),
    "detour of 0.3 s": replace(M8_LANE, detour_s=0.3),
    "detour of 0.6 s": replace(M8_LANE, detour_s=0.6),
    "flat damage": replace(M8_LANE, current_hp_damage=False),
}
FIGHTS = {"6v6": {}, "6v7 one caster": {"red_casters": 1}, "6v9 three casters": {"red_casters": 3}, "6v9 three melee": {"red_melee": 3}}


def fights(rules: LaneRules) -> dict:
    return {label: m7_tests.fight(**surplus)(rules, 0, DT)[0] for label, surplus in FIGHTS.items()}


def natural_fight(lane: str, rules: LaneRules, seeds=SEEDS) -> dict:
    """The first waves of an untouched lane, from the first minion blow.

    `alone_s` is the fight with every later wave removed, until one team has no minion left. The other values are on
    the natural clock: when the first minion of wave 2 comes within acquisition range of an enemy, and how many minions
    of wave 1 each team still has at that moment.
    """
    runs = []
    for seed in seeds:
        alone, first_blow, alone_s = make_lane(lane, rules, seed, DT), None, None
        while alone_s is None and alone.time < 200.0:
            alone.step(alone.tick)
            for team in Team:
                alone.minions[team][:] = [m for m in alone.minions[team] if m.wave == 1]
            alone.invalidate()
            if first_blow is None and any(m.hp < m.max_hp for team in Team for m in alone.minions[team]):
                first_blow = alone.time
            if first_blow is not None and not all(alone.minions[team] for team in Team):
                alone_s = alone.time - first_blow
        sim, joined = make_lane(lane, rules, seed, DT), None
        while joined is None and sim.time < 200.0:
            sim.step(sim.tick)
            for team in Team:
                if any(m.wave == 2 and abs(m.s - foe.s) <= ACQUIRE for m in sim.minions[team] for foe in sim.minions[1 - team]):
                    joined = sim.time
        left = [sum(m.wave == 1 for m in sim.minions[team]) for team in Team]
        health = [sum(m.hp / m.max_hp for m in sim.minions[team] if m.wave == 1) for team in Team]
        runs.append({"first_blow_t": first_blow, "alone_s": alone_s, "wave_2_joins_after_s": joined - first_blow,
                     "wave_1_minions_left_when_wave_2_joins": left[BLUE] + left[RED], "wave_1_health_left_in_minions": health[BLUE] + health[RED]})
    return summarize(runs)


def arrivals(lane: str, rules: LaneRules, waves: int = 4) -> dict:
    """Seconds after its spawn at which each wave's first minion reaches each mark, with the other team removed."""
    geometry = lane_geometry(lane)
    out = {}
    for team in Team:
        heading = geometry.direction(team)
        marks = {
            "own tower edge": outer(geometry, team) + heading * TOWER_RANGE,
            "own hold line": outer(geometry, team) + heading * (TOWER_RANGE + HOLD_MARGIN),
            "centre": geometry.centre,
            "enemy tower edge": outer(geometry, 1 - team) - heading * TOWER_RANGE,
        }
        sim = make_lane(lane, rules, 0, DT)
        reached: dict = {}
        while sim.time < 30.0 * (waves + 2):
            sim.step(sim.tick)
            sim.minions[1 - team].clear()
            sim.invalidate()
            for m in sim.minions[team]:
                for mark, s in marks.items():
                    if heading * (m.s - s) >= 0 and m.wave <= waves:
                        reached.setdefault((m.wave, mark), sim.time - 30.0 * m.wave)
        out[Team(team).name.lower()] = {f"wave {wave}": {mark: reached.get((wave, mark)) for mark in marks} for wave in range(1, waves + 1)}
    return out


def attack_timing(lane: str, rules: LaneRules, seeds=SEEDS, until: float = 300.0) -> dict:
    """An untouched lane for five minutes: minion deaths, cancelled casts, lost missiles, and where bodies would overlap."""
    runs = []
    for seed in seeds:
        sim = make_lane(lane, rules, seed, DT)
        crowding = Crowding(sim)

        def stop(row) -> bool:
            crowding.watch(row)
            return False

        trace = run(sim, lambda sim, events: (), until, stop)
        deaths = sum(type(e) is MinionDeath for e in trace.events)
        runs.append({"minion_deaths": deaths, "casts_cancelled": sim.cancelled, "missiles_lost": sim.lost,
                     "casts_cancelled_per_death": sim.cancelled / deaths, "missiles_lost_per_death": sim.lost / deaths, **crowding.report()})
    return summarize(runs)


class TwoPaths(LaneSim):
    """A diagnostic lane on which red's minions and towers stand on a polyline of their own, `red_path`, and blue's
    on the lane's. Both share the lane coordinate, so marching is unchanged. Only `front` reads `_apart`, with
    blue's lead first, in a lane without champions."""

    def __init__(self, name: str, seed: int, tick_s: float, rules: LaneRules, geometry: LaneGeometry, red_path: LaneGeometry):
        self.red_path = red_path
        super().__init__(name, seed, tick_s, rules, geometry)

    def _path(self, team: int) -> LaneGeometry:
        return self.red_path if team == RED else self.geometry

    def _place(self, unit) -> None:
        if self.rules.straight_ranges:
            unit.x, unit.y = self._path(unit.team).xy(unit.s)

    def _span(self, tower) -> None:
        # a tower's stretch filters the enemy's minions, which stand on the enemy's polyline
        own, self.geometry = self.geometry, self._path(1 - tower.team)
        try:
            super()._span(tower)
        finally:
            self.geometry = own

    def _apart(self, blue: float, red: float) -> float:
        if not self.rules.straight_ranges:
            return abs(blue - red)
        (ax, ay), (bx, by) = self.geometry.xy(blue), self.red_path.xy(red)
        return math.hypot(bx - ax, by - ay)


def reflected(geometry: LaneGeometry) -> LaneGeometry:
    """The lane's polyline reflected about the perpendicular bisector of its two ends and walked from the other end:
    the point at lane coordinate s is the reflection of the point at length - s. On a map that is symmetric between
    the teams this is the path that red walks when blue walks the lane's."""
    (_, x0, y0), (_, x1, y1) = geometry.bends[0], geometry.bends[-1]
    mx, my, span = (x0 + x1) / 2, (y0 + y1) / 2, math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / span, (y1 - y0) / span

    def flip(x: float, y: float) -> tuple[float, float]:
        along = (x - mx) * ux + (y - my) * uy
        return x - 2 * along * ux, y - 2 * along * uy

    return replace(geometry, bends=tuple((geometry.length - s, *flip(x, y)) for s, x, y in reversed(geometry.bends)))


def swapped(geometry: LaneGeometry) -> LaneGeometry:
    """The lane mirrored about its centre: blue gets red's half, its spawn point, and its towers, and red blue's."""
    flip = lambda spots: tuple(geometry.length - s for s in spots)
    return replace(reflected(geometry), spawn=flip(geometry.spawn[::-1]), towers=(flip(geometry.towers[1]), flip(geometry.towers[0])))


def mirror_world(geometry: LaneGeometry, keep_red_places: bool = False) -> tuple[LaneGeometry, LaneGeometry]:
    """The lane for `TwoPaths` in which red's half is the mirror image of blue's: red walks the reflected polyline
    and, unless `keep_red_places`, spawns and keeps its towers where the mirror puts blue's. Returns the lane and
    red's path."""
    if keep_red_places:
        return geometry, reflected(geometry)
    flip = lambda spots: tuple(geometry.length - s for s in spots)
    mirror = replace(geometry, spawn=(geometry.spawn[0], geometry.length - geometry.spawn[0]), towers=(geometry.towers[0], flip(geometry.towers[0])))
    return mirror, reflected(mirror)


def lane_sim(lane: str, rules: LaneRules, seed: int, geometry: LaneGeometry | None = None, red_path: LaneGeometry | None = None, dt: float = DT) -> LaneSim:
    if red_path is None:
        return make_lane(lane, rules, seed, dt, geometry=geometry)
    return TwoPaths(lane, seed, dt, rules, geometry, red_path)


def untouched(lane: str, rules: LaneRules, seeds=SEEDS, until: float = 300.0, past: float = 100.0, geometry: LaneGeometry | None = None,
              red_path: LaneGeometry | None = None, dt: float = DT) -> dict:
    """A lane with no champion for five minutes: when its front first stands more than 100 units on each team's
    half, which half it reaches first, each team's crashes at the enemy outer tower, the largest of them, and the
    tower damage. `by_seed` gives each seed's first departure from the centre and its direction.

    A lane that goes somewhere unprompted is the baseline for every claim that a champion sent it there.
    """
    runs = []
    for seed in seeds:
        sim = lane_sim(lane, rules, seed, geometry, red_path, dt)
        watch = {team: Crashes(sim, team) for team in Team}

        def stop(row) -> bool:
            for crashes in watch.values():
                crashes.watch(row)
            return False

        trace = run(sim, lambda sim, events: (), until, stop)
        fronts = [(r.t, offset(trace.geometry, r.line)) for r in trace.rows if r.contact]
        largest = {team: watch[team].largest() for team in Team}
        on_blue, on_red = (next((t for t, o in fronts if side * o > past), None) for side in (-1, 1))
        runs.append({
            "front_on_blue_half_s": on_blue,
            "front_on_red_half_s": on_red,
            "front_leaves_the_centre_s": min((t for t in (on_blue, on_red) if t is not None), default=None),
            "blue_half_first": int(on_blue is not None and (on_red is None or on_blue < on_red)),
            "red_half_first": int(on_red is not None and (on_blue is None or on_red < on_blue)),
            "blue_crashes": len(watch[BLUE].spans),
            "red_crashes": len(watch[RED].spans),
            "largest_blue_crash": largest[BLUE]["peak"] if largest[BLUE] else 0,
            "largest_red_crash": largest[RED]["peak"] if largest[RED] else 0,
            "second_wave_in_largest_red_crash": second_wave(largest[RED]),
            "blue_tower_damage": tower_damage(trace.events, BLUE),
            "red_tower_damage": tower_damage(trace.events, RED),
        })
    by_seed = [{"seed": seed, "leaves_s": run["front_leaves_the_centre_s"], "toward": "blue" if run["blue_half_first"] else "red" if run["red_half_first"] else None}
               for seed, run in zip(seeds, runs)]
    return summarize(runs) | {"by_seed": by_seed}


BEND_SEEDS = range(12)
BEND_PLACES = (-295.0, -150.0, 0.0, 150.0, 295.0)
BEND_ANGLES = (5.0, 10.0, 20.0, 46.0)
# The corner is the fifth node of a side lane in M7's route graph.
CORNER_NODE = 4


def bent(base: LaneGeometry, turns) -> LaneGeometry:
    """The base lane's length, towers, and spawn points on a line that turns by `turn_deg` at each lane coordinate
    `at` of `turns`, a list of (at, turn_deg)."""
    s = x = y = heading = 0.0
    nodes = [(0.0, 0.0, 0.0)]
    for at, turn_deg in sorted(turns):
        x, y, s = x + (at - s) * math.cos(heading), y + (at - s) * math.sin(heading), at
        nodes.append((at, x, y))
        heading += math.radians(turn_deg)
    nodes.append((base.length, x + (base.length - s) * math.cos(heading), y + (base.length - s) * math.sin(heading)))
    return replace(base, bends=tuple(nodes))


def one_bend(base: LaneGeometry, at: float, turn_deg: float) -> LaneGeometry:
    """The base lane's length, towers, and spawn points on a line with one bend of `turn_deg` at lane coordinate `at`."""
    return bent(base, [(at, turn_deg)])


def turns(geometry: LaneGeometry) -> list[tuple[float, float]]:
    """Each inner node of the lane's polyline as (distance from the centre toward red, turn in degrees)."""
    out = []
    for (s0, x0, y0), (s1, x1, y1), (_, x2, y2) in zip(geometry.bends, geometry.bends[1:], geometry.bends[2:]):
        turn = math.atan2(y2 - y1, x2 - x1) - math.atan2(y1 - y0, x1 - x0)
        out.append((s1 - geometry.centre, math.degrees((turn + math.pi) % (2 * math.pi) - math.pi)))
    return out


def bends(seeds=BEND_SEEDS, until: float = 600.0) -> dict:
    """What tips an untouched top lane under straight-line ranges. Every row is the M8 lane rules on top lane's
    length, towers, and spawn points, with a different shape: no bend, one bend by its place from the lane's
    centre and by its angle, M7's route graph, the M8 map, the M8 map's own bends alone and in pairs (`bend_sets`).
    Mid lane is the reference for a lane that no bend tips. As diagnostics only, the M8 map also runs mirrored about
    the lane's centre, with red on the mirror of blue's polyline, with both spawn points moved along the lane, and
    at other tick lengths. A row counts, over the seeds, which half the front reaches first and when, the crashes
    of both teams, and the damage to both outer towers, and gives each seed's departure and its direction."""
    graph, m8 = lane_geometry("top", REFERENCE_MAP), lane_geometry("top")
    corner = graph.bends[CORNER_NODE][0]
    shapes = {"no bend": replace(graph, bends=())}
    shapes |= {f"one bend of 46 degrees, {place:+.0f} from the centre": one_bend(graph, graph.centre + place, 46.0) for place in BEND_PLACES}
    shapes |= {f"one bend of {angle:.0f} degrees, {corner - graph.centre:+.0f} from the centre": one_bend(graph, corner, angle) for angle in BEND_ANGLES}
    shapes |= {"M7's route graph": graph, "the M8 map": m8}
    shapes |= bend_sets(graph, m8)
    rows = {f"top, {name}": untouched("top", M8_LANE, seeds, until, geometry=shape) for name, shape in shapes.items()}
    rows |= {f"{lane}, the M8 map": untouched(lane, M8_LANE, seeds, until) for lane in ("mid", "bot")}
    rows["bot, M7's route graph"] = untouched("bot", M8_LANE, seeds, until, geometry=lane_geometry("bot", REFERENCE_MAP))
    rows["top, the M8 map, ranges along the lane"] = untouched("top", replace(M8_LANE, straight_ranges=False), seeds, until)
    rows["top, the M8 map mirrored about the lane's centre"] = untouched("top", M8_LANE, seeds, until, geometry=swapped(m8))
    for name, keep in (("red walks the mirror of blue's polyline, and spawns and keeps its towers where the mirror puts blue's", False),
                       ("red walks the mirror of blue's polyline, spawn points and towers as on the M8 map", True)):
        lane, path = mirror_world(m8, keep)
        rows[f"top, {name}"] = untouched("top", M8_LANE, seeds, until, geometry=lane, red_path=path)
    for shift in SPAWN_SHIFTS:
        rows[f"top, the M8 map with both spawn points {shift:+.0f} units nearer the centre"] = untouched("top", M8_LANE, seeds, until, geometry=nearer(m8, shift))
    half = (m8.length - graph.length) / 2
    rows[f"top, the M8 map with both spawn points {half:.1f} units nearer the centre, so that the walk to the centre is M7's"] = untouched("top", M8_LANE, seeds, until, geometry=nearer(m8, half))
    rows[f"top, M7's route graph with both spawn points {half:.1f} units further from the centre, so that the walk to the centre is the M8 map's"] = untouched(
        "top", M8_LANE, seeds, until, geometry=nearer(graph, -half))
    for dt in BEND_TICKS:
        rows[f"top, the M8 map at a tick of {dt} s"] = untouched("top", M8_LANE, seeds, until, dt=dt)
    return {"corner_of_m7s_graph_from_the_centre": corner - graph.centre,
            "bends_of_the_m8_map_from_the_centre": [s - m8.centre for s, _, _ in m8.bends if abs(s - m8.centre) < 2000.0],
            "turns_of_the_m8_map": turns(m8), "rows": rows}


SPAWN_SHIFTS = (-100.0, -50.0, -25.0, -10.0, 10.0, 25.0, 50.0, 100.0)
BEND_TICKS = (0.125, 0.25, 1.0)


def nearer(geometry: LaneGeometry, shift: float) -> LaneGeometry:
    """The lane with both spawn points `shift` units nearer the centre, so that both walks to the centre are
    shorter by that much and the waves meet at the same place a little earlier."""
    return replace(geometry, spawn=(geometry.spawn[0] + geometry.direction(BLUE) * shift, geometry.spawn[1] + geometry.direction(RED) * shift))


def bend_sets(graph: LaneGeometry, m8: LaneGeometry) -> dict[str, LaneGeometry]:
    """Lanes of top lane's length, towers, and spawn points with the M8 map's bends nearest the centre, placed and
    turned as the M8 map has them, alone, in pairs, mirrored, and all of them. A place is a distance from the
    centre toward red."""
    near = sorted(turns(m8), key=lambda bend: abs(bend[0]))
    (a, turn_a), (b, turn_b) = near[0], near[1]
    centre = graph.centre

    def shape(bends) -> LaneGeometry:
        return bent(graph, [(centre + place, turn) for place, turn in bends])

    central = [bend for bend in turns(m8) if abs(bend[0]) < 2000.0]
    return {
        f"the M8 map's bend at {a:+.0f}, {turn_a:.1f} degrees, alone": shape([(a, turn_a)]),
        f"the M8 map's bend at {b:+.0f}, {turn_b:.1f} degrees, alone": shape([(b, turn_b)]),
        f"the M8 map's two nearest bends, {a:+.0f} and {b:+.0f}": shape([(a, turn_a), (b, turn_b)]),
        f"those two bends mirrored, {-a:+.0f} and {-b:+.0f}": shape([(-a, turn_a), (-b, turn_b)]),
        f"a pair placed symmetrically, {a:+.0f} and {-a:+.0f}, both {turn_a:.1f} degrees": shape([(a, turn_a), (-a, turn_a)]),
        f"a pair placed symmetrically, {b:+.0f} and {-b:+.0f}, both {turn_b:.1f} degrees": shape([(b, turn_b), (-b, turn_b)]),
        f"the M8 map's {len(central)} bends within 2000 of the centre": shape(central),
        f"those {len(central)} bends mirrored": shape([(-place, turn) for place, turn in central]),
        "every bend of the M8 map, on M7's length": shape(turns(m8)),
        "the M8 map's length, towers, and spawn points with no bend": replace(m8, bends=()),
    }


def described(target) -> tuple:
    """A target as its kind and, for a minion, its wave, kind, and slot, so that a blue target and its red mirror
    compare equal."""
    if target is None:
        return ()
    if type(target).__name__ == "Minion":
        return ("minion", target.wave, target.rules.kind.name, target.slot, target.hp > 0)
    if type(target).__name__ == "Tower":
        return ("tower", target.tier)
    return ("champion",)


MIRROR_FIELDS = ("marched", "hp", "target", "anchored", "ready", "swing", "swing_at", "draws")
# what each field's first difference points to in the lane's rules
MIRROR_RULE = {"draws": "a tie between equally near targets, broken by a draw keyed by the minion's uid",
               "target": "target acquisition by straight-line range", "near_gap": "the straight-line distance to the nearest enemy",
               "marched": "the march: a walker's room to its target or to the enemy's lead walker",
               "anchored": "whether the target is in attack range", "ready": "attack timing", "swing": "attack timing", "swing_at": "the target of a cast",
               "hp": "a blow landed with different damage or at a different time", "alive": "a death"}


def mirror_state(sim: LaneSim) -> dict:
    geometry = sim.geometry
    out = {}
    for team in Team:
        for m in sim.minions[team]:
            out[team, m.wave, m.rules.kind.name, m.slot] = {
                "marched": geometry.direction(team) * (m.s - geometry.spawn[team]), "hp": m.hp, "target": described(m.target), "anchored": m.anchored,
                "ready": m.ready, "swing": m.swing, "swing_at": described(m.swing_at), "draws": m.draws, "near_gap": m.near_gap}
    return out


def mirror_break(lane: str, seed: int, rules: LaneRules = M8_LANE, geometry: LaneGeometry | None = None, red_path: LaneGeometry | None = None,
                 until: float = 600.0, tolerance: float = 1e-6, past: float = 100.0) -> dict:
    """Step an untouched lane, and after every tick compare each blue minion with the red minion of the same wave,
    kind, and slot: how far each has marched from its own spawn, its health, its target, its attack clock, its
    and its tie draws. Report the first tick on which a pair differs, every field that differs then with both
    values and both minions' distance to their nearest enemy, the pair's state on the tick before, the rule each
    field points to, the minion deaths of that tick, and when and toward which half the front first leaves the
    centre in the same run, with the first tick before then on which the teams have different numbers of minions."""
    sim = lane_sim(lane, rules, seed, geometry, red_path)
    first, left, before, unequal = None, None, {}, None
    while sim.time < until - 1e-9 and (first is None or left is None):
        events = sim.step(sim.tick)
        if unequal is None and len(sim.minions[BLUE]) != len(sim.minions[RED]):
            unequal = {"t": sim.time, "blue": len(sim.minions[BLUE]), "red": len(sim.minions[RED])}
        if first is None:
            state = mirror_state(sim)
            pairs = {key[1:] for key in state}
            differ = []
            for pair in sorted(pairs, key=str):
                b, r = state.get((BLUE, *pair)), state.get((RED, *pair))
                if b is None or r is None:
                    differ.append({"pair": pair, "field": "alive", "blue": b is not None, "red": r is not None})
                    continue
                for name in MIRROR_FIELDS:
                    x, y = b[name], r[name]
                    same = x == y or (isinstance(x, float) and isinstance(y, float) and abs(x - y) <= tolerance)
                    if not same:
                        differ.append({"pair": pair, "field": name, "blue": x, "red": y, "near_gap": (b["near_gap"], r["near_gap"]),
                                       "tick_before": (before.get((BLUE, *pair)), before.get((RED, *pair)))})
            if differ:
                deaths = [f"{Team(e.team).name.lower()} {e.kind.name.lower()} at {e.s:.1f}" for e in events if type(e) is MinionDeath]
                fields = sorted({row["field"] for row in differ}, key=list(MIRROR_FIELDS + ("alive",)).index)
                first = {"t": sim.time, "pairs_that_differ": len({row["pair"] for row in differ}), "fields": fields,
                         "rules": [MIRROR_RULE[name] for name in fields], "differences": differ[:12], "deaths_on_that_tick": deaths}
            before = state
        front = sim.front()
        if left is None and front.s is not None:
            o = offset(sim.geometry, front.s)
            if abs(o) > past:
                left = {"t": sim.time, "toward": "red" if o > 0 else "blue"}
    return {"seed": seed, "first_difference": first, "first_unequal_minion_count": unequal, "front_leaves_the_centre": left}


def drift(seeds=SEEDS, until: float = 600.0) -> dict:
    """Why an untouched top lane on the M8 map leaves the centre toward red: per seed, the first tick on which the
    two waves stop being mirror images and the field that differs, beside the departure, on the M8 map, on a lane
    with no bend, mirrored about its centre, and with red on the mirror of blue's polyline."""
    graph, m8 = lane_geometry("top", REFERENCE_MAP), lane_geometry("top")
    lanes = {"top, the M8 map": (m8, None), "top, no bend": (replace(graph, bends=()), None), "top, the M8 map mirrored about the lane's centre": (swapped(m8), None),
             "top, red walks the mirror of blue's polyline, and spawns and keeps its towers where the mirror puts blue's": mirror_world(m8),
             "mid, the M8 map": (lane_geometry("mid"), None)}
    out = {}
    for name, (shape, path) in lanes.items():
        runs = [mirror_break(name.split(",")[0], seed, geometry=shape, red_path=path, until=until) for seed in seeds]
        first = runs[0]["first_difference"]
        out[name] = {"runs": runs, "casters_on_the_tick_before_the_first_difference": casters(name.split(",")[0], seeds[0], first["t"] - DT, shape, path) if first else None}
    return out


def casters(lane: str, seed: int, t: float, geometry: LaneGeometry | None = None, red_path: LaneGeometry | None = None) -> dict:
    """Each team's casters with a minion target at time `t` of an untouched lane: the distance to the target along
    the lane and in a straight line, and the flight time of a missile over the straight line."""
    sim = lane_sim(lane, M8_LANE, seed, geometry, red_path)
    while sim.time < t - 1e-9:
        sim.step(sim.tick)
    out = {}
    for team in Team:
        out[Team(team).name.lower()] = [{"wave": m.wave, "slot": m.slot, "along": abs(m.s - m.target.s), "straight": sim._range(m, m.target),
                                         "flight_s": sim._range(m, m.target) / m.rules.missile_speed}
                                        for m in sim.minions[team] if m.rules.kind.name == "CASTER" and type(m.target).__name__ == "Minion"]
    return out


def level_lead(rules: LaneRules, seeds=SEEDS, leads=(0.0, 0.5, 1.0, 2.0), until: float = 600.0) -> dict:
    """An untouched lane for 10 minutes, by blue's level lead: how often each team's wave reaches the enemy outer tower,
    how large its largest visit is, and the damage each outer tower takes."""
    out = {}
    for lane in ("top", "mid"):
        for lead in leads:
            runs = []
            for seed in seeds:
                sim = make_lane(lane, rules, seed, DT)
                watch = {team: Crashes(sim, team) for team in Team}

                def stop(row) -> bool:
                    for crashes in watch.values():
                        crashes.watch(row)
                    return False

                trace = run(sim, lambda sim, events: (), until, stop, lead)
                runs.append({
                    "blue_crashes": len(watch[BLUE].spans),
                    "red_crashes": len(watch[RED].spans),
                    "largest_blue_crash": max((span["peak"] for span in watch[BLUE].spans), default=0),
                    "largest_red_crash": max((span["peak"] for span in watch[RED].spans), default=0),
                    "red_tower_damage": tower_damage(trace.events, RED),
                    "blue_tower_damage": tower_damage(trace.events, BLUE),
                })
            out[f"{lane}, blue level lead {lead}"] = summarize(runs)
    return out


def main() -> None:
    results = {
        "ruleset": RULESET_ID,
        "seeds": list(SEEDS),
        "dt": DT,
        "variants": {name: asdict(rules) for name, rules in VARIANTS.items()},
        "fights": {name: fights(rules) for name, rules in VARIANTS.items()},
        "natural_fight": {lane: {name: natural_fight(lane, rules) for name, rules in VARIANTS.items()} for lane in ("mid", "top")},
        "arrivals": {lane: {name: arrivals(lane, VARIANTS[name]) for name in ("m8 lane", "m7 rules")} for lane in ("top", "mid")},
        "attack_timing": {lane: attack_timing(lane, M8_LANE) for lane in ("mid", "top")},
        "untouched": {lane: {name: untouched(lane, VARIANTS[name]) for name in ("m8 lane", "M7's route graph", "ranges along the lane", "blows land at once")}
                      for lane in ("top", "mid", "bot")},
        "bends": bends(),
        "drift": drift(BEND_SEEDS),
        "level_lead": level_lead(M8_LANE),
    }
    results["run"] = stamp(SEEDS, {"dt": DT})
    RESULTS.parent.mkdir(exist_ok=True)
    one_row_per_line = re.sub(r"\[[^\[\]]*\]|\{[^{}]*\}", lambda row: re.sub(r"\s+", " ", row.group()), json.dumps(rounded(results), indent=1))
    RESULTS.write_text(one_row_per_line, encoding="utf-8")
    for name, table in results["fights"].items():
        print(f"fights {name:<22}", {label: (m["fight_s"], m["blue_left"], m["red_left"]) for label, m in table.items()})
    for lane, by in results["natural_fight"].items():
        for name, row in by.items():
            print(f"natural fight {lane} {name}: alone {row['alone_s']['median']} s, wave 2 joins after {row['wave_2_joins_after_s']['median']} s, "
                  f"{row['wave_1_minions_left_when_wave_2_joins']['median']} minions of wave 1 left with {row['wave_1_health_left_in_minions']['median']:.2f} minion healths")
    for lane, row in results["attack_timing"].items():
        print(f"attack timing {lane}:", {key: value["median"] for key, value in row.items()})
    for lane, by in results["untouched"].items():
        for name, row in by.items():
            print(f"untouched {lane} {name}:", {key: (value["median"], value["n"]) for key, value in row.items() if key != "by_seed"})
    for name, row in results["bends"]["rows"].items():
        print(f"bends {name}: blue half first in {row['blue_half_first']['mean'] * row['blue_half_first']['n']:.0f}, red half first in {row['red_half_first']['mean'] * row['red_half_first']['n']:.0f} "
              f"of {row['blue_half_first']['n']}, leaves the centre at {row['front_leaves_the_centre_s']['median']} s, crashes blue {row['blue_crashes']['mean'] * row['blue_crashes']['n']:.0f} "
              f"red {row['red_crashes']['mean'] * row['red_crashes']['n']:.0f}, tower damage blue {row['blue_tower_damage']['mean']:.0f} red {row['red_tower_damage']['mean']:.0f}")
        print(f"    by seed: {[(run['leaves_s'], run['toward']) for run in row['by_seed']]}")
    for name, row in results["drift"].items():
        for run in row["runs"]:
            first = run["first_difference"]
            print(f"drift {name}, seed {run['seed']}: leaves {run['front_leaves_the_centre']}, first unequal count {run['first_unequal_minion_count']}, "
                  f"first difference at {first['t'] if first else None} in {first['fields'] if first else None}")
        print(f"    casters before the first difference: {row['casters_on_the_tick_before_the_first_difference']}")
    for name, row in results["level_lead"].items():
        print(f"level lead {name}: crashes blue {row['blue_crashes']['mean']} red {row['red_crashes']['mean']}, largest blue {row['largest_blue_crash']['max']} red {row['largest_red_crash']['max']}")
    print(f"wrote {RESULTS}")


if __name__ == "__main__":
    main()
