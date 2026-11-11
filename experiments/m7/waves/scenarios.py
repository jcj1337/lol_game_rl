"""M7 wave experiments: ablation of the optional lane mechanics, and slow-push and freeze scenarios with a mortal champion.

Run: python -m experiments.m7.waves.scenarios
"""

import json
import re
import statistics
import time
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path
from typing import NamedTuple

from experiments.m7.provenance import stamp
from experiments.m7.waves.lane import (
    ACQUIRE,
    BASELINE,
    KINDS,
    MID,
    RECOMMENDED,
    RULES,
    TOP,
    TOWER_RANGE,
    ChampionDamage,
    ChampionInput,
    Front,
    Kind,
    LaneGeometry,
    LaneSim,
    Mechanics,
    MinionDeath,
    Mode,
    Team,
    TowerDamage,
)

BLUE, RED = Team.BLUE, Team.RED
RECOMMENDED_NAME = "A+B"
FLAT_NAME = "A+B flat damage"
SIDE_SPEED_NAME = "A+B side speed"
CHAMPION_PLAN_CONFIGS = (RECOMMENDED_NAME, FLAT_NAME, SIDE_SPEED_NAME)
CONFIGS = {
    "baseline": BASELINE,
    "A": Mechanics(champion_aggro=True),
    "B": Mechanics(lateral_slots=True),
    RECOMMENDED_NAME: RECOMMENDED,
    FLAT_NAME: Mechanics(champion_aggro=True, lateral_slots=True, current_hp_damage=False),
    SIDE_SPEED_NAME: Mechanics(champion_aggro=True, lateral_slots=True, side_lane_speed=True),
}
SEEDS = range(5)
DTS = (0.125, 0.25, 0.5, 1.0)
REFERENCE_DT = 0.125
REPORT_DT = 0.5
TOLERANCE = 0.10
SAMPLE_S = 5.0
RESULTS = Path(__file__).parent / "results" / "waves.json"

WAVE_SPAN = 1500.0
CRASH_GAP_S = 5.0
TOWER_MARGIN = 50.0
STAND_OFF = 550.0
BOUNCE_MARKS_S = (30, 60, 90, 120)
PERTURB_MARKS_S = (120, 180, 240, 300, 360)
FIGHT_START_S = 181.0
FIGHT_LIMIT_S = 55.0
BUILT_START_S = 180.0
BUILT_MARGIN = 300.0
SLOW_PUSH_LIMIT_S = 300.0
SLOW_PUSH_STACK = 12
AFTER_CRASH_S = 20.0
TOWER_ZONE = 600.0
FREEZE_BAND = 1500.0
FREEZE_RUN_S = 240.0
BREAKER_ARRIVES_S = 240.0
FREEZE_SURPLUS = (0, 2, 3, 4, 6)
THIN_OVER = (1, 2, 3, 4)
TRIM_TO = (2, 3, 4)
MELEE_REACH = KINDS[Kind.MELEE].stop_range
CASTER_REACH = KINDS[Kind.CASTER].stop_range

LANER_HP = 650.0
LANER_ARMOR = 30.0
LANER_REGEN = 1.5
LANER_SPEED = 335.0
RETREAT_BELOW = 0.30
RETURN_ABOVE = 0.60

ASSUMPTIONS = {
    "laner": "level 1 to 3 laner: hit_damage 65, attack_speed 0.65, attack_range 550, aoe_dps 70 (ChampionInput defaults), always a valid minion target",
    "mortal_laner": "the champion of the slow-push and freeze cases has 650 health, 30 armor, 1.5 health regeneration per second, and move speed 335, all placeholders; it walks to where it wants to stand; below 30 percent health it walks to its own tower and stays out of the wave until it is back above 60 percent; at zero health it is dead for the rest of the run; the lane has no width, so the champion is in the minions' path, and a valid target, while the waves are in contact, while it holds, or while it pushes; otherwise it has stepped aside, and a champion that has stepped aside hits nothing",
    "champion_stand": "a champion stands one melee range short of the enemy lead minion while the waves are in contact, and 550 short of it (outside minion acquisition range) once its own wave is gone; never inside enemy tower range plus 50; a mortal champion also never walks ahead of its own lead minion",
    "champion_hold": "a holding champion stands at the wave like any other while its own minions fight; with no minion of its own beyond the hold line it waits on that line, which stops the enemy lead minion 300 units outside its own tower range, and takes the wave attacks there until its next wave comes within acquisition range of the enemy minions, which then turn on the new wave by the ordinary targeting rule",
    "wave_span": "a wave is every minion within 1500 units of its team's lead minion, or of the front for the thin trigger",
    "crash": "a crash is a run of ticks with the blue lead minion inside the red tower's attack range, gaps under 5 s merged",
    "line": "front scalar: the contact point; out of contact, the lead minion of the team that has marched further from its spawn",
    "centre": "the lane centre is the midpoint of the two spawn points, where undisturbed waves meet",
    "perturbation": "S1b removes the last red caster of wave 1 before the waves meet",
    "slow_push": "S4c runs on the game's own wave clock from 0:00. From first contact, the blue plan starts at once; from a red crash, a red champion first pushes until its lead minion is in the blue tower's range and then leaves, while blue last-hits, and the blue plan starts at that moment. The run stops 20 s after the first blue minion enters the red tower's range, or 300 s after the plan starts. 'thin 3 once' thins while a red caster is in range, until the champion itself has killed three casters, and last-hits otherwise. 'thin casters' thins whenever a red caster is in range and last-hits otherwise",
    "slow_push_test": "a slow push emerged if some thinning plan reaches the red tower later than the push plan and with a median of 12 or more minions within 1500 units of its lead; this is the first round's test, unchanged",
    "built_state": "S5c starts at 180 s with full-health waves in contact 300 units outside the blue outer tower's range in top lane, surplus red casters on the red caster line, next waves on the normal clock. On the natural clock the blue wave spawned at 150 s would have reached this point at 176.8 s and the red one at 184.8 s, so the built state is within 5 s of a natural phase",
    "freeze_thin": "S5c thin over n: the holding champion thins while red minions within 1500 of the front outnumber blue ones by more than n, and last-hits otherwise",
    "freeze_trim": "S5c trim to m: with none of its own minions within 1500 of the front, the holding champion thins while more than m red minions are there, and last-hits otherwise",
    "freeze_test": "a freeze emerged if some surplus and holding plan keeps the front in the band for over half the run in every seed, neither control does in any seed, and the champion neither dies nor retreats in any seed",
    "fight": "S0 starts at 181 s at the top lane centre so that no reinforcement arrives within the 55 s window",
}


class Row(NamedTuple):
    t: float
    line: float | None
    lead_blue: float | None
    lead_red: float | None
    n_blue: int
    n_red: int
    contact: bool
    wave_blue: int


class Trace(NamedTuple):
    geometry: LaneGeometry
    rows: list[Row]
    events: list


def line(geometry: LaneGeometry, front: Front) -> float | None:
    if front.s is not None:
        return front.s
    blue, red = front.lead
    if blue is None or red is None:
        return blue if red is None else red
    marched = [abs(lead - geometry.spawn_s(team)) for team, lead in zip(Team, front.lead)]
    if abs(marched[0] - marched[1]) < 1.0:
        return (blue + red) / 2
    return blue if marched[0] > marched[1] else red


def crowd(sim, team: Team, s: float | None) -> int:
    return 0 if s is None else sum(n for spot, n in sim.units(team) if abs(spot - s) <= WAVE_SPAN)


def stand(sim, team: Team, hold: bool = False) -> float:
    geometry, front = sim.geometry, sim.front()
    heading = geometry.direction(team)
    own, foe = front.lead[team], front.lead[1 - team]
    if foe is not None:
        s = foe - heading * (MELEE_REACH if hold or front.s is not None else STAND_OFF)
    else:
        s = own if own is not None else geometry.tower_s[team]
    if hold:
        floor = geometry.tower_s[team] + heading * (TOWER_RANGE + BUILT_MARGIN - MELEE_REACH)
        s = max(s, floor) if heading > 0 else min(s, floor)
    edge = geometry.tower_s[1 - team] - heading * (TOWER_RANGE + TOWER_MARGIN)
    return min(s, edge) if heading > 0 else max(s, edge)


def laner(sim, team: Team, mode: Mode, capacity: float = 1.0, hold: bool = False) -> ChampionInput:
    return ChampionInput(int(team), team, stand(sim, team, hold), mode, capacity=capacity, targetable=True)


def post(sim, team: Team, hold: bool) -> float:
    """Where a mortal champion wants to stand: ASSUMPTIONS champion_stand, and champion_hold when it holds."""
    geometry, front = sim.geometry, sim.front()
    heading = geometry.direction(team)
    own, foe = front.lead[team], front.lead[1 - team]

    def beyond(a: float, b: float) -> bool:
        return heading * (a - b) > 0

    hold_line = geometry.tower_s[team] + heading * (TOWER_RANGE + BUILT_MARGIN - MELEE_REACH)
    if front.s is not None:
        s = foe - heading * MELEE_REACH
    elif hold:
        s = own if own is not None and beyond(own, hold_line) else hold_line
    elif foe is None:
        s = own if own is not None else geometry.tower_s[team]
    else:
        s = foe - heading * STAND_OFF
    if own is not None and beyond(s, own) and not (hold and front.s is None):
        s = own if beyond(own, geometry.tower_s[team]) else geometry.tower_s[team]
    edge = geometry.tower_s[1 - team] - heading * (TOWER_RANGE + TOWER_MARGIN)
    return min(s, edge) if heading > 0 else max(s, edge)


@dataclass
class Laner:
    """A champion with a position and health, per ASSUMPTIONS mortal_laner."""

    team: Team
    s: float
    hp: float = LANER_HP
    lowest: float = LANER_HP
    taken: float = 0.0
    tanked_s: float = 0.0
    retreats: int = 0
    retreating: bool = False
    dead: bool = False

    def act(self, sim, events, mode: Mode, hold: bool = False) -> list[ChampionInput]:
        if self.dead:
            return []
        hits = sum(e.damage for e in events if type(e) is ChampionDamage and e.champ_id == self.team) * 100 / (100 + LANER_ARMOR)
        self.taken += hits
        self.tanked_s += sim.dt * (hits > 0)
        self.hp = min(LANER_HP, self.hp - hits + LANER_REGEN * sim.dt)
        self.lowest = min(self.lowest, self.hp)
        if self.hp <= 0:
            self.dead = True
            return []
        if self.retreating:
            self.retreating = self.hp < RETURN_ABOVE * LANER_HP
        elif self.hp < RETREAT_BELOW * LANER_HP:
            self.retreating = True
            self.retreats += 1
        want = sim.geometry.tower_s[self.team] if self.retreating else post(sim, self.team, hold)
        step = LANER_SPEED * sim.dt
        self.s += max(-step, min(step, want - self.s))
        in_path = not self.retreating and (hold or mode is Mode.PUSH or sim.front().s is not None)
        return [ChampionInput(int(self.team), self.team, self.s, mode if in_path else Mode.NONE, targetable=in_path)]

    def report(self) -> dict:
        return {
            "champion_lowest_health": max(self.lowest, 0.0) / LANER_HP,
            "champion_damage": self.taken,
            "champion_tanked_s": self.tanked_s,
            "champion_retreats": self.retreats,
            "champion_died": self.dead,
        }


def run(sim, policy, until: float, stop=lambda row: False) -> Trace:
    rows, events, last = [], [], []
    while sim.time < until - 1e-9:
        last = sim.step(policy(sim, last))
        events += last
        front = sim.front()
        rows.append(Row(sim.time, line(sim.geometry, front), *front.lead, *front.counts, front.s is not None, crowd(sim, BLUE, front.lead[BLUE])))
        if stop(rows[-1]):
            break
    return Trace(sim.geometry, rows, events)


class SpawnOrderTies(LaneSim):
    """Control: co-located targets are chosen by spawn order instead of a keyed draw."""

    def _pick(self, m, tied):
        return tied[0]


def idle(sim, events):
    return ()


def last_hitters(blue_capacity: float = 1.0):
    return lambda sim, events: [laner(sim, BLUE, Mode.LAST_HIT, blue_capacity), laner(sim, RED, Mode.LAST_HIT)]


def one_red_caster_short():
    removed = []

    def policy(sim, events):
        casters = [m for m in sim.bodies[RED] if m.rules.kind is Kind.CASTER]
        if not removed and len(casters) == 3:
            sim.bodies[RED].remove(casters[-1])
            removed.append(sim.time)
        return ()

    return policy


class HardPush:
    """Blue pushes from first contact until its wave is under the red tower, then leaves. Red last-hits until then if present."""

    def __init__(self, red_present: bool):
        self.red_present = red_present
        self.met = False
        self.stopped_at = None

    def __call__(self, sim, events):
        front = sim.front()
        if self.stopped_at is not None:
            return []
        if under_tower(sim.geometry, RED, front.lead[BLUE]):
            self.stopped_at = sim.time
            return []
        self.met = self.met or front.s is not None
        inputs = [laner(sim, RED, Mode.LAST_HIT)] if self.red_present else []
        return inputs + [laner(sim, BLUE, Mode.PUSH)] if self.met else inputs


def under_tower(geometry: LaneGeometry, tower_team: Team, s: float | None) -> bool:
    return s is not None and abs(s - geometry.tower_s[tower_team]) <= TOWER_RANGE


def offset(geometry: LaneGeometry, s: float | None) -> float | None:
    """Distance past the lane centre toward red's side."""
    return None if s is None else geometry.direction(BLUE) * (s - geometry.centre)


def at(trace: Trace, t: float) -> Row | None:
    return next((r for r in trace.rows if r.t >= t - 1e-9), None)


def cs_fraction(events: list, team: Team, where=lambda death: True) -> float | None:
    deaths = [e for e in events if type(e) is MinionDeath and e.team is not team and where(e)]
    return sum(e.killer == team for e in deaths) / len(deaths) if deaths else None


def tower_damage(events: list, team: Team, start: float = 0.0, end: float = float("inf")) -> float:
    return sum(e.damage for e in events if type(e) is TowerDamage and e.team is team and start <= e.t <= end)


def crash_spans(trace: Trace) -> list[list[float]]:
    spans = []
    for r in trace.rows:
        if under_tower(trace.geometry, RED, r.lead_blue):
            if spans and r.t - spans[-1][1] <= CRASH_GAP_S:
                spans[-1][1] = r.t
            else:
                spans.append([r.t, r.t])
    return spans


def crash_metrics(trace: Trace, dt: float) -> dict:
    spans = crash_spans(trace)
    first = at(trace, spans[0][0]) if spans else None
    return {
        "crash_t": first.t if first else None,
        "crash_wave": first.wave_blue if first else None,
        "crashes": len(spans),
        "tower_damage_first_crash": tower_damage(trace.events, RED, spans[0][0] - dt, spans[0][1]) if spans else None,
    }


def waves_in_contact(make, seed, dt, start: float, front: float, red_melee: int = 0, red_casters: int = 0):
    sim = make(TOP, seed=seed, dt=dt, start_time=start)
    sim.add_minion(BLUE, Kind.MELEE, front - MELEE_REACH / 2, count=3)
    sim.add_minion(RED, Kind.MELEE, front + MELEE_REACH / 2, count=3 + red_melee)
    sim.add_minion(BLUE, Kind.CASTER, front + MELEE_REACH / 2 - CASTER_REACH, count=3)
    sim.add_minion(RED, Kind.CASTER, front - MELEE_REACH / 2 + CASTER_REACH, count=3 + red_casters)
    return sim


def fight(red_melee: int = 0, red_casters: int = 0):
    def case(make, seed, dt):
        sim = waves_in_contact(make, seed, dt, FIGHT_START_S, TOP.centre, red_melee, red_casters)
        left = [6, 6 + red_melee + red_casters]
        while min(left) > 0 and sim.time < FIGHT_START_S + FIGHT_LIMIT_S:
            sim.step()
            left = [crowd(sim, team, TOP.centre) for team in Team]
        return {"fight_s": sim.time - FIGHT_START_S, "blue_left": left[BLUE], "red_left": left[RED]}, None

    return case


def undisturbed(geometry: LaneGeometry):
    def case(make, seed, dt):
        trace = run(make(geometry, seed=seed, dt=dt), idle, 600.0)
        touch = next(r for r in trace.rows if r.contact)
        offsets = [offset(geometry, r.line) for r in trace.rows if r.t >= 120.0 and r.line is not None]
        damage = [tower_damage(trace.events, team) for team in Team]
        return {
            "first_contact_t": touch.t,
            "first_contact_s": touch.line,
            "offset_lo": min(offsets),
            "offset_hi": max(offsets),
            "blue_tower_damage": damage[BLUE],
            "red_tower_damage": damage[RED],
            "towers_untouched": max(damage) == 0,
        }, trace

    return case


def perturbed(geometry: LaneGeometry):
    def case(make, seed, dt):
        trace = run(make(geometry, seed=seed, dt=dt), one_red_caster_short(), 600.0)
        metrics = {f"offset_{mark}": offset(geometry, at(trace, mark).line) for mark in PERTURB_MARKS_S}
        reached = next((r for r in trace.rows if under_tower(geometry, RED, r.lead_blue)), None)
        metrics["red_tower_reached_t"] = reached.t if reached else None
        metrics["red_tower_reached_wave"] = reached.wave_blue if reached else None
        metrics["blue_tower_reached_t"] = next((r.t for r in trace.rows if under_tower(geometry, BLUE, r.lead_red)), None)
        metrics["blue_tower_damage"] = tower_damage(trace.events, BLUE)
        metrics["red_tower_damage"] = tower_damage(trace.events, RED)
        return metrics, trace

    return case


def last_hit(blue_capacity: float = 1.0):
    def case(make, seed, dt):
        trace = run(make(MID, seed=seed, dt=dt), last_hitters(blue_capacity), 600.0)
        offsets = [offset(MID, r.line) for r in trace.rows if r.t >= 120.0 and r.line is not None]
        return {"offset_lo": min(offsets), "offset_hi": max(offsets), "cs_blue": cs_fraction(trace.events, BLUE), "cs_red": cs_fraction(trace.events, RED)}, trace

    return case


def bounce(geometry: LaneGeometry, red_present: bool = False):
    def case(make, seed, dt):
        policy = HardPush(red_present)
        trace = run(make(geometry, seed=seed, dt=dt), policy, 600.0)
        metrics = crash_metrics(trace, dt)
        crash = metrics["crash_t"]
        for mark in BOUNCE_MARKS_S:
            row = at(trace, crash + mark) if crash is not None else None
            metrics[f"offset_{mark}"] = offset(geometry, row.line) if row else None
        after = [offset(geometry, r.line) for r in trace.rows if crash is not None and crash < r.t <= crash + BOUNCE_MARKS_S[-1] and r.contact]
        metrics["deepest_offset"] = min(after, default=None)
        metrics["bounced"] = bool(after) and min(after) < 0
        metrics["red_cs_under_tower"] = cs_fraction(trace.events, RED, lambda death: under_tower(geometry, RED, death.s))
        return metrics, trace

    return case


def slow_push(geometry: LaneGeometry, start: str, plan: str, red_last_hits: bool):
    def case(make, seed, dt):
        sim = make(geometry, seed=seed, dt=dt)
        blue = Laner(BLUE, geometry.tower_s[BLUE])
        began, crash, peak, met, casters = [], [], [0], [], [0]

        def policy(sim, events):
            front = sim.front()
            if front.s is not None and not met:
                met.append(sim.time)
            crashed_on_blue = under_tower(geometry, BLUE, front.lead[RED])
            if not began and met and (start == "first contact" or crashed_on_blue):
                began.append(sim.time)
            if not began:
                return blue.act(sim, events, Mode.LAST_HIT) + [laner(sim, RED, Mode.PUSH)] * (bool(met) and start == "red crash")
            casters[0] += sum(type(e) is MinionDeath and e.team is RED and e.kind is Kind.CASTER and e.killer == BLUE for e in events)
            caster_near = any(m.rules.kind is Kind.CASTER and abs(m.s - blue.s) <= 550.0 for m in sim.bodies[RED])
            mode = {
                "last hit": Mode.LAST_HIT,
                "push": Mode.PUSH,
                "thin 3 once": Mode.THIN if casters[0] < 3 and caster_near else Mode.LAST_HIT,
                "thin casters": Mode.THIN if caster_near else Mode.LAST_HIT,
            }[plan]
            return blue.act(sim, events, mode) + [laner(sim, RED, Mode.LAST_HIT)] * red_last_hits

        def stop(row: Row) -> bool:
            if not began:
                return False
            if not crash and under_tower(geometry, RED, row.lead_blue):
                crash.append(row)
            if crash:
                zone = geometry.tower_s[RED]
                peak[0] = max(peak[0], sum(n for spot, n in sim.units(BLUE) if abs(spot - zone) <= TOWER_RANGE + TOWER_ZONE))
            return row.t >= (crash[0].t + AFTER_CRASH_S if crash else began[0] + SLOW_PUSH_LIMIT_S)

        trace = run(sim, policy, 3600.0, stop)
        since = [r for r in trace.rows if began and r.t >= began[0] and (not crash or r.t <= crash[0].t)]
        return {
            "plan_start_t": began[0] if began else None,
            "crash_s": crash[0].t - began[0] if crash else None,
            "wave": crash[0].wave_blue if crash else None,
            "peak_at_tower": peak[0] if crash else None,
            "largest_wave": max((r.wave_blue for r in since), default=None),
            "gold": sum(e.gold for e in trace.events if type(e) is MinionDeath and e.killer == BLUE),
            **blue.report(),
        }, trace

    return case


def freeze(surplus: int, plan: str, thin_over: int | None = None, trim_to: int | None = None, breaker: bool = False):
    lo = TOP.tower_s[BLUE] + TOWER_RANGE
    hi = lo + FREEZE_BAND

    def case(make, seed, dt):
        sim = waves_in_contact(make, seed, dt, BUILT_START_S, lo + BUILT_MARGIN, red_casters=surplus)
        blue = Laner(BLUE, post(sim, BLUE, True))

        def policy(sim, events):
            inputs = []
            if plan == "push":
                inputs += blue.act(sim, events, Mode.PUSH)
            elif plan == "hold":
                front = line(sim.geometry, sim.front())
                red, own = crowd(sim, RED, front), crowd(sim, BLUE, front)
                thin = (thin_over is not None and red - own > thin_over) or (trim_to is not None and own == 0 and red > trim_to)
                mode = Mode.THIN if thin else Mode.LAST_HIT
                inputs += blue.act(sim, events, mode, hold=True)
            if breaker and sim.time >= BREAKER_ARRIVES_S:
                inputs.append(laner(sim, RED, Mode.PUSH))
            return inputs

        trace = run(sim, policy, BUILT_START_S + FREEZE_RUN_S)
        inside = [r.line is not None and lo <= r.line <= hi for r in trace.rows]
        metrics = {
            "band_s": sum(inside) * dt,
            **blue.report(),
            "cs_blue": cs_fraction(trace.events, BLUE),
            "under_tower_s": sum(under_tower(TOP, BLUE, r.lead_red) for r in trace.rows) * dt,
            "blue_tower_damage": tower_damage(trace.events, BLUE),
            "pushed_out": any(r.lead_blue is not None and r.lead_blue > TOP.centre for r in trace.rows),
        }
        if breaker:
            after = [ok for r, ok in zip(trace.rows, inside) if r.t > BREAKER_ARRIVES_S]
            metrics["band_s_after_breaker"] = sum(after) * dt
            metrics["red_tower_reached"] = any(under_tower(TOP, RED, r.lead_blue) for r in trace.rows)
        return metrics, trace

    return case


def tower_farm(capacity: float):
    def case(make, seed, dt):
        sim = make(MID, seed=seed, dt=dt, start_time=181.0)
        edge = MID.tower_s[BLUE] + TOWER_RANGE
        sim.add_minion(RED, Kind.MELEE, edge + 100.0, count=6)
        sim.add_minion(RED, Kind.CASTER, edge + 400.0, count=6)
        trace = run(sim, lambda sim, events: [laner(sim, BLUE, Mode.LAST_HIT, capacity)], 215.0)
        deaths = [e for e in trace.events if type(e) is MinionDeath and e.team is RED]
        return {"cs_blue": cs_fraction(trace.events, BLUE), "red_deaths": len(deaths)}, trace

    return case


CASES = {
    "S0 fight 6v6": fight(),
    "S0 fight 6v7 caster": fight(red_casters=1),
    "S0 fight 6v7 melee": fight(red_melee=1),
    "S0 fight 6v10 casters": fight(red_casters=4),
    "S1b undisturbed mid": undisturbed(MID),
    "S1b undisturbed top": undisturbed(TOP),
    "S1b one caster short mid": perturbed(MID),
    "S1b one caster short top": perturbed(TOP),
    "S2 last hit": last_hit(),
    "S3b bounce mid": bounce(MID),
    "S3b bounce top": bounce(TOP),
}
SLOW_PUSH_LANES = {"top": TOP, "mid": MID}
SLOW_PUSH_STARTS = ("first contact", "red crash")
SLOW_PUSH_PLANS = ("last hit", "push", "thin 3 once", "thin casters")
THIN_PLANS = ("thin 3 once", "thin casters")


def slow_push_name(lane: str, start: str, plan: str, red_last_hits: bool = False) -> str:
    return f"S4c {lane} from {start}, {plan}, red {'last hit' if red_last_hits else 'absent'}"


for lane_name, lane_shape in SLOW_PUSH_LANES.items():
    for start in SLOW_PUSH_STARTS:
        for plan in SLOW_PUSH_PLANS:
            for red_last_hits in (False, True):
                CASES[slow_push_name(lane_name, start, plan, red_last_hits)] = slow_push(lane_shape, start, plan, red_last_hits)
for k in FREEZE_SURPLUS:
    CASES[f"S5c k={k} hold"] = freeze(k, "hold")
    for n in THIN_OVER:
        CASES[f"S5c k={k} hold, thin over {n}"] = freeze(k, "hold", n)
    for m in TRIM_TO:
        CASES[f"S5c k={k} hold, trim to {m}"] = freeze(k, "hold", trim_to=m)
    CASES[f"S5c k={k} absent"] = freeze(k, "absent")
    CASES[f"S5c k={k} push"] = freeze(k, "push")
    CASES[f"S5c k={k} hold, red breaker"] = freeze(k, "hold", breaker=True)
for capacity in (0.5, 0.25):
    CASES[f"S6 last hit capacity {capacity}"] = last_hit(capacity)
for capacity in (1.0, 0.5, 0.25):
    CASES[f"S6 tower capacity {capacity}"] = tower_farm(capacity)

TICK_METRICS = (
    ("S1b undisturbed mid", "first_contact_t"),
    ("S1b one caster short top", "red_tower_reached_t"),
    ("S1b one caster short top", "red_tower_reached_wave"),
    ("S2 last hit", "cs_blue"),
    ("S3b bounce mid", "crash_t"),
    (slow_push_name("top", "first contact", "push"), "crash_s"),
    (slow_push_name("top", "first contact", "thin 3 once"), "crash_s"),
    (slow_push_name("top", "first contact", "thin 3 once"), "wave"),
    (slow_push_name("top", "red crash", "thin casters"), "crash_s"),
    (slow_push_name("top", "red crash", "thin casters"), "wave"),
    ("S5c k=3 hold", "band_s"),
    ("S5c k=3 hold", "champion_lowest_health"),
    ("S5c k=4 hold, thin over 3", "band_s"),
    ("S5c k=4 hold, thin over 3", "champion_lowest_health"),
    ("S5c k=6 hold", "band_s"),
    ("S5c k=4 absent", "band_s"),
    ("S5c k=4 push", "band_s"),
)
SERIES = (
    "S1b one caster short top",
    slow_push_name("top", "first contact", "thin 3 once"),
    slow_push_name("top", "red crash", "thin casters"),
    "S5c k=4 hold, thin over 3",
    "S5c k=4 absent",
)


def maker(mechanics: Mechanics):
    return partial(LaneSim, mechanics=mechanics)


def summarize(runs: list[dict]) -> dict:
    summary = {}
    for name in runs[0]:
        values = [float(m[name]) for m in runs if m[name] is not None]
        summary[name] = {
            "median": statistics.median(values) if values else None,
            "mean": statistics.mean(values) if values else None,
            "min": min(values, default=None),
            "max": max(values, default=None),
            "n": len(values),
        }
    return summary


def sampled(trace: Trace) -> list[list]:
    series, due = [], 0.0
    for r in trace.rows:
        if r.t >= due - 1e-9:
            spots = [None if s is None else round(s) for s in (r.line, r.lead_blue, r.lead_red)]
            series.append([r.t, *spots, r.n_blue, r.n_red])
            due = (r.t // SAMPLE_S + 1) * SAMPLE_S
    return series


def champion_plan(name: str) -> bool:
    return name.startswith(("S4c", "S5c"))


def measure(mechanics: Mechanics, names, dt: float) -> dict:
    make = maker(mechanics)
    return {name: summarize([CASES[name](make, seed, dt)[0] for seed in SEEDS]) for name in names}


def relative(reference: float | None, value: float | None) -> float | None:
    """Relative change, 0.0 when both are missing or both zero, None when it is undefined."""
    if reference is None or value is None:
        return 0.0 if reference is value else None
    if reference == 0:
        return 0.0 if value == 0 else None
    return (value - reference) / abs(reference)


def within(change: float | None) -> bool:
    return change is not None and abs(change) <= TOLERANCE


def tick_sensitivity(mechanics: Mechanics) -> dict:
    names = sorted({name for name, _ in TICK_METRICS})
    by_dt = {dt: measure(mechanics, names, dt) for dt in DTS}
    report = {}
    for name, metric in TICK_METRICS:
        reference = by_dt[REFERENCE_DT][name][metric]["median"]
        entry = {str(dt): by_dt[dt][name][metric]["median"] for dt in DTS}
        for dt in DTS:
            if dt != REFERENCE_DT:
                change = relative(reference, by_dt[dt][name][metric]["median"])
                entry[f"change_{dt}"] = change
                entry[f"within_{dt}"] = within(change)
        report[f"{name} / {metric}"] = entry
    return report


def cost(mechanics: Mechanics, runs: int = 7) -> dict:
    timed = []
    for seed in range(runs):
        sim, policy, last, spent, deaths = LaneSim(MID, seed=seed, dt=REPORT_DT, mechanics=mechanics), last_hitters(), [], 0, 0
        while sim.time < 600.0:
            inputs = policy(sim, last)
            started = time.perf_counter_ns()
            last = sim.step(inputs)
            spent += time.perf_counter_ns() - started
            deaths += sum(type(e) is MinionDeath for e in last)
        timed.append({"us_per_tick": spent / 1000 / sim.tick, "ticks": sim.tick, "deaths": deaths})
    micros = [r["us_per_tick"] for r in timed]
    return {"median_us": statistics.median(micros), "min_us": min(micros), "max_us": max(micros), "runs": timed}


def lane_verdict(cases: dict) -> dict:
    """stability: no undisturbed run damages a tower in 10 minutes. bounce: every run crosses back over the centre within 120 s of the crash."""
    lanes = ("mid", "top")
    untouched = statistics.mean(cases[f"S1b undisturbed {lane}"]["towers_untouched"]["mean"] for lane in lanes)
    bounced = statistics.mean(cases[f"S3b bounce {lane}"]["bounced"]["mean"] for lane in lanes)
    return {"stability": untouched == 1, "bounce": bounced == 1, "undisturbed_runs_with_towers_untouched": untouched, "runs_bounced": bounced}


def champion_plan_verdict(cases: dict) -> dict:
    """slow push: ASSUMPTIONS slow_push_test. freeze: ASSUMPTIONS freeze_test."""
    stacked, largest = {}, (0.0, None)
    for lane in SLOW_PUSH_LANES:
        for start in SLOW_PUSH_STARTS:
            for red_last_hits in (False, True):
                push = cases[slow_push_name(lane, start, "push", red_last_hits)]["crash_s"]["median"]
                for plan in THIN_PLANS:
                    name = slow_push_name(lane, start, plan, red_last_hits)
                    crash, wave = cases[name]["crash_s"]["median"], cases[name]["wave"]["median"]
                    if wave is None:
                        continue
                    largest = max(largest, (wave, name))
                    if push is not None and crash > push and wave >= SLOW_PUSH_STACK:
                        stacked[name] = wave
    held, held_by_an_immortal, best = {}, {}, (0.0, None)
    plans = ["hold"] + [f"hold, thin over {n}" for n in THIN_OVER] + [f"hold, trim to {m}" for m in TRIM_TO]
    for k in FREEZE_SURPLUS:
        controls = max(cases[f"S5c k={k} {control}"]["band_s"]["max"] for control in ("absent", "push"))
        for plan in plans:
            case = cases[f"S5c k={k} {plan}"]
            band = case["band_s"]
            best = max(best, (band["median"], f"k={k} {plan}"))
            if band["min"] > FREEZE_RUN_S / 2 > controls:
                held_by_an_immortal[f"k={k} {plan}"] = band["min"]
                if case["champion_died"]["max"] == 0 and case["champion_retreats"]["max"] == 0:
                    held[f"k={k} {plan}"] = band["min"]
    return {
        "slow_push": bool(stacked),
        "freeze": bool(held),
        "slow_push_cases": stacked,
        "largest_thinned_wave_at_red_tower": largest,
        "longest_hold": best,
        "freeze_cases": held,
        "freeze_cases_if_health_is_ignored": held_by_an_immortal,
    }


def rounded(value):
    if isinstance(value, float):
        return round(value, 3)
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [rounded(item) for item in value]
    return value


def show(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.0f}" if abs(value) >= 100 or value == int(value) else f"{value:.2f}"


def spread(summary: dict) -> str:
    return f"{show(summary['median'])} [{show(summary['min'])}..{show(summary['max'])}]"


def print_table(cases: dict) -> None:
    print(f"median [min..max] over seeds {SEEDS.start}..{SEEDS.stop - 1} at dt={REPORT_DT}")
    print(f"{'case / metric':<52}" + "".join(f"{name:<24}" for name in CONFIGS))
    for name in CASES:
        for metric in cases[RECOMMENDED_NAME][name]:
            print(f"{name + ' / ' + metric:<52}" + "".join(f"{spread(cases[config][name][metric]) if name in cases[config] else '':<24}" for config in CONFIGS))


def main() -> None:
    cases = {
        config: measure(mechanics, [name for name in CASES if config in CHAMPION_PLAN_CONFIGS or not champion_plan(name)], REPORT_DT)
        for config, mechanics in CONFIGS.items()
    }
    make = maker(RECOMMENDED)
    results = {
        "ruleset": RULES["meta"]["id"],
        "seeds": list(SEEDS),
        "dt": REPORT_DT,
        "assumptions": ASSUMPTIONS,
        "configs": {config: asdict(mechanics) for config, mechanics in CONFIGS.items()},
        "recommended": RECOMMENDED_NAME,
        "cases": cases,
        "emerged": {config: lane_verdict(cases[config]) | (champion_plan_verdict(cases[config]) if config in CHAMPION_PLAN_CONFIGS else {}) for config in CONFIGS},
        "S7b_tick_sensitivity": tick_sensitivity(RECOMMENDED),
        "S9b_cost": cost(RECOMMENDED),
        "series_columns": ["t", "line", "lead_blue", "lead_red", "n_blue", "n_red"],
        "series": {name: sampled(CASES[name](make, 0, REPORT_DT)[1]) for name in SERIES},
    }
    results["run"] = stamp(SEEDS, {"report_dt": REPORT_DT, "tick_sweep_dts": DTS, "reference_dt": REFERENCE_DT, "tolerance": TOLERANCE, "cases": len(CASES)})
    RESULTS.parent.mkdir(exist_ok=True)
    one_row_per_line = re.sub(r"\[[^\[\]]*\]|\{[^{}]*\}", lambda row: re.sub(r"\s+", " ", row.group()), json.dumps(rounded(results), indent=1))
    RESULTS.write_text(one_row_per_line, encoding="utf-8")
    print_table(cases)
    for config, verdict in results["emerged"].items():
        print(f"emerged {config}: " + ", ".join(f"{name}={value}" for name, value in verdict.items()))
    for key, entry in results["S7b_tick_sensitivity"].items():
        changes = ", ".join(f"dt={dt}: {show(entry[str(dt)])}" for dt in DTS)
        inside = ", ".join(f"{dt} {'within' if entry[f'within_{dt}'] else 'OUTSIDE'}" for dt in DTS if dt != REFERENCE_DT)
        print(f"S7b {key:<40}{changes}  ({inside} {TOLERANCE:.0%})")
    report = results["S9b_cost"]
    deaths = [r["deaths"] for r in report["runs"]]
    print(f"S9b {RECOMMENDED_NAME}: {report['median_us']:.1f} us/tick median of {len(deaths)} runs [{report['min_us']:.1f}..{report['max_us']:.1f}], deaths per run {min(deaths)}..{max(deaths)}")
    print(f"wrote {RESULTS} ({RESULTS.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
