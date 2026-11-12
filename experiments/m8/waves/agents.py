"""Wave experiments through the action interface and the observation.

Every run is a full `World` with ten champions. A plan only chooses an entry of `ACTIONS` on a decision tick, from
what its champion's observation holds: its own health, and its lane as its team sees it. The world does the rest:
the walk, the stance, the hits, minion damage, death. So every behaviour reported here is one that an agent could
produce with the same actions and the same information.

A champion is at a lane only if a `Laner` plays it. Every other champion stays on its fountain, out of the lane's
XP range and out of every minion's and tower's reach. A laner whose plan says `leave` walks back to its fountain.
One whose plan says `tower` stands at its own outer tower, where it still gains XP and may be hit.

The champions are the five profiles of `riftgame.champions` at a chosen level. Their numbers are placeholders.
"""

from dataclasses import dataclass
from typing import Callable

from experiments.m8.waves.harness import BLUE, RED, Row, Trace, crowd, line, outer
from riftgame.champions import ACTIONS, HOME, KEEP, LANES, LEVEL_XP, OUTER_TOWER, ROLES, Action, Income, Kind, capability_of, level_of
from riftgame.lanes import M8_LANE, TOWER_RANGE, ChampionDamage, LaneGeometry, LaneRules, LaneSim, MinionDeath
from riftgame.lanes import Kind as Minion
from riftgame.vision import Observation, observe_team
from riftgame.world import Config, World

HOLD_SEAT = ACTIONS.index(Action(Kind.HOLD))
TO_FOUNTAIN = ACTIONS.index(Action(Kind.MOVE, "own_fountain"))
RETREAT_BELOW = 0.30
RETURN_ABOVE = 0.60
WAVE_SPAN = 1500.0


def lane_action(lane: str, mode: str, stand: str = "wave") -> int:
    return ACTIONS.index(Action(Kind.LANE, (lane, mode, stand)))


def seat_of(team: int, role: str) -> int:
    return team * 5 + ROLES.index(role)


@dataclass(frozen=True, slots=True)
class Seen:
    """What a laner knows about its wave when it decides, all of it from its observation.

    `own` counts its team's minions within 1500 units behind their lead minion. `foe` counts the enemy minions
    that its team sees now within 1500 units behind the enemy lead, and is 0 while the team sees none."""

    time_s: float
    contact: bool
    own: int
    foe: int
    health: float
    caster_kills: int
    foe_at_own_tower: bool
    own_at_enemy_tower: bool


Plan = Callable[[Seen], tuple[str, str] | str]


def staged(seed: int, levels: dict[str, int], start_s: float = 0.0, config: Config = Config(), rules: LaneRules = M8_LANE) -> World:
    """A world whose named roles have the given level on both teams, so that no team leads. Everyone is on its
    fountain. `at_tower` puts a champion at its lane.

    With `start_s` the clock and the lanes start there, with empty lanes. `rules` swaps the lane rules, for a
    diagnostic.
    """
    world = World(config, seed)
    if start_s or rules != M8_LANE:
        world.tick = round(start_s / config.tick_s)
        world.lanes = {name: LaneSim(name, seed, config.tick_s, rules, start_s=start_s) for name in world.lanes}
    for role, level in levels.items():
        for team in (BLUE, RED):
            c = world.champions[seat_of(team, role)]
            c.xp = LEVEL_XP[level - 2] if level > 1 else 0.0
            can = capability_of(c)
            c.hp, c.mana = can.max_hp, can.max_mana
    return world


def at_tower(world: World, seat: int) -> None:
    """Start a champion at its own outer tower, where a laner stands when the first wave arrives."""
    c = world.champions[seat]
    c.pos = OUTER_TOWER[c.team][HOME[c.role]]


def scout(o: Observation, lane: str, team: int, geometry: LaneGeometry, caster_kills: int = 0) -> Seen:
    """A laner's view of its wave, read from its observation alone."""
    view = o.lanes[LANES.index(lane)]

    def framed(s: float) -> float:
        return s if team == BLUE else geometry.length - s

    foe_lead = view.enemy_lead if view.enemy_age_s == 0.0 else None
    return Seen(o.time_s, view.contact, sum(view.own_near), sum(view.enemy_near) if foe_lead is not None else 0, o.me.hp / o.me.max_hp, caster_kills,
                foe_lead is not None and abs(foe_lead - framed(outer(geometry, team))) <= TOWER_RANGE,
                view.own_lead is not None and abs(view.own_lead - framed(outer(geometry, 1 - team))) <= TOWER_RANGE)


class Laner:
    """One seat under a plan. The plan names a mode and a stand, or one of the words `leave`, `tower`, and `stay`.

    Below 30 percent health the laner walks to its own outer tower and comes back above 60 percent. That is a choice
    of actions too: a `MOVE` to the tower node, then the plan's `LANE` action again.

    `act` reads the observation only. `watch` reads the world: it keeps the experiment's record of the champion,
    and it counts the champion's own caster kills, which a champion knows.
    """

    def __init__(self, world: World, seat: int, plan: Plan, retreats: bool = True):
        self.seat, self.plan, self.can_retreat = seat, plan, retreats
        self.lane = HOME[seat % 5]
        self.geometry = world.lanes[self.lane].geometry
        self.home = ACTIONS.index(Action(Kind.MOVE, f"own_{self.lane}_t1"))
        self.caster_kills = 0
        self.retreating = False
        self.retreats = 0
        self.lowest = 1.0
        self.deaths = 0
        self.was_alive = True
        self.minion_damage = 0.0
        self.hits_before_contact = 0
        self.contact_seen = False
        at_tower(world, seat)

    def watch(self, world: World) -> None:
        c = world.champions[self.seat]
        alive = c.hp > 0
        self.deaths += self.was_alive and not alive
        self.was_alive = alive
        self.lowest = min(self.lowest, c.hp / capability_of(c).max_hp)
        blows = [e for _, e in world.events if type(e) is ChampionDamage and e.seat == self.seat]
        self.minion_damage += sum(e.damage for e in blows)
        self.contact_seen = self.contact_seen or world.lanes[self.lane].front().s is not None
        self.hits_before_contact += 0 if self.contact_seen else len(blows)
        self.caster_kills += sum(type(e) is MinionDeath and e.killer == self.seat and e.kind is Minion.CASTER for _, e in world.events)

    def act(self, o: Observation) -> int:
        me = o.me
        if me.hp <= 0:
            return KEEP
        health = me.hp / me.max_hp
        if self.retreating:
            self.retreating = health < RETURN_ABOVE
        elif self.can_retreat and health < RETREAT_BELOW:
            self.retreating = True
            self.retreats += 1
        if self.retreating:
            return self.home
        choice = self.plan(scout(o, self.lane, self.seat // 5, self.geometry, self.caster_kills))
        if choice == "leave":
            return TO_FOUNTAIN
        if choice == "tower":
            return self.home
        if choice == "stay":
            return HOLD_SEAT
        return lane_action(self.lane, *choice)

    def report(self, world: World) -> dict:
        """What the plan cost and earned. `minion_blows_before_first_contact` counts minion blows on the champion
        before the lane's waves first met, which the first wave of the real game would not deal."""
        c = world.champions[self.seat]
        return {"champion_lowest_health": self.lowest, "champion_retreats": self.retreats, "champion_deaths": self.deaths,
                "minion_damage_taken": self.minion_damage, "minion_blows_before_first_contact": self.hits_before_contact,
                "minion_gold": c.earned[Income.MINION], "xp": c.xp, "level": level_of(c.xp)}


NO_LANER = {"champion_lowest_health": None, "champion_retreats": None, "champion_deaths": None, "minion_damage_taken": None,
            "minion_blows_before_first_contact": None, "minion_gold": None, "xp": None, "level": None}


def play(world: World, lane: str, laners: list[Laner], until_s: float, stop=lambda row: False) -> Trace:
    """Run the world under the laners' plans and return the lane's trace. Seats without a plan keep holding, on
    their fountain."""
    sim = world.lanes[lane]
    config = world.config
    rows, events = [], []
    by_seat = {laner.seat: laner for laner in laners}
    teams = sorted({seat // 5 for seat in by_seat})
    while world.tick * config.tick_s < until_s - 1e-9:
        actions = None
        if world.tick % config.decision_ticks == 0:
            actions = [KEEP] * 10
            for team in teams:
                for role, o in enumerate(observe_team(world, team)):
                    if team * 5 + role in by_seat:
                        actions[team * 5 + role] = by_seat[team * 5 + role].act(o)
        world.step(actions)
        for laner in laners:
            laner.watch(world)
        events += [e for name, e in world.events if name == lane]
        front = sim.front()
        rows.append(Row(sim.time, line(sim.geometry, front), *front.lead, *front.counts, front.s is not None, crowd(sim, BLUE, front.lead[BLUE])))
        if stop(rows[-1]):
            break
    return Trace(sim.geometry, rows, events)


def always(mode: str, stand: str = "wave") -> Plan:
    return lambda seen: (mode, stand)


def thin_then(kills: int, after: str) -> Plan:
    """Thin until the laner has killed `kills` casters, then play `after`."""
    return lambda seen: ("thin", "wave") if seen.caster_kills < kills else (after, "wave")


def hold_thin_over(lead: int) -> Plan:
    """Hold. Thin while the enemy wave leads by more than `lead` minions, and last-hit otherwise."""
    return lambda seen: ("thin" if seen.foe - seen.own > lead else "last_hit", "hold")


def hold_trim_to(size: int, with_mode: str = "thin") -> Plan:
    """Hold. With its own wave gone, cut the enemy wave down to `size` minions, and last-hit otherwise."""
    return lambda seen: (with_mode if seen.own == 0 and seen.foe > size else "last_hit", "hold")


def until_crash(plan: Plan, then: str = "leave") -> Plan:
    """Follow `plan` until the laner's wave is in the enemy outer tower's range, then leave for good."""
    crashed = []

    def choose(seen: Seen):
        if seen.own_at_enemy_tower:
            crashed.append(seen.time_s)
        return then if crashed else plan(seen)

    return choose


def from_wave(number: int, plan: Plan, before: Plan, wave_s: float = 30.0) -> Plan:
    """Follow `before` until the `number`th waves are due to meet, then follow `plan`. The first waves meet when
    the laner first sees contact, and each later pair one wave interval after the pair before it."""
    met = []

    def choose(seen: Seen):
        if not met and seen.contact:
            met.append(seen.time_s)
        return plan(seen) if met and seen.time_s >= met[0] + (number - 1) * wave_s else before(seen)

    return choose


def band(geometry, team: int = BLUE) -> tuple[float, float]:
    """The stretch of lane from the edge of the team's outer tower range to 1500 units outside it, low end first."""
    heading = geometry.direction(team)
    edge = outer(geometry, team) + heading * TOWER_RANGE
    return tuple(sorted((edge, edge + heading * WAVE_SPAN)))
