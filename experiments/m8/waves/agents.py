"""Wave experiments through the action interface.

Every run is a full `World` with ten champions. A plan only chooses an entry of `ACTIONS` on a decision tick, from
what a laner at its wave can know: its own health, its own caster kills, and the minions near the front. The world
does the rest: the walk, the stance, the hits, minion damage, death. So every behaviour reported here is one that
an agent could produce with the same actions.

The champions are the five profiles of `riftgame.champions` at a chosen level. Their numbers are placeholders.
"""

from dataclasses import dataclass
from typing import Callable

from experiments.m8.waves.harness import BLUE, RED, Row, Trace, crowd, line, outer, under_tower
from riftgame.champions import ACTIONS, HOME, KEEP, LEVEL_XP, OUTER_TOWER, ROLES, Action, Income, Kind, capability_of, level_of
from riftgame.lanes import M8_LANE, TOWER_RANGE, LaneRules, LaneSim, MinionDeath
from riftgame.lanes import Kind as Minion
from riftgame.world import Config, World

HOLD_SEAT = ACTIONS.index(Action(Kind.HOLD))
RETREAT_BELOW = 0.30
RETURN_ABOVE = 0.60
WAVE_SPAN = 1500.0


def lane_action(lane: str, mode: str, stand: str = "wave") -> int:
    return ACTIONS.index(Action(Kind.LANE, (lane, mode, stand)))


def seat_of(team: int, role: str) -> int:
    return team * 5 + ROLES.index(role)


@dataclass(frozen=True, slots=True)
class Seen:
    """What a laner knows about its wave when it decides. Counts are minions within 1500 units of the front."""

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
    """A world whose named roles start at their outer towers at the given level, on both teams, so that no team leads.

    With `start_s` the clock and the lanes start there, with empty lanes. Everyone else holds on its fountain.
    `rules` swaps the lane rules, for a diagnostic.
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
            c.hp, c.mana, c.pos = can.max_hp, can.max_mana, OUTER_TOWER[team][HOME[c.role]]
    return world


class Laner:
    """One seat under a plan. The plan names a mode and a stand, or one of the words `leave` and `stay`.

    Below 30 percent health the laner walks to its own outer tower and comes back above 60 percent. That is a choice
    of actions too: a `MOVE` to the tower node, then the plan's `LANE` action again.
    """

    def __init__(self, seat: int, plan: Plan, retreats: bool = True):
        self.seat, self.plan, self.can_retreat = seat, plan, retreats
        self.lane = HOME[seat % 5]
        self.home = ACTIONS.index(Action(Kind.MOVE, f"own_{self.lane}_t1"))
        self.caster_kills = 0
        self.retreating = False
        self.retreats = 0
        self.lowest = 1.0
        self.deaths = 0
        self.was_alive = True

    def watch(self, world: World) -> None:
        c = world.champions[self.seat]
        alive = c.hp > 0
        self.deaths += self.was_alive and not alive
        self.was_alive = alive
        self.lowest = min(self.lowest, c.hp / capability_of(c).max_hp)
        self.caster_kills += sum(type(e) is MinionDeath and e.killer == self.seat and e.kind is Minion.CASTER for _, e in world.events)

    def act(self, world: World) -> int:
        c = world.champions[self.seat]
        if c.hp <= 0:
            return KEEP
        health = c.hp / capability_of(c).max_hp
        if self.retreating:
            self.retreating = health < RETURN_ABOVE
        elif self.can_retreat and health < RETREAT_BELOW:
            self.retreating = True
            self.retreats += 1
        if self.retreating:
            return self.home
        choice = self.plan(scout(world, self.seat, self.caster_kills))
        if choice == "leave":
            return self.home
        if choice == "stay":
            return HOLD_SEAT
        return lane_action(self.lane, *choice)

    def report(self, world: World) -> dict:
        c = world.champions[self.seat]
        return {"champion_lowest_health": self.lowest, "champion_retreats": self.retreats, "champion_deaths": self.deaths,
                "minion_gold": c.earned[Income.MINION], "level": level_of(c.xp)}


def scout(world: World, seat: int, caster_kills: int = 0) -> Seen:
    c = world.champions[seat]
    team = seat // 5
    sim = world.lanes[HOME[seat % 5]]
    front = sim.front()
    at = line(sim.geometry, front)
    return Seen(world.tick * world.config.tick_s, front.s is not None, crowd(sim, team, at), crowd(sim, 1 - team, at),
                c.hp / capability_of(c).max_hp, caster_kills, under_tower(sim.geometry, team, front.lead[1 - team]),
                under_tower(sim.geometry, 1 - team, front.lead[team]))


def play(world: World, lane: str, laners: list[Laner], until_s: float, stop=lambda row: False) -> Trace:
    """Run the world under the laners' plans and return the lane's trace. Seats without a plan keep holding."""
    sim = world.lanes[lane]
    config = world.config
    rows, events = [], []
    by_seat = {laner.seat: laner for laner in laners}
    while world.tick * config.tick_s < until_s - 1e-9:
        actions = None
        if world.tick % config.decision_ticks == 0:
            actions = [by_seat[seat].act(world) if seat in by_seat else KEEP for seat in range(10)]
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


def until_at_own_tower(plan: Plan, then: Plan) -> Plan:
    """Follow `plan` until the enemy wave is in the laner's own outer tower's range, then follow `then`."""
    arrived = []

    def choose(seen: Seen):
        if seen.foe_at_own_tower:
            arrived.append(seen.time_s)
        return then(seen) if arrived else plan(seen)

    return choose


def band(geometry, team: int = BLUE) -> tuple[float, float]:
    """The stretch of lane from the edge of the team's outer tower range to 1500 units outside it, low end first."""
    heading = geometry.direction(team)
    edge = outer(geometry, team) + heading * TOWER_RANGE
    return tuple(sorted((edge, edge + heading * WAVE_SPAN)))
