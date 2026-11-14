"""Checkpoint C7: integrated games of all ten seats (M7 section 10.1).

  soak       Scripted games of 20 game minutes for 50 seeds with the invariant checker on. A referee checks the
             event log against the ruleset: every wave spawn, camp spawn, camp respawn, and champion respawn on
             its tick, no minion past a living enemy tower, and tower shots on a champion that hits an enemy
             champion under the enemy's tower. It also counts what the policies did.
  baseline   The scripted team against a team of random legal actions, gold plus XP at 15:00, 50 seeds with the
             scripted team on blue and 50 with it on red.
  towers     For every outer tower that falls in a soak or baseline game: the attacking wave's furthest advance in
             that lane in the 120 s before the fall and the 120 s after.
  replays    Three replays and their digests, which `tests/test_integrated.py` pins.
  sweep      Scripted outcomes at ticks of 0.125, 0.25, 0.5, and 1.0 s with a decision every 2 s, and at
             decisions every 1, 2, and 5 s at the research tick of `Config()`, 20 seeds, per seed and paired.

The referee reads the world, which no policy does. Its expected ticks come from the ruleset's numbers, not from
the functions of `riftgame` that schedule the events.

Run: python -m experiments.m8.integrated [section ...]
"""

import json
import math
import statistics
import sys
import time
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

from experiments.m8.provenance import stamp
from riftgame.champions import ACTIONS, FOUNTAIN, HOME, LANES, ROLES, TEAMS, Income, Kind, Outcome, level_of
from riftgame.combat import CALL_S, Hit, Kill
from riftgame.harness import random_legal, record, rerun, tick
from riftgame.jungle import SITES, CampDeath, CampSpawn
from riftgame.lanes import RULESET_ID, SWITCH_RANGE, TIERS, TOWER_ATTACK_SPEED, TOWER_RANGE, MinionDeath, TowerDestroyed, TowerShot
from riftgame.map import load_map
from riftgame.policies import DANGER_RADIUS, Side, policy, team_policies
from riftgame.ruleset import load, scheduled
from riftgame.vision import observe_team
from riftgame.world import Config, InvariantError, World

RESULTS = Path(__file__).parent / "results" / "integrated.json"
R = load()
MINIONS, DEATH, SCUTTLER = R["minions"], R["death"], R["scuttler"]
RIFT = load_map(load("patch_26_22_m8")["map"]["id"]).rift
SEEDS = range(50)
SWEEP_SEEDS = range(20)
GAME_S, BASELINE_S, ADVANCE_WINDOW_S = 1200.0, 900.0, 120.0
WORKERS = 8
TICKS = (0.125, 0.25, 0.5, 1.0)
DECISIONS = (1.0, 2.0, 5.0)


def random_side(team: int):
    return random_legal


def wave_times(until_s: float) -> list[float]:
    times, t = [], float(MINIONS["first_spawn_s"])
    while t < until_s:
        times.append(t)
        t += scheduled(MINIONS["interval_schedule"], t)
    return times


def respawn_wait_s(level: int, at_s: float) -> float:
    scaling = DEATH["time_scaling_per_30s"] * (max(0.0, at_s - DEATH["time_scaling_start_s"]) // 30)
    return DEATH["respawn_s"][level - 1] * (1.0 + scaling)


class Referee:
    """Watches a world after every tick and checks the C7 rules against it. `faults` lists every breach."""

    def __init__(self, world: World, sides: tuple[Side | None, Side | None]):
        self.world, self.sides = world, sides
        self.dt = world.config.tick_s
        self.waves = wave_times(3600.0)
        self.stretch: dict[tuple[str, int, int], tuple[int, bool]] = {}
        self.levels = [level_of(c.xp) for c in world.champions]
        self.faults: list[str] = []
        self.checked = Counter()
        self.work = Counter()
        self.seen_minions = {name: set() for name in LANES}
        self.waves_seen = {(name, team): set() for name in LANES for team in range(2)}
        self.dead_since: dict[int, tuple[int, int]] = {}
        self.camp_death: dict[int, int] = {}
        self.camp_spawn: dict[int, int] = {}
        self.scuttler_deaths: list[int] = []
        self.hits: list[tuple[int, Hit]] = []
        self.advance = {(name, team): [] for name in LANES for team in range(2)}
        self.falls: list[tuple[str, int, int, float]] = []

    def fault(self, text: str) -> None:
        if len(self.faults) < 50:
            self.faults.append(f"tick {self.world.tick - 1}: {text}")
        self.checked["faults"] += 1

    def decided(self, observations, actions) -> None:
        """Count the new orders of a decision tick: an action that is neither KEEP nor the intent already running.
        For a scripted side, also the laners' retreats while an enemy other than their lane opponent is in view
        near them, and the junglers' fights against laners."""
        for team, side in enumerate(self.sides):
            for o, action in zip(observations[team * 5:team * 5 + 5], actions[team * 5:team * 5 + 5]):
                a = ACTIONS[action]
                if a.kind is Kind.KEEP or action == o.me.intent:
                    continue
                self.work[f"chose {a.kind.name}"] += 1
                if side is None or o.me.hp <= 0:
                    continue
                lane = HOME[o.me.role]
                if lane is None:
                    self.work["gank orders"] += a.kind is Kind.FIGHT and a.target != o.me.role
                    continue
                others = [role for role, enemy in enumerate(o.enemies) if enemy is not None and role != o.me.role
                          and side.apart(o.me.place, enemy.place) <= DANGER_RADIUS]
                if others and a.kind is Kind.MOVE and (a.target.startswith(f"own_{lane}_t") or a.target == "own_base"):
                    self.work["retreats on a sighting"] += 1

    def after(self) -> None:
        world, dt = self.world, self.dt
        tick = world.tick - 1
        t0 = tick * dt
        for name in LANES:
            sim = world.lanes[name]
            for team in range(2):
                for m in sim.minions[team]:
                    if m.uid in self.seen_minions[name]:
                        continue
                    self.seen_minions[name].add(m.uid)
                    self.checked["wave spawns"] += 1
                    n = m.wave
                    self.waves_seen[name, team].add(n)
                    offset = (m.born - self.waves[n - 1]) / MINIONS["spawn_stagger_s"] if 0 < n <= len(self.waves) else -1
                    if not (abs(offset - round(offset)) < 1e-6 and 0 <= round(offset) <= 6):
                        self.fault(f"minion {m.uid} of wave {n} in {name} born at {m.born}")
                    if math.floor(m.born / dt + 1e-9) != tick:
                        self.fault(f"minion {m.uid} born at {m.born} appeared on tick {tick}")
                tower = sim.front_tower(1 - team)
                heading = sim.geometry.direction(team)
                furthest = max((heading * m.s for m in sim.minions[team]), default=None)
                if furthest is not None:
                    self.advance[name, team].append((t0, furthest * heading))
                if tower is not None:
                    self.checked["minion places under a standing tower"] += len(sim.minions[team])
                    for m in sim.minions[team]:
                        if heading * (m.s - tower.s) > 1e-6:
                            self.fault(f"minion {m.uid} of team {team} at {m.s:.1f} is past the standing tower at {tower.s:.1f} in {name}")
        shots = []
        for lane, e in world.events:
            if type(e) is CampSpawn:
                self.camp_spawned(e.camp, tick)
            elif type(e) is CampDeath:
                self.camp_death[e.camp] = tick
                if SITES[e.camp].kind.scuttler:
                    self.scuttler_deaths.append(tick)
                self.work["camp clears"] += 1
            elif type(e) is Kill:
                victim = world.champions[e.victim]
                self.dead_since[e.victim] = (tick, self.levels[e.victim])
                self.work["kills" if e.killer is not None else "executions"] += 1
                self.work[f"deaths of {TEAMS[victim.team]}"] += 1
            elif type(e) is Hit:
                self.hits.append((tick, e))
            elif type(e) is TowerShot:
                shots.append((lane, e))
            elif type(e) is TowerDestroyed:
                self.work["towers destroyed"] += 1
                if e.tier == 0:
                    self.falls.append((lane, e.team, tick, e.t))
            elif type(e) is MinionDeath and e.killer is not None:
                self.work["minions killed by champions"] += 1
        self.towers(tick, shots)
        for seat, (died, level) in list(self.dead_since.items()):
            c = world.champions[seat]
            if c.hp > 0:
                due = died + math.ceil(respawn_wait_s(level, died * dt) / dt - 1e-9)
                self.checked["champion respawns"] += 1
                if tick != due or c.pos != FOUNTAIN[c.team]:
                    self.fault(f"seat {seat} died on tick {died} at level {level} and came back on tick {tick}, due {due}")
                del self.dead_since[seat]
        for c in world.champions:
            if c.outcome_tick == tick:
                self.work[f"ended {c.outcome.name}"] += 1
        self.hits = [entry for entry in self.hits if tick - entry[0] <= world.config.ticks(CALL_S)]
        self.levels = [level_of(c.xp) for c in world.champions]

    def camp_spawned(self, camp: int, tick: int) -> None:
        kind = SITES[camp].kind
        self.checked["camp spawns"] += 1
        self.camp_spawn[camp] = tick
        if kind.scuttler:
            first = math.ceil(SCUTTLER["first_spawn_s"] / self.dt - 1e-9)
            due = first if not self.scuttler_deaths else (self.scuttler_deaths[-1] + math.ceil(SCUTTLER["respawn_s"] / self.dt - 1e-9))
        elif camp not in self.camp_death:
            due = math.ceil(R["camps"][kind.name]["first_spawn_s"] / self.dt - 1e-9)
        else:
            due = self.camp_death[camp] + math.ceil(R["camps"][kind.name]["respawn_s"] / self.dt - 1e-9)
        if tick != due:
            self.fault(f"camp {SITES[camp].node} spawned on tick {tick}, due {due}")

    def provokers(self, stand: dict, tower, tick: int) -> set[int]:
        """The enemy champions in range of a tower that hit, on this tick or within the call-for-help window before
        it, a champion of the tower's team that stood within its switch range (reference rows E16c, E16d). Places
        are where the lane held each champion when the towers fired, so a champion that died on the tick counts
        where it stood. A champion that the lane did not hold is in range of none of its towers."""
        def within(seat: int, limit: float) -> bool:
            return seat in stand and math.hypot(stand[seat][0] - tower.x, stand[seat][1] - tower.y) <= limit + 1e-6
        since = tick - self.world.config.ticks(CALL_S)
        return {hit.attacker for at, hit in self.hits
                if at >= since and hit.victim // 5 == tower.team and within(hit.victim, SWITCH_RANGE) and within(hit.attacker, TOWER_RANGE)}

    def towers(self, tick: int, shots: list[tuple[str, TowerShot]]) -> None:
        """Every shot on a champion is checked. While a tower has a provoker, a shot on a champion goes to a
        provoker, and a tower that has had one for a whole attack period and a tick has shot one. Without a
        provoker, a tower shoots a champion only in its range and only while no enemy minion is: minions do not
        move while the towers fire, so a minion alive in range after the tick was in range when it fired."""
        period = math.ceil(1.0 / TOWER_ATTACK_SPEED / self.dt - 1e-9) + 1
        for lane in LANES:
            sim = self.world.lanes[lane]
            stand = {seat: (spot.x, spot.y) for seat, spot in sim._stand.items()}
            for team, tier in ((team, tier) for team in range(2) for tier in range(len(TIERS))):
                tower = sim.towers[team][tier]
                fired = [shot.seat for name, shot in shots if name == lane and shot.team == team and shot.tier == tier]
                key = (lane, team, tier)
                provokers = self.provokers(stand, tower, tick) if tower.hp > 0 or fired else set()
                if not provokers:
                    self.stretch.pop(key, None)
                    for seat in fired:
                        self.checked["tower shots on champions with no provoker"] += 1
                        if seat not in stand or math.hypot(stand[seat][0] - tower.x, stand[seat][1] - tower.y) > TOWER_RANGE + 1e-6:
                            self.fault(f"the {TEAMS[team]} {TIERS[tier]} tower in {lane} shot seat {seat} out of its range")
                        elif sim._in_range_of(tower, 1 - team):
                            self.fault(f"the {TEAMS[team]} {TIERS[tier]} tower in {lane} shot seat {seat} with an enemy minion in range and no provoker")
                    continue
                self.checked["ticks with a provoked tower"] += 1
                for seat in fired:
                    self.checked["tower shots on champions with a provoker in range"] += 1
                    if seat not in provokers:
                        self.fault(f"the {TEAMS[team]} {TIERS[tier]} tower in {lane} shot seat {seat} with provokers {sorted(provokers)}")
                since, answered = self.stretch.get(key, (tick, False))
                if not answered and any(seat in provokers for seat in fired):
                    self.checked["provoked stretches answered by a shot"] += 1
                    answered = True
                if not answered and tick - since + 1 >= period and tower.hp > 0:
                    self.fault(f"the {TEAMS[team]} {TIERS[tier]} tower in {lane} had provokers {sorted(provokers)} from tick {since} and shot none")
                    answered = True
                self.stretch[key] = (since, answered)

    def finish(self) -> None:
        """What should have happened by the end and did not: a wave that never spawned, a camp that never came
        back, a champion that never respawned."""
        world, dt = self.world, self.dt
        last = world.tick - 1
        for name in LANES:
            for team in range(2):
                seen = self.waves_seen[name, team]
                due = {n for n, at in enumerate(self.waves, 1) if math.floor(at / dt + 1e-9) < last}
                for n in sorted(due - seen):
                    self.fault(f"wave {n} of team {team} in {name} never spawned")
        for camp, site in enumerate(SITES):
            if site.kind.scuttler:
                continue
            died = self.camp_death.get(camp)
            if died is None:
                due = math.ceil(R["camps"][site.kind.name]["first_spawn_s"] / dt - 1e-9)
                if camp not in self.camp_spawn and due < last:
                    self.fault(f"camp {site.node} never spawned, due on tick {due}")
            elif self.camp_spawn.get(camp, -1) < died:
                due = died + math.ceil(R["camps"][site.kind.name]["respawn_s"] / dt - 1e-9)
                if due < last:
                    self.fault(f"camp {site.node} died on tick {died} and never came back, due on tick {due}")
        for seat, (died, level) in self.dead_since.items():
            due = died + math.ceil(respawn_wait_s(level, died * dt) / dt - 1e-9)
            if due < last:
                self.fault(f"seat {seat} died on tick {died} and never came back, due on tick {due}")


def play(args) -> dict:
    seed, config, blue, red, seconds, check, score_s = (*args, None)[:7]
    world = World(config, seed)
    sides = (Side(0) if blue == "scripted" else None, Side(1) if red == "scripted" else None)
    policies = team_policies(blue=policy if blue == "scripted" else random_side, red=policy if red == "scripted" else random_side)
    referee = Referee(world, sides)
    ticks = round(seconds / config.tick_s)
    score_tick = None if score_s is None else round(score_s / config.tick_s)
    score = None
    began, error = time.perf_counter(), None
    try:
        for _ in range(ticks):
            deciding = world.tick % config.decision_ticks == 0
            observations = [*observe_team(world, 0), *observe_team(world, 1)] if deciding else None
            actions = tick(world, policies, check)
            if deciding:
                referee.decided(observations, actions)
            referee.after()
            if world.tick == score_tick:
                score = [sum(sum(c.earned) + c.xp for c in world.champions[team * 5:team * 5 + 5]) for team in range(2)]
    except InvariantError as e:
        error = f"tick {world.tick}: {e}"
    referee.finish()
    wall = time.perf_counter() - began
    teams = [world.champions[team * 5:team * 5 + 5] for team in range(2)]
    return {
        "seed": seed, "tick_s": config.tick_s, "decision_s": config.tick_s * config.decision_ticks, "blue": blue, "red": red,
        "ticks": world.tick, "wall_s": wall, "invariant_error": error, "faults": referee.faults, "checked": dict(referee.checked),
        "work": dict(referee.work),
        "gold_plus_xp_at_score": score,
        "gold": [sum(sum(c.earned) for c in side) for side in teams],
        "xp": [sum(c.xp for c in side) for side in teams],
        "minion_gold": [sum(c.earned[Income.MINION] for c in side) for side in teams],
        "upgrades": [c.upgrades for c in world.champions],
        "deaths": [referee.work[f"deaths of {team}"] for team in TEAMS],
        "towers_standing": [sum(tower.hp > 0 for name in LANES for tower in world.lanes[name].towers[team]) for team in range(2)],
        "tower_hp": [sum(max(0.0, tower.hp) for name in LANES for tower in world.lanes[name].towers[team]) for team in range(2)],
        "falls": [{"lane": lane, "tower_team": team, "t": t, "before": furthest(referee, lane, 1 - team, t - ADVANCE_WINDOW_S, t),
                   "after": furthest(referee, lane, 1 - team, t, t + ADVANCE_WINDOW_S), "after_window_s": min(ADVANCE_WINDOW_S, seconds - t)}
                  for lane, team, _, t in referee.falls],
    }


def furthest(referee: Referee, lane: str, team: int, lo: float, hi: float) -> float | None:
    """The attacking team's furthest advance in a lane over a window, as a distance from its own end."""
    geometry = referee.world.lanes[lane].geometry
    spots = [s for t, s in referee.advance[lane, team] if lo <= t < hi]
    if not spots:
        return None
    return max(spots) if team == 0 else geometry.length - min(spots)


def spread(values: list[float]) -> dict:
    return {"median": statistics.median(values), "min": min(values), "max": max(values), "values": values}


def games(args: list[tuple]) -> list[dict]:
    with Pool(WORKERS) as pool:
        return pool.map(play, args)


# What a scripted game must show for its policies to exercise each subsystem.
BEHAVIOURS = ("ended PLACED", "ended RECALLED", "ended CLEARED", "chose FIGHT", "ended KILLED", "retreats on a sighting", "gank orders",
              "ended LOST", "ended INTERRUPTED", "chose SIEGE")


def soak() -> dict:
    runs = games([(seed, Config(), "scripted", "scripted", GAME_S, True) for seed in SEEDS])
    checked, work = Counter(), Counter()
    for run in runs:
        checked.update(run["checked"])
        work.update(run["work"])
    return {
        "games": len(runs), "game_s": GAME_S,
        "invariant_errors": [(run["seed"], run["invariant_error"]) for run in runs if run["invariant_error"]],
        "rule_faults": [(run["seed"], fault) for run in runs for fault in run["faults"]],
        "checked": dict(checked),
        "work_total": dict(work),
        "work_per_game": {key: spread([run["work"].get(key, 0) for run in runs]) for key in sorted(work)},
        "games_missing_a_behaviour": {key: [run["seed"] for run in runs if not run["work"].get(key)] for key in BEHAVIOURS},
        "falls": [fall | {"seed": run["seed"]} for run in runs for fall in run["falls"]],
        "wall_s": spread([run["wall_s"] for run in runs]),
    }


def baseline() -> dict:
    out = {}
    for scripted_team in (0, 1):
        sides = ("scripted", "random") if scripted_team == 0 else ("random", "scripted")
        runs = games([(seed, Config(), *sides, GAME_S, True, BASELINE_S) for seed in SEEDS])
        margins = [run["gold_plus_xp_at_score"][scripted_team] - run["gold_plus_xp_at_score"][1 - scripted_team] for run in runs]
        out[f"scripted on {TEAMS[scripted_team]}"] = {
            "seeds_won": sum(margin > 0 for margin in margins), "seeds": len(runs), "margin_gold_plus_xp": spread(margins),
            "invariant_errors": [(run["seed"], run["invariant_error"]) for run in runs if run["invariant_error"]],
            "rule_faults": [(run["seed"], fault) for run in runs for fault in run["faults"]],
            "checked": dict(sum((Counter(run["checked"]) for run in runs), Counter())),
            "falls": [fall | {"seed": run["seed"]} for run in runs for fall in run["falls"]],
        }
    return out


def towers(soaked: dict, based: dict) -> dict:
    falls = soaked["falls"] + [fall for row in based.values() for fall in row["falls"]]
    rows = [fall | {"increased": fall["before"] is not None and fall["after"] is not None and fall["after"] > fall["before"]} for fall in falls]
    full = [row for row in rows if row["after_window_s"] >= ADVANCE_WINDOW_S]
    return {"window_s": ADVANCE_WINDOW_S, "falls": len(rows), "falls_with_a_full_window": len(full),
            "increased_with_a_full_window": sum(row["increased"] for row in full), "rows": rows}


REPLAYS = {"scripted teams, seed 7": (7, "scripted", "scripted"), "scripted blue, random red, seed 11": (11, "scripted", "random"),
           "random teams, seed 13": (13, "random", "random")}


def replay_policies(blue: str, red: str):
    return team_policies(blue=policy if blue == "scripted" else random_side, red=policy if red == "scripted" else random_side)


def replays() -> dict:
    out = {}
    for name, (seed, blue, red) in REPLAYS.items():
        replay, digests = record(Config(), seed, replay_policies(blue, red), round(GAME_S / Config().tick_s))
        again = rerun(replay)
        out[name] = {"ticks": len(digests), "final_digest": digests[-1], "rerun_equal_on_every_tick": again == digests,
                     "digest_every_600_ticks": digests[599::600]}
    return out


MEASURES = ("gold", "xp", "minion_gold", "tower_hp")
COUNTS = ("kills", "camp clears", "ended RECALLED", "ended PLACED", "chose FIGHT", "minions killed by champions", "retreats on a sighting", "gank orders")


def measures(run: dict) -> dict:
    row = {f"{key} {TEAMS[team]}": run[key][team] for key in MEASURES for team in range(2)}
    row.update({key: run["work"].get(key, 0) for key in COUNTS})
    return row


def compare(settings: dict[str, list[dict]], reference: str) -> dict:
    """Per measure and setting: every seed's value, its spread, and the paired difference from the reference
    setting seed by seed. `noise_iqr` is the spread across seeds at the reference, as its interquartile range."""
    out = {}
    base = [measures(run) for run in settings[reference]]
    for key in base[0]:
        ref = [row[key] for row in base]
        q = statistics.quantiles(ref, n=4)
        entry = {"noise_iqr": q[2] - q[0]}
        for name, runs in settings.items():
            values = [measures(run)[key] for run in runs]
            diffs = [v - r for v, r in zip(values, ref)]
            entry[name] = {"values": values, "median": statistics.median(values), "min": min(values), "max": max(values),
                           "paired_median": statistics.median(diffs), "paired_min": min(diffs), "paired_max": max(diffs),
                           "seeds_higher": sum(d > 0 for d in diffs), "seeds_lower": sum(d < 0 for d in diffs)}
        out[key] = entry
    return out


def sweep() -> dict:
    configs = {f"tick {t} s, decide every 2 s": Config(tick_s=t, decision_ticks=round(2.0 / t)) for t in TICKS}
    research = Config().tick_s
    configs |= {f"tick {research:g} s, decide every {d:g} s": Config(tick_s=research, decision_ticks=round(d / research)) for d in DECISIONS}
    runs = {name: games([(seed, config, "scripted", "scripted", GAME_S, False) for seed in SWEEP_SEEDS]) for name, config in configs.items()}
    ticks = {f"tick {t} s, decide every 2 s": runs[f"tick {t} s, decide every 2 s"] for t in TICKS}
    decisions = {f"tick {research:g} s, decide every {d:g} s": runs[f"tick {research:g} s, decide every {d:g} s"] for d in DECISIONS}
    return {"seeds": len(SWEEP_SEEDS), "game_s": GAME_S,
            "tick_with_decision_every_2_s": compare(ticks, "tick 0.125 s, decide every 2 s"),
            "decision_at_the_research_tick": compare(decisions, f"tick {research:g} s, decide every 2 s"),
            "wall_s_per_game": {name: statistics.median(run["wall_s"] for run in rows) for name, rows in runs.items()},
            "faults": [(name, run["seed"], fault) for name, rows in runs.items() for run in rows for fault in run["faults"]]}


def rounded(value):
    if isinstance(value, float):
        return round(value, 3)
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [rounded(item) for item in value]
    return value


def main() -> None:
    chosen = sys.argv[1:] or ["soak", "baseline", "replays", "sweep"]
    results = json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() and sys.argv[1:] else {}
    results["ruleset"] = RULESET_ID
    for name in chosen:
        began = time.perf_counter()
        results[name] = {"soak": soak, "baseline": baseline, "replays": replays, "sweep": sweep}[name]()
        print(f"{name}: {time.perf_counter() - began:.0f} s")
    if "soak" in results and "baseline" in results:
        results["towers"] = towers(results["soak"], results["baseline"])
    results["run"] = stamp(list(SEEDS), {"game_s": GAME_S, "baseline_s": BASELINE_S, "sweep_seeds": len(SWEEP_SEEDS), "sections": chosen})
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps(rounded(results), indent=1), encoding="utf-8")
    report(results)


def report(results: dict) -> None:
    if "soak" in results:
        s = results["soak"]
        print(f"soak: {s['games']} games, invariant errors {len(s['invariant_errors'])}, rule faults {len(s['rule_faults'])}")
        print("  checked:", s["checked"])
        print("  games missing a behaviour:", {k: len(v) for k, v in s["games_missing_a_behaviour"].items()})
    for name, row in results.get("baseline", {}).items():
        print(f"baseline, {name}: won {row['seeds_won']} of {row['seeds']}, margin median {row['margin_gold_plus_xp']['median']:.0f}, "
              f"errors {len(row['invariant_errors'])}, faults {len(row['rule_faults'])}")
    if "towers" in results:
        t = results["towers"]
        print(f"towers: {t['falls']} outer falls, {t['increased_with_a_full_window']} of {t['falls_with_a_full_window']} with a full window advance further")
    for name, row in results.get("replays", {}).items():
        print(f"replay {name}: {row['final_digest'][:16]} rerun equal {row['rerun_equal_on_every_tick']}")
    if "sweep" in results:
        print("sweep wall s per game:", results["sweep"]["wall_s_per_game"], "faults", len(results["sweep"]["faults"]))


if __name__ == "__main__":
    main()
