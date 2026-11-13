"""Scripted policies for all ten seats of an integrated game (M7 section 10.1, checkpoint C7).

`team_policies()` gives one policy per seat. Each is `act(observation, noise) -> action index`, like every policy
of `riftgame.harness`, and holds no state. It reads only its champion's observation and public facts: the map,
the profiles, the progressions, and the side it plays on, which a player knows. Knowing the side lets it turn a
place of its frame back into a map position exactly. Each role walks down a list of wants and takes the first
one that its mask allows.

- A laner last-hits with its wave, wards the river beside its lane, trades with its lane opponent when it is
  ahead in health and away from the enemy tower, backs off to its tower when another enemy shows up near it,
  recalls to heal and to buy, and late in the game pushes and sieges a lane whose opponent is dead.
- The support stays with its carry, spends its item's charges on the wave, wards the bot-side river, and joins
  the carry's fights.
- The jungler clears camps as `harness.jungler` does, wards a river spot near its path, ganks a hurt enemy laner
  that its team sees, and leaves when an enemy that it cannot fight shows up.

Every threshold here is Assumed. The policies exist to exercise every subsystem in one game, not to play well.
"""

from collections.abc import Callable

from riftgame.champions import (ACTIONS, HOLD, HOME, KEEP, LANES, MAP, NODE_POS, PROGRESSIONS, RECALL, RIFT, ROLES, TEAMS, Action, Kind,
                                capability)
from riftgame.harness import Policy, jungler
from riftgame.lanes import TOWER_RANGE
from riftgame.map import Pos
from riftgame.vision import _FRAME_EDGES, Observation, Place, legal_mask

JUNGLE, CARRY, SUPPORT = ROLES.index("jungle"), ROLES.index("carry"), ROLES.index("support")

# Shares of maximum health and distances in map units, all Assumed.
RETREAT_BELOW = 0.30      # walk to safety, or recall when nobody is near
DISENGAGE_BELOW = 0.40    # leave a fight
HEALED = 0.90             # leave the fountain
TRADE_ABOVE = 0.60        # fight the lane opponent when this healthy and at least as healthy as it
TRADE_REACH = 300.0       # and when it stands within this much beyond the attack range
DANGER_RADIUS = 1800.0    # an enemy other than the lane opponents this near sends a laner back to its tower
SAFE_TO_RECALL = 1400.0   # recall only with no enemy seen this near
GANK_RADIUS = 3500.0      # a jungler ganks a hurt laner within this walk
GANK_BELOW = 0.60         # a laner below this share of its health is hurt
GANK_ABOVE = 0.70         # a jungler above this share is healthy enough to gank
TOWER_MARGIN = 250.0      # nobody picks a fight with a target this near the enemy tower's range
AT_TOWER = 300.0          # a champion this near its own tower stands at it
WARD_AFTER_S = 75.0
WARD_COVER = 1200.0       # an own ward this near a spot already watches it
WARD_DETOUR = 2500.0      # a jungler wards only a spot this near
PUSH_AFTER_S = 600.0
SIEGE_REACH = 700.0       # own lead minion this near the enemy front tower lets a pusher siege
GONE_S = 20.0             # a lane opponent unseen this long is away from the lane

RIVER_SPOT = {"top": ("top_river>top_corner",), "mid": ("top_river>mid_river", "bot_river>mid_river"), "bot": ("bot_river>bot_corner",)}
SUPPORT_SPOTS = ("bot_river>bot_corner", "bot_river>mid_river")
JUNGLE_SPOTS = ("top_river>mid_river", "bot_river>mid_river", "top_river>top_corner", "bot_river>bot_corner")


def _index(kind: Kind, target=None) -> int:
    return ACTIONS.index(Action(kind, target))


LANE = {lane: {(mode, stand): _index(Kind.LANE, (lane, mode, stand)) for mode in ("passive", "last_hit", "thin", "push")
               for stand in ("wave", "hold")} for lane in LANES}
FIGHT = tuple(_index(Kind.FIGHT, role) for role in range(5))
SIEGE = {lane: _index(Kind.SIEGE, lane) for lane in LANES}
WARD_AT = {a.target: i for i, a in enumerate(ACTIONS) if a.kind is Kind.WARD}
TO_FOUNTAIN = _index(Kind.MOVE, "own_fountain")
TO_BASE = _index(Kind.MOVE, "own_base")
TO_TOWER = {lane: tuple(_index(Kind.MOVE, f"own_{lane}_t{tier}") for tier in (1, 2)) for lane in LANES}
FOUNTAIN_PLACE = Place("own_fountain>own_base", 0.0)


def _routes(team: int) -> dict[str, tuple[int, float, float]]:
    """Per route of a team's frame off the lanes: its one map edge, the start, and the sign of `vision.to_frame`."""
    return {route: (edge, start, sign) for edge, (route, start, sign) in enumerate(_FRAME_EDGES[team]) if route not in RIFT.lanes}


class Side:
    """What a policy knows from the side it plays on: how its frame maps onto the map, and where the towers of
    each lane stand in its frame, its own from the outer one inward and the enemy's likewise."""

    def __init__(self, team: int):
        self.team = team
        self.routes = _routes(team)
        self.cache: dict[Place, Pos] = {}

        def framed(s: float, lane: str) -> float:
            return s if team == 0 else RIFT.lanes[lane].length - s

        def towers(of: int, lane: str) -> list[float]:
            sites = sorted((t for t in MAP.towers if t.lane == lane and t.team == TEAMS[of]), key=lambda t: ("outer", "inner", "inhibitor").index(t.tier))
            return [framed(t.s, lane) for t in sites]

        self.own_towers = {lane: towers(team, lane) for lane in LANES}
        self.enemy_towers = {lane: towers(1 - team, lane) for lane in LANES}

    def pos(self, place: Place) -> Pos:
        pos = self.cache.get(place)
        if pos is None:
            if place.route in RIFT.lanes:
                s = place.s if self.team == 0 else RIFT.lanes[place.route].length - place.s
                pos = RIFT.lane_pos(place.route, s)
            else:
                edge, start, sign = self.routes[place.route]
                pos = Pos(edge, (place.s - start) * sign)
            self.cache[place] = pos
        return pos

    def apart(self, a: Place, b: Place) -> float:
        return RIFT.separation(self.pos(a), self.pos(b))

    def walk(self, a: Place, b: Place) -> float:
        return RIFT.distance(self.pos(a), self.pos(b))


def _share(o: Observation) -> float:
    return o.me.hp / o.me.max_hp


def _foe_share(o: Observation, role: int) -> float:
    enemy = o.enemies[role]
    return enemy.hp / capability(ROLES[role], enemy.level, enemy.upgrades).max_hp


def _kind(o: Observation) -> Kind:
    return ACTIONS[o.me.intent].kind


def _pick(o: Observation, *wants: int | None) -> int:
    """The first want that the mask allows. KEEP when none does and keeping is legal, else HOLD."""
    mask = legal_mask(o)
    for want in wants:
        if want is not None and mask[want]:
            return want
    return KEEP if mask[KEEP] else HOLD


def _near(side: Side, o: Observation, radius: float, but: tuple[int, ...] = ()) -> list[int]:
    """Roles of the enemies that the team sees now within `radius` of this champion, by the straight line."""
    return [role for role, enemy in enumerate(o.enemies) if enemy is not None and role not in but and side.apart(o.me.place, enemy.place) <= radius]


def _front_tower(side: Side, o: Observation, lane: str) -> float | None:
    """Where the enemy's front tower of a lane stands in the frame, by what the team knows of tower health."""
    for s, hp in zip(side.enemy_towers[lane], o.lanes[LANES.index(lane)].enemy_towers):
        if hp > 0:
            return s
    return None


def _by_tower(side: Side, o: Observation, place: Place) -> bool:
    """Whether a place on a lane is near the range of that lane's enemy front tower."""
    if place.route not in RIFT.lanes:
        return False
    tower = _front_tower(side, o, place.route)
    return tower is not None and abs(place.s - tower) <= TOWER_RANGE + TOWER_MARGIN


def _to_safety(side: Side, o: Observation, lane: str | None) -> int:
    """The walk to the own front tower of the lane, or to the fountain without a lane. A walk under way goes on,
    and a champion that already stands at the tower holds there."""
    if lane is None:
        walk = TO_FOUNTAIN
    else:
        standing = [hp > 0 for hp in o.lanes[LANES.index(lane)].own_towers]
        tier = 0 if standing[0] else 1 if standing[1] else None
        walk = TO_BASE if tier is None else TO_TOWER[lane][tier]
        if tier is not None and o.me.place.route == lane and abs(o.me.place.s - side.own_towers[lane][tier]) <= AT_TOWER:
            return HOLD
    return KEEP if o.me.intent == walk else walk


def _survive(side: Side, o: Observation, lane: str | None) -> int | None:
    """Heal on the fountain, finish a recall, and get out when hurt: recall with nobody near, else walk to safety
    first."""
    if o.me.place == FOUNTAIN_PLACE and _share(o) < HEALED:
        return HOLD
    if _kind(o) is Kind.RECALL:
        return KEEP
    if _share(o) < RETREAT_BELOW:
        return RECALL if not _near(side, o, SAFE_TO_RECALL) else _to_safety(side, o, lane)
    return None


def _shop(side: Side, o: Observation) -> int | None:
    """Recall to buy once the next upgrade is affordable and no enemy is near."""
    me = o.me
    progression = PROGRESSIONS[ROLES[me.role]]
    if me.upgrades < len(progression) and me.gold >= progression[me.upgrades].cost and not _near(side, o, SAFE_TO_RECALL):
        return RECALL
    return None


def _fight_on(o: Observation) -> int | None:
    """Keep a running fight while healthy. A hurt fighter falls through to its other wants."""
    return KEEP if _kind(o) is Kind.FIGHT and _share(o) >= DISENGAGE_BELOW else None


def _defend(o: Observation) -> int | None:
    """Hit back at the weakest enemy in view that hurt this champion a moment ago, while healthy."""
    if _share(o) < DISENGAGE_BELOW:
        return None
    hurt = [role for role, hit in enumerate(o.me.hurt_by) if hit and o.enemies[role] is not None]
    return FIGHT[min(hurt, key=lambda role: (_foe_share(o, role), role))] if hurt else None


def _trade(side: Side, o: Observation, foe: int) -> int | None:
    """Fight the lane opponent when it stands near and away from its tower, and this champion is healthy and
    at least as healthy as it."""
    enemy = o.enemies[foe]
    if enemy is None or _share(o) < TRADE_ABOVE or _foe_share(o, foe) > _share(o):
        return None
    reach = capability(ROLES[o.me.role], o.me.level, o.me.upgrades).attack_range + TRADE_REACH
    if side.apart(o.me.place, enemy.place) > reach or _by_tower(side, o, enemy.place):
        return None
    return FIGHT[foe]


def _ward(side: Side, o: Observation, spots: tuple[str, ...], detour: float | None = None) -> int | None:
    """A ward on the first spot that no own ward watches, once the champion holds a charge."""
    if o.me.ward_charges <= 0 or o.time_s < WARD_AFTER_S:
        return None
    for spot in spots:
        at = NODE_POS[side.team][spot]
        if detour is not None and RIFT.distance(side.pos(o.me.place), at) > detour:
            continue
        if all(RIFT.separation(at, side.pos(ward.place)) > WARD_COVER for ward in o.wards):
            return WARD_AT[spot]
    return None


def _siege(side: Side, o: Observation, lane: str, foe: int) -> int | None:
    """Late, with the lane opponent dead or long out of view, push the wave, and hit the tower once the own wave
    is at it."""
    last = o.remembered[foe]
    gone = o.rivals[foe].dead_s > 0.0 or last is None or last.age_s >= GONE_S
    if o.time_s < PUSH_AFTER_S or not gone:
        return None
    view = o.lanes[LANES.index(lane)]
    tower = _front_tower(side, o, lane)
    if tower is not None and view.own_lead is not None and abs(view.own_lead - tower) <= SIEGE_REACH and not view.contact:
        return SIEGE[lane]
    return LANE[lane]["push", "wave"]


def _going(o: Observation, kind: Kind) -> int | None:
    """Keep a walk of this kind that is under way."""
    return KEEP if _kind(o) is kind else None


def laner(side: Side, o: Observation) -> int:
    me = o.me
    if me.hp <= 0:
        return KEEP
    lane = me.home or HOME[me.role]
    foe = me.role
    farm = LANE[lane]["last_hit", "wave"]
    survive = _survive(side, o, lane)
    if survive is not None:
        return _pick(o, survive, farm)
    if _near(side, o, DANGER_RADIUS, but=(foe,)) and _kind(o) is not Kind.FIGHT:
        return _pick(o, _defend(o), _to_safety(side, o, lane))
    return _pick(o, _fight_on(o), _defend(o), _going(o, Kind.WARD), _shop(side, o), _trade(side, o, foe),
                 _ward(side, o, RIVER_SPOT[lane]), _siege(side, o, lane, foe), farm)


def support(side: Side, o: Observation) -> int:
    me = o.me
    if me.hp <= 0:
        return KEEP
    wave = LANE["bot"]["last_hit" if me.item_charges > 0 else "passive", "wave"]
    survive = _survive(side, o, "bot")
    if survive is not None:
        return _pick(o, survive, wave)
    carry = next(mate for mate in o.mates if mate.role == CARRY)
    target = ACTIONS[carry.intent].target if ACTIONS[carry.intent].kind is Kind.FIGHT else None
    joins = FIGHT[target] if target is not None and o.enemies[target] is not None else None
    if joins is None and _near(side, o, DANGER_RADIUS, but=(CARRY, SUPPORT)) and _kind(o) is not Kind.FIGHT:
        return _pick(o, _defend(o), _to_safety(side, o, "bot"))
    return _pick(o, _fight_on(o), joins, _defend(o), _going(o, Kind.WARD), _shop(side, o), _ward(side, o, SUPPORT_SPOTS), wave)


def _gank(side: Side, o: Observation) -> int | None:
    """Fight the most hurt enemy laner that the team sees within a walk, while this jungler is healthy."""
    if _share(o) < GANK_ABOVE:
        return None
    targets = [(_foe_share(o, role), role) for role, enemy in enumerate(o.enemies)
               if enemy is not None and role != JUNGLE and enemy.place.route in RIFT.lanes and _foe_share(o, role) < GANK_BELOW
               and side.walk(o.me.place, enemy.place) <= GANK_RADIUS and not _by_tower(side, o, enemy.place)]
    return FIGHT[min(targets)[1]] if targets else None


def jungle(side: Side, o: Observation, noise: float) -> int:
    me = o.me
    if me.hp <= 0:
        return KEEP
    survive = _survive(side, o, None)
    if survive is not None:
        return _pick(o, survive, TO_FOUNTAIN)
    threats = [role for role in _near(side, o, DANGER_RADIUS) if _foe_share(o, role) > _share(o)]
    if threats and _kind(o) is not Kind.FIGHT:
        return _pick(o, _defend(o), TO_FOUNTAIN)
    busy = _kind(o) in (Kind.CAMP, Kind.RECALL)
    return _pick(o, _fight_on(o), _defend(o), _gank(side, o), None if busy else _shop(side, o), _going(o, Kind.WARD),
                 None if busy else _ward(side, o, JUNGLE_SPOTS, WARD_DETOUR), jungler(o, noise))


def policy(team: int) -> Policy:
    """The scripted policy of one side: one rule per role."""
    side = Side(team)

    def act(o: Observation, noise: float) -> int:
        if o.me.role == JUNGLE:
            return jungle(side, o, noise)
        if o.me.role == SUPPORT:
            return support(side, o)
        return laner(side, o)

    return act


def team_policies(blue: Callable[[int], Policy] = policy, red: Callable[[int], Policy] = policy) -> tuple[Policy, ...]:
    """One policy per seat: the blue seats from `blue(0)` and the red ones from `red(1)`."""
    return (*[blue(0)] * 5, *[red(1)] * 5)
