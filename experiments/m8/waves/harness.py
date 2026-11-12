"""Shared parts of the M8 wave experiments: a lane run loop, the scripted champions, and the metrics."""

import statistics
from dataclasses import dataclass
from typing import NamedTuple

from riftgame.lanes import (
    ADDED,
    MELEE_REACH,
    STAND_OFF,
    TOWER_MARGIN,
    TOWER_RANGE,
    ChampionDamage,
    ChampionInput,
    Front,
    Kind,
    LaneGeometry,
    LaneRules,
    LaneSim,
    MinionDeath,
    Mode,
    Team,
    TowerDamage,
    stance,
)

BLUE, RED = Team.BLUE, Team.RED
BODY = 2 * ADDED["minions"]["pathing_radius"]
WAVE_SPAN = 1500.0
CRASH_GAP_S = 5.0

LANER_HP = 650.0
LANER_ARMOR = 30.0
LANER_REGEN = 1.5
LANER_SPEED = 335.0
RETREAT_BELOW = 0.30
RETURN_ABOVE = 0.60


class Row(NamedTuple):
    t: float
    line: float | None
    lead_blue: float | None
    lead_red: float | None
    n_blue: int
    n_red: int
    contact: bool
    wave_blue: int


class Trace(NamedTuple):
    geometry: LaneGeometry
    rows: list[Row]
    events: list


def make_lane(name: str, rules: LaneRules, seed: int, dt: float, start_s: float = 0.0, geometry: LaneGeometry | None = None) -> LaneSim:
    return LaneSim(name, seed, dt, rules, geometry, start_s)


def outer(geometry: LaneGeometry, team: int) -> float:
    return geometry.towers[team][0]


def line(geometry: LaneGeometry, front: Front) -> float | None:
    """The contact point, or out of contact the lead minion of the team that has marched further from its spawn."""
    if front.s is not None:
        return front.s
    blue, red = front.lead
    if blue is None or red is None:
        return blue if red is None else red
    marched = [abs(lead - geometry.spawn[team]) for team, lead in zip(Team, front.lead)]
    if abs(marched[0] - marched[1]) < 1.0:
        return (blue + red) / 2
    return blue if marched[0] > marched[1] else red


def crowd(sim: LaneSim, team: int, s: float | None, span: float = WAVE_SPAN) -> int:
    return 0 if s is None else sum(abs(m.s - s) <= span for m in sim.minions[team])


class Crowding:
    """Where minion bodies would be in each other's way. The lane has no bodies, so this only counts.

    `overlapping` counts minions that stand within one body width of an ally in the same lateral slot, a place two
    bodies cannot share. `on_one_target` is the largest number of melee minions that attack one target at once.
    Both are taken on ticks with the waves in contact.
    """

    def __init__(self, sim: LaneSim):
        self.sim = sim
        self.minion_ticks = self.overlapping = self.on_one_target = 0

    def watch(self, row: "Row") -> None:
        if not row.contact:
            return
        for team in Team:
            minions = self.sim.minions[team]
            self.minion_ticks += len(minions)
            lines: dict = {}
            for m in minions:
                lines.setdefault(m.slot, []).append(m.s)
            for spots in lines.values():
                spots.sort()
                near = [b - a < BODY for a, b in zip(spots, spots[1:])]
                self.overlapping += sum(left or right for left, right in zip([False] + near, near + [False]))
            hits: dict = {}
            for m in minions:
                if m.rules.kind is Kind.MELEE and m.anchored and m.target is not None:
                    hits[id(m.target)] = hits.get(id(m.target), 0) + 1
            self.on_one_target = max(self.on_one_target, max(hits.values(), default=0))

    def report(self) -> dict:
        return {"overlapping_share": self.overlapping / self.minion_ticks if self.minion_ticks else 0.0, "most_melee_on_one_target": self.on_one_target}


def under_tower(geometry: LaneGeometry, tower_team: int, s: float | None) -> bool:
    return s is not None and abs(s - outer(geometry, tower_team)) <= TOWER_RANGE


def offset(geometry: LaneGeometry, s: float | None) -> float | None:
    """Distance past the lane centre toward red's side."""
    return None if s is None else geometry.direction(BLUE) * (s - geometry.centre)


def run(sim: LaneSim, policy, until: float, stop=lambda row: False, level_lead: float = 0.0) -> Trace:
    rows, events, last = [], [], []
    while sim.time < until - 1e-9:
        last = sim.step(sim.tick, policy(sim, last), level_lead)
        events += last
        front = sim.front()
        rows.append(Row(sim.time, line(sim.geometry, front), *front.lead, *front.counts, front.s is not None, crowd(sim, BLUE, front.lead[BLUE])))
        if stop(rows[-1]):
            break
    return Trace(sim.geometry, rows, events)


def at(trace: Trace, t: float) -> Row | None:
    return next((r for r in trace.rows if r.t >= t - 1e-9), None)


def cs_fraction(events: list, team: int, where=lambda death: True) -> float | None:
    deaths = [e for e in events if type(e) is MinionDeath and e.team != team and where(e)]
    return sum(e.killer == team for e in deaths) / len(deaths) if deaths else None


def tower_damage(events: list, team: int, start: float = 0.0, end: float = float("inf")) -> float:
    return sum(e.damage for e in events if type(e) is TowerDamage and e.team == team and e.tier == 0 and start <= e.t <= end)


def crash_spans(trace: Trace) -> list[list[float]]:
    """Runs of ticks with the blue lead minion inside the red outer tower's range, gaps under 5 s merged."""
    spans: list[list[float]] = []
    for r in trace.rows:
        if under_tower(trace.geometry, RED, r.lead_blue):
            if spans and r.t - spans[-1][1] <= CRASH_GAP_S:
                spans[-1][1] = r.t
            else:
                spans.append([r.t, r.t])
    return spans


class Crashes:
    """Each visit of one team's lead minion to the enemy outer tower's range, gaps under 5 s merged.

    A visit records its start, its end, the largest number of that team's minions within `zone` units of the tower's
    range at one moment, when that moment was, and how many minions each spawn wave had there at that moment.
    """

    def __init__(self, sim: LaneSim, team: int, zone: float = 600.0):
        self.sim, self.team, self.zone = sim, team, zone
        self.spans: list[dict] = []

    def watch(self, row: Row) -> None:
        geometry, foe = self.sim.geometry, 1 - self.team
        if not under_tower(geometry, foe, row.lead_blue if self.team == BLUE else row.lead_red):
            return
        near = [m for m in self.sim.minions[self.team] if abs(m.s - outer(geometry, foe)) <= TOWER_RANGE + self.zone]
        by_wave: dict = {}
        for m in near:
            by_wave[m.wave] = by_wave.get(m.wave, 0) + 1
        if self.spans and row.t - self.spans[-1]["end"] <= CRASH_GAP_S:
            span = self.spans[-1]
            span["end"] = row.t
            if len(near) > span["peak"]:
                span["peak"], span["peak_t"], span["by_wave"] = len(near), row.t, by_wave
        else:
            self.spans.append({"start": row.t, "end": row.t, "peak": len(near), "peak_t": row.t, "by_wave": by_wave})

    def largest(self) -> dict | None:
        return max(self.spans, key=lambda span: span["peak"], default=None)


def second_wave(span: dict | None) -> int:
    """The size of the second-largest wave in a crash at its largest moment. 0 for a crash of one wave."""
    sizes = sorted(span["by_wave"].values(), reverse=True) if span else []
    return sizes[1] if len(sizes) > 1 else 0


def waves_in_contact(sim: LaneSim, front: float, red_melee: int = 0, red_casters: int = 0) -> LaneSim:
    """Full-health waves in contact at `front`, with surplus red minions on their own lines."""
    caster_reach = 500.0
    sim.add_minion(BLUE, Kind.MELEE, front - MELEE_REACH / 2, count=3)
    sim.add_minion(RED, Kind.MELEE, front + MELEE_REACH / 2, count=3 + red_melee)
    sim.add_minion(BLUE, Kind.CASTER, front + MELEE_REACH / 2 - caster_reach, count=3)
    sim.add_minion(RED, Kind.CASTER, front - MELEE_REACH / 2 + caster_reach, count=3 + red_casters)
    return sim


def legacy_stand(sim: LaneSim, team: int, hold: bool = False) -> float:
    """Where M7's first scenario champion stands. It cannot die and jumps to this spot every tick."""
    geometry, front = sim.geometry, sim.front()
    heading = geometry.direction(team)
    own, foe = front.lead[team], front.lead[1 - team]
    if foe is not None:
        s = foe - heading * (MELEE_REACH if hold or front.s is not None else STAND_OFF)
    else:
        s = own if own is not None else outer(geometry, team)
    edge = outer(geometry, 1 - team) - heading * (TOWER_RANGE + TOWER_MARGIN)
    return min(s, edge) if heading > 0 else max(s, edge)


def legacy_laner(sim: LaneSim, team: int, mode: Mode, capacity: float = 1.0) -> ChampionInput:
    return ChampionInput(int(team), team, legacy_stand(sim, team), mode, capacity=capacity)


@dataclass
class Laner:
    """A scripted champion that walks, takes minion damage, retreats to its tower when low, and can die.

    Its numbers are placeholders for a level 1 to 3 laner. Below 30 percent health it walks to its own tower and
    stays out of the wave until it is back above 60 percent. At zero health it is dead for the rest of the run.
    """

    team: int
    s: float
    max_hp: float = LANER_HP
    armor: float = LANER_ARMOR
    regen: float = LANER_REGEN
    speed: float = LANER_SPEED
    hit_damage: float = 65.0
    attack_speed: float = 0.65
    attack_range: float = 550.0
    aoe_dps: float = 70.0
    hp: float | None = None
    lowest: float | None = None
    taken: float = 0.0
    tanked_s: float = 0.0
    retreats: int = 0
    retreating: bool = False
    dead: bool = False

    def __post_init__(self):
        self.hp = self.max_hp if self.hp is None else self.hp
        self.lowest = self.hp

    def act(self, sim: LaneSim, events: list, mode: Mode, hold: bool = False) -> list[ChampionInput]:
        """`hold` stands on the hold line while hitting in `mode`."""
        if self.dead:
            return []
        hits = sum(e.damage for e in events if type(e) is ChampionDamage and e.seat == self.team) * 100 / (100 + self.armor)
        self.taken += hits
        self.tanked_s += sim.tick_s * (hits > 0)
        self.hp = min(self.max_hp, self.hp - hits + self.regen * sim.tick_s)
        self.lowest = min(self.lowest, self.hp)
        if self.hp <= 0:
            self.dead = True
            return []
        if self.retreating:
            self.retreating = self.hp < RETURN_ABOVE * self.max_hp
        elif self.hp < RETREAT_BELOW * self.max_hp:
            self.retreating = True
            self.retreats += 1
        want, in_path = stance(sim, self.team, mode, self.attack_range, hold=hold)
        if self.retreating:
            home = sim.front_tower(self.team)
            want, in_path = (home.s if home is not None else sim.geometry.spawn[self.team]), False
        step = self.speed * sim.tick_s
        self.s += max(-step, min(step, want - self.s))
        return [ChampionInput(int(self.team), self.team, self.s, mode if in_path else Mode.PASSIVE, in_path,
                              self.hit_damage, self.attack_speed, self.attack_range, self.aoe_dps)]

    def report(self) -> dict:
        return {
            "champion_lowest_health": max(self.lowest, 0.0) / self.max_hp,
            "champion_end_health": max(self.hp, 0.0) / self.max_hp,
            "champion_damage": self.taken,
            "champion_tanked_s": self.tanked_s,
            "champion_retreats": self.retreats,
            "champion_died": self.dead,
        }


def summarize(runs: list[dict]) -> dict:
    summary = {}
    for name in runs[0]:
        values = [float(m[name]) for m in runs if m[name] is not None]
        summary[name] = {
            "median": statistics.median(values) if values else None,
            "mean": statistics.mean(values) if values else None,
            "min": min(values, default=None),
            "max": max(values, default=None),
            "n": len(values),
        }
    return summary


def rounded(value):
    if isinstance(value, float):
        return round(value, 3)
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [rounded(item) for item in value]
    return value
