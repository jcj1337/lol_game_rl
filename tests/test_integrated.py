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
    "scripted teams, seed 7": "394aa559680303b161c2492f4d844229ac001fef50aaa49ebc10256b61c2d0d8",
    "scripted blue, random red, seed 11": "6a8e718c128b0f9d7f23a19b24d0536d1fe6efe30607aa7f8043f21e87161b00",
    "random teams, seed 13": "97916ca25b4ef9dbcacd665270c2081477c45dde927e36a86696c07fdac305ea",
}


@pytest.mark.parametrize("name", list(REPLAYS))
def test_three_pinned_replays_reproduce_their_digests_on_every_tick(name):
    seed, blue, red = REPLAYS[name]
    replay, digests = record(Config(), seed, replay_policies(blue, red), round(1200.0 / Config().tick_s))
    assert rerun(replay) == digests
    assert digests[-1] == PINNED[name]


# Under the tower rule of `riftgame.policies` few scripted games provoke a tower. In campaign 5, after the fix of
# `LaneSim._free_to_walk`, 14 of seeds 0 to 49 shot a provoker: seed 35 four times, seed 23 three times, seeds 11, 13,
# 18, 32, 39, and 41 twice, and seeds 3, 10, 12, 17, 22, and 43 once. The three that shot most are here, so a tower
# that ignores its provokers breaks the referee's rule (mutation runner).
@pytest.mark.parametrize("seed", [35, 23, 11])
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


# Seed 2 is in the list because campaign 5 moved the first fall of seed 0 from 1,060 s to 1,094 s, which leaves less
# than the window of 120 s inside 20 minutes.
def test_after_an_outer_tower_falls_the_attacking_wave_advances_further_in_that_lane():
    runs = [play((seed, Config(), "scripted", "random", 1200.0, False)) for seed in (0, 2)]
    full = [fall for run in runs for fall in run["falls"] if fall["after_window_s"] >= 120.0]
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
