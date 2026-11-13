"""C6: what a team sees, what it remembers, its wards, and that nothing hidden reaches it.

The two leak tests copy a running game, change every hidden field in the copy, and compare what the team is told
and what its champions do. `sources_of` and `exposed` decide what is hidden from the map's own sight measure, so
they share no code with `riftgame.vision`.
"""

import copy
import math
import random
from dataclasses import fields, is_dataclass, replace
from functools import cache

import pytest

from riftgame.champions import (ACTIONS, FOUNTAIN, HOLD, KEEP, LANES, LEVEL_XP, NO_HOMEGUARD, PROGRESSIONS, RECALL, RIFT, ROLES, WARDS,
                                Champion, Duty, Income, Kind, Outcome, capability_of, level_of, speed_of)
from riftgame.harness import jungler, scripted
from riftgame.jungle import SITES
from riftgame.lanes import Kind as Minion
from riftgame.rng import Stream, keyed_uniform
from riftgame.vision import (CampMemory, EnemyMemory, EnemyView, LastSeen, Place, Rival, Sight, TowerMemory, WardView, WaveMemory, encode,
                             legal_mask, observe, observe_team, sees, to_frame)
from riftgame.world import Config, World, check_invariants
from worlds import (BLUE_CARRY, BLUE_JUNGLE, BLUE_MID, BLUE_SUPPORT, BLUE_TOP, EVERY_TICK, RED_CARRY, RED_JUNGLE, RED_MID, RED_TOP, act,
                    busy, lane, lane_place, move, raze, staged, submit)

TICK_S = 0.5
# M7 section 6.1: the sight radius of a champion, a lane minion, a lane tower, and a Stealth Ward.
SIGHT, MINION_SIGHT, TOWER_SIGHT, WARD_SIGHT = 1350.0, 1200.0, 1350.0, 900.0
# Reference rows F1: a ward is placed from 625 units, a champion holds 2 charges and keeps 3 wards on the map.
PLACE_RANGE, MAX_CHARGES, MAX_WARDS = 625.0, 2, 3
WAVE_SPAN, ACQUIRE, STAND_OFF = 1500.0, 500.0, 550.0
TOP, JUNGLE, MID, CARRY, SUPPORT = range(5)
FIGHT = tuple(act(Kind.FIGHT, role) for role in range(5))
RIVER = RIFT.lane_s("mid", RIFT.at("mid_river"))
PLACES = tuple(RIFT.at(node) for node in RIFT.node_names) + tuple(
    replace(FOUNTAIN[0], edge=i, offset=edge.length * share) for i, edge in enumerate(RIFT.edges) for share in (0.25, 0.5, 0.75))


def knowledge(world: World, team: int) -> list:
    """Everything a team is told: per champion its observation, the encoding a learner reads, and its mask."""
    return [(o, encode(o), legal_mask(o)) for o in observe_team(world, team)]


def team_of(world: World, team: int) -> list[Champion]:
    return world.champions[team * 5:team * 5 + 5]


def sources_of(world: World, team: int) -> set:
    """A team's sight sources as (place, radius), read from the world with no help from `riftgame.vision`."""
    found = {(c.pos, SIGHT) for c in team_of(world, team) if c.hp > 0}
    for name in LANES:
        sim = world.lanes[name]
        found |= {(RIFT.lane_pos(name, tower.s), TOWER_SIGHT) for tower in sim.towers[team] if tower.hp > 0}
        found |= {(RIFT.lane_pos(name, m.s), MINION_SIGHT) for m in sim.minions[team]}
    return found | {(s.pos, s.radius) for s in world.sights if s.team == team}


def lit(sources, pos, slack: float = 0.0) -> bool:
    return any(RIFT.sees(at, pos, radius + slack) for at, radius in sources)


def quiet_world(places: dict, config: Config = EVERY_TICK, towers: bool = False) -> World:
    """A world in which no wave ever spawns, with the given seats on their marks. Without `towers` every lane tower
    has fallen, so champions, the minions a test adds, and wards are the only sight sources."""
    world = staged(places, config)
    for sim in world.lanes.values():
        sim.clock.next_wave = math.inf
    return world if towers else raze(world)


def mid(from_river: float):
    """A place on mid lane by its distance from the river crossing, negative toward the blue base."""
    return RIFT.lane_pos("mid", RIVER + from_river)


def walk(start: str, goal: str, route_units: float):
    """The place `route_units` of walking from node `start` toward node `goal`."""
    return RIFT.advance(RIFT.at(start), RIFT.at(goal), route_units)


def over_the_wall(share: float):
    """A place on the path from the blue mid outer tower's node to the blue Raptors. A wall crosses it at 51
    percent, so 35 and 48 percent are on the lane's side and 65 percent is on the camp's side."""
    return walk("blue_mid_t1", "blue_raptors", share * RIFT.distance(RIFT.at("blue_mid_t1"), RIFT.at("blue_raptors")))


def at_levels(world: World, levels) -> World:
    for c, level in zip(world.champions, levels, strict=True):
        c.xp = LEVEL_XP[level - 2] if level > 1 else 0.0
    return world


PUSH_TOP, HOLD_MID, THIN_BOT, HOME_BOT = lane("top", "push"), lane("mid", "last_hit", "hold"), lane("bot", "thin"), lane("bot", "passive")
ORDERS = (PUSH_TOP, None, HOLD_MID, THIN_BOT, act(Kind.FOLLOW, CARRY))


def varied(o, noise: float) -> int:
    """A team that exercises every automatic movement: top pushes and the carry thins with the wave, mid last-hits
    on the hold line, the support follows the carry, and the jungler runs the scripted clear. Top and the carry
    fight an enemy they see half of the time and keep the fight after it has left the view. The jungler and the
    support go to place a ward now and then."""
    me, mask = o.me, legal_mask(o)
    if me.hp <= 0:
        return KEEP
    if ACTIONS[me.intent].kind in (Kind.FIGHT, Kind.WARD) and mask[KEEP]:
        return KEEP
    if me.role in (TOP, CARRY) and noise < 0.5:
        seen = [role for role, enemy in enumerate(o.enemies) if enemy is not None and mask[FIGHT[role]]]
        if seen:
            return FIGHT[seen[int(noise * 2 * len(seen))]]
    if me.role in (JUNGLE, SUPPORT) and noise > 0.8:
        spots = [i for i in WARDS if mask[i]]
        if spots:
            return spots[int((noise - 0.8) * 5 * len(spots))]
    if me.role == JUNGLE:
        return jungler(o, noise)
    for want in (ORDERS[me.role], HOME_BOT, KEEP):
        if mask[want]:
            return want
    return HOLD


def advance(world: World, policies) -> None:
    """One tick with one policy per team, on the keyed noise that `harness.tick` uses."""
    actions = None
    if world.tick % world.config.decision_ticks == 0:
        actions = [policies[seat // 5](o, keyed_uniform(world.seed, Stream.POLICY, seat, world.tick))
                   for seat, o in enumerate((*observe_team(world, 0), *observe_team(world, 1)))]
    world.step(actions)


ENEMIES = {"scripted": scripted, "busy": busy, "varied": varied}
GAMES = [(3, "busy"), (5, "scripted"), (8, "varied"), (11, "busy")]
SNAPSHOTS = (600, 800, 1200, 1400)


@cache
def _snapshots(seed: int, enemy: str, team: int) -> dict:
    world = World(Config(), seed)
    policies = (varied, ENEMIES[enemy]) if team == 0 else (ENEMIES[enemy], varied)
    taken = {}
    while world.tick < SNAPSHOTS[-1]:
        advance(world, policies)
        if world.tick in SNAPSHOTS:
            taken[world.tick] = world.snapshot()
    return taken


def game(seed: int, enemy: str, team: int, ticks: int) -> World:
    """A game after `ticks` ticks in which `team` plays `varied` against the named policy."""
    return World.restore(_snapshots(seed, enemy, team)[ticks])


# Every field of a champion is either changed in a hidden enemy or listed here with the reason it is not hidden.
CHAMPION_HIDDEN = ("pos", "hp", "mana", "xp", "gold", "earned", "upgrades", "intent", "intent_tick", "channel", "outcome",
                   "outcome_tick", "allowance", "attack_credit", "item_charges", "homeguard_tick", "homeguard_block", "slow",
                   "slow_until", "lockdown_tick", "ward_charges", "ward_tick")
CHAMPION_KNOWN = {"seat": "who it is", "respawn_tick": "the death timer is public",
                  "hurt_tick": "it records the hits of the observing team's own champions"}
# A dead champion's health is its death, which is public. It holds by the invariant and stands on its fountain.
DEAD_KEPT = ("pos", "hp", "intent")
MINION_HIDDEN = ("s", "hp", "target", "ready", "credit")
CAMP_HIDDEN = ("hp", "max_hp", "level", "spawn_tick", "engaged")


def _other(rng: random.Random, now, choices):
    return rng.choice([value for value in choices if value != now])


def scramble_champion(c: Champion, tick: int, rng: random.Random, hides) -> None:
    """Change every hidden field of an enemy champion to another legal value. Its level stays, and so does whether
    it has ever been paid for a kill, which decides first blood and is public."""
    level = level_of(c.xp)
    low = LEVEL_XP[level - 2] if level > 1 else 0.0
    high = LEVEL_XP[level - 1] if level <= len(LEVEL_XP) else low + 1000.0
    c.xp = _other(rng, c.xp, [low + (high - low) * share for share in (0.1, 0.3, 0.5, 0.7, 0.9)])
    progression = PROGRESSIONS[ROLES[c.role]]
    if c.upgrades < len(progression):
        c.earned[Income.MINION] += progression[c.upgrades].cost
        c.upgrades += 1
    else:
        c.upgrades -= 1
        c.earned[Income.STARTING] -= progression[c.upgrades].cost
    extra = rng.uniform(5.0, 200.0)
    c.gold += extra
    c.earned[Income.PASSIVE] += extra
    can = capability_of(c)
    c.mana = _other(rng, c.mana, [can.max_mana * share for share in (0.2, 0.5, 0.8)])
    c.intent_tick -= 1 + rng.randrange(20)
    c.outcome = Outcome(_other(rng, c.outcome, range(len(Outcome))))
    c.outcome_tick -= 1 + rng.randrange(40)
    c.allowance -= rng.uniform(1.0, 60.0)
    c.attack_credit = _other(rng, c.attack_credit, (0.0, 0.25, 0.5, 0.75, 1.0))
    c.item_charges = _other(rng, c.item_charges, range(4))
    c.homeguard_block += 1 + rng.randrange(20)
    c.slow = _other(rng, c.slow, (0.0, 0.2, 0.4))
    c.slow_until += 1 + rng.randrange(6)
    c.lockdown_tick += 1 + rng.randrange(30)
    c.ward_charges = _other(rng, c.ward_charges, range(MAX_CHARGES + 1))
    c.ward_tick = -1 if c.ward_charges == MAX_CHARGES else max(tick, c.ward_tick) + 1 + rng.randrange(300)
    c.homeguard_tick = tick - rng.randrange(8) if c.homeguard_tick == NO_HOMEGUARD else NO_HOMEGUARD
    c.channel += 1 + rng.randrange(4)
    if c.hp <= 0:
        return
    c.hp = _other(rng, c.hp, [can.max_hp * share for share in (0.15, 0.4, 0.65, 0.9)])
    c.intent = _other(rng, c.intent, range(1, len(ACTIONS)))
    # A hidden enemy is moved inside its own half, where the other team's waves do not walk into it at once.
    home, away = FOUNTAIN[c.team], FOUNTAIN[1 - c.team]
    spots = [pos for pos in PLACES if pos != c.pos and hides(pos) and RIFT.separation(pos, home) < RIFT.separation(pos, away)]
    assert spots, "the enemy's half has a place that the team does not see"
    c.pos = rng.choice(spots)


def scramble(world: World, team: int, rng: random.Random, slack: float = 0.0, reach: tuple[float, float] = (0.0, 0.0),
             quiet: bool = False) -> dict:
    """Change everything in `world` that is hidden from `team`, and return what was changed.

    A place is hidden when no sight source of the team sees it, with `slack` added to every radius, and when no
    champion of the team stands within `reach` of it by the straight line: the first reach is for an enemy
    champion and the second for an enemy minion. An enemy champion that the team's memory holds as seen now is
    not hidden either: one that damaged a champion of the team is seen wherever it stands.

    Changed, per hidden enemy champion: `CHAMPION_HIDDEN`, and for a dead one all of them but `DEAD_KEPT`. Per
    hidden enemy minion: `MINION_HIDDEN`, where a moved minion stays in hidden places. Per camp whose place is
    hidden and whose spawn the team does not know: `CAMP_HIDDEN`, a living camp dies and a dead one lives, and a
    Scuttler changes its health or its spawn tick. A hidden enemy front tower loses one health. Enemy Stealth Wards: two are removed, one comes back elsewhere,
    and new ones are put on every champion of the team, on hidden enemies, and on hidden camps. The enemy team's
    whole memory: every field of every `CampMemory`, `EnemyMemory`, `WaveMemory`, and `TowerMemory`. A lane whose
    minions were moved forgets what it derived from their places.

    What the enemy knows moves the enemy champions that the team is watching, and that is no leak. So `quiet`
    leaves alone what would move them on the next tick: the enemy's wards stay, new ones go only to hidden
    places, and its memory records of what it sees now stay current.
    """
    tick, foe = world.tick, 1 - team
    sources, mine = sources_of(world, team), [c.pos for c in team_of(world, team)]

    def hides(pos, near: float = reach[0]) -> bool:
        return not lit(sources, pos, slack) and all(RIFT.separation(pos, at) > near for at in mine)

    changed = {"champions": [], "dead": [], "minions": 0, "moved": 0, "camps": [], "river": [], "wards": 0, "towers": 0}
    for c, record in zip(team_of(world, foe), world.memory[team].enemies):
        if c.hp <= 0:
            scramble_champion(c, tick, rng, hides)
            changed["dead"].append(c.seat)
        elif record.seen_tick != tick and hides(c.pos):
            scramble_champion(c, tick, rng, hides)
            changed["champions"].append(c.seat)
    for name in LANES:
        sim = world.lanes[name]
        for m in sim.minions[foe]:
            if not hides(RIFT.lane_pos(name, m.s), reach[1]):
                continue
            shifted = m.s + rng.choice((-1, 1)) * rng.uniform(50.0, 400.0)
            if 0.0 <= shifted <= sim.length and hides(RIFT.lane_pos(name, shifted), reach[1]):
                m.s = shifted
                changed["moved"] += 1
            m.hp = _other(rng, m.hp, [m.max_hp * share for share in (0.2, 0.5, 0.8)])
            m.target = sim.front_tower(team) if m.target is None else None
            m.ready += rng.uniform(0.1, 1.0)
            m.credit = _other(rng, m.credit, (0.0, 0.3, 0.6))
            changed["minions"] += 1
        sim.invalidate()
        front = sim.front_tower(foe)
        if front is not None and front.hp > 2.0 and hides(RIFT.lane_pos(name, front.s)):
            front.hp -= 1.0
            changed["towers"] += 1
    known = world.memory[team].camps
    for i, (camp, site) in enumerate(zip(world.camps, SITES)):
        if known[i].spawn_tick >= tick or not hides(site.pos):
            continue
        if site.kind.scuttler:
            # The river holds one Scuttler, alive or due, so a hidden one keeps its state and changes its numbers.
            if camp.hp > 0:
                camp.hp *= 0.5
            elif camp.spawn_tick > tick:
                camp.spawn_tick += 7
            else:
                continue
            changed["river"].append(i)
            continue
        if camp.hp > 0:
            camp.hp, camp.max_hp, camp.level, camp.spawn_tick, camp.engaged = 0.0, camp.max_hp + 50.0, camp.level + 1, tick + 5 + rng.randrange(200), -1
        else:
            camp.hp, camp.max_hp, camp.level, camp.spawn_tick, camp.engaged = 300.0, 900.0, camp.level + 1, -1, foe * 5 + JUNGLE
        changed["camps"].append(i)
    theirs = [s for s in world.sights if s.team == foe and s.owner >= 0]
    for s in theirs[:0 if quiet else 2]:
        world.sights.remove(s)
    if len(theirs) > 1 and not quiet:
        world.sights.append(Sight(foe, rng.choice(PLACES), WARD_SIGHT, theirs[1].expires + 7, theirs[1].owner))
    spots = [c.pos for c in team_of(world, foe) if c.seat in changed["champions"]] + [SITES[i].pos for i in changed["camps"]]
    for n, pos in enumerate(spots[:6] if quiet else mine + spots[:6]):
        owner = foe * 5 + n % 5
        if sum(s.owner == owner for s in world.sights) < MAX_WARDS:
            world.sights.append(Sight(foe, pos, WARD_SIGHT, tick + 100 + n, owner))
            changed["wards"] += 1
    memory = world.memory[foe]
    for record in memory.camps:
        record.hp, record.level, record.seen_tick, record.spawn_tick = (record.hp + 5.0, record.level + 2, _other(rng, record.seen_tick, range(tick - 9, tick)),
                                                                        max(tick, record.spawn_tick) + 30)
    stale = range(tick - 3, tick + 1 - quiet)
    for record in memory.enemies:
        if not (quiet and record.seen_tick == tick):
            record.pos, record.was, record.hp, record.level = _other(rng, record.pos, PLACES), _other(rng, record.was, (None, *PLACES)), record.hp + 7.0, record.level + 1
            record.upgrades, record.seen_tick = record.upgrades + 1, _other(rng, record.seen_tick, stale)
    for record in memory.towers:
        record.hp, record.seen_tick = record.hp / 2 + 1.0, _other(rng, record.seen_tick, range(tick - 9, tick))
    for record in memory.waves:
        if not (quiet and record.seen_tick == tick):
            record.lead, record.near, record.seen_tick = rng.uniform(2000.0, 9000.0), _other(rng, record.near, ((1, 1, 0), (3, 2, 1), (2, 3, 0))), _other(rng, record.seen_tick, stale)
    return changed


def test_the_scramble_changes_every_hidden_field_and_names_the_ones_it_leaves():
    assert set(CHAMPION_HIDDEN) | set(CHAMPION_KNOWN) == {f.name for f in fields(Champion)}
    assert {f.name for f in fields(CampMemory)} == {"hp", "level", "seen_tick", "spawn_tick"}
    assert {f.name for f in fields(EnemyMemory)} == {"pos", "was", "hp", "level", "upgrades", "seen_tick"}
    assert {f.name for f in fields(WaveMemory)} == {"lead", "near", "seen_tick"}
    assert {f.name for f in fields(TowerMemory)} == {"hp", "seen_tick"}
    assert {f.name for f in fields(type(World().camps[0]))} == set(CAMP_HIDDEN)
    for seed, enemy in GAMES:
        world = game(seed, enemy, 0, 800)
        twin = World.restore(world.snapshot())
        changed = scramble(twin, 0, random.Random(1))
        if changed["champions"] and changed["dead"] and changed["moved"] and changed["camps"]:
            break
    else:
        raise AssertionError("no game has a hidden living enemy, a dead one, a hidden minion, and a hidden camp at tick 800")
    for seat in changed["champions"] + changed["dead"]:
        was, now = world.champions[seat], twin.champions[seat]
        kept = DEAD_KEPT if seat in changed["dead"] else ()
        assert [name for name in CHAMPION_HIDDEN if getattr(was, name) == getattr(now, name)] == [name for name in CHAMPION_HIDDEN if name in kept]
        assert all(getattr(was, name) == getattr(now, name) for name in CHAMPION_KNOWN)
        assert level_of(was.xp) == level_of(now.xp) and (was.earned[Income.KILL] > 0) == (now.earned[Income.KILL] > 0)
    for was, now in zip(world.memory[1].camps + world.memory[1].enemies + world.memory[1].waves + world.memory[1].towers,
                        twin.memory[1].camps + twin.memory[1].enemies + twin.memory[1].waves + twin.memory[1].towers):
        assert all(getattr(was, f.name) != getattr(now, f.name) for f in fields(was))
    for i in changed["camps"]:
        assert all(getattr(world.camps[i], name) != getattr(twin.camps[i], name) for name in CAMP_HIDDEN[:4])

    def minions(game: World) -> dict:
        return {(name, m.uid): (m.s, m.hp, m.target is None, m.ready, m.credit) for name in LANES for m in game.lanes[name].minions[1]}

    was, now = minions(world), minions(twin)
    differ = [key for key in was if was[key] != now[key]]
    assert len(MINION_HIDDEN) == 5 and len(differ) == changed["minions"]
    assert all(a != b for key in differ for a, b in zip(was[key][1:], now[key][1:]))


@pytest.mark.parametrize("seed, enemy", GAMES)
@pytest.mark.parametrize("team", [0, 1])
def test_changing_every_field_hidden_from_a_team_changes_none_of_its_observations_encodings_or_masks(team, seed, enemy):
    total = {"champions": 0, "dead": 0, "minions": 0, "camps": 0, "wards": 0, "towers": 0}
    for ticks in SNAPSHOTS:
        world = game(seed, enemy, team, ticks)
        twin = World.restore(world.snapshot())
        changed = scramble(twin, team, random.Random(seed + ticks))
        check_invariants(twin)
        assert twin.digest() != world.digest()
        assert knowledge(twin, team) == knowledge(world, team), f"tick {ticks}"
        for (o, code, _), (other, other_code, _) in zip(knowledge(twin, 1 - team), knowledge(world, 1 - team)):
            assert o != other and code != other_code, "the other team is told of the change, and its encoding shows it"
        for name in total:
            total[name] += changed[name] if name in ("minions", "wards", "towers") else len(changed[name])
    assert total["champions"] >= 4 and total["minions"] >= 10 and total["camps"] >= 8 and total["wards"] >= 20 and total["towers"] >= 2, total


# How far a unit can be from where a state shows it, inside one tick: one move of a fast champion.
SLACK = 300.0
# The straight line along which an enemy champion or minion can hit a champion over a wall without being seen
# first: the longest attack range, 550, and a move of each.
REACH = (1000.0, 1000.0)
# The behaviour test changes only what is hidden by this much more, so that the comparison lasts.
MARGIN = 1500.0
HORIZON = 60


def facts(world: World, team: int) -> dict:
    """What `exposed` reads of one world at one tick: the team's sight sources and places, and the enemy's
    champions, minions, camps, and public facts (levels, deaths, standing towers)."""
    foe = 1 - team
    minions = {(name, m.uid): (m.s, m.hp, m.max_hp, m.credit, m.ready, m.swing, m.delay, m.draws, type(m.target).__name__,
                               getattr(m.target, "uid", None), getattr(m.target, "tier", None))
               for name in LANES for m in world.lanes[name].minions[foe]}
    public = [(level_of(c.xp), c.hp > 0, c.respawn_tick) for c in team_of(world, foe)]
    public += [tower.hp > 0 for name in LANES for tower in world.lanes[name].towers[foe]]
    towers = {RIFT.lane_pos(name, tower.s): tower.hp for name in LANES for tower in world.lanes[name].towers[foe]}
    return {"sources": sources_of(world, team), "mine": {c.pos for c in team_of(world, team)},
            "foes": copy.deepcopy(team_of(world, foe)), "minions": minions, "camps": copy.deepcopy(world.camps), "public": public,
            "towers": towers}


def exposed(before: tuple[dict, dict], after: tuple[dict, dict]) -> bool:
    """Whether the tick from `before` to `after` may have shown the team a difference between the two worlds.

    The worlds differ in enemy champions, enemy minions, camps, and enemy towers. A difference is exposed when a sight source of
    the team, where it stood before or after the tick, sees a place where the differing thing stood before or
    after it, by the map's sight measure with `SLACK` added to the radius. It is also exposed within `REACH` of a
    champion of the team, and when a public fact differs. This errs toward exposure, so it never excuses a leak.
    """
    if after[0]["public"] != after[1]["public"]:
        return True
    sources = before[0]["sources"] | after[0]["sources"] | after[1]["sources"]
    mine = before[0]["mine"] | after[0]["mine"] | after[1]["mine"]
    champions, minions, camps = set(), set(), set()
    for one, other in (before, after):
        champions |= {c.pos for a, b in zip(one["foes"], other["foes"]) if a != b for c in (a, b)}
        for key in one["minions"].keys() | other["minions"].keys():
            if one["minions"].get(key) != other["minions"].get(key):
                minions |= {RIFT.lane_pos(key[0], rows[key][0]) for rows in (one["minions"], other["minions"]) if key in rows}
        camps |= {SITES[i].pos for i, (a, b) in enumerate(zip(one["camps"], other["camps"])) if a != b}
        camps |= {pos for pos, hp in one["towers"].items() if other["towers"][pos] != hp}
    for near, places in ((REACH[0], champions), (REACH[1], minions), (0.0, camps)):
        for pos in places:
            if lit(sources, pos, SLACK) or any(RIFT.separation(pos, at) <= near for at in mine):
                return True
    return False


def twins(world: World, team: int, enemy, seed: int) -> dict:
    """Scramble a copy of `world` and run both forward on the same actions: the team's from its policy, and the
    enemy's from its policy in the first world. Until the first exposed tick, assert that the team is told the
    same in both and that its champions and its whole memory (camps, enemies with their last places and upgrades,
    waves, and towers) are in the same state. Then run on, up to `HORIZON` ticks in all, to see
    whether the team is ever told of the difference. Returns what the comparison covered."""
    twin = World.restore(world.snapshot())
    changed = scramble(twin, team, random.Random(seed), SLACK + MARGIN, (REACH[0] + MARGIN, REACH[1] + MARGIN), quiet=True)
    check_invariants(twin)
    assert twin.digest() != world.digest()
    pair, foe = (world, twin), 1 - team
    report = {"changed": changed, "compared": 0, "revealed": False, "kinds": set(), "stands": set(), "modes": set(), "blind": 0}
    for step in range(HORIZON):
        told = [knowledge(game, team) for game in pair]
        if told[0] != told[1]:
            assert step > report["compared"], f"the team is told of a hidden change at step {step}"
            report["revealed"] = True
            break
        before = (facts(world, team), facts(twin, team))
        intents = [ACTIONS[c.intent] for c in team_of(world, team)]
        records = [record.seen_tick == world.tick for record in world.memory[team].enemies]
        decide = world.tick % world.config.decision_ticks == 0
        if decide:
            mine = [varied(o, keyed_uniform(world.seed, Stream.POLICY, team * 5 + role, world.tick)) for role, (o, _, _) in enumerate(told[0])]
            theirs = [enemy(o, keyed_uniform(world.seed, Stream.POLICY, foe * 5 + role, world.tick)) for role, o in enumerate(observe_team(world, foe))]
        for game in pair:
            # An enemy that is dead in one world only takes no order there. Its death is public, so the tick is exposed.
            alive = [action if c.hp > 0 else KEEP for action, c in zip(theirs, team_of(game, foe))] if decide else None
            game.step((mine + alive if team == 0 else alive + mine) if decide else None)
        if step > report["compared"] or exposed(before, (facts(world, team), facts(twin, team))):
            continue
        assert team_of(world, team) == team_of(twin, team), f"the team's champions differ at step {step} with nothing revealed"
        assert world.memory[team] == twin.memory[team], f"the team's memory differs at step {step} with nothing revealed"
        report["compared"] += 1
        for action in intents:
            report["kinds"].add(action.kind)
            if action.kind is Kind.LANE:
                report["modes"].add(action.target[1])
                report["stands"].add(action.target[2])
            report["blind"] += action.kind is Kind.FIGHT and not records[action.target]
    return report


@cache
def comparisons(seed: int, enemy: str, team: int) -> tuple:
    return tuple(twins(game(seed, enemy, team, ticks), team, ENEMIES[enemy], seed + ticks) for ticks in SNAPSHOTS)


@pytest.mark.parametrize("seed, enemy", GAMES)
@pytest.mark.parametrize("team", [0, 1])
def test_a_teams_champions_do_the_same_in_two_worlds_that_differ_only_in_what_is_hidden_from_it(team, seed, enemy):
    """The assertions are in `twins`: on every tick before anything is exposed the team is told the same in both
    worlds, and each of its champions is in the same state, which holds its place, health, intent, and outcome."""
    reports = comparisons(seed, enemy, team)
    assert sum(report["compared"] for report in reports) >= 30
    assert any(report["revealed"] for report in reports), "the worlds differ in something that the team finds out"


def test_the_behaviour_comparison_covers_every_automatic_movement_and_enough_ticks():
    reports = [report for seed, enemy in GAMES for team in (0, 1) for report in comparisons(seed, enemy, team)]
    compared = [report["compared"] for report in reports]
    assert sum(compared) >= 450 and sum(n >= 10 for n in compared) >= 18, compared
    assert sum(report["revealed"] for report in reports) >= len(reports) // 2
    assert set().union(*(report["kinds"] for report in reports)) >= {Kind.LANE, Kind.FIGHT, Kind.FOLLOW, Kind.CAMP, Kind.WARD, Kind.HOLD}
    assert set().union(*(report["stands"] for report in reports)) == {"wave", "hold"}
    assert set().union(*(report["modes"] for report in reports)) >= {"push", "last_hit", "thin"}
    assert sum(report["blind"] for report in reports) >= 20, "champion ticks spent in a fight whose target is out of view"
    changed = [report["changed"] for report in reports]
    assert sum(len(c["champions"]) for c in changed) >= 40 and sum(c["minions"] for c in changed) >= 200
    assert sum(len(c["camps"]) for c in changed) >= 80 and sum(c["wards"] for c in changed) >= 80 and sum(c["towers"] for c in changed) >= 3


def test_a_fighter_whose_target_is_out_of_view_walks_to_where_its_team_last_saw_it_wherever_the_target_is():
    def chase(hidden_at):
        world = quiet_world({BLUE_TOP: mid(-1300.0), RED_JUNGLE: mid(0.0)})
        world.step()
        submit(world, {BLUE_TOP: FIGHT[JUNGLE]})
        world.champions[RED_JUNGLE].pos = hidden_at
        path = []
        for _ in range(10):
            world.step()
            path.append(world.champions[BLUE_TOP].pos)
        return path, world.champions[BLUE_TOP]

    path, fighter = chase(FOUNTAIN[1])
    assert chase(RIFT.at("red_krugs"))[0] == path and len(set(path)) > 4
    reach = capability_of(fighter).attack_range
    assert RIFT.lane_s("mid", fighter.pos) == pytest.approx(RIVER - reach) and fighter.outcome is Outcome.LOST


@pytest.mark.parametrize("ally_behind_the_wall", [False, True])
def test_a_fighter_follows_a_target_that_steps_behind_a_wall_only_if_its_team_sees_where_the_target_went(ally_behind_the_wall):
    """The fighter stands on the lane's side of the Raptor wall with its target in reach. The target walks one
    tick toward the camp, which takes it behind the wall and 314 units from the fighter. On that tick the fighter
    heads for where its team saw the target at the start of the tick, so it stands in both worlds. On the next it
    walks after the target only if its team saw where the target went."""
    places = {BLUE_TOP: over_the_wall(0.35), RED_MID: over_the_wall(0.48)} | ({BLUE_SUPPORT: RIFT.at("blue_raptors")} if ally_behind_the_wall else {})
    world = quiet_world(places)
    fighter, target = world.champions[BLUE_TOP], world.champions[RED_MID]
    world.step()
    submit(world, {BLUE_TOP: FIGHT[MID], RED_MID: move("enemy_raptors")})
    assert RIFT.separation(places[BLUE_TOP], target.pos) > capability_of(fighter).attack_range + 100.0
    assert not RIFT.sees(places[BLUE_TOP], target.pos, SIGHT) and sees(world, 0, target.pos) == ally_behind_the_wall
    assert fighter.pos == places[BLUE_TOP], "no fighter reacts on the tick its target moves"
    world.step()
    assert sees(world, 0, target.pos) == ally_behind_the_wall
    assert (fighter.pos != places[BLUE_TOP]) == ally_behind_the_wall


def own_end(team: int, from_own_end: float) -> float:
    """A mid lane coordinate by its distance from a team's own end."""
    return from_own_end if team == 0 else RIFT.lanes["mid"].length - from_own_end


def laner_ahead_of_a_wave(team: int, wave: float | None = 7000.0, ward: bool = False, ally: bool = False, minion: bool = False) -> World:
    """Mid lane from a team's own end: its lead minion at 11,500, its mid laner at 9,000 with a push order, and
    an enemy wave behind the laner at `wave`, where nothing of the team sees it. A ward, an ally, or a second
    minion of the team near the wave sees it. The laner has walked one tick when this returns."""
    laner, foe = team * 5 + MID, 1 - team
    places = {laner: lane_place(team, "mid", 9000.0)}
    if ally:
        places[team * 5 + TOP] = lane_place(team, "mid", wave - 300.0)
    world = quiet_world(places)
    sim = world.lanes["mid"]
    sim.add_minion(team, Minion.MELEE, own_end(team, 11_500.0))
    if wave is not None:
        sim.add_minion(foe, Minion.MELEE, own_end(team, wave), count=3)
    if minion:
        sim.add_minion(team, Minion.CASTER, own_end(team, wave - 900.0))
    if ward:
        world.ward(team * 5 + JUNGLE, lane_place(team, "mid", wave - 300.0), WARD_SIGHT, 90.0, MAX_WARDS)
    submit(world, {laner: lane("mid", "push")})
    return world


def leads(world: World, team: int) -> tuple[float | None, float | None]:
    """The lead minion of a team in mid lane and of its enemy, as distances from the team's own end."""
    mine = max((own_end(team, m.s) for m in world.lanes["mid"].minions[team]), default=None)
    theirs = min((own_end(team, m.s) for m in world.lanes["mid"].minions[1 - team]), default=None)
    return mine, theirs


@pytest.mark.parametrize("team", [0, 1])
def test_a_laner_walks_with_its_own_wave_wherever_an_enemy_wave_that_its_team_does_not_see_is_or_is_not(team):
    laner = team * 5 + MID
    worlds = [laner_ahead_of_a_wave(team), laner_ahead_of_a_wave(team, wave=5000.0), laner_ahead_of_a_wave(team, wave=None)]
    for _ in range(12):
        own, enemy = leads(worlds[0], team)
        me = worlds[0].champions[laner]
        expected = RIFT.advance(me.pos, lane_place(team, "mid", own), speed_of(worlds[0], me) * TICK_S)
        assert not lit(sources_of(worlds[0], team), lane_place(team, "mid", enemy))
        assert observe(worlds[0], laner).lanes[LANES.index("mid")].enemy_lead is None
        for world in worlds:
            world.step()
            assert world.champions[laner].pos == expected
    there = [leads(world, team)[1] for world in worlds]
    assert there[0] == pytest.approx(there[1] + 2000.0) and there[0] < 5000.0 and there[2] is None, "the waves marched on, 2,000 units apart"


@pytest.mark.parametrize("source", ["ward", "ally", "minion"])
@pytest.mark.parametrize("team", [0, 1])
def test_a_laner_takes_its_stance_against_a_wave_once_a_ward_an_ally_or_a_minion_of_its_team_sees_it(team, source):
    laner = team * 5 + MID
    world = laner_ahead_of_a_wave(team, **{source: True})
    me = world.champions[laner]
    reach = min(capability_of(me).attack_range, STAND_OFF)
    assert not RIFT.sees(me.pos, lane_place(team, "mid", leads(world, team)[1]), SIGHT), "the laner itself does not see the wave"
    for _ in range(3):
        own, enemy = leads(world, team)
        view = observe(world, laner).lanes[LANES.index("mid")]
        assert (view.enemy_lead, view.enemy_near, view.enemy_age_s, view.contact) == (pytest.approx(enemy), (3, 0, 0), 0.0, False)
        expected = RIFT.advance(me.pos, lane_place(team, "mid", enemy - reach), speed_of(world, me) * TICK_S)
        back = RIFT.distance(me.pos, lane_place(team, "mid", own))
        world.step()
        assert me.pos == expected and RIFT.distance(me.pos, lane_place(team, "mid", own)) > back, "it turns from its own wave to the enemy's"


# 400 units of walking out on two arms of a junction. The first two are M7's cases. The corners are worked from
# the M8 map's nodes: top_corner (1968, 12459), top_corner_a (1508, 11601), top_river (4400, 9600). The lane arm
# is 973 long, so 400 along it is (1779, 12106). The river arm is 3,753 long and 1.15 times that to walk, so 400
# walked is 348 straight, at (2193, 12194). The two are 424 apart. The same for bot_corner gives 450.
JUNCTIONS = [("mid_river", "blue_mid_t1", "top_river", 475.0), ("mid_river", "red_mid_t1", "bot_river", 490.0),
             ("top_corner", "top_corner_a", "top_river", 424.0), ("bot_corner", "bot_corner_b", "bot_river", 450.0)]


def shown(world: World, viewer: int, enemy: int):
    return observe(world, viewer).enemies[enemy % 5]


@pytest.mark.parametrize("node, arm, other_arm, apart", JUNCTIONS)
def test_two_champions_on_two_arms_of_a_junction_see_each_other(node, arm, other_arm, apart):
    a, b = walk(node, arm, 400.0), walk(node, other_arm, 400.0)
    assert RIFT.distance(a, b) == pytest.approx(800.0) and RIFT.separation(a, b) == pytest.approx(apart, abs=1.0)
    world = quiet_world({BLUE_MID: a, RED_JUNGLE: b})
    world.step()
    assert sees(world, 0, b) and sees(world, 1, a)
    hp, upgrades = world.champions[RED_JUNGLE].hp, world.champions[RED_JUNGLE].upgrades
    assert shown(world, BLUE_MID, RED_JUNGLE) == EnemyView(to_frame(0, b), None, hp, 1, upgrades), "seen for the first time, so with no earlier place"
    assert shown(world, RED_JUNGLE, BLUE_MID) is not None
    assert all(o.enemies[JUNGLE] is not None for o in observe_team(world, 0)), "teammates share the view"


# M7's open-ground case: mid lane 800 units from the river crossing and the river 920 walked units out. The straight
# line is 1,012 on the blue side and 1,046 on the red side, and the walk is 1,720, longer than a champion sees.
@pytest.mark.parametrize("lane_arm, river_arm, apart", [("blue_mid_t1", "top_river", 1012.0), ("red_mid_t1", "bot_river", 1046.0)])
def test_a_champion_in_mid_lane_and_one_in_the_river_see_each_other_over_open_ground_although_the_walk_is_longer_than_sight(lane_arm, river_arm, apart):
    laner, in_river = walk("mid_river", lane_arm, 800.0), walk("mid_river", river_arm, 920.0)
    assert RIFT.separation(laner, in_river) == pytest.approx(apart, abs=1.0) and RIFT.distance(laner, in_river) == pytest.approx(1720.0)
    world = quiet_world({BLUE_MID: laner, RED_JUNGLE: in_river})
    world.step()
    assert sees(world, 0, in_river) and sees(world, 1, laner)
    assert shown(world, BLUE_MID, RED_JUNGLE) is not None and shown(world, RED_JUNGLE, BLUE_MID) is not None


# M7's wall cases: the place on the lane nearest a camp behind the lane wall, 1,171 from the blue Raptors in mid
# lane and 954 from the blue Gromp in top lane. The map is no exact mirror: the red camps are 1,197 and 1,101 away.
@pytest.mark.parametrize("name, camp, apart", [("mid", "blue_raptors", 1171.0), ("top", "blue_gromp", 954.0), ("mid", "red_raptors", 1197.0),
                                               ("bot", "red_gromp", 1101.0)])
def test_a_champion_in_lane_and_one_at_the_camp_behind_the_lane_wall_do_not_see_each_other_within_sight_range(name, camp, apart):
    laner, behind = RIFT.lane_pos(name, RIFT.project_to_lane(name, *RIFT.xy(RIFT.at(camp)))), RIFT.at(camp)
    assert RIFT.separation(laner, behind) == pytest.approx(apart, abs=1.0) and RIFT.separation(laner, behind) < SIGHT
    world = quiet_world({BLUE_MID: laner, RED_JUNGLE: behind})
    for _ in range(3):
        world.step()
        assert not sees(world, 0, behind) and not sees(world, 1, laner)
        assert shown(world, BLUE_MID, RED_JUNGLE) is None and shown(world, RED_JUNGLE, BLUE_MID) is None
    assert observe(world, BLUE_MID).remembered[JUNGLE] is None, "the team has never seen it"


def test_a_champion_that_walks_out_from_behind_the_wall_is_seen_from_the_tick_the_map_gives_and_lost_when_it_walks_out_of_range():
    laner = RIFT.lane_pos("mid", RIFT.project_to_lane("mid", *RIFT.xy(RIFT.at("blue_raptors"))))
    world = quiet_world({BLUE_MID: laner, RED_JUNGLE: RIFT.at("blue_raptors")})
    orders = {0: move("enemy_mid_t1"), 9: move("enemy_base")}
    seen, truth = [], []
    for tick in range(26):
        submit(world, {RED_JUNGLE: orders[tick]} if tick in orders else {})
        seen.append(shown(world, BLUE_MID, RED_JUNGLE) is not None)
        truth.append(RIFT.sees(laner, world.champions[RED_JUNGLE].pos, SIGHT))
        assert seen[-1] == (shown(world, RED_JUNGLE, BLUE_MID) is not None) == sees(world, 0, world.champions[RED_JUNGLE].pos)
    assert seen == truth
    first, last = seen.index(True), len(seen) - seen[::-1].index(True)
    assert 0 < first < last < len(seen) and all(seen[first:last]), "hidden behind the wall, then seen, then out of range"


def test_a_ranged_attack_reaches_a_target_behind_a_wall_on_exactly_the_ticks_on_which_a_ward_of_the_attackers_team_stands():
    """The carry and the support stand on the lane's side of the Raptor wall and a red champion on the camp's
    side, 352 units from the carry. The support places a ward on the camp from 611 units, over the wall."""
    world = quiet_world({BLUE_CARRY: over_the_wall(0.35), BLUE_SUPPORT: over_the_wall(0.48), RED_MID: over_the_wall(0.65),
                         BLUE_JUNGLE: RIFT.at("blue_raptors")})
    carry, target = world.champions[BLUE_CARRY], world.champions[RED_MID]
    assert RIFT.separation(carry.pos, target.pos) == pytest.approx(352.0, abs=1.0)
    assert not any(RIFT.sees(world.champions[seat].pos, target.pos, SIGHT) for seat in (BLUE_CARRY, BLUE_SUPPORT))
    # The jungler shows the team where the target stands and leaves, so that the carry has a place to fight toward.
    world.step()
    world.champions[BLUE_JUNGLE].pos = FOUNTAIN[0]
    placed_on, lasts = 6, 180
    hits, stood, places = [], [], set()
    for tick in range(placed_on + lasts + 6):
        full = capability_of(target).max_hp
        carry.hp, target.hp = capability_of(carry).max_hp, full
        stood.append(any(s.owner == BLUE_SUPPORT for s in world.sights))
        submit(world, {BLUE_CARRY: FIGHT[MID]} | ({BLUE_SUPPORT: act(Kind.WARD, "own_raptors")} if tick == placed_on else {}))
        hits.append(target.hp < full)
        places.add((carry.pos, target.pos))
    assert world.champions[BLUE_SUPPORT].outcome is Outcome.PLACED and len(places) == 1, "nobody moved"
    assert hits == [False] * (placed_on + 1) + [True] * lasts + [False] * 5
    assert hits == stood


@pytest.mark.parametrize("team", [0, 1])
def test_enemy_stealth_wards_placed_anywhere_change_nothing_that_a_team_is_told_now_or_later(team):
    world = game(8, "varied", team, 1200)
    foe = 1 - team
    # An enemy that acts on what its wards show it would show the team the difference, so the enemy stands still.
    for c in team_of(world, foe):
        c.intent = HOLD
    world.ward(team * 5 + JUNGLE, world.champions[team * 5 + JUNGLE].pos, WARD_SIGHT, 90.0, MAX_WARDS)
    twin = World.restore(world.snapshot())
    hidden = [c.pos for c in team_of(world, foe) if c.hp > 0 and not lit(sources_of(world, team), c.pos)]
    assert hidden, "an enemy that a ward of its own team would show, if such a ward were a sight source of the other team"
    spots = [c.pos for c in team_of(world, team)] + hidden + [site.pos for site in SITES]
    for n, pos in enumerate(spots[:15]):
        twin.ward(foe * 5 + n % 5, pos, WARD_SIGHT, 90.0, MAX_WARDS)
    assert sum(s.team == foe and s.owner >= 0 for s in twin.sights) == 15
    assert all(mine != theirs for mine, theirs in zip(knowledge(twin, foe), knowledge(world, foe)))
    for step in range(40):
        told = knowledge(world, team)
        assert knowledge(twin, team) == told, f"step {step}"
        own = tuple(WardView(to_frame(team, s.pos), (s.expires - world.tick) * TICK_S) for s in world.sights if s.team == team and s.owner >= 0)
        assert all(o.wards == own for o, _, _ in told)
        actions = None
        if world.tick % world.config.decision_ticks == 0:
            mine = [varied(o, keyed_uniform(world.seed, Stream.POLICY, team * 5 + role, world.tick)) for role, (o, _, _) in enumerate(told)]
            actions = mine + [KEEP] * 5 if team == 0 else [KEEP] * 5 + mine
        world.step(actions)
        twin.step(actions)
    assert team_of(twin, team) == team_of(world, team)


@pytest.mark.parametrize("team", [0, 1])
def test_a_last_seen_record_keeps_place_and_health_while_the_enemy_walks_off_and_heals_and_its_age_grows_by_the_clock(team):
    viewer, enemy = team * 5 + MID, (1 - team) * 5 + JUNGLE
    world = quiet_world({viewer: lane_place(team, "mid", 5000.0), enemy: lane_place(team, "mid", 5300.0)})
    world.champions[enemy].hp = 200.0
    submit(world, {enemy: move("own_base")})
    last, ages = None, []
    for _ in range(30):
        world.step()
        o = observe(world, viewer)
        if o.enemies[JUNGLE] is not None:
            last = o.remembered[JUNGLE]
            assert last == LastSeen(to_frame(team, world.champions[enemy].pos), world.champions[enemy].hp, 1, world.champions[enemy].upgrades, 0.0)
            assert not ages, "once out of view it stays out"
        else:
            ages.append(o.remembered[JUNGLE].age_s)
            assert o.remembered[JUNGLE][:4] == last[:4]
            assert all(mate.remembered == o.remembered for mate in observe_team(world, team))
    assert ages == [TICK_S * n for n in range(1, len(ages) + 1)] and len(ages) > 20
    assert RIFT.separation(world.champions[enemy].pos, lane_place(team, "mid", last.place.s)) > 3000.0
    assert world.champions[enemy].hp > last.hp + 10.0


@pytest.mark.parametrize("team", [0, 1])
def test_a_remembered_wave_keeps_its_lead_and_size_out_of_sight_and_is_forgotten_when_the_team_sees_its_place_empty(team):
    viewer, scout, foe = team * 5 + MID, team * 5 + TOP, 1 - team
    world = quiet_world({viewer: lane_place(team, "mid", 5000.0)})
    sim = world.lanes["mid"]
    sim.add_minion(foe, Minion.MELEE, own_end(team, 6000.0), count=3)
    sim.add_minion(foe, Minion.CASTER, own_end(team, 6300.0), count=2)
    sim.add_minion(foe, Minion.SIEGE, own_end(team, 7600.0))

    def view():
        return observe(world, viewer).lanes[LANES.index("mid")]

    for _ in range(3):
        world.step()
        assert (view().enemy_lead, view().enemy_near, view().enemy_age_s) == (pytest.approx(leads(world, team)[1]), (3, 2, 0), 0.0)
    frozen = view()
    world.champions[viewer].pos = FOUNTAIN[team]
    for n in range(1, 13):
        world.step()
        assert (view().enemy_lead, view().enemy_near, view().enemy_age_s) == (frozen.enemy_lead, (3, 2, 0), n * TICK_S)
    assert leads(world, team)[1] < frozen.enemy_lead - 1900.0, "the wave has marched on"
    world.champions[scout].pos = lane_place(team, "mid", frozen.enemy_lead + 1400.0)
    world.step()
    assert (view().enemy_lead, view().enemy_age_s) == (frozen.enemy_lead, 13 * TICK_S), "a look that does not reach the remembered place changes nothing"
    world.champions[scout].pos = lane_place(team, "mid", frozen.enemy_lead + 1000.0)
    world.step()
    assert (view().enemy_lead, view().enemy_near, view().enemy_age_s, view().contact) == (None, (0, 0, 0), 0.0, False)
    assert not lit(sources_of(world, team), lane_place(team, "mid", leads(world, team)[1])), "the team learned it from the empty place alone"


# Reference row F1 gives a ward 90 s at average champion level 1 and 120 s at 18, and a recharge of 210 s and 90 s.
# On the straight line between, nine champions of level 1 and one of level 18 (average 2.7) give 93 s and 198 s,
# and ten of level 4 give 95.29 s and 188.82 s, which round up to 191 and 378 ticks.
LEVELS = [((1,) * 10, 180, 420), ((18,) * 10, 240, 180), ((1,) * 9 + (18,), 186, 396), ((4,) * 10, 191, 378)]


@pytest.mark.parametrize("levels, lasts, recharge", LEVELS)
def test_a_ward_shows_a_hidden_enemy_for_exactly_its_duration_at_the_average_champion_level(levels, lasts, recharge):
    world = at_levels(quiet_world({BLUE_SUPPORT: over_the_wall(0.48), RED_MID: over_the_wall(0.65)}), levels)
    target = world.champions[RED_MID].pos
    world.step()
    assert shown(world, BLUE_SUPPORT, RED_MID) is None and not sees(world, 0, target)
    submit(world, {BLUE_SUPPORT: act(Kind.WARD, "own_raptors")})
    seen = []
    for _ in range(lasts + 5):
        o = observe(world, BLUE_SUPPORT)
        seen.append(o.enemies[MID] is not None)
        assert seen[-1] == sees(world, 0, target) == (o.remembered[MID].age_s == 0.0)
        left = (lasts - len(seen)) * TICK_S
        assert o.wards == ((WardView(to_frame(0, RIFT.at("blue_raptors")), left),) if seen[-1] else ())
        world.step()
    assert seen == [True] * lasts + [False] * 5
    assert world.sights == [] and shown(world, RED_MID, BLUE_SUPPORT) is None


def test_a_champion_with_a_ward_order_walks_until_the_spot_is_625_units_away_by_the_straight_line_and_places_the_ward_on_the_spot():
    """The jungler comes along a jungle path, which is 1.15 times as long to walk as it is straight. Two ticks
    of walking leave 885 units of path, 770 straight. The third leaves 700, 609 straight: in range by the straight
    line and not by the walk."""
    spot = RIFT.at("blue_raptors")
    world = quiet_world({BLUE_JUNGLE: walk("blue_raptors", "blue_red", 700.0 + 3 * 185.0)})
    me = world.champions[BLUE_JUNGLE]
    assert speed_of(world, me) * TICK_S == 185.0 and (me.ward_charges, observe(world, BLUE_JUNGLE).me.ward_charges) == (1, 1)
    for tick in range(2):
        was = me.pos
        submit(world, {BLUE_JUNGLE: act(Kind.WARD, "own_raptors")} if tick == 0 else {})
        assert RIFT.distance(was, me.pos) == pytest.approx(185.0) and RIFT.separation(me.pos, spot) > PLACE_RANGE
        assert world.sights == [] and (ACTIONS[me.intent].kind, me.outcome, me.ward_charges) == (Kind.WARD, Outcome.NONE, 1)
    world.step()
    assert RIFT.separation(me.pos, spot) == pytest.approx(700.0 / 1.15) and RIFT.distance(me.pos, spot) == pytest.approx(700.0)
    assert world.sights == [Sight(0, spot, WARD_SIGHT, 2 + 180, BLUE_JUNGLE)]
    o = observe(world, BLUE_JUNGLE)
    assert (o.me.intent, o.me.outcome, o.me.outcome_age_s, o.me.ward_charges) == (HOLD, Outcome.PLACED, TICK_S, 0)
    assert o.wards == (WardView(to_frame(0, spot), 179 * TICK_S),)
    assert not any(legal_mask(o)[i] for i in WARDS), "no charge, no ward"
    stood = me.pos
    submit(world, {BLUE_JUNGLE: act(Kind.WARD, "own_red")})
    for _ in range(3):
        world.step()
    assert me.pos != stood and len(world.sights) == 1 and legal_mask(observe(world, BLUE_JUNGLE))[KEEP], "it walks on and waits for a charge"


@pytest.mark.parametrize("levels, lasts, recharge", LEVELS)
def test_a_spent_ward_charge_comes_back_after_the_recharge_time_at_the_average_champion_level_to_the_tick(levels, lasts, recharge):
    world = at_levels(quiet_world({BLUE_JUNGLE: walk("blue_raptors", "blue_red", 300.0)}), levels)
    me = world.champions[BLUE_JUNGLE]
    me.ward_charges, me.ward_tick = MAX_CHARGES, -1
    assert observe(world, BLUE_JUNGLE).me.ward_ready_s == 0.0 and all(legal_mask(observe(world, BLUE_JUNGLE))[i] for i in WARDS)
    submit(world, {BLUE_JUNGLE: act(Kind.WARD, "own_raptors")})
    charges, ready = [], []
    for _ in range(recharge + 3):
        view = observe(world, BLUE_JUNGLE).me
        charges.append(view.ward_charges)
        ready.append(view.ward_ready_s)
        world.step()
    assert charges == [1] * recharge + [2] * 3
    assert ready == [(recharge - n) * TICK_S for n in range(1, recharge + 1)] + [0.0] * 3


def test_a_champion_starts_with_one_ward_charge_gets_the_second_after_210_s_and_never_holds_more_than_two():
    world = quiet_world({})
    held = []
    for _ in range(1300):
        held.append({c.ward_charges for c in world.champions})
        world.step()
    check_invariants(world)
    assert held == [{1}] * 421 + [{2}] * 879
    assert all((o.me.ward_charges, o.me.ward_ready_s) == (MAX_CHARGES, 0.0) for o in observe_team(world, 0))


def test_a_fourth_ward_and_every_later_one_removes_the_champions_oldest_and_nobody_elses():
    spots = ["own_raptors", "own_red", "own_krugs", "own_wolves", "own_blue"]
    world = quiet_world({BLUE_SUPPORT: RIFT.at("blue_gromp"), RED_JUNGLE: RIFT.at("red_gromp")})
    submit(world, {BLUE_SUPPORT: act(Kind.WARD, "own_gromp"), RED_JUNGLE: act(Kind.WARD, "own_gromp")})
    me = world.champions[BLUE_JUNGLE]
    for n, node in enumerate(spots, start=1):
        me.pos, me.ward_charges, me.ward_tick = RIFT.at(node.replace("own", "blue")), MAX_CHARGES, -1
        submit(world, {BLUE_JUNGLE: act(Kind.WARD, node)})
        check_invariants(world)
        mine = [s.pos for s in world.sights if s.owner == BLUE_JUNGLE]
        assert mine == [RIFT.at(node.replace("own", "blue")) for node in spots[max(0, n - MAX_WARDS):n]]
        assert [s.owner for s in world.sights if s.owner != BLUE_JUNGLE] == [BLUE_SUPPORT, RED_JUNGLE]
        places = [ward.place for ward in observe(world, BLUE_TOP).wards]
        assert places == [to_frame(0, RIFT.at("blue_gromp"))] + [to_frame(0, pos) for pos in mine], "the team's wards, the oldest first"
        assert len(observe(world, RED_TOP).wards) == 1


def brawl(config: Config, allowance: float) -> World:
    """The blue mid laner off its lane, beside the blue Raptors and out of its tower's range, with a red jungler
    in reach of it and a red top laner in view. The jungler has hit the laner on the tick before."""
    world = quiet_world({BLUE_MID: over_the_wall(0.80), RED_JUNGLE: over_the_wall(0.85), RED_TOP: over_the_wall(0.92)}, config, towers=True)
    world.champions[BLUE_MID].allowance = allowance
    world.step()
    submit(world, {RED_JUNGLE: FIGHT[MID]})
    submit(world, {RED_JUNGLE: HOLD})
    return world


def test_a_laner_with_roam_allowance_may_ward_and_is_charged_as_roaming_while_it_is_off_its_lane():
    world = quiet_world({BLUE_MID: RIFT.at("blue_mid_t1")}, towers=True)
    o = observe(world, BLUE_MID)
    assert (o.me.home, o.me.duty, o.me.allowance) == ("mid", Duty.ON_LANE, 90.0) and all(legal_mask(o)[i] for i in WARDS)
    submit(world, {BLUE_MID: act(Kind.WARD, "own_raptors")})
    for n in range(1, 9):
        view = observe(world, BLUE_MID).me
        assert view.place.route != "mid" and (view.duty, view.allowance) == (Duty.ROAMING, 90.0 - n * TICK_S)
        world.step()
    assert view.outcome is Outcome.PLACED and len(observe(world, BLUE_MID).wards) == 1


def test_a_returning_laner_may_not_ward_and_keeps_its_self_defence_its_ways_home_and_its_recall():
    world = brawl(EVERY_TICK, allowance=0.0)
    o = observe(world, BLUE_MID)
    mask = legal_mask(o)
    assert o.me.allowance < 0 and o.me.ward_charges == 1 and o.me.hurt_by == (False, True, False, False, False)
    assert not any(mask[i] for i in WARDS)
    assert o.enemies[TOP] is not None and mask[FIGHT[JUNGLE]] and not mask[FIGHT[TOP]]
    assert mask[RECALL] and mask[move("own_base")] and mask[move("own_mid_t1")] and all(mask[lane("mid", mode)] for mode in ("passive", "push"))
    assert not mask[move("own_raptors")] and not mask[move("enemy_base")] and not mask[lane("top", "passive")] and not mask[HOLD] and not mask[KEEP]
    submit(world, {BLUE_MID: act(Kind.WARD, "own_raptors")})
    assert not legal_mask(observe(world, BLUE_MID))[KEEP], "nor keep a ward order that it has"
    world = brawl(EVERY_TICK, allowance=0.0)
    for n in range(12):
        assert legal_mask(observe(world, BLUE_MID))[FIGHT[JUNGLE]] == (n < 9), "the self-defence window is 5 s from the hit"
        assert shown(world, BLUE_MID, RED_JUNGLE) is not None
        world.step()


def test_a_laner_with_allowance_and_one_under_no_restriction_keep_every_ward_and_every_fight_in_view():
    for world in (brawl(EVERY_TICK, allowance=30.0), brawl(Config(decision_ticks=1, roam_restricted=False), allowance=0.0)):
        o = observe(world, BLUE_MID)
        mask = legal_mask(o)
        assert all(mask[i] for i in WARDS) and mask[FIGHT[JUNGLE]] and mask[FIGHT[TOP]]
        assert mask[move("own_raptors")] and mask[move("enemy_base")] and mask[HOLD] and mask[KEEP] and mask[RECALL]
        assert not mask[lane("top", "passive")], "the lane stays fixed"
    assert o.me.duty is None and observe(brawl(EVERY_TICK, allowance=30.0), BLUE_MID).me.duty is Duty.ROAMING


@pytest.mark.parametrize("team", [0, 1])
def test_a_minion_shows_its_team_an_enemy_on_its_lane_within_1200_units_along_the_lane_and_not_beyond(team):
    foe = 1 - team
    near, far = foe * 5 + TOP, foe * 5 + CARRY
    world = quiet_world({near: lane_place(team, "mid", 7000.0), far: lane_place(team, "mid", 9000.0)})
    world.lanes["mid"].add_minion(team, Minion.MELEE, own_end(team, 6000.0))
    for gap, seen in ((1200.0, True), (1201.0, False), (-1200.0, True), (-1201.0, False)):
        assert sees(world, team, lane_place(team, "mid", 6000.0 + gap)) == seen
    assert not sees(world, foe, lane_place(team, "mid", 7000.0 - SIGHT - 1.0)), "the minion is no source of the other team"
    world.step()
    viewer = observe(world, team * 5)
    assert viewer.enemies[TOP] is not None and viewer.enemies[CARRY] is None and viewer.remembered[CARRY] is None
    assert not any(RIFT.sees(c.pos, world.champions[near].pos, SIGHT) for c in team_of(world, team)), "no champion of the team sees it"


def test_a_minion_shows_its_team_an_enemy_beside_its_lane_by_the_maps_sight_measure():
    """The open-ground case and the wall case, with a minion in the laner's place: the river 1,012 units from
    mid lane is seen, and the Raptor camp 1,171 units behind the lane wall is not."""
    in_river = walk("mid_river", "top_river", 920.0)
    world = quiet_world({RED_JUNGLE: in_river, RED_TOP: RIFT.at("blue_raptors")})
    sim = world.lanes["mid"]
    sim.add_minion(0, Minion.CASTER, RIVER - 800.0)
    sim.add_minion(0, Minion.CASTER, RIFT.project_to_lane("mid", *RIFT.xy(RIFT.at("blue_raptors"))))
    minions = [RIFT.lane_pos("mid", m.s) for m in sim.minions[0]]
    assert [RIFT.separation(minions[0], in_river), RIFT.separation(minions[1], RIFT.at("blue_raptors"))] == [pytest.approx(1012.0, abs=1.0), pytest.approx(1171.0, abs=1.0)]
    assert sees(world, 0, in_river) and not sees(world, 0, RIFT.at("blue_raptors"))
    beside = [pos for pos in PLACES if RIFT.lane_s("mid", pos) is None]
    by_minion = [any(RIFT.sees(at, pos, MINION_SIGHT) for at in minions) for pos in beside]
    assert [sees(world, 0, pos) for pos in beside] == [lit(sources_of(world, 0), pos) for pos in beside]
    assert sum(by_minion) >= 3 and all(sees(world, 0, pos) for pos, seen in zip(beside, by_minion) if seen)
    world.step()
    assert shown(world, BLUE_TOP, RED_JUNGLE) is not None and shown(world, BLUE_TOP, RED_TOP) is None


def test_sight_along_a_lane_never_claims_what_the_maps_measure_denies_and_no_place_on_a_lane_sees_a_camp_within_minion_sight():
    pairs = camps = 0
    for name, route in RIFT.lanes.items():
        for step in range(int(route.length // 50)):
            at = RIFT.lane_pos(name, step * 50.0)
            for ahead in (*range(50, 1350, 50), 1349.9):
                if step * 50.0 + ahead <= route.length:
                    assert RIFT.sees(at, RIFT.lane_pos(name, step * 50.0 + ahead), SIGHT), f"{name} lane at {step * 50} and {ahead} further"
                    pairs += 1
        for step in range(int(route.length // 20) + 1):
            at = RIFT.lane_pos(name, step * 20.0)
            assert not any(RIFT.sees(at, site.pos, MINION_SIGHT) for site in SITES), f"{name} lane at {step * 20}"
            camps += sum(RIFT.separation(at, site.pos) <= MINION_SIGHT for site in SITES)
    assert pairs > 30_000 and camps > 100, "camps stand within a minion's sight range of the lanes, behind walls"


@pytest.mark.parametrize("seed, enemy", GAMES[1:3])
def test_in_a_running_game_a_team_sees_no_place_that_its_sources_do_not_see_by_the_maps_measure(seed, enemy):
    seen = hidden = 0
    for ticks in SNAPSHOTS:
        world = game(seed, enemy, 0, ticks)
        for team in (0, 1):
            sources = sources_of(world, team)
            for pos in PLACES:
                by_map = lit(sources, pos)
                if all(RIFT.lane_s(name, pos) is None for name in LANES):
                    assert sees(world, team, pos) == by_map
                else:
                    assert by_map or not sees(world, team, pos)
                seen += by_map
                hidden += not by_map
    assert seen > 300 and hidden > 300


# The kernel takes sight along a lane from the lane coordinate, which is up to about 40 units longer than the
# straight line across the bends of a corner. A minion that near the edge of sight is left out of the comparison.
BAND = 60.0


def lane_truth(world: World, team: int, name: str):
    """One lane as the team's sources see it by the map's measure: the `LaneView` fields that follow from the
    minions, or None if an enemy minion stands within `BAND` of the edge of the team's sight."""
    sim, sources = world.lanes[name], sources_of(world, team)

    def framed(s: float) -> float:
        return s if team == 0 else sim.length - s

    def wave(spots: list, toward_red: bool) -> tuple:
        """The minion furthest along its march, and the minions within the wave span of it by kind."""
        if not spots:
            return None, (0, 0, 0)
        lead = max(s for s, _ in spots) if toward_red else min(s for s, _ in spots)
        return lead, tuple(sum(kind == k and abs(s - lead) <= WAVE_SPAN for s, kind in spots) for k in Minion)

    seen = []
    for m in sim.minions[1 - team]:
        pos = RIFT.lane_pos(name, m.s)
        if lit(sources, pos, -BAND):
            seen.append((m.s, m.rules.kind))
        elif lit(sources, pos, BAND):
            return None
    own, own_near = wave([(m.s, m.rules.kind) for m in sim.minions[team]], team == 0)
    foe, foe_near = wave(seen, team == 1)
    contact = own is not None and foe is not None and RIFT.separation(RIFT.lane_pos(name, own), RIFT.lane_pos(name, foe)) <= ACQUIRE + 1e-6
    return (None if own is None else framed(own), own_near, None if foe is None else framed(foe), foe_near, contact)


@pytest.mark.parametrize("seed, enemy", GAMES[1:3])
def test_the_lane_fields_of_an_observation_are_the_lanes_truth_while_the_team_sees_the_enemy_wave_and_rivals_are_public(seed, enemy):
    world = game(seed, enemy, 0, 600)
    policies = (varied, ENEMIES[enemy])
    counts = {"seen": 0, "unseen": 0, "contact": 0, "apart": 0, "edge": 0, "hidden rival": 0, "dead rival": 0, "tower known": 0, "tower unseen": 0}
    for step in range(240):
        advance(world, policies)
        if step % 3:
            continue
        for team in (0, 1):
            o = observe(world, team * 5 + step % 5)
            foes = team_of(world, 1 - team)
            assert o.rivals == tuple(Rival(level_of(c.xp), max(0, c.respawn_tick + 1 - world.tick) * TICK_S) for c in foes)
            counts["hidden rival"] += sum(c.hp > 0 and view is None for c, view in zip(foes, o.enemies))
            counts["dead rival"] += sum(c.hp <= 0 and rival.dead_s > 0 and view is None for c, view, rival in zip(foes, o.enemies, o.rivals))
            for name, view in zip(LANES, o.lanes):
                sim = world.lanes[name]
                assert view.own_towers == tuple(max(0.0, tower.hp) for tower in sim.towers[team])
                sources = sources_of(world, team)
                for tier, tower in enumerate(sim.towers[1 - team]):
                    place = RIFT.lane_pos(name, tower.s)
                    known = tower.hp <= 0 or tower is not sim.front_tower(1 - team) or lit(sources, place, -BAND)
                    if known:
                        assert (view.enemy_towers[tier], view.enemy_towers_age_s[tier]) == (max(0.0, tower.hp), 0.0), f"{name} tier {tier}, tick {world.tick}"
                        counts["tower known"] += 1
                    elif not lit(sources, place, BAND):
                        assert view.enemy_towers_age_s[tier] > 0.0 and view.enemy_towers[tier] >= tower.hp, f"{name} tier {tier}, tick {world.tick}"
                        counts["tower unseen"] += 1
                truth = lane_truth(world, team, name)
                if truth is None:
                    counts["edge"] += 1
                    continue
                own, own_near, foe, foe_near, contact = truth
                assert (view.own_lead, view.own_near, view.contact) == (pytest.approx(own), own_near, contact), f"{name} lane, team {team}, tick {world.tick}"
                if foe is None:
                    assert view.enemy_age_s != 0.0 or view.enemy_lead is None
                    counts["unseen"] += 1
                else:
                    assert (view.enemy_lead, view.enemy_near, view.enemy_age_s) == (pytest.approx(foe), foe_near, 0.0), f"{name} lane, team {team}, tick {world.tick}"
                    counts["seen"] += 1
                    counts["contact" if contact else "apart"] += 1
    assert counts["seen"] > 150 and counts["unseen"] > 10 and counts["contact"] > 50 and counts["apart"] > 10, counts
    assert counts["edge"] < counts["seen"] / 4 and counts["hidden rival"] > 50 and counts["dead rival"] > 5, counts
    assert counts["tower known"] > 100 and counts["tower unseen"] > 20, counts


def test_an_encoding_has_one_length_holds_finite_numbers_and_is_equal_exactly_when_the_observation_is():
    world = World(Config(), seed=4)
    by_code, by_observation, lengths = {}, {}, set()
    for _ in range(1000):
        if world.tick % world.config.decision_ticks == 0:
            for o in (*observe_team(world, 0), *observe_team(world, 1)):
                code = encode(o)
                lengths.add(len(code))
                assert all(type(value) is float and math.isfinite(value) for value in code)
                assert by_code.setdefault(code, o) == o, "two observations share an encoding"
                assert by_observation.setdefault(o, code) == code
        advance(world, (varied, busy))
    assert len(lengths) == 1 and len(by_code) == len(by_observation) == 2500
    assert encode(observe(World.restore(world.snapshot()), RED_CARRY)) == encode(observe(world, RED_CARRY))


def one_leaf_changed(value, path: tuple = ()):
    """Every copy of a part of an observation that differs from it in one leaf, with the path to that leaf."""
    if is_dataclass(value):
        for f in fields(value):
            for where, changed in one_leaf_changed(getattr(value, f.name), (*path, f.name)):
                yield where, replace(value, **{f.name: changed})
    elif isinstance(value, tuple) and hasattr(value, "_fields"):
        for name in value._fields:
            for where, changed in one_leaf_changed(getattr(value, name), (*path, name)):
                yield where, value._replace(**{name: changed})
    elif isinstance(value, tuple):
        for i, item in enumerate(value):
            for where, changed in one_leaf_changed(item, (*path, i)):
                yield where, value[:i] + (changed,) + value[i + 1:]
    elif value is None:
        filled = {"enemies": EnemyView(Place("mid", 100.0), Place("mid", 80.0), 50.0, 3, 2), "remembered": LastSeen(Place("mid", 100.0), 50.0, 3, 2, 2.0),
                  "was": Place("mid", 80.0), "home": "mid", "duty": Duty.ON_LANE}
        yield path, filled.get(path[-2] if type(path[-1]) is int else path[-1], 1.5)
    elif isinstance(value, bool):
        yield path, not value
    elif isinstance(value, str):
        yield path, "top" if value != "top" else "mid"
    elif isinstance(value, (Outcome, Duty)):
        yield path, type(value)((value + 1) % len(type(value)))
    else:
        yield path, value + 1


def test_every_field_of_an_observation_changes_its_encoding():
    world = busy_moment(8)
    seat = next(c.seat for c in world.champions if c.hp > 0 and len(observe(world, c.seat).wards) > 0
                and any(observe(world, c.seat).enemies) and not all(observe(world, c.seat).enemies))
    o = observe(world, seat)
    code, same, differ = encode(o), [], 0
    assert any(last and not seen for last, seen in zip(o.remembered, o.enemies)), "an enemy that the team remembers and does not see"
    for path, changed in one_leaf_changed(o):
        assert changed != o and len(encode(changed)) == len(code)
        if encode(changed) == code:
            same.append(path)
        else:
            differ += 1
    assert same == [] and differ > 250


def busy_moment(seed: int) -> World:
    """A game at a tick with a ward of each team on the map, a remembered wave out of view, and a fight under way."""
    world = game(seed, "varied", 0, 600)
    for _ in range(600):
        wards = {s.team for s in world.sights if s.owner >= 0}
        stale = any(wave.lead is not None and wave.seen_tick < world.tick for memory in world.memory for wave in memory.waves)
        if wards == {0, 1} and stale and any(ACTIONS[c.intent].kind is Kind.FIGHT for c in world.champions):
            return world
        advance(world, (varied, varied))
    raise AssertionError("the game never has wards of both teams, a remembered wave, and a fight at once")


def test_a_snapshot_taken_with_wards_wave_memory_and_a_fight_under_way_replays_every_digest():
    world = busy_moment(8)
    snapshot = world.snapshot()
    runs = []
    for game in (world, World.restore(snapshot)):
        digests, ended = [], set()
        for _ in range(600):
            advance(game, (varied, varied))
            digests.append(game.digest())
            ended |= {c.outcome for c in game.champions if c.outcome_tick == game.tick - 1}
        runs.append(digests)
    assert runs[0] == runs[1] and len(set(runs[0])) == 600
    assert Outcome.PLACED in ended and ended & {Outcome.LOST, Outcome.KILLED}, "wards were placed and a fight ended in the replayed stretch"
    assert World.restore(snapshot).digest() == World.restore(snapshot).digest() != world.digest()


WARD_CHANGES = {"team": 1, "pos": RIFT.at("red_gromp"), "radius": 901.0, "expires": 77, "owner": BLUE_TOP}
WAVE_CHANGES = {"lead": 4321.0, "near": (1, 0, 0), "seen_tick": 5}


@pytest.mark.parametrize("field", WARD_CHANGES)
def test_the_digest_changes_with_every_field_of_a_ward(field):
    assert set(WARD_CHANGES) == {f.name for f in fields(Sight)}
    world = World()
    world.ward(BLUE_JUNGLE, RIFT.at("blue_gromp"), WARD_SIGHT, 90.0, MAX_WARDS)
    before = world.digest()
    world.sights[0] = replace(world.sights[0], **{field: WARD_CHANGES[field]})
    assert world.digest() != before


@pytest.mark.parametrize("field", WAVE_CHANGES)
def test_the_digest_changes_with_every_field_of_a_wave_memory(field):
    assert set(WAVE_CHANGES) == {f.name for f in fields(WaveMemory)}
    world = World()
    before = world.digest()
    setattr(world.memory[1].waves[2], field, WAVE_CHANGES[field])
    assert world.digest() != before
