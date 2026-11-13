import copy
import math
from dataclasses import replace

import pytest

from riftgame import champions
from riftgame.lanes import (
    ACQUIRE,
    ADDED,
    AreaSpent,
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
    Minion,
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
from riftgame.map import REFERENCE_MAP, load_map

BLUE, RED = Team.BLUE, Team.RED
# Reference rows A4b and A4c: the game's minion path through each side-lane corner, from one outer tower's node to
# the other's, with the four waypoints between them.
TOP_CORNER = ((1285, 10423), (1508, 11601), (1968, 12459), (2720, 13100), (3486, 13473), (4359, 13597))
BOT_CORNER = ((10506, 1301), (11432, 1472), (12294, 1913), (13001, 2628), (13529, 3694), (13751, 4790))
MINIONS_M8 = ADDED["minions"]
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
    events, sim = lone_red_wave(Mode.LAST_HIT, in_path=True)
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
    champion = ChampionInput(0, BLUE, centre, Mode.LAST_HIT)
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


def test_the_stance_follows_the_mode_table_and_a_hold_stands_on_the_hold_line_whatever_the_champion_hits():
    sim = quiet_lane("top")
    geometry = sim.geometry
    centre, blue_tower = geometry.centre, geometry.towers[BLUE][0]
    sim.add_minion(RED, Kind.MELEE, centre + 55.0, count=3)
    lone = {mode: stance(sim, BLUE, mode, attack_range=175.0) for mode in Mode}
    for mode in (Mode.PASSIVE, Mode.LAST_HIT, Mode.THIN):
        assert lone[mode] == (pytest.approx(centre + 55.0 - STAND_OFF), False)
    assert lone[Mode.PUSH] == (pytest.approx(centre + 55.0 - 175.0), True)
    for mode in Mode:
        assert stance(sim, BLUE, mode, attack_range=175.0, hold=True) == (pytest.approx(blue_tower + TOWER_RANGE + HOLD_MARGIN - MELEE_REACH), True)
    sim.add_minion(BLUE, Kind.MELEE, centre - 55.0, count=3)
    for mode in Mode:
        for hold in (False, True):
            assert stance(sim, BLUE, mode, hold=hold) == (pytest.approx(centre + 55.0 - MELEE_REACH), True)
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
    champion = ChampionInput(0, BLUE, centre - 100.0, Mode.LAST_HIT)
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


def test_the_m7_rule_set_is_the_m8_lane_without_the_rules_m7_left_out_and_with_m7s_resolution():
    assert replace(M8_LANE, side_lane_speed=False, call_for_help=False, pushing_advantage=False, straight_ranges=False, tower_shelter=False,
                   first_wave_call=False, attack_timing=False, m7_map=True, m7_resolution=True, tower_blocks=False) == M7_LANE
    assert (M8_LANE.melee_cap, M8_LANE.minion_damage_scale, M8_LANE.current_hp_damage) == (0, 1.0, True)


def bend(geometry, xy):
    """The lane coordinate of the lane node at map coordinates `xy`."""
    return next(s for s, x, y in geometry.bends if (x, y) == xy)


def toward(start, end, units):
    """The map point `units` from `start` on the straight line to `end`."""
    share = units / math.dist(start, end)
    return start[0] + (end[0] - start[0]) * share, start[1] + (end[1] - start[1]) * share


def test_a_range_inside_the_lane_is_the_straight_line_on_the_map_and_marching_stays_on_the_lane():
    """The span runs from 200 units before the first waypoint of top lane's corner to 200 units after the third.
    It crosses three bends, which the straight line cuts short by 77 units."""
    top = lane_geometry("top")
    tower, first, second, third, fourth = TOP_CORNER[:5]
    before, after = bend(top, first) - 200.0, bend(top, third) + 200.0
    walk = 200.0 + math.dist(first, second) + math.dist(second, third) + 200.0
    straight = math.dist(toward(first, tower, 200.0), toward(third, fourth, 200.0))
    assert after - before == pytest.approx(walk) and top.gap(before, after) == pytest.approx(straight)
    assert walk - straight == pytest.approx(76.7, abs=0.1)
    assert top.gap(before - 400.0, before) == pytest.approx(400.0)
    mid = lane_geometry("mid")
    assert mid.gap(mid.centre - 300.0, mid.centre) == pytest.approx(300.0)
    marched = after - SPEED * DT
    reach = (top.gap(before, marched) + marched - before) / 2
    assert top.gap(before, marched) < reach - 5.0 and reach + 5.0 < marched - before
    for rules, in_range in ((M8_LANE, True), (replace(M8_LANE, straight_ranges=False), False)):
        sim = quiet_lane("top", rules)
        sim.add_minion(RED, Kind.MELEE, after)
        sim.minions[RED][0].hp = 1.0
        champion = ChampionInput(0, BLUE, before, Mode.LAST_HIT, attack_range=reach)
        deaths = of(sim.step(sim.tick, [champion]), MinionDeath)
        assert bool(deaths) is in_range
        assert sim.minions[RED] == [] or sim.minions[RED][0].s == pytest.approx(marched)


def test_minions_on_two_sides_of_a_bend_acquire_each_other_by_the_straight_line():
    """The sharpest bend of top lane turns 21 degrees. Two minions 253 units on each side of it are 506 units
    apart along the lane and 497 in a straight line."""
    top = lane_geometry("top")
    _, first, second, third = TOP_CORNER[:4]
    corner, half = bend(top, second), 253.0
    gap = top.gap(corner - half, corner + half)
    assert gap == pytest.approx(math.dist(toward(second, first, half), toward(second, third, half)))
    assert gap + 2.0 < ACQUIRE < 2 * half - 2.0
    for rules, engaged in ((M8_LANE, True), (replace(M8_LANE, straight_ranges=False), False)):
        sim = quiet_lane("top", rules)
        sim.add_minion(BLUE, Kind.CASTER, corner - half)
        sim.add_minion(RED, Kind.CASTER, corner + half)
        sim.step(sim.tick)
        blue, red = sim.minions[BLUE][0], sim.minions[RED][0]
        assert (blue.target is red) is engaged
        closed = 0.0 if engaged else (2 * half - ACQUIRE) / 2
        assert (blue.s, red.s) == (pytest.approx(corner - half + closed), pytest.approx(corner + half - closed)), "minions in reach stand still"


def tanked(rules, from_tower, harassing=False, wave=0, fallen=False):
    """Blows on a blue champion that stands in the path `from_tower` units outside its own outer tower."""
    sim = quiet_lane(rules=rules)
    tower = sim.geometry.towers[BLUE][0]
    sim.towers[BLUE][0].hp *= not fallen
    sim.add_minion(RED, Kind.CASTER, tower + from_tower + 450.0, count=3, wave=wave)
    champion = ChampionInput(0, BLUE, tower + from_tower, Mode.LAST_HIT, in_path=True, harassing=harassing)
    return of(run(sim, LATE + 6.0, lambda sim: [champion]), ChampionDamage)


def test_a_champion_inside_a_towers_range_is_not_attacked_for_standing_in_the_path():
    assert tanked(M8_LANE, TOWER_RANGE + 100.0)
    assert tanked(M8_LANE, TOWER_RANGE - 100.0) == []
    assert tanked(replace(M8_LANE, tower_shelter=False), TOWER_RANGE - 100.0)
    assert tanked(M8_LANE, TOWER_RANGE - 100.0, harassing=True), "a call for help reaches a champion under its tower"
    assert tanked(M8_LANE, TOWER_RANGE - 100.0, fallen=True), "a fallen tower shelters nobody"


def test_only_minions_of_the_first_wave_answer_a_call_for_help_while_they_attack_a_tower():
    def called(rules, wave):
        sim = quiet_lane(rules=rules)
        tower = sim.geometry.towers[BLUE][0]
        sim.add_minion(RED, Kind.MELEE, tower + 300.0, wave=wave)
        champion = ChampionInput(0, BLUE, tower + 250.0, Mode.PASSIVE, in_path=False, harassing=True)
        run(sim, LATE + 2.0)
        return of(run(sim, LATE + 6.0, lambda sim: [champion]), ChampionDamage)

    assert called(M8_LANE, wave=1) and called(M8_LANE, wave=2) == []
    assert called(replace(M8_LANE, first_wave_call=False), wave=1) == []


def test_a_champion_on_the_hold_line_hits_what_its_mode_says():
    def held(mode):
        sim = quiet_lane()
        tower = sim.geometry.towers[BLUE][0]
        sim.add_minion(RED, Kind.MELEE, tower + TOWER_RANGE + 700.0, count=3)
        sim.add_minion(RED, Kind.CASTER, tower + TOWER_RANGE + 900.0, count=3)

        deepest = []

        def policy(sim):
            deepest.append(min(m.s for m in sim.minions[RED]) if sim.minions[RED] else math.inf)
            s, in_path = stance(sim, BLUE, mode, hold=True)
            return [ChampionInput(0, BLUE, s, mode, in_path)]

        events = run(sim, LATE + 12.0, policy)
        deaths = of(events, MinionDeath)
        return {e.kind for e in deaths if e.killer == 0}, bool(of(events, ChampionDamage)), min(deepest) - tower - TOWER_RANGE

    for mode in Mode:
        killed, bitten, margin = held(mode)
        assert bitten and margin >= HOLD_MARGIN - 1e-6, f"{mode.name} on the hold line keeps the wave {HOLD_MARGIN} outside the tower's range"
        if mode is Mode.PASSIVE or mode is Mode.LAST_HIT:
            assert killed == set()
        if mode is Mode.THIN:
            assert killed == {Kind.CASTER}
        if mode is Mode.PUSH:
            assert Kind.MELEE in killed


INSTANT = replace(M8_LANE, attack_timing=False)
TIMING = {kind: MINIONS_M8["attack_timing"][kind.name.lower()] for kind in Kind}


def blows_on_a_champion(rules, kind, gap, seconds=30.0):
    """Times, from the first tick, at which a lone red minion `gap` units from a blue champion in its path hits it."""
    sim = quiet_lane(rules=rules)
    centre = sim.geometry.centre
    sim.add_minion(RED, kind, centre + gap)
    champion = ChampionInput(0, BLUE, centre, Mode.PASSIVE, in_path=True)
    return [e.t - LATE for e in of(run(sim, LATE + seconds, lambda sim: [champion]), ChampionDamage)]


@pytest.mark.parametrize("kind, gap", [(Kind.MELEE, 100.0), (Kind.CASTER, 500.0), (Kind.SIEGE, 290.0)])
def test_a_blow_leaves_the_minion_one_cast_time_after_the_attack_starts_and_a_missile_then_flies(kind, gap):
    timing, period = TIMING[kind], 1.0 / MINIONS[kind.name.lower()]["attack_speed"]
    flight = gap / timing["missile_speed"] if "missile_speed" in timing else 0.0
    timed, instant = blows_on_a_champion(M8_LANE, kind, gap), blows_on_a_champion(INSTANT, kind, gap)
    assert instant[0] == 0.0
    assert timed[0] == pytest.approx(timing["cast_s"] + flight)
    assert [b - a for a, b in zip(timed, timed[1:])] == pytest.approx([period] * (len(timed) - 1)), "the cadence is the attack speed"
    assert len(instant) - len(timed) in (0, 1)


def fine_lane():
    """A quiet lane on a 0.1 s tick, fine enough to tell a cast time from a missile flight."""
    sim = LaneSim("mid", 0, 0.1, M8_LANE, start_s=LATE)
    sim.clock.next_wave = math.inf
    return sim


def first_hurt(sim, minion, limit=5.0):
    """Seconds from the lane's start until `minion` first loses health."""
    health = minion.hp
    while minion.hp == health and sim.time < LATE + limit:
        sim.step(sim.tick)
    return sim.time - LATE


def test_a_cast_whose_target_dies_starts_again_and_costs_only_the_time_spent_on_the_dead_target():
    cast, period = TIMING[Kind.MELEE]["cast_s"], 1.0 / MINIONS["melee"]["attack_speed"]

    def second_target_hurt(killed_at):
        sim = fine_lane()
        centre = sim.geometry.centre
        sim.add_minion(BLUE, Kind.MELEE, centre - 50.0)
        sim.add_minion(RED, Kind.MELEE, centre + 50.0)
        sim.add_minion(RED, Kind.MELEE, centre + 60.0)
        near, far = sim.minions[RED]
        while sim.time < LATE + killed_at - 1e-9:
            sim.step(sim.tick)
        assert far.hp == far.max_hp, "the blue minion hits the nearer target first"
        near.hp, near.died_at = 0.0, sim.time
        return first_hurt(sim, far), sim.cancelled

    # the blue minion's second cast runs from 0.8 s to 1.193 s
    hurt, cancelled = second_target_hurt(killed_at=1.0)
    assert cancelled == 1 and hurt == pytest.approx(1.0 + cast, abs=0.1 + 1e-9), "the cast starts again when the target dies"
    hurt, cancelled = second_target_hurt(killed_at=0.5)
    assert cancelled == 0 and hurt == pytest.approx(period + cast, abs=0.1 + 1e-9), "a target that dies between casts costs nothing"


def test_a_missile_whose_target_dies_in_flight_is_lost():
    sim = fine_lane()
    centre = sim.geometry.centre
    sim.add_minion(BLUE, Kind.CASTER, centre - 250.0)
    sim.add_minion(RED, Kind.CASTER, centre + 250.0, count=2)
    while not sim._missiles and sim.time < LATE + 5.0:
        sim.step(sim.tick)
    blue = [missile for missile in sim._missiles if missile[3] == BLUE]
    assert len(blue) == 1 and len(sim.values()[-1]) == len(sim._missiles), "a missile in flight is part of the lane's state"
    victim = blue[0][-1]
    other = next(m for m in sim.minions[RED] if m is not victim)
    victim.hp, victim.died_at = 0.0, sim.time
    run(sim, sim.time + 500.0 / TIMING[Kind.CASTER]["missile_speed"] + 0.1)
    assert sim.lost == 1 and other.hp == other.max_hp, "the missile does not turn to another target"


def test_two_equal_minions_still_kill_each_other_in_the_same_instant():
    sim = quiet_lane()
    centre = sim.geometry.centre
    sim.add_minion(BLUE, Kind.MELEE, centre - 50.0)
    sim.add_minion(RED, Kind.MELEE, centre + 50.0)
    events = of(run(sim, LATE + 120.0), MinionDeath)
    assert len(events) == 2 and events[0].t == events[1].t


def dead_targets(sim):
    """The dead minions that a cast or a missile in flight still points at."""
    casts = [m.swing_at for team in Team for m in sim.minions[team] if type(m.swing_at) is Minion and m.swing_at.hp <= 0]
    flights = [missile[-1] for missile in sim._missiles if type(missile[-1]) is Minion and missile[-1].hp <= 0]
    return casts, flights


def health(sim):
    return [(m.uid, m.hp) for team in Team for m in sim.minions[team]]


def test_the_lanes_values_hold_when_the_dead_target_of_a_pending_cast_died_and_that_time_changes_what_follows():
    """A minion that dies leaves the lane's lists at the end of its tick. A cast that still points at it is
    cancelled on a later tick, and the cast that replaces it starts from the moment the target died."""
    sim = LaneSim("mid", 0, DT)
    cast_states, flight_states, diverged = 0, 0, 0
    while sim.time < 130.0:
        sim.step(sim.tick)
        casts, flights = dead_targets(sim)
        cast_states += bool(casts)
        flight_states += bool(flights)
        for kind in range(2):
            if not dead_targets(sim)[kind]:
                continue
            twin = copy.deepcopy(sim)
            assert twin.values() == sim.values()
            target = dead_targets(twin)[kind][0]
            assert all(m is not target for team in Team for m in twin.minions[team]), "the dead minion is in no list of the lane"
            target.died_at -= 0.1
            assert twin.values() != sim.values(), f"tick {sim.tick}"
            if kind == 0:
                ahead = copy.deepcopy(sim)
                for _ in range(6):
                    ahead.step(ahead.tick)
                    twin.step(twin.tick)
                    if health(ahead) != health(twin):
                        diverged += 1
                        break
    assert cast_states >= 1 and flight_states >= 1, "the run must reach a cast and a missile that point at a dead minion"
    assert diverged >= 1, "the time of death decides when the next blow lands, so the lane's values must hold it"


def test_the_lanes_values_hold_how_long_a_placed_minion_still_waits():
    one, other = quiet_lane(), quiet_lane()
    one.add_minion(RED, Kind.MELEE, one.geometry.centre, delay=0.2)
    other.add_minion(RED, Kind.MELEE, other.geometry.centre, delay=0.3)
    assert one.values() != other.values()


def turns(geometry) -> list[float]:
    """The angle in degrees by which the lane turns at each of its nodes from one outer tower to the other. An
    outer tower stands up to 256 units from the lane node that is named after it."""
    low, high = geometry.towers[BLUE][0] - 300.0, geometry.towers[RED][0] + 300.0
    angles = []
    for (_, x0, y0), (s, x1, y1), (_, x2, y2) in zip(geometry.bends, geometry.bends[1:], geometry.bends[2:]):
        if low <= s <= high:
            turn = math.atan2(y2 - y1, x2 - x1) - math.atan2(y1 - y0, x1 - x0)
            angles.append(abs(math.degrees((turn + math.pi) % (2 * math.pi) - math.pi)))
    return angles


def path(points) -> float:
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


@pytest.mark.parametrize("name, corner, cut", [("top", TOP_CORNER, 98.0), ("bot", BOT_CORNER, 109.0)])
def test_the_m8_map_traces_a_side_lane_corner_with_the_games_four_waypoints_and_m7s_map_with_one_of_them(name, corner, cut):
    m8, m7 = lane_geometry(name), lane_geometry(name, REFERENCE_MAP)
    assert m8 == lane_geometry(name, "map_summoners_rift_m8")
    nodes = [(x, y) for _, x, y in m8.bends]
    first = nodes.index(corner[0])
    assert tuple(nodes[first:first + 6]) == corner
    old = [(x, y) for _, x, y in m7.bends]
    first = old.index(corner[0])
    assert tuple(old[first:first + 3]) == (corner[0], corner[2], corner[5]), "M7's map keeps the second waypoint alone"
    assert path(corner) - path((corner[0], corner[2], corner[5])) == pytest.approx(cut, abs=1.0)
    assert m8.length - m7.length == pytest.approx(path(corner) - path((corner[0], corner[2], corner[5])))
    assert len(m8.bends) == len(m7.bends) + 3 and m8.bends[:first + 1] == m7.bends[:first + 1], "nothing before the corner moved"


def test_no_bend_between_the_outer_towers_of_an_m8_lane_turns_more_than_25_degrees():
    for name in LANE_NAMES:
        angles = turns(lane_geometry(name))
        assert angles and max(angles) <= 25.0, name
    assert len(turns(lane_geometry("top"))) == len(turns(lane_geometry("bot"))) == 6, "two tower nodes and four waypoints"
    for name in ("top", "bot"):
        assert max(turns(lane_geometry(name, REFERENCE_MAP))) > 40.0, "M7's single corner node turns more, so the measure can tell"


M7_LENGTH = {"top": 22483.0, "mid": 16502.0, "bot": 22581.0}
M8_LENGTH = {"top": 22581.0, "mid": 16502.0, "bot": 22690.0}


@pytest.mark.parametrize("name", LANE_NAMES)
def test_the_m7_lane_runs_on_m7s_lane_and_the_m8_lane_on_the_m8_maps(name):
    m7, m8 = LaneSim(name, 0, DT, M7_LANE), LaneSim(name, 0, DT, M8_LANE)
    assert m7.length == pytest.approx(M7_LENGTH[name], abs=1.0) and m8.length == pytest.approx(M8_LENGTH[name], abs=1.0)
    assert m7.geometry == lane_geometry(name, REFERENCE_MAP) and m8.geometry == lane_geometry(name)
    assert m7.length == pytest.approx(load_map().rift.lanes[name].length), "the M7 map file's lane"
    assert m8.length == pytest.approx(champions.RIFT.lanes[name].length), "the lane of the map that the M8 world runs on"
    assert LaneSim(name, 0, DT).rules == M8_LANE and not M8_LANE.m7_map and M7_LANE.m7_map


@pytest.mark.parametrize("name, reference_units", [("top", 10184), ("mid", 8095), ("bot", 10333)])
def test_the_walk_from_the_fountain_to_the_outer_tower_on_the_m8_map_matches_the_reference_as_on_m7s_map(name, reference_units):
    """The reference walks are those of tests/test_map.py. The outer towers stand before the corners, so the added
    waypoints change none of them."""
    for data in (champions.MAP, load_map()):
        site = next(t for t in data.towers if t.name == f"blue_{name}_outer")
        walk = data.rift.distance(data.rift.at("blue_fountain"), data.rift.lane_pos(name, site.s))
        assert walk == pytest.approx(reference_units, rel=0.04)
    assert champions.MAP.rift is champions.RIFT and champions.MAP is not load_map()


@pytest.mark.parametrize("team", [BLUE, RED])
@pytest.mark.parametrize("rules, standing, passes", [(M8_LANE, True, False), (M8_LANE, False, True), (replace(M8_LANE, tower_blocks=False), True, True)],
                         ids=["M8, tower standing", "M8, tower fallen", "without the rule"])
def test_a_minion_that_chases_an_enemy_minion_behind_the_enemy_front_tower_stops_at_the_tower_while_it_stands(team, rules, standing, passes):
    """A melee minion 300 units before the enemy outer tower targets an enemy caster 200 units behind it, which
    waits where it was put. While the tower stands the melee minion walks up to the tower's lane coordinate and no
    further. Once the tower is down it walks on into its reach of the caster."""
    sim = quiet_lane(rules=rules)
    tower, ahead = sim.towers[1 - team][0], sim.geometry.direction(team)
    if not standing:
        tower.hp = 0.0
    sim.add_minion(team, Kind.MELEE, tower.s - ahead * 300.0)
    sim.add_minion(1 - team, Kind.CASTER, tower.s + ahead * 200.0, delay=30.0)
    walker, quarry = sim.minions[team][0], sim.minions[1 - team][0]
    beyond = []
    for _ in range(3):
        sim.step(sim.tick)
        assert walker.target is quarry, "it walks to the caster, not to the tower"
        beyond.append(ahead * (walker.s - tower.s))
    if passes:
        assert beyond[-1] > 0.0 and walker.s == pytest.approx(quarry.s - ahead * MELEE_REACH)
    else:
        assert beyond[0] < 0.0 and beyond[1:] == [0.0, 0.0]


@pytest.mark.parametrize("bound, minions, seconds", [(math.inf, True, DT), (0.2, True, 0.2), (0.0, True, 0.0), (math.inf, False, 0.0)])
def test_a_push_runs_its_area_damage_only_while_it_hits_a_minion_and_for_no_more_seconds_than_its_mana_pays_for(bound, minions, seconds):
    """A pusher with no attack ready for ten seconds, so that its only damage is the area's, and two enemy minions in its range
    that wait where they were put. Each loses the area's damage per second times the seconds the lane reports."""
    sim = quiet_lane()
    centre = sim.geometry.centre
    if minions:
        sim.add_minion(RED, Kind.SIEGE, centre + 300.0, count=2, delay=1e6)
    before = [m.hp for m in sim.minions[RED]]
    pusher = ChampionInput(0, BLUE, centre, Mode.PUSH, in_path=True, attack_speed=0.1, credit=0.0, aoe_dps=40.0, aoe_s=bound)
    spent = of(sim.step(sim.tick, [pusher]), AreaSpent)
    assert spent == ([AreaSpent(0, pytest.approx(seconds))] if seconds > 0 else [])
    assert [was - m.hp for was, m in zip(before, sim.minions[RED])] == pytest.approx([40.0 * seconds] * len(before))
