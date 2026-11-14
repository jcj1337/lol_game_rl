"""The information state, which holds what one team knows at the start of a tick as a world (M7 section 9.3,
contract 1).

`redact(world, team)` keeps the team's own champions, minions, towers, wards, shrines, and memory, what its sight
sources see now, and the public facts. Every other field gets a canonical blank that depends on nothing hidden. The
result reads the same as the source through `observe_team` for the team's five seats. It is not a valid game world.
An enemy that the team does not see stands on its fountain with nothing in its ledger, and an unseen camp is empty.
`riftgame.hypotheses` fills the blanks.

`FIELDS` classifies every field of the state once, as the field stands in a unit of the team's enemy or in a camp.
The team's own units and its own memory are known in full, apart from the scratch fields that every tick sets again
before it reads them. `redact` reads the table, so the table is what the redaction does.

Assumed. An enemy minion or enemy tower that the team sees now is kept in full, attack state included, because a
player sees the attack. A reference that a kept unit holds to an enemy minion that is left out goes, and so does a
cast in progress on it. A champion target that a minion or a missile kept from an earlier tick is blanked to its
seat, the only part of it that a later tick reads. A missile in flight is kept, because an enemy minion shoots only
at the team's units and the team's own missiles are its own. Lane counters that only the digest reads are zero.
"""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple

from riftgame.champions import (FOUNTAIN, HOLD, LANES, LEVEL_XP, NO_HOMEGUARD, RIFT, ROLES, WARD, Champion, Income, Outcome,
                                capability, level_of)
from riftgame.jungle import Camp
from riftgame.lanes import TIERS, ChampionInput, ChampionTarget, LaneSim, Minion, Mode, Tower, WaveClock
from riftgame.vision import CampMemory, EnemyMemory, Memory, Sight, TowerMemory, WaveMemory, _wave_seen, new_memory, sees
from riftgame.world import Config, Snapshot, World

# An enemy's ledger keeps one public fact, whether the enemy has been paid for a kill, because the first kill of the
# game pays first blood and kills are public (M7 section 6.3). The blank holds it as this amount in the kill entry.
KILL_MARK = 1.0


class Known(Enum):
    """What a team knows of one field of an enemy unit or a camp, and so what `redact` does with it.

    PUBLIC fields are kept. SEEN fields are kept while the team sees the unit now and blank otherwise, and an enemy
    minion or ward that the team does not see goes as a whole. HIDDEN fields are blank also in a unit in view, and
    the blank may keep the part that the team knows, as the floor of the level's XP band keeps the public level.
    SCRATCH fields are set again by every tick before it reads them, so they are blank in every unit, the team's own
    too. UNITS fields hold units, which their own tables redact.
    """

    PUBLIC = "public"
    SEEN = "seen"
    HIDDEN = "hidden"
    SCRATCH = "scratch"
    UNITS = "units"


class Scope(NamedTuple):
    """What a blank may read besides its unit. That is the config and the clock, the team, the seats that the team
    sees now with its own among them, and the team's own record of the unit."""

    config: Config
    tick: int
    team: int
    seats: frozenset[int]
    record: object = None


class Field(NamedTuple):
    known: Known
    blank: Callable[[object, Scope], object] | None = None


PUBLIC, SEEN, HIDDEN, SCRATCH, UNITS = Known.PUBLIC, Known.SEEN, Known.HIDDEN, Known.SCRATCH, Known.UNITS


def band_floor(level: int) -> float:
    """The least XP of a level."""
    return LEVEL_XP[level - 2] if level > 1 else 0.0


def _const(value) -> Callable[[object, Scope], object]:
    return lambda unit, scope: value


def _full_health(c: Champion, scope: Scope) -> float:
    return 0.0 if c.respawn_tick >= 0 else capability(ROLES[c.seat % 5], level_of(c.xp), 0).max_hp


def _ledger(c: Champion, scope: Scope) -> list[float]:
    earned = [0.0] * len(Income)
    earned[Income.KILL] = KILL_MARK if c.earned[Income.KILL] > 0 else 0.0
    return earned


def _engaged(camp: Camp, scope: Scope) -> int:
    return camp.engaged if scope.record.seen_tick == scope.tick and camp.engaged in scope.seats else -1


def _target_blank(t: ChampionTarget, scope: Scope) -> ChampionInput:
    return ChampionInput(t.inp.seat, t.inp.team, 0.0, Mode.PASSIVE)


CHAMPION = {
    "seat": Field(PUBLIC),
    "pos": Field(SEEN, lambda c, scope: FOUNTAIN[c.seat // 5]),
    "hp": Field(SEEN, _full_health),
    "mana": Field(HIDDEN, _const(0.0)),
    "xp": Field(HIDDEN, lambda c, scope: band_floor(level_of(c.xp))),
    "gold": Field(HIDDEN, _const(0.0)),
    "earned": Field(HIDDEN, _ledger),
    "upgrades": Field(SEEN, _const(0)),
    "intent": Field(HIDDEN, _const(HOLD)),
    "intent_tick": Field(HIDDEN, _const(0)),
    "channel": Field(HIDDEN, _const(0)),
    "outcome": Field(HIDDEN, _const(Outcome.NONE)),
    "outcome_tick": Field(HIDDEN, _const(-1)),
    "allowance": Field(HIDDEN, lambda c, scope: scope.config.roam_cap_s),
    "attack_credit": Field(HIDDEN, _const(1.0)),
    "item_charges": Field(HIDDEN, _const(0)),
    "respawn_tick": Field(PUBLIC),
    "respawned_tick": Field(PUBLIC),
    "respawned_level": Field(PUBLIC),
    "homeguard_tick": Field(HIDDEN, _const(NO_HOMEGUARD)),
    "homeguard_block": Field(HIDDEN, _const(0)),
    # It holds the ticks on which the team's own champions damaged this one.
    "hurt_tick": Field(PUBLIC),
    "slow": Field(HIDDEN, _const(0.0)),
    "slow_until": Field(HIDDEN, _const(0)),
    "lockdown_tick": Field(HIDDEN, _const(0)),
    "ward_charges": Field(HIDDEN, _const(WARD["ward_charges"])),
    "ward_tick": Field(HIDDEN, _const(-1)),
}
CAMP = {
    "hp": Field(SEEN, _const(0.0)),
    "max_hp": Field(SEEN, _const(0.0)),
    "level": Field(SEEN, _const(0)),
    # The team knows a spawn only by the timer rule of M7 section 3.3, which its memory follows.
    "spawn_tick": Field(HIDDEN, lambda camp, scope: scope.record.spawn_tick),
    "engaged": Field(HIDDEN, _engaged),
}
# An enemy tower shoots only the team's units, which see it, and only the team's units damage it.
TOWER = {
    "team": Field(PUBLIC), "tier": Field(PUBLIC), "s": Field(PUBLIC), "x": Field(PUBLIC), "y": Field(PUBLIC),
    "lo": Field(PUBLIC), "hi": Field(PUBLIC), "free_at": Field(PUBLIC),
    "hp": Field(SEEN, lambda tower, scope: scope.record.hp),
    "credit": Field(SEEN, _const(1.0)),
    "heat": Field(PUBLIC), "heat_at": Field(PUBLIC),
}
_MINION_SCRATCH = {"near": None, "near_gap": float("inf"), "near_walk": float("inf"), "anchored": False, "free_at": 0.0,
                   "died_group": -1, "x": 0.0, "y": 0.0}
MINION = {name: Field(SCRATCH, _const(_MINION_SCRATCH[name])) if name in _MINION_SCRATCH else Field(SEEN)
          for name in Minion.__dataclass_fields__}
CHAMPION_TARGET = {
    "inp": Field(HIDDEN, _target_blank),
    "s": Field(HIDDEN, _const(0.0)), "x": Field(HIDDEN, _const(0.0)), "y": Field(HIDDEN, _const(0.0)),
    "hp": Field(PUBLIC), "free_at": Field(PUBLIC),
}
# A champion input lives in the state only inside a champion target, whose blank keeps the seat and the team.
CHAMPION_INPUT = {name: Field(PUBLIC) if name in ("seat", "team") else Field(HIDDEN) for name in ChampionInput.__dataclass_fields__}
# These are blank as wholes. An enemy ward or shrine goes, and the enemy's memory is the one every team starts with.
SIGHT = {name: Field(HIDDEN) for name in Sight.__dataclass_fields__}
MEMORY = {name: Field(HIDDEN) for name in Memory.__dataclass_fields__}
RECORDS = {kind: {name: Field(HIDDEN) for name in kind.__dataclass_fields__} for kind in (CampMemory, EnemyMemory, WaveMemory, TowerMemory)}
CLOCK = {name: Field(PUBLIC) for name in ("wave", "next_wave", "queue")}
LANE = {
    **{name: Field(PUBLIC) for name in ("name", "tick_s", "rules", "geometry", "length", "lane_id", "tick", "_straight", "clock",
                                        "spawned", "level_lead", "_serial")},
    "seed": Field(HIDDEN, _const(0)),
    "minions": Field(UNITS), "towers": Field(UNITS), "_missiles": Field(UNITS),
    **{name: Field(HIDDEN, _const(0)) for name in ("dead", "removed", "cancelled", "lost")},
    "_champion_credit": Field(HIDDEN, lambda sim, scope: {seat: credit for seat, credit in sim._champion_credit.items() if seat // 5 == scope.team}),
    "_order": Field(HIDDEN, lambda sim, scope: len(sim._missiles)),
    "_stand": Field(SCRATCH, lambda sim, scope: {}),
    **{name: Field(SCRATCH, lambda sim, scope: ([], [])) for name in ("_prey", "_callers", "_marks")},
    "_group": Field(SCRATCH, _const(0)),
    "_events": Field(SCRATCH, lambda sim, scope: []),
    "_t0": Field(SCRATCH, _const(0.0)),
    "_sighted": Field(SCRATCH, lambda sim, scope: [None, None]),
    "_fronts": Field(SCRATCH, lambda sim, scope: {}),
}
# The seed keys every draw of the source game, among them which river node the next Scuttler takes, so it is blank.
# A comparison sets the seed of each rollout itself.
SNAPSHOT = {**{name: Field(PUBLIC) for name in ("ruleset_id", "map_id", "config", "tick")}, "seed": Field(HIDDEN, _const(0)),
            **{name: Field(UNITS) for name in ("champions", "lanes", "camps", "sights", "memory")}}

FIELDS: dict[type, dict[str, Field]] = {
    Snapshot: SNAPSHOT, Champion: CHAMPION, LaneSim: LANE, WaveClock: CLOCK, Minion: MINION, Tower: TOWER, Camp: CAMP,
    ChampionTarget: CHAMPION_TARGET, ChampionInput: CHAMPION_INPUT, Sight: SIGHT, Memory: MEMORY, **RECORDS,
}


def _redact(unit, table: dict[str, Field], keep: bool, scope: Scope) -> None:
    for name, field in table.items():
        if field.known in (HIDDEN, SCRATCH) or (field.known is SEEN and not keep):
            setattr(unit, name, field.blank(unit, scope))


@dataclass(frozen=True, slots=True)
class InfoState:
    """What `team` knows at the start of tick `snapshot.tick`, before actions.

    `snapshot` is a world in which every field hidden from the team holds a canonical blank. `seen` says, by enemy
    role, whether the team sees that champion now, so that its memory record is current. An information state is
    never changed in place. To change what the team knows, change a world and redact it again.
    """

    team: int
    snapshot: Snapshot
    seen: tuple[bool, ...]

    def world(self) -> World:
        """A fresh world restored from the snapshot. It is not a valid game world."""
        return World.restore(self.snapshot)

    def digest(self) -> str:
        return hashlib.sha256(f"{self.team} {self.seen} {self.world().digest()}".encode()).hexdigest()


def redact(world: World, team: int) -> InfoState:
    """The information state of `team` in `world`. The source is copied and never changed.

    Redacting an information state's own world gives the same information state.
    """
    info = World.restore(world.snapshot())
    tick, foe, memory = info.tick, 1 - team, info.memory[team]
    seen = tuple(record.seen_tick == tick for record in memory.enemies)
    seats = frozenset((*range(team * 5, team * 5 + 5), *(foe * 5 + role for role, now in enumerate(seen) if now)))
    scope = Scope(info.config, tick, team, seats)
    for c, now in zip(info.champions[foe * 5:foe * 5 + 5], seen):
        _redact(c, CHAMPION, now, scope)
    for camp, record in zip(info.camps, memory.camps):
        _redact(camp, CAMP, record.seen_tick == tick, scope._replace(record=record))
    for lane, name in enumerate(LANES):
        sim = info.lanes[name]
        kept = {id(m) for m in _wave_seen(info, team, name)[0]}
        sim.minions[foe][:] = [m for m in sim.minions[foe] if id(m) in kept]
        for tier, tower in enumerate(sim.towers[foe]):
            record = memory.towers[lane * len(TIERS) + tier]
            _redact(tower, TOWER, sees(info, team, RIFT.lane_pos(name, tower.s)), scope._replace(record=record))
        _redact_lane(sim, scope)
    info.sights[:] = [s for s in info.sights if s.team == team]
    info.memory[foe] = new_memory(info.config, foe)
    info.seed = SNAPSHOT["seed"].blank(info, scope)
    return InfoState(team, info.snapshot(), seen)


def _redact_lane(sim: LaneSim, scope: Scope) -> None:
    """The lane's own fields, its minions' scratch fields, and every reference that a kept unit or missile holds."""
    living = {id(m) for team in range(2) for m in sim.minions[team]}
    blanks: dict[int, object] = {}

    def refer(target):
        if target is None or type(target) is Tower or id(target) in living:
            return target
        if id(target) not in blanks:
            if type(target) is ChampionTarget:
                blank = ChampionTarget(target.inp, target.s)
                _redact(blank, CHAMPION_TARGET, True, scope)
            elif target.hp > 0:
                blank = None
            else:
                blank = Minion(target.uid, target.team, target.rules, 0.0, 0.0, 0.0, 0.0, 0.0, died_at=target.died_at)
            blanks[id(target)] = blank
        return blanks[id(target)]

    for team in range(2):
        for m in sim.minions[team]:
            _redact(m, MINION, True, scope)
            m.target, m.aimed, m.swing_at = refer(m.target), refer(m.aimed), refer(m.swing_at)
    missiles = [(land, uid, order, team, rules, ad, refer(target)) for land, uid, order, team, rules, ad, target in sim._missiles]
    sim._missiles = [(land, uid, k, team, rules, ad, target) for k, (land, uid, _, team, rules, ad, target)
                     in enumerate((missile for missile in missiles if missile[-1] is not None), 1)]
    _redact(sim, LANE, True, scope)
    sim.invalidate()
