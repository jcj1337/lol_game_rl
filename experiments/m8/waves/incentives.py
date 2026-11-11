"""Incentive screen: what a scripted laner earns in five minutes under each wave mode, over twelve lane states.

The screen reports. It has no pass condition on which mode earns most. If one mode earns most in every state, the
output says so, and the handoff has to trace the cause to named mechanics.

Run: python -m experiments.m8.waves.incentives
"""

import json
import re
from pathlib import Path

from experiments.m8.provenance import stamp
from experiments.m8.waves.harness import BLUE, RED, Laner, legacy_laner, make_lane, outer, rounded, run, summarize, tower_damage, under_tower
from riftgame.lanes import M8_LANE, MINIONS, RULESET_ID, MinionDeath, Mode, xp_share

SEEDS = range(5)
DT = 0.5
WINDOW_S = 300.0
RESULTS = Path(__file__).parent / "results" / "incentives.json"
MODES = (Mode.PASSIVE, Mode.LAST_HIT, Mode.THIN, Mode.PUSH, Mode.HOLD)
OPPONENTS = {"absent": None, "last hits": Mode.LAST_HIT, "pushes": Mode.PUSH}
STATES = {}
for lane in ("top", "mid"):
    for opponent in OPPONENTS:
        STATES[f"{lane}, from first contact, opponent {opponent}"] = (lane, "first contact", opponent, 0.0)
    STATES[f"{lane}, after a crash at the own tower, opponent absent"] = (lane, "own tower", "absent", 0.0)
    STATES[f"{lane}, after a crash at the own tower, opponent last hits"] = (lane, "own tower", "last hits", 0.0)
    STATES[f"{lane}, from first contact, opponent last hits, own team one level ahead"] = (lane, "first contact", "last hits", 1.0)


def earn(lane: str, start: str, opponent: str, level_lead: float, mode: Mode):
    def case(seed):
        sim = make_lane(lane, M8_LANE, seed, DT)
        geometry = sim.geometry
        blue = Laner(BLUE, outer(geometry, BLUE))
        began, met = [], []

        def policy(sim, events):
            front = sim.front()
            if front.s is not None and not met:
                met.append(sim.time)
            if not began and met and (start == "first contact" or under_tower(geometry, BLUE, front.lead[RED])):
                began.append(sim.time)
            if not began:
                return blue.act(sim, events, Mode.LAST_HIT) + [legacy_laner(sim, RED, Mode.PUSH)] * bool(met)
            red = OPPONENTS[opponent]
            return blue.act(sim, events, mode) + ([legacy_laner(sim, RED, red)] if red is not None else [])

        positions = []

        def stop(row) -> bool:
            positions.append((row.t, blue.s, blue.dead))
            return bool(began) and row.t >= began[0] + WINDOW_S

        trace = run(sim, policy, 3600.0, stop, level_lead)
        where = dict((round(t / DT), (s, dead)) for t, s, dead in positions)
        gold = xp = kills = 0.0
        for e in trace.events:
            if type(e) is not MinionDeath or e.team != RED or e.t < began[0]:
                continue
            s, dead = where.get(int(e.t // DT) + 1, (blue.s, blue.dead))
            if e.killer == BLUE:
                gold += e.gold
                kills += 1
            if not dead and abs(e.s - s) <= MINIONS["xp_range"]:
                xp += xp_share(e.xp, 1)
        report = blue.report()
        return {
            "gold": gold,
            "xp": xp,
            "gold_plus_xp": gold + xp,
            "minions_killed": kills,
            "own_tower_damage": tower_damage(trace.events, BLUE, began[0]),
            "enemy_tower_damage": tower_damage(trace.events, RED, began[0]),
            "lowest_health": report["champion_lowest_health"],
            "retreats": report["champion_retreats"],
            "died": report["champion_died"],
        }

    return case


def main() -> None:
    table, winners = {}, {}
    for state, (lane, start, opponent, level_lead) in STATES.items():
        table[state] = {mode.name.lower(): summarize([earn(lane, start, opponent, level_lead, mode)(seed) for seed in SEEDS]) for mode in MODES}
        winners[state] = max(table[state], key=lambda name: table[state][name]["gold_plus_xp"]["median"])
    always = set(winners.values())
    results = {
        "ruleset": RULESET_ID,
        "seeds": list(SEEDS),
        "dt": DT,
        "window_s": WINDOW_S,
        "laner": "the scripted champion of harness.Laner: 650 health, 30 armor, 65 damage, 0.65 attacks per second, range 550, all placeholders. XP counts alone in the lane, within 1500 units of the death.",
        "mode_that_earns_most_by_state": winners,
        "one_mode_earns_most_in_every_state": always.pop() if len(always) == 1 else None,
        "states": table,
    }
    results["run"] = stamp(SEEDS, {"dt": DT, "window_s": WINDOW_S, "states": len(STATES)})
    RESULTS.parent.mkdir(exist_ok=True)
    one_row_per_line = re.sub(r"\[[^\[\]]*\]|\{[^{}]*\}", lambda row: re.sub(r"\s+", " ", row.group()), json.dumps(rounded(results), indent=1))
    RESULTS.write_text(one_row_per_line, encoding="utf-8")
    print(f"gold + XP in {WINDOW_S:.0f} s, median over seeds {SEEDS.start}..{SEEDS.stop - 1} (gold, XP, lowest health, own tower damage)")
    for state, modes in table.items():
        print(state)
        for name, row in modes.items():
            mark = " <- most" if winners[state] == name else ""
            print(f"   {name:<9} {row['gold_plus_xp']['median']:7.0f}  ({row['gold']['median']:5.0f}, {row['xp']['median']:5.0f}, {row['lowest_health']['median']:.2f}, {row['own_tower_damage']['median']:6.0f}){mark}")
    print("one mode earns most in every state:", results["one_mode_earns_most_in_every_state"])
    print(f"wrote {RESULTS}")


if __name__ == "__main__":
    main()
