"""Shared staging for the kernel tests: worlds with champions on their marks, action lookups, and test policies."""

import math
from collections import Counter

from riftgame.champions import ACTIONS, HOLD, HOME, KEEP, RIFT, SEATS, Action, Kind
from riftgame.harness import jungler, tick
from riftgame.rng import Stream, keyed_uniform
from riftgame.vision import Observation, legal_mask
from riftgame.world import Config, World

EVERY_TICK = Config(tick_s=0.5, decision_ticks=1)
BLUE_TOP, BLUE_JUNGLE, BLUE_MID, BLUE_CARRY, BLUE_SUPPORT = range(5)
RED_TOP, RED_JUNGLE, RED_MID, RED_CARRY, RED_SUPPORT = range(5, 10)


def act(kind: Kind, target=None) -> int:
    return ACTIONS.index(Action(kind, target))


def move(node: str) -> int:
    return act(Kind.MOVE, node)


def lane(name: str, mode: str, stand: str = "wave") -> int:
    return act(Kind.LANE, (name, mode, stand))


def lane_place(team: int, lane: str, from_own_end: float):
    """A lane position by its distance from the team's own end of the lane."""
    length = RIFT.lanes[lane].length
    return RIFT.lane_pos(lane, from_own_end if team == 0 else length - from_own_end)


def staged(places: dict, config: Config = EVERY_TICK, seed: int = 0) -> World:
    """A new world with the given seats moved to their marks. Everyone else holds on its fountain."""
    world = World(config, seed)
    for seat, pos in places.items():
        world.champions[seat].pos = pos
    return world


def submit(world: World, orders: dict) -> None:
    """Advance one tick on which the given seats get their actions and everyone else keeps."""
    world.step([orders.get(seat, KEEP) for seat in SEATS])


def until(done, advance, limit: int = 400) -> int:
    """Call `advance` until `done()` holds, and return how often. A world that never gets there fails the test."""
    for calls in range(limit):
        if done():
            return calls
        advance()
    raise AssertionError(f"not reached after {limit} ticks")


def patient(o: Observation, noise: float) -> int:
    """Random legal actions that mostly get finished: it keeps a running intent four times in five."""
    mask = legal_mask(o)
    if mask[KEEP] and o.me.intent != HOLD and noise < 0.8:
        return KEEP
    legal = [i for i, ok in enumerate(mask) if ok]
    return legal[int(noise * 5 % 1 * len(legal))]


def busy(o: Observation, noise: float) -> int:
    """Scripted junglers among patient laners, so that camps are cleared while the laners act at random."""
    return jungler(o, noise) if HOME[o.me.role] is None else patient(o, noise)


def hazard(world: World, per_tick: float, amount: float) -> None:
    """Damage from nowhere, keyed on the seat and the tick, so that champions die without combat."""
    for seat in SEATS:
        if keyed_uniform(world.seed, Stream.COMBAT, seat, world.tick) < per_tick:
            world.damage_champion(seat, amount)


def ended_now(world: World) -> Counter:
    """Outcomes recorded on the tick that just ran."""
    return Counter(c.outcome.name for c in world.champions if c.outcome_tick == world.tick - 1)


def play(world: World, policy, ticks: int) -> tuple[list[str], Counter]:
    """Run `ticks` ticks. Returns the digest after each, and the outcomes recorded on the way."""
    digests, ended = [], Counter()
    for _ in range(ticks):
        tick(world, policy)
        digests.append(world.digest())
        ended += ended_now(world)
    return digests, ended


def raze(world: World) -> World:
    """Take every lane tower down, for a test that walks champions where towers would shoot them."""
    for sim in world.lanes.values():
        for tower in (*sim.towers[0], *sim.towers[1]):
            tower.hp = 0.0
    return world


def no_waves(world: World) -> World:
    """Stop every lane from spawning, so that the lanes hold only the minions a test puts there."""
    for sim in world.lanes.values():
        sim.clock.next_wave = math.inf
    return world


class StubLane:
    """A lane that only reports values, for the tests of what the world digest reads from a lane."""

    def __init__(self, values: tuple = ()):
        self.state = values

    def values(self):
        return self.state
