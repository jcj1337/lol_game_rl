"""Break the code on purpose and count the tests that notice.

Each mutation replaces one piece of source text in a temporary copy of the repository and runs the named tests
there. The working tree is never touched. A mutation that no test notices is reported as SURVIVED.

Run: python -m experiments.m8.mutations
Run a subset: python -m experiments.m8.mutations "draw key" "attack credit"
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COPIED = ("riftgame", "tests", "pyproject.toml")
LANES, WORLD, CHAMPIONS, VISION, ECONOMY = (f"riftgame/{name}.py" for name in ("lanes", "world", "champions", "vision", "economy"))
LANE_TESTS = "tests/test_lanes.py"
KERNEL_TESTS = " ".join(f"tests/test_world_{name}.py" for name in ("clock", "intents", "roles", "snapshot", "observation", "soak"))
ECONOMY_TESTS = "tests/test_economy.py"
TIMEOUT_S = 300

MUTATIONS = [
    ("a tower shot ignores the minion kind's share", LANES, "target.rules.tower_shot_pct * target.max_hp", "0.45 * target.max_hp", LANE_TESTS),
    ("gold is paid for every minion death", LANES, "gold = target.gold if killer is not None else 0", "gold = target.gold", LANE_TESTS),
    ("a champion that stepped aside still hits", LANES, "return inp.in_path and inp.mode is not Mode.PASSIVE", "return inp.mode is not Mode.PASSIVE", LANE_TESTS),
    ("minions attack a champion that stepped aside", LANES, "in_path = [c for c in inputs if c.in_path and self.rules.champion_aggro]", "in_path = [c for c in inputs if self.rules.champion_aggro]", LANE_TESTS),
    ("the side-lane speed bonus applies in mid", LANES, "self.rules.side_lane_speed and self.geometry.side and", "self.rules.side_lane_speed and", LANE_TESTS),
    ("the pushing advantage ignores its start time", LANES, "or self._t0 < PUSHING[\"start_s\"] or", "or", LANE_TESTS),
    ("the pushing advantage ignores fallen towers", LANES, "towers = max(0, fallen[1 - ahead] - fallen[ahead])", "towers = 0", LANE_TESTS),
    ("the call for help reaches any distance", LANES, "if abs(caller.s - m.s) <= CALL_RANGE + EPS:", "if True:", LANE_TESTS),
    ("a minion that attacks a tower answers the call", LANES, "if callers and type(target) is not Tower:", "if callers:", LANE_TESTS),
    ("minions march past a standing tower", LANES, "room = min(room, abs(tower.s - m.s) - stop)", "pass", LANE_TESTS),
    ("minions are never removed at the base", LANES, "if tower is None and room <= EPS:", "if False:", LANE_TESTS),
    ("the lane leaves a minion's health out of its values", LANES, "(m.uid, m.rules.kind.value, m.s, m.hp, m.max_hp,", "(m.uid, m.rules.kind.value, m.s, m.max_hp,", LANE_TESTS),
    ("the draw key leaves the lane out", LANES, "keyed_uniform(self.seed, Stream.MINION_TARGET, self.lane_id, *key)", "keyed_uniform(self.seed, Stream.MINION_TARGET, 0, *key)", LANE_TESTS),
    ("every champion kill is marked as a shared support kill", LANES, "if choice and inp.execute_below > 0:", "if choice:", LANE_TESTS),
    ("a holding champion stands at the wave instead of the hold line", LANES, "s = own if own is not None and beyond(own, hold_line) else hold_line", "s = foe - heading * STAND_OFF", LANE_TESTS),
    ("a minion hits a champion in reach although an enemy minion is in acquisition range", LANES,
     "if not self.rules.m7_resolution and any(foe.hp > 0 and abs(foe.s - m.s) <= ACQUIRE + EPS for foe in self.minions[1 - m.team]):", "if False:", LANE_TESTS),
    ("champions that attack at the same instant are served in input order", LANES,
     "inputs = sorted(inputs, key=lambda inp: keyed_uniform(self.seed, Stream.LAST_HIT, self.lane_id, self.tick, inp.seat))", "inputs = list(inputs)", LANE_TESTS),
    ("a champion that leaves the lane keeps its attack credit", LANES, "for seat, credit in self._champion_credit.items() if seat in present}", "for seat, credit in self._champion_credit.items()}", LANE_TESTS),
    ("KEEP resets progress", WORLD, "            if action == KEEP:\n                continue\n", "            if action == KEEP:\n                c.channel = 0\n                continue\n", KERNEL_TESTS),
    ("the same action again resets progress", WORLD, "            if action != c.intent:\n", "            if True:\n", KERNEL_TESTS),
    ("a replaced intent records an outcome", WORLD, "                c.intent, c.intent_tick, c.channel = action, self.tick, 0\n",
     "                c.intent, c.intent_tick, c.channel = action, self.tick, 0\n                c.outcome, c.outcome_tick = Outcome.INTERRUPTED, self.tick\n", KERNEL_TESTS),
    ("a finished intent stays standing", CHAMPIONS, "    c.intent, c.channel, c.outcome, c.outcome_tick = HOLD, 0, outcome, tick\n", "    c.channel, c.outcome, c.outcome_tick = 0, outcome, tick\n", KERNEL_TESTS),
    ("the allowance stops at zero", WORLD, "c.allowance = min(config.roam_cap_s, c.allowance + rates[state])", "c.allowance = max(0.0, min(config.roam_cap_s, c.allowance + rates[state]))", KERNEL_TESTS),
    ("a returning laner is charged as roaming", CHAMPIONS, "    return Duty.RETURNING if RETURNS[c.seat % 5][c.intent] or on_fountain(c) else Duty.ROAMING", "    return Duty.RETURNING if on_fountain(c) else Duty.ROAMING", KERNEL_TESTS),
    ("a walk to the enemy base counts as a way home", CHAMPIONS, ' - {"enemy_base"}', "", KERNEL_TESTS),
    ("a laner with no allowance may hold off its lane", VISION, "(leash is Leash.HOME and a.kind is Kind.HOLD)", "a.kind is Kind.HOLD", KERNEL_TESTS),
    ("assignments never end on the clock", CHAMPIONS, "    if world.tick * config.tick_s >= config.assignments_end_s:\n        return None\n", "", KERNEL_TESTS),
    ("junglers get a home lane", CHAMPIONS, 'HOME = ("top", None, "mid", "bot", "bot")', 'HOME = ("top", "mid", "mid", "bot", "bot")', KERNEL_TESTS),
    ("the digest hashes object ids", WORLD, "self.champions, [self.lanes[name].values() for name in LANES])", "self.champions, [self.lanes[name].values() for name in LANES], [id(c) for c in self.champions])", KERNEL_TESTS),
    ("the digest leaves the lanes out", WORLD, "self.champions, [self.lanes[name].values() for name in LANES])", "self.champions, [])", KERNEL_TESTS),
    ("a restored world shares its champions with the snapshot", WORLD, "world.champions = copy.deepcopy(list(snapshot.champions))", "world.champions = list(snapshot.champions)", KERNEL_TESTS),
    ("a snapshot shares its lanes with the world", WORLD, "tuple(copy.deepcopy(self.lanes[name]) for name in LANES))", "tuple(self.lanes[name] for name in LANES))", KERNEL_TESTS),
    ("an enemy champion leaks into the observation", VISION, "    return Observation(world.tick * world.config.tick_s, me, tuple(views))",
     "    return Observation(world.tick * world.config.tick_s, me, tuple(views) + (_view(world, world.champions[(seat + 5) % 10]),))", KERNEL_TESTS),
    ("red positions are not put in red's frame", VISION, "    route, start, sign = _FRAME_EDGES[team][pos.edge]", "    route, start, sign = _FRAME_EDGES[0][pos.edge]", KERNEL_TESTS),
    ("red action targets resolve to blue nodes", CHAMPIONS, "DEST = tuple(tuple(NODE_POS[team][a.target] if", "DEST = tuple(tuple(NODE_POS[0][a.target] if", KERNEL_TESTS),
    ("a follower chases positions already moved this tick", CHAMPIONS, "    return stood[ally] if world.champions[ally].hp > 0 else None", "    return world.champions[ally].pos if world.champions[ally].hp > 0 else None", KERNEL_TESTS),
    ("durations round down", WORLD, "return math.ceil(seconds / self.tick_s - 1e-9)", "return math.floor(seconds / self.tick_s + 1e-9)", KERNEL_TESTS),
    ("a respawn comes one tick late", WORLD, "c.respawn_tick = self.tick + self.config.ticks(", "c.respawn_tick = self.tick + 1 + self.config.ticks(", KERNEL_TESTS),
    ("damage does not interrupt a recall", WORLD, "        if ACTIONS[c.intent].kind is Kind.RECALL:\n            finish(c, Outcome.INTERRUPTED, self.tick)\n", "", KERNEL_TESTS),
    ("a recall on the fountain channels like any other", CHAMPIONS, "    if c.channel < world.config.ticks(RECALL_S) and not on_fountain(c):", "    if c.channel < world.config.ticks(RECALL_S):", KERNEL_TESTS),
    ("a dead champion may be given an action", WORLD, "            if c.hp <= 0:\n                raise InvariantError(f\"seat {c.seat} is dead and was given {ACTIONS[action]}\")\n", "", KERNEL_TESTS),
    ("actions are accepted on any tick", WORLD, "        if self.tick % self.config.decision_ticks:\n            raise ValueError(f\"tick {self.tick} is not a decision tick\")\n", "", KERNEL_TESTS),
    ("a shared kill pays the minion's gold twice", ECONOMY, "                pay(partner, Income.MINION, e.gold)\n", "                pay(partner, Income.MINION, e.gold)\n                pay(killer, Income.MINION, e.gold)\n", ECONOMY_TESTS),
    ("a charge is not used up by a shared kill", ECONOMY, "                killer.item_charges -= 1\n", "", ECONOMY_TESTS),
    ("minion gold is booked as passive gold", ECONOMY, "            else:\n                pay(killer, Income.MINION, e.gold)", "            else:\n                pay(killer, Income.PASSIVE, e.gold)", ECONOMY_TESTS),
    ("minion XP is not split", ECONOMY, "xp_share(e.xp, len(sharers))", "xp_share(e.xp, 1)", ECONOMY_TESTS),
    ("XP range is a walk and not a straight line", ECONOMY, "RIFT.separation(c.pos, where) <= XP_RANGE", "RIFT.distance(c.pos, where) <= XP_RANGE", ECONOMY_TESTS),
    ("a dead champion gets XP", ECONOMY, "c.team != e.team and c.hp > 0 and RIFT", "c.team != e.team and RIFT", ECONOMY_TESTS),
    ("a jungler gets full lane XP", ECONOMY, "    if c.role != JUNGLE or now_s", "    if True or now_s", ECONOMY_TESTS),
    ("passive gold starts at 0:00", ECONOMY, 'if now_s >= ECONOMY["passive_gold_start_s"] else 0.0', "if True else 0.0", ECONOMY_TESTS),
    ("a support charge arrives every tick", ECONOMY, "            if charge_due:", "            if True:", ECONOMY_TESTS),
    ("a support shares a kill with no ally in range", ECONOMY, " and charge_partner(world, c) is not None:", ":", ECONOMY_TESTS),
    ("minion blows do not hurt champions", WORLD, "            hits += economy.minion_hits(events)\n", "", ECONOMY_TESTS),
    ("champions do not regenerate health", WORLD, "                c.hp = min(can.max_hp, c.hp + can.hp_regen * config.tick_s)", "                pass", ECONOMY_TESTS),
    ("the lanes never get the level lead", WORLD, "economy.lane_inputs(self, name), lead)", "economy.lane_inputs(self, name), 0.0)", ECONOMY_TESTS),
    ("a champion in a lane is no input to it", ECONOMY, "        if mine is None or mine[0] != lane or s is None:\n            continue", "        if True:\n            continue", ECONOMY_TESTS),
    ("a laner stands at its tower whatever the wave does", CHAMPIONS, "    return RIFT.lane_pos(lane, s)", "    return OUTER_TOWER[seat // 5][lane]", ECONOMY_TESTS),
]


def failures(tree: Path, tests: str) -> int | None:
    try:
        run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests.split()], cwd=tree, capture_output=True, text=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return None
    if run.returncode == 0:
        return 0
    tail = run.stdout.strip().splitlines()[-1] if run.stdout.strip() else ""
    return 1 if "failed" in tail or "error" in tail else None


def main() -> int:
    survived = 0
    with tempfile.TemporaryDirectory() as scratch:
        tree = Path(scratch) / "tree"
        tree.mkdir()
        for name in COPIED:
            source = ROOT / name
            if source.is_dir():
                shutil.copytree(source, tree / name, ignore=shutil.ignore_patterns("__pycache__"))
            else:
                shutil.copy(source, tree / name)
        chosen = [m for m in MUTATIONS if not sys.argv[1:] or any(word in m[0] for word in sys.argv[1:])]
        for label, path, old, new, tests in chosen:
            target = tree / path
            original = target.read_text(encoding="utf-8")
            if original.count(old) != 1:
                print(f"STALE     {label}: the text to replace occurs {original.count(old)} times in {path}")
                survived += 1
                continue
            target.write_text(original.replace(old, new), encoding="utf-8")
            result = failures(tree, tests)
            target.write_text(original, encoding="utf-8")
            status = "caught" if result else "SURVIVED" if result == 0 else "ERROR"
            survived += status != "caught"
            print(f"{status:<9} {label}")
        clean = failures(tree, " ".join(sorted({tests for *_, tests in chosen})))
        print(f"unmutated copy: {'passes' if clean == 0 else 'FAILS'}")
    print(f"{len(chosen) - survived} of {len(chosen)} mutations caught")
    return 1 if survived or clean != 0 else 0


if __name__ == "__main__":
    sys.exit(main())
