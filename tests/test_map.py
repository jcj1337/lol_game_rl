import math

import pytest

from riftgame.map import Pos, load_map
from riftgame.ruleset import load

MAP = load_map()
RIFT = MAP.rift


def tower(name):
    return next(t for t in MAP.towers if t.name == name)


# Independent derivation from the game's minion paths (spawn point, barracks, path polyline),
# recorded in the M7 map research. The route graph must agree within 4 percent.
@pytest.mark.parametrize(
    "lane, reference_units",
    [("top", 10184), ("mid", 8095), ("bot", 10333)],
)
def test_fountain_to_outer_tower_matches_the_reference_walk(lane, reference_units):
    fountain = RIFT.at("blue_fountain")
    site = RIFT.lane_pos(lane, tower(f"blue_{lane}_outer").s)
    assert RIFT.distance(fountain, site) == pytest.approx(reference_units, rel=0.04)


def test_fountain_to_fountain_through_mid_matches_the_reference_walk():
    assert RIFT.distance(RIFT.at("blue_fountain"), RIFT.at("red_fountain")) == pytest.approx(19791, rel=0.02)


@pytest.mark.parametrize("lane, reference_seconds", [("mid", 21.8), ("top", 31.2), ("bot", 31.4)])
def test_first_waves_meet_when_the_reference_geometry_says(lane, reference_seconds):
    gap = MAP.minion_spawn_s[("red", lane)] - MAP.minion_spawn_s[("blue", lane)]
    seconds = gap / 2 / load()["minions"]["move_speed"]
    assert seconds == pytest.approx(reference_seconds, rel=0.04)


def test_side_lanes_are_the_same_length_and_longer_than_mid():
    lanes = RIFT.lanes
    assert lanes["top"].length == pytest.approx(lanes["bot"].length, rel=0.01)
    assert lanes["mid"].length < 0.8 * lanes["top"].length


def test_each_lane_has_three_towers_per_team_ordered_from_base_outward():
    for lane in ("top", "mid", "bot"):
        blue = [tower(f"blue_{lane}_{tier}").s for tier in ("inhibitor", "inner", "outer")]
        red = [tower(f"red_{lane}_{tier}").s for tier in ("outer", "inner", "inhibitor")]
        assert blue == sorted(blue) and red == sorted(red)
        assert blue[-1] < RIFT.lanes[lane].length / 2 < red[0]


def test_twelve_camps_three_per_quadrant_all_known_to_the_ruleset():
    kinds = load()["camps"]
    assert len(MAP.camps) == 12
    for team in ("blue", "red"):
        buff_quadrant = {MAP.camps[f"{team}_{c}"] for c in ("gromp", "blue", "wolves")}
        red_quadrant = {MAP.camps[f"{team}_{c}"] for c in ("raptors", "red", "krugs")}
        assert buff_quadrant == {"gromp", "blue_sentinel", "murk_wolves"}
        assert red_quadrant == {"raptors", "red_brambleback", "krugs"}
    assert all(kind in kinds for kind in MAP.camps.values())


def test_distance_is_symmetric_and_obeys_the_triangle_inequality():
    names = ["blue_fountain", "blue_gromp", "mid_river", "bot_river", "red_krugs", "red_bot_t1"]
    points = [RIFT.at(n) for n in names]
    for a in points:
        for b in points:
            assert RIFT.distance(a, b) == pytest.approx(RIFT.distance(b, a))
            for c in points:
                assert RIFT.distance(a, c) <= RIFT.distance(a, b) + RIFT.distance(b, c) + 1e-6


def test_walking_arrives_in_distance_over_speed_and_never_overshoots():
    start, dest = RIFT.at("blue_fountain"), RIFT.at("red_krugs")
    total = RIFT.distance(start, dest)
    speed, pos, ticks = 340.0, start, 0
    while pos != dest:
        before = RIFT.distance(pos, dest)
        pos = RIFT.advance(pos, dest, speed)
        ticks += 1
        assert RIFT.distance(pos, dest) == pytest.approx(max(0.0, before - speed), abs=1e-6)
    assert ticks == math.ceil(total / speed)


def test_a_redirect_continues_from_the_current_position():
    start = RIFT.at("blue_fountain")
    toward_top = RIFT.at("blue_top_t1")
    pos = start
    for _ in range(10):
        pos = RIFT.advance(pos, toward_top, 340.0)
    walked = RIFT.distance(start, pos)
    assert walked == pytest.approx(3400.0)
    new_dest = RIFT.at("blue_bot_t1")
    remaining = RIFT.distance(pos, new_dest)
    assert remaining <= walked + RIFT.distance(start, new_dest)
    after = RIFT.advance(pos, new_dest, 340.0)
    assert RIFT.distance(after, new_dest) == pytest.approx(remaining - 340.0)


def test_lane_coordinate_round_trips_and_is_none_off_lane():
    for s in (0.0, 1234.5, 8000.0, RIFT.lanes["top"].length):
        assert RIFT.lane_s("top", RIFT.lane_pos("top", s)) == pytest.approx(s)
    jungle = Pos(RIFT.at("blue_gromp").edge, 10.0)
    assert RIFT.lane_s("top", jungle) is None or RIFT.lane_s("mid", jungle) is None


def test_lane_distance_equals_lane_coordinate_difference():
    a, b = RIFT.lane_pos("mid", 3000.0), RIFT.lane_pos("mid", 9000.0)
    assert RIFT.distance(a, b) == pytest.approx(6000.0)
