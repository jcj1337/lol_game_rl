"""C8: scenario recipes, their overrides, and saved scenarios (M7 section 9.1)."""

import dataclasses
from functools import cache

import pytest

from riftgame.champions import ACTIONS, FOUNTAIN, HOLD, NODE_POS, PROGRESSIONS, RECALL, Kind, capability, capability_of, level_of
from riftgame.clock import refine
from riftgame.harness import tick
from riftgame.hypotheses import realize
from riftgame.info import band_floor
from riftgame.lanes import RULESET_ID
from riftgame.policies import team_policies
from riftgame.scenario import (RecipeError, Scenario, base_world, build, decision_tick, load, parse, parse_action, restore, save,
                               spell)
from riftgame.vision import observe_team, to_frame
from riftgame.world import Config, World, check_invariants

RECIPE = f"""
ruleset = "{RULESET_ID}"
seed = 11
tick_s = 0.5
base = {{ policy = "scripted_v0", seed = 4, until_s = 300 }}

[[champion]]
seat = "blue_top"
health = 0.8
gold = 650
level = 6
upgrades = 2
intent = "LANE top last_hit hold"

[knowledge.blue]
red_jungle = {{ last_seen = "bot_river", at_s = 288, health = 0.9 }}
red_gromp = "unknown"

[decision]
seat = "blue_top"
kind = "individual"
horizon_s = 30
commit_s = 10
rollouts = 2
hidden = "activity_v0"
focus = ["red_jungle"]
places = ["top_river"]
alternatives = ["LANE top push wave", "RECALL"]
"""


@cache
def small() -> Scenario:
    return load(RECIPE)


def refused(text: str) -> str:
    with pytest.raises(RecipeError) as caught:
        parse(text)
    return str(caught.value)


def test_every_action_has_one_spelling_and_the_parser_takes_nothing_else():
    assert [parse_action(spell(i)) for i in range(len(ACTIONS))] == list(range(len(ACTIONS)))
    assert spell(parse_action("LANE top last_hit wave")) == "LANE top last_hit wave"
    assert ACTIONS[parse_action("FIGHT jungle")] == (Kind.FIGHT, 1)
    for wrong in ("LANE top last_hit", "lane top last_hit wave", "LANE  top last_hit wave", "FIGHT 1", "MOVE blue_top_t1", "RECALL ", ""):
        with pytest.raises(RecipeError):
            parse_action(wrong)


UNKNOWN_KEYS = [
    ("seed = 11", 'seed = 11\ncolour = "red"', "colour"),
    ("until_s = 300 }", "until_s = 300, speed = 2 }", "speed"),
    ("health = 0.8\n", "health = 0.8\narmour = 3\n", "armour"),
    ("at_s = 288, health = 0.9 }", "at_s = 288, health = 0.9, colour = 1 }", "colour"),
    ('hidden = "activity_v0"', 'hidden = "activity_v0"\nbudget = 3', "budget"),
    ('alternatives = ["LANE top push wave", "RECALL"]', 'alternatives = [{ name = "push", blue_top = "LANE top push wave", colour = 1 }]', "colour"),
    ('focus = ["red_jungle"]', 'focus = ["red_jungle"]\ncontinuation = { blue = "standard", red = "standard", green = "standard" }', "green"),
    ('alternatives = ["LANE top push wave", "RECALL"]',
     'alternatives = ["LANE top push wave", "RECALL"]\n\n[[hypothesis]]\nname = "a"\nweight = 1\ncolour = 2', "colour"),
    ('alternatives = ["LANE top push wave", "RECALL"]',
     'alternatives = ["LANE top push wave", "RECALL"]\n\n[[hypothesis]]\nname = "a"\nweight = 1\nred_jungle = { activity = "stay", speed = 3 }', "speed"),
]


@pytest.mark.parametrize("old, new, key", UNKNOWN_KEYS)
def test_a_recipe_with_an_unknown_key_anywhere_is_refused_with_the_key_named(old, new, key):
    assert RECIPE.count(old) == 1
    assert f"unknown key {key!r}" in refused(RECIPE.replace(old, new))


REFUSALS = [
    (f'ruleset = "{RULESET_ID}"', 'ruleset = "ref-26.22-r1"', "ruleset"),
    ("rollouts = 2", "rollouts = 1", "rollouts"),
    ("commit_s = 10", "commit_s = 40", "commit_s"),
    ('seat = "blue_top"\nkind', 'seat = "blue_toplaner"\nkind', "no seat"),
    ('places = ["top_river"]', 'places = ["blue_top_t1"]', "no place"),
    ('last_seen = "bot_river"', 'last_seen = "red_gromp"', "no place"),
    ("[knowledge.blue]", '[[lane]]\nname = "top"\n\n[knowledge.blue]', "[[lane]]"),
    ("[knowledge.blue]", "[knowledge.red]", "deciding team's knowledge"),
    ('alternatives = ["LANE top push wave", "RECALL"]', 'alternatives = [{ name = "mid", blue_mid = "RECALL" }]', "individual"),
    ('kind = "individual"', 'kind = "coordinated"', "team plan"),
    ('alternatives = ["LANE top push wave", "RECALL"]', 'alternatives = [{ name = "both", blue_top = "RECALL", red_top = "RECALL" }]', "deciding team"),
    ('alternatives = ["LANE top push wave", "RECALL"]', 'alternatives = ["LANE top push"]', "no action"),
    ('alternatives = ["LANE top push wave", "RECALL"]', 'alternatives = ["RECALL", "RECALL"]', "unique"),
    ('seat = "blue_top"\nhealth', 'seat = "red_top"\nhealth', "not on the deciding team"),
    ("tick_s = 0.5", "tick_s = 0.3\ndecision_s = 1.0", "whole number of ticks"),
    ("tick_s = 0.5", "tick_s = 0.2", "base.tick_s"),
    ("tick_s = 0.5", "tick_s = 1.0", "base.tick_s"),
    ("until_s = 300 }", "until_s = 300, tick_s = 0.75 }", "base.tick_s"),
    ("tick_s = 0.5", "tick_s = 0.25\ndecision_s = 0.75", "base ticks"),
    ("health = 0.8", "health = 1.5", "health"),
]


@pytest.mark.parametrize("old, new, words", REFUSALS)
def test_a_recipe_that_breaks_the_format_is_refused_with_its_reason(old, new, words):
    assert RECIPE.count(old) == 1
    assert words in refused(RECIPE.replace(old, new))


def test_a_recipe_that_contradicts_its_base_game_is_refused_when_it_is_materialised():
    recipe = parse(RECIPE)
    source = base_world(recipe)
    seen = next(role for role, record in enumerate(source.memory[0].enemies) if record.seen_tick == source.tick)
    names = ("red_top", "red_jungle", "red_mid", "red_carry", "red_support")
    contradictions = [
        (RECIPE.replace('red_jungle = { last_seen = "bot_river", at_s = 288, health = 0.9 }',
                        f'{names[seen]} = {{ last_seen = "bot_river", at_s = 288 }}'), "sees this champion now"),
        (RECIPE.replace("at_s = 288", "at_s = 301"), "before the decision"),
        (RECIPE.replace('alternatives = ["LANE top push wave", "RECALL"]', 'alternatives = ["LANE mid push wave"]'), "mask forbids"),
    ]
    for text, words in contradictions:
        with pytest.raises(RecipeError, match=words):
            build(parse(text), World.restore(source.snapshot()))


def test_the_decision_falls_on_the_first_decision_tick_at_or_after_until_s():
    for tick_s, every in ((0.5, 4), (0.25, 8)):
        config = Config(tick_s=tick_s, decision_ticks=every)
        for until in (0.0, 299.0, 300.0, 300.1, 301.9, 302.0):
            assert decision_tick(config, until) == min(t for t in range(10_000) if t % every == 0 and t * tick_s >= until)
    assert small().meta.tick == 600 and small().info.world().tick == 600


def test_a_recipe_materialised_at_finer_ticks_describes_its_one_decision_state_at_each():
    made = {tick_s: load(RECIPE, tick_s) for tick_s in (0.5, 0.25, 0.125)}
    half = made[0.5]
    for tick_s, s in made.items():
        assert s.meta.config.tick_s == tick_s and s.meta.base_tick_s == 0.5 and s.meta.tick * tick_s == 300.0
        assert World.restore(s.hindsight).digest() == refine(World.restore(half.hindsight), tick_s).digest()
        assert (s.info.seen, s.hidden_enemies, s.hypotheses, s.rejected) == (half.info.seen, half.hidden_enemies, half.hypotheses, half.rejected)


def test_overrides_set_the_deciding_teams_champions_and_memory_and_keep_every_invariant():
    world = small().info.world()
    me = world.champions[0]
    can = capability_of(me)
    assert (me.hp, me.gold, level_of(me.xp), me.upgrades, spell(me.intent)) == (0.8 * can.max_hp, 650.0, 6, 2, "LANE top last_hit hold")
    assert abs(sum(me.earned) - sum(u.cost for u in PROGRESSIONS["top"][:2]) - 650.0) < 1e-6
    o = observe_team(world, 0)[0]
    last = o.remembered[1]
    assert last.place == to_frame(0, NODE_POS[0]["bot_river"]) and last.age_s == 300.0 - 288.0
    assert last.hp == pytest.approx(0.9 * capability("jungle", last.level, last.upgrades).max_hp) and last.level == o.rivals[1].level
    gromp = o.camps[[a.target for a in ACTIONS if a.kind is Kind.CAMP].index("enemy_gromp")]
    assert gromp.seen_age_s is None and gromp.spawn_s is None and gromp.hp == 0.0
    check_invariants(World.restore(small().hindsight))


def staged_source() -> World:
    """The base game of the recipe at its decision tick, with pending effects of every kind on the deciding team
    and a dead enemy, so that a restore that drops one of them shows."""
    source = base_world(parse(RECIPE))
    t = source.tick
    mid, carry, support = source.champions[2], source.champions[3], source.champions[4]
    mid.intent, mid.intent_tick, mid.channel = RECALL, t - 3, 3
    carry.slow, carry.slow_until, carry.lockdown_tick = 0.3, t + 6, t + 15
    source.ward(4, support.pos, 900.0, 40.0, 3)
    red_top = source.champions[5]
    red_top.hp, red_top.intent, red_top.pos, red_top.respawn_tick = 0.0, HOLD, FOUNTAIN[1], t + 21
    return source


def pending(world: World) -> dict:
    t = world.tick
    return {"missiles in flight": sum(len(sim._missiles) for sim in world.lanes.values()),
            "recall channels": sum(ACTIONS[c.intent].kind is Kind.RECALL and c.channel > 0 for c in world.champions),
            "slows": sum(c.slow_until > t and c.slow > 0 for c in world.champions),
            "lockdown cooldowns": sum(c.lockdown_tick > t for c in world.champions),
            "ward expiries": sum(s.owner >= 0 and s.expires > t for s in world.sights),
            "camp respawn timers": sum(camp.spawn_tick > t for camp in world.camps),
            "champion respawn timers": sum(c.respawn_tick > t for c in world.champions),
            "intents in progress": sum(c.intent_tick < t and c.intent != HOLD for c in world.champions),
            "attack credits": sum(0.0 < c.attack_credit < 1.0 for c in world.champions)}


def state(world: World) -> tuple:
    return (world.memory, world.champions, world.camps, world.sights, [sim.values() for sim in world.lanes.values()], world.seed, world.tick)


def test_a_saved_scenario_restores_memory_and_pending_effects_and_replays_with_equal_digests_on_every_tick(tmp_path):
    made = build(parse(RECIPE), staged_source())
    save(made, tmp_path / "scenario.pkl")
    back = restore(tmp_path / "scenario.pkl")
    assert back.info.digest() == made.info.digest() and back.decision == made.decision and back.hypotheses == made.hypotheses
    assert back.meta == made.meta
    ticks = made.meta.config.ticks(made.decision.horizon_s)
    for start in (lambda s: World.restore(s.hindsight), lambda s: realize(s.info, s.hypotheses[0], 0)):
        a, b = start(made), start(back)
        assert all(pending(a).values()), pending(a)
        assert state(a) == state(b) and a.digest() == b.digest()
        policies = team_policies()
        for _ in range(ticks):
            tick(a, policies)
            tick(b, policies)
            assert a.digest() == b.digest(), f"tick {a.tick}"
        assert state(a) == state(b)


@pytest.mark.parametrize("field, value, words", [("ruleset_id", "ref-0", "ruleset"), ("map_id", "map_other", "map"), ("code", "0" * 16, "code")])
def test_a_saved_scenario_made_under_another_ruleset_map_or_code_is_refused(tmp_path, field, value, words):
    other = dataclasses.replace(small(), meta=dataclasses.replace(small().meta, **{field: value}))
    save(other, tmp_path / "other.pkl")
    with pytest.raises(ValueError, match=words):
        restore(tmp_path / "other.pkl")
    save(small(), tmp_path / "same.pkl")
    assert restore(tmp_path / "same.pkl").info.digest() == small().info.digest()


def test_the_source_world_is_kept_apart_and_differs_from_the_information_state_only_in_what_the_team_cannot_know():
    s = small()
    source, info = World.restore(s.hindsight), s.info.world()
    assert observe_team(source, 0) == observe_team(info, 0)
    assert source.champions[:5] == info.champions[:5] and source.memory[0] == info.memory[0]


def written(*blocks: str, recipe: str = RECIPE) -> str:
    return recipe + "".join(f'\n[[hypothesis]]\nname = "h{i}"\nweight = {i + 1}\n{block}\n' for i, block in enumerate(blocks))


# Blue's top laner stands at top_river. The red jungler was last seen at bot_river, or with `SEEN_AT_TOP` at top_river,
# where a stay puts it in front of that laner whatever the base game did.
AT_TOP = RECIPE.replace("health = 0.8\n", 'health = 0.8\npos = { node = "top_river" }\n')
SEEN_AT_TOP = AT_TOP.replace('last_seen = "bot_river"', 'last_seen = "top_river"')


def test_hand_written_hypotheses_replace_the_generator_and_are_completed_checked_and_weighted():
    s = load(written('red_jungle = { activity = "stay" }', 'red_jungle = { activity = "recall" }'))
    assert s.decision.hidden == "explicit" and [h.name for h in s.hypotheses] == ["h0", "h1"]
    assert [h.weight for h in s.hypotheses] == pytest.approx([1 / 3, 2 / 3])
    unseen = [role for role, now in enumerate(s.info.seen) if not now and s.info.world().champions[5 + role].hp > 0]
    assert all((h.plans[role] is not None) == (role in unseen) for h in s.hypotheses for role in range(5))
    # The redacted jungler holds the least XP of its public level, so the band is read from the scenario itself.
    level = level_of(s.info.world().champions[6].xp)
    low, high = band_floor(level), band_floor(level + 1)
    assert load(written(f'red_jungle = {{ activity = "stay", xp = {low} }}')).hypotheses[0].plans[1].xp == low
    with pytest.raises(RecipeError, match="rejected, XP_BAND"):
        load(written(f'red_jungle = {{ activity = "stay", xp = {high} }}'))
    assert load(written('red_jungle = { activity = "stay" }', recipe=AT_TOP)).hypotheses[0].plans[1].activity.name == "STAY"
    with pytest.raises(RecipeError, match="rejected, IN_VIEW"):
        load(written('red_jungle = { activity = "stay" }', recipe=SEEN_AT_TOP))
