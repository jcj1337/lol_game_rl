import pytest

from experiments.m7.kernel import hindsight
from experiments.m7.kernel.hindsight import RED_JUNGLE, decision_point, hypothesis, known
from experiments.m7.kernel.world import LastSeen, World, fingerprint

RED_MID = 7


@pytest.fixture(scope="module")
def measured():
    return hindsight.measure()


@pytest.fixture(scope="module")
def worlds():
    return decision_point()


def test_the_two_worlds_differ_only_in_what_blue_cannot_see(measured):
    pair = measured["w1_w2"]
    assert set(pair["hidden_fields_changed_w1_to_w2"]) == {
        "red_jungler_hp", "red_jungler_gold", "red_jungler_upgrades", "red_raptors_alive", "red_memory_of_the_blue_jungler_tick",
        "red_bot_outer_tower_hp"}
    assert all(before != after for before, after in pair["hidden_fields_changed_w1_to_w2"].values())
    assert pair["worlds_differ"] and pair["blue_observations_and_masks_identical"]


def test_sampling_positions_only_gives_blue_a_different_report_in_each_world(measured):
    """The defect: the comparison reads true health, gold, upgrades, and camps that blue never saw."""
    old = measured["a_position_only"]
    assert not old["reports_identical"] and old["rollouts_that_differ"]["farm"] > 0
    assert old["w1"]["farm"]["survived"] < old["w2"]["farm"]["survived"] == 1.0


def test_identical_blue_observations_do_not_show_that_defect(measured):
    assert measured["a_position_only"]["deciding_team_sees_the_source_state_in_every_rollout_world"]


def test_truth_blind_hypotheses_give_blue_one_report_for_both_worlds(measured):
    blind = measured["b_truth_blind"]
    assert measured["w1_w2"]["blue_knowledge_identical"]
    assert blind["reports_identical"] and blind["rollouts_that_differ"] == {"farm": 0, "retreat": 0}
    assert blind["deciding_team_sees_the_source_state_in_every_rollout_world"]
    assert blind["w1"]["farm"]["survived"] < blind["w1"]["retreat"]["survived"], "the report must still tell the alternatives apart"


def test_a_rollout_world_is_a_function_of_what_blue_knows_and_the_rollout_index(worlds):
    w1, w2, _ = worlds
    first, second = known(w1, 0), known(w2, 0)
    built = [hypothesis(first, k).digest() for k in range(4)]
    assert built == [hypothesis(second, k).digest() for k in range(4)]
    assert len(set(built)) == 4, "rollouts must differ from each other"


def test_blue_knowledge_changes_when_something_blue_can_see_changes(worlds):
    w1 = worlds[0]
    assert RED_MID in w1.views[0].enemies and RED_JUNGLE not in w1.views[0].enemies
    seen, unseen, remembered = (World.restore(w1.snapshot()) for _ in range(3))
    seen.champs[RED_MID].hp -= 1.0
    seen.see()
    unseen.champs[RED_JUNGLE].hp -= 1.0
    unseen.see()
    record = remembered.memory[0].enemies[RED_JUNGLE]
    remembered.memory[0].enemies[RED_JUNGLE] = LastSeen(record.pos, record.tick, record.hp - 1.0, record.level, record.upgrades)
    base = fingerprint(known(w1, 0))
    assert fingerprint(known(unseen, 0)) == base
    assert fingerprint(known(seen, 0)) != base and fingerprint(known(remembered, 0)) != base


def test_what_blue_knows_does_not_change_with_the_health_of_any_enemy_tower(worlds):
    w1 = worlds[0]
    before = fingerprint(known(w1, 0))
    for lane in w1.lanes.values():
        for tower in lane.towers:
            if tower.team == 1:
                changed = World.restore(w1.snapshot())
                twin = next(t for t in changed.lanes[lane.name].towers if t.name == tower.name)
                twin.hp -= 1000.0
                assert fingerprint(known(changed, 0)) == before, tower.name
