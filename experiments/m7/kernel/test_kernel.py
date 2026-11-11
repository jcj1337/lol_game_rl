import numpy as np
import pytest

from experiments.m7.kernel import scenarios
from experiments.m7.kernel.lanes import RealLane
from experiments.m7.kernel.observe import N_ACTIONS, OBS_SIZE, actions, encode, legal_mask, observe, run
from experiments.m7.kernel.policy import scripted
from experiments.m7.kernel.world import CAMPS, RECALL_S, Kind, R, World


@pytest.fixture(scope="module")
def q1():
    return scenarios.timing()


@pytest.fixture(scope="module")
def q2():
    return scenarios.fights()


@pytest.fixture(scope="module")
def q3():
    return scenarios.information()


@pytest.fixture(scope="module")
def q4():
    return scenarios.snapshots()


def test_fixed_intents_give_one_trajectory_at_decision_intervals_1_5_10(q1):
    assert q1["a_ticks_compared"] == 300
    assert q1["a_identical_to_interval_1"] == {5: True, 10: True}
    assert q1["a_reactive_policy_differs_between_interval_1_and_10"], "the digest must be able to tell trajectories apart"


def test_move_replaced_mid_route_continues_from_the_current_position(q1):
    assert q1["b_walked_units"] == pytest.approx(q1["b_speed_times_time"])
    assert q1["b_first_step_on_new_route_units"] == pytest.approx(q1["b_speed_times_time"] / 30)


def test_recall_restarted_after_a_cancel_takes_the_whole_channel_again(q1):
    assert RECALL_S == 8.5
    assert q1["c_uninterrupted_s"]["dt_0.5"] == 8.5
    assert q1["c_cancelled_at_7s_then_restarted"]["seconds_from_first_cast"] == 7.0 + 8.5
    assert q1["c_uninterrupted_s"]["dt_1.0"] == 9.0, "a 1 s tick rounds the 8.5 s channel up"


def test_damage_during_the_channel_cancels_the_recall(q1):
    hit = q1["d_hit_once_at_5s"]
    assert hit["hp_lost"] > 0 and hit["channel_s"] == 0.0
    assert hit["seconds_from_first_cast"] == 5.5 + 8.5


def outcomes_split_on(rows: list[dict], factor: str) -> bool:
    groups: dict[tuple, set] = {}
    for r in rows:
        others = tuple(r[k] for k in ("runner_speed_edge", "lockdown", "units_to_own_tower") if k != factor)
        groups.setdefault(others, set()).add(r["outcome"])
    return any(len(outcomes) == 2 for outcomes in groups.values())


def test_escape_is_neither_guaranteed_nor_impossible_and_depends_on_speed_slow_and_distance(q2):
    assert q2["a_escapes"] > 0 and q2["a_deaths"] > 0
    for factor in ("runner_speed_edge", "lockdown", "units_to_own_tower"):
        assert outcomes_split_on(q2["a_retreat_at_half_hp"], factor), factor


def test_an_ally_who_walks_in_soon_enough_turns_a_lost_duel(q2):
    assert q2["b_alone"]["a_dead"] and not q2["b_alone"]["foe_dead"]
    assert 0 < q2["b_largest_ally_distance_side_wins"] < 8000, "the threshold must fall inside the sweep"


def test_the_defenders_tower_reverses_the_same_duel(q2):
    open_lane, under_tower = q2["c_same_duel"]
    assert open_lane["winner"] == "attacker" and under_tower["winner"] == "defender"


def test_a_gank_is_more_dangerous_far_from_the_laners_own_tower(q2):
    ganks = {(g["laner_at"], g["decision_interval_ticks"], g["laner_start_hp"]): g for g in q2["d_gank"]}
    for (place, interval, hp), far in ganks.items():
        if place == "enemy outer tower":
            near = ganks["own outer tower", interval, hp]
            assert near["laner_survives"] and far["laner_lowest_hp"] < near["laner_lowest_hp"]
    assert any(not g["laner_survives"] for g in q2["d_gank"])


def test_blue_observations_are_identical_when_only_hidden_state_differs(q3):
    hidden = q3["a_hidden_state"]
    assert hidden["worlds_differ"] and hidden["hidden_things_stayed_unseen_by_blue"]
    assert hidden["blue_observation_mismatches"] == 0
    assert hidden["blue_observations_differing_after_reveal"] == 5


def test_last_seen_record_freezes_when_the_enemy_leaves_vision(q3):
    seen = q3["b_last_seen"]
    assert seen["record_tick_20s_later"] == seen["last_visible_tick"] and seen["record_pos_is_last_visible_pos"]
    assert seen["units_moved_since"] > 0 and not seen["observation_visible"] and seen["observation_age_s"] >= 20


def test_a_pursuer_whose_target_is_in_fog_goes_to_the_last_seen_spot_only(q3):
    chase = q3["e_pursuit_of_a_target_in_fog"]
    assert not chase["target_visible"]
    assert chase["pursuer_units_from_last_seen_spot"] == 0 and chase["pursuer_units_from_true_position"] > 5000


def test_camp_timer_is_known_from_a_seen_clear_or_learned_in_the_final_window(q3):
    gromp, buff = q3["c_camp_timers"]
    assert (gromp["window_s"], buff["window_s"]) == (R["camps"]["timer_window_other_s"], R["camps"]["timer_window_buff_s"])
    for case, kind in ((gromp, "gromp"), (buff, "blue_sentinel")):
        assert case["respawn_s"] == case["clear_s"] + R["camps"][kind]["respawn_s"]
        assert case["clearing_team_knows_s"] == case["respawn_s"]
        assert case["enemy_knows_on_first_look_s"] is None
        assert case["enemy_learns_at_s"] == case["respawn_s"] - case["window_s"]
        assert case["enemy_learns_s"] == case["respawn_s"]


def test_ward_reveals_a_hidden_enemy_for_exactly_its_duration(q3):
    ward = q3["d_ward"]
    assert ward["hidden_before_ward"] and ward["hidden_after_expiry"]
    assert ward["revealed_for_s"] == R["vision"]["ward_duration_s"][0]
    assert ward["charges_left"] == R["vision"]["ward_charges"] - 1


def test_restored_snapshot_replays_the_same_digest_every_tick(q4):
    assert q4["a_ticks_replayed"] == 300 and q4["a_ticks_matching"] == 300


def test_changing_one_top_intent_leaves_the_bot_lane_untouched_for_20_seconds(q4):
    assert q4["b_top_lane_first_differs_after_s"] is not None and q4["b_top_lane_first_differs_after_s"] < 20
    bot = q4["b_bot_lane_first_differs_after_s"]
    assert bot is None or bot >= 20


def test_vector_and_mask_have_fixed_shape_and_the_scripted_policy_stays_legal():
    w = World(seed=2)
    for _ in range(60):
        for c in w.champs:
            o = observe(w, c.id)
            vector, mask = encode(o), legal_mask(o)
            assert vector.shape == (OBS_SIZE,) and vector.dtype == np.float32 and np.isfinite(vector).all()
            table = actions(c.team)
            assert mask.shape == (N_ACTIONS,) == (len(table),)
            assert mask[table.index(scripted(o))]
            visible = {e.id for e in o.enemies if e is not None and e.visible}
            for legal, action in zip(mask, table):
                if action.kind == Kind.FIGHT:
                    assert legal == (action.target in visible)
                elif action.kind == Kind.CAMP:
                    assert legal, "walking to an empty camp is a legal mistake"
        run(w, scripted, 10)
    assert {a.target for a in actions(0) if a.kind == Kind.CAMP} == set(CAMPS)


def test_real_wave_model_keeps_interval_invariance_replay_and_lane_independence():
    timing, snap = scenarios.interval_invariance(RealLane), scenarios.snapshots(RealLane)
    assert timing["a_identical_to_interval_1"] == {5: True, 10: True}
    assert timing["a_reactive_policy_differs_between_interval_1_and_10"]
    assert snap["a_ticks_matching"] == 300
    assert snap["b_top_lane_first_differs_after_s"] is not None and snap["b_top_lane_first_differs_after_s"] < 20
    assert snap["b_bot_lane_first_differs_after_s"] is None or snap["b_bot_lane_first_differs_after_s"] >= 20
