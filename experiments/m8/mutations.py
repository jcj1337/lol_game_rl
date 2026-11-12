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
RECALL_TESTS = "tests/test_recall.py"
JUNGLE = "riftgame/jungle.py"
JUNGLE_TESTS = "tests/test_jungle.py tests/test_world_observation.py"
COMBAT = "riftgame/combat.py"
COMBAT_TESTS = "tests/test_combat.py"
VISION_TESTS = "tests/test_vision.py"
TIMEOUT_S = 300

MUTATIONS = [
    ("a tower shot ignores the minion kind's share", LANES, "target.rules.tower_shot_pct * target.max_hp", "0.45 * target.max_hp", LANE_TESTS),
    ("gold is paid for every minion death", LANES, "gold = target.gold if killer is not None else 0", "gold = target.gold", LANE_TESTS),
    ("a champion that stepped aside still hits", LANES, "return inp.in_path and inp.mode is not Mode.PASSIVE", "return inp.mode is not Mode.PASSIVE", LANE_TESTS),
    ("minions attack a champion that stepped aside", LANES, "in_path = [stand[c.seat] for c in inputs if c.in_path and self.rules.champion_aggro and", "in_path = [stand[c.seat] for c in inputs if self.rules.champion_aggro and", LANE_TESTS),
    ("the side-lane speed bonus applies in mid", LANES, "self.rules.side_lane_speed and self.geometry.side and", "self.rules.side_lane_speed and", LANE_TESTS),
    ("the pushing advantage ignores its start time", LANES, "or self._t0 < PUSHING[\"start_s\"] or", "or", LANE_TESTS),
    ("the pushing advantage ignores fallen towers", LANES, "towers = max(0, fallen[1 - ahead] - fallen[ahead])", "towers = 0", LANE_TESTS),
    ("the call for help reaches any distance", LANES, "if apart(caller, m) <= CALL_RANGE + EPS:", "if True:", LANE_TESTS),
    ("a minion that attacks a tower answers the call", LANES, "if callers and (type(target) is not Tower or (first_wave_call and m.wave == 1)):", "if callers:", LANE_TESTS),
    ("minions march past a standing tower", LANES, "room = min(room, abs(tower.s - m.s) - stop)", "pass", LANE_TESTS),
    ("minions are never removed at the base", LANES, "if tower is None and room <= EPS:", "if False:", LANE_TESTS),
    ("the lane leaves a minion's health out of its values", LANES, "(m.uid, m.rules.kind.value, m.s, m.hp, m.max_hp,", "(m.uid, m.rules.kind.value, m.s, m.max_hp,", LANE_TESTS),
    ("the draw key leaves the lane out", LANES, "keyed_uniform(self.seed, Stream.MINION_TARGET, self.lane_id, *key)", "keyed_uniform(self.seed, Stream.MINION_TARGET, 0, *key)", LANE_TESTS),
    ("every champion kill is marked as a shared support kill", LANES, "if choice and inp.execute_below > 0:", "if choice:", LANE_TESTS),
    ("a holding champion stands at the wave instead of the hold line", LANES, "s = own if own is not None and beyond(own, hold_line) else hold_line", "s = foe - heading * STAND_OFF", LANE_TESTS),
    ("a minion hits a champion in reach although an enemy minion is in acquisition range", LANES,
     "if not self.rules.m7_resolution and any(foe.hp > 0 and self._range(foe, m) <= ACQUIRE + EPS for foe in self.minions[1 - m.team]):", "if False:", LANE_TESTS),
    ("champions that attack at the same instant are served in input order", LANES,
     "inputs = sorted(inputs, key=lambda inp: keyed_uniform(self.seed, Stream.LAST_HIT, self.lane_id, self.tick, inp.seat))", "inputs = list(inputs)", LANE_TESTS),
    ("a champion that leaves the lane keeps its attack credit", LANES, "for seat, credit in self._champion_credit.items() if seat in present}", "for seat, credit in self._champion_credit.items()}", LANE_TESTS),
    ("a range inside the lane is a walk along the lane", LANES, "self._straight = rules.straight_ranges", "self._straight = False", LANE_TESTS),
    ("a champion under a tower is attacked for standing in the path", LANES,
     "return any(tower.hp > 0 and self._range(tower, spot) <= TOWER_RANGE + EPS for team in Team for tower in self.towers[team])", "return False", LANE_TESTS),
    ("a fallen tower still shelters a champion", LANES, "return any(tower.hp > 0 and self._range(tower, spot) <= TOWER_RANGE + EPS for team",
     "return any(self._range(tower, spot) <= TOWER_RANGE + EPS for team", LANE_TESTS),
    ("every wave answers a call for help while it attacks a tower", LANES, "or (first_wave_call and m.wave == 1)):", "or first_wave_call):", LANE_TESTS),
    ("a blow leaves the minion when the cast starts", LANES, "m.swing = t0 + start + m.rules.cast_s", "m.swing = t0 + start", LANE_TESTS),
    ("a missile lands at once", LANES, "land = now + self._range(m, target) / m.rules.missile_speed", "land = now", LANE_TESTS),
    ("a cancelled cast costs nothing", LANES, "began = max(min(died, now), now - m.rules.cast_s)", "began = now - m.rules.cast_s", LANE_TESTS),
    ("a cancelled cast costs the whole cast", LANES, "began = max(min(died, now), now - m.rules.cast_s)", "began = now", LANE_TESTS),
    ("a missile to a dead target still lands", LANES, "target = aimed if aimed.hp > 0 else None", "target = aimed", LANE_TESTS),
    ("the lane digest leaves out when a dead target died", LANES, "return (0, target.uid, target.hp > 0, target.died_at)", "return (0, target.uid, target.hp > 0)", LANE_TESTS),
    ("the lane digest leaves out how long a placed minion waits", LANES, "_target_code(m.aimed), m.delay)", "_target_code(m.aimed))", LANE_TESTS),
    ("the M8 lane runs on M7's graph", LANES, "REFERENCE_MAP if rules.m7_map else MAP_ID", "REFERENCE_MAP", LANE_TESTS),
    ("the M7 lane runs on the M8 map", LANES, "REFERENCE_MAP if rules.m7_map else MAP_ID", "MAP_ID", LANE_TESTS),
    ("the lane leaves its missiles out of its values", LANES, "tuple(sorted(self._champion_credit.items())), missiles)", "tuple(sorted(self._champion_credit.items())), ())", LANE_TESTS),
    ("a lane action ignores its stand", CHAMPIONS, "known_front(world, seat // 5, lane), hold=hold)", "known_front(world, seat // 5, lane), hold=False)", KERNEL_TESTS),
    ("a champion on the hold line is not in the minions' path", ECONOMY, "can.attack_range, fronts[c.team], hold=mine[2])", "can.attack_range, fronts[c.team], hold=False)", ECONOMY_TESTS),
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
    ("a lane waypoint is a MOVE target", CHAMPIONS, ' if node not in ADDED["map"]["lane_waypoints"])', ")", KERNEL_TESTS),
    ("junglers get a home lane", CHAMPIONS, 'HOME = ("top", None, "mid", "bot", "bot")', 'HOME = ("top", "mid", "mid", "bot", "bot")', KERNEL_TESTS),
    ("the digest hashes object ids", WORLD, "self.champions, [self.lanes[name].values() for name in LANES])", "self.champions, [self.lanes[name].values() for name in LANES], [id(c) for c in self.champions])", KERNEL_TESTS),
    ("the digest leaves the lanes out", WORLD, "self.champions, [self.lanes[name].values() for name in LANES])", "self.champions, [])", KERNEL_TESTS),
    ("a restored world shares its champions with the snapshot", WORLD, "world.champions = copy.deepcopy(list(snapshot.champions))", "world.champions = list(snapshot.champions)", KERNEL_TESTS),
    ("a snapshot shares its lanes with the world", WORLD, "tuple(copy.deepcopy(self.lanes[name]) for name in LANES))", "tuple(self.lanes[name] for name in LANES))", KERNEL_TESTS),
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
    ("the lanes never get the level lead", WORLD, "economy.lane_inputs(self, name, calls), lead)", "economy.lane_inputs(self, name, calls), 0.0)", ECONOMY_TESTS),
    ("a champion in a lane is no input to it", ECONOMY, "        if c.hp <= 0:\n            continue", "        if True:\n            continue", ECONOMY_TESTS),
    ("a laner stands at its tower whatever the wave does", CHAMPIONS, "    return RIFT.lane_pos(lane, s)", "    return OUTER_TOWER[seat // 5][lane]", ECONOMY_TESTS),
    ("the fountain is twice as wide", CHAMPIONS, '<= R["fountain"]["regen_radius"]', '<= 2 * R["fountain"]["regen_radius"]', RECALL_TESTS),
    ("the rules of the fountain apply off the fountain", CHAMPIONS, "    if not on_fountain(c):\n        if c.homeguard_tick != NO_HOMEGUARD", "    if False:\n        if c.homeguard_tick != NO_HOMEGUARD", RECALL_TESTS),
    ("the fountain heals the dead", CHAMPIONS, "    if c.hp > 0:\n        can, config = capability_of(c), world.config\n", "    if True:\n        can, config = capability_of(c), world.config\n", RECALL_TESTS),
    ("the fountain restores no mana", CHAMPIONS, '        c.mana = min(can.max_mana, c.mana + FOUNTAIN_REGEN["mana_regen_per_s"] * can.max_mana * config.tick_s)\n', "", RECALL_TESTS),
    ("the fountain restores health at the mana rate", CHAMPIONS, 'c.hp + FOUNTAIN_REGEN["hp_regen_per_s"] * can.max_hp', 'c.hp + FOUNTAIN_REGEN["mana_regen_per_s"] * can.max_hp', RECALL_TESTS),
    ("a champion shops off its fountain", CHAMPIONS, "            c.homeguard_tick = NO_HOMEGUARD\n        return\n", "            c.homeguard_tick = NO_HOMEGUARD\n        shop(c)\n        return\n", RECALL_TESTS),
    ("the dead do not shop", CHAMPIONS, "            c.homeguard_tick = next_move\n    shop(c)\n", "            c.homeguard_tick = next_move\n        shop(c)\n", RECALL_TESTS),
    ("a purchase ignores the cost", CHAMPIONS, "        c.gold -= progression[c.upgrades].cost\n", "", RECALL_TESTS),
    ("the exact price does not buy", CHAMPIONS, "and c.gold >= progression[c.upgrades].cost:", "and c.gold > progression[c.upgrades].cost:", RECALL_TESTS),
    ("a champion buys one upgrade per tick", CHAMPIONS, "    while c.upgrades < len(progression) and", "    if c.upgrades < len(progression) and", RECALL_TESTS),
    ("a champion buys its progression from the cheapest entry up", CHAMPIONS, "    progression = PROGRESSIONS[ROLES[c.seat % 5]]\n    while", "    progression = sorted(PROGRESSIONS[ROLES[c.seat % 5]], key=lambda upgrade: upgrade.cost)\n    while", RECALL_TESTS),
    ("a new champion keeps its starting gold", CHAMPIONS, '    pay(c, Income.STARTING, _E["starting_gold"])\n    shop(c)\n', '    pay(c, Income.STARTING, _E["starting_gold"])\n', RECALL_TESTS),
    ("capability reads unspent gold", CHAMPIONS, "    return capability(ROLES[c.seat % 5], level_of(c.xp), c.upgrades)", "    return capability(ROLES[c.seat % 5], level_of(c.xp), c.upgrades + (c.gold >= 5000))", RECALL_TESTS),
    ("upgrades change no capability", CHAMPIONS, "    for upgrade in PROGRESSIONS[profile][:upgrades]:", "    for upgrade in ():", RECALL_TESTS),
    ("the second boots step costs the whole tier-2 price", CHAMPIONS, 'tier2 = Upgrade(listed["boots_tier2_gold"] - tier1.cost,', 'tier2 = Upgrade(listed["boots_tier2_gold"],', RECALL_TESTS),
    ("the second boots step adds the whole tier-2 speed", CHAMPIONS, '{"move_speed": boots["boots_tier2_speed"] - boots["boots_tier1_speed"]})', '{"move_speed": boots["boots_tier2_speed"]})', RECALL_TESTS),
    ("the gold invariant is not checked", WORLD, "        if abs(sum(c.earned) - spent(c) - c.gold) > GOLD_TOLERANCE:", "        if False:", RECALL_TESTS),
    ("homeguard does not speed a champion up", WORLD, "c.pos = RIFT.advance(c.pos, dest, speed_of(self, c) * tick_s)", "c.pos = RIFT.advance(c.pos, dest, capability_of(c).move_speed * tick_s)", RECALL_TESTS),
    ("homeguard is there before its start time", CHAMPIONS, 'if next_move >= max(config.ticks(HOMEGUARD["start_s"]), c.homeguard_block):', "if next_move >= c.homeguard_block:", RECALL_TESTS),
    ("homeguard never ends", CHAMPIONS, "        if c.homeguard_tick != NO_HOMEGUARD and not in_homeguard_zone(c.seat // 5, c.pos):", "        if False:", RECALL_TESTS),
    ("homeguard ends at the outer tower and not before it", CHAMPIONS, 't.s + (2 * i - 1) * HOMEGUARD["ends_before_outer_tower"]', "t.s", RECALL_TESTS),
    ("the homeguard endpoint of red is not mirrored", CHAMPIONS, "            return s < end if team == 0 else s > end", "            return s < end", RECALL_TESTS),
    ("homeguard holds on jungle and river edges", CHAMPIONS, "            return s < end if team == 0 else s > end\n    return False", "            return s < end if team == 0 else s > end\n    return True", RECALL_TESTS),
    ("homeguard does not decay", CHAMPIONS, '    decayed = min(1.0, max(0.0, off_fountain_s) / HOMEGUARD["decay_s"])', "    decayed = 0.0", RECALL_TESTS),
    ("homeguard decays from the start of the move that leaves the fountain", CHAMPIONS, "(world.tick - c.homeguard_tick - 0.5)", "(world.tick - c.homeguard_tick + 0.5)", RECALL_TESTS),
    ("the decaying bonus is read at the start of the tick", CHAMPIONS, "(world.tick - c.homeguard_tick - 0.5)", "(world.tick - c.homeguard_tick - 1)", RECALL_TESTS),
    ("damage does not end homeguard", WORLD, "        enter_combat(self, c)\n", "", RECALL_TESTS),
    ("combat ends homeguard and does not block it", CHAMPIONS, '    c.homeguard_block = world.tick + world.config.ticks(HOMEGUARD["blocked_after_combat_s"])\n', "", RECALL_TESTS),
    ("the block after combat is ignored", CHAMPIONS, 'if next_move >= max(config.ticks(HOMEGUARD["start_s"]), c.homeguard_block):', 'if next_move >= config.ticks(HOMEGUARD["start_s"]):', RECALL_TESTS),
    ("the observation hides homeguard", VISION, "homeguard=homeguard_bonus(world, c),", "homeguard=0.0,", RECALL_TESTS),
    ("the observation hides the homeguard block", VISION, "homeguard_blocked_s=max(0, c.homeguard_block - world.tick) * tick_s,", "homeguard_blocked_s=0.0,", RECALL_TESTS),
    ("a camp respawns from its first spawn and not from its death", JUNGLE, "            world.camps[i].spawn_tick = tick + config.ticks(kind.respawn_s)",
     "            world.camps[i].spawn_tick = config.ticks(kind.first_spawn_s) + config.ticks(kind.respawn_s)", JUNGLE_TESTS),
    ("the scuttlers wait until every other camp is cleared", JUNGLE, "    due = [i for i, camp in enumerate(world.camps) if 0 <= camp.spawn_tick <= tick]",
     "    due = [i for i, camp in enumerate(world.camps) if 0 <= camp.spawn_tick <= tick and not (SITES[i].kind.scuttler and any(c.hp > 0 for c in world.camps))]", JUNGLE_TESTS),
    ("the first scuttlers spawn at full health", JUNGLE, "first=tick == world.config.ticks(kind.first_spawn_s))", "first=False)", JUNGLE_TESTS),
    ("a scuttler respawns while one of the first two lives", JUNGLE, " and not any(world.camps[i].hp > 0 for i in SCUTTLERS):", ":", JUNGLE_TESTS),
    ("the next scuttler always spawns at the top river node", JUNGLE, "        river = SCUTTLERS[int(keyed_uniform(seed, Stream.CAMP, tick) * len(SCUTTLERS))]", "        river = SCUTTLERS[0]", JUNGLE_TESTS),
    ("a camp spawns at level 1 whatever the champions' levels", JUNGLE, "    level = math.floor(sum(level_of(c.xp) for c in world.champions) / len(world.champions) + 0.5)", "    level = 1", JUNGLE_TESTS),
    ("an average champion level of a half rounds down", JUNGLE, " / len(world.champions) + 0.5)", " / len(world.champions))", JUNGLE_TESTS),
    ("a champion hits a camp from anywhere", JUNGLE, " or c.pos != DEST[team][c.intent]:", ":", JUNGLE_TESTS),
    ("only the hardest blow of a tick counts", JUNGLE, "        camp.hp -= math.fsum(dealt for dealt, _, _ in struck[i])", "        camp.hp -= max(struck[i])[0]", JUNGLE_TESTS),
    ("a camp turns on every champion that hits it", JUNGLE, "        if camp.engaged < 0:\n            camp.engaged = leader\n", "        camp.engaged = leader\n", JUNGLE_TESTS),
    ("the killer is the first seat that hit and not the hardest hitter", JUNGLE, "        leader = max(struck[i])[2]", "        leader = struck[i][0][2]", JUNGLE_TESTS),
    ("a camp keeps hitting a champion outside its leash", JUNGLE, "            if c.hp > 0 and RIFT.separation(c.pos, site.pos) <= LEASH:", "            if c.hp > 0:", JUNGLE_TESTS),
    ("a camp never resets", JUNGLE, "            camp.hp = camp.max_hp\n", "            pass\n", JUNGLE_TESTS),
    ("a camp resets although another champion fights it", JUNGLE, " and not any(c.hp > 0 for c in fighters(world, i)):", ":", JUNGLE_TESTS),
    ("every camp has the buff camps' timer window", JUNGLE, 'window = CAMPS["timer_window_buff_s" if name in BUFFS else "timer_window_other_s"]', 'window = CAMPS["timer_window_buff_s"]', JUNGLE_TESTS),
    ("camp hits never reach the champions", WORLD, "        hits, blows = jungle.collect(self)", "        hits, blows = [], jungle.collect(self)[1]", JUNGLE_TESTS),
    ("a champion at a camp that dies gets no cleared outcome", WORLD, "                finish(c, Outcome.CLEARED, self.tick)\n", "                pass\n", JUNGLE_TESTS),
    ("the shrine goes to the other team", WORLD, "self.light(death.killer // 5,", "self.light(1 - death.killer // 5,", JUNGLE_TESTS),
    ("a shrine lasts one tick longer", WORLD, "self.tick + self.config.ticks(seconds), owner))", "self.tick + 1 + self.config.ticks(seconds), owner))", JUNGLE_TESTS),
    ("the digest leaves the camps, the sight sources and the memories out", WORLD, "self.tick, self.camps, self.sights, self.memory,", "self.tick,", JUNGLE_TESTS),
    ("a restored world shares its camps with the snapshot", WORLD, "world.camps = copy.deepcopy(list(snapshot.camps))", "world.camps = list(snapshot.camps)", JUNGLE_TESTS),
    ("a snapshot shares its memories with the world", WORLD, "memory=tuple(copy.deepcopy(self.memory)),", "memory=tuple(self.memory),", JUNGLE_TESTS),
    ("a camp order ends absent on arrival whatever is there", CHAMPIONS, " and world.camps[CAMP_OF[team][c.intent]].hp <= 0\n", "\n", JUNGLE_TESTS),
    ("red camp actions name blue's camps", CHAMPIONS, "CAMP_OF = tuple(tuple([frame_name(team, node) for node in CAMP_SITES]", "CAMP_OF = tuple(tuple([frame_name(0, node) for node in CAMP_SITES]", JUNGLE_TESTS),
    ("a laner gets the jungle item's camp XP", ECONOMY, "    if killer.role == JUNGLE:", "    if True:", JUNGLE_TESTS),
    ("the first-camp XP is paid for every camp", ECONOMY, "if killer.earned[Income.CAMP] == 0 else 0.0", "if True else 0.0", JUNGLE_TESTS),
    ("camp gold is booked as minion gold", ECONOMY, "    pay(killer, Income.CAMP, death.gold)", "    pay(killer, Income.MINION, death.gold)", JUNGLE_TESTS),
    ("the enemy team sees through a shrine", VISION, "[(s.pos, s.radius) for s in world.sights if s.team == team]", "[(s.pos, s.radius) for s in world.sights]", JUNGLE_TESTS),
    ("a dead champion gives sight", VISION, "for c in world.champions[first:first + 5] if c.hp > 0]", "for c in world.champions[first:first + 5]]", JUNGLE_TESTS),
    ("a team sees whatever is on an edge near a source", VISION, "gaps[at.edge] <= radius and RIFT.sees(at, pos, radius)", "gaps[at.edge] <= radius", JUNGLE_TESTS),
    ("a camp is seen from half of the stretch of an edge within reach of it", VISION, "reach.append((i, lo * e.length, hi * e.length))", "reach.append((i, lo * e.length, (lo + hi) / 2 * e.length))", JUNGLE_TESTS),
    ("the memory takes a camp within a source's radius as seen whatever the terrain", VISION, "if lo <= at.offset <= hi and RIFT.sees(at, SITES[i].pos, radius)}", "if lo <= at.offset <= hi}", JUNGLE_TESTS),
    ("a shrine that ran out still gives sight", VISION,"        world.sights[:] = [s for s in world.sights if s.expires > tick]", "        pass", JUNGLE_TESTS),
    ("an unseen clear gives the timer", VISION, "            if death.camp in seen and death.respawn >= 0:", "            if death.respawn >= 0:", JUNGLE_TESTS),
    ("the sight of an empty camp gives the timer at any time", VISION, "            if 0 <= camp.spawn_tick <= now + config.ticks(SITES[i].kind.timer_window_s):", "            if 0 <= camp.spawn_tick:", JUNGLE_TESTS),
    ("a timer that ran out stands when the camp is seen empty", VISION, "            elif mine.spawn_tick < now:\n                mine.spawn_tick = -1\n", "", JUNGLE_TESTS),
    ("a team's memory takes in camps it does not see", VISION, "        for i in seen:", "        for i in range(len(SITES)):", JUNGLE_TESTS),
    ("the first spawns are not public", VISION, "CampMemory(0.0, 0, -1, config.ticks(site.kind.first_spawn_s))", "CampMemory(0.0, 0, -1, -1)", JUNGLE_TESTS),
    ("the observation shows the other team's memory", VISION, "    known = world.memory[c.team].camps", "    known = world.memory[1 - c.team].camps", JUNGLE_TESTS),
    ("the camps of a red observation are in blue's order", VISION, "    for i in _FRAME_CAMPS[c.team]:", "    for i in _FRAME_CAMPS[0]:", JUNGLE_TESTS),
    ("the walk to a camp is measured through one end of the champion's edge", VISION, "min(back + from_a[i], on + from_b[i])", "back + from_a[i]", JUNGLE_TESTS),
    ("an enemy champion leaks into the observation beside the camps", VISION, "tuple(views[:role] + views[role + 1:]), _camps(",
     "tuple(views[:role] + views[role + 1:] + [_view(world, world.champions[(first + 5) % 10 + role])]), _camps(", KERNEL_TESTS),
    ("a fighter hits a target out of its range", COMBAT, "if foe.hp > 0 and _reaches(c, foe) and sees(world, c.seat // 5, foe.pos):", "if foe.hp > 0 and sees(world, c.seat // 5, foe.pos):", COMBAT_TESTS),
    ("a fighter hits a target that its team does not see", COMBAT, "if foe.hp > 0 and _reaches(c, foe) and sees(world, c.seat // 5, foe.pos):", "if foe.hp > 0 and _reaches(c, foe):", COMBAT_TESTS),
    ("attack range is a walk and not the straight line", COMBAT, "return RIFT.separation(c.pos, foe.pos) <= capability_of(c).attack_range + IN_RANGE", "return RIFT.distance(c.pos, foe.pos) <= capability_of(c).attack_range + IN_RANGE", COMBAT_TESTS),
    ("a champion that holds does not hit back", COMBAT, "    for c in guards:", "    for c in ():", COMBAT_TESTS),
    ("a holding champion has no attack on champions", CHAMPIONS, "    Kind.HOLD: Rule(attacks=Target.CHAMPION),", "    Kind.HOLD: Rule(),", COMBAT_TESTS),
    ("champion damage ignores the tick length", CHAMPIONS, "(c.attack_credit + speed * world.config.tick_s)", "(c.attack_credit + speed)", COMBAT_TESTS),
    ("champion damage ignores the attack credit", COMBAT, "attack_worth(world, c, can.champion_dps)", "can.champion_dps * world.config.tick_s", COMBAT_TESTS),
    ("camp damage ignores the attack credit", JUNGLE, "attack_worth(world, c, capability_of(c).camp_dps)", "capability_of(c).camp_dps * world.config.tick_s", JUNGLE_TESTS),
    ("a ready attack is worth nothing on a champion or a camp", CHAMPIONS, "(c.attack_credit + speed * world.config.tick_s)", "(speed * world.config.tick_s)", COMBAT_TESTS),
    ("a fight tick leaves the credit untouched", COMBAT, "        if c.seat in used:\n            c.attack_credit = 0.0\n", "        if c.seat in used:\n            pass\n", COMBAT_TESTS),
    ("damage on champions does not grow with the level", CHAMPIONS, '"area_dps", "camp_dps", "champion_dps"))', '"area_dps", "camp_dps"))', COMBAT_TESTS),
    ("a lockdown is used without the mana for it", COMBAT, " and c.mana >= can.lockdown_mana", "", COMBAT_TESTS),
    ("a lockdown has no cooldown", COMBAT, " and world.tick >= c.lockdown_tick", "", COMBAT_TESTS),
    ("a lockdown costs no mana", COMBAT, "            attacker.mana -= can.lockdown_mana\n", "", COMBAT_TESTS),
    ("a lockdown lasts one tick longer", COMBAT, "tick + 1 + config.ticks(can.lockdown_s)", "tick + 2 + config.ticks(can.lockdown_s)", COMBAT_TESTS),
    ("a lockdown does not slow its target", CHAMPIONS, "    slowed = 1.0 - c.slow if world.tick < c.slow_until else 1.0", "    slowed = 1.0", COMBAT_TESTS),
    ("a tick spent damaging a champion leaves the attack ready", COMBAT, "    used = {hit.attacker for hit in hits} | {seat for _, seat, _ in camp_blows}", "    used = {seat for _, seat, _ in camp_blows}", COMBAT_TESTS),
    ("a tick spent on a camp leaves the attack ready", COMBAT, "    used = {hit.attacker for hit in hits} | {seat for _, seat, _ in camp_blows}", "    used = {hit.attacker for hit in hits}", COMBAT_TESTS),
    ("an idle champion earns no attack", COMBAT, "            c.attack_credit = min(1.0, c.attack_credit + capability_of(c).attack_speed * tick_s)", "            pass", COMBAT_TESTS),
    ("the world ignores the credit that a lane hands back", COMBAT, "        elif c.seat in lane_credit:", "        elif False:", COMBAT_TESTS),
    ("a champion that deals damage does not enter combat", COMBAT, "        enter_combat(world, attacker)\n", "", COMBAT_TESTS),
    ("a hit leaves no mark on its victim", COMBAT, "        victim.hurt_tick[hit.attacker % 5] = tick\n", "", COMBAT_TESTS),
    ("the killer is the attacker that dealt the least", COMBAT, "            most = max(by.values())", "            most = min(by.values())", COMBAT_TESTS),
    ("a kill pays nothing to those that assist", COMBAT, "    for seat in kill.assists:", "    for seat in ():", COMBAT_TESTS),
    ("the assist window never closes", COMBAT, "[foe for foe in foes if tick - victim.hurt_tick[foe.role] <= window]", "[foe for foe in foes if victim.hurt_tick[foe.role] >= 0]", COMBAT_TESTS),
    ("every kill pays the first-blood bonus", COMBAT, "    if killers and not any(c.earned[Income.KILL] for c in champions):", "    if killers:", COMBAT_TESTS),
    ("every kill of the first tick with a kill pays first blood", COMBAT, 'ECONOMY["first_blood_bonus"] * (victim is first)', 'ECONOMY["first_blood_bonus"] * (first is not None)', COMBAT_TESTS),
    ("kill gold ignores the victim's level", COMBAT, " * max(0, level - 6)", " * 0", COMBAT_TESTS),
    ("kill XP is paid in full to everyone that shares it", COMBAT, 'KILL_XP["solo" if len(sharers) == 1 else "shared_total"], level) / len(sharers)', 'KILL_XP["solo" if len(sharers) == 1 else "shared_total"], level)', COMBAT_TESTS),
    ("an ally at any distance shares a kill's XP", COMBAT, ' and RIFT.separation(ally.pos, victim.pos) <= ECONOMY["kill_xp_range"]}', "}", COMBAT_TESTS),
    ("of two kills on one tick only the first that the code visits is paid", WORLD, "        for kill in kills:\n            combat.reward(self, kill)\n", "        for kill in kills[:1]:\n            combat.reward(self, kill)\n", COMBAT_TESTS),
    ("a fight does not end when its target dies", WORLD, "                    finish(fighter, Outcome.KILLED, self.tick)\n", "                    pass\n", COMBAT_TESTS),
    ("a siege goes on after the lane's last tower", WORLD, "                        finish(sieger, Outcome.CLEARED, self.tick)\n", "                        pass\n", COMBAT_TESTS),
    ("tower shots never reach the champions", WORLD, "            hits += economy.tower_hits(events)\n", "", COMBAT_TESTS),
    ("a dead enemy is seen where it lies", VISION, "            if enemy.hp > 0 and (any(", "            if (any(", COMBAT_TESTS),
    ("a champion that damages an enemy stays hidden from the victim's team", VISION, "any(ally.hurt_tick[enemy.seat % 5] == tick for ally in allies) or _lit(lit, enemy.pos)", "_lit(lit, enemy.pos)", COMBAT_TESTS),
    ("towers give no sight", VISION, "    return champions + towers + [", "    return champions + [", COMBAT_TESTS),
    ("a fallen tower gives sight", VISION, " in TOWER_SITES[team] if lanes[lane].tower_alive(team, tier)]", " in TOWER_SITES[team]]", COMBAT_TESTS),
    ("self-defence is not legal under a leash", VISION, "(permitted[i] or me.hurt_by[foe])", "permitted[i]", COMBAT_TESTS),
    ("a fight against an enemy out of view is legal", VISION, "o.enemies[foe] is not None and (permitted[i] or me.hurt_by[foe])", "(permitted[i] or me.hurt_by[foe])", COMBAT_TESTS),
    ("the self-defence window never closes", VISION, "hurt_by=tuple(tick >= since for tick in c.hurt_tick),", "hurt_by=tuple(tick >= 0 for tick in c.hurt_tick),", COMBAT_TESTS),
    ("the observation shows an enemy that the team saw earlier", VISION, "if record.seen_tick == tick else None", "if record.seen_tick >= 0 else None", COMBAT_TESTS),
    ("a fighter walks to the true place of a target that its team does not see", CHAMPIONS,
     "    if record.seen_tick != world.tick:\n        return _short_of(c, record.pos)\n    target = world.champions[(1 - team) * 5 + foe]\n    if RULE[target.intent].pursues or not world.watches(team, target.pos, stood):",
     "    target = world.champions[(1 - team) * 5 + foe]\n    if RULE[target.intent].pursues:", COMBAT_TESTS),
    ("a fighter heads for where its team saw its target before the move step", CHAMPIONS, "    if RULE[target.intent].pursues or not world.watches(team, target.pos, stood):", "    if True:", COMBAT_TESTS),
    ("a fighter heads for the new place of a target that left its team's view on this tick", CHAMPIONS, "    if RULE[target.intent].pursues or not world.watches(team, target.pos, stood):", "    if RULE[target.intent].pursues:", COMBAT_TESTS),
    ("a fight is lost on the tick of arrival", CHAMPIONS, "    return Outcome.LOST if c.channel > 1 else Outcome.NONE", "    return Outcome.LOST if c.channel > 0 else Outcome.NONE", COMBAT_TESTS),
    ("a fighter walks onto its target instead of stopping at its range", CHAMPIONS, "    return RIFT.advance(target, pos, reach)", "    return target", COMBAT_TESTS),
    ("a tower's ramp never starts again", LANES, "        if t - tower.heat_at >= RAMP_RESET_S:\n            tower.heat = 0\n", "", COMBAT_TESTS),
    ("a tower's ramp has no limit", LANES, "min(RAMP_MAX, RAMP_PER_HIT * tower.heat)", "RAMP_PER_HIT * tower.heat", COMBAT_TESTS),
    ("a tower's shot on a champion ignores the game time", LANES, 'damage = interpolated(table["ad"], table["ad_span_s"], t) * (', 'damage = table["ad"][0] * (', COMBAT_TESTS),
    ("a tower ignores who damaged its ally", LANES, "marks = [spot for spot in marks if self._provokes(spot, tower)] or ([] if foes else marks)", "marks = [] if foes else marks", COMBAT_TESTS),
    ("a tower shoots a champion before minions", LANES, "or ([] if foes else marks)", "or marks", COMBAT_TESTS),
    ("a tower answers for an ally at any distance", LANES, " and self._range(victim, tower) <= SWITCH_RANGE + EPS:", ":", COMBAT_TESTS),
    ("a tower shoots a champion whose input does not ask for it", LANES, "        marked = [stand[c.seat] for c in inputs if c.tower_target]", "        marked = [stand[c.seat] for c in inputs]", COMBAT_TESTS),
    ("a champion beside the lane stands on the lane for its towers", LANES, "                spot.x, spot.y = spot.inp.xy\n", "                self._place(spot)\n", COMBAT_TESTS),
    ("backdoor protection is off", LANES, "            damage *= 1.0 - BACKDOOR\n", "            pass\n", COMBAT_TESTS),
    ("a tower takes no more from a melee champion", LANES, "            damage *= MELEE_TAKEN\n", "            pass\n", COMBAT_TESTS),
    ("a tower's armor is ignored", LANES, "damage = inp.hit_damage * ARMOR_HALVING / (ARMOR_HALVING + armor)", "damage = inp.hit_damage", COMBAT_TESTS),
    ("an outer tower keeps its armor", LANES, 'if "armor_decay_span_s" in table else ARMOR', 'if False else ARMOR', COMBAT_TESTS),
    ("plates never break", LANES, "            if missing < share * full <= full - tower.hp:", "            if False:", COMBAT_TESTS),
    ("the lane leaves a tower's ramp out of its values", LANES, "(t.team, t.tier, t.hp, t.credit, t.heat, t.heat_at)", "(t.team, t.tier, t.hp, t.credit)", COMBAT_TESTS),
    ("the lane keeps a credit for a champion that brings its own", LANES, "            if inp.credit is None:\n                self._champion_credit[inp.seat] = left", "            if True:\n                self._champion_credit[inp.seat] = left", COMBAT_TESTS),
    ("plate gold reaches champions at any distance", ECONOMY, " and RIFT.separation(c.pos, at) <= LOCAL_GOLD_RANGE]", "]", COMBAT_TESTS),
    ("every fallen tower pays the first-tower bonus", ECONOMY, "        if i == 0 and down == len(fallen):", "        if i == 0:", COMBAT_TESTS),
    ("a fallen tower pays no global gold", ECONOMY, '            pay(c, Income.TOWER, TOWERS[TIERS[tier]]["global_gold"])', "            pass", COMBAT_TESTS),
    ("a champion off the lane is no input to it", ECONOMY, "            if not near and not (victims and beside[c.pos.edge]):", "            if True:", COMBAT_TESTS),
    ("the call for help never ends", COMBAT, "    since = world.tick - world.config.ticks(CALL_S)", "    since = 0", COMBAT_TESTS),
    ("a laner's stance reads the lane's true front", CHAMPIONS, "capability_of(c).attack_range, known_front(world, seat // 5, lane), hold=hold)",
     "capability_of(c).attack_range, world.lanes[lane].front(), hold=hold)", VISION_TESTS),
    ("a fighter heads for its target's true place", CHAMPIONS, "        return _short_of(c, record.pos)\n    target = world.champions[(1 - team) * 5 + foe]",
     "        return _short_of(c, world.champions[(1 - team) * 5 + foe].pos)\n    target = world.champions[(1 - team) * 5 + foe]", VISION_TESTS),
    ("a fighter follows a target that stepped out of its team's view", CHAMPIONS, "    if RULE[target.intent].pursues or not world.watches(team, target.pos, stood):",
     "    if RULE[target.intent].pursues:", VISION_TESTS),
    ("an observation shows every living enemy", VISION,
     "    enemies = tuple(EnemyView(to_frame(team, record.pos), record.hp, record.level) if record.seen_tick == tick else None\n                    for record in records)",
     "    enemies = tuple(EnemyView(to_frame(team, foe.pos), foe.hp, level_of(foe.xp)) if foe.hp > 0 else None\n                    for foe in world.champions[(1 - team) * 5:(2 - team) * 5])",
     VISION_TESTS),
    ("an observation shows an enemy that the team saw earlier as seen now", VISION,
     "record.hp, record.level) if record.seen_tick == tick else None", "record.hp, record.level) if record.seen_tick >= 0 else None", VISION_TESTS),
    ("an observation lists enemy wards", VISION, "for s in world.sights if s.team == team and s.owner >= 0)", "for s in world.sights if s.owner >= 0)", VISION_TESTS),
    ("an enemy ward is a sight source for both teams", VISION, "[(s.pos, s.radius) for s in world.sights if s.team == team]",
     "[(s.pos, s.radius) for s in world.sights if s.team == team or s.owner >= 0]", VISION_TESTS),
    ("minions are no sight source", VISION, "        if not sim.minions[team]:\n            continue\n", "        if True:\n            continue\n", VISION_TESTS),
    ("minions show their team no enemy wave", VISION, "    spans = list(sim.sighted(team))\n", "    spans = []\n", VISION_TESTS),
    ("minions see any distance", LANES, 'MINION_SIGHT = MINIONS["sight_range"]', "MINION_SIGHT = 1e9", VISION_TESTS),
    ("minions see through walls beside their lane", VISION, " <= MINION_SIGHT and RIFT.sight_clear(RIFT.lane_pos(name, s), pos):", " <= MINION_SIGHT:", VISION_TESTS),
    ("wave memory follows the wave out of sight", VISION, "            seen, spans = _wave_seen(world, team, name)\n",
     "            seen, spans = world.lanes[name].minions[1 - team], _wave_seen(world, team, name)[1]\n", VISION_TESTS),
    ("a remembered wave is never forgotten", VISION, "            elif wave.lead is not None and any(lo <= wave.lead <= hi for lo, hi in spans):", "            elif False:", VISION_TESTS),
    ("a last-seen record follows the enemy out of sight", VISION, "            if enemy.hp > 0 and (any(ally.hurt_tick[enemy.seat % 5] == tick for ally in allies) or _lit(lit, enemy.pos)\n",
     "            if enemy.hp > 0 and (True or _lit(lit, enemy.pos)\n", VISION_TESTS),
    ("a ward never expires", VISION, "        world.sights[:] = [s for s in world.sights if s.expires > tick]", "        pass", VISION_TESTS),
    ("a ward costs no charge", CHAMPIONS, "    c.ward_charges -= 1\n", "    pass\n", VISION_TESTS),
    ("a ward is placed from any distance", CHAMPIONS, '    if c.ward_charges <= 0 or RIFT.separation(c.pos, spot) > WARD["ward_place_range"] + IN_RANGE:',
     "    if c.ward_charges <= 0:", VISION_TESTS),
    ("a ward is placed within 625 units of walking", CHAMPIONS, '    if c.ward_charges <= 0 or RIFT.separation(c.pos, spot) > WARD["ward_place_range"] + IN_RANGE:',
     '    if c.ward_charges <= 0 or RIFT.distance(c.pos, spot) > WARD["ward_place_range"] + IN_RANGE:', VISION_TESTS),
    ("a ward is placed where the champion stands", CHAMPIONS, '    world.ward(c.seat, spot, WARD["ward_sight_range"],', '    world.ward(c.seat, c.pos, WARD["ward_sight_range"],', VISION_TESTS),
    ("the mask offers WARD without a charge", VISION, "    if me.ward_charges <= 0:\n        for i in WARDS:", "    if False:\n        for i in WARDS:", VISION_TESTS),
    ("a fourth and every later ward keeps the champion's oldest and drops its newest", WORLD, "            self.sights.remove(mine[0])", "            self.sights.remove(mine[-1])", VISION_TESTS),
    ("a fourth ward removes the oldest ward on the map, whoever placed it", WORLD, "            self.sights.remove(mine[0])", "            self.sights.remove(self.sights[0])", VISION_TESTS),
    ("a champion keeps any number of wards on the map", WORLD, "        if len(mine) >= most:", "        if False:", VISION_TESTS),
    ("a ward's duration ignores the champion level", CHAMPIONS, '_by_average_level(world, WARD["ward_duration_s"]), WARD["ward_max_placed"])',
     'WARD["ward_duration_s"][0], WARD["ward_max_placed"])', VISION_TESTS),
    ("a ward's recharge ignores the champion level", CHAMPIONS,
     '        c.ward_tick = world.tick + world.config.ticks(_by_average_level(world, WARD["ward_recharge_s"]))\n    world.ward(',
     '        c.ward_tick = world.tick + world.config.ticks(WARD["ward_recharge_s"][0])\n    world.ward(', VISION_TESTS),
    ("a champion holds a third ward charge", CHAMPIONS, '        full = c.ward_charges >= WARD["ward_charges"]', '        full = c.ward_charges >= WARD["ward_charges"] + 1', VISION_TESTS),
    ("a returning laner may ward", VISION, "        return RETURNS[role][i] or (leash is Leash.HOME and a.kind is Kind.HOLD)",
     "        return RETURNS[role][i] or a.kind is Kind.WARD or (leash is Leash.HOME and a.kind is Kind.HOLD)", VISION_TESTS),
    ("a laner on a ward walk off its lane is charged as returning", CHAMPIONS, "    return Duty.RETURNING if RETURNS[c.seat % 5][c.intent] or on_fountain(c) else Duty.ROAMING",
     "    return Duty.RETURNING if RETURNS[c.seat % 5][c.intent] or on_fountain(c) or ACTIONS[c.intent].kind is Kind.WARD else Duty.ROAMING", VISION_TESTS),
    ("a ranged attack needs no sight of its target", "riftgame/combat.py", "        if foe.hp > 0 and _reaches(c, foe) and sees(world, c.seat // 5, foe.pos):",
     "        if foe.hp > 0 and _reaches(c, foe):", VISION_TESTS),
    ("an observation reports the lane's true enemy lead", VISION, "        views.append(LaneView(framed(own), tuple(near), framed(wave.lead), wave.near,",
     "        views.append(LaneView(framed(own), tuple(near), framed(sim.front().lead[1 - team]), wave.near,", VISION_TESTS),
    ("an enemy's death timer is hidden", VISION, "    rivals = tuple(Rival(level_of(foe.xp), max(0, foe.respawn_tick + 1 - tick) * tick_s)", "    rivals = tuple(Rival(level_of(foe.xp), 0.0)", VISION_TESTS),
    ("the encoding leaves the ward slots out", VISION, "    for slot in range(WARD_SLOTS):", "    for slot in range(0):", VISION_TESTS),
    ("the encoding leaves an enemy's remembered place out", VISION, "                *_place_code(last.place if last else None), last.hp if last else UNKNOWN,",
     "                last.hp if last else UNKNOWN,", VISION_TESTS),
    ("the digest leaves the wards out", WORLD, "state = (RULESET_ID, MAP_ID, self.seed, self.tick, self.camps, self.sights, self.memory,",
     "state = (RULESET_ID, MAP_ID, self.seed, self.tick, self.camps, [], self.memory,", VISION_TESTS),
    ("a snapshot leaves the wards out", WORLD, "camps=tuple(copy.deepcopy(self.camps)), sights=tuple(self.sights),", "camps=tuple(copy.deepcopy(self.camps)), sights=(),", VISION_TESTS),
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
