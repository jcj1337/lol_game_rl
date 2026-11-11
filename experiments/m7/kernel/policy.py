"""One scripted policy, enough for a plausible game. It reads the Observation and public tables only."""

from riftgame.rng import Stream, keyed_uniform

from experiments.m7.kernel.lanes import TEAMS
from experiments.m7.kernel.observe import Observation
from experiments.m7.kernel.profiles import ASSUMPTIONS, ROLE_LANE, ROLES, next_cost
from experiments.m7.kernel.world import CAMPS, FOUNTAIN, HOLD, MAP, RECALL, RIFT, F, Intent, Kind

OUTER_S = {(t.team, t.lane): t.s for t in MAP.towers if t.tier == "outer"}
WARD_SPOT = RIFT.at("bot_river")
LOW_HP, HEALED, TRADE_REACH, TRADE_CHANCE, GANK_REACH, GANK_HP = 0.35, 0.9, 900.0, 0.04, 3000.0, 0.6


def scripted(o: Observation) -> Intent:
    me = o.me
    team, role = me.id // 5, ROLES[me.id % 5]
    side = TEAMS[team]
    health = me.hp / me.max_hp
    at_base = RIFT.distance(me.pos, FOUNTAIN[team]) <= F["regen_radius"]
    if at_base and health < HEALED:
        return HOLD
    wants_base = not at_base and (health < LOW_HP or me.gold >= next_cost(role, me.upgrades))

    if role == "jungle":
        if wants_base:
            leashed = any(visible and alive and RIFT.distance(me.pos, CAMPS[name].pos) <= ASSUMPTIONS["camp_leash"]
                          for name, visible, alive, _, _ in o.camps)
            return Intent(Kind.MOVE, RIFT.at(f"{side}_base")) if leashed else RECALL
        prey = [e for e in o.enemies if e is not None and e.visible and e.id % 5 != 1
                and e.hp < GANK_HP * e.max_hp and RIFT.distance(me.pos, e.pos) < GANK_REACH]
        if prey:
            return Intent(Kind.FIGHT, min(prey, key=lambda e: e.hp).id)

        def start_s(camp) -> float:
            name, _, alive, age_s, respawn_s = camp
            up_at = 0.0 if alive else respawn_s if respawn_s is not None else o.time - age_s + CAMPS[name].respawn_s
            return max(up_at, o.time + RIFT.distance(me.pos, CAMPS[name].pos) / me.speed)

        return Intent(Kind.CAMP, min((c for c in o.camps if c[0].startswith((side, "scuttle"))), key=start_s)[0])

    lane = ROLE_LANE[role]
    foe = o.enemies[me.id % 5]
    if foe is not None and foe.visible and RIFT.distance(me.pos, foe.pos) < TRADE_REACH:
        foe_health = foe.hp / foe.max_hp
        if health < LOW_HP or health < foe_health - 0.2:
            return Intent(Kind.MOVE, RIFT.at(f"{side}_{lane}_t2"))
        hit = health < 1.0 or me.intent.kind == Kind.FIGHT
        if hit or keyed_uniform(0, Stream.POLICY, me.id, int(o.time)) < TRADE_CHANCE:
            return Intent(Kind.FIGHT, foe.id)
    foe_front = o.fronts[lane][1]
    pressed = foe_front >= 0 and abs(foe_front - OUTER_S[side, lane]) < 1200
    if wants_base and (health < LOW_HP or not pressed):
        return RECALL
    if role == "support" and me.wards > 0 and WARD_SPOT not in o.wards:
        return Intent(Kind.WARD, WARD_SPOT)
    return Intent(Kind.FARM, (lane, "last_hit"))
