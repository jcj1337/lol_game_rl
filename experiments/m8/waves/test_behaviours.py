"""What the M8 lane does with waves when champions act through the action table, and what it does not do.

The criteria are those of `docs/design/M8_foundation.md`, section 5.3, and they are provisional. Every wave test
runs on the five seeds of the results file. Six tests are strict expected failures. Each keeps in view a bar that
the lane does not meet. If one starts to pass, the suite fails until someone removes the marker on purpose.
"""

from dataclasses import replace

import pytest

from experiments.m8.waves import agents, capabilities, investigate, m7_tests
from experiments.m8.waves.capabilities import bounced
from riftgame.lanes import M7_LANE, M8_LANE, MINIONS
from riftgame.vision import Observation

SEEDS = capabilities.SEEDS
WORKERS = 6
WAVE_INTERVAL_S = MINIONS["interval_schedule"][0][1]
TOP_1, MID_1, MID_3, MID_6 = "top, level 1, from 0:00", "mid, level 1, from 0:00", "mid, level 3, from 2:30", "mid, level 6, from 6:00"
CARRY_3 = "carry alone, level 3, from 2:30"
ALONG_THE_LANE = replace(M8_LANE, straight_ranges=False)
M7_GRAPH = replace(M8_LANE, m7_map=True)


@pytest.fixture(scope="module")
def stacks():
    return capabilities.stacking((TOP_1, CARRY_3), seeds=SEEDS, workers=WORKERS)


@pytest.fixture(scope="module")
def holds():
    return capabilities.holding((MID_1,), surpluses=(2, 3), seeds=SEEDS, workers=WORKERS)


@pytest.fixture(scope="module")
def bounces():
    return capabilities.bounce((TOP_1, MID_1, MID_3), seeds=SEEDS, workers=WORKERS)


def test_the_port_reproduces_m7s_numbers_wherever_the_draw_key_is_the_same():
    names = ["S0 fight 6v6", "S0 fight 6v7 caster", "S1b undisturbed top", "S3b bounce top", "S5c k=3 hold",
             m7_tests.slow_push_name("top", "first contact", "thin 3 once"), m7_tests.slow_push_name("top", "red crash", "thin casters")]
    check = m7_tests.port_check(m7_tests.measure(M7_LANE, names, m7_tests.REPORT_DT))
    assert check["metrics_compared"] >= 50
    assert check["differing"] == []


def test_a_plan_reads_its_champions_observation_and_nothing_else():
    world = agents.staged(0, {"mid": 1})
    laner = agents.Laner(world, agents.seat_of(agents.BLUE, "mid"), agents.always("last_hit"))
    seen = []
    laner.plan = lambda view: seen.append(view) or ("last_hit", "wave")
    agents.play(world, "mid", [laner], 80.0)
    assert laner.act.__annotations__["o"] is Observation
    assert any(view.contact for view in seen) and not seen[0].contact


def test_a_champion_under_its_tower_gains_xp_and_an_absent_one_gains_none_after_it_left(stacks):
    """The two controls are different things: the old `absent` stood at the tower."""
    gaps = stacks["paired"][f"{TOP_1}, from own tower, opponent absent"]
    absent, under = (stacks["cases"][f"{TOP_1}, from own tower, opponent absent"][plan]["xp"] for plan in ("absent", "under tower"))
    assert under["min"] > absent["max"]
    assert all(plans["absent"]["largest_crash_peak"]["n"] == len(SEEDS) for plans in gaps.values())


def test_a_hard_push_in_mid_crashes_before_the_next_enemy_wave_can_reach_its_tower():
    contact = m7_tests.undisturbed("mid")(M8_LANE, 0, investigate.DT)[0]["first_contact_t"]
    red_wave_2_home = 2 * WAVE_INTERVAL_S + investigate.arrivals("mid", M8_LANE)["red"]["wave 2"]["own tower edge"]
    mid = capabilities.stacking((MID_1,), starts=("first contact",), reds=(False,), plans=("absent", "under tower", "push"), seeds=SEEDS, workers=WORKERS)
    push = mid["cases"][f"{MID_1}, from first contact, opponent absent"]["push"]
    assert push["first_crash_s"]["n"] == len(SEEDS)
    assert contact + push["first_crash_s"]["max"] < red_wave_2_home


# A regression pin on blue's side, chosen after the results. With the plan on red no plan accumulates in this setting
# (capabilities.json, sides), so it says nothing about how often accumulation appears.
@pytest.mark.xfail(strict=True, reason="a regression pin of campaign 4 that held at the 0.5 s tick; after campaign 5's in-tick lane fixes, at the research tick of 0.25 s, no plan accumulates reinforcements in this setting (handoff 009)")
def test_a_thinning_plan_brings_three_minions_from_each_of_two_waves_and_more_than_a_push_an_empty_lane_or_a_laner_under_its_tower(stacks):
    setting, plan = f"{CARRY_3}, from own tower, opponent absent", "thin 3, then last hit"
    assert plan in stacks["accumulates"][setting] and plan in stacks["delays"][setting]
    rows = stacks["cases"][setting]
    assert rows[plan]["largest_crash_second_wave"]["min"] >= capabilities.WAVE_SHARE
    assert rows[plan]["largest_crash_peak"]["min"] > max(rows[control]["largest_crash_peak"]["max"] for control in capabilities.STACK_CONTROLS)
    assert stacks["paired"][setting][plan]["push"]["largest_crash_peak"]["higher"] == len(SEEDS)


@pytest.mark.xfail(strict=True, reason="the slow-push drill of a level 1 top laner does not bring more minions than a hard push in every seed (handoff 007)")
def test_killing_the_three_casters_of_the_first_wave_and_then_last_hitting_accumulates_reinforcements(stacks):
    assert "thin 3, then last hit" in stacks["accumulates"][f"{TOP_1}, from first contact, opponent absent"]


@pytest.mark.xfail(strict=True, reason="against an opponent that last-hits no plan accumulates reinforcements in every seed (handoff 007)")
def test_reinforcements_also_accumulate_against_an_opponent_that_last_hits(stacks):
    assert any(plans for setting, plans in stacks["accumulates"].items() if setting.endswith("opponent last hits"))


@pytest.mark.xfail(strict=True, reason="a regression pin of campaign 4 that held at the 0.5 s tick; after campaign 5's in-tick lane fixes, at the research tick of 0.25 s, this hold no longer sustains control in this setting (handoff 009)")
def test_a_champion_that_holds_and_thins_keeps_a_larger_wave_out_of_its_towers_range_for_three_wave_cycles(holds):
    setting, plan = f"{MID_1}, 2 surplus casters, opponent last hits", "hold, thin over 1"
    held = holds["sustains"][setting][plan]
    assert held["cycles"] >= capabilities.SUSTAINED_CYCLES
    assert held["cycles"] > max(holds["cases"][setting][control]["held_cycles"]["max"] for control in capabilities.CONTROLS)
    assert holds["cases"][setting][plan]["champion_deaths"]["max"] == 0
    assert holds["paired"][setting][plan]["under tower"]["kept_out_s"]["higher"] == len(SEEDS)
    assert "hold, last hit" not in holds["sustains"][setting], "the hold that the old action table could express does not last there"


@pytest.mark.xfail(strict=True, reason="no hold lasts the 240 s of M7's freeze test: the longest lasts four wave cycles (handoff 007)")
def test_some_hold_lasts_all_eight_wave_cycles_of_the_run(holds):
    assert max(row["cycles"] for row in holds["longest"].values()) == capabilities.HOLD_RUN_S // capabilities.WAVE_S


@pytest.mark.xfail(strict=True, reason="no plan holds a first wave of 6:00 for a level 6 mid laner (handoff 007)")
def test_some_plan_sustains_control_for_a_level_6_mid_laner():
    late = capabilities.holding((MID_6,), surpluses=(3,), seeds=SEEDS, workers=WORKERS)
    assert any(late["sustains"].values())


@pytest.mark.xfail(strict=True, reason="a regression pin of campaign 4 that held at the 0.5 s tick; after campaign 5's in-tick lane fixes, at the research tick of 0.25 s, this hold no longer sustains control from the third wave (handoff 009)")
def test_a_hold_is_also_sustained_when_the_surplus_arrives_with_the_third_wave():
    later = capabilities.holding((MID_3,), surpluses=(3,), reds=(True,), seeds=SEEDS, workers=WORKERS, wave=capabilities.LATER_WAVE)
    assert "hold, thin" in later["sustains"][f"{MID_3}, 3 surplus casters, opponent last hits"]


@pytest.mark.parametrize("champion", [MID_1, pytest.param(MID_3, marks=pytest.mark.xfail(strict=True, reason=(
    "a regression pin of campaign 4 that held at the 0.5 s tick; after campaign 5's in-tick lane fixes, at the research tick of 0.25 s, the untouched mid lane at level 3 gets back past the centre first in some run (handoff 009)")))])
def test_after_a_crash_of_a_thinned_wave_mid_lane_comes_back_past_the_centre_before_an_untouched_lane_does(bounces, champion):
    row = bounces[f"{champion}, thin 3, then last hit"]
    assert bounced(row, len(SEEDS))
    assert row["front_back_past_centre_s"]["max"] <= capabilities.MID_BOUNCE_S


@pytest.mark.parametrize("plan", list(capabilities.BOUNCE_PLANS))
def test_after_a_crash_top_lane_comes_back_past_the_centre_before_an_untouched_lane_does(bounces, plan):
    row = bounces[f"{TOP_1}, {plan}"]
    assert bounced(row, len(SEEDS))
    assert row["back_sooner_than_untouched_s"]["min"] > WAVE_INTERVAL_S


@pytest.mark.parametrize("lane", ["top", "mid", "bot"])
def test_an_untouched_lane_keeps_its_front_at_the_centre_for_the_first_150_seconds(lane):
    row = investigate.untouched(lane, M8_LANE, SEEDS, until=150.0)
    assert row["front_on_blue_half_s"]["n"] == row["front_on_red_half_s"]["n"] == 0


def test_on_m7s_route_graph_an_untouched_top_lane_goes_to_blues_half_within_100_seconds_in_every_seed():
    """The defect that the M8 map removes, kept as a test of the diagnosis."""
    row = investigate.untouched("top", M7_GRAPH, SEEDS, until=150.0)
    assert row["front_on_blue_half_s"]["n"] == len(SEEDS) and row["front_on_blue_half_s"]["max"] <= 100.0


def test_a_bend_tips_an_untouched_lane_toward_its_own_side_and_a_bend_at_the_centre_or_no_bend_does_not():
    graph = investigate.lane_geometry("top", investigate.REFERENCE_MAP)
    seeds, centre = range(3), graph.centre

    def first(shape) -> tuple[int, int]:
        row = investigate.untouched("top", M8_LANE, seeds, until=150.0, geometry=shape)
        return round(row["blue_half_first"]["mean"] * len(seeds)), round(row["red_half_first"]["mean"] * len(seeds))

    assert first(replace(graph, bends=())) == (0, 0)
    assert first(investigate.one_bend(graph, centre, 46.0)) == (0, 0)
    assert first(investigate.one_bend(graph, centre - 295.0, 46.0)) == (len(seeds), 0)
    assert first(investigate.one_bend(graph, centre + 295.0, 46.0)) == (0, len(seeds))
    assert first(investigate.one_bend(graph, centre - 295.0, 10.0)) == (len(seeds), 0), "the angle does not decide it"


def test_a_sweep_sets_each_cases_range_across_clocks_beside_its_range_across_seeds_and_lists_each_verdict_that_flips():
    def clock(values, holds):
        row = {metric: {"a": {"p": values, "q": [1, 1, 1]}} if metric != "bounce_back_s_by_seed" else {"a": values} for metric in capabilities.BY_SEED}
        return row | {"verdicts": {"sustains": {"a": {"p": holds, "q": True}}}}

    out = capabilities.sensitivity({"0.25": clock([4, 6, 5], True), "0.5": clock([8, 8, 8], False)})
    crash = out["metrics"]["largest_crash_by_seed"]
    moved, still = crash["by_case"]["a, p"], crash["by_case"]["a, q"]
    assert moved["means"] == {"0.25": 5, "0.5": 8} and moved["range_across_clocks"] == 3 and moved["mean_range_across_seeds"] == 1
    assert moved["shift_from_reference"] == {"0.5": 3} and still["range_across_clocks"] == 0
    assert crash["cases_moving_more_across_clocks_than_across_seeds"] == 1 and crash["cases_equal_in_every_seed_at_every_clock"] == 1
    assert list(crash["largest_shifts"])[0] == "a, p"
    held = out["verdicts"]["sustains"]
    assert held["cases"] == 2 and held["unchanged"] == 1 and held["flips"] == {"a, p": {"0.25": True, "0.5": False}}


def test_with_the_plan_on_red_the_mirror_world_measures_reds_crash_and_reds_own_tower():
    blue, red = (capabilities.stacking_case((TOP_1, "first contact", False, "push", 0), team=team) for team in (agents.BLUE, agents.RED))
    for row in (blue, red):
        assert row["first_crash_s"] is not None and row["largest_crash_peak"] >= 3
        assert row["enemy_tower_damage"] > 0 and row["own_tower_damage"] == 0


def test_cast_times_and_missile_flight_lengthen_the_untouched_first_wave_fight():
    instant = replace(M8_LANE, attack_timing=False)
    for lane in ("mid", "top"):
        timed, at_once = (investigate.natural_fight(lane, rules, SEEDS)["alone_s"]["min"] for rules in (M8_LANE, instant))
        assert timed >= at_once + 1.5


def test_a_cap_on_melee_attackers_does_not_change_how_long_a_placed_fight_lasts():
    base = investigate.fights(M8_LANE)
    for cap in (1, 2, 3):
        capped = investigate.fights(replace(M8_LANE, melee_cap=cap))
        for label in base:
            assert abs(capped[label]["fight_s"] - base[label]["fight_s"]) <= 1.5
