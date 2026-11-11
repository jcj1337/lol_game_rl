"""M8 wave investigation: what decides stacking, holding, and bouncing on the M8 lane.

Each section answers one question with a run that this file reproduces.
  fights       How long does a placed minion fight last, and do the rule variants change it?
  natural_fight  How long does the untouched first-wave fight last on the natural clock, and what is left of it when wave 2 arrives?
  arrivals     When does each wave reach the centre and the tower edges?
  stacking     Over a family of thinning plans and two starts, how large and how late is the crash?
  holding      Can a champion hold a wave off its tower, from M7's built state and from a phase-aligned one?
  bounce       Does the lane come back after a crash?
  level_lead   What does the pushing advantage do to an untouched lane?
  attacker_cap Do stacking and holding change when at most n melee minions may attack one target?
  fight_speed  How do the answers move when minion blows on minions are scaled? A diagnostic, not a candidate rule.

Run: python -m experiments.m8.waves.investigate
"""

import json
import re
from dataclasses import asdict, replace
from pathlib import Path

from experiments.m8.provenance import stamp
from experiments.m8.waves import m7_tests
from experiments.m8.waves.harness import (
    BLUE,
    RED,
    Crashes,
    Laner,
    legacy_laner,
    line,
    make_lane,
    offset,
    outer,
    rounded,
    run,
    summarize,
    tower_damage,
    under_tower,
)
from riftgame.lanes import ACQUIRE, HOLD_MARGIN, M7_LANE, M8_LANE, RULESET_ID, TOWER_RANGE, Kind, LaneRules, MinionDeath, Mode, Team, lane_geometry

SEEDS = range(5)
DT = 0.5
RESULTS = Path(__file__).parent / "results" / "investigation.json"
VARIANTS = {
    "m8 lane": M8_LANE,
    "m7 rules": M7_LANE,
    "melee cap 3": replace(M8_LANE, melee_cap=3),
    "melee cap 2": replace(M8_LANE, melee_cap=2),
    "melee cap 1": replace(M8_LANE, melee_cap=1),
    "flat damage": replace(M8_LANE, current_hp_damage=False),
}
SCALES = (1.0, 0.85, 0.7, 0.6, 0.5)
FIGHTS = {"6v6": {}, "6v7 one caster": {"red_casters": 1}, "6v9 three casters": {"red_casters": 3}, "6v9 three melee": {"red_melee": 3}}
PLAN_RUN_S = 240.0
TWO_WAVES = 12
DURABLE = {"max_hp": 1300.0, "regen": 3.0}
HOLD_RUN_S = 240.0
BAND = 1500.0


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


def push_plan(lane: str, start: str, thin: int, after: Mode | None, red_last_hits: bool):
    """Blue thins until it has killed `thin` casters, then plays `after`. `after` None is the hard push.

    From `first contact` the plan starts when the first waves meet. From `own tower` a red champion first pushes
    until its lead minion is in the blue outer tower's range and then leaves, and the plan starts at that moment.
    """

    def case(rules, seed, dt):
        sim = make_lane(lane, rules, seed, dt)
        geometry = sim.geometry
        blue = Laner(BLUE, outer(geometry, BLUE))
        crashes = Crashes(sim, BLUE)
        began, met, casters, largest, touch = [], [], [0], [0], []

        def policy(sim, events):
            front = sim.front()
            if front.s is not None and not met:
                met.append(sim.time)
            if not began and met and (start == "first contact" or under_tower(geometry, BLUE, front.lead[RED])):
                began.append(sim.time)
            if not began:
                return blue.act(sim, events, Mode.LAST_HIT) + [legacy_laner(sim, RED, Mode.PUSH)] * (bool(met) and start == "own tower")
            casters[0] += sum(type(e) is MinionDeath and e.team == RED and e.kind is Kind.CASTER and e.killer == BLUE for e in events)
            mode = Mode.PUSH if after is None else Mode.THIN if casters[0] < thin else after
            return blue.act(sim, events, mode) + [legacy_laner(sim, RED, Mode.LAST_HIT)] * red_last_hits

        def stop(row) -> bool:
            if began:
                crashes.watch(row)
                largest[0] = max(largest[0], row.wave_blue)
                if not touch and under_tower(geometry, RED, row.lead_blue):
                    touch.append(row.wave_blue)
            return bool(began) and row.t >= began[0] + PLAN_RUN_S

        trace = run(sim, policy, 3600.0, stop)
        first, biggest = (crashes.spans[0] if crashes.spans else None), crashes.largest()
        return {
            "first_crash_s": first["start"] - began[0] if first else None,
            "first_crash_peak": first["peak"] if first else None,
            "wave_at_first_touch_m7": touch[0] if touch else None,
            "first_crash_waves": len(first["waves"]) if first else None,
            "largest_crash_s": biggest["start"] - began[0] if biggest else None,
            "largest_crash_peak": biggest["peak"] if biggest else 0,
            "largest_crash_waves": len(biggest["waves"]) if biggest else None,
            "largest_wave_anywhere": largest[0],
            "red_tower_damage": tower_damage(trace.events, RED, began[0]),
            "gold": sum(e.gold for e in trace.events if type(e) is MinionDeath and e.killer == BLUE and e.t >= began[0]),
            "champion_lowest_health": blue.report()["champion_lowest_health"],
        }, trace

    return case


PLANS = {"push": (0, None), "last hit": (0, Mode.LAST_HIT), "passive": (0, Mode.PASSIVE)}
for kills in (1, 2, 3):
    PLANS[f"thin {kills}, then last hit"] = (kills, Mode.LAST_HIT)
    PLANS[f"thin {kills}, then passive"] = (kills, Mode.PASSIVE)
PLANS["thin every caster"] = (10**6, Mode.LAST_HIT)


def stacking(rules: LaneRules, lanes=("top", "mid"), starts=("first contact", "own tower"), reds=(False, True), seeds=SEEDS) -> dict:
    out, best = {}, {"peak": 0, "case": None}
    for lane in lanes:
        for start in starts:
            for red_last_hits in reds:
                setting = f"{lane}, from {start}, red {'last hits' if red_last_hits else 'absent'}"
                rows = {plan: summarize([push_plan(lane, start, thin, after, red_last_hits)(rules, seed, DT)[0] for seed in seeds]) for plan, (thin, after) in PLANS.items()}
                out[setting] = rows
                for plan, row in rows.items():
                    peak = row["largest_crash_peak"]["median"]
                    if plan != "push" and peak > best["peak"]:
                        best = {"peak": peak, "case": f"{setting}, {plan}", "crash_s": row["largest_crash_s"]["median"], "waves": row["largest_crash_waves"]["median"],
                                "push_first_crash_s": rows["push"]["first_crash_s"]["median"], "push_peak": rows["push"]["largest_crash_peak"]["median"]}
    stacked = [f"{setting}, {plan}" for setting, rows in out.items() for plan, row in rows.items() if plan != "push" and row["largest_crash_peak"]["median"] >= TWO_WAVES]
    return {"largest_crash_of_a_plan_that_is_not_a_push": best, "plans_with_a_two_wave_stack": stacked, "cases": out}


def phase_aligned_hold(surplus: int, plan: str, laner: dict | None = None):
    """Top lane on the natural clock. `surplus` red casters stand at the hold line when the blue wave of 150 s reaches
    its own tower's edge, so the first thing that happens is the arrival of the champion's wave.

    plan `hold`: the champion holds and last-hits. plan `hold or push`: it holds, and pushes while more than four red
    minions and none of its own are within 1500 units of the front. plan `absent`: no champion.
    """
    top = lane_geometry("top")
    lo = outer(top, BLUE) + TOWER_RANGE
    start_s = 150.0

    def case(rules, seed, dt):
        sim = make_lane("top", rules, seed, dt, start_s)
        blue = Laner(BLUE, lo + HOLD_MARGIN - 110.0, **(laner or {}))
        placed = []

        def policy(sim, events):
            lead = sim.front().lead[BLUE]
            if not placed and lead is not None and lead >= lo:
                sim.add_minion(RED, Kind.CASTER, lo + HOLD_MARGIN + 390.0, count=surplus)
                placed.append(sim.time)
            if plan == "absent" or not placed:
                return []
            front = line(sim.geometry, sim.front())
            red = sum(abs(m.s - front) <= 1500 for m in sim.minions[RED]) if front is not None else 0
            own = sum(abs(m.s - front) <= 1500 for m in sim.minions[BLUE]) if front is not None else 0
            if plan == "hold or push" and own == 0 and red > 4:
                return blue.act(sim, events, Mode.PUSH)
            return blue.act(sim, events, Mode.HOLD)

        trace = run(sim, policy, 3600.0, lambda row: bool(placed) and row.t >= placed[0] + HOLD_RUN_S)
        arrive_s = placed[0]
        rows = [r for r in trace.rows if r.t >= arrive_s]
        inside = [r.line is not None and lo <= r.line <= lo + BAND for r in rows]
        cycles = [sum(ok for r, ok in zip(rows, inside) if arrive_s + 30 * i <= r.t < arrive_s + 30 * (i + 1)) * dt for i in range(int(HOLD_RUN_S // 30))]
        return {
            "band_s": sum(inside) * dt,
            "cycles_mostly_in_band": sum(c >= 15.0 for c in cycles),
            "under_tower_s": sum(under_tower(top, BLUE, r.lead_red) for r in rows) * dt,
            "blue_tower_damage": tower_damage(trace.events, BLUE),
            "pushed_out": any(r.lead_blue is not None and r.lead_blue > top.centre for r in rows),
            **blue.report(),
        }, trace

    return case


LANERS = {"placeholder laner": None, "durable laner": DURABLE}


def holding(rules: LaneRules, seeds=SEEDS, laners=tuple(LANERS), aligned_state: bool = True) -> dict:
    """M7's freeze verdict on its built state, for the placeholder laner and a durable one, and the phase-aligned state."""
    out = {}
    for label in laners:
        laner = LANERS[label]
        built = {}
        for k in m7_tests.FREEZE_SURPLUS:
            built[f"S5c k={k} hold"] = m7_tests.freeze(k, "hold", laner=laner)
            for n in m7_tests.THIN_OVER:
                built[f"S5c k={k} hold, thin over {n}"] = m7_tests.freeze(k, "hold", n, laner=laner)
            for m in m7_tests.TRIM_TO:
                built[f"S5c k={k} hold, trim to {m}"] = m7_tests.freeze(k, "hold", trim_to=m, laner=laner)
            built[f"S5c k={k} absent"] = m7_tests.freeze(k, "absent")
            built[f"S5c k={k} push"] = m7_tests.freeze(k, "push", laner=laner)
        cases = {name: summarize([case(rules, seed, DT)[0] for seed in seeds]) for name, case in built.items()}
        verdict = freeze_verdict(cases)
        aligned = {}
        for surplus in (2, 3, 4, 5, 6, 8) if aligned_state else ():
            for plan in ("hold", "hold or push", "absent"):
                aligned[f"{surplus} casters, {plan}"] = summarize([phase_aligned_hold(surplus, plan, laner)(rules, seed, DT)[0] for seed in seeds])
        held = {name: row["band_s"]["min"] for name, row in aligned.items()
                if "absent" not in name and row["band_s"]["min"] > HOLD_RUN_S / 2 and row["champion_retreats"]["max"] == 0 and row["champion_died"]["max"] == 0}
        out[label] = {
            "m7_built_state": verdict,
            "phase_aligned_state_holds_over_half_the_run_without_retreat": held,
            "phase_aligned_state": aligned,
            "m7_built_state_cases": {name: row for name, row in cases.items() if name.endswith(("hold", "absent", "trim to 4", "thin over 3"))},
        }
    return out


def freeze_verdict(cases: dict) -> dict:
    """M7's freeze test, from m7_tests.champion_plan_verdict, without the slow-push half."""
    held, ignoring_health, best = {}, {}, (0.0, None)
    plans = ["hold"] + [f"hold, thin over {n}" for n in m7_tests.THIN_OVER] + [f"hold, trim to {m}" for m in m7_tests.TRIM_TO]
    for k in m7_tests.FREEZE_SURPLUS:
        controls = max(cases[f"S5c k={k} {control}"]["band_s"]["max"] for control in ("absent", "push"))
        for plan in plans:
            case = cases[f"S5c k={k} {plan}"]
            band = case["band_s"]
            best = max(best, (band["median"], f"k={k} {plan}"))
            if band["min"] > m7_tests.FREEZE_RUN_S / 2 > controls:
                ignoring_health[f"k={k} {plan}"] = band["min"]
                if case["champion_died"]["max"] == 0 and case["champion_retreats"]["max"] == 0:
                    held[f"k={k} {plan}"] = band["min"]
    controls = {f"k={k}": max(cases[f"S5c k={k} {control}"]["band_s"]["max"] for control in ("absent", "push")) for k in m7_tests.FREEZE_SURPLUS}
    return {"freeze": bool(held), "freeze_cases": held, "longest_hold": best, "freeze_cases_if_health_is_ignored": ignoring_health,
            "largest_band_s_of_a_control_by_surplus": controls}


def bounce(rules: LaneRules, seeds=SEEDS, lanes=("top", "mid", "bot")) -> dict:
    """M7's hard push of the first wave, then nobody. How far the lane comes back within 120 s of the crash."""
    out = {}
    for lane in lanes:
        runs = []
        for seed in seeds:
            metrics, trace = m7_tests.bounce(lane)(rules, seed, DT)
            geometry, crash = trace.geometry, metrics["crash_t"]
            back = next((r.t - crash for r in trace.rows if r.t > crash and r.contact and offset(geometry, r.line) < 0), None)
            answer = next((r.t - crash for r in trace.rows if r.t > crash and under_tower(geometry, BLUE, r.lead_red)), None)
            runs.append({"bounced_m7": metrics["bounced"], "crash_wave": metrics["crash_wave"], "deepest_offset": metrics["deepest_offset"],
                         "front_back_past_centre_s": back, "red_wave_at_blue_tower_s": answer})
        out[lane] = summarize(runs)
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


def attacker_cap(seeds=range(3)) -> dict:
    out = {}
    for cap in (0, 1, 2, 3):
        rules = replace(M8_LANE, melee_cap=cap)
        stack = stacking(rules, lanes=("top",), reds=(False,), seeds=seeds)
        hold = holding(rules, seeds=seeds, laners=("placeholder laner",), aligned_state=False)["placeholder laner"]["m7_built_state"]
        out[f"cap {cap}" if cap else "no cap"] = {
            "largest_crash": stack["largest_crash_of_a_plan_that_is_not_a_push"]["peak"],
            "plans_with_a_two_wave_stack": len(stack["plans_with_a_two_wave_stack"]),
            "m7_freeze_verdict": hold["freeze"],
            "m7_longest_hold": hold["longest_hold"],
        }
    return out


def fight_speed(seeds=range(3)) -> dict:
    out = {}
    for scale in SCALES:
        rules = replace(M8_LANE, minion_damage_scale=scale)
        stack = stacking(rules, lanes=("top",), reds=(False,), seeds=seeds)
        hold = holding(rules, seeds=seeds, laners=("placeholder laner",))["placeholder laner"]
        out[str(scale)] = {
            "even_fight_s": fights(rules)["6v6"]["fight_s"],
            "natural_first_wave_fight_mid_s": natural_fight("mid", rules, seeds)["alone_s"]["median"],
            "largest_crash": stack["largest_crash_of_a_plan_that_is_not_a_push"],
            "plans_with_a_two_wave_stack": stack["plans_with_a_two_wave_stack"],
            "plans_with_12_at_first_touch_m7": [f"{setting}, {plan}" for setting, rows in stack["cases"].items() for plan, row in rows.items()
                                                if plan != "push" and (row["wave_at_first_touch_m7"]["median"] or 0) >= TWO_WAVES],
            "m7_freeze_verdict": hold["m7_built_state"]["freeze"],
            "m7_longest_hold": hold["m7_built_state"]["longest_hold"],
            "m7_freeze_cases": hold["m7_built_state"]["freeze_cases"],
            "phase_aligned_holds": hold["phase_aligned_state_holds_over_half_the_run_without_retreat"],
        }
    return out


def main() -> None:
    results = {
        "ruleset": RULESET_ID,
        "seeds": list(SEEDS),
        "dt": DT,
        "variants": {name: asdict(rules) for name, rules in VARIANTS.items()},
        "fights": {name: fights(rules) for name, rules in VARIANTS.items()},
        "natural_fight": {lane: {name: natural_fight(lane, VARIANTS[name]) for name in ("m8 lane", "m7 rules")} for lane in ("mid", "top")},
        "arrivals": {lane: {name: arrivals(lane, VARIANTS[name]) for name in ("m8 lane", "m7 rules")} for lane in ("top", "mid")},
        "stacking": stacking(M8_LANE),
        "holding": holding(M8_LANE),
        "bounce": {name: bounce(VARIANTS[name]) for name in ("m8 lane", "m7 rules")},
        "level_lead": level_lead(M8_LANE),
        "attacker_cap": attacker_cap(),
        "fight_speed": fight_speed(),
    }
    results["run"] = stamp(SEEDS, {"dt": DT, "scales": SCALES, "plan_run_s": PLAN_RUN_S, "hold_run_s": HOLD_RUN_S, "durable": DURABLE})
    RESULTS.parent.mkdir(exist_ok=True)
    one_row_per_line = re.sub(r"\[[^\[\]]*\]|\{[^{}]*\}", lambda row: re.sub(r"\s+", " ", row.group()), json.dumps(rounded(results), indent=1))
    RESULTS.write_text(one_row_per_line, encoding="utf-8")
    for name, table in results["fights"].items():
        print(f"fights {name:<12}", {label: (m["fight_s"], m["blue_left"], m["red_left"]) for label, m in table.items()})
    for lane, by in results["natural_fight"].items():
        for name, row in by.items():
            print(f"natural fight {lane} {name}:", {key: (value["median"], value["min"], value["max"]) for key, value in row.items()})
    for name, row in results["attacker_cap"].items():
        print(f"attacker cap, {name}:", row)
    for lane, by in results["arrivals"].items():
        for name, teams in by.items():
            print(f"arrivals {lane} {name}:", teams["blue"])
    stack = results["stacking"]
    print("stacking, largest crash:", stack["largest_crash_of_a_plan_that_is_not_a_push"], "two-wave stacks:", stack["plans_with_a_two_wave_stack"])
    for label, hold in results["holding"].items():
        print(f"holding {label}: M7 built state", hold["m7_built_state"], "| phase aligned", hold["phase_aligned_state_holds_over_half_the_run_without_retreat"])
    for name, lanes in results["bounce"].items():
        print(f"bounce {name}:", {lane: (row["bounced_m7"]["min"], row["bounced_m7"]["max"], row["front_back_past_centre_s"]["median"], row["red_wave_at_blue_tower_s"]["median"]) for lane, row in lanes.items()})
    for name, row in results["level_lead"].items():
        print(f"level lead {name}: crashes blue {row['blue_crashes']['mean']} red {row['red_crashes']['mean']}, largest blue {row['largest_blue_crash']['max']} red {row['largest_red_crash']['max']}, "
              f"tower damage red {row['red_tower_damage']['mean']:.0f} blue {row['blue_tower_damage']['mean']:.0f}")
    for scale, row in results["fight_speed"].items():
        print(f"fight speed x{scale}: placed fight {row['even_fight_s']} s, natural mid fight {row['natural_first_wave_fight_mid_s']} s, largest crash {row['largest_crash']['peak']} ({row['largest_crash']['case']}), "
              f"two-wave stacks {len(row['plans_with_a_two_wave_stack'])} (M7 first-tick measure {len(row['plans_with_12_at_first_touch_m7'])}), M7 freeze {row['m7_freeze_verdict']} {row['m7_longest_hold']}, aligned holds {row['phase_aligned_holds']}")
    print(f"wrote {RESULTS}")


if __name__ == "__main__":
    main()
