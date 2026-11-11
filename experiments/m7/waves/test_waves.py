import math
import statistics

import pytest

from experiments.m7.waves import scenarios
from experiments.m7.waves.cohort import CohortLane
from experiments.m7.waves.lane import (
    ACQUIRE,
    MID,
    MINIONS,
    RECOMMENDED,
    SPEED,
    TOP,
    TOWER_RANGE,
    ChampionDamage,
    ChampionInput,
    Kind,
    LaneGeometry,
    LaneSim,
    Mechanics,
    MinionDeath,
    Mode,
    Team,
    TowerDamage,
    XpGrant,
)
from riftgame.map import load_map

BLUE, RED = Team.BLUE, Team.RED
AGGRO = Mechanics(champion_aggro=True)
SLOTS = Mechanics(lateral_slots=True)
MELEE_AD_AT_181_S = 11 + (80 - 11) * (181 - 60) / (2520 - 60)
VARIANTS = pytest.mark.parametrize("make", [LaneSim, CohortLane])
POLICIES = pytest.mark.parametrize("policy", [scenarios.idle, scenarios.last_hitters()])


def deaths(events, team=None):
    return [e for e in events if type(e) is MinionDeath and team in (None, e.team)]


def one_melee_under_blue_tower(make, champions, until=200.0):
    sim = make(MID, start_time=181.0)
    sim.add_minion(RED, Kind.MELEE, MID.tower_s[BLUE] + TOWER_RANGE + 100.0)
    events = []
    while sim.time < until:
        events += sim.step(champions)
    return events


@POLICIES
def test_swapping_sides_mirrors_the_front(policy):
    left = scenarios.run(LaneSim(MID, seed=3), policy, 300.0)
    right = scenarios.run(LaneSim(MID.swapped_sides(), seed=3), policy, 300.0)
    assert any(r.line != pytest.approx(MID.centre) for r in left.rows if r.contact), "the lane never left the centre, so the mirror is untested"
    for a, b in zip(left.rows, right.rows, strict=True):
        assert (a.n_blue, a.n_red) == (b.n_blue, b.n_red)
        for lead_a, lead_b in ((a.lead_blue, b.lead_blue), (a.lead_red, b.lead_red)):
            assert (lead_a is None) == (lead_b is None)
            assert lead_a is None or lead_b == pytest.approx(MID.length - lead_a, abs=1e-6)


@POLICIES
@pytest.mark.parametrize("make", [scenarios.SpawnOrderTies, CohortLane])
def test_without_random_ties_neither_team_gains_ground_on_a_symmetric_lane(make, policy):
    symmetric = LaneGeometry(MID.length, MID.spawn_offset, (MID.tower_s[BLUE], MID.length - MID.tower_s[BLUE]))
    trace = scenarios.run(make(symmetric, seed=0), policy, 300.0)
    assert sum(r.contact for r in trace.rows) > 100
    for r in trace.rows:
        assert r.n_blue == r.n_red
        assert r.lead_blue is None or r.lead_blue + r.lead_red == pytest.approx(symmetric.length, abs=1e-6)
    blue, red = (sorted((e.t, e.kind, e.killer is None) for e in deaths(trace.events, team)) for team in Team)
    assert blue == red


@VARIANTS
def test_first_waves_meet_halfway_between_the_spawn_points_when_their_leads_come_into_acquisition_range(make):
    metrics, _ = scenarios.undisturbed(MID)(make, 0, 0.25)
    march = (MID.spawn_s(RED) - MID.spawn_s(BLUE) - ACQUIRE) / 2
    assert metrics["first_contact_s"] == pytest.approx((MID.spawn_s(BLUE) + MID.spawn_s(RED)) / 2)
    assert metrics["first_contact_t"] == math.ceil((MINIONS["first_spawn_s"] + march / SPEED) / 0.25) * 0.25


@VARIANTS
def test_every_spawned_minion_is_alive_or_dead(make):
    sim = make(MID, seed=1)
    trace = scenarios.run(sim, scenarios.HardPush(red_present=True), 300.0)
    waves = 9
    sieges = 3
    assert sim.spawned == 2 * (6 * waves + sieges)
    assert sim.spawned == sum(sim.front().counts) + len(deaths(trace.events))
    assert len(deaths(trace.events)) > 50


@VARIANTS
def test_same_seed_and_inputs_give_identical_events(make):
    first = scenarios.run(make(MID, seed=5), scenarios.last_hitters(), 300.0)
    second = scenarios.run(make(MID, seed=5), scenarios.last_hitters(), 300.0)
    assert first.events == second.events
    assert len(first.events) > 100


def test_a_champion_in_one_lane_does_not_change_another_lane():
    def lane_zero_events(other_lane_policy):
        mine, other = LaneSim(MID, seed=7, lane_id=0), LaneSim(MID, seed=7, lane_id=1)
        events, last = [], []
        while mine.time < 300.0:
            last = other.step(other_lane_policy(other, last))
            events += mine.step()
        return events

    quiet = lane_zero_events(scenarios.idle)
    assert quiet == lane_zero_events(scenarios.HardPush(red_present=True))
    other_lane_id = scenarios.run(LaneSim(MID, seed=7, lane_id=1), scenarios.idle, 300.0).events
    assert quiet != other_lane_id, "lane_id is not part of the draw key"


@VARIANTS
def test_gold_goes_only_to_the_champion_that_lands_the_killing_blow(make):
    trace = scenarios.run(make(MID, seed=2), scenarios.last_hitters(), 300.0)
    kills = deaths(trace.events)
    assert {e.killer for e in kills} == {None, BLUE, RED}
    for e in kills:
        assert (e.gold > 0) == (e.killer is not None)
        assert e.killer != e.team
        if e.killer is not None:
            assert e.gold >= MINIONS[e.kind.name.lower()]["gold"]


def test_last_hit_adds_no_damage_before_the_killing_blow():
    harmless = ChampionInput(0, BLUE, MID.tower_s[BLUE], Mode.LAST_HIT, hit_damage=0.0)
    alone = deaths(one_melee_under_blue_tower(LaneSim, []))
    watched = deaths(one_melee_under_blue_tower(LaneSim, [harmless]))
    assert len(alone) == 1 and alone == watched


def test_last_hit_under_tower_takes_melee_after_two_shots_and_loses_casters():
    metrics, trace = scenarios.tower_farm(1.0)(LaneSim, 0, 1.0)
    taken = [e for e in deaths(trace.events, RED) if e.killer == BLUE]
    assert metrics["red_deaths"] == 12
    assert [e.kind for e in taken] == [Kind.MELEE] * 6
    assert sum(e.gold for e in taken) == 6 * MINIONS["melee"]["gold"]


@VARIANTS
@pytest.mark.parametrize("sharers", [1, 2, 3])
def test_xp_is_split_by_xp_share_among_enemy_champions_in_range(make, sharers):
    near = [ChampionInput(i, BLUE, MID.tower_s[BLUE], Mode.NONE) for i in range(sharers)]
    far = ChampionInput(8, BLUE, MID.tower_s[BLUE] - MINIONS["xp_range"], Mode.NONE)
    same_team = ChampionInput(9, RED, MID.tower_s[BLUE], Mode.NONE)
    events = one_melee_under_blue_tower(make, [*near, far, same_team])
    grants = {e.champ_id: e.xp for e in events if type(e) is XpGrant}
    assert len(deaths(events)) == 1
    assert grants == {c.champ_id: MINIONS["melee"]["xp"] * MINIONS["xp_share"][sharers - 1] for c in near}


def test_hard_push_crashes_the_first_wave_before_the_second_could_reach_the_tower():
    metrics, _ = scenarios.bounce(MID)(LaneSim, 0, 1.0)
    second_wave_arrives = 2 * MINIONS["first_spawn_s"] + (MID.tower_s[RED] - TOWER_RANGE - MID.spawn_s(BLUE)) / SPEED
    assert metrics["crash_t"] < second_wave_arrives
    assert metrics["tower_damage_first_crash"] > 0


def test_less_capacity_means_less_farm():
    def farm(case):
        return statistics.median(case(LaneSim, seed, 1.0)[0]["cs_blue"] for seed in range(3))

    lane = [farm(scenarios.last_hit(capacity)) for capacity in (1.0, 0.5, 0.25)]
    tower = [farm(scenarios.tower_farm(capacity)) for capacity in (1.0, 0.5, 0.25)]
    assert lane[0] > lane[1] > lane[2]
    assert tower[0] > tower[1] > tower[2]


def test_crash_time_is_stable_across_tick_lengths_up_to_one_second():
    times = [scenarios.bounce(MID)(LaneSim, 0, dt)[0]["crash_t"] for dt in (0.25, 0.5, 1.0)]
    assert max(times) - min(times) <= scenarios.TOLERANCE * min(times)


def test_both_variants_agree_on_the_hard_push_crash():
    individual, _ = scenarios.bounce(MID)(LaneSim, 0, 1.0)
    cohort, _ = scenarios.bounce(MID)(CohortLane, 0, 1.0)
    assert cohort["crash_t"] == pytest.approx(individual["crash_t"], rel=scenarios.TOLERANCE)
    assert cohort["crash_wave"] == individual["crash_wave"]


def test_lanes_take_their_length_spawn_points_and_outer_towers_from_the_reference_map():
    data = load_map()
    for name, geometry in (("mid", MID), ("top", TOP)):
        outer = {site.team: site.s for site in data.towers if site.lane == name and site.tier == "outer"}
        assert geometry.length == data.rift.lanes[name].length
        assert geometry.tower_s == (outer["blue"], outer["red"])
        assert [geometry.spawn_s(team) for team in Team] == [data.minion_spawn_s["blue", name], data.minion_spawn_s["red", name]]


def test_first_round_call_signatures_and_defaults_are_unchanged():
    sim = LaneSim(MID, 3, 1, 0.5)
    champion = ChampionInput(0, BLUE, MID.centre, Mode.LAST_HIT, 65.0, 0.65, 550.0, 70.0, 1.0)
    assert (sim.seed, sim.lane_id, sim.dt, sim.mechanics, champion.targetable) == (3, 1, 0.5, Mechanics(), False)


def lone_red_melee(mechanics, champion_s, blue_melee_s=None, until=190.0):
    """One red melee walks toward the blue tower past a targetable blue champion that does not attack."""
    sim = LaneSim(MID, start_time=181.0, mechanics=mechanics)
    sim.add_minion(RED, Kind.MELEE, champion_s + 400.0)
    if blue_melee_s is not None:
        sim.add_minion(BLUE, Kind.MELEE, blue_melee_s)
    champion = ChampionInput(0, BLUE, champion_s, Mode.NONE, targetable=True)
    events = []
    while sim.time < until:
        events += sim.step([champion])
    return sim, events


def test_without_champion_aggro_a_targetable_champion_changes_nothing():
    spot = MID.tower_s[BLUE] + TOWER_RANGE + 600.0
    sim, events = lone_red_melee(Mechanics(), spot)
    assert not [e for e in events if type(e) is ChampionDamage]
    assert [e for e in events if type(e) is TowerDamage and e.team is BLUE], "the minion never walked past the champion to the tower"


def test_a_minion_with_no_enemy_minion_in_range_stops_at_the_champion_and_deals_60_percent_damage():
    spot = MID.tower_s[BLUE] + TOWER_RANGE + 600.0
    sim, events = lone_red_melee(AGGRO, spot)
    bites = [e for e in events if type(e) is ChampionDamage]
    assert sim.front().lead[RED] == pytest.approx(spot + MINIONS["melee"]["attack_range"])
    assert len(bites) >= 8
    assert {e.champ_id for e in bites} == {0}
    assert all(e.damage == pytest.approx(0.60 * MELEE_AD_AT_181_S) for e in bites)


def test_a_minion_attacks_an_enemy_minion_in_acquisition_range_before_the_champion():
    spot = MID.tower_s[BLUE] + TOWER_RANGE + 600.0
    _, events = lone_red_melee(AGGRO, spot, blue_melee_s=spot - 50.0, until=186.0)
    assert not [e for e in events if type(e) is ChampionDamage]


@pytest.mark.parametrize("mechanics, held", [(RECOMMENDED, True), (Mechanics(), False)])
def test_a_holding_champion_keeps_a_wave_off_its_tower_and_pays_health_only_with_champion_aggro(mechanics, held):
    sim = LaneSim(TOP, start_time=181.0, mechanics=mechanics)
    edge = TOP.tower_s[BLUE] + TOWER_RANGE
    sim.add_minion(RED, Kind.MELEE, edge + 800.0, count=3)
    sim.add_minion(RED, Kind.CASTER, edge + 1200.0, count=3)
    trace = scenarios.run(sim, lambda sim, events: [scenarios.laner(sim, BLUE, Mode.NONE, hold=True)], 200.0)
    tower = sum(e.damage for e in trace.events if type(e) is TowerDamage and e.team is BLUE)
    champion = sum(e.damage for e in trace.events if type(e) is ChampionDamage)
    assert (tower == 0) == held
    assert (champion > 0) == held
    assert all(r.lead_red > edge for r in trace.rows) == held


def test_with_lateral_slots_an_even_fight_ends_level_and_the_same_for_every_seed():
    make = scenarios.maker(SLOTS)
    paired = [scenarios.fight()(make, seed, 1.0)[0] for seed in range(5)]
    drawn = [scenarios.fight()(LaneSim, seed, 1.0)[0] for seed in range(5)]
    assert all(run == paired[0] for run in paired)
    assert (paired[0]["blue_left"], paired[0]["red_left"]) == (0, 0)
    assert len({run["fight_s"] for run in drawn}) > 1, "the first-round model no longer varies by seed, so the comparison is empty"


def test_one_extra_caster_wins_the_fight_with_more_than_half_its_wave_left():
    for mechanics in (Mechanics(), SLOTS):
        for seed in range(3):
            metrics, _ = scenarios.fight(red_casters=1)(scenarios.maker(mechanics), seed, 1.0)
            assert metrics["blue_left"] == 0
            assert metrics["red_left"] >= 4
