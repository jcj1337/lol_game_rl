"""Measurements of the M8 kernel with its lanes and economy.

  throughput  Simulated seconds per wall second on one process, for a random-action game and a farming game.
  profile     Where the time of the farming game goes.
  snapshot    Size and cost of a snapshot.
  intents     How the intents of a random-action game end.
  roam        The roam bound under the policy that always prefers to leave its lane, at two clock settings.
  farming     What each seat has after ten minutes of scripted farming, by ledger entry.

Run: python -m experiments.m8.kernel
"""

import cProfile
import json
import pickle
import pstats
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests"))

from test_world_roles import CLOCKS, GAME_S, LANERS, roam_soak  # noqa: E402
from worlds import patient  # noqa: E402

from experiments.m8.provenance import stamp  # noqa: E402
from riftgame.champions import LANES, ROLES, SEATS, TEAMS, Income, level_of  # noqa: E402
from riftgame.harness import farmer, random_legal, tick  # noqa: E402
from riftgame.lanes import RULESET_ID, MinionDeath  # noqa: E402
from riftgame.world import Config, World  # noqa: E402

RESULTS = Path(__file__).parent / "results" / "kernel.json"
POLICIES = {"random legal actions": random_legal, "scripted farming": farmer}
PLAY_S, RUNS = 600.0, 7


def game(policy, seed: int, seconds: float = PLAY_S) -> tuple[float, dict, World]:
    world = World(Config(), seed)
    ticks = round(seconds / world.config.tick_s)
    work = Counter()
    began = time.perf_counter()
    for _ in range(ticks):
        tick(world, policy)
        work["minion deaths"] += sum(type(e) is MinionDeath for _, e in world.events)
        work["champion deaths"] += sum(c.outcome_tick == world.tick - 1 and c.outcome.name == "DIED" for c in world.champions)
    wall = time.perf_counter() - began
    work["ticks"] = world.tick
    return seconds / wall, dict(work), world


def throughput() -> dict:
    out = {}
    rates = {name: [] for name in POLICIES}
    work = {}
    for run in range(RUNS):
        for name, policy in POLICIES.items():
            rate, done, _ = game(policy, 0)
            rates[name].append(rate)
            assert work.setdefault(name, done) == done, "the same seed must do the same work in every run"
    for name, values in rates.items():
        out[name] = {"median": statistics.median(values), "min": min(values), "max": max(values), "runs": RUNS, "work_per_run": work[name]}
    return out


def profile() -> dict:
    world = World(Config(), 0)
    profiler = cProfile.Profile()
    profiler.runcall(lambda: [tick(world, farmer) for _ in range(1200)])
    stats = pstats.Stats(profiler)
    watched = {("lanes.py", "step"): "lanes", ("economy.py", "lane_inputs"): "lane inputs", ("economy.py", "settle_lane"): "gold and XP",
               ("vision.py", "observe"): "observe", ("vision.py", "legal_mask"): "legal mask", ("world.py", "_move"): "movement", ("world.py", "_settle"): "settle"}
    shares = {}
    for (file, _, name), (_, _, _, cumulative, _) in stats.stats.items():
        label = watched.get((Path(file).name, name))
        if label and "riftgame" in file:
            shares[label] = cumulative / stats.total_tt
    return dict(sorted(shares.items(), key=lambda item: -item[1]))


def snapshot() -> dict:
    _, _, world = game(farmer, 0)
    saved = world.snapshot()

    def micros(call) -> float:
        took = []
        for _ in range(20):
            began = time.perf_counter()
            call()
            took.append(time.perf_counter() - began)
        return statistics.median(took) * 1e6

    return {"at_s": world.tick * world.config.tick_s, "pickled_bytes": len(pickle.dumps(saved)), "pickled_bytes_at_0_s": len(pickle.dumps(World().snapshot())),
            "take_us": micros(world.snapshot), "restore_us": micros(lambda: World.restore(saved)), "minions": sum(len(side) for name in LANES for side in world.lanes[name].minions)}


def intents() -> dict:
    world, ended = World(Config(), 2026), Counter()
    for _ in range(1200):
        tick(world, patient, check=True)
        ended += Counter(c.outcome.name for c in world.champions if c.outcome_tick == world.tick - 1)
    return dict(ended)


def roam() -> dict:
    out = {}
    for name, config in CLOCKS.items():
        rows = roam_soak(config, GAME_S)
        laners = [rows[seat] for seat in LANERS]
        shares = [row["roamed_after_s"] / row["window_s"] for row in laners]
        out[name] = {
            "longest_stretch_s": [min(row["longest_stretch_s"] for row in laners), max(row["longest_stretch_s"] for row in laners)],
            "stretch_bound_s": config.roam_cap_s + config.decision_ticks * config.tick_s,
            "roaming_share_after_first_allowance": [min(shares), max(shares)],
            "share_bound": max(config.roam_refill / (1 + config.roam_refill) + config.decision_ticks * config.tick_s / row["window_s"] for row in laners),
            "lowest_allowance_s": min(row["lowest_allowance_s"] for row in laners),
            "off_lane_share": [min(row["off_lane_s"] / GAME_S for row in laners), max(row["off_lane_s"] / GAME_S for row in laners)],
            "largest_step_over_speed_times_tick": max(row["largest_step_over_speed"] for row in rows),
            "junglers_always_unrestricted": all(rows[seat]["always_open"] for seat in SEATS if seat not in LANERS),
            "deaths": sum(row["jumps"]["DIED"] for row in rows),
        }
    return out


def farming() -> dict:
    _, _, world = game(farmer, 0)
    return {f"{TEAMS[c.team]} {ROLES[c.role]}": {"level": level_of(c.xp), "xp": c.xp, **{source.name.lower(): c.earned[source] for source in Income}}
            for c in world.champions}


def rounded(value):
    if isinstance(value, float):
        return round(value, 3)
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [rounded(item) for item in value]
    return value


def main() -> None:
    results = {"ruleset": RULESET_ID, "config": "tick 0.5 s, decision every 4 ticks", "game_s": PLAY_S, "throughput_sim_s_per_wall_s": throughput(),
               "profile_share_of_farming_game": profile(), "snapshot": snapshot(), "intents_ended_in_a_random_game": intents(), "roam": roam(),
               "after_600_s_of_scripted_farming": farming()}
    results["run"] = stamp([0, 3, 2026], {"runs": RUNS, "game_s": PLAY_S, "roam_game_s": GAME_S})
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps(rounded(results), indent=1), encoding="utf-8")
    for name, row in results["throughput_sim_s_per_wall_s"].items():
        print(f"throughput, {name}: median {row['median']:.0f} [{row['min']:.0f} to {row['max']:.0f}] sim s per wall s, {row['runs']} runs, work {row['work_per_run']}")
    print("profile:", rounded(results["profile_share_of_farming_game"]))
    print("snapshot:", rounded(results["snapshot"]))
    print("intents:", results["intents_ended_in_a_random_game"])
    for name, row in results["roam"].items():
        print(f"roam, {name}:", rounded(row))
    for seat, row in results["after_600_s_of_scripted_farming"].items():
        print(f"farming, {seat}:", rounded(row))
    print(f"wrote {RESULTS}")


if __name__ == "__main__":
    main()
