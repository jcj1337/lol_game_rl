"""The world: every mutable fact of one game, the tick order, snapshots, the digest, and the invariant checker.

The state is the seed, the tick, ten champions in seat order, three lanes, the camps, the sight sources that are
not units, and each team's memory. Randomness is keyed by the seed, so there is no generator state. The config is
not state: two worlds with equal state have equal digests.
`events` holds the events of the last tick for whoever watches a game, each with the lane it came from, with
"jungle", or with "combat". It is derived, not state.
"""

import copy
import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass, fields, is_dataclass
from typing import NamedTuple

from riftgame import combat, economy, jungle
from riftgame.champions import (ACTIONS, ENABLED, FOE, FOUNTAIN, HOLD, KEEP, LANES, RIFT, RULE, SEATS, SIEGE_LANE,
                                Champion, Kind, Outcome, capability_of, damage, death_timer_s, duty, enter_combat, finish,
                                level_of, settle_fountain, spawn, speed_of, spent)
from riftgame.lanes import RULESET_ID, AttackCredit, LaneSim, TowerDestroyed
from riftgame.map import REFERENCE_MAP, Pos
from riftgame.vision import Memory, Sight, legal_mask, new_memory, observe, remember

MAP_ID = REFERENCE_MAP
# Gold and its ledger add the same amounts in different orders, so they agree only up to rounding.
GOLD_TOLERANCE = 1e-6


class InvariantError(RuntimeError):
    pass


class Attacks(NamedTuple):
    """Everything that step 4 collects: the champions' hits on champions, the hits of minions, camps, and towers
    on champions as (seat, raw damage), the champions' blows on camps as (camp, seat, health removed), and the
    attack credit that the lanes hand back, by seat."""

    strikes: list[combat.Hit]
    hits: list[tuple[int, float]]
    blows: list[tuple[int, int, float]]
    credit: dict[int, float]


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
    camps: tuple[jungle.Camp, ...]
    sights: tuple[Sight, ...]
    memory: tuple[Memory, ...]


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
    __slots__ = ("config", "seed", "tick", "champions", "lanes", "camps", "sights", "memory", "events")

    def __init__(self, config: Config = Config(), seed: int = 0):
        self.config, self.seed, self.tick = config, seed, 0
        self.champions = [spawn(seat, config.roam_cap_s) for seat in SEATS]
        self.lanes = {name: LaneSim(name, seed, config.tick_s) for name in LANES}
        self.camps = jungle.new_camps(config)
        self.sights: list[Sight] = []
        self.memory = [new_memory(config, team) for team in range(2)]
        self.events: list[tuple[str, object]] = []

    def snapshot(self) -> Snapshot:
        return Snapshot(RULESET_ID, MAP_ID, self.config, self.seed, self.tick, tuple(copy.deepcopy(self.champions)),
                        camps=tuple(copy.deepcopy(self.camps)), sights=tuple(self.sights),
                        memory=tuple(copy.deepcopy(self.memory)),
                        lanes=tuple(copy.deepcopy(self.lanes[name]) for name in LANES))

    @classmethod
    def restore(cls, snapshot: Snapshot) -> "World":
        if (snapshot.ruleset_id, snapshot.map_id) != (RULESET_ID, MAP_ID):
            raise ValueError(f"snapshot of ruleset {snapshot.ruleset_id} on map {snapshot.map_id} cannot be restored "
                             f"into ruleset {RULESET_ID} on map {MAP_ID}")
        world = cls.__new__(cls)
        world.config, world.seed, world.tick = snapshot.config, snapshot.seed, snapshot.tick
        world.champions = copy.deepcopy(list(snapshot.champions))
        world.lanes = dict(zip(LANES, copy.deepcopy(snapshot.lanes)))
        world.camps = copy.deepcopy(list(snapshot.camps))
        world.sights = list(snapshot.sights)
        world.memory = copy.deepcopy(list(snapshot.memory))
        world.events = []
        return world

    def digest(self) -> str:
        state = (RULESET_ID, MAP_ID, self.seed, self.tick, self.camps, self.sights, self.memory,
                 self.champions, [self.lanes[name].values() for name in LANES])
        return hashlib.sha256(repr(_plain(state)).encode()).hexdigest()

    def step(self, actions: Sequence[int] | None = None) -> None:
        """One tick, in the order of M7 section 5.2. Pinned replays depend on the order.

        `actions` is one action index per seat, on decision ticks only.
        """
        self._apply(actions)
        self._spawn()
        self._move()
        self._resolve(self._collect())
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
        """Camps and champion respawns. Lanes spawn their own waves."""
        self.events = [("jungle", e) for e in jungle.spawn(self)]
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
                    c.pos = RIFT.advance(c.pos, dest, speed_of(self, c) * tick_s)

    def _collect(self) -> Attacks:
        """Every attack of this tick, all from the state that the move step left. The champions' hits on champions
        come first, because the lanes need to know who is harassing whom."""
        strikes = combat.collect(self)
        calls = combat.harassed(self, strikes)
        lead = economy.level_lead(self)
        hits, blows = jungle.collect(self)
        credit = {}
        for name in LANES:
            events = self.lanes[name].step(self.tick, economy.lane_inputs(self, name, calls), lead)
            for e in events:
                if type(e) is AttackCredit:
                    credit[e.seat] = e.credit
                else:
                    self.events.append((name, e))
            hits += economy.minion_hits(events)
            hits += economy.tower_hits(events)
        return Attacks(strikes, hits, blows, credit)

    def _resolve(self, attacks: Attacks) -> None:
        """All damage lands at once. Then the deaths of the tick are settled together, and gold and XP are paid."""
        strikes, hits, blows, credit = attacks
        combat.spend(self, strikes, blows, credit)
        combat.land(self, strikes, hits)
        self.events += [("combat", hit) for hit in strikes]
        for death in jungle.resolve(self, blows):
            self.events.append(("jungle", death))
            economy.settle_camp(self, death)
            for c in jungle.fighters(self, death.camp):
                finish(c, Outcome.CLEARED, self.tick)
            if jungle.SITES[death.camp].kind.scuttler:
                self.light(death.killer // 5, jungle.SITES[death.camp].pos, jungle.SHRINE_RADIUS, jungle.SHRINE_S)
        now = self.tick * self.config.tick_s
        kills = combat.kills(self, strikes)
        for kill in kills:
            for fighter in self.champions[(1 - kill.victim // 5) * 5:(2 - kill.victim // 5) * 5]:
                if FOE[fighter.intent] == kill.victim % 5:
                    finish(fighter, Outcome.KILLED, self.tick)
        for kill in kills:
            c = self.champions[kill.victim]
            c.pos = FOUNTAIN[c.team]
            c.respawn_tick = self.tick + self.config.ticks(death_timer_s(level_of(c.xp), now))
            finish(c, Outcome.DIED, self.tick)
        for kill in kills:
            combat.reward(self, kill)
            self.events.append(("combat", kill))
        for name in LANES:
            economy.settle_lane(self, name, [e for lane, e in self.events if lane == name])
        economy.settle_towers(self)
        for name, e in self.events:
            if type(e) is TowerDestroyed and self.lanes[name].front_tower(e.team) is None:
                for sieger in self.champions[(1 - e.team) * 5:(2 - e.team) * 5]:
                    if SIEGE_LANE[sieger.intent] == name:
                        finish(sieger, Outcome.CLEARED, self.tick)

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
            settle_fountain(self, c)
            state = duty(self, c)
            if state is not None:
                # No floor. A laner that overstays until its next decision goes into debt and repays it on its lane.
                c.allowance = min(config.roam_cap_s, c.allowance + rates[state])

    def _see(self) -> None:
        """Team memory, of the camps and the enemy champions. C6 adds the enemy waves."""
        remember(self)

    def light(self, team: int, pos: Pos, radius: float, seconds: float) -> None:
        """Give a team a sight source that stays at `pos` for `seconds`: a Speed Shrine, and a ward with C6."""
        self.sights.append(Sight(team, pos, radius, self.tick + self.config.ticks(seconds)))

    def damage_champion(self, seat: int, raw: float) -> None:
        """The one place a champion loses health. Damage ends a recall and Homeguard. Death is resolved in the tick's
        damage step."""
        c = self.champions[seat]
        if c.hp <= 0 or raw <= 0:
            return
        c.hp = max(0.0, c.hp - damage(raw, capability_of(c)))
        enter_combat(self, c)
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
        if abs(sum(c.earned) - spent(c) - c.gold) > GOLD_TOLERANCE:
            raise InvariantError(f"seat {c.seat} has {c.gold} gold, earned {sum(c.earned)}, and spent {spent(c)}")
        if not (0 <= c.pos.edge < len(RIFT.edges) and 0.0 <= c.pos.offset <= RIFT.edges[c.pos.edge].length):
            raise InvariantError(f"seat {c.seat} is off the map at {c.pos}")
        if c.hp <= 0 and c.intent != HOLD:
            raise InvariantError(f"seat {c.seat} is dead and holds {ACTIONS[c.intent]}")
        if not 0.0 <= c.attack_credit <= 1.0:
            raise InvariantError(f"seat {c.seat} has an attack credit of {c.attack_credit}")
    for fault in jungle.faults(world):
        raise InvariantError(fault)
    # An observation covers a whole team, so it is taken only once every champion's own state has passed.
    for c in world.champions:
        if not any(legal_mask(observe(world, c.seat))):
            raise InvariantError(f"seat {c.seat} has no legal action")
