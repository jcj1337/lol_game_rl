from dataclasses import fields, is_dataclass

import pytest

from riftgame.champions import HOLD, KEEP, RECALL, RIFT, SEATS, Champion, Kind, Outcome
from riftgame.harness import run
from riftgame.vision import Observation, Place, legal_mask, observe
from riftgame.world import Config, World
from worlds import EVERY_TICK, act, lane_place, move, patient, staged

CHANGED = {"pos": RIFT.at("mid_river"), "hp": 1.5, "mana": 2.5, "xp": 3300.0, "gold": 77.0, "earned": [1.0, 2.0, 3.0, 4.0],
           "upgrades": 2, "intent": move("mid_river"), "intent_tick": 3, "channel": 4, "outcome": Outcome.INTERRUPTED,
           "outcome_tick": 5, "allowance": -12.0, "attack_credit": 0.25, "item_charges": 1, "respawn_tick": 44}


def team_knowledge(world: World, team: int) -> list:
    return [(o, legal_mask(o)) for o in (observe(world, seat) for seat in range(team * 5, team * 5 + 5))]


@pytest.mark.parametrize("team", [0, 1])
def test_changing_every_field_of_every_enemy_champion_changes_no_observation_and_no_mask(team):
    assert set(CHANGED) == {f.name for f in fields(Champion)} - {"seat"}
    world = World(Config(), seed=8)
    run(world, patient, 240)
    before = team_knowledge(world, team)
    enemy_before = team_knowledge(world, 1 - team)
    for enemy in world.champions[(1 - team) * 5:(1 - team) * 5 + 5]:
        for name, value in CHANGED.items():
            assert getattr(enemy, name) != value
            setattr(enemy, name, value)
    assert team_knowledge(world, team) == before
    assert all(now != was for now, was in zip(team_knowledge(world, 1 - team), enemy_before)), "the test must be able to see a change"


def test_an_observation_holds_the_champion_its_four_teammates_and_the_clock():
    world = World(Config(), seed=8)
    run(world, patient, 30)
    for seat in SEATS:
        o = observe(world, seat)
        assert [f.name for f in fields(Observation)] == ["time_s", "me", "mates"]
        assert o.time_s == 15.0 and o.me.role == seat % 5
        assert [mate.role for mate in o.mates] == [role for role in range(5) if role != seat % 5]
        others = [mate for mate in range(seat // 5 * 5, seat // 5 * 5 + 5) if mate != seat]
        assert o.mates == tuple(observe(world, mate).me for mate in others)


def test_a_place_is_measured_outward_from_the_teams_own_fountain():
    world = staged({seat: lane_place(seat // 5, "top", 3000.0) for seat in (0, 5)} | {seat: RIFT.at("bot_river") for seat in (1, 6)})
    blue_top, red_top = observe(world, 0).me.place, observe(world, 5).me.place
    assert blue_top == Place("top", 3000.0)
    assert red_top.route == "top" and red_top.s == pytest.approx(3000.0)
    assert RIFT.lane_s("top", world.champions[5].pos) == pytest.approx(RIFT.lanes["top"].length - 3000.0)
    assert observe(world, 2).me.place == observe(world, 7).me.place == Place("own_fountain>own_base", 0.0)
    blue_jungle = observe(world, 1).me.place
    assert blue_jungle.route == "own_red>bot_river" and blue_jungle.s == pytest.approx(RIFT.edges[RIFT.at("bot_river").edge].length)
    assert observe(world, 6).me.place == Place("bot_river>enemy_red", 0.0)


def flat(value) -> list:
    if is_dataclass(value):
        return [leaf for f in fields(value) for leaf in flat(getattr(value, f.name))]
    if isinstance(value, tuple):
        return [leaf for item in value for leaf in flat(item)]
    return [value]


def same(a: Observation, b: Observation) -> bool:
    return all(x == pytest.approx(y, abs=1e-6) if isinstance(x, float) else x == y for x, y in zip(flat(a), flat(b), strict=True))


FOLLOW_CARRY = act(Kind.FOLLOW, 3)
# By tick, then by role. Every target is one that the map mirrors exactly: a lane measured from its own end, a base
# node, a fountain, an ally.
BLUE_MARKS = {0: ("top", 3000.0), 1: ("mid", 2600.0), 2: ("mid", 4100.0), 3: ("bot", 3600.0), 4: ("bot", 3300.0)}
BLUE_ORDERS = {0: {0: move("own_base"), 1: move("own_base"), 2: RECALL, 3: move("own_base"), 4: FOLLOW_CARRY},
               8: {2: RECALL, 3: HOLD},
               24: {1: move("enemy_base")}}
BLUE_HITS = {6: (2, 50.0), 12: (0, 10_000.0)}
RED_MARKS = {0: ("top", 5200.0), 1: ("bot", 2900.0), 2: ("top", 4000.0), 3: ("bot", 4400.0), 4: ("mid", 3700.0)}
RED_ORDERS = {0: {1: move("own_base"), 3: RECALL, 4: move("own_base")},
              10: {2: move("own_base")},
              30: {4: RECALL}}
RED_HITS = {10: (3, 30.0)}
SCRIPT_TICKS = 52


def scripted_game(first_team: int) -> list[list[tuple]]:
    """Play the two scripts, the blue one by `first_team`. Returns, per tick, each team's observations and masks."""
    sides = {first_team: (BLUE_MARKS, BLUE_ORDERS, BLUE_HITS), 1 - first_team: (RED_MARKS, RED_ORDERS, RED_HITS)}
    world = staged({team * 5 + role: lane_place(team, lane, s) for team, (marks, _, _) in sides.items()
                    for role, (lane, s) in marks.items()})
    seen = []
    for t in range(SCRIPT_TICKS):
        for team, (_, _, hits) in sides.items():
            if t in hits:
                role, raw = hits[t]
                world.damage_champion(team * 5 + role, raw)
        seen.append([team_knowledge(world, first_team), team_knowledge(world, 1 - first_team)])
        actions = [KEEP] * 10
        for team, (_, orders, _) in sides.items():
            for role, action in orders.get(t, {}).items():
                actions[team * 5 + role] = action
        world.step(actions)
    return seen


def test_a_mirrored_action_sequence_gives_the_red_team_the_observations_blue_got():
    as_blue, as_red = scripted_game(0), scripted_game(1)
    for t, (blue_game, red_game) in enumerate(zip(as_blue, as_red, strict=True)):
        for mine, theirs in zip(blue_game, red_game, strict=True):
            for (o, mask), (mirrored, mirrored_mask) in zip(mine, theirs, strict=True):
                assert same(o, mirrored) and mask == mirrored_mask, f"tick {t}, role {o.me.role}"


def test_the_mirrored_game_exercises_what_it_claims():
    seen = scripted_game(1)
    outcomes = {o.me.outcome for tick in seen for side in tick for o, _ in side}
    assert {Outcome.ARRIVED, Outcome.RECALLED, Outcome.INTERRUPTED, Outcome.DIED} <= outcomes
    duties = {o.me.duty for tick in seen for side in tick for o, _ in side}
    assert len(duties) == 4, "on lane, returning, roaming, and the jungler's none"
    assert any(o.me.dead_s > 0 for tick in seen for o, _ in tick[0]) and seen[-1][0][0][0].me.hp > 0
    assert len({o.me.place for tick in seen for side in tick for o, _ in side}) > 100
    assert len({mask for tick in seen for side in tick for _, mask in side}) > 5


def test_the_mask_comes_from_the_observation_alone_and_is_never_empty():
    world = World(EVERY_TICK, seed=2)
    for _ in range(200):
        for seat in SEATS:
            o = observe(world, seat)
            mask = legal_mask(o)
            assert any(mask) and len(mask) == 98
            assert mask == legal_mask(observe(world, seat))
        run(world, patient, 1)
