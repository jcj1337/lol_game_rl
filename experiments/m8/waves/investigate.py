"""M8 wave investigation: the lane without champions.

Each section answers one question with a run that this file reproduces. The questions about champions (stacking,
holding, bouncing, and the diagnostics on them) are in `capabilities.py`, which drives a full world.
  fights         How long does a placed minion fight last, and do the rule variants change it?
  natural_fight  How long does the untouched first-wave fight last on the natural clock, and what is left of it when wave 2 arrives?
  arrivals       When does each wave reach the centre and the tower edges?
  attack_timing  How many casts are cancelled and missiles lost in an untouched lane, and how often would bodies overlap?
  untouched      Where does a lane go when nobody touches it, and how large are its crashes?
  bends          Which bend of a lane tips an untouched lane under straight-line ranges: by its place, by its angle?
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
from riftgame.lanes import ACQUIRE, HOLD_MARGIN, M7_LANE, M8_LANE, RULESET_ID, TOWER_RANGE, LaneGeometry, LaneRules, MinionDeath, Team, lane_geometry
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


def untouched(lane: str, rules: LaneRules, seeds=SEEDS, until: float = 300.0, past: float = 100.0, geometry: LaneGeometry | None = None) -> dict:
    """A lane with no champion for five minutes: when its front first stands more than 100 units on each team's
    half, which half it reaches first, each team's crashes at the enemy outer tower, the largest of them, and the
    tower damage.

    A lane that goes somewhere unprompted is the baseline for every claim that a champion sent it there.
    """
    runs = []
    for seed in seeds:
        sim = make_lane(lane, rules, seed, DT, geometry=geometry)
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
    return summarize(runs)


BEND_SEEDS = range(12)
BEND_PLACES = (-295.0, -150.0, 0.0, 150.0, 295.0)
BEND_ANGLES = (5.0, 10.0, 20.0, 46.0)
# The corner is the fifth node of a side lane in M7's route graph.
CORNER_NODE = 4


def one_bend(base: LaneGeometry, at: float, turn_deg: float) -> LaneGeometry:
    """The base lane's length, towers, and spawn points on a line with one bend of `turn_deg` at lane coordinate `at`."""
    turn = math.radians(turn_deg)
    end = (at + (base.length - at) * math.cos(turn), (base.length - at) * math.sin(turn))
    return replace(base, bends=((0.0, 0.0, 0.0), (at, at, 0.0), (base.length, *end)))


def bends(seeds=BEND_SEEDS, until: float = 600.0) -> dict:
    """What tips an untouched top lane under straight-line ranges. Every row is the M8 lane rules on top lane's
    length, towers, and spawn points, with a different shape: no bend, one bend by its place from the lane's
    centre and by its angle, M7's route graph, and the M8 map. Mid lane is the reference for a lane that no bend
    tips. A row counts, over the seeds, which half the front reaches first and when, the crashes of both teams,
    and the damage to both outer towers."""
    graph, m8 = lane_geometry("top", REFERENCE_MAP), lane_geometry("top")
    corner = graph.bends[CORNER_NODE][0]
    shapes = {"no bend": replace(graph, bends=())}
    shapes |= {f"one bend of 46 degrees, {place:+.0f} from the centre": one_bend(graph, graph.centre + place, 46.0) for place in BEND_PLACES}
    shapes |= {f"one bend of {angle:.0f} degrees, {corner - graph.centre:+.0f} from the centre": one_bend(graph, corner, angle) for angle in BEND_ANGLES}
    shapes |= {"M7's route graph": graph, "the M8 map": m8}
    rows = {f"top, {name}": untouched("top", M8_LANE, seeds, until, geometry=shape) for name, shape in shapes.items()}
    rows |= {f"{lane}, the M8 map": untouched(lane, M8_LANE, seeds, until) for lane in ("mid", "bot")}
    rows["bot, M7's route graph"] = untouched("bot", M8_LANE, seeds, until, geometry=lane_geometry("bot", REFERENCE_MAP))
    rows["top, the M8 map, ranges along the lane"] = untouched("top", replace(M8_LANE, straight_ranges=False), seeds, until)
    return {"corner_of_m7s_graph_from_the_centre": corner - graph.centre,
            "bends_of_the_m8_map_from_the_centre": [s - m8.centre for s, _, _ in m8.bends if abs(s - m8.centre) < 2000.0], "rows": rows}


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
            print(f"untouched {lane} {name}:", {key: (value["median"], value["n"]) for key, value in row.items()})
    for name, row in results["bends"]["rows"].items():
        print(f"bends {name}: blue half first in {row['blue_half_first']['mean'] * row['blue_half_first']['n']:.0f}, red half first in {row['red_half_first']['mean'] * row['red_half_first']['n']:.0f} "
              f"of {row['blue_half_first']['n']}, leaves the centre at {row['front_leaves_the_centre_s']['median']} s, crashes blue {row['blue_crashes']['mean'] * row['blue_crashes']['n']:.0f} "
              f"red {row['red_crashes']['mean'] * row['red_crashes']['n']:.0f}, tower damage blue {row['blue_tower_damage']['mean']:.0f} red {row['red_tower_damage']['mean']:.0f}")
    for name, row in results["level_lead"].items():
        print(f"level lead {name}: crashes blue {row['blue_crashes']['mean']} red {row['red_crashes']['mean']}, largest blue {row['largest_blue_crash']['max']} red {row['largest_red_crash']['max']}")
    print(f"wrote {RESULTS}")


if __name__ == "__main__":
    main()
