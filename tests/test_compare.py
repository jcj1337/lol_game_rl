"""C8: the comparison harness, its report, and the two continuation styles (M7 sections 9.2 to 9.4)."""

import dataclasses
import json
import random
from statistics import NormalDist
from functools import cache

import pytest

from riftgame.champions import ACTIONS, KEEP, LANES, RIFT, Kind, capability, capability_of, homeguard_bonus
from riftgame.compare import (NOTE, _weighted, agreement, continuation_policies, line_world, metrics, play, ranking, relation, report,
                              run, summarise, threshold, verdict)
from riftgame.harness import record, tick
from riftgame.lanes import RULESET_ID, TOWER_RANGE
from riftgame.policies import AGGRESSIVE, C7, STANDARD, policy, styled, team_policies
from riftgame.rng import Stream, keyed_uniform
from riftgame.scenario import Scenario, base_world, build, load, parse
from riftgame.vision import Observation, legal_mask, observe_team, to_frame
from riftgame.world import Config, World
from test_vision import scramble

# The clock of C7, which the C7 pins and the tower counts were taken on. The default clock may differ.
HALF = Config(tick_s=0.5, decision_ticks=4)

RECIPE = f"""
ruleset = "{RULESET_ID}"
seed = 5
tick_s = 0.5
base = {{ policy = "scripted_v0", seed = 6, until_s = 480 }}

[[champion]]
seat = "blue_top"
health = 0.7

[decision]
seat = "blue_top"
kind = "individual"
horizon_s = 24
commit_s = 12
rollouts = 2
hidden = "activity_v0"
places = ["own_top_t1"]
continuation = [{{ blue = "standard", red = "standard" }}, {{ blue = "aggressive", red = "aggressive" }}]
alternatives = ["LANE top push wave", "LANE top last_hit hold", "RECALL"]
"""
PLAN = RECIPE.replace('kind = "individual"', 'kind = "coordinated"').replace(
    'alternatives = ["LANE top push wave", "LANE top last_hit hold", "RECALL"]',
    'alternatives = [{ name = "top shoves, jungle walks top", blue_top = "LANE top push wave", blue_jungle = "MOVE top_corner" },'
    ' { name = "both recall", blue_top = "RECALL", blue_jungle = "RECALL" }]')


@cache
def individual() -> Scenario:
    return load(RECIPE)


@cache
def compared() -> dict:
    return run(individual())


def text(comparison: dict) -> str:
    return json.dumps(comparison, indent=1)


def test_a_comparison_rerun_gives_byte_identical_output_with_workers_and_without():
    again = run(load(RECIPE))
    assert text(again) == text(compared())
    assert text(run(individual(), workers=2)) == text(compared())


def without_hindsight(comparison: dict) -> dict:
    return {key: value for key, value in comparison.items() if key != "hindsight"}


def numbers(tree) -> list[float]:
    if isinstance(tree, dict):
        return [x for key in sorted(tree) for x in numbers(tree[key])]
    return [float(tree)] if isinstance(tree, (int, float)) and not isinstance(tree, bool) else []


# Over 24 s the hidden change below reaches nothing of blue's. Over 60 s it moves the minions that blue's team misses.
BLIND = RECIPE.replace("horizon_s = 24", "horizon_s = 60").replace(
    'continuation = [{ blue = "standard", red = "standard" }, { blue = "aggressive", red = "aggressive" }]', 'continuation = { blue = "standard", red = "standard" }')


def test_changing_every_field_hidden_from_the_deciding_team_changes_the_hindsight_line_and_nothing_else_in_the_report():
    recipe = parse(BLIND)
    source = base_world(recipe)
    twin = World.restore(source.snapshot())
    changed = scramble(twin, 0, random.Random(8))
    assert changed["champions"] and changed["camps"] and twin.digest() != source.digest()
    a, b = build(recipe, source), build(parse(BLIND), twin)
    assert a.info.digest() == b.info.digest() and a.hypotheses == b.hypotheses
    ra, rb = run(a), run(b)
    assert text(without_hindsight(ra)) == text(without_hindsight(rb))
    moved = max(abs(x - y) for x, y in zip(numbers(ra["hindsight"]), numbers(rb["hindsight"])))
    assert moved > 0.1, "the hindsight line runs from the source world, so it sees the change"
    first, second = ("blind", [ra], summarise([ra])), ("blind", [rb], summarise([rb]))
    assert report(*first, hindsight=False) == report(*second, hindsight=False)
    assert report(*first) != report(*second)


def test_the_comparison_lines_never_read_the_source_world():
    blind = dataclasses.replace(individual(), hindsight=None)
    out = run(blind)
    assert out["hindsight"] == {} and out["lines"] == compared()["lines"]


def decisions(scenario: Scenario, option, line: int = 0, rollout: int = 0, spy: list | None = None) -> list:
    decision = scenario.decision
    policies = continuation_policies(decision.continuations[0], scenario.meta.config)
    if spy is not None:
        def watched(act):
            def seen(o, noise):
                spy.append((o, noise))
                return act(o, noise)
            return seen
        policies = tuple(watched(act) for act in policies)
    log = []
    play(line_world(scenario, line, rollout), policies, option, decision, log)
    return log


def test_an_individual_alternative_changes_one_seat_at_the_decision_tick_and_every_other_choice_is_a_policys():
    s = individual()
    d = s.decision
    policies = continuation_policies(d.continuations[0], s.meta.config)
    baseline = decisions(s, d.options()[0])
    seed = line_world(s, 0, 0).seed
    for option in d.alternatives:
        log = decisions(s, option)
        (seat, action), = option.actions
        assert seat == d.seat and log[0][2][seat] == action
        assert [k for k in range(10) if log[0][2][k] != baseline[0][2][k]] == ([seat] if baseline[0][2][seat] != action else [])
        commit, held = s.meta.config.ticks(d.commit_s), True
        for at, observations, actions in log[1:]:
            mine = observations[seat]
            held = held and at - log[0][0] < commit and mine.me.intent == action and legal_mask(mine)[KEEP]
            for k, (act, o) in enumerate(zip(policies, observations)):
                expected = KEEP if k == seat and held else act(o, keyed_uniform(seed, Stream.POLICY, k, at))
                assert actions[k] == expected, f"seat {k} at tick {at}"


def test_a_coordinated_alternative_changes_several_seats_of_one_team_and_the_report_calls_it_a_team_plan():
    s = load(PLAN)
    d = s.decision
    baseline = decisions(s, d.options()[0])
    for option in d.alternatives:
        seats = [seat for seat, _ in option.actions]
        assert len(seats) == 2 and {seat // 5 for seat in seats} == {0}
        log = decisions(s, option)
        assert [log[0][2][seat] for seat in seats] == [action for _, action in option.actions]
        assert all(log[0][2][k] == baseline[0][2][k] for k in range(10) if k not in seats)
    out = run(s)
    assert out["scenario"]["label"] == "team plan"
    assert "blue_top, team plan" in report("plan", [out], summarise([out]))


def test_continuation_policies_receive_observations_and_noise_and_nothing_else():
    spy = []
    decisions(individual(), individual().decision.alternatives[0], spy=spy)
    assert spy and all(type(o) is Observation and type(noise) is float and 0.0 <= noise < 1.0 for o, noise in spy)


def test_the_verdict_rule_is_a_paired_mean_beyond_the_threshold_in_the_good_direction():
    assert verdict(2.1, 1.0, 1, 2.0) == "better" and verdict(1.9, 1.0, 1, 2.0) == "unclear" and verdict(-2.1, 1.0, 1, 2.0) == "worse"
    assert verdict(-2.1, 1.0, -1, 2.0) == "better" and verdict(2.1, 1.0, -1, 2.0) == "worse" and verdict(0.0, 0.0, 1, 2.0) == "unclear"
    assert verdict(0.5, 0.0, 1, 2.0) == "better", "every rollout gave the same difference"
    assert verdict(3.0, 1.0, 1, 3.8) == "unclear"


def test_the_threshold_is_the_student_t_quantile_at_the_family_level_shared_over_the_consequences():
    """Known two-sided 95 percent quantiles for one consequence, and Bonferroni's share for several."""
    for rollouts, quantile in ((2, 12.7062), (3, 4.3027), (6, 2.5706), (16, 2.1314), (10**6, 1.9600)):
        assert threshold(1, rollouts) == pytest.approx(quantile, abs=1e-4)
    assert threshold(29, 10**6) == pytest.approx(NormalDist().inv_cdf(1 - 0.05 / 58), abs=1e-4), "the normal quantile at 0.05 / 58 per tail"
    assert threshold(29, 16) > threshold(29, 10**6) > threshold(1, 16), "fewer rollouts and more consequences ask for more"


def test_the_weighted_line_weights_the_hypotheses_rollout_by_rollout_so_lines_that_move_together_keep_their_error():
    """Two hypotheses whose rollouts give the same differences are one line: the weighted standard error is that
    line's, not the smaller error of two independent lines. Lines that move against each other cancel."""
    rng = random.Random(3)
    one = [[[rng.gauss(0.0, 1.0)], [rng.gauss(0.5, 1.0)]] for _ in range(16)]
    pairs = [(1, 0), (0, 1)]
    alone = _weighted([one], [1.0], pairs, 1)
    twice = _weighted([one, one], [0.5, 0.5], pairs, 1)
    assert twice[1, 0, 0] == pytest.approx(alone[1, 0, 0])
    mirrored = [[[-row[0][0]], [-row[1][0]]] for row in one]
    assert _weighted([one, mirrored], [0.5, 0.5], pairs, 1)[1, 0, 0] == pytest.approx((0.0, 0.0), abs=1e-12)


def test_a_ranking_is_a_dominance_a_trade_off_or_no_clear_ranking_by_the_stated_rule():
    assert relation(["better", "unclear"]) == "dominates" and relation(["worse", "unclear"]) == "dominated"
    assert relation(["better", "worse"]) == "trades off" and relation(["unclear", "unclear"]) == "no clear difference"
    names = ("baseline", "a", "b")

    def pairs(table):
        flip = {"better": "worse", "worse": "better", "unclear": "unclear"}
        out = {}
        for (x, y), v in table.items():
            out[x, y], out[y, x] = v, [flip[w] for w in v]
        return out

    clear_a = pairs({(1, 0): ["better", "unclear"], (1, 2): ["better", "unclear"], (2, 0): ["unclear", "unclear"]})
    assert ranking(names, clear_a) == {"outcome": "a dominates", "dominance": ["a dominates b", "a dominates baseline"]}
    crossed = pairs({(1, 0): ["better", "worse"], (1, 2): ["better", "unclear"], (2, 0): ["unclear", "unclear"]})
    assert ranking(names, crossed)["outcome"] == "trade-off"
    partial = pairs({(1, 0): ["better", "unclear"], (1, 2): ["unclear", "unclear"], (2, 0): ["unclear", "unclear"]})
    assert ranking(names, partial) == {"outcome": "partial order", "dominance": ["a dominates baseline"]}, "nothing trades off"
    flat = pairs({(1, 0): ["unclear"] * 2, (1, 2): ["unclear"] * 2, (2, 0): ["unclear"] * 2})
    assert ranking(names, flat) == {"outcome": "no clear ranking", "dominance": []}


def synthetic(tick_s: float, relations: dict[tuple[str, str], str]) -> dict:
    def line(r):
        return {"alternatives": {"a": {"relation": r, "metrics": {"champion gold earned": {"verdict": "unclear"}}}}, "ranking": {"outcome": r}}

    lines = {}
    for (style, name), r in relations.items():
        lines.setdefault(style, {})[name] = line(r)
    return {"scenario": {"tick_s": tick_s, "alternatives": {"a": {}}}, "metrics": [{"scope": "champion", "name": "gold earned"}], "lines": lines}


@pytest.mark.parametrize("vary, expected", [("nothing", None), ("hypothesis", ["hypothesis"]), ("style", ["style"]), ("tick", ["tick"])])
def test_a_ranking_that_changes_with_a_factor_is_uncertain_and_names_the_factor(vary, expected):
    def relations(tick_s):
        out = {}
        for style in ("standard", "aggressive"):
            for name in ("h1", "h2", "weighted"):
                changed = {"hypothesis": name == "h2", "style": style == "aggressive", "tick": tick_s == 0.25}.get(vary, False)
                out[style, name] = "trades off" if changed else "dominates"
        return out

    entry = summarise([synthetic(0.25, relations(0.25)), synthetic(0.5, relations(0.5))])["relations"]["a"]
    if expected is None:
        assert entry == {"stable": True, "value": "dominates"}
    else:
        assert entry["stable"] is False and entry["value"] == "uncertain" and entry["depends on"] == expected


def test_a_line_that_one_tick_has_and_another_lacks_makes_the_ranking_uncertain():
    both = {(style, name): "dominates" for style in ("standard", "aggressive") for name in ("h1", "h2", "weighted")}
    fewer = {key: value for key, value in both.items() if key[1] != "h2"}
    entry = summarise([synthetic(0.25, both), synthetic(0.5, fewer)])["ranking"]
    assert entry["stable"] is False and "tick" in entry["depends on"]
    assert entry["values"]["standard, tick 0.5 s, h2"] == "absent"


def test_agreement_with_a_reference_tick_counts_the_lines_and_relations_that_rank_alike_and_names_the_rest():
    research = synthetic(0.25, {("standard", "h1"): "dominates", ("standard", "weighted"): "dominates"})
    reference = synthetic(0.125, {("standard", "h1"): "dominates", ("standard", "weighted"): "trades off"})
    agree = agreement(research, reference)
    assert (agree["rankings"], agree["rankings agree"], agree["relations"], agree["relations agree"]) == (2, 1, 2, 1)
    assert agree["differ"] == {"standard, weighted, ranking": ["dominates", "trades off"], "standard, weighted, a": ["dominates", "trades off"]}
    assert agreement(research, research)["differ"] == {}


def test_a_reference_tick_is_reported_apart_and_changes_no_stability_verdict():
    out, fine = compared(), run(load(RECIPE, 0.25))
    assert fine["scenario"]["decision_at_s"] == out["scenario"]["decision_at_s"] and fine["scenario"]["base_tick_s"] == 0.5
    plain = report("individual", [out], summarise([out]))
    words = report("individual", [out], summarise([out]), reference={"comparison": fine, "agreement": agreement(out, fine)})
    assert "Reference tick 0.25 s (apart from the stability rule): the ranking at 0.5 s" in words and "Reference tick" not in plain

    def stability(text: str) -> str:
        return text[text.index("  Ranking:"):text.index("  Weighted lines")]

    assert stability(words) == stability(plain)


def test_the_report_states_its_terms_and_gives_every_consequence_apart():
    out = compared()
    s = individual()
    words = report("individual", [out], summarise([out]))
    for phrase in (NOTE, f"Ruleset {RULESET_ID}", "Horizon 24 s, commit 12 s, 2 rollouts", "continuations: standard, aggressive",
                   f"{s.hidden_enemies} hidden enemy champions", "Tick 0.5 s", "generator activity_v0", "Hypotheses and weights",
                   "One decision state", "Hindsight", f"clear beyond {threshold(len(metrics(s.decision)), 2):.2f} standard errors"):
        assert phrase in words, phrase
    names = [f"{m.scope} {m.name}" for m in metrics(s.decision)]
    assert "champion arrival own_top_t1" in names
    for lines in [*out["lines"].values(), out["hindsight"]]:
        for line in lines.values():
            outcome = line["ranking"]["outcome"]
            assert outcome in ("trade-off", "partial order", "no clear ranking") or outcome.removesuffix(" dominates") in out["scenario"]["alternatives"] | {"baseline": 0}
            for alternative in line["alternatives"].values():
                assert list(alternative["metrics"]) == names
                assert alternative["relation"] in ("dominates", "dominated", "trades off", "no clear difference")
    assert set(out["lines"]["standard"]) == {h.name for h in s.hypotheses} | {"weighted"}


# At commit 2a503e2 the C7 style reproduced C7's own pins, 7dad3ef2... for seed 7 and 2886c042... for seed 11, which
# showed that `Style` left the C7 policy as it was. The pursuit fix, the lane's in-tick fixes, and the 0.25 s clock
# of M8's fifth campaign then moved the kernel. These are the C7 style's digests on that kernel, a regression pin.
PINS = {7: ("scripted", "721c682ed655aca1e2e6dff4f5b58e584a6e8faddfe63d0628de0b4b01f6d129"),
        11: ("random", "70ff8ee104220f9f02bbfbed8e377b2e178d587cbd28716dfd2d819355a4fe81")}


@pytest.mark.parametrize("seed", list(PINS))
def test_the_c7_style_reproduces_its_pinned_replays(seed):
    from experiments.m8.integrated import random_side
    red, pin = PINS[seed]
    _, digests = record(HALF, seed, team_policies(blue=styled(C7), red=styled(C7) if red == "scripted" else random_side), 2400)
    assert digests[-1] == pin


def tower_case(world: World, seat: int, decision_s: float) -> str:
    """The tower rule read from the world for a champion on its lane: "forbidden" when it could walk into the range of
    a standing enemy tower of the lane before its next decision and no minion of its team stands in that range,
    "exempt" when such a tower is that near but a minion of its team stands in its range, and "free" otherwise."""
    c = world.champions[seat]
    team, place = seat // 5, to_frame(seat // 5, c.pos)
    if place.route not in LANES:
        return "free"
    sim, length = world.lanes[place.route], RIFT.lanes[place.route].length

    def framed(s: float) -> float:
        return s if team == 0 else length - s

    walk = capability_of(c).move_speed * (1.0 + homeguard_bonus(world, c)) * decision_s
    near = [framed(tower.s) for tower in sim.towers[1 - team] if tower.hp > 0 and abs(place.s - framed(tower.s)) <= TOWER_RANGE + walk]
    covered = [any(abs(framed(m.s) - s) <= TOWER_RANGE for m in sim.minions[team]) for s in near]
    return "free" if not near else "exempt" if all(covered) else "forbidden"


def fights(style, seed: int, seconds: float = 1200.0) -> dict[str, int]:
    """Fights started or kept in a game of `style` on both teams, by their case under the tower rule."""
    decision_s = HALF.tick_s * HALF.decision_ticks
    world, policies = World(HALF, seed), team_policies(styled(style, decision_s), styled(style, decision_s))
    cases = {"free": 0, "exempt": 0, "forbidden": 0}
    while world.tick * HALF.tick_s < seconds:
        if world.tick % HALF.decision_ticks == 0:
            for seat, (act, o) in enumerate(zip(policies, (*observe_team(world, 0), *observe_team(world, 1)))):
                choice = act(o, keyed_uniform(world.seed, Stream.POLICY, seat, world.tick))
                if ACTIONS[choice].kind is Kind.FIGHT or (choice == KEEP and ACTIONS[o.me.intent].kind is Kind.FIGHT):
                    cases[tower_case(world, seat, decision_s)] += 1
        tick(world, policies)
    return cases


def test_no_scripted_style_fights_where_the_tower_rule_forbids_it_and_both_fight_where_an_own_minion_covers_them():
    for style in (STANDARD, AGGRESSIVE):
        cases = fights(style, 3)
        assert cases["forbidden"] == 0 and cases["free"] > 50 and cases["exempt"] > 0, (style.name, cases)
    assert fights(C7, 3)["forbidden"] > 0, "without the rule a scripted champion fights where a tower can reach it"


def test_the_aggressive_style_trades_without_a_lead_ganks_unhurt_laners_places_no_ward_and_differs_on_the_same_observations():
    decision_s = HALF.tick_s * HALF.decision_ticks
    world, game = World(HALF, 3), team_policies(styled(STANDARD, decision_s), styled(STANDARD, decision_s))
    styles = {name: (policy(0, style, decision_s), policy(1, style, decision_s)) for name, style in (("standard", STANDARD), ("aggressive", AGGRESSIVE))}
    counts = {name: {"trades without a lead": 0, "ganks of an unhurt laner": 0, "wards": 0} for name in styles}
    differ = 0
    while world.tick * HALF.tick_s < 1200.0:
        if world.tick % HALF.decision_ticks == 0:
            for seat, o in enumerate((*observe_team(world, 0), *observe_team(world, 1))):
                chosen = {name: side[seat // 5](o, 0.5) for name, side in styles.items()}
                differ += chosen["standard"] != chosen["aggressive"]
                me = o.me.hp / o.me.max_hp
                for name, choice in chosen.items():
                    a = ACTIONS[choice]
                    if a.kind is Kind.FIGHT and o.enemies[a.target] is not None and not o.me.hurt_by[a.target]:
                        enemy = o.enemies[a.target]
                        share = enemy.hp / capability(("top", "jungle", "mid", "carry", "support")[a.target], enemy.level, enemy.upgrades).max_hp
                        lane_opponent = o.me.role in (0, 2, 3) and a.target == o.me.role
                        counts[name]["trades without a lead"] += lane_opponent and share > me
                        counts[name]["ganks of an unhurt laner"] += o.me.role == 1 and share >= STANDARD.gank_below
                    counts[name]["wards"] += a.kind is Kind.WARD
        tick(world, game)
    assert all(counts["standard"][key] == 0 for key in ("trades without a lead", "ganks of an unhurt laner")) and counts["standard"]["wards"] > 0
    assert counts["aggressive"]["trades without a lead"] > 0 and counts["aggressive"]["ganks of an unhurt laner"] > 0 and counts["aggressive"]["wards"] == 0
    assert differ > 100
