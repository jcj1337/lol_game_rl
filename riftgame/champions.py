"""Champions: seats, capability, the action table, and how an intent is carried out.

A seat is `team * 5 + role`, with team 0 blue and team 1 red. An action is an index into `ACTIONS`. Both teams
share the table, because its targets are named in the acting team's frame: `own_*` and `enemy_*` stand for the
map's `blue_*` and `red_*` nodes, and an ally or an enemy is named by its role.

A champion holds one intent, the index of the action it is carrying out. `RULES` says how each kind is carried
out: the world calls `walk` in the move step and `settle` after damage. The functions here take the world and
never import it.
"""

from bisect import bisect_right
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import IntEnum
from functools import cache
from itertools import accumulate
from typing import TYPE_CHECKING, NamedTuple

from riftgame import ruleset
from riftgame.lanes import Mode, stance
from riftgame.map import Pos, load_map

if TYPE_CHECKING:
    from riftgame.world import World

R = ruleset.load()
MAP = load_map()
RIFT = MAP.rift

TEAMS = ("blue", "red")
ROLES = ("top", "jungle", "mid", "carry", "support")
LANES = ("top", "mid", "bot")
HOME = ("top", None, "mid", "bot", "bot")
MODES = ("passive", "last_hit", "thin", "push", "hold")
SEATS = range(10)

FOUNTAIN = tuple(RIFT.at(f"{team}_fountain") for team in TEAMS)
OUTER_TOWER = tuple({t.lane: RIFT.lane_pos(t.lane, t.s) for t in MAP.towers if t.team == team and t.tier == "outer"}
                    for team in TEAMS)
RECALL_S = R["recall"]["cast_s"] + R["recall"]["channel_s"]


class Capability(NamedTuple):
    max_hp: float
    hp_regen: float
    max_mana: float
    move_speed: float
    hit_damage: float
    attack_speed: float
    attack_range: float
    area_dps: float


# Assumed until M9. The numbers come from the M7 prototype, except hp_regen and max_mana, which are new guesses.
PROFILES = {
    "top":     Capability(650.0, 1.7, 300.0, 340.0, 65.0, 0.65, 175.0, 20.0),
    "jungle":  Capability(600.0, 1.6, 320.0, 345.0, 62.0, 0.68, 175.0, 25.0),
    "mid":     Capability(540.0, 1.2, 420.0, 335.0, 55.0, 0.63, 525.0, 40.0),
    "carry":   Capability(520.0, 0.8, 330.0, 325.0, 60.0, 0.70, 550.0, 10.0),
    "support": Capability(560.0, 1.1, 380.0, 335.0, 50.0, 0.60, 500.0, 5.0),
}
LEVEL_GROWTH = 0.08
LEVEL_SCALED = frozenset(("max_hp", "hp_regen", "max_mana", "hit_damage", "area_dps"))


@cache
def capability(profile: str, level: int, upgrades: int) -> Capability:
    """What a champion can do. `upgrades` changes nothing until C3 adds the progressions."""
    growth = 1.0 + LEVEL_GROWTH * (level - 1)
    base = PROFILES[profile]
    return Capability(*(value * growth if name in LEVEL_SCALED else value for name, value in zip(base._fields, base)))


def damage(raw: float, target: Capability) -> float:
    """Health that `raw` damage removes from a champion with capability `target`. The identity until M9."""
    return raw


_E = R["economy"]
LEVEL_XP = tuple(accumulate(_E["xp_first_level_up"] + _E["xp_level_up_step"] * n for n in range(_E["level_cap"] - 1)))


def level_of(xp: float) -> int:
    return 1 + bisect_right(LEVEL_XP, xp)


def death_timer_s(level: int, now_s: float) -> float:
    d = R["death"]
    scaling = d["time_scaling_per_30s"] * (max(0.0, now_s - d["time_scaling_start_s"]) // 30)
    return d["respawn_s"][level - 1] * (1.0 + scaling)


class Kind(IntEnum):
    KEEP = 0
    HOLD = 1
    RECALL = 2
    MOVE = 3
    LANE = 4
    CAMP = 5
    FOLLOW = 6
    FIGHT = 7
    SIEGE = 8
    WARD = 9


class Outcome(IntEnum):
    """How a champion's last finished intent ended."""

    NONE = 0
    ARRIVED = 1
    CLEARED = 2
    ABSENT = 3
    KILLED = 4
    LOST = 5
    PLACED = 6
    RECALLED = 7
    INTERRUPTED = 8
    DIED = 9


class Duty(IntEnum):
    """Where an assigned laner stands against its lane. The value indexes the rate that the roam allowance moves at."""

    ON_LANE = 0
    RETURNING = 1
    ROAMING = 2


class Income(IntEnum):
    """Sources of gold, one ledger entry each."""

    STARTING = 0
    PASSIVE = 1
    MINION = 2
    SUPPORT_ITEM = 3


class Action(NamedTuple):
    """`target` is a frame node name for MOVE, CAMP and WARD, a (lane, mode) pair for LANE, a lane for SIEGE,
    and a role index for FOLLOW and FIGHT."""

    kind: Kind
    target: str | int | tuple[str, str] | None = None


def frame_name(team: int, node: str) -> str:
    """A map node's name in a team's frame."""
    side, _, rest = node.partition("_")
    if side not in TEAMS:
        return node
    return ("own_" if side == TEAMS[team] else "enemy_") + rest


NODES = tuple(frame_name(0, node) for node in RIFT.node_names)
CAMP_NODES = tuple(frame_name(0, node) for node in (*MAP.camps, *MAP.scuttlers.values()))

# WARD comes last so that C6 can settle the ward spots without moving another index.
ACTIONS = (
    Action(Kind.KEEP), Action(Kind.HOLD), Action(Kind.RECALL),
    *(Action(Kind.MOVE, node) for node in NODES),
    *(Action(Kind.LANE, (lane, mode)) for lane in LANES for mode in MODES),
    *(Action(Kind.CAMP, node) for node in CAMP_NODES),
    *(Action(Kind.FOLLOW, role) for role in range(len(ROLES))),
    *(Action(Kind.FIGHT, role) for role in range(len(ROLES))),
    *(Action(Kind.SIEGE, lane) for lane in LANES),
    *(Action(Kind.WARD, node) for node in CAMP_NODES),
)
KEEP, HOLD, RECALL = 0, 1, 2

NODE_POS = tuple({frame_name(team, node): RIFT.at(node) for node in RIFT.node_names} for team in range(2))
DEST = tuple(tuple(NODE_POS[team][a.target] if a.kind in (Kind.MOVE, Kind.CAMP) else None for a in ACTIONS)
             for team in range(2))


@dataclass(slots=True)
class Champion:
    """One champion's mutable state. Team, role, profile and home lane follow from the seat, level from XP, and
    liveness from health."""

    seat: int
    pos: Pos
    hp: float
    mana: float
    xp: float
    gold: float
    earned: list[float]
    upgrades: int
    intent: int
    intent_tick: int
    channel: int
    outcome: Outcome
    outcome_tick: int
    allowance: float
    attack_credit: float
    item_charges: int
    respawn_tick: int

    @property
    def team(self) -> int:
        return self.seat // 5

    @property
    def role(self) -> int:
        return self.seat % 5


def capability_of(c: Champion) -> Capability:
    return capability(ROLES[c.seat % 5], level_of(c.xp), c.upgrades)


def pay(c: Champion, source: Income, amount: float) -> None:
    c.gold += amount
    c.earned[source] += amount


def spawn(seat: int, allowance: float) -> Champion:
    """A champion at the start of a game: on its fountain, at full health, holding."""
    full = capability(ROLES[seat % 5], 1, 0)
    c = Champion(seat=seat, pos=FOUNTAIN[seat // 5], hp=full.max_hp, mana=full.max_mana, xp=0.0, gold=0.0,
                 earned=[0.0] * len(Income), upgrades=0, intent=HOLD, intent_tick=0, channel=0, outcome=Outcome.NONE,
                 outcome_tick=-1, allowance=allowance, attack_credit=0.0, item_charges=0, respawn_tick=-1)
    pay(c, Income.STARTING, _E["starting_gold"])
    return c


def finish(c: Champion, outcome: Outcome, tick: int) -> None:
    """End the champion's intent with an outcome. It holds until its next decision."""
    c.intent, c.channel, c.outcome, c.outcome_tick = HOLD, 0, outcome, tick


LANE_EDGES = {name: frozenset(lane.edges) for name, lane in RIFT.lanes.items()}
LANE_NODE_IDS = {name: frozenset(n for e in edges for n in (RIFT.edges[e].a, RIFT.edges[e].b))
                 for name, edges in LANE_EDGES.items()}


def on_lane(lane: str, pos: Pos) -> bool:
    """True on an edge of the lane, and at one of its nodes even when the position names a neighbouring edge."""
    if pos.edge in LANE_EDGES[lane]:
        return True
    edge = RIFT.edges[pos.edge]
    nodes = LANE_NODE_IDS[lane]
    return (pos.offset <= 0.0 and edge.a in nodes) or (pos.offset >= edge.length and edge.b in nodes)


def on_fountain(c: Champion) -> bool:
    return RIFT.separation(c.pos, FOUNTAIN[c.seat // 5]) <= R["fountain"]["regen_radius"]


def lane_post(world: "World", seat: int, lane: str) -> Pos:
    """Where a champion with a `LANE` intent for `lane` walks to: the stance of its wave mode.

    The stance reads the lane's true front. C6 has to pass the front that the champion's team sees.
    """
    c = world.champions[seat]
    mode = Mode(MODES.index(ACTIONS[c.intent].target[1]))
    s, _ = stance(world.lanes[lane], seat // 5, mode, capability_of(c).attack_range)
    return RIFT.lane_pos(lane, s)


def _returns(role: int) -> tuple[bool, ...]:
    lane = HOME[role]
    if lane is None:
        return (False,) * len(ACTIONS)
    # Every lane ends in the enemy base, and the shortest walk there may leave the home lane, so it is no way home.
    homeward = ({frame_name(0, RIFT.node_names[n]) for n in LANE_NODE_IDS[lane]} | {"own_base", "own_fountain"}) - {"enemy_base"}
    return tuple(a.kind is Kind.RECALL or (a.kind is Kind.LANE and a.target[0] == lane)
                 or (a.kind is Kind.MOVE and a.target in homeward) for a in ACTIONS)


# By role: the actions that take a laner back to its lane or its base. A laner under one of them is returning,
# not roaming, and they are what a laner with no allowance may choose.
RETURNS = tuple(_returns(role) for role in range(len(ROLES)))


def home_lane(world: "World", seat: int) -> str | None:
    """The lane a champion is assigned to now. None for a jungler, and for a laner once its assignment has ended."""
    lane = HOME[seat % 5]
    if lane is None:
        return None
    config = world.config
    if world.tick * config.tick_s >= config.assignments_end_s:
        return None
    if config.outer_tower_ends_assignment and not all(world.lanes[lane].tower_alive(team, "outer") for team in range(2)):
        return None
    return lane


def duty(world: "World", c: Champion) -> Duty | None:
    """The duty state of M7 section 5.10. None when no roam allowance applies to the champion."""
    if not world.config.roam_restricted:
        return None
    lane = home_lane(world, c.seat)
    if lane is None:
        return None
    if c.hp <= 0:
        return Duty.RETURNING
    if on_lane(lane, c.pos):
        return Duty.ON_LANE
    return Duty.RETURNING if RETURNS[c.seat % 5][c.intent] or on_fountain(c) else Duty.ROAMING


class Rule(NamedTuple):
    """How one kind of intent is carried out.

    `walk` gives the position the champion heads for in the move step, or None to stand. `settle` runs after
    damage: it advances the intent and returns its outcome once it is over. A pursuer moves after everyone else,
    against the positions held before the move step. A kind with an `enabled_by` note is masked off until then.
    """

    walk: Callable[["World", Champion, Sequence[Pos]], Pos | None] | None = None
    settle: Callable[["World", Champion], Outcome] | None = None
    pursues: bool = False
    enabled_by: str = ""


def _to_node(world: "World", c: Champion, stood: Sequence[Pos]) -> Pos:
    return DEST[c.seat // 5][c.intent]


def _to_post(world: "World", c: Champion, stood: Sequence[Pos]) -> Pos:
    return lane_post(world, c.seat, ACTIONS[c.intent].target[0])


def _to_ally(world: "World", c: Champion, stood: Sequence[Pos]) -> Pos | None:
    ally = c.seat // 5 * 5 + ACTIONS[c.intent].target
    return stood[ally] if world.champions[ally].hp > 0 else None


def _on_arrival(outcome: Outcome) -> Callable[["World", Champion], Outcome]:
    def settle(world: "World", c: Champion) -> Outcome:
        return outcome if c.pos == DEST[c.seat // 5][c.intent] else Outcome.NONE
    return settle


def _channel_recall(world: "World", c: Champion) -> Outcome:
    c.channel += 1
    if c.channel < world.config.ticks(RECALL_S) and not on_fountain(c):
        return Outcome.NONE
    c.pos = FOUNTAIN[c.seat // 5]
    return Outcome.RECALLED


RULES = {
    Kind.KEEP: Rule(),
    Kind.HOLD: Rule(),
    Kind.RECALL: Rule(settle=_channel_recall),
    Kind.MOVE: Rule(walk=_to_node, settle=_on_arrival(Outcome.ARRIVED)),
    Kind.LANE: Rule(walk=_to_post),
    # No camp exists until C4, so every camp is found empty.
    Kind.CAMP: Rule(walk=_to_node, settle=_on_arrival(Outcome.ABSENT)),
    Kind.FOLLOW: Rule(walk=_to_ally, pursues=True),
    Kind.FIGHT: Rule(enabled_by="C5 adds combat, and C6 the team view that a target must be in"),
    Kind.SIEGE: Rule(enabled_by="C5 adds combat against towers"),
    Kind.WARD: Rule(enabled_by="C6 adds wards"),
}
RULE = tuple(RULES[a.kind] for a in ACTIONS)
ENABLED = tuple(not rule.enabled_by for rule in RULE)
