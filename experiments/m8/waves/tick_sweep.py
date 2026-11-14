"""The tick sweep of `capabilities` under a named lane, with its summary and the difference between the sides.

It runs `capabilities.verdict_counts` at four ticks with a decision every 2 s, on both sides, and prints per side the
verdict counts at each tick, the cases that keep each verdict at every tick, and for each metric the median
absolute shift from 0.125 s, the cases that move more across ticks than across seeds, and the mean at each tick.
The side bias is blue's value less red's per case, seed by seed, at each tick. `--from` reads the sweep from a
results file instead of running it, so the committed results give the baseline.

Run: python -m experiments.m8.waves.tick_sweep [--rules NAME] [--json PATH] [--from PATH]
"""

import argparse
import json
import statistics

from experiments.m8.waves.capabilities import BY_SEED, SIDES, TICKS, DECISION_S, flat, sensitivity, verdict_counts
from experiments.m8.waves.tick_probe import RULES
from riftgame.world import Config

WORKERS = 6


def sweep(rules_name: str, ticks=TICKS, seeds=range(3), workers: int = WORKERS) -> dict:
    return {side: {str(tick_s): verdict_counts(RULES[rules_name], Config(tick_s=tick_s, decision_ticks=round(DECISION_S / tick_s)), seeds, workers, team)
                   for tick_s in ticks} for side, team in SIDES.items()}


def side_bias(by_side: dict) -> dict:
    """Per metric and tick: over the cases and seeds with a value on both sides, the median and the mean of blue's
    value less red's, and how many are higher and lower."""
    out = {}
    for metric in BY_SEED:
        for tick_s in by_side["blue"]:
            blue, red = (flat(by_side[side][tick_s][metric]) for side in SIDES)
            gaps = [b - r for case in blue for b, r in zip(blue[case], red[case]) if b is not None and r is not None]
            out.setdefault(metric, {})[tick_s] = {"median": statistics.median(gaps) if gaps else None, "mean": statistics.mean(gaps) if gaps else None,
                                                  "higher": sum(g > 0 for g in gaps), "lower": sum(g < 0 for g in gaps), "n": len(gaps)}
    return out


def summary(by_side: dict) -> dict:
    out = {"sides": {}, "side_bias": side_bias(by_side)}
    for side, by_tick in by_side.items():
        spread = sensitivity(by_tick)
        out["sides"][side] = {
            "verdicts": {kind: {"unchanged": row["unchanged"], "cases": row["cases"], "true_at": row["true_at"], "flips": row["flips"]} for kind, row in spread["verdicts"].items()},
            "metrics": {metric: {key: row[key] for key in ("cases_with_a_value_in_every_run", "cases_moving_more_across_clocks_than_across_seeds",
                                                         "median_absolute_shift_from_reference", "mean_by_clock")} for metric, row in spread["metrics"].items()},
        }
    return out


def rnd(value):
    if isinstance(value, float):
        return round(value, 2)
    if isinstance(value, dict):
        return {k: rnd(v) for k, v in value.items()}
    return value


def show(result: dict) -> None:
    for side, row in result["sides"].items():
        for kind, verdict in row["verdicts"].items():
            print(f"[{side}] {kind}: unchanged in {verdict['unchanged']} of {verdict['cases']}, true at {verdict['true_at']}")
        for metric, m in row["metrics"].items():
            print(f"[{side}] {metric}: {m['cases_with_a_value_in_every_run']} cases, more across ticks than seeds in {m['cases_moving_more_across_clocks_than_across_seeds']}, "
                  f"median |shift| {rnd(m['median_absolute_shift_from_reference'])}, means {rnd(m['mean_by_clock'])}")
    for metric, by_tick in result["side_bias"].items():
        print(f"blue less red, {metric}: " + "; ".join(f"{t}: median {rnd(r['median'])} mean {rnd(r['mean'])} (+{r['higher']}/-{r['lower']} of {r['n']})" for t, r in by_tick.items()))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules", default="m8 lane", choices=list(RULES))
    parser.add_argument("--json")
    parser.add_argument("--from", dest="source")
    parser.add_argument("--workers", type=int, default=WORKERS)
    args = parser.parse_args()
    if args.source:
        by_side = json.loads(open(args.source, encoding="utf-8").read())["tick_sweep"]
    else:
        by_side = sweep(args.rules, workers=args.workers)
        if args.json:
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump({"rules": args.rules, "tick_sweep": by_side}, f)
    result = summary(by_side)
    show(result)
    if args.json and args.source:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f)


if __name__ == "__main__":
    main()
