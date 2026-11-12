"""Jungle: the twelve camps and the two Rift Scuttlers.

A camp is one pool of health at a map node, with a damage rate against one champion at a time. It first appears
on the game clock, whatever any champion does, and it comes back a fixed delay after it dies. The world keeps one
`Camp` per entry of `SITES`, in that order.

The functions here take the world and never import it. They change camps and nothing else. What a tick does to the
rest of the world leaves as a return value, and the world applies it: hits on champions, gold and XP, ended intents,
and the Speed Shrine that a dead Scuttler leaves.
"""

import math
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from riftgame import ruleset
from riftgame.champions import CAMP_OF, CAMP_SITES, DEST, MAP, RIFT, Champion, R, Target, attacks, capability_of, level_of
from riftgame.map import Pos
from riftgame.rng import Stream, keyed_uniform

if TYPE_CHECKING:
    from riftgame.world import Config, World

CAMPS = R["camps"]
SCUTTLER = R["scuttler"]
ASSUMED = ruleset.load("patch_26_22_m8")["camps"]
LEVEL_CAP = R["economy"]["level_cap"]
LEASH = ASSUMED["leash_range"]
SHRINE_S = SCUTTLER["shrine_duration_s"]
SHRINE_RADIUS = SCUTTLER["shrine_sight_radius"]
BUFFS = ("blue_sentinel", "red_brambleback")


@dataclass(frozen=True, slots=True)
class CampKind:
    """The rules of one kind of camp. `gold`, `xp`, and `hp` hold the value at level 1 and at the level cap.

    The reference gives those two ends and no curve between them. The straight line over the levels is Assumed.
    `first_hp_factor` scales the health of a spawn on the kind's first-spawn tick. `timer_window_s` is how long
    before a respawn the sight of the empty camp tells a team the time.
    """

    name: str
    first_spawn_s: float
    respawn_s: float
    gold: tuple[float, float]
    xp: tuple[float, float]
    hp: tuple[float, float]
    first_hp_factor: float
    damage_per_s: float
    timer_window_s: float
    scuttler: bool

    def health(self, level: int, first: bool = False) -> float:
        return _at_level(self.hp, level) * (self.first_hp_factor if first else 1.0)

    def reward(self, level: int) -> tuple[float, float]:
        """Gold and XP of a camp of this level."""
        return _at_level(self.gold, level), _at_level(self.xp, level)


def _at_level(ends: tuple[float, float], level: int) -> float:
    return ends[0] + (ends[1] - ends[0]) * (level - 1) / (LEVEL_CAP - 1)


def _kind(name: str) -> CampKind:
    scuttler = name == "scuttler"
    rules = SCUTTLER if scuttler else CAMPS[name]
    gold = rules["gold"]
    # The reference names no timer window for the Scuttler. It gets the window of the camps without a buff (Assumed).
    window = CAMPS["timer_window_buff_s" if name in BUFFS else "timer_window_other_s"]
    return CampKind(name, rules["first_spawn_s"], rules["respawn_s"], tuple(gold) if isinstance(gold, list) else (gold, gold),
                    tuple(rules["xp"]), tuple(rules["hp"]), rules.get("first_spawn_hp_factor", 1.0),
                    ASSUMED["damage_per_s"][name], window, scuttler)


@dataclass(frozen=True, slots=True)
class Site:
    """A map node where a camp lives."""

    node: str
    pos: Pos
    kind: CampKind


KINDS = {name: _kind(name) for name in (*dict.fromkeys(MAP.camps.values()), "scuttler")}
SITES = tuple(Site(node, RIFT.at(node), KINDS[MAP.camps.get(node, "scuttler")]) for node in CAMP_SITES)
SCUTTLERS = tuple(i for i, site in enumerate(SITES) if site.kind.scuttler)


@dataclass(slots=True)
class Camp:
    """One camp's mutable state. A camp is alive while its health is above zero.

    `spawn_tick` is the tick of its next spawn. It is -1 while the camp is alive, and for a river node where no
    Scuttler is due. `level` and `max_hp` are those of its last spawn. `engaged` is the seat it attacks, or -1.
    """

    hp: float
    max_hp: float
    level: int
    spawn_tick: int
    engaged: int


@dataclass(frozen=True, slots=True)
class CampSpawn:
    t: float
    camp: int
    level: int


@dataclass(frozen=True, slots=True)
class CampDeath:
    """`camp` and `respawn` index `SITES`. `respawn` is the camp whose next spawn this death set, or -1 if it set
    none: the first of the two first Scuttlers to die starts no timer."""

    t: float
    camp: int
    killer: int
    gold: float
    xp: float
    respawn: int


def new_camps(config: "Config") -> list[Camp]:
    """The camps at the start of a game: none alive, each due at its first spawn time."""
    return [Camp(0.0, 0.0, 0, config.ticks(site.kind.first_spawn_s), -1) for site in SITES]


def spawn(world: "World") -> list[CampSpawn]:
    """Step 2 of the tick: every camp whose spawn tick has come appears at full health.

    A camp spawns at the average level of the ten champions (Sourced, reference rows B10g and C14b). A half
    rounds up (Assumed).
    """
    tick = world.tick
    due = [i for i, camp in enumerate(world.camps) if 0 <= camp.spawn_tick <= tick]
    if not due:
        return []
    level = math.floor(sum(level_of(c.xp) for c in world.champions) / len(world.champions) + 0.5)
    for i in due:
        camp, kind = world.camps[i], SITES[i].kind
        camp.max_hp = kind.health(level, first=tick == world.config.ticks(kind.first_spawn_s))
        camp.hp, camp.level, camp.spawn_tick, camp.engaged = camp.max_hp, level, -1, -1
    return [CampSpawn(tick * world.config.tick_s, i, level) for i in due]


def attack(world: "World", c: Champion) -> tuple[int, float] | None:
    """The camp that a champion attacks this tick and the health its attack removes, or None.

    This is the one place that decides it. A champion whose attack goes to a camp on this tick attacks while it
    stands at its camp and the camp is alive. The attack is the same one that it would otherwise spend on minions,
    a champion, or a tower (M7 section 7.4), so a tick of it uses the champion's attack up.
    """
    if attacks(c) is not Target.CAMP:
        return None
    team = c.seat // 5
    camp = CAMP_OF[team][c.intent]
    if world.camps[camp].hp <= 0 or c.pos != DEST[team][c.intent]:
        return None
    return camp, capability_of(c).camp_dps * world.config.tick_s


def collect(world: "World") -> tuple[list[tuple[int, float]], list[tuple[int, int, float]]]:
    """Step 4 of the tick: the camps' hits on champions as (seat, raw damage), and the champions' blows on camps
    as (camp, seat, health removed).

    A camp hits the champion that engaged it for as long as that champion lives within the leash, whatever the
    champion does. Once it does not, the camp lets go of it. A hurt camp that has let go returns to full health,
    unless another champion is fighting it: then the next blow engages it as it is.
    """
    tick_s = world.config.tick_s
    hits = []
    for i, (camp, site) in enumerate(zip(world.camps, SITES)):
        if camp.engaged >= 0:
            c = world.champions[camp.engaged]
            if c.hp > 0 and RIFT.separation(c.pos, site.pos) <= LEASH:
                if site.kind.damage_per_s:
                    hits.append((c.seat, site.kind.damage_per_s * tick_s))
                continue
            camp.engaged = -1
        if 0 < camp.hp < camp.max_hp and not any(c.hp > 0 for c in fighters(world, i)):
            camp.hp = camp.max_hp
    blows = []
    for c in world.champions:
        blow = attack(world, c)
        if blow is not None:
            blows.append((blow[0], c.seat, blow[1]))
    return hits, blows


def resolve(world: "World", blows: list[tuple[int, int, float]]) -> list[CampDeath]:
    """Step 5 of the tick: take the champions' blows, and report the camps that died.

    The champion that dealt the most to a camp this tick leads, with a keyed draw between equals. The leader
    engages a camp that nobody had engaged, and it is the killer of a camp that dies. Blows are summed without
    regard to their order, so the seat order changes nothing.
    """
    if not blows:
        return []
    tick, seed, config = world.tick, world.seed, world.config
    struck: dict[int, list[tuple[float, float, int]]] = {}
    for i, seat, dealt in blows:
        struck.setdefault(i, []).append((dealt, keyed_uniform(seed, Stream.CAMP, tick, i, seat), seat))
    killers = {}
    for i in sorted(struck):
        camp = world.camps[i]
        leader = max(struck[i])[2]
        if camp.engaged < 0:
            camp.engaged = leader
        camp.hp -= math.fsum(dealt for dealt, _, _ in struck[i])
        if camp.hp <= 0:
            camp.hp, camp.engaged = 0.0, -1
            killers[i] = leader
    respawn = {}
    for i in killers:
        kind = SITES[i].kind
        if not kind.scuttler:
            world.camps[i].spawn_tick = tick + config.ticks(kind.respawn_s)
            respawn[i] = i
    # The Scuttler's timer starts when the river is empty: after both of the first two, and after each later one.
    if len(respawn) < len(killers) and not any(world.camps[i].hp > 0 for i in SCUTTLERS):
        river = SCUTTLERS[int(keyed_uniform(seed, Stream.CAMP, tick) * len(SCUTTLERS))]
        world.camps[river].spawn_tick = tick + config.ticks(SITES[river].kind.respawn_s)
        respawn |= {i: river for i in killers if i not in respawn}
    return [CampDeath(tick * config.tick_s, i, killer, *SITES[i].kind.reward(world.camps[i].level), respawn.get(i, -1))
            for i, killer in killers.items()]


def fighters(world: "World", camp: int) -> list[Champion]:
    """The champions that stand at a camp with a `CAMP` intent for it."""
    at = SITES[camp].pos
    return [c for c in world.champions if CAMP_OF[c.seat // 5][c.intent] == camp and c.pos == at]


def faults(world: "World") -> Iterator[str]:
    """What is wrong with the camps, one message each. A world that legal play can reach yields nothing."""
    for camp, site in zip(world.camps, SITES):
        if not 0.0 <= camp.hp <= camp.max_hp:
            yield f"camp {site.node} has {camp.hp} health of {camp.max_hp}"
        if camp.hp > 0 and camp.spawn_tick >= 0:
            yield f"camp {site.node} is alive and due to spawn at tick {camp.spawn_tick}"
        if camp.hp <= 0 and camp.spawn_tick < 0 and not site.kind.scuttler:
            yield f"camp {site.node} is dead and not due to spawn"
        if camp.engaged >= 0 and camp.hp <= 0:
            yield f"camp {site.node} is dead and engaged with seat {camp.engaged}"
    river = [world.camps[i] for i in SCUTTLERS]
    kind = SITES[SCUTTLERS[0]].kind
    alive = [camp for camp in river if camp.hp > 0]
    due = [camp.spawn_tick for camp in river if camp.hp <= 0 and camp.spawn_tick >= 0]
    # Two Scuttlers exist only as the first pair: both due at the first spawn time, or both alive with its health.
    pair = (not alive and all(when == world.config.ticks(kind.first_spawn_s) for when in due)
            or not due and all(camp.max_hp == kind.health(camp.level, first=True) for camp in alive))
    if len(alive) + len(due) != 1 and not (len(alive) + len(due) == 2 and pair):
        yield f"the river has {len(alive)} Scuttlers alive and {len(due)} due"
