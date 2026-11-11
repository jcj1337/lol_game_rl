"""Lanes: the minions and towers of one lane, on the lane coordinate `s`.

One `LaneSim` serves every lane. It owns the lane's minions, its six towers, and its wave clock. Champions enter
only as per-tick `ChampionInput`s, and everything that crosses into the rest of the world leaves as an event.
`LaneRules` names each optional rule, so an experiment can switch one rule and nothing else.
"""

import heapq
from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntEnum
from math import inf

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
SPEED = MINIONS["move_speed"]
ACQUIRE = MINIONS["acquisition_range"]
CALL_RANGE = ADDED["minions"]["call_for_help_range"]
XP_SHARE = MINIONS["xp_share"]
DAMAGE_TO_CHAMPIONS = MINIONS["damage_to_champions"]
TOWER_RANGE = TOWERS["attack_range"]
TOWER_ATTACK_SPEED = TOWERS["attack_speed"]
TIERS = ("outer", "inner", "inhibitor")
LANE_NAMES = ("top", "mid", "bot")
EPS = 1e-6
SAME_INSTANT = 1e-9
CHAMPION_KEY = 1 << 40
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
    PASSIVE = 0
    LAST_HIT = 1
    THIN = 2
    PUSH = 3
    HOLD = 4


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
    m7_resolution: bool = False


M8_LANE = LaneRules()
M7_LANE = LaneRules(side_lane_speed=False, call_for_help=False, pushing_advantage=False, m7_resolution=True)


@dataclass(frozen=True, slots=True)
class LaneGeometry:
    """`spawn` and `towers` are indexed by team. Each team's towers run from the outer tower inward."""

    name: str
    length: float
    spawn: tuple[float, float]
    towers: tuple[tuple[float, ...], tuple[float, ...]]
    side: bool

    def direction(self, team: int) -> int:
        return 1 if self.spawn[team] < self.spawn[1 - team] else -1

    @property
    def centre(self) -> float:
        """Where two undisturbed waves meet: halfway between the spawn points."""
        return (self.spawn[0] + self.spawn[1]) / 2

    def mirrored(self) -> "LaneGeometry":
        """The same lane with every position reflected, so blue marches toward the low end."""
        flip = lambda spots: tuple(self.length - s for s in spots)
        return LaneGeometry(self.name, self.length, flip(self.spawn), (flip(self.towers[0]), flip(self.towers[1])), self.side)


def lane_geometry(name: str) -> LaneGeometry:
    data = load_map()
    sites = {(site.team, site.tier): site.s for site in data.towers if site.lane == name}
    towers = tuple(tuple(sites[team, tier] for tier in TIERS) for team in ("blue", "red"))
    spawn = (data.minion_spawn_s["blue", name], data.minion_spawn_s["red", name])
    return LaneGeometry(name, data.rift.lanes[name].length, spawn, towers, name != "mid")


@dataclass(frozen=True, slots=True)
class ChampionInput:
    """One champion's part in a lane tick.

    in_path: the champion stands in the minions' path. Only then may a minion target it, and only then does it hit.
    execute_below: with a support-item charge and an ally in range, a hit kills a minion at or below this share of
    its maximum health, and the kill is shared. 0 without a charge.
    harassing: the champion damaged an enemy champion, so nearby enemy minions answer the call for help.
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
class ChampionDamage:
    """One minion blow on a champion, before the champion's armor."""

    t: float
    seat: int
    damage: float


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


def _kind_rules(kind: Kind, tower_priority: int) -> KindRules:
    table = MINIONS[kind.name.lower()]
    to_towers = MINIONS["siege_damage_to_towers" if kind is Kind.SIEGE else "damage_to_towers"]
    return KindRules(kind, table["attack_speed"], table["attack_range"], min(table["attack_range"], ACQUIRE),
                     table["pct_current_hp_vs_minions"], table["xp"], table["tower_shot_pct_max_hp"], to_towers, tower_priority, table)


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
    team: int
    tier: int
    s: float
    hp: float
    credit: float = 1.0
    free_at: float = 0.0


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
    anchored: bool = False
    free_at: float = 0.0
    died_group: int = -1


@dataclass(slots=True, eq=False)
class ChampionTarget:
    """A champion in the minions' path for one tick, with the fields a minion reads on any target."""

    inp: ChampionInput
    s: float
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
        self.clock = WaveClock(start_s)
        self.spawned = 0
        self.dead = 0
        self.removed = 0
        self.level_lead = 0.0
        self._serial = [0, 0]
        self._champion_credit: dict[int, float] = {}
        self._prey: tuple[list[ChampionTarget], ...] = ([], [])
        self._callers: tuple[list[ChampionTarget], ...] = ([], [])
        self._group = 0
        self._events: list = []
        self._t0 = 0.0

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
        touching = blue is not None and red is not None and abs(red - blue) <= ACQUIRE + EPS
        return Front((blue + red) / 2 if touching else None, (blue, red), (len(self.minions[0]), len(self.minions[1])))

    def values(self) -> tuple:
        """Every mutable fact of the lane as nested tuples of plain values, for the world digest."""
        minions = tuple(
            (m.uid, m.rules.kind.value, m.s, m.hp, m.max_hp, m.ad, m.gold, m.wave, m.slot, m.born, m.boost, m.credit, m.draws, _target_code(m.target))
            for team in Team for m in self.minions[team]
        )
        towers = tuple((t.team, t.tier, t.hp, t.credit) for team in Team for t in self.towers[team])
        clock = (self.clock.wave, self.clock.next_wave, tuple((when, kind.value, wave, slot) for when, kind, wave, slot in self.clock.queue))
        counts = (self.tick, self.spawned, self.dead, self.removed, *self._serial)
        return (self.name, counts, clock, towers, minions, tuple(sorted(self._champion_credit.items())))

    def add_minion(self, team: int, kind: Kind, s: float, when: float | None = None, delay: float = 0.0, count: int = 1, slot: float | None = None, wave: int = 0) -> None:
        """Without a slot, the count minions take neighbouring slots centred on the middle of the lane."""
        born = self.time if when is None else when
        hp, ad, gold = unit_stats(kind, born)
        for i in range(count):
            lateral = i - (count - 1) / 2 if slot is None else slot
            self._serial[team] += 1
            uid = 2 * (self._serial[team] - 1) + team
            self.minions[team].append(Minion(uid, team, KINDS[kind], s, hp, hp, ad, gold, wave, lateral, born, delay=delay))
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
        in_path = [c for c in inputs if c.in_path and self.rules.champion_aggro]
        self._prey = tuple([ChampionTarget(c, c.s) for c in in_path if c.team != team] for team in Team)
        callers = [c for c in inputs if c.harassing and self.rules.call_for_help]
        self._callers = tuple([ChampionTarget(c, c.s) for c in callers if c.team != team] for team in Team)
        self._acquire()
        self._march()
        self._fight(inputs)
        for team in Team:
            self.minions[team][:] = [m for m in self.minions[team] if m.hp > 0]
        self.tick = tick + 1
        return self._events

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
        for foe in self.minions[1 - m.team] if foes is None else foes:
            if foe.hp <= 0:
                continue
            gap = abs(foe.s - m.s)
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
        near = [c for c in self._prey[m.team] if abs(c.s - m.s) <= limit + EPS]
        return min(near, key=lambda c: (abs(c.s - m.s), c.inp.seat)) if near else None

    def _in_reach(self, m: Minion):
        foe, _ = self._nearest(m, m.rules.attack_range)
        if foe is not None:
            return foe
        if not self.rules.m7_resolution and any(foe.hp > 0 and abs(foe.s - m.s) <= ACQUIRE + EPS for foe in self.minions[1 - m.team]):
            return None
        tower = self.front_tower(1 - m.team)
        if tower is not None and abs(tower.s - m.s) <= m.rules.attack_range + EPS:
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
        for team in Team:
            tower = self.front_tower(1 - team)
            callers = self._callers[team]
            for m in self.minions[team]:
                target = m.target
                reach = m.rules.attack_range + EPS
                if callers and type(target) is not Tower:
                    caller = min(callers, key=lambda c: (abs(c.s - m.s), c.inp.seat))
                    if abs(caller.s - m.s) <= CALL_RANGE + EPS:
                        m.target = caller
                        m.near, m.near_gap = None, inf
                        m.anchored = abs(caller.s - m.s) <= reach
                        continue
                if type(target) is Minion and target.hp > 0 and abs(target.s - m.s) <= reach:
                    m.anchored = True
                    continue
                if cap and type(target) is Minion and m.rules.kind is Kind.MELEE:
                    crowd[target.uid] = crowd.get(target.uid, 1) - 1
                m.near, m.near_gap = self._nearest(m, inf)
                if cap and m.rules.kind is Kind.MELEE and m.near is not None and crowd.get(m.near.uid, 0) >= cap:
                    open_foes = [foe for foe in self.minions[1 - team] if crowd.get(foe.uid, 0) < cap]
                    m.near, m.near_gap = self._nearest(m, inf, open_foes)
                if m.near_gap <= ACQUIRE + EPS:
                    target = m.near
                    if cap and m.rules.kind is Kind.MELEE:
                        crowd[target.uid] = crowd.get(target.uid, 0) + 1
                elif tower is not None and abs(tower.s - m.s) <= ACQUIRE + EPS:
                    target = tower
                else:
                    target = self._champion_near(m, ACQUIRE)
                m.target = target
                m.anchored = target is not None and abs(target.s - m.s) <= reach

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
                room = min(room, m.near_gap - stop)
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
            m.free_at = m.delay + advance / speed
            m.delay = 0.0

    def _schedule(self, queue: list, actor, key: int, speed: float, start: float) -> None:
        credit = min(1.0, actor.credit + speed * start)
        total = credit + speed * (self.tick_s - start)
        attacks = int(total)
        for k in range(1, attacks + 1):
            queue.append((start + (k - credit) / speed, key, actor))
        actor.credit = total - attacks

    def _fight(self, inputs: Sequence[ChampionInput]) -> None:
        dt = self.tick_s
        if not self.rules.m7_resolution:
            # champions that attack at the same instant must not be served by seat, or one of two equal laners takes every tie
            inputs = sorted(inputs, key=lambda inp: keyed_uniform(self.seed, Stream.LAST_HIT, self.lane_id, self.tick, inp.seat))
            present = {inp.seat for inp in inputs}
            self._champion_credit = {seat: credit for seat, credit in self._champion_credit.items() if seat in present}
        queue: list = []
        for team in Team:
            for m in self.minions[team]:
                target, speed = m.target, m.rules.attack_speed
                if m.hp <= 0 or target is None or abs(target.s - m.s) > m.rules.attack_range + EPS:
                    m.credit = min(1.0, m.credit + speed * dt)
                else:
                    self._schedule(queue, m, m.uid, speed, max(m.free_at, target.free_at))
        for team in Team:
            for tower in self.towers[team]:
                arrivals = [m.free_at for m in self.minions[1 - team] if m.hp > 0 and abs(m.s - tower.s) <= TOWER_RANGE + EPS]
                if tower.hp > 0 and arrivals:
                    self._schedule(queue, tower, -1 - 3 * team - tower.tier, TOWER_ATTACK_SPEED, min(arrivals))
                else:
                    tower.credit = min(1.0, tower.credit + TOWER_ATTACK_SPEED * dt)
        champions = []
        for i, inp in enumerate(inputs):
            rate = inp.attack_speed * inp.capacity
            credit = self._champion_credit.get(inp.seat, 1.0)
            ready = 0.0 if credit >= 1.0 else (1.0 - credit) / rate if rate > 0 else inf
            champion = _Champion(inp, rate, ready)
            champions.append((CHAMPION_KEY + i, champion))
            if self._hits(inp) and ready < dt:
                queue.append((ready, CHAMPION_KEY + i, champion))
        pushers = [c.inp for _, c in champions if c.inp.mode is Mode.PUSH and c.inp.in_path and c.inp.aoe_dps * c.inp.capacity > 0]
        heapq.heapify(queue)
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
            group.sort(key=lambda entry: entry[0])
            for _, actor in group:
                if type(actor) is Minion:
                    self._minion_attack(actor, now)
                elif type(actor) is Tower:
                    self._tower_attack(actor, now)
            for key, champion in champions:
                if champion.ready <= now + SAME_INSTANT and self._champion_attack(champion.inp, now):
                    champion.ready = now + 1.0 / champion.rate
                    if champion.ready < dt:
                        heapq.heappush(queue, (champion.ready, key, champion))
        self._sweep(pushers, dt - swept, dt)
        for _, champion in champions:
            if champion.rate > 0:
                self._champion_credit[champion.inp.seat] = min(1.0, 1.0 - (champion.ready - dt) * champion.rate)

    @staticmethod
    def _hits(inp: ChampionInput) -> bool:
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
        if type(target) is Tower:
            self._hit_tower(target, m.ad * m.rules.tower_multiplier, now)
        elif type(target) is ChampionTarget:
            self._events.append(ChampionDamage(self._t0 + now, target.inp.seat, m.ad * DAMAGE_TO_CHAMPIONS))
        else:
            multiplier, reduction = self._push_edge(m.team)
            blow = m.ad + m.rules.pct_current_hp * target.hp * self.rules.current_hp_damage
            self._hurt(target, max(0.0, blow * multiplier - reduction) * self.rules.minion_damage_scale, None, now)

    def _tower_attack(self, tower: Tower, now: float) -> None:
        foes = [m for m in self.minions[1 - tower.team] if m.hp > 0 and abs(m.s - tower.s) <= TOWER_RANGE + EPS] if tower.hp > 0 else []
        if not foes:
            tower.credit = min(1.0, tower.credit + 1.0)
            return
        target = min(foes, key=lambda m: (m.rules.tower_priority, abs(m.s - tower.s), m.uid))
        self._hurt(target, target.rules.tower_shot_pct * target.max_hp, None, now)

    def _hit_tower(self, tower: Tower, damage: float, now: float) -> None:
        if tower.hp <= 0:
            return
        tower.hp -= damage
        self._events.append(TowerDamage(self._t0 + now, tower.team, tower.tier, damage))
        if tower.hp <= 0:
            self._events.append(TowerDestroyed(self._t0 + now, tower.team, tower.tier))

    def _champion_attack(self, inp: ChampionInput, now: float) -> bool:
        if not self._hits(inp):
            return False
        foes = [m for m in self.minions[1 - inp.team] if m.hp > 0 and abs(m.s - inp.s) <= inp.attack_range + EPS]
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
            for m in self.minions[1 - inp.team]:
                if m.hp > 0 and abs(m.s - inp.s) <= inp.attack_range + EPS:
                    self._hurt(m, damage, inp.seat, now)

    def _hurt(self, target: Minion, damage: float, killer: int | None, now: float, shared: bool = False) -> None:
        target.hp -= damage
        if target.hp <= 0:
            target.died_group = self._group
            self.dead += 1
            gold = target.gold if killer is not None else 0
            self._events.append(MinionDeath(self._t0 + now, target.team, target.rules.kind, target.s, killer, gold, target.rules.xp, shared))


def stance(lane: LaneSim, team: int, mode: Mode, attack_range: float = STAND_OFF, front: Front | None = None) -> tuple[float, bool]:
    """Where a champion in this wave mode wants to stand, and whether it stands in the minions' path there.

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
    hold = mode is Mode.HOLD
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
