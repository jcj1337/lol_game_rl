"""C8: a world refined to a finer clock is the same state, with every timer at the same game second."""

import copy
import re
from dataclasses import fields, is_dataclass, replace
from enum import Enum
from functools import cache

import pytest

from riftgame.champions import (FOUNTAIN, HOMEGUARD, KEEP, NEVER, NO_HOMEGUARD, NODE_POS, RECALL, RIFT, Kind, capability_of,
                                homeguard_bonus, on_fountain, speed_of)
from riftgame.clock import refine
from riftgame.combat import Hit
from riftgame.harness import tick
from riftgame.jungle import SITES, CampSpawn
from riftgame.policies import team_policies
from riftgame.vision import legal_mask, observe_team
from riftgame.world import Config, World, check_invariants
from worlds import BLUE_CARRY, BLUE_MID, BLUE_SUPPORT, BLUE_TOP, RED_TOP, act, move

HALF = Config(tick_s=0.5, decision_ticks=4)
FINER = (0.25, 0.125)
# How fast the Homeguard bonus falls while it decays, in share of move speed per second.
DECAY = (HOMEGUARD["speed_bonus"] - HOMEGUARD["speed_bonus_after_decay"]) / HOMEGUARD["decay_s"]
# A field counts ticks when its name says so. `homeguard_block` is a tick whose name does not say so.
TICKED = re.compile(r"tick|until|expires|block")


@cache
def played_snapshot():
    """A game at 512 s, while red's mid laner is dead and both teams remember an enemy seen on two ticks, so that a
    refined world shows a death timer and a remembered step."""
    world = World(HALF, 6)
    policies = team_policies()
    while world.tick < 1024:
        tick(world, policies)
    return world.snapshot()


def played() -> World:
    return World.restore(played_snapshot())


@pytest.mark.parametrize("tick_s", [0.2, 0.3, 0.4, 1.0])
def test_a_tick_that_does_not_divide_the_worlds_own_a_whole_number_of_times_is_refused(tick_s):
    with pytest.raises(ValueError):
        refine(played(), tick_s)


def test_refining_to_the_worlds_own_tick_gives_a_copy_with_the_same_digest():
    world = played()
    same = refine(world, 0.5)
    assert same is not world and same.digest() == world.digest()


def ticks_of(snapshot) -> dict[str, tuple[object, str, int | None]]:
    """Every whole-number tick of the state by its path, as (holder, field, index): an int field whose name counts
    ticks, `channel`, and each element of a list of ints under such a name."""
    found, seen = {}, set()

    def visit(value, path: str) -> None:
        if value is None or isinstance(value, (bool, int, float, str, Enum)) or id(value) in seen:
            return
        seen.add(id(value))
        if isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                visit(item, f"{path}[{i}]")
            return
        if isinstance(value, dict):
            for key, item in value.items():
                visit(item, f"{path}[{key!r}]")
            return
        for name in [f.name for f in fields(value)] if is_dataclass(value) else list(vars(value)):
            item = getattr(value, name)
            if TICKED.search(name) or name == "channel":
                if type(item) is int:
                    found[f"{path}.{name}"] = (value, name, None)
                elif isinstance(item, list) and all(type(x) is int for x in item):
                    found.update({f"{path}.{name}[{i}]": (value, name, i) for i in range(len(item))})
            visit(item, f"{path}.{name}")

    visit(snapshot, "world")
    return found


def read(holder, name: str, index: int | None) -> int:
    value = getattr(holder, name)
    return value if index is None else value[index]


def write(holder, name: str, index: int | None, value: int) -> None:
    if index is None:
        object.__setattr__(holder, name, value)
    else:
        getattr(holder, name)[index] = value


def test_every_tick_of_the_state_falls_at_the_same_game_second_and_every_sentinel_stays():
    world = played()
    world.ward(BLUE_SUPPORT, NODE_POS[0]["own_krugs"], 900.0, 40.0, 3)
    source = copy.deepcopy(world.snapshot())
    ticks = ticks_of(source)
    assert {type(holder).__name__ for holder, _, _ in ticks.values()} >= {
        "Snapshot", "Config", "Champion", "Camp", "Sight", "CampMemory", "EnemyMemory", "WaveMemory", "TowerMemory", "LaneSim"}
    assert {name for _, name, _ in ticks.values()} >= {"homeguard_block", "channel", "hurt_tick", "slow_until", "lockdown_tick"}
    sentinels = {path: read(*where) for path, where in ticks.items() if read(*where) < 0}
    assert {-1, NEVER} <= set(sentinels.values())
    for tick_s in FINER:
        after = ticks_of(refine(World.restore(source), tick_s).snapshot())
        assert {path: read(*after[path]) for path in sentinels} == sentinels
    t = source.tick
    for where in ticks.values():
        write(*where, t)
    marked = World.restore(source)
    for tick_s in FINER:
        fine = refine(marked, tick_s)
        after = ticks_of(fine.snapshot())
        assert after.keys() == ticks.keys()
        assert {path: read(*where) for path, where in after.items() if read(*where) * tick_s != t * HALF.tick_s} == {}
        assert fine.config.tick_s == tick_s and all(sim.tick_s == tick_s for sim in fine.lanes.values())


CAMP = next(i for i, site in enumerate(SITES) if not site.kind.scuttler)


def staged() -> World:
    """A world on the 0.5 s clock at 120 s with one timer of each kind running, each where nothing cuts it short.
    Blue's mid laner recalls in the top river, its carry is slowed at its raptors, its support is dead with a ward
    out, a blue camp is dead, and its top laner fights red's top laner in the bot river with its lockdown cooling."""
    world = World(HALF, 2)
    while world.tick < 240:
        world.step()
    t = world.tick
    mid, carry, support, top, foe = (world.champions[s] for s in (BLUE_MID, BLUE_CARRY, BLUE_SUPPORT, BLUE_TOP, RED_TOP))
    for c in (mid, carry, top, foe):
        c.homeguard_tick = NO_HOMEGUARD
    mid.pos, mid.intent, mid.intent_tick, mid.channel = NODE_POS[0]["top_river"], RECALL, t - 3, 3
    carry.pos, carry.slow, carry.slow_until = NODE_POS[0]["own_raptors"], 0.3, t + 6
    support.hp, support.respawn_tick = 0.0, t + 21
    world.ward(BLUE_SUPPORT, NODE_POS[0]["own_krugs"], 900.0, 40.0, 3)
    camp = world.camps[CAMP]
    camp.hp, camp.engaged, camp.spawn_tick = 0.0, -1, t + 30
    top.pos = foe.pos = NODE_POS[0]["bot_river"]
    top.intent, top.intent_tick, top.lockdown_tick = act(Kind.FIGHT, 0), t, t + 8
    record = world.memory[0].enemies[0]
    record.pos, record.was, record.seen_tick = foe.pos, None, t
    check_invariants(world)
    return world


def moments(world: World) -> dict[str, float]:
    """The game second at which each staged timer runs out, read from what the world does. A recall ends with its
    last tick. The other timers end when the tick that they name begins."""
    dt = world.config.tick_s
    mid, carry, support = (world.champions[s] for s in (BLUE_MID, BLUE_CARRY, BLUE_SUPPORT))
    found = {}
    while len(found) < 6:
        start = world.tick * dt
        assert start < 200.0, f"timers left running: {found}"
        if speed_of(world, carry) >= capability_of(carry).move_speed * (1 + homeguard_bonus(world, carry)):
            found.setdefault("slow ends", start)
        world.step()
        if support.hp > 0:
            found.setdefault("respawn", start)
        if mid.pos == FOUNTAIN[0]:
            found.setdefault("recall ends", world.tick * dt)
        if all(s.owner != BLUE_SUPPORT for s in world.sights):
            found.setdefault("ward expires", start)
        for _, e in world.events:
            if type(e) is CampSpawn and e.camp == CAMP:
                found.setdefault("camp respawns", e.t)
            if type(e) is Hit and e.attacker == BLUE_TOP and e.slow > 0:
                found.setdefault("lockdown ready", start)
    return found


@pytest.mark.parametrize("tick_s", FINER)
def test_running_timers_end_at_the_same_game_second_on_the_finer_clock(tick_s):
    world = staged()
    now = world.tick * HALF.tick_s
    # A recall of 8.5 s begun 1.5 s ago, a respawn in 10.5 s, a ward of 40 s, a camp in 15 s, a slow for 3 s more, a
    # lockdown ready in 4 s.
    expected = {"recall ends": now + 7.0, "respawn": now + 10.5, "ward expires": now + 40.0, "camp respawns": now + 15.0,
                "slow ends": now + 3.0, "lockdown ready": now + 4.0}
    fine = refine(world, tick_s)
    check_invariants(fine)
    assert moments(world) == expected
    assert moments(fine) == expected


def ahead_blank(o):
    """An observation without the values that look one tick ahead or one tick back: `dead_s`, the Homeguard bonus,
    and the place where an enemy was one tick before."""
    def view(v):
        return replace(v, dead_s=0.0, homeguard=0.0)

    return replace(o, me=view(o.me), mates=tuple(view(v) for v in o.mates), rivals=tuple(r._replace(dead_s=0.0) for r in o.rivals),
                   enemies=tuple(None if e is None else e._replace(was=None) for e in o.enemies))


@pytest.mark.parametrize("tick_s", FINER)
def test_a_refined_world_keeps_every_invariant_and_each_teams_observations_apart_from_what_looks_one_tick_ahead(tick_s):
    world = played()
    t = world.tick
    leaving = next(c for c in world.champions[:5] if c.hp > 0)
    leaving.pos, leaving.homeguard_tick = NODE_POS[0]["own_base"], t - 2
    assert not on_fountain(leaving)
    fine = refine(world, tick_s)
    check_invariants(fine)
    step = HALF.tick_s - tick_s
    k = round(HALF.tick_s / tick_s)
    seen = {"dead": 0, "decaying": 0, "was": 0}
    for team in range(2):
        before, after = observe_team(world, team), observe_team(fine, team)
        assert [legal_mask(o) for o in after] == [legal_mask(o) for o in before]
        assert [ahead_blank(o) for o in after] == [ahead_blank(o) for o in before]
        for o, p in zip(before, after):
            for a, b in zip((o.me, *o.mates, *o.rivals), (p.me, *p.mates, *p.rivals)):
                assert b.dead_s == (a.dead_s - step if a.dead_s > 0 else 0.0)
                seen["dead"] += a.dead_s > 0
            for a, b in zip((o.me, *o.mates), (p.me, *p.mates)):
                assert abs(b.homeguard - a.homeguard) <= DECAY * step / 2 + 1e-12
                seen["decaying"] += a.homeguard != b.homeguard
        for old, new in zip(world.memory[team].enemies, fine.memory[team].enemies):
            if old.was is not None:
                assert RIFT.distance(new.was, new.pos) == pytest.approx(RIFT.distance(old.was, old.pos) / k)
                seen["was"] += 1
    assert all(seen.values()), seen


@pytest.mark.parametrize("tick_s", FINER)
def test_a_decision_tick_stays_one_and_the_decisions_fall_at_the_same_game_seconds(tick_s):
    for offset in range(HALF.decision_ticks):
        world = played()
        for _ in range(offset):
            world.step()
        fine = refine(world, tick_s)
        if offset:
            with pytest.raises(ValueError):
                fine.step([KEEP] * 10)
        else:
            fine.step([KEEP] * 10)

    def decided(world: World) -> list[float]:
        times = []

        def spy(o, noise):
            times.append(o.time_s)
            return KEEP

        end = world.tick * world.config.tick_s + 10.0
        while world.tick * world.config.tick_s < end:
            tick(world, (spy,) * 10)
        return sorted(set(times))

    world = played()
    world.step()
    assert decided(refine(world, tick_s)) == decided(world) == [514.0, 516.0, 518.0, 520.0, 522.0]


@pytest.mark.parametrize("tick_s", FINER)
def test_a_champion_that_left_its_fountain_under_homeguard_walks_as_far_on_the_finer_clock(tick_s):
    world = World(HALF, 1)
    while world.tick < 80:
        world.step()
    mid = world.champions[BLUE_MID]
    world.step([move("own_mid_t1") if seat == BLUE_MID else KEEP for seat in range(10)])
    while on_fountain(mid) or world.tick - mid.homeguard_tick < 2:
        world.step()
    assert HOMEGUARD["speed_bonus_after_decay"] < homeguard_bonus(world, mid) < HOMEGUARD["speed_bonus"]
    fine = refine(world, tick_s)
    for _ in range(3):
        world.step()
    for _ in range(3 * round(HALF.tick_s / tick_s)):
        fine.step()
    walked = [RIFT.distance(FOUNTAIN[0], w.champions[BLUE_MID].pos) for w in (world, fine)]
    assert walked[1] == pytest.approx(walked[0], abs=1e-6)
    assert all(w.champions[BLUE_MID].homeguard_tick != NO_HOMEGUARD for w in (world, fine)) and walked[0] < RIFT.distance(FOUNTAIN[0], NODE_POS[0]["own_mid_t1"])
