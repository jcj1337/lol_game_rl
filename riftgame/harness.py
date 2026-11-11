"""Running games: the policy interface, two scripted policies, and replays.

A policy is `act(observation, noise) -> action index`. The noise is a keyed draw on the seat and the tick, so
a policy holds no generator and a replay needs only the actions.
"""

from collections.abc import Callable
from dataclasses import dataclass

from riftgame.champions import ACTIONS, HOME, KEEP, RETURNS, ROLES, SEATS, Action, Kind
from riftgame.rng import Stream, keyed_uniform
from riftgame.vision import Observation, legal_mask, observe
from riftgame.world import Config, InvariantError, World, check_invariants

Policy = Callable[[Observation, float], int]


def random_legal(o: Observation, noise: float) -> int:
    legal = [i for i, ok in enumerate(legal_mask(o)) if ok]
    return legal[int(noise * len(legal))]


_AWAY = tuple(tuple(i for i, a in enumerate(ACTIONS) if a.kind is Kind.MOVE and not RETURNS[role][i])
              for role in range(len(ROLES)))
_HOMEWARD = tuple(None if lane is None else ACTIONS.index(Action(Kind.LANE, (lane, "passive"))) for lane in HOME)


def roamer(o: Observation, noise: float) -> int:
    """Always prefers a legal action away from its lane: it finishes a walk off the lane, then starts another.

    It heads for its lane only when the mask leaves nothing else.
    """
    mask, role = legal_mask(o), o.me.role
    if mask[KEEP] and o.me.intent in _AWAY[role]:
        return KEEP
    away = [i for i in _AWAY[role] if mask[i]]
    if away:
        return away[int(noise * len(away))]
    homeward = _HOMEWARD[role]
    return homeward if homeward is not None and mask[homeward] else KEEP


_FARM = tuple(None if lane is None else ACTIONS.index(Action(Kind.LANE, (lane, "last_hit"))) for lane in HOME)


def farmer(o: Observation, noise: float) -> int:
    """Every laner last-hits in its own lane and junglers hold. The scripted baseline until C4 and C5 give more to do."""
    farm = _FARM[o.me.role]
    return farm if farm is not None and legal_mask(o)[farm] else KEEP


def tick(world: World, policy: Policy, check: bool = False) -> tuple[int, ...] | None:
    """Advance one tick and return the actions submitted on it, or None between decisions.

    With `check`, an illegal choice or a broken invariant raises `InvariantError`.
    """
    actions = None
    if world.tick % world.config.decision_ticks == 0:
        observations = [observe(world, seat) for seat in SEATS]
        actions = tuple(policy(o, keyed_uniform(world.seed, Stream.POLICY, seat, world.tick))
                        for seat, o in enumerate(observations))
        if check:
            for seat, (o, action) in enumerate(zip(observations, actions)):
                if not legal_mask(o)[action]:
                    raise InvariantError(f"seat {seat} chose {ACTIONS[action]}, which its mask forbids")
    before = world.tick
    world.step(actions)
    if check:
        check_invariants(world, before)
    return actions


def run(world: World, policy: Policy, ticks: int, check: bool = False) -> None:
    for _ in range(ticks):
        tick(world, policy, check)


@dataclass(frozen=True, slots=True)
class Replay:
    """A game as its config, its seed, and what was submitted on each tick."""

    config: Config
    seed: int
    log: tuple[tuple[int, ...] | None, ...]


def record(config: Config, seed: int, policy: Policy, ticks: int) -> tuple[Replay, list[str]]:
    """Play a new game and return its replay with the digest after every tick."""
    world, log, digests = World(config, seed), [], []
    for _ in range(ticks):
        log.append(tick(world, policy))
        digests.append(world.digest())
    return Replay(config, seed, tuple(log)), digests


def rerun(replay: Replay) -> list[str]:
    """The digest after every tick of a replayed game."""
    world, digests = World(replay.config, replay.seed), []
    for actions in replay.log:
        world.step(actions)
        digests.append(world.digest())
    return digests
