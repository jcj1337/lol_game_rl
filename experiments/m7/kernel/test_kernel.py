import numpy as np
import pytest

from experiments.m7.kernel import scenarios
from experiments.m7.kernel.lanes import RealLane
from experiments.m7.kernel.observe import MODES, N_ACTIONS, NODES, OBS_SIZE, Leash, actions, encode, leash, legal_mask, observe, run
from experiments.m7.kernel.policy import scripted
from experiments.m7.kernel.profiles import ROAM_CAP_S, ROAM_REFILL
from experiments.m7.kernel.world import CAMPS, HOLD, KEEP, RECALL, RECALL_S, RIFT, Duty, Intent, Kind, Outcome, R, World, on_lane


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


@pytest.fixture(scope="module")
def role():
    return scenarios.role_duty()


def assert_interval_contract(timing: dict) -> None:
    assert timing["a_ticks_compared"] == 300
    assert timing["a_interval_n_equals_interval_1_with_keep"] == {2: True, 4: True, 10: True}
    for n, ended in timing["a_intents_ended_in_the_window"].items():
        assert {"CLEARED", "ABSENT", "RECALLED", "PLACED"} <= set(ended), f"orders must end inside the window at interval {n}"
    assert timing["a_reactive_policy_differs_between_interval_1_and_10"], "the digest must be able to tell trajectories apart"
    assert timing["a_fixed_orders_differ_between_interval_1_and_10"], "a champion whose order ended waits for its next decision"


def test_a_run_at_interval_n_equals_a_run_at_interval_1_that_keeps_between_decisions(q1):
    assert_interval_contract(q1)


def test_keep_and_a_repeated_action_leave_progress_alone_and_another_action_discards_it():
    w = scenarios.staged({scenarios.BLUE_TOP: scenarios.top(11000.0)}, dt=0.5)
    me = w.champs[scenarios.BLUE_TOP]
    w.submit(me.id, RECALL)
    for action in (KEEP, RECALL):
        w.step()
        progress = me.channel
        w.submit(me.id, action)
        assert me.intent == RECALL and me.channel == progress > 0
    w.submit(me.id, HOLD)
    assert me.intent == HOLD and me.channel == 0.0


def test_an_ended_intent_leaves_the_champion_holding_until_it_gets_a_new_action():
    w = scenarios.staged({scenarios.BLUE_TOP: scenarios.top(6000.0)})
    me = w.champs[scenarios.BLUE_TOP]
    w.submit(me.id, Intent(Kind.MOVE, scenarios.top(6500.0)))
    for _ in range(2):
        w.step()
    assert (me.outcome, me.outcome_tick, me.intent, me.pos) == (Outcome.ARRIVED, 1, HOLD, scenarios.top(6500.0))
    seen = observe(w, me.id).me
    assert (seen.outcome, seen.outcome_age_s) == (Outcome.ARRIVED, 1.0)
    for _ in range(10):
        w.submit(me.id, KEEP)
        w.step()
    assert me.pos == scenarios.top(6500.0) and me.outcome_tick == 1


def test_a_fight_cannot_start_against_an_enemy_out_of_view():
    w = scenarios.staged({scenarios.BLUE_TOP: scenarios.top(6000.0)})
    with pytest.raises(ValueError):
        w.submit(scenarios.BLUE_TOP, scenarios.fight(scenarios.RED_TOP))


def test_a_champion_that_dies_drops_its_intent_and_its_killer_records_the_kill():
    w = scenarios.staged({scenarios.BLUE_TOP: scenarios.top(11000.0), scenarios.RED_TOP: scenarios.top(11100.0)})
    loser, winner = w.champs[scenarios.BLUE_TOP], w.champs[scenarios.RED_TOP]
    loser.hp = 1.0
    w.submit(loser.id, Intent(Kind.FARM, ("top", "push")))
    w.submit(winner.id, scenarios.fight(loser.id))
    w.step()
    assert (loser.outcome, loser.intent) == (Outcome.DIED, HOLD)
    assert (winner.outcome, winner.intent) == (Outcome.KILLED, HOLD)
    while loser.respawn_tick >= 0:
        w.step()
    assert loser.intent == HOLD and loser.hp == loser.max_hp


def test_move_replaced_mid_route_continues_from_the_current_position(q1):
    assert q1["b_walked_units"] == pytest.approx(q1["b_speed_times_time"])
    assert q1["b_first_step_on_new_route_units"] == pytest.approx(q1["b_speed_times_time"] / 30)


def test_recall_restarted_after_a_cancel_takes_the_whole_channel_again(q1):
    assert RECALL_S == 8.5
    assert q1["c_uninterrupted"]["dt_0.5"] == {"seconds_from_first_cast": 8.5, "seconds_from_last_cast": 8.5,
                                               "outcome_at_fountain": "RECALLED"}
    assert q1["c_cancelled_at_7s_then_restarted"]["seconds_from_first_cast"] == 7.0 + 8.5
    assert q1["c_uninterrupted"]["dt_1.0"]["seconds_from_first_cast"] == 9.0, "a 1 s tick rounds the 8.5 s channel up"


def test_damage_during_the_channel_ends_the_recall_and_it_does_not_restart_by_itself(q1):
    hit = q1["d_hit_once_at_5s"]
    assert hit["hp_lost"] > 0 and hit["channel_s"] == 0.0
    assert (hit["outcome"], hit["outcome_s"], hit["intent_after"]) == ("INTERRUPTED", 5.0, "HOLD")
    assert not hit["at_fountain_after_17s_without_a_new_order"]
    assert hit["seconds_from_last_cast"] == 8.5 and hit["outcome_at_fountain"] == "RECALLED"


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


def test_a_pursuer_whose_target_is_in_fog_goes_to_the_last_seen_spot_and_never_reads_the_true_position(q3):
    chase = q3["e_pursuit_of_a_target_in_fog"]["target_stays_in_fog"]
    assert not chase["target_visible"] and chase["last_seen_pos_is_where_the_target_stood"]
    assert chase["pursuer_units_from_last_seen_spot"] == pytest.approx(chase["pursuer_attack_range"])
    assert chase["pursuer_units_from_true_position"] > 5000
    assert chase["same_path_with_the_target_hidden_elsewhere"]


def test_a_pursuer_that_reaches_the_last_seen_spot_without_seeing_the_target_ends_with_lost(q3):
    chase = q3["e_pursuit_of_a_target_in_fog"]["target_stays_in_fog"]
    assert (chase["outcome"], chase["intent_after"]) == ("LOST", "HOLD")
    assert chase["outcome_s"] == chase["arrived_s"] + 1.0, "it looks once from the spot before it gives up"


def test_a_target_that_reappears_before_the_pursuer_arrives_is_fought_again_with_no_outcome(q3):
    chase = q3["e_pursuit_of_a_target_in_fog"]["target_reappears_before_arrival"]
    assert chase["units_from_last_seen_spot_when_the_target_reappeared"] > 175.0
    assert (chase["outcome"], chase["intent"]) == ("NONE", "FIGHT") and chase["target_hp_lost"] > 0


SEEN_BY_BOTH_SIDES = ("pos", "hp", "dead")


def test_a_fight_gives_the_same_positions_and_health_whichever_side_the_code_visits_first(q2):
    for name, case in q2["e_seat_order"].items():
        assert case["same_length"] and case["ended_in_a_death"], name
        assert not [d for d in case["differences"] if d["field"] in SEEN_BY_BOTH_SIDES], name


@pytest.mark.xfail(strict=True, reason="when both fighters die on one tick, first blood and the kill XP go to whoever "
                                       "killed the champion that the code visits first. Reported to the parent, not fixed.")
def test_kill_rewards_are_the_same_whichever_side_the_code_visits_first(q2):
    assert not [d for case in q2["e_seat_order"].values() for d in case["differences"]]


def test_camp_timer_is_known_from_a_seen_clear_or_learned_in_the_final_window(q3):
    gromp, buff = q3["c_camp_timers"]
    assert (gromp["window_s"], buff["window_s"]) == (R["camps"]["timer_window_other_s"], R["camps"]["timer_window_buff_s"])
    for case, kind in ((gromp, "gromp"), (buff, "blue_sentinel")):
        assert case["respawn_s"] == case["clear_s"] + R["camps"][kind]["respawn_s"]
        assert case["clearing_team_knows_s"] == case["respawn_s"]
        assert case["enemy_knows_on_first_look_s"] is None
        assert case["enemy_learns_at_s"] == case["respawn_s"] - case["window_s"]
        assert case["enemy_learns_s"] == case["respawn_s"]
        assert case["ticks_ended_absent_before_the_spawn"] > 0 and case["outcome_at_clear"] == "CLEARED"


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
                    assert legal == (leash(o.me) == Leash.NONE), "walking to an empty camp is a legal mistake"
        run(w, scripted, 10)
    assert {a.target for a in actions(0) if a.kind == Kind.CAMP} == set(CAMPS)


def soaks(role: dict, *policies: str):
    for clock in role["a_soak"].values():
        for name in policies:
            yield clock[name]


def laners(soak: dict) -> list[dict]:
    return [c for c in soak["champions"] if c["role"] != "jungle"]


def test_a_laner_that_leaves_whenever_it_may_roams_no_more_than_the_refill_rate_allows(role):
    limit = ROAM_REFILL / (1 + ROAM_REFILL)
    assert role["share_limit"] == limit == 0.2
    for soak in soaks(role, "abandoner_nearest_exit", "abandoner_anywhere"):
        decision_s = soak["decision_every_s"]
        for c in laners(soak):
            window = c["window_after_exhaustion_s"]
            assert window >= 600, "the share is measured over at least ten game minutes after the first allowance ran out"
            # From the first tick at zero, every roamed second is paid for by 1 / ROAM_REFILL seconds on the lane, except
            # the debt still open at the end. The debt is under one decision interval, because the mask sends the laner
            # home at its first decision after the allowance runs out.
            assert 0.15 < c["roaming_share_after_exhaustion"] <= limit + decision_s / ((1 + ROAM_REFILL) * window)
            assert c["roaming_share"] <= limit + (ROAM_CAP_S + decision_s) / ((1 + ROAM_REFILL) * soak["game_s"])
            assert c["longest_roam_between_lane_visits_s"] <= ROAM_CAP_S + decision_s
            assert c["lowest_allowance_s"] > -decision_s
            assert c["illegal_choices"] == 0


def test_an_allowance_that_stopped_at_zero_would_let_the_same_laner_roam_past_the_limit(role):
    """Why the kernel keeps a debt: each new roam would overrun by up to one decision interval and never pay for it."""
    for clock in role["a_lowest_and_highest_laner_share_if_the_allowance_stopped_at_zero"].values():
        for shares in clock.values():
            assert shares["roaming_share_after_exhaustion"][0] > role["share_limit"] + 0.01


def test_no_champion_moves_faster_than_its_speed_except_by_dying_or_recalling(role):
    for soak in soaks(role, "abandoner_nearest_exit", "abandoner_anywhere", "scripted"):
        assert all(c["largest_step_over_speed"] <= 1 + 1e-9 for c in soak["champions"])
    for soak in soaks(role, "scripted"):
        assert all(c["deaths_or_recalls"] > 0 for c in soak["champions"]), "the exception must occur in the run"


def test_a_jungler_is_never_restricted_and_has_no_allowance_to_spend(role):
    for soak in soaks(role, "abandoner_nearest_exit", "abandoner_anywhere", "scripted"):
        for c in soak["champions"]:
            if c["role"] == "jungle":
                assert c["always_unrestricted"] and c["in_state_s"]["FREE"] == soak["game_s"]
                assert c["lowest_allowance_s"] == c["final_allowance_s"] == ROAM_CAP_S
            else:
                assert not c["always_unrestricted"] and c["in_state_s"]["FREE"] == 0


def test_the_scripted_policy_stays_inside_the_role_for_thirty_minutes(role):
    for soak in soaks(role, "scripted"):
        assert sum(c["illegal_choices"] for c in soak["champions"]) == 0
        assert min(c["lowest_allowance_s"] for c in soak["champions"]) > 0


def test_a_roam_of_realistic_length_is_legal_from_start_to_finish(role):
    roam = role["d_realistic_roam"]
    assert roam["decisions"] == roam["legal_decisions"] > 0
    assert roam["back_on_lane_s"] - roam["arrived_s"] >= 15.0 + roam["walk_units_each_way_off_the_lane"] / 335.0
    assert roam["seconds_charged_as_roaming"] >= 15.0 and 0 < roam["allowance_left_s"] < ROAM_CAP_S


def legal_actions(w: World, cid: int) -> set:
    o = observe(w, cid)
    return {a for a, legal in zip(actions(cid // 5), legal_mask(o)) if legal}


def test_the_mask_keeps_a_laner_with_no_allowance_on_its_lane_and_sends_a_stray_one_home():
    mid_river = RIFT.at("mid_river")
    beside_lane = RIFT.advance(mid_river, RIFT.at("top_river"), 300.0)
    river = RIFT.lane_s("mid", mid_river)
    blue_mid, red_mid, red_jungle = scenarios.BLUE_MID, scenarios.RED_MID, scenarios.RED_JUNGLE
    w = scenarios.staged({blue_mid: RIFT.lane_pos("mid", river - 200.0), red_mid: RIFT.lane_pos("mid", river + 200.0),
                          red_jungle: beside_lane})
    me = w.champs[blue_mid]
    home = {Intent(Kind.FARM, ("mid", mode)) for mode in MODES}
    lane_nodes = [p for p in NODES if on_lane("mid", p)]
    assert len(lane_nodes) == 9

    with_allowance = legal_actions(w, blue_mid)
    assert {a for a in with_allowance if a.kind == Kind.FARM} == home
    in_view = (scenarios.fight(red_mid), scenarios.fight(red_jungle))
    assert {a for a in actions(0) if a.kind not in (Kind.FARM, Kind.FIGHT)} | set(in_view) == with_allowance - home

    me.roam = 0.0
    assert observe(w, blue_mid).me.duty == Duty.IN_LANE
    assert legal_actions(w, blue_mid) == home | {KEEP, HOLD, RECALL, scenarios.fight(red_mid)} | {
        Intent(kind, p) for kind in (Kind.MOVE, Kind.WARD) for p in lane_nodes}

    me.pos = beside_lane
    assert observe(w, blue_mid).me.duty == Duty.ROAMING
    assert legal_actions(w, blue_mid) == home | {RECALL}
    w.submit(blue_mid, Intent(Kind.FARM, ("mid", "push")))
    assert observe(w, blue_mid).me.duty == Duty.EXCUSED
    assert legal_actions(w, blue_mid) == home | {RECALL, KEEP}


def test_the_allowance_drains_while_roaming_refills_on_the_lane_and_holds_still_otherwise():
    blue_mid = scenarios.BLUE_MID
    w = scenarios.staged({blue_mid: RIFT.advance(RIFT.at("mid_river"), RIFT.at("bot_river"), 600.0)}, dt=0.5)
    me = w.champs[blue_mid]

    def allowance_after(seconds: float) -> float:
        for _ in range(round(seconds / w.dt)):
            w.step()
        return me.roam

    assert allowance_after(10.0) == ROAM_CAP_S - 10.0
    w.submit(blue_mid, RECALL)
    assert allowance_after(4.0) == ROAM_CAP_S - 10.0, "recalling"
    w.submit(blue_mid, Intent(Kind.FARM, ("mid", "last_hit")))
    while not on_lane("mid", me.pos):
        assert me.roam == ROAM_CAP_S - 10.0, "walking back"
        w.step()
    assert allowance_after(8.0) == ROAM_CAP_S - 10.0 + 8.5 * ROAM_REFILL, "8 s and the tick that reached the lane"
    assert allowance_after(60.0) == ROAM_CAP_S, "the cap"
    me.hp = 0.0
    w.submit(blue_mid, Intent(Kind.MOVE, RIFT.at("bot_river")))
    assert allowance_after(5.0) == ROAM_CAP_S and me.pos == scenarios.FOUNTAIN[0], "dead"


def test_real_wave_model_keeps_interval_invariance_replay_and_lane_independence():
    timing, snap = scenarios.interval_invariance(RealLane), scenarios.snapshots(RealLane)
    assert_interval_contract(timing)
    assert snap["a_ticks_matching"] == 300
    assert snap["b_top_lane_first_differs_after_s"] is not None and snap["b_top_lane_first_differs_after_s"] < 20
    assert snap["b_bot_lane_first_differs_after_s"] is None or snap["b_bot_lane_first_differs_after_s"] >= 20
