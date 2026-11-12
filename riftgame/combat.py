"""Combat: champion against champion, the one attack budget, and what a kill pays.

There is no fight object and no outcome roll (M7 section 5.9). On each tick `collect` gathers every champion's
damage on an enemy champion from one state. `land` applies all of it at once, together with the blows of minions,
camps, and towers. `kills` settles every death of the tick from the world as it stands before any of them. The
order in which the code visits champions therefore changes nothing.

The functions here take the world and never import it. `collect`, `harassed`, and `kills` only read. `spend`,
`land`, and `reward` change champions and nothing else, and the world applies the deaths.

These reference rules are left out: bounties and shutdown gold, the level-difference modifier on kill XP, the
growth of the assist pool in the early game, and the armor penetration of tower shots. Champions have no armor
until M9.
"""

from dataclasses import dataclass
from math import fsum
from typing import TYPE_CHECKING

from riftgame import ruleset
from riftgame.champions import FOE, IN_RANGE, RIFT, Champion, Income, R, Target, attacks, capability_of, enter_combat, level_of, pay
from riftgame.rng import Stream, keyed_uniform
from riftgame.vision import sees

if TYPE_CHECKING:
    from riftgame.world import World

WINDOWS = ruleset.load("patch_26_22_m8")["combat"]
ASSIST_S = WINDOWS["assist_window_s"]
CALL_S = WINDOWS["call_for_help_window_s"]
KILL_XP = WINDOWS["kill_xp"]
ECONOMY = R["economy"]
LEVEL_CAP = ECONOMY["level_cap"]
RETALIATION, KILLER, FIRST_BLOOD = range(3)


@dataclass(frozen=True, slots=True)
class Hit:
    """One champion's damage on an enemy champion on one tick, before the victim's armor. `slow` is the share of
    move speed that the attacker's lockdown takes from the victim, or 0.0 if it used none."""

    attacker: int
    victim: int
    damage: float
    slow: float


@dataclass(frozen=True, slots=True)
class Kill:
    """A champion's death and what it pays. `killer` is None for an execution, which pays nothing.

    `gold` goes to the killer and holds the first-blood bonus when `first_blood` is set. `assist_gold` goes to each
    seat of `assists`, and `xp` to each seat of `sharers`: the killer, the assisters, and the killer's allies that
    stood within XP range of the victim.
    """

    t: float
    victim: int
    killer: int | None
    gold: float
    first_blood: bool
    assists: tuple[int, ...]
    assist_gold: float
    sharers: tuple[int, ...]
    xp: float


def pick(world: "World", tied: list[Champion], *key: int) -> Champion:
    """One of several champions that tie, by a keyed draw on the tick and `key`.

    The champions are put in the order of their places on the map before the draw, so exchanging seats changes no
    pick. The seat orders only champions that stand on one spot.
    """
    if len(tied) == 1:
        return tied[0]
    ordered = sorted(tied, key=_place)
    return ordered[int(keyed_uniform(world.seed, Stream.COMBAT, world.tick, *key) * len(ordered))]


def _place(c: Champion) -> tuple[int, float, int]:
    return c.pos.edge, c.pos.offset, c.seat


def _reaches(c: Champion, foe: Champion) -> bool:
    return RIFT.separation(c.pos, foe.pos) <= capability_of(c).attack_range + IN_RANGE


def _hit(world: "World", c: Champion, foe: Champion) -> Hit:
    """A tick of a champion's damage rate. Its lockdown goes with it when it is ready and the mana covers it."""
    can = capability_of(c)
    locks = can.lockdown_slow > 0 and world.tick >= c.lockdown_tick and c.mana >= can.lockdown_mana
    return Hit(c.seat, foe.seat, can.champion_dps * world.config.tick_s, can.lockdown_slow if locks else 0.0)


def collect(world: "World") -> list[Hit]:
    """Step 4 of the tick: every champion's damage on an enemy champion, from the places held after the move step.

    A fighter hits its target on a tick when the target is alive, within its attack range by the straight line,
    and in the view of its team. A champion that holds or follows hits back at the enemy that deals it the most
    damage on this tick and stands within its own range. It needs no sight of that enemy: a champion that damages
    an enemy champion is visible to the victim's team on that tick (M7 section 6.1).
    """
    champions = world.champions
    fighters, guards = [], []
    for c in champions:
        if attacks(c) is Target.CHAMPION:
            (fighters if FOE[c.intent] >= 0 else guards).append(c)
    hits = []
    for c in fighters:
        foe = champions[(1 - c.seat // 5) * 5 + FOE[c.intent]]
        if foe.hp > 0 and _reaches(c, foe) and sees(world, c.seat // 5, foe.pos):
            hits.append(_hit(world, c, foe))
    if not hits:
        return hits
    answers = []
    for c in guards:
        on_me = [hit for hit in hits if hit.victim == c.seat and _reaches(c, champions[hit.attacker])]
        if on_me:
            most = max(hit.damage for hit in on_me)
            hardest = [champions[hit.attacker] for hit in on_me if hit.damage == most]
            answers.append(_hit(world, c, pick(world, hardest, RETALIATION, c.pos.edge, int(c.pos.offset))))
    return hits + answers


def harassed(world: "World", hits: list[Hit]) -> dict[int, tuple[int, ...]]:
    """Per champion that is harassing now: the seats of the enemy champions that it damaged on this tick or within
    the call-for-help window before it. Minions and towers answer for that long."""
    victims: dict[int, set[int]] = {}
    for hit in hits:
        victims.setdefault(hit.attacker, set()).add(hit.victim)
    since = world.tick - world.config.ticks(CALL_S)
    for victim in world.champions:
        if max(victim.hurt_tick) >= since:
            foes = (1 - victim.seat // 5) * 5
            for role, tick in enumerate(victim.hurt_tick):
                if tick >= since:
                    victims.setdefault(foes + role, set()).add(victim.seat)
    return {seat: tuple(sorted(seats)) for seat, seats in victims.items()}


def spend(world: "World", hits: list[Hit], camp_blows: list[tuple[int, int, float]], lane_credit: dict[int, float]) -> None:
    """What this tick leaves of each living champion's attack credit, the one budget for every target class (M7
    section 7.4).

    A tick that damaged a champion or a camp used the attack up. A champion that hit in a lane has what the lane
    handed back. Every other champion earned its attack speed times the tick, up to one ready attack.
    """
    used = {hit.attacker for hit in hits} | {seat for _, seat, _ in camp_blows}
    tick_s = world.config.tick_s
    for c in world.champions:
        if c.hp <= 0:
            continue
        if c.seat in used:
            c.attack_credit = 0.0
        elif c.seat in lane_credit:
            c.attack_credit = lane_credit[c.seat]
        else:
            c.attack_credit = min(1.0, c.attack_credit + capability_of(c).attack_speed * tick_s)


def land(world: "World", hits: list[Hit], blows: list[tuple[int, float]]) -> None:
    """Step 5 of the tick, first half: all damage of the tick lands at once.

    `blows` are the hits of minions, camps, and towers on champions, as (seat, raw damage). Each victim loses the
    sum of what was aimed at it. A champion's hit also marks its victim, puts the attacker into combat, and
    carries its lockdown: the attacker pays the mana and starts the cooldown, and the victim is slowed from its
    next move on. Of several lockdowns on one victim the strongest counts, and a lockdown replaces a running one
    that is not stronger.
    """
    tick, config, champions = world.tick, world.config, world.champions
    taken: dict[int, list[float]] = {}
    for seat, raw in blows:
        taken.setdefault(seat, []).append(raw)
    for hit in hits:
        taken.setdefault(hit.victim, []).append(hit.damage)
    for seat, raws in taken.items():
        world.damage_champion(seat, fsum(raws))
    locks: dict[int, tuple[float, int]] = {}
    for hit in hits:
        attacker, victim = champions[hit.attacker], champions[hit.victim]
        victim.hurt_tick[hit.attacker % 5] = tick
        enter_combat(world, attacker)
        if hit.slow > 0:
            can = capability_of(attacker)
            attacker.mana -= can.lockdown_mana
            attacker.lockdown_tick = tick + config.ticks(can.lockdown_cooldown_s)
            locks[hit.victim] = max(locks.get(hit.victim, (0.0, 0)), (hit.slow, tick + 1 + config.ticks(can.lockdown_s)))
    for seat, (slow, until) in locks.items():
        victim = champions[seat]
        if tick + 1 >= victim.slow_until or slow >= victim.slow:
            victim.slow, victim.slow_until = slow, until


def _at_level(ends: list[float], level: int) -> float:
    """The reference gives a kill's XP at victim level 1 and at the level cap. The straight line between is Assumed."""
    return ends[0] + (ends[1] - ends[0]) * (level - 1) / (LEVEL_CAP - 1)


def kills(world: "World", hits: list[Hit]) -> list[Kill]:
    """Step 5 of the tick, second half: who killed each champion that died on this tick, and what each kill pays.

    It reads the world after the damage and before any dead champion is moved or any reward is paid. Two champions
    that kill each other on one tick are therefore both paid in full, and so is a killer that died earlier.

    The killer is the enemy champion that dealt the victim the most damage on this tick. If none did, it is the
    enemy champion that damaged it last within the assist window. With neither the death is an execution. The
    other enemy champions that damaged the victim within the window assist: they share the assist pool. The kill's
    XP is the solo amount for a killer alone. Otherwise the shared total is split equally among the killer, the
    assisters, and the killer's allies that were alive before this tick and stand within XP range of the victim.
    The first kill of the game pays the first-blood bonus, and of several on one tick a keyed draw picks one.
    """
    tick, champions = world.tick, world.champions
    dead = sorted((c for c in champions if c.hp <= 0 and c.respawn_tick < 0), key=_place)
    if not dead:
        return []
    window = world.config.ticks(ASSIST_S)
    dealt: dict[int, dict[int, float]] = {}
    for hit in hits:
        by = dealt.setdefault(hit.victim, {})
        by[hit.attacker] = by.get(hit.attacker, 0.0) + hit.damage
    killers: dict[int, Champion] = {}
    recent: dict[int, list[Champion]] = {}
    for victim in dead:
        foes = champions[(1 - victim.team) * 5:(2 - victim.team) * 5]
        recent[victim.seat] = [foe for foe in foes if tick - victim.hurt_tick[foe.role] <= window]
        by = dealt.get(victim.seat)
        if by:
            most = max(by.values())
            tied = [champions[seat] for seat, damage in by.items() if damage == most]
        else:
            last = max((victim.hurt_tick[foe.role] for foe in recent[victim.seat]), default=None)
            tied = [foe for foe in recent[victim.seat] if victim.hurt_tick[foe.role] == last]
        if tied:
            killers[victim.seat] = pick(world, tied, KILLER, victim.pos.edge, int(victim.pos.offset))
    first = None
    if killers and not any(c.earned[Income.KILL] for c in champions):
        first = pick(world, [victim for victim in dead if victim.seat in killers], FIRST_BLOOD)
    now = tick * world.config.tick_s
    found = []
    for victim in dead:
        killer = killers.get(victim.seat)
        if killer is None:
            found.append(Kill(now, victim.seat, None, 0.0, False, (), 0.0, (), 0.0))
            continue
        level = level_of(victim.xp)
        gold = ECONOMY["kill_gold_base"] + ECONOMY["kill_gold_level_7_plus_step"] * max(0, level - 6)
        assists = tuple(foe.seat for foe in recent[victim.seat] if foe is not killer)
        sharers = {killer.seat, *assists}
        sharers |= {ally.seat for ally in champions[killer.team * 5:killer.team * 5 + 5]
                    if ally.respawn_tick < 0 and RIFT.separation(ally.pos, victim.pos) <= ECONOMY["kill_xp_range"]}
        xp = _at_level(KILL_XP["solo" if len(sharers) == 1 else "shared_total"], level) / len(sharers)
        found.append(Kill(now, victim.seat, killer.seat, gold + ECONOMY["first_blood_bonus"] * (victim is first), victim is first,
                          assists, ECONOMY["assist_pool_fraction"] * gold / len(assists) if assists else 0.0,
                          tuple(sorted(sharers)), xp))
    return found


def reward(world: "World", kill: Kill) -> None:
    """Pay a kill: its gold to the killer, the assist pool to the assisters, and its XP to everyone that shares it."""
    if kill.killer is None:
        return
    champions = world.champions
    pay(champions[kill.killer], Income.KILL, kill.gold)
    for seat in kill.assists:
        pay(champions[seat], Income.ASSIST, kill.assist_gold)
    for seat in kill.sharers:
        champions[seat].xp += kill.xp
