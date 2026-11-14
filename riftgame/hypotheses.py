"""Hypotheses about what one team cannot see, and the worlds they make (M7 section 9.3).

A hypothesis gives each enemy champion that the team does not see one activity since the team last saw it (`Plan`).
`realize(info, hypothesis, rollout)` builds a full world from the information state and that history. The activity
decides where the champion stands, its health, mana, XP inside the band of its public level, gold, upgrades, intent,
and the camps it cleared. Every function here takes the information state and nothing else, so none of them can copy
a value that the team does not know (contract 3).

`activity_v0(info, focus)` varies the activities of the focus enemies and puts every other enemy that the team does
not see at its role's default activity. It emits only hypotheses that pass the four checks. Each check raises
`Rejected` with its `Reason` for a hypothesis written by hand.

- UNREACHABLE. The activity cannot be carried out from the last-seen place in the elapsed time.
- IN_VIEW. The champion would stand where the team sees at the decision tick.
- XP_BAND. Its XP leaves the band of its public level.
- CAMP_UNVISITED and UPGRADES_WITHOUT_FOUNTAIN. A camp is cleared that no path visits, or upgrades change without
  a recall.

INCONSISTENT names a hypothesis that breaks the activity table itself. It gives a plan to an enemy in view or dead,
has a laner clear, clears a camp while the history says it was dead or after the team saw it alive, or leaves a
champion that would have died.

Assumed rules, all simulator guesses. The numbers are in `[hypotheses]` of `patch_26_22_m8.toml`.

- An enemy never seen was last seen on its fountain at 0:00 at full health, with what its starting gold buys.
- Kills and respawns are public (M7 section 6.3). An enemy whose latest respawn came after the team last saw it was
  last seen on its fountain on the tick of that respawn, at full health at its level then, holding what its estimated
  gold buys there. A respawn is a visit to the fountain, so its upgrades may differ from those that the team saw.
- Health regenerates at the champion's rate in every activity, and a clear loses the camp's damage for each second
  of fighting. A finished recall gives full health and mana, and so does a respawn since the sighting. Every other
  enemy has `mana_share` of its full mana, because the state keeps no record of an enemy's mana.
- Gold. The ledger holds the starting gold, the passive gold and the support item's passive gold to the decision
  tick, which the clock gives exactly, the role's `farm_gold_per_s` from `farm_from_s` to the last sighting, the
  activity's own income after it, and the base kill gold for an enemy that has been paid for a kill. An estimate
  below the price of the upgrades that the team saw is raised to it.
- XP. The gain is `farm_xp_per_s` for each second at the wave, and the camps' XP with the jungle item's bonus for
  a clear. The XP at the last sighting is the least in the band of the level that the team saw that brings the gain
  into the band of the public level now.
- Stay keeps the last-seen place and holds. Farm stands where a last-hitting champion stands at the lane's front and
  last-hits. Where the team sees that place, the laner farms from the fog. It stands at the first place back along
  its lane that the team does not see, within XP range of that place, and earns the XP but no minion gold. Move walks
  the route at the champion's speed and holds on arrival. Recall channels at the last-seen place, buys with the
  estimated gold on the fountain, and walks toward `recall_return` without Homeguard. It holds where the team's view
  would begin, as a champion may wait in its base. A jungler's recall may carry a path that it clears from the
  fountain on, at full health.
- Clear walks to each camp, waits for a spawn that comes before the decision tick, fights for the camp's health over
  the champion's camp rate, and holds at the last camp. A camp that the team saw empty without learning when it died
  may have been cleared before that sighting. The default path of a jungler takes, one after another, the camp of its
  own side that it can finish soonest, while the clear ends before the decision tick and the XP stays below the top
  of its public level's band. No path names a Rift Scuttler.
- If a role's default activity fails a check, the enemy stays. If that fails it recalls, and a jungler then recalls
  and clears its default path from the fountain. If that fails too it moves to the nearest node, by route from the
  last-seen place, that leaves it out of the team's view. If every such move fails, a jungler clears the longest
  start of its default path that passes. Last, an enemy that the team did not see move on the tick of its
  sighting recalled while the team watched it: the channel began before the sighting and ended on the tick after it.
  A focus enemy none of whose activities passes takes that default.
- Visible and dead enemies keep the public and seen fields and the canonical private fields of the information
  state, with XP at the floor of the band, the estimated gold, and `mana_share` of full mana. A dead enemy buys on
  its fountain.
- Unseen camps follow the team's memory and the timer rule of M7 section 3.3. A known spawn holds. A camp last seen
  alive is alive. A camp last seen empty without a known spawn died `unseen_death_s` before that sighting, and at
  least two ticks before it, because the look's own tick would have shown the death. On M7's clock of 0.5 s, on
  which a decision state is built, that is the latest death the rule allows. It is stated in seconds so that the
  death keeps its game second when the state is refined to a finer tick. A respawn takes the average public level,
  and a first spawn level 1. The river keeps one Scuttler alive or due, or the first pair while nothing shows the
  pair broken, at the node of the latest knowledge, and at the first node when the team sees both empty without a
  known spawn.
- Unseen enemy minions follow the public wave schedule. A remembered wave that the team no longer sees stands at its
  remembered lead with its remembered size. Every other minion of the schedule stands where an untouched march from
  the enemy spawn puts it, short of the team's standing front tower, if that place is behind the team's lead minion,
  every enemy minion that the team sees, and the remembered lead, and out of the team's view. They have full health.
- No enemy ward or shrine. The enemy's memory is rebuilt by rule. It holds what the enemy sees at the decision tick
  in the built world, and the public facts that every team starts with (M7 section 9.3, limits).

`rollout` is accepted for the signature of M7 section 9.3, contract 3. The generator draws nothing, so every rollout
of a hypothesis gives the same world, and rollouts differ by the world seed that the comparison sets.
"""

import math
from dataclasses import dataclass, replace
from enum import Enum, IntEnum
from itertools import product
from typing import NamedTuple

from riftgame import ruleset
from riftgame.champions import (ACTIONS, FOUNTAIN, HOLD, HOME, LANES, NEVER, NODE_POS, NODES, PROGRESSIONS, RECALL, RECALL_S, RIFT,
                                ROLES, Action, Champion, Income, Kind, Outcome, R, capability, level_of, spawn)
from riftgame.economy import JUNGLE_ITEM
from riftgame.info import KILL_MARK, InfoState, band_floor
from riftgame.jungle import SCUTTLERS, SITES
from riftgame.lanes import KINDS, SIDE_SPEED, SPEED, Minion, Mode, WaveClock, stance, unit_stats
from riftgame.map import Pos
from riftgame.vision import _wave_seen, new_memory, remember_team, sees
from riftgame.world import Config, World

H = ruleset.load("patch_26_22_m8")["hypotheses"]
ECONOMY = R["economy"]
ITEM = R["support_item"]
FOUNTAIN_RADIUS = R["fountain"]["regen_radius"]
XP_RANGE = R["minions"]["xp_range"]
# The step in which a champion walking back from its fountain looks for where the team's view begins.
WALK_STEP = 100.0
JUNGLE = ROLES.index("jungle")
SUPPORT = ROLES.index("support")


class Activity(IntEnum):
    STAY = 0
    FARM = 1
    CLEAR = 2
    RECALL = 3
    MOVE = 4


@dataclass(frozen=True, slots=True)
class Plan:
    """One enemy's activity since the team last saw it.

    `path` names camps by their index in `jungle.SITES`, in clearing order. They are the camps of a CLEAR, and for
    RECALL the camps that the jungler clears after it is back on its fountain. `to` is a `MOVE` target in the enemy's
    own frame (`champions.NODES`). With `watched` a RECALL began before the sighting, while the team watched the
    enemy stand there, and ended on the tick after it. `xp` and `upgrades` are an author's values, checked like the
    rest. Without them the activity decides both.
    """

    activity: Activity
    path: tuple[int, ...] = ()
    to: str | None = None
    xp: float | None = None
    upgrades: int | None = None
    watched: bool = False


@dataclass(frozen=True, slots=True)
class Hypothesis:
    """One plan per enemy role. A plan is None for an enemy that the team sees now or that is dead, and for an enemy
    left to its role's default activity, which `complete` fills in. `cleared` names camps that an author states were
    cleared unseen. A path of the hypothesis must visit each."""

    name: str
    weight: float
    plans: tuple[Plan | None, ...]
    cleared: tuple[int, ...] = ()


class Reason(Enum):
    UNREACHABLE = "unreachable from the last-seen place in the elapsed time"
    IN_VIEW = "in the team's view at the decision tick"
    XP_BAND = "XP outside the band of the public level"
    CAMP_UNVISITED = "a camp cleared that no path visits"
    UPGRADES_WITHOUT_FOUNTAIN = "upgrades changed without a visit to the fountain"
    INCONSISTENT = "inconsistent with the activity table"


class Rejected(ValueError):
    def __init__(self, reason: Reason, message: str):
        super().__init__(f"{reason.name}: {message}")
        self.reason = reason


class Dropped(NamedTuple):
    """A plan that `activity_v0` considered for a focus enemy and left out, with the check that failed."""

    role: int
    plan: Plan
    reason: Reason
    message: str


class Generated(NamedTuple):
    hypotheses: tuple[Hypothesis, ...]
    dropped: tuple[Dropped, ...]


class _Sighting(NamedTuple):
    """Where and how the team last knew an enemy. For a respawn after the team's last sighting, `seen_upgrades` are
    the upgrades that the team saw, and `upgrades` what the enemy bought on its fountain from them. It is None for a
    sighting by the team."""

    pos: Pos
    tick: int
    hp: float
    level: int
    upgrades: int
    seen_upgrades: int | None = None


class _Line(NamedTuple):
    """One camp's history. It is alive from tick `up` on at `level`, until a clear, and dead before `up` when `up` lies
    after the decision tick. `seen` marks a camp that the team sees now. `died` is the last tick on which a death that
    the team saw only afterwards can have fallen, or None."""

    up: int
    level: int
    first: bool
    seen: bool = False
    died: int | None = None


class _Trace(NamedTuple):
    """What one enemy's activity leaves at the decision tick."""

    pos: Pos
    intent: int
    intent_tick: int
    channel: int
    outcome: Outcome
    outcome_tick: int
    hp: float
    full_mana: bool
    xp: float
    upgrades: int
    earned: tuple[float, ...]
    clears: tuple[tuple[int, int], ...]


def _action(kind: Kind, target=None) -> int:
    return ACTIONS.index(Action(kind, target))


FARM_ACTION = tuple(None if lane is None else _action(Kind.LANE, (lane, "last_hit", "wave")) for lane in HOME)
OWN_CAMPS = tuple(tuple(i for i, site in enumerate(SITES) if site.node.startswith(side + "_")) for side in ("blue", "red"))


class _Context:
    """What every hypothesis of one information state shares. `base` is the information state's world with the
    unseen enemy minions placed. `sightings` holds, by enemy role, the last sighting of a living enemy that the team
    does not see now, and None for every other. `defaults` holds each such enemy's default plan, or the `Rejected` of
    the last one that failed."""

    __slots__ = ("team", "foe", "tick", "levels", "camp_level", "sightings", "base", "lines", "defaults")

    def __init__(self, info: InfoState):
        self.team, self.foe = info.team, 1 - info.team
        world = info.world()
        self.tick = world.tick
        foes = world.champions[self.foe * 5:self.foe * 5 + 5]
        self.levels = tuple(level_of(c.xp) for c in foes)
        self.camp_level = math.floor(sum(level_of(c.xp) for c in world.champions) / len(world.champions) + 0.5)
        records = world.memory[self.team].enemies
        self.sightings = tuple(None if now or c.respawn_tick >= 0 else _sighting(world, c, record)
                               for c, record, now in zip(foes, records, info.seen))
        _place_minions(world, self.team)
        self.base = world
        self.lines = _lines(world, self.team, self.camp_level)
        self.defaults = tuple(None if sight is None else _default(self, role) for role, sight in enumerate(self.sightings))


_last: list = [None, None]


def _context(info: InfoState) -> _Context:
    """The context of the information state, kept for the last one asked about, since a comparison realizes many
    hypotheses of one."""
    if _last[0] is not info:
        _last[:] = [info, _Context(info)]
    return _last[1]


def _sighting(world: World, c: Champion, record) -> _Sighting:
    """The team's last sighting of the enemy, or its latest respawn where that came later (module docstring)."""
    if record.seen_tick < 0:
        start = spawn(c.seat, world.config.roam_cap_s, -1)
        seen = _Sighting(FOUNTAIN[c.team], 0, start.hp, 1, start.upgrades)
    else:
        seen = _Sighting(record.pos, record.seen_tick, record.hp, record.level, record.upgrades)
    if c.respawned_tick < seen.tick:
        return seen
    upgrades = _shop(world, c.seat, seen.upgrades, c.respawned_tick)
    full = capability(ROLES[c.role], c.respawned_level, upgrades).max_hp
    return _Sighting(FOUNTAIN[c.team], c.respawned_tick, full, c.respawned_level, upgrades, seen.upgrades)


def _band(level: int) -> tuple[float, float]:
    """The XP band of a level, from its floor up to the floor of the next level, or with no top at the cap."""
    return band_floor(level), band_floor(level + 1) if level < ECONOMY["level_cap"] else math.inf


def _place_minions(world: World, team: int) -> None:
    """Put the enemy minions that the team does not see where the wave schedule leaves them (module docstring). A
    lane whose minions the schedule did not all spawn gets none."""
    foe, tick, dt = 1 - team, world.tick, world.config.tick_s
    entries = WaveClock(0.0).due(tick * dt)
    for lane, name in enumerate(LANES):
        sim = world.lanes[name]
        if len(entries) != sim._serial[foe]:
            continue
        ahead, tower = sim.geometry.direction(foe), sim.front_tower(team)
        seen = {m.uid for m in sim.minions[foe]}
        bound = min([ahead * m.s for m in (*sim.minions[team], *sim.minions[foe])] + ([ahead * tower.s] if tower else []), default=math.inf)
        placed = []
        wave = world.memory[team].waves[lane]
        if wave.lead is not None and wave.seen_tick != tick and ahead * wave.lead <= bound:
            for kind, count in enumerate(wave.near):
                there = [k for k, (when, of, _, _) in enumerate(entries) if of == kind and 2 * k + foe not in seen and when < wave.seen_tick * dt]
                placed += [(k, wave.lead) for k in there[max(0, len(there) - count):]]
            bound = min(bound, ahead * wave.lead)
        used = {k for k, _ in placed} | {(uid - foe) // 2 for uid in seen}
        oldest = tick * dt - sim.length / SPEED - 30.0
        for k, (when, kind, number, _) in enumerate(entries):
            if k not in used and when >= oldest:
                s = _marched(sim, foe, when, kind, number, tick, tower)
                if s is not None and ahead * s <= bound:
                    placed.append((k, s))
        if not placed:
            continue
        for k, s in placed:
            when, kind, number, slot = entries[k]
            hp, ad, gold = unit_stats(kind, when)
            sim.minions[foe].append(Minion(2 * k + foe, foe, KINDS[kind], s, hp, hp, ad, gold, number, slot, when, _boost(sim, number, when)))
        sim.invalidate()
        visible = {id(m) for m in _wave_seen(world, team, name)[0]}
        sim.minions[foe][:] = sorted((m for m in sim.minions[foe] if m.uid in seen or id(m) not in visible), key=lambda m: m.uid)
        sim.invalidate()


def _boost(sim, number: int, when: float) -> float:
    """The side-lane speed bonus that `LaneSim._spawn` gives a minion of this wave."""
    if sim.rules.side_lane_speed and sim.geometry.side and number >= SIDE_SPEED["first_wave"] and when < SIDE_SPEED["until_s"]:
        return max(0.0, SIDE_SPEED["bonus"] - SIDE_SPEED["per_wave"] * (number - SIDE_SPEED["first_wave"]))
    return 0.0


def _marched(sim, foe: int, when: float, kind: int, number: int, tick: int, tower) -> float | None:
    """The lane coordinate of an untouched minion at the start of `tick`. It marches from its spawn as `LaneSim._march`
    moves a walker with nothing in its way, and stops short of the team's front tower. None for a minion that has
    reached the team's base, which the lane removes."""
    dt, heading = sim.tick_s, sim.geometry.direction(foe)
    boost, ends = _boost(sim, number, when), SIDE_SPEED["stage_ends_s"]
    first = int(when // dt)
    s, delay = sim.geometry.spawn[foe], max(0.0, when - first * dt)
    for k in range(first, tick):
        stage = sum(k * dt - when >= end for end in ends)
        speed = SPEED if not boost or stage == len(ends) else SPEED + max(0.0, boost - SIDE_SPEED["stage_drop"] * stage)
        s += heading * speed * (dt - delay)
        delay = 0.0
    if tower is not None:
        stop = tower.s - heading * KINDS[kind].stop_range
        return stop if heading * (s - stop) > 0 else s
    end = sim.geometry.spawn[1 - foe]
    return None if heading * (end - s) <= 0 else s


def _lines(world: World, team: int, level: int) -> dict[int, _Line]:
    """Every camp but the Scuttlers, as the team's memory and the timer rule leave it (module docstring)."""
    tick, config = world.tick, world.config
    lines = {}
    for i, (camp, site, mine) in enumerate(zip(world.camps, SITES, world.memory[team].camps)):
        if site.kind.scuttler:
            continue
        respawn, first = config.ticks(site.kind.respawn_s), config.ticks(site.kind.first_spawn_s)
        if mine.seen_tick == tick and camp.hp > 0:
            lines[i] = _Line(NEVER, camp.level, False, seen=True)
        elif mine.seen_tick == tick:
            known, died = mine.spawn_tick >= 0, _unseen_death(config, tick)
            lines[i] = _Line(mine.spawn_tick if known else died + respawn, level, False, True, None if known else died)
        elif mine.spawn_tick >= 0:
            lines[i] = _Line(mine.spawn_tick, 1 if mine.spawn_tick == first else level, mine.spawn_tick == first)
        elif mine.hp > 0:
            lines[i] = _Line(NEVER, mine.level, False)
        else:
            died = _unseen_death(config, mine.seen_tick)
            lines[i] = _Line(died + respawn, level, False, died=died)
    return lines


def _unseen_death(config: Config, seen: int) -> int:
    """The last tick on which a camp that the team saw empty on tick `seen`, without learning its spawn, can have
    died (module docstring)."""
    return seen - max(2, config.ticks(H["unseen_death_s"]))


def _clear(ctx: _Context, sight: _Sighting, path: tuple[int, ...]) -> tuple[tuple[tuple[int, int], ...], float, float, float, float]:
    """Walk the path from the last sighting. Returns the clears as (camp, tick), the time in seconds at which the last
    one ends, the health then, and the gold and XP of the camps. Raises `Rejected` for a path that cannot be cleared
    before the decision tick."""
    dt, tick = ctx.base.config.tick_s, ctx.tick
    can = capability(ROLES[JUNGLE], sight.level, sight.upgrades)
    t, at, hp = sight.tick * dt, sight.pos, sight.hp
    clears, gold, xp = [], 0.0, 0.0
    first = _farm_estimate(ctx.base, JUNGLE, sight.tick) == 0.0
    for i in path:
        line, site = ctx.lines[i], SITES[i]
        arrive = t + RIFT.distance(at, site.pos) / can.move_speed
        fight = site.kind.health(line.level, first=line.first) / can.camp_dps
        before = line.died is not None and math.ceil((arrive + fight) / dt - 1e-9) - 1 <= line.died
        start = arrive if before else max(arrive, line.up * dt)
        end = start + fight
        if end > tick * dt:
            raise Rejected(Reason.UNREACHABLE, f"the clear of {site.node} ends after the decision tick")
        killed = math.ceil(end / dt - 1e-9) - 1
        _check_clear(ctx, i, killed)
        hp = min(can.max_hp, hp + can.hp_regen * (start - t)) + (can.hp_regen - site.kind.damage_per_s) * fight
        if hp <= 0:
            raise Rejected(Reason.INCONSISTENT, f"the jungler would die at {site.node}")
        hp = min(can.max_hp, hp)
        camp_gold, camp_xp = site.kind.reward(line.level)
        gold += camp_gold
        xp += camp_xp + JUNGLE_ITEM["large_monster_bonus_xp"] + (JUNGLE_ITEM["first_large_monster_bonus_xp"] if first else 0.0)
        first = False
        clears.append((i, killed))
        t, at = end, site.pos
    return tuple(clears), t, hp, gold, xp


def _check_clear(ctx: _Context, camp: int, killed: int) -> None:
    """A camp may die on tick `killed` if the team has not seen it since, or has seen it empty since without learning
    the respawn that this death gives."""
    line, mine, site, config = ctx.lines[camp], ctx.base.memory[ctx.team].camps[camp], SITES[camp], ctx.base.config
    if line.seen and line.up == NEVER:
        raise Rejected(Reason.INCONSISTENT, f"the team sees {site.node} alive now")
    if mine.seen_tick > killed:
        respawn = killed + config.ticks(site.kind.respawn_s)
        if mine.hp > 0 or mine.spawn_tick >= 0 or respawn <= mine.seen_tick + config.ticks(site.kind.timer_window_s):
            raise Rejected(Reason.INCONSISTENT, f"the team has seen {site.node} since tick {killed}")


def _default_path(ctx: _Context, sight: _Sighting) -> tuple[int, ...]:
    """The camps of the jungler's own side that it clears one after another, each the one it can finish soonest,
    while the clear ends before the decision tick and its XP stays below the top of its public level's band."""
    low, _ = _band(sight.level)
    _, high = _band(ctx.levels[JUNGLE])
    path: tuple[int, ...] = ()
    while True:
        best = None
        for i in OWN_CAMPS[ctx.foe]:
            if i in path:
                continue
            try:
                _, end, _, _, xp = _clear(ctx, sight, path + (i,))
            except Rejected:
                continue
            if low + xp < high and (best is None or end < best[0]):
                best = (end, i)
        if best is None:
            return path
        path += (best[1],)


def _home(ctx: _Context, role: int, watched: bool = False) -> _Sighting | None:
    """The enemy of `role` back on its fountain after a recall from its last sighting, with full health and what its
    estimated gold buys there, or None while the recall has not ended by the decision tick. A `watched` recall ends on
    the tick after the sighting."""
    sight, world = ctx.sightings[role], ctx.base
    on_fountain = RIFT.separation(sight.pos, FOUNTAIN[ctx.foe]) <= FOUNTAIN_RADIUS
    home = sight.tick + (1 if watched or on_fountain else world.config.ticks(RECALL_S))
    if home > ctx.tick:
        return None
    upgrades = _shop(world, ctx.foe * 5 + role, sight.upgrades, sight.tick)
    return _Sighting(FOUNTAIN[ctx.foe], home, capability(ROLES[role], sight.level, upgrades).max_hp, sight.level, upgrades)


def _cleared_after_recall(ctx: _Context, role: int) -> tuple[int, ...]:
    """The default path of a jungler that clears from its fountain after a recall, or () for any other."""
    back = _home(ctx, role) if role == JUNGLE else None
    return () if back is None else _default_path(ctx, back)


def _default(ctx: _Context, role: int) -> Plan | Rejected:
    """The role's default activity, or the first fallback that passes the checks (module docstring)."""
    sight = ctx.sightings[role]
    first = Plan(Activity.CLEAR, _default_path(ctx, sight)) if role == JUNGLE else Plan(Activity.FARM)
    after = _cleared_after_recall(ctx, role)
    nearest = sorted(NODES, key=lambda node: (RIFT.distance(sight.pos, NODE_POS[ctx.foe][node]), node))
    failed = None
    shorter = tuple(Plan(Activity.CLEAR, first.path[:k]) for k in range(len(first.path) - 1, 0, -1))
    for plan in (first, Plan(Activity.STAY), Plan(Activity.RECALL), *((Plan(Activity.RECALL, after),) if after else ()),
                 *(Plan(Activity.MOVE, to=node) for node in nearest), *shorter, Plan(Activity.RECALL, watched=True)):
        try:
            _trace(ctx, role, plan)
            return plan
        except Rejected as error:
            failed = failed or error
    return failed


def _hidden_walk(ctx: _Context, start: Pos, dest: Pos, walk: float) -> tuple[Pos, bool]:
    """Where a champion that walks up to `walk` units from `start` toward `dest` stands when it stops short of the
    team's view, and whether it stopped short."""
    at, done = start, 0.0
    while done < walk:
        step = min(walk, done + WALK_STEP)
        nxt = RIFT.advance(start, dest, step)
        if sees(ctx.base, ctx.team, nxt):
            return at, True
        at, done = nxt, step
    return at, False


def _first_hidden(ctx: _Context, start: Pos, dest: Pos, reach: float) -> Pos | None:
    """The first place, walking from `start` toward `dest`, that the team does not see, while it lies within `reach`
    of `start` by the straight line, or None."""
    done, route = 0.0, RIFT.distance(start, dest)
    while done < route:
        done = min(route, done + WALK_STEP)
        at = RIFT.advance(start, dest, done)
        if RIFT.separation(start, at) > reach:
            return None
        if not sees(ctx.base, ctx.team, at):
            return at
    return None


def _check_path(role: int, path: tuple[int, ...]) -> None:
    if role != JUNGLE:
        raise Rejected(Reason.INCONSISTENT, "only a jungler clears camps")
    if not path or len(set(path)) != len(path) or any(SITES[i].kind.scuttler for i in path):
        raise Rejected(Reason.INCONSISTENT, f"the path {path} is empty, repeats a camp, or names a Scuttler")


def _farm_estimate(world: World, role: int, until: int) -> float:
    rate, start = H["farm_gold_per_s"][ROLES[role]], H["farm_from_s"][ROLES[role]]
    return rate * max(0.0, until * world.config.tick_s - start)


def spent_on(role: int, upgrades: int) -> float:
    """The price of the first `upgrades` entries of a role's progression."""
    return sum(upgrade.cost for upgrade in PROGRESSIONS[ROLES[role]][:upgrades])


def _ledger(world: World, seat: int, kills: bool, until: int, income: dict[Income, float], upgrades: int) -> tuple[float, ...]:
    """An enemy's ledger at the decision tick (module docstring, Gold), raised to pay for `upgrades`."""
    config, tick, role = world.config, world.tick, seat % 5
    earned = [0.0] * len(Income)
    earned[Income.STARTING] = ECONOMY["starting_gold"]
    earned[Income.PASSIVE] = ECONOMY["passive_gold_per_10s"] / 10 * config.tick_s * max(0, tick - config.ticks(ECONOMY["passive_gold_start_s"]))
    if role == SUPPORT:
        earned[Income.SUPPORT_ITEM] = ITEM["passive_gold_per_10s"] / 10 * config.tick_s * tick
    farm = Income.CAMP if role == JUNGLE else Income.MINION
    earned[farm] = _farm_estimate(world, role, until)
    earned[Income.KILL] = ECONOMY["kill_gold_base"] if kills else 0.0
    for source, amount in income.items():
        earned[source] += amount
    earned[farm] += max(0.0, spent_on(role, upgrades) - sum(earned))
    return tuple(earned)


def _shop(world: World, seat: int, upgrades: int, until: int) -> int:
    """The upgrades that an enemy holds after it shops on its fountain, from `upgrades` on, with its estimated ledger
    and the farm estimate up to tick `until`."""
    kills = world.champions[seat].earned[Income.KILL] >= KILL_MARK
    return _bought(seat % 5, upgrades, sum(_ledger(world, seat, kills, until, {}, upgrades)) - spent_on(seat % 5, upgrades))


def _bought(role: int, upgrades: int, gold: float) -> int:
    """The upgrades that a champion holds after it buys, in order, what `gold` pays for."""
    progression = PROGRESSIONS[ROLES[role]]
    while upgrades < len(progression) and gold >= progression[upgrades].cost:
        gold -= progression[upgrades].cost
        upgrades += 1
    return upgrades


def _xp(sight: _Sighting, level: int, gain: float) -> float:
    """The XP now. It is the least XP in the band seen at the last sighting that, with `gain`, lies in the band now."""
    seen_low, seen_high = _band(sight.level)
    low, high = _band(level)
    then = max(seen_low, low - gain)
    if then >= seen_high or then + gain >= high:
        raise Rejected(Reason.XP_BAND, f"{gain:.0f} XP since level {sight.level} does not end inside level {level}")
    return then + gain


def _trace(ctx: _Context, role: int, plan: Plan) -> _Trace:
    """The state that the plan leaves the enemy of `role` in at the decision tick. Raises `Rejected` on a failed
    check."""
    sight, world = ctx.sightings[role], ctx.base
    least = sight.upgrades if sight.seen_upgrades is None else sight.seen_upgrades
    if sight.seen_upgrades is not None and plan.upgrades is not None:
        sight = sight._replace(upgrades=plan.upgrades, hp=capability(ROLES[role], sight.level, plan.upgrades).max_hp)
    seat, tick, dt = ctx.foe * 5 + role, ctx.tick, world.config.tick_s
    elapsed = (tick - sight.tick) * dt
    can = capability(ROLES[role], sight.level, sight.upgrades)
    pos, intent, intent_tick, channel, outcome, outcome_tick = sight.pos, HOLD, sight.tick, 0, Outcome.NONE, -1
    hp, gain, income, clears, recalled = sight.hp + can.hp_regen * elapsed, 0.0, {}, (), False
    if plan.activity is Activity.FARM:
        lane = HOME[role]
        if lane is None:
            raise Rejected(Reason.INCONSISTENT, "a jungler does not farm a lane")
        sim = world.lanes[lane]
        s, _ = stance(sim, ctx.foe, Mode.LAST_HIT, can.attack_range, sim.front())
        pos = post = RIFT.lane_pos(lane, s)
        fog = sees(world, ctx.team, post)
        if fog:
            pos = _first_hidden(ctx, post, RIFT.lane_pos(lane, 0.0 if ctx.foe == 0 else sim.length), XP_RANGE)
            if pos is None:
                raise Rejected(Reason.IN_VIEW, f"the team sees the {lane} front and the lane behind it within XP range")
        walk = RIFT.distance(sight.pos, pos) / can.move_speed
        if walk > elapsed:
            raise Rejected(Reason.UNREACHABLE, f"the {lane} front is {walk - elapsed:.1f} s further than the elapsed time allows")
        intent = FARM_ACTION[role]
        income = {} if fog else {Income.MINION: H["farm_gold_per_s"][ROLES[role]] * (elapsed - walk)}
        gain = H["farm_xp_per_s"][ROLES[role]] * (elapsed - walk)
    elif plan.activity is Activity.CLEAR:
        _check_path(role, plan.path)
        clears, end, hp, gold, gain = _clear(ctx, sight, plan.path)
        hp += can.hp_regen * (tick * dt - end)
        income = {Income.CAMP: gold}
        pos, outcome, outcome_tick = SITES[plan.path[-1]].pos, Outcome.CLEARED, clears[-1][1]
    elif plan.activity is Activity.RECALL:
        if plan.watched:
            record = world.memory[ctx.team].enemies[role]
            if sight.seen_upgrades is not None or record.seen_tick < 0 or record.was not in (None, record.pos):
                raise Rejected(Reason.INCONSISTENT, f"the team did not watch the enemy {ROLES[role]} stand at its last sighting")
        back = _home(ctx, role, plan.watched)
        if back is None and plan.path:
            raise Rejected(Reason.UNREACHABLE, "the recall ends after the decision tick, so no camp is cleared after it")
        if back is None:
            intent, channel = RECALL, tick - sight.tick
        else:
            recalled = True
            if plan.upgrades is not None:
                back = back._replace(upgrades=plan.upgrades, hp=capability(ROLES[role], sight.level, plan.upgrades).max_hp)
            pos, intent_tick, outcome, outcome_tick, hp = back.pos, back.tick, Outcome.RECALLED, back.tick - 1, math.inf
            if plan.path:
                _check_path(role, plan.path)
                clears, end, hp, gold, gain = _clear(ctx, back, plan.path)
                hp += capability(ROLES[role], sight.level, back.upgrades).hp_regen * (tick * dt - end)
                income = {Income.CAMP: gold}
                pos, outcome, outcome_tick = SITES[plan.path[-1]].pos, Outcome.CLEARED, clears[-1][1]
            else:
                speed = capability(ROLES[role], sight.level, back.upgrades).move_speed
                dest = NODE_POS[ctx.foe][H["recall_return"][ROLES[role]]]
                route, walk = RIFT.distance(pos, dest), (tick - intent_tick) * dt * speed
                pos, waits = _hidden_walk(ctx, pos, dest, min(route, walk))
                intent = HOLD if waits or route <= walk else _action(Kind.MOVE, H["recall_return"][ROLES[role]])
                if not waits and route <= walk:
                    outcome, outcome_tick = Outcome.ARRIVED, intent_tick + world.config.ticks(route / speed) - 1
    elif plan.activity is Activity.MOVE:
        if plan.to not in NODES:
            raise Rejected(Reason.INCONSISTENT, f"{plan.to} is no place to move to")
        dest = NODE_POS[ctx.foe][plan.to]
        route = RIFT.distance(sight.pos, dest)
        pos = RIFT.advance(sight.pos, dest, can.move_speed * elapsed)
        if route <= can.move_speed * elapsed:
            outcome, outcome_tick = Outcome.ARRIVED, sight.tick + world.config.ticks(route / can.move_speed) - 1
        else:
            intent = _action(Kind.MOVE, plan.to)
    upgrades = back.upgrades if recalled else sight.upgrades if plan.upgrades is None else plan.upgrades
    if upgrades < least:
        raise Rejected(Reason.INCONSISTENT, f"upgrades fall from {least} to {upgrades}")
    if upgrades != sight.upgrades and not recalled:
        raise Rejected(Reason.UPGRADES_WITHOUT_FOUNTAIN, f"upgrades go from {sight.upgrades} to {upgrades} without a recall")
    kills = world.champions[seat].earned[Income.KILL] >= KILL_MARK
    earned = _ledger(world, seat, kills, sight.tick, income, upgrades)
    level = ctx.levels[role]
    xp = _xp(sight, level, gain) if plan.xp is None else plan.xp
    low, high = _band(level)
    if not low <= xp < high:
        raise Rejected(Reason.XP_BAND, f"XP {xp:.0f} is outside level {level}, from {low:.0f} to {high:.0f}")
    full = capability(ROLES[role], level, upgrades).max_hp
    if sees(world, ctx.team, pos):
        raise Rejected(Reason.IN_VIEW, f"the enemy {ROLES[role]} would stand where the team sees")
    fountain = recalled or sight.seen_upgrades is not None
    return _Trace(pos, intent, intent_tick, channel, outcome, outcome_tick, min(full, hp), fountain, xp, upgrades, earned, clears)


def complete(info: InfoState, hypothesis: Hypothesis) -> Hypothesis:
    """The hypothesis with every plan that it leaves out filled in from the role's default activity, as a scenario
    loader fills an author's hypothesis (M7 section 9.3, contract 5). Raises `Rejected` for a plan given to an enemy
    that the team sees or that is dead."""
    return _complete(_context(info), hypothesis)


def _complete(ctx: _Context, hypothesis: Hypothesis) -> Hypothesis:
    if len(hypothesis.plans) != 5:
        raise Rejected(Reason.INCONSISTENT, f"{len(hypothesis.plans)} plans for five enemies")
    plans = []
    for role, (plan, sight, default) in enumerate(zip(hypothesis.plans, ctx.sightings, ctx.defaults)):
        if sight is None and plan is not None:
            raise Rejected(Reason.INCONSISTENT, f"the enemy {ROLES[role]} is in view or dead and needs no activity")
        if sight is not None and plan is None and isinstance(default, Rejected):
            raise default
        plans.append(plan if plan is not None or sight is None else default)
    return replace(hypothesis, plans=tuple(plans))


def _traces(ctx: _Context, hypothesis: Hypothesis) -> tuple[_Trace | None, ...]:
    traces = tuple(None if plan is None else _trace(ctx, role, plan) for role, plan in enumerate(hypothesis.plans))
    visited = {camp for trace in traces if trace for camp, _ in trace.clears}
    for camp in hypothesis.cleared:
        if camp not in visited:
            raise Rejected(Reason.CAMP_UNVISITED, f"{SITES[camp].node} is cleared and no path visits it")
    return traces


def check(info: InfoState, hypothesis: Hypothesis) -> None:
    """Raise `Rejected` with its reason if the hypothesis, completed, fails a check."""
    ctx = _context(info)
    _traces(ctx, _complete(ctx, hypothesis))


def realize(info: InfoState, hypothesis: Hypothesis, rollout: int = 0) -> World:
    """A full world, made of the information state and of every hidden field as the hypothesis tells its history."""
    ctx = _context(info)
    traces = _traces(ctx, _complete(ctx, hypothesis))
    world = World.restore(ctx.base.snapshot())
    lines = dict(ctx.lines)
    for trace in traces:
        for camp, killed in trace.clears if trace else ():
            lines[camp] = _Line(killed + world.config.ticks(SITES[camp].kind.respawn_s), ctx.camp_level, False)
    for role, trace in enumerate(traces):
        _champion(ctx, world, role, trace)
    _camps(ctx, world, lines)
    _river(ctx, world)
    world.memory[ctx.foe] = new_memory(world.config, ctx.foe)
    remember_team(world, ctx.foe, ctx.tick - 1)
    return world


def _champion(ctx: _Context, world: World, role: int, trace: _Trace | None) -> None:
    c = world.champions[ctx.foe * 5 + role]
    kills = c.earned[Income.KILL] >= KILL_MARK
    if trace is None:
        upgrades = c.upgrades
        if c.respawn_tick >= 0:
            upgrades = _shop(world, c.seat, _sighting(world, c, world.memory[ctx.team].enemies[role]).upgrades, ctx.tick)
        earned, mana_share = _ledger(world, c.seat, kills, ctx.tick, {}, upgrades), H["mana_share"]
    else:
        upgrades, earned, mana_share = trace.upgrades, trace.earned, 1.0 if trace.full_mana else H["mana_share"]
        c.pos, c.hp, c.xp = trace.pos, trace.hp, trace.xp
        c.intent, c.intent_tick, c.channel, c.outcome, c.outcome_tick = trace.intent, trace.intent_tick, trace.channel, trace.outcome, trace.outcome_tick
    c.upgrades, c.earned = upgrades, list(earned)
    c.gold = sum(c.earned) - spent_on(role, upgrades)
    c.mana = capability(ROLES[role], level_of(c.xp), upgrades).max_mana * mana_share


def _camps(ctx: _Context, world: World, lines: dict[int, _Line]) -> None:
    for i, line in lines.items():
        camp, kind = world.camps[i], SITES[i].kind
        if line is ctx.lines[i] and line.seen:
            if camp.hp <= 0:
                camp.spawn_tick = line.up
            continue
        alive = line.up <= ctx.tick
        camp.level, camp.max_hp = line.level, kind.health(line.level, first=line.first and alive)
        camp.hp, camp.spawn_tick, camp.engaged = camp.max_hp if alive else 0.0, -1 if alive else line.up, -1


def _river(ctx: _Context, world: World) -> None:
    """The Scuttlers that the team does not see now, and a respawn that it does not know (module docstring). The river
    holds one Scuttler alive or due, or the first pair, which is both due at the first spawn or both alive with the
    health of a first spawn. A team that sees both nodes empty without a known spawn has the next Scuttler due at the
    first node, the respawn delay after the latest death that the timer rule allows (`_unseen_death`)."""
    tick, config, known = ctx.tick, world.config, world.memory[ctx.team].camps
    kind = SITES[SCUTTLERS[0]].kind
    first = config.ticks(kind.first_spawn_s)
    unseen = [i for i in SCUTTLERS if known[i].seen_tick != tick]

    def put(i: int, up: int, level: int, pair: bool = False) -> None:
        camp, alive = world.camps[i], up <= tick
        camp.level, camp.max_hp = level, kind.health(level, first=pair)
        camp.hp, camp.spawn_tick, camp.engaged = camp.max_hp if alive else 0.0, -1 if alive else up, -1

    def empty(i: int) -> None:
        camp = world.camps[i]
        camp.hp, camp.spawn_tick, camp.engaged = 0.0, -1, -1

    seen = [world.camps[i] for i in SCUTTLERS if i not in unseen]
    whole = all(known[i].spawn_tick == first or (known[i].seen_tick >= 0 and known[i].hp > 0) for i in unseen)
    if unseen and (tick < first or (whole and all(camp.hp > 0 and camp.max_hp == kind.health(camp.level, first=True) for camp in seen))):
        for i in unseen:
            put(i, first, known[i].level if known[i].hp > 0 else 1, pair=True)
        return
    for i in unseen:
        empty(i)
    if any(camp.hp > 0 or camp.spawn_tick >= 0 for camp in seen):
        return
    held = [i for i in unseen if known[i].spawn_tick >= 0 or known[i].hp > 0]
    if held:
        i = max(held, key=lambda i: (known[i].seen_tick, i))
        up = known[i].spawn_tick if known[i].spawn_tick >= 0 else NEVER
        put(i, up, known[i].level if known[i].hp > 0 else ctx.camp_level)
    elif unseen:
        put(min(unseen, key=lambda i: (known[i].seen_tick, i)), NEVER, ctx.camp_level)
    else:
        put(SCUTTLERS[0], _unseen_death(config, tick) + config.ticks(kind.respawn_s), ctx.camp_level)


def _describe(plan: Plan) -> str:
    if plan.path:
        return ("clears " if plan.activity is Activity.CLEAR else "recalls, then clears ") + ", ".join(SITES[i].node for i in plan.path)
    if plan.activity is Activity.MOVE:
        return f"moves to {plan.to}"
    if plan.watched:
        return "recalls where the team saw it"
    return {Activity.STAY: "stays", Activity.FARM: "farms", Activity.RECALL: "recalls"}[plan.activity]


def _candidates(ctx: _Context, role: int) -> list[Plan | Dropped]:
    plans: list[Plan | Dropped] = [Plan(Activity.STAY)]
    if HOME[role] is not None:
        plans.append(Plan(Activity.FARM))
    else:
        path = _default_path(ctx, ctx.sightings[role])
        plans.append(Plan(Activity.CLEAR, path) if path else
                     Dropped(role, Plan(Activity.CLEAR), Reason.UNREACHABLE, "no camp of its side can be cleared in the elapsed time"))
    after = _cleared_after_recall(ctx, role)
    return plans + [Plan(Activity.RECALL), *((Plan(Activity.RECALL, after),) if after else ()), *(Plan(Activity.MOVE, to=to) for to in H["move_to"])]


def generate(info: InfoState, focus: tuple[int, ...] | None = None) -> Generated:
    """`activity_v0` with the plans it considered and left out, and why.

    `focus` names enemy roles whose activity varies, by default the enemy jungler. A focus enemy that the team sees
    or that is dead needs no activity and is left out of the focus. Raises `Rejected` when no hypothesis passes.
    """
    ctx = _context(info)
    focus = tuple(role for role in ((JUNGLE,) if focus is None else focus) if ctx.sightings[role] is not None)
    for role, default in enumerate(ctx.defaults):
        if role not in focus and isinstance(default, Rejected):
            raise default
    options, dropped = [], []
    for role in focus:
        passing = []
        for plan in _candidates(ctx, role):
            if isinstance(plan, Dropped):
                dropped.append(plan)
                continue
            try:
                _trace(ctx, role, plan)
                passing.append(plan)
            except Rejected as error:
                dropped.append(Dropped(role, plan, error.reason, str(error)))
        if not passing and isinstance(ctx.defaults[role], Plan):
            passing.append(ctx.defaults[role])
        options.append(passing)
    hypotheses = []
    for choice in product(*options):
        plans = list(ctx.defaults)
        for role, plan in zip(focus, choice):
            plans[role] = plan
        name = "; ".join(f"{ROLES[role]} {_describe(plan)}" for role, plan in zip(focus, choice)) or "default activities"
        weight = math.prod(H["weights"][plan.activity.name.lower()] for plan in choice)
        hypotheses.append(Hypothesis(name, weight, tuple(plans)))
    if not hypotheses:
        raise Rejected(Reason.INCONSISTENT, f"no activity of the focus enemies {[ROLES[role] for role in focus]} passes the checks")
    total = sum(h.weight for h in hypotheses)
    return Generated(tuple(replace(h, weight=h.weight / total) for h in hypotheses), tuple(dropped))


def activity_v0(info: InfoState, focus: tuple[int, ...] | None = None) -> tuple[Hypothesis, ...]:
    """The hypotheses of M7 section 9.3 for the information state, with their normalised weights (module docstring)."""
    return generate(info, focus).hypotheses
