import pytest

from riftgame.champions import (FOUNTAIN, HOLD, OUTER_TOWER, PROFILES, RECALL, RIFT, ROLES, SEATS, TEAMS, Capability,
                                Income, Outcome, capability_of, pay)
from riftgame.ruleset import load
from riftgame.vision import observe
from riftgame.world import Config, InvariantError, World, check_invariants
from worlds import (BLUE_CARRY, BLUE_JUNGLE, BLUE_MID, BLUE_SUPPORT, BLUE_TOP, EVERY_TICK, RED_CARRY, RED_JUNGLE, RED_MID,
                    RED_TOP, lane_place, move, staged, submit, until)

TICK_S = EVERY_TICK.tick_s
# The reference values, written out so that the tests do not read them from the code they test.
RECALL_S = 8.5
FOUNTAIN_RADIUS, FOUNTAIN_HP_PER_S, FOUNTAIN_MANA_PER_S = 1100.0, 0.08, 0.10
BOOTS_PRICES, BOOTS_SPEEDS = (300, 800), (25, 45)
HOMEGUARD_FROM_S, HOMEGUARD_FULL, HOMEGUARD_DECAYED, HOMEGUARD_DECAY_S = 20.0, 0.80, 0.40, 4.0
HOMEGUARD_ENDS_BEFORE_TOWER, HOMEGUARD_BLOCK_S = 500.0, 8.0
LISTED = load("patch_26_22_m8")["upgrades"]
PRICES = {role: [*BOOTS_PRICES, *(entry["cost"] for entry in LISTED[role])] for role in ROLES}
TRIPS = [(BLUE_TOP, "top"), (RED_TOP, "top"), (BLUE_MID, "mid"), (RED_MID, "mid"), (BLUE_CARRY, "bot"), (RED_CARRY, "bot")]
BEYOND_THE_TOWER = {"top": "top_corner", "mid": "mid_river", "bot": "bot_corner"}


def idle(world: World, seconds: float) -> None:
    for _ in range(round(seconds / world.config.tick_s)):
        world.step()


def pace(world: World, seat: int, orders: dict | None = None) -> float:
    """Advance one tick. Returns the seat's walk on it as a multiple of the walk that its own move speed gives."""
    me = world.champions[seat]
    was, own = me.pos, capability_of(me).move_speed * world.config.tick_s
    submit(world, orders or {})
    return RIFT.distance(was, me.pos) / own


def out(world: World, seat: int) -> float:
    """How far a champion has walked from its fountain."""
    return RIFT.distance(FOUNTAIN[seat // 5], world.champions[seat].pos)


def view(world: World, seat: int):
    return observe(world, seat).me


def with_upgrades(role: int, count: int) -> Capability:
    """A level 1 profile with its first `count` upgrades, added up from the ruleset files."""
    can = PROFILES[ROLES[role]]._asdict()
    can["move_speed"] += (0, *BOOTS_SPEEDS)[min(count, 2)]
    for entry in LISTED[ROLES[role]][:max(0, count - 2)]:
        for name, amount in entry["adds"].items():
            can[name] += amount
    return Capability(**can)


def recall_ticks(world: World, seat: int) -> int:
    """Recall the seat from where it stands. Returns the ticks until it is on its fountain."""
    me, began = world.champions[seat], world.tick
    submit(world, {seat: RECALL})
    until(lambda: me.outcome is Outcome.RECALLED and me.outcome_tick >= began, world.step)
    return world.tick - began


def walk_ticks(world: World, seat: int, lane: str, far: float) -> int:
    """Walk the seat out along `lane`. Returns the ticks until it is `far` units from its fountain."""
    began = world.tick
    submit(world, {seat: move(BEYOND_THE_TOWER[lane])})
    until(lambda: out(world, seat) >= far, world.step)
    return world.tick - began


def walk_s(route: float, speed: float, homeguard: bool) -> float:
    """Seconds from the fountain to a point `route` units out that lies past the Homeguard endpoint. It is distance
    over speed, with the Homeguard rule on top in continuous time."""
    if not homeguard:
        return route / speed
    on_fountain_s = FOUNTAIN_RADIUS / ((1 + HOMEGUARD_FULL) * speed)
    decay_units = speed * HOMEGUARD_DECAY_S * (1 + (HOMEGUARD_FULL + HOMEGUARD_DECAYED) / 2)
    decayed_units = route - HOMEGUARD_ENDS_BEFORE_TOWER - FOUNTAIN_RADIUS - decay_units
    assert decayed_units > 0
    return on_fountain_s + HOMEGUARD_DECAY_S + decayed_units / ((1 + HOMEGUARD_DECAYED) * speed) + HOMEGUARD_ENDS_BEFORE_TOWER / speed


CANCELS = {"damage": (lambda world: world.damage_champion(BLUE_TOP, 5.0), Outcome.INTERRUPTED),
           "a new action": (lambda world: submit(world, {BLUE_TOP: HOLD}), Outcome.NONE)}


@pytest.mark.parametrize("cancel, outcome", CANCELS.values(), ids=CANCELS.keys())
def test_a_cancelled_recall_loses_all_progress_and_a_restarted_recall_takes_the_full_time_again(cancel, outcome):
    start = lane_place(0, "top", 9000.0)
    world = staged({BLUE_TOP: start})
    me = world.champions[BLUE_TOP]
    submit(world, {BLUE_TOP: RECALL})
    idle(world, RECALL_S - 2 * TICK_S)
    assert view(world, BLUE_TOP).channel_s == RECALL_S - TICK_S, "one tick short of the fountain"
    cancel(world)
    assert (view(world, BLUE_TOP).channel_s, me.intent, me.outcome, me.pos) == (0.0, HOLD, outcome, start)
    idle(world, 3.0)
    assert me.pos == start
    restarted = world.tick

    def channel():
        assert me.pos == start
        world.step()

    submit(world, {BLUE_TOP: RECALL})
    until(lambda: me.outcome is Outcome.RECALLED, channel)
    assert (world.tick - restarted) * TICK_S == RECALL_S and me.pos == FOUNTAIN[0]


@pytest.mark.parametrize("seat", [BLUE_MID, RED_CARRY])
@pytest.mark.parametrize("tick_s", [0.5, 0.25])
def test_the_fountain_restores_8_percent_of_health_and_10_percent_of_mana_per_second_up_to_the_maximum(seat, tick_s):
    world = World(Config(tick_s=tick_s, decision_ticks=1))
    me = world.champions[seat]
    can = capability_of(me)
    hp, mana = 0.1 * can.max_hp, 0.2 * can.max_mana
    me.hp, me.mana = hp, mana
    for ticks in range(1, round(13.0 / tick_s) + 1):
        world.step()
        assert me.hp == pytest.approx(min(can.max_hp, hp + ticks * tick_s * (FOUNTAIN_HP_PER_S * can.max_hp + can.hp_regen)))
        assert me.mana == pytest.approx(min(can.max_mana, mana + ticks * tick_s * (FOUNTAIN_MANA_PER_S * can.max_mana + can.mana_regen)))
    assert (me.hp, me.mana) == (can.max_hp, can.max_mana)


def test_the_fountain_restores_nothing_beyond_its_radius():
    edge = RIFT.at("blue_base")
    world = staged({BLUE_TOP: RIFT.advance(FOUNTAIN[0], edge, FOUNTAIN_RADIUS - 1.0), BLUE_MID: RIFT.advance(FOUNTAIN[0], edge, FOUNTAIN_RADIUS + 1.0)})
    inside, outside = world.champions[BLUE_TOP], world.champions[BLUE_MID]
    for c in (inside, outside):
        c.hp, c.mana = 100.0, 50.0
    world.step()
    assert inside.hp == pytest.approx(100.0 + TICK_S * (FOUNTAIN_HP_PER_S * capability_of(inside).max_hp + capability_of(inside).hp_regen))
    assert inside.mana == pytest.approx(50.0 + TICK_S * (FOUNTAIN_MANA_PER_S * capability_of(inside).max_mana + capability_of(inside).mana_regen))
    assert outside.hp == pytest.approx(100.0 + TICK_S * capability_of(outside).hp_regen)
    assert outside.mana == pytest.approx(50.0 + TICK_S * capability_of(outside).mana_regen)


def test_the_fountain_restores_nothing_to_a_dead_champion():
    world = World(EVERY_TICK)
    me = world.champions[BLUE_CARRY]
    world.damage_champion(BLUE_CARRY, 10_000.0)
    world.step()

    def lie_dead():
        assert me.pos == FOUNTAIN[0] and me.hp == 0.0
        world.step()

    assert until(lambda: me.hp > 0, lie_dead) * TICK_S == 10.0, "the death timer of level 1"


def test_a_champion_starts_with_boots_bought_from_its_starting_gold():
    for c in World(Config(tick_s=0.5, decision_ticks=4)).champions:
        assert (c.upgrades, c.gold, c.earned[Income.STARTING]) == (1, 500.0 - BOOTS_PRICES[0], 500.0)
        assert capability_of(c) == with_upgrades(c.role, 1)
        assert capability_of(c).move_speed == PROFILES[ROLES[c.role]].move_speed + 25


def test_the_second_boots_step_costs_800_and_brings_the_speed_bonus_to_45():
    world = World(EVERY_TICK)
    me = world.champions[BLUE_MID]
    pay(me, Income.MINION, 599.0)
    world.step()
    assert (me.upgrades, me.gold) == (1, 799.0), "one gold short"
    pay(me, Income.MINION, 1.0)
    world.step()
    assert (me.upgrades, me.gold) == (2, 0.0)
    assert capability_of(me).move_speed == PROFILES["mid"].move_speed + 45


@pytest.mark.parametrize("seat", SEATS)
def test_a_champion_buys_the_entries_of_its_progression_in_order_and_several_in_one_tick(seat):
    world = World(EVERY_TICK)
    me = world.champions[seat]
    prices = PRICES[ROLES[me.role]]
    assert len(prices) == 5 and all(price > 0 for price in prices)
    pay(me, Income.MINION, sum(prices[1:4]) + 50.0 - me.gold)
    world.step()
    assert me.upgrades == 4 and 50.0 <= me.gold < 51.0, "the support item pays a little on every tick"
    assert me.gold == pytest.approx(sum(me.earned) - sum(prices[:4]))
    assert capability_of(me) == pytest.approx(with_upgrades(me.role, 4))
    pay(me, Income.MINION, prices[4] - 50.0)
    world.step()
    assert me.upgrades == 5 and me.gold == pytest.approx(sum(me.earned) - sum(prices)) and me.gold < 1.0
    assert capability_of(me) == pytest.approx(with_upgrades(me.role, 5))
    pay(me, Income.MINION, 5000.0)
    world.step()
    assert me.upgrades == 5 and me.gold >= 5000.0, "nothing is left to buy"


def test_the_five_progressions_differ_and_every_entry_changes_a_capability():
    full = [with_upgrades(role, 5) for role in range(len(ROLES))]
    gains = [tuple(after - before for after, before in zip(can, PROFILES[role])) for can, role in zip(full, ROLES)]
    assert len(set(gains)) == len(ROLES)
    for role in range(len(ROLES)):
        steps = [with_upgrades(role, count) for count in range(6)]
        assert all(later != earlier and all(a >= b for a, b in zip(later, earlier)) for earlier, later in zip(steps, steps[1:]))


def test_a_champion_cannot_skip_an_entry_it_cannot_afford_for_a_cheaper_one_further_on():
    world = World(EVERY_TICK)
    me = world.champions[BLUE_SUPPORT]
    prices = PRICES["support"]
    assert prices[2] < prices[1]
    pay(me, Income.MINION, prices[2] - me.gold)
    world.step()
    assert me.upgrades == 1 and me.gold >= prices[2]


@pytest.mark.parametrize("seat", [BLUE_MID, RED_MID])
def test_unspent_gold_changes_no_capability_until_the_champion_stands_on_its_fountain(seat):
    world = staged({seat: lane_place(seat // 5, "mid", 5000.0)})
    me = world.champions[seat]
    poor = capability_of(me)
    pay(me, Income.MINION, 10_000.0)
    assert capability_of(me) == poor
    for _ in range(20):
        world.step()
        assert (me.upgrades, me.gold, capability_of(me)) == (1, 10_200.0, poor)
    submit(world, {seat: RECALL})
    until(lambda: me.outcome is Outcome.RECALLED, world.step)
    assert (me.upgrades, me.gold) == (5, pytest.approx(10_500.0 - sum(PRICES["mid"])))
    assert capability_of(me) == pytest.approx(with_upgrades(me.role, 5)) and capability_of(me) != poor


def test_the_shop_reaches_as_far_as_the_fountain_and_no_further():
    edge = RIFT.at("red_base")
    world = staged({RED_TOP: RIFT.advance(FOUNTAIN[1], edge, FOUNTAIN_RADIUS - 1.0), RED_MID: RIFT.advance(FOUNTAIN[1], edge, FOUNTAIN_RADIUS + 1.0)})
    inside, outside = world.champions[RED_TOP], world.champions[RED_MID]
    for c in (inside, outside):
        pay(c, Income.MINION, 10_000.0)
    for _ in range(10):
        world.step()
    assert (inside.upgrades, outside.upgrades) == (5, 1)


def test_a_dead_champion_shops_and_returns_at_the_full_health_of_what_it_bought():
    world = staged({BLUE_TOP: lane_place(0, "top", 9000.0)})
    me = world.champions[BLUE_TOP]
    pay(me, Income.MINION, PRICES["top"][1] + PRICES["top"][2] - me.gold)
    world.damage_champion(BLUE_TOP, 10_000.0)
    world.step()
    assert (me.hp, me.upgrades, me.gold) == (0.0, 3, pytest.approx(0.0))
    until(lambda: me.hp > 0, world.step)
    assert me.hp == with_upgrades(0, 3).max_hp > with_upgrades(0, 1).max_hp


def test_gold_is_the_ledger_less_the_price_of_the_upgrades_through_a_recall_with_purchases():
    world = staged({BLUE_TOP: OUTER_TOWER[0]["top"]})
    me = world.champions[BLUE_TOP]
    pay(me, Income.MINION, 2000.0)
    submit(world, {BLUE_TOP: RECALL})
    for _ in range(160):
        world.step()
        check_invariants(world)
        assert me.gold >= 0
    assert me.upgrades == 3 and me.earned[Income.PASSIVE] > 0
    assert me.gold == pytest.approx(sum(me.earned) - sum(PRICES["top"][:3]))


def unpaid_upgrade(c):
    c.upgrades += 1


def gold_from_nowhere(c):
    c.gold += 1.0


def lost_ledger_entry(c):
    c.earned[Income.STARTING] -= 1.0


@pytest.mark.parametrize("change", [unpaid_upgrade, gold_from_nowhere, lost_ledger_entry])
def test_the_checker_raises_when_gold_is_not_the_ledger_less_the_price_of_the_upgrades(change):
    world = World(Config(tick_s=0.5, decision_ticks=4))
    check_invariants(world)
    change(world.champions[RED_MID])
    with pytest.raises(InvariantError):
        check_invariants(world)


def test_homeguard_starts_at_20_s_and_only_for_a_champion_on_its_fountain():
    world = staged({BLUE_MID: RIFT.advance(FOUNTAIN[0], RIFT.at("blue_base"), FOUNTAIN_RADIUS + 50.0)})
    idle(world, HOMEGUARD_FROM_S - 2 * TICK_S)
    orders = {BLUE_TOP: move("own_top_t1"), BLUE_MID: move("own_mid_t1")}
    for early in range(2):
        assert view(world, BLUE_TOP).homeguard == view(world, BLUE_CARRY).homeguard == 0.0
        assert pace(world, BLUE_TOP, orders if early == 0 else None) == pytest.approx(1.0)
    assert world.tick * TICK_S == HOMEGUARD_FROM_S and out(world, BLUE_TOP) < FOUNTAIN_RADIUS
    assert view(world, BLUE_TOP).homeguard == view(world, BLUE_CARRY).homeguard == HOMEGUARD_FULL
    assert observe(world, BLUE_CARRY).mates[0].homeguard == HOMEGUARD_FULL, "a teammate sees it"
    assert view(world, BLUE_MID).homeguard == 0.0
    walked = out(world, BLUE_MID)
    assert pace(world, BLUE_TOP) == pytest.approx(1 + HOMEGUARD_FULL)
    assert out(world, BLUE_MID) - walked == pytest.approx(capability_of(world.champions[BLUE_MID]).move_speed * TICK_S)


@pytest.mark.parametrize("seat", [BLUE_TOP, RED_MID])
def test_homeguard_decays_in_a_straight_line_to_40_percent_over_the_4_s_after_the_champion_leaves_its_fountain(seat):
    world = World(EVERY_TICK)
    idle(world, 25.0)
    order = {seat: move("enemy_base")}
    on_fountain, off_fountain = [], []
    for _ in range(24):
        began_on_fountain = out(world, seat) <= FOUNTAIN_RADIUS
        seen = view(world, seat).homeguard
        bonus = pace(world, seat, order) - 1
        assert seen == pytest.approx(bonus), "the observation shows the bonus of the coming move"
        (on_fountain if began_on_fountain else off_fountain).append(bonus)
        order = None
    assert len(on_fountain) >= 3 and on_fountain == pytest.approx([HOMEGUARD_FULL] * len(on_fountain))
    decay_ticks = round(HOMEGUARD_DECAY_S / TICK_S)
    slope = (HOMEGUARD_FULL - HOMEGUARD_DECAYED) / HOMEGUARD_DECAY_S
    assert off_fountain[:decay_ticks] == pytest.approx([HOMEGUARD_FULL - slope * (n + 0.5) * TICK_S for n in range(decay_ticks)])
    assert sum(off_fountain[:decay_ticks]) * TICK_S == pytest.approx(HOMEGUARD_DECAY_S * (HOMEGUARD_FULL + HOMEGUARD_DECAYED) / 2)
    assert len(off_fountain) > decay_ticks + 5
    assert off_fountain[decay_ticks:] == pytest.approx([HOMEGUARD_DECAYED] * (len(off_fountain) - decay_ticks))


@pytest.mark.parametrize("seat, lane", TRIPS)
def test_homeguard_ends_500_units_before_the_outer_tower_of_the_lane_and_returns_only_on_the_fountain(seat, lane):
    world = World(EVERY_TICK)
    idle(world, 25.0)
    home, tower, beyond = FOUNTAIN[seat // 5], OUTER_TOWER[seat // 5][lane], move(BEYOND_THE_TOWER[lane])
    end = RIFT.distance(home, tower) - HOMEGUARD_ENDS_BEFORE_TOWER
    assert RIFT.distance(home, RIFT.at(BEYOND_THE_TOWER[lane])) == pytest.approx(RIFT.distance(home, tower) + RIFT.distance(tower, RIFT.at(BEYOND_THE_TOWER[lane])))
    inside, outside = [], []
    order = {seat: beyond}
    while out(world, seat) < end + 800.0:
        began = out(world, seat)
        (inside if began < end else outside).append(pace(world, seat, order))
        order = None
    assert inside[-5:] == pytest.approx([1 + HOMEGUARD_DECAYED] * 5) and min(inside) >= 1 + HOMEGUARD_DECAYED - 1e-9
    assert len(outside) >= 3 and outside == pytest.approx([1.0] * len(outside))
    assert view(world, seat).homeguard == 0.0
    order = {seat: move("own_fountain")}
    while out(world, seat) > FOUNTAIN_RADIUS:
        assert pace(world, seat, order) == pytest.approx(1.0), "walking back inside the endpoint does not return it"
        order = None
    assert pace(world, seat) == pytest.approx(1 + HOMEGUARD_FULL)


def test_damage_ends_homeguard_at_once_and_it_does_not_return_on_the_way():
    world = World(EVERY_TICK)
    idle(world, 25.0)
    assert pace(world, BLUE_TOP, {BLUE_TOP: move("own_top_t1")}) == pytest.approx(1 + HOMEGUARD_FULL)
    for _ in range(6):
        assert pace(world, BLUE_TOP) > 1 + HOMEGUARD_DECAYED
    world.damage_champion(BLUE_TOP, 1.0)
    assert view(world, BLUE_TOP).homeguard == 0.0
    for _ in range(30):
        assert pace(world, BLUE_TOP) == pytest.approx(1.0)
    assert out(world, BLUE_TOP) < RIFT.distance(FOUNTAIN[0], OUTER_TOWER[0]["top"]) - HOMEGUARD_ENDS_BEFORE_TOWER


def test_after_damage_homeguard_stays_away_for_8_s_even_on_the_fountain():
    world = World(EVERY_TICK)
    idle(world, 25.0)
    assert (view(world, RED_TOP).homeguard, view(world, RED_TOP).homeguard_blocked_s) == (HOMEGUARD_FULL, 0.0)
    world.damage_champion(RED_TOP, 1.0)
    last = round(HOMEGUARD_BLOCK_S / TICK_S) - 1
    for ticks in range(last + 1):
        assert (view(world, RED_TOP).homeguard, view(world, RED_TOP).homeguard_blocked_s) == (0.0, HOMEGUARD_BLOCK_S - ticks * TICK_S)
        assert view(world, RED_MID).homeguard == HOMEGUARD_FULL, "a teammate keeps its own"
        walked = pace(world, RED_TOP, {RED_TOP: move("own_top_t1")} if ticks == last else None)
    assert walked == pytest.approx(1.0), "it sets out half a second early, at its own speed"
    assert (view(world, RED_TOP).homeguard, view(world, RED_TOP).homeguard_blocked_s) == (HOMEGUARD_FULL, 0.0)
    assert out(world, RED_TOP) < FOUNTAIN_RADIUS and pace(world, RED_TOP) == pytest.approx(1 + HOMEGUARD_FULL)


def test_a_recall_on_the_fountain_does_not_lift_the_block_after_damage():
    world = World(EVERY_TICK)
    idle(world, 25.0)
    world.damage_champion(BLUE_MID, 1.0)
    world.step()
    submit(world, {BLUE_MID: RECALL})
    assert world.champions[BLUE_MID].outcome is Outcome.RECALLED, "on the fountain a recall completes at once"
    assert view(world, BLUE_MID).homeguard == 0.0 and view(world, BLUE_MID).homeguard_blocked_s > 6.0


@pytest.mark.parametrize("seat", [BLUE_JUNGLE, RED_JUNGLE])
def test_homeguard_ends_when_the_champion_leaves_the_lane_for_the_jungle_and_does_not_return_on_the_lane(seat):
    world = World(EVERY_TICK)
    idle(world, 25.0)
    team = seat // 5
    home, camp = FOUNTAIN[team], RIFT.at(f"{TEAMS[team]}_wolves")
    gates = [RIFT.at(f"{TEAMS[team]}_{lane}_t2") for lane in ("top", "mid")]
    gate = min(gates, key=lambda node: RIFT.distance(home, node) + RIFT.distance(node, camp))
    assert RIFT.distance(home, camp) == pytest.approx(RIFT.distance(home, gate) + RIFT.distance(gate, camp)), "the walk leaves a lane at the gate"
    on_lane, in_jungle = [], []
    order = {seat: move("own_wolves")}
    while RIFT.distance(world.champions[seat].pos, camp) > 400.0:
        began = out(world, seat)
        (on_lane if began < RIFT.distance(home, gate) else in_jungle).append(pace(world, seat, order))
        order = None
    assert on_lane[-3:] == pytest.approx([1 + HOMEGUARD_DECAYED] * 3)
    assert len(in_jungle) >= 3 and in_jungle == pytest.approx([1.0] * len(in_jungle))
    order = {seat: move("own_base")}
    for _ in range(12):
        assert pace(world, seat, order) == pytest.approx(1.0)
        order = None
    assert out(world, seat) < RIFT.distance(home, gate), "back on the lane, inside the endpoint"


def test_a_champion_that_respawns_has_homeguard_like_anyone_on_the_fountain():
    world = staged({BLUE_TOP: lane_place(0, "top", 9000.0)})
    idle(world, 25.0)
    me = world.champions[BLUE_TOP]
    world.damage_champion(BLUE_TOP, 10_000.0)

    def lie_dead():
        assert view(world, BLUE_TOP).homeguard == 0.0
        world.step()

    until(lambda: me.hp > 0, lie_dead)
    assert view(world, BLUE_TOP).homeguard == HOMEGUARD_FULL
    assert pace(world, BLUE_TOP, {BLUE_TOP: move("own_top_t1")}) == pytest.approx(1 + HOMEGUARD_FULL)


@pytest.mark.parametrize("seat, lane", TRIPS)
@pytest.mark.parametrize("begin_s", [0.0, 30.0], ids=["before homeguard", "with homeguard"])
def test_the_round_trip_from_an_outer_tower_takes_the_recall_and_the_walk_that_route_and_speed_give_within_one_tick(seat, lane, begin_s):
    tower = OUTER_TOWER[seat // 5][lane]
    world = staged({seat: tower})
    me = world.champions[seat]
    pay(me, Income.MINION, BOOTS_PRICES[1] - me.gold)
    idle(world, begin_s)
    route = out(world, seat)
    recall_s = recall_ticks(world, seat) * TICK_S
    assert me.upgrades == 2 and me.gold == pytest.approx(0.0), "it bought the second boots on the fountain"
    trip_s = recall_s + walk_ticks(world, seat, lane, route) * TICK_S
    speed = PROFILES[ROLES[me.role]].move_speed + BOOTS_SPEEDS[1]
    homeguard = begin_s + RECALL_S >= HOMEGUARD_FROM_S
    assert recall_s == RECALL_S
    assert abs(trip_s - (RECALL_S + walk_s(route, speed, homeguard))) <= TICK_S


def test_a_world_restored_in_the_middle_of_a_homeguard_walk_replays_the_same_digests():
    world = World(EVERY_TICK)
    idle(world, 25.0)
    submit(world, {seat: move("enemy_base") for seat in (BLUE_TOP, BLUE_MID, RED_TOP)})
    idle(world, 3.0)
    world.damage_champion(BLUE_MID, 1.0)
    world.damage_champion(RED_CARRY, 1.0)
    saved = world.snapshot()
    first = []
    for _ in range(60):
        world.step()
        first.append((world.digest(), [c.pos for c in world.champions]))
    again = World.restore(saved)
    for expected in first:
        again.step()
        assert (again.digest(), [c.pos for c in again.champions]) == expected
