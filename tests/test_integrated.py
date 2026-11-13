"""Checkpoint C7 on a few seeds: integrated games of all ten seats under the scripted policies of
`riftgame.policies`. The 50-seed evidence is `experiments/m8/integrated.py` and its results file; these tests run
the same referee on fewer games, so they fail when the code breaks a rule."""

import pytest

from experiments.m8.integrated import BEHAVIOURS, REPLAYS, play, replay_policies
from riftgame.champions import ACTIONS, Kind
from riftgame.harness import record, rerun, tick
from riftgame.policies import team_policies
from riftgame.vision import legal_mask, observe_team
from riftgame.world import Config, World

# The final digest of each replay after 20 game minutes. A change to the state or to the policies moves them, and
# the pin is then updated on purpose.
PINNED = {
    "scripted teams, seed 7": "7dad3ef27f81f78616b590557158c44d1cd7e12b9f9835230c79736c32c747c2",
    "scripted blue, random red, seed 11": "2886c042a858d8f0c77b338708bceddc0d21a91eb51c914a521ca13db7c68991",
    "random teams, seed 13": "5da0ac5b648ec8dc02d1d5fc969996b2797ebdc1831a7c53298ab9c7fa1b4b0e",
}


@pytest.mark.parametrize("name", list(REPLAYS))
def test_three_pinned_replays_reproduce_their_digests_on_every_tick(name):
    seed, blue, red = REPLAYS[name]
    replay, digests = record(Config(), seed, replay_policies(blue, red), 2400)
    assert rerun(replay) == digests
    assert digests[-1] == PINNED[name]


# Seed 3 is in the list because its game provokes the towers often enough that a tower which ignores its provokers
# breaks the referee's rule. Seeds 0 and 1 do not, which the mutation runner showed.
@pytest.mark.parametrize("seed", [0, 1, 3])
def test_a_scripted_game_of_20_minutes_breaks_no_invariant_and_no_rule_of_the_referee(seed):
    run = play((seed, Config(), "scripted", "scripted", 1200.0, True))
    assert run["invariant_error"] is None and run["faults"] == []
    checked = run["checked"]
    assert checked["wave spawns"] > 1000 and checked["camp spawns"] > 40 and checked["champion respawns"] > 10
    assert checked["minion places under a standing tower"] > 50_000
    assert checked["tower shots on champions with a provoker in range"] > 0 and checked["tower shots on champions with no provoker"] > 10


def test_the_scripted_policies_exercise_every_subsystem_over_a_few_games():
    work = {}
    for seed in range(3):
        for key, value in play((seed, Config(), "scripted", "scripted", 1200.0, False))["work"].items():
            work[key] = work.get(key, 0) + value
    missing = [key for key in BEHAVIOURS if not work.get(key)]
    assert missing == [], f"no game showed {missing}"


@pytest.mark.parametrize("scripted_team", [0, 1])
def test_a_scripted_team_beats_a_random_team_on_gold_and_xp_at_15_minutes(scripted_team):
    sides = ("scripted", "random") if scripted_team == 0 else ("random", "scripted")
    for seed in range(3):
        score = play((seed, Config(), *sides, 900.0, False, 900.0))["gold_plus_xp_at_score"]
        assert score[scripted_team] > score[1 - scripted_team], f"seed {seed}"


def test_after_an_outer_tower_falls_the_attacking_wave_advances_further_in_that_lane():
    run = play((0, Config(), "scripted", "random", 1200.0, False))
    full = [fall for fall in run["falls"] if fall["after_window_s"] >= 120.0]
    assert full, "a scripted team takes an outer tower from a random one within 20 minutes"
    assert all(fall["after"] > fall["before"] for fall in full)


def test_every_scripted_choice_is_legal_and_reads_only_the_observation():
    """Each policy gets the observation and the noise and nothing else, so a choice it makes twice from equal
    observations is the same, and its mask allows it."""
    world, policies = World(Config(), 5), team_policies()
    kinds = set()
    for _ in range(1200):
        if world.tick % world.config.decision_ticks == 0:
            observations = [*observe_team(world, 0), *observe_team(world, 1)]
            for seat, (act, o) in enumerate(zip(policies, observations)):
                choice = act(o, 0.5)
                assert legal_mask(o)[choice] and act(o, 0.5) == choice
                kinds.add(ACTIONS[choice].kind)
        tick(world, policies)
    assert {Kind.LANE, Kind.CAMP, Kind.WARD, Kind.RECALL, Kind.MOVE} <= kinds
