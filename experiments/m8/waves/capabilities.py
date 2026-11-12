"""Holding, stacking, and bouncing through the action interface, across champion capabilities and starting states.

Each case is a full world. A plan picks `LANE` actions only (and a walk to its tower when low), so every result is
reachable by an agent. Each section answers one question.
  stacking  Over plans, starts, and champions, how large and how late is the crash, and how many waves are in it?
  holding   Does a champion on the hold line keep an enemy wave off its tower longer than no champion does?
  bounce    After a crash, does the lane come back, and when?

Run: python -m experiments.m8.waves.capabilities
"""

import json
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
from functools import partial
from pathlib import Path

from experiments.m8.provenance import stamp
from experiments.m8.waves import agents
from experiments.m8.waves.agents import Laner, always, hold_thin_over, hold_trim_to, seat_of, thin_then, until_crash
from experiments.m8.waves import investigate
from experiments.m8.waves.harness import BLUE, RED, Crashes, Crowding, offset, outer, rounded, second_wave, summarize, tower_damage, under_tower
from riftgame.champions import HOME, ROLES
from riftgame.lanes import HOLD_MARGIN, M8_LANE, RULESET_ID, LaneRules
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
    "push": lambda: always("push"),
    "last hit": lambda: always("last_hit"),
    "passive": lambda: always("passive"),
    "thin 1, then last hit": lambda: thin_then(1, "last_hit"),
    "thin 2, then last hit": lambda: thin_then(2, "last_hit"),
    "thin 3, then last hit": lambda: thin_then(3, "last_hit"),
    "thin 3, then passive": lambda: thin_then(3, "passive"),
    "thin every caster": lambda: always("thin"),
}
CONTROLS = ("absent", "last hit with the wave", "push")
HOLD_PLANS = {
    "absent": None,
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


def lane_of(champion: str) -> str:
    return HOME[ROLES.index(CHAMPIONS[champion][0][0])]


def team_laners(champion: str, team: int, plan, retreats: bool = True) -> list[Laner]:
    """The lane's champions of one team under `plan`. A support stands where its carry stands and hits nothing."""
    roles = CHAMPIONS[champion][0]
    laners = [Laner(seat_of(team, roles[0]), plan(), retreats)]
    if len(roles) > 1:
        carry = laners[0]

        def beside(seen, carry=carry):
            choice = carry.plan(seen)
            return choice if isinstance(choice, str) else ("passive", choice[1])

        laners.append(Laner(seat_of(team, roles[1]), beside, retreats))
    return laners


def stacking_case(args, rules: LaneRules = M8_LANE, config: Config = Config()) -> dict:
    """Blue plays a plan from first contact, or from the moment a red push reaches blue's outer tower."""
    champion, start, red_last_hits, plan, seed = args
    roles, level, start_s = CHAMPIONS[champion]
    lane = lane_of(champion)
    world = agents.staged(seed, dict.fromkeys(roles, level), start_s, config, rules)
    sim = world.lanes[lane]
    geometry = sim.geometry
    began = []

    def opening(seen):
        if not began and seen.contact and (start == "first contact" or seen.foe_at_own_tower):
            began.append(seen.time_s)
        return bool(began)

    blue_plan = PUSH_PLANS[plan]

    def blue():
        chosen = blue_plan()
        return lambda seen: chosen(seen) if opening(seen) else ("last_hit", "wave")

    def red():
        after = always("last_hit") if red_last_hits else (lambda seen: "leave")
        before = always("push") if start == "own tower" else after
        return lambda seen: after(seen) if began else before(seen)

    laners = team_laners(champion, BLUE, blue)
    present = red_last_hits or start == "own tower"
    crashes, crowding = Crashes(sim, BLUE), Crowding(sim)
    largest = [0]

    def stop(row) -> bool:
        if began:
            crashes.watch(row)
            crowding.watch(row)
            largest[0] = max(largest[0], row.wave_blue)
        return bool(began) and row.t >= began[0] + PLAN_RUN_S

    trace = agents.play(world, lane, laners + (team_laners(champion, RED, red) if present else []), start_s + 900.0, stop)
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
        "red_tower_damage": tower_damage(trace.events, RED, began[0]) if began else None,
        "casts_cancelled": sim.cancelled,
        "missiles_lost": sim.lost,
        **crowding.report(),
        **laners[0].report(world),
    }


def holding_case(args, rules: LaneRules = M8_LANE, config: Config = Config()) -> dict:
    """The experiment places `surplus` red casters at the hold line when blue's first wave reaches its own tower's edge.

    The run then lasts 240 s. With a red laner, red last-hits from the start.
    """
    champion, surplus, red_last_hits, plan, seed = args
    roles, level, start_s = CHAMPIONS[champion]
    lane = lane_of(champion)
    world = agents.staged(seed, dict.fromkeys(roles, level), start_s, config, rules)
    sim = world.lanes[lane]
    geometry = sim.geometry
    lo, hi = agents.band(geometry)
    placed = []
    laners = team_laners(champion, BLUE, HOLD_PLANS[plan]) if HOLD_PLANS[plan] else []
    reds = team_laners(champion, RED, lambda: always("last_hit")) if red_last_hits else []
    peak = [0]

    def stop(row) -> bool:
        if not placed and row.lead_blue is not None and row.lead_blue >= lo:
            sim.add_minion(RED, Minion.CASTER, lo + HOLD_MARGIN + 390.0, count=surplus)
            placed.append(row.t)
        if placed:
            peak[0] = max(peak[0], agents.crowd(sim, RED, row.line))
        return bool(placed) and row.t >= placed[0] + HOLD_RUN_S

    trace = agents.play(world, lane, laners + reds, start_s + 900.0, stop)
    rows = [r for r in trace.rows if r.t >= placed[0]]
    inside = [r.line is not None and lo <= r.line <= hi for r in rows]
    dt = world.config.tick_s
    breached = [under_tower(geometry, BLUE, r.lead_red) for r in rows]
    spans = [(placed[0] + WAVE_S * i, placed[0] + WAVE_S * (i + 1)) for i in range(int(HOLD_RUN_S // WAVE_S))]
    cycles = [sum(ok for r, ok in zip(rows, inside) if lo_t <= r.t < hi_t) * dt for lo_t, hi_t in spans]
    at_tower = [sum(hit for r, hit in zip(rows, breached) if lo_t <= r.t < hi_t) * dt for lo_t, hi_t in spans]
    held = [near >= WAVE_S / 2 and reached == 0 for near, reached in zip(cycles, at_tower)]
    report = laners[0].report(world) if laners else {"champion_lowest_health": None, "champion_retreats": None, "champion_deaths": None, "minion_gold": None, "level": None}
    return {
        "band_s": sum(inside) * dt,
        "cycles_mostly_in_band": sum(c >= WAVE_S / 2 for c in cycles),
        "held_cycles": next((i for i, ok in enumerate(held) if not ok), len(held)),
        "kept_out_s": next((r.t - placed[0] for r, hit in zip(rows, breached) if hit), HOLD_RUN_S),
        "under_tower_s": sum(breached) * dt,
        "blue_tower_damage": tower_damage(trace.events, BLUE),
        "pushed_out": any(r.lead_blue is not None and r.lead_blue > geometry.centre for r in rows),
        "largest_enemy_wave": peak[0],
        **report,
    }


BOUNCE_PLANS = {"hard push": lambda: always("push"), "thin 3, then last hit": lambda: thin_then(3, "last_hit")}


def bounce_case(args, rules: LaneRules = M8_LANE, config: Config = Config()) -> dict:
    """A laner follows a plan from first contact until its wave is in the enemy tower's range, then leaves. Nobody
    else acts. A lane that meets again within 100 units of the centre has reset. One that meets on blue's half
    has bounced. The same world with no laner at all runs beside it, because an untouched lane drifts too."""
    champion, plan, seed = args
    roles, level, start_s = CHAMPIONS[champion]
    lane = lane_of(champion)
    world = agents.staged(seed, dict.fromkeys(roles, level), start_s, config, rules)
    geometry = world.lanes[lane].geometry
    laners = team_laners(champion, BLUE, lambda: until_crash(BOUNCE_PLANS[plan]()), retreats=False)
    crashes = Crashes(world.lanes[lane], BLUE)
    answer = Crashes(world.lanes[lane], RED)

    def stop(row) -> bool:
        crashes.watch(row)
        answer.watch(row)
        return False

    trace = agents.play(world, lane, laners, start_s + BOUNCE_RUN_S, stop)
    if not crashes.spans:
        return {"crash_s": None, "crash_peak": None, "front_back_past_centre_s": None, "red_wave_at_blue_tower_s": None, "answer_peak": None,
                "front_on_blue_half_share": None, "front_at_centre_share": None, "deepest_offset": None, "untouched_front_there_s": None, "back_before_the_untouched_lane": 0}
    crash = crashes.spans[0]["start"]
    later = [r for r in trace.rows if r.t > crash]
    back = next((r.t - crash for r in later if r.contact and offset(geometry, r.line) < -RESET_WITHIN), None)
    replies = [span for span in answer.spans if span["start"] > crash]
    contacts = [offset(geometry, r.line) for r in later if r.contact]
    untouched = agents.staged(seed, dict.fromkeys(roles, level), start_s, config, rules)
    drift = agents.play(untouched, lane, [], start_s + BOUNCE_RUN_S)
    there = next((r.t - crash for r in drift.rows if r.t > crash and r.contact and offset(geometry, r.line) < -RESET_WITHIN), None)
    return {
        "untouched_front_there_s": there,
        "back_before_the_untouched_lane": int(back is not None and (there is None or back < there)),
        "crash_s": crash - start_s,
        "crash_peak": crashes.spans[0]["peak"],
        "front_back_past_centre_s": back,
        "red_wave_at_blue_tower_s": replies[0]["start"] - crash if replies else None,
        "answer_peak": replies[0]["peak"] if replies else None,
        "front_on_blue_half_share": sum(o < -RESET_WITHIN for o in contacts) / len(contacts) if contacts else None,
        "front_at_centre_share": sum(abs(o) <= RESET_WITHIN for o in contacts) / len(contacts) if contacts else None,
        "deepest_offset": min(contacts, default=None),
    }


def over_seeds(case, keys: list[tuple], seeds=SEEDS, workers: int = WORKERS) -> dict:
    """`case` over every key and seed, summarized per key. The runs are independent, so they go to a process pool."""
    jobs = [(*key, seed) for key in keys for seed in seeds]
    if workers > 1:
        with ProcessPoolExecutor(workers) as pool:
            done = list(pool.map(case, jobs, chunksize=4))
    else:
        done = [case(job) for job in jobs]
    out = {}
    for job, metrics in zip(jobs, done):
        out.setdefault(job[:-1], []).append(metrics)
    return {key: summarize(runs) for key, runs in out.items()}


def stacking(champions=tuple(CHAMPIONS), starts=("first contact", "own tower"), reds=(False, True), plans=tuple(PUSH_PLANS), seeds=SEEDS, workers=WORKERS,
             rules: LaneRules = M8_LANE, config: Config = Config()) -> dict:
    keys = [(c, start, red, plan) for c in champions for start in starts for red in reds for plan in plans]
    rows = over_seeds(partial(stacking_case, rules=rules, config=config), keys, seeds, workers)
    cases = {}
    for (c, start, red, plan), row in rows.items():
        cases.setdefault(f"{c}, from {start}, red {'last hits' if red else 'absent'}", {})[plan] = row
    return {"cases": cases, **stacking_verdict(cases)}


def stacking_verdict(cases: dict) -> dict:
    """Per setting: which plans accumulate reinforcements, which thinning plans delay the crash, and the largest crash.

    A plan accumulates when, in every seed, its largest crash holds at its largest moment at least three minions
    from each of two spawn waves, and more minions than the largest crash of a hard push and of a lane with no
    laner in the same setting. A thinning plan delays when its first crash comes later than the push's in every seed.
    """
    out = {"accumulates": {}, "delays": {}, "largest_crash": {}, "crashes_of_12_or_more": []}
    for setting, rows in cases.items():
        push, nobody = rows["push"], rows["absent"]
        bar = max(push["largest_crash_peak"]["max"], nobody["largest_crash_peak"]["max"])
        plans = {plan: row for plan, row in rows.items() if plan not in ("push", "absent")}
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
                                         "push_crash_s": push["largest_crash_s"]["median"], "no_laner_peak": nobody["largest_crash_peak"]["median"],
                                         "no_laner_second_wave": nobody["largest_crash_second_wave"]["median"]}
    return out


def holding(champions=tuple(CHAMPIONS), surpluses=SURPLUS, reds=(False, True), plans=tuple(HOLD_PLANS), seeds=SEEDS, workers=WORKERS,
            rules: LaneRules = M8_LANE, config: Config = Config()) -> dict:
    keys = [(c, k, red, plan) for c in champions for k in surpluses for red in reds for plan in plans]
    rows = over_seeds(partial(holding_case, rules=rules, config=config), keys, seeds, workers)
    cases = {}
    for (c, k, red, plan), row in rows.items():
        cases.setdefault(f"{c}, {k} surplus casters, red {'last hits' if red else 'absent'}", {})[plan] = row
    return {"cases": cases, **holding_verdict(cases)}


def holding_verdict(cases: dict) -> dict:
    """Per setting: the hold plans that keep the enemy wave near the tower and out of its range, without a death.

    A wave cycle of 30 s is held when the front is in the band for at least half of it and the enemy wave is never
    in the tower's range during it. A hold plan sustains control when, in every seed, the champion does not die and
    the first three cycles are all held, and when that is more cycles than a lane with no champion, a laner that
    last-hits with its wave, or one that pushes holds in any seed. Retreats and health are reported.
    """
    out = {"sustains": {}, "longest": {}}
    for setting, rows in cases.items():
        bar = max(rows[control]["held_cycles"]["max"] for control in CONTROLS)
        holds = {plan: row for plan, row in rows.items() if plan.startswith("hold") and not row["champion_deaths"]["max"]}
        out["sustains"][setting] = {plan: {"cycles": row["held_cycles"]["min"], "retreats": row["champion_retreats"]["max"], "lowest_health": row["champion_lowest_health"]["min"]}
                                    for plan, row in holds.items() if row["held_cycles"]["min"] >= SUSTAINED_CYCLES and row["held_cycles"]["min"] > bar}
        best = max(holds, key=lambda plan: holds[plan]["held_cycles"]["min"], default=None)
        out["longest"][setting] = {"plan": best, "cycles": holds[best]["held_cycles"]["min"] if best else 0,
                                   **{f"{control} cycles": rows[control]["held_cycles"]["max"] for control in CONTROLS}}
    cycles = [row["cycles"] for row in out["longest"].values()]
    out["settings_with_a_hold_of_at_least_n_cycles_in_every_seed"] = {str(n): sum(c >= n for c in cycles) for n in range(1, int(HOLD_RUN_S // WAVE_S) + 1)}
    return out


def bounce(champions=tuple(CHAMPIONS), plans=tuple(BOUNCE_PLANS), seeds=SEEDS, workers=WORKERS, rules: LaneRules = M8_LANE, config: Config = Config()) -> dict:
    rows = over_seeds(partial(bounce_case, rules=rules, config=config), [(c, plan) for c in champions for plan in plans], seeds, workers)
    return {f"{c}, {plan}": row for (c, plan), row in rows.items()}


VARIANTS = {
    "m8 lane": M8_LANE,
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


def bounced(row: dict, seeds: int) -> bool:
    """A bounce case counts when the front came back in every run, and in every run before the untouched lane's did."""
    return row["front_back_past_centre_s"]["n"] == seeds and row["back_before_the_untouched_lane"]["min"] == 1


def thinning(plans: list[str]) -> list[str]:
    return [plan for plan in plans if plan.startswith("thin")]


def verdict_counts(rules: LaneRules = M8_LANE, config: Config = Config(), seeds=range(3), workers=WORKERS) -> dict:
    """How often each verdict holds on the two diagnostic champions under these lane rules and this clock."""
    stack = stacking(DIAGNOSTIC_CHAMPIONS, seeds=seeds, workers=workers, rules=rules, config=config)
    hold = holding(DIAGNOSTIC_CHAMPIONS, surpluses=DIAGNOSTIC_SURPLUS, seeds=seeds, workers=workers, rules=rules, config=config)
    back = bounce(DIAGNOSTIC_CHAMPIONS, seeds=seeds, workers=workers, rules=rules, config=config)
    return {
        "settings": len(stack["accumulates"]),
        "settings_where_a_plan_accumulates": sum(bool(plans) for plans in stack["accumulates"].values()),
        "settings_where_a_thinning_plan_accumulates": sum(bool(thinning(plans)) for plans in stack["accumulates"].values()),
        "largest_crash": max(row["peak"] for row in stack["largest_crash"].values()),
        "largest_crash_with_no_laner": max(row["no_laner_peak"] for row in stack["largest_crash"].values()),
        "crashes_of_12_or_more": len(stack["crashes_of_12_or_more"]),
        "hold_settings": len(hold["sustains"]),
        "settings_where_a_hold_sustains_control": sum(bool(plans) for plans in hold["sustains"].values()),
        "longest_hold_cycles": max(row["cycles"] for row in hold["longest"].values()),
        "bounce_cases": len(back),
        "bounce_cases_back_in_every_run": sum(row["front_back_past_centre_s"]["n"] == len(seeds) for row in back.values()),
        "bounce_cases_back_before_the_untouched_lane": sum(bounced(row, len(seeds)) for row in back.values()),
    }


def diagnostics(variants=VARIANTS, seeds=range(3), workers=WORKERS) -> dict:
    """The verdicts under one changed lane rule at a time. A diagnostic changes the lane only for this table. It
    shows which rule a verdict rests on, not what the lane should be."""
    return {name: {"natural_first_wave_fight_s": {lane: investigate.natural_fight(lane, rules, seeds)["alone_s"]["median"] for lane in ("mid", "top")},
                   **verdict_counts(rules, seeds=seeds, workers=workers)} for name, rules in variants.items()}


def tick_sweep(ticks=(0.25, 0.5), seeds=range(3), workers=WORKERS) -> dict:
    """The same verdicts at two tick lengths, with a decision every 2 s at both."""
    return {str(tick_s): verdict_counts(config=Config(tick_s=tick_s, decision_ticks=round(2.0 / tick_s)), seeds=seeds, workers=workers) for tick_s in ticks}


def write(results: dict, path: Path, settings: dict) -> None:
    results["run"] = stamp(SEEDS, settings)
    path.parent.mkdir(exist_ok=True)
    one_row_per_line = re.sub(r"\[[^\[\]]*\]|\{[^{}]*\}", lambda row: re.sub(r"\s+", " ", row.group()), json.dumps(rounded(results), indent=1))
    path.write_text(one_row_per_line, encoding="utf-8")


def main() -> None:
    results = {"ruleset": RULESET_ID, "seeds": list(SEEDS), "champions": {label: {"roles": list(roles), "level": level, "start_s": start_s} for label, (roles, level, start_s) in CHAMPIONS.items()},
               "stacking": stacking(), "holding": holding(), "bounce": bounce(),
               "variants": {name: asdict(rules) for name, rules in VARIANTS.items()}, "diagnostics": diagnostics(), "tick_sweep": tick_sweep()}
    write(results, RESULTS, {"plan_run_s": PLAN_RUN_S, "hold_run_s": HOLD_RUN_S, "bounce_run_s": BOUNCE_RUN_S, "surplus": SURPLUS})
    stack, hold = results["stacking"], results["holding"]
    print(f"stacking: a plan accumulates in {sum(bool(plans) for plans in stack['accumulates'].values())} of {len(stack['accumulates'])} settings, "
          f"a thinning plan in {sum(bool(thinning(plans)) for plans in stack['accumulates'].values())}, largest crash {max(row['peak'] for row in stack['largest_crash'].values())}, "
          f"largest with no laner {max(row['no_laner_peak'] for row in stack['largest_crash'].values())}, crashes of 12 or more: {len(stack['crashes_of_12_or_more'])}")
    print(f"holding: a hold sustains control in {sum(bool(plans) for plans in hold['sustains'].values())} of {len(hold['sustains'])} settings, "
          f"by cycles {hold['settings_with_a_hold_of_at_least_n_cycles_in_every_seed']}")
    for case, row in results["bounce"].items():
        print(f"bounce {case}: back after {row['front_back_past_centre_s']['median']} s in {row['front_back_past_centre_s']['n']} of {len(SEEDS)} runs, "
              f"untouched lane there after {row['untouched_front_there_s']['median']} s in {row['untouched_front_there_s']['n']}, counts: {bounced(row, len(SEEDS))}")
    for name, row in results["diagnostics"].items():
        print(f"diagnostic {name}: {row}")
    for tick_s, row in results["tick_sweep"].items():
        print(f"tick {tick_s} s: {row}")
    print(f"wrote {RESULTS}")


if __name__ == "__main__":
    sys.exit(main())
