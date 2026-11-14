"""C8. The information state of a team (M7 section 9.3, contract 1).

The source worlds are the games of `tests/test_vision.py` and random legal games. The hidden fields are changed by
the scramble of C6 (`tests/test_vision.py`), the change of every private field of a visible enemy (`tests/test_pursuit.py`),
and `scramble_rest` below, which changes what those two leave alone. That is the lane counters and scratch fields,
every other field of a hidden enemy minion, and the attack state of a hidden enemy tower. All three decide what is hidden from the
map's own sight measure and share no code with `riftgame.info`.
"""

import pickle
import random
from dataclasses import fields, is_dataclass
from enum import Enum

import pytest

from riftgame.champions import FOUNTAIN, LANES, LEVEL_XP, RIFT, Income, level_of
from riftgame.harness import random_legal, tick
from riftgame.info import FIELDS, Known, redact
from riftgame.lanes import (AreaSpent, AttackCredit, ChampionDamage, KindRules, LaneGeometry, LaneRules, LaneSim, MinionDeath, MinionRemoved,
                            TowerDamage, TowerDestroyed, TowerPlate, TowerShot, WaveClock)
from riftgame.map import Pos
from riftgame.vision import new_memory
from riftgame.world import Config, World, _plain
from test_pursuit import change_private
from test_vision import GAMES, SLACK, SNAPSHOTS, game, knowledge, lit, scramble, sources_of, team_of

# Frozen values that are known with whatever holds them. They are the clock settings, places, the rules of a lane, and the
# events of a lane's last tick, which only its scratch field `_events` holds.
VALUES = (Config, Pos, LaneRules, LaneGeometry, KindRules, MinionDeath, MinionRemoved, TowerDamage, TowerDestroyed, TowerPlate, ChampionDamage,
          TowerShot, AttackCredit, AreaSpent)


def state_types(value, found: dict, done: set) -> dict:
    """Every class of unit in the state, with the names of its fields."""
    if id(value) in done or value is None or isinstance(value, (bool, int, float, str, Enum)):
        return found
    done.add(id(value))
    if isinstance(value, (list, tuple)):
        children = list(value)
    elif isinstance(value, dict):
        children = [*value.keys(), *value.values()]
    elif is_dataclass(value):
        found[type(value)] = {f.name for f in fields(value)}
        children = [getattr(value, f.name) for f in fields(value)]
    else:
        found[type(value)] = set(vars(value))
        children = list(vars(value).values())
    for child in children:
        state_types(child, found, done)
    return found


def test_every_field_of_the_state_is_classified_once():
    """A field or a class of unit that the state gains and the table does not name fails here."""
    found = state_types(game(8, "varied", 0, 1200).snapshot(), {}, set())
    units = {kind: names for kind, names in found.items() if kind not in VALUES}
    assert {LaneSim, WaveClock} <= set(units) and set(FIELDS) == set(units), set(FIELDS) ^ set(units)
    for kind, names in units.items():
        assert set(FIELDS[kind]) == names, (kind.__name__, set(FIELDS[kind]) ^ names)
        assert all(isinstance(field.known, Known) for field in FIELDS[kind].values())


@pytest.mark.parametrize("seed, enemy", GAMES)
@pytest.mark.parametrize("team", [0, 1])
def test_the_information_state_tells_the_team_what_the_source_tells_it(team, seed, enemy):
    for ticks in SNAPSHOTS:
        world = game(seed, enemy, team, ticks)
        assert knowledge(redact(world, team).world(), team) == knowledge(world, team), f"tick {ticks}"


@pytest.mark.parametrize("seed", [2, 6])
def test_the_information_state_tells_both_teams_what_the_source_tells_them_in_random_legal_games(seed):
    world, compared = World(Config(), seed), 0
    while world.tick < 1600:
        tick(world, random_legal)
        if world.tick % 200 == 0:
            for team in (0, 1):
                assert knowledge(redact(world, team).world(), team) == knowledge(world, team), f"tick {world.tick}, team {team}"
                compared += 1
    assert compared == 16


def scramble_rest(world: World, team: int, rng: random.Random) -> int:
    """Change the fields hidden from `team` that the C6 scramble leaves alone, the world's seed among them, and return
    how many units changed."""
    foe, mine = 1 - team, sources_of(world, team)
    world.seed += 1
    changed = 0
    for name in LANES:
        sim = world.lanes[name]
        sim.seed = world.seed
        sim.dead, sim.removed, sim.cancelled, sim.lost, sim._order = sim.dead + 3, sim.removed + 1, sim.cancelled + 5, sim.lost + 2, sim._order + 900
        sim._missiles = [(land, uid, order + 900, *rest) for land, uid, order, *rest in sim._missiles]
        sim._t0, sim._group = sim._t0 + 1.0, sim._group + 4
        sim._champion_credit[foe * 5 + 2] = 0.3
        for m in (*sim.minions[0], *sim.minions[1]):
            m.near_gap, m.near_walk, m.anchored, m.free_at, m.died_group = 77.0, 88.0, not m.anchored, m.free_at + 0.1, 9
            changed += 1
        for m in sim.minions[foe]:
            if not lit(mine, RIFT.lane_pos(name, m.s), SLACK):
                m.wave, m.slot, m.born, m.boost, m.draws, m.swing, m.delay = m.wave + 1, m.slot + 0.5, m.born - 1.0, m.boost + 5.0, m.draws + 2, m.swing + 0.3, 0.2
                m.gold, m.ad, m.max_hp = m.gold + 1.0, m.ad + 2.0, m.max_hp + 3.0
                changed += 1
        front = sim.front_tower(foe)
        if front is not None and not lit(mine, RIFT.lane_pos(name, front.s), SLACK):
            front.credit = 0.25 if front.credit != 0.25 else 0.75
            changed += 1
    return changed


def hidden_twin(world: World, team: int, seed: int) -> World:
    """A copy of `world` in which every field hidden from `team` has another value."""
    twin = World.restore(world.snapshot())
    rng = random.Random(seed)
    scramble(twin, team, rng)
    for c, record in zip(team_of(twin, 1 - team), twin.memory[team].enemies):
        if c.hp > 0 and record.seen_tick == twin.tick:
            change_private(c, twin.tick, rng)
    assert scramble_rest(twin, team, rng) > 0
    return twin


@pytest.mark.parametrize("seed, enemy", GAMES)
@pytest.mark.parametrize("team", [0, 1])
def test_changing_every_field_hidden_from_a_team_changes_nothing_in_its_information_state(team, seed, enemy):
    for ticks in SNAPSHOTS:
        world = game(seed, enemy, team, ticks)
        twin = hidden_twin(world, team, seed * 100 + ticks)
        assert twin.digest() != world.digest()
        info, other = redact(world, team), redact(twin, team)
        assert other.digest() == info.digest() and pickle.dumps(other) == pickle.dumps(info), f"tick {ticks}"


def test_the_information_state_changes_with_what_the_team_sees():
    """The comparison above can see a change. The health of an enemy in view and the place of the team's own champion
    each change the information state."""
    for seed, enemy in GAMES:
        world = game(seed, enemy, 0, 800)
        visible = [c for c, record in zip(team_of(world, 1), world.memory[0].enemies) if c.hp > 0 and record.seen_tick == world.tick]
        if visible:
            break
    else:
        raise AssertionError("no game shows blue a living enemy at tick 800")
    info = redact(world, 0)
    hurt = World.restore(world.snapshot())
    hurt.champions[visible[0].seat].hp -= 10.0
    hurt.memory[0].enemies[visible[0].seat % 5].hp -= 10.0
    moved = World.restore(world.snapshot())
    moved.champions[0].pos = FOUNTAIN[0]
    assert redact(hurt, 0).digest() != info.digest() and redact(moved, 0).digest() != info.digest()


@pytest.mark.parametrize("seed, enemy", GAMES[:2])
def test_redacting_an_information_state_gives_it_back(seed, enemy):
    for team in (0, 1):
        for ticks in SNAPSHOTS:
            info = redact(game(seed, enemy, team, ticks), team)
            assert pickle.dumps(redact(info.world(), team)) == pickle.dumps(info)


def test_an_unseen_enemy_holds_only_blanks_and_the_public_facts_and_the_enemy_holds_no_ward_and_the_starting_memory():
    checked = 0
    for seed, enemy in GAMES:
        for team in (0, 1):
            world = game(seed, enemy, team, 1200)
            info = redact(world, team)
            state = info.world()
            assert [s for s in state.sights if s.team != team] == []
            assert _plain(state.memory[1 - team]) == _plain(new_memory(state.config, 1 - team))
            for c, truth, now in zip(team_of(state, 1 - team), team_of(world, 1 - team), info.seen):
                if now:
                    assert (c.pos, c.hp, c.upgrades) == (truth.pos, truth.hp, truth.upgrades)
                    continue
                kill = 1.0 if truth.earned[Income.KILL] > 0 else 0.0
                level = level_of(truth.xp)
                assert c.pos == FOUNTAIN[1 - team] and c.gold == 0.0 and c.upgrades == 0 and c.earned == [kill if i == Income.KILL else 0.0 for i in Income]
                assert c.xp == (LEVEL_XP[level - 2] if level > 1 else 0.0) and level_of(c.xp) == level and c.respawn_tick == truth.respawn_tick
                checked += 1
    assert checked >= 20, checked
