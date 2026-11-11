"""Tick-level view of a lane. `describe` gives one line per call, and the module traces one M7 case.

Run: python -m experiments.m8.waves.trace "S4c top from first contact, thin 3 once, red absent" "m8 lane" 0 0.5 60 2.5
The arguments are the case, the configuration, the seed, the tick, the first second to print, and the print interval.
"""

import sys

from experiments.m8.waves import m7_tests
from riftgame.lanes import ChampionDamage, LaneSim, MinionDeath, Team, TowerDamage


def groups(sim: LaneSim, team: int) -> str:
    """Each group as kind, position, wave numbers, and member health, ordered along the lane."""
    by_spot: dict = {}
    for m in sim.minions[team]:
        by_spot.setdefault((round(m.s / 25) * 25, m.rules.kind.name[0]), []).append(m)
    parts = []
    for (s, kind), members in sorted(by_spot.items()):
        waves = "".join(str(w) for w in sorted({m.wave for m in members}))
        parts.append(f"{kind}{s}w{waves}:{'/'.join(str(round(m.hp)) for m in sorted(members, key=lambda m: m.hp))}")
    return " ".join(parts)


def describe(sim: LaneSim, events: list, inputs=()) -> str:
    deaths = [f"{Team(e.team).name[0]}{e.kind.name[0]}@{e.s:.0f}{'' if e.killer is None else ' by ' + str(e.killer)}" for e in events if type(e) is MinionDeath]
    tower = {Team(team).name[0]: round(sum(e.damage for e in events if type(e) is TowerDamage and e.team == team)) for team in Team}
    bitten = round(sum(e.damage for e in events if type(e) is ChampionDamage))
    stands = " ".join(f"{Team(c.team).name[0]}:{c.mode.name}{'' if c.in_path else '(aside)'}@{c.s:.0f}" for c in inputs)
    return f"{sim.time:7.2f} [{stands}] BLUE[{groups(sim, Team.BLUE)}] RED[{groups(sim, Team.RED)}] deaths={deaths} tower={tower} bitten={bitten}"


def main(case: str, config: str = "m8 lane", seed: str = "0", dt: str = "0.5", start: str = "0", every: str = "0.5") -> None:
    first, gap, due = float(start), float(every), [float(start)]
    step = LaneSim.step

    def traced(self, tick, inputs=(), level_lead=0.0):
        events = step(self, tick, inputs, level_lead)
        deaths = any(type(e) is MinionDeath for e in events)
        if self.time >= first and (self.time >= due[0] or deaths):
            print(describe(self, events, inputs))
            due[0] = self.time + gap
        return events

    LaneSim.step = traced
    try:
        metrics, _ = m7_tests.CASES[case](m7_tests.CONFIGS[config], int(seed), float(dt))
    finally:
        LaneSim.step = step
    print(metrics)


if __name__ == "__main__":
    main(*sys.argv[1:])
