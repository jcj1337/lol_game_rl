from collections import Counter

import pytest

from riftgame.champions import (ACTIONS, HOLD, HOME, KEEP, LANES, MODES, RECALL, RIFT, ROLES, SEATS, STANDS, Duty, Kind, Outcome,
                                on_lane, speed_of)
from riftgame.harness import roamer, tick
from riftgame.vision import legal_mask, observe
from riftgame.world import Config, World
from worlds import (BLUE_CARRY, BLUE_JUNGLE, BLUE_MID, BLUE_SUPPORT, BLUE_TOP, RED_CARRY, RED_JUNGLE, RED_MID,
                    RED_SUPPORT, RED_TOP, act, hazard, lane_place, move, staged, submit, until)

LANERS = [seat for seat in SEATS if HOME[seat % 5] is not None]
JUNGLERS = [BLUE_JUNGLE, RED_JUNGLE]
OPEN_KINDS = (Kind.HOLD, Kind.RECALL, Kind.MOVE, Kind.CAMP, Kind.SIEGE, Kind.WARD)


def open_actions(role: int, lanes) -> set[int]:
    """Every action that needs no enemy in view, with LANE limited to `lanes`, for a champion that holds and has
    a ward charge."""
    return {KEEP} | {i for i, a in enumerate(ACTIONS)
                     if a.kind in OPEN_KINDS or (a.kind is Kind.LANE and a.target[0] in lanes)
                     or (a.kind is Kind.FOLLOW and a.target != role)}


def return_actions(lane: str) -> set[int]:
    middle = {"top": "top_corner", "mid": "mid_river", "bot": "bot_corner"}[lane]
    nodes = ("own_fountain", "own_base", f"own_{lane}_exit", f"own_{lane}_t2", f"own_{lane}_t1", middle,
             f"enemy_{lane}_t1", f"enemy_{lane}_t2", f"enemy_{lane}_exit")
    return {RECALL} | {act(Kind.LANE, (lane, mode, stand)) for mode in MODES for stand in STANDS} | {move(node) for node in nodes}


def legal(world: World, seat: int) -> set[int]:
    return {i for i, ok in enumerate(legal_mask(observe(world, seat))) if ok}


def roam_soak(config: Config, seconds: float, deaths_per_game: float = 3.0, seed: int = 8) -> list[dict]:
    """Ten champions under the roamer, measured through their observations and positions.

    `always_open` says that the role never took an action away: at every decision the champion could choose
    everything that a champion with allowance left may choose.
    """
    world = World(config, seed)
    tick_s, ticks = config.tick_s, round(seconds / config.tick_s)
    rows = [{"roamed_s": 0.0, "stretch_s": 0.0, "longest_stretch_s": 0.0, "spent_at_s": None, "roamed_after_s": 0.0,
             "lowest_allowance_s": config.roam_cap_s, "off_lane_s": 0.0, "largest_step_over_speed": 0.0, "jumps": Counter(),
             "always_open": True, "sent_home": 0} for _ in SEATS]
    for _ in range(ticks):
        hazard(world, deaths_per_game / ticks, 1e6)
        stood = [(c.pos, speed_of(world, c)) for c in world.champions]
        if world.tick % config.decision_ticks == 0:
            for seat, row in enumerate(rows):
                if world.champions[seat].hp > 0:
                    lanes = [HOME[seat % 5]] if HOME[seat % 5] else LANES
                    row["always_open"] &= open_actions(seat % 5, lanes) - {KEEP} <= legal(world, seat)
        actions = tick(world, roamer, check=True)
        for seat, (c, row) in enumerate(zip(world.champions, rows)):
            me = observe(world, seat).me
            roaming = me.duty is Duty.ROAMING
            row["roamed_s"] += tick_s * roaming
            row["stretch_s"] = 0.0 if me.duty is Duty.ON_LANE else row["stretch_s"] + tick_s * roaming
            row["longest_stretch_s"] = max(row["longest_stretch_s"], row["stretch_s"])
            row["lowest_allowance_s"] = min(row["lowest_allowance_s"], me.allowance)
            if row["spent_at_s"] is not None:
                row["roamed_after_s"] += tick_s * roaming
            elif me.allowance <= 0:
                row["spent_at_s"] = world.tick * tick_s
            if HOME[seat % 5] and c.hp > 0 and not on_lane(HOME[seat % 5], c.pos):
                row["off_lane_s"] += tick_s
            if actions and ACTIONS[actions[seat]].kind is Kind.LANE:
                row["sent_home"] += 1
            if c.outcome_tick == world.tick - 1 and c.outcome in (Outcome.DIED, Outcome.RECALLED):
                row["jumps"][c.outcome.name] += 1
            else:
                was, speed = stood[seat]
                step = RIFT.distance(was, c.pos) / (speed * tick_s)
                row["largest_step_over_speed"] = max(row["largest_step_over_speed"], step)
    for row in rows:
        row["window_s"] = None if row["spent_at_s"] is None else seconds - row["spent_at_s"]
    return rows


CLOCKS = {"tick 0.5 s, decision 2 s": Config(tick_s=0.5, decision_ticks=4), "tick 1 s, decision 5 s": Config(tick_s=1.0, decision_ticks=5)}
GAME_S = 840.0


@pytest.fixture(scope="module", params=CLOCKS.values(), ids=CLOCKS.keys())
def soak(request):
    config = request.param
    return config, config.decision_ticks * config.tick_s, roam_soak(config, GAME_S)


def test_no_laner_roams_longer_than_the_cap_plus_one_decision_interval_at_a_stretch(soak):
    config, decision_s, rows = soak
    longest = [rows[seat]["longest_stretch_s"] for seat in LANERS]
    assert max(longest) <= config.roam_cap_s + decision_s
    assert max(longest) >= config.roam_cap_s, "some laner must use its whole allowance, or the cap was never tested"
    assert min(rows[seat]["lowest_allowance_s"] for seat in LANERS) > -decision_s


def test_a_laners_roaming_share_after_its_first_allowance_is_spent_stays_within_the_refill_bound(soak):
    config, decision_s, rows = soak
    limit = config.roam_refill / (1 + config.roam_refill)
    assert limit == 0.2
    for seat in LANERS:
        row = rows[seat]
        assert row["window_s"] >= 600, "the share is measured over at least ten game minutes"
        assert row["roamed_after_s"] <= limit * row["window_s"] + decision_s
        assert row["roamed_after_s"] >= 0.1 * row["window_s"], "the policy must press on the bound"
        assert row["sent_home"] > 0 and not row["always_open"]


def test_junglers_are_never_restricted(soak):
    config, _, rows = soak
    for seat in JUNGLERS:
        assert rows[seat]["always_open"] and rows[seat]["sent_home"] == 0
        assert rows[seat]["lowest_allowance_s"] == config.roam_cap_s and rows[seat]["roamed_s"] == 0.0


def test_no_champion_moves_faster_than_its_speed_except_when_it_dies(soak):
    _, _, rows = soak
    assert all(row["largest_step_over_speed"] <= 1 + 1e-9 for row in rows)
    assert max(row["largest_step_over_speed"] for row in rows) > 0.99
    assert sum(row["jumps"]["DIED"] for row in rows) > 0, "the exception must occur in the run"


def test_with_the_restriction_switched_off_the_same_policy_is_never_restricted():
    config = Config(tick_s=0.5, decision_ticks=4, roam_restricted=False)
    rows, restricted = roam_soak(config, 420.0), roam_soak(Config(tick_s=0.5, decision_ticks=4), 420.0)
    for seat in LANERS:
        row = rows[seat]
        assert row["always_open"] and row["sent_home"] == 0 and row["lowest_allowance_s"] == config.roam_cap_s
        assert row["off_lane_s"] > restricted[seat]["off_lane_s"], "the same game with the restriction keeps it home longer"
        assert restricted[seat]["sent_home"] > 0 and not restricted[seat]["always_open"]


def test_with_the_restriction_switched_off_a_laner_keeps_its_open_mask_however_long_it_stays_away():
    world = staged({BLUE_MID: RIFT.at("top_river")}, Config(tick_s=0.5, decision_ticks=1, roam_restricted=False))
    for _ in range(400):
        world.step()
    seen = observe(world, BLUE_MID).me
    assert (seen.home, seen.duty, seen.allowance) == ("mid", None, 90.0) and seen.ward_charges > 0
    assert legal(world, BLUE_MID) == open_actions(BLUE_MID, ["mid"])


def test_the_bound_follows_the_configured_cap_and_refill():
    config = Config(tick_s=0.5, decision_ticks=4, roam_cap_s=30.0, roam_refill=0.5)
    decision_s = config.decision_ticks * config.tick_s
    # With the minions stopped at the enemy front tower, seed 8 sends no laner past the default refill and seed 1 does.
    rows = roam_soak(config, 600.0, seed=1)
    longest = [rows[seat]["longest_stretch_s"] for seat in LANERS]
    assert 30.0 <= max(longest) <= 30.0 + decision_s
    for seat in LANERS:
        row = rows[seat]
        assert row["roamed_after_s"] <= row["window_s"] / 3 + decision_s
    over_default = [rows[seat]["roamed_after_s"] - 0.2 * rows[seat]["window_s"] for seat in LANERS]
    assert max(over_default) > 2 * decision_s, "some laner must roam past what the default refill would allow"


@pytest.mark.parametrize("seat", LANERS)
def test_a_laner_with_allowance_may_do_anything_except_lane_elsewhere(seat):
    assert legal(World(Config(tick_s=0.5, decision_ticks=4)), seat) == open_actions(seat % 5, [HOME[seat % 5]])


@pytest.mark.parametrize("seat", JUNGLERS)
def test_a_jungler_may_lane_anywhere(seat):
    world = World(Config(tick_s=0.5, decision_ticks=4))
    world.champions[seat].allowance = -50.0
    assert legal(world, seat) == open_actions(seat % 5, LANES)
    assert observe(world, seat).me.home is None and observe(world, seat).me.duty is None


def off_the_mid_lane(units: float = 400.0):
    return RIFT.advance(RIFT.at("mid_river"), RIFT.at("top_river"), units)


@pytest.mark.parametrize("seat", [BLUE_MID, RED_MID])
def test_a_laner_with_no_allowance_off_its_lane_may_only_choose_to_return(seat):
    world = staged({seat: off_the_mid_lane()})
    me = world.champions[seat]
    me.allowance = 0.0
    assert observe(world, seat).me.duty is Duty.ROAMING
    assert legal(world, seat) == return_actions("mid")
    submit(world, {seat: move("own_mid_t1")})
    assert observe(world, seat).me.duty is Duty.RETURNING and me.allowance == 0.0
    assert legal(world, seat) == return_actions("mid") | {KEEP}


@pytest.mark.parametrize("seat", [BLUE_MID, RED_MID])
def test_a_laner_with_no_allowance_on_its_lane_may_only_stay_or_return(seat):
    world = staged({seat: lane_place(seat // 5, "mid", 6000.0)})
    me = world.champions[seat]
    submit(world, {seat: move("top_river")})
    me.allowance = -5.0
    assert observe(world, seat).me.duty is Duty.ON_LANE
    assert legal(world, seat) == return_actions("mid") | {HOLD}
    submit(world, {seat: HOLD})
    assert legal(world, seat) == return_actions("mid") | {HOLD, KEEP}


RETURN_CHOICES = {"own tower node": move("own_mid_t1"), "own base": move("own_base"), "own fountain": move("own_fountain"),
                  "lane": act(Kind.LANE, ("mid", "passive", "wave")), "recall": RECALL}


@pytest.mark.parametrize("choice", RETURN_CHOICES.values(), ids=RETURN_CHOICES.keys())
def test_a_laner_with_no_allowance_can_walk_to_its_tower_or_base_and_is_not_charged_for_the_way(choice):
    world = staged({BLUE_MID: off_the_mid_lane(3000.0)})
    me = world.champions[BLUE_MID]
    me.allowance = -1.5
    assert legal_mask(observe(world, BLUE_MID))[choice]
    submit(world, {BLUE_MID: choice})
    off_lane_ticks = 0
    for _ in range(40):
        seen = observe(world, BLUE_MID).me
        if seen.duty is Duty.ON_LANE:
            break
        assert seen.duty is Duty.RETURNING and seen.allowance == -1.5
        off_lane_ticks += 1
        world.step()
    assert off_lane_ticks >= 15


def test_the_allowance_drains_while_roaming_holds_while_returning_and_refills_on_the_lane_up_to_the_cap():
    world = staged({BLUE_MID: off_the_mid_lane(600.0)})
    me = world.champions[BLUE_MID]

    def allowance_after(seconds: float) -> float:
        for _ in range(round(seconds / world.config.tick_s)):
            world.step()
        return me.allowance

    assert allowance_after(10.0) == 80.0, "holding off the lane"
    submit(world, {BLUE_MID: move("top_river")})
    assert allowance_after(4.5) == 75.0, "walking further away"
    submit(world, {BLUE_MID: RECALL})
    assert allowance_after(3.5) == 75.0, "recalling"
    world.damage_champion(BLUE_MID, 10_000.0)
    assert allowance_after(10.0) == 75.0 and me.hp <= 0, "dead"
    assert allowance_after(5.0) == 75.0 and me.hp > 0, "standing on the fountain"
    submit(world, {BLUE_MID: act(Kind.LANE, ("mid", "push", "wave"))})

    def walk_back():
        assert me.allowance == 75.0, "walking back"
        world.step()

    until(lambda: on_lane("mid", me.pos), walk_back)
    assert allowance_after(8.0) == 75.0 + 8.5 * 0.25, "8 s and the tick that reached the lane"
    assert allowance_after(60.0) == 90.0, "the cap"


def test_the_allowance_runs_below_zero_until_the_next_decision():
    world = staged({BLUE_MID: off_the_mid_lane()})
    me = world.champions[BLUE_MID]
    me.allowance = 1.0
    for _ in range(4):
        world.step()
    assert me.allowance == -1.0


def test_assignments_end_at_the_configured_time_and_then_every_lane_is_open():
    world = staged({BLUE_TOP: off_the_mid_lane()}, Config(tick_s=0.5, decision_ticks=1, assignments_end_s=20.0))
    me = world.champions[BLUE_TOP]
    me.allowance = -3.0
    for _ in range(39):
        world.step()
    assert observe(world, BLUE_TOP).time_s == 19.5
    seen = observe(world, BLUE_TOP).me
    assert (seen.home, seen.duty) == ("top", Duty.ROAMING) and legal(world, BLUE_TOP) == return_actions("top")
    world.step()
    seen = observe(world, BLUE_TOP).me
    assert (seen.home, seen.duty, seen.allowance) == (None, None, -23.0)
    assert legal(world, BLUE_TOP) == open_actions(BLUE_TOP, LANES)
    for _ in range(20):
        world.step()
    assert me.allowance == -23.0


@pytest.mark.parametrize("fallen_team", [0, 1])
def test_a_fallen_outer_tower_ends_the_assignments_of_that_lane_alone(fallen_team):
    world = World(Config(tick_s=0.5, decision_ticks=4))
    world.lanes["bot"].towers[fallen_team][0].hp = 0.0
    for seat in (BLUE_CARRY, BLUE_SUPPORT, RED_CARRY, RED_SUPPORT):
        world.champions[seat].allowance = -5.0
        assert observe(world, seat).me.home is None
        assert legal(world, seat) == open_actions(seat % 5, LANES)
    for seat in (BLUE_TOP, BLUE_MID, RED_TOP, RED_MID):
        assert observe(world, seat).me.home == HOME[seat % 5]
        assert legal(world, seat) == open_actions(seat % 5, [HOME[seat % 5]])


def test_a_fallen_outer_tower_ends_no_assignment_when_the_config_says_so():
    world = World(Config(tick_s=0.5, decision_ticks=4, outer_tower_ends_assignment=False))
    world.lanes["bot"].towers[0][0].hp = 0.0
    assert observe(world, BLUE_CARRY).me.home == "bot"
    assert legal(world, BLUE_CARRY) == open_actions(BLUE_CARRY % 5, ["bot"])


def test_roles_and_home_lanes_are_fixed_by_the_seat():
    assert ROLES == ("top", "jungle", "mid", "carry", "support")
    assert [observe(World(Config(tick_s=0.5, decision_ticks=4)), seat).me.home for seat in SEATS] == ["top", None, "mid", "bot", "bot"] * 2
    assert [observe(World(Config(tick_s=0.5, decision_ticks=4)), seat).me.role for seat in SEATS] == [0, 1, 2, 3, 4] * 2
