"""The world: every mutable fact of one game, the tick order, snapshots, the digest, and the invariant checker.

The state is the seed, the tick, ten champions in seat order, and three lanes. Randomness is keyed by the seed,
so there is no generator state. The config is not state: two worlds with equal state have equal digests.
`events` holds the lane events of the last tick for whoever watches a game. It is derived, not state.
"""

import copy
import hashlib
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, fields, is_dataclass

from riftgame import economy
from riftgame.champions import (ACTIONS, ENABLED, FOUNTAIN, HOLD, KEEP, LANES, RIFT, RULE, SEATS, Champion, Kind,
                                Outcome, capability_of, damage, death_timer_s, duty, finish, level_of, spawn)
from riftgame.lanes import RULESET_ID, LaneSim
from riftgame.map import REFERENCE_MAP
from riftgame.vision import legal_mask, observe

MAP_ID = REFERENCE_MAP


class InvariantError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Config:
    """Clock and role settings of one game. All are starting values (M7 sections 5.2 and 5.10).

    The roam allowance is an experimental restriction. `roam_restricted` switches it off. Lanes stay fixed
    either way, until `assignments_end_s` or, with `outer_tower_ends_assignment`, until an outer tower of the
    lane falls.
    """

    tick_s: float = 0.5
    decision_ticks: int = 4
    roam_restricted: bool = True
    roam_cap_s: float = 90.0
    roam_refill: float = 0.25
    assignments_end_s: float = 840.0
    outer_tower_ends_assignment: bool = True

    def __post_init__(self):
        if self.tick_s <= 0 or self.decision_ticks < 1:
            raise ValueError("tick_s must be positive and decision_ticks at least 1")

    def ticks(self, seconds: float) -> int:
        """A duration in whole ticks, rounded up."""
        return math.ceil(seconds / self.tick_s - 1e-9)


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Everything needed to restore a world and replay from it. The lanes are in the order of `LANES`."""

    ruleset_id: str
    map_id: str
    config: Config
    seed: int
    tick: int
    champions: tuple[Champion, ...]
    lanes: tuple[LaneSim, ...]


def _plain(value):
    """State as nested tuples of plain values. Anything that could hash by identity or by dict order is refused."""
    if value is None or isinstance(value, (bool, float, str)):
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, (list, tuple)):
        return tuple(_plain(v) for v in value)
    if is_dataclass(value):
        return tuple(_plain(getattr(value, f.name)) for f in fields(value))
    raise TypeError(f"{type(value).__name__} is not a plain value")


class World:
    __slots__ = ("config", "seed", "tick", "champions", "lanes", "events")

    def __init__(self, config: Config = Config(), seed: int = 0):
        self.config, self.seed, self.tick = config, seed, 0
        self.champions = [spawn(seat, config.roam_cap_s) for seat in SEATS]
        self.lanes = {name: LaneSim(name, seed, config.tick_s) for name in LANES}
        self.events: list[tuple[str, object]] = []

    def snapshot(self) -> Snapshot:
        return Snapshot(RULESET_ID, MAP_ID, self.config, self.seed, self.tick, tuple(copy.deepcopy(self.champions)),
                        tuple(copy.deepcopy(self.lanes[name]) for name in LANES))

    @classmethod
    def restore(cls, snapshot: Snapshot) -> "World":
        if (snapshot.ruleset_id, snapshot.map_id) != (RULESET_ID, MAP_ID):
            raise ValueError(f"snapshot of ruleset {snapshot.ruleset_id} on map {snapshot.map_id} cannot be restored "
                             f"into ruleset {RULESET_ID} on map {MAP_ID}")
        world = cls.__new__(cls)
        world.config, world.seed, world.tick = snapshot.config, snapshot.seed, snapshot.tick
        world.champions = copy.deepcopy(list(snapshot.champions))
        world.lanes = dict(zip(LANES, copy.deepcopy(snapshot.lanes)))
        world.events = []
        return world

    def digest(self) -> str:
        state = (RULESET_ID, MAP_ID, self.seed, self.tick, self.champions, [self.lanes[name].values() for name in LANES])
        return hashlib.sha256(repr(_plain(state)).encode()).hexdigest()

    def step(self, actions: Sequence[int] | None = None) -> None:
        """One tick, in the order of M7 section 5.2. Pinned replays depend on the order.

        `actions` is one action index per seat, on decision ticks only.
        """
        self._apply(actions)
        self._spawn()
        self._move()
        hits = self._collect()
        self._resolve(hits)
        self._settle()
        self._see()
        self.tick += 1

    def _apply(self, actions: Sequence[int] | None) -> None:
        if actions is None:
            return
        if self.tick % self.config.decision_ticks:
            raise ValueError(f"tick {self.tick} is not a decision tick")
        for c, action in zip(self.champions, actions, strict=True):
            if action == KEEP:
                continue
            if c.hp <= 0:
                raise InvariantError(f"seat {c.seat} is dead and was given {ACTIONS[action]}")
            if not ENABLED[action]:
                raise ValueError(f"{ACTIONS[action].kind.name} is not enabled yet: {RULE[action].enabled_by}")
            if action != c.intent:
                c.intent, c.intent_tick, c.channel = action, self.tick, 0

    def _spawn(self) -> None:
        """Champion respawns. Lanes spawn their own waves, and camps arrive with C4."""
        for c in self.champions:
            if 0 <= c.respawn_tick <= self.tick:
                can = capability_of(c)
                c.hp, c.mana, c.respawn_tick = can.max_hp, can.max_mana, -1

    def _move(self) -> None:
        stood = [c.pos for c in self.champions]
        tick_s = self.config.tick_s
        for pursuers in (False, True):
            for c in self.champions:
                rule = RULE[c.intent]
                if rule.walk is None or rule.pursues is not pursuers or c.hp <= 0:
                    continue
                dest = rule.walk(self, c, stood)
                if dest is not None:
                    c.pos = RIFT.advance(c.pos, dest, capability_of(c).move_speed * tick_s)

    def _collect(self) -> list[tuple[int, float]]:
        """This tick's hits on champions, as (seat, raw damage). Minions are the only attackers until C5."""
        lead = economy.level_lead(self)
        self.events = []
        hits = []
        for name in LANES:
            events = self.lanes[name].step(self.tick, economy.lane_inputs(self, name), lead)
            self.events += [(name, e) for e in events]
            hits += economy.minion_hits(events)
        return hits

    def _resolve(self, hits: Iterable[tuple[int, float]]) -> None:
        for seat, raw in hits:
            self.damage_champion(seat, raw)
        now = self.tick * self.config.tick_s
        for c in self.champions:
            if c.hp <= 0 and c.respawn_tick < 0:
                c.pos = FOUNTAIN[c.team]
                c.respawn_tick = self.tick + self.config.ticks(death_timer_s(level_of(c.xp), now))
                finish(c, Outcome.DIED, self.tick)
        for name in LANES:
            economy.settle_lane(self, name, [e for lane, e in self.events if lane == name])

    def _settle(self) -> None:
        config = self.config
        rates = (config.roam_refill * config.tick_s, 0.0, -config.tick_s)
        economy.accrue(self)
        for c in self.champions:
            if c.hp > 0:
                can = capability_of(c)
                c.hp = min(can.max_hp, c.hp + can.hp_regen * config.tick_s)
            settle = RULE[c.intent].settle
            if settle is not None and c.hp > 0:
                outcome = settle(self, c)
                if outcome:
                    finish(c, outcome, self.tick)
            state = duty(self, c)
            if state is not None:
                # No floor. A laner that overstays until its next decision goes into debt and repays it on its lane.
                c.allowance = min(config.roam_cap_s, c.allowance + rates[state])

    def _see(self) -> None:
        """Team view and memory. Empty until C6."""

    def damage_champion(self, seat: int, raw: float) -> None:
        """The one place a champion loses health. Damage ends a recall. Death is resolved in the tick's damage step."""
        c = self.champions[seat]
        if c.hp <= 0 or raw <= 0:
            return
        c.hp = max(0.0, c.hp - damage(raw, capability_of(c)))
        if ACTIONS[c.intent].kind is Kind.RECALL:
            finish(c, Outcome.INTERRUPTED, self.tick)


def check_invariants(world: World, previous_tick: int | None = None) -> None:
    """Raise `InvariantError` if the world is in a state that no sequence of legal actions may reach."""
    if previous_tick is not None and world.tick != previous_tick + 1:
        raise InvariantError(f"the clock went from tick {previous_tick} to tick {world.tick}")
    for c in world.champions:
        can = capability_of(c)
        if not 0.0 <= c.hp <= can.max_hp:
            raise InvariantError(f"seat {c.seat} has {c.hp} health of {can.max_hp}")
        if not 0.0 <= c.mana <= can.max_mana:
            raise InvariantError(f"seat {c.seat} has {c.mana} mana of {can.max_mana}")
        if c.gold < 0:
            raise InvariantError(f"seat {c.seat} has {c.gold} gold")
        if not (0 <= c.pos.edge < len(RIFT.edges) and 0.0 <= c.pos.offset <= RIFT.edges[c.pos.edge].length):
            raise InvariantError(f"seat {c.seat} is off the map at {c.pos}")
        if c.hp <= 0 and c.intent != HOLD:
            raise InvariantError(f"seat {c.seat} is dead and holds {ACTIONS[c.intent]}")
    # An observation covers a whole team, so it is taken only once every champion's own state has passed.
    for c in world.champions:
        if not any(legal_mask(observe(world, c.seat))):
            raise InvariantError(f"seat {c.seat} has no legal action")
