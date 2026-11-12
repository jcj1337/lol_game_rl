"""What one champion may know, and which actions that knowledge leaves legal.

`observe` is the only function that reads the world for a policy. It reads the champion's own state, its
teammates' state, its team's memory, and the clock. `legal_mask` takes the observation alone.

A team's memory holds what the team has seen. `remember` is the only function that writes it, once a tick, from
what `sources` lets the team see. The memory holds the camps and the enemy champions. C6 adds the enemy waves.

Everything in an observation is in the champion's team frame. Actions and nodes are named as in
`riftgame.champions`. A position is a `Place`, measured outward from the team's own fountain. The map has no
exact mirror symmetry, so two mirrored places are the same `Place` only on a lane and on a fountain.
"""

import math
from dataclasses import dataclass
from enum import IntEnum
from functools import cache
from typing import TYPE_CHECKING, NamedTuple

from riftgame import ruleset
from riftgame.champions import (ACTIONS, CAMP_OF, ENABLED, FOUNTAIN, HOME, KEEP, MAP, RETURNS, RIFT, TEAMS, Champion, Duty,
                                Kind, Outcome, R, capability_of, duty, frame_name, home_lane, homeguard_bonus, level_of)
from riftgame.jungle import SITES, CampDeath
from riftgame.map import Pos, _crosses

if TYPE_CHECKING:
    from riftgame.world import Config, World

SIGHT = R["champions"]["sight_range"]
TOWER_SIGHT = R["towers"]["sight_range"]
# Per team: the lane, the tier, and the place of each of its lane towers.
TOWER_SITES = tuple(tuple((t.lane, t.tier, RIFT.lane_pos(t.lane, t.s)) for t in MAP.towers if t.team == team) for team in TEAMS)
DEFENCE_S = ruleset.load("patch_26_22_m8")["combat"]["self_defence_window_s"]


@dataclass(frozen=True, slots=True)
class Sight:
    """A sight source that stays where it was put: it gives `team` sight within `radius` of `pos` until the tick
    `expires`. A Speed Shrine is one, and C6 adds wards as more of the same."""

    team: int
    pos: Pos
    radius: float
    expires: int


@dataclass(slots=True)
class CampMemory:
    """What a team knows of one camp.

    `hp` and `level` are what the team last saw at the camp's location, at `seen_tick`: zero for an empty camp,
    and -1 for the tick if it never saw the location. `spawn_tick` is the camp's next spawn where the team knows
    it, and -1 where it does not. A known spawn that has passed stays until the team sees the location again.
    """

    hp: float
    level: int
    seen_tick: int
    spawn_tick: int


@dataclass(slots=True)
class EnemyMemory:
    """What a team knows of one enemy champion: where it last saw it, with what health and level, and when.

    `seen_tick` is -1 if the team never saw it. The record is current, and the team sees the champion now, while
    `seen_tick` is the world's tick. Out of the view the record stays as it was (M7 section 6.2).
    """

    pos: Pos
    hp: float
    level: int
    seen_tick: int


@dataclass(slots=True)
class Memory:
    """One team's memory. The camps are in the order of `jungle.SITES`, the enemy champions in role order."""

    camps: list[CampMemory]
    enemies: list[EnemyMemory]


def new_memory(config: "Config", team: int) -> Memory:
    """A team's memory at the start of a game. The first spawn of every camp is public (reference row D16a), and
    so is the fountain that every enemy champion starts on."""
    return Memory([CampMemory(0.0, 0, -1, config.ticks(site.kind.first_spawn_s)) for site in SITES],
                  [EnemyMemory(FOUNTAIN[1 - team], 0.0, 0, -1) for _ in range(5)])


def _edge_gaps() -> list[list[float]]:
    """Per pair of map edges, the shortest straight line between them. No two positions on the two edges are
    nearer than that, so a pair of edges further apart than a sight radius needs no sight test."""
    def off(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
        dx, dy = bx - ax, by - ay
        f = min(1.0, max(0.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - ax - f * dx, py - ay - f * dy)

    def gap(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float], d: tuple[float, float]) -> float:
        if _crosses(*a, *b, (*c, *d)):
            return 0.0
        return min(off(*a, *c, *d), off(*b, *c, *d), off(*c, *a, *b), off(*d, *a, *b))

    ends = [(RIFT.node_xy[e.a], RIFT.node_xy[e.b]) for e in RIFT.edges]
    return [[gap(*one, *other) for other in ends] for one in ends]


EDGE_GAP = _edge_gaps()


def sources(world: "World", team: int) -> list[tuple[Pos, float]]:
    """Every sight source of a team now, as (position, radius): its living champions, its standing lane towers,
    and its shrines.

    This is the one place the list lives. Lane minions and wards are sources too (M7 section 6.1). C6 adds them
    here.
    """
    first = team * 5
    champions = [(c.pos, SIGHT) for c in world.champions[first:first + 5] if c.hp > 0]
    lanes = world.lanes
    towers = [(pos, TOWER_SIGHT) for lane, tier, pos in TOWER_SITES[team] if lanes[lane].tower_alive(team, tier)]
    return champions + towers + [(s.pos, s.radius) for s in world.sights if s.team == team]


def _lit(lit: list[tuple[Pos, float]], pos: Pos) -> bool:
    gaps = EDGE_GAP[pos.edge]
    return any(gaps[at.edge] <= radius and RIFT.sees(at, pos, radius) for at, radius in lit)


def sees(world: "World", team: int, pos: Pos) -> bool:
    """Whether a team sees a position now, by the sight measure of M7 section 5.1."""
    return _lit(sources(world, team), pos)


@cache
def _camps_in_reach(edge: int, radius: float) -> tuple[tuple[int, float, float], ...]:
    """Per camp that a source of this radius could see from this edge: the camp, and the two offsets between which
    the edge lies within the radius of it. A source off that stretch needs no sight test for the camp."""
    e = RIFT.edges[edge]
    (ax, ay), (bx, by) = RIFT.node_xy[e.a], RIFT.node_xy[e.b]
    dx, dy = bx - ax, by - ay
    reach = []
    for i, site in enumerate(SITES):
        px, py = RIFT.xy(site.pos)
        # The edge's point at share f of its length is within the radius where a quadratic in f is not positive.
        a, b, c = dx * dx + dy * dy, 2 * (dx * (ax - px) + dy * (ay - py)), (ax - px) ** 2 + (ay - py) ** 2 - radius * radius
        root = b * b - 4 * a * c
        if root >= 0:
            lo, hi = (-b - math.sqrt(root)) / (2 * a) - _SLACK, (-b + math.sqrt(root)) / (2 * a) + _SLACK
            if lo <= 1 and hi >= 0:
                reach.append((i, lo * e.length, hi * e.length))
    return tuple(reach)


# The stretch is a little wide, so that rounding never rules out a source that the sight test would accept.
_SLACK = 1e-9


def remember(world: "World") -> None:
    """Step 7 of the tick: sight sources that have run out go, and each team's memory takes in what the team sees.

    A team that sees a camp's location records the camp's health and level. It learns the camp's next spawn by the
    reference rule (M7 section 3.3): it sees the location on the tick the camp dies, or it sees the empty camp
    within the kind's window before the spawn. Outside both, the sight of an empty camp tells it that the camp is
    gone and no more.

    The reference has no rule for the Scuttler. Here the same rule holds, with the window of a camp without a buff.
    The team that sees the death that starts the river's timer learns the spawn at whichever river node it falls,
    as the game marks that node ahead of time (Assumed).

    A team sees a living enemy champion that stands where the team sees, and one that damaged a champion of the
    team on this tick (M7 section 6.1). Its record of a champion that it sees is current. Out of the view the
    record freezes.
    """
    tick, config = world.tick, world.config
    # A policy reads the memory from the next tick on, so ages and windows count from there.
    now = tick + 1
    if any(s.expires <= tick for s in world.sights):
        world.sights[:] = [s for s in world.sights if s.expires > tick]
    deaths = [e for _, e in world.events if type(e) is CampDeath]
    for team in range(2):
        lit = sources(world, team)
        allies = world.champions[team * 5:team * 5 + 5]
        for enemy, record in zip(world.champions[(1 - team) * 5:(2 - team) * 5], world.memory[team].enemies):
            if enemy.hp > 0 and (any(ally.hurt_tick[enemy.seat % 5] == tick for ally in allies) or _lit(lit, enemy.pos)):
                record.pos, record.hp, record.level, record.seen_tick = enemy.pos, enemy.hp, level_of(enemy.xp), now
        seen = {i for at, radius in lit for i, lo, hi in _camps_in_reach(at.edge, radius)
                if lo <= at.offset <= hi and RIFT.sees(at, SITES[i].pos, radius)}
        known = world.memory[team].camps
        for i in seen:
            camp, mine = world.camps[i], known[i]
            mine.hp, mine.seen_tick = camp.hp, now
            if camp.hp > 0:
                mine.level, mine.spawn_tick = camp.level, -1
                continue
            mine.level = 0
            if 0 <= camp.spawn_tick <= now + config.ticks(SITES[i].kind.timer_window_s):
                mine.spawn_tick = camp.spawn_tick
            elif mine.spawn_tick < now:
                mine.spawn_tick = -1
        for death in deaths:
            if death.camp in seen and death.respawn >= 0:
                known[death.respawn].spawn_tick = world.camps[death.respawn].spawn_tick


@dataclass(frozen=True, slots=True)
class Place:
    """A position in a team's frame, `s` units along a route.

    A route is a lane, measured from the team's own end, or one edge off the lanes, named `a>b` by its end nodes
    with `a` the end that is nearer the team's fountain.
    """

    route: str
    s: float


@dataclass(frozen=True, slots=True)
class ChampionView:
    """A champion as it and its teammates know it. `home` is the lane it is assigned to now, `duty` its duty
    state while a roam allowance applies to it, `intent` an action index, `dead_s` the time until it can act again.
    `homeguard` is the share of its move speed that Homeguard adds on this tick, and `homeguard_blocked_s` the time
    until it may have Homeguard again after combat. `hurt_by` says, by enemy role, whether that enemy damaged it
    within the self-defence window."""

    role: int
    place: Place
    hp: float
    max_hp: float
    mana: float
    max_mana: float
    level: int
    xp: float
    gold: float
    upgrades: int
    intent: int
    channel_s: float
    outcome: Outcome
    outcome_age_s: float
    dead_s: float
    home: str | None
    duty: Duty | None
    allowance: float
    item_charges: int
    homeguard: float
    homeguard_blocked_s: float
    hurt_by: tuple[bool, ...]


class EnemyView(NamedTuple):
    """An enemy champion that the champion's team sees now."""

    place: Place
    hp: float
    level: int


class CampView(NamedTuple):
    """A camp as the champion's team remembers it, and the champion's walk to it.

    `hp` and `level` are what the team last saw at the camp's location, `seen_age_s` ago: zero for an empty camp,
    and None for the age if it never saw the location. `spawn_s` is the time until the camp's next spawn where the
    team knows it, 0 once that time has passed, and None where it knows none. `walk` is the route length from the
    champion to the camp.
    """

    hp: float
    level: int
    seen_age_s: float | None
    spawn_s: float | None
    walk: float


@dataclass(frozen=True, slots=True)
class Observation:
    """`mates` are the four teammates in role order. `camps` are in the order of the `CAMP` actions. `enemies`
    are the five enemy champions in role order, each None unless the team sees it now. A dead enemy is not seen."""

    time_s: float
    me: ChampionView
    mates: tuple[ChampionView, ...]
    camps: tuple[CampView, ...]
    enemies: tuple[EnemyView | None, ...]


def _frame_edges(team: int) -> tuple[tuple[str, float, float], ...]:
    """Per map edge: the route it belongs to, and the start and sign that turn an offset into the route's `s`."""
    lane_of = {e: (name, lane.starts[i], lane.length) for name, lane in RIFT.lanes.items() for i, e in enumerate(lane.edges)}
    rows = []
    for i, edge in enumerate(RIFT.edges):
        if i in lane_of:
            name, start, length = lane_of[i]
            rows.append((name, start, 1.0) if team == 0 else (name, length - start, -1.0))
            continue
        a, b = frame_name(team, RIFT.node_names[edge.a]), frame_name(team, RIFT.node_names[edge.b])
        if RIFT.distance(FOUNTAIN[team], Pos(i, 0.0)) <= RIFT.distance(FOUNTAIN[team], Pos(i, edge.length)):
            rows.append((f"{a}>{b}", 0.0, 1.0))
        else:
            rows.append((f"{b}>{a}", edge.length, -1.0))
    return tuple(rows)


_FRAME_EDGES = tuple(_frame_edges(team) for team in range(2))


def to_frame(team: int, pos: Pos) -> Place:
    route, start, sign = _FRAME_EDGES[team][pos.edge]
    return Place(route, start + sign * pos.offset)


def _view(world: "World", c: Champion) -> ChampionView:
    tick_s = world.config.tick_s
    can = capability_of(c)
    since = world.tick - world.config.ticks(DEFENCE_S)
    return ChampionView(
        hurt_by=tuple(tick >= since for tick in c.hurt_tick),
        role=c.role, place=to_frame(c.team, c.pos), hp=c.hp, max_hp=can.max_hp, mana=c.mana, max_mana=can.max_mana,
        level=level_of(c.xp), xp=c.xp, gold=c.gold, upgrades=c.upgrades, intent=c.intent, channel_s=c.channel * tick_s,
        outcome=c.outcome, outcome_age_s=(world.tick - c.outcome_tick) * tick_s if c.outcome else 0.0,
        dead_s=max(0, c.respawn_tick + 1 - world.tick) * tick_s, home=home_lane(world, c.seat), duty=duty(world, c),
        allowance=c.allowance, item_charges=c.item_charges, homeguard=homeguard_bonus(world, c),
        homeguard_blocked_s=max(0, c.homeguard_block - world.tick) * tick_s)


# Per team: the camps in the order of that team's `CAMP` actions. Per map node: the walk from it to every camp.
_FRAME_CAMPS = tuple(tuple(i for i in CAMP_OF[team] if i >= 0) for team in range(2))
_CAMP_WALK = tuple(tuple(row[RIFT.node_names.index(site.node)] for site in SITES) for row in RIFT.node_dist)


def _camps(world: "World", c: Champion) -> tuple[CampView, ...]:
    tick, tick_s = world.tick, world.config.tick_s
    known = world.memory[c.team].camps
    edge = RIFT.edges[c.pos.edge]
    back, on = c.pos.offset, edge.length - c.pos.offset
    from_a, from_b = _CAMP_WALK[edge.a], _CAMP_WALK[edge.b]
    views = []
    for i in _FRAME_CAMPS[c.team]:
        mine = known[i]
        views.append(CampView(mine.hp, mine.level, None if mine.seen_tick < 0 else (tick - mine.seen_tick) * tick_s,
                              None if mine.spawn_tick < 0 else max(0, mine.spawn_tick - tick) * tick_s,
                              min(back + from_a[i], on + from_b[i])))
    return tuple(views)


def observe(world: "World", seat: int) -> Observation:
    first = seat // 5 * 5
    views = [_view(world, c) for c in world.champions[first:first + 5]]
    me = views.pop(seat % 5)
    tick, team = world.tick, seat // 5
    enemies = tuple(EnemyView(to_frame(team, record.pos), record.hp, record.level) if record.seen_tick == tick else None
                    for record in world.memory[team].enemies)
    return Observation(tick * world.config.tick_s, me, tuple(views), _camps(world, world.champions[seat]), enemies)


class Leash(IntEnum):
    """What the laning role leaves legal."""

    FREE = 0      # no assignment: every enabled action
    LANED = 1     # assigned, with allowance left or with no allowance rule: LANE only for the home lane
    HOME = 2      # no allowance, on the home lane: the return actions and HOLD
    RETURN = 3    # no allowance, off the home lane: the return actions


def _leash(me: ChampionView) -> Leash:
    if me.home is None:
        return Leash.FREE
    if me.duty is None or me.allowance > 0:
        return Leash.LANED
    return Leash.HOME if me.duty is Duty.ON_LANE else Leash.RETURN


@cache
def _permitted(role: int, leash: Leash) -> tuple[bool, ...]:
    def permits(i: int) -> bool:
        a = ACTIONS[i]
        if not ENABLED[i] or (a.kind is Kind.FOLLOW and a.target == role):
            return False
        if leash is Leash.FREE:
            return True
        if leash is Leash.LANED:
            return a.kind is not Kind.LANE or a.target[0] == HOME[role]
        return RETURNS[role][i] or (leash is Leash.HOME and a.kind is Kind.HOLD)

    return tuple(permits(i) for i in range(len(ACTIONS)))


_DEAD = tuple(i == KEEP for i in range(len(ACTIONS)))
_FIGHT = tuple((i, a.target) for i, a in enumerate(ACTIONS) if a.kind is Kind.FIGHT)


def legal_mask(o: Observation) -> tuple[bool, ...]:
    """One flag per entry of `ACTIONS`. A dead champion may only KEEP.

    `FIGHT` is legal only against an enemy that the team sees now, which is a living one. KEEP is legal when the
    role permits the intent it keeps, so a running fight is kept also after its target has left the view.
    """
    me = o.me
    if me.hp <= 0:
        return _DEAD
    permitted = _permitted(me.role, _leash(me))
    mask = list(permitted)
    for i, foe in _FIGHT:
        # Self-defence: a fight against an enemy that damaged this champion a moment ago is legal under every leash.
        mask[i] = o.enemies[foe] is not None and (permitted[i] or me.hurt_by[foe])
    mask[KEEP] = permitted[me.intent] or mask[me.intent]
    return tuple(mask)
