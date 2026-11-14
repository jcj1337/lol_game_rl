"""Champions: seats, capability, the action table, and how an intent is carried out.

A seat is `team * 5 + role`, with team 0 blue and team 1 red. An action is an index into `ACTIONS`. Both teams
share the table, because its targets are named in the acting team's frame: `own_*` and `enemy_*` stand for the
map's `blue_*` and `red_*` nodes, and an ally or an enemy is named by its role.

A champion holds one intent, the index of the action it is carrying out. `RULES` says how each kind is carried
out: the world calls `walk` in the move step and `settle` after damage. The functions here take the world and
never import it.

The fountain's rules are here too: regeneration, the purchases of a profile's fixed progression, and Homeguard.
"""

from bisect import bisect_right
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import IntEnum
from functools import cache
from itertools import accumulate
from typing import TYPE_CHECKING, NamedTuple

from riftgame import ruleset
from riftgame.lanes import Front, Mode, stance
from riftgame.map import Pos, load_map

if TYPE_CHECKING:
    from riftgame.world import World

R = ruleset.load()
ADDED = ruleset.load("patch_26_22_m8")
MAP = load_map(ADDED["map"]["id"])
RIFT = MAP.rift

TEAMS = ("blue", "red")
ROLES = ("top", "jungle", "mid", "carry", "support")
LANES = ("top", "mid", "bot")
HOME = ("top", None, "mid", "bot", "bot")
MODES = ("passive", "last_hit", "thin", "push")
STANDS = ("wave", "hold")
SEATS = range(10)

FOUNTAIN = tuple(RIFT.at(f"{team}_fountain") for team in TEAMS)
OUTER_TOWER = tuple({t.lane: RIFT.lane_pos(t.lane, t.s) for t in MAP.towers if t.team == team and t.tier == "outer"}
                    for team in TEAMS)
RECALL_S = R["recall"]["cast_s"] + R["recall"]["channel_s"]
WARD = R["vision"]
WARD_START = ADDED["vision"]["ward_start_charges"]
FOUNTAIN_REGEN = R["fountain"]
HOMEGUARD = R["homeguard"]
NO_HOMEGUARD = -1
IN_RANGE = 1e-6
# Per team and lane, the lane coordinate where Homeguard ends, on the base side of the outer tower's site.
HOMEGUARD_END = tuple({t.lane: t.s + (2 * i - 1) * HOMEGUARD["ends_before_outer_tower"]
                       for t in MAP.towers if t.team == team and t.tier == "outer"} for i, team in enumerate(TEAMS))


class Capability(NamedTuple):
    max_hp: float
    hp_regen: float
    max_mana: float
    move_speed: float
    hit_damage: float
    attack_speed: float
    attack_range: float
    area_dps: float
    camp_dps: float
    champion_dps: float
    lockdown_slow: float
    lockdown_s: float
    lockdown_cooldown_s: float
    lockdown_mana: float
    mana_regen: float
    area_mana_s: float


# Assumed until M9. The numbers come from the M7 prototype, except hp_regen, max_mana, lockdown_mana, mana_regen, and
# area_mana_s, which are new guesses, and camp_dps, which is set so that the jungler alone clears its six camps in
# about 75 s of fighting. After the camp rate come the damage per second against champions and the lockdown: the
# share of move speed it removes, with 1.0 a stop, its duration, its cooldown, and its mana cost. The carry has no
# lockdown. The area damage of the `push` mode is an ability too. It costs `area_mana_s` mana for each second in
# which it hits a minion, so that a full bar, with `mana_regen` per second, pays for pushing five or six waves.
PROFILES = {
    "top":     Capability(650.0, 1.7, 300.0, 340.0, 65.0, 0.65, 175.0, 20.0, 95.0, 55.0, 0.30, 2.0, 10.0, 50.0, 1.0, 8.0),
    "jungle":  Capability(600.0, 1.6, 320.0, 345.0, 62.0, 0.68, 175.0, 25.0, 190.0, 60.0, 0.40, 2.0, 10.0, 50.0, 1.0, 8.0),
    "mid":     Capability(540.0, 1.2, 420.0, 335.0, 55.0, 0.63, 525.0, 40.0, 110.0, 65.0, 0.25, 2.0, 12.0, 60.0, 1.5, 12.0),
    "carry":   Capability(520.0, 0.8, 330.0, 325.0, 60.0, 0.70, 550.0, 10.0, 100.0, 70.0, 0.00, 0.0, 0.0, 0.0, 1.1, 6.0),
    "support": Capability(560.0, 1.1, 380.0, 335.0, 50.0, 0.60, 500.0, 5.0, 55.0, 35.0, 0.45, 2.5, 12.0, 60.0, 1.4, 6.0),
}
LEVEL_GROWTH = 0.08
LEVEL_SCALED = frozenset(("max_hp", "hp_regen", "max_mana", "hit_damage", "area_dps", "camp_dps", "champion_dps", "mana_regen"))


class Upgrade(NamedTuple):
    """One entry of a progression: its price, and the amount it adds to each capability field it names."""

    cost: float
    adds: dict[str, float]


def _progression(profile: str) -> tuple[Upgrade, ...]:
    """Two boot steps on the reference prices and speeds, then the profile's placeholder entries."""
    boots, listed = R["champions"], ADDED["upgrades"]
    tier1 = Upgrade(boots["boots_tier1_gold"], {"move_speed": boots["boots_tier1_speed"]})
    tier2 = Upgrade(listed["boots_tier2_gold"] - tier1.cost,
                    {"move_speed": boots["boots_tier2_speed"] - boots["boots_tier1_speed"]})
    return (tier1, tier2, *(Upgrade(entry["cost"], entry["adds"]) for entry in listed[profile]))


# What each profile buys, in order. Assumed until M9, except the boots.
PROGRESSIONS = {profile: _progression(profile) for profile in PROFILES}


@cache
def capability(profile: str, level: int, upgrades: int) -> Capability:
    """What a champion can do at a level with the first `upgrades` entries of its profile's progression.

    Level growth scales the profile, and each upgrade adds its amounts on top. Unspent gold is no input.
    """
    growth = 1.0 + LEVEL_GROWTH * (level - 1)
    base = PROFILES[profile]
    can = {name: value * growth if name in LEVEL_SCALED else value for name, value in zip(base._fields, base)}
    for upgrade in PROGRESSIONS[profile][:upgrades]:
        for name, amount in upgrade.adds.items():
            can[name] += amount
    return Capability(**can)


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
    CAMP = 4
    KILL = 5
    ASSIST = 6
    PLATE = 7
    TOWER = 8


class Target(IntEnum):
    """What a champion's one attack goes to on a tick (M7 section 7.4). Its intent alone decides the class."""

    NONE = 0
    MINIONS = 1
    CHAMPION = 2
    CAMP = 3
    TOWER = 4


class Action(NamedTuple):
    """`target` is a frame node name for MOVE, CAMP and WARD, a lane for SIEGE, and a role index for FOLLOW and FIGHT.

    For LANE it is (lane, mode, stand). The mode says what the champion hits. The stand says where it stands:
    `wave` walks with the wave, and `hold` stays on the hold line in front of its own tower. The two are separate,
    so a champion can hold a wave and thin it at once."""

    kind: Kind
    target: str | int | tuple[str, str, str] | None = None


def frame_name(team: int, node: str) -> str:
    """A map node's name in a team's frame."""
    side, _, rest = node.partition("_")
    if side not in TEAMS:
        return node
    return ("own_" if side == TEAMS[team] else "enemy_") + rest


# A lane waypoint shapes a lane and is no destination, so no `MOVE` names it.
NODES = tuple(frame_name(0, node) for node in RIFT.node_names if node not in ADDED["map"]["lane_waypoints"])
CAMP_NODES = tuple(frame_name(0, node) for node in (*MAP.camps, *MAP.scuttlers.values()))

def _edge_middle(a: str, b: str) -> Pos:
    ends = {RIFT.node_names.index(a), RIFT.node_names.index(b)}
    edge = next(i for i, e in enumerate(RIFT.edges) if {e.a, e.b} == ends)
    return Pos(edge, RIFT.edges[edge].length / 2)


# A ward spot is a camp, a Scuttler's river node, or the middle of a river edge between a Scuttler node and a lane
# (Assumed: the places a jungler passes). The river spots are named `a>b` by the edge's ends and need no frame.
RIVER_WARDS = {f"{a}>{b}": _edge_middle(a, b) for a, b in ADDED["vision"]["river_ward_spots"]}
WARD_SPOTS = (*CAMP_NODES, *RIVER_WARDS)
ACTIONS = (
    Action(Kind.KEEP), Action(Kind.HOLD), Action(Kind.RECALL),
    *(Action(Kind.MOVE, node) for node in NODES),
    *(Action(Kind.LANE, (lane, mode, stand)) for lane in LANES for stand in STANDS for mode in MODES),
    *(Action(Kind.CAMP, node) for node in CAMP_NODES),
    *(Action(Kind.FOLLOW, role) for role in range(len(ROLES))),
    *(Action(Kind.FIGHT, role) for role in range(len(ROLES))),
    *(Action(Kind.SIEGE, lane) for lane in LANES),
    *(Action(Kind.WARD, spot) for spot in WARD_SPOTS),
)
KEEP, HOLD, RECALL = 0, 1, 2

# Per action: the lane, the wave mode, and whether the champion holds. None for every other kind.
LANE_ORDER = tuple((a.target[0], Mode(MODES.index(a.target[1])), a.target[2] == "hold") if a.kind is Kind.LANE else None
                   for a in ACTIONS)

NODE_POS = tuple({**{frame_name(team, node): RIFT.at(node) for node in RIFT.node_names}, **RIVER_WARDS} for team in range(2))
DEST = tuple(tuple(NODE_POS[team][a.target] if a.kind in (Kind.MOVE, Kind.CAMP, Kind.WARD) else None for a in ACTIONS)
             for team in range(2))
WARDS = tuple(i for i, a in enumerate(ACTIONS) if a.kind is Kind.WARD)
# The world keeps its camps in the order of `CAMP_SITES`, which are map nodes. By team and action: the index of the
# camp that a `CAMP` action names, and -1 for every other action.
CAMP_SITES = (*MAP.camps, *MAP.scuttlers.values())
CAMP_OF = tuple(tuple([frame_name(team, node) for node in CAMP_SITES].index(a.target) if a.kind is Kind.CAMP else -1
                      for a in ACTIONS) for team in range(2))
# Per action: the role of the enemy that a `FIGHT` action names, and the lane that a `SIEGE` action names.
FOE = tuple(a.target if a.kind is Kind.FIGHT else -1 for a in ACTIONS)
SIEGE_LANE = tuple(a.target if a.kind is Kind.SIEGE else None for a in ACTIONS)
NEVER = -1_000_000_000


@dataclass(slots=True)
class Champion:
    """One champion's mutable state. Team, role, profile and home lane follow from the seat, level from XP,
    liveness from health, and the gold it has spent from its upgrades.

    `homeguard_tick` is the tick of its last move that began on its fountain with Homeguard, or `NO_HOMEGUARD`.
    `homeguard_block` is the first tick on which it may have Homeguard again after combat.

    `attack_credit` is the share of an attack that is ready, at most 1.0. It is the one budget for every target
    class (`attack_worth`). `hurt_tick` holds, by enemy role, the last tick on which that enemy damaged this champion, or `NEVER`, a
    tick long before the game. Every window that reads it is shorter than the shortest death. A lockdown removes the share `slow` of its move speed on every tick before
    `slow_until`. Its own lockdown is ready again from `lockdown_tick` on.

    `ward_charges` are the Stealth Wards it can place. `ward_tick` is the tick on which it gets the next one, or -1
    while it holds them all.

    `respawned_tick` is the tick of its latest respawn, or -1 before the first, and `respawned_level` its level then.
    Kills and respawns are public (M7 section 6.3), and nothing in the kernel reads either field."""

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
    respawned_tick: int
    respawned_level: int
    homeguard_tick: int
    homeguard_block: int
    hurt_tick: list[int]
    slow: float
    slow_until: int
    lockdown_tick: int
    ward_charges: int
    ward_tick: int

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


def spent(c: Champion) -> float:
    """The gold a champion has paid for the upgrades it owns."""
    return sum(upgrade.cost for upgrade in PROGRESSIONS[ROLES[c.seat % 5]][:c.upgrades])


def shop(c: Champion) -> None:
    """Buy the next upgrades of the champion's progression, in order, while its unspent gold covers them."""
    progression = PROGRESSIONS[ROLES[c.seat % 5]]
    while c.upgrades < len(progression) and c.gold >= progression[c.upgrades].cost:
        c.gold -= progression[c.upgrades].cost
        c.upgrades += 1


def spawn(seat: int, allowance: float, ward_tick: int) -> Champion:
    """A champion at the start of a game: on its fountain, at full health, holding, its starting gold spent on
    what its progression offers for it."""
    full = capability(ROLES[seat % 5], 1, 0)
    c = Champion(seat=seat, pos=FOUNTAIN[seat // 5], hp=full.max_hp, mana=full.max_mana, xp=0.0, gold=0.0,
                 earned=[0.0] * len(Income), upgrades=0, intent=HOLD, intent_tick=0, channel=0, outcome=Outcome.NONE,
                 outcome_tick=-1, allowance=allowance, attack_credit=0.0, item_charges=0, respawn_tick=-1,
                 respawned_tick=-1, respawned_level=0, homeguard_tick=NO_HOMEGUARD, homeguard_block=0, hurt_tick=[NEVER] * len(ROLES),
                 slow=0.0, slow_until=0, lockdown_tick=0, ward_charges=WARD_START, ward_tick=ward_tick if WARD_START < WARD["ward_charges"] else -1)
    pay(c, Income.STARTING, _E["starting_gold"])
    shop(c)
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


def in_homeguard_zone(team: int, pos: Pos) -> bool:
    """True on the way from a team's fountain into a lane, up to the lane's Homeguard endpoint.

    The way is the edge between fountain and base and the lanes themselves. A jungle or river edge is off it.
    """
    if pos.edge == FOUNTAIN[team].edge:
        return True
    for lane, end in HOMEGUARD_END[team].items():
        s = RIFT.lane_s(lane, pos)
        if s is not None:
            return s < end if team == 0 else s > end
    return False


def homeguard_bonus(world: "World", c: Champion) -> float:
    """The share of its move speed that Homeguard adds to a champion's move on this tick. 0.0 without Homeguard.

    The bonus falls in a straight line from its full value to its decayed value. The line is an assumption. The
    reference gives the two values and the time between them, and no shape.
    """
    if c.homeguard_tick == NO_HOMEGUARD:
        return 0.0
    # The move that begins on the fountain keeps the full bonus. After it the bonus is read at the middle of the
    # tick, which on a straight line is its mean over the tick, so the distance walked is exact.
    off_fountain_s = (world.tick - c.homeguard_tick - 0.5) * world.config.tick_s
    decayed = min(1.0, max(0.0, off_fountain_s) / HOMEGUARD["decay_s"])
    return HOMEGUARD["speed_bonus"] - (HOMEGUARD["speed_bonus"] - HOMEGUARD["speed_bonus_after_decay"]) * decayed


def speed_of(world: "World", c: Champion) -> float:
    """The speed a champion moves at on this tick: Homeguard adds to it and a lockdown takes from it."""
    slowed = 1.0 - c.slow if world.tick < c.slow_until else 1.0
    return capability_of(c).move_speed * (1.0 + homeguard_bonus(world, c)) * slowed


def enter_combat(world: "World", c: Champion) -> None:
    """Combat takes Homeguard away and blocks it for a while. Taking damage is combat, and so is dealing damage to
    a champion."""
    c.homeguard_tick = NO_HOMEGUARD
    c.homeguard_block = world.tick + world.config.ticks(HOMEGUARD["blocked_after_combat_s"])


def settle_fountain(world: "World", c: Champion) -> None:
    """The fountain's part of the tick's last step.

    On its fountain a living champion regenerates and gets Homeguard for its next move, and any champion shops,
    the dead included. Off it, Homeguard ends once the champion is outside the Homeguard zone, and walking back
    into the zone does not return it.
    """
    if not on_fountain(c):
        if c.homeguard_tick != NO_HOMEGUARD and not in_homeguard_zone(c.seat // 5, c.pos):
            c.homeguard_tick = NO_HOMEGUARD
        return
    if c.hp > 0:
        can, config = capability_of(c), world.config
        c.hp = min(can.max_hp, c.hp + FOUNTAIN_REGEN["hp_regen_per_s"] * can.max_hp * config.tick_s)
        c.mana = min(can.max_mana, c.mana + FOUNTAIN_REGEN["mana_regen_per_s"] * can.max_mana * config.tick_s)
        next_move = world.tick + 1
        if next_move >= max(config.ticks(HOMEGUARD["start_s"]), c.homeguard_block):
            c.homeguard_tick = next_move
    shop(c)


def known_front(world: "World", team: int, lane: str) -> Front:
    """A lane's front as a team knows it: its own lead minion, and the enemy lead minion if it sees one now
    (M7 section 6.3). Everything that places a champion at a wave reads this and never the lane's true front."""
    wave = world.memory[team].waves[LANES.index(lane)]
    return world.lanes[lane].known_front(team, wave.lead if wave.seen_tick == world.tick else None)


def lane_post(world: "World", seat: int, lane: str) -> Pos:
    """Where a champion with a `LANE` intent for `lane` walks to: the stance of its wave mode and its stand,
    at the front that its team knows."""
    c = world.champions[seat]
    _, mode, hold = LANE_ORDER[c.intent]
    s, _ = stance(world.lanes[lane], seat // 5, mode, capability_of(c).attack_range, known_front(world, seat // 5, lane), hold=hold)
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

    `walk` gives the position the champion heads for in the move step, or None to stand. Every walk is read from
    the state at the start of the step, before anyone moves, so no walk depends on another champion's move on the
    same tick. `settle` runs after damage: it advances the intent and returns its outcome once it is over.
    `attacks` is the one class of target that the champion's attack goes to under this intent.
    """

    walk: Callable[["World", Champion], Pos | None] | None = None
    settle: Callable[["World", Champion], Outcome] | None = None
    attacks: Target = Target.NONE


def _to_node(world: "World", c: Champion) -> Pos:
    return DEST[c.seat // 5][c.intent]


def _to_post(world: "World", c: Champion) -> Pos:
    return lane_post(world, c.seat, ACTIONS[c.intent].target[0])


def _to_ally(world: "World", c: Champion) -> Pos | None:
    ally = world.champions[c.seat // 5 * 5 + ACTIONS[c.intent].target]
    return ally.pos if ally.hp > 0 else None


def _within(pos: Pos, target: Pos, reach: float) -> Pos | None:
    """Where to walk from `pos` to bring `target` within `reach`: the place on the route that is `reach` short of
    the target. None once the target is in reach by the straight line."""
    if RIFT.separation(pos, target) <= reach + IN_RANGE:
        return None
    return RIFT.advance(target, pos, reach)


def _to_enemy(world: "World", c: Champion) -> Pos | None:
    """A fighter heads for its target by its team's record of it alone (M7 section 7.1). It never reads where the
    target is now or what it intends.

    The fighter closes to its attack range of the place where its team sees the target, or with the record out of
    date of the last-seen place. While the target's last step, as the team saw it, took it away from the fighter,
    the fighter heads instead for the place `_lead_short` short of where one more such step puts the target. Where
    that step would carry the target past the end of its lane, or off the lanes past the end of its edge, the
    fighter heads no further than that node, because the target may go on along any edge from it.
    """
    record = world.memory[c.seat // 5].enemies[FOE[c.intent]]
    reach = capability_of(c).attack_range
    if record.seen_tick == world.tick and record.was is not None and RIFT.distance(c.pos, record.pos) > RIFT.distance(c.pos, record.was):
        step = RIFT.distance(record.was, record.pos)
        ahead, cut = _one_more_step(record.was, record.pos, step)
        return _within(c.pos, ahead, max(0.0, _lead_short(reach, step) - cut))
    return _within(c.pos, record.pos, reach)


def _lead_short(reach: float, step: float) -> float:
    """How far short of the led place a fighter with attack range `reach` heads, against a target seen to step
    `step` away from it.

    Let the fighter end x past the target's seen place, along the target's way. A target whose next step is a then
    stays in range when x - reach <= a <= x + reach. With x = 2 step - reach, a target that stops, turns back by
    its step, or steps up to twice as far, as one does when a slow ends, stays in range. The turn stays only while
    the step is at most 2/3 of the range. Above that, x = reach - step keeps the turn, the stop, and one more step.
    Above the range no x keeps both the turn and one more step, and x = step - reach keeps the step and the stop.
    The fighter heads step - x short of the led place.
    """
    return min(reach, max(reach - step, 2 * step - reach))


def _one_more_step(was: Pos, pos: Pos, step: float) -> tuple[Pos, float]:
    """Where a champion that stepped `step` from `was` to `pos` stands after one more such step, and how much of
    that step the way cut off. On a lane by the lane coordinate, up to the lane's end. Off the lanes along its
    edge, away from the node it came by, up to the edge's end."""
    for name, lane in RIFT.lanes.items():
        s0, s1 = RIFT.lane_s(name, was), RIFT.lane_s(name, pos)
        if s0 is not None and s1 is not None:
            s = 2 * s1 - s0
            return RIFT.lane_pos(name, s), max(0.0, -s, s - lane.length)
    edge = RIFT.edges[pos.edge]
    if was.edge == pos.edge:
        toward_b = pos.offset > was.offset
    else:
        toward_b = edge.a in (RIFT.edges[was.edge].a, RIFT.edges[was.edge].b)
    ahead = min(step, edge.length - pos.offset if toward_b else pos.offset)
    return Pos(pos.edge, pos.offset + (ahead if toward_b else -ahead)), step - ahead


def _to_ward_spot(world: "World", c: Champion) -> Pos | None:
    return _within(c.pos, DEST[c.seat // 5][c.intent], WARD["ward_place_range"])


def _to_tower(world: "World", c: Champion) -> Pos | None:
    lane = SIEGE_LANE[c.intent]
    tower = world.lanes[lane].front_tower(1 - c.seat // 5)
    return None if tower is None else _within(c.pos, RIFT.lane_pos(lane, tower.s), capability_of(c).attack_range)


def _on_arrival(outcome: Outcome) -> Callable[["World", Champion], Outcome]:
    def settle(world: "World", c: Champion) -> Outcome:
        return outcome if c.pos == DEST[c.seat // 5][c.intent] else Outcome.NONE
    return settle


def _find_empty(world: "World", c: Champion) -> Outcome:
    """A camp that is not alive when the champion stands at it was found empty. A camp that dies under the champion
    ends the intent with `CLEARED` in the damage step, before this runs."""
    team = c.seat // 5
    empty = c.pos == DEST[team][c.intent] and world.camps[CAMP_OF[team][c.intent]].hp <= 0
    return Outcome.ABSENT if empty else Outcome.NONE


def _channel_recall(world: "World", c: Champion) -> Outcome:
    c.channel += 1
    if c.channel < world.config.ticks(RECALL_S) and not on_fountain(c):
        return Outcome.NONE
    c.pos = FOUNTAIN[c.seat // 5]
    return Outcome.RECALLED


def _lose_track(world: "World", c: Champion) -> Outcome:
    """A fight is lost once the champion has stood within its attack range of the target's last-seen place for a
    whole tick and its team still does not see the target. The view that it gives up on was then taken from that
    place. `channel` counts those ticks. A target seen again on the way resets the count and records nothing.
    """
    record = world.memory[c.seat // 5].enemies[FOE[c.intent]]
    if record.seen_tick == world.tick or RIFT.separation(c.pos, record.pos) > capability_of(c).attack_range + IN_RANGE:
        c.channel = 0
        return Outcome.NONE
    c.channel += 1
    return Outcome.LOST if c.channel > 1 else Outcome.NONE


def _by_average_level(world: "World", ends: Sequence[float]) -> float:
    """A value that the reference gives at average champion level 1 and at the level cap. The straight line
    between the two is Assumed."""
    average = sum(level_of(c.xp) for c in world.champions) / len(world.champions)
    return ends[0] + (ends[1] - ends[0]) * (average - 1) / (_E["level_cap"] - 1)


def _place_ward(world: "World", c: Champion) -> Outcome:
    """A champion within placement range of its ward spot places a Stealth Ward there and spends a charge. The
    ward gives its team sight for a time that grows with the average champion level. With no charge the champion
    waits in range for one."""
    spot = DEST[c.seat // 5][c.intent]
    if c.ward_charges <= 0 or RIFT.separation(c.pos, spot) > WARD["ward_place_range"] + IN_RANGE:
        return Outcome.NONE
    c.ward_charges -= 1
    if c.ward_tick < 0:
        c.ward_tick = world.tick + world.config.ticks(_by_average_level(world, WARD["ward_recharge_s"]))
    world.ward(c.seat, spot, WARD["ward_sight_range"], _by_average_level(world, WARD["ward_duration_s"]), WARD["ward_max_placed"])
    return Outcome.PLACED


def recharge_ward(world: "World", c: Champion) -> None:
    """A champion short of a ward charge gets one when its recharge time has run, and then starts the next. The
    recharge shortens with the average champion level."""
    if 0 <= c.ward_tick <= world.tick:
        c.ward_charges += 1
        full = c.ward_charges >= WARD["ward_charges"]
        c.ward_tick = -1 if full else world.tick + world.config.ticks(_by_average_level(world, WARD["ward_recharge_s"]))


def _find_no_tower(world: "World", c: Champion) -> Outcome:
    """A siege of a lane with no enemy tower left to damage was a walk for nothing. The fall of the lane's last
    tower under a siege ends it with `CLEARED` in the damage step, before this runs."""
    standing = world.lanes[SIEGE_LANE[c.intent]].front_tower(1 - c.seat // 5)
    return Outcome.ABSENT if standing is None else Outcome.NONE


RULES = {
    Kind.KEEP: Rule(),
    Kind.HOLD: Rule(attacks=Target.CHAMPION),
    Kind.RECALL: Rule(settle=_channel_recall),
    Kind.MOVE: Rule(walk=_to_node, settle=_on_arrival(Outcome.ARRIVED)),
    Kind.LANE: Rule(walk=_to_post, attacks=Target.MINIONS),
    Kind.CAMP: Rule(walk=_to_node, settle=_find_empty, attacks=Target.CAMP),
    Kind.FOLLOW: Rule(walk=_to_ally, attacks=Target.CHAMPION),
    Kind.FIGHT: Rule(walk=_to_enemy, settle=_lose_track, attacks=Target.CHAMPION),
    Kind.SIEGE: Rule(walk=_to_tower, settle=_find_no_tower, attacks=Target.TOWER),
    Kind.WARD: Rule(walk=_to_ward_spot, settle=_place_ward),
}
RULE = tuple(RULES[a.kind] for a in ACTIONS)


def attack_worth(world: "World", c: Champion, rate: float) -> float:
    """What a champion's attack deals on this tick to a target that takes damage as a rate: a champion or a camp.

    The attack credit is one budget for every class of target (M7 section 7.4). A whole attack is one hit on a
    minion or a tower, and `rate / attack_speed` on a champion or a camp, which is the rate's damage over one
    attack period. On a tick against such a target the champion spends all the credit it has: what it brought
    into the tick and what the tick earns. So a ready attack lands at once on any class, as it does on a minion,
    and a champion that has just spent its attack elsewhere deals only what it has earned since.
    """
    speed = capability_of(c).attack_speed
    return rate / speed * (c.attack_credit + speed * world.config.tick_s)


def attacks(c: Champion) -> Target:
    """The class of target that a champion's attack goes to on this tick. This is the one place that decides it:
    minions for `LANE`, a camp for `CAMP`, a tower for `SIEGE`, the named enemy for `FIGHT`, and for `HOLD` and
    `FOLLOW` the enemy champion that is attacking it. A champion on any other intent, and a dead one, attacks
    nothing. Whether a target of that class is in reach is for the subsystem that owns the class to say."""
    return RULE[c.intent].attacks if c.hp > 0 else Target.NONE
