import math
from collections import Counter

import pytest

from riftgame.champions import (ACTIONS, ADDED, CAMP_NODES, FOUNTAIN, HOLD, KEEP, LANES, MAP, MODES, NODES, RECALL, RIFT, SEATS,
                                STANDS, TEAMS, Kind, Outcome, capability_of, level_of)
from riftgame.lanes import HOLD_MARGIN, MELEE_REACH, TOWER_RANGE
from riftgame.vision import legal_mask, observe
from riftgame.world import Config, InvariantError, World
from worlds import BLUE_CARRY, BLUE_MID, BLUE_SUPPORT, BLUE_TOP, EVERY_TICK, RED_TOP, act, lane_place, move, raze, staged, submit, until

TICK_S = EVERY_TICK.tick_s


def test_the_action_table_keeps_its_layout():
    first = {kind: next(i for i, a in enumerate(ACTIONS) if a.kind is kind) for kind in Kind}
    assert first == {Kind.KEEP: 0, Kind.HOLD: 1, Kind.RECALL: 2, Kind.MOVE: 3, Kind.LANE: 42, Kind.CAMP: 66, Kind.FOLLOW: 80,
                     Kind.FIGHT: 85, Kind.SIEGE: 90, Kind.WARD: 93}
    assert len(ACTIONS) == len(set(ACTIONS)) == 107
    assert [a.kind for a in ACTIONS] == sorted(a.kind for a in ACTIONS), "each kind is one block"


def test_the_action_table_is_built_from_the_map_and_the_seats():
    count = Counter(a.kind for a in ACTIONS)
    waypoints = ADDED["map"]["lane_waypoints"]
    assert count[Kind.MOVE] == len(RIFT.node_names) - len(waypoints) == 39
    assert count[Kind.LANE] == len(LANES) * len(MODES) * len(STANDS) == 24
    assert {a.target for a in ACTIONS if a.kind is Kind.LANE} == {(lane, mode, stand) for lane in LANES for mode in MODES for stand in STANDS}
    assert (MODES, STANDS) == (("passive", "last_hit", "thin", "push"), ("wave", "hold"))
    assert count[Kind.CAMP] == len(MAP.camps) + len(MAP.scuttlers) == 14
    assert count[Kind.FOLLOW] == count[Kind.FIGHT] == 5 and count[Kind.SIEGE] == 3


def world_node(team: int, name: str) -> str:
    own, enemy = TEAMS[team], TEAMS[1 - team]
    return name.replace("own_", f"{own}_").replace("enemy_", f"{enemy}_")


WALKS = [(Kind.MOVE, node) for node in NODES] + [(Kind.CAMP, node) for node in CAMP_NODES]


@pytest.mark.parametrize("batch", range(0, len(WALKS), 5))
def test_a_walk_ends_at_the_node_its_action_names_in_the_teams_frame_after_distance_over_speed(batch):
    """Blue and red seats get the same action indices, so each index must name mirrored nodes."""
    config = Config(tick_s=1.0, decision_ticks=1)
    world = raze(World(config))
    orders = {seat: act(*WALKS[batch + seat % 5]) for seat in SEATS if batch + seat % 5 < len(WALKS)}
    due = {}
    for seat, action in orders.items():
        node = RIFT.at(world_node(seat // 5, ACTIONS[action].target))
        walk = RIFT.distance(FOUNTAIN[seat // 5], node)
        due[seat] = (node, max(1, math.ceil(walk / capability_of(world.champions[seat]).move_speed - 1e-9)))
    submit(world, orders)
    for _ in range(max(ticks for _, ticks in due.values())):
        world.step()
    for seat, action in orders.items():
        me, (node, ticks) = world.champions[seat], due[seat]
        expected = Outcome.ARRIVED if ACTIONS[action].kind is Kind.MOVE else Outcome.ABSENT
        assert (me.outcome, me.outcome_tick, me.intent) == (expected, ticks - 1, HOLD), ACTIONS[action]
        assert RIFT.distance(me.pos, node) == 0.0, ACTIONS[action]


def test_keep_and_the_same_action_again_leave_progress_alone():
    world = staged({BLUE_TOP: lane_place(0, "top", 9000.0)})
    me = world.champions[BLUE_TOP]
    submit(world, {BLUE_TOP: RECALL})
    until(lambda: me.outcome is not Outcome.NONE, lambda: submit(world, {BLUE_TOP: KEEP if world.tick % 2 else RECALL}))
    assert (me.outcome, world.tick * TICK_S) == (Outcome.RECALLED, 8.5)


def test_any_other_action_discards_progress_and_records_no_outcome():
    world = staged({BLUE_TOP: lane_place(0, "top", 9000.0)})
    me = world.champions[BLUE_TOP]
    submit(world, {BLUE_TOP: RECALL})
    for _ in range(13):
        world.step()
    assert observe(world, BLUE_TOP).me.channel_s == 7.0
    submit(world, {BLUE_TOP: HOLD})
    assert (me.outcome, me.intent, observe(world, BLUE_TOP).me.channel_s) == (Outcome.NONE, HOLD, 0.0)
    submit(world, {BLUE_TOP: RECALL})
    restarted = (world.tick - 1) * TICK_S
    until(lambda: me.outcome is not Outcome.NONE, world.step)
    assert (me.outcome, world.tick * TICK_S - restarted) == (Outcome.RECALLED, 8.5)


def test_a_finished_intent_records_its_outcome_and_tick_and_the_champion_holds_until_told_otherwise():
    target = RIFT.at("blue_top_t2")
    world = staged({BLUE_TOP: RIFT.advance(target, RIFT.at("blue_top_t1"), 300.0)})
    me = world.champions[BLUE_TOP]
    submit(world, {BLUE_TOP: move("own_top_t2")})
    world.step()
    assert (me.outcome, me.outcome_tick, me.intent, me.pos) == (Outcome.ARRIVED, 1, HOLD, target)
    seen = observe(world, BLUE_TOP).me
    assert (seen.outcome, seen.outcome_age_s, seen.intent) == (Outcome.ARRIVED, 0.5, HOLD)
    for _ in range(10):
        submit(world, {BLUE_TOP: KEEP})
    assert (me.pos, me.outcome_tick, me.intent) == (target, 1, HOLD)
    assert observe(world, BLUE_TOP).me.outcome_age_s == 5.5


@pytest.mark.parametrize("seat", [BLUE_TOP, RED_TOP])
@pytest.mark.parametrize("stand", STANDS)
@pytest.mark.parametrize("mode", MODES)
def test_a_lane_action_waits_for_its_wave_at_the_own_outer_tower_or_on_the_hold_line_and_never_ends(seat, mode, stand):
    world = World(Config(tick_s=1.0, decision_ticks=1))
    me = world.champions[seat]
    tower = next(t for t in MAP.towers if t.name == f"{TEAMS[seat // 5]}_top_outer")
    submit(world, {seat: act(Kind.LANE, ("top", mode, stand))})
    for _ in range(45):
        world.step()
    assert world.lanes["top"].front().counts == (6, 6)
    outward = 1 if seat < 5 else -1
    post = tower.s + outward * (TOWER_RANGE + HOLD_MARGIN - MELEE_REACH) * (stand == "hold")
    assert RIFT.distance(me.pos, RIFT.lane_pos("top", post)) == pytest.approx(0.0, abs=1e-6)
    assert (me.outcome, me.intent) == (Outcome.NONE, act(Kind.LANE, ("top", mode, stand)))


def test_a_follower_stops_while_its_ally_is_dead_and_never_ends():
    world = staged({BLUE_CARRY: lane_place(0, "bot", 5000.0), BLUE_SUPPORT: lane_place(0, "bot", 3000.0)})
    carry, support = world.champions[BLUE_CARRY], world.champions[BLUE_SUPPORT]
    follow = act(Kind.FOLLOW, BLUE_CARRY)
    submit(world, {BLUE_SUPPORT: follow})
    world.damage_champion(BLUE_CARRY, carry.hp)
    world.step()
    stopped = support.pos

    def wait():
        assert support.pos == stopped
        world.step()

    assert until(lambda: carry.hp > 0, wait) >= 20
    for _ in range(60):
        world.step()
    assert support.pos == carry.pos == FOUNTAIN[0]
    assert (support.outcome, support.intent) == (Outcome.NONE, follow)


def test_damage_interrupts_a_recall_and_the_recall_does_not_restart_by_itself():
    start = lane_place(0, "top", 9000.0)
    world = staged({BLUE_TOP: start})
    me = world.champions[BLUE_TOP]
    full = me.hp
    submit(world, {BLUE_TOP: RECALL})
    for _ in range(9):
        world.step()
    world.damage_champion(BLUE_TOP, 25.0)
    assert (me.outcome, me.outcome_tick, me.intent, full - me.hp) == (Outcome.INTERRUPTED, 10, HOLD, 25.0)
    assert observe(world, BLUE_TOP).me.channel_s == 0.0
    for _ in range(40):
        world.step()
    assert (me.pos, me.outcome) == (start, Outcome.INTERRUPTED)
    submit(world, {BLUE_TOP: RECALL})
    restarted = (world.tick - 1) * TICK_S
    until(lambda: me.outcome is Outcome.RECALLED, world.step)
    assert world.tick * TICK_S - restarted == 8.5 and me.pos == FOUNTAIN[0]


XP_FOR_LEVEL_7 = 280 + 380 + 480 + 580 + 680 + 780


@pytest.mark.parametrize("tick_s, xp, dead_s", [(0.5, 0.0, 10.0), (0.75, 0.0, 10.5), (0.5, XP_FOR_LEVEL_7, 20.0)])
def test_a_champion_at_zero_health_dies_and_returns_on_its_fountain_after_the_death_timer_of_its_level(tick_s, xp, dead_s):
    world = staged({BLUE_MID: lane_place(0, "mid", 6000.0)}, Config(tick_s=tick_s, decision_ticks=1))
    me = world.champions[BLUE_MID]
    me.xp = xp
    assert level_of(xp) == (7 if xp else 1)
    submit(world, {BLUE_MID: move("enemy_base")})
    world.damage_champion(BLUE_MID, 10_000.0)
    world.step()
    died = world.tick
    assert (me.hp, me.outcome, me.outcome_tick, me.intent, me.pos) == (0.0, Outcome.DIED, died - 1, HOLD, FOUNTAIN[0])
    assert observe(world, BLUE_MID).me.dead_s == pytest.approx(dead_s)

    def stay_dead():
        seen = observe(world, BLUE_MID)
        assert seen.me.dead_s > 0 and legal_mask(seen) == tuple(i == KEEP for i in range(len(ACTIONS)))
        submit(world, {})

    until(lambda: me.hp > 0, stay_dead)
    assert (world.tick - died) * tick_s == pytest.approx(dead_s)
    assert (me.hp, me.mana) == (capability_of(me).max_hp, capability_of(me).max_mana)
    assert (me.pos, me.intent, me.outcome) == (FOUNTAIN[0], HOLD, Outcome.DIED)
    assert legal_mask(observe(world, BLUE_MID))[HOLD]


def test_an_action_for_a_dead_champion_is_refused():
    world = staged({})
    world.damage_champion(BLUE_MID, 10_000.0)
    with pytest.raises(InvariantError):
        submit(world, {BLUE_MID: HOLD})
    submit(world, {BLUE_MID: KEEP})
    with pytest.raises(InvariantError):
        submit(world, {BLUE_MID: move("mid_river")})


def test_damage_to_a_dead_champion_changes_nothing():
    world = staged({})
    world.damage_champion(BLUE_MID, 10_000.0)
    world.step()
    before = world.digest()
    world.damage_champion(BLUE_MID, 50.0)
    assert world.digest() == before


def test_a_lane_waypoint_is_a_node_of_the_map_and_no_move_names_it():
    """The six waypoints that trace the side-lane corners shape a lane. A champion walks over them and cannot
    name one as a destination."""
    waypoints = ADDED["map"]["lane_waypoints"]
    assert sorted(waypoints) == ["bot_corner_a", "bot_corner_b", "bot_corner_c", "top_corner_a", "top_corner_b", "top_corner_c"]
    assert all(node in RIFT.node_names for node in waypoints)
    targets = {a.target for a in ACTIONS if a.kind is Kind.MOVE}
    assert not targets & set(waypoints) and {"top_corner", "bot_corner", "mid_river"} <= targets
    assert all(RIFT.lane_s(node[:3], RIFT.at(node)) is not None for node in waypoints), "each lies on its lane"


def test_ward_is_offered_to_a_champion_with_a_charge_and_to_no_other_and_the_world_accepts_it():
    world = staged({seat: lane_place(seat // 5, "mid", 7000.0) for seat in SEATS})
    indices = [i for i, a in enumerate(ACTIONS) if a.kind is Kind.WARD]
    assert indices and {ACTIONS[i].target for i in indices} == set(CAMP_NODES)
    world.champions[RED_TOP].ward_charges = 0
    for seat in SEATS:
        mask = legal_mask(observe(world, seat))
        assert observe(world, seat).me.ward_charges == (0 if seat == RED_TOP else 1)
        assert [mask[i] for i in indices] == [seat != RED_TOP] * len(indices)
    submit(world, {BLUE_TOP: indices[0]})
    assert world.champions[BLUE_TOP].intent == indices[0]
