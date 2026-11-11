"""What the M8 lane does with waves, and what it does not do.

Three tests are strict expected failures. Each keeps a required behaviour that the reference constants do not
produce in view. If one starts to pass, the suite fails until someone removes the marker on purpose.
"""

from dataclasses import replace

import pytest

from experiments.m8.waves import investigate, m7_tests
from riftgame.lanes import M7_LANE, M8_LANE, MINIONS

SEEDS = range(2)
WAVE_INTERVAL_S = MINIONS["interval_schedule"][0][1]
SLOWER_FIGHTS = replace(M8_LANE, minion_damage_scale=0.7)
FROM_CONTACT = "top, from first contact, red absent"
UNRESOLVED = "on the reference constants an advantaged wave wins fast and dies at the tower before its reinforcement arrives (handoff 005)"


@pytest.fixture(scope="module")
def plans():
    """Ten plans, both lanes, both starts, the opponent absent or last-hitting."""
    return investigate.stacking(M8_LANE, seeds=SEEDS)


@pytest.fixture(scope="module")
def top_plans(plans):
    return plans


def freeze_verdict(rules):
    return investigate.holding(rules, seeds=SEEDS, laners=("placeholder laner",), aligned_state=False)["placeholder laner"]["m7_built_state"]


def test_the_port_reproduces_m7s_numbers_wherever_the_draw_key_is_the_same():
    names = ["S0 fight 6v6", "S0 fight 6v7 caster", "S1b undisturbed top", "S3b bounce top", "S5c k=3 hold",
             m7_tests.slow_push_name("top", "first contact", "thin 3 once"), m7_tests.slow_push_name("top", "red crash", "thin casters")]
    check = m7_tests.port_check(m7_tests.measure(M7_LANE, names, m7_tests.REPORT_DT))
    assert check["metrics_compared"] >= 50
    assert check["differing"] == []


def test_a_hard_push_crashes_before_the_next_enemy_wave_can_reach_its_tower(top_plans):
    contact = m7_tests.undisturbed("top")(M8_LANE, 0, investigate.DT)[0]["first_contact_t"]
    red_wave_2_home = 2 * WAVE_INTERVAL_S + investigate.arrivals("top", M8_LANE)["red"]["wave 2"]["own tower edge"]
    push = top_plans["cases"][FROM_CONTACT]["push"]
    assert contact + push["first_crash_s"]["max"] < red_wave_2_home
    assert push["first_crash_peak"]["min"] == 6


@pytest.mark.parametrize("plan", ["thin 1, then last hit", "thin 3, then last hit", "thin every caster"])
def test_in_top_lane_from_first_contact_a_thinned_wave_crashes_later_than_a_hard_push_and_holds_minions_of_two_waves(top_plans, plan):
    rows = top_plans["cases"][FROM_CONTACT]
    push, thinned = rows["push"], rows[plan]
    assert thinned["first_crash_s"]["min"] > push["first_crash_s"]["max"]
    assert thinned["first_crash_waves"]["min"] == 2
    assert thinned["first_crash_peak"]["min"] > push["first_crash_peak"]["max"]


@pytest.mark.xfail(strict=True, reason=UNRESOLVED)
def test_some_plan_in_some_lane_brings_two_stacked_waves_to_the_enemy_tower(plans):
    assert plans["plans_with_a_two_wave_stack"]


@pytest.mark.xfail(strict=True, reason=UNRESOLVED)
def test_some_holding_plan_passes_m7s_freeze_test():
    assert freeze_verdict(M8_LANE)["freeze"]


def test_stacking_and_holding_both_appear_once_an_even_fight_outlasts_the_wave_interval():
    assert investigate.fights(M8_LANE)["6v6"]["fight_s"] < WAVE_INTERVAL_S < investigate.fights(SLOWER_FIGHTS)["6v6"]["fight_s"]
    stacked = investigate.stacking(SLOWER_FIGHTS, lanes=("top",), reds=(False,), seeds=SEEDS)
    assert stacked["plans_with_a_two_wave_stack"]
    assert stacked["largest_crash_of_a_plan_that_is_not_a_push"]["waves"] >= 2
    assert freeze_verdict(SLOWER_FIGHTS)["freeze"]


def test_a_cap_on_melee_attackers_does_not_change_how_long_a_fight_lasts():
    base = investigate.fights(M8_LANE)
    for cap in (1, 2, 3):
        capped = investigate.fights(replace(M8_LANE, melee_cap=cap))
        for label in base:
            assert abs(capped[label]["fight_s"] - base[label]["fight_s"]) <= 1.5


@pytest.mark.parametrize("lane", ["top", "bot"])
def test_a_crashed_side_lane_comes_back_past_the_centre_within_120_seconds(lane):
    row = investigate.bounce(M8_LANE, seeds=SEEDS, lanes=(lane,))[lane]
    assert row["bounced_m7"]["min"] == 1
    assert row["red_wave_at_blue_tower_s"]["max"] <= 120


@pytest.mark.xfail(strict=True, reason="mid lane has no speed rule, and its front needs about 150 s to come back (handoff 005)")
def test_a_crashed_mid_lane_comes_back_past_the_centre_within_120_seconds():
    assert investigate.bounce(M8_LANE, seeds=SEEDS, lanes=("mid",))["mid"]["bounced_m7"]["min"] == 1
