"""Economy: what a champion earns from lanes, from camps, from towers, and from the clock.

Each source stays apart in every champion's ledger. Minion gold is paid once, to the champion that lands the
killing blow, or to the support's nearest ally when a support-item charge shares the kill. The support item pays
its own gold. Passive gold comes from the clock. XP for a minion is split among the enemy champions in range.
A camp's gold and XP go to its killer alone. A tower plate and the first tower of the game pay the enemy
champions near the tower, and a fallen tower pays the whole enemy team. `riftgame.combat` pays for kills.

The champion inputs of a lane are here too, because they are built from what a champion can do.
"""

from math import hypot
from typing import TYPE_CHECKING

from riftgame.champions import (LANE_ORDER, LANES, MAP, RIFT, ROLES, SIEGE_LANE, TEAMS, Champion, Income, R, capability_of,
                                known_front, level_of, pay)
from riftgame.lanes import (ADDED, CALL_RANGE, SWITCH_RANGE, TIERS, TOWERS, ChampionDamage, ChampionInput, MinionDeath, Mode,
                            TowerDestroyed, TowerPlate, TowerShot, stance, xp_share)
from riftgame.vision import EDGE_GAP

if TYPE_CHECKING:
    from riftgame.world import World

ECONOMY = R["economy"]
ITEM = R["support_item"]
JUNGLE_ITEM = R["jungle_item"]
XP_RANGE = R["minions"]["xp_range"]
SUPPORT, JUNGLE = ROLES.index("support"), ROLES.index("jungle")
# The reference names melee and ranged champions. Until M9 gives profiles an attack type, range decides it.
RANGED_FROM = 300.0
LOCAL_GOLD_RANGE = ADDED["towers"]["local_gold_range"]
TOWER_POS = {(t.lane, TEAMS.index(t.team), TIERS.index(t.tier)): RIFT.lane_pos(t.lane, t.s) for t in MAP.towers}


def _towers_in_reach() -> dict[str, list[tuple[tuple[int, int, float, float], ...]]]:
    """Per lane and map edge: the lane's towers that some place on the edge is within the switch range of, as
    (team, tier, x, y). A champion on an edge with none cannot matter to a tower of that lane."""
    def off(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
        dx, dy = bx - ax, by - ay
        f = min(1.0, max(0.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        return hypot(px - ax - f * dx, py - ay - f * dy)

    ends = [(*RIFT.node_xy[e.a], *RIFT.node_xy[e.b]) for e in RIFT.edges]
    sites = {lane: [(team, tier, *RIFT.xy(pos)) for (name, team, tier), pos in TOWER_POS.items() if name == lane] for lane in LANES}
    return {lane: [tuple(site for site in sites[lane] if off(site[2], site[3], *end) <= SWITCH_RANGE) for end in ends] for lane in LANES}


TOWERS_IN_REACH = _towers_in_reach()
# Per lane and map edge: whether some place on the edge is within the call-for-help range of the lane.
BESIDE = {name: [min(EDGE_GAP[e][on] for on in lane.edges) <= CALL_RANGE for e in range(len(RIFT.edges))]
          for name, lane in RIFT.lanes.items()}


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


def lane_inputs(world: "World", lane: str, calls: dict[int, tuple[int, ...]]) -> list[ChampionInput]:
    """The champions that take part in this lane's tick, whatever their intent: every living champion that is on
    the lane, or within the switch range of one of its standing towers, or harassing beside it.

    `calls` holds, per harassing champion, the enemy champions that it damaged (`combat.harassed`). A champion on
    the lane with a `LANE` intent for it hits minions in its mode. One with a `SIEGE` intent for the lane hits the
    enemy front tower. Everyone else only stands there: a tower may shoot it, and minions answer a call for help
    against it. A champion's attack credit goes in with its input, and the lane hands it back for those that hit.
    Its mana bounds the seconds of area damage it can pay for. A champion stands at the front that its team knows,
    as it walked there (`champions.lane_post`).
    """
    inputs = []
    sim, reach, beside = world.lanes[lane], TOWERS_IN_REACH[lane], BESIDE[lane]
    fronts = [None, None]
    for c in world.champions:
        if c.hp <= 0:
            continue
        s = RIFT.lane_s(lane, c.pos)
        victims = calls.get(c.seat, ())
        xy = None
        if s is None:
            xy = RIFT.xy(c.pos)
            near = any(hypot(xy[0] - x, xy[1] - y) <= SWITCH_RANGE and sim.tower_alive(team, TIERS[tier])
                       for team, tier, x, y in reach[c.pos.edge])
            if not near and not (victims and beside[c.pos.edge]):
                continue
            s = RIFT.project_to_lane(lane, *xy)
        can = capability_of(c)
        mine = LANE_ORDER[c.intent]
        mode, in_path, execute = Mode.PASSIVE, False, 0.0
        if mine is not None and mine[0] == lane and xy is None:
            mode = mine[1]
            if fronts[c.team] is None:
                fronts[c.team] = known_front(world, c.team, lane)
            _, in_path = stance(sim, c.team, mode, can.attack_range, fronts[c.team], hold=mine[2])
            if c.role == SUPPORT and c.item_charges > 0 and charge_partner(world, c) is not None:
                execute = ITEM["execute_threshold_ranged" if can.attack_range >= RANGED_FROM else "execute_threshold_melee"]
        inputs.append(ChampionInput(c.seat, c.team, s, mode, in_path, can.hit_damage, can.attack_speed, can.attack_range,
                                    can.area_dps, execute_below=execute, harassing=bool(victims), credit=c.attack_credit, xy=xy,
                                    tower_target=True, victims=victims, siege=SIEGE_LANE[c.intent] == lane,
                                    melee=can.attack_range < RANGED_FROM, aoe_s=c.mana / can.area_mana_s))
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


def settle_camp(world: "World", death) -> None:
    """Pay the gold and XP of a camp that died this tick to its killer. Nobody shares them (Assumed).

    The jungle item adds XP for each camp its holder kills, and more for the first. A Scuttler counts as a camp
    here (Assumed).
    """
    killer = world.champions[death.killer]
    bonus = 0.0
    if killer.role == JUNGLE:
        # Every camp pays gold, so a ledger with no camp gold marks the first camp without a field of its own.
        first = JUNGLE_ITEM["first_large_monster_bonus_xp"] if killer.earned[Income.CAMP] == 0 else 0.0
        bonus = JUNGLE_ITEM["large_monster_bonus_xp"] + first
    killer.xp += death.xp + bonus
    pay(killer, Income.CAMP, death.gold)


def minion_hits(events: list) -> list[tuple[int, float]]:
    """This tick's minion blows on champions, as (seat, raw damage)."""
    return [(e.seat, e.damage) for e in events if type(e) is ChampionDamage]


def tower_hits(events: list) -> list[tuple[int, float]]:
    """This tick's tower shots on champions, as (seat, raw damage)."""
    return [(e.seat, e.damage) for e in events if type(e) is TowerShot]


def _share_locally(world: "World", lane: str, team: int, tier: int, gold: float, source: Income) -> None:
    """Split gold among the living enemy champions near a tower. With nobody there, nobody is paid."""
    at = TOWER_POS[lane, team, tier]
    near = [c for c in world.champions if c.team != team and c.hp > 0 and RIFT.separation(c.pos, at) <= LOCAL_GOLD_RANGE]
    for c in near:
        pay(c, source, gold / len(near))


def settle_towers(world: "World") -> None:
    """Pay this tick's broken plates and fallen towers, from the lanes' events.

    A plate pays its gold to the living enemy champions near the tower, whoever dealt the damage. A fallen tower
    pays its global gold to every champion of the other team. The first tower of the game also pays its bonus to
    the enemy champions near it. Of several towers that fall on one tick the earliest in the tick is the first,
    and then the lane order decides (Assumed).

    The reference also gives a share to the champion that dealt the damage, wherever it stands. That is left out,
    and so is the decay of an outer tower's plate gold after 11:00.
    """
    fallen = []
    for lane, e in world.events:
        if type(e) is TowerPlate:
            _share_locally(world, lane, e.team, e.tier, TOWERS["plate_gold"], Income.PLATE)
        elif type(e) is TowerDestroyed:
            fallen.append((e.t, LANES.index(lane), e.team, e.tier))
    if not fallen:
        return
    down = sum(not world.lanes[lane].tower_alive(team, tier) for lane in LANES for team in range(2) for tier in TIERS)
    for i, (_, lane, team, tier) in enumerate(sorted(fallen)):
        for c in world.champions[(1 - team) * 5:(2 - team) * 5]:
            pay(c, Income.TOWER, TOWERS[TIERS[tier]]["global_gold"])
        if i == 0 and down == len(fallen):
            _share_locally(world, LANES[lane], team, tier, TOWERS["first_tower_bonus_gold"], Income.TOWER)


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
