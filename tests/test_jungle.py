import itertools
import os
import pickle
import subprocess
import sys
from collections import Counter
from dataclasses import fields, replace
from pathlib import Path

import pytest

from riftgame.champions import (ACTIONS, CAMP_NODES, CAMP_SITES, FOUNTAIN, HOLD, KEEP, LANES, MAP, RECALL, RIFT, ROLES, SEATS,
                                TEAMS, Income, Kind, Outcome, R, capability, capability_of, frame_name, level_of, spent)
from riftgame.harness import jungler, run, scripted, tick
from riftgame.jungle import SCUTTLERS, SITES, Camp, CampDeath, CampSpawn
from riftgame.ruleset import load
from riftgame.vision import EDGE_GAP, CampMemory, Sight, observe, sees
from riftgame.world import Config, InvariantError, World, check_invariants
from worlds import (BLUE_JUNGLE, BLUE_MID, BLUE_SUPPORT, BLUE_TOP, EVERY_TICK, RED_JUNGLE, RED_MID, RED_TOP, StubLane, act, busy,
                    ended_now, lane_place, move, play, staged, submit, until)

REPO = Path(__file__).parents[1]
TICK_S = EVERY_TICK.tick_s
ASSUMED = load("patch_26_22_m8")["camps"]
LEASH = ASSUMED["leash_range"]
# Reference rows B8 to B10, C13 to C15, and D16: first spawn, respawn delay, gold, XP and health at level 1, and
# the window before a respawn in which the sight of the empty camp gives the timer.
REFERENCE = {
    "blue_sentinel": (55.0, 300.0, 90.0, 95.0, 2300.0, 60.0),
    "red_brambleback": (55.0, 300.0, 90.0, 95.0, 2300.0, 60.0),
    "gromp": (67.0, 135.0, 80.0, 120.0, 2050.0, 10.0),
    "murk_wolves": (55.0, 135.0, 85.0, 80.0, 2860.0, 10.0),
    "raptors": (55.0, 135.0, 75.0, 70.0, 3700.0, 10.0),
    "krugs": (67.0, 135.0, 109.0, 121.0, 2360.0, 10.0),
    "scuttler": (175.0, 150.0, 55.0, 100.0, 1550.0, 10.0),
}
KIND = {node: MAP.camps.get(node, "scuttler") for node in CAMP_SITES}
FIRST_S, RESPAWN_S, GOLD, XP, HEALTH, WINDOW_S = ({node: REFERENCE[kind][column] for node, kind in KIND.items()} for column in range(6))
FIRST_SCUTTLER_HEALTH = 0.65 * 1550.0
ITEM_XP, FIRST_CAMP_XP = 80.0, 150.0
SHRINE_S, SHRINE_RADIUS = 90.0, 525.0
ONE_PER_KIND = ["blue_blue", "blue_red", "blue_gromp", "blue_wolves", "blue_raptors", "blue_krugs"]
TEAM_OF = {0: range(5), 1: range(5, 10)}


def at(node: str):
    return RIFT.at(node)


def site(node: str) -> int:
    return CAMP_SITES.index(node)


def camp_action(seat: int, node: str) -> int:
    """The `CAMP` action that names a map node in the seat's team frame."""
    return act(Kind.CAMP, frame_name(seat // 5, node))


def view(world: World, seat: int, node: str):
    """What a seat's observation holds for the camp at a map node."""
    return observe(world, seat).camps[CAMP_NODES.index(frame_name(seat // 5, node))]


def now(world: World) -> float:
    return world.tick * world.config.tick_s


def quiet(places: dict | None = None, until_s: float = 0.0, config: Config = EVERY_TICK, seed: int = 0) -> World:
    """A world without minions, with the given seats on their marks, run to a game time with everyone holding."""
    world = staged(places or {}, config, seed)
    world.lanes = {name: StubLane() for name in LANES}
    while now(world) < until_s:
        world.step()
    return world


def events(world: World, kind: type) -> list:
    return [e for name, e in world.events if name == "jungle" and type(e) is kind]


def clear(world: World, orders: dict[int, str], limit: int = 400) -> CampDeath:
    """Send each seat to fight the camp at its map node, and run until a camp dies. Returns that death."""
    submit(world, {seat: camp_action(seat, node) for seat, node in orders.items()})
    for _ in range(limit):
        died = events(world, CampDeath)
        if died:
            assert len(died) == 1
            return died[0]
        world.step()
    raise AssertionError(f"no camp died within {limit} ticks")


def spawns(world: World, camp: int) -> list[CampSpawn]:
    return [spawn for spawn in events(world, CampSpawn) if spawn.camp == camp]


def next_spawn(world: World, camp: int, limit: int = 700) -> CampSpawn:
    """Run until the camp spawns, and return the spawn."""
    for _ in range(limit):
        world.step()
        if spawns(world, camp):
            return spawns(world, camp)[0]
    raise AssertionError(f"the camp did not spawn within {limit} ticks")


def river_alive(world: World) -> list[int]:
    return [i for i in SCUTTLERS if world.camps[i].hp > 0]


@pytest.mark.parametrize("policy", [None, scripted], ids=["nobody acts", "scripted junglers and laners"])
def test_every_camp_first_appears_at_its_ruleset_clock_time_whatever_the_champions_do(policy):
    world = World(Config(), seed=3)
    spawned, alive_from, cleared = {}, {}, 0
    while now(world) <= 176.0:
        world.step() if policy is None else tick(world, policy)
        for spawn in events(world, CampSpawn):
            spawned.setdefault(CAMP_SITES[spawn.camp], spawn.t)
        cleared += len(events(world, CampDeath))
        for i, camp in enumerate(world.camps):
            if camp.hp > 0:
                alive_from.setdefault(CAMP_SITES[i], now(world) - world.config.tick_s)
    assert spawned == FIRST_S == alive_from
    assert (spawned["blue_blue"], spawned["red_krugs"], spawned["top_river"], spawned["bot_river"]) == (55.0, 67.0, 175.0, 175.0)
    assert (cleared > 8) == (policy is scripted), "the scripted game must have junglers that clear before the Scuttlers spawn"


@pytest.mark.parametrize("mid_clear", [False, True], ids=["nobody acts", "a jungler is in the middle of a camp"])
def test_both_first_scuttlers_spawn_at_2_55_one_on_each_river_node_with_65_percent_health(mid_clear):
    world = quiet({BLUE_JUNGLE: at("blue_raptors")}, until_s=165.0)
    raptors = world.camps[site("blue_raptors")]
    if mid_clear:
        submit(world, {BLUE_JUNGLE: camp_action(BLUE_JUNGLE, "blue_raptors")})
    while now(world) < 175.0:
        assert not river_alive(world) and not events(world, CampSpawn)
        world.step()
    world.step()
    assert sorted((CAMP_SITES[spawn.camp], spawn.t, spawn.level) for spawn in events(world, CampSpawn)) == [("bot_river", 175.0, 1), ("top_river", 175.0, 1)]
    assert [(world.camps[i].hp, world.camps[i].max_hp) for i in SCUTTLERS] == [(pytest.approx(FIRST_SCUTTLER_HEALTH),) * 2] * 2
    if mid_clear:
        assert 0 < raptors.hp < raptors.max_hp and raptors.engaged == BLUE_JUNGLE
        assert world.champions[BLUE_JUNGLE].outcome is Outcome.NONE, "no clear has finished"
    else:
        assert all(c.intent == HOLD and c.outcome is Outcome.NONE for c in world.champions)


def test_a_camp_spawns_at_the_average_champion_level_rounded_half_up_and_its_health_and_rewards_lie_on_the_line_between_the_reference_ends():
    world = quiet({BLUE_JUNGLE: at("blue_gromp")})
    for c in world.champions[5:]:
        c.xp = 280.0 + 380.0 + 480.0 + 580.0 + 680.0
    assert sorted(level_of(c.xp) for c in world.champions) == [1] * 5 + [6] * 5
    while now(world) <= 67.0:
        world.step()
    assert [spawn.level for spawn in events(world, CampSpawn)] == [4] * 4, "the average of 3.5 rounds up"
    gromp = world.camps[site("blue_gromp")]
    assert gromp.hp == gromp.max_hp == pytest.approx(2050.0 + (4817.5 - 2050.0) * 3 / 17)
    death = clear(world, {BLUE_JUNGLE: "blue_gromp"})
    assert (death.gold, death.xp) == (80.0, pytest.approx(120.0 + (180.0 - 120.0) * 3 / 17))
    world.champions[BLUE_JUNGLE].pos = at("top_river")
    while now(world) <= 175.0:
        world.step()
    assert world.camps[site("top_river")].max_hp == pytest.approx(0.65 * (1550.0 + (5270.0 - 1550.0) * 3 / 17))
    death = clear(world, {BLUE_JUNGLE: "top_river"})
    assert (death.gold, death.xp) == (pytest.approx(55.0 + (121.0 - 55.0) * 3 / 17), pytest.approx(100.0 + (150.0 - 100.0) * 3 / 17))


@pytest.mark.parametrize("node", [node for node in CAMP_SITES if KIND[node] != "scuttler"])
def test_a_camp_respawns_its_ruleset_delay_after_its_death_to_the_tick_and_is_empty_until_then(node):
    world = quiet({BLUE_JUNGLE: at(node)}, until_s=90.0)
    camp = world.camps[site(node)]
    death = clear(world, {BLUE_JUNGLE: node})
    assert death.t > 90.0 and death.respawn == site(node)
    for _ in range(round(RESPAWN_S[node] / TICK_S) - 1):
        world.step()
        assert camp.hp == 0.0 and not spawns(world, site(node))
    world.step()
    assert [spawn.t for spawn in spawns(world, site(node))] == [death.t + RESPAWN_S[node]]
    assert camp.hp == camp.max_hp == HEALTH[node]
    for _ in range(10):
        world.step()
    assert camp.hp == camp.max_hp and world.champions[BLUE_JUNGLE].intent == HOLD, "a finished order does not start again"


@pytest.mark.parametrize("tick_s, respawn_s", [(0.25, 135.0), (1.0, 135.0), (0.4, 135.2)])
def test_a_respawn_delay_is_rounded_up_to_whole_ticks(tick_s, respawn_s):
    world = quiet({BLUE_JUNGLE: at("blue_gromp")}, until_s=70.0, config=Config(tick_s=tick_s, decision_ticks=1))
    death = clear(world, {BLUE_JUNGLE: "blue_gromp"})
    assert next_spawn(world, site("blue_gromp")).t == pytest.approx(death.t + respawn_s)


def test_no_scuttler_respawns_until_both_first_scuttlers_are_dead_and_then_the_river_holds_one_at_a_time_150_s_after_the_last_death():
    top, bot = site("top_river"), site("bot_river")
    world = quiet({BLUE_JUNGLE: at("top_river"), RED_JUNGLE: at("bot_river")}, until_s=176.0)
    first = clear(world, {BLUE_JUNGLE: "top_river"})
    assert (first.camp, first.respawn) == (top, -1)
    for _ in range(round(200.0 / TICK_S)):
        world.step()
        assert river_alive(world) == [bot] and not events(world, CampSpawn)
    last = clear(world, {RED_JUNGLE: "bot_river"})
    for round_ in range(3):
        assert last.respawn in (top, bot) and last.t > first.t + 200.0
        for _ in range(round(150.0 / TICK_S) - 1):
            world.step()
            assert not river_alive(world) and not events(world, CampSpawn)
        world.step()
        assert [(spawn.camp, spawn.t) for spawn in events(world, CampSpawn)] == [(last.respawn, last.t + 150.0)]
        assert river_alive(world) == [last.respawn]
        assert world.camps[last.respawn].hp == 1550.0, "only the first two Scuttlers have less health"
        world.champions[BLUE_JUNGLE].pos = SITES[last.respawn].pos
        for _ in range(round(20.0 / TICK_S)):
            world.step()
            assert river_alive(world) == [last.respawn]
        last = clear(world, {BLUE_JUNGLE: CAMP_SITES[last.respawn]})


def test_the_first_two_scuttlers_dying_on_one_tick_start_one_timer():
    world = quiet({BLUE_JUNGLE: at("top_river"), RED_JUNGLE: at("bot_river")}, until_s=176.0)
    submit(world, {BLUE_JUNGLE: camp_action(BLUE_JUNGLE, "top_river"), RED_JUNGLE: camp_action(RED_JUNGLE, "bot_river")})
    until(lambda: events(world, CampDeath), world.step)
    both = events(world, CampDeath)
    assert len(both) == 2 and both[0].respawn == both[1].respawn in SCUTTLERS
    assert next_spawn(world, both[0].respawn).t == both[0].t + 150.0 and len(river_alive(world)) == 1


def test_the_river_node_of_the_next_scuttler_is_a_draw_keyed_on_the_seed():
    def node_drawn(seed: int) -> int:
        world = quiet({BLUE_JUNGLE: at("top_river"), RED_JUNGLE: at("bot_river")}, until_s=176.0, seed=seed)
        clear(world, {BLUE_JUNGLE: "top_river"})
        return clear(world, {RED_JUNGLE: "bot_river"}).respawn

    drawn = [node_drawn(seed) for seed in range(12)]
    assert set(drawn) == set(SCUTTLERS), "both river nodes come up"
    assert drawn == [node_drawn(seed) for seed in range(12)], "the same seed draws the same node"


@pytest.mark.parametrize("seat", range(5), ids=ROLES)
def test_a_clear_takes_the_camps_health_over_the_champions_camp_damage_rate_within_one_tick(seat):
    world = quiet({seat: at("blue_blue")}, until_s=60.0)
    began = now(world)
    death = clear(world, {seat: "blue_blue"})
    took = death.t + TICK_S - began
    assert abs(took - 2300.0 / capability(ROLES[seat], 1, 0).camp_dps) <= TICK_S
    assert capability(ROLES[seat], 3, 0).camp_dps > capability(ROLES[seat], 1, 0).camp_dps, "the rate grows with level"
    assert all(capability("jungle", 1, 0).camp_dps > capability(role, 1, 0).camp_dps for role in ROLES if role != "jungle")


@pytest.mark.parametrize("seats", [(BLUE_TOP, BLUE_JUNGLE), (BLUE_TOP, BLUE_JUNGLE, RED_MID)])
def test_champions_on_one_camp_add_their_damage_rates(seats):
    world = quiet({seat: at("blue_raptors") for seat in seats}, until_s=60.0)
    began = now(world)
    death = clear(world, {seat: "blue_raptors" for seat in seats})
    rate = sum(capability(ROLES[seat % 5], 1, 0).camp_dps for seat in seats)
    assert abs(death.t + TICK_S - began - 3700.0 / rate) <= TICK_S
    assert all(world.champions[seat].outcome is Outcome.CLEARED for seat in seats)


def test_travel_between_camps_takes_route_length_over_speed_and_the_first_blow_lands_on_the_tick_of_arrival():
    world = quiet({BLUE_JUNGLE: at("blue_blue")}, until_s=70.0)
    me, gromp = world.champions[BLUE_JUNGLE], world.camps[site("blue_gromp")]
    walk, can = RIFT.distance(me.pos, at("blue_gromp")), capability_of(me)
    assert walk > 2000.0
    began = now(world)
    submit(world, {BLUE_JUNGLE: camp_action(BLUE_JUNGLE, "blue_gromp")})
    while me.pos != at("blue_gromp"):
        assert gromp.hp == gromp.max_hp, "no blow lands before the champion stands at the camp"
        world.step()
    assert abs(now(world) - began - walk / can.move_speed) <= TICK_S
    assert gromp.hp == gromp.max_hp - can.camp_dps * TICK_S
    death = clear(world, {BLUE_JUNGLE: "blue_gromp"})
    assert abs(death.t + TICK_S - began - walk / can.move_speed - 2050.0 / can.camp_dps) <= 2 * TICK_S


def test_a_camp_hits_the_champion_that_engaged_it_first_at_its_damage_rate_and_nobody_else():
    rate = ASSUMED["damage_per_s"]["red_brambleback"]
    world = quiet({BLUE_TOP: at("blue_red"), BLUE_JUNGLE: at("blue_red")}, until_s=60.0)
    top, jungle = world.champions[BLUE_TOP], world.champions[BLUE_JUNGLE]
    full, regen = capability_of(top).max_hp, capability_of(top).hp_regen
    assert rate > regen > 0
    submit(world, {BLUE_TOP: camp_action(BLUE_TOP, "blue_red")})
    assert top.hp == full, "the camp answers from the tick after the first blow"
    submit(world, {BLUE_JUNGLE: camp_action(BLUE_JUNGLE, "blue_red")})
    for hits in range(1, 12):
        assert top.hp == pytest.approx(full - hits * (rate - regen) * TICK_S)
        assert jungle.hp == capability_of(jungle).max_hp
        assert world.camps[site("blue_red")].engaged == BLUE_TOP
        world.step()


def test_a_camps_hit_is_damage_like_any_other_so_it_ends_a_recall():
    world = quiet({BLUE_JUNGLE: at("blue_red")}, until_s=60.0)
    me = world.champions[BLUE_JUNGLE]
    submit(world, {BLUE_JUNGLE: camp_action(BLUE_JUNGLE, "blue_red")})
    submit(world, {BLUE_JUNGLE: RECALL})
    assert (me.outcome, me.intent) == (Outcome.INTERRUPTED, HOLD) and me.hp < capability_of(me).max_hp


def test_a_scuttler_deals_no_damage():
    world = quiet({BLUE_SUPPORT: at("top_river")}, until_s=176.0)
    me = world.champions[BLUE_SUPPORT]
    submit(world, {BLUE_SUPPORT: camp_action(BLUE_SUPPORT, "top_river")})
    for _ in range(20):
        world.step()
        assert me.hp == capability_of(me).max_hp and world.camps[site("top_river")].engaged == BLUE_SUPPORT
    assert world.camps[site("top_river")].hp < FIRST_SCUTTLER_HEALTH


def test_a_camp_keeps_hitting_a_champion_that_walks_away_inside_its_leash_and_returns_to_full_health_once_the_champion_is_out():
    rate = ASSUMED["damage_per_s"]["raptors"]
    world = quiet({BLUE_JUNGLE: at("blue_raptors")}, until_s=60.0)
    me, raptors = world.champions[BLUE_JUNGLE], world.camps[site("blue_raptors")]
    regen = capability_of(me).hp_regen
    submit(world, {BLUE_JUNGLE: camp_action(BLUE_JUNGLE, "blue_raptors")})
    for _ in range(9):
        world.step()
    hurt = raptors.hp
    assert hurt == 3700.0 - 10 * capability_of(me).camp_dps * TICK_S
    hit_while_leaving = 0
    for step in range(12):
        before = me.hp
        submit(world, {BLUE_JUNGLE: move("own_red")})
        if RIFT.separation(me.pos, at("blue_raptors")) <= LEASH:
            hit_while_leaving += 1
            assert me.hp == pytest.approx(before - (rate - regen) * TICK_S), f"step {step}"
            assert (raptors.hp, raptors.engaged) == (hurt, BLUE_JUNGLE)
            assert me.outcome is Outcome.NONE, "leaving is a new action and records no outcome"
        else:
            assert me.hp == pytest.approx(before + regen * TICK_S), f"step {step}"
            assert (raptors.hp, raptors.engaged) == (3700.0, -1)
    assert 3 <= hit_while_leaving <= 9 and RIFT.separation(me.pos, at("blue_raptors")) > LEASH


def test_a_camp_stays_hurt_and_keeps_hitting_a_champion_that_stops_fighting_inside_its_leash():
    world = quiet({BLUE_JUNGLE: at("blue_raptors")}, until_s=60.0)
    me, raptors = world.champions[BLUE_JUNGLE], world.camps[site("blue_raptors")]
    submit(world, {BLUE_JUNGLE: camp_action(BLUE_JUNGLE, "blue_raptors")})
    submit(world, {BLUE_JUNGLE: HOLD})
    hurt, before = raptors.hp, me.hp
    for _ in range(30):
        world.step()
    assert (raptors.hp, raptors.engaged) == (hurt, BLUE_JUNGLE) and hurt < 3700.0
    assert me.hp == pytest.approx(before - 30 * (ASSUMED["damage_per_s"]["raptors"] - capability_of(me).hp_regen) * TICK_S)


def test_a_camp_returns_to_full_health_when_the_champion_it_fights_dies():
    world = quiet({BLUE_TOP: at("blue_raptors")}, until_s=60.0)
    raptors = world.camps[site("blue_raptors")]
    submit(world, {BLUE_TOP: camp_action(BLUE_TOP, "blue_raptors")})
    world.step()
    assert raptors.engaged == BLUE_TOP and raptors.hp == 3700.0 - 2 * capability("top", 1, 0).camp_dps * TICK_S
    world.damage_champion(BLUE_TOP, 10_000.0)
    world.step()
    assert world.champions[BLUE_TOP].outcome is Outcome.DIED and (raptors.hp, raptors.engaged) == (3700.0, -1)


@pytest.mark.parametrize("leaves_by", ["dying", "walking out of the leash"])
def test_a_camp_whose_champion_is_gone_turns_on_a_champion_that_is_still_fighting_it_and_keeps_its_wounds(leaves_by):
    world = quiet({BLUE_TOP: at("blue_raptors"), BLUE_JUNGLE: at("blue_raptors")}, until_s=60.0)
    raptors, top, jungle = world.camps[site("blue_raptors")], world.champions[BLUE_TOP], world.champions[BLUE_JUNGLE]
    submit(world, {BLUE_TOP: camp_action(BLUE_TOP, "blue_raptors")})
    submit(world, {BLUE_JUNGLE: camp_action(BLUE_JUNGLE, "blue_raptors")})
    assert raptors.engaged == BLUE_TOP and jungle.hp == capability_of(jungle).max_hp
    if leaves_by == "dying":
        world.damage_champion(BLUE_TOP, 10_000.0)
    else:
        submit(world, {BLUE_TOP: move("own_fountain")})
    health = raptors.hp
    while raptors.engaged == BLUE_TOP:
        world.step()
        health -= capability_of(jungle).camp_dps * TICK_S
        assert raptors.hp == health, "the camp never returns to full health while the jungler fights on"
    assert raptors.engaged == BLUE_JUNGLE and (top.hp <= 0 or RIFT.separation(top.pos, at("blue_raptors")) > LEASH)
    before = jungle.hp
    world.step()
    assert jungle.hp < before, "the camp now hits the jungler"
    death = clear(world, {})
    assert death.killer == BLUE_JUNGLE and jungle.outcome is Outcome.CLEARED


@pytest.mark.parametrize("node", [*ONE_PER_KIND, "top_river"])
def test_a_jungler_gets_the_camps_gold_in_its_own_ledger_entry_and_the_camps_xp_plus_the_items_bonus(node):
    world = quiet({BLUE_JUNGLE: at(node)}, until_s=176.0)
    me = world.champions[BLUE_JUNGLE]
    death = clear(world, {BLUE_JUNGLE: node})
    assert (death.killer, death.gold, death.xp) == (BLUE_JUNGLE, GOLD[node], XP[node])
    assert me.earned[Income.CAMP] == GOLD[node] and me.gold == pytest.approx(sum(me.earned) - spent(me))
    assert me.xp == XP[node] + ITEM_XP + FIRST_CAMP_XP and level_of(me.xp) == 2, "the first camp gives level 2"
    assert me.outcome is Outcome.CLEARED and me.outcome_tick == world.tick - 1
    second = "blue_gromp" if node != "blue_gromp" else "blue_blue"
    me.pos = at(second)
    death = clear(world, {BLUE_JUNGLE: second})
    assert me.xp == XP[node] + ITEM_XP + FIRST_CAMP_XP + XP[second] + ITEM_XP, "the larger bonus is paid once"
    assert me.earned[Income.CAMP] == GOLD[node] + GOLD[second]
    assert all(c.earned[Income.CAMP] == 0 and c.xp == 0 for c in world.champions if c.seat != BLUE_JUNGLE)


def test_a_laner_gets_the_camps_gold_and_xp_without_the_jungle_items_bonus():
    world = quiet({BLUE_TOP: at("blue_blue")}, until_s=60.0)
    me = world.champions[BLUE_TOP]
    clear(world, {BLUE_TOP: "blue_blue"})
    assert (me.earned[Income.CAMP], me.xp, me.outcome) == (90.0, 95.0, Outcome.CLEARED)


def test_of_two_champions_that_hit_a_camp_on_its_last_tick_the_one_that_dealt_more_gets_all_of_it_and_both_orders_end_cleared():
    world = quiet({BLUE_TOP: at("blue_blue"), BLUE_JUNGLE: at("blue_blue"), BLUE_MID: at("blue_blue")}, until_s=60.0)
    submit(world, {BLUE_MID: camp_action(BLUE_MID, "blue_blue")})
    submit(world, {BLUE_MID: move("own_fountain")})
    death = clear(world, {BLUE_TOP: "blue_blue", BLUE_JUNGLE: "blue_blue"})
    top, jungle, mid = (world.champions[seat] for seat in (BLUE_TOP, BLUE_JUNGLE, BLUE_MID))
    assert death.killer == BLUE_JUNGLE
    assert (jungle.earned[Income.CAMP], jungle.xp) == (90.0, 95.0 + ITEM_XP + FIRST_CAMP_XP)
    assert (top.earned[Income.CAMP], top.xp) == (0.0, 0.0) == (mid.earned[Income.CAMP], mid.xp)
    assert top.outcome is jungle.outcome is Outcome.CLEARED and top.outcome_tick == jungle.outcome_tick == world.tick - 1
    assert mid.outcome is Outcome.NONE, "a champion that left before the camp died did not clear it"


def test_two_champions_that_dealt_the_same_on_the_last_tick_draw_for_the_reward_on_the_seed():
    def winner(seed: int) -> int:
        world = quiet({BLUE_TOP: at("blue_blue"), RED_TOP: at("blue_blue")}, until_s=60.0, seed=seed)
        death = clear(world, {BLUE_TOP: "blue_blue", RED_TOP: "blue_blue"})
        paid = {c.seat: (c.earned[Income.CAMP], c.xp) for c in world.champions if c.earned[Income.CAMP] or c.xp}
        assert paid == {death.killer: (90.0, 95.0)}, "the camp pays once"
        return death.killer

    winners = [winner(seed) for seed in range(12)]
    assert set(winners) == {BLUE_TOP, RED_TOP}
    assert winners == [winner(seed) for seed in range(12)]


def test_a_champion_that_kills_a_camp_on_the_tick_it_dies_is_paid_for_the_camp_and_its_order_ends_with_its_death():
    def fight() -> World:
        world = quiet({BLUE_JUNGLE: at("blue_red")}, until_s=60.0)
        submit(world, {BLUE_JUNGLE: camp_action(BLUE_JUNGLE, "blue_red")})
        return world

    rehearsal = fight()
    last = until(lambda: events(rehearsal, CampDeath), rehearsal.step)
    world = fight()
    me = world.champions[BLUE_JUNGLE]
    for _ in range(last - 1):
        world.step()
    assert world.camps[site("blue_red")].hp > 0
    me.hp = 1.0
    world.step()
    assert [death.killer for death in events(world, CampDeath)] == [BLUE_JUNGLE]
    assert (me.hp, me.outcome, me.outcome_tick, me.pos) == (0.0, Outcome.DIED, world.tick - 1, FOUNTAIN[0])
    assert (me.earned[Income.CAMP], me.xp) == (90.0, 95.0 + ITEM_XP + FIRST_CAMP_XP)


def test_a_camp_order_ends_absent_when_the_champion_arrives_at_a_dead_camp_or_is_given_at_one():
    world = quiet({BLUE_JUNGLE: at("blue_blue"), BLUE_TOP: at("blue_wolves")}, until_s=60.0)
    clear(world, {BLUE_JUNGLE: "blue_blue"})
    top, jungle = world.champions[BLUE_TOP], world.champions[BLUE_JUNGLE]
    submit(world, {BLUE_TOP: camp_action(BLUE_TOP, "blue_blue"), BLUE_JUNGLE: camp_action(BLUE_JUNGLE, "blue_blue")})
    assert (jungle.outcome, jungle.outcome_tick, jungle.intent) == (Outcome.ABSENT, world.tick - 1, HOLD)
    until(lambda: top.pos == at("blue_blue"), world.step)
    assert (top.outcome, top.outcome_tick, top.intent) == (Outcome.ABSENT, world.tick - 1, HOLD)


def fight_for_gromp(top: int, jungle: int, stagger: bool) -> list:
    """A top laner and a jungler of opposite teams fight the blue Gromp. Returns what happens, by role, tick by tick."""
    world = quiet({top: at("blue_gromp"), jungle: at("blue_gromp")}, until_s=70.0)
    gromp = world.camps[site("blue_gromp")]
    orders = {top: camp_action(top, "blue_gromp"), jungle: camp_action(jungle, "blue_gromp")}
    trace = []
    for step in range(40):
        submit(world, {top: orders[top]} if stagger and step == 0 else orders if step < 2 else {})
        trace.append((gromp.hp, ROLES[gromp.engaged % 5] if gromp.engaged >= 0 else None, [ROLES[e.killer % 5] for e in events(world, CampDeath)],
                      [(c.hp, c.xp, c.gold, c.earned[Income.CAMP], c.outcome) for c in (world.champions[top], world.champions[jungle])]))
    return trace


@pytest.mark.parametrize("stagger", [False, True], ids=["both arrive on one tick", "the top laner arrives first"])
def test_exchanging_the_seats_that_fight_a_camp_changes_nothing(stagger):
    one, other = fight_for_gromp(BLUE_TOP, RED_JUNGLE, stagger), fight_for_gromp(RED_TOP, BLUE_JUNGLE, stagger)
    assert one == other
    assert one[0][1] == ("top" if stagger else "jungle"), "the camp turns on the first to hit it, and on the hardest hitter of one tick"
    assert [killers for _, _, killers, _ in one if killers] == [["jungle"]]
    assert one[-1][3][0][0] < capability("top", 1, 0).max_hp or one[-1][3][1][0] < capability("jungle", 1, 0).max_hp


def shrine_marks(node: str):
    """Two river positions, 500 and 550 units in a straight line from a river node: one on each side of the shrine's radius."""
    detour = RIFT.distance(at(node), at("mid_river")) / RIFT.separation(at(node), at("mid_river"))
    inside, outside = (RIFT.advance(at(node), at("mid_river"), straight * detour) for straight in (500.0, 550.0))
    assert RIFT.separation(at(node), inside) == pytest.approx(500.0) and RIFT.separation(at(node), outside) == pytest.approx(550.0)
    return inside, outside


@pytest.mark.parametrize("killer, node", [(BLUE_JUNGLE, "top_river"), (RED_JUNGLE, "top_river"), (RED_JUNGLE, "bot_river")])
def test_a_dead_scuttler_leaves_its_killers_team_alone_90_s_of_sight_within_525_units_to_the_tick(killer, node):
    team = killer // 5
    world = quiet({killer: at(node)}, until_s=176.0)
    inside, outside = shrine_marks(node)
    clear(world, {killer: node})
    world.champions[killer].pos = FOUNTAIN[team]
    for _ in range(round(SHRINE_S / TICK_S)):
        assert sees(world, team, inside) and sees(world, team, at(node)) and not sees(world, team, outside)
        assert not sees(world, 1 - team, inside) and not sees(world, 1 - team, at(node))
        assert [(s.team, s.pos, s.radius) for s in world.sights] == [(team, at(node), SHRINE_RADIUS)]
        assert all(view(world, seat, node).seen_age_s == 0.0 for seat in TEAM_OF[team])
        assert all(view(world, seat, node).seen_age_s is None for seat in TEAM_OF[1 - team])
        world.step()
    assert not sees(world, team, inside) and not sees(world, team, at(node)) and world.sights == []
    assert all(view(world, seat, node).seen_age_s == TICK_S for seat in TEAM_OF[team])


@pytest.mark.parametrize("clearing_team", [0, 1], ids=["blue clears", "red clears"])
@pytest.mark.parametrize("node", ["blue_blue", "blue_gromp", "red_red", "red_raptors"])
def test_the_team_that_sees_a_clear_knows_the_respawn_at_once_and_the_other_team_only_from_the_window_before_it(clearing_team, node):
    killer, watcher = clearing_team * 5 + 1, (1 - clearing_team) * 5 + 1
    world = quiet({killer: at(node)}, until_s=90.0)
    unaware = [view(world, seat, node) for seat in TEAM_OF[1 - clearing_team]]
    assert all((v.hp, v.seen_age_s, v.spawn_s) == (0.0, None, 0.0) for v in unaware), "never seen, and the public first spawn has passed"
    death = clear(world, {killer: node})
    respawn_at = death.t + RESPAWN_S[node]
    for seat in TEAM_OF[clearing_team]:
        seen = view(world, seat, node)
        assert (seen.hp, seen.seen_age_s, now(world) + seen.spawn_s) == (0.0, 0.0, respawn_at)
    assert [view(world, seat, node) for seat in TEAM_OF[1 - clearing_team]] == unaware, "an unseen clear changes nothing for the other team"

    world.champions[watcher].pos = at(node)
    world.step()
    looked = view(world, watcher, node)
    assert (looked.hp, looked.seen_age_s, looked.spawn_s) == (0.0, 0.0, None), "the empty camp tells the time only inside the window"
    assert all(view(world, seat, node).spawn_s is None for seat in TEAM_OF[1 - clearing_team]), "teammates share one memory"
    until(lambda: view(world, watcher, node).spawn_s is not None, world.step, limit=700)
    assert (now(world), view(world, watcher, node).spawn_s) == (respawn_at - WINDOW_S[node], WINDOW_S[node])
    until(lambda: view(world, watcher, node).hp > 0, world.step, limit=200)
    assert now(world) == respawn_at + TICK_S, "the camp is seen alive from the tick it respawns"
    for seat in (killer, watcher):
        assert (view(world, seat, node).hp, view(world, seat, node).level, view(world, seat, node).spawn_s) == (HEALTH[node], 1, None)


@pytest.mark.parametrize("node", ["blue_blue", "blue_gromp"])
def test_a_look_at_an_empty_camp_before_the_window_gives_no_timer_however_long_the_team_then_waits(node):
    world = quiet({BLUE_JUNGLE: at(node)}, until_s=90.0)
    death = clear(world, {BLUE_JUNGLE: node})
    world.champions[RED_JUNGLE].pos = at(node)
    world.step()
    world.champions[RED_JUNGLE].pos = FOUNTAIN[1]
    while now(world) < death.t + RESPAWN_S[node] + 20.0:
        world.step()
        mine = view(world, RED_JUNGLE, node)
        assert (mine.hp, mine.spawn_s) == (0.0, None) and mine.seen_age_s > 0
    assert world.camps[site(node)].hp > 0, "the camp is back and the team that looked away does not know"


def test_a_known_timer_runs_out_of_sight_and_a_team_learns_of_an_unseen_clear_only_by_seeing_the_empty_camp():
    node = "blue_gromp"
    world = quiet({BLUE_JUNGLE: at(node)}, until_s=90.0)
    death = clear(world, {BLUE_JUNGLE: node})
    world.champions[BLUE_JUNGLE].pos = FOUNTAIN[0]
    while now(world) < death.t + RESPAWN_S[node]:
        world.step()
        assert now(world) + view(world, BLUE_TOP, node).spawn_s == death.t + RESPAWN_S[node]
    world.champions[RED_JUNGLE].pos = at(node)
    again = clear(world, {RED_JUNGLE: node})
    assert again.t > death.t + RESPAWN_S[node]
    for _ in range(40):
        world.step()
        stale = view(world, BLUE_TOP, node)
        assert (stale.hp, stale.spawn_s) == (0.0, 0.0), "the timer that ran out still stands, as the camp was not seen since"
        assert stale.seen_age_s == pytest.approx(now(world) - death.t - TICK_S)
    world.champions[BLUE_JUNGLE].pos = at(node)
    world.step()
    looked = view(world, BLUE_TOP, node)
    assert (looked.hp, looked.seen_age_s, looked.spawn_s) == (0.0, 0.0, None)


def test_the_team_that_sees_the_death_that_starts_the_rivers_timer_knows_the_next_scuttler_and_the_other_team_learns_it_in_the_last_10_s():
    world = quiet({BLUE_JUNGLE: at("top_river"), RED_JUNGLE: at("bot_river")}, until_s=176.0)
    first = clear(world, {BLUE_JUNGLE: "top_river"})
    assert first.respawn == -1 and view(world, BLUE_JUNGLE, "top_river").spawn_s is None, "one Scuttler lives, so no timer runs"
    world.champions[BLUE_JUNGLE].pos = FOUNTAIN[0]
    world.step()
    blue_before = [view(world, BLUE_TOP, node) for node in ("top_river", "bot_river")]
    last = clear(world, {RED_JUNGLE: "bot_river"})
    next_node = CAMP_SITES[last.respawn]
    assert now(world) + view(world, RED_TOP, next_node).spawn_s == last.t + 150.0
    blue_after = [view(world, BLUE_TOP, node) for node in ("top_river", "bot_river")]
    assert [v._replace(seen_age_s=None) for v in blue_after] == [v._replace(seen_age_s=None) for v in blue_before]
    world.champions[BLUE_JUNGLE].pos = at(next_node)
    world.champions[RED_JUNGLE].pos = FOUNTAIN[1]
    world.step()
    assert view(world, BLUE_TOP, next_node).spawn_s is None
    until(lambda: view(world, BLUE_TOP, next_node).spawn_s is not None, world.step, limit=400)
    assert (now(world), view(world, BLUE_TOP, next_node).spawn_s) == (last.t + 150.0 - 10.0, 10.0)


def test_the_first_spawn_of_every_camp_is_known_to_both_teams_from_the_start():
    world = World()
    for seat in SEATS:
        camps = observe(world, seat).camps
        assert [camp.spawn_s for camp in camps] == [67.0, 55.0, 55.0, 55.0, 55.0, 67.0] * 2 + [175.0, 175.0]
        assert all((camp.hp, camp.level, camp.seen_age_s) == (0.0, 0, None) for camp in camps)
    run(world, lambda o, noise: KEEP, 100)
    assert [camp.spawn_s for camp in observe(world, RED_MID).camps] == [17.0, 5.0, 5.0, 5.0, 5.0, 17.0] * 2 + [125.0, 125.0]


def test_the_camps_of_an_observation_are_in_the_order_of_the_camp_actions_with_the_walk_from_the_champion():
    world = World(Config(), seed=4)
    run(world, scripted, 300)
    first = next(i for i, a in enumerate(ACTIONS) if a.kind is Kind.CAMP)
    for seat in SEATS:
        own, enemy = ("blue", "red") if seat < 5 else ("red", "blue")
        o = observe(world, seat)
        assert len(o.camps) == len(CAMP_NODES) == 14
        for k, camp in enumerate(o.camps):
            node = ACTIONS[first + k].target.replace("own_", f"{own}_").replace("enemy_", f"{enemy}_")
            assert camp.walk == pytest.approx(RIFT.distance(world.champions[seat].pos, at(node)))
            assert (camp.hp > 0) == (world.camps[site(node)].hp > 0) or camp.seen_age_s != 0.0
    for seat in (BLUE_JUNGLE, RED_JUNGLE):
        seen_now = [k for k, camp in enumerate(observe(world, seat).camps) if camp.seen_age_s == 0.0]
        assert seen_now and all(CAMP_NODES[k].startswith("own_") for k in seen_now), "a jungler in its own jungle sees its own camps"


def test_the_gap_between_two_edges_is_a_floor_on_the_separation_of_any_positions_on_them_and_is_reached():
    marks = [[RIFT.advance(RIFT.at(RIFT.node_names[edge.a]), RIFT.at(RIFT.node_names[edge.b]), edge.length * part / 9) for part in range(10)]
             for edge in RIFT.edges]
    assert all(mark.edge == i for i, on_edge in enumerate(marks) for mark in on_edge[1:-1])
    apart = 0
    for i, j in itertools.combinations_with_replacement(range(len(RIFT.edges)), 2):
        gap = EDGE_GAP[i][j]
        nearest = min(RIFT.separation(a, b) for a in marks[i] for b in marks[j])
        assert gap == EDGE_GAP[j][i] and gap <= nearest + 1e-6
        shared = {RIFT.edges[i].a, RIFT.edges[i].b} & {RIFT.edges[j].a, RIFT.edges[j].b}
        assert gap == 0.0 if shared else nearest - gap < RIFT.edges[i].length / 9 + RIFT.edges[j].length / 9
        apart += gap > R["champions"]["sight_range"]
    assert apart > 1000, "most pairs of edges are further apart than a champion sees"


def test_a_team_sees_a_position_exactly_when_one_of_its_living_champions_its_standing_towers_or_its_own_shrines_does():
    places = {BLUE_TOP: lane_place(0, "top", 6000.0), BLUE_JUNGLE: at("blue_raptors"), BLUE_MID: lane_place(0, "mid", 5000.0),
              3: lane_place(0, "bot", 7000.0), 4: lane_place(0, "bot", 6500.0), RED_TOP: lane_place(1, "top", 6000.0),
              RED_JUNGLE: at("red_krugs"), RED_MID: lane_place(1, "mid", 5000.0), 8: lane_place(1, "bot", 7000.0)}
    world = staged(places)
    world.damage_champion(BLUE_MID, 10_000.0)
    world.step()
    assert world.champions[BLUE_MID].pos == FOUNTAIN[0] and world.champions[BLUE_MID].hp == 0
    world.light(0, at("top_river"), SHRINE_RADIUS, SHRINE_S)
    world.light(1, at("bot_river"), SHRINE_RADIUS, SHRINE_S)
    fallen = ("blue_mid_outer", "red_bot_inner")
    world.lanes["mid"].towers[0][0].hp = world.lanes["bot"].towers[1][1].hp = 0.0
    marks = [RIFT.advance(RIFT.at(RIFT.node_names[edge.a]), RIFT.at(RIFT.node_names[edge.b]), edge.length * part / 7)
             for edge in RIFT.edges for part in range(8)]
    sight = R["champions"]["sight_range"]
    for team in (0, 1):
        by_champion = [any(c.hp > 0 and RIFT.sees(c.pos, mark, sight) for c in world.champions[team * 5:team * 5 + 5]) for mark in marks]
        by_shrine = [any(s.team == team and RIFT.sees(s.pos, mark, s.radius) for s in world.sights) for mark in marks]
        towers = [RIFT.lane_pos(t.lane, t.s) for t in MAP.towers if t.team == TEAMS[team] and t.name != fallen[team]]
        by_tower = [any(RIFT.sees(tower, mark, R["towers"]["sight_range"]) for tower in towers) for mark in marks]
        assert len(towers) == 8
        assert [sees(world, team, mark) for mark in marks] == [a or b or c for a, b, c in zip(by_champion, by_shrine, by_tower)]
        assert sum(by_champion) > 20 and sum(b and not a and not c for a, b, c in zip(by_champion, by_shrine, by_tower)) > 2
        assert sum(c and not a and not b for a, b, c in zip(by_champion, by_shrine, by_tower)) > 20
        assert sum(not a and not b and not c for a, b, c in zip(by_champion, by_shrine, by_tower)) > 100
    assert not sees(world, 0, FOUNTAIN[0]) and sees(world, 1, FOUNTAIN[1]), "a dead champion on its fountain sees nothing"
    assert sees(world, 0, at("top_river")) and not sees(world, 1, at("top_river"))
    assert sees(world, 1, at("bot_river")) and not sees(world, 0, at("bot_river"))


@pytest.mark.parametrize("seed", [3, 4])
def test_a_teams_memory_takes_in_a_camp_on_exactly_the_ticks_on_which_the_team_sees_its_location(seed):
    world = World(Config(), seed)
    seen = Counter()
    for _ in range(700):
        tick(world, busy)
        for team in (0, 1):
            ages = [camp.seen_age_s for camp in observe(world, team * 5).camps]
            for k, node in enumerate(CAMP_NODES):
                in_sight = sees(world, team, at(node.replace("own_", f"{TEAMS[team]}_").replace("enemy_", f"{TEAMS[1 - team]}_")))
                assert (ages[k] == 0.0) == in_sight, f"tick {world.tick}, team {team}, {node}"
                seen[in_sight] += 1
    assert seen[True] > 2000 and seen[False] > 10_000


def mid_game(seed: int = 7) -> World:
    """A scripted game at a moment when a jungler is fighting a camp and a shrine stands."""
    world = World(Config(), seed)
    run(world, scripted, 380)
    until(lambda: world.sights and any(camp.engaged >= 0 for camp in world.camps), lambda: tick(world, scripted), limit=600)
    assert any(memory.hp > 0 for memory in world.memory[0].camps) and any(memory.spawn_tick > world.tick for memory in world.memory[1].camps)
    return world


CAMP_CHANGED = {"hp": 1.5, "max_hp": 9000.0, "level": 7, "spawn_tick": 12345, "engaged": 3}
MEMORY_CHANGED = {"hp": 1.5, "level": 7, "seen_tick": 3, "spawn_tick": 12345}
SIGHT_CHANGED = {"team": 0, "pos": RIFT.at("mid_river"), "radius": 1.5, "expires": 12345}


def test_the_digest_changes_with_every_field_of_a_camp_of_a_memory_and_of_a_sight_source():
    assert set(CAMP_CHANGED) == {f.name for f in fields(Camp)} and set(MEMORY_CHANGED) == {f.name for f in fields(CampMemory)}
    assert set(SIGHT_CHANGED) == {f.name for f in fields(Sight)}
    world = mid_game()
    seen = {world.digest()}
    for record, changed in ((world.camps[13], CAMP_CHANGED), (world.memory[1].camps[2], MEMORY_CHANGED)):
        for name, value in changed.items():
            assert getattr(record, name) != value
            setattr(record, name, value)
            seen.add(world.digest())
    for name, value in SIGHT_CHANGED.items():
        assert getattr(world.sights[0], name) != value
        world.sights[0] = replace(world.sights[0], **{name: value})
        seen.add(world.digest())
    world.sights.append(world.sights[0])
    seen.add(world.digest())
    assert len(seen) == 1 + len(CAMP_CHANGED) + len(MEMORY_CHANGED) + len(SIGHT_CHANGED) + 1


def test_a_snapshot_taken_in_the_middle_of_a_clear_with_a_shrine_up_replays_every_digest_here_and_in_another_process(tmp_path):
    game = mid_game()
    snapshot = game.snapshot()
    file = tmp_path / "snapshot.pickle"
    file.write_bytes(pickle.dumps(snapshot))
    expected, ended = play(game, scripted, 400)
    assert ended["CLEARED"] >= 4 and len(set(expected)) == 400
    game.camps[0].hp, game.memory[0].camps[0].hp = -5.0, -5.0
    game.sights.clear()
    used = World.restore(snapshot)
    run(used, scripted, 150)
    assert play(World.restore(snapshot), scripted, 400)[0] == expected
    script = ("import pickle, sys; from riftgame.harness import scripted, tick; from riftgame.world import World\n"
              "world = World.restore(pickle.loads(open(sys.argv[1], 'rb').read()))\n"
              "for _ in range(400):\n"
              "    tick(world, scripted)\n"
              "    print(world.digest())\n")
    for hash_seed in ("1", "2"):
        env = os.environ | {"PYTHONHASHSEED": hash_seed, "PYTHONPATH": str(REPO)}
        child = subprocess.run([sys.executable, "-c", script, str(file)], env=env, capture_output=True, text=True, check=True)
        assert child.stdout.split() == expected


def set_camp(node: str, **changes):
    return lambda world: [setattr(world.camps[site(node)], name, value) for name, value in changes.items()]


def both(*breaks):
    return lambda world: [change(world) for change in breaks]


BREAKS = {
    "camp health above its maximum": set_camp("blue_blue", hp=2300.5),
    "camp health below zero": set_camp("blue_blue", hp=-0.5),
    "a living camp that is due to spawn": set_camp("red_krugs", spawn_tick=900),
    "a dead camp that is not due to spawn": set_camp("red_krugs", hp=0.0),
    "a dead camp that is engaged": set_camp("red_krugs", hp=0.0, spawn_tick=900, engaged=6),
    "a river with no Scuttler alive or due": both(set_camp("top_river", hp=0.0), set_camp("bot_river", hp=0.0)),
    "a Scuttler due while another lives": set_camp("top_river", hp=0.0, spawn_tick=900),
    "two Scuttlers due after the first spawn": both(set_camp("top_river", hp=0.0, spawn_tick=900), set_camp("bot_river", hp=0.0, spawn_tick=900)),
    "two Scuttlers alive that are not the first pair": both(set_camp("top_river", hp=1550.0, max_hp=1550.0), set_camp("bot_river", hp=1550.0, max_hp=1550.0)),
}


@pytest.mark.parametrize("change", BREAKS.values(), ids=BREAKS.keys())
def test_the_checker_raises_on(change):
    world = quiet(until_s=180.0)
    check_invariants(world)
    change(world)
    with pytest.raises(InvariantError):
        check_invariants(world)


@pytest.mark.parametrize("seed", [0, 1])
def test_a_scripted_game_runs_ten_minutes_with_the_invariant_checker_on_every_tick_and_both_junglers_clear_camps(seed):
    world = World(Config(), seed)
    ended, most_on_river = Counter(), 0
    for _ in range(1200):
        tick(world, scripted, check=True)
        ended += ended_now(world)
        most_on_river = max(most_on_river, len(river_alive(world)) if now(world) > 400.0 else 0)
    assert ended["CLEARED"] >= 20 and most_on_river == 1
    for seat in (BLUE_JUNGLE, RED_JUNGLE):
        me = world.champions[seat]
        assert me.earned[Income.CAMP] > 800 and level_of(me.xp) >= 4 and me.gold == pytest.approx(sum(me.earned) - spent(me))
    assert all(c.earned[Income.CAMP] == 0 for c in world.champions if c.role != 1)


def test_the_scripted_jungler_goes_for_a_camp_it_knows_to_be_up_and_waits_at_one_that_is_about_to_spawn():
    world = quiet({BLUE_JUNGLE: at("blue_red")}, until_s=50.0)
    assert jungler(observe(world, BLUE_JUNGLE), 0.0) == HOLD, "it stands at the camp that spawns in 5 s"
    while now(world) < 56.0:
        world.step()
    assert jungler(observe(world, BLUE_JUNGLE), 0.0) == camp_action(BLUE_JUNGLE, "blue_red")
    world.champions[BLUE_JUNGLE].pos = FOUNTAIN[0]
    world.step()
    choice = ACTIONS[jungler(observe(world, BLUE_JUNGLE), 0.0)]
    assert choice.kind is Kind.CAMP and choice.target.startswith("own_"), "from its fountain it walks to a camp of its own side"


def test_the_scripted_jungler_recalls_when_it_is_low_and_stays_on_its_fountain_until_it_has_recovered():
    world = quiet({BLUE_JUNGLE: at("blue_red")}, until_s=60.0)
    me = world.champions[BLUE_JUNGLE]
    me.hp = 0.3 * capability_of(me).max_hp
    assert jungler(observe(world, BLUE_JUNGLE), 0.0) == RECALL
    submit(world, {BLUE_JUNGLE: RECALL})
    assert jungler(observe(world, BLUE_JUNGLE), 0.0) == KEEP
    me.pos = FOUNTAIN[0]
    world.step()
    assert jungler(observe(world, BLUE_JUNGLE), 0.0) == HOLD
    me.hp = 0.9 * capability_of(me).max_hp
    world.step()
    assert ACTIONS[jungler(observe(world, BLUE_JUNGLE), 0.0)].kind is Kind.CAMP
