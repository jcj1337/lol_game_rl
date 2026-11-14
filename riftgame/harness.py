"""Running games: the policy interface, scripted policies, and replays.

A policy is `act(observation, noise) -> action index`. The noise is a keyed draw on the seat and the tick, so
a policy holds no generator and a replay needs only the actions.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from riftgame.champions import (ACTIONS, CAMP_OF, HOLD, HOME, KEEP, LANES, MAP, RECALL, RETURNS, RIFT, ROLES, SEATS, TEAMS, Action, Kind,
                                capability)
from riftgame.economy import JUNGLE_ITEM
from riftgame.jungle import SITES
from riftgame.lanes import TOWER_RANGE
from riftgame.rng import Stream, keyed_uniform
from riftgame.vision import Observation, Place, legal_mask, observe_team
from riftgame.world import Config, InvariantError, World, check_invariants

Policy = Callable[[Observation, float], int]


def random_legal(o: Observation, noise: float) -> int:
    legal = [i for i, ok in enumerate(legal_mask(o)) if ok]
    return legal[int(noise * len(legal))]


_AWAY = tuple(tuple(i for i, a in enumerate(ACTIONS) if a.kind is Kind.MOVE and not RETURNS[role][i])
              for role in range(len(ROLES)))
_HOMEWARD = tuple(None if lane is None else ACTIONS.index(Action(Kind.LANE, (lane, "passive", "wave"))) for lane in HOME)


def roamer(o: Observation, noise: float) -> int:
    """Always prefers a legal action away from its lane: it finishes a walk off the lane, then starts another.

    It heads for its lane only when the mask leaves nothing else.
    """
    mask, role = legal_mask(o), o.me.role
    if mask[KEEP] and o.me.intent in _AWAY[role]:
        return KEEP
    away = [i for i in _AWAY[role] if mask[i]]
    if away:
        return away[int(noise * len(away))]
    homeward = _HOMEWARD[role]
    return homeward if homeward is not None and mask[homeward] else KEEP


_FARM = tuple(None if lane is None else ACTIONS.index(Action(Kind.LANE, (lane, "last_hit", "wave"))) for lane in HOME)


def farmer(o: Observation, noise: float) -> int:
    """Every laner last-hits in its own lane and junglers hold. `scripted` adds the jungler."""
    farm = _FARM[o.me.role]
    return farm if farm is not None and legal_mask(o)[farm] else KEEP


_CAMP = tuple(i for i, a in enumerate(ACTIONS) if a.kind is Kind.CAMP)
_WALK_TO = tuple(ACTIONS.index(Action(Kind.MOVE, ACTIONS[i].target)) for i in _CAMP)
_CAMP_KIND = tuple(SITES[CAMP_OF[0][i]].kind for i in _CAMP)
_OWN_CAMPS = tuple(k for k, i in enumerate(_CAMP) if ACTIONS[i].target.startswith("own_"))
_FOUNTAIN = Place("own_fountain>own_base", 0.0)
# Shares of maximum health, all Assumed: the jungler starts no camp that would take it below the first, recalls
# below the second, and leaves its fountain above the third.
FIGHT_DOWN_TO, RECALL_BELOW, LEAVE_ABOVE = 0.25, 0.35, 0.8


def approach(o: Observation, k: int) -> int:
    """The action that takes a champion into a fight with camp `k` of its observation.

    A walk that ends before a spawn that its team knows of would find the camp empty, so the champion walks to the
    camp first and waits there.
    """
    camp = o.camps[k]
    speed = capability(ROLES[o.me.role], o.me.level, o.me.upgrades).move_speed
    if camp.hp <= 0 and camp.spawn_s and camp.spawn_s >= camp.walk / speed:
        return _WALK_TO[k] if camp.walk > 0 else HOLD
    return _CAMP[k]


def jungler(o: Observation, noise: float) -> int:
    """Clears the camp that pays the most gold plus XP per second of walking, waiting, and fighting, by what its
    team remembers. The XP counts the jungle item's bonus for a camp.

    It finishes a camp or a recall that it has started. It waits at a camp whose spawn its team knows. With no
    camp that it could fight safely it recalls, and with no camp that its team knows of it walks to the own camp
    that the team has not seen for the longest.
    """
    me = o.me
    if me.hp <= 0 or ACTIONS[me.intent].kind in (Kind.CAMP, Kind.RECALL):
        return KEEP
    home = me.place == _FOUNTAIN
    if me.hp < (LEAVE_ABOVE if home else RECALL_BELOW) * me.max_hp:
        return HOLD if home else RECALL
    can = capability(ROLES[me.role], me.level, me.upgrades)
    # A camp spawns at the average level of all ten champions. The team's own average stands in for it.
    level = round((me.level + sum(mate.level for mate in o.mates)) / 5)
    best, best_rate, unsafe = None, 0.0, False
    for k, camp in enumerate(o.camps):
        if camp.hp <= 0 and camp.spawn_s is None:
            continue
        kind = _CAMP_KIND[k]
        fight_s = (camp.hp or kind.health(level)) / can.camp_dps
        if me.hp - kind.damage_per_s * fight_s < FIGHT_DOWN_TO * me.max_hp:
            unsafe = True
            continue
        reward = sum(kind.reward(camp.level or level)) + JUNGLE_ITEM["large_monster_bonus_xp"]
        rate = reward / (max(camp.walk / can.move_speed, camp.spawn_s or 0.0) + fight_s)
        if rate > best_rate:
            best, best_rate = k, rate
    if best is not None:
        return approach(o, best)
    if unsafe:
        return HOLD if home else RECALL
    return _WALK_TO[max(_OWN_CAMPS, key=lambda k: float("inf") if o.camps[k].seen_age_s is None else o.camps[k].seen_age_s)]


def scripted(o: Observation, noise: float) -> int:
    """The scripted baseline for all ten seats: junglers clear camps and laners last-hit in their own lanes."""
    return jungler(o, noise) if HOME[o.me.role] is None else farmer(o, noise)


_FIGHT = tuple(i for i, a in enumerate(ACTIONS) if a.kind is Kind.FIGHT)
_TO_FOUNTAIN = ACTIONS.index(Action(Kind.MOVE, "own_fountain"))


def _enemy_towers(side: int) -> dict[str, tuple[float, ...]]:
    """Per lane, where the enemy towers stand in the frame of the team `side`, from the outer one inward."""
    def framed(t) -> float:
        return t.s if side == 0 else RIFT.lanes[t.lane].length - t.s
    return {lane: tuple(framed(t) for t in sorted((t for t in MAP.towers if t.lane == lane and t.team != TEAMS[side]),
                                                  key=lambda t: ("outer", "inner", "inhibitor").index(t.tier))) for lane in LANES}


def _by_open_tower(o: Observation, towers: dict[str, tuple[float, ...]], decision_s: float) -> bool:
    """Whether the champion could walk into the range of a standing enemy tower of its lane before its next
    decision while no minion of its own stands in that range. Distances run along the lane, which is never shorter
    than the straight line to a tower beside a straight stretch of lane."""
    lane = o.me.place.route
    if lane not in towers:
        return False
    view = o.lanes[LANES.index(lane)]
    walk = capability(ROLES[o.me.role], o.me.level, o.me.upgrades).move_speed * (1.0 + o.me.homeguard) * decision_s
    for s, hp in zip(towers[lane], view.enemy_towers):
        covered = view.own_lead is not None and abs(view.own_lead - s) <= TOWER_RANGE
        if hp > 0 and not covered and abs(o.me.place.s - s) <= TOWER_RANGE + walk:
            return True
    return False


def brawler(retreat_below: float = 0.0, side: int | None = None, decision_s: float = 2.0) -> Policy:
    """A policy that fights what it sees: the enemy champion with the least health in its team's view.

    It keeps a fight that it has started, also after the target has left the view. Below the share
    `retreat_below` of its health it walks to its own fountain instead. It chooses nothing that its mask forbids.

    With `side`, the team it plays on, it also stays out of enemy tower range (Assumed). At a decision on a lane
    from which it could walk into the range of a standing enemy tower within `decision_s`, the time to its next
    decision, while no minion of its own stands in that range, it drops its fight, starts none, and holds. It reads
    only its observation and where the towers stand.
    """
    towers = None if side is None else _enemy_towers(side)

    def act(o: Observation, noise: float) -> int:
        me, mask = o.me, legal_mask(o)
        if me.hp <= 0:
            return KEEP
        if me.hp < retreat_below * me.max_hp:
            return KEEP if me.intent == _TO_FOUNTAIN else _TO_FOUNTAIN
        if towers is not None and mask[HOLD] and _by_open_tower(o, towers, decision_s):
            return KEEP if me.intent == HOLD else HOLD
        if ACTIONS[me.intent].kind is Kind.FIGHT and mask[KEEP]:
            return KEEP
        seen = [(enemy.hp, role) for role, enemy in enumerate(o.enemies) if enemy is not None and mask[_FIGHT[role]]]
        if seen:
            return _FIGHT[min(seen)[1]]
        return KEEP if mask[KEEP] else _TO_FOUNTAIN

    return act


def tick(world: World, policy: Policy | Sequence[Policy], check: bool = False) -> tuple[int, ...] | None:
    """Advance one tick and return the actions submitted on it, or None between decisions.

    `policy` plays every seat, or it is one policy per seat. With `check`, an illegal choice or a broken invariant
    raises `InvariantError`.
    """
    actions = None
    if world.tick % world.config.decision_ticks == 0:
        observations = [*observe_team(world, 0), *observe_team(world, 1)]
        policies = policy if isinstance(policy, Sequence) else [policy] * len(observations)
        actions = tuple(act(o, keyed_uniform(world.seed, Stream.POLICY, seat, world.tick))
                        for seat, (act, o) in enumerate(zip(policies, observations, strict=True)))
        if check:
            for seat, (o, action) in enumerate(zip(observations, actions)):
                if not legal_mask(o)[action]:
                    raise InvariantError(f"seat {seat} chose {ACTIONS[action]}, which its mask forbids")
    before = world.tick
    world.step(actions)
    if check:
        check_invariants(world, before)
    return actions


def run(world: World, policy: Policy, ticks: int, check: bool = False) -> None:
    for _ in range(ticks):
        tick(world, policy, check)


@dataclass(frozen=True, slots=True)
class Replay:
    """A game as its config, its seed, and what was submitted on each tick."""

    config: Config
    seed: int
    log: tuple[tuple[int, ...] | None, ...]


def record(config: Config, seed: int, policy: Policy, ticks: int) -> tuple[Replay, list[str]]:
    """Play a new game and return its replay with the digest after every tick."""
    world, log, digests = World(config, seed), [], []
    for _ in range(ticks):
        log.append(tick(world, policy))
        digests.append(world.digest())
    return Replay(config, seed, tuple(log)), digests


def rerun(replay: Replay) -> list[str]:
    """The digest after every tick of a replayed game."""
    world, digests = World(replay.config, replay.seed), []
    for actions in replay.log:
        world.step(actions)
        digests.append(world.digest())
    return digests
