"""Comparisons of alternatives from one scenario (M7 sections 9.2 to 9.4, checkpoint C8).

For each continuation, each line, and each rollout r, one world is built. A hypothesis line builds it with
`realize(info, hypothesis, r)` from the information state alone. The hindsight line restores the source world. The
world's seed is then set from the scenario seed and r. Every option starts from a copy of that world, so the
options of one (continuation, line, rollout) are paired. The baseline lets the continuation policies choose. An
alternative substitutes its actions at the decision tick and holds each (`KEEP`) for `commit_s` or until the intent
ends. Every other seat, and a seat after its hold, is played by its continuation policy from its observation alone.

The consequences of M7 section 9.4 are measured at the horizon for the deciding champion and its team, each apart.
None is ever combined with another into a score. `VERDICT_RULE` and `STABILITY_RULE` state how a report ranks.
The hindsight line is reported apart and never enters a weight, a verdict, a ranking, or the stability rule.
"""

import math
import pickle
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from multiprocessing import Pool
from statistics import NormalDist

from riftgame.champions import ACTIONS, FOUNTAIN, HOME, KEEP, NODE_POS, RIFT, Duty, Kind, capability_of, duty, level_of
from riftgame.combat import Kill
from riftgame.harness import Policy
from riftgame.hypotheses import realize
from riftgame.jungle import CampDeath
from riftgame.lanes import MinionDeath, TowerDamage, TowerDestroyed, TowerPlate
from riftgame.policies import STYLES, styled, team_policies
from riftgame.rng import Stream, keyed_u64, keyed_uniform
from riftgame.scenario import SEAT_NAMES, Alternative, Continuation, Decision, Scenario, spell
from riftgame.vision import legal_mask, observe_team
from riftgame.world import Config, World

HINDSIGHT = -1
ARRIVED = 300.0   # a champion this near a named place, by the straight line, has arrived there (Assumed)
ZERO = 1e-9       # a paired mean this small is no difference: sums in another order differ by rounding
NOTE = "These are simulator comparisons under stated policies and hypotheses, not calibrated advice or win probabilities."
FAMILY = 0.05    # the chance that two options with no difference at all differ clearly on some consequence of a line (Assumed)
VERDICT_RULE = ("Verdict rule. An option is better than another on a consequence when the paired mean difference lies beyond the "
                "threshold in the consequence's good direction, worse when it lies beyond it in the other, and unclear otherwise. "
                "The threshold is the two-sided Student t quantile, with one degree of freedom fewer than the rollouts, at the "
                "family level of 5 percent shared out over the consequences (Bonferroni), in standard errors. The weighted line "
                "weights the hypotheses' paired differences rollout by rollout, since a rollout's worlds share their seed, and "
                "takes the mean and standard error of those sums. An option dominates another when it is better on at least one "
                "consequence and worse on none, and the two trade off when it is better on one and worse on another. A line's "
                "ranking is a dominance when one option dominates every other option, a trade-off when some pair trades off, a "
                "partial order when some option dominates another and no pair trades off, and no clear ranking when no pair "
                "differs clearly on any consequence.")
STABILITY_RULE = ("Stability rule. A verdict, a relation to the baseline, or a ranking is stable only if it is the same on every "
                  "hypothesis line and the weighted line, under every continuation style, and at every research tick. Otherwise it is "
                  "uncertain, and the report names what it depends on. The hindsight line and the reference tick enter none of this.")


@dataclass(frozen=True, slots=True)
class Metric:
    """One consequence at the horizon. `better` is +1 when more is better and -1 when less is."""

    name: str
    scope: str
    better: int


CHAMPION = (Metric("gold earned", "champion", 1), Metric("xp earned", "champion", 1), Metric("level", "champion", 1),
            Metric("upgrades bought", "champion", 1), Metric("health share", "champion", 1), Metric("mana share", "champion", 1),
            Metric("deaths", "champion", -1), Metric("seconds absent", "champion", -1), Metric("kills", "champion", 1),
            Metric("minions killed", "champion", 1), Metric("minions missed", "champion", -1))
TEAM = (Metric("gold earned", "team", 1), Metric("xp earned", "team", 1), Metric("upgrades bought", "team", 1),
        Metric("health share", "team", 1), Metric("mana share", "team", 1), Metric("deaths", "team", -1),
        Metric("seconds absent", "team", -1), Metric("enemy deaths", "team", 1), Metric("minions killed", "team", 1),
        Metric("minions missed", "team", -1), Metric("tower damage dealt", "team", 1), Metric("tower damage taken", "team", -1),
        Metric("plates taken", "team", 1), Metric("plates lost", "team", -1), Metric("towers taken", "team", 1),
        Metric("towers lost", "team", -1), Metric("camps taken", "team", 1), Metric("camps taken by the enemy", "team", -1))
DEFINITIONS = {
    "seconds absent": "dead, recalling, or walking back: a laner under its duty RETURNING, a champion without a duty on its base edge",
    "minions killed": "enemy minions to whose killing blow the champion, or a champion of the team, was credited",
    "minions missed": "enemy minions that died in the champion's home lane without its killing blow (0 without a home lane), or anywhere without one from the team",
    "health share": "health over maximum health at the horizon, 0 when dead, a mean over the team",
    "arrival": f"seconds from the decision until the champion stands within {ARRIVED:g} units of the place, the horizon if never",
}


def metrics(decision: Decision) -> tuple[Metric, ...]:
    return (*CHAMPION, *(Metric(f"arrival {place}", "champion", -1) for place in decision.places), *TEAM)


def rollout_seed(seed: int, rollout: int) -> int:
    return keyed_u64(seed, rollout) >> 1


def reseed(world: World, seed: int) -> None:
    """Set the seed of a world and of its lanes, which keep their own."""
    world.seed = seed
    for sim in world.lanes.values():
        sim.seed = seed


def continuation_policies(continuation: Continuation, config: Config) -> tuple[Policy, ...]:
    """The policies of every seat under a continuation, for a game played on `config`'s clock."""
    decision_s = config.tick_s * config.decision_ticks
    return team_policies(blue=styled(STYLES[continuation.blue], decision_s), red=styled(STYLES[continuation.red], decision_s))


def _absent(world: World, c) -> bool:
    if c.hp <= 0 or ACTIONS[c.intent].kind is Kind.RECALL:
        return True
    state = duty(world, c)
    if state is not None:
        return state is Duty.RETURNING
    return c.pos.edge == FOUNTAIN[c.team].edge


class Tally:
    """The consequences of one continuation, counted tick by tick from the world and its events."""

    def __init__(self, world: World, decision: Decision):
        self.seat, self.team = decision.seat, decision.team
        self.start = world.tick
        self.lane = HOME[self.seat % 5]
        self.mates = range(self.team * 5, self.team * 5 + 5)
        self.earned = [sum(c.earned) for c in world.champions]
        self.xp = [c.xp for c in world.champions]
        self.upgrades = [c.upgrades for c in world.champions]
        self.places = [NODE_POS[self.team][place] for place in decision.places]
        self.arrival: list[float | None] = [None] * len(self.places)
        self.counts = defaultdict(float)

    def after(self, world: World) -> None:
        seat, team, counts, dt = self.seat, self.team, self.counts, world.config.tick_s
        for source, e in world.events:
            kind = type(e)
            if kind is Kill:
                ours = e.victim // 5 == team
                counts["team deaths" if ours else "team enemy deaths"] += 1
                counts["deaths"] += e.victim == seat
                counts["kills"] += e.killer == seat
            elif kind is MinionDeath:
                if e.team == team:
                    continue
                credited = e.killer is not None and e.killer // 5 == team
                counts["team minions killed" if credited else "team minions missed"] += 1
                counts["minions killed"] += e.killer == seat
                counts["minions missed"] += source == self.lane and e.killer != seat
            elif kind is TowerDamage:
                counts["team tower damage taken" if e.team == team else "team tower damage dealt"] += e.damage
            elif kind is TowerPlate:
                counts["team plates lost" if e.team == team else "team plates taken"] += 1
            elif kind is TowerDestroyed:
                counts["team towers lost" if e.team == team else "team towers taken"] += 1
            elif kind is CampDeath:
                counts["team camps taken" if e.killer // 5 == team else "team camps taken by the enemy"] += 1
        for s in self.mates:
            if _absent(world, world.champions[s]):
                counts["team seconds absent"] += dt
                counts["seconds absent"] += dt * (s == seat)
        me = world.champions[seat]
        for i, place in enumerate(self.places):
            if self.arrival[i] is None and RIFT.separation(me.pos, place) <= ARRIVED:
                self.arrival[i] = (world.tick - self.start) * dt

    def vector(self, world: World, horizon_s: float) -> tuple[float, ...]:
        """The consequences in the order of `metrics`."""
        def share(c, field: str, most: str) -> float:
            return 0.0 if c.hp <= 0 else getattr(c, field) / getattr(capability_of(c), most)

        seat, counts, mates = self.seat, self.counts, [world.champions[s] for s in self.mates]
        me = world.champions[seat]
        mine = (sum(me.earned) - self.earned[seat], me.xp - self.xp[seat], level_of(me.xp), me.upgrades - self.upgrades[seat],
                share(me, "hp", "max_hp"), share(me, "mana", "max_mana"), counts["deaths"], counts["seconds absent"], counts["kills"],
                counts["minions killed"], counts["minions missed"] if self.lane is not None else 0.0,
                *(horizon_s if t is None else t for t in self.arrival))
        team = (sum(sum(c.earned) - self.earned[c.seat] for c in mates), sum(c.xp - self.xp[c.seat] for c in mates),
                sum(c.upgrades - self.upgrades[c.seat] for c in mates), sum(share(c, "hp", "max_hp") for c in mates) / 5,
                sum(share(c, "mana", "max_mana") for c in mates) / 5, counts["team deaths"], counts["team seconds absent"],
                counts["team enemy deaths"], counts["team minions killed"], counts["team minions missed"], counts["team tower damage dealt"],
                counts["team tower damage taken"], counts["team plates taken"], counts["team plates lost"], counts["team towers taken"],
                counts["team towers lost"], counts["team camps taken"], counts["team camps taken by the enemy"])
        return tuple(float(v) for v in (*mine, *team))


def play(world: World, policies: Sequence[Policy], option: Alternative, decision: Decision, log: list | None = None) -> tuple[float, ...]:
    """Continue `world` from the decision tick to the horizon under one option, and return its consequences.

    At the decision tick the option's seats get its actions and every other seat its policy's choice. Until the
    commit time ends, a held seat keeps its action while its intent is still that action and KEEP is legal. Every
    other choice is the seat's policy on its observation and the keyed noise. `log`, when given, receives the
    (tick, observations, actions) of every decision tick.
    """
    config = world.config
    held = dict(option.actions)
    start, commit = world.tick, config.ticks(decision.commit_s)
    tally = Tally(world, decision)
    for _ in range(config.ticks(decision.horizon_s)):
        actions = None
        if world.tick % config.decision_ticks == 0:
            observations = (*observe_team(world, 0), *observe_team(world, 1))
            actions = [act(o, keyed_uniform(world.seed, Stream.POLICY, seat, world.tick)) for seat, (act, o) in enumerate(zip(policies, observations, strict=True))]
            for seat in list(held):
                if world.tick == start:
                    actions[seat] = held[seat]
                elif world.tick - start < commit and world.champions[seat].intent == held[seat] and legal_mask(observations[seat])[KEEP]:
                    actions[seat] = KEEP
                else:
                    del held[seat]
            if log is not None:
                log.append((world.tick, observations, tuple(actions)))
        world.step(actions)
        tally.after(world)
    return tally.vector(world, decision.horizon_s)


def line_world(scenario: Scenario, line: int, rollout: int) -> World:
    """The world from which every option of one line and rollout starts. Only the hindsight line reads the source."""
    if line == HINDSIGHT:
        world = World.restore(scenario.hindsight)
    else:
        world = realize(scenario.info, scenario.hypotheses[line], rollout)
    reseed(world, rollout_seed(scenario.meta.seed, rollout))
    return world


def rollouts(scenario: Scenario, continuation: int, line: int, rollout: int) -> tuple[tuple[tuple[float, ...], ...], tuple[int, ...]]:
    """The consequences of every option on one world, and the actions that the baseline chose at the decision tick
    for the seats that the alternatives name."""
    decision = scenario.decision
    policies = continuation_policies(decision.continuations[continuation], scenario.meta.config)
    snapshot = line_world(scenario, line, rollout).snapshot()
    seats = sorted({seat for a in decision.alternatives for seat, _ in a.actions})
    out, chosen = [], ()
    for option in decision.options():
        log = [] if not option.actions else None
        out.append(play(World.restore(snapshot), policies, option, decision, log))
        if log is not None:
            chosen = tuple(log[0][2][seat] for seat in seats)
    return tuple(out), chosen


_SCENARIO: Scenario | None = None


def _init(blob: bytes) -> None:
    global _SCENARIO
    _SCENARIO = pickle.loads(blob)


def _task(key: tuple[int, int, int]):
    return rollouts(_SCENARIO, *key)


def _paired(values: Sequence[Sequence[float]], a: int, b: int, k: int) -> tuple[float, float]:
    """The mean of option a less option b on consequence k over the rollouts, and its standard error."""
    diffs = [row[a][k] - row[b][k] for row in values]
    n = len(diffs)
    mean = sum(diffs) / n
    var = sum((d - mean) ** 2 for d in diffs) / (n - 1)
    return mean, math.sqrt(var / n)


def _within(t: float, df: int) -> float:
    """The chance that a Student t variable with `df` degrees of freedom lies within t of zero (Abramowitz and
    Stegun 26.7.3 and 26.7.4)."""
    theta = math.atan(t / math.sqrt(df))
    s, c = math.sin(theta), math.cos(theta)
    if df % 2:
        term, total = c, 0.0
        for k in range(1, (df - 1) // 2 + 1):
            total += term
            term *= c * c * 2 * k / (2 * k + 1)
        return 2 / math.pi * (theta + s * total)
    term, total = 1.0, 0.0
    for k in range(1, df // 2 + 1):
        total += term
        term *= c * c * (2 * k - 1) / (2 * k)
    return s * total


def threshold(consequences: int, rollouts: int) -> float:
    """The standard errors beyond which a paired mean is clear (`VERDICT_RULE`)."""
    df, tail = rollouts - 1, FAMILY / consequences
    lo, hi = NormalDist().inv_cdf(1 - tail / 2), 1e9
    for _ in range(200):
        mid = math.sqrt(lo * hi)
        lo, hi = (mid, hi) if 1 - _within(mid, df) > tail else (lo, mid)
    return hi


def verdict(mean: float, se: float, better: int, z: float) -> str:
    if abs(mean) <= ZERO:
        return "unclear"
    if mean * better > z * se:
        return "better"
    if -mean * better > z * se:
        return "worse"
    return "unclear"


def relation(verdicts: Sequence[str]) -> str:
    """How an option stands against another from its verdicts on every consequence."""
    better, worse = "better" in verdicts, "worse" in verdicts
    if better and not worse:
        return "dominates"
    if worse and not better:
        return "dominated"
    return "trades off" if better else "no clear difference"


def ranking(names: Sequence[str], pairs: dict[tuple[int, int], list[str]]) -> dict:
    """The ranking of a line from the verdicts of every ordered pair of options."""
    dominates = sorted((names[a], names[b]) for (a, b), v in pairs.items() if relation(v) == "dominates")
    top = [a for a in range(len(names)) if all(relation(pairs[a, b]) == "dominates" for b in range(len(names)) if b != a)]
    crossed = any(relation(v) == "trades off" for v in pairs.values())
    outcome = f"{names[top[0]]} dominates" if top else "trade-off" if crossed else "partial order" if dominates else "no clear ranking"
    return {"outcome": outcome, "dominance": [f"{a} dominates {b}" for a, b in dominates]}


def _line(stats: dict[tuple[int, int, int], tuple[float, float]], names: Sequence[str], table: Sequence[Metric], z: float) -> dict:
    """A line's verdicts against the baseline, relations, and ranking, from paired (mean, se) of every ordered pair."""
    n = len(names)
    pairs = {(a, b): [verdict(*stats[a, b, k], m.better, z) for k, m in enumerate(table)] for a in range(n) for b in range(n) if a != b}
    alternatives = {}
    for a in range(1, n):
        alternatives[names[a]] = {
            "relation": relation(pairs[a, 0]),
            "metrics": {f"{m.scope} {m.name}": {"mean": stats[a, 0, k][0], "se": stats[a, 0, k][1], "verdict": pairs[a, 0][k]}
                        for k, m in enumerate(table)}}
    return {"alternatives": alternatives, "ranking": ranking(names, pairs)}


def run(scenario: Scenario, workers: int = 1) -> dict:
    """The comparison of a scenario's options, as plain data in a fixed order. Equal with any number of workers."""
    decision = scenario.decision
    table = metrics(decision)
    options = decision.options()
    names = [o.name for o in options]
    lines = [*range(len(scenario.hypotheses)), *([HINDSIGHT] if scenario.hindsight is not None else [])]
    keys = [(c, line, r) for c in range(len(decision.continuations)) for line in lines for r in range(decision.rollouts)]
    if workers > 1:
        with Pool(workers, initializer=_init, initargs=(pickle.dumps(scenario),)) as pool:
            results = pool.map(_task, keys, chunksize=1)
    else:
        results = [rollouts(scenario, *key) for key in keys]
    found = dict(zip(keys, results))
    weights = [h.weight for h in scenario.hypotheses]
    z = threshold(len(table), decision.rollouts)
    pairs = [(a, b) for a in range(len(options)) for b in range(len(options)) if a != b]
    seats = sorted({seat for a in decision.alternatives for seat, _ in a.actions})
    out, hindsight, chosen = {}, {}, {}
    for c, continuation in enumerate(decision.continuations):
        per = {}
        label = continuation.label()
        rows = sorted({found[c, line, r][1] for line in lines if line != HINDSIGHT for r in range(decision.rollouts)})
        chosen[label] = [{SEAT_NAMES[seat]: spell(action) for seat, action in zip(seats, row)} for row in rows]
        for line in lines:
            values = [found[c, line, r][0] for r in range(decision.rollouts)]
            per[line] = {(a, b, k): _paired(values, a, b, k) for a, b in pairs for k in range(len(table))}
        out[label] = {scenario.hypotheses[line].name: _line(per[line], names, table, z) for line in lines if line != HINDSIGHT}
        by_hypothesis = [[found[c, h, r][0] for r in range(decision.rollouts)] for h in range(len(weights))]
        out[label]["weighted"] = _line(_weighted(by_hypothesis, weights, pairs, len(table)), names, table, z)
        if HINDSIGHT in per:
            hindsight[label] = _line(per[HINDSIGHT], names, table, z)
    return {"scenario": describe(scenario), "metrics": [{"name": m.name, "scope": m.scope, "better": m.better} for m in table],
            "baseline chose": chosen, "lines": out, "hindsight": hindsight}


def _weighted(values: Sequence[Sequence[Sequence[Sequence[float]]]], weights: Sequence[float], pairs, consequences: int) -> dict:
    """The weighted line's paired (mean, se) of every ordered pair and consequence, from each hypothesis's consequences
    by rollout and option. A rollout's worlds share their seed, so the hypotheses' differences are weighted within each
    rollout, and the standard error comes from those sums."""
    rollouts, options = len(values[0]), len(values[0][0])
    combined = [[[sum(w * line[r][o][k] for w, line in zip(weights, values, strict=True)) for k in range(consequences)]
                 for o in range(options)] for r in range(rollouts)]
    return {(a, b, k): _paired(combined, a, b, k) for a, b in pairs for k in range(consequences)}


def describe(scenario: Scenario) -> dict:
    """What a report states about a scenario. Nothing here reads the source world."""
    meta, decision = scenario.meta, scenario.decision
    return {
        "ruleset": meta.ruleset_id, "map": meta.map_id, "tick_s": meta.config.tick_s, "base_tick_s": meta.base_tick_s,
        "decision_s": meta.config.tick_s * meta.config.decision_ticks, "decision_at_s": meta.tick * meta.config.tick_s,
        "seed": meta.seed, "code": meta.code, "info_digest": scenario.info.digest(),
        "seat": SEAT_NAMES[decision.seat], "kind": decision.kind, "label": "team plan" if decision.kind == "coordinated" else "individual",
        "horizon_s": decision.horizon_s, "commit_s": decision.commit_s, "rollouts": decision.rollouts,
        "consequences": len(metrics(decision)), "threshold_se": threshold(len(metrics(decision)), decision.rollouts),
        "generator": "activity_v0" if decision.hidden == "activity_v0" else "explicit hypotheses, gaps from activity_v0",
        "hidden_enemies": scenario.hidden_enemies,
        "continuations": [c.label() for c in decision.continuations],
        "alternatives": {a.name: {SEAT_NAMES[seat]: spell(action) for seat, action in a.actions} for a in decision.alternatives},
        "hypotheses": [{"name": h.name, "weight": h.weight} for h in scenario.hypotheses],
        "rejected": [list(row) for row in scenario.rejected],
        "places": list(decision.places),
    }


def _cells(comparisons: Sequence[dict], pick) -> dict[tuple[str, float, str], str]:
    """One value per (continuation, tick, line) of every comparison of a recipe, the weighted line included. A line
    that one comparison has and another lacks is "absent" in the other, which no present value equals."""
    cells = {(label, comparison["scenario"]["tick_s"], name): pick(line)
             for comparison in comparisons for label, lines in comparison["lines"].items() for name, line in lines.items()}
    ticks = sorted({comparison["scenario"]["tick_s"] for comparison in comparisons})
    named = sorted({(label, name) for label, _, name in cells})
    return {(label, tick, name): cells.get((label, tick, name), "absent") for label, name in named for tick in ticks}


def depends(cells: dict[tuple[str, float, str], str]) -> list[str]:
    """The factors that change a value: the hypothesis at one continuation and tick, the continuation at one tick
    and line, the tick at one continuation and line."""
    found = []
    for factor, i in (("hypothesis", 2), ("style", 0), ("tick", 1)):
        groups = defaultdict(set)
        for key, value in cells.items():
            groups[key[:i] + key[i + 1:]].add(value)
        if any(len(values) > 1 for values in groups.values()):
            found.append(factor)
    return found


def _stable(cells: dict[tuple[str, float, str], str]) -> dict:
    values = sorted(set(cells.values()))
    if len(values) == 1:
        return {"stable": True, "value": values[0]}
    factors = depends(cells)
    by = {f"{label}, tick {tick:g} s, {name}": value for (label, tick, name), value in sorted(cells.items())}
    return {"stable": False, "value": "uncertain", "depends on": factors or ["the combination of hypothesis, style, and tick"], "values": by}


def summarise(comparisons: Sequence[dict]) -> dict:
    """The stability of every ranking, relation, and verdict over the comparisons of one recipe at its ticks."""
    first = comparisons[0]
    alternatives = list(first["scenario"]["alternatives"])
    keys = [f"{m['scope']} {m['name']}" for m in first["metrics"]]
    return {
        "ranking": _stable(_cells(comparisons, lambda line: line["ranking"]["outcome"])),
        "relations": {a: _stable(_cells(comparisons, lambda line, a=a: line["alternatives"][a]["relation"])) for a in alternatives},
        "verdicts": {a: {k: _stable(_cells(comparisons, lambda line, a=a, k=k: line["alternatives"][a]["metrics"][k]["verdict"])) for k in keys}
                     for a in alternatives},
    }


def agreement(research: dict, reference: dict) -> dict:
    """Whether a comparison at a reference tick ranks as one at the research tick does, line by line: the ranking,
    and each alternative's relation to the baseline. A line that the reference lacks counts as a difference."""
    differ, rankings, relations, same_rankings, same_relations = {}, 0, 0, 0, 0
    for label, lines in research["lines"].items():
        for name, line in lines.items():
            other = reference["lines"].get(label, {}).get(name)
            cell = f"{label}, {name}"
            mine, theirs = line["ranking"]["outcome"], "absent" if other is None else other["ranking"]["outcome"]
            rankings += 1
            same_rankings += mine == theirs
            if mine != theirs:
                differ[f"{cell}, ranking"] = [mine, theirs]
            for a, entry in line["alternatives"].items():
                there = "absent" if other is None else other["alternatives"][a]["relation"]
                relations += 1
                same_relations += entry["relation"] == there
                if entry["relation"] != there:
                    differ[f"{cell}, {a}"] = [entry["relation"], there]
    return {"research_tick_s": research["scenario"]["tick_s"], "reference_tick_s": reference["scenario"]["tick_s"],
            "rankings": rankings, "rankings agree": same_rankings, "relations": relations, "relations agree": same_relations,
            "differ": differ}


def style_notes() -> dict[str, str]:
    """Each style by how it differs from the standard one, field by field."""
    standard = STYLES["standard"]
    notes = {}
    for name, style in STYLES.items():
        if name == "scripted_v0":
            continue
        changed = [f"{f} {getattr(style, f)!r} (standard {getattr(standard, f)!r})" for f in style.__dataclass_fields__
                   if f != "name" and getattr(style, f) != getattr(standard, f)]
        notes[name] = "; ".join(changed) or f"the C7 thresholds, tower rule {'on' if style.tower_rule else 'off'}"
    return notes


def _signed(mean: float, se: float) -> str:
    return f"{mean:+.3g} ± {se:.2g}"


def _clear(line: dict, every: bool = False) -> list[str]:
    """The consequences on which each alternative differs clearly from the baseline on one line, or with `every`
    each one whose paired mean is not zero."""
    rows = []
    for name, a in line["alternatives"].items():
        clear = [f"{k} {_signed(m['mean'], m['se'])} {m['verdict']}" for k, m in a["metrics"].items()
                 if m["verdict"] != "unclear" or (every and abs(m["mean"]) > ZERO)]
        rows.append(f"      {name}: {a['relation']}" + (f"; {'; '.join(clear)}" if clear else ""))
    return rows


def _outcome(line: dict) -> str:
    ranking = line["ranking"]
    return ranking["outcome"] + (f" ({'; '.join(ranking['dominance'])})" if ranking["dominance"] else "")


def _uncertain(entry: dict, indent: str) -> list[str]:
    if entry["stable"]:
        return [f"{indent}stable: {entry['value']}"]
    lines = [f"{indent}uncertain, depends on {', '.join(entry['depends on'])}:"]
    groups = defaultdict(list)
    for where, value in entry["values"].items():
        groups[value].append(where)
    for value, wheres in sorted(groups.items()):
        lines.append(f"{indent}  {value}: {'; '.join(wheres)}")
    return lines


def report(name: str, comparisons: Sequence[dict], stability: dict, hindsight: bool = True, reference: dict | None = None) -> str:
    """The text report of one recipe at its research ticks. With `hindsight` it ends with the hindsight lines, apart.
    `reference` holds a comparison at a reference tick and its `agreement` with the research tick, reported apart."""
    first = comparisons[0]["scenario"]
    ticks = [c["scenario"]["tick_s"] for c in comparisons] + ([reference["comparison"]["scenario"]["tick_s"]] if reference else [])
    out = [f"== {name}: {first['seat']}, {first['label']} ==",
           f"  {NOTE}",
           f"  Ruleset {first['ruleset']} on {first['map']}. One decision state: the base game and the overrides run once at "
           f"{first['base_tick_s']:g} s, and that state is compared at {', '.join(f'{t:g} s' for t in ticks)}, refined to each "
           f"tick finer than {first['base_tick_s']:g} s. A decision every {first['decision_s']:g} s.",
           f"  Horizon {first['horizon_s']:g} s, commit {first['commit_s']:g} s, {first['rollouts']} rollouts per line, "
           f"continuations: {', '.join(first['continuations'])}.",
           f"  A paired difference is clear beyond {first['threshold_se']:.2f} standard errors: {first['consequences']} consequences "
           f"at a family level of {FAMILY:.0%}, {first['rollouts'] - 1} degrees of freedom.",
           f"  Alternatives: {'; '.join(f'{a} ({', '.join(f'{s} {v}' for s, v in acts.items())})' for a, acts in first['alternatives'].items())}."]
    for c in comparisons:
        s = c["scenario"]
        hyps = ", ".join(f"{h['name']} ({h['weight']:.3g})" for h in s["hypotheses"])
        rejected = "; ".join(f"{n}: {r}" for n, r in s["rejected"]) or "none"
        chose = "; ".join(f"{label} " + " or ".join(", ".join(f"{seat} {action}" for seat, action in row.items()) for row in rows)
                          for label, rows in c["baseline chose"].items())
        out += [f"  Tick {s['tick_s']:g} s: decision at {s['decision_at_s']:g} s, {s['hidden_enemies']} hidden enemy champions, "
                f"generator {s['generator']}. The baseline chose, by style: {chose}.",
                f"    Hypotheses and weights: {hyps}.", f"    Rejected by the checks: {rejected}."]
        if len(s["hypotheses"]) == 1:
            out.append("    One hypothesis: the stability rule does not vary the hidden state here.")
    out.append("  Ranking:")
    out += _uncertain(stability["ranking"], "    ")
    out.append("  Relation of each alternative to the baseline:")
    for a, entry in stability["relations"].items():
        out.append(f"    {a}:")
        out += _uncertain(entry, "      ")
    out.append("  Verdicts against the baseline, consequence by consequence, over every hypothesis, style, and tick:")
    for a, verdicts in stability["verdicts"].items():
        groups = defaultdict(list)
        for k, entry in verdicts.items():
            if not entry["stable"]:
                groups[f"uncertain, depends on {', '.join(entry['depends on'])}"].append(k)
            elif entry["value"] != "unclear":
                groups[f"always {entry['value']}"].append(k)
        out.append(f"    {a}:")
        out += [f"      {group}: {', '.join(keys)}" for group, keys in sorted(groups.items())] or ["      unclear on every consequence"]
    out.append("  Weighted lines, with the clear differences from the baseline (paired mean ± se):")
    for c in comparisons:
        for label, lines in c["lines"].items():
            out.append(f"    tick {c['scenario']['tick_s']:g} s, {label}: {_outcome(lines['weighted'])}")
            out += _clear(lines["weighted"])
    if reference:
        agree, c = reference["agreement"], reference["comparison"]
        same = "agrees" if agree["rankings agree"] == agree["rankings"] else "differs"
        out.append(f"  Reference tick {agree['reference_tick_s']:g} s (apart from the stability rule): the ranking at {agree['research_tick_s']:g} s "
                   f"{same}. It agrees on {agree['rankings agree']} of {agree['rankings']} lines, and on {agree['relations agree']} of "
                   f"{agree['relations']} relations to the baseline.")
        out += [f"    {where}: {mine} at {agree['research_tick_s']:g} s, {theirs} at {agree['reference_tick_s']:g} s"
                for where, (mine, theirs) in agree["differ"].items()]
        for label, lines in c["lines"].items():
            out.append(f"    tick {c['scenario']['tick_s']:g} s, {label}: {_outcome(lines['weighted'])}")
            out += _clear(lines["weighted"])
    if hindsight:
        out.append("  Hindsight (the source world; apart from every weight, verdict, ranking, and stability; every nonzero paired mean):")
        for c in [*comparisons, *([reference["comparison"]] if reference else [])]:
            for label, line in c["hindsight"].items():
                out.append(f"    tick {c['scenario']['tick_s']:g} s, {label}: {_outcome(line)}")
                out += _clear(line, every=True)
    return "\n".join(out)
