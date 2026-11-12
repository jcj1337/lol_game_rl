"""Lanes: the minions and towers of one lane, on the lane coordinate `s`.

One `LaneSim` serves every lane. It owns the lane's minions, its six towers, and its wave clock. Champions enter
only as per-tick `ChampionInput`s, and everything that crosses into the rest of the world leaves as an event.
`LaneRules` names each optional rule, so an experiment can switch one rule and nothing else.

A tower has one attack for minions and champions, so its shots on champions are here, and so are a champion's
hits on a tower. Both happen only where an input asks for them: a tower shoots a champion whose input is a
`tower_target`, and a champion hits a tower when its input says `siege`.
"""

import heapq
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntEnum
from math import hypot, inf

from riftgame.map import load_map
from riftgame.rng import Stream, keyed_uniform
from riftgame.ruleset import interpolated, load, scheduled

RULES = load()
ADDED = load("patch_26_22_m8")
RULESET_ID = ADDED["meta"]["id"]
MINIONS = RULES["minions"]
TOWERS = RULES["towers"]
SIDE_SPEED = ADDED["minions"]["side_lane_speed"]
PUSHING = ADDED["minions"]["pushing_advantage"]
TIMING = ADDED["minions"]["attack_timing"]
SPEED = MINIONS["move_speed"]
ACQUIRE = MINIONS["acquisition_range"]
CALL_RANGE = ADDED["minions"]["call_for_help_range"]
XP_SHARE = MINIONS["xp_share"]
DAMAGE_TO_CHAMPIONS = MINIONS["damage_to_champions"]
TOWER_RANGE = TOWERS["attack_range"]
TOWER_ATTACK_SPEED = TOWERS["attack_speed"]
TOWER_ADDED = ADDED["towers"]
RAMP_PER_HIT = TOWERS["champion_ramp_per_hit"]
RAMP_MAX = TOWERS["champion_ramp_max"]
RAMP_RESET_S = TOWER_ADDED["champion_ramp_reset_s"]
SWITCH_RANGE = TOWERS["target_switch_range"]
ARMOR = TOWERS["armor"]
ARMOR_HALVING = TOWER_ADDED["armor_halving"]
MELEE_TAKEN = TOWERS["melee_champion_damage_taken"]
BACKDOOR = TOWERS["backdoor_damage_reduction"]
BACKDOOR_RANGE = TOWER_ADDED["backdoor_minion_range"]
PLATES = tuple(TOWERS["plate_break_missing_hp"])
TIERS = ("outer", "inner", "inhibitor")
LANE_NAMES = ("top", "mid", "bot")
EPS = 1e-6
SAME_INSTANT = 1e-9
CHAMPION_KEY = 1 << 40
BLOW, START, RELEASE, LAND = range(4)
SLOTS = (-1, 0, 1)
STAND_OFF = 550.0
HOLD_MARGIN = 300.0
TOWER_MARGIN = 50.0


class Team(IntEnum):
    BLUE = 0
    RED = 1


class Kind(IntEnum):
    MELEE = 0
    CASTER = 1
    SIEGE = 2


class Mode(IntEnum):
    """What a champion at a wave hits. Where it stands is a separate choice: with the wave, or on the hold line."""

    PASSIVE = 0
    LAST_HIT = 1
    THIN = 2
    PUSH = 3


@dataclass(frozen=True, slots=True)
class LaneRules:
    """The optional rules of the lane. The defaults are the M8 lane.

    champion_aggro: a minion with no enemy minion or tower in acquisition range attacks the closest enemy champion
    that stands in its path.
    lateral_slots: a minion keeps a lateral slot in its wave and, among enemies equally far along the lane, picks the
    laterally closest. An assumption about formation, not a sourced rule.
    current_hp_damage: a minion blow on a minion adds the reference share of the target's current health.
    side_lane_speed: top and bot minions of wave 2 and later spawn with the reference speed bonus.
    call_for_help: a minion within call range of an enemy champion that is attacking an allied champion targets that
    champion, unless the minion is attacking a tower. It is the top tier of the reference priority list.
    pushing_advantage: from 3:30 the minions of the team with the higher average level deal more damage to enemy
    minions and take less from them.
    melee_cap: at most this many melee minions attack one target, 0 for no limit. A diagnostic bound on what unit
    collision could do to a fight, not a rule of the M8 lane.
    minion_damage_scale: scales every minion blow on a minion. A diagnostic for how fight length changes the lane,
    not a rule of the M8 lane.
    straight_ranges: every range inside the lane is the straight line on the map: acquisition, attack, tower, and
    call ranges, between minions, towers, and champions alike. Marching stays on the lane coordinate. Without the
    rule a range is a distance along the lane, which is longer around a lane corner.
    tower_shelter: a champion inside the range of a standing lane tower is not attacked for standing in the
    minions' path. A call for help still reaches it.
    first_wave_call: minions of the first wave answer a call for help even while they attack a tower.
    attack_timing: a minion's blow leaves it one cast time after the attack starts, and a caster's or a siege
    minion's blow then flies to its target. A cast whose target dies or leaves reach is cancelled and starts again
    on a new target. A missile whose target dies in flight is lost. Without the rule every blow lands at the
    instant the attack is ready. Tower shots and champion hits are instant either way.
    free_cancel: a cast whose target died lands on the new target when the old cast would have landed, so a
    cancelled cast costs nothing. A diagnostic for how much rests on the unsourced cancel, not a rule of the M8 lane.
    missiles_turn: a missile whose target died lands on whatever its shooter can reach now. A diagnostic for how
    much rests on the unsourced lost missile, not a rule of the M8 lane.
    detour_s: a melee minion that turns to a new minion target loses this long before its cast, as if it walked
    around other bodies to reach it. A diagnostic bound on movement obstruction, not a rule of the M8 lane. It
    needs attack_timing.
    m7_resolution: resolve three details as M7's lane did, so that its results can be reproduced. A minion whose target
    dies inside a tick may hit a champion in reach although an enemy minion is in acquisition range. Champions that
    attack at the same instant are served in input order. A champion that leaves the lane keeps its attack credit.
    The M8 lane keeps the target priority on every retarget, orders such champions by a keyed draw, and gives a
    returning champion a ready attack.
    """

    champion_aggro: bool = True
    lateral_slots: bool = True
    current_hp_damage: bool = True
    side_lane_speed: bool = True
    call_for_help: bool = True
    pushing_advantage: bool = True
    melee_cap: int = 0
    minion_damage_scale: float = 1.0
    straight_ranges: bool = True
    tower_shelter: bool = True
    first_wave_call: bool = True
    attack_timing: bool = True
    free_cancel: bool = False
    missiles_turn: bool = False
    detour_s: float = 0.0
    m7_resolution: bool = False


M8_LANE = LaneRules()
M7_LANE = LaneRules(side_lane_speed=False, call_for_help=False, pushing_advantage=False, straight_ranges=False, tower_shelter=False,
                    first_wave_call=False, attack_timing=False, m7_resolution=True)


@dataclass(frozen=True, slots=True)
class LaneGeometry:
    """`spawn` and `towers` are indexed by team. Each team's towers run from the outer tower inward.

    `bends` holds the lane's nodes as (lane coordinate, x, y), in rising order of the coordinate. Without them the
    lane is one straight line.
    """

    name: str
    length: float
    spawn: tuple[float, float]
    towers: tuple[tuple[float, ...], tuple[float, ...]]
    side: bool
    bends: tuple[tuple[float, float, float], ...] = ()

    def direction(self, team: int) -> int:
        return 1 if self.spawn[team] < self.spawn[1 - team] else -1

    @property
    def centre(self) -> float:
        """Where two undisturbed waves meet: halfway between the spawn points."""
        return (self.spawn[0] + self.spawn[1]) / 2

    def mirrored(self) -> "LaneGeometry":
        """The same lane with every position reflected, so blue marches toward the low end."""
        flip = lambda spots: tuple(self.length - s for s in spots)
        bends = tuple((self.length - s, x, y) for s, x, y in reversed(self.bends))
        return LaneGeometry(self.name, self.length, flip(self.spawn), (flip(self.towers[0]), flip(self.towers[1])), self.side, bends)

    def xy(self, s: float) -> tuple[float, float]:
        """Map coordinates of a lane coordinate."""
        bends = self.bends
        if not bends:
            return s, 0.0
        after = min(max(bisect_right(bends, (s, inf)), 1), len(bends) - 1)
        (s0, x0, y0), (s1, x1, y1) = bends[after - 1], bends[after]
        f = (s - s0) / (s1 - s0)
        return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f

    def gap(self, a: float, b: float) -> float:
        """The straight line on the map between two lane coordinates. It is shorter than the walk around a bend."""
        (ax, ay), (bx, by) = self.xy(a), self.xy(b)
        return hypot(bx - ax, by - ay)


def lane_geometry(name: str) -> LaneGeometry:
    data = load_map()
    sites = {(site.team, site.tier): site.s for site in data.towers if site.lane == name}
    towers = tuple(tuple(sites[team, tier] for tier in TIERS) for team in ("blue", "red"))
    spawn = (data.minion_spawn_s["blue", name], data.minion_spawn_s["red", name])
    rift, lane = data.rift, data.rift.lanes[name]
    nodes = [rift.edges[lane.edges[0]].a] + [rift.edges[e].b for e in lane.edges]
    bends = tuple((s, *rift.node_xy[node]) for s, node in zip((*lane.starts, lane.length), nodes))
    return LaneGeometry(name, lane.length, spawn, towers, name != "mid", bends)


@dataclass(frozen=True, slots=True)
class ChampionInput:
    """One champion's part in a lane tick.

    in_path: the champion stands in the minions' path. Only then may a minion target it, and only then does it hit.
    execute_below: with a support-item charge and an ally in range, a hit kills a minion at or below this share of
    its maximum health, and the kill is shared. 0 without a charge.
    harassing: the champion damaged an enemy champion, so nearby enemy minions answer the call for help.
    credit: the share of an attack that the champion has ready. The lane spends it on the champion's hits and
    hands what is left back in an `AttackCredit`. Without it the lane keeps a credit for the seat itself.
    xy: the champion's map coordinates where it stands beside the lane. Without them it stands on the lane at `s`.
    tower_target: towers may shoot the champion.
    victims: the seats of the enemy champions that it damaged, for as long as it is harassing. A tower turns on
    it when one of them stands near the tower.
    siege: the champion hits the enemy front tower and nothing else.
    melee: a tower takes more damage from its hits.
    """

    seat: int
    team: int
    s: float
    mode: Mode
    in_path: bool = True
    hit_damage: float = 65.0
    attack_speed: float = 0.65
    attack_range: float = 550.0
    aoe_dps: float = 70.0
    capacity: float = 1.0
    execute_below: float = 0.0
    harassing: bool = False
    credit: float | None = None
    xy: tuple[float, float] | None = None
    tower_target: bool = False
    victims: tuple[int, ...] = ()
    siege: bool = False
    melee: bool = False


@dataclass(frozen=True, slots=True)
class MinionDeath:
    """`gold` is the minion's gold if a champion landed the killing blow, else 0. `shared` marks a support-item kill."""

    t: float
    team: int
    kind: Kind
    s: float
    killer: int | None
    gold: float
    xp: float
    shared: bool = False


@dataclass(frozen=True, slots=True)
class MinionRemoved:
    """A minion walked past the last enemy lane tower and reached the enemy base."""

    t: float
    team: int
    kind: Kind


@dataclass(frozen=True, slots=True)
class TowerDamage:
    t: float
    team: int
    tier: int
    damage: float


@dataclass(frozen=True, slots=True)
class TowerDestroyed:
    t: float
    team: int
    tier: int


@dataclass(frozen=True, slots=True)
class TowerPlate:
    """A tower's missing health crossed one of the plate thresholds, whoever dealt the damage."""

    t: float
    team: int
    tier: int


@dataclass(frozen=True, slots=True)
class ChampionDamage:
    """One minion blow on a champion, before the champion's armor."""

    t: float
    seat: int
    damage: float


@dataclass(frozen=True, slots=True)
class TowerShot:
    """One tower shot on a champion, before the champion's armor. `team` and `tier` name the tower."""

    t: float
    team: int
    tier: int
    seat: int
    damage: float


@dataclass(frozen=True, slots=True)
class AttackCredit:
    """The attack credit that a hitting champion's input brought, as this tick leaves it."""

    seat: int
    credit: float


@dataclass(frozen=True, slots=True)
class Front:
    """`s` is the contact point of the two leading minions, or None while they are out of acquisition range."""

    s: float | None
    lead: tuple[float | None, float | None]
    counts: tuple[int, int]


@dataclass(frozen=True, slots=True)
class KindRules:
    kind: Kind
    attack_speed: float
    attack_range: float
    stop_range: float
    pct_current_hp: float
    xp: float
    tower_shot_pct: float
    tower_multiplier: float
    tower_priority: int
    table: dict
    cast_s: float
    missile_speed: float


def _kind_rules(kind: Kind, tower_priority: int) -> KindRules:
    table = MINIONS[kind.name.lower()]
    to_towers = MINIONS["siege_damage_to_towers" if kind is Kind.SIEGE else "damage_to_towers"]
    timing = TIMING[kind.name.lower()]
    return KindRules(kind, table["attack_speed"], table["attack_range"], min(table["attack_range"], ACQUIRE),
                     table["pct_current_hp_vs_minions"], table["xp"], table["tower_shot_pct_max_hp"], to_towers, tower_priority, table,
                     timing["cast_s"], timing.get("missile_speed", 0.0))


KINDS = (_kind_rules(Kind.MELEE, 1), _kind_rules(Kind.CASTER, 2), _kind_rules(Kind.SIEGE, 0))
MELEE_REACH = KINDS[Kind.MELEE].stop_range


def unit_stats(kind: Kind, t: float) -> tuple[float, float, float]:
    """Health, attack damage, and gold of a minion that spawns at game time t."""
    table = KINDS[kind].table
    upgrades = max(0, int((t - MINIONS["upgrade_first_s"]) // MINIONS["upgrade_interval_s"]))
    return (interpolated(table["hp"], table["hp_span_s"], t), interpolated(table["ad"], table["ad_span_s"], t),
            table["gold"] + table.get("gold_per_upgrade", 0) * upgrades)


def xp_share(base: float, sharers: int) -> float:
    """XP that each of `sharers` champions in range gets for one minion."""
    return base * XP_SHARE[min(sharers, len(XP_SHARE)) - 1] if sharers else 0.0


class WaveClock:
    """Spawn time, kind, wave number, and lateral slot for one team's minions. Both teams spawn the same list."""

    def __init__(self, start: float):
        self.wave = 0
        self.next_wave = float(MINIONS["first_spawn_s"])
        self.queue: list[tuple[float, Kind, int, int]] = []
        while self.next_wave < start:
            self._advance()

    def _advance(self) -> float:
        t = self.next_wave
        self.wave += 1
        self.next_wave = t + scheduled(MINIONS["interval_schedule"], t)
        return t

    def due(self, before: float) -> list[tuple[float, Kind, int, int]]:
        while self.next_wave < before:
            t = self._advance()
            siege = self.wave >= MINIONS["first_siege_wave"] and self.wave % scheduled(MINIONS["siege_schedule"], t) == 0
            line = [(Kind.MELEE, slot) for slot in SLOTS] + [(Kind.SIEGE, 0)] * siege + [(Kind.CASTER, slot) for slot in SLOTS]
            self.queue += [(t + i * MINIONS["spawn_stagger_s"], kind, self.wave, slot) for i, (kind, slot) in enumerate(line)]
        ready = [entry for entry in self.queue if entry[0] < before]
        del self.queue[: len(ready)]
        return ready


@dataclass(slots=True, eq=False)
class Tower:
    """`heat` counts the tower's consecutive shots on champions, and `heat_at` is the time of the last one."""

    team: int
    tier: int
    s: float
    hp: float
    credit: float = 1.0
    free_at: float = 0.0
    x: float = 0.0
    y: float = 0.0
    heat: int = 0
    heat_at: float = -inf
    lo: float = -inf
    hi: float = inf


@dataclass(slots=True, eq=False)
class Minion:
    uid: int
    team: int
    rules: KindRules
    s: float
    hp: float
    max_hp: float
    ad: float
    gold: float
    wave: int = 0
    slot: float = 0.0
    born: float = 0.0
    boost: float = 0.0
    credit: float = 1.0
    draws: int = 0
    target: "Minion | Tower | ChampionTarget | None" = None
    delay: float = 0.0
    near: "Minion | None" = None
    near_gap: float = inf
    near_walk: float = inf
    anchored: bool = False
    free_at: float = 0.0
    died_group: int = -1
    x: float = 0.0
    y: float = 0.0
    died_at: float = -1.0
    ready: float = 0.0
    swing: float = 0.0
    swing_at: "Minion | Tower | ChampionTarget | None" = None
    aimed: "Minion | Tower | ChampionTarget | None" = None


@dataclass(slots=True, eq=False)
class ChampionTarget:
    """A champion in the minions' path for one tick, with the fields a minion reads on any target."""

    inp: ChampionInput
    s: float
    x: float = 0.0
    y: float = 0.0
    hp: float = 1.0
    free_at: float = 0.0


@dataclass(slots=True, eq=False)
class _Champion:
    inp: ChampionInput
    rate: float
    ready: float


def _target_code(target) -> tuple:
    if target is None:
        return ()
    if type(target) is Minion:
        return (0, target.uid)
    if type(target) is Tower:
        return (1, target.team, target.tier)
    return (2, target.inp.seat)


class LaneSim:
    def __init__(self, name: str, seed: int, tick_s: float, rules: LaneRules = M8_LANE, geometry: LaneGeometry | None = None, start_s: float = 0.0):
        self.name = name
        self.seed = seed
        self.tick_s = tick_s
        self.rules = rules
        self.geometry = lane_geometry(name) if geometry is None else geometry
        self.length = self.geometry.length
        self.lane_id = LANE_NAMES.index(name)
        self.tick = round(start_s / tick_s)
        self.minions: tuple[list[Minion], list[Minion]] = ([], [])
        self.towers = tuple([Tower(team, tier, s, TOWERS[TIERS[tier]]["hp"]) for tier, s in enumerate(self.geometry.towers[team])] for team in Team)
        self._straight = rules.straight_ranges
        for tower in (*self.towers[0], *self.towers[1]):
            self._place(tower)
            self._span(tower)
        self.clock = WaveClock(start_s)
        self.spawned = 0
        self.dead = 0
        self.removed = 0
        self.level_lead = 0.0
        self._serial = [0, 0]
        self._champion_credit: dict[int, float] = {}
        self._stand: dict[int, ChampionTarget] = {}
        self._prey: tuple[list[ChampionTarget], ...] = ([], [])
        self._callers: tuple[list[ChampionTarget], ...] = ([], [])
        self._marks: tuple[list[ChampionTarget], ...] = ([], [])
        self._group = 0
        self._events: list = []
        self._t0 = 0.0
        self._missiles: list[tuple] = []
        self._order = 0
        self.cancelled = 0
        self.lost = 0

    @property
    def time(self) -> float:
        return self.tick * self.tick_s

    def tower_alive(self, team: int, tier: str) -> bool:
        return self.towers[team][TIERS.index(tier)].hp > 0

    def front_tower(self, team: int) -> Tower | None:
        """The team's outermost standing tower, the only one that can fight or take damage."""
        return next((tower for tower in self.towers[team] if tower.hp > 0), None)

    def front(self) -> Front:
        leads = []
        for team in Team:
            spots = [m.s for m in self.minions[team]]
            leads.append((max(spots) if self.geometry.direction(team) > 0 else min(spots)) if spots else None)
        blue, red = leads
        touching = blue is not None and red is not None and self._apart(blue, red) <= ACQUIRE + EPS
        return Front((blue + red) / 2 if touching else None, (blue, red), (len(self.minions[0]), len(self.minions[1])))

    def values(self) -> tuple:
        """Every mutable fact of the lane as nested tuples of plain values, for the world digest."""
        minions = tuple(
            (m.uid, m.rules.kind.value, m.s, m.hp, m.max_hp, m.ad, m.gold, m.wave, m.slot, m.born, m.boost, m.credit, m.draws, _target_code(m.target),
             m.ready, m.swing, _target_code(m.swing_at), _target_code(m.aimed))
            for team in Team for m in self.minions[team]
        )
        missiles = tuple((land, uid, team, rules.kind.value, ad, _target_code(target)) for land, uid, _, team, rules, ad, target in sorted(self._missiles, key=lambda blow: blow[:3]))
        towers = tuple((t.team, t.tier, t.hp, t.credit, t.heat, t.heat_at) for team in Team for t in self.towers[team])
        clock = (self.clock.wave, self.clock.next_wave, tuple((when, kind.value, wave, slot) for when, kind, wave, slot in self.clock.queue))
        counts = (self.tick, self.spawned, self.dead, self.removed, *self._serial, self.cancelled, self.lost)
        return (self.name, counts, clock, towers, minions, tuple(sorted(self._champion_credit.items())), missiles)

    def add_minion(self, team: int, kind: Kind, s: float, when: float | None = None, delay: float = 0.0, count: int = 1, slot: float | None = None, wave: int = 0) -> None:
        """Without a slot, the count minions take neighbouring slots centred on the middle of the lane."""
        born = self.time if when is None else when
        hp, ad, gold = unit_stats(kind, born)
        for i in range(count):
            lateral = i - (count - 1) / 2 if slot is None else slot
            self._serial[team] += 1
            uid = 2 * (self._serial[team] - 1) + team
            self.minions[team].append(Minion(uid, team, KINDS[kind], s, hp, hp, ad, gold, wave, lateral, born, delay=delay))
            self._place(self.minions[team][-1])
            self.spawned += 1

    def step(self, tick: int, inputs: Sequence[ChampionInput] = (), level_lead: float = 0.0) -> list:
        """Advance the lane by the tick that starts at world tick `tick`. `level_lead` is blue's average level minus red's."""
        self.tick = tick
        self.level_lead = level_lead
        t0 = self._t0 = self.time
        dt = self.tick_s
        self._events = []
        for when, kind, wave, slot in self.clock.due(t0 + dt):
            for team in Team:
                self._spawn(team, kind, wave, when, max(0.0, when - t0), slot)
        stand = self._stand = {c.seat: ChampionTarget(c, c.s) for c in inputs}
        for spot in stand.values():
            if spot.inp.xy is None:
                self._place(spot)
            else:
                spot.x, spot.y = spot.inp.xy
        marked = [stand[c.seat] for c in inputs if c.tower_target]
        self._marks = tuple([spot for spot in marked if spot.inp.team != team] for team in Team)
        in_path = [stand[c.seat] for c in inputs if c.in_path and self.rules.champion_aggro and not self._sheltered(stand[c.seat])]
        self._prey = tuple([spot for spot in in_path if spot.inp.team != team] for team in Team)
        callers = [stand[c.seat] for c in inputs if c.harassing and self.rules.call_for_help]
        self._callers = tuple([spot for spot in callers if spot.inp.team != team] for team in Team)
        self._acquire()
        self._march()
        self._fight(inputs)
        for team in Team:
            self.minions[team][:] = [m for m in self.minions[team] if m.hp > 0]
        self.tick = tick + 1
        return self._events

    def _span(self, tower: Tower) -> None:
        """Set the stretch of lane coordinates outside which no point of the lane is within the tower's range."""
        reach = TOWER_RANGE + EPS
        if not self._straight:
            tower.lo, tower.hi = tower.s - reach, tower.s + reach
            return
        step, geometry = 10.0, self.geometry
        near = [i * step for i in range(int(self.length // step) + 2) if hypot(*(a - b for a, b in zip(geometry.xy(i * step), (tower.x, tower.y)))) <= reach + 2 * step]
        tower.lo, tower.hi = min(near) - step, max(near) + step

    def _place(self, unit) -> None:
        if self.rules.straight_ranges:
            unit.x, unit.y = self.geometry.xy(unit.s)

    def _range(self, a, b) -> float:
        """The distance that decides whether two units of the lane can interact. Marching uses the lane coordinate.

        The loops that run for every pair of units on every tick compute the same distance in place.
        """
        return hypot(a.x - b.x, a.y - b.y) if self._straight else abs(a.s - b.s)

    def _in_range_of(self, tower: Tower, team: int) -> list[Minion]:
        """The living minions of `team` within the tower's attack range, in the lane's order.

        `tower.lo` and `tower.hi` bound the lane coordinates that can be in range at all, so that a tower with no
        minion near it costs two comparisons.
        """
        lo, hi, limit = tower.lo, tower.hi, TOWER_RANGE + EPS
        if self._straight:
            x, y = tower.x, tower.y
            return [m for m in self.minions[team] if lo <= m.s <= hi and m.hp > 0 and hypot(m.x - x, m.y - y) <= limit]
        s = tower.s
        return [m for m in self.minions[team] if lo <= m.s <= hi and m.hp > 0 and abs(m.s - s) <= limit]

    def _apart(self, a: float, b: float) -> float:
        return self.geometry.gap(a, b) if self.rules.straight_ranges else abs(a - b)

    def _sheltered(self, spot: ChampionTarget) -> bool:
        if not self.rules.tower_shelter:
            return False
        return any(tower.hp > 0 and self._range(tower, spot) <= TOWER_RANGE + EPS for team in Team for tower in self.towers[team])

    def _spawn(self, team: int, kind: Kind, wave: int, when: float, delay: float, slot: int) -> None:
        self.add_minion(team, kind, self.geometry.spawn[team], when, delay, slot=slot, wave=wave)
        if self.rules.side_lane_speed and self.geometry.side and wave >= SIDE_SPEED["first_wave"] and when < SIDE_SPEED["until_s"]:
            self.minions[team][-1].boost = max(0.0, SIDE_SPEED["bonus"] - SIDE_SPEED["per_wave"] * (wave - SIDE_SPEED["first_wave"]))

    def _speed(self, m: Minion) -> float:
        if not m.boost:
            return SPEED
        ends = SIDE_SPEED["stage_ends_s"]
        stage = sum(self._t0 - m.born >= end for end in ends)
        return SPEED if stage == len(ends) else SPEED + max(0.0, m.boost - SIDE_SPEED["stage_drop"] * stage)

    def _pick(self, m: Minion, tied: list) -> Minion:
        m.draws += 1
        # without the tick in the key, runs at different tick lengths draw the same numbers
        key = (m.uid, m.draws) if self.rules.lateral_slots else (self.tick, m.uid, m.draws)
        return tied[int(keyed_uniform(self.seed, Stream.MINION_TARGET, self.lane_id, *key) * len(tied))]

    def _nearest(self, m: Minion, limit: float, foes: list | None = None):
        best, tied = limit, []
        straight, x, y, s = self._straight, m.x, m.y, m.s
        for foe in self.minions[1 - m.team] if foes is None else foes:
            if foe.hp <= 0:
                continue
            gap = hypot(foe.x - x, foe.y - y) if straight else abs(foe.s - s)
            if gap < best - EPS:
                best, tied = gap, [foe]
            elif gap <= best + EPS:
                tied.append(foe)
        if not tied:
            return None, inf
        if len(tied) > 1 and self.rules.lateral_slots:
            aside = min(abs(foe.slot - m.slot) for foe in tied)
            tied = [foe for foe in tied if abs(foe.slot - m.slot) == aside]
        return (tied[0] if len(tied) == 1 else self._pick(m, tied)), best

    def _champion_near(self, m: Minion, limit: float):
        near = [c for c in self._prey[m.team] if self._range(c, m) <= limit + EPS]
        return min(near, key=lambda c: (self._range(c, m), c.inp.seat)) if near else None

    def _in_reach(self, m: Minion):
        foe, _ = self._nearest(m, m.rules.attack_range)
        if foe is not None:
            return foe
        if not self.rules.m7_resolution and any(foe.hp > 0 and self._range(foe, m) <= ACQUIRE + EPS for foe in self.minions[1 - m.team]):
            return None
        tower = self.front_tower(1 - m.team)
        if tower is not None and self._range(tower, m) <= m.rules.attack_range + EPS:
            return tower
        return self._champion_near(m, m.rules.attack_range)

    def _acquire(self) -> None:
        cap = self.rules.melee_cap
        crowd: dict[int, int] = {}
        if cap:
            for team in Team:
                for m in self.minions[team]:
                    if m.rules.kind is Kind.MELEE and type(m.target) is Minion and m.target.hp > 0:
                        crowd[m.target.uid] = crowd.get(m.target.uid, 0) + 1
        apart, first_wave_call = self._range, self.rules.first_wave_call
        for team in Team:
            tower = self.front_tower(1 - team)
            callers = self._callers[team]
            for m in self.minions[team]:
                target = m.target
                reach = m.rules.attack_range + EPS
                if callers and (type(target) is not Tower or (first_wave_call and m.wave == 1)):
                    caller = min(callers, key=lambda c: (apart(c, m), c.inp.seat))
                    if apart(caller, m) <= CALL_RANGE + EPS:
                        m.target = caller
                        m.near, m.near_gap, m.near_walk = None, inf, inf
                        m.anchored = apart(caller, m) <= reach
                        continue
                if type(target) is Minion and target.hp > 0 and apart(target, m) <= reach:
                    m.anchored = True
                    continue
                if cap and type(target) is Minion and m.rules.kind is Kind.MELEE:
                    crowd[target.uid] = crowd.get(target.uid, 1) - 1
                m.near, m.near_gap = self._nearest(m, inf)
                if cap and m.rules.kind is Kind.MELEE and m.near is not None and crowd.get(m.near.uid, 0) >= cap:
                    open_foes = [foe for foe in self.minions[1 - team] if crowd.get(foe.uid, 0) < cap]
                    m.near, m.near_gap = self._nearest(m, inf, open_foes)
                # the walk to the target is measured now, before anyone marches, so the order of marching cannot matter
                m.near_walk = abs(m.near.s - m.s) if m.near is not None and self.rules.straight_ranges else m.near_gap
                if m.near_gap <= ACQUIRE + EPS:
                    target = m.near
                    if cap and m.rules.kind is Kind.MELEE:
                        crowd[target.uid] = crowd.get(target.uid, 0) + 1
                elif tower is not None and apart(tower, m) <= ACQUIRE + EPS:
                    target = tower
                else:
                    target = self._champion_near(m, ACQUIRE)
                m.target = target
                m.anchored = target is not None and apart(target, m) <= reach

    def _march(self) -> None:
        geometry, dt = self.geometry, self.tick_s
        walkers = [m for team in Team for m in self.minions[team] if not m.anchored]
        lead_walker: list[float | None] = [None, None]
        for team in Team:
            spots = [m.s for m in walkers if m.team == team]
            if spots:
                lead_walker[team] = max(spots) if geometry.direction(team) > 0 else min(spots)
        for team in Team:
            for m in self.minions[team]:
                if m.anchored:
                    m.free_at, m.delay = m.delay, 0.0
        towers = [self.front_tower(team) for team in Team]
        for m in walkers:
            heading = geometry.direction(m.team)
            tower = towers[1 - m.team]
            stop = m.rules.stop_range
            room = heading * (geometry.spawn[1 - m.team] - m.s)
            if tower is None and room <= EPS:
                m.hp = 0.0
                self.removed += 1
                self._events.append(MinionRemoved(self._t0, m.team, m.rules.kind))
                continue
            if m.near is not None:
                room = min(room, m.near_walk - stop)
            if lead_walker[1 - m.team] is not None:
                # two walkers closing on each other each take half the gap, so they meet instead of crossing within a tick
                room = min(room, (abs(lead_walker[1 - m.team] - m.s) - stop) / 2)
            if type(m.target) is ChampionTarget:
                ahead = heading * (m.target.s - m.s)
                if ahead < 0:
                    heading, room = -heading, -ahead - stop
                else:
                    room = min(room, ahead - stop)
            elif (m.target is None or type(m.target) is Tower) and tower is not None and heading * (tower.s - m.s) > 0:
                room = min(room, abs(tower.s - m.s) - stop)
            speed = self._speed(m)
            advance = max(0.0, min(speed * (dt - m.delay), room))
            m.s += heading * advance
            self._place(m)
            m.free_at = m.delay + advance / speed
            m.delay = 0.0

    def _schedule(self, queue: list, actor, key: int, speed: float, start: float) -> None:
        credit = min(1.0, actor.credit + speed * start)
        total = credit + speed * (self.tick_s - start)
        attacks = int(total)
        for k in range(1, attacks + 1):
            self._push(queue, start + (k - credit) / speed, key, BLOW, actor)
        actor.credit = total - attacks

    def _push(self, queue: list, when: float, key: int, what: int, actor) -> None:
        """Queue one event of this tick. The running number keeps events of one actor at one instant in the order
        they were queued."""
        self._order += 1
        heapq.heappush(queue, (when, key, self._order, what, actor))

    def _resume(self, queue: list, m: Minion) -> None:
        """Queue a minion's next attack event of this tick: the release of a cast in progress, or the start of one."""
        if m.swing_at is not None:
            when, what = m.swing - self._t0, RELEASE
        else:
            target = m.target
            if target is None or self._range(m, target) > m.rules.attack_range + EPS:
                return
            when, what = max(m.free_at, target.free_at, m.ready - self._t0), START
        if when < self.tick_s:
            self._push(queue, max(when, 0.0), m.uid, what, m)

    def _cast(self, queue: list, m: Minion, target, start: float) -> None:
        """Start an attack on `target` at `start`. The blow leaves the minion one cast time later."""
        t0 = self._t0
        if self.rules.detour_s and m.rules.kind is Kind.MELEE and type(target) is Minion and m.aimed is not None and m.aimed is not target:
            start += self.rules.detour_s
        m.target = m.swing_at = m.aimed = target
        m.swing = t0 + start + m.rules.cast_s
        m.ready = t0 + start + 1.0 / m.rules.attack_speed
        if m.swing - t0 < self.tick_s:
            self._push(queue, m.swing - t0, m.uid, RELEASE, m)

    def _live(self, m: Minion, target):
        """The target of a cast or a missile as it stands now, or None when it can no longer be hit."""
        if type(target) is ChampionTarget:
            target = self._stand.get(target.inp.seat)
            if target is None or not (target in self._prey[m.team] or target in self._callers[m.team]):
                return None
        elif target.hp <= 0:
            return None
        return target

    def _start(self, queue: list, m: Minion, now: float) -> None:
        if m.hp <= 0:
            return
        target = m.target
        if target is None or target.hp <= 0 or self._range(m, target) > m.rules.attack_range + EPS:
            target = self._in_reach(m)
        if target is None:
            m.ready = self._t0 + now
            return
        self._cast(queue, m, target, now)

    def _release(self, queue: list, m: Minion, now: float) -> None:
        aimed, m.swing_at = m.swing_at, None
        if m.hp <= 0 and m.died_group != self._group:
            return
        t0 = self._t0
        target = self._live(m, aimed)
        if target is None or self._range(m, target) > m.rules.attack_range + EPS:
            self.cancelled += 1
            died = aimed.died_at - t0 if type(aimed) is Minion and aimed.hp <= 0 else now
            again = self._in_reach(m) if m.hp > 0 else None
            if again is None:
                m.ready = t0 + now
            else:
                # the cast began again when the old target died, so the time lost is the part of the cast spent on it
                began = max(min(died, now), now - m.rules.cast_s)
                if self.rules.free_cancel:
                    began = now - m.rules.cast_s
                arrived = max(m.free_at, again.free_at)
                self._cast(queue, m, again, max(began, arrived) if arrived > 0 else began)
            return
        if m.rules.missile_speed:
            land = now + self._range(m, target) / m.rules.missile_speed
            missile = (t0 + land, m.uid, self._order, m.team, m.rules, m.ad, target)
            if land < self.tick_s:
                self._push(queue, land, m.uid, LAND, missile)
            else:
                self._missiles.append(missile)
        else:
            self._strike(m.team, m.rules, m.ad, target, now)
        if m.hp > 0 and m.ready - t0 < self.tick_s:
            self._push(queue, max(m.ready - t0, now), m.uid, START, m)

    def _land(self, missile: tuple, now: float) -> None:
        _, uid, _, team, rules, ad, aimed = missile
        if type(aimed) is ChampionTarget:
            target = self._stand.get(aimed.inp.seat)
        else:
            target = aimed if aimed.hp > 0 else None
        if target is None and self.rules.missiles_turn:
            shooter = next((m for m in self.minions[team] if m.uid == uid and m.hp > 0), None)
            target = self._in_reach(shooter) if shooter is not None else None
        if target is None:
            self.lost += 1
        else:
            self._strike(team, rules, ad, target, now)

    def _fight(self, inputs: Sequence[ChampionInput]) -> None:
        dt = self.tick_s
        if not self.rules.m7_resolution:
            # champions that attack at the same instant must not be served by seat, or one of two equal laners takes every tie
            inputs = sorted(inputs, key=lambda inp: keyed_uniform(self.seed, Stream.LAST_HIT, self.lane_id, self.tick, inp.seat))
            present = {inp.seat for inp in inputs}
            self._champion_credit = {seat: credit for seat, credit in self._champion_credit.items() if seat in present}
        queue: list = []
        timed = self.rules.attack_timing
        if timed:
            due = [missile for missile in self._missiles if missile[0] - self._t0 < dt]
            self._missiles = [missile for missile in self._missiles if missile[0] - self._t0 >= dt]
            for missile in due:
                self._push(queue, max(missile[0] - self._t0, 0.0), missile[1], LAND, missile)
        for team in Team:
            for m in self.minions[team]:
                target, speed = m.target, m.rules.attack_speed
                if timed:
                    self._resume(queue, m)
                elif m.hp <= 0 or target is None or self._range(m, target) > m.rules.attack_range + EPS:
                    m.credit = min(1.0, m.credit + speed * dt)
                else:
                    self._schedule(queue, m, m.uid, speed, max(m.free_at, target.free_at))
        for team in Team:
            for tower in self.towers[team]:
                arrivals = [m.free_at for m in self._in_range_of(tower, 1 - team)]
                marks = self._marks_in_range(tower)
                if marks and (not arrivals or any(self._provokes(spot, tower) for spot in marks)):
                    arrivals = [0.0]
                if tower.hp > 0 and arrivals:
                    self._schedule(queue, tower, -1 - 3 * team - tower.tier, TOWER_ATTACK_SPEED, min(arrivals))
                else:
                    tower.credit = min(1.0, tower.credit + TOWER_ATTACK_SPEED * dt)
        champions = []
        for i, inp in enumerate(inputs):
            rate = inp.attack_speed * inp.capacity
            credit = self._champion_credit.get(inp.seat, 1.0) if inp.credit is None else inp.credit
            ready = 0.0 if credit >= 1.0 else (1.0 - credit) / rate if rate > 0 else inf
            champion = _Champion(inp, rate, ready)
            champions.append((CHAMPION_KEY + i, champion))
            if self._hits(inp) and ready < dt:
                self._push(queue, ready, CHAMPION_KEY + i, BLOW, champion)
        pushers = [c.inp for _, c in champions if c.inp.mode is Mode.PUSH and c.inp.in_path and c.inp.aoe_dps * c.inp.capacity > 0]
        swept = 0.0
        self._group = 0
        while queue:
            now = queue[0][0]
            self._sweep(pushers, now - swept, now)
            swept = now
            self._group += 1
            group = []
            while queue and queue[0][0] <= now + SAME_INSTANT:
                group.append(heapq.heappop(queue)[1:])
            group.sort(key=lambda entry: entry[:2])
            for _, _, what, actor in group:
                if what == START:
                    self._start(queue, actor, now)
                elif what == RELEASE:
                    self._release(queue, actor, now)
                elif what == LAND:
                    self._land(actor, now)
                elif type(actor) is Minion:
                    self._minion_attack(actor, now)
                elif type(actor) is Tower:
                    self._tower_attack(actor, now)
            for key, champion in champions:
                if champion.ready <= now + SAME_INSTANT and self._champion_attack(champion.inp, now):
                    champion.ready = now + 1.0 / champion.rate
                    if champion.ready < dt:
                        self._push(queue, champion.ready, key, BLOW, champion)
        self._sweep(pushers, dt - swept, dt)
        for _, champion in champions:
            inp = champion.inp
            if champion.rate <= 0:
                continue
            left = min(1.0, 1.0 - (champion.ready - dt) * champion.rate)
            if inp.credit is None:
                self._champion_credit[inp.seat] = left
            elif self._hits(inp):
                self._events.append(AttackCredit(inp.seat, max(0.0, left)))

    @staticmethod
    def _hits(inp: ChampionInput) -> bool:
        if inp.siege:
            return True
        return inp.in_path and inp.mode is not Mode.PASSIVE

    def _push_edge(self, attacker_team: int) -> tuple[float, float]:
        """Damage multiplier and flat reduction for a minion blow of `attacker_team` on an enemy minion."""
        if not self.rules.pushing_advantage or self._t0 < PUSHING["start_s"] or self.level_lead == 0:
            return 1.0, 0.0
        ahead = Team.BLUE if self.level_lead > 0 else Team.RED
        levels = min(abs(self.level_lead), PUSHING["level_cap"])
        fallen = [sum(tower.hp <= 0 for tower in self.towers[team]) for team in Team]
        towers = max(0, fallen[1 - ahead] - fallen[ahead])
        if attacker_team == ahead:
            return 1.0 + min(PUSHING["damage_max"], (PUSHING["damage_base"] + PUSHING["damage_per_tower"] * towers) * levels), 0.0
        return 1.0, min(PUSHING["reduction_max"], PUSHING["reduction_base"] + towers * levels)

    def _minion_attack(self, m: Minion, now: float) -> None:
        # a minion killed in this same instant still lands its blow, so simultaneous exchanges stay symmetric
        if m.hp <= 0 and m.died_group != self._group:
            return
        target = m.target
        if target is None or target.hp <= 0:
            target = m.target = self._in_reach(m)
            if target is None:
                m.credit = min(1.0, m.credit + 1.0)
                return
        self._strike(m.team, m.rules, m.ad, target, now)

    def _strike(self, team: int, rules: KindRules, ad: float, target, now: float) -> None:
        """One minion blow lands on a tower, a champion, or an enemy minion."""
        if type(target) is Tower:
            self._hit_tower(target, ad * rules.tower_multiplier, now)
        elif type(target) is ChampionTarget:
            self._events.append(ChampionDamage(self._t0 + now, target.inp.seat, ad * DAMAGE_TO_CHAMPIONS))
        else:
            multiplier, reduction = self._push_edge(team)
            blow = ad + rules.pct_current_hp * target.hp * self.rules.current_hp_damage
            self._hurt(target, max(0.0, blow * multiplier - reduction) * self.rules.minion_damage_scale, None, now)

    def _marks_in_range(self, tower: Tower) -> list[ChampionTarget]:
        """The enemy champions that a standing tower may shoot now."""
        if tower.hp <= 0:
            return []
        return [spot for spot in self._marks[tower.team] if self._range(spot, tower) <= TOWER_RANGE + EPS]

    def _provokes(self, spot: ChampionTarget, tower: Tower) -> bool:
        """Whether a champion damaged one of the tower's allied champions that stands near the tower."""
        for seat in spot.inp.victims:
            victim = self._stand.get(seat)
            if victim is not None and victim.inp.team == tower.team and self._range(victim, tower) <= SWITCH_RANGE + EPS:
                return True
        return False

    def _tower_attack(self, tower: Tower, now: float) -> None:
        """One tower shot. It goes to an enemy champion in range that damaged an allied champion near the tower,
        else to a minion, else to the closest enemy champion in range (reference rows E16c and E16d)."""
        foes = self._in_range_of(tower, 1 - tower.team) if tower.hp > 0 else []
        marks = self._marks_in_range(tower)
        marks = [spot for spot in marks if self._provokes(spot, tower)] or ([] if foes else marks)
        if marks:
            self._shoot(tower, min(marks, key=lambda spot: (self._range(spot, tower), spot.inp.seat)), now)
            return
        if not foes:
            tower.credit = min(1.0, tower.credit + 1.0)
            return
        target = min(foes, key=lambda m: (m.rules.tower_priority, self._range(m, tower), m.uid))
        self._hurt(target, target.rules.tower_shot_pct * target.max_hp, None, now)

    def _shoot(self, tower: Tower, spot: ChampionTarget, now: float) -> None:
        """A shot on a champion deals the tower's attack damage at this game time, and half of it more for each
        shot on a champion before it, up to the ramp's limit. The ramp does not care which champion the shots
        hit. It starts again once the tower has hit no champion for the reset time (reference row E13g)."""
        t = self._t0 + now
        if t - tower.heat_at >= RAMP_RESET_S:
            tower.heat = 0
        table = TOWERS[TIERS[tower.tier]]
        damage = interpolated(table["ad"], table["ad_span_s"], t) * (1.0 + min(RAMP_MAX, RAMP_PER_HIT * tower.heat))
        tower.heat, tower.heat_at = tower.heat + 1, t
        self._events.append(TowerShot(t, tower.team, tower.tier, spot.inp.seat, damage))

    def _siege_blow(self, inp: ChampionInput, tower: Tower, now: float) -> float:
        """The health that one champion hit takes from a tower: cut by the tower's armor, raised for a melee
        champion, and cut again while none of the champion's minions is near the tower. An outer tower's armor
        falls to zero over its decay span. The straight line over that span is Assumed."""
        table = TOWERS[TIERS[tower.tier]]
        armor = interpolated([ARMOR, 0.0], table["armor_decay_span_s"], self._t0 + now) if "armor_decay_span_s" in table else ARMOR
        damage = inp.hit_damage * ARMOR_HALVING / (ARMOR_HALVING + armor)
        if inp.melee:
            damage *= MELEE_TAKEN
        if not any(m.hp > 0 and self._range(m, tower) <= BACKDOOR_RANGE + EPS for m in self.minions[inp.team]):
            damage *= 1.0 - BACKDOOR
        return damage

    def _hit_tower(self, tower: Tower, damage: float, now: float) -> None:
        if tower.hp <= 0:
            return
        full = TOWERS[TIERS[tower.tier]]["hp"]
        missing = full - tower.hp
        tower.hp -= damage
        self._events.append(TowerDamage(self._t0 + now, tower.team, tower.tier, damage))
        for share in PLATES:
            if missing < share * full <= full - tower.hp:
                self._events.append(TowerPlate(self._t0 + now, tower.team, tower.tier))
        if tower.hp <= 0:
            self._events.append(TowerDestroyed(self._t0 + now, tower.team, tower.tier))

    def _champion_attack(self, inp: ChampionInput, now: float) -> bool:
        if not self._hits(inp):
            return False
        me = self._stand[inp.seat]
        if inp.siege:
            tower = self.front_tower(1 - inp.team)
            if tower is None or self._range(tower, me) > inp.attack_range + EPS:
                return False
            self._hit_tower(tower, self._siege_blow(inp, tower, now), now)
            return True
        reach = inp.attack_range + EPS
        if self._straight:
            x, y = me.x, me.y
            foes = [m for m in self.minions[1 - inp.team] if m.hp > 0 and hypot(m.x - x, m.y - y) <= reach]
        else:
            foes = [m for m in self.minions[1 - inp.team] if m.hp > 0 and abs(m.s - me.s) <= reach]
        choice = [m for m in foes if m.hp <= inp.hit_damage]
        shared = False
        if not choice and inp.execute_below > 0:
            choice = [m for m in foes if m.hp <= inp.execute_below * m.max_hp]
        if choice and inp.execute_below > 0:
            shared = True
        elif not choice and inp.mode is Mode.THIN:
            choice = [m for m in foes if m.rules.kind is Kind.CASTER] or foes
        elif not choice and inp.mode is Mode.PUSH:
            choice = foes
        if not choice:
            return False
        target = min(choice, key=lambda m: (m.hp, m.uid))
        self._hurt(target, target.hp if shared else inp.hit_damage, inp.seat, now, shared)
        return True

    def _sweep(self, pushers: list, span: float, now: float) -> None:
        if span <= 0:
            return
        for inp in pushers:
            damage = inp.aoe_dps * inp.capacity * span
            me = self._stand[inp.seat]
            for m in self.minions[1 - inp.team]:
                if m.hp > 0 and self._range(m, me) <= inp.attack_range + EPS:
                    self._hurt(m, damage, inp.seat, now)

    def _hurt(self, target: Minion, damage: float, killer: int | None, now: float, shared: bool = False) -> None:
        target.hp -= damage
        if target.hp <= 0:
            target.died_group = self._group
            target.died_at = self._t0 + now
            self.dead += 1
            gold = target.gold if killer is not None else 0
            self._events.append(MinionDeath(self._t0 + now, target.team, target.rules.kind, target.s, killer, gold, target.rules.xp, shared))


def stance(lane: LaneSim, team: int, mode: Mode, attack_range: float = STAND_OFF, front: Front | None = None, hold: bool = False) -> tuple[float, bool]:
    """Where a champion that hits in `mode` wants to stand, and whether it stands in the minions' path there.

    `hold` is the champion's choice to stand on the hold line. It is independent of what the champion hits.

    `front` is the wave front that the champion's team knows. Without it the lane's true front is used, which is
    only right while nothing hides a wave from a team.

    While the waves are in contact every mode stands at the wave, one melee reach short of the enemy lead minion.
    Before that a champion waits at its own front tower until its wave has passed it, then walks with the wave.
    With its own wave gone a champion steps aside, 550 units short of the enemy lead, unless it pushes or holds.
    A pushing champion stays in the path at its attack range. A holding champion stays in the path on the line that
    stops the enemy lead minion 300 units outside the range of its own front tower. No mode stands ahead of its own
    lead minion except a hold with no contact, or inside the enemy front tower's range plus 50 units.
    """
    geometry = lane.geometry
    front = lane.front() if front is None else front
    heading = geometry.direction(team)
    own, foe = front.lead[team], front.lead[1 - team]
    own_tower, enemy_tower = lane.front_tower(team), lane.front_tower(1 - team)
    home = own_tower.s if own_tower is not None else geometry.spawn[team]
    contact = front.s is not None

    def beyond(a: float, b: float) -> bool:
        return heading * (a - b) > 0

    hold_line = home + heading * (TOWER_RANGE + HOLD_MARGIN - MELEE_REACH)
    if contact:
        s = foe - heading * MELEE_REACH
    elif hold:
        s = own if own is not None and beyond(own, hold_line) else hold_line
    elif foe is None:
        s = own if own is not None and beyond(own, home) else home
    else:
        s = foe - heading * (min(attack_range, STAND_OFF) if mode is Mode.PUSH else STAND_OFF)
    if own is not None and beyond(s, own) and not (hold and not contact):
        s = own if beyond(own, home) else home
    if enemy_tower is not None:
        edge = enemy_tower.s - heading * (TOWER_RANGE + TOWER_MARGIN)
        s = min(s, edge) if heading > 0 else max(s, edge)
    return s, contact or hold or mode is Mode.PUSH
