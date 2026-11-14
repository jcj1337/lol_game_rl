"""One stacking case at two ticks, side by side: every minion death with its wave, its killer, and its time, and
every half second the laners' places and the leads. A diagnostic of `tick_probe`, it patches the lane only to watch.

Run: python -m experiments.m8.waves.tick_trace CASE PLAN SEED [--ticks 0.125,0.5] [--rules NAME] [--until S]
"""

import argparse

from experiments.m8.waves import tick_probe
from experiments.m8.waves.agents import seat_of
from experiments.m8.waves.capabilities import CHAMPIONS, DECISION_S, SIDES, lane_of, stacking_run
from riftgame import world as world_module
from riftgame.champions import RIFT
from riftgame.lanes import LaneSim
from riftgame.world import Config


def record(case: str, plan: str, seed: int, tick_s: float, rules_name: str):
    side, champion, start, last_hits = tick_probe.CASES[case]
    team = SIDES[side]
    lane = lane_of(champion)
    role = CHAMPIONS[champion][0][0]
    seats = (seat_of(0, role), seat_of(1, role))
    deaths, rows = [], []
    hurt, tower_attack, step = LaneSim._hurt, LaneSim._tower_attack, world_module.World.step

    def watched_hurt(self, target, damage, killer, now, shared=False):
        alive = target.hp > 0
        hurt(self, target, damage, killer, now, shared)
        if alive and target.hp <= 0 and self.name == lane:
            by = f"seat {killer}" if killer is not None else "tower" if getattr(self, "_by_tower", False) else "minion"
            deaths.append((round(self._t0 + now, 4), "BR"[target.team], target.rules.kind.name.lower(), target.wave, target.uid, by))

    def watched_tower(self, tower, now):
        self._by_tower = True
        try:
            tower_attack(self, tower, now)
        finally:
            self._by_tower = False

    def watched_step(self, actions=None):
        step(self, actions)
        t = self.tick * self.config.tick_s
        if abs(t * 2 - round(t * 2)) < 1e-9:
            sim = self.lanes[lane]
            front = sim.front()
            places = [RIFT.lane_s(lane, self.champions[s].pos) for s in seats]
            rows.append((t, front.lead, front.counts, front.s, places, [self.champions[s].intent for s in seats],
                         [round(self.champions[s].hp) for s in seats]))

    LaneSim._hurt, LaneSim._tower_attack, world_module.World.step = watched_hurt, watched_tower, watched_step
    try:
        config = Config(tick_s=tick_s, decision_ticks=round(DECISION_S / tick_s))
        metrics, trace, began, biggest = stacking_run((champion, start, last_hits, plan, seed), tick_probe.RULES[rules_name], config, team)
    finally:
        LaneSim._hurt, LaneSim._tower_attack, world_module.World.step = hurt, tower_attack, step
    return metrics, began, deaths, rows


def fmt(value):
    return "-" if value is None else f"{value:.0f}" if isinstance(value, float) else str(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case")
    parser.add_argument("plan")
    parser.add_argument("seed", type=int)
    parser.add_argument("--ticks", default="0.125,0.5")
    parser.add_argument("--rules", default="m8 lane")
    parser.add_argument("--until", type=float, default=200.0)
    parser.add_argument("--since", type=float, default=0.0)
    parser.add_argument("--every", type=float, default=2.0)
    args = parser.parse_args()
    runs = {float(t): record(args.case, args.plan, args.seed, float(t), args.rules) for t in args.ticks.split(",")}
    for tick_s, (metrics, began, deaths, rows) in runs.items():
        print(f"tick {tick_s}: began {began}, first crash {metrics['first_crash_s']}, largest {metrics['largest_crash_peak']} "
              f"second wave {metrics['largest_crash_second_wave']}, gold {metrics['minion_gold']}")
    ticks = list(runs)
    by_t = [{r[0]: r for r in runs[t][3]} for t in ticks]
    print("time | " + " | ".join(f"tick {t}: leads B/R, counts, champ s B/R, hp" for t in ticks))
    t = args.since
    while t <= args.until:
        cells = []
        for table in by_t:
            r = table.get(round(t, 4))
            cells.append("?" if r is None else f"{fmt(r[1][0])}/{fmt(r[1][1])} {r[2][0]}v{r[2][1]} c{fmt(r[3])} @{fmt(r[4][0])}/{fmt(r[4][1])} hp{r[6]}")
        print(f"{t:6.1f} | " + " | ".join(cells))
        t += args.every
    print("deaths, side by side in order")
    lists = [[d for d in runs[t][2] if args.since <= d[0] <= args.until] for t in ticks]
    for i in range(max(map(len, lists))):
        print(f"{i:3d} " + " || ".join(" ".join(map(str, lst[i])) if i < len(lst) else "" for lst in lists))


if __name__ == "__main__":
    main()
