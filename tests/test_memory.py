"""What a team remembers of enemy towers and champions, the lanes' derived caches, and the river ward spots."""

import pickle

import pytest

from riftgame.champions import FOUNTAIN, LANES, RIFT, Kind
from riftgame.lanes import Kind as Minion
from riftgame.map import Pos
from riftgame.vision import EnemyView, LastSeen, legal_mask, observe, sees, to_frame
from riftgame.world import InvariantError, World, check_invariants
from test_vision import MID, PLACES, PLACE_RANGE, RIVER, TICK_S, mid, own_end, quiet_world
from worlds import act, lane_place, move, submit, until

JUNGLE = 1
# Rows E13a, E14a, and E15a: the health of an outer, an inner, and a base lane tower.
OUTER_HP, INNER_HP, BASE_HP = 9000.0, 5000.0, 4750.0
RIVER_SPOTS = ("top_river>top_corner", "top_river>mid_river", "bot_river>mid_river", "bot_river>bot_corner")


@pytest.mark.parametrize("team", [0, 1])
def test_an_enemy_towers_health_shows_while_the_team_sees_it_freezes_out_of_view_and_reads_zero_once_fallen(team):
    viewer, foe = team * 5 + MID, 1 - team
    world = quiet_world({}, towers=True)
    sim = world.lanes["mid"]
    outer = sim.towers[foe][0]
    world.champions[viewer].pos = lane_place(team, "mid", own_end(team, outer.s) - 1000.0)

    def view():
        lane = observe(world, viewer).lanes[LANES.index("mid")]
        return lane.enemy_towers, lane.enemy_towers_age_s

    world.step()
    assert view() == ((OUTER_HP, INNER_HP, BASE_HP), (0.0, 0.0, 0.0))
    outer.hp -= 500.0
    world.step()
    assert view() == ((OUTER_HP - 500.0, INNER_HP, BASE_HP), (0.0, 0.0, 0.0)), "seen, so the record follows the tower"
    world.champions[viewer].pos = FOUNTAIN[team]
    outer.hp -= 700.0
    for n in range(1, 7):
        world.step()
        assert view() == ((OUTER_HP - 500.0, INNER_HP, BASE_HP), (n * TICK_S, 0.0, 0.0)), "the towers behind a standing one take no damage"
    outer.hp = 0.0
    world.step()
    assert view() == ((0.0, INNER_HP, BASE_HP), (0.0, TICK_S, 0.0)), "a fall is public, and the inner tower is the front now and out of view"
    world.step()
    assert view() == ((0.0, INNER_HP, BASE_HP), (0.0, 2 * TICK_S, 0.0))


@pytest.mark.parametrize("team", [0, 1])
def test_an_enemys_upgrades_show_while_it_is_seen_and_stay_in_the_last_seen_record_and_its_earlier_place_needs_two_ticks_of_sight(team):
    viewer, enemy = team * 5 + MID, (1 - team) * 5 + JUNGLE
    world = quiet_world({viewer: lane_place(team, "mid", 5000.0), enemy: lane_place(team, "mid", 5300.0)})
    foe = world.champions[enemy]

    def seen():
        o = observe(world, viewer)
        return o.enemies[JUNGLE], o.remembered[JUNGLE]

    world.step()
    first = to_frame(team, foe.pos)
    assert seen() == (EnemyView(first, None, foe.hp, 1, 1), LastSeen(first, foe.hp, 1, 1, 0.0)), "seen once: no earlier place"
    submit(world, {enemy: move("own_base")})
    assert seen()[0] == EnemyView(to_frame(team, foe.pos), first, foe.hp, 1, 1) and foe.pos != world.champions[viewer].pos
    foe.upgrades = 3
    world.step()
    walked_to, hp = to_frame(team, foe.pos), foe.hp
    assert seen()[0].upgrades == seen()[1].upgrades == 3
    foe.pos = FOUNTAIN[1 - team]
    foe.upgrades = 4
    world.step()
    assert seen() == (None, LastSeen(walked_to, hp, 1, 3, TICK_S)), "out of view the record keeps what was seen"
    foe.pos = lane_place(team, "mid", 5300.0)
    world.step()
    again = seen()[0]
    assert (again.was, again.upgrades) == (None, 4), "seen again after a tick out of view: no earlier place"


ON_LANES = [pos for pos in PLACES if any(RIFT.lane_s(name, pos) is not None for name in LANES)]
BESIDE = [pos for pos in PLACES if all(RIFT.lane_s(name, pos) is None for name in LANES)]


def sight(world: World, places=ON_LANES) -> tuple:
    """Blue's sight of the test places on the lanes, and what its mid lane derives from its minions: the stretches
    they see and the front against three enemy leads."""
    sim = world.lanes["mid"]
    return ([sees(world, 0, pos) for pos in places], sim.sighted(0), [sim.known_front(0, foe) for foe in (None, RIVER + 1800.0, RIVER + 3000.0)])


def minions_at(world: World, s: float) -> World:
    world.lanes["mid"].add_minion(0, Minion.MELEE, s, count=3, delay=1e6)
    return world


def test_a_lane_whose_minions_were_moved_by_hand_sees_like_a_fresh_lane_once_invalidated_and_after_a_snapshot_or_a_pickle():
    places = {MID: mid(-4000.0)}
    moved = minions_at(quiet_world(places), RIVER - 2000.0)
    moved.step()
    before = sight(moved)
    for m in moved.lanes["mid"].minions[0]:
        m.s = RIVER + 1500.0
    fresh = minions_at(quiet_world(places), RIVER + 1500.0)
    assert sight(fresh) != before, "the move shows in what blue sees"
    assert sight(moved) == before, "the lane still holds what it derived from the old places"
    with pytest.raises(InvariantError, match="stale"):
        check_invariants(moved)
    for copy in (World.restore(moved.snapshot()), pickle.loads(pickle.dumps(moved))):
        assert sight(copy) == sight(fresh)
        check_invariants(copy)
    moved.lanes["mid"].invalidate()
    assert sight(moved) == sight(fresh)
    check_invariants(moved)


def test_a_lane_whose_minions_were_moved_by_hand_sees_beside_the_lane_like_a_fresh_lane_once_invalidated():
    places = {MID: mid(-4000.0)}
    moved = minions_at(quiet_world(places), RIVER - 2000.0)
    moved.step()
    for m in moved.lanes["mid"].minions[0]:
        m.s = RIVER + 1500.0
    moved.lanes["mid"].invalidate()
    fresh = minions_at(quiet_world(places), RIVER + 1500.0)
    assert sight(moved, BESIDE) == sight(fresh, BESIDE)


@pytest.mark.parametrize("team", [0, 1])
@pytest.mark.parametrize("spot", RIVER_SPOTS)
def test_a_river_ward_spot_is_the_middle_of_its_river_edge_for_both_teams_and_a_ward_order_places_the_ward_there(spot, team):
    a, b = spot.split(">")
    ends = {RIFT.node_names.index(a), RIFT.node_names.index(b)}
    edge = next(i for i, e in enumerate(RIFT.edges) if {e.a, e.b} == ends)
    middle = Pos(edge, RIFT.edges[edge].length / 2)
    seat = team * 5 + JUNGLE
    world = quiet_world({seat: RIFT.at(b)})
    order = act(Kind.WARD, spot)
    assert legal_mask(observe(world, seat))[order]
    me = world.champions[seat]
    submit(world, {seat: order})
    until(lambda: world.sights, world.step)
    assert [(s.team, s.pos, s.owner) for s in world.sights] == [(team, middle, seat)]
    assert RIFT.separation(me.pos, middle) <= PLACE_RANGE + 1e-6
    assert [ward.place for ward in observe(world, seat).wards] == [to_frame(team, middle)]


def test_the_invariant_check_finds_a_minion_moved_by_hand_whose_map_coordinates_were_not_derived_again():
    world = minions_at(quiet_world({}), RIVER - 2000.0)
    sim = world.lanes["mid"]
    assert sim.stale() is None, "no cache is filled yet, so only the coordinates can go stale"
    for m in sim.minions[0]:
        m.s = RIVER + 1500.0
    with pytest.raises(InvariantError, match="map coordinates"):
        check_invariants(world)
    sim.invalidate()
    check_invariants(world)


@pytest.mark.parametrize("cache, fault", [("sight", "cached sight"), ("front", "cached front")])
def test_the_invariant_check_finds_each_lane_cache_that_disagrees_with_the_minions(cache, fault):
    world = minions_at(quiet_world({}), RIVER - 2000.0)
    sim = world.lanes["mid"]
    assert sim.stale() is None
    if cache == "sight":
        sim.sighted(0)
    else:
        sim.known_front(0, None)
    for m in sim.minions[0]:
        m.s = RIVER + 1500.0
    with pytest.raises(InvariantError, match=fault):
        check_invariants(world)
    sim.invalidate()
    check_invariants(world)
