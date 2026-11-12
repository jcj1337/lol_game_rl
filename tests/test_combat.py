import math
from collections import Counter

import pytest

from riftgame import champions
from riftgame.champions import (ACTIONS, FOUNTAIN, HOLD, KEEP, LEVEL_XP, PROFILES, RECALL, RIFT, ROLES, SEATS, Income, Kind, Outcome,
                                capability, capability_of, level_of, speed_of)
from riftgame.combat import Hit, Kill, harassed
from riftgame.economy import lane_inputs
from riftgame.harness import random_legal, tick
from riftgame.jungle import SITES
from riftgame.lanes import (AttackCredit, ChampionDamage, ChampionInput, LaneSim, MinionDeath, Mode, TowerDamage, TowerDestroyed,
                            TowerPlate, TowerShot)
from riftgame.lanes import Kind as Minion
from riftgame.vision import EnemyView, Place, legal_mask, observe, sees
from riftgame.world import Config, World
from test_world_observation import CHANGED, team_knowledge
from test_world_roles import legal, off_the_mid_lane, return_actions
from worlds import (BLUE_CARRY, BLUE_JUNGLE, BLUE_MID, BLUE_SUPPORT, BLUE_TOP, EVERY_TICK, RED_CARRY, RED_JUNGLE, RED_MID,
                    RED_SUPPORT, RED_TOP, act, ended_now, lane, move, patient, play, raze, staged, submit, until)

TICK_S = EVERY_TICK.tick_s
TOP, JUNGLE, MID, CARRY, SUPPORT = range(5)
RIVER = RIFT.lane_s("mid", RIFT.at("mid_river"))
# Reference rows E13c, E13f, E13g, E16d: an outer tower's attack damage over game time, its range and attack speed, the
# ramp against champions with its limit and reset, and how near an attacked ally must be.
TOWER_AD, TOWER_AD_FULL_S, TOWER_RANGE, TOWER_SHOTS_PER_S = (182.0, 350.0), 810.0, 750.0, 0.833
RAMP_PER_HIT, RAMP_MAX, RAMP_RESET_S, SWITCH_RANGE = 0.5, 1.5, 5.0, 1400.0
# Rows E13a, E13b, E13h, E14b, E14d, E15a, E15c, E15d, E16a.
OUTER_HP, TOWER_ARMOR, MELEE_FACTOR, BACKDOOR_CUT = 9000.0, 60.0, 1.2, 0.8
PLATES, PLATE_GOLD, GLOBAL_GOLD, FIRST_TOWER_GOLD, LOCAL_RANGE = (0.10, 0.25, 0.45, 0.70, 1.00), 120.0, 50.0, 300.0, 1200.0
# Rows E18a, E18b, E18e, and the death timer of a level 1 champion.
KILL_GOLD, KILL_GOLD_STEP, FIRST_BLOOD, ASSIST_SHARE, KILL_XP_RANGE = 300.0, 10.0, 100.0, 0.5, 1600.0
SOLO_XP, SHARED_XP, DEAD_S = (42.0, 990.0), (27.97, 891.0), 10.0
# Assumed windows of the M8 ruleset.
ASSIST_S, DEFENCE_S, CALL_S = 10.0, 5.0, 2.0


def calm(places: dict, config: Config = EVERY_TICK, seed: int = 0, towers: bool = True) -> World:
    """A world in which no minion wave ever spawns, with the given seats on their marks. Without `towers` every
    lane tower has fallen, so the champions are the only sight sources and nothing shoots them."""
    world = staged(places, config, seed)
    for sim in world.lanes.values():
        sim.clock.next_wave = math.inf
    return world if towers else raze(world)


def mid(from_river: float):
    """A place on mid lane by its distance from the river crossing, negative toward the blue base."""
    return RIFT.lane_pos("mid", RIVER + from_river)


def fight(role: int) -> int:
    return act(Kind.FIGHT, role)


def events(world: World, kind: type) -> list:
    return [e for _, e in world.events if type(e) is kind]


def grow(world: World, seat: int, level: int, upgrades: int = 0) -> None:
    """Put a champion at a level with a number of upgrades, at full health and mana."""
    c = world.champions[seat]
    c.xp, c.upgrades = (float(LEVEL_XP[level - 2]) if level > 1 else 0.0), upgrades
    assert level_of(c.xp) == level
    c.hp, c.mana = capability_of(c).max_hp, capability_of(c).max_mana


def play_out(world: World, steps: int, orders: dict | None = None, staging: dict | None = None) -> list[list]:
    """Run `steps` ticks, with orders and direct changes to the world by step. Returns the combat events of each."""
    log = []
    for step in range(steps):
        if staging and step in staging:
            staging[step](world)
        submit(world, (orders or {}).get(step, {}))
        log.append([e for name, e in world.events if name == "combat"])
    return log


def struck(world: World, attacker: int, victim: int) -> bool:
    return any(hit.attacker == attacker and hit.victim == victim for hit in events(world, Hit))


def gap(world: World, a: int, b: int) -> float:
    return RIFT.separation(world.champions[a].pos, world.champions[b].pos)


@pytest.mark.parametrize("profile", ROLES)
def test_damage_per_second_on_champions_never_falls_with_a_level_or_an_upgrade_and_rises_with_every_level(profile):
    rates = [[capability(profile, level, upgrades).champion_dps for upgrades in range(6)] for level in range(1, 19)]
    assert all(later > earlier for low, high in zip(rates, rates[1:]) for earlier, later in zip(low, high))
    assert all(later >= earlier for row in rates for earlier, later in zip(row, row[1:]))
    assert rates[0][0] == PROFILES[profile].champion_dps > 0


def test_a_fighter_deals_its_damage_rate_times_the_tick_and_more_at_every_step_up_in_capability():
    """The carry's placeholder rate is 70 per second, grows by 8 percent of that per level, and each of its three
    damage upgrades adds 21."""
    expected = {(1, 0): 35.0, (1, 3): 45.5, (4, 3): 53.9, (4, 5): 74.9, (9, 5): 88.9}
    dealt = []
    for (level, upgrades), damage in expected.items():
        world = calm({BLUE_CARRY: mid(-200.0), RED_TOP: mid(200.0)})
        grow(world, BLUE_CARRY, level, upgrades)
        foe = world.champions[RED_TOP]
        world.step()
        before = foe.hp
        submit(world, {BLUE_CARRY: fight(TOP)})
        hit, = events(world, Hit)
        assert (hit.attacker, hit.victim, hit.damage) == (BLUE_CARRY, RED_TOP, pytest.approx(damage))
        assert before - foe.hp == pytest.approx(damage - capability_of(foe).hp_regen * TICK_S), "less a tick of the victim's regeneration"
        dealt.append(hit.damage)
    assert dealt == sorted(set(dealt))


@pytest.mark.parametrize("units", [600.0, 1500.0, 3000.0])
def test_an_ally_joins_a_fight_on_the_tick_that_its_route_over_its_speed_gives(units):
    world = calm({BLUE_TOP: mid(-150.0), BLUE_JUNGLE: mid(-units), RED_SUPPORT: mid(0.0)})
    ally, foe = world.champions[BLUE_JUNGLE], world.champions[RED_SUPPORT]
    submit(world, {BLUE_TOP: fight(SUPPORT)})
    assert struck(world, BLUE_TOP, RED_SUPPORT) and observe(world, BLUE_JUNGLE).enemies[SUPPORT] is not None
    can = capability_of(ally)
    route = RIFT.distance(ally.pos, foe.pos)
    assert route == pytest.approx(units)
    due = math.ceil((route - can.attack_range) / (can.move_speed * TICK_S) - 1e-9)
    submit(world, {BLUE_JUNGLE: fight(SUPPORT)})
    steps = 1 + until(lambda: struck(world, BLUE_JUNGLE, RED_SUPPORT), world.step)
    assert steps == due and foe.hp > 0
    assert RIFT.distance(ally.pos, foe.pos) == pytest.approx(can.attack_range)


def watch(world: World, attacker: int, victim: int, steps: int, orders: dict, staging: dict | None = None) -> list[tuple]:
    """Per tick: whether the attacker damaged the victim, whether the victim stood within the attacker's range
    by the straight line, and whether the attacker's team saw the victim's place."""
    rows = []
    for step in range(steps):
        if staging and step in staging:
            staging[step](world)
        submit(world, orders.get(step, {}))
        a, v = world.champions[attacker], world.champions[victim]
        rows.append((struck(world, attacker, victim), gap(world, attacker, victim) <= capability_of(a).attack_range + 1e-6,
                     sees(world, a.team, v.pos)))
    return rows


def test_a_champion_takes_champion_damage_exactly_on_the_ticks_when_the_attacker_is_in_range_and_its_team_sees_it():
    """A carry walks up to a jungler that holds 1,200 units away, hits it, and loses it when it walks off faster."""
    world = calm({BLUE_CARRY: mid(-1200.0), RED_JUNGLE: mid(0.0)}, towers=False)
    world.step()
    rows = watch(world, BLUE_CARRY, RED_JUNGLE, 30, {0: {BLUE_CARRY: fight(JUNGLE)}, 8: {RED_JUNGLE: move("own_base")}})
    assert all(hit == (near and seen) for hit, near, seen in rows)
    assert [hit for hit, _, _ in rows] == [False] * 3 + [True] * 5 + [False] * 22
    assert all(seen for _, _, seen in rows), "the victim was in view the whole time, so only the range decided"
    assert 550.0 < gap(world, BLUE_CARRY, RED_JUNGLE) < 800.0


def over_the_wall(world: World, share: float):
    """A place on the path from the blue mid outer tower's node to the blue Raptors. A wall crosses the path at 51
    percent of it."""
    a, b = RIFT.at("blue_mid_t1"), RIFT.at("blue_raptors")
    return RIFT.advance(a, b, share * RIFT.distance(a, b))


def test_a_ranged_attack_reaches_over_a_wall_only_while_an_ally_sees_the_target_and_the_victims_team_sees_who_hits_it():
    world = calm({}, towers=True)
    places = {BLUE_CARRY: over_the_wall(world, 0.35), RED_MID: over_the_wall(world, 0.65), BLUE_SUPPORT: RIFT.at("blue_raptors")}
    for seat, pos in places.items():
        world.champions[seat].pos = pos
    assert gap(world, BLUE_CARRY, RED_MID) == pytest.approx(352.0, abs=1.0)
    assert not RIFT.sees(places[BLUE_CARRY], places[RED_MID], 1350.0) and RIFT.sees(places[BLUE_SUPPORT], places[RED_MID], 1350.0)
    world.step()

    def leave(world):
        world.champions[BLUE_SUPPORT].pos = FOUNTAIN[0]

    def come_back(world):
        world.champions[BLUE_SUPPORT].pos = places[BLUE_SUPPORT]

    shown = []

    def note(world):
        shown.append(observe(world, RED_MID).enemies[CARRY] is not None)

    staging = {step: note for step in range(13)} | {4: lambda w: (note(w), leave(w)), 5: lambda w: (note(w), come_back(w)),
                                                    8: lambda w: (note(w), leave(w))}
    rows = watch(world, BLUE_CARRY, RED_MID, 12, {0: {BLUE_CARRY: fight(MID)}}, staging)
    note(world)
    assert all(near for _, near, _ in rows), "the target stood within the carry's range by the straight line on every tick"
    assert [seen for _, _, seen in rows] == [True] * 4 + [False] + [True] * 3 + [False] * 4
    assert [hit for hit, _, _ in rows] == [seen for _, _, seen in rows]
    assert not sees(world, 1, places[BLUE_CARRY]), "no red source sees the carry's place"
    assert shown[1:] == [hit for hit, _, _ in rows], "red sees the carry on exactly the ticks on which it damaged a red champion"
    me = world.champions[BLUE_CARRY]
    assert (me.outcome, me.outcome_tick, me.pos) == (Outcome.LOST, world.tick - 2, places[BLUE_CARRY])


def test_attack_range_is_the_straight_line_and_not_the_walk():
    """A jungle path is 1.15 times as long to walk as it is straight. 494 straight units along one are a walk of 568,
    against the carry's range of 550."""
    world = calm({})
    world.champions[BLUE_CARRY].pos, world.champions[RED_TOP].pos = over_the_wall(world, 0.55), over_the_wall(world, 0.97)
    assert gap(world, BLUE_CARRY, RED_TOP) < 550.0 < RIFT.distance(world.champions[BLUE_CARRY].pos, world.champions[RED_TOP].pos)
    world.step()
    stood = world.champions[BLUE_CARRY].pos
    submit(world, {BLUE_CARRY: fight(TOP)})
    assert struck(world, BLUE_CARRY, RED_TOP) and world.champions[BLUE_CARRY].pos == stood


def test_a_champion_that_holds_hits_back_at_the_enemy_that_damages_it_from_behind_a_wall():
    world = calm({})
    places = {BLUE_CARRY: over_the_wall(world, 0.35), RED_MID: over_the_wall(world, 0.65), BLUE_SUPPORT: RIFT.at("blue_raptors")}
    for seat, pos in places.items():
        world.champions[seat].pos = pos
    world.step()
    log = play_out(world, 4, {0: {BLUE_CARRY: fight(MID)}, 2: {BLUE_CARRY: HOLD}})
    assert [sorted(hit.attacker for hit in tick) for tick in log] == [[BLUE_CARRY, RED_MID]] * 2 + [[]] * 2
    assert log[0][1].damage == capability_of(world.champions[RED_MID]).champion_dps * TICK_S


def test_a_standing_tower_gives_its_team_sight_and_a_fallen_one_gives_none():
    world = calm({RED_TOP: mid(-1500.0)})
    tower = RIFT.lane_pos("mid", world.lanes["mid"].towers[0][0].s)
    assert RIFT.separation(tower, mid(-1500.0)) < 1350.0 < RIFT.separation(FOUNTAIN[0], mid(-1500.0))
    world.step()
    seen = observe(world, BLUE_TOP).enemies[TOP]
    assert seen == EnemyView(Place("mid", pytest.approx(RIVER - 1500.0)), world.champions[RED_TOP].hp, 1)
    assert [enemy is None for enemy in observe(world, BLUE_TOP).enemies] == [False, True, True, True, True]
    assert legal_mask(observe(world, BLUE_TOP))[fight(TOP)]
    world.lanes["mid"].towers[0][0].hp = 0.0
    world.step()
    assert observe(world, BLUE_TOP).enemies[TOP] is None and not legal_mask(observe(world, BLUE_TOP))[fight(TOP)]


def tower_ad(t: float) -> float:
    return TOWER_AD[0] + (TOWER_AD[1] - TOWER_AD[0]) * t / TOWER_AD_FULL_S


def tower_shot(k: int, first_s: float, heat: int | None = None) -> tuple[float, float]:
    """The time and the damage of an outer tower's shot number k on a champion, counted from 0, by the reference."""
    t = first_s + k / TOWER_SHOTS_PER_S
    return t, tower_ad(t) * (1.0 + min(RAMP_MAX, RAMP_PER_HIT * (k if heat is None else heat)))


def under_the_blue_mid_tower(from_tower: float, seat: int = RED_TOP, others: dict | None = None) -> tuple[World, float]:
    """A calm world with a level 18 champion with every upgrade on mid lane, `from_tower` units on the river's
    side of the blue outer tower. It has the health to take five tower shots. `others` stand on the lane too."""
    world = calm({})
    at = world.lanes["mid"].towers[0][0].s
    world.champions[seat].pos = RIFT.lane_pos("mid", at + from_tower)
    for other, offset in (others or {}).items():
        world.champions[other].pos = RIFT.lane_pos("mid", at + offset)
    grow(world, seat, 18, 5)
    return world, at


def test_a_tower_with_no_minion_in_range_shoots_a_champion_from_the_tick_it_enters_and_ramps_by_the_reference_rule():
    world, at = under_the_blue_mid_tower(TOWER_RANGE + 1.0)
    me = world.champions[RED_TOP]
    full = me.hp
    for _ in range(6):
        world.step()
        assert events(world, TowerShot) == [] and me.hp == full, "one unit outside the range"
    me.pos = RIFT.lane_pos("mid", at + TOWER_RANGE)
    entered = world.tick
    shots = []
    for _ in range(12):
        world.step()
        shots += [(world.tick - 1, e) for e in events(world, TowerShot)]
    expected = [tower_shot(k, entered * TICK_S) for k in range(5)]
    assert [tick for tick, _ in shots] == [math.floor(t / TICK_S + 1e-9) for t, _ in expected] == [entered + n for n in (0, 2, 4, 7, 9)]
    assert [(e.team, e.tier, e.seat) for _, e in shots] == [(0, 0, RED_TOP)] * 5
    assert [e.t for _, e in shots] == pytest.approx([t for t, _ in expected])
    assert [e.damage for _, e in shots] == pytest.approx([damage for _, damage in expected])
    assert [e.damage / tower_ad(e.t) for _, e in shots] == pytest.approx([1.0, 1.5, 2.0, 2.5, 2.5])
    assert shots[0][1].damage == pytest.approx(182.0 + 168.0 * entered * TICK_S / 810.0)
    regenerated = capability_of(me).hp_regen * TICK_S * 12
    assert full - me.hp == pytest.approx(sum(e.damage for _, e in shots) - regenerated) and me.hp > 0


@pytest.mark.parametrize("away_ticks, resets", [(9, False), (10, True)])
def test_a_towers_ramp_starts_again_five_seconds_after_its_last_hit_on_a_champion_and_not_before(away_ticks, resets):
    world, at = under_the_blue_mid_tower(TOWER_RANGE)
    me = world.champions[RED_TOP]
    shots = []
    for _ in range(10):
        world.step()
        shots += events(world, TowerShot)
    assert len(shots) == 5 and world.tick == 10
    last = shots[-1].t
    me.pos = RIFT.lane_pos("mid", at + 2000.0)
    me.hp = capability_of(me).max_hp
    for _ in range(away_ticks):
        world.step()
        assert events(world, TowerShot) == []
    me.pos = RIFT.lane_pos("mid", at + TOWER_RANGE)
    back = world.tick * TICK_S
    world.step()
    shot, = events(world, TowerShot)
    assert shot.t == back and (back - last >= RAMP_RESET_S) is resets
    assert shot.damage == pytest.approx(tower_shot(0, back, heat=0 if resets else 5)[1])


def test_a_tower_turns_from_minions_to_a_champion_that_damages_an_ally_and_back_when_the_call_has_run_out():
    world, at = under_the_blue_mid_tower(600.0, seat=RED_CARRY, others={BLUE_TOP: 300.0})
    grow(world, BLUE_TOP, 18, 5)
    world.lanes["mid"].add_minion(1, Minion.SIEGE, at + 280.0, count=2)
    siege = list(world.lanes["mid"].minions[1])
    assert RIFT.separation(world.champions[BLUE_TOP].pos, RIFT.lane_pos("mid", at)) <= SWITCH_RANGE
    orders = {3: {RED_CARRY: fight(TOP)}, 8: {RED_CARRY: HOLD}}
    shots, minion_hp = [], [sum(m.hp for m in siege)]
    for step in range(16):
        submit(world, orders.get(step, {}))
        shots += [(step, e.seat) for e in events(world, TowerShot)]
        minion_hp.append(sum(m.hp for m in siege))
    due = [math.floor(k / TOWER_SHOTS_PER_S / TICK_S + 1e-9) for k in range(7)]
    assert due == [0, 2, 4, 7, 9, 12, 14]
    on_minions = [step for step in range(16) if minion_hp[step + 1] < minion_hp[step]]
    assert sorted(on_minions + [step for step, _ in shots]) == due
    assert shots == [(4, RED_CARRY), (7, RED_CARRY), (9, RED_CARRY)], "its last hit fell on tick 7 and the call lasts 2 s more"
    assert on_minions == [0, 2, 12, 14] and world.champions[BLUE_TOP].hp > 0 and world.champions[RED_CARRY].hp > 0


def lane_under_tower(victim_from_tower: float | None, minions: bool = False) -> list:
    """A lane tick with a red champion 400 units from the blue outer tower. It has damaged the blue champion of
    seat 2, which stands `victim_from_tower` units behind the tower, or is not there."""
    sim = LaneSim("mid", 0, TICK_S, start_s=300.0)
    sim.clock.next_wave = math.inf
    at = sim.geometry.towers[0][0]
    if minions:
        sim.add_minion(1, Minion.SIEGE, at + 300.0)
    inputs = [ChampionInput(7, 1, at + 400.0, Mode.PASSIVE, in_path=False, tower_target=True, victims=(2,))]
    if victim_from_tower is not None:
        inputs.append(ChampionInput(2, 0, at - victim_from_tower, Mode.PASSIVE, in_path=False, tower_target=True))
    return [e for e in sim.step(sim.tick, inputs) if type(e) is TowerShot]


def test_a_tower_answers_for_an_ally_only_within_the_switch_range_and_shoots_minions_first_otherwise():
    assert [e.seat for e in lane_under_tower(SWITCH_RANGE - 5.0, minions=True)] == [7]
    assert lane_under_tower(SWITCH_RANGE + 5.0, minions=True) == []
    assert lane_under_tower(None, minions=True) == []
    assert [e.seat for e in lane_under_tower(None)] == [7], "with no minion in range the tower shoots the champion anyway"


def test_a_tower_shoots_nobody_whose_input_does_not_make_it_a_target_and_the_closest_of_two_that_do():
    sim = LaneSim("mid", 0, TICK_S, start_s=300.0)
    sim.clock.next_wave = math.inf
    at = sim.geometry.towers[0][0]
    quiet = [ChampionInput(7, 1, at + 400.0, Mode.PASSIVE, in_path=False), ChampionInput(8, 1, at + 300.0, Mode.PASSIVE, in_path=False)]
    assert sim.step(sim.tick, quiet) == []
    marked = [ChampionInput(7, 1, at + 400.0, Mode.PASSIVE, in_path=False, tower_target=True),
              ChampionInput(8, 1, at + 300.0, Mode.PASSIVE, in_path=False, tower_target=True),
              ChampionInput(0, 0, at + 100.0, Mode.PASSIVE, in_path=False, tower_target=True)]
    assert [(e.team, e.seat) for e in sim.step(sim.tick, marked) if type(e) is TowerShot] == [(0, 8)]


def test_a_champion_beside_the_lane_is_in_a_towers_range_by_the_straight_line():
    """The path from the blue mid outer tower's node to the Raptors leaves the lane. A champion 400 walked units
    along it is no longer on the lane and still within the tower's range."""
    world = calm({})
    me = world.champions[RED_TOP]
    me.pos = over_the_wall(world, 0.3)
    grow(world, RED_TOP, 18, 5)
    tower = RIFT.lane_pos("mid", world.lanes["mid"].towers[0][0].s)
    assert RIFT.lane_s("mid", me.pos) is None and RIFT.separation(me.pos, tower) < TOWER_RANGE
    world.step()
    assert [e.seat for e in events(world, TowerShot)] == [RED_TOP]
    me.pos = over_the_wall(world, 0.7)
    assert RIFT.separation(me.pos, tower) > TOWER_RANGE
    for _ in range(4):
        world.step()
        assert events(world, TowerShot) == []


def siege_world(from_tower: float = 1000.0, seat: int = BLUE_TOP, level: int = 18) -> tuple[World, object, float]:
    """A calm world with a strong champion on mid lane, on the blue side of the red outer tower."""
    world = calm({})
    tower = world.lanes["mid"].towers[1][0]
    world.champions[seat].pos = RIFT.lane_pos("mid", tower.s - from_tower)
    world.champions[seat].attack_credit = 1.0
    grow(world, seat, level, 5)
    return world, tower, tower.s


def tower_damage(world: World) -> list[float]:
    return [e.damage for e in events(world, TowerDamage)]


def test_a_siege_walks_to_attack_range_of_the_front_tower_and_hits_it_with_whole_attacks_cut_by_armor_and_backdoor():
    world, tower, at = siege_world()
    me = world.champions[BLUE_TOP]
    can = capability_of(me)
    assert can.attack_range == 175.0 and tower.hp == OUTER_HP
    blow = can.hit_damage * 100.0 / (100.0 + TOWER_ARMOR) * MELEE_FACTOR * (1.0 - BACKDOOR_CUT)
    arrive = math.ceil((1000.0 - can.attack_range) / (can.move_speed * TICK_S))
    hits = []
    submit(world, {BLUE_TOP: act(Kind.SIEGE, "mid")})
    for step in range(1, arrive + 8):
        hits += [(step, damage) for damage in tower_damage(world)]
        world.step()
    period = 1.0 / can.attack_speed
    assert [step for step, _ in hits] == [arrive + math.floor(k * period / TICK_S + 1e-9) for k in range(len(hits))]
    assert len(hits) >= 3 and [damage for _, damage in hits] == pytest.approx([blow] * len(hits))
    assert OUTER_HP - tower.hp == pytest.approx(blow * len(hits))
    assert RIFT.distance(me.pos, RIFT.lane_pos("mid", at)) == pytest.approx(can.attack_range)
    assert (me.outcome, ACTIONS[me.intent].kind) == (Outcome.NONE, Kind.SIEGE)


@pytest.mark.parametrize("seat, minion_near, factor", [(BLUE_TOP, False, MELEE_FACTOR * (1.0 - BACKDOOR_CUT)), (BLUE_TOP, True, MELEE_FACTOR),
                                                       (BLUE_CARRY, False, 1.0 - BACKDOOR_CUT), (BLUE_CARRY, True, 1.0)])
def test_a_tower_takes_more_from_a_melee_champion_and_a_fifth_while_none_of_the_attackers_minions_is_near(seat, minion_near, factor):
    world, tower, at = siege_world(100.0, seat)
    if minion_near:
        world.lanes["mid"].add_minion(0, Minion.MELEE, at - TOWER_RANGE + 1.0, delay=TICK_S)
    else:
        world.lanes["mid"].add_minion(0, Minion.MELEE, at - TOWER_RANGE - 400.0, delay=TICK_S)
    submit(world, {seat: act(Kind.SIEGE, "mid")})
    assert tower_damage(world) == pytest.approx([capability_of(world.champions[seat]).hit_damage * 100.0 / 160.0 * factor])


def test_an_outer_towers_armor_is_gone_by_fifteen_minutes():
    blows = {}
    for start_s in (0.0, 600.0, 900.0):
        sim = LaneSim("mid", 0, TICK_S, start_s=start_s)
        sim.clock.next_wave = math.inf
        at = sim.geometry.towers[1][0]
        hitter = ChampionInput(3, 0, at - 300.0, Mode.PASSIVE, in_path=False, hit_damage=80.0, siege=True)
        blows[start_s] = next(e.damage for e in sim.step(sim.tick, [hitter]) if type(e) is TowerDamage)
    assert blows == pytest.approx({0.0: 80.0 / 1.6 * 0.2, 600.0: 80.0 / 1.6 * 0.2, 900.0: 80.0 * 0.2})


def test_a_siege_spends_the_same_attack_credit_as_a_lane_hit_and_hands_back_what_is_left():
    sim = LaneSim("mid", 0, TICK_S, start_s=300.0)
    sim.clock.next_wave = math.inf
    at = sim.geometry.towers[1][0]
    dealt = []
    for credit in (1.0, 0.9, 0.5):
        hitter = ChampionInput(3, 0, at - 300.0, Mode.PASSIVE, in_path=False, hit_damage=80.0, attack_speed=0.5, siege=True, credit=credit)
        out = sim.step(sim.tick, [hitter])
        dealt.append((sum(type(e) is TowerDamage for e in out), [e.credit for e in out if type(e) is AttackCredit]))
    assert dealt == [(1, [pytest.approx(0.25)]), (1, [pytest.approx(0.15)]), (0, [pytest.approx(0.75)])]
    assert sim.values()[-2] == (), "the lane keeps no credit for a champion that brings its own"


def test_each_plate_pays_its_gold_to_the_living_enemy_champions_within_1200_units_whoever_broke_it():
    world, tower, at = siege_world(100.0)
    near, far, dead = world.champions[BLUE_MID], world.champions[BLUE_JUNGLE], world.champions[BLUE_CARRY]
    near.pos, far.pos = RIFT.lane_pos("mid", at - LOCAL_RANGE + 1.0), RIFT.lane_pos("mid", at - LOCAL_RANGE - 1.0)
    dead.pos = RIFT.lane_pos("mid", at - 400.0)
    world.damage_champion(BLUE_CARRY, 10_000.0)
    submit(world, {BLUE_TOP: act(Kind.SIEGE, "mid")})
    broken = 0
    for share in PLATES[:-1]:
        tower.hp = OUTER_HP * (1.0 - share) + 1.0
        world.champions[BLUE_TOP].hp = capability_of(world.champions[BLUE_TOP]).max_hp
        world.step()
        until(lambda: events(world, TowerPlate), world.step)
        broken += 1
        for c in (world.champions[BLUE_TOP], near):
            assert c.earned[Income.PLATE] == pytest.approx(broken * PLATE_GOLD / 2)
        assert far.earned[Income.PLATE] == dead.earned[Income.PLATE] == 0.0
        assert all(c.earned[Income.PLATE] == 0.0 for c in world.champions[5:])
    assert world.champions[BLUE_TOP].hp > 0


def test_a_plate_broken_by_minions_pays_the_enemy_champion_that_stands_near_and_nobody_if_none_does():
    for standing_near, paid in ((True, PLATE_GOLD), (False, 0.0)):
        world = calm({})
        sim = world.lanes["mid"]
        tower = sim.towers[1][0]
        tower.hp = OUTER_HP * 0.9 + 1.0
        sim.add_minion(0, Minion.SIEGE, tower.s - 250.0, count=3)
        world.champions[BLUE_SUPPORT].pos = RIFT.lane_pos("mid", tower.s - (1000.0 if standing_near else 1300.0))
        until(lambda: events(world, TowerPlate), world.step)
        assert [c.earned[Income.PLATE] for c in world.champions] == [paid if c.seat == BLUE_SUPPORT else 0.0 for c in world.champions]
        assert events(world, TowerDamage) and not events(world, Hit)


def test_a_fallen_tower_pays_its_global_gold_to_the_other_team_and_the_first_one_a_bonus_to_those_near_it():
    world, tower, at = siege_world(100.0)
    world.champions[BLUE_MID].pos = RIFT.lane_pos("mid", at - 900.0)
    before = [(c.gold, sum(c.earned)) for c in world.champions]
    world.damage_champion(BLUE_SUPPORT, 10_000.0)
    submit(world, {BLUE_TOP: act(Kind.SIEGE, "mid")})
    tower.hp = 1.0
    until(lambda: events(world, TowerDestroyed), world.step)
    assert len(events(world, TowerPlate)) == 1, "the last plate breaks with the tower"
    local = PLATE_GOLD / 2 + FIRST_TOWER_GOLD / 2
    assert [c.earned[Income.TOWER] + c.earned[Income.PLATE] for c in world.champions[:5]] == [GLOBAL_GOLD + local, GLOBAL_GOLD, GLOBAL_GOLD + local, GLOBAL_GOLD, GLOBAL_GOLD]
    assert all(c.earned[Income.TOWER] == c.earned[Income.PLATE] == 0.0 for c in world.champions[5:])
    inner = world.lanes["mid"].towers[1][1]
    inner.hp = 1.0
    world.champions[BLUE_TOP].hp = capability_of(world.champions[BLUE_TOP]).max_hp
    world.step()
    until(lambda: events(world, TowerDestroyed), world.step, limit=60)
    assert [c.earned[Income.TOWER] for c in world.champions[:5]] == [GLOBAL_GOLD + FIRST_TOWER_GOLD / 2 + 25.0, GLOBAL_GOLD + 25.0,
                                                                       GLOBAL_GOLD + FIRST_TOWER_GOLD / 2 + 25.0, GLOBAL_GOLD + 25.0, GLOBAL_GOLD + 25.0]
    for c, (gold, earned) in zip(world.champions, before):
        assert c.gold - gold == pytest.approx(sum(c.earned) - earned), "every payment went through the ledger"


def test_a_siege_goes_on_to_the_next_tower_and_ends_when_the_lane_has_none_left():
    world, tower, at = siege_world(100.0)
    me = world.champions[BLUE_TOP]
    siege = act(Kind.SIEGE, "mid")
    submit(world, {BLUE_TOP: siege})
    for standing in world.lanes["mid"].towers[1]:
        assert me.intent == siege and me.outcome is Outcome.NONE
        me.hp = capability_of(me).max_hp
        standing.hp = 1.0
        until(lambda: standing.hp <= 0, world.step, limit=80)
    assert (me.outcome, me.outcome_tick, me.intent) == (Outcome.CLEARED, world.tick - 1, HOLD)
    assert world.lanes["mid"].front_tower(1) is None
    submit(world, {BLUE_TOP: siege, BLUE_MID: act(Kind.SIEGE, "top")})
    assert (me.outcome, me.outcome_tick, me.intent) == (Outcome.ABSENT, world.tick - 1, HOLD)
    assert world.champions[BLUE_MID].intent == act(Kind.SIEGE, "top"), "top lane still has towers"
    assert all(legal_mask(observe(world, BLUE_TOP))[act(Kind.SIEGE, name)] for name in ("top", "mid", "bot"))


def brawl(orders: dict, hp: dict | None = None, places: dict | None = None, steps: int = 1, towers: bool = True) -> World:
    """A calm world in which the given seats stand around the mid river, see each other, and get their orders."""
    world = calm(places or {BLUE_TOP: mid(-100.0), BLUE_CARRY: mid(-300.0), RED_SUPPORT: mid(0.0)}, towers=towers)
    for seat, left in (hp or {}).items():
        world.champions[seat].hp = left
    world.step()
    submit(world, orders)
    for _ in range(steps - 1):
        world.step()
    return world


def kill_xp(ends: tuple[float, float], level: int) -> float:
    return ends[0] + (ends[1] - ends[0]) * (level - 1) / 17


def test_the_champion_that_dealt_the_most_damage_on_the_tick_is_the_killer_and_the_other_attacker_assists():
    world = brawl({BLUE_TOP: fight(SUPPORT), BLUE_CARRY: fight(SUPPORT)}, hp={RED_SUPPORT: 50.0})
    kill, = events(world, Kill)
    dealt = {hit.attacker: hit.damage for hit in events(world, Hit) if hit.victim == RED_SUPPORT}
    assert dealt == {BLUE_TOP: 27.5, BLUE_CARRY: 35.0}
    assert (kill.victim, kill.killer, kill.assists, kill.first_blood) == (RED_SUPPORT, BLUE_CARRY, (BLUE_TOP,), True)
    top, carry, victim = (world.champions[seat] for seat in (BLUE_TOP, BLUE_CARRY, RED_SUPPORT))
    assert carry.earned[Income.KILL] == KILL_GOLD + FIRST_BLOOD and carry.earned[Income.ASSIST] == 0.0
    assert top.earned[Income.ASSIST] == ASSIST_SHARE * KILL_GOLD and top.earned[Income.KILL] == 0.0
    assert top.xp == carry.xp == pytest.approx(SHARED_XP[0] / 2)
    assert (victim.outcome, victim.pos, victim.xp) == (Outcome.DIED, FOUNTAIN[1], 0.0)
    assert victim.earned[Income.KILL] == victim.earned[Income.ASSIST] == 0.0
    assert [c.xp for c in world.champions if c.seat not in (BLUE_TOP, BLUE_CARRY)] == [0.0] * 8


@pytest.mark.parametrize("units, shares", [(KILL_XP_RANGE - 1.0, True), (KILL_XP_RANGE + 1.0, False)])
def test_an_ally_within_xp_range_of_the_victim_shares_the_kills_xp_and_gets_no_gold(units, shares):
    places = {BLUE_TOP: mid(-100.0), BLUE_JUNGLE: mid(-units), RED_SUPPORT: mid(0.0)}
    world = brawl({BLUE_TOP: fight(SUPPORT)}, hp={RED_SUPPORT: 20.0}, places=places, towers=False)
    kill, = events(world, Kill)
    assert kill.sharers == ((BLUE_TOP, BLUE_JUNGLE) if shares else (BLUE_TOP,))
    xp = SHARED_XP[0] / 2 if shares else SOLO_XP[0]
    assert [world.champions[seat].xp for seat in (BLUE_TOP, BLUE_JUNGLE)] == [pytest.approx(xp), pytest.approx(xp) if shares else 0.0]
    assert world.champions[BLUE_JUNGLE].earned[Income.KILL] == world.champions[BLUE_JUNGLE].earned[Income.ASSIST] == 0.0


@pytest.mark.parametrize("level, gold", [(1, 300.0), (6, 300.0), (7, 310.0), (12, 360.0), (18, 420.0)])
def test_kill_gold_and_kill_xp_follow_the_victims_level(level, gold):
    world = calm({BLUE_CARRY: mid(-300.0), RED_SUPPORT: mid(0.0)})
    grow(world, RED_SUPPORT, level)
    world.champions[RED_SUPPORT].hp = 20.0
    world.step()
    submit(world, {BLUE_CARRY: fight(SUPPORT)})
    kill, = events(world, Kill)
    me = world.champions[BLUE_CARRY]
    assert KILL_GOLD + KILL_GOLD_STEP * max(0, level - 6) == gold
    assert (kill.gold, me.earned[Income.KILL]) == (gold + FIRST_BLOOD, gold + FIRST_BLOOD)
    assert me.xp == kill.xp == pytest.approx(kill_xp(SOLO_XP, level))
    assert {1: 42.0, 18: 990.0}.get(level, me.xp) == pytest.approx(me.xp)


def test_only_the_first_kill_of_a_game_pays_the_first_blood_bonus():
    world = brawl({BLUE_CARRY: fight(SUPPORT)}, hp={RED_SUPPORT: 20.0, RED_TOP: 20.0},
                  places={BLUE_CARRY: mid(-300.0), RED_SUPPORT: mid(0.0), RED_TOP: mid(100.0)})
    assert [kill.first_blood for kill in events(world, Kill)] == [True]
    submit(world, {BLUE_CARRY: fight(TOP)})
    kill, = events(world, Kill)
    assert (kill.victim, kill.first_blood, kill.gold) == (RED_TOP, False, KILL_GOLD)
    assert world.champions[BLUE_CARRY].earned[Income.KILL] == 2 * KILL_GOLD + FIRST_BLOOD


@pytest.mark.parametrize("ticks_later, killed", [(1, True), (20, True), (21, False)])
def test_a_champion_that_dies_to_something_else_is_the_kill_of_whoever_damaged_it_last_within_ten_seconds(ticks_later, killed):
    world = brawl({BLUE_TOP: fight(SUPPORT)}, places={BLUE_TOP: mid(-100.0), RED_SUPPORT: mid(0.0)})
    hit_tick = world.tick - 1
    assert struck(world, BLUE_TOP, RED_SUPPORT) and ASSIST_S / TICK_S == 20
    world.champions[BLUE_TOP].pos = FOUNTAIN[0]
    until(lambda: world.tick == hit_tick + ticks_later, world.step)
    world.damage_champion(RED_SUPPORT, 10_000.0)
    world.step()
    assert not events(world, Hit), "nobody damaged the victim on the tick it died"
    kill, = events(world, Kill)
    top = world.champions[BLUE_TOP]
    assert (kill.killer, top.earned[Income.KILL], top.xp) == ((BLUE_TOP, KILL_GOLD + FIRST_BLOOD, SOLO_XP[0]) if killed else (None, 0.0, 0.0))
    assert world.champions[RED_SUPPORT].outcome is Outcome.DIED


def test_of_two_champions_that_damaged_the_victim_earlier_the_later_one_is_the_killer_and_the_other_assists():
    world = brawl({BLUE_TOP: fight(SUPPORT)})
    submit(world, {BLUE_TOP: HOLD, BLUE_CARRY: fight(SUPPORT)})
    submit(world, {BLUE_CARRY: HOLD})
    world.step()
    world.damage_champion(RED_SUPPORT, 10_000.0)
    world.step()
    kill, = events(world, Kill)
    assert (kill.killer, kill.assists, kill.assist_gold) == (BLUE_CARRY, (BLUE_TOP,), ASSIST_SHARE * KILL_GOLD)


def test_two_champions_that_kill_each_other_on_one_tick_are_both_paid_and_one_of_them_gets_first_blood():
    world = brawl({BLUE_MID: fight(MID), RED_MID: fight(MID)}, hp={BLUE_MID: 1.0, RED_MID: 1.0},
                  places={BLUE_MID: mid(-200.0), RED_MID: mid(200.0)})
    blue, red = world.champions[BLUE_MID], world.champions[RED_MID]
    kills = events(world, Kill)
    assert sorted((kill.victim, kill.killer) for kill in kills) == [(BLUE_MID, RED_MID), (RED_MID, BLUE_MID)]
    assert sorted(c.earned[Income.KILL] for c in (blue, red)) == [KILL_GOLD, KILL_GOLD + FIRST_BLOOD]
    assert blue.xp == red.xp == SOLO_XP[0]
    assert [(c.hp, c.outcome, c.outcome_tick, c.pos) for c in (blue, red)] == [(0.0, Outcome.DIED, world.tick - 1, FOUNTAIN[team]) for team in (0, 1)]
    assert sum(kill.first_blood for kill in kills) == 1


def test_a_champion_killed_in_a_fight_returns_on_its_fountain_after_the_death_timer_with_nothing_held_against_it():
    world = brawl({BLUE_CARRY: fight(SUPPORT)}, hp={RED_SUPPORT: 20.0})
    victim = world.champions[RED_SUPPORT]
    died = world.tick - 1
    assert (victim.outcome, victim.outcome_tick, victim.pos, victim.hp) == (Outcome.DIED, died, FOUNTAIN[1], 0.0)
    assert observe(world, RED_SUPPORT).me.hurt_by[CARRY] and observe(world, RED_SUPPORT).me.dead_s == DEAD_S
    waited = until(lambda: victim.hp > 0, world.step)
    assert waited * TICK_S == DEAD_S and world.tick - 1 == died + DEAD_S / TICK_S
    can = capability_of(victim)
    assert (victim.hp, victim.mana, victim.pos, victim.intent) == (can.max_hp, can.max_mana, FOUNTAIN[1], HOLD)
    assert not any(observe(world, RED_SUPPORT).me.hurt_by)


def test_a_fight_ends_killed_when_its_target_dies_whoever_killed_it():
    world = brawl({BLUE_TOP: fight(SUPPORT), BLUE_CARRY: fight(SUPPORT), RED_SUPPORT: fight(TOP)}, hp={RED_SUPPORT: 50.0})
    for seat in (BLUE_TOP, BLUE_CARRY):
        c = world.champions[seat]
        assert (c.outcome, c.outcome_tick, c.intent) == (Outcome.KILLED, world.tick - 1, HOLD)
    world = brawl({BLUE_TOP: fight(SUPPORT)})
    world.damage_champion(RED_SUPPORT, 10_000.0)
    world.step()
    assert world.champions[BLUE_TOP].outcome is Outcome.KILLED


def chase(hide=None, turn_at: int | None = None) -> tuple[World, list]:
    """A carry fights a jungler that stands 1,295 units away and walks off, a little faster than the carry. The
    jungler is out of blue's view after six ticks. Returns the world after 14 ticks, and per tick the carry's
    place, whether blue saw the jungler after the tick, the jungler's place, and the combat events."""
    world = calm({BLUE_CARRY: mid(-1295.0), RED_JUNGLE: mid(0.0)}, towers=False)
    world.step()
    orders = {0: {BLUE_CARRY: fight(JUNGLE), RED_JUNGLE: move("own_base")}}
    if turn_at is not None:
        orders[turn_at] = {RED_JUNGLE: move("enemy_base")}
    rows = []
    for step in range(14):
        if hide is not None and step == 8:
            world.champions[RED_JUNGLE].pos = hide
        submit(world, orders.get(step, {}))
        me, foe = world.champions[BLUE_CARRY], world.champions[RED_JUNGLE]
        rows.append((me.pos, sees(world, 0, foe.pos), foe.pos, events(world, Hit), me.outcome))
    return world, rows


def test_a_fighter_whose_target_leaves_the_view_walks_to_where_its_team_last_saw_it_and_gives_up_there():
    world, rows = chase()
    me = world.champions[BLUE_CARRY]
    seen = [in_view for _, in_view, _, _, _ in rows]
    assert seen == [True] * 5 + [False] * 9
    last_seen = rows[4][2]
    reach, step = capability_of(me).attack_range, capability_of(me).move_speed * TICK_S
    to_go = [RIFT.distance(pos, last_seen) for pos, _, _, _, _ in rows]
    arrived = next(i for i, left in enumerate(to_go) if left <= reach + 1e-6)
    assert arrived == 9
    assert [to_go[i] - to_go[i + 1] for i in range(6, arrived - 1)] == pytest.approx([step] * (arrived - 7)), "a straight walk at full speed"
    assert to_go[arrived] == pytest.approx(reach)
    assert [outcome for _, _, _, _, outcome in rows] == [Outcome.NONE] * (arrived + 1) + [Outcome.LOST] * (13 - arrived)
    assert (me.outcome_tick, me.intent, me.pos) == (arrived + 2, HOLD, rows[arrived][0])
    assert not any(hits for _, _, _, hits, _ in rows) and RIFT.separation(me.pos, world.champions[RED_JUNGLE].pos) > 1350.0


def test_the_fighters_path_is_the_same_wherever_its_hidden_target_is():
    _, rows = chase()
    _, moved = chase(hide=RIFT.at("red_krugs"))
    assert [row[2] for row in rows] != [row[2] for row in moved], "the target is in two different places"
    assert [(row[0], row[1], row[4]) for row in rows] == [(row[0], row[1], row[4]) for row in moved]


def test_a_target_seen_again_before_the_fighter_arrives_is_fought_again_and_no_outcome_is_recorded():
    world, rows = chase(turn_at=8)
    me = world.champions[BLUE_CARRY]
    seen = [in_view for _, in_view, _, _, _ in rows]
    assert seen == [True] * 5 + [False] * 3 + [True] * 6
    assert all(outcome is Outcome.NONE for _, _, _, _, outcome in rows) and me.intent == fight(JUNGLE)
    assert any(hits for _, _, _, hits, _ in rows[8:])
    assert RIFT.separation(me.pos, world.champions[RED_JUNGLE].pos) <= capability_of(me).attack_range + 1e-6


def test_the_mask_offers_a_fight_only_against_a_living_enemy_in_view_and_keeps_a_running_fight_with_a_hidden_target():
    fights = {role: fight(role) for role in range(5)}
    start = calm({BLUE_CARRY: mid(-1295.0), RED_JUNGLE: mid(0.0), RED_TOP: mid(-2800.0)}, towers=False)
    assert not any(legal_mask(observe(start, BLUE_CARRY))[i] for i in fights.values()), "nothing is seen before the first tick"
    start.step()
    mask = legal_mask(observe(start, BLUE_CARRY))
    assert [mask[fights[role]] for role in range(5)] == [False, True, False, False, False]
    assert observe(start, BLUE_CARRY).enemies[TOP] is None and RIFT.separation(mid(-1295.0), mid(-2800.0)) > 1350.0
    submit(start, {BLUE_CARRY: fights[JUNGLE], RED_JUNGLE: move("own_base")})
    for _ in range(7):
        start.step()
    hidden = observe(start, BLUE_CARRY)
    assert hidden.enemies[JUNGLE] is None and hidden.me.intent == fights[JUNGLE]
    mask = legal_mask(hidden)
    assert mask[KEEP] and not mask[fights[JUNGLE]]
    start.damage_champion(RED_JUNGLE, 10_000.0)
    start.step()
    start.champions[RED_JUNGLE].pos = start.champions[BLUE_CARRY].pos
    start.step()
    assert start.champions[RED_JUNGLE].hp == 0.0 and sees(start, 0, start.champions[RED_JUNGLE].pos)
    assert observe(start, BLUE_CARRY).enemies[JUNGLE] is None, "a dead enemy is not seen, wherever it lies"


@pytest.mark.parametrize("leash", ["off its lane", "on its lane"])
@pytest.mark.parametrize("restricted", [True, False])
def test_a_laner_with_no_allowance_may_fight_the_enemy_that_damaged_it_and_keeps_its_ways_home(leash, restricted):
    spot = off_the_mid_lane(800.0) if leash == "off its lane" else mid(-300.0)
    config = Config(decision_ticks=1, roam_restricted=restricted)
    world = calm({BLUE_MID: spot, RED_JUNGLE: spot, RED_TOP: RIFT.advance(spot, RIFT.at("mid_river"), 300.0)}, config)
    me = world.champions[BLUE_MID]
    me.allowance = -6.0
    home = return_actions("mid") | ({HOLD} if leash == "on its lane" else set())
    world.step()
    seen = observe(world, BLUE_MID)
    assert seen.enemies[JUNGLE] is not None and seen.enemies[TOP] is not None and not any(seen.me.hurt_by)
    fights = {fight(JUNGLE), fight(TOP)}

    def choices() -> set[int]:
        return legal(world, BLUE_MID) - {KEEP}

    if restricted:
        assert choices() == home
    else:
        assert fights <= choices() and home <= choices()
    submit(world, {RED_JUNGLE: fight(MID)})
    submit(world, {RED_JUNGLE: HOLD})
    hit_tick = world.tick - 2
    assert observe(world, BLUE_MID).me.hurt_by == (False, True, False, False, False)
    if restricted:
        assert choices() == home | {fight(JUNGLE)}, "self-defence adds the attacker and nobody else"
    else:
        assert fights <= choices()
    until(lambda: world.tick == hit_tick + DEFENCE_S / TICK_S, world.step)
    assert observe(world, BLUE_MID).me.hurt_by[JUNGLE] and me.allowance <= 0 and fight(JUNGLE) in choices()
    world.step()
    assert not any(observe(world, BLUE_MID).me.hurt_by), "the window is 5 s"
    if restricted:
        assert choices() == home
    else:
        assert fights <= choices()


def test_a_fight_started_in_self_defence_may_be_kept_until_the_attacker_has_stopped_damaging_the_laner_for_five_seconds():
    spot = off_the_mid_lane(800.0)
    world = calm({BLUE_MID: spot, RED_JUNGLE: spot})
    me = world.champions[BLUE_MID]
    me.allowance = -6.0
    world.step()
    submit(world, {RED_JUNGLE: fight(MID)})
    submit(world, {BLUE_MID: fight(JUNGLE)})
    submit(world, {RED_JUNGLE: move("own_base")})
    last_hit = world.tick - 2
    assert me.hurt_tick[JUNGLE] == last_hit and me.intent == fight(JUNGLE)
    # The chase takes it onto its lane, where a laner with no allowance may also hold.
    while world.tick <= last_hit + DEFENCE_S / TICK_S:
        assert legal(world, BLUE_MID) - {HOLD} == return_actions("mid") | {fight(JUNGLE), KEEP}
        world.step()
    assert observe(world, BLUE_MID).enemies[JUNGLE] is not None and me.intent == fight(JUNGLE)
    assert legal(world, BLUE_MID) - {HOLD} == return_actions("mid"), "it has to choose a way home at its next decision"


def test_a_lockdown_slows_the_target_for_its_duration_costs_mana_and_comes_back_after_its_cooldown():
    world = calm({BLUE_JUNGLE: mid(-150.0), RED_CARRY: mid(0.0)}, towers=False)
    me, foe = world.champions[BLUE_JUNGLE], world.champions[RED_CARRY]
    grow(world, RED_CARRY, 18, 5)
    can = capability_of(me)
    assert (can.lockdown_slow, can.lockdown_s, can.lockdown_cooldown_s, can.lockdown_mana, can.max_mana) == (0.40, 2.0, 10.0, 50.0, 320.0)
    assert capability_of(foe).lockdown_slow == 0.0
    world.step()
    full_step = capability_of(foe).move_speed * TICK_S
    slows, steps, mana = [], [], []
    orders = {0: {BLUE_JUNGLE: fight(CARRY), RED_CARRY: move("own_base")}}
    for step in range(30):
        was = foe.pos
        submit(world, orders.get(step, {}))
        slows += [(step, hit.slow) for hit in events(world, Hit) if hit.attacker == BLUE_JUNGLE and hit.slow]
        steps.append(RIFT.distance(was, foe.pos))
        mana.append(me.mana)
        if step == 2:
            assert speed_of(world, foe) == pytest.approx(capability_of(foe).move_speed * 0.6)
    assert slows == [(0, 0.40), (20, 0.40)], "ready again 10 s after its use"
    slowed = [i for i, walked in enumerate(steps) if walked == pytest.approx(full_step * 0.6)]
    assert slowed == [1, 2, 3, 4, 21, 22, 23, 24], "2 s from the move after the hit"
    assert all(walked == pytest.approx(full_step) for i, walked in enumerate(steps) if i not in slowed)
    assert mana == [270.0] * 20 + [220.0] * 10
    assert speed_of(world, foe) == capability_of(foe).move_speed and foe.hp > 0


def test_a_lockdown_needs_its_mana_and_a_carry_has_none():
    world = brawl({BLUE_TOP: fight(SUPPORT), BLUE_CARRY: fight(SUPPORT)}, steps=3)
    assert world.champions[BLUE_TOP].mana == 250.0 and world.champions[BLUE_CARRY].mana == 330.0
    world = calm({BLUE_TOP: mid(-100.0), RED_SUPPORT: mid(0.0)})
    world.champions[BLUE_TOP].mana = 49.0
    world.step()
    log = play_out(world, 3, {0: {BLUE_TOP: fight(SUPPORT)}})
    assert [hit.slow for tick in log for hit in tick if hit.attacker == BLUE_TOP] == [0.0] * 3 and world.champions[BLUE_TOP].mana == 49.0
    assert world.champions[RED_SUPPORT].slow_until <= world.tick


def with_minions_in_reach(order: int | None, credit: float = 1.0) -> tuple[World, list]:
    """A blue carry on mid lane with two red caster minions that one hit kills and a red top laner in its range.
    The minions and the top laner stand 300 and 400 units from it. Returns the world after six ticks and the
    minion deaths of each tick."""
    world = calm({BLUE_CARRY: mid(0.0), RED_TOP: mid(400.0)})
    grow(world, RED_TOP, 18, 5)
    sim = world.lanes["mid"]
    sim.add_minion(1, Minion.CASTER, RIVER + 300.0, count=2)
    for m in sim.minions[1]:
        m.hp = 55.0
    # The casters stand and shoot at a blue minion that cannot hurt them and does not die.
    sim.add_minion(0, Minion.SIEGE, RIVER - 100.0)
    sim.minions[0][0].hp, sim.minions[0][0].ad = 1e9, 0.0
    world.champions[BLUE_CARRY].attack_credit = credit
    world.step()
    deaths = []
    for step in range(6):
        submit(world, {BLUE_CARRY: order} if step == 0 and order is not None else {})
        deaths.append([e.killer for e in events(world, MinionDeath)])
    return world, deaths


def test_a_champion_that_fights_a_champion_kills_no_minion_although_minions_are_in_its_reach():
    world, deaths = with_minions_in_reach(fight(TOP))
    assert deaths == [[]] * 6 and len(world.lanes["mid"].minions[1]) == 2
    assert world.champions[RED_TOP].hp < capability_of(world.champions[RED_TOP]).max_hp - 150.0
    assert world.champions[BLUE_CARRY].attack_credit == 0.0
    world, deaths = with_minions_in_reach(lane("mid", "push"))
    assert deaths[0] == deaths[2] == [BLUE_CARRY] and sum(deaths, []) == [BLUE_CARRY] * 2, "the same champion kills them when its intent says so"
    assert world.champions[RED_TOP].hp == capability_of(world.champions[RED_TOP]).max_hp


def test_a_champion_that_switches_from_a_fight_to_the_lane_has_no_ready_attack():
    world, _ = with_minions_in_reach(fight(TOP))
    me = world.champions[BLUE_CARRY]
    assert me.attack_credit == 0.0 and capability_of(me).attack_speed == 0.70
    kills = []
    for step in range(8):
        submit(world, {BLUE_CARRY: lane("mid", "push")} if step == 0 else {})
        kills.append(len(events(world, MinionDeath)))
    period_ticks = 1.0 / 0.70 / TICK_S
    assert kills == [0, 0, 1, 0, 0, 1, 0, 0] and [math.floor(period_ticks), math.floor(2 * period_ticks)] == [2, 5]
    idle, deaths = with_minions_in_reach(None)
    assert idle.champions[BLUE_CARRY].attack_credit == 1.0 and deaths == [[]] * 6
    submit(idle, {BLUE_CARRY: lane("mid", "push")})
    assert len(events(idle, MinionDeath)) == 1, "a champion that did not attack has its attack ready"


def test_an_idle_champion_earns_its_attack_speed_times_the_tick_up_to_one_ready_attack():
    world = calm({BLUE_CARRY: mid(0.0)})
    me = world.champions[BLUE_CARRY]
    credits = []
    for _ in range(4):
        world.step()
        credits.append(me.attack_credit)
    assert credits == pytest.approx([0.35, 0.70, 1.0, 1.0])


def test_a_champion_that_switches_from_a_camp_to_the_lane_has_no_ready_attack_and_its_blows_went_to_the_camp_alone():
    node = "blue_raptors"
    camp = next(i for i, site in enumerate(SITES) if site.node == node)
    world = calm({BLUE_CARRY: RIFT.at(node), RED_TOP: RIFT.at(node)})
    grow(world, RED_TOP, 18, 5)
    until(lambda: world.camps[camp].hp > 0, world.step)
    full = world.camps[camp].hp
    submit(world, {BLUE_CARRY: act(Kind.CAMP, "own_raptors"), RED_TOP: fight(CARRY)})
    world.step()
    me, foe = world.champions[BLUE_CARRY], world.champions[RED_TOP]
    assert full - world.camps[camp].hp == pytest.approx(2 * capability_of(me).camp_dps * TICK_S)
    assert struck(world, RED_TOP, BLUE_CARRY) and not struck(world, BLUE_CARRY, RED_TOP), "its attack is on the camp"
    assert me.attack_credit == 0.0
    left = world.camps[camp].hp
    submit(world, {BLUE_CARRY: HOLD})
    assert struck(world, BLUE_CARRY, RED_TOP) and world.camps[camp].hp == left, "holding, it hits back and leaves the camp alone"


INTENTS = {"fight": fight(SUPPORT), "siege": act(Kind.SIEGE, "mid"), "push": lane("mid", "push"), "hold": HOLD, "move": move("mid_river")}


@pytest.mark.parametrize("intent, damaged", [("fight", "champion"), ("siege", "tower"), ("push", "minions"), ("hold", "champion"), ("move", None)])
def test_on_every_tick_a_champions_attack_goes_to_one_class_of_target_and_its_intent_says_which(intent, damaged):
    """A carry stands where a tower, minions, and an enemy champion are all in its range, and the enemy champion
    fights it. Whatever loses health to the carry, nothing else does."""
    world = calm({})
    sim = world.lanes["mid"]
    tower = sim.towers[1][0]
    me, foe = world.champions[BLUE_CARRY], world.champions[RED_SUPPORT]
    me.pos, foe.pos = RIFT.lane_pos("mid", tower.s - 500.0), RIFT.lane_pos("mid", tower.s - 100.0)
    grow(world, BLUE_CARRY, 18, 5)
    grow(world, RED_SUPPORT, 18, 5)
    sim.add_minion(1, Minion.SIEGE, tower.s - 200.0, count=2, delay=10.0)
    world.step()
    submit(world, {BLUE_CARRY: INTENTS[intent], RED_SUPPORT: fight(CARRY)})
    ever = set()
    for _ in range(3):
        minions = sum(m.hp for m in sim.minions[1])
        world.step()
        hurt = {"champion": struck(world, BLUE_CARRY, RED_SUPPORT), "tower": bool(events(world, TowerDamage)),
                "minions": sum(m.hp for m in sim.minions[1]) < minions}
        now = {name for name, lost in hurt.items() if lost}
        assert now <= {damaged}
        ever |= now
        assert struck(world, RED_SUPPORT, BLUE_CARRY) and me.hp > 0
    assert ever == ({damaged} if damaged else set())


def test_minions_answer_a_call_for_help_for_two_seconds_after_the_last_hit_on_an_ally():
    def blows(attack: bool) -> tuple[list, list]:
        world = calm({BLUE_MID: mid(-100.0), RED_CARRY: mid(300.0)})
        grow(world, RED_CARRY, 18, 5)
        world.lanes["mid"].add_minion(0, Minion.CASTER, RIVER - 200.0, count=3)
        world.step()
        flags, struck_by_minions = [], []
        orders = {0: {RED_CARRY: fight(MID)}, 2: {RED_CARRY: HOLD}} if attack else {}
        for step in range(14):
            submit(world, orders.get(step, {}))
            struck_by_minions.append(any(e.seat == RED_CARRY for e in events(world, ChampionDamage)))
            carry = next(inp for inp in lane_inputs(world, "mid", harassed(world, [])) if inp.seat == RED_CARRY)
            flags.append((carry.harassing, carry.victims))
        return flags, struck_by_minions

    flags, struck_by_minions = blows(attack=True)
    assert CALL_S / TICK_S == 4
    assert flags == [(True, (BLUE_MID,))] * 5 + [(False, ())] * 9, "after its last hit on tick 1 it is harassing for four ticks more"
    assert any(struck_by_minions[:8]) and not any(struck_by_minions[10:])
    flags, struck_by_minions = blows(attack=False)
    assert flags == [(False, ())] * 14 and not any(struck_by_minions)


def test_dealing_damage_to_a_champion_takes_homeguard_away_like_taking_it():
    world = calm({})
    for _ in range(45):
        world.step()
    me, foe = world.champions[BLUE_CARRY], world.champions[RED_TOP]
    assert observe(world, BLUE_CARRY).me.homeguard > 0
    foe.pos = RIFT.advance(FOUNTAIN[0], RIFT.at("blue_base"), 300.0)
    grow(world, RED_TOP, 18, 5)
    world.step()
    submit(world, {BLUE_CARRY: fight(TOP)})
    assert struck(world, BLUE_CARRY, RED_TOP) and not struck(world, RED_TOP, BLUE_CARRY)
    seen = observe(world, BLUE_CARRY).me
    assert seen.homeguard == 0.0 and seen.homeguard_blocked_s == 7.5, "8 s from the tick of the hit"


@pytest.mark.parametrize("team", [0, 1])
def test_changing_every_field_of_every_enemy_that_a_team_does_not_see_changes_no_observation_and_no_mask(team):
    world = World(Config(), seed=1)
    for _ in range(100):
        tick(world, patient)
    seen = observe(world, team * 5).enemies
    hidden = [enemy for enemy in world.champions[(1 - team) * 5:(2 - team) * 5] if seen[enemy.role] is None]
    assert 0 < len(hidden) < 5, "the team must see some enemies and not others"
    before, enemy_before = team_knowledge(world, team), team_knowledge(world, 1 - team)
    for enemy in hidden:
        for name, value in CHANGED.items():
            assert getattr(enemy, name) != value
            setattr(enemy, name, value)
    assert team_knowledge(world, team) == before
    changed = [now != was for now, was in zip(team_knowledge(world, 1 - team), enemy_before)]
    assert all(changed), "the test must be able to see a change"


@pytest.mark.parametrize("team", [0, 1])
def test_an_enemy_that_moves_where_a_team_does_not_see_changes_nothing_the_team_knows_until_it_is_seen(team):
    world = World(Config(), seed=1)
    for _ in range(100):
        tick(world, patient)
    twin = World.restore(world.snapshot())
    seen = observe(world, team * 5).enemies
    hidden = [enemy.seat for enemy in world.champions[(1 - team) * 5:(2 - team) * 5] if seen[enemy.role] is None and enemy.hp > 0]
    assert hidden
    for seat in hidden:
        twin.champions[seat].pos = FOUNTAIN[1 - team]
    hold = [HOLD if c.hp > 0 else KEEP for c in world.champions]
    for step in range(40):
        assert team_knowledge(twin, team) == team_knowledge(world, team), f"step {step}"
        for game in (world, twin):
            game.step(hold if step == 0 else None)
    assert [c.pos for c in twin.champions] != [c.pos for c in world.champions]
    twin.champions[hidden[0]].pos = next(c.pos for c in world.champions[team * 5:team * 5 + 5] if c.hp > 0)
    for game in (world, twin):
        game.step()
    assert team_knowledge(twin, team) != team_knowledge(world, team), "sight of the moved enemy shows the change"


DUELS = {
    "duel": [("a", 0, TOP, -200.0, ("fight", "b")), ("b", 1, MID, 200.0, ("fight", "a"))],
    "kite": [("a", 0, TOP, -200.0, ("fight", "b")), ("b", 1, MID, 200.0, ("move", "top_river"))],
    "two on one": [("a", 0, TOP, -100.0, ("fight", "c")), ("b", 0, JUNGLE, -400.0, ("fight", "c")), ("c", 1, MID, 200.0, ("fight", "a"))],
    "both die on one tick": [("a", 0, TOP, -50.0, ("fight", "b")), ("b", 1, MID, 50.0, ("fight", "a"))],
    "two die on one tick": [("a", 0, TOP, -50.0, ("fight", "c")), ("b", 0, JUNGLE, -60.0, ("fight", "c")), ("c", 1, MID, 50.0, ("fight", "a")),
                            ("d", 1, CARRY, 60.0, ("fight", "a"))],
}
LOW = {"both die on one tick": {"a": 1.0, "b": 1.0}, "two die on one tick": {"a": 1.0, "c": 1.0}}
KILLS = {"duel": 1, "kite": 1, "two on one": 1, "both die on one tick": 2, "two die on one tick": 2}


def staged_fight(name: str, seat_of: dict) -> list:
    """Play a fight with each fighter in the seat it is given. Returns, per tick and fighter: its place while it
    lives, its health, gold, XP, ledger, last outcome, and the tick of that outcome."""
    cast = DUELS[name]
    world = calm({seat_of[label]: mid(offset) for label, _, _, offset, _ in cast})
    fighters = [world.champions[seat_of[label]] for label, *_ in cast]
    for (label, *_), c in zip(cast, fighters):
        c.hp = LOW.get(name, {}).get(label, c.hp)
    world.step()
    orders = {}
    for label, _, _, _, (kind, target) in cast:
        orders[seat_of[label]] = act(Kind.FIGHT, seat_of[target] % 5) if kind == "fight" else move(target)
    rows = []
    for step in range(60):
        submit(world, orders if step == 0 else {})
        rows.append([(c.pos if c.hp > 0 else None, c.hp, c.gold, c.xp, tuple(c.earned), c.outcome, c.outcome_tick) for c in fighters])
        if any(c.hp <= 0 for c in fighters):
            break
    return rows


@pytest.mark.parametrize("name", DUELS)
def test_exchanging_the_seats_of_the_two_teams_changes_no_place_health_death_tick_gold_or_xp(name):
    as_cast = {label: side * 5 + role for label, side, role, _, _ in DUELS[name]}
    exchanged = {label: (1 - side) * 5 + role for label, side, role, _, _ in DUELS[name]}
    rows = staged_fight(name, as_cast)
    assert rows == staged_fight(name, exchanged)
    paid = [row[4][Income.KILL] for row in rows[-1]]
    assert sum(amount > 0 for amount in paid) == KILLS[name] and len(rows) < 60


@pytest.fixture
def one_profile(monkeypatch):
    """Every role plays the top laner's numbers, so that two seats of one team can be exchanged."""
    capability.cache_clear()
    for role in ROLES:
        monkeypatch.setitem(PROFILES, role, PROFILES["top"])
        monkeypatch.setitem(champions.PROGRESSIONS, role, champions.PROGRESSIONS["top"])
    yield
    capability.cache_clear()


@pytest.mark.parametrize("name", DUELS)
def test_exchanging_seats_inside_a_team_changes_no_place_health_death_tick_gold_or_xp(name, one_profile):
    as_cast = {label: side * 5 + role for label, side, role, _, _ in DUELS[name]}
    turned = {TOP: JUNGLE, JUNGLE: CARRY, MID: TOP, CARRY: MID}
    exchanged = {label: side * 5 + turned[role] for label, side, role, _, _ in DUELS[name]}
    assert sorted(as_cast.values()) != sorted(exchanged.values())
    rows = staged_fight(name, as_cast)
    assert rows == staged_fight(name, exchanged)
    assert any(row[0] is None for row in rows[-1])


def test_when_one_champion_of_each_team_dies_on_one_tick_both_kills_and_both_assists_are_paid_and_one_first_blood():
    rows = staged_fight("two die on one tick", {label: side * 5 + role for label, side, role, _, _ in DUELS["two die on one tick"]})
    a, b, c, d = rows[-1]
    assert a[0] is None and c[0] is None and b[0] is not None and d[0] is not None and len(rows) == 1
    kill_gold = sorted(row[4][Income.KILL] + row[4][Income.ASSIST] for row in (a, b, c, d))
    assert kill_gold == [150.0, 150.0, 300.0, 400.0], "two kills, two assists, and one first blood"
    assert [row[3] for row in (a, b, c, d)] == pytest.approx([SHARED_XP[0] / 2] * 4)


def test_new_combat_state_is_in_the_digest_and_a_snapshot_taken_in_a_fight_replays_every_digest():
    world = World(Config(), seed=3)
    for _ in range(96):
        tick(world, random_legal)
    while not events(world, Hit) or world.tick % 4:
        tick(world, random_legal)
    snapshot = world.snapshot()
    first, ended = play(world, random_legal, 400)
    again, _ = play(World.restore(snapshot), random_legal, 400)
    assert first == again and len(set(first)) == 400
    assert ended["DIED"] > 0
    fresh = World.restore(snapshot)
    base = fresh.digest()
    fresh.memory[0].enemies[MID].seen_tick += 1
    seen = fresh.digest()
    fresh.memory[1].enemies[TOP].hp += 1.0
    remembered = fresh.digest()
    fresh.lanes["bot"].towers[0][1].heat += 1
    heated = fresh.digest()
    fresh.lanes["top"].towers[1][2].heat_at = 3.5
    assert len({base, seen, remembered, heated, fresh.digest()}) == 5


def test_a_game_of_random_legal_actions_fights_sieges_kills_and_loses_targets_with_no_invariant_failure():
    world = World(Config(), seed=1)
    chosen, happened, ended = Counter(), Counter(), Counter()
    for _ in range(1200):
        actions = tick(world, random_legal, check=True)
        chosen.update(ACTIONS[action].kind for action in actions or ())
        happened.update(type(e).__name__ for _, e in world.events)
        ended += ended_now(world)
    assert chosen[Kind.FIGHT] > 20 and chosen[Kind.SIEGE] > 20
    assert all(happened[name] > 0 for name in ("Hit", "Kill", "TowerShot", "TowerDamage"))
    assert {"KILLED", "DIED"} <= set(ended)
    kills = sum(c.earned[Income.KILL] > 0 for c in world.champions)
    assert kills > 0 and all(c.gold >= 0 for c in world.champions)
