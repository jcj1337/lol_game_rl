"""What the fog of C6 hides, and how far the leak tests reach.

  hidden_state  How many hidden things the hidden-state test changes, per kind, with every observation unchanged.
  behaviour     How many ticks the behaviour test compares before something is revealed, and what it covers.
  seen          In scripted games, the share of time on which a team sees each enemy champion and each enemy
                wave, and how many sight sources of each kind it has.

The first two sections run the comparisons of `tests/test_vision.py` and report their sizes. The assertions are
in the tests.

Run: python -m experiments.m8.vision
"""

import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests"))

from test_vision import GAMES, SNAPSHOTS, comparisons, game, knowledge, scramble  # noqa: E402

from experiments.m8.provenance import stamp  # noqa: E402
from riftgame.champions import LANES, ROLES  # noqa: E402
from riftgame.harness import random_legal, scripted, tick  # noqa: E402
from riftgame.lanes import RULESET_ID  # noqa: E402
from riftgame.vision import sources  # noqa: E402
from riftgame.world import Config, World  # noqa: E402

RESULTS = Path(__file__).parent / "results" / "vision.json"
SEEDS = range(5)
PLAY_S = 600.0
POLICIES = {"scripted farming and jungling": scripted, "random legal actions": random_legal}


def hidden_state() -> dict:
    total = {"champions": 0, "dead": 0, "minions": 0, "camps": 0, "wards": 0}
    worlds = same = 0
    for seed, enemy in GAMES:
        for team in (0, 1):
            for ticks in SNAPSHOTS:
                world = game(seed, enemy, team, ticks)
                twin = World.restore(world.snapshot())
                changed = scramble(twin, team, random.Random(seed + ticks))
                worlds += 1
                same += knowledge(twin, team) == knowledge(world, team)
                for name in total:
                    total[name] += changed[name] if name in ("minions", "wards") else len(changed[name])
    return {"worlds": worlds, "worlds_with_every_observation_encoding_and_mask_unchanged": same, "hidden_things_changed": total}


def behaviour() -> dict:
    reports = [report for seed, enemy in GAMES for team in (0, 1) for report in comparisons(seed, enemy, team)]
    compared = sorted(report["compared"] for report in reports)
    return {
        "comparisons": len(reports),
        "ticks_compared": sum(compared),
        "ticks_compared_by_comparison": compared,
        "comparisons_that_reached_a_reveal": sum(report["revealed"] for report in reports),
        "intent_kinds_covered": sorted(kind.name for kind in set().union(*(report["kinds"] for report in reports))),
        "champion_ticks_in_a_fight_with_the_target_out_of_view": sum(report["blind"] for report in reports),
    }


def seen(policy, seed: int) -> dict:
    """One game: per team, the share of ticks on which it sees each living enemy champion and has a current record
    of each lane's enemy wave while that lane has enemy minions, and its mean number of wards."""
    world = World(Config(), seed)
    ticks = round(PLAY_S / world.config.tick_s)
    alive = [[0] * 5 for _ in range(2)]
    shown = [[0] * 5 for _ in range(2)]
    waves = [[0] * 3 for _ in range(2)]
    known = [[0] * 3 for _ in range(2)]
    wards = [0, 0]
    for _ in range(ticks):
        tick(world, policy)
        for team in range(2):
            memory = world.memory[team]
            for role, (enemy, record) in enumerate(zip(world.champions[(1 - team) * 5:(2 - team) * 5], memory.enemies)):
                alive[team][role] += enemy.hp > 0
                shown[team][role] += enemy.hp > 0 and record.seen_tick == world.tick
            for i, (name, wave) in enumerate(zip(LANES, memory.waves)):
                there = bool(world.lanes[name].minions[1 - team])
                waves[team][i] += there
                known[team][i] += there and wave.seen_tick == world.tick
            wards[team] += sum(s.team == team and s.owner >= 0 for s in world.sights)
    out = {}
    for team in range(2):
        out |= {f"team {team} sees enemy {ROLES[role]}": shown[team][role] / alive[team][role] for role in range(5)}
        out |= {f"team {team} sees the enemy wave in {name}": known[team][i] / waves[team][i] for i, name in enumerate(LANES) if waves[team][i]}
        out[f"team {team} wards on the map"] = wards[team] / ticks
        out[f"team {team} sight sources at the end, without minions"] = len(sources(world, team))
    return out


def summary(runs: list[dict]) -> dict:
    return {name: {"median": statistics.median(run[name] for run in runs), "min": min(run[name] for run in runs), "max": max(run[name] for run in runs)}
            for name in runs[0]}


def main() -> None:
    results = {"ruleset": RULESET_ID, "hidden_state": hidden_state(), "behaviour": behaviour(),
               "seen": {name: summary([seen(policy, seed) for seed in SEEDS]) for name, policy in POLICIES.items()}}
    results["run"] = stamp(SEEDS, {"play_s": PLAY_S, "games": GAMES, "snapshots": SNAPSHOTS})
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print("hidden state:", results["hidden_state"])
    print("behaviour:", results["behaviour"])
    for name, rows in results["seen"].items():
        print(name)
        for key, row in rows.items():
            print(f"  {key}: {row['median']:.3f} [{row['min']:.3f} to {row['max']:.3f}]")
    print(f"wrote {RESULTS}")


if __name__ == "__main__":
    main()
