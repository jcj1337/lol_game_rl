import pytest

from riftgame.champions import FOUNTAIN, HOLD, KEEP, RECALL, RIFT, Kind, Outcome, capability_of
from riftgame.world import Config, World
from worlds import BLUE_CARRY, BLUE_SUPPORT, BLUE_TOP, EVERY_TICK, act, busy, lane_place, move, patient, play, staged, submit, until

TICKS = 600


@pytest.mark.parametrize("n", [2, 4, 10])
def test_a_run_at_interval_n_equals_a_run_at_interval_1_that_keeps_between_decisions(n):
    spaced, ended = play(World(Config(tick_s=0.5, decision_ticks=n), seed=12), busy, TICKS)

    def keeping_between(o, noise):
        return busy(o, noise) if round(o.time_s / EVERY_TICK.tick_s) % n == 0 else KEEP

    every_tick, _ = play(World(EVERY_TICK, seed=12), keeping_between, TICKS)
    assert spaced == every_tick
    assert {"ARRIVED", "ABSENT", "CLEARED", "RECALLED", "DIED"} <= set(ended), f"intents must end inside the run, got {dict(ended)}"


def test_a_policy_that_decides_every_tick_plays_a_different_game_from_one_that_decides_every_tenth():
    every_tick, _ = play(World(EVERY_TICK, seed=11), patient, TICKS)
    every_tenth, _ = play(World(Config(tick_s=0.5, decision_ticks=10), seed=11), patient, TICKS)
    assert every_tick[-1] != every_tenth[-1], "the digest must be able to tell two trajectories apart"


def test_a_redirected_move_continues_from_where_the_champion_stands_and_walks_speed_times_time():
    world = staged({})
    me = world.champions[BLUE_TOP]
    step = capability_of(me).move_speed * world.config.tick_s
    second = RIFT.at("red_fountain")
    walked, trail = 0.0, me.pos
    for t in range(30):
        to_go = RIFT.distance(me.pos, second)
        submit(world, {BLUE_TOP: move("top_river") if t < 10 else move("enemy_fountain")})
        if t == 10:
            assert to_go - RIFT.distance(me.pos, second) == pytest.approx(step), "the first step is on the new route"
        assert RIFT.distance(trail, me.pos) == pytest.approx(step)
        walked += RIFT.distance(trail, me.pos)
        trail = me.pos
    assert me.outcome is Outcome.NONE
    assert walked == pytest.approx(capability_of(me).move_speed * 30 * world.config.tick_s)


@pytest.mark.parametrize("tick_s, seconds", [(0.25, 8.5), (0.5, 8.5), (0.4, 8.8), (1.0, 9.0)])
def test_a_recall_takes_the_cast_and_the_channel_rounded_up_to_whole_ticks(tick_s, seconds):
    world = staged({BLUE_TOP: lane_place(0, "top", 9000.0)}, Config(tick_s=tick_s, decision_ticks=1))
    me = world.champions[BLUE_TOP]
    start = me.pos
    submit(world, {BLUE_TOP: RECALL})

    def channel():
        assert me.pos == start, "the champion stands still while it channels"
        world.step()

    until(lambda: me.outcome is not Outcome.NONE, channel)
    assert world.tick * tick_s == pytest.approx(seconds)
    assert (me.outcome, me.pos, me.intent) == (Outcome.RECALLED, FOUNTAIN[0], HOLD)


@pytest.mark.parametrize("units_out", [0.0, 900.0])
def test_a_recall_on_the_fountain_completes_at_once(units_out):
    world = staged({BLUE_TOP: RIFT.advance(FOUNTAIN[0], RIFT.at("blue_base"), units_out)})
    me = world.champions[BLUE_TOP]
    submit(world, {BLUE_TOP: RECALL})
    assert (me.outcome, me.outcome_tick, me.pos) == (Outcome.RECALLED, 0, FOUNTAIN[0])


@pytest.mark.parametrize("bad", [{"tick_s": 0.0}, {"tick_s": -0.5}, {"decision_ticks": 0}])
def test_a_clock_that_cannot_run_is_refused(bad):
    with pytest.raises(ValueError):
        Config(**bad)


def test_actions_are_refused_between_decision_ticks():
    world = World(Config(tick_s=0.5, decision_ticks=4))
    world.step([KEEP] * 10)
    with pytest.raises(ValueError):
        world.step([KEEP] * 10)
    for _ in range(3):
        world.step()
    world.step([HOLD] * 10)


def test_a_follower_heads_for_where_its_ally_stood_before_the_move_step():
    start = lane_place(0, "bot", 4000.0)
    world = staged({BLUE_CARRY: start, BLUE_SUPPORT: start})
    carry, support = world.champions[BLUE_CARRY], world.champions[BLUE_SUPPORT]
    assert capability_of(support).move_speed > capability_of(carry).move_speed
    submit(world, {BLUE_CARRY: move("enemy_base"), BLUE_SUPPORT: act(Kind.FOLLOW, BLUE_CARRY)})
    assert support.pos == start
    for _ in range(20):
        trail = carry.pos
        world.step()
        assert support.pos == trail and carry.pos != trail


def test_two_champions_that_follow_each_other_swap_places_whichever_seat_moves_first():
    near, far = lane_place(0, "bot", 4000.0), lane_place(0, "bot", 4100.0)
    world = staged({BLUE_CARRY: near, BLUE_SUPPORT: far})
    submit(world, {BLUE_CARRY: act(Kind.FOLLOW, BLUE_SUPPORT), BLUE_SUPPORT: act(Kind.FOLLOW, BLUE_CARRY)})
    assert (world.champions[BLUE_CARRY].pos, world.champions[BLUE_SUPPORT].pos) == (far, near)
