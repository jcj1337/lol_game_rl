"""Round trips from the outer tower: recall, buy on the fountain, walk back to the tower's site.

One row per lane, team, Homeguard case, and number of boot steps bought on the fountain. The walker is the lane's
laner, the carry in bot lane. Every trip starts at the same game time.

  trip_s             Measured in the world: the recall plus the walk, in whole ticks.
  arithmetic_s       The recall plus route length over speed, with the Homeguard rule in continuous time.
  waves_spawned      Minion waves that the lane's clock spawned during this trip.
  waves_any_start    The fewest and the most waves that a trip of this length spans, over every start time.

Without Homeguard means that the champion takes one point of damage on the tick it arrives on the fountain, which
blocks Homeguard for the walk. The speeds are placeholder profiles, so the times say how the rules add up and
nothing about when a recall pays.

Run: python -m experiments.m8.recall
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests"))

from test_recall import BOOTS_PRICES, TRIPS, idle, out, recall_ticks, walk_s, walk_ticks  # noqa: E402
from worlds import EVERY_TICK, staged  # noqa: E402

from experiments.m8.provenance import stamp  # noqa: E402
from riftgame.champions import OUTER_TOWER, ROLES, TEAMS, Income, capability_of  # noqa: E402
from riftgame.lanes import MINIONS, RULESET_ID  # noqa: E402
from riftgame.ruleset import scheduled  # noqa: E402

RESULTS = Path(__file__).parent / "results" / "recall.json"
START_S = 45.0
TICK_S = EVERY_TICK.tick_s


def trip(seat: int, lane: str, boots: int, homeguard: bool) -> dict:
    world = staged({seat: OUTER_TOWER[seat // 5][lane]})
    me = world.champions[seat]
    idle(world, START_S)
    # A purse that buys exactly `boots` boot steps, with a ledger that agrees with it.
    me.upgrades, me.gold = 0, float(sum(BOOTS_PRICES[:boots]))
    me.earned = [me.gold if source is Income.STARTING else 0.0 for source in Income]
    route, clock = out(world, seat), world.lanes[lane].clock
    waves = clock.wave
    recall_s = recall_ticks(world, seat) * TICK_S
    if not homeguard:
        world.damage_champion(seat, 1.0)
    speed = capability_of(me).move_speed
    walked_s = walk_ticks(world, seat, lane, route) * TICK_S
    trip_s = recall_s + walked_s
    interval = scheduled(MINIONS["interval_schedule"], START_S)
    return {"team": TEAMS[seat // 5], "lane": lane, "walker": ROLES[seat % 5], "homeguard": homeguard, "boot_steps": me.upgrades,
            "move_speed": speed, "route_units": round(route, 1), "recall_s": recall_s, "walk_s": walked_s, "trip_s": trip_s,
            "arithmetic_s": round(recall_s + walk_s(route, speed, homeguard), 3), "waves_spawned": clock.wave - waves,
            "waves_any_start": [math.floor(trip_s / interval), math.ceil(trip_s / interval)]}


def main() -> None:
    rows = [trip(seat, lane, boots, homeguard) for seat, lane in TRIPS for homeguard in (True, False) for boots in range(3)]
    results = {"ruleset": RULESET_ID, "config": "tick 0.5 s, a decision on every tick", "trip_starts_at_s": START_S,
               "wave_interval_s": scheduled(MINIONS["interval_schedule"], START_S), "trips": rows,
               "run": stamp([0], {"start_s": START_S, "tick_s": TICK_S})}
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps(results, indent=1), encoding="utf-8")
    for row in rows:
        print(f"{row['team']:<5}{row['lane']:<4} homeguard {row['homeguard']!s:<6} boot steps {row['boot_steps']}  speed {row['move_speed']:.0f}  "
              f"route {row['route_units']:>8.1f}  trip {row['trip_s']:>5.1f} s (arithmetic {row['arithmetic_s']:>6.3f})  "
              f"waves spawned {row['waves_spawned']}, any start {row['waves_any_start']}")
    print(f"wrote {RESULTS}")


if __name__ == "__main__":
    main()
