"""Pursuit and the automatic behaviour of a team read only what the team knows, also of the enemies it sees.

A team sees where an enemy champion stands, its health, level, and upgrades. It does not see what the enemy
intends or how its last intent ended, its XP within the level, its gold, mana, attack credit, ward charges, lockdown
cooldown, item charges, Homeguard, or slow. Every champion picks where it heads from the state at the start of the
move step, by its team's memory alone, so two worlds that differ only in those fields of visible enemies give the
team the same observations and the same moves on that tick (handoff 007, F14).

Within that limit a faster fighter keeps or regains contact. On a lane, a jungle path, and a base edge it closes by
its speed edge, keeps a slowed target in range when the slow ends, and keeps a target that stops or turns back.
"""

import random
from functools import cache

import pytest

from riftgame import combat
from riftgame.champions import (ACTIONS, FOE, HOLD, KEEP, LANES, NO_HOMEGUARD, RIFT, Champion, Income, Kind, Outcome, capability, capability_of,
                                lane_post, level_of)
from riftgame.economy import lane_inputs
from riftgame.harness import random_legal
from riftgame.rng import Stream, keyed_uniform
from riftgame.vision import observe_team
from riftgame.world import Config, World, check_invariants
from test_combat import calm, grow, heal, struck
from test_vision import ENEMIES, GAMES, advance, game, knowledge, mid, quiet_world, team_of, varied
from worlds import BLUE_CARRY, BLUE_JUNGLE, BLUE_TOP, RED_JUNGLE, RED_MID, act, move, submit

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
        # A full tower ramp kills a healed support in one shot, so a death can fall on the step. It must fall in both
        # worlds alike, and a moment with one does not count, as a death sends the champion to its fountain in both.
        died = [[seat for seat in living if world.champions[seat].hp <= 0] for world in (probe, twin)]
        assert died[0] == died[1], f"tick {probe.tick - 1}"
        assert [c.pos for c in team_of(twin, team)] == [c.pos for c in team_of(probe, team)], f"tick {probe.tick - 1}"
        if died[0]:
            continue
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
    world = World(Config(tick_s=0.5, decision_ticks=4), seed=seed)
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


# Three ways a chase runs along, each from its first node toward its second, with the node that a blue target walks to
# on it, and the way's detour, its route length over its straight length, from [detour] of map_summoners_rift_m8.toml.
WAYS = {"mid lane": ("mid_river", "blue_base", "own_base", 1.0), "jungle path": ("blue_raptors", "blue_red", "own_krugs", 1.15),
        "base edge": ("blue_base", "blue_fountain", "own_fountain", 1.0)}


def along(way: str, units: float):
    start, toward, _, _ = WAYS[way]
    return RIFT.advance(RIFT.at(start), RIFT.at(toward), units)


def pursue(way: str, fighter: int, fighter_boots: int, target: int, target_boots: int, at: float, gap: float, ticks: int,
           fight_from: int = 0, walk_from: int = 0, goal: str | None = None, then: dict | None = None, mana: bool = False) -> tuple:
    """A red level 1 `fighter` fights a blue level 1 `target` on `way`, with every tower down. The target stands `at`
    units along the way and the fighter `gap` units behind it. The target walks on toward `goal`, by default the
    way's node, from tick `walk_from`, and the fighter fights from tick `fight_from`. `then` gives the target other
    orders by tick. Only the fighter may have mana, and only with `mana`. Returns per tick whether the fighter hit the
    target, the route between them after the tick, the target's step, and the fighter's place."""
    _, _, node, detour = WAYS[way]
    near, far = along(way, at - gap), along(way, at)
    assert RIFT.distance(near, far) == pytest.approx(gap) and RIFT.separation(near, far) == pytest.approx(gap / detour), "one edge"
    world = calm({fighter: near, target: far}, towers=False)
    grow(world, fighter, 1, fighter_boots)
    grow(world, target, 1, target_boots)
    me, foe = world.champions[fighter], world.champions[target]
    foe.mana = 0.0
    if not mana:
        me.mana = 0.0
    world.step()
    script = {walk_from: {target: move(goal or node)}}
    script.setdefault(fight_from, {})[fighter] = act(Kind.FIGHT, target % 5)
    for tick, order in (then or {}).items():
        script.setdefault(tick, {})[target] = order
    hits, gaps, steps, places = [], [], [], []
    for tick in range(ticks):
        stood = foe.pos
        submit(world, script.get(tick, {}))
        hits.append(struck(world, fighter, target))
        gaps.append(RIFT.distance(me.pos, foe.pos))
        steps.append(RIFT.distance(stood, foe.pos))
        places.append(me.pos)
        heal(world)
    return hits, gaps, steps, places


@pytest.mark.parametrize("way", WAYS)
def test_a_faster_fighter_closes_by_its_speed_edge_on_every_tick_and_then_hits_on_every_tick(way):
    """A red jungler with both boot steps walks 195 a tick and chases a blue carry without boots, which walks 162.5,
    from 380 units behind, more than its step outside its range of 175. Its team sees the carry step away, so it
    heads past the place where it saw the carry and walks its full step on every tick, gaining its edge of 32.5. It
    is in range once the route is at most its range times the way's detour, and it hits on every tick from then on,
    on the jungle path across the fork at the Red Brambleback, and on the base edge after the carry has reached its
    fountain. Before campaign 5 a fighter off the lanes stopped at its range of the place it saw, so the carry's step
    kept it 337.5 behind on the jungle path and on the base edge for good."""
    jungler, carry = capability("jungle", 1, 2), capability("carry", 1, 0)
    mine, theirs, reach = jungler.move_speed / 2, carry.move_speed / 2, jungler.attack_range
    assert (mine, theirs, reach) == (195.0, 162.5, 175.0)
    hits, gaps, _, _ = pursue(way, RED_JUNGLE, 2, BLUE_CARRY, 0, at=400.0, gap=380.0, ticks=12)
    closing = [380.0 - (mine - theirs) * (tick + 1) for tick in range(12)]
    contact = next(tick for tick, route in enumerate(closing) if route <= reach * WAYS[way][3])
    assert contact == (5 if way == "jungle path" else 6)
    assert gaps[:contact + 1] == pytest.approx(closing[:contact + 1])
    assert hits == [False] * contact + [True] * (12 - contact)


def test_a_fighter_heads_for_its_range_of_where_its_team_saw_a_target_that_walks_toward_it():
    """A red jungler that walks 195 a tick fights a blue carry that walks 162.5 toward it down mid lane from 600
    units. Its team sees the carry come nearer, so it leads nothing: it heads for its range of 175 from where its team
    saw the carry. The route closes by both steps on the first tick, to 242.5, and on the second the jungler walks the
    67.5 to its range of that place while the carry walks its step, which leaves 12.5. A fighter that led the carry
    one more step would stand still on the second tick and stay 80 away."""
    hits, gaps, _, _ = pursue("mid lane", RED_JUNGLE, 2, BLUE_CARRY, 0, at=700.0, gap=600.0, ticks=2, goal="mid_river")
    assert gaps == pytest.approx([600.0 - 195.0 - 162.5, 12.5])
    assert hits == [False, True]


@pytest.mark.parametrize("way, gap", [("mid lane", 300.0), ("jungle path", 400.0), ("base edge", 300.0)])
def test_a_slower_fighter_falls_behind_by_its_speed_deficit_on_every_tick_and_stops_hitting(way, gap):
    """A red mid laner without boots walks 167.5 a tick and fights a blue jungler with its first boots, which walks
    185, from inside its range of 525. On the first tick its team has seen the jungler only stand, so it holds, and
    the jungler's step opens the route by 185. From then on it walks its full step after the jungler and loses 17.5 on
    every tick. It hits while the straight line, the route over the way's detour, is within its range."""
    reach = capability("mid", 1, 0).attack_range
    hits, gaps, _, _ = pursue(way, RED_MID, 0, BLUE_JUNGLE, 1, at=gap + 20.0, gap=gap, ticks=6)
    expected = [gap + 185.0 + 17.5 * tick for tick in range(6)]
    assert gaps == pytest.approx(expected)
    assert hits == [route <= reach * WAYS[way][3] for route in expected]
    assert hits[:2] == [True, True] and hits[-1] is False


@pytest.mark.parametrize("way, at, ticks", [("mid lane", 400.0, 14), ("jungle path", 300.0, 13), ("base edge", 200.0, 10)])
def test_a_faster_fighter_keeps_a_slowed_target_in_range_on_every_tick_after_the_slow_ends(way, at, ticks):
    """The pair of the gank of experiments/m8/combat.py. A red jungler that walks 185 a tick hits a blue top laner
    that walks 182.5 from 150 units, and its lockdown slows the top laner by 0.4 for four ticks. The top laner walks
    off on the next tick, which costs the jungler that tick, as its team saw the top laner stand. While slowed the
    top laner steps 109.5, and the jungler ends 2 * 109.5 - 175 = 44 past the place where its team saw it, 65.5
    behind it. From there any next step up to 219 stays in range, so the first full step of 182.5 after the slow
    leaves the top laner 138.5 away. From then on its step is longer than the range, the jungler heads for its range
    of the led place, and its edge of 2.5 a tick covers the rest. So from the third tick on it hits on every tick,
    across the end of the slow and, on the jungle path, across the fork at the Red Brambleback on tick 11. Before
    campaign 5 the jungler stood at its range of the led place, and the end of the slow left it 248 behind."""
    jungler = capability("jungle", 1, 1)
    assert (jungler.move_speed / 2, capability("top", 1, 1).move_speed / 2, jungler.lockdown_slow, jungler.lockdown_s) == (185.0, 182.5, 0.4, 2.0)
    hits, gaps, steps, _ = pursue(way, RED_JUNGLE, 1, BLUE_TOP, 1, at=at, gap=150.0, ticks=ticks, walk_from=1, mana=True)
    assert steps == pytest.approx([0.0] + [109.5] * 4 + [182.5] * (ticks - 5))
    assert gaps == pytest.approx([150.0, 259.5, 184.0, 108.5, 65.5, 138.5] + [175.0] * (ticks - 6))
    assert hits == [True, False, 184.0 <= 175.0 * WAYS[way][3]] + [True] * (ticks - 3)


@pytest.mark.parametrize("then", ["stops", "turns back"])
@pytest.mark.parametrize("target, boots, step", [(BLUE_CARRY, 0, 162.5), (BLUE_TOP, 1, 182.5)], ids=["step 162.5", "step 182.5"])
def test_a_led_target_that_stops_or_turns_back_stays_in_range_unless_its_step_is_longer_than_the_range(target, boots, step, then):
    """A red jungler with both boot steps, 195 a tick and a range of 175, stands on a blue champion that walks off
    down mid lane, and fights it from the next tick. On tick 6 the target stops or turns back.

    A carry without boots steps 162.5. The jungler ends 175 - 162.5 = 12.5 past the place where its team saw it, 150
    behind it, from where a target that stops is 12.5 away and one that turns back by its step is 175 away. Both are
    in range, and the jungler leads the turned target from the next tick. A top laner with its first boots steps
    182.5, longer than the range. The jungler ends 7.5 past the seen place, 175 behind it, which keeps a stop in
    range. No place keeps both one more step and a step back in range, as they are 365 apart and the range spans 350,
    so the turn leaves the top laner 190 away. The jungler then closes by its edge of 12.5 and is in range again on
    tick 8."""
    assert capability("carry" if target == BLUE_CARRY else "top", 1, boots).move_speed / 2 == step
    orders = {6: HOLD if then == "stops" else move("enemy_base")}
    hits, gaps, _, _ = pursue("mid lane", RED_JUNGLE, 2, target, boots, at=400.0, gap=0.0, ticks=10, fight_from=1, then=orders)
    steady, after = {("stops", 162.5): (150.0, [12.5] * 4), ("turns back", 162.5): (150.0, [175.0] + [150.0] * 3),
                     ("stops", 182.5): (175.0, [7.5] * 4), ("turns back", 182.5): (175.0, [190.0, 177.5, 175.0, 175.0])}[then, step]
    assert gaps == pytest.approx([step] + [steady] * 5 + after)
    assert hits == [False] + [True] * 5 + [route <= 175.0 for route in after]


# Two forks. One is where a jungle path meets two others, the other the end of a lane, where the other lanes and the
# path to the fountain meet. Per fork the way to it, the node, the target's start, and the three places it may walk on to.
FORKS = {"Red Brambleback": ("jungle path", "blue_red", 1300.0, ("own_krugs", "bot_river", "own_mid_t2")),
         "blue base": ("mid lane", "blue_base", None, ("own_fountain", "own_top_exit", "own_bot_exit"))}


@pytest.mark.parametrize("fork", FORKS)
def test_at_a_fork_a_fighter_keeps_the_target_in_range_on_any_branch_and_walks_the_same_until_its_team_sees_which(fork):
    """A red jungler with both boot steps chases a blue top laner to a fork, along the jungle path from the blue
    Raptors to the Red Brambleback, and down mid lane to the blue base. The top laner steps 182.5, longer than the
    range, so the jungler keeps it 175 away. On tick 3 the next step would carry the top laner past the fork, and the
    jungler heads no further than the fork, as its team cannot tell which branch the top laner takes.

    At the Brambleback the top laner is 6.5 short of the fork and ends about 176 past it. The jungler heads for the
    fork itself, about 176 from the top laner on any branch, which the path's detour of 1.15 puts in range. At the
    base the top laner is 50 short and ends 132.5 past it. The jungler heads for 175 - 132.5 = 42.5 short of the
    base, 175 from the top laner on any branch. From the next tick it leads the top laner along its branch. Heading
    for its range of the fork instead would leave it about 351 and 307.5 behind."""
    way, node, at, branches = FORKS[fork]
    to_node = RIFT.distance(RIFT.at(WAYS[way][0]), RIFT.at(node))
    at = to_node - 50.0 - 3 * 182.5 if at is None else at
    runs = [pursue(way, RED_JUNGLE, 2, BLUE_TOP, 1, at=at, gap=0.0, ticks=8, fight_from=1, goal=goal) for goal in branches]
    short = to_node - (at + 3 * 182.5)
    assert short == pytest.approx(50.0 if fork == "blue base" else 6.54, abs=0.01)
    for hits, gaps, steps, _ in runs:
        assert steps == pytest.approx([182.5] * 8)
        assert gaps == pytest.approx([182.5, 175.0, 175.0, max(175.0, 182.5 - short)] + [175.0] * 4)
        assert hits == [False] + [True] * 7
    assert len({tuple(run[3][:4]) for run in runs}) == 1, "the same walk until the team sees the branch"
    assert len({run[3][4] for run in runs}) == 3, "and three walks after"
    assert RIFT.distance(runs[0][3][3], RIFT.at(node)) == pytest.approx(max(0.0, 175.0 - (182.5 - short)))


@pytest.mark.parametrize("way", WAYS)
@pytest.mark.parametrize("step", [60.0, 100.0, 116.0, 350.0 / 3.0, 116.7, 117.0, 140.0, 175.0])
def test_a_faster_fighter_in_contact_keeps_a_target_that_steps_steadily_away_in_range_on_every_tick(way, step):
    """A red jungler with both boot steps, 195 a tick and a range of 175, stands on a blue carry that walks off
    along the way with a lasting slow that sets its step. For every step up to the range the fighter is at least as
    fast, so after the first tick, which it loses because its team has seen the carry only stand, it hits on every
    tick. Around 2/3 of the range the fighter's own place decides whether its team's record still shows the carry
    walking away from it. At exactly 2/3 the fighter ends half a step behind, the record ties, and the fighter stands
    for a tick, which the carry's next step turns into exactly the range, so it still hits."""
    carry = capability("carry", 1, 0)
    slow = 1.0 - step / (carry.move_speed / 2)
    world = calm({RED_JUNGLE: along(way, 400.0), BLUE_CARRY: along(way, 400.0)}, towers=False)
    grow(world, RED_JUNGLE, 1, 2)
    grow(world, BLUE_CARRY, 1, 0)
    fighter, target = world.champions[RED_JUNGLE], world.champions[BLUE_CARRY]
    fighter.mana = target.mana = 0.0
    target.slow, target.slow_until = slow, 10 ** 6
    world.step()
    hits = []
    for tick in range(10):
        submit(world, {0: {BLUE_CARRY: move(WAYS[way][2])}, 1: {RED_JUNGLE: act(Kind.FIGHT, BLUE_CARRY % 5)}}.get(tick, {}))
        hits.append(struck(world, RED_JUNGLE, BLUE_CARRY))
        heal(world)
    assert hits[2:] == [True] * 8, hits
