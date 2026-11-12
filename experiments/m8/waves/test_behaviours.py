"""What the M8 lane does with waves when champions act through the action table, and what it does not do.

The criteria are those of `docs/design/M8_foundation.md`, section 5.3. Every wave test runs on the five seeds of
the results file. Eight tests are strict expected failures. Each keeps in view a bar that the lane does not meet.
If one starts to pass, the suite fails until someone removes the marker on purpose.
"""

from dataclasses import replace

import pytest

from experiments.m8.waves import capabilities, investigate, m7_tests
from experiments.m8.waves.capabilities import bounced
from riftgame.lanes import M7_LANE, M8_LANE, MINIONS

SEEDS = capabilities.SEEDS
WORKERS = 6
WAVE_INTERVAL_S = MINIONS["interval_schedule"][0][1]
TOP_1, MID_1, MID_3, MID_6 = "top, level 1, from 0:00", "mid, level 1, from 0:00", "mid, level 3, from 2:30", "mid, level 6, from 6:00"
ALONG_THE_LANE = replace(M8_LANE, straight_ranges=False)


@pytest.fixture(scope="module")
def stacks():
    return capabilities.stacking((TOP_1,), seeds=SEEDS, workers=WORKERS)


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


def test_a_hard_push_in_mid_crashes_before_the_next_enemy_wave_can_reach_its_tower():
    contact = m7_tests.undisturbed("mid")(M8_LANE, 0, investigate.DT)[0]["first_contact_t"]
    red_wave_2_home = 2 * WAVE_INTERVAL_S + investigate.arrivals("mid", M8_LANE)["red"]["wave 2"]["own tower edge"]
    mid = capabilities.stacking((MID_1,), starts=("first contact",), reds=(False,), plans=("absent", "push"), seeds=SEEDS, workers=WORKERS)
    push = mid["cases"][f"{MID_1}, from first contact, red absent"]["push"]
    assert push["first_crash_s"]["n"] == len(SEEDS)
    assert contact + push["first_crash_s"]["max"] < red_wave_2_home


def test_one_thinning_plan_brings_three_minions_from_each_of_two_waves_and_more_than_a_push_or_an_empty_lane_does(stacks):
    setting, plan = f"{TOP_1}, from own tower, red absent", "thin 3, then passive"
    assert plan in stacks["accumulates"][setting] and plan in stacks["delays"][setting]
    rows = stacks["cases"][setting]
    assert rows[plan]["largest_crash_second_wave"]["min"] >= capabilities.WAVE_SHARE
    assert rows[plan]["largest_crash_peak"]["min"] > max(rows[control]["largest_crash_peak"]["max"] for control in ("push", "absent"))


@pytest.mark.xfail(strict=True, reason="the slow-push drill brings 7 minions, one of them from the first wave, where a hard push brings 9 (handoff 006)")
def test_killing_the_three_casters_of_the_first_wave_and_then_last_hitting_accumulates_reinforcements(stacks):
    assert "thin 3, then last hit" in stacks["accumulates"][f"{TOP_1}, from first contact, red absent"]


@pytest.mark.xfail(strict=True, reason="against an opponent that last-hits no plan accumulates reinforcements in every seed, in any of 16 settings (handoff 006)")
def test_reinforcements_also_accumulate_against_an_opponent_that_last_hits(stacks):
    assert any(plans for setting, plans in stacks["accumulates"].items() if setting.endswith("red last hits"))


@pytest.mark.xfail(strict=True, reason="12 minions is a provisional count: the largest crash holds 11 (handoff 006)")
def test_some_plan_brings_12_minions_to_the_enemy_tower(stacks):
    assert stacks["crashes_of_12_or_more"]


def test_a_champion_that_holds_and_thins_keeps_a_larger_wave_out_of_its_towers_range_for_three_wave_cycles(holds):
    setting, plan = f"{MID_1}, 2 surplus casters, red last hits", "hold, thin over 1"
    held = holds["sustains"][setting][plan]
    assert held["cycles"] >= capabilities.SUSTAINED_CYCLES
    assert held["cycles"] > max(holds["cases"][setting][control]["held_cycles"]["max"] for control in capabilities.CONTROLS)
    assert holds["cases"][setting][plan]["champion_deaths"]["max"] == 0
    assert "hold, last hit" not in holds["sustains"][setting], "the hold that the old action table could express does not last there"


@pytest.mark.xfail(strict=True, reason="no hold lasts the 240 s of M7's freeze test: the longest lasts four wave cycles (handoff 006)")
def test_some_hold_lasts_all_eight_wave_cycles_of_the_run(holds):
    assert max(row["cycles"] for row in holds["longest"].values()) == capabilities.HOLD_RUN_S // capabilities.WAVE_S


@pytest.mark.xfail(strict=True, reason="no plan holds a wave of 6:00 for a level 6 mid laner (handoff 006)")
def test_some_plan_sustains_control_for_a_level_6_mid_laner():
    late = capabilities.holding((MID_6,), surpluses=(3,), seeds=SEEDS, workers=WORKERS)
    assert any(late["sustains"].values())


@pytest.mark.parametrize("champion", [MID_1, MID_3])
def test_after_a_crash_of_a_thinned_wave_mid_lane_comes_back_past_the_centre_before_an_untouched_lane_does(bounces, champion):
    row = bounces[f"{champion}, thin 3, then last hit"]
    assert bounced(row, len(SEEDS))
    assert row["front_back_past_centre_s"]["max"] <= capabilities.MID_BOUNCE_S


@pytest.mark.xfail(strict=True, reason="after a one-wave crash at 0:00 the tower clears the wave before the next enemy wave arrives, and mid resets to the centre (handoff 006)")
def test_after_a_hard_push_of_the_first_wave_mid_lane_comes_back_past_the_centre(bounces):
    assert bounced(bounces[f"{MID_1}, hard push"], len(SEEDS))


@pytest.mark.xfail(strict=True, reason="an untouched top lane goes to blue's half before the crashed one does, so the crash cannot be said to cause it (handoff 006)")
def test_after_a_crash_top_lane_comes_back_past_the_centre_before_an_untouched_lane_does(bounces):
    assert bounced(bounces[f"{TOP_1}, thin 3, then last hit"], len(SEEDS))


def test_an_untouched_lane_keeps_its_front_at_the_centre_in_mid_and_with_ranges_along_the_lane_in_top():
    for lane, rules in (("mid", M8_LANE), ("top", ALONG_THE_LANE)):
        row = investigate.untouched(lane, rules, SEEDS, until=150.0)
        assert row["front_on_blue_half_s"]["n"] == row["front_on_red_half_s"]["n"] == 0


@pytest.mark.xfail(strict=True, reason="with straight-line ranges the one sharp corner of the route graph tips an untouched top lane toward blue's tower (handoff 006)")
def test_an_untouched_top_lane_keeps_its_front_at_the_centre_for_the_first_150_seconds():
    row = investigate.untouched("top", M8_LANE, SEEDS, until=150.0)
    assert row["front_on_blue_half_s"]["n"] == row["front_on_red_half_s"]["n"] == 0


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
