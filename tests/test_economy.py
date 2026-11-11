import pytest

from riftgame import economy
from riftgame.champions import LANES, OUTER_TOWER, RIFT, SEATS, Income, Kind, R, capability_of, level_of
from riftgame.lanes import TOWER_RANGE, ChampionDamage, MinionDeath, unit_stats
from riftgame.lanes import Kind as Minion
from riftgame.vision import legal_mask, observe
from riftgame.world import Config, World
from worlds import (BLUE_CARRY, BLUE_JUNGLE, BLUE_MID, BLUE_SUPPORT, BLUE_TOP, RED_CARRY, RED_MID, RED_SUPPORT, RED_TOP, act,
                    staged, submit)

TICK_S = 0.5
PASSIVE_PER_S = R["economy"]["passive_gold_per_10s"] / 10
PASSIVE_FROM_S = R["economy"]["passive_gold_start_s"]
ITEM = R["support_item"]
BLUE, RED = 0, 1


def lane(name, mode):
    return act(Kind.LANE, (name, mode))


def at_towers(*seats):
    return {seat: OUTER_TOWER[seat // 5][("top", None, "mid", "bot", "bot")[seat % 5]] for seat in seats}


def played(orders, seconds=300.0, seed=0, world=None):
    """A game in which the given seats start at their outer towers with their orders. Returns it with every lane event."""
    world = staged(at_towers(*orders), Config(decision_ticks=1), seed) if world is None else world
    events = []
    submit(world, orders)
    events += world.events
    while world.tick * TICK_S < seconds:
        world.step()
        events += world.events
    return world, events


def deaths(events, team, lane_name=None):
    return [e for name, e in events if type(e) is MinionDeath and e.team == team and lane_name in (None, name)]


def test_a_laner_earns_the_gold_of_exactly_the_minions_it_killed_and_nobody_else_earns_minion_gold():
    world, events = played({BLUE_MID: lane("mid", "last_hit")})
    mine = [e for e in deaths(events, RED) if e.killer == BLUE_MID]
    assert len(mine) > 20
    assert world.champions[BLUE_MID].earned[Income.MINION] == pytest.approx(sum(e.gold for e in mine))
    assert all(c.earned[Income.MINION] == 0 for c in world.champions if c.seat != BLUE_MID)
    assert all(e.gold == 0 for e in deaths(events, RED) if e.killer is None)


def test_minion_gold_in_bot_lane_is_paid_once_however_the_two_champions_share_the_farm():
    world, events = played({BLUE_CARRY: lane("bot", "last_hit"), BLUE_SUPPORT: lane("bot", "last_hit")})
    dead = deaths(events, RED, "bot")
    killed = [e for e in dead if e.killer is not None]
    pair = world.champions[BLUE_CARRY].earned[Income.MINION] + world.champions[BLUE_SUPPORT].earned[Income.MINION]
    assert {e.killer for e in killed} == {BLUE_CARRY, BLUE_SUPPORT}
    assert pair == pytest.approx(sum(e.gold for e in killed))
    assert pair <= sum(unit_stats(e.kind, e.t)[2] for e in dead)


def test_a_pair_in_range_gets_1_3_times_a_solo_laners_xp_and_neither_gets_more_than_the_solo_laner():
    solo, _ = played({BLUE_CARRY: lane("bot", "passive")})
    pair, _ = played({BLUE_CARRY: lane("bot", "passive"), BLUE_SUPPORT: lane("bot", "passive")})
    alone = solo.champions[BLUE_CARRY].xp
    carry, support = pair.champions[BLUE_CARRY].xp, pair.champions[BLUE_SUPPORT].xp
    assert alone > 1000
    assert carry + support == pytest.approx(1.3 * alone, rel=0.02)
    assert carry <= alone and support <= alone
    assert solo.champions[BLUE_SUPPORT].xp == 0


def test_the_support_item_pays_3_gold_per_10_s_plus_18_per_charge_used_and_gives_at_most_one_charge_per_20_s():
    world, events = played({BLUE_CARRY: lane("bot", "last_hit"), BLUE_SUPPORT: lane("bot", "last_hit")})
    now = world.tick * TICK_S
    support, carry = world.champions[BLUE_SUPPORT], world.champions[BLUE_CARRY]
    shared = [e for e in deaths(events, RED, "bot") if e.shared]
    assert len(shared) >= 3 and all(e.killer == BLUE_SUPPORT for e in shared)
    assert support.earned[Income.SUPPORT_ITEM] == pytest.approx(ITEM["passive_gold_per_10s"] / 10 * now + ITEM["charge_gold"] * len(shared))
    charges_so_far = 1 + (now - TICK_S - ITEM["charge_first_s"]) // ITEM["charge_interval_s"]
    assert len(shared) + support.item_charges <= charges_so_far
    assert 0 <= support.item_charges <= ITEM["charge_max"]
    own = [e for e in deaths(events, RED, "bot") if e.killer == BLUE_CARRY]
    assert carry.earned[Income.MINION] == pytest.approx(sum(e.gold for e in own + shared))
    assert carry.earned[Income.SUPPORT_ITEM] == 0


def test_a_support_without_an_ally_in_range_shares_nothing():
    world, events = played({BLUE_SUPPORT: lane("bot", "last_hit")})
    assert not [e for e in deaths(events, RED) if e.shared]
    support = world.champions[BLUE_SUPPORT]
    assert support.item_charges == ITEM["charge_max"]
    assert support.earned[Income.SUPPORT_ITEM] == pytest.approx(ITEM["passive_gold_per_10s"] / 10 * world.tick * TICK_S)


def test_every_champions_gold_is_the_sum_of_its_ledger_and_each_source_is_accounted_for_apart():
    orders = {BLUE_TOP: lane("top", "push"), BLUE_MID: lane("mid", "thin"), BLUE_CARRY: lane("bot", "last_hit"), BLUE_SUPPORT: lane("bot", "passive"),
              RED_TOP: lane("top", "last_hit"), RED_MID: lane("mid", "push"), RED_CARRY: lane("bot", "last_hit"), RED_SUPPORT: lane("bot", "last_hit")}
    world, events = played(orders)
    now = world.tick * TICK_S
    farmers = set(orders) - {BLUE_SUPPORT}
    for c in world.champions:
        assert c.gold == pytest.approx(sum(c.earned))
        assert c.earned[Income.STARTING] == R["economy"]["starting_gold"]
        assert c.earned[Income.PASSIVE] == pytest.approx(PASSIVE_PER_S * (now - PASSIVE_FROM_S))
        assert (c.earned[Income.SUPPORT_ITEM] > 0) == (c.seat in (BLUE_SUPPORT, RED_SUPPORT))
        assert (c.earned[Income.MINION] > 0) == (c.seat in farmers)
    for team in (BLUE, RED):
        minion_gold = sum(c.earned[Income.MINION] for c in world.champions if c.team == team)
        assert minion_gold == pytest.approx(sum(e.gold for e in deaths(events, 1 - team)))


def death_at(world, lane_name, s, team=RED):
    return MinionDeath(world.tick * TICK_S, team, Minion.MELEE, s, None, 0, 62.0)


def test_minion_xp_goes_to_living_enemy_champions_within_1500_units_in_a_straight_line():
    centre = RIFT.lanes["mid"].length / 2
    world = staged({BLUE_MID: RIFT.lane_pos("mid", centre - 1400), BLUE_TOP: RIFT.lane_pos("mid", centre - 1600), RED_MID: RIFT.lane_pos("mid", centre)})
    economy.settle_lane(world, "mid", [death_at(world, "mid", centre)])
    assert [world.champions[seat].xp for seat in (BLUE_MID, BLUE_TOP, RED_MID)] == [62.0, 0, 0]
    world.champions[BLUE_TOP].pos = RIFT.lane_pos("mid", centre - 1000)
    economy.settle_lane(world, "mid", [death_at(world, "mid", centre)])
    assert world.champions[BLUE_TOP].xp == pytest.approx(62.0 * 0.65)
    world.champions[BLUE_MID].hp = 0.0
    economy.settle_lane(world, "mid", [death_at(world, "mid", centre)])
    assert world.champions[BLUE_TOP].xp == pytest.approx(62.0 * 1.65)
    assert world.champions[BLUE_MID].xp == pytest.approx(62.0 * 1.65)


def test_xp_range_is_a_straight_line_and_not_a_walk():
    corner = RIFT.lanes["top"].starts[4]
    before, after = RIFT.lane_pos("top", corner - 800), RIFT.lane_pos("top", corner + 800)
    assert RIFT.distance(before, after) == pytest.approx(1600) and RIFT.separation(before, after) < 1500
    world = staged({BLUE_TOP: before})
    economy.settle_lane(world, "top", [death_at(world, "top", corner + 800)])
    assert world.champions[BLUE_TOP].xp == 62.0


def test_a_jungler_keeps_30_percent_of_lane_minion_xp_at_the_start_and_all_of_it_from_20_minutes():
    world = World()
    jungler, laner = world.champions[BLUE_JUNGLE], world.champions[BLUE_MID]
    assert economy.jungle_share(jungler, 0.0) == pytest.approx(0.30)
    assert economy.jungle_share(jungler, 600.0) == pytest.approx(0.65)
    assert economy.jungle_share(jungler, 1200.0) == 1.0
    assert economy.jungle_share(laner, 0.0) == 1.0


def test_the_lanes_get_the_teams_level_lead():
    world = World(Config(decision_ticks=1))
    assert economy.level_lead(world) == 0
    world.champions[BLUE_TOP].xp = 280.0 + 380.0
    assert level_of(world.champions[BLUE_TOP].xp) == 3
    assert economy.level_lead(world) == pytest.approx(0.4)
    world.step()
    assert all(world.lanes[name].level_lead == pytest.approx(0.4) for name in LANES)


def test_minions_hurt_a_champion_that_holds_them_and_its_health_then_comes_back_at_its_regeneration_rate():
    world = staged(at_towers(BLUE_MID), Config(decision_ticks=1))
    tower = world.lanes["mid"].geometry.towers[BLUE][0]
    world.lanes["mid"].add_minion(RED, Minion.CASTER, tower + TOWER_RANGE + 900.0, count=2)
    submit(world, {BLUE_MID: lane("mid", "hold")})
    champion = world.champions[BLUE_MID]
    full = capability_of(champion).max_hp
    bitten = []
    while world.tick * TICK_S < 12.0:
        world.step()
        bitten += [e for _, e in world.events if type(e) is ChampionDamage]
    assert bitten and all(e.seat == BLUE_MID for e in bitten)
    lowest = champion.hp
    lost = sum(e.damage for e in bitten)
    assert full - lost <= lowest <= full - lost + capability_of(champion).hp_regen * 12.0
    assert lowest < full - 50
    world.lanes["mid"].minions[RED].clear()
    for _ in range(20):
        world.step()
    assert champion.hp == pytest.approx(min(full, lowest + capability_of(champion).hp_regen * 10.0))


def test_changing_the_minions_and_towers_of_every_lane_changes_no_observation_and_no_mask():
    world, _ = played({BLUE_MID: lane("mid", "last_hit"), RED_MID: lane("mid", "last_hit")}, seconds=90.0)
    before = [(observe(world, seat), legal_mask(observe(world, seat))) for seat in SEATS]
    for name in LANES:
        sim = world.lanes[name]
        sim.minions[RED].clear()
        sim.add_minion(BLUE, Minion.SIEGE, sim.geometry.centre, count=4)
        for team in (BLUE, RED):
            sim.towers[team][0].hp -= 1000.0
    assert [(observe(world, seat), legal_mask(observe(world, seat))) for seat in SEATS] == before


def test_a_champion_in_one_lane_changes_nothing_in_another_lane():
    quiet, _ = played({}, seconds=200.0, seed=7)
    busy, _ = played({BLUE_TOP: lane("top", "push")}, seconds=200.0, seed=7)
    assert busy.lanes["top"].values() != quiet.lanes["top"].values()
    assert busy.lanes["mid"].values() == quiet.lanes["mid"].values()
    assert busy.lanes["bot"].values() == quiet.lanes["bot"].values()
    assert [busy.champions[seat] for seat in SEATS if seat != BLUE_TOP] == [quiet.champions[seat] for seat in SEATS if seat != BLUE_TOP]


def test_a_restored_world_with_champions_in_every_lane_replays_tick_for_tick():
    orders = {BLUE_TOP: lane("top", "push"), BLUE_MID: lane("mid", "thin"), BLUE_CARRY: lane("bot", "last_hit"), BLUE_SUPPORT: lane("bot", "last_hit"),
              RED_TOP: lane("top", "hold"), RED_MID: lane("mid", "last_hit"), RED_CARRY: lane("bot", "push"), RED_SUPPORT: lane("bot", "passive")}
    world, _ = played(orders, seconds=120.0, seed=3)
    saved = world.snapshot()
    first = []
    for _ in range(600):
        world.step()
        first.append(world.digest())
    again = World.restore(saved)
    for digest in first:
        again.step()
        assert again.digest() == digest
    assert sum(c.earned[Income.MINION] for c in world.champions) > 500
