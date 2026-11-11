"""What one champion may know, and which actions that knowledge leaves legal.

`observe` is the only function that reads the world for a policy. Until C6 adds the team view and memory, it
reads the champion's own state, its teammates' state, and public facts. `legal_mask` takes the observation alone.

Everything in an observation is in the champion's team frame. Actions and nodes are named as in
`riftgame.champions`. A position is a `Place`, measured outward from the team's own fountain. The map has no
exact mirror symmetry, so two mirrored places are the same `Place` only on a lane and on a fountain.
"""

from dataclasses import dataclass
from enum import IntEnum
from functools import cache
from typing import TYPE_CHECKING

from riftgame.champions import (ACTIONS, ENABLED, FOUNTAIN, HOME, KEEP, RETURNS, RIFT, Champion, Duty, Kind, Outcome,
                                capability_of, duty, frame_name, home_lane, level_of)
from riftgame.map import Pos

if TYPE_CHECKING:
    from riftgame.world import World


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
    state while a roam allowance applies to it, `intent` an action index, `dead_s` the time until it can act again."""

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


@dataclass(frozen=True, slots=True)
class Observation:
    """`mates` are the four teammates in role order."""

    time_s: float
    me: ChampionView
    mates: tuple[ChampionView, ...]


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
    return ChampionView(
        role=c.role, place=to_frame(c.team, c.pos), hp=c.hp, max_hp=can.max_hp, mana=c.mana, max_mana=can.max_mana,
        level=level_of(c.xp), xp=c.xp, gold=c.gold, upgrades=c.upgrades, intent=c.intent, channel_s=c.channel * tick_s,
        outcome=c.outcome, outcome_age_s=(world.tick - c.outcome_tick) * tick_s if c.outcome else 0.0,
        dead_s=max(0, c.respawn_tick + 1 - world.tick) * tick_s, home=home_lane(world, c.seat), duty=duty(world, c),
        allowance=c.allowance, item_charges=c.item_charges)


def observe(world: "World", seat: int) -> Observation:
    first = seat // 5 * 5
    views = [_view(world, c) for c in world.champions[first:first + 5]]
    me = views.pop(seat % 5)
    return Observation(world.tick * world.config.tick_s, me, tuple(views))


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


def legal_mask(o: Observation) -> tuple[bool, ...]:
    """One flag per entry of `ACTIONS`. KEEP is legal when the intent it keeps is. A dead champion may only KEEP."""
    me = o.me
    if me.hp <= 0:
        return _DEAD
    permitted = _permitted(me.role, _leash(me))
    # Self-defence goes here: C5 keeps FIGHT against an enemy that is attacking this champion legal under every leash.
    return (permitted[me.intent], *permitted[1:])
