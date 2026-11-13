"""Pursuit and the automatic behaviour of a team read only what the team knows, also of the enemies it sees.

A team sees where an enemy champion stands, its health, level, and upgrades. It does not see what the enemy
intends or how its last intent ended, its XP within the level, its gold, mana, attack credit, ward charges, lockdown
cooldown, item charges, Homeguard, or slow. Every champion picks where it heads from the state at the start of the
move step, by its team's memory alone, so two worlds that differ only in those fields of visible enemies give the
team the same observations and the same moves on that tick (handoff 007, F14).
"""

import random
from functools import cache

import pytest

from riftgame import combat
from riftgame.champions import ACTIONS, FOE, KEEP, LANES, NO_HOMEGUARD, RIFT, Champion, Income, Kind, Outcome, capability_of, lane_post, level_of
from riftgame.economy import lane_inputs
from riftgame.harness import random_legal
from riftgame.rng import Stream, keyed_uniform
from riftgame.vision import observe_team
from riftgame.world import World, check_invariants
from test_vision import ENEMIES, GAMES, advance, game, knowledge, mid, quiet_world, team_of, varied
from worlds import BLUE_CARRY, BLUE_TOP, RED_JUNGLE, RED_MID, act, move, submit

TOP, JUNGLE, MID = 0, 1, 2
# The fields of a visible enemy champion that its place, health, level, and upgrades do not show.
PRIVATE = ("intent", "intent_tick", "outcome", "outcome_tick", "xp", "gold", "attack_credit", "channel", "mana", "allowance", "ward_charges",
           "ward_tick", "lockdown_tick", "item_charges", "homeguard_tick", "homeguard_block", "slow", "slow_until")


def _other(rng: random.Random, now, choices):
    return rng.choice([value for value in choices if value != now])


def change_private(c: Champion, tick: int, rng: random.Random) -> None:
    """Give every field of `PRIVATE` another legal value. The gold goes through the ledger."""
    can = capability_of(c)
    c.intent = _other(rng, c.intent, range(1, len(ACTIONS)))
    c.intent_tick -= 1 + rng.randrange(20)
    c.outcome = _other(rng, c.outcome, list(Outcome))
    c.outcome_tick -= 1 + rng.randrange(20)
    # XP within the level, which is public.
    c.xp = next(xp for xp in (c.xp + 1.0, c.xp - 1.0, c.xp + 0.5) if xp >= 0 and level_of(xp) == level_of(c.xp))
    extra = rng.uniform(5.0, 200.0)
    c.gold += extra
    c.earned[Income.PASSIVE] += extra
    c.attack_credit = _other(rng, c.attack_credit, (0.0, 0.25, 0.5, 0.75, 1.0))
    c.channel += 1 + rng.randrange(4)
    c.mana = _other(rng, c.mana, [can.max_mana * share for share in (0.0, 0.2, 0.5, 0.8, 1.0)])
    c.allowance -= rng.uniform(1.0, 60.0)
    c.ward_charges = _other(rng, c.ward_charges, range(3))
    c.ward_tick = -1 if c.ward_charges == 2 else max(tick, c.ward_tick) + 1 + rng.randrange(300)
    c.lockdown_tick = tick + 1 + rng.randrange(30) if c.lockdown_tick <= tick else tick - rng.randrange(30)
    c.item_charges = _other(rng, c.item_charges, range(4))
    c.homeguard_tick = tick - rng.randrange(8) if c.homeguard_tick == NO_HOMEGUARD else NO_HOMEGUARD
    c.homeguard_block += 1 + rng.randrange(20)
    c.slow = _other(rng, c.slow, (0.0, 0.2, 0.4))
    c.slow_until = _other(rng, c.slow_until, range(tick + 1, tick + 8))


def heal_team(world: World, team: int) -> None:
    """Full health, so that no champion of the team dies on the next tick and is moved to its fountain."""
    for c in team_of(world, team):
        if c.hp > 0:
            c.hp = capability_of(c).max_hp


@cache
def pairs(seed: int, enemy: str, team: int) -> tuple:
    """Moments of a running game at which the team sees at least one living enemy and none of its champions
    recalls, which would teleport it. Each is two copies of the game, the second with every private field of every
    visible enemy changed, and the number of enemies changed. A test runs copies of them."""
    world = game(seed, enemy, team, 600)
    policies = (varied, ENEMIES[enemy]) if team == 0 else (ENEMIES[enemy], varied)
    rng, found = random.Random(seed * 7 + team), []
    for _ in range(160):
        advance(world, policies)
        visible = [c for c, record in zip(team_of(world, 1 - team), world.memory[team].enemies) if c.hp > 0 and record.seen_tick == world.tick]
        if not visible or any(ACTIONS[c.intent].kind is Kind.RECALL for c in team_of(world, team)):
            continue
        probe, twin = World.restore(world.snapshot()), World.restore(world.snapshot())
        for copy in (probe, twin):
            heal_team(copy, team)
        for c in visible:
            changed = twin.champions[c.seat]
            change_private(changed, twin.tick, rng)
            assert all(getattr(changed, name) != getattr(c, name) for name in PRIVATE if name != "gold") and changed.gold != c.gold
        found.append((probe, twin, len(visible)))
    return tuple(found)


def team_actions(world: World, team: int) -> list[int] | None:
    """The team's actions from its policy on this tick, and KEEP for every enemy, so that a changed intent stays."""
    if world.tick % world.config.decision_ticks:
        return None
    mine = [varied(o, keyed_uniform(world.seed, Stream.POLICY, team * 5 + role, world.tick)) for role, o in enumerate(observe_team(world, team))]
    return mine + [KEEP] * 5 if team == 0 else [KEEP] * 5 + mine


@pytest.mark.parametrize("seed, enemy", GAMES)
@pytest.mark.parametrize("team", [0, 1])
def test_changing_the_private_fields_of_the_enemies_a_team_sees_changes_none_of_its_observations_and_none_of_its_moves(team, seed, enemy):
    moments = pairs(seed, enemy, team)
    compared = changed = 0
    for kept, held, visible in moments:
        probe, twin = World.restore(kept.snapshot()), World.restore(held.snapshot())
        assert knowledge(twin, team) == knowledge(probe, team), f"tick {probe.tick}"
        check_invariants(twin)
        actions = team_actions(probe, team)
        living = [c.seat for c in team_of(probe, team) if c.hp > 0]
        for world in (probe, twin):
            world.step(actions)
        assert all(world.champions[seat].hp > 0 for world in (probe, twin) for seat in living), "nobody of the team was moved by a death"
        assert [c.pos for c in team_of(twin, team)] == [c.pos for c in team_of(probe, team)], f"tick {probe.tick - 1}"
        compared += 1
        changed += visible
    assert compared >= 15 and changed >= 25, (compared, changed)


def fighters_hits(world: World, team: int, strikes: list) -> list:
    return [hit for hit in strikes if hit.attacker // 5 == team and FOE[world.champions[hit.attacker].intent] >= 0]


@pytest.mark.parametrize("seed, enemy", GAMES)
@pytest.mark.parametrize("team", [0, 1])
def test_stance_lane_inputs_targeting_and_retaliation_read_no_private_field_of_a_visible_enemy(team, seed, enemy):
    """On the state at the start of the tick: where each laner of the team stands in its lane, what each lane is
    given for the team's champions, the team's fighters' hits, and its guards' answers, which follow the enemy hits
    on the guard and so are compared where those hits are equal."""
    kinds = set()
    inputs = 0
    for probe, twin, _ in pairs(seed, enemy, team):
        probe, twin = World.restore(probe.snapshot()), World.restore(twin.snapshot())
        for c in team_of(probe, team):
            action = ACTIONS[c.intent]
            kinds.add(action.kind)
            if action.kind is Kind.LANE and c.hp > 0:
                assert lane_post(twin, c.seat, action.target[0]) == lane_post(probe, c.seat, action.target[0])
        strikes = [combat.collect(world) for world in (probe, twin)]
        assert fighters_hits(twin, team, strikes[1]) == fighters_hits(probe, team, strikes[0])
        on_team = [[(hit.attacker, hit.victim, hit.damage) for hit in hits if hit.victim // 5 == team] for hits in strikes]
        if on_team[0] != on_team[1]:
            continue
        assert [hit for hit in strikes[1] if hit.attacker // 5 == team] == [hit for hit in strikes[0] if hit.attacker // 5 == team]
        # Whether a champion of the team is harassing follows its own hits, the answers included.
        calls = [combat.harassed(world, hits) for world, hits in zip((probe, twin), strikes)]
        for name in LANES:
            mine = [[inp for inp in lane_inputs(world, name, call) if inp.team == team] for world, call in zip((probe, twin), calls)]
            assert mine[1] == mine[0], f"{name} lane, tick {probe.tick}"
            inputs += len(mine[0])
    assert {Kind.LANE, Kind.FIGHT} <= kinds and inputs >= 100, (kinds, inputs)


def f14_probe(target_order: int, walked: bool) -> World:
    """Handoff 007 F14. A carry fights a jungler in its view, which has walked off for two ticks or held 625 units
    away, just out of the carry's range. Then the jungler's intent is set to `target_order`, where it stands, and
    the red mid laner stands 50 units further along the lane. Returns the world on that tick, before it runs."""
    start = mid(600.0) if walked else mid(800.0)
    world = quiet_world({BLUE_CARRY: mid(-300.0 if walked else 0.0), RED_JUNGLE: start, RED_MID: mid(3000.0), BLUE_TOP: mid(-2500.0)})
    world.step()
    submit(world, {BLUE_CARRY: act(Kind.FIGHT, JUNGLE)} | ({RED_JUNGLE: move("own_base")} if walked else {}))
    if walked:
        world.step()
    jungler = world.champions[RED_JUNGLE]
    jungler.intent = target_order
    world.champions[RED_MID].pos = RIFT.lane_pos("mid", RIFT.lane_s("mid", jungler.pos) + 50.0)
    return world


@pytest.mark.parametrize("walked", [True, False], ids=["after a walk", "after a hold"])
def test_a_fighter_moves_the_same_against_a_target_that_walks_follows_or_fights_from_equal_observations(walked):
    orders = [move("own_base"), act(Kind.FOLLOW, MID), act(Kind.FIGHT, TOP)]
    worlds = [f14_probe(order, walked) for order in orders]
    assert all(knowledge(world, 0) == knowledge(worlds[0], 0) for world in worlds)
    assert observe_team(worlds[0], 0)[0].enemies[JUNGLE] is not None, "blue sees the jungler"
    stood = worlds[0].champions[BLUE_CARRY].pos
    for world in worlds:
        world.step()
    assert len({world.champions[RED_JUNGLE].pos for world in worlds}) == 3, "the three intents walk the jungler three ways"
    assert len({tuple(c.pos for c in team_of(world, 0)) for world in worlds}) == 1, "and blue walks one way"
    walk = RIFT.distance(stood, worlds[0].champions[BLUE_CARRY].pos)
    assert walk == pytest.approx(175.0 if walked else 75.0), "a full step after the walk, and to its range of where it saw the jungler after the hold"


@pytest.mark.parametrize("seed", [2, 6])
def test_random_legal_games_give_both_teams_moves_that_no_private_field_of_a_visible_enemy_changes(seed):
    """Random legal actions for every seat: every intent kind, rings of fights and chains of followers. On every
    16th tick each team's visible enemies get new private fields in a copy, and the team's moves are compared."""
    world = World(seed=seed)
    rng, compared = random.Random(seed), 0
    for _ in range(600):
        if world.tick % 16 == 0:
            for team in (0, 1):
                if any(ACTIONS[c.intent].kind is Kind.RECALL for c in team_of(world, team)):
                    continue
                probe, twin = World.restore(world.snapshot()), World.restore(world.snapshot())
                for copy in (probe, twin):
                    heal_team(copy, team)
                visible = [c.seat for c, record in zip(team_of(twin, 1 - team), twin.memory[team].enemies) if c.hp > 0 and record.seen_tick == twin.tick]
                for seat in visible:
                    change_private(twin.champions[seat], twin.tick, rng)
                assert knowledge(twin, team) == knowledge(probe, team)
                actions = [random_legal(o, keyed_uniform(seed, Stream.POLICY, seat, probe.tick)) if seat // 5 == team else KEEP
                           for seat, o in enumerate((*observe_team(probe, 0), *observe_team(probe, 1)))]
                actions = [action if probe.champions[seat].hp > 0 else KEEP for seat, action in enumerate(actions)]
                for copy in (probe, twin):
                    copy.step(actions)
                assert [c.pos for c in team_of(twin, team)] == [c.pos for c in team_of(probe, team)], f"tick {world.tick}, team {team}"
                compared += bool(visible)
        actions = None
        if world.tick % world.config.decision_ticks == 0:
            actions = [random_legal(o, keyed_uniform(seed, Stream.POLICY, seat, world.tick)) for seat, o in
                       enumerate((*observe_team(world, 0), *observe_team(world, 1)))]
        world.step(actions)
    assert compared >= 20, compared
