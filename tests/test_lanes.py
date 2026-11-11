import copy
import math
from dataclasses import replace

import pytest

from riftgame.lanes import (
    ACQUIRE,
    CALL_RANGE,
    HOLD_MARGIN,
    LANE_NAMES,
    M7_LANE,
    M8_LANE,
    MELEE_REACH,
    MINIONS,
    SPEED,
    STAND_OFF,
    TOWER_RANGE,
    TOWERS,
    ChampionDamage,
    ChampionInput,
    Kind,
    LaneSim,
    MinionDeath,
    MinionRemoved,
    Mode,
    Team,
    TowerDamage,
    TowerDestroyed,
    lane_geometry,
    stance,
    unit_stats,
    xp_share,
)

BLUE, RED = Team.BLUE, Team.RED
DT = 0.5
LATE = 300.0


def run(sim, until, policy=lambda sim: ()):
    events = []
    while sim.time < until - 1e-9:
        events += sim.step(sim.tick, policy(sim))
    return events


def of(events, kind):
    return [e for e in events if type(e) is kind]


def pusher(team):
    def policy(sim):
        s, in_path = stance(sim, team, Mode.PUSH)
        return [ChampionInput(int(team), team, s, Mode.PUSH, in_path)]

    return policy


def last_hitters(sim):
    return [ChampionInput(int(team), team, stance(sim, team, Mode.LAST_HIT)[0], Mode.LAST_HIT) for team in Team]


def quiet_lane(name="mid", rules=M8_LANE, start_s=LATE, seed=0):
    """A lane late enough that no wave spawned yet is on it, so a test places every minion itself."""
    sim = LaneSim(name, seed, DT, rules, start_s=start_s)
    sim.clock.next_wave = math.inf
    return sim


@pytest.mark.parametrize("name", LANE_NAMES)
def test_first_waves_meet_at_the_time_that_route_length_and_minion_speed_give(name):
    sim = LaneSim(name, 0, DT)
    geometry = sim.geometry
    while sim.front().s is None:
        sim.step(sim.tick)
    march = (abs(geometry.spawn[RED] - geometry.spawn[BLUE]) - ACQUIRE) / 2
    expected = MINIONS["first_spawn_s"] + march / SPEED
    assert expected <= sim.time <= expected + DT
    assert sim.front().s == pytest.approx(geometry.centre)


@pytest.mark.parametrize("name", ["mid", "top"])
def test_reflecting_the_lane_reflects_every_position(name):
    geometry = lane_geometry(name)
    left, right = LaneSim(name, 3, DT), LaneSim(name, 3, DT, geometry=geometry.mirrored())
    moved = False
    for _ in range(600):
        left.step(left.tick, pusher(BLUE)(left) if left.time > 100 else ())
        right.step(right.tick, pusher(BLUE)(right) if right.time > 100 else ())
        a, b = left.front(), right.front()
        assert a.counts == b.counts
        for lead_a, lead_b in zip(a.lead, b.lead):
            assert (lead_a is None) == (lead_b is None)
            assert lead_a is None or lead_b == pytest.approx(geometry.length - lead_a, abs=1e-6)
        moved = moved or (a.s is not None and abs(a.s - geometry.centre) > 500)
    assert moved, "the lane never left the centre, so the mirror is untested"


def test_every_spawned_minion_is_alive_dead_or_removed():
    sim = LaneSim("mid", 1, DT)
    for tower in sim.towers[RED]:
        tower.hp = 0.0
    events = run(sim, 300.0, pusher(BLUE))
    deaths, removed = of(events, MinionDeath), of(events, MinionRemoved)
    assert sim.spawned == 2 * (6 * 9 + 3)
    assert sim.spawned == sum(sim.front().counts) + len(deaths) + len(removed)
    assert (sim.dead, sim.removed) == (len(deaths), len(removed))
    assert len(deaths) > 50 and len(removed) > 5


def test_the_same_seed_gives_the_same_events_and_another_lane_draws_other_numbers():
    first, second = (run(LaneSim("top", 5, DT), 300.0, last_hitters) for _ in range(2))
    assert first == second and len(first) > 100
    untouched = run(LaneSim("top", 5, DT), 300.0)
    with_the_draws_of_bot = run(LaneSim("bot", 5, DT, geometry=lane_geometry("top")), 300.0)
    assert untouched != with_the_draws_of_bot, "the lane is not part of the key of a minion's tie-break draw"


def test_gold_goes_only_to_the_champion_that_lands_the_killing_blow():
    deaths = of(run(LaneSim("mid", 2, DT), 300.0, last_hitters), MinionDeath)
    mine = [e for e in deaths if e.killer is not None]
    assert len(mine) > 40 and len(mine) < len(deaths)
    assert all(e.gold == 0 for e in deaths if e.killer is None)
    assert all(e.gold == unit_stats(e.kind, 0.0)[2] or e.kind is Kind.SIEGE for e in mine)
    assert all(e.killer == 1 - e.team for e in mine)


def test_xp_for_a_minion_follows_the_reference_split():
    assert xp_share(62, 0) == 0
    assert xp_share(62, 1) == 62
    assert xp_share(62, 2) == pytest.approx(62 * 0.65)
    assert 2 * xp_share(62, 2) == pytest.approx(1.3 * 62)
    assert xp_share(62, 5) == pytest.approx(62 * 0.26)


def test_a_tower_shoots_siege_then_melee_then_caster_and_each_shot_takes_the_reference_share():
    sim = quiet_lane()
    edge = sim.geometry.towers[BLUE][0] + TOWER_RANGE
    for kind in (Kind.CASTER, Kind.MELEE, Kind.SIEGE):
        sim.add_minion(RED, kind, edge + 200.0)
    deaths = of(run(sim, LATE + 30.0), MinionDeath)
    assert [e.kind for e in deaths] == [Kind.SIEGE, Kind.MELEE, Kind.CASTER]
    shots = [math.ceil(1 / MINIONS[kind]["tower_shot_pct_max_hp"]) for kind in ("siege", "melee", "caster")]
    assert shots == [8, 3, 2]
    spacing = 1 / TOWERS["attack_speed"]
    for death, shot in zip(deaths, (8, 11, 13)):
        assert death.t - deaths[0].t == pytest.approx((shot - 8) * spacing, abs=DT)
    assert all(e.killer is None and e.gold == 0 for e in deaths)


def test_minion_blows_on_a_tower_carry_the_reference_multipliers():
    sim = quiet_lane()
    target = sim.geometry.towers[RED][0]
    sim.add_minion(BLUE, Kind.MELEE, target - 300.0)
    sim.add_minion(BLUE, Kind.SIEGE, target - 300.0)
    blows = {round(e.damage, 3) for e in of(run(sim, LATE + 3.0), TowerDamage)}
    melee, siege = unit_stats(Kind.MELEE, LATE)[1], unit_stats(Kind.SIEGE, LATE)[1]
    assert blows == {round(melee * 0.60, 3), round(siege * 0.84, 3)}


def test_only_the_front_tower_fights_and_a_fallen_one_lets_the_wave_march_on():
    sim = quiet_lane()
    outer_s, inner_s = sim.geometry.towers[RED][0], sim.geometry.towers[RED][1]
    sim.add_minion(BLUE, Kind.MELEE, outer_s - 400.0, count=3)
    run(sim, LATE + 2.0)
    assert sim.tower_alive(RED, "outer") and sim.towers[RED][0].hp < TOWERS["outer"]["hp"]
    assert sim.towers[RED][1].hp == TOWERS["inner"]["hp"]
    assert all(m.s <= outer_s - MELEE_REACH + 1e-6 for m in sim.minions[BLUE])
    sim.towers[RED][0].hp = 1.0
    sim.add_minion(BLUE, Kind.MELEE, outer_s - 400.0, count=3)
    events = run(sim, LATE + 20.0)
    assert [(e.team, e.tier) for e in of(events, TowerDestroyed)] == [(RED, 0)]
    assert not sim.tower_alive(RED, "outer") and sim.tower_alive(RED, "inner")
    assert any(e.tier == 1 for e in of(events, TowerDamage)) or all(m.s > outer_s for m in sim.minions[BLUE])
    run(sim, LATE + 40.0)
    assert sim.towers[RED][1].hp < TOWERS["inner"]["hp"] or not sim.minions[BLUE]
    assert all(m.s <= inner_s for m in sim.minions[BLUE])


def test_a_wave_past_the_last_lane_tower_is_removed_at_the_enemy_base():
    sim = quiet_lane()
    for tower in sim.towers[RED]:
        tower.hp = 0.0
    sim.add_minion(BLUE, Kind.MELEE, sim.geometry.spawn[RED] - 1000.0, count=3)
    removed = of(run(sim, LATE + 10.0), MinionRemoved)
    assert len(removed) == 3 and not sim.minions[BLUE] and sim.removed == 3


def seconds_from_spawn_to_centre(name, rules, wave):
    sim = LaneSim(name, 0, DT, rules)
    while True:
        sim.step(sim.tick)
        sim.minions[RED].clear()
        if any(m.wave == wave and m.s >= sim.geometry.centre for m in sim.minions[BLUE]):
            return sim.time - 30.0 * wave


def test_side_lane_minions_of_the_second_wave_are_faster_and_mid_lane_minions_are_not():
    assert seconds_from_spawn_to_centre("mid", M8_LANE, 2) == seconds_from_spawn_to_centre("mid", M8_LANE, 1)
    first, second = (seconds_from_spawn_to_centre("top", M8_LANE, wave) for wave in (1, 2))
    assert 5.0 <= first - second <= 8.0
    assert seconds_from_spawn_to_centre("top", M7_LANE, 2) == first
    third = seconds_from_spawn_to_centre("top", M8_LANE, 3)
    assert second <= third < first


def one_exchange(level_lead, start_s=LATE, fallen_red_towers=0):
    sim = quiet_lane(start_s=start_s)
    for tower in sim.towers[RED][:fallen_red_towers]:
        tower.hp = 0.0
    centre = sim.geometry.centre
    sim.add_minion(BLUE, Kind.MELEE, centre - MELEE_REACH / 2)
    sim.add_minion(RED, Kind.MELEE, centre + MELEE_REACH / 2)
    hp, ad, _ = unit_stats(Kind.MELEE, start_s)
    sim.step(sim.tick, (), level_lead)
    blow = ad + 0.02 * hp
    return (hp - sim.minions[RED][0].hp) / blow, blow - (hp - sim.minions[BLUE][0].hp)


def test_the_pushing_advantage_follows_the_reference_formula_and_starts_at_210_seconds():
    assert one_exchange(0.0) == pytest.approx((1.0, 0.0))
    assert one_exchange(2.0, start_s=150.0) == pytest.approx((1.0, 0.0))
    assert one_exchange(2.0) == pytest.approx((1.10, 1.0))
    assert one_exchange(0.5) == pytest.approx((1.025, 1.0))
    assert one_exchange(5.0) == pytest.approx((1.15, 1.0))
    assert one_exchange(2.0, fallen_red_towers=1) == pytest.approx((1.20, 3.0))
    dealt, reduced = one_exchange(-2.0)
    assert dealt == pytest.approx(1.0 - 1.0 / (unit_stats(Kind.MELEE, LATE)[1] + 0.02 * unit_stats(Kind.MELEE, LATE)[0]))
    assert reduced == pytest.approx(-0.10 * (unit_stats(Kind.MELEE, LATE)[1] + 0.02 * unit_stats(Kind.MELEE, LATE)[0]))


def test_the_pushing_advantage_can_be_switched_off():
    rules = replace(M8_LANE, pushing_advantage=False)
    sim = quiet_lane(rules=rules)
    centre = sim.geometry.centre
    sim.add_minion(BLUE, Kind.MELEE, centre - 55.0)
    sim.add_minion(RED, Kind.MELEE, centre + 55.0)
    sim.step(sim.tick, (), 3.0)
    assert sim.minions[BLUE][0].hp == sim.minions[RED][0].hp


def harassed(rules, harassing, distance=400.0):
    sim = quiet_lane(rules=rules)
    centre = sim.geometry.centre
    sim.add_minion(BLUE, Kind.MELEE, centre - 55.0)
    sim.add_minion(RED, Kind.MELEE, centre + 55.0)
    champion = ChampionInput(0, BLUE, centre + 55.0 - distance, Mode.PASSIVE, in_path=False, harassing=harassing)
    return of(run(sim, LATE + 4.0, lambda sim: [champion]), ChampionDamage)


def test_minions_answer_a_call_for_help_within_its_range_and_only_then():
    assert harassed(M8_LANE, harassing=False) == []
    bites = harassed(M8_LANE, harassing=True)
    assert bites and all(e.seat == 0 for e in bites)
    assert bites[0].damage == pytest.approx(unit_stats(Kind.MELEE, LATE)[1] * 0.60)
    assert harassed(M8_LANE, harassing=True, distance=CALL_RANGE + 50.0) == []
    assert harassed(replace(M8_LANE, call_for_help=False), harassing=True) == []


def test_a_minion_that_attacks_a_tower_ignores_a_call_for_help():
    sim = quiet_lane()
    tower = sim.geometry.towers[BLUE][0]
    sim.add_minion(RED, Kind.MELEE, tower + 300.0)
    champion = ChampionInput(0, BLUE, tower + 250.0, Mode.PASSIVE, in_path=False, harassing=True)
    run(sim, LATE + 2.0)
    events = run(sim, LATE + 6.0, lambda sim: [champion])
    assert of(events, TowerDamage) and not of(events, ChampionDamage)


def lone_red_wave(mode, in_path, attack_range=550.0, health=None):
    sim = quiet_lane()
    centre = sim.geometry.centre
    sim.add_minion(RED, Kind.MELEE, centre + 400.0, count=3)
    for m in sim.minions[RED]:
        m.hp = m.hp if health is None else health
    champion = ChampionInput(0, BLUE, centre, mode, in_path, attack_range=attack_range)
    events = run(sim, LATE + 20.0, lambda sim: [champion])
    return events, sim


def test_minions_attack_a_champion_in_their_path_and_ignore_one_that_stepped_aside():
    events, sim = lone_red_wave(Mode.HOLD, in_path=True)
    assert of(events, ChampionDamage)
    assert all(m.s >= sim.geometry.centre + MELEE_REACH - 1e-6 for m in sim.minions[RED]), "the wave walked through the champion"
    events, sim = lone_red_wave(Mode.LAST_HIT, in_path=False)
    assert not of(events, ChampionDamage)
    assert all(m.s < sim.geometry.centre - 1000.0 for m in sim.minions[RED])


def test_a_champion_that_stepped_aside_kills_nothing_and_one_that_pushes_in_the_path_pays_for_it():
    events, _ = lone_red_wave(Mode.PUSH, in_path=False, health=1.0)
    assert len(of(events, MinionDeath)) == 3 and all(e.killer is None for e in of(events, MinionDeath))
    events, _ = lone_red_wave(Mode.PUSH, in_path=True)
    assert [e.killer for e in of(events, MinionDeath)] == [0, 0, 0] and of(events, ChampionDamage)


def test_minions_leave_a_champion_for_its_wave_when_the_wave_comes_into_range():
    sim = quiet_lane()
    centre = sim.geometry.centre
    sim.add_minion(RED, Kind.CASTER, centre + 300.0, count=3)
    champion = ChampionInput(0, BLUE, centre, Mode.HOLD)
    before = of(run(sim, LATE + 4.0, lambda sim: [champion]), ChampionDamage)
    sim.add_minion(BLUE, Kind.MELEE, centre - 150.0, count=3)
    after = of(run(sim, LATE + 10.0, lambda sim: [champion]), ChampionDamage)
    assert before and all(e.t <= LATE + 4.0 + 1 / 0.667 + DT for e in after)


def support_hit(execute_below, health_share):
    sim = quiet_lane()
    centre = sim.geometry.centre
    sim.add_minion(RED, Kind.MELEE, centre + 200.0)
    sim.minions[RED][0].hp = health_share * sim.minions[RED][0].max_hp
    support = ChampionInput(4, BLUE, centre, Mode.LAST_HIT, hit_damage=50.0, execute_below=execute_below)
    return of(sim.step(sim.tick, [support]), MinionDeath)


def test_a_support_charge_executes_a_low_minion_and_marks_the_kill_as_shared():
    assert support_hit(0.0, 0.45) == []
    assert support_hit(0.5, 0.55) == []
    [death] = support_hit(0.5, 0.45)
    assert (death.killer, death.shared, death.gold) == (4, True, unit_stats(Kind.MELEE, LATE)[2])
    [death] = support_hit(0.0, 0.05)
    assert (death.killer, death.shared) == (4, False)


def test_the_stance_of_each_wave_mode_follows_the_mode_table():
    sim = quiet_lane("top")
    geometry = sim.geometry
    centre, blue_tower = geometry.centre, geometry.towers[BLUE][0]
    sim.add_minion(RED, Kind.MELEE, centre + 55.0, count=3)
    lone = {mode: stance(sim, BLUE, mode, attack_range=175.0) for mode in Mode}
    for mode in (Mode.PASSIVE, Mode.LAST_HIT, Mode.THIN):
        assert lone[mode] == (pytest.approx(centre + 55.0 - STAND_OFF), False)
    assert lone[Mode.PUSH] == (pytest.approx(centre + 55.0 - 175.0), True)
    assert lone[Mode.HOLD] == (pytest.approx(blue_tower + TOWER_RANGE + HOLD_MARGIN - MELEE_REACH), True)
    sim.add_minion(BLUE, Kind.MELEE, centre - 55.0, count=3)
    for mode in Mode:
        assert stance(sim, BLUE, mode) == (pytest.approx(centre + 55.0 - MELEE_REACH), True)
    sim.minions[BLUE].clear()
    sim.minions[RED].clear()
    sim.add_minion(RED, Kind.MELEE, geometry.towers[RED][0] - 100.0)
    assert stance(sim, BLUE, Mode.PUSH)[0] == pytest.approx(geometry.towers[RED][0] - TOWER_RANGE - 50.0)


def test_a_copied_lane_replays_tick_for_tick_and_its_values_change_with_any_minion():
    sim = LaneSim("bot", 4, DT)
    run(sim, 200.0, last_hitters)
    twin = copy.deepcopy(sim)
    assert twin.values() == sim.values()
    for _ in range(400):
        assert sim.step(sim.tick, last_hitters(sim)) == twin.step(twin.tick, last_hitters(twin))
        assert sim.values() == twin.values()
    twin.minions[BLUE][0].hp -= 1.0
    assert sim.values() != twin.values()
    hash(sim.values())


def retarget_after_a_kill(rules):
    """Two red melee minions strike one target that dies to the first blow, with a champion in reach and a second blue minion 300 units away."""
    sim = quiet_lane(rules=rules)
    centre = sim.geometry.centre
    sim.add_minion(RED, Kind.MELEE, centre, count=2)
    sim.add_minion(BLUE, Kind.CASTER, centre - 100.0)
    sim.add_minion(BLUE, Kind.CASTER, centre - 400.0)
    sim.minions[BLUE][0].hp = 1.0
    champion = ChampionInput(0, BLUE, centre - 60.0, Mode.LAST_HIT)
    events = []
    for _ in range(3):
        events += sim.step(sim.tick, [champion])
    return of(events, ChampionDamage)


def test_a_minion_whose_target_dies_keeps_the_priority_of_minions_over_a_champion_in_its_reach():
    assert retarget_after_a_kill(M8_LANE) == []
    assert retarget_after_a_kill(M7_LANE) != [], "the case does not reach the retarget that M7's lane resolved differently"


def kills_of_two_equal_laners(order, seed=0):
    sim = LaneSim("bot", seed, DT)

    def pair(sim):
        s = stance(sim, BLUE, Mode.LAST_HIT)[0]
        return [ChampionInput(seat, BLUE, s, Mode.LAST_HIT) for seat in order]

    deaths = of(run(sim, 600.0, pair), MinionDeath)
    return {seat: sum(e.killer == seat for e in deaths) for seat in (3, 4)}, sim.values()


def test_two_equal_laners_share_contested_last_hits_and_the_order_of_the_inputs_changes_nothing():
    kills, values = kills_of_two_equal_laners((3, 4))
    assert (kills, values) == kills_of_two_equal_laners((4, 3))
    assert min(kills.values()) > 0.6 * max(kills.values())


def test_a_champion_that_comes_back_to_a_lane_has_its_attack_ready():
    sim = quiet_lane()
    centre = sim.geometry.centre
    sim.add_minion(RED, Kind.MELEE, centre + 300.0, count=2)
    for m in sim.minions[RED]:
        m.hp = 1.0
    champion = ChampionInput(0, BLUE, centre, Mode.LAST_HIT, in_path=True)
    assert len(of(sim.step(sim.tick, [champion]), MinionDeath)) == 1
    sim.step(sim.tick, [])
    assert len(of(sim.step(sim.tick, [champion]), MinionDeath)) == 1


def test_the_m7_rule_set_is_the_m8_lane_without_the_three_rules_m7_left_out_and_with_m7s_resolution():
    assert replace(M8_LANE, side_lane_speed=False, call_for_help=False, pushing_advantage=False, m7_resolution=True) == M7_LANE
    assert (M8_LANE.melee_cap, M8_LANE.minion_damage_scale, M8_LANE.current_hp_damage) == (0, 1.0, True)
