from dataclasses import fields, is_dataclass

import pytest

from riftgame.champions import ACTIONS, HOLD, KEEP, RECALL, RIFT, SEATS, Champion, Kind, Outcome, level_of
from riftgame.harness import run
from riftgame.jungle import SITES
from riftgame.vision import CampView, EnemyView, Observation, Place, Sight, encode, legal_mask, observe, sees
from riftgame.world import Config, World
from worlds import EVERY_TICK, act, busy, lane_place, move, patient, staged

CHANGED = {"pos": RIFT.at("mid_river"), "hp": 1.5, "mana": 2.5, "gold": 77.0, "earned": [1.0, 2.0, 3.0, 4.0],
           "upgrades": 2, "intent": move("mid_river"), "intent_tick": 3, "channel": 4, "outcome": Outcome.INTERRUPTED,
           "outcome_tick": 5, "allowance": -12.0, "attack_credit": 0.25, "item_charges": 1,
           "respawned_tick": 6, "respawned_level": 3, "homeguard_tick": 7, "homeguard_block": 9, "hurt_tick": [3, 4, 5, 6, 7], "slow": 0.5, "slow_until": 9, "lockdown_tick": 11,
           "ward_charges": 2, "ward_tick": 12345}
# A champion's level and its death timer are public. What is hidden of these two fields is the XP inside the level
# and nothing of the respawn tick.
PARTLY_PUBLIC = {"xp", "respawn_tick"}


def hidden_changes(enemy: Champion) -> dict:
    """A new value for every field of an enemy champion, with its level and its death timer left as they are.

    The XP moves inside its level. The respawn tick of a living champion goes to another tick in the past. That
    of a dead one stays, because the time until it respawns is public.
    """
    xp = enemy.xp + 1.0 if level_of(enemy.xp + 1.0) == level_of(enemy.xp) else enemy.xp - 1.0
    assert level_of(xp) == level_of(enemy.xp)
    changes = CHANGED | {"xp": xp}
    if enemy.respawn_tick < 0:
        changes["respawn_tick"] = -2
    return changes


def team_knowledge(world: World, team: int) -> list:
    """Everything a team's policies read: each champion's observation, its mask, and its encoded observation."""
    return [(o, legal_mask(o), encode(o)) for o in (observe(world, seat) for seat in range(team * 5, team * 5 + 5))]


@pytest.mark.parametrize("team", [0, 1])
def test_changing_every_hidden_field_of_every_enemy_champion_changes_no_observation_and_no_mask(team):
    assert set(CHANGED) | PARTLY_PUBLIC == {f.name for f in fields(Champion)} - {"seat"}
    world = World(Config(tick_s=0.5, decision_ticks=4), seed=8)
    run(world, patient, 240)
    before = team_knowledge(world, team)
    enemy_before = team_knowledge(world, 1 - team)
    enemies = world.champions[(1 - team) * 5:(1 - team) * 5 + 5]
    public = [(level_of(enemy.xp), max(0, enemy.respawn_tick + 1 - world.tick)) for enemy in enemies]
    for enemy in enemies:
        changes = hidden_changes(enemy)
        assert set(changes) >= set(CHANGED) | {"xp"} | ({"respawn_tick"} if enemy.hp > 0 else set())
        for name, value in changes.items():
            assert getattr(enemy, name) != value
            setattr(enemy, name, value)
    assert [(level_of(enemy.xp), max(0, enemy.respawn_tick + 1 - world.tick)) for enemy in enemies] == public
    assert team_knowledge(world, team) == before
    assert all(now != was for now, was in zip(team_knowledge(world, 1 - team), enemy_before)), "the test must be able to see a change"


@pytest.mark.parametrize("team", [0, 1])
def test_changing_every_camp_fact_a_team_has_not_seen_changes_no_observation_and_no_mask_now_or_while_it_stays_unseen(team):
    world = World(Config(tick_s=0.5, decision_ticks=4), seed=8)
    run(world, busy, 420)
    hidden = [i for i, site in enumerate(SITES) if not sees(world, team, site.pos)]
    assert 0 < len(hidden) < len(SITES), "the team must see some camps and not others"
    assert {s.team for s in world.sights} == {0, 1} and any(camp.hp <= 0 for camp in world.camps)
    twin = World.restore(world.snapshot())
    for i in hidden:
        camp = twin.camps[i]
        if camp.hp > 0:
            camp.hp, camp.max_hp, camp.level, camp.spawn_tick, camp.engaged = 0.0, 77.0, 9, twin.tick + 3, -1
        else:
            camp.hp, camp.max_hp, camp.level, camp.spawn_tick, camp.engaged = 123.0, 456.0, 7, -1, -1
    for memory in twin.memory[1 - team].camps:
        memory.hp, memory.level, memory.seen_tick, memory.spawn_tick = memory.hp + 5.0, memory.level + 2, memory.seen_tick + 9, memory.spawn_tick + 30
    twin.sights[:] = [s for s in twin.sights if s.team == team] + [Sight(1 - team, SITES[hidden[0]].pos, 2000.0, twin.tick + 500)]
    assert all(now != was for now, was in zip(team_knowledge(twin, 1 - team), team_knowledge(world, 1 - team))), "the test must be able to see a change"
    hold = [HOLD if c.hp > 0 else KEEP for c in world.champions]
    for step in range(60):
        assert team_knowledge(twin, team) == team_knowledge(world, team), f"step {step}"
        for game in (world, twin):
            game.step(hold if step == 0 else None)
    assert [camp.hp > 0 for camp in twin.camps] != [camp.hp > 0 for camp in world.camps], "the two worlds still differ where the team cannot see"
    for game in (world, twin):
        game.champions[team * 5 + 1].pos = SITES[hidden[0]].pos
        game.step()
    assert team_knowledge(twin, team) != team_knowledge(world, team), "sight of a changed camp shows the change"


def test_an_observation_holds_the_champion_its_four_teammates_the_camps_and_the_clock():
    world = World(Config(tick_s=0.5, decision_ticks=4), seed=8)
    run(world, patient, 30)
    for seat in SEATS:
        o = observe(world, seat)
        assert [f.name for f in fields(Observation)] == ["time_s", "me", "mates", "camps", "enemies", "remembered", "rivals", "lanes",
                                                         "wards"]
        assert EnemyView._fields == ("place", "was", "hp", "level", "upgrades") and len(o.enemies) == 5
        assert CampView._fields == ("hp", "level", "seen_age_s", "spawn_s", "walk")
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
    if isinstance(value, CampView):
        # The map mirrors no walk off the lanes, so a camp's walk is left out of the mirror test.
        value = value[:-1]
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
            # The encoded observation holds the walk to each camp, which the map does not mirror.
            for (o, mask, _), (mirrored, mirrored_mask, _) in zip(mine, theirs, strict=True):
                assert same(o, mirrored) and mask == mirrored_mask, f"tick {t}, role {o.me.role}"


def test_the_mirrored_game_exercises_what_it_claims():
    seen = scripted_game(1)
    outcomes = {o.me.outcome for tick in seen for side in tick for o, _, _ in side}
    assert {Outcome.ARRIVED, Outcome.RECALLED, Outcome.INTERRUPTED, Outcome.DIED} <= outcomes
    duties = {o.me.duty for tick in seen for side in tick for o, _, _ in side}
    assert len(duties) == 4, "on lane, returning, roaming, and the jungler's none"
    assert any(o.me.dead_s > 0 for tick in seen for o, _, _ in tick[0]) and seen[-1][0][0][0].me.hp > 0
    assert len({o.me.place for tick in seen for side in tick for o, _, _ in side}) > 100
    assert len({mask for tick in seen for side in tick for _, mask, _ in side}) > 5


def test_the_mask_comes_from_the_observation_alone_and_is_never_empty():
    world = World(EVERY_TICK, seed=2)
    for _ in range(200):
        for seat in SEATS:
            o = observe(world, seat)
            mask = legal_mask(o)
            assert any(mask) and len(mask) == len(ACTIONS)
            assert mask == legal_mask(observe(world, seat))
        run(world, patient, 1)
