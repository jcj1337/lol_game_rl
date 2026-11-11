"""The lane contract the kernel is written against, and a pooled-health stand-in for the real wave model."""

import math
from typing import NamedTuple, Protocol

from riftgame import ruleset
from riftgame.map import load_map
from riftgame.rng import Stream, keyed_uniform
from riftgame.ruleset import scheduled

from experiments.m7.kernel.profiles import ASSUMPTIONS

R = ruleset.load()
M = R["minions"]
TEAMS = ("blue", "red")
GAP = ASSUMPTIONS["stub_engage_gap"]
UNIT_HP = (M["melee"]["hp"][0] + M["caster"]["hp"][0]) / 2
UNIT_DPS = (M["melee"]["ad"][0] * M["melee"]["attack_speed"] + M["caster"]["ad"][0] * M["caster"]["attack_speed"]) / 2
UNIT_GOLD = (M["melee"]["gold"] + M["caster"]["gold"]) / 2
UNIT_XP = (M["melee"]["xp"] + M["caster"]["xp"]) / 2
TOWER_UNITS_PER_S = R["towers"]["attack_speed"] * (M["melee"]["tower_shot_pct_max_hp"] + M["caster"]["tower_shot_pct_max_hp"]) / 2
TOWER_ARMOR = 100 / (100 + R["towers"]["armor"])


class ChampionInput(NamedTuple):
    champ_id: int
    team: int
    s: float
    mode: str
    hit_damage: float
    attack_speed: float
    attack_range: float
    aoe_dps: float
    capacity: float


class MinionDeath(NamedTuple):
    team: int
    s: float
    gold: float
    xp: float
    killer: int


class Tower:
    __slots__ = ("name", "team", "tier", "s", "hp", "target", "ramp")

    def __init__(self, name: str, team: int, tier: str, s: float, hp: float):
        self.name, self.team, self.tier, self.s, self.hp = name, team, tier, s, hp
        self.target, self.ramp = -1, 0.0


class Lane(Protocol):
    towers: list[Tower]

    def step(self, inputs: list[ChampionInput]) -> list[MinionDeath]: ...

    def front(self) -> float: ...

    def minions(self) -> list[tuple[int, float]]: ...


def lane_towers(name: str) -> list[Tower]:
    return [Tower(t.name, TEAMS.index(t.team), t.tier, t.s, float(R["towers"][t.tier]["hp"]))
            for t in load_map().towers if t.lane == name]


class StubLane:
    """Each team's minions are groups of [s, pooled hp], most advanced first. Groups merge when one reaches the next."""

    __slots__ = ("name", "lane_id", "seed", "dt", "tick", "length", "spawn_s", "next_spawn_s", "groups", "towers")

    def __init__(self, name: str, dt: float, seed: int, lane_id: int):
        m = load_map()
        self.name, self.lane_id, self.seed, self.dt, self.tick = name, lane_id, seed, dt, 0
        self.length = m.rift.lanes[name].length
        self.spawn_s = (m.minion_spawn_s[("blue", name)], m.minion_spawn_s[("red", name)])
        self.next_spawn_s = float(M["first_spawn_s"])
        self.groups: tuple[list, list] = ([], [])
        self.towers = lane_towers(name)

    def front(self) -> float:
        blue, red = self.groups
        if blue and red:
            return (blue[0][0] + red[0][0]) / 2
        return (blue or red)[0][0] if blue or red else self.length / 2

    def minions(self) -> list[tuple[int, float]]:
        return [(team, g[0]) for team in (0, 1) for g in self.groups[team]]

    def step(self, inputs: list[ChampionInput]) -> list[MinionDeath]:
        now = self.tick * self.dt
        if now >= self.next_spawn_s:
            for team in (0, 1):
                self.groups[team].append([self.spawn_s[team], ASSUMPTIONS["stub_wave_size"] * UNIT_HP])
            self.next_spawn_s += scheduled(M["interval_schedule"], now)
        self._march()
        events = self._fight(inputs)
        self.tick += 1
        return events

    def _march(self) -> None:
        reach = M["move_speed"] * self.dt
        fronts = [g[0][0] if g else None for g in self.groups]
        for team, sign in ((0, 1.0), (1, -1.0)):
            limit = min((sign * t.s for t in self.towers if t.team != team and t.hp > 0), default=math.inf) - GAP
            if fronts[0] is not None and fronts[1] is not None:
                limit = min(limit, sign * fronts[team] + max(0.0, (fronts[1] - fronts[0] - GAP) / 2))
            merged: list[list[float]] = []
            for s, hp in self.groups[team]:
                p = max(sign * s, min(sign * s + reach, limit))
                if merged and p >= limit:
                    merged[-1][1] += hp
                else:
                    merged.append([sign * p, hp])
                    limit = p
            self.groups[team][:] = merged

    def _fight(self, inputs: list[ChampionInput]) -> list[MinionDeath]:
        dt = self.dt
        fronts = [g[0] if g else None for g in self.groups]
        damage = [0.0, 0.0]
        engaged = fronts[0] is not None and fronts[1] is not None and fronts[1][0] - fronts[0][0] <= GAP + 1e-6
        if engaged:
            for team in (0, 1):
                damage[1 - team] += math.ceil(fronts[team][1] / UNIT_HP) * UNIT_DPS * dt
        for t in self.towers:
            foe = fronts[1 - t.team]
            if t.hp > 0 and foe is not None and abs(foe[0] - t.s) <= R["towers"]["attack_range"]:
                damage[1 - t.team] += TOWER_UNITS_PER_S * UNIT_HP * dt
                if not engaged and abs(foe[0] - t.s) <= GAP + 1e-6:
                    t.hp -= math.ceil(foe[1] / UNIT_HP) * UNIT_DPS * M["damage_to_towers"] * TOWER_ARMOR * dt
        farmers: tuple[list, list] = ([], [])
        for inp in inputs:
            foe = fronts[1 - inp.team]
            if inp.capacity > 0 and foe is not None and abs(foe[0] - inp.s) <= inp.attack_range + GAP:
                farmers[1 - inp.team].append(inp)
                if inp.mode != "last_hit":
                    hits = inp.hit_damage * inp.attack_speed + (inp.aoe_dps if inp.mode == "push" else 0.0)
                    damage[1 - inp.team] += hits * inp.capacity * dt
        events = []
        chance = ASSUMPTIONS["stub_last_hit_chance"]
        for team in (0, 1):
            group = fronts[team]
            if group is None or damage[team] <= 0:
                continue
            before = math.ceil(group[1] / UNIT_HP)
            group[1] -= damage[team]
            for k in range(before - max(0, math.ceil(group[1] / UNIT_HP))):
                killer = next((f.champ_id for i, f in enumerate(farmers[team])
                               if keyed_uniform(self.seed, Stream.LAST_HIT, self.lane_id, self.tick, team, k, i) < chance[f.mode]), -1)
                events.append(MinionDeath(team, group[0], UNIT_GOLD, UNIT_XP, killer))
            if group[1] <= 0:
                self.groups[team].pop(0)
        return events


class RealLane:
    """Adapter from the M7 wave prototype (experiments/m7/waves) to the kernel's Lane contract.

    That model has one tower a side, so the inner and inhibitor towers here never take minion damage. It shares XP
    only among the champions it is handed, so the kernel ignores its grants and shares XP by route distance itself.
    """

    __slots__ = ("sim", "towers", "length")
    CLUSTER = 300.0

    def __init__(self, name: str, dt: float, seed: int, lane_id: int):
        from experiments.m7.waves import lane as waves
        m = load_map()
        self.length = m.rift.lanes[name].length
        self.towers = lane_towers(name)
        outer = {t.team: t.s for t in self.towers if t.tier == "outer"}
        offset = (m.minion_spawn_s[("blue", name)] + self.length - m.minion_spawn_s[("red", name)]) / 2
        self.sim = waves.LaneSim(waves.LaneGeometry(self.length, offset, (outer[0], outer[1])), seed, lane_id, dt)

    def front(self) -> float:
        blue, red = self.sim.front().lead
        if blue is None or red is None:
            return self.length / 2 if blue is None and red is None else blue if red is None else red
        return (blue + red) / 2

    def minions(self) -> list[tuple[int, float]]:
        groups = []
        for team in (0, 1):
            last = None
            for s in sorted(s for s, _ in self.sim.units(team)):
                if last is None or s - last > self.CLUSTER:
                    groups.append((team, s))
                    last = s
        return groups

    def step(self, inputs: list[ChampionInput]) -> list[MinionDeath]:
        from experiments.m7.waves import lane as waves
        modes = {"last_hit": waves.Mode.LAST_HIT, "thin": waves.Mode.THIN, "push": waves.Mode.PUSH}
        events = self.sim.step([waves.ChampionInput(i.champ_id, i.team, i.s, modes[i.mode], i.hit_damage, i.attack_speed,
                                                    i.attack_range, i.aoe_dps, i.capacity) for i in inputs])
        for tower in self.towers:
            if tower.tier == "outer":
                tower.hp = self.sim.towers[tower.team].hp
        return [MinionDeath(int(e.team), e.s, e.gold, M[e.kind.name.lower()]["xp"], -1 if e.killer is None else e.killer)
                for e in events if isinstance(e, waves.MinionDeath)]
