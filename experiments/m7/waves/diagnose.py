"""Tick-level trace of one scenario case. Run: python -m experiments.m7.waves.diagnose "S5b k=4 hold" baseline 0 1.0 60"""

import sys
from functools import partial

from experiments.m7.waves import scenarios
from experiments.m7.waves.lane import ChampionDamage, LaneSim, MinionDeath, Team, TowerDamage


class Finished(Exception):
    pass


def groups(sim, team: Team) -> str:
    """Each group as kind, position, and the health of its members, ordered along the lane."""
    by_spot = {}
    for m in sim.bodies[team]:
        by_spot.setdefault((round(m.s), m.rules.kind.name[0]), []).append(round(m.hp))
    return " ".join(f"{kind}{s}:{'/'.join(map(str, sorted(hp)))}" for (s, kind), hp in sorted(by_spot.items()))


class Traced(LaneSim):
    seconds = 60.0

    def step(self, inputs=()):
        if self.time >= self.start_time + self.seconds:
            raise Finished
        events = super().step(inputs)
        deaths = [f"{e.team.name[0]}{e.kind.name[0]}@{e.s:.0f}{'' if e.killer is None else ' by ' + str(e.killer)}" for e in events if type(e) is MinionDeath]
        tower = {team.name: round(sum(e.damage for e in events if type(e) is TowerDamage and e.team is team)) for team in Team}
        bitten = round(sum(e.damage for e in events if type(e) is ChampionDamage))
        stands = " ".join(f"{Team(c.team).name[0]}:{c.mode.name}@{c.s:.0f}" for c in inputs)
        front = scenarios.line(self.geometry, self.front())
        print(f"{self.time:7.2f} front={front and round(front)} champions[{stands}] BLUE[{groups(self, Team.BLUE)}] RED[{groups(self, Team.RED)}] deaths={deaths} tower_damage={tower} champion_damage={bitten}")
        return events


def main(case: str, config: str = "baseline", seed: str = "0", dt: str = "1.0", seconds: str = "60") -> None:
    make = partial(type("Limited", (Traced,), {"seconds": float(seconds)}), mechanics=scenarios.CONFIGS[config])
    try:
        scenarios.CASES[case](make, int(seed), float(dt))
    except Finished:
        pass


if __name__ == "__main__":
    main(*sys.argv[1:])
