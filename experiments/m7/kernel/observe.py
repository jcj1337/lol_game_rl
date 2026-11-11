"""What one champion may know, as an object, a fixed-length vector, and an action mask.

`observe` is the only function here that touches the World. It reads the champion's own team, that team's View and
TeamMemory, the clock, and which towers stand. `encode` and `legal_mask` take the Observation alone.
"""

from enum import IntEnum
from functools import cache
from typing import NamedTuple

import numpy as np

from riftgame.map import Pos

from experiments.m7.kernel.profiles import ROAM_CAP_S, ROLE_LANE, ROLES, stats
from experiments.m7.kernel.world import (CAMPS, HOLD, KEEP, LANES, RECALL, RECALL_S, RIFT, Duty, Intent, Kind, Outcome, World,
                                         duty, on_lane)

MODES = ("last_hit", "thin", "push")
NODES = tuple(RIFT.at(name) for name in RIFT.node_names)
SPAN = 15000.0
HELD = tuple(k for k in Kind if k != Kind.KEEP)
FIGHT_AT = 3 + len(NODES) + len(LANES) * len(MODES) + len(CAMPS)
N_ACTIONS = FIGHT_AT + 5 + len(NODES)
OBS_SIZE = 6 + len(Outcome) + 1 + 1 + len(Duty) + 5 * 18 + 5 * 8 + len(CAMPS) * 6 + len(LANES) * 3 + 18 + 4


class ChampView(NamedTuple):
    id: int
    pos: Pos
    x: float
    y: float
    hp: float
    max_hp: float
    speed: float
    level: int
    xp: float
    gold: float
    upgrades: int
    intent: Intent
    channel: float
    slowed: bool
    wards: int
    dead_s: float
    kills: int
    deaths: int
    outcome: Outcome
    outcome_age_s: float
    roam: float
    duty: Duty


class EnemyView(NamedTuple):
    id: int
    visible: bool
    pos: Pos
    x: float
    y: float
    age_s: float
    hp: float
    max_hp: float
    level: int
    upgrades: int


class Observation:
    """`camps` rows are (name, visible, last observed alive, seconds since observed or -1, known respawn time or None)."""

    __slots__ = ("time", "me", "mates", "enemies", "camps", "fronts", "towers", "wards", "enemy_wards")


def observe(world: World, cid: int) -> Observation:
    me = world.champs[cid]
    team, tick, dt = me.team, world.tick, world.dt
    view, memory = world.views[team], world.memory[team]

    def own(c) -> ChampView:
        return ChampView(c.id, c.pos, *RIFT.xy(c.pos), c.hp, c.max_hp, c.speed, c.level, c.xp, c.gold, c.upgrades, c.intent,
                         c.channel, tick < c.slow_until, c.wards, max(0, c.respawn_tick - tick) * dt, c.kills, c.deaths,
                         c.outcome, (tick - c.outcome_tick) * dt, c.roam, duty(c))

    def enemy(i: int) -> EnemyView | None:
        seen = memory.enemies.get(i)
        if seen is None:
            return None
        return EnemyView(i, i in view.enemies, seen.pos, *RIFT.xy(seen.pos), (tick - seen.tick) * dt, seen.hp,
                         stats(ROLES[i % 5], seen.level, seen.upgrades)[0], seen.level, seen.upgrades)

    o = Observation()
    o.time = tick * dt
    o.me = own(me)
    o.mates = tuple(own(c) for c in world.champs[team * 5:team * 5 + 5] if c is not me)
    o.enemies = tuple(enemy(i) for i in range(5 - team * 5, 10 - team * 5))
    o.camps = tuple((name, name in view.camps, m.alive, (tick - m.seen_tick) * dt if m.seen_tick >= 0 else -1.0, m.respawn_s)
                    for name, m in memory.camps.items())
    o.fronts, o.enemy_wards = view.fronts, view.wards
    o.towers = tuple(t.hp > 0 for t in world.towers)
    o.wards = tuple(s.pos for s in world.sources if s.ward and s.team == team)
    return o


def encode(o: Observation) -> np.ndarray:
    team = (o.me, *o.mates)
    f: list[float] = [o.time / 900.0, *(i == o.me.id % 5 for i in range(5)),
                      *(o.me.outcome == k for k in Outcome), min(1.0, o.me.outcome_age_s / 60),
                      o.me.roam / ROAM_CAP_S, *(o.me.duty == k for k in Duty)]
    for c in team:
        f += (c.x / SPAN, c.y / SPAN, c.hp / c.max_hp, c.level / 18, c.xp / 1000, c.gold / 3000, c.upgrades / 4,
              c.channel / RECALL_S, c.slowed, c.wards / 2, c.dead_s / 60, *(c.intent.kind == k for k in HELD))
    for e in o.enemies:
        f += (0.0,) * 8 if e is None else (1.0, e.visible, e.x / SPAN, e.y / SPAN, min(1.0, e.age_s / 300),
                                           e.hp / e.max_hp, e.level / 18, e.upgrades / 4)
    for _, visible, alive, age_s, respawn_s in o.camps:
        f += (visible, alive, age_s >= 0, min(1.0, age_s / 300) if age_s >= 0 else 1.0, respawn_s is not None,
              0.0 if respawn_s is None else max(-1.0, min(1.0, (respawn_s - o.time) / 300)))
    for lane in LANES:
        own_s, foe_s = o.fronts[lane]
        length = RIFT.lanes[lane].length
        f += (own_s / length, foe_s >= 0, max(foe_s, 0.0) / length)
    f += o.towers
    f += (len(o.wards) / 3, len(o.enemy_wards) / 3, sum(c.kills for c in team) / 20, sum(c.deaths for c in team) / 20)
    return np.array(f, dtype=np.float32)


@cache
def actions(team: int) -> tuple[Intent, ...]:
    return (KEEP, HOLD, RECALL, *(Intent(Kind.MOVE, p) for p in NODES),
            *(Intent(Kind.FARM, (lane, mode)) for lane in LANES for mode in MODES),
            *(Intent(Kind.CAMP, name) for name in CAMPS),
            *(Intent(Kind.FIGHT, i) for i in range(5 - team * 5, 10 - team * 5)),
            *(Intent(Kind.WARD, p) for p in NODES))


class Leash(IntEnum):
    """What the laning role lets a champion do, from its duty state and its roam allowance."""

    NONE = 0        # a jungler, or a laner with allowance left: anything except farming another lane
    HOME_LANE = 1   # no allowance, on the home lane: only actions whose target lies on that lane
    RETURN = 2      # no allowance, off the home lane: farm the home lane or recall


def leash(me: ChampView) -> Leash:
    if me.duty == Duty.FREE or me.roam > 0:
        return Leash.NONE
    return Leash.HOME_LANE if me.duty == Duty.IN_LANE else Leash.RETURN


def permits(state: Leash, home: str | None, a: Intent, enemies: tuple = ()) -> bool:
    """Whether a champion with home lane `home` may hold intent `a` under this leash."""
    if home is None:
        return True
    if a.kind == Kind.FARM:
        return a.target[0] == home
    if state == Leash.NONE:
        return True
    if state == Leash.RETURN:
        return a.kind == Kind.RECALL
    if a.kind == Kind.FIGHT:
        foe = enemies[a.target % 5]
        return foe is not None and on_lane(home, foe.pos)
    return a.kind in (Kind.HOLD, Kind.RECALL) or (a.kind in (Kind.MOVE, Kind.WARD) and on_lane(home, a.target))


@cache
def _unleashed(team: int, home: str | None) -> np.ndarray:
    return np.array([permits(Leash.NONE, home, a) for a in actions(team)])


def legal_mask(o: Observation) -> np.ndarray:
    """Aligned with `actions(team)`. FIGHT needs a target that is visible now, WARD needs a charge, and the role must permit it.

    KEEP is legal when the role permits the intent that it keeps.
    """
    me = o.me
    team, home, state = me.id // 5, ROLE_LANE.get(ROLES[me.id % 5]), leash(me)
    mask = np.ones(N_ACTIONS, dtype=bool)
    mask[FIGHT_AT:FIGHT_AT + 5] = [e is not None and e.visible for e in o.enemies]
    mask[FIGHT_AT + 5:] = me.wards > 0
    mask &= _unleashed(team, home) if state == Leash.NONE else [permits(state, home, a, o.enemies) for a in actions(team)]
    mask[0] = permits(state, home, me.intent, o.enemies)
    return mask


def run(world: World, policy, ticks: int) -> int:
    """Advance `ticks` ticks, asking `policy(observation) -> Intent` for every champion on decision ticks."""
    decisions = 0
    for _ in range(ticks):
        if world.tick % world.decision_interval == 0:
            intents = [policy(observe(world, c.id)) for c in world.champs]
            for c, intent in zip(world.champs, intents):
                world.submit(c.id, intent)
            decisions += len(intents)
        world.step()
    return decisions
