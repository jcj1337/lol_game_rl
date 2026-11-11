import os
import pickle
import subprocess
import sys
from dataclasses import fields, replace
from pathlib import Path

import pytest

from riftgame.champions import RIFT, Champion, Outcome
from riftgame.harness import Replay, random_legal, record, rerun, run
from riftgame.world import Config, Snapshot, World
from worlds import BLUE_MID, RED_CARRY, StubLane, move, patient, play

REPO = Path(__file__).parents[1]


def test_a_restored_snapshot_replays_the_same_digest_at_every_tick_for_1000_ticks():
    game = World(Config(), seed=5)
    run(game, patient, 300)
    snapshot = game.snapshot()
    first, ended = play(game, patient, 1000)
    again, _ = play(World.restore(snapshot), patient, 1000)
    assert first == again and len(set(first)) == 1000
    assert {"ARRIVED", "ABSENT", "RECALLED"} <= set(ended)


def test_a_snapshot_survives_whatever_happens_to_the_world_it_came_from_and_to_its_restored_copies():
    game = World(Config(), seed=6)
    run(game, patient, 200)
    snapshot = game.snapshot()
    expected, _ = play(World.restore(snapshot), patient, 100)
    run(game, random_legal, 150)
    game.champions[BLUE_MID].gold += 1000.0
    game.champions[RED_CARRY].earned[0] += 1000.0
    game.champions[RED_CARRY].pos = RIFT.at("mid_river")
    used = World.restore(snapshot)
    run(used, random_legal, 150)
    assert play(World.restore(snapshot), patient, 100)[0] == expected


def test_a_snapshot_restores_in_another_process_to_the_same_digests(tmp_path):
    game = World(Config(), seed=7)
    run(game, patient, 200)
    file = tmp_path / "snapshot.pickle"
    file.write_bytes(pickle.dumps(game.snapshot()))
    expected, _ = play(game, random_legal, 200)
    script = ("import pickle, sys; from riftgame.harness import random_legal, tick; from riftgame.world import World\n"
              "world = World.restore(pickle.loads(open(sys.argv[1], 'rb').read()))\n"
              "for _ in range(200):\n"
              "    tick(world, random_legal)\n"
              "    print(world.digest())\n")
    for hash_seed in ("1", "2"):
        env = os.environ | {"PYTHONHASHSEED": hash_seed, "PYTHONPATH": str(REPO)}
        child = subprocess.run([sys.executable, "-c", script, str(file)], env=env, capture_output=True, text=True, check=True)
        assert child.stdout.split() == expected


@pytest.mark.parametrize("change", [{"ruleset_id": "another-ruleset"}, {"map_id": "another-map"}])
def test_restoring_into_a_different_ruleset_or_map_is_an_error(change):
    snapshot = World().snapshot()
    World.restore(snapshot)
    with pytest.raises(ValueError):
        World.restore(replace(snapshot, **change))


def test_a_snapshot_names_what_it_takes_to_restore_and_replay():
    assert [f.name for f in fields(Snapshot)] == ["ruleset_id", "map_id", "config", "seed", "tick", "champions", "lanes"]
    config = Config(tick_s=0.25, decision_ticks=3, roam_cap_s=40.0)
    game = World(config, seed=9)
    run(game, patient, 30)
    restored = World.restore(game.snapshot())
    assert (restored.config, restored.seed, restored.tick, restored.digest()) == (config, 9, 30, game.digest())


def test_two_worlds_built_apart_with_equal_state_have_equal_digests():
    a, b = World(Config(), seed=4), World(Config(), seed=4)
    assert a is not b and a.digest() == b.digest()
    assert a.digest() != World(Config(), seed=5).digest()


CHANGED = {"pos": RIFT.at("mid_river"), "hp": 1.5, "mana": 2.5, "xp": 300.0, "gold": 77.0, "earned": [1.0, 2.0, 3.0, 4.0],
           "upgrades": 2, "intent": move("mid_river"), "intent_tick": 3, "channel": 4, "outcome": Outcome.INTERRUPTED,
           "outcome_tick": 5, "allowance": 12.0, "attack_credit": 0.25, "item_charges": 1, "respawn_tick": 44}


def test_the_test_changes_every_champion_field():
    assert set(CHANGED) == {f.name for f in fields(Champion)} - {"seat"}


@pytest.mark.parametrize("field", CHANGED)
def test_the_digest_changes_with_every_champion_field(field):
    world = World()
    before = world.digest()
    setattr(world.champions[RED_CARRY], field, CHANGED[field])
    assert world.digest() != before


def test_the_digest_changes_with_the_tick_and_with_what_a_lane_reports():
    world = World()
    before = world.digest()
    world.lanes["bot"] = StubLane(values=(1, 2.5))
    one = world.digest()
    world.lanes["bot"] = StubLane(values=(1, 3.5))
    assert len({before, one, world.digest()}) == 3
    stepped = World()
    stepped.step()
    assert stepped.digest() != before


def test_the_digest_refuses_state_that_is_not_plain_values():
    world = World()
    world.lanes["mid"] = StubLane(values=({"a": 1}, object()))
    with pytest.raises(TypeError):
        world.digest()


def test_a_replay_reproduces_every_digest():
    replay, digests = record(Config(), 21, patient, 600)
    assert rerun(replay) == digests and len(digests) == 600
    assert (replay.config, replay.seed, len(replay.log)) == (Config(), 21, 600)
    assert [actions is not None for actions in replay.log[:5]] == [True, False, False, False, True]


def test_a_replay_with_one_changed_action_gives_other_digests():
    replay, digests = record(Config(), 21, patient, 200)
    first = list(replay.log[0])
    assert first[BLUE_MID] != move("enemy_base")
    first[BLUE_MID] = move("enemy_base")
    changed = Replay(replay.config, replay.seed, (tuple(first), *replay.log[1:]))
    assert rerun(changed)[0] != digests[0]


PIN = {"config": Config(), "seed": 2026, "ticks": 600,
       "digest": "e7bb8a6cdcd36657413094d5367c41004bc56cc63a982d7d3a47e75862757090"}


def test_the_pinned_replay_digest_changes_only_with_a_deliberate_update_of_the_pin():
    _, digests = record(PIN["config"], PIN["seed"], patient, PIN["ticks"])
    assert digests[-1] == PIN["digest"]
