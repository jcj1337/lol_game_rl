"""Economy: what a champion earns from lanes and from the clock.

Three sources stay apart in every champion's ledger. Minion gold is paid once, to the champion that lands the
killing blow, or to the support's nearest ally when a support-item charge shares the kill. The support item pays
its own gold. Passive gold comes from the clock. XP for a minion is split among the enemy champions in range.
"""

from typing import TYPE_CHECKING

from riftgame.champions import ACTIONS, MODES, RIFT, ROLES, Champion, Income, Kind, R, capability_of, level_of, pay
from riftgame.lanes import ChampionDamage, ChampionInput, MinionDeath, Mode, stance, xp_share

if TYPE_CHECKING:
    from riftgame.world import World

ECONOMY = R["economy"]
ITEM = R["support_item"]
JUNGLE_ITEM = R["jungle_item"]
XP_RANGE = R["minions"]["xp_range"]
SUPPORT, JUNGLE = ROLES.index("support"), ROLES.index("jungle")
# The reference names melee and ranged champions. Until M9 gives profiles an attack type, range decides it.
RANGED_FROM = 300.0


def lane_mode(c: Champion) -> tuple[str, Mode] | None:
    """The lane and wave mode of a living champion's `LANE` intent."""
    action = ACTIONS[c.intent]
    if c.hp <= 0 or action.kind is not Kind.LANE:
        return None
    lane, mode = action.target
    return lane, Mode(MODES.index(mode))


def level_lead(world: "World") -> float:
    """Blue's average champion level minus red's."""
    levels = [level_of(c.xp) for c in world.champions]
    return (sum(levels[:5]) - sum(levels[5:])) / 5


def charge_partner(world: "World", support: Champion) -> Champion | None:
    """The nearest living ally within the support item's range, who gets the gold of a shared kill."""
    near = [(RIFT.separation(support.pos, ally.pos), ally.seat) for ally in world.champions
            if ally.team == support.team and ally.seat != support.seat and ally.hp > 0]
    gap, seat = min(near, default=(float("inf"), -1))
    return world.champions[seat] if gap <= ITEM["charge_ally_range"] else None


def lane_inputs(world: "World", lane: str) -> list[ChampionInput]:
    """The champions that take part in this lane's tick: alive, on the lane, with a `LANE` intent for it."""
    inputs = []
    for c in world.champions:
        mine = lane_mode(c)
        s = RIFT.lane_s(lane, c.pos)
        if mine is None or mine[0] != lane or s is None:
            continue
        can = capability_of(c)
        _, in_path = stance(world.lanes[lane], c.team, mine[1], can.attack_range)
        execute = 0.0
        if c.role == SUPPORT and c.item_charges > 0 and charge_partner(world, c) is not None:
            execute = ITEM["execute_threshold_ranged" if can.attack_range >= RANGED_FROM else "execute_threshold_melee"]
        inputs.append(ChampionInput(c.seat, c.team, s, mine[1], in_path, can.hit_damage, can.attack_speed, can.attack_range,
                                    can.area_dps, execute_below=execute))
    return inputs


def jungle_share(c: Champion, now_s: float) -> float:
    """The share of lane-minion XP that a jungler keeps under the jungle item."""
    if c.role != JUNGLE or now_s >= JUNGLE_ITEM["minion_xp_penalty_end_s"]:
        return 1.0
    return 1.0 - JUNGLE_ITEM["minion_xp_penalty_start"] * (1.0 - now_s / JUNGLE_ITEM["minion_xp_penalty_end_s"])


def settle_lane(world: "World", lane: str, events: list) -> None:
    """Pay the gold and XP of this tick's minion deaths in one lane."""
    now_s = world.tick * world.config.tick_s
    for e in events:
        if type(e) is not MinionDeath:
            continue
        if e.killer is not None:
            killer = world.champions[e.killer]
            partner = charge_partner(world, killer) if e.shared and killer.item_charges > 0 else None
            if partner is not None:
                killer.item_charges -= 1
                pay(killer, Income.SUPPORT_ITEM, ITEM["charge_gold"])
                pay(partner, Income.MINION, e.gold)
            else:
                pay(killer, Income.MINION, e.gold)
        where = RIFT.lane_pos(lane, e.s)
        sharers = [c for c in world.champions if c.team != e.team and c.hp > 0 and RIFT.separation(c.pos, where) <= XP_RANGE]
        for c in sharers:
            c.xp += xp_share(e.xp, len(sharers)) * jungle_share(c, now_s)


def minion_hits(events: list) -> list[tuple[int, float]]:
    """This tick's minion blows on champions, as (seat, raw damage)."""
    return [(e.seat, e.damage) for e in events if type(e) is ChampionDamage]


def accrue(world: "World") -> None:
    """Income from the clock: passive gold for everyone, and the support item's gold and charges."""
    tick_s = world.config.tick_s
    now_s = world.tick * tick_s
    passive = ECONOMY["passive_gold_per_10s"] / 10 * tick_s if now_s >= ECONOMY["passive_gold_start_s"] else 0.0
    # Charges arrive on a fixed clock from the first one. A charge that finds the item full is lost.
    since_first = now_s - ITEM["charge_first_s"]
    charge_due = since_first >= 0 and since_first // ITEM["charge_interval_s"] > (since_first - tick_s) // ITEM["charge_interval_s"]
    for c in world.champions:
        if passive:
            pay(c, Income.PASSIVE, passive)
        if c.role == SUPPORT:
            pay(c, Income.SUPPORT_ITEM, ITEM["passive_gold_per_10s"] / 10 * tick_s)
            if charge_due:
                c.item_charges = min(ITEM["charge_max"], c.item_charges + 1)
