"""Checkpoint C8: the scenarios of M7 section 9.5, rows 1 to 4, compared under two continuation styles.

  freeze_push_shove   Blue top freezes, slow-pushes, or shoves its wave.
  recall_or_stay      Blue mid, hurt and short of its next upgrade, recalls now, stays, shoves first, or backs off.
  jungler_botside     The red jungler was last seen at its gromp, bot side. Blue's carry shoves, holds, or backs off.
  jungle_options      Blue's jungler walks to gank top, clears an own camp, invades an enemy camp, or moves to mid river.

Each recipe of `experiments/m8/scenarios` runs its base game once, on the base tick that the recipe names, and the
overrides set the deciding champion there. That decision state is refined (`riftgame.clock.refine`) to each tick of
`TICKS` and to `REFERENCE`, with a decision every 2 s, so every tick compares one state. 0.25 s is the research
tick and 0.5 s the sensitivity, and the stability rule reads both. 0.125 s is a reference, not ground truth. It is
reported apart, with whether the research tick's rankings agree with it, and it enters no stability verdict: it
would make a ranking that is stable at the two research ticks uncertain over a numerical setting that the owner
named a reference. Each materialised scenario is saved under `results/c8_scenarios`, restored from the file, and
compared from the copy.
Every comparison runs both styles of `riftgame.policies` on both teams, and the hypotheses of `activity_v0` with
the red jungler in focus. The hindsight line runs from the source world and is reported apart.

Rollouts. Every recipe asks for 16. `activity_v0` draws nothing, so within one hypothesis the rollouts differ only
by the world seed, which the kernel draws on for minion targets, last-hit order, combat order, and camps. Most of the
spread between hypotheses is therefore in separate lines, and the rollouts measure the seed's part. "rollouts" in the
results counts the paired cells (line, alternative, consequence) whose standard error is not zero. 16 rollouts keep a
full run with the reference tick under the budget of about 25 minutes on 6 processes, and they give a standard
error of a quarter of the rollouts' spread.

The comparison content of `results/c8.json` is deterministic: a rerun gives the same bytes except the "run" block,
which records the time and the code.

Run: python -m experiments.m8.c8 [--report] [--workers N]
"""

import json
import sys
import time
from pathlib import Path

from experiments.m8.provenance import stamp
from riftgame import compare, scenario
from riftgame.lanes import RULESET_ID
from riftgame.world import World

HERE = Path(__file__).parent
RECIPES = HERE / "scenarios"
RESULTS = HERE / "results" / "c8.json"
SAVED = HERE / "results" / "c8_scenarios"
NAMES = ("freeze_push_shove", "recall_or_stay", "jungler_botside", "jungle_options")
RESEARCH = 0.25
TICKS = (RESEARCH, 0.5)
REFERENCE = 0.125
WORKERS = 6


def rounded(value):
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [rounded(item) for item in value]
    return value


def compare_recipe(name: str, workers: int) -> dict:
    text = (RECIPES / f"{name}.toml").read_text(encoding="utf-8")
    base = scenario.base_world(scenario.parse(text))

    def compared(tick_s: float) -> dict:
        path = SAVED / f"{name}@{tick_s:g}.pkl"
        scenario.save(scenario.build(scenario.parse(text, tick_s), World.restore(base.snapshot())), path)
        return compare.run(scenario.restore(path), workers)

    comparisons = [compared(tick_s) for tick_s in TICKS]
    reference = compared(REFERENCE)
    return {"recipe": (RECIPES / f"{name}.toml").relative_to(HERE.parents[1]).as_posix(), "comparisons": comparisons,
            "stability": compare.summarise(comparisons),
            "reference": {"comparison": reference, "agreement": compare.agreement(comparisons[TICKS.index(RESEARCH)], reference)}}


def spread(scenarios: dict) -> dict:
    """How many paired cells of the hypothesis lines have a standard error that is not zero."""
    cells = [m["se"] > 0 for row in scenarios.values() for c in row["comparisons"] for lines in c["lines"].values()
             for name, line in lines.items() if name != "weighted" for a in line["alternatives"].values() for m in a["metrics"].values()]
    return {"per line": scenarios[NAMES[0]]["comparisons"][0]["scenario"]["rollouts"], "cells": len(cells), "cells with spread": sum(cells)}


def report(results: dict) -> str:
    lines = [compare.NOTE, f"Ruleset {results['ruleset']}. Research ticks {' and '.join(f'{t:g} s' for t in results['ticks'])} for the "
             f"stability rule, and {results['reference tick']:g} s as a reference apart, a decision every 2 s. Each scenario's decision "
             "state is built once, on its base tick, and refined to each finer tick.",
             "Styles, each on both teams:"]
    lines += [f"  {name}: {note}" for name, note in results["styles"].items()]
    lines += ["Consequences, each apart, never summed:"] + [f"  {k}: {v}" for k, v in results["definitions"].items()]
    lines += results["rules"]
    r = results["rollouts"]
    lines.append(f"{r['per line']} rollouts per line. {r['cells with spread']} of {r['cells']} paired cells of the hypothesis lines have a standard error above zero.")
    for name, row in results["scenarios"].items():
        lines += ["", compare.report(name, row["comparisons"], row["stability"], reference=row["reference"])]
    run = results["run"]["config"]
    lines.append(f"\nWall time {run['wall_s']:.0f} s on {run['workers']} processes.")
    return "\n".join(lines)


def main() -> None:
    if "--report" in sys.argv:
        print(report(json.loads(RESULTS.read_text(encoding="utf-8"))))
        return
    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else WORKERS
    began = time.perf_counter()
    scenarios = {}
    for name in NAMES:
        start = time.perf_counter()
        scenarios[name] = compare_recipe(name, workers)
        print(f"{name}: {time.perf_counter() - start:.0f} s", flush=True)
    results = {"ruleset": RULESET_ID, "note": compare.NOTE, "ticks": list(TICKS), "reference tick": REFERENCE, "styles": compare.style_notes(),
               "definitions": compare.DEFINITIONS, "rules": [compare.VERDICT_RULE, compare.STABILITY_RULE],
               "scenarios": scenarios, "rollouts": spread(scenarios)}
    results["run"] = stamp([], {"ticks": list(TICKS), "reference tick": REFERENCE, "scenarios": list(NAMES), "workers": workers,
                                "wall_s": time.perf_counter() - began})
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps(rounded(results), indent=1), encoding="utf-8")
    print(report(rounded(results)))


if __name__ == "__main__":
    main()
