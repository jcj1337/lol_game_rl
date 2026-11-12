"""M7's wave cases and pass tests, unchanged, on the M8 lane.

The cases, the scripted plans, and the two verdicts are those of experiments/m7/waves/scenarios.py. Only the lane
underneath changes. The configuration `m7 rules` switches off what M7 did not model, so its numbers must equal the
`A+B` column of M7's waves.json. `m8 lane` is the lane that M8 ships.

Run: python -m experiments.m8.waves.m7_tests
"""

import json
import re
from dataclasses import asdict
from pathlib import Path

from experiments.m8.provenance import stamp
from experiments.m8.waves import harness
from experiments.m8.waves.harness import (
    BLUE,
    RED,
    Laner,
    Row,
    at,
    crash_spans,
    crowd,
    cs_fraction,
    legacy_laner,
    line,
    offset,
    outer,
    rounded,
    run,
    summarize,
    tower_damage,
    under_tower,
    waves_in_contact,
)
from riftgame.lanes import M7_LANE, M8_LANE, RULESET_ID, TOWER_RANGE, Kind, LaneRules, MinionDeath, Mode, Team, lane_geometry, stance

CONFIGS = {"m7 rules": M7_LANE, "m8 lane": M8_LANE}
SEEDS = range(5)
DTS = (0.125, 0.25, 0.5, 1.0)
REFERENCE_DT = 0.125
REPORT_DT = 0.5
TOLERANCE = 0.10
RESULTS = Path(__file__).parent / "results" / "m7_tests_on_m8_lane.json"
M7_RESULTS = Path(__file__).parents[2] / "m7" / "waves" / "results" / "waves.json"

BOUNCE_MARKS_S = (30, 60, 90, 120)
PERTURB_MARKS_S = (120, 180, 240, 300, 360)
FIGHT_START_S = 181.0
FIGHT_LIMIT_S = 55.0
BUILT_START_S = 180.0
BUILT_MARGIN = 300.0
SLOW_PUSH_LIMIT_S = 300.0
SLOW_PUSH_STACK = 12
AFTER_CRASH_S = 20.0
TOWER_ZONE = 600.0
FREEZE_BAND = 1500.0
FREEZE_RUN_S = 240.0
BREAKER_ARRIVES_S = 240.0
FREEZE_SURPLUS = (0, 2, 3, 4, 6)
THIN_OVER = (1, 2, 3, 4)
TRIM_TO = (2, 3, 4)
TOP, MID = lane_geometry("top"), lane_geometry("mid")
DRAW_KEY = {"lane_id": None}


def make_lane(*args, **kwargs):
    """M7 keyed every lane's draws with lane id 0. The port check sets that id to compare like with like."""
    sim = harness.make_lane(*args, **kwargs)
    if DRAW_KEY["lane_id"] is not None:
        sim.lane_id = DRAW_KEY["lane_id"]
    return sim


def idle(sim, events):
    return ()


def last_hitters(blue_capacity: float = 1.0):
    return lambda sim, events: [legacy_laner(sim, BLUE, Mode.LAST_HIT, blue_capacity), legacy_laner(sim, RED, Mode.LAST_HIT)]


def one_red_caster_short():
    removed = []

    def policy(sim, events):
        casters = [m for m in sim.minions[RED] if m.rules.kind is Kind.CASTER]
        if not removed and len(casters) == 3:
            sim.minions[RED].remove(casters[-1])
            removed.append(sim.time)
        return ()

    return policy


class HardPush:
    """Blue pushes from first contact until its wave is under the red tower, then leaves. Red last-hits until then if present."""

    def __init__(self, red_present: bool):
        self.red_present = red_present
        self.met = False
        self.stopped_at = None

    def __call__(self, sim, events):
        front = sim.front()
        if self.stopped_at is not None:
            return []
        if under_tower(sim.geometry, RED, front.lead[BLUE]):
            self.stopped_at = sim.time
            return []
        self.met = self.met or front.s is not None
        inputs = [legacy_laner(sim, RED, Mode.LAST_HIT)] if self.red_present else []
        return inputs + [legacy_laner(sim, BLUE, Mode.PUSH)] if self.met else inputs


def crash_metrics(trace, dt: float) -> dict:
    spans = crash_spans(trace)
    first = at(trace, spans[0][0]) if spans else None
    return {
        "crash_t": first.t if first else None,
        "crash_wave": first.wave_blue if first else None,
        "crashes": len(spans),
        "tower_damage_first_crash": tower_damage(trace.events, RED, spans[0][0] - dt, spans[0][1]) if spans else None,
    }


def fight(red_melee: int = 0, red_casters: int = 0):
    def case(rules, seed, dt):
        sim = waves_in_contact(make_lane("top", rules, seed, dt, FIGHT_START_S), TOP.centre, red_melee, red_casters)
        left = [6, 6 + red_melee + red_casters]
        while min(left) > 0 and sim.time < FIGHT_START_S + FIGHT_LIMIT_S:
            sim.step(sim.tick)
            left = [crowd(sim, team, TOP.centre) for team in Team]
        return {"fight_s": sim.time - FIGHT_START_S, "blue_left": left[BLUE], "red_left": left[RED]}, None

    return case


def undisturbed(lane: str):
    def case(rules, seed, dt):
        trace = run(make_lane(lane, rules, seed, dt), idle, 600.0)
        geometry = trace.geometry
        touch = next(r for r in trace.rows if r.contact)
        offsets = [offset(geometry, r.line) for r in trace.rows if r.t >= 120.0 and r.line is not None]
        damage = [tower_damage(trace.events, team) for team in Team]
        return {
            "first_contact_t": touch.t,
            "first_contact_s": touch.line,
            "offset_lo": min(offsets),
            "offset_hi": max(offsets),
            "blue_tower_damage": damage[BLUE],
            "red_tower_damage": damage[RED],
            "towers_untouched": max(damage) == 0,
        }, trace

    return case


def perturbed(lane: str):
    def case(rules, seed, dt):
        trace = run(make_lane(lane, rules, seed, dt), one_red_caster_short(), 600.0)
        geometry = trace.geometry
        metrics = {f"offset_{mark}": offset(geometry, at(trace, mark).line) for mark in PERTURB_MARKS_S}
        reached = next((r for r in trace.rows if under_tower(geometry, RED, r.lead_blue)), None)
        metrics["red_tower_reached_t"] = reached.t if reached else None
        metrics["red_tower_reached_wave"] = reached.wave_blue if reached else None
        metrics["blue_tower_reached_t"] = next((r.t for r in trace.rows if under_tower(geometry, BLUE, r.lead_red)), None)
        metrics["blue_tower_damage"] = tower_damage(trace.events, BLUE)
        metrics["red_tower_damage"] = tower_damage(trace.events, RED)
        return metrics, trace

    return case


def last_hit(blue_capacity: float = 1.0):
    def case(rules, seed, dt):
        trace = run(make_lane("mid", rules, seed, dt), last_hitters(blue_capacity), 600.0)
        offsets = [offset(MID, r.line) for r in trace.rows if r.t >= 120.0 and r.line is not None]
        return {"offset_lo": min(offsets), "offset_hi": max(offsets), "cs_blue": cs_fraction(trace.events, BLUE), "cs_red": cs_fraction(trace.events, RED)}, trace

    return case


def bounce(lane: str, red_present: bool = False):
    def case(rules, seed, dt):
        trace = run(make_lane(lane, rules, seed, dt), HardPush(red_present), 600.0)
        geometry = trace.geometry
        metrics = crash_metrics(trace, dt)
        crash = metrics["crash_t"]
        for mark in BOUNCE_MARKS_S:
            row = at(trace, crash + mark) if crash is not None else None
            metrics[f"offset_{mark}"] = offset(geometry, row.line) if row else None
        after = [offset(geometry, r.line) for r in trace.rows if crash is not None and crash < r.t <= crash + BOUNCE_MARKS_S[-1] and r.contact]
        metrics["deepest_offset"] = min(after, default=None)
        metrics["bounced"] = bool(after) and min(after) < 0
        metrics["red_cs_under_tower"] = cs_fraction(trace.events, RED, lambda death: under_tower(geometry, RED, death.s))
        return metrics, trace

    return case


def slow_push(lane: str, start: str, plan: str, red_last_hits: bool):
    def case(rules, seed, dt):
        sim = make_lane(lane, rules, seed, dt)
        geometry = sim.geometry
        blue = Laner(BLUE, outer(geometry, BLUE))
        began, crash, peak, met, casters = [], [], [0], [], [0]

        def policy(sim, events):
            front = sim.front()
            if front.s is not None and not met:
                met.append(sim.time)
            crashed_on_blue = under_tower(geometry, BLUE, front.lead[RED])
            if not began and met and (start == "first contact" or crashed_on_blue):
                began.append(sim.time)
            if not began:
                return blue.act(sim, events, Mode.LAST_HIT) + [legacy_laner(sim, RED, Mode.PUSH)] * (bool(met) and start == "red crash")
            casters[0] += sum(type(e) is MinionDeath and e.team == RED and e.kind is Kind.CASTER and e.killer == BLUE for e in events)
            caster_near = any(m.rules.kind is Kind.CASTER and abs(m.s - blue.s) <= 550.0 for m in sim.minions[RED])
            mode = {
                "last hit": Mode.LAST_HIT,
                "push": Mode.PUSH,
                "thin 3 once": Mode.THIN if casters[0] < 3 and caster_near else Mode.LAST_HIT,
                "thin casters": Mode.THIN if caster_near else Mode.LAST_HIT,
            }[plan]
            return blue.act(sim, events, mode) + [legacy_laner(sim, RED, Mode.LAST_HIT)] * red_last_hits

        def stop(row: Row) -> bool:
            if not began:
                return False
            if not crash and under_tower(geometry, RED, row.lead_blue):
                crash.append(row)
            if crash:
                peak[0] = max(peak[0], crowd(sim, BLUE, outer(geometry, RED), TOWER_RANGE + TOWER_ZONE))
            return row.t >= (crash[0].t + AFTER_CRASH_S if crash else began[0] + SLOW_PUSH_LIMIT_S)

        trace = run(sim, policy, 3600.0, stop)
        since = [r for r in trace.rows if began and r.t >= began[0] and (not crash or r.t <= crash[0].t)]
        return {
            "plan_start_t": began[0] if began else None,
            "crash_s": crash[0].t - began[0] if crash else None,
            "wave": crash[0].wave_blue if crash else None,
            "peak_at_tower": peak[0] if crash else None,
            "largest_wave": max((r.wave_blue for r in since), default=None),
            "gold": sum(e.gold for e in trace.events if type(e) is MinionDeath and e.killer == BLUE),
            **blue.report(),
        }, trace

    return case


def freeze(surplus: int, plan: str, thin_over: int | None = None, trim_to: int | None = None, breaker: bool = False, laner: dict | None = None):
    """`laner` overrides the scripted champion's placeholder numbers. M7's cases leave it out."""
    lo = outer(TOP, BLUE) + TOWER_RANGE
    hi = lo + FREEZE_BAND

    def case(rules, seed, dt):
        sim = waves_in_contact(make_lane("top", rules, seed, dt, BUILT_START_S), lo + BUILT_MARGIN, red_casters=surplus)
        blue = Laner(BLUE, stance(sim, BLUE, Mode.LAST_HIT, hold=True)[0], **(laner or {}))

        def policy(sim, events):
            inputs = []
            if plan == "push":
                inputs += blue.act(sim, events, Mode.PUSH)
            elif plan == "hold":
                front = line(sim.geometry, sim.front())
                red, own = crowd(sim, RED, front), crowd(sim, BLUE, front)
                thin = (thin_over is not None and red - own > thin_over) or (trim_to is not None and own == 0 and red > trim_to)
                inputs += blue.act(sim, events, Mode.THIN if thin else Mode.LAST_HIT, hold=True)
            if breaker and sim.time >= BREAKER_ARRIVES_S:
                inputs.append(legacy_laner(sim, RED, Mode.PUSH))
            return inputs

        trace = run(sim, policy, BUILT_START_S + FREEZE_RUN_S)
        inside = [r.line is not None and lo <= r.line <= hi for r in trace.rows]
        metrics = {
            "band_s": sum(inside) * dt,
            **blue.report(),
            "cs_blue": cs_fraction(trace.events, BLUE),
            "under_tower_s": sum(under_tower(TOP, BLUE, r.lead_red) for r in trace.rows) * dt,
            "blue_tower_damage": tower_damage(trace.events, BLUE),
            "pushed_out": any(r.lead_blue is not None and r.lead_blue > TOP.centre for r in trace.rows),
        }
        if breaker:
            after = [ok for r, ok in zip(trace.rows, inside) if r.t > BREAKER_ARRIVES_S]
            metrics["band_s_after_breaker"] = sum(after) * dt
            metrics["red_tower_reached"] = any(under_tower(TOP, RED, r.lead_blue) for r in trace.rows)
        return metrics, trace

    return case


def tower_farm(capacity: float):
    def case(rules, seed, dt):
        sim = make_lane("mid", rules, seed, dt, 181.0)
        edge = outer(MID, BLUE) + TOWER_RANGE
        sim.add_minion(RED, Kind.MELEE, edge + 100.0, count=6)
        sim.add_minion(RED, Kind.CASTER, edge + 400.0, count=6)
        trace = run(sim, lambda sim, events: [legacy_laner(sim, BLUE, Mode.LAST_HIT, capacity)], 215.0)
        deaths = [e for e in trace.events if type(e) is MinionDeath and e.team == RED]
        return {"cs_blue": cs_fraction(trace.events, BLUE), "red_deaths": len(deaths)}, trace

    return case


CASES = {
    "S0 fight 6v6": fight(),
    "S0 fight 6v7 caster": fight(red_casters=1),
    "S0 fight 6v7 melee": fight(red_melee=1),
    "S0 fight 6v10 casters": fight(red_casters=4),
    "S1b undisturbed mid": undisturbed("mid"),
    "S1b undisturbed top": undisturbed("top"),
    "S1b one caster short mid": perturbed("mid"),
    "S1b one caster short top": perturbed("top"),
    "S2 last hit": last_hit(),
    "S3b bounce mid": bounce("mid"),
    "S3b bounce top": bounce("top"),
}
SLOW_PUSH_LANES = ("top", "mid")
SLOW_PUSH_STARTS = ("first contact", "red crash")
SLOW_PUSH_PLANS = ("last hit", "push", "thin 3 once", "thin casters")
THIN_PLANS = ("thin 3 once", "thin casters")


def slow_push_name(lane: str, start: str, plan: str, red_last_hits: bool = False) -> str:
    return f"S4c {lane} from {start}, {plan}, red {'last hit' if red_last_hits else 'absent'}"


for lane_name in SLOW_PUSH_LANES:
    for start in SLOW_PUSH_STARTS:
        for plan in SLOW_PUSH_PLANS:
            for red_last_hits in (False, True):
                CASES[slow_push_name(lane_name, start, plan, red_last_hits)] = slow_push(lane_name, start, plan, red_last_hits)
for k in FREEZE_SURPLUS:
    CASES[f"S5c k={k} hold"] = freeze(k, "hold")
    for n in THIN_OVER:
        CASES[f"S5c k={k} hold, thin over {n}"] = freeze(k, "hold", n)
    for m in TRIM_TO:
        CASES[f"S5c k={k} hold, trim to {m}"] = freeze(k, "hold", trim_to=m)
    CASES[f"S5c k={k} absent"] = freeze(k, "absent")
    CASES[f"S5c k={k} push"] = freeze(k, "push")
    CASES[f"S5c k={k} hold, red breaker"] = freeze(k, "hold", breaker=True)
for capacity in (0.5, 0.25):
    CASES[f"S6 last hit capacity {capacity}"] = last_hit(capacity)
for capacity in (1.0, 0.5, 0.25):
    CASES[f"S6 tower capacity {capacity}"] = tower_farm(capacity)

TICK_METRICS = (
    ("S1b undisturbed mid", "first_contact_t"),
    ("S1b one caster short top", "red_tower_reached_t"),
    ("S1b one caster short top", "red_tower_reached_wave"),
    ("S2 last hit", "cs_blue"),
    ("S3b bounce mid", "crash_t"),
    (slow_push_name("top", "first contact", "push"), "crash_s"),
    (slow_push_name("top", "first contact", "thin 3 once"), "crash_s"),
    (slow_push_name("top", "first contact", "thin 3 once"), "wave"),
    (slow_push_name("top", "red crash", "thin casters"), "crash_s"),
    (slow_push_name("top", "red crash", "thin casters"), "wave"),
    ("S5c k=3 hold", "band_s"),
    ("S5c k=3 hold", "champion_lowest_health"),
    ("S5c k=4 hold, thin over 3", "band_s"),
    ("S5c k=4 hold, thin over 3", "champion_lowest_health"),
    ("S5c k=6 hold", "band_s"),
    ("S5c k=4 absent", "band_s"),
    ("S5c k=4 push", "band_s"),
)


def measure(rules: LaneRules, names, dt: float) -> dict:
    return {name: summarize([CASES[name](rules, seed, dt)[0] for seed in SEEDS]) for name in names}


def lane_verdict(cases: dict) -> dict:
    """M7's tests. stability: no undisturbed run damages a tower in 10 minutes. bounce: every run crosses back over the centre within 120 s of the crash."""
    untouched = [cases[f"S1b undisturbed {lane}"]["towers_untouched"] for lane in ("mid", "top")]
    bounced = [cases[f"S3b bounce {lane}"]["bounced"] for lane in ("mid", "top")]
    return {"stability": all(u["min"] == 1 for u in untouched), "bounce": all(b["min"] == 1 for b in bounced)}


def champion_plan_verdict(cases: dict) -> dict:
    """M7's tests. A slow push: some thinning plan reaches the red tower later than the push plan with a median of 12 or
    more minions within 1500 units of its lead. A freeze: some surplus and holding plan keeps the front in the band for
    over half the run in every seed, neither control does in any seed, and the champion neither dies nor retreats."""
    stacked, largest = {}, (0.0, None)
    for lane in SLOW_PUSH_LANES:
        for start in SLOW_PUSH_STARTS:
            for red_last_hits in (False, True):
                push = cases[slow_push_name(lane, start, "push", red_last_hits)]["crash_s"]["median"]
                for plan in THIN_PLANS:
                    name = slow_push_name(lane, start, plan, red_last_hits)
                    crash, wave = cases[name]["crash_s"]["median"], cases[name]["wave"]["median"]
                    if wave is None:
                        continue
                    largest = max(largest, (wave, name))
                    if push is not None and crash > push and wave >= SLOW_PUSH_STACK:
                        stacked[name] = wave
    held, held_by_an_immortal, best = {}, {}, (0.0, None)
    plans = ["hold"] + [f"hold, thin over {n}" for n in THIN_OVER] + [f"hold, trim to {m}" for m in TRIM_TO]
    for k in FREEZE_SURPLUS:
        controls = max(cases[f"S5c k={k} {control}"]["band_s"]["max"] for control in ("absent", "push"))
        for plan in plans:
            case = cases[f"S5c k={k} {plan}"]
            band = case["band_s"]
            best = max(best, (band["median"], f"k={k} {plan}"))
            if band["min"] > FREEZE_RUN_S / 2 > controls:
                held_by_an_immortal[f"k={k} {plan}"] = band["min"]
                if case["champion_died"]["max"] == 0 and case["champion_retreats"]["max"] == 0:
                    held[f"k={k} {plan}"] = band["min"]
    return {
        "slow_push": bool(stacked),
        "freeze": bool(held),
        "slow_push_cases": stacked,
        "largest_thinned_wave_at_red_tower": largest,
        "longest_hold": best,
        "freeze_cases": held,
        "freeze_cases_if_health_is_ignored": held_by_an_immortal,
    }


def relative(reference: float | None, value: float | None) -> float | None:
    if reference is None or value is None:
        return 0.0 if reference is value else None
    if reference == 0:
        return 0.0 if value == 0 else None
    return (value - reference) / abs(reference)


def tick_sensitivity(rules: LaneRules) -> dict:
    names = sorted({name for name, _ in TICK_METRICS})
    by_dt = {dt: measure(rules, names, dt) for dt in DTS}
    report = {}
    for name, metric in TICK_METRICS:
        reference = by_dt[REFERENCE_DT][name][metric]["median"]
        entry = {str(dt): by_dt[dt][name][metric]["median"] for dt in DTS}
        for dt in DTS:
            if dt != REFERENCE_DT:
                change = relative(reference, by_dt[dt][name][metric]["median"])
                entry[f"within_{dt}"] = change is not None and abs(change) <= TOLERANCE
        report[f"{name} / {metric}"] = entry
    return report


def port_check(cases: dict) -> dict:
    """Every metric of the `m7 rules` configuration against the `A+B` column of M7's results file."""
    reference = json.loads(M7_RESULTS.read_text(encoding="utf-8"))["cases"]["A+B"]
    compared, differing = 0, []
    missing = [f"{name} / {metric}" for name, metrics in reference.items() for metric in metrics if metric not in cases.get(name, {})]
    for name, metrics in cases.items():
        for metric, summary in metrics.items():
            if metric not in reference.get(name, {}):
                continue
            compared += 1
            theirs = reference[name][metric]
            if any(rounded(summary[key]) != theirs[key] for key in ("median", "min", "max")):
                differing.append(f"{name} / {metric}: m8 {rounded(summary['median'])} [{rounded(summary['min'])}..{rounded(summary['max'])}], m7 {theirs['median']} [{theirs['min']}..{theirs['max']}]")
    return {"metrics_in_m7_results": sum(len(metrics) for metrics in reference.values()), "metrics_compared": compared,
            "metrics_not_ported": missing, "metrics_differing": len(differing), "differing": differing}


def port_check_with_m7_draw_key() -> dict:
    """The same comparison with the lane id of the draw key set to M7's 0, so that only the port is compared."""
    DRAW_KEY["lane_id"] = 0
    try:
        return port_check(measure(M7_LANE, CASES, REPORT_DT))
    finally:
        DRAW_KEY["lane_id"] = None


def main() -> None:
    cases = {config: measure(rules, CASES, REPORT_DT) for config, rules in CONFIGS.items()}
    results = {
        "ruleset": RULESET_ID,
        "seeds": list(SEEDS),
        "dt": REPORT_DT,
        "configs": {config: asdict(rules) for config, rules in CONFIGS.items()},
        "port_check_m7_rules_against_m7_results": port_check(cases["m7 rules"]),
        "port_check_with_m7_draw_key": port_check_with_m7_draw_key(),
        "verdicts": {config: lane_verdict(cases[config]) | champion_plan_verdict(cases[config]) for config in CONFIGS},
        "tick_sensitivity_m8_lane": tick_sensitivity(M8_LANE),
        "cases": cases,
    }
    results["run"] = stamp(SEEDS, {"report_dt": REPORT_DT, "tick_sweep_dts": DTS, "reference_dt": REFERENCE_DT, "tolerance": TOLERANCE, "cases": len(CASES)})
    RESULTS.parent.mkdir(exist_ok=True)
    one_row_per_line = re.sub(r"\[[^\[\]]*\]|\{[^{}]*\}", lambda row: re.sub(r"\s+", " ", row.group()), json.dumps(rounded(results), indent=1))
    RESULTS.write_text(one_row_per_line, encoding="utf-8")
    check = results["port_check_m7_rules_against_m7_results"]
    print(f"port check: {check['metrics_compared']} of {check['metrics_in_m7_results']} metrics of M7's A+B column compared, {check['metrics_differing']} differ, {len(check['metrics_not_ported'])} not ported")
    print(f"  cases that differ: {sorted({row.split(' / ')[0] for row in check['differing']})}")
    keyed = results["port_check_with_m7_draw_key"]
    print(f"port check with M7's draw key: {keyed['metrics_compared']} compared, {keyed['metrics_differing']} differ")
    for config, verdict in results["verdicts"].items():
        print(f"verdict {config}: " + ", ".join(f"{name}={value}" for name, value in verdict.items()))
    sweep = results["tick_sensitivity_m8_lane"]
    inside = sum(entry[f"within_{REPORT_DT}"] for entry in sweep.values())
    print(f"tick sweep, m8 lane: {inside} of {len(sweep)} metrics within {TOLERANCE:.0%} of the {REFERENCE_DT} s reference at {REPORT_DT} s")
    for key, entry in sweep.items():
        if not entry[f"within_{REPORT_DT}"]:
            print("   moves:", key, {str(dt): entry[str(dt)] for dt in DTS})
    print(f"wrote {RESULTS}")


if __name__ == "__main__":
    main()
