"""Incentive screen: what a laner earns in five minutes under each `LANE` action, over twelve lane states.

Every run is a full world, and the laner plays one entry of the action table for the whole window (with a walk to
its tower when it is low). The screen reports. It has no pass condition on which action earns most. If one action
earns most in every state, the output says so, and the handoff has to trace the cause to named mechanics.

Run: python -m experiments.m8.waves.incentives
"""

import json
import re
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from experiments.m8.provenance import stamp
from experiments.m8.waves import agents
from experiments.m8.waves.agents import Laner, always, seat_of
from experiments.m8.waves.harness import BLUE, RED, rounded, summarize, tower_damage
from riftgame.champions import MODES, STANDS, Income
from riftgame.lanes import RULESET_ID

SEEDS = range(5)
WINDOW_S = 300.0
WORKERS = 8
RESULTS = Path(__file__).parent / "results" / "incentives.json"
ACTIONS = tuple((mode, stand) for stand in STANDS for mode in MODES)
OPPONENTS = {"absent": None, "last hits": "last_hit", "pushes": "push"}
STATES = {}
for lane in ("top", "mid"):
    for opponent in OPPONENTS:
        STATES[f"{lane}, from first contact, opponent {opponent}"] = (lane, "first contact", opponent)
    for opponent in ("absent", "last hits", "pushes"):
        STATES[f"{lane}, after a crash at the own tower, opponent {opponent}"] = (lane, "own tower", opponent)


def earn(args) -> dict:
    """One laner at level 1 from 0:00. The window starts at first contact, or when a red push reaches blue's tower."""
    state, mode, stand, seed = args
    lane, start, opponent = STATES[state]
    world = agents.staged(seed, {lane: 1})
    began = []

    def opened(seen) -> bool:
        if not began and seen.contact and (start == "first contact" or seen.foe_at_own_tower):
            began.append(seen.time_s)
        return bool(began)

    def blue(seen):
        return (mode, stand) if opened(seen) else ("last_hit", "wave")

    def red(seen):
        if not began:
            return ("push", "wave") if start == "own tower" else ("last_hit", "wave") if OPPONENTS[opponent] else "leave"
        return (OPPONENTS[opponent], "wave") if OPPONENTS[opponent] else "leave"

    me = Laner(world, seat_of(BLUE, lane), blue)
    # An opponent that never comes to the lane stays on its fountain.
    foes = [Laner(world, seat_of(RED, lane), red)] if OPPONENTS[opponent] or start == "own tower" else []
    champion = world.champions[me.seat]
    before = []

    def stop(row) -> bool:
        if began and not before:
            before.append((champion.earned[Income.MINION], champion.xp))
        return bool(began) and row.t >= began[0] + WINDOW_S

    trace = agents.play(world, lane, [me, *foes], 900.0, stop)
    gold, xp = champion.earned[Income.MINION] - before[0][0], champion.xp - before[0][1]
    return {"gold": gold, "xp": xp, "gold_plus_xp": gold + xp, "own_tower_damage": tower_damage(trace.events, BLUE, began[0]),
            "enemy_tower_damage": tower_damage(trace.events, RED, began[0]), "lowest_health": me.lowest, "retreats": me.retreats, "deaths": me.deaths}


def main() -> None:
    jobs = [(state, mode, stand, seed) for state in STATES for mode, stand in ACTIONS for seed in SEEDS]
    with ProcessPoolExecutor(WORKERS) as pool:
        done = list(pool.map(earn, jobs, chunksize=4))
    runs: dict = {}
    for (state, mode, stand, _), metrics in zip(jobs, done):
        runs.setdefault(state, {}).setdefault(f"{mode}, {stand}", []).append(metrics)
    table = {state: {action: summarize(rows) for action, rows in by.items()} for state, by in runs.items()}
    winners = {state: max(by, key=lambda action: by[action]["gold_plus_xp"]["median"]) for state, by in table.items()}
    always_most = set(winners.values())
    results = {
        "ruleset": RULESET_ID,
        "seeds": list(SEEDS),
        "laner": "the top or mid profile of riftgame.champions at level 1 from 0:00, a placeholder. Gold is minion gold. XP is the champion's own.",
        "action_that_earns_most_by_state": winners,
        "one_action_earns_most_in_every_state": always_most.pop() if len(always_most) == 1 else None,
        "states": table,
    }
    results["run"] = stamp(SEEDS, {"window_s": WINDOW_S, "states": len(STATES), "actions": len(ACTIONS)})
    RESULTS.parent.mkdir(exist_ok=True)
    one_row_per_line = re.sub(r"\[[^\[\]]*\]|\{[^{}]*\}", lambda row: re.sub(r"\s+", " ", row.group()), json.dumps(rounded(results), indent=1))
    RESULTS.write_text(one_row_per_line, encoding="utf-8")
    for state, by in table.items():
        print(state, "->", winners[state], {action: round(row["gold_plus_xp"]["median"]) for action, row in by.items()})
    print("one action earns most in every state:", results["one_action_earns_most_in_every_state"])
    print(f"wrote {RESULTS}")


if __name__ == "__main__":
    main()
