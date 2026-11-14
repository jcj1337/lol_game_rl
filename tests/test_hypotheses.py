"""C8. The hidden-state generator and the worlds it builds, with the three tests of M7 section 9.3.

Truth-blind. A source and its twin with every hidden field changed (`test_info.hidden_twin`) give the same hypotheses
and the same built worlds, and a builder that copies one true hidden value fails the same comparison. Consistent.
Every built world passes the invariant checker, tells the team what the source tells it, and shows the team, by the
team's own memory rule run again at the decision tick, exactly what the information state says it sees now.
Rejection. Each check rejects a hypothesis written to break it, and passes its twin. The remaining tests show that the
activity decides the fields, and that the enemy's memory is rebuilt by rule.
"""

import math
from dataclasses import fields
from functools import cache

import pytest

from riftgame.champions import (FOUNTAIN, HOLD, HOME, LANES, NODE_POS, NODES, PROGRESSIONS, RECALL_S, RIFT, ROLES, Income, Outcome, R,
                                capability, capability_of, level_of)
from riftgame.clock import refine
from riftgame.harness import tick
from riftgame.hypotheses import H, Activity, Hypothesis, Plan, Reason, Rejected, activity_v0, check, generate, realize
from riftgame.info import band_floor, redact
from riftgame.jungle import SCUTTLERS, SITES
from riftgame.lanes import Mode, stance
from riftgame.policies import STANDARD, styled, team_policies
from riftgame.vision import CampMemory, EnemyMemory, _wave_seen, new_memory, remember_team, sees
from riftgame.world import Config, Snapshot, World, _plain, check_invariants
from test_info import hidden_twin
from test_vision import ENEMIES, GAMES, SLACK, SNAPSHOTS, advance, game, knowledge, lit, sources_of, varied

JUNGLE, MID = ROLES.index("jungle"), ROLES.index("mid")
FOCI = (None, (0,), (2,), (1, 3))
# The tests that read exact ticks of a game play it on one of these clocks, whatever the default clock is.
PINNED = Config(tick_s=0.5, decision_ticks=4)
QUARTER = Config(tick_s=0.25, decision_ticks=8)
# The tests that find their state in the games by a criterion hold on both clocks.
CLOCKS = pytest.mark.parametrize("config", [Config(), PINNED], ids=lambda config: f"tick_{config.tick_s}")
# The game times of the snapshots of `tests/test_vision.py`, so that a search looks at the same moments on any clock.
TIMES_S = tuple(ticks * PINNED.tick_s for ticks in SNAPSHOTS)
# The snapshots of `tests/test_vision.py`, as (seed, enemy, team, ticks), at which `activity_v0` finds no hypothesis, a
# limit of the generator. Blue at 600 s of game (8, varied): red's jungler respawned at 564.5 s and is a level higher
# now, and in truth it killed red_gromp at 598.5 s. The generator's clear of that camp ends at 605.2 s, because it
# walks from the fountain without Homeguard, lands no ready attack, and gives the camp the average level now.
REFUSED = frozenset({(8, "varied", 0, 1200)})


def refused(seed: int, enemy: str, team: int, ticks: int, info) -> bool:
    """Whether the snapshot is one of `REFUSED`. There the generator must raise, so the entry goes once it does not."""
    if (seed, enemy, team, ticks) not in REFUSED:
        return False
    for focus in FOCI:
        with pytest.raises(Rejected) as caught:
            activity_v0(info, focus)
        assert caught.value.reason is Reason.INCONSISTENT, caught.value
    return True


@cache
def _pinned(seed: int, enemy: str, team: int, ticks: int, config: Config) -> Snapshot:
    world = World(config, seed)
    policies = (varied, ENEMIES[enemy]) if team == 0 else (ENEMIES[enemy], varied)
    while world.tick < ticks:
        advance(world, policies)
    return world.snapshot()


def pinned(seed: int, enemy: str, team: int, ticks: int, config: Config = PINNED) -> World:
    """The game of `tests/test_vision.py` with these arguments, played on a pinned clock."""
    return World.restore(_pinned(seed, enemy, team, ticks, config))


@cache
def _played(seed: int, enemy: str, team: int, config: Config) -> tuple[Snapshot, ...]:
    world = World(config, seed)
    policies = (varied, ENEMIES[enemy]) if team == 0 else (ENEMIES[enemy], varied)
    marks = [config.ticks(seconds) for seconds in TIMES_S]
    taken = []
    while world.tick < marks[-1]:
        advance(world, policies)
        if world.tick in marks:
            taken.append(world.snapshot())
    return tuple(taken)


def states(config: Config):
    """Every game of `tests/test_vision.py` played on this clock, at the times of its snapshots, in order, as
    (team, world)."""
    for seed, enemy in GAMES:
        for team in (0, 1):
            for snapshot in _played(seed, enemy, team, config):
                yield team, World.restore(snapshot)


def hidden_junglers(config: Config):
    """The states of `states` in which the team does not see the living enemy jungler and has seen it before, as
    (info, record)."""
    for team, world in states(config):
        info = redact(world, team)
        record = info.world().memory[team].enemies[JUNGLE]
        if not info.seen[JUNGLE] and world.champions[(1 - team) * 5 + JUNGLE].hp > 0 and record.seen_tick >= 0:
            yield info, record


def remembered(memory) -> list:
    """A team's memory without `was`, which a second run of the memory rule on one tick moves along."""
    return [tuple(getattr(record, f.name) for f in fields(record) if f.name != "was")
            for record in (*memory.camps, *memory.enemies, *memory.waves, *memory.towers)]


def seen_again(world: World, team: int) -> list:
    """The team's memory after its own memory rule looks at `world` once more for the tick that just ended."""
    looked = World.restore(world.snapshot())
    remember_team(looked, team, looked.tick - 1)
    return remembered(looked.memory[team])


@pytest.mark.parametrize("seed, enemy", GAMES)
@pytest.mark.parametrize("team", [0, 1])
def test_every_built_world_is_valid_and_shows_the_team_exactly_its_information_state(team, seed, enemy):
    built = 0
    for ticks in SNAPSHOTS:
        world = game(seed, enemy, team, ticks)
        info, told = redact(world, team), knowledge(world, team)
        if refused(seed, enemy, team, ticks, info):
            continue
        known = remembered(info.world().memory[team])
        for focus in FOCI:
            for h in activity_v0(info, focus):
                check(info, h)
                state = realize(info, h, 0)
                check_invariants(state)
                assert knowledge(state, team) == told, f"tick {ticks}, {h.name}"
                assert seen_again(state, team) == known, f"tick {ticks}, {h.name}"
                assert minions_seen(state, team) == minions_seen(info.world(), team), f"tick {ticks}, {h.name}"
                assert placed_past_the_lead(info, state) == [], f"tick {ticks}, {h.name}"
                built += 1
    assert built >= 20, built


def minions_seen(world: World, team: int) -> list:
    """The enemy minions that the team sees in each lane, by the kernel's sight of a lane."""
    return [sorted(m.uid for m in _wave_seen(world, team, name)[0]) for name in LANES]


def placed_past_the_lead(info, state: World) -> list:
    """The enemy minions that a built world adds to the information state and puts past the team's lead minion of
    their lane, which they would have had to walk through."""
    team, past = info.team, []
    kept = info.world()
    for name in LANES:
        sim, ahead = state.lanes[name], state.lanes[name].geometry.direction(1 - team)
        known = {m.uid for m in kept.lanes[name].minions[1 - team]}
        if sim.minions[team]:
            lead = min(ahead * m.s for m in sim.minions[team])
            past += [(name, m.uid) for m in sim.minions[1 - team] if m.uid not in known and ahead * m.s > lead]
    return past


def test_no_minion_of_the_schedule_is_put_behind_the_teams_wave_or_where_the_team_sees():
    """At tick 1256 blue's outer mid tower falls, every red minion in mid dies, and blue's jungler stands on its
    fountain, so blue no longer sees the lane between its inner tower and the back of its wave. Every minion of both
    teams in bot dies too. A red minion of the schedule whose untouched march ends behind blue's wave died at the
    front, and one whose march ends where blue sees would be seen, so neither is put there."""
    world = pinned(5, "scripted", 0, 1256)
    mid, bot = world.lanes["mid"], world.lanes["bot"]
    mid.towers[0][0].hp = 0.0
    mid.minions[1].clear()
    bot.minions[0].clear()
    bot.minions[1].clear()
    for sim in (mid, bot):
        for m in sim.minions[0]:
            m.target, m.swing_at, m.aimed = None, None, None
        sim._missiles = []
        sim.invalidate()
    jungler = world.champions[JUNGLE]
    jungler.pos, jungler.intent = FOUNTAIN[0], HOLD
    for team in (0, 1):
        remember_team(world, team, world.tick - 1)
    info = redact(world, 0)
    for h in activity_v0(info):
        state = realize(info, h, 0)
        check_invariants(state)
        assert placed_past_the_lead(info, state) == [] and minions_seen(state, 0) == minions_seen(info.world(), 0)


def test_a_minion_of_the_schedule_that_would_stand_in_the_teams_view_is_not_placed():
    """At tick 684 of this game an untouched march would put red minions of bot lane where blue sees, and blue sees none
    of them there."""
    info = redact(pinned(5, "scripted", 0, 684), 0)
    for h in activity_v0(info):
        state = realize(info, h, 0)
        assert minions_seen(state, 0) == minions_seen(info.world(), 0), h.name


def test_unseen_camps_that_no_path_clears_follow_the_teams_memory_and_the_timer_rule():
    """A spawn that the team knows holds. A camp last seen alive is alive at the level seen. A camp last seen empty
    with no known spawn died `unseen_death_s` before that sighting, and at least two ticks before it."""
    checked = 0
    for seed, enemy in GAMES:
        for team in (0, 1):
            info = redact(game(seed, enemy, team, 1200), team)
            if refused(seed, enemy, team, 1200, info):
                continue
            for h in activity_v0(info):
                state = realize(info, h, 0)
                cleared = {camp for plan in h.plans if plan for camp in plan.path}
                for i, (camp, mine, site) in enumerate(zip(state.camps, state.memory[team].camps, SITES)):
                    if site.kind.scuttler or i in cleared or mine.seen_tick == state.tick:
                        continue
                    if mine.spawn_tick >= 0:
                        due = mine.spawn_tick
                    elif mine.hp > 0:
                        due = -1
                        assert camp.level == mine.level
                    else:
                        due = unseen_death(state.config, mine.seen_tick) + state.config.ticks(site.kind.respawn_s)
                    alive = due <= state.tick
                    assert (camp.hp > 0, camp.spawn_tick) == (alive, -1 if alive else due), (seed, team, site.node)
                    checked += 1
    assert checked >= 100, checked


def unseen_death(config: Config, seen: int) -> int:
    """The latest tick on which a camp that the team saw empty on tick `seen` without learning its spawn died: before
    the look's own tick, and `unseen_death_s` before the sighting."""
    return seen - max(2, config.ticks(H["unseen_death_s"]))


def blind(world: World, twin: World, team: int, build) -> list:
    """What differs between a source and its hidden twin, for every focus. That is the hypotheses, or a built world."""
    info, other = redact(world, team), redact(twin, team)
    differ = []
    for focus in FOCI:
        hypotheses = activity_v0(info, focus)
        if activity_v0(other, focus) != hypotheses:
            differ.append((focus, "hypotheses"))
            continue
        differ += [(focus, h.name, rollout) for h in hypotheses for rollout in (0, 1)
                   if build(info, h, rollout, world).digest() != build(other, h, rollout, twin).digest()]
    return differ


def honest(info, h, rollout, source) -> World:
    return realize(info, h, rollout)


def leaky(info, h, rollout, source) -> World:
    """A builder that copies the enemy jungler's true health from the source."""
    world = realize(info, h, rollout)
    seat = (1 - info.team) * 5 + JUNGLE
    world.champions[seat].hp = source.champions[seat].hp
    return world


@pytest.mark.parametrize("seed, enemy", GAMES)
@pytest.mark.parametrize("team", [0, 1])
def test_changing_every_hidden_field_changes_neither_the_hypotheses_nor_any_world_built_from_them(team, seed, enemy):
    compared = 0
    for ticks in SNAPSHOTS:
        world = game(seed, enemy, team, ticks)
        if refused(seed, enemy, team, ticks, redact(world, team)):
            continue
        assert blind(world, hidden_twin(world, team, seed * 100 + ticks), team, honest) == [], f"tick {ticks}"
        compared += sum(len(activity_v0(redact(world, team), focus)) for focus in FOCI)
    assert compared >= 20, compared


def test_the_truth_blind_comparison_fails_for_a_builder_that_copies_one_true_hidden_value():
    leaks = []
    for seed, enemy in GAMES:
        for ticks in SNAPSHOTS:
            world = game(seed, enemy, 0, ticks)
            if refused(seed, enemy, 0, ticks, redact(world, 0)):
                continue
            twin = hidden_twin(world, 0, seed * 100 + ticks)
            assert blind(world, twin, 0, honest) == []
            leaks += blind(world, twin, 0, leaky)
    assert leaks, "the leak of the jungler's true health is seen"


# The enemy jungler of blue in this game was last seen by red 30.5 s before tick 824. It stays, recalls, and clears
# without failing a check, and its default path clears blue_red.
ELAPSED_S = 30.5


@cache
def hidden_jungler():
    world = pinned(8, "varied", 1, 824)
    info = redact(world, 1)
    record = info.world().memory[1].enemies[JUNGLE]
    assert not info.seen[JUNGLE] and (info.snapshot.tick - record.seen_tick) * PINNED.tick_s == ELAPSED_S
    return world, info, record


def alone(plan: Plan, cleared: tuple[int, ...] = (), role: int = JUNGLE) -> Hypothesis:
    """A hypothesis that gives the enemy of `role` the plan and every other enemy its default."""
    return Hypothesis("by hand", 1.0, tuple(plan if other == role else None for other in range(5)), cleared)


def verdict(info, h) -> Reason | None:
    try:
        check(info, h)
    except Rejected as error:
        return error.reason
    return None


def jungler_speed(record) -> float:
    return capability("jungle", record.level, record.upgrades).move_speed


def test_a_path_out_of_reach_is_rejected_and_a_path_in_reach_passes():
    """Blue's six camps take longer to fight at their least health than the 30.5 s since the sighting."""
    _, info, record = hidden_jungler()
    every = (4, 5, 3, 0, 1, 2)
    assert sum(SITES[i].kind.health(1) for i in every) / capability("jungle", record.level, record.upgrades).camp_dps > ELAPSED_S
    assert verdict(info, alone(Plan(Activity.CLEAR, every))) is Reason.UNREACHABLE
    assert verdict(info, alone(Plan(Activity.CLEAR, (4,)))) is None


def test_a_place_in_the_teams_view_is_rejected_and_one_out_of_it_passes():
    world, info, record = hidden_jungler()
    watched, mine = [], sources_of(world, 1)
    walk = jungler_speed(record) * ELAPSED_S
    for node in NODES:
        place = NODE_POS[0][node]
        if RIFT.distance(record.pos, place) < 0.9 * walk:
            watched.append((lit(mine, place, -SLACK), not lit(mine, place, SLACK), node))
    seen = next(node for inside, _, node in watched if inside)
    hidden = next(node for _, outside, node in watched if outside)
    assert verdict(info, alone(Plan(Activity.MOVE, to=seen))) is Reason.IN_VIEW
    assert verdict(info, alone(Plan(Activity.MOVE, to=hidden))) is None


def test_xp_outside_the_public_level_is_rejected_and_xp_inside_it_passes():
    world, info, _ = hidden_jungler()
    level = level_of(world.champions[JUNGLE].xp)
    assert verdict(info, alone(Plan(Activity.STAY, xp=band_floor(level + 1)))) is Reason.XP_BAND
    assert verdict(info, alone(Plan(Activity.STAY, xp=band_floor(level)))) is None


def test_a_stay_is_rejected_for_an_enemy_whose_public_level_rose_since_the_sighting_because_staying_earns_no_xp():
    rose = 0
    for seed, enemy in GAMES:
        for team in (0, 1):
            for ticks in SNAPSHOTS:
                world = game(seed, enemy, team, ticks)
                info = redact(world, team)
                record = info.world().memory[team].enemies[JUNGLE]
                if info.seen[JUNGLE] or world.champions[(1 - team) * 5 + JUNGLE].hp <= 0 or record.seen_tick < 0:
                    continue
                if level_of(world.champions[(1 - team) * 5 + JUNGLE].xp) > record.level:
                    assert verdict(info, alone(Plan(Activity.STAY))) is Reason.XP_BAND
                    rose += 1
    assert rose >= 3, rose


def test_a_laner_last_seen_on_its_fountain_a_second_ago_cannot_be_farming_its_lane():
    """Blue sees red's top laner at tick 1200. Its record is moved to red's fountain one second before, and every place
    of top lane is further from there than the laner walks in a second."""
    world = pinned(5, "scripted", 0, 1200)
    record = world.memory[0].enemies[0]
    record.pos, record.seen_tick = FOUNTAIN[1], world.tick - world.config.ticks(1.0)
    info = redact(world, 0)
    lane = RIFT.lanes["top"]
    nearest = min(RIFT.distance(FOUNTAIN[1], RIFT.lane_pos("top", s)) for s in range(0, int(lane.length), 100))
    assert not info.seen[0] and nearest > capability("top", record.level, record.upgrades).move_speed * 1.0
    assert verdict(info, alone(Plan(Activity.FARM), role=0)) is Reason.UNREACHABLE


@CLOCKS
def test_the_river_keeps_one_scuttler_at_the_node_of_the_latest_knowledge(config):
    """The state is the first of the games in which the team sees neither river node, more than 180 s after the first
    Scuttlers spawned. The team's memory of the river is then written. It saw one node empty 40 s ago and knows its
    spawn 20 s from now. It still holds a spawn for the other node from a death that it saw 180 s ago, and that spawn
    has passed without a look since. Only one Scuttler can be due, so the built world keeps the one of the latest
    sighting, whichever node that is."""
    kind = SITES[SCUTTLERS[0]].kind
    found = next(((team, world) for team, world in states(config)
                  if all(world.memory[team].camps[i].seen_tick != world.tick for i in SCUTTLERS)
                  and world.tick - config.ticks(180.0) > config.ticks(kind.first_spawn_s)), None)
    assert found, "a state in which the team sees neither river node"
    team, world = found
    for latest, stale in (SCUTTLERS, SCUTTLERS[::-1]):
        edited = World.restore(world.snapshot())
        camps, now = edited.memory[team].camps, edited.tick
        due, seen = now + config.ticks(20.0), now - config.ticks(180.0)
        camps[latest] = CampMemory(0.0, 0, now - config.ticks(40.0), due)
        camps[stale] = CampMemory(0.0, 0, seen, seen - 1 + config.ticks(kind.respawn_s))
        assert camps[stale].spawn_tick < now < due
        info = redact(edited, team)
        for h in activity_v0(info):
            state = realize(info, h, 0)
            check_invariants(state)
            assert (state.camps[latest].hp, state.camps[latest].spawn_tick) == (0.0, due), (SITES[latest].node, h.name)
            assert (state.camps[stale].hp, state.camps[stale].spawn_tick) == (0.0, -1), (SITES[stale].node, h.name)


def farming_places(config: Config):
    """The living enemy laners above level 1 that the team does not see in the states of `states`, whose farming
    place the team sees, as (team, world, role, place). The farming place is where a last-hitting laner stands at the
    front of its lane in a built world, which holds the enemy minions that the team does not see."""
    for team, world in states(config):
        info, foe = redact(world, team), 1 - team
        built = realize(info, activity_v0(info)[0], 0)
        for role, lane in enumerate(HOME):
            level = level_of(world.champions[foe * 5 + role].xp)
            if lane is None or info.seen[role] or world.champions[foe * 5 + role].hp <= 0 or level < 2:
                continue
            sim = built.lanes[lane]
            s, _ = stance(sim, foe, Mode.LAST_HIT, capability(ROLES[role], level - 1, 0).attack_range, sim.front())
            if sees(built, team, RIFT.lane_pos(lane, s)):
                yield team, world, role, RIFT.lane_pos(lane, s)


@CLOCKS
def test_a_laner_whose_level_rose_out_of_view_beside_a_front_the_team_sees_farms_from_the_fog(config):
    """The state is the first of `farming_places`. The team's record of the laner is then written. It saw the laner at
    the farming place 15 s ago, at full health and a level below the one it has now, with no upgrades, so that no
    upgrade price raises the laner's ledger. Staying and recalling earn no XP, so only farming explains the level. The
    laner farms from the fog, on its lane, out of the team's view and within XP range of the farming place, and it
    earns no minion gold since the sighting."""
    found = next(farming_places(config), None)
    assert found, "an enemy laner out of view whose farming place the team sees"
    team, world, role, place = found
    lane, seat = HOME[role], (1 - team) * 5 + role
    level = level_of(world.champions[seat].xp) - 1
    record = EnemyMemory(place, None, capability(ROLES[role], level, 0).max_hp, level, 0, world.tick - config.ticks(15.0))
    world.memory[team].enemies[role] = record
    info = redact(world, team)
    for plan in (Plan(Activity.STAY), Plan(Activity.RECALL)):
        assert verdict(info, alone(plan, role=role)) is Reason.XP_BAND
    farm = alone(Plan(Activity.FARM), role=role)
    assert verdict(info, farm) is None
    c = realize(info, farm, 0).champions[seat]
    assert RIFT.lane_s(lane, c.pos) is not None and not sees(info.world(), team, c.pos)
    assert RIFT.separation(place, c.pos) <= R["minions"]["xp_range"]
    estimate = H["farm_gold_per_s"][ROLES[role]] * max(0.0, record.seen_tick * config.tick_s - H["farm_from_s"][ROLES[role]])
    assert c.earned[Income.MINION] == pytest.approx(estimate)


def test_a_jungler_seen_near_death_that_has_levelled_since_recalled_and_then_cleared_from_its_fountain():
    """On the clock of 0.25 s, blue last saw red's jungler with 11 health 81 s before tick 800, and it is a level higher
    now. It died after that sighting, which is public, so its clear from its fountain at the respawn passes. The state
    is then written as if the jungler had lived on. Staying and recalling earn no XP, and a clear from where it was
    seen would kill it, so it recalled first."""
    world = pinned(3, "busy", 0, 800, QUARTER)
    jungler = world.champions[5 + JUNGLE]
    assert jungler.respawned_tick >= world.memory[0].enemies[JUNGLE].seen_tick
    assert any(h.plans[JUNGLE].activity is Activity.CLEAR for h in activity_v0(redact(world, 0)))
    jungler.respawned_tick = -1
    info = redact(world, 0)
    record = info.world().memory[0].enemies[JUNGLE]
    assert not info.seen[JUNGLE] and record.hp < 20.0 and level_of(jungler.xp) > record.level
    for plan in (Plan(Activity.STAY), Plan(Activity.RECALL)):
        assert verdict(info, alone(plan)) is Reason.XP_BAND
    after = [h for h in activity_v0(info) if h.plans[JUNGLE].activity is Activity.RECALL and h.plans[JUNGLE].path]
    assert after
    for h in after:
        path = h.plans[JUNGLE].path
        c = realize(info, h, 0).champions[5 + JUNGLE]
        assert c.outcome is Outcome.CLEARED and c.pos == SITES[path[-1]].pos and c.upgrades >= record.upgrades
        assert verdict(info, alone(Plan(Activity.CLEAR, path))) is Reason.INCONSISTENT


def test_a_camp_cleared_that_no_path_visits_is_rejected_and_one_on_the_path_passes():
    _, info, _ = hidden_jungler()
    path = Plan(Activity.CLEAR, (4,))
    assert verdict(info, alone(path, cleared=(5,))) is Reason.CAMP_UNVISITED
    assert verdict(info, alone(path, cleared=(4,))) is None


def test_upgrades_bought_without_a_visit_to_the_fountain_are_rejected_and_the_seen_ones_pass():
    _, info, record = hidden_jungler()
    assert verdict(info, alone(Plan(Activity.STAY, upgrades=record.upgrades + 1))) is Reason.UPGRADES_WITHOUT_FOUNTAIN
    assert verdict(info, alone(Plan(Activity.STAY, upgrades=record.upgrades))) is None
    assert verdict(info, alone(Plan(Activity.RECALL, upgrades=record.upgrades + 1))) is None


def jungler_in(info, plan: Plan):
    return realize(info, alone(plan), 0).champions[(1 - info.team) * 5 + JUNGLE]


def test_a_stay_heals_by_regeneration_and_keeps_the_last_seen_place():
    world, info, record = hidden_jungler()
    c = jungler_in(info, Plan(Activity.STAY))
    level = level_of(world.champions[JUNGLE].xp)
    regen = capability("jungle", record.level, record.upgrades).hp_regen
    assert c.pos == record.pos and c.hp == pytest.approx(min(capability("jungle", level, record.upgrades).max_hp, record.hp + regen * ELAPSED_S))
    assert c.hp > record.hp


@CLOCKS
def test_a_move_walks_the_route_at_its_speed_for_the_elapsed_time(config):
    """A move that passes the checks toward a place more than 500 units beyond what the hidden enemy jungler walks in
    the time since the sighting stops on the route after that walk. One toward a place more than 500 units short of it
    ends there. The test checks the states of `hidden_junglers` that have three places of each kind, in order, until
    one has three moves of each kind that pass."""
    for info, record in hidden_junglers(config):
        walk =jungler_speed(record) * (info.snapshot.tick - record.seen_tick) * config.tick_s
        routes = {node: RIFT.distance(record.pos, NODE_POS[1 - info.team][node]) for node in NODES}
        if sum(route > walk + 500.0 for route in routes.values()) < 3 or sum(route < walk - 500.0 for route in routes.values()) < 3:
            continue
        moved = near = 0
        for node, route in routes.items():
            plan, goal = Plan(Activity.MOVE, to=node), NODE_POS[1 - info.team][node]
            if abs(route - walk) <= 500.0 or verdict(info, alone(plan)) is not None:
                continue
            c = jungler_in(info, plan)
            if route > walk:
                assert RIFT.distance(record.pos, c.pos) == pytest.approx(walk), node
                assert RIFT.distance(record.pos, c.pos) + RIFT.distance(c.pos, goal) == pytest.approx(route), node
                moved += 1
            else:
                assert c.pos == goal, node
                near += 1
        if moved >= 3 and near >= 3:
            return
    pytest.fail("no state of the games has three moves that pass toward places beyond the walk and three short of it")


def test_a_recall_gives_full_health_and_mana_and_the_upgrades_that_the_estimated_gold_buys():
    world, info, record = hidden_jungler()
    level = level_of(world.champions[JUNGLE].xp)
    stay, recall = jungler_in(info, Plan(Activity.STAY)), jungler_in(info, Plan(Activity.RECALL))
    can = capability("jungle", level, recall.upgrades)
    assert ELAPSED_S > RECALL_S and (recall.hp, recall.mana) == (can.max_hp, can.max_mana)
    progression = PROGRESSIONS["jungle"]
    bought = sum(upgrade.cost for upgrade in progression[record.upgrades:recall.upgrades])
    assert recall.upgrades > record.upgrades == stay.upgrades
    assert sum(recall.earned) == pytest.approx(sum(stay.earned)) and recall.gold == pytest.approx(stay.gold - bought)
    assert recall.upgrades == len(progression) or recall.gold < progression[recall.upgrades].cost


def back_by(info, camp: int) -> int | None:
    """The tick by which the team's memory and the timer rule of M7 section 3.3 have the camp back after a death. A
    known spawn holds, and a camp seen empty without one died `unseen_death` before that sighting. None for a camp last
    seen alive or due at its first spawn."""
    mine, config = info.world().memory[info.team].camps[camp], info.snapshot.config
    if mine.spawn_tick >= 0:
        return None if mine.spawn_tick == config.ticks(SITES[camp].kind.first_spawn_s) else mine.spawn_tick
    return None if mine.hp > 0 else unseen_death(config, mine.seen_tick) + config.ticks(SITES[camp].kind.respawn_s)


def clears_without_a_wait(config: Config):
    """The states of `hidden_junglers` in which the generator's clear takes two camps or more, each of which `back_by`
    has back by the sighting, as (info, record, path)."""
    for info, record in hidden_junglers(config):
        path = next((h.plans[JUNGLE].path for h in activity_v0(info) if h.plans[JUNGLE].activity is Activity.CLEAR), ())
        ticks = [back_by(info, i) for i in path]
        if len(path) >= 2 and all(tick is not None and tick <= record.seen_tick for tick in ticks):
            yield info, record, path


@CLOCKS
def test_a_clear_leaves_its_camps_dead_with_the_respawn_timers_of_their_clear_times_and_pays_the_jungler(config):
    """The clear times follow from route length over speed and camp health over the camp damage rate. The state is
    the first of `clears_without_a_wait`. Every camp of the path was up again before the jungler's sighting, so no
    clear waits, and every camp respawned at the average public level. The jungler is paid the estimate of its camp
    gold up to the sighting and the gold of the camps."""
    found = next(clears_without_a_wait(config), None)
    assert found, "a hidden enemy jungler whose clear takes two camps that were back by its sighting"
    info, record, path = found
    level =math.floor(sum(level_of(c.xp) for c in info.world().champions) / 10 + 0.5)
    state = realize(info, alone(Plan(Activity.CLEAR, path)), 0)
    can, tick_s = capability("jungle", record.level, record.upgrades), config.tick_s
    t, at = record.seen_tick * tick_s, record.pos
    for i in path:
        t += RIFT.distance(at, SITES[i].pos) / can.move_speed + SITES[i].kind.health(level) / can.camp_dps
        killed, at = math.ceil(t / tick_s - 1e-9) - 1, SITES[i].pos
        camp = state.camps[i]
        assert camp.hp == 0.0 and camp.spawn_tick == killed + config.ticks(SITES[i].kind.respawn_s), SITES[i].node
    c = state.champions[(1 - info.team) * 5 + JUNGLE]
    assert c.pos == SITES[path[-1]].pos and c.outcome is Outcome.CLEARED and c.outcome_tick == killed
    estimate = H["farm_gold_per_s"]["jungle"] * max(0.0, record.seen_tick * tick_s - H["farm_from_s"]["jungle"])
    assert c.earned[Income.CAMP] == pytest.approx(estimate + sum(SITES[i].kind.reward(level)[0] for i in path))


@pytest.mark.parametrize("seed, enemy", GAMES[:2])
def test_the_enemys_memory_is_what_it_sees_at_the_decision_tick_and_the_public_facts_and_nothing_of_the_source(seed, enemy):
    forgotten = 0
    for team in (0, 1):
        for ticks in SNAPSHOTS:
            world = game(seed, enemy, team, ticks)
            info, foe = redact(world, team), 1 - team
            for h in activity_v0(info):
                state = realize(info, h, 0)
                rule = World.restore(state.snapshot())
                rule.memory[foe] = new_memory(rule.config, foe)
                remember_team(rule, foe, rule.tick - 1)
                assert _plain(state.memory[foe]) == _plain(rule.memory[foe])
                for record, source in zip(state.memory[foe].enemies, world.memory[foe].enemies):
                    if record.seen_tick != state.tick and source.seen_tick >= 0:
                        assert record.seen_tick == -1
                        forgotten += 1
    assert forgotten >= 10, forgotten


def test_the_generator_drops_the_activities_that_fail_and_says_why_and_its_weights_sum_to_one():
    _, info, _ = hidden_jungler()
    hypotheses, dropped = generate(info)
    assert sum(h.weight for h in hypotheses) == pytest.approx(1.0) and len(hypotheses) >= 3
    for d in dropped:
        assert verdict(info, alone(d.plan)) is d.reason or d.plan.activity is Activity.CLEAR
    for h in hypotheses:
        assert verdict(info, h) is None


@cache
def _standard(config: Config, seed: int, until_s: float) -> Snapshot:
    world = World(config, seed)
    build = styled(STANDARD, config.tick_s * config.decision_ticks)
    policies = team_policies(build, build)
    while world.tick < config.ticks(until_s):
        tick(world, policies)
    return world.snapshot()


def standard(config: Config, seed: int, until_s: float) -> World:
    """The game of the standard style on both sides, the base game of C8's scenarios, at `until_s`."""
    return World.restore(_standard(config, seed, until_s))


@cache
def killed_unseen(config: Config) -> tuple[tuple[int, Snapshot, int, int], ...]:
    """The decision states of the standard game of seed 3 up to 300 s in which the team does not see a living enemy
    laner that respawned after the team last saw it, at the level it has now, as (team, snapshot, role, tick of the
    respawn). The game's own record of who was dead finds them, not the state."""
    world = World(config, 3)
    build = styled(STANDARD, config.tick_s * config.decision_ticks)
    policies = team_policies(build, build)
    back, found = {}, []
    while world.tick < config.ticks(300.0):
        dead = [c for c in world.champions if c.hp <= 0]
        tick(world, policies)
        back |= {c.seat: (world.tick - 1, level_of(c.xp)) for c in dead if c.hp > 0}
        if world.tick % config.decision_ticks:
            continue
        for team in (0, 1):
            for role, record in enumerate(world.memory[team].enemies):
                c = world.champions[(1 - team) * 5 + role]
                respawned, level = back.get(c.seat, (-1, 0))
                if HOME[role] and c.hp > 0 and record.seen_tick != world.tick and respawned >= record.seen_tick and level_of(c.xp) == level:
                    found.append((team, world.snapshot(), role, respawned))
    return tuple(found)


@CLOCKS
def test_an_enemy_killed_after_the_team_last_saw_it_is_built_from_its_respawn_on_its_fountain(config, monkeypatch):
    """Kills and respawns are public (M7 section 6.3). The state is the one of `killed_unseen` longest after the
    respawn. Staying, the laner stands on its fountain with full health and mana, with every upgrade that its
    estimated gold buys there. Every generated world gives it full health, since nothing it does after its respawn
    fights, and puts it no further from its fountain than it walks in the time since. A respawn is a visit to the
    fountain, so the upgrades that the team saw and one more pass the checks without a recall, and one fewer does not.
    The respawn keeps the level of that moment, and it shops: had the team seen the laner a level lower and with no
    upgrades before it died, it would still stay on its fountain at full health, with what its gold buys there."""
    found = killed_unseen(config)
    assert found, "an enemy laner that respawned after the team last saw it"
    team, snapshot, role, respawned = max(found, key=lambda f: f[1].tick - f[3])
    world = World.restore(snapshot)
    info, seat = redact(world, team), (1 - team) * 5 + role
    record = info.world().memory[team].enemies[role]
    assert record.upgrades >= 1 and level_of(world.champions[seat].xp) >= 2
    monkeypatch.setitem(H, "mana_share", 0.5)
    stay = realize(info, alone(Plan(Activity.STAY), role=role), 0).champions[seat]
    can, progression = capability_of(stay), PROGRESSIONS[ROLES[role]]
    assert (stay.pos, stay.hp, stay.mana) == (FOUNTAIN[1 - team], can.max_hp, can.max_mana)
    assert stay.upgrades >= record.upgrades and (stay.upgrades == len(progression) or stay.gold < progression[stay.upgrades].cost)
    since = (world.tick - respawned) * config.tick_s
    for h in activity_v0(info):
        c = realize(info, h, 0).champions[seat]
        assert c.hp == capability_of(c).max_hp, h.name
        assert RIFT.distance(FOUNTAIN[1 - team], c.pos) <= capability_of(c).move_speed * since + 1e-6, h.name
    for upgrades in (record.upgrades, record.upgrades + 1):
        assert verdict(info, alone(Plan(Activity.STAY, upgrades=upgrades), role=role)) is None, upgrades
    assert verdict(info, alone(Plan(Activity.STAY, upgrades=record.upgrades - 1), role=role)) is Reason.INCONSISTENT
    world.memory[team].enemies[role].level -= 1
    world.memory[team].enemies[role].upgrades = 0
    lower = redact(world, team)
    c = realize(lower, alone(Plan(Activity.STAY), role=role), 0).champions[seat]
    assert (c.pos, c.hp) == (FOUNTAIN[1 - team], capability_of(c).max_hp)
    assert c.upgrades > 0 and (c.upgrades == len(progression) or c.gold < progression[c.upgrades].cost)


def consistent(info, world: World, state: World) -> None:
    """The built world passes the invariant checker and tells the team what the source tells it, and the team's
    memory rule run again on it sees what the information state says the team sees."""
    check_invariants(state)
    assert knowledge(state, info.team) == knowledge(world, info.team)
    assert seen_again(state, info.team) == remembered(info.world().memory[info.team])


def test_an_enemy_gone_from_where_the_team_watched_it_stand_recalled_from_before_the_sighting():
    """At 506 s of the standard game of seed 2, blue last saw red's mid laner 4 s before, at the place where it stood
    on the tick before, and blue sees that place now. The laner cannot reach its lane's front in 4 s, and staying, a
    recall begun at the sighting, and every move end where blue sees. A recall that blue watched, begun before the
    sighting and ended on the tick after it, explains the state: the laner is back from its fountain, out of blue's
    view, and the built world is consistent. The same recall is rejected once blue saw the laner move on that tick."""
    world = standard(PINNED, 2, 506.0)
    info, seat = redact(world, 0), 5 + MID
    record = info.world().memory[0].enemies[MID]
    assert not info.seen[MID] and record.was == record.pos and sees(info.world(), 0, record.pos)
    assert (info.snapshot.tick - record.seen_tick) * PINNED.tick_s == 4.0
    for h in activity_v0(info):
        state = realize(info, h, 0)
        consistent(info, world, state)
        c = state.champions[seat]
        assert (c.outcome, c.outcome_tick) == (Outcome.RECALLED, record.seen_tick) and not sees(info.world(), 0, c.pos), h.name
    watched = alone(Plan(Activity.RECALL, watched=True), role=MID)
    assert verdict(info, watched) is None
    moved = World.restore(world.snapshot())
    moved.memory[0].enemies[MID].was = RIFT.advance(record.pos, FOUNTAIN[1], 100.0)
    assert verdict(redact(moved, 0), watched) is Reason.INCONSISTENT


def test_a_jungler_whose_default_path_ends_where_the_team_sees_clears_the_longest_start_of_it_that_passes():
    """At 340 s of the standard game of seed 4, red has not seen blue's jungler since it respawned, and it is a level
    higher now. Staying, recalling, and moving earn no XP, and the default path from its fountain ends at a camp that
    red sees. The longest start of that path that passes explains the level: the jungler holds at the last camp of it,
    out of red's view, and the built world is consistent."""
    world = standard(PINNED, 4, 340.0)
    info = redact(world, 1)
    hypotheses, dropped = generate(info)
    full = next(d.plan.path for d in dropped if d.role == JUNGLE and d.plan.activity is Activity.CLEAR and d.reason is Reason.IN_VIEW)
    for h in hypotheses:
        path = h.plans[JUNGLE].path
        assert h.plans[JUNGLE].activity is Activity.CLEAR and 0 < len(path) < len(full) and path == full[:len(path)], h.name
        assert verdict(info, alone(Plan(Activity.CLEAR, full[:len(path) + 1]))) is not None
        state = realize(info, h, 0)
        consistent(info, world, state)
        c = state.champions[JUNGLE]
        assert (c.pos, c.outcome) == (SITES[path[-1]].pos, Outcome.CLEARED) and not sees(info.world(), 1, c.pos)


def test_a_camp_that_the_team_saw_empty_respawns_at_the_same_game_second_on_every_tick_of_one_refined_state():
    """The state is blue's at 600 s of a game on the 0.5 s clock. Blue's memory is then written: it saw its Gromp
    empty 10 s ago, and its Krugs and both river nodes empty now, all without a known spawn, and they are dead. The
    state refined to 0.25 s and to 0.125 s builds worlds whose camps respawn at the same game seconds as on its own
    clock, and the river holds one Scuttler due."""
    world = pinned(5, "scripted", 0, 1200)
    t, memory = world.tick, world.memory[0].camps
    gromp, krugs = (next(i for i, site in enumerate(SITES) if site.node == name) for name in ("blue_gromp", "blue_krugs"))
    for i, seen in ((gromp, t - PINNED.ticks(10.0)), (krugs, t), (SCUTTLERS[0], t), (SCUTTLERS[1], t)):
        world.camps[i].hp, world.camps[i].spawn_tick, world.camps[i].engaged = 0.0, t + 600, -1
        memory[i] = CampMemory(0.0, 0, seen, -1)
    respawns = {}
    for tick_s in (0.5, 0.25, 0.125):
        info = redact(refine(world, tick_s), 0)
        state = realize(info, activity_v0(info)[0], 0)
        respawns[tick_s] = [(state.camps[i].hp, state.camps[i].spawn_tick * tick_s if state.camps[i].spawn_tick >= 0 else None)
                            for i in (gromp, krugs, *SCUTTLERS)]
    assert respawns[0.25] == respawns[0.5] == respawns[0.125]
    assert [hp for hp, _ in respawns[0.5]] == [0.0] * 4 and sum(at is not None and at > 600.0 for _, at in respawns[0.5]) == 3


def test_on_a_clock_of_one_second_a_camp_seen_empty_died_two_ticks_before_the_sighting():
    """On a clock of 1 s, `unseen_death_s` is one tick, and the look of that tick would have shown the death. The camp
    died two ticks before the sighting, the latest that the timer rule allows."""
    config = Config(tick_s=1.0, decision_ticks=2)
    world = World(config, 5)
    while world.tick < 300:
        world.step()
    t, gromp = world.tick, next(i for i, site in enumerate(SITES) if site.node == "blue_gromp")
    world.camps[gromp].hp, world.camps[gromp].spawn_tick, world.camps[gromp].engaged = 0.0, t + 200, -1
    world.memory[0].camps[gromp] = CampMemory(0.0, 0, t - 10, -1)
    info = redact(world, 0)
    state = realize(info, activity_v0(info)[0], 0)
    assert state.camps[gromp].spawn_tick == t - 10 - 2 + config.ticks(SITES[gromp].kind.respawn_s)
