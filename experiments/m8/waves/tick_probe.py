"""The wave cases whose accumulation verdict flips with the tick, at four ticks with a decision every 2 s.

Per case and tick it prints each seed's first crash, the largest crash with its waves, the last hits of each team's
laner by time since the plan began, and the accumulation verdict of `capabilities.stacking_verdict`. A setting runs
with every plan and every control, so the verdict is the one that the sweep gives. `--fights` prints instead the deaths
of an untouched lane's first waves at each tick. `--rules` names a lane of `RULES`: the M8 lane, the C7 lane without
the three in-tick rules, the C7 lane with one of them, and the tie-key diagnostic.

Run: python -m experiments.m8.waves.tick_probe [--rules NAME] [--cases NAME,...] [--ticks 0.125,0.5] [--json PATH] [--fights]
"""

import argparse
import json
import statistics
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from functools import partial

from experiments.m8.waves.capabilities import CHAMPIONS, PUSH_PLANS, SIDES, TICKS, DECISION_S, spread, stacking_run, stacking_verdict
from experiments.m8.waves.agents import seat_of
from riftgame.lanes import M8_LANE, LaneSim, MinionDeath, Team
from riftgame.world import Config

SEEDS = range(3)
WORKERS = 6
MARKS_S = (30, 60, 90, 120, 180, 240)
# name: (side, champion, start, opponent last hits)
CASES = {
    "blue top 1 own tower": ("blue", "top, level 1, from 0:00", "own tower", True),
    "blue top 1 first contact": ("blue", "top, level 1, from 0:00", "first contact", True),
    "red mid 3 first contact": ("red", "mid, level 3, from 2:30", "first contact", True),
    "red top 1 own tower": ("red", "top, level 1, from 0:00", "own tower", True),
}
RULES = {
    "m8 lane": M8_LANE,
    "c7 lane": replace(M8_LANE, acquire_on_arrival=False, walk_on_loss=False, march_to_standing=False),
    "c7 lane, acquire on arrival": replace(M8_LANE, walk_on_loss=False, march_to_standing=False),
    "c7 lane, walk on loss": replace(M8_LANE, acquire_on_arrival=False, march_to_standing=False),
    "c7 lane, march to standing": replace(M8_LANE, acquire_on_arrival=False, walk_on_loss=False),
    "no walk on loss": replace(M8_LANE, walk_on_loss=False),
    "tie by set": replace(M8_LANE, tie_by_set=True),
}


def run(job, rules_name: str):
    case, plan, tick_s, seed = job
    side, champion, start, last_hits = CASES[case]
    team = SIDES[side]
    config = Config(tick_s=tick_s, decision_ticks=round(DECISION_S / tick_s))
    metrics, trace, began, biggest = stacking_run((champion, start, last_hits, plan, seed), RULES[rules_name], config, team)
    role = CHAMPIONS[champion][0][0]
    seats = {"own": seat_of(team, role), "foe": seat_of(1 - team, role)}
    hits = {who: [e.t - began for e in trace.events if type(e) is MinionDeath and e.killer == seat and began is not None and e.t >= began]
            for who, seat in seats.items()}
    return job, {"first_crash_s": metrics["first_crash_s"], "largest_crash_peak": metrics["largest_crash_peak"],
                 "largest_by_wave": dict(sorted((biggest or {}).get("by_wave", {}).items())), "largest_crash_s": metrics["largest_crash_s"],
                 "last_hits": {who: [sum(t <= mark for t in times) for mark in MARKS_S] for who, times in hits.items()},
                 "metrics": metrics}


def probe(cases, ticks, rules_name: str, seeds=SEEDS, workers: int = WORKERS) -> dict:
    jobs = [(case, plan, tick_s, seed) for case in cases for plan in PUSH_PLANS for tick_s in ticks for seed in seeds]
    with ProcessPoolExecutor(workers) as pool:
        done = dict(pool.map(partial(run, rules_name=rules_name), jobs, chunksize=2))
    out = {}
    for case in cases:
        setting = CASES[case][1]
        for tick_s in ticks:
            rows = {plan: [done[case, plan, tick_s, seed] for seed in seeds] for plan in PUSH_PLANS}
            verdict = stacking_verdict({setting: {plan: spread([r["metrics"] for r in runs]) for plan, runs in rows.items()}})
            out.setdefault(case, {})[str(tick_s)] = {"accumulates": verdict["accumulates"][setting],
                                                     "plans": {plan: [{k: v for k, v in r.items() if k != "metrics"} for r in runs] for plan, runs in rows.items()}}
    return out


def first_wave_fight(lane: str, tick_s: float, rules_name: str, seed: int) -> dict:
    """The first waves of an untouched lane with every later wave removed: the first blow, the minion deaths
    after it, and how long until one team has no minion left."""
    sim = LaneSim(lane, seed, tick_s, RULES[rules_name])
    first_blow, deaths = None, []
    while sim.time < 200.0:
        events = sim.step(sim.tick)
        for team in Team:
            sim.minions[team][:] = [m for m in sim.minions[team] if m.wave == 1]
        sim.invalidate()
        deaths += [round(e.t, 3) for e in events if type(e) is MinionDeath]
        if first_blow is None and any(m.hp < m.max_hp for team in Team for m in sim.minions[team]):
            first_blow = sim.time
        if first_blow is not None and not all(sim.minions[team] for team in Team):
            break
    return {"first_blow": first_blow, "deaths": deaths, "ends": sim.time, "left": [len(sim.minions[team]) for team in Team]}


def fights(ticks, rules_name: str, seeds=SEEDS) -> None:
    for lane in ("top", "mid"):
        for tick_s in ticks:
            runs = [first_wave_fight(lane, tick_s, rules_name, seed) for seed in seeds]
            print(f"{lane} {tick_s:>5}: first blow {[r['first_blow'] for r in runs]}, ends {[r['ends'] for r in runs]}, left {[r['left'] for r in runs]}, "
                  f"deaths {runs[0]['deaths']}")


def mean(values):
    values = [v for v in values if v is not None]
    return round(statistics.mean(values), 2) if values else None


def show(out: dict) -> None:
    for case, by_tick in out.items():
        print(f"== {case}")
        for tick_s, row in by_tick.items():
            print(f"  tick {tick_s}: accumulates under {len(row['accumulates'])} plans {row['accumulates']}")
        for plan in PUSH_PLANS:
            print(f"  {plan}")
            for tick_s, row in by_tick.items():
                runs = row["plans"][plan]
                first = [r["first_crash_s"] for r in runs]
                print(f"    {tick_s:>5}: first crash {first} mean {mean(first)}; largest {[r['largest_crash_peak'] for r in runs]} "
                      f"waves {[r['largest_by_wave'] for r in runs]}; last hits own {[r['last_hits']['own'] for r in runs]} foe {[r['last_hits']['foe'] for r in runs]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules", default="m8 lane", choices=list(RULES))
    parser.add_argument("--cases", default=",".join(CASES))
    parser.add_argument("--ticks", default=",".join(map(str, TICKS)))
    parser.add_argument("--json")
    parser.add_argument("--fights", action="store_true")
    args = parser.parse_args()
    if args.fights:
        return fights([float(t) for t in args.ticks.split(",")], args.rules)
    out = probe(args.cases.split(","), [float(t) for t in args.ticks.split(",")], args.rules)
    show(out)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f)


if __name__ == "__main__":
    main()
