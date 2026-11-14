from collections import Counter

import pytest

import riftgame.world
from riftgame.champions import ACTIONS, FOUNTAIN, HOLD, KEEP, RIFT, SEATS, Kind, Outcome, speed_of
from riftgame.harness import random_legal, run, tick
from riftgame.map import Pos
from riftgame.world import Config, InvariantError, World, check_invariants
from worlds import BLUE_MID, act, ended_now, hazard, move, patient

GAME_S = 600.0
GAMES = [(seed, random_legal if seed % 2 == 0 else patient, Config(tick_s=0.5, decision_ticks=4) if seed % 4 < 2 else Config(tick_s=1.0, decision_ticks=5))
         for seed in range(10)]


@pytest.fixture(scope="module")
def soak():
    """Ten games of random legal actions with the invariant checker on every tick, and champions that get hurt."""
    ended, largest_step = Counter(), 0.0
    for seed, policy, config in GAMES:
        world = World(config, seed)
        for _ in range(round(GAME_S / config.tick_s)):
            hazard(world, 0.02 * config.tick_s, 130.0)
            stood = [(c.pos, speed_of(world, c)) for c in world.champions]
            tick(world, policy, check=True)
            now = ended_now(world)
            ended += now
            for c, (was, speed) in zip(world.champions, stood):
                if not (c.outcome_tick == world.tick - 1 and c.outcome in (Outcome.DIED, Outcome.RECALLED)):
                    largest_step = max(largest_step, RIFT.distance(was, c.pos) / (speed * config.tick_s))
        assert world.tick * config.tick_s == GAME_S
    return ended, largest_step


def test_ten_games_of_random_legal_actions_run_ten_minutes_each_with_no_invariant_failure(soak):
    ended, _ = soak
    assert len(GAMES) == 10 and GAME_S >= 600
    assert {"ARRIVED", "ABSENT", "RECALLED", "INTERRUPTED", "DIED"} <= set(ended), dict(ended)


def test_no_position_changes_by_more_than_speed_times_the_tick_except_on_death_and_on_recall(soak):
    ended, largest_step = soak
    assert 0.99 < largest_step <= 1 + 1e-9
    assert ended["DIED"] > 0 and ended["RECALLED"] > 0, "both exceptions must occur in the run"


def broken(change) -> World:
    world = World(Config(tick_s=0.5, decision_ticks=1), seed=1)
    run(world, patient, 20)
    change(world.champions[BLUE_MID], world)
    return world


def set_field(name: str, value):
    return lambda c, world: setattr(c, name, value)


BREAKS = {
    "health above the maximum": set_field("hp", 10_000.0),
    "health below zero": set_field("hp", -1.0),
    "mana above the maximum": set_field("mana", 10_000.0),
    "mana below zero": set_field("mana", -1.0),
    "negative gold": set_field("gold", -0.5),
    "an edge that is not on the map": set_field("pos", Pos(len(RIFT.edges), 0.0)),
    "a position beyond the end of its edge": set_field("pos", Pos(0, RIFT.edges[0].length + 1.0)),
    "a position before the start of its edge": set_field("pos", Pos(0, -1.0)),
    "a dead champion that holds an intent": lambda c, world: (setattr(c, "hp", 0.0), setattr(c, "intent", move("mid_river"))),
}


@pytest.mark.parametrize("change", BREAKS.values(), ids=BREAKS.keys())
def test_the_checker_raises_on(change):
    check_invariants(broken(lambda c, world: None))
    with pytest.raises(InvariantError):
        check_invariants(broken(change))


def test_the_checker_raises_on_a_clock_that_did_not_advance_by_exactly_one_tick():
    world = World(Config(tick_s=0.5, decision_ticks=4))
    world.step()
    check_invariants(world, previous_tick=0)
    for previous in (1, -1):
        with pytest.raises(InvariantError):
            check_invariants(world, previous_tick=previous)


def test_the_checker_raises_on_an_empty_legal_mask(monkeypatch):
    world = World(Config(tick_s=0.5, decision_ticks=4))
    monkeypatch.setattr(riftgame.world, "legal_mask", lambda o: (False,) * len(ACTIONS))
    with pytest.raises(InvariantError):
        check_invariants(world)


def test_a_checked_tick_raises_when_a_policy_chooses_an_action_its_mask_forbids():
    fight = act(Kind.FIGHT, 0)
    with pytest.raises(InvariantError):
        tick(World(Config(tick_s=0.5, decision_ticks=4)), lambda o, noise: fight, check=True)
    lane_elsewhere = act(Kind.LANE, ("bot", "push", "wave"))
    with pytest.raises(InvariantError):
        tick(World(Config(tick_s=0.5, decision_ticks=4)), lambda o, noise: lane_elsewhere if o.me.role == 0 else KEEP, check=True)
    world = World(Config(tick_s=0.5, decision_ticks=4))
    tick(world, lambda o, noise: HOLD, check=True)
    assert world.tick == 1 and all(c.pos == FOUNTAIN[c.team] for c in world.champions) and len(SEATS) == 10
