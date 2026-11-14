"""Measurements of the jungle and the scripted jungler.

Every champion number is a placeholder, and so is every camp's damage. The numbers show what the kernel does with
them. They say nothing about what a jungler should do.

  first_clear  A scripted game from 0:00. For each jungler: the first six camps it kills with the time of each kill,
               its level, gold, XP, and health at the sixth, and when its own six camps had all died once.
  sweep        From 3:00, with the blue jungler alone acting: from each start position and in each camp state, the
               time to reach and to finish each destination, the gold and XP it pays, and the destination that
               the scripted jungler picks. The jungler has killed no camp before, so the XP of a destination
               includes the jungle item's bonus for a camp and for the first camp. XP from lane minions that
               die near the jungler on its way is counted apart.

The sweep stages its camp states by hand. It sets the camps, and it writes the blue team's memory as if the team
had seen every clear. A time is the start of the tick in which the event falls.

Run: python -m experiments.m8.jungle
"""

import json
from pathlib import Path

from experiments.m8.provenance import stamp
from riftgame.champions import ACTIONS, CAMP_NODES, CAMP_SITES, FOUNTAIN, KEEP, ROLES, TEAMS, Income, Outcome, capability_of, level_of
from riftgame.harness import approach, jungler, scripted, tick
from riftgame.jungle import SCUTTLERS, SITES, CampDeath
from riftgame.lanes import RULESET_ID
from riftgame.map import Pos
from riftgame.vision import observe
from riftgame.world import Config, Snapshot, World

RESULTS = Path(__file__).parent / "results" / "jungle.json"
SEEDS = (0, 1, 2)
CLEAR_HORIZON_S = 600.0
SWEEP_AT_S, SWEEP_HORIZON_S = 180.0, 420.0
JUNGLER = ROLES.index("jungle")
STARTS = ["own_fountain", *(node for node in CAMP_NODES if node.startswith("own_")), "top_river", "bot_river"]
# By name: the camps that are dead at the start of the sweep. The far camp is the enemy Gromp.
STATES = {
    "all up": [],
    "own blue-buff side cleared": ["own_gromp", "own_blue", "own_wolves"],
    "everything cleared except the enemy gromp": [node for node in CAMP_NODES if node != "enemy_gromp"],
}


def first_clear(seed: int) -> dict:
    world = World(Config(), seed)
    deaths, kills, after_six = [], ([], []), {}
    for _ in range(round(CLEAR_HORIZON_S / world.config.tick_s)):
        tick(world, scripted)
        for _, e in world.events:
            if type(e) is not CampDeath:
                continue
            deaths.append(e)
            killer = world.champions[e.killer]
            if killer.role != JUNGLER or len(kills[killer.team]) == 6:
                continue
            kills[killer.team].append({"camp": CAMP_SITES[e.camp], "t_s": e.t, "hp_after": killer.hp})
            if len(kills[killer.team]) == 6:
                after_six[killer.team] = {"first_clear_s": e.t, "level": level_of(killer.xp), "xp": killer.xp, "gold": killer.gold,
                                          "camp_gold": killer.earned[Income.CAMP], "hp": killer.hp, "max_hp": capability_of(killer).max_hp}
    out = {}
    for team in range(2):
        first_death = {e.camp: e.t for e in reversed(deaths) if CAMP_SITES[e.camp].startswith(TEAMS[team])}
        out[TEAMS[team]] = {**after_six.get(team, {"first_clear_s": None}), "route": kills[team],
                            "own_six_camps_all_dead_once_s": max(first_death.values()) if len(first_death) == 6 else None}
    return out


def staged(dead: list[str]) -> Snapshot:
    """A world at the start of the sweep in which nobody has acted, with the named camps cleared on this tick."""
    world = World(Config(), 0)
    while world.tick * world.config.tick_s < SWEEP_AT_S:
        world.step()
    for node in dead:
        # Blue's camp names are in the order of the world's camps.
        camp, kind = world.camps[CAMP_NODES.index(node)], SITES[CAMP_NODES.index(node)].kind
        camp.hp, camp.engaged = 0.0, -1
        camp.spawn_tick = -1 if kind.scuttler else world.tick + world.config.ticks(kind.respawn_s)
    if not any(world.camps[i].hp > 0 for i in SCUTTLERS):
        # The game draws the river node of the next Scuttler. The sweep puts it on the top node.
        world.camps[SCUTTLERS[0]].spawn_tick = world.tick + world.config.ticks(SITES[SCUTTLERS[0]].kind.respawn_s)
    for camp, known in zip(world.camps, world.memory[0].camps):
        if camp.hp <= 0:
            known.hp, known.level, known.seen_tick, known.spawn_tick = 0.0, 0, world.tick, camp.spawn_tick
    return world.snapshot()


def start_pos(start: str) -> Pos:
    return FOUNTAIN[0] if start == "own_fountain" else SITES[CAMP_NODES.index(start)].pos


def run_to(snapshot: Snapshot, start: str, k: int) -> dict:
    """Send the blue jungler from a start position to camp `k` of its observation, and time the walk and the clear."""
    world = World.restore(snapshot)
    config, me = world.config, world.champions[JUNGLER]
    me.pos = start_pos(start)
    began = world.tick
    row = {"reach_s": None, "finish_s": None, "gold": 0.0, "xp": 0.0, "lane_xp_on_the_way": 0.0, "hp_left": None}
    while (world.tick - began) * config.tick_s < SWEEP_HORIZON_S and me.hp > 0:
        actions = None
        if world.tick % config.decision_ticks == 0:
            actions = [KEEP] * 10
            actions[JUNGLER] = approach(observe(world, JUNGLER), k)
        xp = me.xp
        world.step(actions)
        since = (world.tick - 1 - began) * config.tick_s
        if row["reach_s"] is None and me.pos == SITES[k].pos:
            row["reach_s"] = since
        if me.outcome is Outcome.CLEARED:
            return row | {"finish_s": since, "gold": me.earned[Income.CAMP], "xp": me.xp - xp, "lane_xp_on_the_way": xp, "hp_left": me.hp}
    return row


def sweep() -> dict:
    out = {}
    for state, dead in STATES.items():
        snapshot = staged(dead)
        out[state] = {}
        for start in STARTS:
            world = World.restore(snapshot)
            world.champions[JUNGLER].pos = start_pos(start)
            choice = ACTIONS[jungler(observe(world, JUNGLER), 0.0)]
            rows = {node: run_to(snapshot, start, k) for k, node in enumerate(CAMP_NODES)}
            rate = {node: (row["gold"] + row["xp"]) / row["finish_s"] for node, row in rows.items() if row["finish_s"]}
            out[state][start] = {"scripted_jungler_picks": f"{choice.kind.name} {choice.target}",
                                 "most_gold_plus_xp_per_second": max(rate, key=rate.get) if rate else None, "destinations": rows}
    return out


def rounded(value):
    if isinstance(value, float):
        return round(value, 3)
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [rounded(item) for item in value]
    return value


def main() -> None:
    results = {"ruleset": RULESET_ID, "config": f"tick {Config().tick_s:g} s, a decision every {Config().tick_s * Config().decision_ticks:g} s", "first_clear": {f"seed {seed}": first_clear(seed) for seed in SEEDS},
               "sweep": {"at_s": SWEEP_AT_S, "horizon_s": SWEEP_HORIZON_S, "team": "blue", "states": sweep()}}
    results["run"] = stamp(SEEDS, {"clear_horizon_s": CLEAR_HORIZON_S, "sweep_at_s": SWEEP_AT_S, "sweep_horizon_s": SWEEP_HORIZON_S})
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps(rounded(results), indent=1), encoding="utf-8")
    for seed, teams in results["first_clear"].items():
        for team, row in teams.items():
            route = ", ".join(f"{kill['camp']} {kill['t_s']:.1f}" for kill in row["route"])
            print(f"first clear, {seed}, {team}: {rounded({key: value for key, value in row.items() if key != 'route'})}\n    {route}")
    for state, starts in results["sweep"]["states"].items():
        print(f"sweep, {state}")
        for start, row in starts.items():
            best = row["most_gold_plus_xp_per_second"]
            took = row["destinations"][best] if best else None
            print(f"    from {start:<12} picks {row['scripted_jungler_picks']:<18} best measured: {best}"
                  + (f", reached at {took['reach_s']:.1f} s, finished at {took['finish_s']:.1f} s, gold {took['gold']:.0f}, XP {took['xp']:.0f}" if took else ""))
    print(f"wrote {RESULTS}")


if __name__ == "__main__":
    main()
