"""Throughput of a scripted 15-minute game, for Q5. Each invocation writes one complete file with its own run block.

With no argument, measure both lane models at a decision every 5 s and write results/bench_tick1.0_decision5.json.
With the argument `start`, measure only the M8 starting clock (0.5 s tick, a decision every 2 s) on the real lane and
write results/bench_tick0.5_decision2.json.
"""

import cProfile
import json
import pstats
import statistics
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path

from experiments.m7.provenance import stamp

from experiments.m7.kernel.lanes import RealLane, StubLane
from experiments.m7.kernel.observe import encode, legal_mask, observe, run
from experiments.m7.kernel.policy import scripted
from experiments.m7.kernel.world import World

RESULTS_DIR = Path(__file__).parent / "results"
SEED, GAME_S, DECISION_S, RUNS, GAMES_PER_PROCESS, TIMED_BATCHES = 0, 900, 5, 7, 6, 3
START_TICK_S, START_DECISION_S = 0.5, 2
LANE_MODELS = {"stub": StubLane, "real": RealLane}
SUBSYSTEMS = {
    "lanes": ("_lanes",),
    "champions and intents": ("_spawn", "_act", "_combat", "_resolve"),
    "vision and memory": ("see",),
    "observation and encoding": ("observe", "encode", "legal_mask"),
    "policy": ("scripted",),
}


def agent(o):
    encode(o)
    legal_mask(o)
    return scripted(o)


def play(lane: str, dt: float = 1.0, seconds: int = GAME_S, decision_s: float = DECISION_S):
    w = World(seed=SEED, dt=dt, decision_interval=round(decision_s / dt), lane_factory=LANE_MODELS[lane])
    start = time.perf_counter()
    decisions = run(w, agent, round(seconds / dt))
    return time.perf_counter() - start, decisions, w


def worker(lane: str):
    _, decisions, w = play(lane)
    return decisions, w.counts


def spread(values: list[float], digits: int = 0) -> dict:
    return {"median": round(statistics.median(values), digits), "min": round(min(values), digits),
            "max": round(max(values), digits), "runs": len(values)}


def cpu_load_percent() -> float | None:
    command = ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).LoadPercentage"]
    try:
        return float(subprocess.run(command, capture_output=True, text=True, timeout=60).stdout.strip())
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def single_process(lane: str) -> dict:
    rates: dict[float, list[float]] = {1.0: [], 0.5: []}
    work = set()
    for _ in range(RUNS):
        for dt, sample in rates.items():
            seconds, decisions, w = play(lane, dt)
            sample.append(GAME_S / dt / seconds)
            if dt == 1.0:
                work.add((decisions, *w.counts.items()))
    if len(work) != 1:
        raise RuntimeError(f"runs of one seed did different work: {work}")
    decisions, *counts = work.pop()
    return {"ticks_per_s_dt_1.0": spread(rates[1.0]), "ticks_per_s_dt_0.5": spread(rates[0.5]),
            "game_seconds_per_s_dt_0.5": spread([r / 2 for r in rates[0.5]]),
            "work_per_game_dt_1.0": dict(counts) | {"agent_decisions": decisions}}


def profiled_shares(lane: str) -> dict:
    profiler = cProfile.Profile()
    profiler.enable()
    play(lane)
    profiler.disable()
    cumulative: dict[str, float] = {}
    for (path, _, name), (_, _, _, seconds, _) in pstats.Stats(profiler).stats.items():
        if "kernel" in path:
            cumulative[name] = cumulative.get(name, 0.0) + seconds
    shares = {label: round(sum(cumulative[n] for n in names) / cumulative["run"], 3) for label, names in SUBSYSTEMS.items()}
    return shares | {"run loop and submit": round(1.0 - sum(shares.values()), 3)}


def micro(lane: str) -> dict:
    _, _, w = play(lane, seconds=GAME_S // 2)

    def per_call_us(fn, n: int) -> float:
        start = time.perf_counter()
        for i in range(n):
            fn(i)
        return round((time.perf_counter() - start) / n * 1e6, 1)

    observations = [observe(w, i) for i in range(10)]
    snap = w.snapshot()
    if World.restore(snap).digest() != w.digest():
        raise RuntimeError("restore did not reproduce the state")
    return {"observe_encode_mask_us": per_call_us(lambda i: (o := observe(w, i % 10), encode(o), legal_mask(o)), 3000),
            "observe_us": per_call_us(lambda i: observe(w, i % 10), 3000),
            "encode_us": per_call_us(lambda i: encode(observations[i % 10]), 3000),
            "legal_mask_us": per_call_us(lambda i: legal_mask(observations[i % 10]), 3000),
            "snapshot_us": per_call_us(lambda i: w.snapshot(), 300),
            "restore_us": per_call_us(lambda i: World.restore(snap), 300),
            "snapshot_bytes": len(snap), "at_game_s": w.tick * w.dt}


def scaling(lane: str, expected_work: dict) -> dict:
    out = {}
    for processes in (1, 6, 12):
        games = processes * GAMES_PER_PROCESS
        walls = []
        with Pool(processes) as pool:
            pool.map(worker, [lane] * processes, chunksize=1)
            for _ in range(TIMED_BATCHES):
                start = time.perf_counter()
                done = pool.map(worker, [lane] * games, chunksize=1)
                walls.append(time.perf_counter() - start)
                if any(counts | {"agent_decisions": decisions} != expected_work for decisions, counts in done):
                    raise RuntimeError("a worker game did different work from the single-process game")
        out[processes] = {"games_per_hour": spread([games / wall * 3600 for wall in walls]),
                          "agent_decisions_per_s": spread([games * expected_work["agent_decisions"] / wall for wall in walls]),
                          "games_per_timed_batch": games}
    base = out[1]["games_per_hour"]["median"]
    for row in out.values():
        row["speedup_over_1_process"] = round(row["games_per_hour"]["median"] / base, 2)
    return out


def measure(lane: str) -> dict:
    single = single_process(lane)
    return {"single_process": single, "profiled_share_of_run_time": profiled_shares(lane), "micro": micro(lane),
            "processes": scaling(lane, single["work_per_game_dt_1.0"])}


def start_worker(_):
    _, decisions, w = play("real", START_TICK_S, decision_s=START_DECISION_S)
    return decisions, w.counts


def starting_values() -> dict:
    rates, work = [], set()
    for _ in range(RUNS):
        seconds, decisions, w = play("real", START_TICK_S, decision_s=START_DECISION_S)
        rates.append(GAME_S / seconds)
        work.add((decisions, *w.counts.items()))
    if len(work) != 1:
        raise RuntimeError(f"runs of one seed did different work: {work}")
    decisions, *counts = work.pop()
    out = {"cpu_load_percent_before": cpu_load_percent(), "lane": "real", "tick_s": START_TICK_S,
           "decision_every_s": START_DECISION_S, "game_s": GAME_S,
           "work_per_game": dict(counts) | {"agent_decisions": decisions},
           "single_process_game_seconds_per_s": spread(rates)}
    for processes in (5, 6):
        games = processes * GAMES_PER_PROCESS
        walls = []
        with Pool(processes) as pool:
            pool.map(start_worker, range(processes), chunksize=1)
            for _ in range(TIMED_BATCHES):
                start = time.perf_counter()
                done = pool.map(start_worker, range(games), chunksize=1)
                walls.append(time.perf_counter() - start)
                if any(d != decisions or dict(counts) != c for d, c in done):
                    raise RuntimeError("a worker game did different work from the single-process game")
        out[f"processes_{processes}"] = {
            "games_per_hour": spread([games / wall * 3600 for wall in walls]),
            "agent_decisions_per_s": spread([games * decisions / wall for wall in walls])}
    return out


def write(tick_s: float, decision_s: float, section: str, body: dict, config: dict) -> None:
    config = {"tick_s": tick_s, "decision_every_s": decision_s, "game_s": GAME_S, "single_process_runs": RUNS,
              "games_per_process": GAMES_PER_PROCESS, "timed_batches": TIMED_BATCHES} | config
    path = RESULTS_DIR / f"bench_tick{tick_s}_decision{decision_s}.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({section: body, "run": stamp([SEED], config)}, indent=1))
    print(json.dumps(body, indent=1))
    print(f"wrote {path}")


def main() -> None:
    if sys.argv[1:] == ["start"]:
        write(START_TICK_S, START_DECISION_S, "q5_starting_values", starting_values(), {"lanes": ["real"], "processes": [5, 6]})
        return
    q5 = {"cpu_load_percent_before": cpu_load_percent(), "game_s": GAME_S, "decision_every_s": DECISION_S}
    for lane in LANE_MODELS:
        q5[f"{lane}_lane"] = measure(lane)
    q5["cpu_load_percent_after"] = cpu_load_percent()
    write(1.0, DECISION_S, "q5_throughput", q5,
          {"lanes": list(LANE_MODELS), "processes": [1, 6, 12], "also_timed_single_process_at_tick_s": 0.5})


if __name__ == "__main__":
    main()
