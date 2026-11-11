"""M7 wave prototype: one lane of minions on a continuous coordinate, reference variant with individual minions."""

import heapq
from dataclasses import dataclass
from enum import IntEnum
from math import inf

from riftgame.map import load_map
from riftgame.rng import Stream, keyed_uniform
from riftgame.ruleset import interpolated, load, scheduled

RULES = load()
MINIONS = RULES["minions"]
TOWERS = RULES["towers"]
SPEED = MINIONS["move_speed"]
ACQUIRE = MINIONS["acquisition_range"]
XP_RANGE = MINIONS["xp_range"]
XP_SHARE = MINIONS["xp_share"]
DAMAGE_TO_CHAMPIONS = MINIONS["damage_to_champions"]
TOWER_RANGE = TOWERS["attack_range"]
TOWER_ATTACK_SPEED = TOWERS["attack_speed"]
EPS = 1e-6
# Side-lane speed-up of the reference patch (wiki, Minion, "Sidelane Speed", read 2026-11-11): from wave 2 until 14:00 a
# top or bot minion spawns with 111 bonus speed, 4.5 less for each later wave. The bonus drops by 15 after 7, 14, and 21 s
# and is removed after 25 s.
SIDE_SPEED_FIRST_WAVE, SIDE_SPEED_BONUS, SIDE_SPEED_PER_WAVE = 2, 111.0, 4.5
SIDE_SPEED_STAGE_ENDS, SIDE_SPEED_STAGE_DROP, SIDE_SPEED_UNTIL_S = (7.0, 14.0, 21.0, 25.0), 15.0, 840.0
SAME_INSTANT = 1e-9
CHAMPION_KEY = 1 << 40
SLOTS = (-1, 0, 1)


class Team(IntEnum):
    BLUE = 0
    RED = 1


class Kind(IntEnum):
    MELEE = 0
    CASTER = 1
    SIEGE = 2


class Mode(IntEnum):
    NONE = 0
    LAST_HIT = 1
    THIN = 2
    PUSH = 3


@dataclass(frozen=True)
class LaneGeometry:
    """far_spawn_offset is the other team's spawn distance from the far end, the same as spawn_offset when omitted."""

    length: float
    spawn_offset: float
    tower_s: tuple[float, float]
    plus_team: Team = Team.BLUE
    far_spawn_offset: float | None = None
    side: bool = False

    def direction(self, team: int) -> int:
        return 1 if team == self.plus_team else -1

    def spawn_s(self, team: int) -> float:
        far = self.spawn_offset if self.far_spawn_offset is None else self.far_spawn_offset
        return self.spawn_offset if team == self.plus_team else self.length - far

    @property
    def centre(self) -> float:
        """Where two undisturbed waves meet: halfway between the spawn points."""
        return (self.spawn_s(Team.BLUE) + self.spawn_s(Team.RED)) / 2

    def swapped_sides(self) -> "LaneGeometry":
        blue, red = self.tower_s
        far = self.spawn_offset if self.far_spawn_offset is None else self.far_spawn_offset
        return LaneGeometry(self.length, far, (self.length - blue, self.length - red), Team(1 - self.plus_team), self.spawn_offset, self.side)


def lane_geometry(name: str) -> LaneGeometry:
    """Length, minion spawn points, and outer towers of a lane on the reference map."""
    data = load_map()
    length = data.rift.lanes[name].length
    outer = {site.team: site.s for site in data.towers if site.lane == name and site.tier == "outer"}
    blue, red = data.minion_spawn_s["blue", name], data.minion_spawn_s["red", name]
    return LaneGeometry(length, blue, (outer["blue"], outer["red"]), far_spawn_offset=length - red, side=name != "mid")


MID = lane_geometry("mid")
TOP = lane_geometry("top")


@dataclass(frozen=True, slots=True)
class Mechanics:
    """Optional rules. The defaults are the first-round model.

    champion_aggro: a minion with no enemy minion or tower in acquisition range attacks the closest targetable enemy champion.
    lateral_slots: a minion keeps a lateral slot in its wave, and among enemies equally far along the lane it picks the
    laterally closest. Draws for the ties that remain are keyed without the tick.
    current_hp_damage: a minion blow on a minion adds the reference patch's share of the target's current health.
    Turning it off is a sensitivity run on that sourced constant, not a candidate rule.
    side_lane_speed: minions of a side lane get the reference patch's speed bonus after they spawn.
    """

    champion_aggro: bool = False
    lateral_slots: bool = False
    current_hp_damage: bool = True
    side_lane_speed: bool = False


BASELINE = Mechanics()
RECOMMENDED = Mechanics(champion_aggro=True, lateral_slots=True)


@dataclass(frozen=True, slots=True)
class ChampionInput:
    champ_id: int
    team: Team
    s: float
    mode: Mode
    hit_damage: float = 65.0
    attack_speed: float = 0.65
    attack_range: float = 550.0
    aoe_dps: float = 70.0
    capacity: float = 1.0
    targetable: bool = False


@dataclass(frozen=True, slots=True)
class MinionDeath:
    t: float
    team: Team
    kind: Kind
    s: float
    killer: int | None
    gold: float


@dataclass(frozen=True, slots=True)
class XpGrant:
    t: float
    champ_id: int
    xp: float


@dataclass(frozen=True, slots=True)
class TowerDamage:
    t: float
    team: Team
    damage: float


@dataclass(frozen=True, slots=True)
class ChampionDamage:
    """One minion blow on a champion, before the champion's armor."""

    t: float
    champ_id: int
    damage: float


@dataclass(frozen=True, slots=True)
class TowerDestroyed:
    t: float
    team: Team


@dataclass(frozen=True, slots=True)
class Front:
    """s is the contact point of the two leading minions, or None while they are out of acquisition range."""

    s: float | None
    lead: tuple[float | None, float | None]
    counts: tuple[int, int]


def front_of(geometry: LaneGeometry, units: tuple[list[tuple[float, int]], list[tuple[float, int]]]) -> Front:
    leads = []
    for team in Team:
        spots = [s for s, _ in units[team]]
        pick = max if geometry.direction(team) > 0 else min
        leads.append(pick(spots) if spots else None)
    blue, red = leads
    touching = blue is not None and red is not None and abs(red - blue) <= ACQUIRE + EPS
    counts = tuple(sum(n for _, n in units[team]) for team in Team)
    return Front((blue + red) / 2 if touching else None, (blue, red), counts)


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
    return KindRules(
        kind,
        table["attack_speed"],
        table["attack_range"],
        min(table["attack_range"], ACQUIRE),
        table["pct_current_hp_vs_minions"],
        table["xp"],
        table["tower_shot_pct_max_hp"],
        to_towers,
        tower_priority,
        table,
    )


KINDS = (_kind_rules(Kind.MELEE, 1), _kind_rules(Kind.CASTER, 2), _kind_rules(Kind.SIEGE, 0))


def unit_stats(kind: Kind, t: float) -> tuple[float, float, float]:
    table = KINDS[kind].table
    upgrades = max(0, int((t - MINIONS["upgrade_first_s"]) // MINIONS["upgrade_interval_s"]))
    return (
        interpolated(table["hp"], table["hp_span_s"], t),
        interpolated(table["ad"], table["ad_span_s"], t),
        table["gold"] + table.get("gold_per_upgrade", 0) * upgrades,
    )


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


@dataclass(slots=True)
class Tower:
    team: int
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
    delay: float = 0.0
    credit: float = 1.0
    target: "Minion | Tower | None" = None
    near: "Minion | None" = None
    near_gap: float = inf
    anchored: bool = False
    free_at: float = 0.0
    draws: int = 0
    died_group: int = -1
    slot: float = 0.0
    born: float = 0.0
    boost: float = 0.0


@dataclass(slots=True, eq=False)
class ChampionTarget:
    """A targetable champion for one tick, with the fields a minion reads on any target."""

    inp: ChampionInput
    s: float
    hp: float = 1.0
    free_at: float = 0.0


@dataclass(slots=True)
class Tick:
    t0: float
    inputs: tuple
    events: list


class Lane:
    """Spawning, targeting, and marching shared by both variants. A body is one minion or one stack of minions."""

    mechanics = BASELINE

    def __init__(self, geometry: LaneGeometry = MID, seed: int = 0, lane_id: int = 0, dt: float = 1.0, start_time: float = 0.0):
        self.geometry = geometry
        self.seed = seed
        self.lane_id = lane_id
        self.dt = dt
        self.start_time = start_time
        self.tick = 0
        self.bodies: tuple[list, list] = ([], [])
        self.towers = tuple(Tower(team, geometry.tower_s[team], TOWERS["outer"]["hp"]) for team in Team)
        self.clock = WaveClock(start_time)
        self.spawned = 0
        self.dead = 0
        self._serial = [0, 0]
        self._champion_credit: dict[int, float] = {}
        self._prey: tuple[list[ChampionTarget], ...] = ([], [])

    @property
    def time(self) -> float:
        return self.start_time + self.tick * self.dt

    def front(self) -> Front:
        return front_of(self.geometry, (self.units(0), self.units(1)))

    def step(self, inputs=()) -> list:
        t0 = self.time
        for when, kind, wave, slot in self.clock.due(t0 + self.dt):
            for team in Team:
                self._spawn(team, kind, wave, when, max(0.0, when - t0), slot)
        tick = Tick(t0, tuple(inputs), [])
        aggro = self.mechanics.champion_aggro
        self._prey = tuple([ChampionTarget(c, c.s) for c in tick.inputs if aggro and c.targetable and c.team != team] for team in Team)
        self._acquire()
        self._march()
        self._fight(tick)
        for team in Team:
            self.bodies[team][:] = [body for body in self.bodies[team] if body.hp > 0]
        self.tick += 1
        return tick.events

    def _next_uid(self, team: int) -> int:
        self._serial[team] += 1
        return 2 * (self._serial[team] - 1) + team

    def _nearest(self, body, limit: float):
        best, tied = limit, []
        for foe in self.bodies[1 - body.team]:
            if foe.hp <= 0:
                continue
            gap = abs(foe.s - body.s)
            if gap < best - EPS:
                best, tied = gap, [foe]
            elif gap <= best + EPS:
                tied.append(foe)
        if not tied:
            return None, inf
        if len(tied) > 1 and self.mechanics.lateral_slots:
            aside = min(abs(foe.slot - body.slot) for foe in tied)
            tied = [foe for foe in tied if abs(foe.slot - body.slot) == aside]
        return (tied[0] if len(tied) == 1 else self._pick(body, tied)), best

    def _champion_near(self, body, limit: float):
        near = [c for c in self._prey[body.team] if abs(c.s - body.s) <= limit + EPS]
        return min(near, key=lambda c: (abs(c.s - body.s), c.inp.champ_id)) if near else None

    def _in_reach(self, body):
        foe, _ = self._nearest(body, body.rules.attack_range)
        if foe is not None:
            return foe
        tower = self.towers[1 - body.team]
        if tower.hp > 0 and abs(tower.s - body.s) <= body.rules.attack_range + EPS:
            return tower
        return self._champion_near(body, body.rules.attack_range)

    def _acquire(self) -> None:
        for team in Team:
            tower = self.towers[1 - team]
            for body in self.bodies[team]:
                target = body.target
                reach = body.rules.attack_range + EPS
                if target is not None and type(target) not in (Tower, ChampionTarget) and target.hp > 0 and abs(target.s - body.s) <= reach:
                    body.anchored = True
                    continue
                body.near, body.near_gap = self._nearest(body, inf)
                if body.near_gap <= ACQUIRE + EPS:
                    target = body.near
                elif tower.hp > 0 and abs(tower.s - body.s) <= ACQUIRE + EPS:
                    target = tower
                else:
                    target = self._champion_near(body, ACQUIRE)
                body.target = target
                body.anchored = target is not None and abs(target.s - body.s) <= reach

    def _march(self) -> None:
        walkers = [body for team in Team for body in self.bodies[team] if not body.anchored]
        lead_walker = [None, None]
        for team in Team:
            spots = [body.s for body in walkers if body.team == team]
            if spots:
                lead_walker[team] = max(spots) if self.geometry.direction(team) > 0 else min(spots)
        for team in Team:
            for body in self.bodies[team]:
                if body.anchored:
                    body.free_at, body.delay = body.delay, 0.0
        for body in walkers:
            heading = self.geometry.direction(body.team)
            tower = self.towers[1 - body.team]
            stop = body.rules.stop_range
            room = heading * (self.geometry.spawn_s(1 - body.team) - body.s)
            if body.near is not None:
                room = min(room, body.near_gap - stop)
            if lead_walker[1 - body.team] is not None:
                # two walkers closing on each other each take half the gap, so they meet instead of crossing within a tick
                room = min(room, (abs(lead_walker[1 - body.team] - body.s) - stop) / 2)
            if type(body.target) is ChampionTarget:
                ahead = heading * (body.target.s - body.s)
                if ahead < 0:
                    heading, room = -heading, -ahead - stop
                else:
                    room = min(room, ahead - stop)
            elif (body.target is None or type(body.target) is Tower) and tower.hp > 0 and heading * (tower.s - body.s) > 0:
                room = min(room, abs(tower.s - body.s) - stop)
            speed = self._speed(body)
            advance = max(0.0, min(speed * (self.dt - body.delay), room))
            body.s += heading * advance
            body.free_at = body.delay + advance / speed
            body.delay = 0.0

    def _speed(self, body) -> float:
        boost = getattr(body, "boost", 0.0)
        if not boost:
            return SPEED
        stage = sum(self.time - body.born >= end for end in SIDE_SPEED_STAGE_ENDS)
        return SPEED if stage == len(SIDE_SPEED_STAGE_ENDS) else SPEED + max(0.0, boost - SIDE_SPEED_STAGE_DROP * stage)

    def _tower_target(self, tower: Tower):
        foes = [b for b in self.bodies[1 - tower.team] if b.hp > 0 and abs(b.s - tower.s) <= TOWER_RANGE + EPS]
        return min(foes, key=lambda b: (b.rules.tower_priority, abs(b.s - tower.s), b.uid)) if foes else None

    def _hit_tower(self, tower: Tower, damage: float, t: float, tick: Tick) -> None:
        if tower.hp <= 0:
            return
        tower.hp -= damage
        tick.events.append(TowerDamage(t, Team(tower.team), damage))
        if tower.hp <= 0:
            tick.events.append(TowerDestroyed(t, Team(tower.team)))

    def _death(self, body, killer: int | None, t: float, tick: Tick) -> None:
        self.dead += 1
        kind = body.rules.kind
        tick.events.append(MinionDeath(t, Team(body.team), kind, body.s, killer, body.gold if killer is not None else 0))
        near = [c for c in tick.inputs if c.team != body.team and abs(c.s - body.s) <= XP_RANGE]
        if near:
            share = body.rules.xp * XP_SHARE[min(len(near), len(XP_SHARE)) - 1]
            tick.events.extend(XpGrant(t, c.champ_id, share) for c in near)


@dataclass(slots=True, eq=False)
class _Champion:
    inp: ChampionInput
    rate: float
    ready: float


class LaneSim(Lane):
    """Reference variant: every minion is a body, and blows land in time order inside the tick."""

    _group = 0

    def __init__(self, *args, mechanics: Mechanics = BASELINE, **kwargs):
        super().__init__(*args, **kwargs)
        self.mechanics = mechanics

    def add_minion(self, team: int, kind: Kind, s: float, when: float | None = None, delay: float = 0.0, count: int = 1, slot: float | None = None) -> None:
        """Without a slot, the count minions take neighbouring slots centred on the middle of the lane."""
        hp, ad, gold = unit_stats(kind, self.time if when is None else when)
        for i in range(count):
            lateral = i - (count - 1) / 2 if slot is None else slot
            self.bodies[team].append(Minion(self._next_uid(team), team, KINDS[kind], s, hp, hp, ad, gold, delay, slot=lateral))
            self.spawned += 1

    def units(self, team: int) -> list[tuple[float, int]]:
        return [(m.s, 1) for m in self.bodies[team]]

    def _spawn(self, team: int, kind: Kind, wave: int, when: float, delay: float, slot: int) -> None:
        self.add_minion(team, kind, self.geometry.spawn_s(team), when, delay, slot=slot)
        minion = self.bodies[team][-1]
        minion.born = when
        if self.mechanics.side_lane_speed and self.geometry.side and wave >= SIDE_SPEED_FIRST_WAVE and when < SIDE_SPEED_UNTIL_S:
            minion.boost = max(0.0, SIDE_SPEED_BONUS - SIDE_SPEED_PER_WAVE * (wave - SIDE_SPEED_FIRST_WAVE))

    def _pick(self, m: Minion, tied: list) -> Minion:
        m.draws += 1
        # without the tick in the key, runs at different dt draw the same numbers
        key = (m.uid, m.draws) if self.mechanics.lateral_slots else (self.tick, m.uid, m.draws)
        u = keyed_uniform(self.seed, Stream.MINION_TARGET, self.lane_id, *key)
        return tied[int(u * len(tied))]

    def _schedule(self, queue: list, actor, key: int, speed: float, start: float) -> None:
        credit = min(1.0, actor.credit + speed * start)
        total = credit + speed * (self.dt - start)
        attacks = int(total)
        for k in range(1, attacks + 1):
            queue.append((start + (k - credit) / speed, key, actor))
        actor.credit = total - attacks

    def _fight(self, tick: Tick) -> None:
        dt = self.dt
        queue: list = []
        for team in Team:
            for m in self.bodies[team]:
                target, speed = m.target, m.rules.attack_speed
                if target is None or abs(target.s - m.s) > m.rules.attack_range + EPS:
                    m.credit = min(1.0, m.credit + speed * dt)
                else:
                    self._schedule(queue, m, m.uid, speed, max(m.free_at, target.free_at))
        for tower in self.towers:
            arrivals = [m.free_at for m in self.bodies[1 - tower.team] if abs(m.s - tower.s) <= TOWER_RANGE + EPS]
            if tower.hp > 0 and arrivals:
                self._schedule(queue, tower, -1 - tower.team, TOWER_ATTACK_SPEED, min(arrivals))
            else:
                tower.credit = min(1.0, tower.credit + TOWER_ATTACK_SPEED * dt)
        champions = []
        for i, inp in enumerate(tick.inputs):
            rate = inp.attack_speed * inp.capacity
            credit = self._champion_credit.get(inp.champ_id, 1.0)
            ready = 0.0 if credit >= 1.0 else (1.0 - credit) / rate if rate > 0 else inf
            champion = _Champion(inp, rate, ready)
            champions.append((CHAMPION_KEY + i, champion))
            if inp.mode is not Mode.NONE and ready < dt:
                queue.append((ready, CHAMPION_KEY + i, champion))
        pushers = [c.inp for _, c in champions if c.inp.mode is Mode.PUSH and c.inp.aoe_dps * c.inp.capacity > 0]
        heapq.heapify(queue)
        swept = 0.0
        while queue:
            now = queue[0][0]
            self._sweep(pushers, now - swept, now, tick)
            swept = now
            self._group += 1
            group = []
            while queue and queue[0][0] <= now + SAME_INSTANT:
                group.append(heapq.heappop(queue)[1:])
            group.sort(key=lambda entry: entry[0])
            for _, actor in group:
                if type(actor) is Minion:
                    self._minion_attack(actor, now, tick)
                elif type(actor) is Tower:
                    self._tower_attack(actor, now, tick)
            for key, champion in champions:
                if champion.ready <= now + SAME_INSTANT and self._champion_attack(champion.inp, now, tick):
                    champion.ready = now + 1.0 / champion.rate
                    if champion.ready < dt:
                        heapq.heappush(queue, (champion.ready, key, champion))
        self._sweep(pushers, dt - swept, dt, tick)
        for _, champion in champions:
            if champion.rate > 0:
                self._champion_credit[champion.inp.champ_id] = min(1.0, 1.0 - (champion.ready - dt) * champion.rate)

    def _minion_attack(self, m: Minion, now: float, tick: Tick) -> None:
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
            self._hit_tower(target, m.ad * m.rules.tower_multiplier, tick.t0 + now, tick)
        elif type(target) is ChampionTarget:
            tick.events.append(ChampionDamage(tick.t0 + now, target.inp.champ_id, m.ad * DAMAGE_TO_CHAMPIONS))
        else:
            self._hurt(target, m.ad + m.rules.pct_current_hp * target.hp * self.mechanics.current_hp_damage, None, now, tick)

    def _tower_attack(self, tower: Tower, now: float, tick: Tick) -> None:
        target = self._tower_target(tower) if tower.hp > 0 else None
        if target is None:
            tower.credit = min(1.0, tower.credit + 1.0)
        else:
            self._hurt(target, target.rules.tower_shot_pct * target.max_hp, None, now, tick)

    def _champion_attack(self, inp: ChampionInput, now: float, tick: Tick) -> bool:
        if inp.mode is Mode.NONE:
            return False
        foes = [m for m in self.bodies[1 - inp.team] if m.hp > 0 and abs(m.s - inp.s) <= inp.attack_range + EPS]
        choice = [m for m in foes if m.hp <= inp.hit_damage]
        if not choice and inp.mode is Mode.THIN:
            choice = [m for m in foes if m.rules.kind is Kind.CASTER] or foes
        elif not choice and inp.mode is Mode.PUSH:
            choice = foes
        if not choice:
            return False
        self._hurt(min(choice, key=lambda m: (m.hp, m.uid)), inp.hit_damage, inp.champ_id, now, tick)
        return True

    def _sweep(self, pushers: list, span: float, now: float, tick: Tick) -> None:
        if span <= 0:
            return
        for inp in pushers:
            damage = inp.aoe_dps * inp.capacity * span
            for m in self.bodies[1 - inp.team]:
                if m.hp > 0 and abs(m.s - inp.s) <= inp.attack_range + EPS:
                    self._hurt(m, damage, inp.champ_id, now, tick)

    def _hurt(self, target: Minion, damage: float, killer: int | None, now: float, tick: Tick) -> None:
        target.hp -= damage
        if target.hp <= 0:
            target.died_group = self._group
            self._death(target, killer, tick.t0 + now, tick)
