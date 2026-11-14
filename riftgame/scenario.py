"""Scenario recipes and saved scenarios (M7 section 9.1, checkpoint C8).

A recipe is a TOML text that a person writes. It names a ruleset, a world seed, a base game run to a clock time,
overrides of what the deciding team can see or remembers, and a decision. `parse` checks it at this boundary:
an unknown key, a wrong type, or a value out of range is a `RecipeError` that names the key. `load` runs the base
game on its own tick to the first decision tick at or after `until_s` and applies the overrides there. That is the
decision state. It then refines the world to the recipe's tick (`riftgame.clock.refine`), redacts it for the deciding
team, and builds the hypotheses. The recipe's tick divides the base tick a whole number of times, so a recipe
materialised at several ticks describes one decision state at each. The source world stays apart, for the hindsight
line only.

Names follow two rules. An entity is named as on the map: a seat as `blue_top`, a camp as `red_gromp`. A place
and an action are named in the deciding team's frame, as in `riftgame.champions`: `own_top_t1`, `top_river`,
`LANE top last_hit wave`, `FIGHT jungle`. A lane position is `{ lane, s }` with `s` measured from the deciding
team's own end of the lane.

```toml
ruleset = "ref-26.22-r1+m8.3"
seed = 11
tick_s = 0.25             # optional, the tick of `Config()`: the comparisons' tick
decision_s = 2.0          # optional, the decision interval of `Config()`
base = { policy = "scripted_v0", seed = 3, until_s = 420, tick_s = 0.5 }   # tick_s optional, 0.5

[[champion]]              # the deciding team's own champions only
seat = "blue_top"
pos = { lane = "top", s = 5200 }     # or { node = "own_top_t1" }
health = 0.55             # share of maximum health; also mana, gold, level, upgrades, intent

[knowledge.blue]          # the deciding team's memory
red_jungle = { last_seen = "bot_river", at_s = 385, health = 0.9 }
red_gromp = "unknown"     # or { seen_s = 300, alive = false, spawn_s = 420 }

[decision]
seat = "blue_top"
kind = "individual"       # or "coordinated"
horizon_s = 90
commit_s = 20             # optional, 0: hold the substituted action this long or until its intent ends
rollouts = 16
hidden = "activity_v0"
focus = ["red_jungle"]    # optional: the enemies whose activity the generator varies
places = ["top_river"]    # optional: places whose arrival time the report gives
continuation = [{ blue = "standard", red = "standard" }, { blue = "aggressive", red = "aggressive" }]
alternatives = ["LANE top last_hit hold", "LANE top push wave", "RECALL"]
# a team plan: alternatives = [{ name = "dive", blue_top = "FIGHT top", blue_jungle = "FIGHT top" }, ...]

[[hypothesis]]            # optional: hand-written hypotheses, which replace the generator's
name = "jungler took gromp"
weight = 0.5
red_jungle = { activity = "clear", path = ["red_gromp"] }   # or stay, farm, recall, move with `to`; optional xp, upgrades
cleared = ["red_gromp"]   # optional: camps cleared unseen, each on some path
```

Every enemy that a hand-written hypothesis leaves out gets its role's default activity, and the whole hypothesis
passes the checks of `riftgame.hypotheses` or the recipe is refused with the reason.

A continuation style is named as in `riftgame.policies.STYLES`, where `scripted_v0` is the standard style. Without
`continuation` both teams play the standard style. A position override moves the champion without a new look: what
the team sees at the decision tick stays what its memory records.

`[[lane]]` tables are refused: a lane's minions carry targets, casts, and missiles in flight that counts per kind
cannot restore. A wave state comes from the base game.

A saved scenario is the materialised result with its metadata, pickled. `restore` refuses one made under another
ruleset, map, or code stamp, as `World.restore` refuses a ruleset.
"""

import hashlib
import math
import pickle
import tomllib
from dataclasses import dataclass
from pathlib import Path

from riftgame.champions import (ACTIONS, FOUNTAIN, LANES, LEVEL_XP, NODE_POS, NODES, PROGRESSIONS, RIFT, ROLES, TEAMS, Income, Kind,
                                capability, capability_of, frame_name, level_of, spent)
from riftgame.clock import refine
from riftgame.harness import tick as advance
from riftgame.hypotheses import Activity, Hypothesis, Plan, Rejected, check, complete, generate
from riftgame.info import InfoState, redact
from riftgame.jungle import SITES
from riftgame.lanes import MAP_ID, RULESET_ID
from riftgame.map import Pos
from riftgame.policies import STANDARD, STYLES, styled, team_policies
from riftgame.vision import CampMemory, legal_mask, observe_team
from riftgame.world import Config, Snapshot, World, check_invariants

SOURCES = Path(__file__).parent
SEATS = {f"{team}_{role}": t * 5 + r for t, team in enumerate(TEAMS) for r, role in enumerate(ROLES)}
SEAT_NAMES = {seat: name for name, seat in SEATS.items()}
CAMPS = {site.node: i for i, site in enumerate(SITES)}
BASE_POLICIES = {"scripted_v0": STANDARD}
GENERATORS = ("activity_v0",)
BASELINE = "baseline"
# M7's starting tick. 0.25 s and 0.125 s divide it, so a scenario at either refines its base game exactly.
BASE_TICK_S = 0.5


class RecipeError(ValueError):
    """A recipe that this boundary refuses, with the key that is wrong."""


def spell(action: int) -> str:
    """An action as a recipe names it: the kind, then the target in the acting team's frame."""
    a = ACTIONS[action]
    if a.target is None:
        return a.kind.name
    if a.kind is Kind.LANE:
        return " ".join((a.kind.name, *a.target))
    if a.kind in (Kind.FOLLOW, Kind.FIGHT):
        return f"{a.kind.name} {ROLES[a.target]}"
    return f"{a.kind.name} {a.target}"


SPELLED = {spell(i): i for i in range(len(ACTIONS))}
assert len(SPELLED) == len(ACTIONS), "two actions share a spelling"


def parse_action(text: str, where: str = "action") -> int:
    """The action index of an exact spelling. Nothing else is accepted: no case folding, no default stand."""
    action = SPELLED.get(text) if isinstance(text, str) else None
    if action is None:
        raise RecipeError(f"{where}: {text!r} is no action; actions are spelled as {spell(4)!r}, "
                          f"'LANE top last_hit wave', 'FIGHT jungle', 'RECALL'")
    return action


@dataclass(frozen=True, slots=True)
class Base:
    """The base game. `config` is its clock, on which the overrides are applied too."""

    policy: str
    seed: int
    until_s: float
    config: Config


@dataclass(frozen=True, slots=True)
class Override:
    """What a recipe sets on one of the deciding team's champions. None leaves a field as the base game left it."""

    seat: int
    pos: Pos | None = None
    health: float | None = None
    mana: float | None = None
    gold: float | None = None
    level: int | None = None
    upgrades: int | None = None
    intent: int | None = None


@dataclass(frozen=True, slots=True)
class Sighting:
    """A last-seen record of an enemy champion that replaces the deciding team's. `pos` is None for a champion that
    the team never saw."""

    role: int
    pos: Pos | None
    at_s: float = 0.0
    health: float | None = None
    level: int | None = None
    upgrades: int | None = None


@dataclass(frozen=True, slots=True)
class CampNote:
    """The deciding team's memory of one camp. `seen_s` is None for a camp whose place it never saw."""

    camp: int
    seen_s: float | None
    alive: bool = False
    level: int = 1
    spawn_s: float | None = None


@dataclass(frozen=True, slots=True)
class Continuation:
    """The style that plays each team after the decision, by name in `riftgame.policies.STYLES`."""

    blue: str
    red: str

    def label(self) -> str:
        return self.blue if self.blue == self.red else f"{self.blue} blue, {self.red} red"


@dataclass(frozen=True, slots=True)
class Alternative:
    """What one option substitutes at the decision tick: (seat, action index) pairs. One seat for an individual
    alternative, several of one team for a team plan. The baseline is the continuation's own choice and has none."""

    name: str
    actions: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class Decision:
    """The decision of a scenario. `alternatives` leaves out the baseline, which every comparison adds first.
    `hidden` is "activity_v0" when the generator supplies the hypotheses and "explicit" when the recipe does."""

    seat: int
    kind: str
    alternatives: tuple[Alternative, ...]
    horizon_s: float
    commit_s: float
    rollouts: int
    hidden: str
    focus: tuple[int, ...] | None
    places: tuple[str, ...]
    continuations: tuple[Continuation, ...]

    @property
    def team(self) -> int:
        return self.seat // 5

    def options(self) -> tuple[Alternative, ...]:
        return (Alternative(BASELINE, ()), *self.alternatives)


@dataclass(frozen=True, slots=True)
class Written:
    """A hand-written hypothesis as the recipe gives it: plans by enemy role and the camps it says were cleared
    unseen. The loader fills every other plan from the generator's default activity and checks the whole."""

    name: str
    weight: float
    plans: tuple[tuple[int, Plan], ...]
    cleared: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class Recipe:
    text: str
    seed: int
    config: Config
    base: Base | None
    overrides: tuple[Override, ...]
    sightings: tuple[Sighting, ...]
    camps: tuple[CampNote, ...]
    decision: Decision
    written: tuple[Written, ...]


def _keys(raw: dict, where: str, required: tuple[str, ...] = (), optional: tuple[str, ...] = ()) -> dict:
    if not isinstance(raw, dict):
        raise RecipeError(f"{where}: expected a table, got {type(raw).__name__}")
    unknown = [key for key in raw if key not in required and key not in optional]
    if unknown:
        raise RecipeError(f"{where}: unknown key {unknown[0]!r}")
    missing = [key for key in required if key not in raw]
    if missing:
        raise RecipeError(f"{where}: missing key {missing[0]!r}")
    return raw


def _number(raw: dict, key: str, where: str, lo: float = -math.inf, hi: float = math.inf, default=None) -> float:
    value = raw.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not lo <= value <= hi:
        raise RecipeError(f"{where}.{key}: expected a number from {lo} to {hi}, got {value!r}")
    return float(value)


def _integer(raw: dict, key: str, where: str, lo: int = 0, hi: int = 2 ** 62, default=None) -> int:
    value = raw.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
        raise RecipeError(f"{where}.{key}: expected a whole number from {lo} to {hi}, got {value!r}")
    return value


def _text(raw: dict, key: str, where: str, choices: tuple[str, ...] | None = None, default=None) -> str:
    value = raw.get(key, default)
    if not isinstance(value, str) or (choices is not None and value not in choices):
        raise RecipeError(f"{where}.{key}: expected {'one of ' + ', '.join(choices) if choices else 'a string'}, got {value!r}")
    return value


def _seat(name, where: str) -> int:
    if name not in SEATS:
        raise RecipeError(f"{where}: {name!r} is no seat; seats are named like 'blue_top' and 'red_jungle'")
    return SEATS[name]


def _place(team: int, name, where: str) -> Pos:
    if not isinstance(name, str) or name not in NODE_POS[team] or name.split("_", 1)[0] in TEAMS:
        raise RecipeError(f"{where}: {name!r} is no place in the deciding team's frame; places are named like 'own_top_t1' and 'top_river'")
    return NODE_POS[team][name]


def _position(team: int, raw, where: str) -> Pos:
    if isinstance(raw, dict) and "node" in raw:
        return _place(team, _keys(raw, where, ("node",))["node"], f"{where}.node")
    _keys(raw, where, ("lane", "s"))
    lane = _text(raw, "lane", where, LANES)
    length = RIFT.lanes[lane].length
    s = _number(raw, "s", where, 0.0, length)
    return RIFT.lane_pos(lane, s if team == 0 else length - s)


def _config(raw: dict, tick_s: float | None) -> Config:
    clock = Config()
    tick_s = _number(raw, "tick_s", "recipe", 0.01, 5.0, clock.tick_s) if tick_s is None else tick_s
    decision_s = _number(raw, "decision_s", "recipe", tick_s, 60.0, clock.tick_s * clock.decision_ticks)
    ticks = round(decision_s / tick_s)
    if abs(ticks * tick_s - decision_s) > 1e-9:
        raise RecipeError(f"recipe.decision_s: {decision_s} s is not a whole number of ticks of {tick_s} s")
    return Config(tick_s=tick_s, decision_ticks=ticks)


def _base_config(raw: dict, config: Config) -> Config:
    """The base game's clock. The recipe's tick divides it a whole number of times, and a decision is a whole number
    of its ticks."""
    tick_s = _number(raw, "tick_s", "base", 0.01, 5.0, BASE_TICK_S)
    k = round(tick_s / config.tick_s)
    if k < 1 or abs(k * config.tick_s - tick_s) > 1e-9:
        raise RecipeError(f"base.tick_s: the recipe's tick of {config.tick_s:g} s does not divide the base tick of {tick_s:g} s a whole number of times")
    if config.decision_ticks % k:
        raise RecipeError(f"base.tick_s: a decision every {config.tick_s * config.decision_ticks:g} s is not a whole number of base ticks of {tick_s:g} s")
    return Config(tick_s=tick_s, decision_ticks=config.decision_ticks // k)


def _override(raw: dict, team: int, where: str) -> Override:
    _keys(raw, where, ("seat",), ("pos", "health", "mana", "gold", "level", "upgrades", "intent"))
    seat = _seat(raw["seat"], f"{where}.seat")
    if seat // 5 != team:
        raise RecipeError(f"{where}.seat: {raw['seat']} is not on the deciding team; only its own champions can be overridden")
    profile = PROGRESSIONS[ROLES[seat % 5]]
    return Override(
        seat, None if "pos" not in raw else _position(team, raw["pos"], f"{where}.pos"),
        None if "health" not in raw else _number(raw, "health", where, 0.01, 1.0),
        None if "mana" not in raw else _number(raw, "mana", where, 0.0, 1.0),
        None if "gold" not in raw else _number(raw, "gold", where, 0.0, 1e6),
        None if "level" not in raw else _integer(raw, "level", where, 1, len(LEVEL_XP) + 1),
        None if "upgrades" not in raw else _integer(raw, "upgrades", where, 0, len(profile)),
        None if "intent" not in raw else parse_action(raw["intent"], f"{where}.intent"))


def _knowledge(raw: dict, team: int) -> tuple[tuple[Sighting, ...], tuple[CampNote, ...]]:
    _keys(raw, "knowledge", optional=TEAMS)
    sightings, camps = [], []
    for side, notes in raw.items():
        where = f"knowledge.{side}"
        if TEAMS.index(side) != team:
            raise RecipeError(f"{where}: only the deciding team's knowledge can be stated; the enemy's memory is rebuilt by rule")
        for key, note in _keys(notes, where, optional=(*SEATS, *CAMPS)).items():
            at = f"{where}.{key}"
            if key in CAMPS:
                if note == "unknown":
                    camps.append(CampNote(CAMPS[key], None))
                    continue
                _keys(note, at, ("seen_s", "alive"), ("level", "spawn_s"))
                alive = note["alive"]
                if not isinstance(alive, bool):
                    raise RecipeError(f"{at}.alive: expected true or false, got {alive!r}")
                if alive and "spawn_s" in note:
                    raise RecipeError(f"{at}.spawn_s: a camp seen alive has no known spawn")
                camps.append(CampNote(CAMPS[key], _number(note, "seen_s", at, 0.0), alive, _integer(note, "level", at, 1, len(LEVEL_XP) + 1, 1),
                                      None if "spawn_s" not in note else _number(note, "spawn_s", at, 0.0)))
                continue
            seat = SEATS[key]
            if seat // 5 == team:
                raise RecipeError(f"{at}: {key} is on the deciding team, whose champions are known in full")
            if note == "unknown":
                sightings.append(Sighting(seat % 5, None))
                continue
            _keys(note, at, ("last_seen", "at_s"), ("health", "level", "upgrades"))
            sightings.append(Sighting(seat % 5, _place(team, note["last_seen"], f"{at}.last_seen"), _number(note, "at_s", at, 0.0),
                                      None if "health" not in note else _number(note, "health", at, 0.01, 1.0),
                                      None if "level" not in note else _integer(note, "level", at, 1, len(LEVEL_XP) + 1),
                                      None if "upgrades" not in note else _integer(note, "upgrades", at, 0, len(PROGRESSIONS[ROLES[seat % 5]]))))
    return tuple(sightings), tuple(camps)


def _alternative(raw, seat: int, kind: str, where: str) -> Alternative:
    if isinstance(raw, str):
        name, actions = raw, ((seat, parse_action(raw, where)),)
    else:
        _keys(raw, where, ("name",), tuple(SEATS))
        name = _text(raw, "name", where)
        actions = tuple(sorted((_seat(key, f"{where}.{key}"), parse_action(text, f"{where}.{key}")) for key, text in raw.items() if key != "name"))
    seats = [s for s, _ in actions]
    if any(s // 5 != seat // 5 for s in seats):
        raise RecipeError(f"{where}: every seat of an alternative is on the deciding team")
    if kind == "individual" and seats != [seat]:
        raise RecipeError(f"{where}: an individual alternative changes the deciding seat alone")
    if kind == "coordinated" and len(seats) < 2:
        raise RecipeError(f"{where}: a team plan changes at least two seats")
    return Alternative(name, actions)


def _continuations(raw) -> tuple[Continuation, ...]:
    rows = [raw] if isinstance(raw, dict) else raw
    if not isinstance(rows, list) or not rows:
        raise RecipeError("decision.continuation: expected a table { blue, red } or a list of them")
    out = []
    for i, row in enumerate(rows):
        where = f"decision.continuation[{i}]"
        _keys(row, where, TEAMS)
        out.append(Continuation(*(_text(row, team, where, tuple(STYLES)) for team in TEAMS)))
    if len(set(out)) < len(out):
        raise RecipeError("decision.continuation: a continuation is listed twice")
    return tuple(out)


def _decision(raw: dict, written: bool) -> Decision:
    _keys(raw, "decision", ("seat", "kind", "horizon_s", "rollouts", "hidden", "alternatives"),
          ("commit_s", "continuation", "focus", "places"))
    seat = _seat(raw["seat"], "decision.seat")
    team = seat // 5
    kind = _text(raw, "kind", "decision", ("individual", "coordinated"))
    horizon = _number(raw, "horizon_s", "decision", 1.0, 1800.0)
    commit = _number(raw, "commit_s", "decision", 0.0, horizon, 0.0)
    rollouts = _integer(raw, "rollouts", "decision", 2, 10_000)
    _text(raw, "hidden", "decision", GENERATORS)
    alternatives = raw["alternatives"]
    if not isinstance(alternatives, list) or not alternatives:
        raise RecipeError("decision.alternatives: expected a list with at least one alternative")
    options = tuple(_alternative(a, seat, kind, f"decision.alternatives[{i}]") for i, a in enumerate(alternatives))
    names = [a.name for a in options]
    if BASELINE in names or len(set(names)) < len(names) or len({a.actions for a in options}) < len(options):
        raise RecipeError("decision.alternatives: names and actions are unique, and 'baseline' is the continuation's own choice")
    focus = raw.get("focus")
    if focus is not None:
        if not isinstance(focus, list) or not focus:
            raise RecipeError("decision.focus: expected a list of enemy seats")
        focus = tuple(sorted({_seat(name, "decision.focus") for name in focus}))
        if any(s // 5 == team for s in focus):
            raise RecipeError("decision.focus: only enemy champions are hidden")
        focus = tuple(s % 5 for s in focus)
    places = raw.get("places", [])
    if not isinstance(places, list):
        raise RecipeError("decision.places: expected a list of places")
    for i, name in enumerate(places):
        _place(team, name, f"decision.places[{i}]")
    continuation = _continuations(raw.get("continuation", {"blue": "standard", "red": "standard"}))
    return Decision(seat, kind, options, horizon, commit, rollouts, "explicit" if written else "activity_v0", focus, tuple(places), continuation)


def _written(raw: dict, team: int, i: int) -> Written:
    where = f"hypothesis[{i}]"
    enemies = tuple(name for name, seat in SEATS.items() if seat // 5 != team)
    _keys(raw, where, ("name", "weight"), (*enemies, "cleared"))
    plans = []
    for key in sorted(k for k in raw if k in enemies):
        at = f"{where}.{key}"
        note = _keys(raw[key], at, ("activity",), ("path", "to", "xp", "upgrades"))
        activity = Activity[_text(note, "activity", at, tuple(a.name.lower() for a in Activity)).upper()]
        path = note.get("path", [])
        if not isinstance(path, list) or any(name not in CAMPS for name in path) or (path and activity is not Activity.CLEAR):
            raise RecipeError(f"{at}.path: a path is a list of camps named like 'red_gromp', for the activity 'clear' only")
        to = None
        if "to" in note:
            if activity is not Activity.MOVE:
                raise RecipeError(f"{at}.to: a destination is for the activity 'move' only")
            _place(team, note["to"], f"{at}.to")
            to = frame_name(1 - team, _absolute(team, note["to"]))
            if to not in NODES:
                raise RecipeError(f"{at}.to: {note['to']!r} is no node that a champion walks to")
        elif activity is Activity.MOVE:
            raise RecipeError(f"{at}: the activity 'move' needs a destination 'to'")
        plans.append((SEATS[key] % 5, Plan(activity, tuple(CAMPS[name] for name in path), to,
                                           None if "xp" not in note else _number(note, "xp", at, 0.0),
                                           None if "upgrades" not in note else _integer(note, "upgrades", at, 0, 20))))
    cleared = raw.get("cleared", [])
    if not isinstance(cleared, list) or any(name not in CAMPS for name in cleared):
        raise RecipeError(f"{where}.cleared: a list of camps named like 'red_gromp'")
    return Written(_text(raw, "name", where), _number(raw, "weight", where, 1e-9, 1e9), tuple(plans), tuple(CAMPS[name] for name in cleared))


def _absolute(team: int, name: str) -> str:
    """A place of the deciding team's frame by its map name."""
    side, _, rest = name.partition("_")
    if side == "own":
        return f"{TEAMS[team]}_{rest}"
    if side == "enemy":
        return f"{TEAMS[1 - team]}_{rest}"
    return name


def parse(text: str, tick_s: float | None = None) -> Recipe:
    """Check a recipe and give it as typed values. `tick_s` replaces the recipe's tick, so one recipe can be
    materialised at several ticks. The base game keeps its own."""
    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise RecipeError(f"recipe: not valid TOML: {e}") from None
    _keys(raw, "recipe", ("ruleset", "seed", "decision"), ("tick_s", "decision_s", "base", "champion", "lane", "knowledge", "hypothesis"))
    if raw["ruleset"] != RULESET_ID:
        raise RecipeError(f"recipe.ruleset: the recipe is for ruleset {raw['ruleset']!r} and this is {RULESET_ID!r}")
    if "lane" in raw:
        raise RecipeError("recipe.lane: [[lane]] overrides are not supported; a lane's minions carry targets, casts, and missiles "
                          "that counts per kind cannot restore, so a wave state comes from the base game")
    seed = _integer(raw, "seed", "recipe")
    config = _config(raw, tick_s)
    base = None
    if "base" in raw:
        _keys(raw["base"], "base", ("policy", "seed", "until_s"), ("tick_s",))
        base = Base(_text(raw["base"], "policy", "base", tuple(BASE_POLICIES)), _integer(raw["base"], "seed", "base"),
                    _number(raw["base"], "until_s", "base", 0.0, 3600.0), _base_config(raw["base"], config))
    written_raw = raw.get("hypothesis", [])
    if not isinstance(written_raw, list):
        raise RecipeError("recipe.hypothesis: expected [[hypothesis]] tables")
    decision = _decision(raw["decision"], bool(written_raw))
    team = decision.team
    overrides = raw.get("champion", [])
    if not isinstance(overrides, list):
        raise RecipeError("recipe.champion: expected [[champion]] tables")
    overrides = tuple(_override(row, team, f"champion[{i}]") for i, row in enumerate(overrides))
    if len({o.seat for o in overrides}) < len(overrides):
        raise RecipeError("recipe.champion: a seat is overridden twice")
    sightings, camps = _knowledge(raw.get("knowledge", {}), team)
    written = tuple(_written(row, team, i) for i, row in enumerate(written_raw))
    if len({w.name for w in written}) < len(written):
        raise RecipeError("recipe.hypothesis: two hypotheses share a name")
    return Recipe(text, seed, config, base, overrides, sightings, camps, decision, written)


def decision_tick(config: Config, until_s: float) -> int:
    """The first decision tick at or after a clock time."""
    first = config.ticks(until_s)
    return -(-first // config.decision_ticks) * config.decision_ticks


def base_world(recipe: Recipe) -> World:
    """The source world: the base game run on its own tick to the decision tick, or the opening state on the
    recipe's tick without a base."""
    if recipe.base is None:
        return World(recipe.config, recipe.seed)
    config = recipe.base.config
    world = World(config, recipe.base.seed)
    builder = styled(BASE_POLICIES[recipe.base.policy], config.tick_s * config.decision_ticks)
    policies = team_policies(builder, builder)
    for _ in range(decision_tick(config, recipe.base.until_s)):
        advance(world, policies)
    return world


def _set_ledger(c, gold: float) -> None:
    """Give a champion `gold` unspent with its ledger in balance. The author's change is booked as starting gold."""
    c.earned[Income.STARTING] += gold - (sum(c.earned) - spent(c))
    c.gold = gold


def apply(recipe: Recipe, world: World) -> None:
    """Apply a recipe's overrides to the source world: its own champions and the deciding team's memory. These are
    fields that redaction keeps whole, so redacting after this equals overriding the information state. A
    position is set without a new look: what the team sees now stays what its memory records."""
    tick, tick_s = world.tick, world.config.tick_s
    team = recipe.decision.team
    for o in recipe.overrides:
        c = world.champions[o.seat]
        where = f"champion {SEAT_NAMES[o.seat]}"
        if c.hp <= 0:
            raise RecipeError(f"{where}: the champion is dead at the decision tick")
        gold = c.gold
        if o.level is not None:
            c.xp = LEVEL_XP[o.level - 2] if o.level > 1 else 0.0
        if o.upgrades is not None:
            c.upgrades = o.upgrades
        _set_ledger(c, gold if o.gold is None else o.gold)
        can = capability_of(c)
        c.hp = min(c.hp, can.max_hp) if o.health is None else o.health * can.max_hp
        c.mana = min(c.mana, can.max_mana) if o.mana is None else o.mana * can.max_mana
        if o.pos is not None:
            c.pos = o.pos
        if o.intent is not None:
            c.intent, c.intent_tick, c.channel = o.intent, tick, 0
    memory = world.memory[team]
    for s in recipe.sightings:
        record, enemy = memory.enemies[s.role], world.champions[(1 - team) * 5 + s.role]
        where = f"knowledge {SEAT_NAMES[enemy.seat]}"
        if record.seen_tick == tick:
            raise RecipeError(f"{where}: the team sees this champion now, so its record is the view and cannot be overridden")
        if s.pos is None:
            record.pos, record.was, record.hp, record.level, record.upgrades, record.seen_tick = FOUNTAIN[1 - team], None, 0.0, 0, 0, -1
            continue
        seen_tick = round(s.at_s / tick_s)
        if not 0 <= seen_tick < tick:
            raise RecipeError(f"{where}.at_s: a last sighting is before the decision at {tick * tick_s} s")
        public = level_of(enemy.xp)
        level = public if s.level is None else s.level
        if level > public:
            raise RecipeError(f"{where}.level: level {level} is above the champion's public level {public}")
        upgrades = (record.upgrades if record.seen_tick >= 0 else 0) if s.upgrades is None else s.upgrades
        share = (record.hp / capability(ROLES[s.role], max(1, record.level), record.upgrades).max_hp if record.seen_tick >= 0 else 1.0) if s.health is None else s.health
        record.pos, record.was, record.level, record.upgrades, record.seen_tick = s.pos, None, level, upgrades, seen_tick
        record.hp = share * capability(ROLES[s.role], level, upgrades).max_hp
    for note in recipe.camps:
        known = memory.camps[note.camp]
        where = f"knowledge {SITES[note.camp].node}"
        if known.seen_tick == tick:
            raise RecipeError(f"{where}: the team sees this camp now")
        if note.seen_s is None:
            memory.camps[note.camp] = CampMemory(0.0, 0, -1, -1)
            continue
        seen_tick = round(note.seen_s / tick_s)
        spawn_tick = -1 if note.spawn_s is None else round(note.spawn_s / tick_s)
        if not 0 <= seen_tick < tick or (spawn_tick >= 0 and spawn_tick <= seen_tick):
            raise RecipeError(f"{where}: a camp is seen before the decision, and a known spawn falls after the sighting")
        kind = SITES[note.camp].kind
        memory.camps[note.camp] = CampMemory(kind.health(note.level) if note.alive else 0.0, note.level if note.alive else 0, seen_tick, spawn_tick)
    try:
        check_invariants(world)
    except Exception as e:
        raise RecipeError(f"recipe: the overridden state breaks an invariant: {e}") from None


@dataclass(frozen=True, slots=True)
class Meta:
    """What a saved scenario was made under. `code` is the stamp of the `riftgame` sources and rulesets.
    `base_tick_s` is the tick on which the decision state was built before its refinement to `config`."""

    ruleset_id: str
    map_id: str
    config: Config
    seed: int
    tick: int
    base_tick_s: float
    recipe: str
    code: str


@dataclass(frozen=True, slots=True)
class Scenario:
    """A materialised scenario: the deciding team's information state, the decision, the hypotheses of every
    comparison line, and the source world kept apart for the hindsight line. `rejected` holds what the generator
    dropped, as (name, reason)."""

    meta: Meta
    decision: Decision
    info: InfoState
    hypotheses: tuple[Hypothesis, ...]
    rejected: tuple[tuple[str, str], ...]
    hindsight: Snapshot | None

    @property
    def hidden_enemies(self) -> int:
        """Enemy champions that are alive and out of the deciding team's view at the decision tick."""
        world = self.info.world()
        enemies = world.champions[(1 - self.decision.team) * 5:(2 - self.decision.team) * 5]
        return sum(c.hp > 0 and not seen for c, seen in zip(enemies, self.info.seen))


def code_stamp() -> str:
    """A digest of every source file of `riftgame` and its rulesets, line endings normalised."""
    lines = "".join(f"{path.relative_to(SOURCES).as_posix()}:{hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()}\n"
                    for path in sorted([*SOURCES.glob("*.py"), *SOURCES.glob("rulesets/*.toml")]))
    return hashlib.sha256(lines.encode()).hexdigest()[:16]


def _plan(plan: Plan) -> str:
    if plan.activity is Activity.CLEAR:
        return "clear " + ", ".join(SITES[i].node for i in plan.path)
    return f"move to {plan.to}" if plan.activity is Activity.MOVE else plan.activity.name.lower()


def _hypotheses(recipe: Recipe, info: InfoState) -> tuple[tuple[Hypothesis, ...], tuple[tuple[str, str], ...]]:
    """The hypotheses of every comparison line with normalised weights, and the plans that the generator dropped."""
    decision = recipe.decision
    enemy = (1 - decision.team) * 5
    try:
        if not recipe.written:
            made = generate(info, decision.focus)
            return made.hypotheses, tuple((f"{SEAT_NAMES[enemy + d.role]} {_plan(d.plan)}", d.reason.name) for d in made.dropped)
        total = sum(w.weight for w in recipe.written)
        out = []
        for w in recipe.written:
            plans = dict(w.plans)
            written = Hypothesis(w.name, w.weight / total, tuple(plans.get(role) for role in range(5)), w.cleared)
            try:
                done = complete(info, written)
                check(info, done)
            except Rejected as e:
                raise RecipeError(f"hypothesis {w.name!r}: rejected, {e}") from None
            out.append(done)
        return tuple(out), ()
    except Rejected as e:
        raise RecipeError(f"hypothesis: the generator found none, {e}") from None


def build(recipe: Recipe, source: World) -> Scenario:
    """Materialise a recipe on a source world at its decision tick, on the base game's clock. The source is changed
    by the overrides, refined to the recipe's tick, and kept, as a snapshot, for the hindsight line alone."""
    decision = recipe.decision
    if source.tick % source.config.decision_ticks:
        raise RecipeError(f"recipe: tick {source.tick} is not a decision tick")
    apply(recipe, source)
    base_tick_s = source.config.tick_s
    source = refine(source, recipe.config.tick_s)
    info = redact(source, decision.team)
    observations = observe_team(info.world(), decision.team)
    if observations[decision.seat % 5].me.hp <= 0:
        raise RecipeError("decision.seat: the deciding champion is dead at the decision tick")
    for a in decision.alternatives:
        for seat, action in a.actions:
            if not legal_mask(observations[seat % 5])[action]:
                raise RecipeError(f"decision.alternatives: {a.name!r} gives {SEAT_NAMES[seat]} {spell(action)}, which its mask forbids at the decision tick")
    hypotheses, rejected = _hypotheses(recipe, info)
    if not hypotheses:
        raise RecipeError("hypothesis: no hypothesis survives the checks")
    meta = Meta(RULESET_ID, MAP_ID, source.config, recipe.seed, source.tick, base_tick_s, recipe.text, code_stamp())
    return Scenario(meta, decision, info, hypotheses, rejected, source.snapshot())


def load(text: str, tick_s: float | None = None) -> Scenario:
    """Parse a recipe, run its base game, and materialise it."""
    recipe = parse(text, tick_s)
    return build(recipe, base_world(recipe))


def save(scenario: Scenario, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps(scenario, protocol=pickle.HIGHEST_PROTOCOL))


def restore(path: Path) -> Scenario:
    """A saved scenario, refused if it was made under another ruleset, map, or code stamp."""
    scenario = pickle.loads(Path(path).read_bytes())
    meta = scenario.meta
    if (meta.ruleset_id, meta.map_id) != (RULESET_ID, MAP_ID):
        raise ValueError(f"scenario of ruleset {meta.ruleset_id} on map {meta.map_id} cannot be restored into ruleset {RULESET_ID} on map {MAP_ID}")
    code = code_stamp()
    if meta.code != code:
        raise ValueError(f"scenario made under code {meta.code} cannot be restored under code {code}; materialise its recipe again")
    return scenario
