"""Holding, stacking, and bouncing through the action interface, across champion capabilities and starting states.

Each case is a full world. A plan picks `LANE` actions only (and a walk to its tower when low), from its champion's
observation, so every result is reachable by an agent. Each section answers one question.
  stacking  Over plans, starts, and champions, how large and how late is the crash, and how many waves are in it?
  holding   Does a champion on the hold line keep an enemy wave off its tower longer than no champion does?
  bounce    After a crash, does the lane come back, and when?

Two controls stand beside every plan and are different things. `absent` is a lane with no champion of that team:
the champion is on its fountain. `under tower` is a champion that stands at its own outer tower and does nothing:
it gains XP there and may be hit.

Every section runs with the plan on blue and, mirrored, with the plan on red. `between_sides` gives blue's value less
red's per seed, and `sides` the verdict counts per side and for both. The diagnostics run with the plan on blue. The
sweeps run both sides at four tick lengths with a decision every 2 s, and at three decision intervals at the research
tick of `Config()`, and `sensitivity` compares each case across the clocks of a sweep with its spread across seeds.

Run: python -m experiments.m8.waves.capabilities
Print the summary of the results file again: python -m experiments.m8.waves.capabilities --report
"""

import json
import re
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
from functools import partial
from pathlib import Path

from experiments.m8.provenance import stamp
from experiments.m8.waves import agents
from experiments.m8.waves.agents import NO_LANER, Laner, always, from_wave, hold_thin_over, hold_trim_to, seat_of, thin_then, until_crash
from experiments.m8.waves import investigate
from experiments.m8.waves.harness import BLUE, RED, Crashes, Crowding, lead_of, offset, outer, rounded, second_wave, summarize, tower_damage, under_tower
from riftgame.champions import HOME, ROLES, known_front
from riftgame.lanes import HOLD_MARGIN, M8_LANE, RULESET_ID, TOWER_RANGE, LaneRules
from riftgame.world import Config
from riftgame.lanes import Kind as Minion

SEEDS = range(5)
RESULTS = Path(__file__).parent / "results" / "capabilities.json"
PLAN_RUN_S = 240.0
HOLD_RUN_S = 240.0
BOUNCE_RUN_S = 600.0
WAVE_S = 30.0
WAVE_SHARE = 3
TWO_WAVES = 12
MID_BOUNCE_S = 120.0
RESET_WITHIN = 100.0
SUSTAINED_CYCLES = 3
LATER_WAVE = 3
WORKERS = 8

# label: (roles on the lane, level, clock at which the lanes start empty). The level goes with the clock: a laner is
# level 1 when the first waves meet, about level 3 at 2:30, and about level 6 at 6:00.
CHAMPIONS = {
    "top, level 1, from 0:00": (("top",), 1, 0.0),
    "top, level 3, from 2:30": (("top",), 3, 150.0),
    "top, level 6, from 6:00": (("top",), 6, 360.0),
    "mid, level 1, from 0:00": (("mid",), 1, 0.0),
    "mid, level 3, from 2:30": (("mid",), 3, 150.0),
    "mid, level 6, from 6:00": (("mid",), 6, 360.0),
    "carry alone, level 3, from 2:30": (("carry",), 3, 150.0),
    "carry and support, level 3, from 2:30": (("carry", "support"), 3, 150.0),
}

PUSH_PLANS = {
    "absent": lambda: (lambda seen: "leave"),
    "under tower": lambda: (lambda seen: "tower"),
    "push": lambda: always("push"),
    "last hit": lambda: always("last_hit"),
    "passive": lambda: always("passive"),
    "thin 1, then last hit": lambda: thin_then(1, "last_hit"),
    "thin 2, then last hit": lambda: thin_then(2, "last_hit"),
    "thin 3, then last hit": lambda: thin_then(3, "last_hit"),
    "thin 3, then passive": lambda: thin_then(3, "passive"),
    "thin every caster": lambda: always("thin"),
}
STACK_CONTROLS = ("push", "absent", "under tower")
STARTS = ("first contact", "own tower", "third wave")
CONTROLS = ("absent", "under tower", "last hit with the wave", "push")
HOLD_PLANS = {
    "absent": None,
    "under tower": lambda: (lambda seen: "tower"),
    "last hit with the wave": lambda: always("last_hit"),
    "push": lambda: always("push"),
    "hold, last hit": lambda: always("last_hit", "hold"),
    "hold, hit nothing": lambda: always("passive", "hold"),
    "hold, thin": lambda: always("thin", "hold"),
    "hold, thin over 1": lambda: hold_thin_over(1),
    "hold, thin over 3": lambda: hold_thin_over(3),
    "hold, trim to 4": lambda: hold_trim_to(4),
    "hold, trim to 4 by pushing": lambda: hold_trim_to(4, "push"),
}
SURPLUS = (2, 3, 4, 6)
LATER_SURPLUS = (3, 4)
PAIRED = {
    "stacking": (("push", "last hit", "absent", "under tower"), ("largest_crash_peak", "first_crash_s", "minion_gold", "xp", "enemy_tower_damage", "own_tower_damage")),
    "holding": (CONTROLS, ("held_cycles", "kept_out_s", "minion_gold", "xp", "own_tower_damage", "champion_lowest_health")),
}
SIDES = {"blue": BLUE, "red": RED}
# The metric on which a plan "beats" a control in the headline of the paired tables: a larger crash, a longer hold.
BEATS = {"stacking": ("largest_crash_peak", "first_crash_s"), "holding": ("held_cycles", "kept_out_s")}
BETWEEN_SIDES = {
    "stacking": ("largest_crash_peak", "largest_crash_second_wave", "first_crash_s", "minion_gold", "xp", "enemy_tower_damage", "own_tower_damage"),
    "holding": ("held_cycles", "kept_out_s", "minion_gold", "xp", "own_tower_damage", "champion_lowest_health", "champion_retreats"),
    "bounce": ("front_back_past_centre_s", "untouched_front_there_s", "back_sooner_than_untouched_s", "crash_s", "crash_peak"),
}


def lane_of(champion: str) -> str:
    return HOME[ROLES.index(CHAMPIONS[champion][0][0])]


def team_laners(world, champion: str, team: int, plan, retreats: bool = True) -> list[Laner]:
    """The lane's champions of one team under `plan`, placed at their outer tower. A support stands where its
    carry stands and hits nothing."""
    roles = CHAMPIONS[champion][0]
    laners = [Laner(world, seat_of(team, roles[0]), plan(), retreats)]
    if len(roles) > 1:
        carry = laners[0]

        def beside(seen, carry=carry):
            choice = carry.plan(seen)
            return choice if isinstance(choice, str) else ("passive", choice[1])

        laners.append(Laner(world, seat_of(team, roles[1]), beside, retreats))
    return laners


class Unseen:
    """How often a team does not see the enemy lead minion of a lane that has one. A plan reads only what its
    team sees, so this is the share of the run on which it knew less than the lane's true front."""

    def __init__(self, world, lane: str, team: int):
        self.world, self.lane, self.team = world, lane, team
        self.ticks = self.unseen = 0

    def watch(self) -> None:
        true = self.world.lanes[self.lane].front().lead[1 - self.team]
        if true is not None:
            self.ticks += 1
            self.unseen += known_front(self.world, self.team, self.lane).lead[1 - self.team] != true

    def share(self) -> float:
        return self.unseen / self.ticks if self.ticks else 0.0


def stacking_case(args, rules: LaneRules = M8_LANE, config: Config = Config(), team: int = BLUE) -> dict:
    """`team` plays a plan from first contact, from the moment an enemy push reaches its outer tower, or from the
    meeting of the third waves after both laners last-hit the first two."""
    return stacking_run(args, rules, config, team)[0]


def stacking_run(args, rules: LaneRules = M8_LANE, config: Config = Config(), team: int = BLUE):
    """`stacking_case` with what a probe reads beside its metrics: the lane's trace, when the plan began, and the
    largest crash."""
    champion, start, foe_last_hits, plan, seed = args
    foe = 1 - team
    roles, level, start_s = CHAMPIONS[champion]
    lane = lane_of(champion)
    world = agents.staged(seed, dict.fromkeys(roles, level), start_s, config, rules)
    sim = world.lanes[lane]
    met, began = [], []

    def opening(seen) -> bool:
        if not met and seen.contact:
            met.append(seen.time_s)
        if not began and met and seen.contact:
            if start == "first contact" or (start == "own tower" and seen.foe_at_own_tower) or (start == "third wave" and seen.time_s >= met[0] + (LATER_WAVE - 1) * WAVE_S):
                began.append(seen.time_s)
        return bool(began)

    chosen_plan = PUSH_PLANS[plan]

    def mine():
        chosen = chosen_plan()
        return lambda seen: chosen(seen) if opening(seen) else ("last_hit", "wave")

    def theirs():
        after = always("last_hit") if foe_last_hits else (lambda seen: "leave")
        before = always("push") if start == "own tower" else always("last_hit") if start == "third wave" else after
        return lambda seen: after(seen) if began else before(seen)

    laners = team_laners(world, champion, team, mine)
    present = foe_last_hits or start != "first contact"
    crashes, crowding, unseen = Crashes(sim, team), Crowding(sim), Unseen(world, lane, team)
    largest = [0]

    def stop(row) -> bool:
        if began:
            crashes.watch(row)
            crowding.watch(row)
            unseen.watch()
            largest[0] = max(largest[0], agents.crowd(sim, team, lead_of(row, team)))
        return bool(began) and row.t >= began[0] + PLAN_RUN_S

    trace = agents.play(world, lane, laners + (team_laners(world, champion, foe, theirs) if present else []), start_s + 900.0, stop)
    first, biggest = (crashes.spans[0] if crashes.spans else None), crashes.largest()
    return {
        "first_crash_s": first["start"] - began[0] if first else None,
        "first_crash_peak": first["peak"] if first else None,
        "first_crash_waves": len(first["by_wave"]) if first else None,
        "largest_crash_s": biggest["start"] - began[0] if biggest else None,
        "largest_crash_peak": biggest["peak"] if biggest else 0,
        "largest_crash_waves": len(biggest["by_wave"]) if biggest else None,
        "largest_crash_second_wave": second_wave(biggest),
        "largest_wave_anywhere": largest[0],
        "enemy_tower_damage": tower_damage(trace.events, foe, began[0]) if began else None,
        "own_tower_damage": tower_damage(trace.events, team, began[0]) if began else None,
        "casts_cancelled": sim.cancelled,
        "missiles_lost": sim.lost,
        "enemy_lead_unseen_share": unseen.share(),
        **crowding.report(),
        **laners[0].report(world),
    }, trace, (began[0] if began else None), biggest


def holding_case(args, rules: LaneRules = M8_LANE, config: Config = Config(), team: int = BLUE) -> dict:
    """The experiment places `surplus` enemy casters at the hold line when a wave of `team` reaches its own tower's
    edge: the first wave, or the third with `wave` 3.

    The run then lasts 240 s. With an enemy laner, it last-hits from the start.
    """
    champion, surplus, foe_last_hits, plan, wave, seed = args
    foe = 1 - team
    roles, level, start_s = CHAMPIONS[champion]
    lane = lane_of(champion)
    world = agents.staged(seed, dict.fromkeys(roles, level), start_s, config, rules)
    sim = world.lanes[lane]
    geometry = sim.geometry
    heading = geometry.direction(team)
    lo, hi = agents.band(geometry, team)
    edge = outer(geometry, team) + heading * TOWER_RANGE
    placed = []
    laners = team_laners(world, champion, team, HOLD_PLANS[plan]) if HOLD_PLANS[plan] else []
    foes = team_laners(world, champion, foe, lambda: always("last_hit")) if foe_last_hits else []
    peak, earliest = [0], []
    unseen = Unseen(world, lane, team)

    def stop(row) -> bool:
        if not earliest and sim.minions[team]:
            earliest.append(min(m.wave for m in sim.minions[team]))
        if not placed and any(m.wave >= earliest[0] + wave - 1 and heading * (m.s - edge) >= 0 for m in sim.minions[team]):
            sim.add_minion(foe, Minion.CASTER, edge + heading * (HOLD_MARGIN + 390.0), count=surplus)
            placed.append(row.t)
        if placed:
            peak[0] = max(peak[0], agents.crowd(sim, foe, row.line))
            unseen.watch()
        return bool(placed) and row.t >= placed[0] + HOLD_RUN_S

    trace = agents.play(world, lane, laners + foes, start_s + 900.0, stop)
    rows = [r for r in trace.rows if r.t >= placed[0]]
    inside = [r.line is not None and lo <= r.line <= hi for r in rows]
    dt = world.config.tick_s
    breached = [under_tower(geometry, team, lead_of(r, foe)) for r in rows]
    spans = [(placed[0] + WAVE_S * i, placed[0] + WAVE_S * (i + 1)) for i in range(int(HOLD_RUN_S // WAVE_S))]
    cycles = [sum(ok for r, ok in zip(rows, inside) if lo_t <= r.t < hi_t) * dt for lo_t, hi_t in spans]
    at_tower = [sum(hit for r, hit in zip(rows, breached) if lo_t <= r.t < hi_t) * dt for lo_t, hi_t in spans]
    held = [near >= WAVE_S / 2 and reached == 0 for near, reached in zip(cycles, at_tower)]
    return {
        "band_s": sum(inside) * dt,
        "cycles_mostly_in_band": sum(c >= WAVE_S / 2 for c in cycles),
        "held_cycles": next((i for i, ok in enumerate(held) if not ok), len(held)),
        "kept_out_s": next((r.t - placed[0] for r, hit in zip(rows, breached) if hit), HOLD_RUN_S),
        "under_tower_s": sum(breached) * dt,
        "own_tower_damage": tower_damage(trace.events, team),
        "pushed_out": any(lead_of(r, team) is not None and offset(geometry, lead_of(r, team), team) > 0 for r in rows),
        "largest_enemy_wave": peak[0],
        "enemy_lead_unseen_share": unseen.share(),
        **(laners[0].report(world) if laners else NO_LANER),
    }


BOUNCE_PLANS = {
    "hard push": lambda: always("push"),
    "thin 3, then last hit": lambda: thin_then(3, "last_hit"),
    "last hit two waves, then hard push": lambda: from_wave(LATER_WAVE, always("push"), always("last_hit"), WAVE_S),
}


def bounce_case(args, rules: LaneRules = M8_LANE, config: Config = Config(), team: int = BLUE) -> dict:
    """A laner of `team` follows a plan from first contact until its wave is in the enemy tower's range, then walks
    back to its fountain. Nobody else is in the lane. A lane that meets again within 100 units of the centre has
    reset. One that meets on the laner's own half has bounced. The same world with no laner at all runs beside it,
    because an untouched lane moves too."""
    champion, plan, seed = args
    roles, level, start_s = CHAMPIONS[champion]
    lane = lane_of(champion)
    world = agents.staged(seed, dict.fromkeys(roles, level), start_s, config, rules)
    geometry = world.lanes[lane].geometry
    laners = team_laners(world, champion, team, lambda: until_crash(BOUNCE_PLANS[plan]()), retreats=False)
    crashes = Crashes(world.lanes[lane], team)
    answer = Crashes(world.lanes[lane], 1 - team)

    def stop(row) -> bool:
        crashes.watch(row)
        answer.watch(row)
        return False

    trace = agents.play(world, lane, laners, start_s + BOUNCE_RUN_S, stop)
    if not crashes.spans:
        return {"crash_s": None, "crash_peak": None, "front_back_past_centre_s": None, "answer_at_own_tower_s": None, "answer_peak": None,
                "front_on_own_half_share": None, "front_at_centre_share": None, "deepest_offset": None, "untouched_front_there_s": None, "back_before_the_untouched_lane": 0,
                "back_sooner_than_untouched_s": None}
    crash = crashes.spans[0]["start"]
    later = [r for r in trace.rows if r.t > crash]
    back = next((r.t - crash for r in later if r.contact and offset(geometry, r.line, team) < -RESET_WITHIN), None)
    replies = [span for span in answer.spans if span["start"] > crash]
    contacts = [offset(geometry, r.line, team) for r in later if r.contact]
    untouched = agents.staged(seed, dict.fromkeys(roles, level), start_s, config, rules)
    drift = agents.play(untouched, lane, [], start_s + BOUNCE_RUN_S)
    there = next((r.t - crash for r in drift.rows if r.t > crash and r.contact and offset(geometry, r.line, team) < -RESET_WITHIN), None)
    return {
        "untouched_front_there_s": there,
        "back_before_the_untouched_lane": int(back is not None and (there is None or back < there)),
        "back_sooner_than_untouched_s": there - back if back is not None and there is not None else None,
        "crash_s": crash - start_s,
        "crash_peak": crashes.spans[0]["peak"],
        "front_back_past_centre_s": back,
        "answer_at_own_tower_s": replies[0]["start"] - crash if replies else None,
        "answer_peak": replies[0]["peak"] if replies else None,
        "front_on_own_half_share": sum(o < -RESET_WITHIN for o in contacts) / len(contacts) if contacts else None,
        "front_at_centre_share": sum(abs(o) <= RESET_WITHIN for o in contacts) / len(contacts) if contacts else None,
        "deepest_offset": min(contacts, default=None),
    }


def over_seeds(case, keys: list[tuple], seeds=SEEDS, workers: int = WORKERS) -> dict:
    """`case` over every key and seed: per key, the runs in the order of the seeds. The runs are independent, so
    they go to a process pool."""
    jobs = [(*key, seed) for key in keys for seed in seeds]
    if workers > 1:
        with ProcessPoolExecutor(workers) as pool:
            done = list(pool.map(case, jobs, chunksize=4))
    else:
        done = [case(job) for job in jobs]
    out = {}
    for job, metrics in zip(jobs, done):
        out.setdefault(job[:-1], []).append(metrics)
    return out


def spread(runs: list[dict]) -> dict:
    """The summary of `summarize`, and beside it every seed's value, so a reader sees the distribution."""
    summary = summarize(runs)
    for name, row in summary.items():
        del row["mean"]
        row["values"] = [m[name] for m in runs]
    return summary


def differences(left: list, right: list) -> dict:
    """`left`'s value minus `right`'s on the same seed: every seed's difference (None where either has no value),
    and the median, range, and how many are above and below zero over the seeds that have one."""
    values = [None if a is None or b is None else a - b for a, b in zip(left, right)]
    gaps = [gap for gap in values if gap is not None]
    return {"values": values, "median": statistics.median(gaps) if gaps else None, "min": min(gaps, default=None), "max": max(gaps, default=None),
            "higher": sum(gap > 0 for gap in gaps), "lower": sum(gap < 0 for gap in gaps), "n": len(gaps)}


def paired(plan: list[dict], control: list[dict], metrics: tuple[str, ...]) -> dict:
    """Per metric, the plan's value minus the control's on the same seed (`differences`)."""
    return {name: differences([m[name] for m in plan], [m[name] for m in control]) for name in metrics}


def pairs(section: str, runs: dict[str, list[dict]]) -> dict:
    controls, metrics = PAIRED[section]
    return {plan: {control: paired(rows, runs[control], metrics) for control in controls if control in runs}
            for plan, rows in runs.items() if plan not in controls}


def opponent(last_hits: bool) -> str:
    return f"opponent {'last hits' if last_hits else 'absent'}"


def stacking(champions=tuple(CHAMPIONS), starts=STARTS, reds=(False, True), plans=tuple(PUSH_PLANS), seeds=SEEDS, workers=WORKERS,
             rules: LaneRules = M8_LANE, config: Config = Config(), team: int = BLUE) -> dict:
    """The stacking section with the plan on `team`. `reds` says whether the opponent last-hits."""
    keys = [(c, start, red, plan) for c in champions for start in starts for red in reds for plan in plans]
    runs = {}
    for (c, start, red, plan), rows in over_seeds(partial(stacking_case, rules=rules, config=config, team=team), keys, seeds, workers).items():
        runs.setdefault(f"{c}, from {start}, {opponent(red)}", {})[plan] = rows
    cases = {setting: {plan: spread(rows) for plan, rows in by_plan.items()} for setting, by_plan in runs.items()}
    return {"cases": cases, "paired": {setting: pairs("stacking", by_plan) for setting, by_plan in runs.items()}, **stacking_verdict(cases)}


def stacking_verdict(cases: dict) -> dict:
    """Per setting: which plans accumulate reinforcements, which thinning plans delay the crash, and the largest crash.

    A plan accumulates when, in every seed, its largest crash holds at its largest moment at least three minions
    from each of two spawn waves, and more minions than the largest crash of a hard push, of a lane with no laner,
    and of a laner that stands under its tower, in the same setting. A thinning plan delays when its first crash
    comes later than the push's in every seed.
    """
    out = {"accumulates": {}, "delays": {}, "largest_crash": {}, "crashes_of_12_or_more": []}
    for setting, rows in cases.items():
        push = rows["push"]
        controls = [rows[control] for control in STACK_CONTROLS if control in rows]
        bar = max(row["largest_crash_peak"]["max"] for row in controls)
        plans = {plan: row for plan, row in rows.items() if plan not in STACK_CONTROLS}
        seeds = push["largest_crash_peak"]["n"]
        out["accumulates"][setting] = sorted(plan for plan, row in plans.items()
                                             if row["largest_crash_second_wave"]["min"] >= WAVE_SHARE and row["largest_crash_peak"]["min"] > bar)
        out["delays"][setting] = sorted(plan for plan, row in plans.items() if plan.startswith("thin") and row["first_crash_s"]["n"] == push["first_crash_s"]["n"] == seeds
                                        and row["first_crash_s"]["min"] > push["first_crash_s"]["max"])
        out["crashes_of_12_or_more"] += [f"{setting}, {plan}" for plan, row in rows.items() if row["largest_crash_peak"]["median"] >= TWO_WAVES]
        if not plans:
            continue
        best = max(plans, key=lambda plan: plans[plan]["largest_crash_peak"]["median"])
        out["largest_crash"][setting] = {"plan": best, "peak": plans[best]["largest_crash_peak"]["median"], "second_wave": plans[best]["largest_crash_second_wave"]["median"],
                                         "crash_s": plans[best]["largest_crash_s"]["median"], "push_peak": push["largest_crash_peak"]["median"],
                                         "push_crash_s": push["largest_crash_s"]["median"],
                                         **{f"{control} peak": rows[control]["largest_crash_peak"]["median"] for control in ("absent", "under tower") if control in rows}}
    return out


def holding(champions=tuple(CHAMPIONS), surpluses=SURPLUS, reds=(False, True), plans=tuple(HOLD_PLANS), seeds=SEEDS, workers=WORKERS,
            rules: LaneRules = M8_LANE, config: Config = Config(), wave: int = 1, team: int = BLUE) -> dict:
    """The holding section with the plan on `team`. `reds` says whether the opponent last-hits."""
    keys = [(c, k, red, plan, wave) for c in champions for k in surpluses for red in reds for plan in plans]
    runs = {}
    for (c, k, red, plan, _), rows in over_seeds(partial(holding_case, rules=rules, config=config, team=team), keys, seeds, workers).items():
        runs.setdefault(f"{c}, {k} surplus casters, {opponent(red)}", {})[plan] = rows
    cases = {setting: {plan: spread(rows) for plan, rows in by_plan.items()} for setting, by_plan in runs.items()}
    return {"cases": cases, "paired": {setting: pairs("holding", by_plan) for setting, by_plan in runs.items()}, **holding_verdict(cases)}


def holding_verdict(cases: dict) -> dict:
    """Per setting: the hold plans that keep the enemy wave near the tower and out of its range, without a death.

    A wave cycle of 30 s is held when the front is in the band for at least half of it and the enemy wave is never
    in the tower's range during it. A hold plan sustains control when, in every seed, the champion does not die and
    the first three cycles are all held, and when that is more cycles than a lane with no champion, a champion
    that stands under its tower, a laner that last-hits with its wave, or one that pushes holds in any seed.
    Retreats, health, and how long the wave was kept out are reported.
    """
    out = {"sustains": {}, "longest": {}}
    for setting, rows in cases.items():
        controls = [control for control in CONTROLS if control in rows]
        bar = max(rows[control]["held_cycles"]["max"] for control in controls)
        holds = {plan: row for plan, row in rows.items() if plan.startswith("hold") and not row["champion_deaths"]["max"]}
        out["sustains"][setting] = {plan: {"cycles": row["held_cycles"]["min"], "kept_out_s": row["kept_out_s"]["min"], "retreats": row["champion_retreats"]["max"],
                                           "lowest_health": row["champion_lowest_health"]["min"]}
                                    for plan, row in holds.items() if row["held_cycles"]["min"] >= SUSTAINED_CYCLES and row["held_cycles"]["min"] > bar}
        best = max(holds, key=lambda plan: holds[plan]["held_cycles"]["min"], default=None)
        out["longest"][setting] = {"plan": best, "cycles": holds[best]["held_cycles"]["min"] if best else 0, "kept_out_s": holds[best]["kept_out_s"]["min"] if best else 0.0,
                                   **{f"{control} cycles": rows[control]["held_cycles"]["max"] for control in controls}}
    cycles = [row["cycles"] for row in out["longest"].values()]
    out["settings_with_a_hold_of_at_least_n_cycles_in_every_seed"] = {str(n): sum(c >= n for c in cycles) for n in range(1, int(HOLD_RUN_S // WAVE_S) + 1)}
    return out


def bounce(champions=tuple(CHAMPIONS), plans=tuple(BOUNCE_PLANS), seeds=SEEDS, workers=WORKERS, rules: LaneRules = M8_LANE, config: Config = Config(),
           team: int = BLUE) -> dict:
    rows = over_seeds(partial(bounce_case, rules=rules, config=config, team=team), [(c, plan) for c in champions for plan in plans], seeds, workers)
    return {f"{c}, {plan}": spread(runs) for (c, plan), runs in rows.items()}


VARIANTS = {
    "m8 lane": M8_LANE,
    "M7's route graph, one bend at each corner": replace(M8_LANE, m7_map=True),
    "blows land at once": replace(M8_LANE, attack_timing=False),
    "ranges along the lane": replace(M8_LANE, straight_ranges=False),
    "no tower shelter": replace(M8_LANE, tower_shelter=False),
    "at most 2 melee minions on a target": replace(M8_LANE, melee_cap=2),
    "a cancelled cast costs nothing": replace(M8_LANE, free_cancel=True),
    "a missile to a dead target turns": replace(M8_LANE, missiles_turn=True),
    "both of those": replace(M8_LANE, free_cancel=True, missiles_turn=True),
    "detour of 0.3 s": replace(M8_LANE, detour_s=0.3),
    "detour of 0.6 s": replace(M8_LANE, detour_s=0.6),
    "minion blows at 0.85": replace(M8_LANE, minion_damage_scale=0.85),
}
DIAGNOSTIC_CHAMPIONS = ("top, level 1, from 0:00", "mid, level 3, from 2:30")
DIAGNOSTIC_SURPLUS = (3, 4)
DIAGNOSTIC_STARTS = ("first contact", "own tower")
DIAGNOSTIC_BOUNCES = ("hard push", "thin 3, then last hit")


def bounced(row: dict, seeds: int) -> bool:
    """A bounce case counts when the front came back in every run, and in every run before the untouched lane's did."""
    return row["front_back_past_centre_s"]["n"] == seeds and row["back_before_the_untouched_lane"]["min"] == 1


def thinning(plans: list[str]) -> list[str]:
    return [plan for plan in plans if plan.startswith("thin")]

def verdicts(stack: dict, hold: dict, back: dict, seeds: int) -> dict:
    """Each verdict of section 5.4 per setting and plan, as true or false."""
    by_champion: dict = {}
    for case, row in back.items():
        plan = next(plan for plan in BOUNCE_PLANS if case.endswith(f", {plan}"))
        by_champion.setdefault(case[: -len(plan) - 2], {})[plan] = bounced(row, seeds)
    return {
        "accumulates": {setting: {plan: plan in stack["accumulates"][setting] for plan in rows if plan not in STACK_CONTROLS} for setting, rows in stack["cases"].items()},
        "delays": {setting: {plan: plan in stack["delays"][setting] for plan in thinning(list(rows))} for setting, rows in stack["cases"].items()},
        "sustains": {setting: {plan: plan in hold["sustains"][setting] for plan in rows if plan.startswith("hold")} for setting, rows in hold["cases"].items()},
        "bounces": by_champion,
    }


def verdict_counts(rules: LaneRules = M8_LANE, config: Config = Config(), seeds=range(3), workers=WORKERS, team: int = BLUE) -> dict:
    """How often each verdict holds on the two diagnostic champions under these lane rules and this clock, with the
    plan on `team`, and what is behind the counts: every verdict per setting and plan, and every seed's largest
    crash, first crash, held cycles, time kept out, and bounce time."""
    stack = stacking(DIAGNOSTIC_CHAMPIONS, DIAGNOSTIC_STARTS, seeds=seeds, workers=workers, rules=rules, config=config, team=team)
    hold = holding(DIAGNOSTIC_CHAMPIONS, surpluses=DIAGNOSTIC_SURPLUS, seeds=seeds, workers=workers, rules=rules, config=config, team=team)
    back = bounce(DIAGNOSTIC_CHAMPIONS, DIAGNOSTIC_BOUNCES, seeds=seeds, workers=workers, rules=rules, config=config, team=team)
    return {
        "settings": len(stack["accumulates"]),
        "settings_where_a_plan_accumulates": sum(bool(plans) for plans in stack["accumulates"].values()),
        "settings_where_a_thinning_plan_accumulates": sum(bool(thinning(plans)) for plans in stack["accumulates"].values()),
        "largest_crash": max(row["peak"] for row in stack["largest_crash"].values()),
        "largest_crash_with_no_laner": max(row["absent peak"] for row in stack["largest_crash"].values()),
        "crashes_of_12_or_more": len(stack["crashes_of_12_or_more"]),
        "hold_settings": len(hold["sustains"]),
        "settings_where_a_hold_sustains_control": sum(bool(plans) for plans in hold["sustains"].values()),
        "longest_hold_cycles": max(row["cycles"] for row in hold["longest"].values()),
        "bounce_cases": len(back),
        "bounce_cases_back_in_every_run": sum(row["front_back_past_centre_s"]["n"] == len(seeds) for row in back.values()),
        "bounce_cases_back_before_the_untouched_lane": sum(bounced(row, len(seeds)) for row in back.values()),
        "verdicts": verdicts(stack, hold, back, len(seeds)),
        "largest_crash_by_seed": {setting: {plan: row["largest_crash_peak"]["values"] for plan, row in rows.items()} for setting, rows in stack["cases"].items()},
        "first_crash_s_by_seed": {setting: {plan: row["first_crash_s"]["values"] for plan, row in rows.items()} for setting, rows in stack["cases"].items()},
        "held_cycles_by_seed": {setting: {plan: row["held_cycles"]["values"] for plan, row in rows.items()} for setting, rows in hold["cases"].items()},
        "kept_out_s_by_seed": {setting: {plan: row["kept_out_s"]["values"] for plan, row in rows.items()} for setting, rows in hold["cases"].items()},
        "bounce_back_s_by_seed": {case: row["front_back_past_centre_s"]["values"] for case, row in back.items()},
    }


def diagnostics(variants=VARIANTS, seeds=range(3), workers=WORKERS) -> dict:
    """The verdicts under one changed lane rule at a time, with the plan on blue. A diagnostic changes the lane only
    for this table. It shows which rule a verdict rests on, not what the lane should be."""
    return {name: {"natural_first_wave_fight_s": {lane: investigate.natural_fight(lane, rules, seeds)["alone_s"]["median"] for lane in ("mid", "top")},
                   **verdict_counts(rules, seeds=seeds, workers=workers)} for name, rules in variants.items()}


TICKS = (0.125, 0.25, 0.5, 1.0)
DECISION_S = 2.0
DECISIONS_S = (1.0, 2.0, 5.0)
DECISION_SWEEP_TICK_S = Config().tick_s


def sweeps(ticks=TICKS, decisions=DECISIONS_S, seeds=range(3), workers=WORKERS, sides=tuple(SIDES)) -> dict:
    """The verdict counts and the numbers behind them, per side, at four tick lengths with a decision every 2 s,
    and at three decision intervals at the research tick. A clock that both sweeps share runs once."""
    clocks = {("tick_sweep", str(tick_s)): (tick_s, round(DECISION_S / tick_s)) for tick_s in ticks}
    clocks |= {("decision_sweep", str(every)): (DECISION_SWEEP_TICK_S, round(every / DECISION_SWEEP_TICK_S)) for every in decisions}
    done, out = {}, {"tick_sweep": {}, "decision_sweep": {}}
    for side in sides:
        for (sweep, label), clock in clocks.items():
            if (side, clock) not in done:
                done[side, clock] = verdict_counts(config=Config(tick_s=clock[0], decision_ticks=clock[1]), seeds=seeds, workers=workers, team=SIDES[side])
            out[sweep].setdefault(side, {})[label] = done[side, clock]
    return out


BY_SEED = ("largest_crash_by_seed", "first_crash_s_by_seed", "held_cycles_by_seed", "kept_out_s_by_seed", "bounce_back_s_by_seed")
LARGEST_SHIFTS = 8


def flat(nested: dict) -> dict:
    """{setting: {plan: value}} as {"setting, plan": value}. A value that is not a dict of plans keeps its key."""
    return {f"{setting}, {plan}": value for setting, plans in nested.items() for plan, value in plans.items()} if all(isinstance(v, dict) for v in nested.values()) else dict(nested)


def sensitivity(sweep: dict) -> dict:
    """How the numbers and the verdicts behind section 5.4 move across the clocks of one sweep, per case, beside how
    far they move across seeds. A case is a setting and a plan. The first clock of the sweep is the reference.

    Per metric and case: every seed's value at every clock, the mean at each clock, the range of those means, the
    range across seeds averaged over the clocks, and each clock's shift of the mean from the reference. Over the
    cases with a value in every run: how many move more across clocks than across seeds, how many give the same
    value in every seed at every clock, the median of the absolute shift from the reference at each clock, and the
    cases that move most. Per verdict: how many cases keep it at every clock, and each case that flips.
    """
    labels = list(sweep)
    reference = labels[0]
    out = {"reference": reference, "metrics": {}, "verdicts": {}}
    for metric in BY_SEED:
        runs = {label: flat(sweep[label][metric]) for label in labels}
        by_case = {}
        for case in runs[reference]:
            values = {label: runs[label][case] for label in labels}
            row = {"values": values}
            if all(value is not None for run in values.values() for value in run):
                means = {label: statistics.mean(run) for label, run in values.items()}
                row |= {"means": means, "range_across_clocks": max(means.values()) - min(means.values()),
                        "mean_range_across_seeds": statistics.mean(max(run) - min(run) for run in values.values()),
                        "shift_from_reference": {label: means[label] - means[reference] for label in labels[1:]}}
            by_case[case] = row
        complete = {case: row for case, row in by_case.items() if "means" in row}
        moving = sorted(complete, key=lambda case: -complete[case]["range_across_clocks"])[:LARGEST_SHIFTS]
        out["metrics"][metric] = {
            "cases": len(by_case),
            "cases_with_a_value_in_every_run": len(complete),
            "cases_moving_more_across_clocks_than_across_seeds": sum(row["range_across_clocks"] > row["mean_range_across_seeds"] for row in complete.values()),
            "cases_equal_in_every_seed_at_every_clock": sum(all(run == row["values"][reference] for run in row["values"].values()) for row in complete.values()),
            "median_absolute_shift_from_reference": {label: statistics.median(abs(row["shift_from_reference"][label]) for row in complete.values()) if complete else None
                                                     for label in labels[1:]},
            "mean_by_clock": {label: statistics.mean(row["means"][label] for row in complete.values()) if complete else None for label in labels},
            "largest_shifts": {case: {"means": complete[case]["means"], "mean_range_across_seeds": complete[case]["mean_range_across_seeds"]} for case in moving},
            "by_case": by_case,
        }
    for kind in sweep[reference]["verdicts"]:
        held = {label: flat(sweep[label]["verdicts"][kind]) for label in labels}
        flips = {case: {label: held[label][case] for label in labels} for case in held[reference] if len({held[label][case] for label in labels}) > 1}
        cases = len(held[reference])
        out["verdicts"][kind] = {"cases": cases, "unchanged": cases - len(flips), "unchanged_share": (cases - len(flips)) / cases if cases else None,
                                 "true_at": {label: sum(held[label].values()) for label in labels}, "flips": flips}
    return out


def between_sides(section: str, blue: dict, red: dict) -> dict:
    """Per setting, plan, and metric: blue's value minus red's on the same seed, with the plan on that side."""
    metrics = BETWEEN_SIDES["bounce" if section == "bounce" else section.split("_")[0]]
    if section == "bounce":
        return {case: {name: differences(row[name]["values"], red[case][name]["values"]) for name in metrics} for case, row in blue.items()}
    return {setting: {plan: {name: differences(row[name]["values"], red["cases"][setting][plan][name]["values"]) for name in metrics}
                      for plan, row in rows.items()} for setting, rows in blue["cases"].items()}


def compare(blue: dict, red: dict) -> dict:
    """One verdict, {setting: {plan: bool}} on each side, compared per setting and per case. A setting counts on
    both sides when some plan holds the verdict on both."""
    settings = {setting: {"blue": [plan for plan, ok in plans.items() if ok], "red": [plan for plan, ok in red[setting].items() if ok]} for setting, plans in blue.items()}
    cases_blue, cases_red = flat(blue), flat(red)
    return {
        "settings": len(settings),
        "settings_blue": sum(bool(row["blue"]) for row in settings.values()),
        "settings_red": sum(bool(row["red"]) for row in settings.values()),
        "settings_both_sides": sum(bool(set(row["blue"]) & set(row["red"])) for row in settings.values()),
        "settings_either_side": sum(bool(row["blue"] or row["red"]) for row in settings.values()),
        "cases": len(cases_blue),
        "cases_blue": sum(cases_blue.values()),
        "cases_red": sum(cases_red.values()),
        "cases_both_sides": sum(ok and cases_red[case] for case, ok in cases_blue.items()),
        "settings_that_differ": {setting: row for setting, row in settings.items() if set(row["blue"]) != set(row["red"])},
    }


def beats(section: dict, kind: str, seeds: int) -> dict:
    """The headline of a paired table: per metric and control, of all plan scenarios (setting and plan), how many
    have the plan's value above the control's in every seed, and below it in every seed."""
    out = {}
    for metric in BEATS[kind]:
        for plans in section["paired"].values():
            for controls in plans.values():
                for control, row in controls.items():
                    tally = out.setdefault(metric, {}).setdefault(control, {"scenarios": 0, "higher_in_every_seed": 0, "lower_in_every_seed": 0})
                    tally["scenarios"] += 1
                    tally["higher_in_every_seed"] += row[metric]["higher"] == seeds
                    tally["lower_in_every_seed"] += row[metric]["lower"] == seeds
    return out


def at_least(longest: dict) -> dict:
    cycles = [row["cycles"] for row in longest.values()]
    return {str(n): sum(c >= n for c in cycles) for n in range(1, int(HOLD_RUN_S // WAVE_S) + 1)}


def side_summary(results: dict, seeds: int) -> dict:
    """The counts of section 5.4 per side and for both sides, and the paired headlines per side."""
    blue, red = ({section: results[section][side] for section in SECTIONS} for side in SIDES)
    on = {side: verdicts(results["stacking"][side], results["holding"][side], results["bounce"][side], seeds) for side in SIDES}
    third = {side: {setting: {plan: plan in plans for plan in results["holding_from_the_third_wave"][side]["cases"][setting] if plan.startswith("hold")}
                    for setting, plans in results["holding_from_the_third_wave"][side]["sustains"].items()} for side in SIDES}
    longest = {section: {setting: {"cycles": min(blue[section]["longest"][setting]["cycles"], red[section]["longest"][setting]["cycles"])}
                         for setting in blue[section]["longest"]} for section in ("holding", "holding_from_the_third_wave")}
    return {
        "accumulates": compare(on["blue"]["accumulates"], on["red"]["accumulates"]),
        "delays": compare(on["blue"]["delays"], on["red"]["delays"]),
        "sustains": compare(on["blue"]["sustains"], on["red"]["sustains"]),
        "sustains_from_the_third_wave": compare(third["blue"], third["red"]),
        "bounces": compare(on["blue"]["bounces"], on["red"]["bounces"]),
        "settings_with_a_hold_of_at_least_n_cycles_in_every_seed": {
            section: {"blue": blue[section]["settings_with_a_hold_of_at_least_n_cycles_in_every_seed"], "red": red[section]["settings_with_a_hold_of_at_least_n_cycles_in_every_seed"],
                      "both_sides": at_least(longest[section])} for section in longest},
        "largest_crash": {side: max(row["peak"] for row in results["stacking"][side]["largest_crash"].values()) for side in SIDES},
        "crashes_of_12_or_more": {side: results["stacking"][side]["crashes_of_12_or_more"] for side in SIDES},
        "bounce_back_in_every_run": {side: sum(row["front_back_past_centre_s"]["n"] == seeds for row in results["bounce"][side].values()) for side in SIDES},
        "paired_headline": {side: {section: beats(results[section][side], section.split("_")[0], seeds) for section in ("stacking", "holding", "holding_from_the_third_wave")}
                            for side in SIDES},
    }


SECTIONS = ("stacking", "holding", "holding_from_the_third_wave", "bounce")


def write(results: dict, path: Path, settings: dict) -> None:
    results["run"] = stamp(SEEDS, settings)
    path.parent.mkdir(exist_ok=True)
    one_row_per_line = re.sub(r"\[[^\[\]]*\]|\{[^{}]*\}", lambda row: re.sub(r"\s+", " ", row.group()), json.dumps(rounded(results), indent=1))
    path.write_text(one_row_per_line, encoding="utf-8")


COUNTS = ("settings_where_a_plan_accumulates", "settings_where_a_thinning_plan_accumulates", "largest_crash", "largest_crash_with_no_laner",
          "settings_where_a_hold_sustains_control", "longest_hold_cycles", "bounce_cases_back_in_every_run", "bounce_cases_back_before_the_untouched_lane")


def report(results: dict) -> None:
    """Print the counts and the rows that the M8 document quotes from a results file."""
    seeds = len(results["seeds"])
    for side in SIDES:
        stack = results["stacking"][side]
        print(f"[{side}] stacking: a plan accumulates in {sum(bool(plans) for plans in stack['accumulates'].values())} of {len(stack['accumulates'])} settings, "
              f"a thinning plan in {sum(bool(thinning(plans)) for plans in stack['accumulates'].values())}, largest crash {max(row['peak'] for row in stack['largest_crash'].values())}, "
              f"largest with no laner {max(row['absent peak'] for row in stack['largest_crash'].values())}, crashes of 12 or more: {len(stack['crashes_of_12_or_more'])}")
        for start in STARTS:
            mine = {setting: plans for setting, plans in stack["accumulates"].items() if f", from {start}, " in setting}
            print(f"[{side}]   from {start}: accumulates in {sum(bool(plans) for plans in mine.values())} of {len(mine)}, delays in {sum(bool(stack['delays'][setting]) for setting in mine)}")
        for setting, plans in stack["accumulates"].items():
            if plans:
                print(f"[{side}]   accumulates: {setting}: {plans}, largest {stack['largest_crash'][setting]}")
        for name in ("holding", "holding_from_the_third_wave"):
            hold = results[name][side]
            print(f"[{side}] {name}: a hold sustains control in {sum(bool(plans) for plans in hold['sustains'].values())} of {len(hold['sustains'])} settings, "
                  f"by cycles {hold['settings_with_a_hold_of_at_least_n_cycles_in_every_seed']}")
            for setting, plans in hold["sustains"].items():
                if plans:
                    print(f"[{side}]   sustains: {setting}: {plans}, controls {({key: value for key, value in hold['longest'][setting].items() if key.endswith(' cycles')})}")
        for case, row in results["bounce"][side].items():
            print(f"[{side}] bounce {case}: back after {row['front_back_past_centre_s']['median']} s in {row['front_back_past_centre_s']['n']} of {seeds} runs, "
                  f"untouched lane there after {row['untouched_front_there_s']['median']} s in {row['untouched_front_there_s']['n']}, "
                  f"sooner by {row['back_sooner_than_untouched_s']['values']}, counts: {bounced(row, seeds)}")
        for name in ("stacking", "holding", "holding_from_the_third_wave"):
            rows = [row for plans in results[name][side]["cases"].values() for row in plans.values()]
            early = [row["minion_blows_before_first_contact"]["max"] for row in rows if row["minion_blows_before_first_contact"]["n"]]
            unseen = [row["enemy_lead_unseen_share"]["median"] for row in rows]
            print(f"[{side}] {name}: cases with a minion blow on the champion before the first waves met: {sum(blows > 0 for blows in early)} of {len(early)}. "
                  f"Share of ticks on which the team did not see the enemy lead minion: median {statistics.median(unseen):.3f}, largest {max(unseen):.3f}")
    summary = results["sides"]
    for kind in ("accumulates", "delays", "sustains", "sustains_from_the_third_wave", "bounces"):
        row = summary[kind]
        print(f"sides {kind}: settings blue {row['settings_blue']}, red {row['settings_red']}, both {row['settings_both_sides']}, either {row['settings_either_side']} of {row['settings']}; "
              f"cases blue {row['cases_blue']}, red {row['cases_red']}, both {row['cases_both_sides']} of {row['cases']}")
        for setting, plans in row["settings_that_differ"].items():
            print(f"    differs: {setting}: {plans}")
    for key in ("settings_with_a_hold_of_at_least_n_cycles_in_every_seed", "largest_crash", "bounce_back_in_every_run"):
        print(f"sides {key}: {summary[key]}")
    for side, sections in summary["paired_headline"].items():
        for section, metrics in sections.items():
            print(f"[{side}] paired {section}: {metrics}")
    for name, row in results["diagnostics"].items():
        print(f"diagnostic {name}: fight {row['natural_first_wave_fight_s']} {({key: row[key] for key in COUNTS})}")
    for sweep in ("tick_sweep", "decision_sweep"):
        for side, by_clock in results[sweep].items():
            for clock, row in by_clock.items():
                print(f"[{side}] {sweep} {clock}: {({key: row[key] for key in COUNTS})}")
            spread_ = sensitivity(by_clock)
            for kind, row in spread_["verdicts"].items():
                print(f"[{side}] {sweep} verdict {kind}: unchanged in {row['unchanged']} of {row['cases']}, true at {row['true_at']}, flips {row['flips']}")
            for metric, row in spread_["metrics"].items():
                print(f"[{side}] {sweep} {metric}: {row['cases_with_a_value_in_every_run']} cases, more across clocks than seeds in {row['cases_moving_more_across_clocks_than_across_seeds']}, "
                      f"equal in {row['cases_equal_in_every_seed_at_every_clock']}, median |shift| from {spread_['reference']}: {rounded(row['median_absolute_shift_from_reference'])}, "
                      f"means {rounded(row['mean_by_clock'])}")
                for case, shift in list(row["largest_shifts"].items())[:3]:
                    print(f"        moves most: {case}: {rounded(shift)}")


def main() -> None:
    if sys.argv[1:] == ["--report"]:
        return report(json.loads(RESULTS.read_text(encoding="utf-8")))
    results = {"ruleset": RULESET_ID, "seeds": list(SEEDS), "champions": {label: {"roles": list(roles), "level": level, "start_s": start_s} for label, (roles, level, start_s) in CHAMPIONS.items()}}
    for side, team in SIDES.items():
        for section, run in (("stacking", partial(stacking, team=team)), ("holding", partial(holding, team=team)),
                             ("holding_from_the_third_wave", partial(holding, surpluses=LATER_SURPLUS, wave=LATER_WAVE, team=team)), ("bounce", partial(bounce, team=team))):
            results.setdefault(section, {})[side] = run()
    for section in SECTIONS:
        results[section]["between_sides"] = between_sides(section, results[section]["blue"], results[section]["red"])
    results["sides"] = side_summary(results, len(SEEDS))
    results |= {"variants": {name: asdict(rules) for name, rules in VARIANTS.items()}, "diagnostics": diagnostics(), **sweeps()}
    for sweep in ("tick_sweep", "decision_sweep"):
        results[f"{sweep}_sensitivity"] = {side: sensitivity(by_clock) for side, by_clock in results[sweep].items()}
    write(results, RESULTS, {"plan_run_s": PLAN_RUN_S, "hold_run_s": HOLD_RUN_S, "bounce_run_s": BOUNCE_RUN_S, "surplus": SURPLUS, "later_surplus": LATER_SURPLUS,
                             "later_wave": LATER_WAVE, "ticks": TICKS, "decision_s": DECISION_S, "decisions_s": DECISIONS_S, "decision_sweep_tick_s": DECISION_SWEEP_TICK_S,
                             "sides": list(SIDES), "sweep_seeds": 3, "diagnostics_side": "blue"})
    report(json.loads(RESULTS.read_text(encoding="utf-8")))
    print(f"wrote {RESULTS}")


if __name__ == "__main__":
    sys.exit(main())
