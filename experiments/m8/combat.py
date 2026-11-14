"""Fights on the M8 kernel: the scenarios of M7 section 5.9, with policies that only choose actions.

Every champion number is a placeholder: five profiles, each with one damage rate and one lockdown. The numbers show
what the kernel does with them. They say nothing about who should win a fight.

  retreat     A top laner fights the enemy top laner and walks to its fountain once it is below half health. The
              chaser never gives up. Sweep of the runner's speed edge, the lockdown, and the distance to the runner's
              own outer tower (18 cases). The speed edge is the second boot step, which adds 20.
  reinforce   A level 1 top laner fights a level 7 one alone, midway between the outer towers. Its jungler walks in
              from d units behind it. From far enough the jungler meets the enemy under the blue outer tower.
  duel        A level 1 defender against a level 2 attacker, in open lane and under the defender's outer tower.
  gank        The enemy jungler leaves the river toward a top laner, which walks to its fountain at its first
              decision after its team sees the jungler. The enemy laner joins once its jungler is within 1,500
              units of the target. Each case runs twice, once with a jungler that chases anywhere and once with
              one that stays out of the range of a standing enemy tower with no minion of its own in it
              (`harness.brawler` with its side).

Each scenario stages its champions by hand before the first tick: places, levels, boot steps, health, and mana.
After that only the policies act. Nobody sees an enemy before the first tick has run, so the first orders fall
on the second decision. A time is the game time after the tick in which the event fell.

Run: python -m experiments.m8.combat
"""

import json
from pathlib import Path

from experiments.m8.provenance import stamp
from riftgame.champions import (ACTIONS, FOUNTAIN, KEEP, LEVEL_XP, PROFILES, RIFT, ROLES, SEATS, Action, Income, Kind, capability_of,
                                spent)
from riftgame.combat import Kill
from riftgame.harness import Policy, brawler
from riftgame.lanes import RULESET_ID, TowerShot
from riftgame.vision import Observation, legal_mask, observe
from riftgame.world import Config, World

RESULTS = Path(__file__).parent / "results" / "combat.json"
SEED = 0
BLUE_TOP, BLUE_JUNGLE, RED_TOP, RED_JUNGLE = 0, 1, 5, 6
TOP, JUNGLE = ROLES.index("top"), ROLES.index("jungle")
FIGHT_TOP = ACTIONS.index(Action(Kind.FIGHT, TOP))
TO_FOUNTAIN = ACTIONS.index(Action(Kind.MOVE, "own_fountain"))
JOIN_WITHIN = 1500.0
DECISION_S = {"1 s": 1.0, "2 s": 2.0, "5 s": 5.0}


def equip(world: World, seat: int, level: int = 1, boots: int = 1, health: float = 1.0, mana: bool = True) -> None:
    """Give a champion a level, a number of boot steps with a ledger that agrees, a share of its health, and its
    mana or none."""
    c = world.champions[seat]
    c.xp, c.upgrades, c.gold = (float(LEVEL_XP[level - 2]) if level > 1 else 0.0), boots, 0.0
    c.earned = [spent(c) if source is Income.STARTING else 0.0 for source in Income]
    can = capability_of(c)
    c.hp, c.mana = health * can.max_hp, can.max_mana if mana else 0.0


def tower_s(world: World, team: int) -> float:
    return world.lanes["top"].towers[team][0].s


def dead(world: World, seat: int) -> bool:
    return world.champions[seat].respawn_tick >= 0


def play(world: World, policies: dict[int, Policy], done, limit_s: float, watch=lambda world: None) -> float:
    """Run until `done(world)` or the time limit, with one policy per acting seat. Returns the game time."""
    tick_s = world.config.tick_s
    while world.tick * tick_s < limit_s and not done(world):
        actions = None
        if world.tick % world.config.decision_ticks == 0:
            actions = [KEEP] * len(SEATS)
            for seat, policy in policies.items():
                o = observe(world, seat)
                actions[seat] = policy(o, 0.0)
                if not legal_mask(o)[actions[seat]]:
                    raise RuntimeError(f"seat {seat} chose {ACTIONS[actions[seat]]}, which its mask forbids")
        world.step(actions)
        watch(world)
    return world.tick * tick_s


def retreat(edge: float, lockdown: bool, safety: float) -> dict:
    world = World(Config(), SEED)
    home = tower_s(world, 0)
    for seat, s in ((BLUE_TOP, home + safety), (RED_TOP, home + safety + 100.0)):
        world.champions[seat].pos = RIFT.lane_pos("top", s)
    equip(world, BLUE_TOP, boots=2 if edge > 0 else 1, mana=lockdown)
    equip(world, RED_TOP, boots=2 if edge < 0 else 1, mana=lockdown)
    runner = world.champions[BLUE_TOP]
    seen = {"lowest": runner.hp, "shots": 0}

    def watch(world: World) -> None:
        seen["lowest"] = min(seen["lowest"], runner.hp)
        seen["shots"] += sum(type(e) is TowerShot and e.seat == RED_TOP for _, e in world.events)

    seconds = play(world, {BLUE_TOP: brawler(0.5), RED_TOP: brawler()},
                   lambda world: dead(world, BLUE_TOP) or dead(world, RED_TOP) or runner.pos == FOUNTAIN[0], 120.0, watch)
    outcome = "death" if dead(world, BLUE_TOP) else "escape" if dead(world, RED_TOP) or runner.pos == FOUNTAIN[0] else "undecided"
    return {"runner_speed_edge": capability_of(runner).move_speed - capability_of(world.champions[RED_TOP]).move_speed,
            "lockdown": lockdown, "units_to_own_tower": safety, "outcome": outcome, "runner_lowest_hp": round(max(seen["lowest"], 0.0)),
            "chaser_dead": dead(world, RED_TOP), "tower_shots_on_chaser": seen["shots"], "seconds": seconds}


def reinforce(d: float | None) -> dict:
    world = World(Config(), SEED)
    spot = (tower_s(world, 0) + tower_s(world, 1)) / 2
    places = {BLUE_TOP: spot, RED_TOP: spot + 100.0} | ({} if d is None else {BLUE_JUNGLE: spot - d})
    for seat, s in places.items():
        world.champions[seat].pos = RIFT.lane_pos("top", s)
    equip(world, RED_TOP, level=7)
    policies = {seat: brawler() for seat in places}
    kills: list[Kill] = []
    shots: list[TowerShot] = []

    def watch(world: World) -> None:
        kills.extend(e for _, e in world.events if type(e) is Kill)
        shots.extend(e for _, e in world.events if type(e) is TowerShot and e.seat == RED_TOP)

    seconds = play(world, policies, lambda world: dead(world, RED_TOP) or (dead(world, BLUE_TOP) and (d is None or dead(world, BLUE_JUNGLE))),
                   180.0, watch)
    died = {kill.victim: kill.t for kill in kills}
    return {"ally_start_units": d, "foe_dead": RED_TOP in died, "a_dead": BLUE_TOP in died, "ally_dead": BLUE_JUNGLE in died,
            "foe_hp_left": round(world.champions[RED_TOP].hp), "tower_shots_on_foe": len(shots), "seconds": seconds}


def duel(under_tower: bool) -> dict:
    world = World(Config(), SEED)
    s = tower_s(world, 0) + (0.0 if under_tower else 2400.0)
    for seat, at in ((BLUE_TOP, s), (RED_TOP, s + 100.0)):
        world.champions[seat].pos = RIFT.lane_pos("top", at)
    equip(world, RED_TOP, level=2)
    shots = []
    seconds = play(world, {BLUE_TOP: brawler(), RED_TOP: brawler()}, lambda world: dead(world, BLUE_TOP) or dead(world, RED_TOP), 120.0,
                   lambda world: shots.extend(e.damage for _, e in world.events if type(e) is TowerShot and e.seat == RED_TOP))
    winner = "attacker" if dead(world, BLUE_TOP) else "defender" if dead(world, RED_TOP) else "undecided"
    return {"under_defender_tower": under_tower, "winner": winner, "attacker_hp": round(world.champions[RED_TOP].hp),
            "defender_hp": round(world.champions[BLUE_TOP].hp), "tower_shots_on_attacker": len(shots),
            "tower_damage_on_attacker": round(sum(shots)), "seconds": seconds}


def wary(o: Observation, noise: float) -> int:
    """Walks to its fountain once its team sees the enemy jungler."""
    if o.enemies[JUNGLE] is None or o.me.hp <= 0:
        return KEEP
    return KEEP if o.me.intent == TO_FOUNTAIN else TO_FOUNTAIN


def second(o: Observation, noise: float) -> int:
    """Fights the enemy top laner once its own jungler is on its lane within 1,500 units of that laner."""
    target, jungler = o.enemies[TOP], next(mate for mate in o.mates if mate.role == JUNGLE)
    near = target is not None and jungler.place.route == target.place.route and abs(jungler.place.s - target.place.s) <= JOIN_WITHIN
    if near and legal_mask(o)[FIGHT_TOP] and o.me.intent != FIGHT_TOP:
        return FIGHT_TOP
    return KEEP


def gank(at_own_tower: bool, decision: str, health: float, avoids_towers: bool) -> dict:
    world = World(Config(decision_ticks=round(DECISION_S[decision] / Config().tick_s)), SEED)
    jungler = brawler(side=1, decision_s=DECISION_S[decision]) if avoids_towers else brawler()
    s = tower_s(world, 0) + 600.0 if at_own_tower else tower_s(world, 1) - 900.0
    world.champions[BLUE_TOP].pos, world.champions[RED_TOP].pos = RIFT.lane_pos("top", s), RIFT.lane_pos("top", s + 1000.0)
    world.champions[RED_JUNGLE].pos = RIFT.at("top_river")
    equip(world, BLUE_TOP, health=health)
    laner = world.champions[BLUE_TOP]
    seen = {"first": None, "lowest": laner.hp}

    def watch(world: World) -> None:
        seen["lowest"] = min(seen["lowest"], laner.hp)
        if seen["first"] is None and observe(world, BLUE_TOP).enemies[JUNGLE] is not None:
            seen["first"] = world.tick * world.config.tick_s

    seconds = play(world, {BLUE_TOP: wary, RED_TOP: second, RED_JUNGLE: jungler},
                   lambda world: dead(world, BLUE_TOP) or dead(world, RED_JUNGLE) or laner.pos == FOUNTAIN[0], 120.0, watch)
    return {"laner_at": "own outer tower" if at_own_tower else "enemy outer tower", "decision_interval": decision,
            "jungler_avoids_towers": avoids_towers, "laner_start_hp": round(capability_of(laner).max_hp * health), "jungler_first_seen_s": seen["first"],
            "laner_survives": not dead(world, BLUE_TOP), "laner_lowest_hp": round(max(seen["lowest"], 0.0)),
            "jungler_survives": not dead(world, RED_JUNGLE), "seconds": seconds}


def main() -> None:
    sweep = [retreat(edge, lockdown, safety) for safety in (1000.0, 2500.0, 4000.0) for lockdown in (False, True) for edge in (-20.0, 0.0, 20.0)]
    walk_in = [reinforce(float(d)) for d in range(0, 8001, 250)]
    wins = [row["ally_start_units"] for row in walk_in if row["foe_dead"] and not (row["a_dead"] and row["ally_dead"])]
    saves = [row["ally_start_units"] for row in walk_in if row["foe_dead"] and not row["a_dead"]]
    ganks = [gank(own, decision, health, avoids) for avoids in (False, True) for health in (1.0, 0.6) for own in (True, False) for decision in DECISION_S]
    fields = ("champion_dps", "attack_range", "move_speed", "max_hp", "lockdown_slow", "lockdown_s", "lockdown_cooldown_s", "lockdown_mana")
    results = {
        "ruleset": RULESET_ID, "config": f"tick {Config().tick_s:g} s, a decision every {Config().tick_s * Config().decision_ticks:g} s, except where a gank row names its interval",
        "placeholder_profiles": {role: {name: getattr(PROFILES[role], name) for name in fields} for role in ROLES},
        "retreat_at_half_health": {"cases": sweep, "escapes": sum(row["outcome"] == "escape" for row in sweep),
                                   "deaths": sum(row["outcome"] == "death" for row in sweep),
                                   "undecided": sum(row["outcome"] == "undecided" for row in sweep),
                                   "escapes_in_which_the_chaser_died": sum(row["outcome"] == "escape" and row["chaser_dead"] for row in sweep)},
        "reinforcement": {"alone": reinforce(None), "cases": walk_in, "largest_ally_distance_side_wins": max(wins, default=None),
                          "largest_ally_distance_a_survives": max(saves, default=None),
                          "outcome_is_monotone_in_distance": wins == [float(d) for d in range(0, 250 * len(wins), 250)]},
        "duel": [duel(False), duel(True)],
        "gank": ganks,
        "run": stamp([SEED], {"tick_s": Config().tick_s, "retreat_below": 0.5, "join_within": JOIN_WITHIN}),
    }
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps(results, indent=1), encoding="utf-8")
    block = results["retreat_at_half_health"]
    print(f"retreat: {block['escapes']} escapes, {block['deaths']} deaths, {block['undecided']} undecided, chaser dead in {block['escapes_in_which_the_chaser_died']} escapes")
    for row in sweep:
        print(f"  to own tower {row['units_to_own_tower']:>6.0f}  lockdown {row['lockdown']!s:<5}  speed edge {row['runner_speed_edge']:>+4.0f}  {row['outcome']:<9}"
              f"  runner lowest hp {row['runner_lowest_hp']:>4}  chaser dead {row['chaser_dead']!s:<5}  tower shots on chaser {row['tower_shots_on_chaser']:>2}  {row['seconds']:>5.1f} s")
    block = results["reinforcement"]
    print(f"reinforce: alone {block['alone']}")
    print(f"  side wins with the ally from up to {block['largest_ally_distance_side_wins']} units, the first fighter survives from up to "
          f"{block['largest_ally_distance_a_survives']}, wins at every distance below the largest: {block['outcome_is_monotone_in_distance']}")
    for row in walk_in:
        print(f"  ally from {row['ally_start_units']:>6.0f}  foe dead {row['foe_dead']!s:<5}  a dead {row['a_dead']!s:<5}  ally dead {row['ally_dead']!s:<5}"
              f"  foe hp left {row['foe_hp_left']:>4}  tower shots on foe {row['tower_shots_on_foe']}  {row['seconds']:>5.1f} s")
    for row in results["duel"]:
        print(f"duel, under the defender's tower {row['under_defender_tower']!s:<5}: winner {row['winner']}, attacker hp {row['attacker_hp']}, defender hp {row['defender_hp']}, "
              f"{row['tower_shots_on_attacker']} tower shots for {row['tower_damage_on_attacker']}, {row['seconds']} s")
    for row in ganks:
        print(f"gank, jungler avoids towers {row['jungler_avoids_towers']!s:<5}  laner at {row['laner_at']:<18} hp {row['laner_start_hp']:>3}  decision {row['decision_interval']}  jungler first seen {row['jungler_first_seen_s']} s"
              f"  laner survives {row['laner_survives']!s:<5} lowest hp {row['laner_lowest_hp']:>3}  jungler survives {row['jungler_survives']!s:<5}  {row['seconds']:>5.1f} s")
    print(f"wrote {RESULTS}")


if __name__ == "__main__":
    main()
