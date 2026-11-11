import itertools

import pytest

from riftgame.map import RiftMap, load_map
from riftgame.ruleset import load

MAP = load_map()
RIFT = MAP.rift
RULES = load()
SIGHT = RULES["champions"]["sight_range"]


def walk(start, goal, route_units):
    """The position `route_units` of walking from node `start` toward node `goal`."""
    return RIFT.advance(RIFT.at(start), RIFT.at(goal), route_units)


def beside(lane, node, along=0.0):
    """The lane position nearest to `node`, moved `along` units toward the red base."""
    return RIFT.lane_pos(lane, RIFT.project_to_lane(lane, *RIFT.xy(RIFT.at(node))) + along)


JUNCTIONS = [
    ("mid_river", "blue_mid_t1", "top_river"),
    ("mid_river", "red_mid_t1", "bot_river"),
    ("top_corner", "blue_top_t1", "red_top_t1"),
    ("bot_corner", "red_bot_t1", "blue_bot_t1"),
    ("blue_mid_t2", "blue_mid_t1", "blue_wolves"),
    ("red_mid_t2", "red_mid_t1", "red_wolves"),
]


@pytest.mark.parametrize("node, arm, other_arm", JUNCTIONS)
def test_positions_on_two_arms_of_a_junction_see_each_other(node, arm, other_arm):
    a, b = walk(node, arm, 400), walk(node, other_arm, 400)
    assert a.edge != b.edge
    assert RIFT.distance(a, b) == pytest.approx(800)
    assert RIFT.separation(a, b) < 800
    assert RIFT.sees(a, b, SIGHT)


# Chord across the corner by the law of cosines on the node coordinates: the lane turns through
# 134 degrees at top_corner and 136 at bot_corner, so 600 out on each arm is 2 * 600 * sin(67 or 68).
CORNERS = [("top_corner", "blue_top_t1", "red_top_t1", 1105), ("bot_corner", "red_bot_t1", "blue_bot_t1", 1112)]


@pytest.mark.parametrize("corner, arm, other_arm, chord", CORNERS)
def test_the_straight_line_across_a_lane_corner_is_shorter_than_the_lane(corner, arm, other_arm, chord):
    a, b = walk(corner, arm, 600), walk(corner, other_arm, 600)
    assert RIFT.distance(a, b) == pytest.approx(1200)
    assert RIFT.separation(a, b) == pytest.approx(chord, abs=1)


@pytest.mark.parametrize("corner, arm, other_arm, _", CORNERS)
def test_an_attack_range_reaches_across_a_lane_corner_before_the_route_does(corner, arm, other_arm, _):
    attack_range = RULES["minions"]["caster"]["attack_range"]
    a, b = walk(corner, arm, 290), walk(corner, other_arm, 290)
    assert RIFT.separation(a, b) <= attack_range < RIFT.distance(a, b)


# 800 along mid lane and 800 map units (920 of walking) along the river from the crossing. The arms
# meet at 79 degrees on the blue side and 82 on the red side, so the chords are 1012 and 1046.
@pytest.mark.parametrize("lane_arm, river_arm, chord", [("blue_mid_t1", "top_river", 1012), ("red_mid_t1", "bot_river", 1046)])
def test_mid_lane_sees_into_the_river_where_the_walk_is_longer_than_sight(lane_arm, river_arm, chord):
    laner, in_river = walk("mid_river", lane_arm, 800), walk("mid_river", river_arm, 920)
    assert RIFT.separation(laner, in_river) == pytest.approx(chord, abs=1)
    assert RIFT.distance(laner, in_river) == pytest.approx(1720)
    assert RIFT.separation(laner, in_river) <= SIGHT < RIFT.distance(laner, in_river)
    assert RIFT.sees(laner, in_river, SIGHT)


ALCOVES = [("top", "blue_gromp"), ("mid", "blue_raptors"), ("bot", "red_gromp"), ("mid", "red_raptors")]


@pytest.mark.parametrize("lane, camp", ALCOVES)
@pytest.mark.parametrize("along", [-500, 0, 500])
def test_a_camp_behind_the_lane_wall_is_within_sight_range_but_not_seen(lane, camp, along):
    laner, monster = beside(lane, camp, along), RIFT.at(camp)
    assert RIFT.separation(laner, monster) <= SIGHT
    assert not RIFT.sees(laner, monster, SIGHT)
    assert RIFT.distance(laner, monster) > RIFT.separation(laner, monster)


@pytest.mark.parametrize("tower_node, camp", [("blue_mid_t1", "blue_raptors"), ("red_mid_t1", "red_raptors")])
def test_a_ward_reaches_over_the_raptor_wall_before_the_camp_comes_into_sight(tower_node, camp):
    ward_range = RULES["vision"]["ward_place_range"]
    monster = RIFT.at(camp)
    outside, inside = walk(camp, tower_node, 705), walk(camp, tower_node, 500)
    assert RIFT.separation(outside, monster) == pytest.approx(705 / 1.15)
    assert RIFT.separation(outside, monster) <= ward_range
    assert not RIFT.sees(outside, monster, SIGHT)
    assert RIFT.sees(inside, monster, SIGHT)


# 800 map units (920 of walking) out on each path. The paths leave the camp 101 degrees apart on the
# blue side and 105 on the red, so the chord is 1235 or 1268 and its middle is about 390 from both
# paths, outside a 250 half-width.
@pytest.mark.parametrize(
    "camp, exit_a, exit_b",
    [("blue_krugs", "blue_bot_t2", "blue_bot_t1"), ("red_krugs", "red_top_t2", "red_top_t1")],
)
def test_two_jungle_paths_do_not_see_across_the_terrain_between_them(camp, exit_a, exit_b):
    a, b = walk(camp, exit_a, 920), walk(camp, exit_b, 920)
    assert RIFT.separation(a, b) <= SIGHT
    assert not RIFT.sees(a, b, SIGHT)
    assert RIFT.sees(walk(camp, exit_a, 250), walk(camp, exit_b, 250), SIGHT)


def test_sight_is_symmetric_and_a_position_sees_itself():
    places = [
        beside("mid", "blue_raptors"),
        RIFT.at("blue_raptors"),
        walk("blue_mid_t1", "blue_raptors", 850),
        walk("mid_river", "top_river", 920),
        walk("mid_river", "blue_mid_t1", 800),
        walk("blue_krugs", "blue_bot_t2", 920),
        walk("blue_krugs", "blue_bot_t1", 920),
        RIFT.at("red_gromp"),
        beside("bot", "red_gromp", 500),
    ]
    answers = set()
    for radius in (RULES["vision"]["ward_place_range"], SIGHT, 3000):
        for a, b in itertools.combinations(places, 2):
            assert RIFT.sees(a, b, radius) == RIFT.sees(b, a, radius)
            assert RIFT.sight_clear(a, b) == RIFT.sight_clear(b, a)
            answers.add(RIFT.sees(a, b, radius))
    assert answers == {True, False}
    assert all(RIFT.sees(p, p, 0) for p in places)


@pytest.mark.parametrize("gap", [200, 1349, 1351, 3000])
def test_on_one_straight_edge_sight_is_the_radius_alone(gap):
    start = RIFT.lane_s("top", RIFT.at("blue_top_t2")) + 500
    a, b = RIFT.lane_pos("top", start), RIFT.lane_pos("top", start + gap)
    assert a.edge == b.edge
    assert RIFT.separation(a, b) == pytest.approx(gap)
    assert RIFT.sees(a, b, SIGHT) == (gap <= SIGHT)
    assert RIFT.sees(a, b, 5000)


def test_a_map_built_without_terrain_blocks_no_sight():
    nodes = {"west": (0, 0), "mid": (1000, 0), "north": (1000, 1000)}
    bare = RiftMap(nodes, [("west", "mid", 1.0), ("mid", "north", 1.0)], {})
    a, b = bare.at("west"), bare.at("north")
    assert bare.separation(a, b) == pytest.approx(2**0.5 * 1000)
    assert bare.distance(a, b) == pytest.approx(2000)
    assert bare.sees(a, b, 1500) and not bare.sees(a, b, 1400)
