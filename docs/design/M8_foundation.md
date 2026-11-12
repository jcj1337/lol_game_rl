# M8 foundation

**Status.** Three campaigns have run. Checkpoints C1 (kernel base), C3 (recall and purchases), C4 (jungle), C5 (combat and death), and C6 (vision, memory, and wards) are built and pass the criteria that M7 wrote for them. C2 (lanes and economy) is built and is not complete. Wave plans now read only what their team sees and stand beside two separate controls, but reinforcements accumulate in 2 of 48 settings, a hold is sustained in 9 of 64, and the wave measures move more with the tick length than with the seed (section 2). C7 and C8 have not started. Nothing was trained. [Handoff 005](../../handoff/005_m8_c1_c2.md) reports the first campaign, [handoff 006](../../handoff/006_m8_c2_corrections_c3_c5.md) the second, and [handoff 007](../../handoff/007_m8_corrections_c6.md) the third.

**Date.** 2026-11-12.

**Builds on.** [`M7_architecture.md`](M7_architecture.md). This document does not repeat M7. It names the M7 section that a piece of M8 implements, and it states every place where M8 departs from M7.

**Evidence labels.** The labels are M7's. **Tested** names a test or a script in this repository. **Sourced** comes from the reference patch research. **Assumed** is a design choice or a placeholder number. **Reported** has no evidence in the repository. **Inference** is a conclusion drawn from tested facts. **Unresolved** marks a known limit.

## 1. Summary

- The kernel of M7 section 5 exists as reusable code in `riftgame/`: ten champions on the full map, a fixed tick with a separate decision interval, intents that end with an outcome, the role duty state, an observation boundary, snapshots, replays, and an invariant checker (section 3). Since the third campaign it also has team sight from every source of M7 section 6.1, team memory of camps, enemy champions, and enemy waves, the full observation with a flat encoding, and wards (section 9).
- One `LaneSim` class runs all three lanes. Every range inside a lane is the straight line on the map, minion attacks have the cast times and missile speeds of the game's data files, and a `LANE` action names what the champion hits and where it stands. The third campaign moved the M8 lane onto a map file of its own, which traces each side-lane corner with the game's four waypoints, after a test showed that one bend off the centre tips an untouched lane (section 4).
- Every wave plan reads its champion's observation and picks entries of the action table in a full world. Each result stands beside a laner on its fountain, a laner under its tower, and a lane that nobody touches. A plan accumulates reinforcements in 2 of 48 settings, both bot-lane carries at level 3 against an absent opponent. A hold keeps a larger wave out of the tower's range for three wave cycles in 9 of 64 settings from the first wave and 3 of 32 from the third. After a crash the front comes back before an untouched lane's front in 18 of 24 cases (section 5.4).
- C2 is still not complete. No plan accumulates against an opponent that last-hits, and no hold lasts longer than four wave cycles. Per case, every wave measure moves more across tick lengths from 0.125 s to 1.0 s than across seeds. In one traced case a quarter second in a minion fight changes which last hits land, and a near-balanced lane turns that into a different crash (section 5.5).
- The acceptance criteria for waves keep the form of campaign 2's second revision and stay provisional. Only the lists of controls changed. Six strict expected failures keep the unmet bars in view (section 5.3).
- Recall, fountain, purchases, and Homeguard (C3), camps, Scuttlers, shrine sight, and camp timers (C4), and per-tick fights, towers against champions, death, and kill rewards (C5) are built behind the interfaces of M7 section 5.11. One attack credit now pays for every class of target, and a fighter follows a target only where its team sees it (sections 6 to 8).
- C6 passes every criterion of M7's C6 row. In 32 worlds, changing everything hidden from a team changes none of its observations, encodings, or masks, and its champions act the same until something is revealed. One leak outside those tests is open: a fighter's walk depends on the intent kind of its visible target (section 9).
- Nothing is validated against the real game. Every champion number is a placeholder. Conclusions about recall timing, denial, and gank opportunities are provisional while wave fidelity is open (section 10).

## 2. Campaigns, phases, and progress

M8 has eight checkpoints (M7 section 10.1).

**Campaign 1, 2026-11-11.** Handoff 005 has the detail.

| Phase | Work | State |
| --- | --- | --- |
| P0 to P1 | Grounding, and the kernel (C1) | Done. Every C1 criterion passes. |
| P2 | `riftgame/lanes.py` as a port of M7's lane | Done. 998 of 998 metrics of M7's results file with M7's draw key. |
| P3 to P4 | Wave investigation with scripted champions, and lanes in the world (C2) | Built. Every criterion of M7's C2 row passes. Three wave behaviours did not appear. |
| P5 | Review and handoff 005 | Done |

**Campaign 2, 2026-11-12.** This campaign corrected C2 and built C3 to C5. Handoff 006 has the detail.

| Phase | Work | Acceptance | State |
| --- | --- | --- | --- |
| Q0 Ground | Read the documents and handoff 005. Capture the baseline. | 329 tests pass, 4 expected failures, all results files current. | Done |
| Q1 Action interface | A `LANE` action is (lane, mode, stand). | An agent can stand on the hold line and hit in any of the four modes. Tested in the lane and in the world. | Done |
| Q2 Lane rules | Straight-line ranges, the two targeting exceptions near towers, attack timing. | Each rule has a switch, a test, and a mutation. With M7's rules the lane stays bit-identical. | Done |
| Q3 Experiments through the action table | `experiments/m8/waves/agents.py` and `capabilities.py`. | Every plan chooses action indices in a full world. Eight champion settings, three kinds of start. | Done |
| Q4 Criteria | Section 5.3. | Each revised criterion states what the old one got wrong and compares a plan with a lane that nobody touches. | Done, in a second revision after the review |
| Q5 Traces | Attack timing counters, a count of overlapping bodies, an untouched-lane baseline, diagnostics, a tick sweep. | Reported. No rule is added to the lane from a diagnostic. | Done |
| Q6 to Q8 | C3, C4, and C5. | The criteria of sections 6.3, 7.3, and 8.3. | Done. All pass. |
| Q9 Evidence and handoff | Rerun every results file, the mutation runner, an independent review, handoff 006. | Every number comes from a current results file or carries the label Reported. | Done |

**Campaign 3, 2026-11-12.** This campaign corrected five findings of the review of campaign 2, reran the wave experiments with two controls and later waves, and built C6. The decision trail is [`007_m8_corrections_c6_decisions.tsv`](../../handoff/007_m8_corrections_c6_decisions.tsv).

| Phase | Work | Acceptance | State |
| --- | --- | --- | --- |
| R0 Ground | Read the documents and handoff 006. Capture the baseline. | 586 tests pass, 9 expected failures, tree clean at commit `1380d0c` (decision trail). | Done |
| R1 Controls | `absent` is a laner on its fountain, and `under tower` a laner at its outer tower. Both stand beside every plan. | The two differ in XP in every seed of the test setting. Every accumulation and hold bar names both. | Done |
| R2 Geometry | Test the corner diagnosis with one-bend lanes. Give M8 a map with the game's four waypoints at each side-lane corner. | An untouched lane stays at the centre for 150 s in all three lanes. `M7_LANE` stays on M7's graph and reproduces M7's metrics. | Done. A later one-way drift remains (section 4.2). |
| R3 Attack capacity | One credit for minions, towers, champions, and camps (`champions.attack_worth`). | Attacks are conserved on every tick across switches between classes. Damage on a champion is the same at two tick lengths. | Done |
| R4 Pursuit | A fighter follows its target's move only where its team sees the new place. | A wall case and the behaviour test of C6. | Done |
| R5 Digest | A minion's target carries whether it lives and when it died, and each minion its spawn delay. | Two lanes that differ only in a dead target's death time have different digests. | Done |
| R6 Wave experiments | Plans read the observation. Later-wave cases. Rows with every seed, durations, costs, and paired comparisons. The tick sweep at four ticks. The first-wave exception measured. | Criteria unchanged in form. Every number of section 5 from the final results files. | Done. C2 stays open. |
| V1 C6 kernel | Sight from minions, wards, and shrines, wave memory, the full observation and its encoding, the `WARD` action, automation on team knowledge. | A 600 s game with the invariant checker on. | Done |
| V2 C6 tests | `tests/test_vision.py` with 80 tests, and 35 mutation entries against it. | The C6 criteria of section 9.4. | Done. All pass. |
| V3 Evidence and handoff | Rerun every results file, `experiments/m8/vision.py`, handoff 007. | Every M8 and M7 results file is current by the provenance checkers. | Done |

**What campaign 3 closed from handoff 006.**

- The early drift of an untouched top lane. On the M8 map every lane keeps its front at the centre for the first 150 s (section 4.2).
- The absent control that stood at its tower. A laner on its fountain and a laner under its tower are now two controls (section 5.2).
- The attack budget that worked in one direction. One credit pays for every class of target (section 8.1).
- The pursuit leak. A fighter no longer reads the new place of a target that has just left its team's view (section 8.1).
- The digest gap. A cancelled cast that restarts from a dead target's death time is in the digest (Tested, `tests/test_lanes.py`).

**Still open.** Wave fidelity, below, and the later one-way drift of an untouched top lane stay open. So do the tick sensitivity, which is now traced once and not removed, the first wave's indifference to champions and its ghosting, unit collision, and the real-game measurements of section 5.8.

**C2 is not complete.** The owner requires freezing, slow pushing, crashing, and bouncing as capabilities, and C2 may not be called complete while one is unresolved. A crash works. The other three are unresolved.

1. **Slow push.** A plan accumulates reinforcements in 2 of 48 settings, both bot-lane carries at level 3 against an absent opponent, with 9 and 8 minions. It accumulates in none of the 24 settings against an opponent that last-hits, and in none that starts from the third wave. The slow-push drill brings 8 minions where a hard push brings 9.
2. **Freeze.** A hold is sustained for three wave cycles in 9 of 64 settings from the first wave and in 3 of 32 from the third. One lasts four cycles, and none lasts longer. From the first wave no plan holds for a level 6 mid laner.
3. **Bounce.** After a crash the front comes back in every run in 23 of 24 cases, and before the untouched lane's front in 18. After a hard push of the first wave mid resets to the centre in 3 of 5 runs. In top at level 6 no plan beats the untouched lane in every run.
4. **The lane itself.** A verdict that must hold in every seed of one setting can flip with the tick length (section 5.5). An untouched top lane still leaves the centre toward red's half at 247 to 281 s in every seed.

## 3. Kernel base (C1)

### 3.1 What exists

| Module | Owns | Checkpoint |
| --- | --- | --- |
| [`world.py`](../../riftgame/world.py) | The state, the eight-step tick of M7 section 5.2, `Config`, snapshots, the digest, the invariant checker, the ward limit per champion | C1, C6 |
| [`champions.py`](../../riftgame/champions.py) | Seats, placeholder capability and progressions, the action table, intents with a rule per kind, the duty state, the fountain's rules, the attack credit (`attack_worth`), the front a team knows (`known_front`), ward charges | C1, C3, C5, C6 |
| [`vision.py`](../../riftgame/vision.py) | `observe`, `observe_team`, `legal_mask`, `encode`, team sight from every source, team memory of camps, enemy champions, and enemy waves | C1, C4, C5, C6 |
| [`harness.py`](../../riftgame/harness.py) | The policy interface, scripted policies that read only the observation, replays | C1, C4, C5 |
| [`lanes.py`](../../riftgame/lanes.py) | Minions and towers of one lane, the stance of a champion at a wave, the stretches of a lane that a team's minions see | C2, C5, C6 |
| [`economy.py`](../../riftgame/economy.py) | Gold, XP, the support item, and the champion inputs of a lane | C2, C4 |
| [`jungle.py`](../../riftgame/jungle.py) | Camps, Scuttlers, and their fights | C4 |
| [`combat.py`](../../riftgame/combat.py) | Champion attacks and kill rewards | C5 |

The world always holds ten champions on the full route graph. Nothing in `riftgame` has a single-lane mode.

### 3.2 Contracts, and where the kernel departs from M7

The kernel implements M7 sections 5.2 (clock and tick order), 5.3 (state), 5.10 (roles), 6 (information), 7 (actions), and 8 (randomness and snapshots). It departs in these places.

| Departure | Reason |
| --- | --- |
| The roam allowance is a set of `Config` fields: the cap, the refill, the end time of assignments, whether a fallen outer tower ends one, and a switch that turns the restriction off. | Owner decision: the allowance is an experimental restriction, not a permanent rule. |
| A laner with no allowance may choose `LANE` for its lane, `RECALL`, and `MOVE` to a node of its lane, to its own base, or to its own fountain. All of these count as returning, not roaming. From C5 on it may also `FIGHT` an enemy that is attacking it. | Owner decision: a returning champion keeps retreat and self-defence choices. |
| The action table has 107 entries. A `LANE` action is (lane, mode, stand), with four modes and two stands (section 4.4). Targets are named in the acting team's frame. | M7 said about 95, with five modes. |
| An observation position is a `Place`: a lane with the distance from the team's own end, or one edge off the lanes. The mirror test is exact only for lane positions, bases, and fountains. | The map has no mirror symmetry that keeps roles. |
| The digest covers the state and not the config. | The decision-interval test compares two runs that differ only in the config. |
| `WARD` names one of 14 spots: the 12 camps and the 2 river nodes (section 9). | M7 lists no ward spots. These are the nodes that the action table already named. |
| M8 runs on its own map file, [`map_summoners_rift_m8.toml`](../../riftgame/rulesets/map_summoners_rift_m8.toml), which adds the game's other three waypoints at each side-lane corner. The six added nodes are no `MOVE` targets, so the table keeps 107 entries. | M7's route graph keeps one waypoint per corner, and that tips an untouched lane (section 4.2). M7's map file stays byte-identical for M7's results. |

### 3.3 Acceptance criteria of C1

The criteria are those of M7 section 10.1 for C1, plus the owner's two corrections on roles. Every row is Tested. The roam numbers are in [`experiments/m8/results/kernel.json`](../../experiments/m8/results/kernel.json).

| Criterion | Result | Test |
| --- | --- | --- |
| A run at decision interval n equals a run at interval 1 that keeps between decisions, for n of 2, 4, and 10, with intents that complete inside the run | Equal digest for digest over 600 ticks, with scripted junglers among random laners. The test requires `ARRIVED`, `ABSENT`, `CLEARED`, and `RECALLED` to occur inside each run. | `tests/test_world_clock.py` |
| A redirected move continues from the current position, and distance walked is speed times time | Every tick's walk is speed times the tick, before and after the redirect | `tests/test_world_clock.py` |
| Restore and replay give equal digests at every tick for 1,000 ticks | 1,000 of 1,000. A pickled snapshot also restores in a new process under two hash seeds. | `tests/test_world_snapshot.py` |
| No laner roams longer than the cap plus one decision interval at a stretch | Holds at both clock settings | `tests/test_world_roles.py` |
| Each laner's roaming share after its first allowance is spent stays within 20 percent plus one decision interval over the window | Holds at both clock settings | `tests/test_world_roles.py` |
| Junglers are never restricted. No position changes by more than the champion's speed times the tick, except on death and on recall. | Both hold in 840 s games in which champions die. The speed is the champion's speed on that tick, Homeguard included. | `tests/test_world_roles.py`, `tests/test_world_soak.py` |
| The restriction is configurable | With it off, no laner is ever sent home. With a cap of 30 s and a refill of 0.5, the bounds follow the configured values. | `tests/test_world_roles.py` |
| A returning laner keeps retreat choices | With an allowance below zero and off its lane, it may walk to its own tower, base, or fountain, and the allowance does not drain | `tests/test_world_roles.py` |
| A soak of random legal actions runs 10 games with no invariant failure | 10 games of 600 s, two policies, two clocks. No failure. | `tests/test_world_soak.py` |
| The invariants | Each one is broken on purpose and the checker raises. C3 adds gold equal to the ledger less the price of the upgrades. C4 adds the camp faults. C6 adds the ward charges and at most three wards per champion, and no test breaks those two on purpose. | `tests/test_world_soak.py`, `tests/test_recall.py`, `tests/test_jungle.py` |
| Leak test for the observation boundary | Every field of every enemy champion is changed, and so are the minions and towers of every lane and every camp fact that the team has not seen. The team's five observations and masks stay identical. C6 extends the test to every hidden field (section 9.4). | `tests/test_world_observation.py`, `tests/test_economy.py` |
| A replay reproduces its digests, and one digest is pinned | 600 of 600. The pin moves with every change to the state, so it moved in every campaign. | `tests/test_world_snapshot.py` |

**Measured, not criteria.** `kernel.json` holds the throughput of one process over 600 s games, and section 10 gives the figures. M7's gate of 300 simulated seconds per wall second is measured at C7 on the integrated game.

## 4. Lanes and economy (C2)

### 4.1 The lane model

`riftgame/lanes.py` holds one class, `LaneSim`. It owns a lane's minions, its six towers, and its wave clock, on the lane coordinate of M7 section 5.1. A champion enters a lane tick as a `ChampionInput`. Everything that leaves the lane is an event. The world applies the events (M7 section 5.11).

`LaneRules` names each optional rule. `M8_LANE` is the lane that M8 ships. `M7_LANE` switches off what M7 did not model and runs on M7's route graph, so that M7's results can be reproduced. Five fields are diagnostics and are off in both.

| Rule | In the M8 lane | Status |
| --- | --- | --- |
| Waves on the reference clock, with reference stats and composition | Yes | Sourced |
| Target priority: enemy minion, then tower, then a champion in the path | Yes, at acquisition and on every retarget | Sourced |
| A blow on a minion adds 2, 3.5, or 5 percent of the target's current health | Yes | Sourced, read twice |
| Lateral slots that break ties between targets | Yes | Assumed. The wiki states it for the melee minions of the first waves only (section 4.2). |
| Side-lane speed for wave 2 and later, until 14:00 | Yes | Sourced, read twice |
| Call for help: minions within 1,000 units turn on an enemy champion that attacks an allied champion, unless they attack a tower | Yes. The world sets the trigger from C5 on. | Sourced |
| Pushing advantage from 3:30, by team level lead and tower lead | Yes | Sourced |
| Three tower tiers. Only the front tower fights and takes damage. | Yes | Sourced |
| A wave past the last lane tower is removed at the enemy base | Yes | Assumed stand-in until M10 |
| Champions that attack at the same instant are served in an order drawn by key, not by seat | Yes | Assumed |
| `straight_ranges`: every range inside the lane is the straight line on the map. Marching stays on the lane coordinate. | Yes, new in campaign 2 | Owner requirement, and the interaction measure of M7 section 5.1 |
| `tower_shelter`: a champion inside the range of a standing lane tower is not attacked for standing in the minions' path | Yes, new in campaign 2 | Sourced. That any standing lane tower counts is Assumed. |
| `first_wave_call`: minions of the first wave answer a call for help while they attack a tower | Yes, new in campaign 2 | Sourced |
| `attack_timing`: a blow leaves the minion one cast time after the attack starts, and a caster's or a siege minion's blow then flies to its target | Yes, new in campaign 2 | Sourced constants (section 4.2). The cancel and the lost missile are Assumed. |
| `m7_map`: the lane runs on M7's route graph, which traces each side-lane corner with one of the game's four waypoints | No. `M7_LANE` turns it on. New in campaign 3. | The M8 map's waypoints are Sourced (section 4.2). |
| `melee_cap`: at most n melee minions on one target | Diagnostic, off | Section 5.5 |
| `minion_damage_scale`: scales minion blows on minions | Diagnostic, off | Section 5.5 |
| `free_cancel` and `missiles_turn`: a cancelled cast costs nothing, and a missile to a dead target lands on what its shooter can reach | Diagnostics, off | Section 5.5 |
| `detour_s`: a melee minion that turns to a new minion target loses this long before its cast | Diagnostic, off | Section 5.6 |

The added constants live in a second ruleset file, [`patch_26_22_m8.toml`](../../riftgame/rulesets/patch_26_22_m8.toml), and the M8 map in `map_summoners_rift_m8.toml`. `patch_26_22.toml`, `map_summoners_rift.toml`, `map.py`, `ruleset.py`, and `rng.py` stay byte-identical, because M7's results files record their hashes.

### 4.2 The rules that campaigns 2 and 3 added, and what the sources say

**Straight-line ranges.** M7 section 5.1 measures movement by the route and interaction by the straight line. Campaign 1 left every range inside a lane on the lane coordinate. On M7's route graph, two points 290 units either side of the top-lane corner are 580 units apart along the lane and 534 in a straight line. Campaign 2 first changed only the ranges between champions or towers and minions. That made things worse. A passive carry in bot lane took 568 damage in five minutes where it had taken 44, because a caster behind the corner counted enemy minions along the lane, found none in range, and turned on the champion that it measured by the straight line (Reported, a scratch run of campaign 2). One measure for every interaction removes the inconsistency. Acquisition, attack, tower, and call ranges all use the map coordinates of the two units. Only marching uses the lane coordinate (Tested, `tests/test_lanes.py`, two corner tests). The hold line, the stand-off, and the experiments' band and tower checks are still placed along the lane. Towers stand on straight stretches, so that differs from the straight line by 16 units at most (Reported by the review of campaign 2, on M7's graph).

**The corner, tested and replaced.** With straight-line ranges on M7's graph, an untouched top lane went to blue's half within 100 s in every seed. Handoff 006 put that down to the graph's one sharp corner node, from one comparison. Campaign 3 tested the diagnosis on top lane's length, towers, and spawn points with other shapes, over 12 seeds of 600 s (Tested, `investigate.py` section `bends`, and `test_a_bend_tips_an_untouched_lane_toward_its_own_side_and_a_bend_at_the_centre_or_no_bend_does_not`). With no bend, or one bend at the centre, the front never leaves the centre. One bend of 46 degrees 150 or 295 units off the centre tips the lane toward the bend's side at 97 s in every seed, and the mirrored bend tips it the other way. A bend of 10 or 20 degrees does the same as one of 46, and one of 5 degrees does not. So the cause is a bend off the centre inside the first fight, not its sharpness. Section 5.4 has the table.

**Why a bend tips the lane** (Reported, one scratch trace recorded in the decision trail). With straight-line ranges a caster across the bend acquires its target one tick earlier and stops 1.2 units short of where it stops on a straight lane. On a straight lane later retargets sit exactly on a range threshold. Across the bend they fall outside it, the minion waits a tick before it walks, and the symmetric fight is no longer a draw. A rule that let a minion acquire a target on arrival inside the tick was tried and removed. It left the drift at 97 s in 12 of 12 seeds on M7's graph and changed the first-wave fight by under 0.5 s at four tick lengths (Reported).

**The M8 map.** `map_summoners_rift_m8.toml` is M7's map file with the game's other three waypoints at each side-lane corner (reference rows A4b and A4c). M7's graph kept one of four, which made one bend of 46 degrees 295 units from where the waves meet and cut 98 units off top lane and 109 off bot (the map file's header). On the M8 map no bend of top lane between the outer towers turns more than about 21 degrees, and the bends nearest the centre are 319 units on blue's side and 669 on red's (`investigation.json`, `bends`). The added points are not collinear, so they change the lane's length and shape. Marching and champion walks use the route, and every range uses the straight line. `LaneRules.m7_map` keeps `M7_LANE` on M7's graph, so the port check still gives 998 of 998 (section 5.1).

With the M8 map an untouched lane keeps its front within 100 units of the centre for the first 150 s in all three lanes and every seed (Tested, `test_an_untouched_lane_keeps_its_front_at_the_centre_for_the_first_150_seconds`). Over 12 seeds of 600 s an untouched top lane first leaves the centre at 281 s (median, 247 to 281), where it left at 97 s on M7's graph, and it has 20 crashes where it had 68. The later drift goes toward red's half in every seed. It goes one way because the lane has no noise and the M8 polyline is not symmetric about the centre (Inference).

**What this does not explain** (Unresolved). The M8 map's nearest bend turns 21 degrees, 319 units on blue's side of the centre. The sweep says that a single bend of 10 or 20 degrees there tips the lane at 97 s, and the independent review ran that one bend alone and saw it do so in 3 of 3 seeds (Reported). The M8 map has that bend and holds until 247 s. So the map removes the early drift, and the sweep does not say why. That the map's four bends offset each other is a guess. No pair of bends was tested. The game's file has one polyline per lane, linked from the blue barracks. That red's minions walk it reversed is Assumed.

**Minion targeting, read again.** The wiki's Minion page was read a third time on 2026-11-12 through a fetch tool, sentence by sentence for its Behavior section. The readings of campaign 1 were less exact on three points.

| What the page says (Sourced) | The M8 lane |
| --- | --- |
| A champion that stands in the minion's path triggers a call for help when no other target is in attack range and the champion is outside a turret's range. | A minion attacks a champion in its path when no enemy minion and no tower is within 500 units, and the champion is outside the range of every standing tower of the lane. Using the acquisition range and not the attack range is Assumed. |
| A champion that damages an enemy champion triggers a call for help. With several sources, minions take the closest. | The `harassing` flag of a champion's lane input. The world sets it from C5 on. |
| Except for the first wave, a call for help is ignored by minions that are attacking a turret. | Modelled, with the exception. |
| A minion switches only to a target of higher priority, and cannot take a new target of the same priority. | A minion keeps a living minion target in reach. A minion on a champion turns to an enemy minion that comes within 500 units. |
| Minions re-evaluate their target between attack windups, "every few seconds". | The lane re-evaluates on every tick. Assumed, no number is given. |
| If an enemy champion stops attacking an allied champion, minions keep targeting it "for a short time". | A window after the champion's last blow (C5, section 8.1). The length is Assumed. Campaign 1 read this as persistence on any champion target. The page ties it to the call for help. |
| Targets must be within 500 units. A call for help reaches 1,000. | Both. The game's data file gives the caster an acquisition range of 700 and the melee minion none. The lane keeps 500 for all. Unresolved. |
| First-wave minions pass through units for 28 s in the side lanes and 18 s in mid, and ignore champions until one walks "much closer" or the waves meet. | Not modelled. Section 5.7 measures what that leaves out. |
| When the first waves meet, the melee minions spread their attacks across the three enemy melee minions "regardless of distance". | The lateral slots do this for every wave. For the first wave it is Sourced. For later waves it stays Assumed. |
| A minion that loses sight of its target takes a new one. A minion below 0.35 percent health gets 0.066 s of grace against a minion's killing blow. | Not modelled. |
| Minions respect unit collision. The minion pages give a pathing radius of 35.74 and a gameplay radius of 48. | Not modelled. Section 5.6 counts where bodies would overlap. |

**Attack timing.** In campaign 1 a minion's blow landed at the instant its attack was ready, and the first blow landed on arrival. The game's character data files (Community Dragon 16.22, read through the fetch tool on 2026-11-12) give each lane minion a cast time and, for ranged minions, a missile speed.

| Minion | Attack period | Cast time | Missile speed |
| --- | --- | --- | --- |
| Melee | 0.8 s | 0.393 s | none |
| Caster | 1.5 s | 0.47 s | 650 |
| Siege | 1.0 s | 0.30 s | 1,200 |

In the M8 lane an attack starts when the minion is ready and its target is in reach. The blow leaves the minion one cast time later. A melee blow lands then. A missile lands after its flight. Two details have no source and are Assumed, from how the game treats any attack. A cast whose target dies or leaves reach is cancelled and starts again on a new target, which costs the part of the cast spent on the old one. A missile whose target dies in flight is lost. Tower shots and champion hits stay instant (Assumed simplification). A caster 500 units from its target lands its first blow 1.24 s after it starts, where campaign 1 landed it at once (Tested, `tests/test_lanes.py`, four timing tests).

**Carried over from campaign 1.** Side-lane speed, the pushing advantage, the priority on every retarget, and the keyed order of simultaneous champion attacks are unchanged. Handoff 005 has their history.

### 4.3 Reference rules that the lane still leaves out

- From M7's list: minion speed growth after 10:00, the smaller waves of the mid game, bounties, role quests, the support item's later tiers and its income from hitting champions.
- From the wiki readings: melee minion armor (0 at the start, 20 late), the first wave's ghosting and its indifference to champions, the retarget cadence, the death grace, and the caster's acquisition range of 700 in the data file.
- Unit collision. Bodies that block each other need a lane with width.
- Tower shots have no cast time or missile flight.

### 4.4 The `LANE` action: what the champion hits, and where it stands

M7 section 5.6 gave a `LANE` action five modes, and one of them, `hold`, fixed both the stand and the hits: a holding champion last-hit. M7's own freeze plans thin a wave while they hold it, so the experiments used a flag that agents did not have. A `LANE` action is now a triple.

| Part | Values | Meaning |
| --- | --- | --- |
| Lane | `top`, `mid`, `bot` | The role rule leaves a laner only its home lane. |
| Mode | `passive`, `last_hit`, `thin`, `push` | What the champion hits: nothing, only a minion that one hit kills, casters first, or everything with its area damage. |
| Stand | `wave`, `hold` | Where it stands once its own wave is gone. `wave` steps aside, or for `push` stays in the path at its attack range. `hold` stays in the path on the line that stops the enemy lead minion 300 units outside its own tower's range. |

While the waves are in contact, every action stands at the wave. That gives 24 `LANE` entries where M7 had 15. It is the smallest change that separates standing from hitting: one flag beside the mode. A sixth mode would have named one more combination and left the others out. `stance(lane, team, mode, attack_range, front, hold)` returns the stand and whether the champion is in the minions' path, and the world and the experiments call the same function (Tested, `tests/test_lanes.py`, `tests/test_world_intents.py`).

No action is called freeze or slow push. Whether a held wave stays is decided by the minions.

**The front that the team knows.** Since C6, `stance` gets its front from `champions.known_front`: the team's own lead minion, and the enemy lead minion only while the team sees it (M7 section 6.3). `lane_post` and `economy.lane_inputs` both call it, so no automatic placement reads the lane's true front (Tested, `tests/test_vision.py`, the two stance tests, and the mutation that hands `stance` the true front).

### 4.5 Gold, XP, and the ledger

`riftgame/economy.py` owns what a champion earns. Each champion has an unspent gold total and a ledger with one entry per source.

| Ledger entry | Paid when | Status |
| --- | --- | --- |
| `STARTING` | 500 at the start | Sourced |
| `PASSIVE` | 20.4 per 10 s from 1:05, to every champion | Sourced |
| `MINION` | A minion's gold, once. To the champion that lands the killing blow, or to the support's nearest ally when a charge shares the kill. | Sourced |
| `SUPPORT_ITEM` | 3 per 10 s to the support, plus 18 for each charge used | Sourced. The start at 0:00 is Assumed. |
| `CAMP` | A camp's gold, to its killer (section 7) | Sourced amounts |
| `KILL`, `ASSIST`, `PLATE`, `TOWER` | Kill gold to the killer, the assist pool to the assisters, plate gold and tower gold to the champions that the rules of section 8.1 name | Sourced amounts |

Gold spent is not stored. It is the price of the upgrades a champion owns, and the invariant checker asserts that unspent gold equals the ledger less that price.

### 4.6 Acceptance criteria of C2

The criteria are those of M7 section 10.1 for C2. Every row is Tested unless it says otherwise.

| Criterion | Result | Evidence |
| --- | --- | --- |
| The three wave experiments run on the M8 lane with M7's pass tests unchanged | Done. M7's verdicts are unchanged: no slow push and no freeze by M7's tests, with M7's scripted champion. | `m7_tests_on_m8_lane.json` |
| Each measurement of M7 section 5.6 stands beside the simulator's value where someone has taken it | Nobody has taken one. Section 5.8 lists the simulator's values. | Section 5.8 |
| No rule is added to produce a freeze or a slow push | The lane gained documented rules, the timing constants of the game's data files, and the game's corner waypoints. Every diagnostic is off in the lane that ships. | Section 4.1, `tests/test_lanes.py` |
| Minion conservation, mirror symmetry, gold only for a champion's own killing blow, the XP split, independence between lanes | Hold | `tests/test_lanes.py`, `tests/test_economy.py` |
| First waves meet at the time that route length and minion speed give, within one tick | 51.5 s in mid and 60.5 s in top and bot, on the M8 map | `tests/test_lanes.py` |
| In bot lane each minion's gold is paid at most once. The pair's XP is 1.3 times a solo laner's within 2 percent. The support item's gold is counted apart. | Hold | `tests/test_economy.py` |
| An incentive screen over at least 10 lane states, with no pass condition | 12 states and the 8 `LANE` actions, in a full world. No action earns most in every state. | Section 5.9 |
| The tick sweep of risk RK2 is reported | 10 of 17 of M7's metrics within 10 percent at 0.5 s, and the world-driven counts at ticks of 0.125, 0.25, 0.5, and 1.0 s | Sections 5.5 and 5.9 |

## 5. Wave behaviour through the action table

Every number in this section is at a 0.5 s tick over 5 seeds unless it says otherwise. A range in brackets is the minimum and maximum across seeds. The results files are in [`experiments/m8/waves/results/`](../../experiments/m8/waves/results/). `python -m experiments.m8.waves.capabilities --report` prints the counts of `capabilities.json` that this section quotes.

### 5.1 The port still reproduces M7

[`m7_tests.py`](../../experiments/m8/waves/m7_tests.py) runs M7's 103 wave cases on the lane. With `M7_LANE`, which runs on M7's route graph, and M7's draw key, 998 of 998 metrics equal M7's results file (Tested, `port_check_with_m7_draw_key`). In campaign 2 a separate check stepped the lane under M7's rules beside the lane of the commit before for 600 s on 3 seeds, and every minion's position and health agreed on every tick (Reported, that script is not kept).

### 5.2 How the experiments run now

[`agents.py`](../../experiments/m8/waves/agents.py) stages a full world of ten champions, and every champion starts on its fountain. A `Laner` puts the lane's champion of each team at its outer tower at a chosen level, the same on both teams, so that no team leads in level. A plan is a function from what the laner's observation holds to a `LANE` action, called on decision ticks every 2 s. It reads the champion's own health and caster kills, and its lane as the team sees it: the team's minions within 1,500 units behind its lead, the enemy minions near the enemy lead while the team sees one, and whether the waves are in contact. The world does the rest: the walk, the stance, the hits, minion damage, death.

The team does not see the enemy lead minion on a median of 6.7 percent of ticks in the stacking cases, 6.0 percent in holding from the first wave, and 6.2 percent from the third. The largest share in one case is 59.5 percent. Below 30 percent health a laner walks to its own outer tower with a `MOVE` and comes back above 60 percent. The staging sets a champion's level, place, and the clock at the start, and the holding cases add the surplus casters during the run. Nothing else is edited in a run.

**Two controls.** `absent` is a laner on its fountain. Its plan word `leave` is a `MOVE` to `own_fountain`. `under tower` is a laner that stands at its own outer tower and does nothing. There it gains XP, which feeds its team's level and so the pushing advantage from 3:30, and it may be hit. In campaign 2 `absent` stood at the tower, so it was the under-tower control under another name. The two now differ in XP in every seed of the test setting (Tested, `test_a_champion_under_its_tower_gains_xp_and_an_absent_one_gains_none_after_it_left`). In the wave counts they give the same held cycles in all 96 holding settings and different largest crashes in 7 of 48 stacking settings. Both stand beside every plan in stacking and holding. The untouched lane beside each bounce case has nobody near it.

The champions are the profiles of `riftgame.champions`, which are placeholders. A level goes with a clock: level 1 from 0:00, level 3 from 2:30, level 6 from 6:00. The lanes start empty at that clock, so the minions have that time's stats and siege waves.

| Champion setting | Lane |
| --- | --- |
| Top at level 1, 3, and 6 | top |
| Mid at level 1, 3, and 6 | mid |
| Carry alone at level 3, and carry with a support that stands with it and hits nothing | bot |

**Later waves.** The first wave has rules of its own (section 5.7), so each experiment also starts later. Stacking starts at the meeting of the third waves, after both laners last-hit the first two. Holding places 3 or 4 surplus casters when the laner's third wave reaches the edge of its tower's range. A bounce follows a hard push after two last-hit waves.

**What a row reports.** Per setting and plan, `capabilities.json` holds every seed's value beside the median, the minimum, and the maximum. It reports durations (`kept_out_s`, `first_crash_s`, `largest_crash_s`) and costs (`minion_gold`, `xp`, `minion_damage_taken`, `champion_lowest_health`, `champion_retreats`, and the damage to the laner's own tower). Under `paired` it compares each plan with each control seed by seed: the median, minimum, and maximum of the plan's value less the control's, and the number of seeds in which the plan's is higher. The file is about 6 MB.

Campaign 1's scripted champion had 30 armor, a pushing area damage of 70 per second, and an opponent that could not die and jumped to its spot. None of that is left in the experiments about champions. M7's own cases keep it, because they are the port check.

### 5.3 Revised criteria, and the evidence against the old ones

The owner asked for criteria that keep the meaning of each capability: sustained wave control, reinforcement accumulation, delayed crashes, and bounce. A first revision in campaign 2 was too loose, and the independent review showed where (handoff 006, §3.5). The criteria below are the second revision. Campaign 3 kept their form and every threshold, and they stay provisional. Only the lists of controls changed, because the old `absent` was not absent (section 5.2). Each criterion compares a plan with a lane that nobody touches, because an untouched lane does not stand still (section 5.4).

| Capability | Old criterion | What is wrong with it | Criterion now |
| --- | --- | --- | --- |
| Crash | A hard push reaches the tower before the second enemy wave can. | Nothing. | Kept. |
| Delayed crash | A thinning plan reaches the tower later than a push, with 12 minions. | Two properties in one verdict. | Its own verdict: a thinning plan's first crash comes later than the push's in every seed. This is a weak property, since thinning is slower than pushing by construction. |
| Reinforcement accumulation | 12 or more minions near the lead at the first tick in tower range. | Twelve is two full waves of six. A wave with a siege minion has seven, a thinned wave has lost some of its own, and a crash can hold parts of three waves. A bar of exactly 12 calls a crash of 11 minions from three waves no stack. | In every seed the plan's largest crash holds, at its largest moment, at least three minions from each of two spawn waves, and more minions than the largest crash of a hard push, of a laner on its fountain, and of a laner under its tower in the same setting. The count of 12 is reported beside it. |
| Sustained wave control | The front stays within 1,500 units outside the tower's range for over half of 240 s, and both controls stay below half. | The band does not measure a hold. With no champion the front was in the band for 214 s of 240 against a last-hitting opponent in mid, while the enemy wave reached the tower in every cycle and dealt 445 damage to it. The control clause also blocked the test at three of five surplus sizes (handoff 005, F9). | A wave cycle of 30 s is held when the front is in the band for at least half of it and the enemy wave is never in the tower's range during it. A hold plan sustains control when, in every seed, the champion does not die, the first three cycles are held, and that is more cycles than a laner on its fountain, a laner under its tower, a laner that last-hits with its wave, or a laner that pushes holds in any seed. |
| Bounce | After a hard push of one wave, the contact point is back past the centre within 120 s, in every run, in mid and top. | One wave of six is the weakest crash. A lane that meets again exactly at the centre counted as not bounced without being named. And an untouched lane can drift to one side by itself, so a return proves nothing about the crash unless it beats that lane. | After a crash, the front comes back more than 100 units past the centre in every run, and in every run before the front of the same lane with no laner gets there. The crash is tried with one hard-pushed wave, with a thinned wave, and with a hard push after two last-hit waves. A lane that meets again within 100 units of the centre is called a reset. |

**What these criteria still choose.** Three cycles is 90 s, where M7's test asked for more than half of 240 s. No counterexample supports that cut. It is where the results have something to show: some hold lasts one cycle in every seed in 52 of 64 settings, two in 40, three in 13, four in 1, and none lasts longer. Three minions per wave and 100 units are choices too. All are named constants in [`capabilities.py`](../../experiments/m8/waves/capabilities.py). Six strict expected failures in [`test_behaviours.py`](../../experiments/m8/waves/test_behaviours.py) keep the unmet bars in view: the slow-push drill of a level 1 top laner, accumulation against an opponent that last-hits, 12 minions at the enemy tower, a hold for all eight wave cycles of the run, a hold of a first wave at 6:00 for a level 6 mid laner, and a mid bounce after a hard push of the first wave. Campaign 2 had eight. The other two now pass as plain tests, a top-lane bounce that beats the untouched lane at level 1 and an untouched top lane that stays at the centre for 150 s.

### 5.4 Results

**An untouched lane first** (`investigation.json`, `untouched`, 300 s, no champion). Everything below is read against this.

| Lane | With the M8 lane | On M7's route graph | With ranges along the lane |
| --- | --- | --- | --- |
| Top | The front stands more than 100 units on red's half at 281 s [247 to 281], in 5 of 5 seeds. No wave reaches a tower within 300 s. | The front is on blue's half at 97 s in 5 of 5 seeds. Red's wave reaches blue's outer tower once or twice, with 8 minions [7 to 12] at most. | The front never leaves the centre, and no wave reaches a tower. |
| Mid | The front leaves the centre in 2 of 5 seeds, at 243 s. | The same | The same |
| Bot | The front leaves the centre in 1 of 5 seeds, at 158 s. | 1 of 5, at 157.5 s | 1 of 5, at 158 s |

**The bend sweep** (`investigation.json`, `bends`). An untouched lane with top lane's length, towers, and spawn points, the M8 lane rules, 12 seeds of 600 s. A crash is a wave at the enemy outer tower.

| Shape | Front on a half first, blue and red, of 12 | Leaves the centre, median | Crashes in the 12 runs, by blue's and by red's waves |
| --- | --- | --- | --- |
| No bend, one bend of 46 degrees at the centre, or one of 5 degrees 295 units on blue's side | 0 and 0 | Never | 0 and 0 in each |
| One bend of 46 degrees, 295 or 150 units on blue's side | 12 and 0 | 97 s | 26 and 42, 34 and 40 |
| One bend of 46 degrees, 150 or 295 units on red's side | 0 and 12 | 97 s | 40 and 32, 37 and 25 |
| One bend of 10 or 20 degrees, 295 units on blue's side | 12 and 0 | 97 s | 34 and 36, 34 and 37 |
| M7's route graph | 12 and 0 | 97 s | 26 and 42 |
| The M8 map, and with ranges along the lane | 0 and 12, 1 and 0 | 281 s [247 to 281], 430 s in 1 seed | 6 and 14, 0 and 0 |
| Mid on the M8 map, for comparison | 3 and 4 | 243 s, in 7 seeds | 16 and 9 |
| Bot on the M8 map, and on M7's route graph | 1 and 3, 3 and 4 | 158 s in 4 seeds, 224.5 s in 7 | 9 and 11, 9 and 16 |

M7's graph gives exactly the numbers of one bend of 46 degrees 295 units on blue's side. The M8 map delays the first departure of top lane from 97 s to 247 to 281 s and cuts its crashes from 68 to 20, against 25 in mid, which has no corner.

**Accumulation and delay** (`capabilities.json`, `stacking`). Seven plans, a hard push, a laner on its fountain, and a laner under its tower. Three starts (first contact, the moment an enemy push reaches the laner's tower, and the meeting of the third waves), an opponent that is absent or last-hits, 8 champion settings: 48 settings in all.

| Result | Value |
| --- | --- |
| Settings in which some plan accumulates reinforcements | 2 of 48. By start, 1 of 16 from first contact, 1 of 16 from the own tower, and 0 of 16 from the third wave. None of the 24 against an opponent that last-hits. |
| From the own tower | Carry alone, level 3, opponent absent. Four thinning plans accumulate. `thin 2, then last hit` brings 9 minions [9 to 9], three of them from the second-largest wave in the crash, 45.5 s after the plan starts. The hard push brings 5, and a laner on its fountain and a laner under its tower 6 each. The plan's crash is the larger against each of the three in 5 of 5 seeds. |
| From first contact | Carry and support, level 3, opponent absent. `thin 3, then passive` brings 8 [8 to 8], three from the second-largest wave, at 171.5 s [171.5 to 174]. The hard push brings 5 at 18 s. With the laner on its fountain or under its tower no wave reaches the tower. |
| Largest crash | 10 minions as a median, in mid at level 1 from first contact against an absent opponent, under `thin 3, then passive`. It does not count, because in 2 of 5 seeds the crash holds 8 with 2 from the second-largest wave. With no laner the largest crash holds 8. No crash holds 12. |
| The slow-push drill: top, level 1, from first contact, kill 3 casters, then last-hit | 8 minions of two waves, six and two, 38.5 s after contact. The hard push there crashes first with 5 at 18 s and brings 9 of two waves at 30 s. The drill does not accumulate. |
| Settings in which some thinning plan delays the first crash | 43 of 48: 16, 15, and 12 of 16 by start |

**Holding from the first wave** (`capabilities.json`, `holding`). The experiment places 2, 3, 4, or 6 surplus enemy casters at the hold line when the laner's wave arrives, and the opponent is absent or last-hits: 64 settings, 7 hold plans and 4 controls each, 240 s.

| Result | Value |
| --- | --- |
| Settings in which some hold plan sustains control | 9 of 64 |
| By champion setting, of 8 each | Top 1, 1, 0 at levels 1, 3, 6. Mid 2, 1, 0. Carry alone 2. Carry and support 2. |
| Settings in which some hold lasts at least 1, 2, 3, 4 cycles in every seed | 52, 40, 13, 1. None lasts 5. |
| With a laner on its fountain, and with one under its tower | The same in every setting. 0 cycles in 45 settings, 1 in 7, 2 to 6 in 12. |
| With a laner that last-hits with its wave, and with one that pushes | 0 cycles in 38 settings, 1 in 9, 2 or more in 17. A pusher holds 0 in 2, 1 in 56, and 2 in 6. |
| Longest hold | Four cycles, by `hold, thin over 1` for mid at level 1 against 3 surplus casters and no opponent. No retreat, lowest health 52 percent, and the wave kept out for all 240 s. No control holds more than 1 cycle there. |
| Sustaining plans | In 7 of the 9 settings only plans that thin or trim while they hold sustain control. `hold, last hit` sustains in 2, both bot-lane carries at level 3 against 3 surplus casters and no opponent, where a laner that last-hits with its wave holds 2 cycles. |
| What a hold costs | In 4 of the 9 settings every sustaining plan retreats once in some seed, and its lowest health falls to 17 to 28 percent. |

**Holding from the third wave** (`capabilities.json`, `holding_from_the_third_wave`). With 3 or 4 surplus casters over 32 settings, a hold plan sustains control in 3, and some hold lasts at least 1, 2, 3, 4 cycles in every seed in 28, 17, 3, and 0. Two are in mid against 3 surplus casters, with no retreat. At level 3 against an opponent that last-hits `hold, thin` sustains control, and at level 6 with no opponent `hold, thin over 3` does. The third is the carry alone at level 3 against 4 surplus casters and an opponent that last-hits. There four plans sustain control, `hold, last hit` among them, and each retreats once in some seed and keeps the wave out for at least 202 s. A laner on its fountain or under its tower holds 0 cycles in 29 of the 32 settings.

**Bounce** (`capabilities.json`, `bounce`). A laner follows a plan from first contact until its wave is in the enemy tower's range, then walks to its fountain. Each cell gives the median seconds from the crash until the front is back more than 100 units past the centre and the runs in which it is, then the same for the untouched lane, then whether the case counts.

| Champion setting | Hard push | `thin 3, then last hit` | Last hit two waves, then hard push |
| --- | --- | --- | --- |
| Top, level 1 | 91.5 s in 5 of 5. Untouched 318 s in 5. Counts. | 70 s in 5. Untouched 297.5 s in 5. Counts. | 62.5 s in 5. Untouched 289 s in 5. Counts. |
| Top, level 3 | 53 s in 5. Untouched 204 s in 5. Counts. | 48.5 s in 5. Untouched 200 s in 5. Counts. | 95 s in 5. Untouched 169 s in 5. Counts. |
| Top, level 6 | 109 s in 5. Untouched 124 s in 5, first in 2 runs. No. | 42.5 s in 5. Untouched 102 s in 5, first in 2 runs. No. | 52.5 s in 5. Untouched 68 s in 5, first in 2 runs. No. |
| Mid, level 1 | 268 s in 2 of 5, on the same tick as the untouched lane. The other 3 reset. No. | 61 s in 5. Untouched 254.5 s in 2. Counts. | 62.5 s in 5. Untouched 229 s in 2. Counts. |
| Mid, level 3 | 149.5 s in 5, on the same tick as the untouched lane in every run. No. | 47.5 s in 5. Untouched 138 s in 5. Counts. | 82.5 s in 5. Untouched 105.5 s in 5, first in 2 runs. No. |
| Mid, level 6 | 46.5 s in 5. Untouched never. Counts. | 34 s in 5. Untouched never. Counts. | 39.5 s in 5. Untouched never. Counts. |
| Carry alone, level 3 | 53.5 s in 5. Untouched never. Counts. | 48.5 s in 5. Untouched never. Counts. | 168 s in 5. Untouched never. Counts. |
| Carry and support, level 3 | 53.5 s in 5. Untouched never. Counts. | 48.5 s in 5. Untouched never. Counts. | 107.5 s in 5. Untouched never. Counts. |

The front comes back in every run in 23 of 24 cases, and before the untouched lane's front in every run in 18. On the M8 map every top-lane crash at levels 1 and 3 beats the untouched lane by at least 42.5 s in every run, which campaign 2 could not show. In bot and in mid at level 6 the untouched lane never gets there within the run, so those returns beat it by default.

**Why mid resets at 0:00.** The level 1 mid laner crashes 5 minions into the tower 63.5 s into the game in every seed. In a run traced in campaign 2, the tower killed them before red's second wave arrived, both second waves then walked the same distance, met at the exact centre with six minions each, and stayed equal for about two minutes, until tie-breaking draws separated them (Reported, one trace, handoff 006). In the 2 runs that come back now, the front returns on the same tick as the untouched lane's front. Whether a real mid lane resets after a first-wave crash is unknown.

### 5.5 Diagnostics: one rule at a time, and the tick

A diagnostic changes one lane rule for one table. It shows which rule a verdict rests on. It is not a candidate for the lane. Two champion settings (top at level 1, mid at level 3), 3 seeds, 8 stacking settings, 8 holding settings with 3 and 4 surplus casters, and 4 bounce cases (`capabilities.json`, `diagnostics`).

| Lane | Untouched first-wave fight, mid and top | A plan accumulates (a thinning plan), of 8 | Largest crash (with no laner) | A hold sustains (longest, cycles), of 8 | Bounces in every run (before the untouched lane), of 4 |
| --- | --- | --- | --- | --- | --- |
| The M8 lane | 33 s, 33.5 s | 0 (0) | 8 (8) | 2 (4) | 4 (3) |
| M7's route graph | 33 s, 34.5 s | 1 (1) | 11 (10) | 2 (3) | 4 (1) |
| Blows land at once | 31 s, 31.5 s | 2 (2) | 9 (7) | 1 (3) | 3 (3) |
| Ranges along the lane | 33 s, 33.5 s | 0 (0) | 8 (6) | 2 (4) | 3 (3) |
| No tower shelter | 33 s, 33.5 s | 0 (0) | 8 (8) | 2 (4) | 4 (3) |
| At most 2 melee minions on a target | 33 s, 33.5 s | 3 (2) | 11 (6) | 2 (4) | 3 (2) |
| A cancelled cast costs nothing | 33 s, 33.5 s | 0 (0) | 9 (7) | 2 (3) | 3 (3) |
| A missile to a dead target turns to another | 33 s, 33.5 s | 1 (1) | 11 (7) | 0 (2) | 3 (3) |
| Both of those | 33 s, 33.5 s | 2 (1) | 9 (8) | 0 (2) | 3 (3) |
| Detour of 0.3 s | 33 s, 33.5 s | 0 (0) | 10 (10) | 3 (3) | 3 (3) |
| Detour of 0.6 s | 33 s, 33.5 s | 1 (1) | 11 (8) | 2 (3) | 3 (3) |
| Minion blows at 0.85 | 38 s, 38.5 s | 0 (0) | 10 (9) | 4 (3) | 4 (0) |

**What the table shows.** No rule produces the behaviours. Every variant moves a count by three settings at most, and not in one direction. The M8 lane accumulates in none of these 8 settings, because its two accumulating settings are bot-lane carries, which the diagnostics do not run. M7's route graph brings back an accumulating setting and a crash of 11, and only 1 of 4 bounces beats the untouched lane there, because the untouched top lane then tips at 97 s (Inference from section 5.4). With blows that land at once, one hold is sustained where the M8 lane has two. Attack timing is therefore a sourced correction of how long fights last. It is not what makes a hold or a stack appear. A missile that turns to another target leaves no hold sustained. Weaker minion blows lengthen the fight by 5 s and leave no bounce that beats the untouched lane.

**Tick length** (`capabilities.json`, `tick_sweep`). The same counts at four ticks, with a decision every 2 s at each.

| Tick | A plan accumulates (a thinning plan), of 8 | Largest crash (with no laner) | A hold sustains (longest, cycles), of 8 | Bounces in every run (before the untouched lane), of 4 |
| --- | --- | --- | --- | --- |
| 0.125 s | 3 (3) | 10 (7) | 3 (3) | 3 (0) |
| 0.25 s | 1 (1) | 9 (9) | 4 (4) | 3 (2) |
| 0.5 s | 0 (0) | 8 (8) | 2 (4) | 4 (3) |
| 1.0 s | 1 (1) | 10 (10) | 4 (3) | 4 (3) |

The counts wobble with no direction. The numbers behind them show more. `tick_spread` takes each case that has a value in every run and computes its mean at each tick, the range of those four means, and its range across seeds averaged over the ticks. The table gives the means of those over the cases.

| Measure | Cases | Mean at 0.125, 0.25, 0.5, 1.0 s | Mean range across ticks | Mean range across seeds | Cases equal at every tick |
| --- | --- | --- | --- | --- | --- |
| Largest crash, minions | 80 | 4.917, 4.892, 4.862, 6.008 | 2.858 | 1.009 | 4 |
| First crash, s | 48 | 42.283, 41.717, 57.115, 50.778 | 30.137 | 3.956 | 0 |
| Held cycles | 88 | 0.973, 1.008, 1.102, 1.117 | 0.33 | 0.179 | 52 |
| Kept out, s | 88 | 92.813, 91.652, 97.97, 96.28 | 10.75 | 6.365 | 18 |
| Bounce back, s | 3 | 69.042, 67.583, 69.611, 68.667 | 10.611 | 1.344 | 0 |

Every measure moves more across ticks than across seeds. The means over all cases move less than single cases do. Between 0.25 s and 0.5 s only the largest crash and the bounce time agree. The mean first crash comes 15 s later at 0.5 s, the wave is kept out 6 s longer, and the held cycles rise from 1.01 to 1.10. The mean largest crash grows at 1.0 s. Section 5.4 counts at 0.5 s, so its crash times and hold lengths are not converged in the tick. Every-seed verdicts on single settings are not stable in the tick.

**How one case flips.** In top at level 1 with both laners present and `thin 2, then last hit`, the first crash comes at 41.5 to 42.5 s at ticks of 0.125 and 0.25 s, and at 191.5 to 197 s at 0.5 and 1.0 s (`tick_sweep`). One trace of that case found the blue laner with 3 last hits by 75 s at 0.25 s and 2 at 0.5 s, and red with 3 and 5 by 90 s (Reported, a scratch probe recorded in the decision trail). A quarter second in a minion fight changes which last hits land, and a near-balanced lane amplifies the difference into a different crash (Inference from that one trace). No rule was varied across ticks, so this does not rule out a single rule. The once-per-tick march of section 4.2 is a candidate. C7 owns the sweep over tick lengths and decision intervals (M7 risk RK2), and until then every count of section 5.4 is a count at 0.5 s.

### 5.6 Attack timing and movement obstruction, from traces

The owner asked for traces of attack timing and movement obstruction, and noted that a cap on attackers does not test obstruction.

**Attack timing.** The lane counts cancelled casts and lost missiles. In an untouched lane over five minutes (`investigation.json`, `attack_timing`):

| Lane | Minion deaths | Casts cancelled | Missiles lost |
| --- | --- | --- | --- |
| Mid | 104 | 43 | 46 |
| Top | 100 | 34 | 50 |

A placed fight of six against six lasts 28 s with timing and 25.5 s without. The untouched first-wave fight lasts 33 s in mid and 33.5 s in top, against 31 s and 31.5 s without timing. When wave 2 reaches the fight in mid, 29 s after the first blow, the six minions of wave 1 that are alive hold 23 percent of their health on average, against 7 percent without timing. Those are the effects of timing that this document can stand behind. Section 5.5 shows that the wave verdicts do not follow from them.

**Movement obstruction.** The lane has no bodies, and two bodies of the sourced pathing radius cannot stand within 71.5 units of each other in one lateral slot. The experiments count where the lane puts them there.

| Run | Minions that overlap an ally, share of minion ticks in contact | Most melee minions on one target |
| --- | --- | --- |
| Untouched mid lane, 5 minutes | 1.2 percent | 2 |
| Untouched top lane, 5 minutes | 0.8 percent | 2 |
| The carry's accumulating plan, `thin 2, then last hit` (9 minions) | 2.7 percent | 3 |
| The carry and support's accumulating plan, `thin 3, then passive` (8 minions) | 7.5 percent | 3 |
| A hard push in either setting | 0.0 percent | 3 |

Never more than three melee minions attack one target, and six bodies fit around one, so the place where bodies would matter is not the target. It is the walk to the next target inside a crowd, and the crowd grows with the stack. The `detour_s` diagnostic charges that walk. A melee minion that turns to a new minion target loses 0.3 s or 0.6 s before its cast. One body's detour at minion speed is about 0.25 s (Assumed geometry on the sourced radius). The length of a fight does not show the detour. A placed fight of six against six stays at 28 s even with a detour of 5 s (Reported by the review of campaign 2). The verdict counts of section 5.5 are the evidence, and they move by one setting. This bounds one effect of obstruction in a lane without width. It does not show what bodies do.

### 5.7 The first wave's exceptions

The wiki gives the first wave three exceptions (section 4.2). The M8 lane models one of them.

| Exception (Sourced) | In the M8 lane | What it changes in section 5.4 |
| --- | --- | --- |
| Minions of the first wave answer a call for help while they attack a tower. | Modelled by `first_wave_call` (Tested, `test_only_minions_of_the_first_wave_answer_a_call_for_help_while_they_attack_a_tower`). | Part of every result. |
| First-wave minions ignore champions until one walks much closer or the waves meet. | Not modelled. | Nothing measured. In 0 of 1,440 stacking and holding cases (480, 640, and 320 by section) does a minion hit the champion before the first waves meet (`minion_blows_before_first_contact`). |
| First-wave minions pass through units for 28 s in the side lanes and 18 s in mid. | Not modelled. | Nothing can. The lane has no bodies (section 5.6). |

### 5.8 What is known, what is not, and three measurements

**Read and equal to the ruleset** (Sourced): minion health, damage, attack speed, range, and the on-hit share. **Read in the game's data files** (Sourced): cast times, missile speeds, and the corner waypoints of the M8 map. **Documented and not modelled:** section 4.3. **Not documented anywhere read so far:** how long bodies take to walk around each other, the retarget cadence, and the length of the short time that minions keep a harassing champion as target.

Three measurements in a custom game on patch 26.22 bear on the open behaviours. The simulator's values changed with the corrections.

| Measurement | The simulator's value |
| --- | --- |
| **A. The untouched first wave in mid.** Nobody touches the lane. When the minions of wave 2 reach the fight, count the minions of wave 1 that are still alive and note how healthy they look. | Wave 2 arrives 29 s after the first blow. Six minions of wave 1 are alive, at 23 percent of their health on average. Left alone, the fight would end 33 s after the first blow. |
| **B. The slow-push drill in top.** A level 1 laner kills the three casters of wave 1 and then only last-hits, with no opponent. Count the minions that reach the enemy outer tower and time their arrival from first contact. | 8 minions of two waves, six and two, 38.5 s after contact. The placeholder top laner needs longer for the casters than a real champion might. |
| **C. An untouched top lane.** Nobody touches the lane for five minutes. Note whether the waves keep meeting near the centre or one side reaches a tower. | The front stays within 100 units of the centre for the first 150 s in every run and first leaves toward red's half at 247 to 281 s. No wave reaches a tower within 300 s. On M7's route graph the front was on blue's half at 97 s in every run. |

A match in A would confirm one timing. B and C test results that this document does not trust.

### 5.9 Incentive screen and M7's tick sweep

**Incentives** (Tested, [`incentives.json`](../../experiments/m8/waves/results/incentives.json)). A level 1 laner plays one `LANE` action for 5 minutes in each of 12 lane states, in a full world. No action earns most in every state. `last_hit` with the wave earns most gold plus XP in 9 states. `thin` with the wave earns most in top after a crash at the own tower against an opponent that pushes, and `push` earns most in the two mid states in which the opponent pushes. A hold that last-hits earns the same as last-hitting with the wave in the two mid states with no opponent and less in the other ten. In 9 of those ten the holding laner retreats at least once in the median run. The laner's numbers are placeholders, so this is a screen of the mechanics.

**M7's tick sweep** (Tested, `m7_tests_on_m8_lane.json`, `tick_sensitivity_m8_lane`). On M7's scripted cases, 10 of 17 metrics are within 10 percent of the 0.125 s reference at a 0.5 s tick. Campaign 1 measured 13 of 17 before cast times existed, and campaign 2 measured 9. The seven that move are a wave metric in each of three top-lane cases, and the band time or the champion's lowest health in three of M7's hold cases.

## 6. Recall, fountain, and purchases (C3)

### 6.1 What exists

The rules are in `riftgame/champions.py`, called from the tick's last step (M7 section 5.5).

| Rule | Built | Status |
| --- | --- | --- |
| Recall | 8.5 s in place. Damage or a new action discards the progress. On the fountain it completes at once. | Sourced. Existed since C1. |
| Fountain | A living champion within 1,100 units of its own fountain regains 8 percent of maximum health and 10 percent of maximum mana per second. | Sourced |
| Purchases | Each profile has a fixed progression of five entries. On its fountain a champion buys the next entries while its gold covers them, several in a tick if it can. Dead champions shop too. | The two boot steps are Sourced: 300 gold for +25 move speed, then 800 more for +45 in all. The other 15 entries are Assumed. |
| Capability | `capability(profile, level, upgrades)` is a pure function. It never reads gold. | M7 section 5.5 |
| Homeguard, first rule only | From 0:20 a champion that leaves its fountain moves 80 percent faster, falling to 40 percent over 4 s, until 500 units before the outer tower site of its lane. Leaving for a jungle or river edge ends it. Damage ends it and blocks it for 8 s. | Sourced values. The straight-line decay and the tick at which it starts are Assumed. |

**State.** Two integers per champion: the tick of its last move that began on the fountain with Homeguard, and the first tick on which it may have Homeguard again. Gold spent is derived from the upgrades owned.

**Departures from M7 and the reference.**

- Every champion starts with boots. Starting gold is 500 and boots cost 300, so the purchase rule fires at 0:00. The M7 prototype did the same on its first tick.
- The reference lets a completed recall clear the 8 s block. That rule is not modelled. A channelled recall takes 8.5 s, so the block has run out by then, and a recall on the fountain would have cleared it at once.
- Movement-speed soft caps, the 150 percent tier, the endpoint that tracks the wave, and the respawn and game-start bonuses are left out (M7 section 3.4).

### 6.2 What a recall costs, measured

[`recall.json`](../../experiments/m8/results/recall.json) holds 36 round trips from an outer tower: recall, buy, walk back. With two boot steps and Homeguard the trip takes 23 s in mid and 27.5 to 28.5 s in the side lanes. Without Homeguard it takes 29.5 to 30 s and 36 to 37.5 s. A wave spawns every 30 s, so a trip spans zero to two waves by its length and its start. These are route lengths and speeds. What a recall costs in farm depends on the wave, and section 5 says how far the waves can be trusted.

### 6.3 Acceptance criteria of C3

| Criterion (M7 section 10.1) | Result | Test |
| --- | --- | --- |
| A cancelled recall loses all progress | Cancelled at 8.0 s of 8.5 s by damage and by a new action. The channel reads 0, and a restarted recall takes 8.5 s again. | `tests/test_recall.py` |
| Unspent gold changes no capability | 10,000 gold off the fountain changes nothing for 20 ticks. After the recall the champion owns all five upgrades. | `tests/test_recall.py` |
| The round trip from an outer tower takes the time that route length and speed give, within one tick | 12 cases, both teams, three lanes, before and after Homeguard starts. The largest difference is 0.36 s against a tick of 0.5 s. | `tests/test_recall.py` |

The test file holds 58 tests. They measure Homeguard as distance walked per tick, not through its state.

## 7. Jungle (C4)

### 7.1 What exists

`riftgame/jungle.py` owns the camps (M7 section 5.8). Team sight and camp memory are in `riftgame/vision.py`.

| Rule | Built | Status |
| --- | --- | --- |
| Camps | Six per side at the map file's camp nodes. A camp is one pool of health with a damage rate against the champion it fights. | M7 section 5.8 |
| First spawns | On the clock, whatever any champion does: 0:55 for eight camps, 1:07 for Gromp and Krugs. | Sourced |
| Respawns | The camp's death plus 300 s for the two buff camps and 135 s for the others. | Sourced |
| Level | A camp spawns at the average champion level, a half rounding up. Health and XP run in a straight line between the ruleset's two ends over levels 1 to 18. | The level rule is Sourced. The line is Assumed. |
| Scuttlers | Two spawn at 2:55, one on each river node, at 65 percent health. Nothing else is a condition. When both are dead, one Scuttler spawns 150 s after the last death on a river node drawn by key, and from then on the river holds one at a time. | Sourced |
| Fighting | A champion with a `CAMP` action walks to the camp node and spends its attack credit on the camp while it stands there. One attack is worth its camp damage rate over its attack speed (`champions.attack_worth`), so a ready attack lands at once. The camp hits the champion that engaged it first, from the tick after the first blow. | Rates are Assumed placeholders. The ready attack departs from M7's C4 wording, which divides the camp's health by the rate alone. |
| Leash | The camp keeps hitting its champion within 800 units. When that champion dies or leaves, the camp returns to full health, unless another champion is still fighting it. | The 800 units are Assumed. |
| Rewards | Gold and XP go to the killer: the champion that dealt most on the last tick, with a keyed draw between equals. A jungler gets the item's 80 XP per camp and 150 once for its first. | Amounts Sourced. That nobody shares is Assumed. |
| Shrine | A dead Scuttler leaves its killer's team 90 s of sight within 525 units of that river node. The speed effect is left out. | Sourced |
| Team sight | `vision.sees` answers whether a team sees a position. C4 counts its living champions within 1,350 units and its shrines, C5 adds towers, and C6 adds lane minions and wards (section 9). | M7 section 6.1 |
| Camp memory | Per team and camp: what the team last saw there, and the respawn time if it knows it. The team knows the time when it saw the camp die, or sees the camp's location in the last 60 s before the respawn for a buff camp and the last 10 s for another. A team learns of an unseen clear only by seeing the empty camp. | Sourced (M7 section 3.3). The Scuttler uses the 10 s window, Assumed. |
| Observation | 14 camp views from the team's memory, in the order of the `CAMP` actions, each with the walk from the champion. | M7 section 6.3 |

**One departure from the brief of campaign 2.** A camp whose champion leaves does not reset while another champion is fighting it. It turns on that champion and keeps its wounds. A full reset would let a camp heal when an invader kills the jungler at it.

### 7.2 The scripted jungler, reported

`harness.jungler` reads only its observation. It goes to the camp with the best known gold plus XP per second of walking, waiting, and clearing, starts no camp that would take it below 25 percent health, and recalls below 35 percent. [`jungle.json`](../../experiments/m8/results/jungle.json) holds its first clear and a sweep of 9 start positions and 3 camp states.

| First clear | Blue | Red |
| --- | --- | --- |
| Sixth camp dead at | 168.5 s | 167.5 s |
| Level, camp gold, health then | 4, 529, 322 of 744 | 4, 529, 320 of 744 |

Each jungler kills its Blue Sentinel at 66.5 s. Campaign 2 measured the sixth camp at 178 s and 179 s. The difference is the ready attack, which now lands at once on a camp (Inference, from the change in section 7.1). No reference gives a clear time on the 2026 clock (M7 question OQ8), so this time has no pass condition. In the sweep the jungler's pick equals the destination with the most gold plus XP per second in 24 of 27 starts and states. No destination is required to win, and every champion number is a placeholder.

### 7.3 Acceptance criteria of C4

| Criterion (M7 section 10.1) | Result | Test |
| --- | --- | --- |
| Each first spawn falls on the ruleset's clock time | 55.0 s, 67.0 s, and 175.0 s, with nobody acting and in a scripted game | `tests/test_jungle.py` |
| The Scuttlers' first spawn does not depend on a clear (owner requirement) | Both at 175.0 s with 1,007.5 health, with nobody acting and with a jungler in the middle of a clear | `tests/test_jungle.py` |
| Each respawn falls on the camp's last death plus the ruleset's delay, to the tick | 12 camps. The Scuttler pair rule holds over three rounds. | `tests/test_jungle.py` |
| Timer knowledge follows the reference rule for seen and unseen clears | The watching team's timer reads 60.0 s for a buff camp and 10.0 s for the others at the first tick it knows. | `tests/test_jungle.py` |
| A clear takes the camp's health over the champion's camp damage rate, within one tick | Five roles, each within one tick of the camp's health less one ready attack, over the rate. The ready attack is worth more than the tolerance, so a clear that ignored it would fail. | `tests/test_jungle.py` |
| Travel between camps takes route length over speed | Within one tick | `tests/test_jungle.py` |
| Leak test | Every camp fact that a team has not seen is changed. Its observations and masks stay identical until it sees a changed camp. | `tests/test_world_observation.py` |
| The handoff reports the scripted jungler's destinations and first-clear time | Section 7.2 | `jungle.json` |

## 8. Combat and death (C5)

### 8.1 What exists

`riftgame/combat.py` collects champion attacks and settles kills (M7 section 5.9). Tower shots on champions and champion hits on towers are in `riftgame/lanes.py`, because a tower has one attack for minions and champions. There is no fight object and no outcome roll.

| Rule | Built | Status |
| --- | --- | --- |
| One attack capacity | A table entry per intent kind names the one class that a champion's attack goes to on a tick: minions for `LANE`, a champion for `FIGHT`, a camp for `CAMP`, a tower for `SIEGE`, and for `HOLD`, `FOLLOW`, and a finished intent the enemy champion that is attacking it. `Champion.attack_credit` is one budget for every class. One credit is one hit on a minion or a tower, or the damage rate over the attack speed on a champion or a camp (`champions.attack_worth`). A tick against a champion or a camp spends all the credit the champion has, what it brought and what the tick earns. So a ready attack lands at once on any class, and a champion that has just hit a minion deals only what it has earned since. The lane takes the credit in with the champion's input and hands back what its hits left. An idle tick earns attack speed times the tick, up to one ready attack. The area damage of the `push` mode, a stand-in for abilities in the lane, and the lockdown are outside the credit. | M7 section 7.4, owner requirement |
| Champion against champion | A fighter closes to its attack range and deals one attack's worth for each credit it spends, on every tick on which the target is alive, within range by the straight line, and in the view of the fighter's team. All hits of a tick are collected before any lands. | M7 section 5.9. The rates are Assumed placeholders. |
| Hitting back | A champion that holds or follows hits the enemy that deals it the most damage on that tick, if that enemy is within its own range. | M7 section 7.1 |
| Lockdown | Used when it is ready, the mana covers it, and the champion hits a champion. It takes a share of the target's move speed for its duration. | Numbers Assumed, from the M7 prototype |
| `FIGHT` | While the team sees the target, the fighter pursues it, and only to places that the team sees (departures below). Out of view, it walks to the last-seen place in team memory. Seen again on the way, the fight resumes with no outcome. One tick after it arrives within attack range of the last-seen place with the target still unseen, the intent ends with `LOST`. The target's death ends it with `KILLED`, whoever killed it. | M7 section 7.1 |
| Sight | Living towers are sight sources of 1,350 units. A champion that damages an enemy champion is visible to the victim's team on that tick. Each team's memory holds a last-seen record per enemy champion. | M7 sections 6.1 and 6.2 |
| Observation and mask | The observation gains the enemies that the team sees now and which enemies damaged this champion recently. `FIGHT` is offered only against a living enemy in view. A running fight with a hidden target is kept with `KEEP`. | M7 section 6.3 |
| Self-defence | `FIGHT` against a visible enemy that damaged this champion within 5 s stays legal under every leash, on and off the lane. The return actions stay legal. | Owner requirement. The 5 s are Assumed. |
| Towers against champions | A tower shoots first an enemy champion in range that damaged an allied champion standing within 1,400 units of the tower, then minions in their order, and with no minion in range the closest enemy champion. A shot deals the tower's attack damage at that game time, plus half of it for each consecutive shot on a champion before it, up to one and a half times more. The ramp starts again 5 s after the last shot on a champion. | Sourced |
| `SIEGE` | The champion walks to its attack range of the lane's enemy front tower and hits it with whole attacks from the shared credit. A hit is cut by the tower's armor, raised by 20 percent for a melee champion, and cut by 80 percent while none of the champion's minions is within 750 units of the tower. It ends with `CLEARED` when the lane's last tower falls. | Sourced factors. The armor formula is from memory, and the 750 units are Assumed. |
| Plates and tower gold | Each time a tower's missing health crosses a plate threshold, 120 gold is split among the living enemy champions within 1,200 units, whoever dealt the damage. A fallen tower pays its global gold to every enemy champion, and the first tower of the game pays 300 more, split among those near. | Sourced |
| Call for help | A champion that damages an enemy champion is harassing for the lane on that tick and for 2 s after. Minions and towers answer for that long. | The trigger is Sourced. The 2 s are Assumed. |
| Death and rewards | All deaths of a tick are settled from the hits collected before any of them. The killer is the enemy champion that dealt the victim the most damage on that tick, or else the one that damaged it last within 10 s. With neither the death is an execution and pays nothing. Kill gold is 300, plus 10 per victim level from 7. Other champions that damaged the victim within 10 s share half of the kill gold. The first kill adds 100. Kill XP runs in a straight line from the reference's two ends over victim levels. Ties are drawn by key on the places of the champions, never by seat. | Amounts Sourced. The 10 s and the straight line are Assumed. |

**Simultaneous deaths.** M7's prototype paid only the killer that the code visited first when two champions died on one tick. Here each killer gets its kill gold and XP, and of several first kills on one tick a keyed draw picks the one that is first blood. The tests stage five fights and exchange the seats, between the teams and inside a team, and compare places, health, death ticks, gold, and XP on every tick.

**Departures from M7 and the brief of campaign 2.**

- Pursuers move last. A fighter heads for where a target that does not pursue stands after it has moved, but only if its team sees that place inside the move step (`vision.watches`, which counts the team's pursuers where they stood, so the seat order changes nothing). A target that steps out of the team's view on that tick is pursued to where the team last saw it. With places from before the move step, a target that walks away is never hit by any chaser at any speed, because the gap after both moves is the range plus the target's step. `FOLLOW` is unchanged.
- First blood is drawn among the kills of the tick, ordered by the victim's place. M7 said a draw picks the team, and that flips when the teams exchange seats.
- `SIEGE` ends with `CLEARED`, or with `ABSENT` when the lane has no tower to damage. M7 names no outcome.
- A laner that fights in self-defence off its lane is still charged as roaming.
- Left out: bounties and shutdown gold, the level-difference modifier on kill XP, the early growth of the assist pool, the 3 s before backdoor protection returns, plate gold decay, Bulwark, and the armor penetration of tower shots. A tower keeps a champion as target only while that champion is harassing.

### 8.2 The fight scenarios of M7 section 5.9, on the M8 kernel

[`combat.json`](../../experiments/m8/results/combat.json) reruns M7's four scenarios with policies that only choose actions. Every champion number is a placeholder, so the outcomes show that the mechanics respond. They do not show who wins a real fight.

| Scenario | Result |
| --- | --- |
| A champion retreats at half health. Speed edge, lockdown, and distance to its own tower, 18 cases. | 10 escapes and 8 deaths. From 1,000 units every runner escapes. From 2,500 and 4,000 units only the faster runner does. The chaser dies under the tower in all 10 escapes. The lockdown changes no case. |
| A level 1 fighter loses to a level 7 enemy alone. Its jungler walks in from d units. | The side wins with the jungler from up to 2,750 units. From 3,000 to 4,500 units both of the side's champions die and the enemy survives with 21 to 86 health. From 4,750 the enemy dies after all, 44.5 to 82 s in, because the first fighter has respawned and walked back by then (Inference). |
| The same duel in open lane and under the defender's outer tower. | In open lane the attacker wins with 86 health after 12 s. Under the tower it dies after 2.5 s to three tower shots. |
| A jungler leaves fog toward a laner. | A laner at its own outer tower is never touched, and the jungler dies under the tower. A laner at the enemy outer tower dies whether it decides every 1, 2, or 5 s, with 650 health or with 390. In campaign 2 it survived on 9 health when it decided every second. The ready attack, which now lands at once on a champion, is the change (Inference). |

Two things in these runs come from the rules and would mislead if read as strategy. A tower with no minion in range shoots any enemy champion in range, so a champion that walks under an enemy tower alone dies within seconds. And conclusions about ganks depend on where the wave stands, which section 5 leaves open.

### 8.3 Acceptance criteria of C5

| Criterion (M7 section 10.1, and the owner's requirements) | Result | Test |
| --- | --- | --- |
| Damage is monotone in capability | Never falls with a level or an upgrade, for five profiles | `tests/test_combat.py` |
| An ally's arrival tick equals route length over speed | From 600, 1,500, and 3,000 units the first hit falls on the tick that the arithmetic gives | `tests/test_combat.py` |
| A champion takes champion damage only on ticks when an attacker is within range by the straight line and the target is in the view of the attacker's team | Open lane: hits on 5 of 30 ticks, exactly those in range. Over a wall: hits on exactly the 7 of 12 ticks with an ally's sight. 494 units in a straight line against a walk of 568 is inside a range of 550. | `tests/test_combat.py` |
| A tower's damage on a champion follows the reference aggro and ramp rule to the tick | No shot at 751 units. Multipliers 1.0, 1.5, 2.0, 2.5, 2.5 on consecutive shots. The ramp is kept after 4.5 s without a shot and starts again after 5 s. The tower turns from minions to a champion that damages an ally and back when the call has run out. | `tests/test_combat.py` |
| Permuting the seat order changes no outcome | Five fights, seats exchanged between the teams and inside a team. Equal on every tick. | `tests/test_combat.py` |
| `FIGHT` follows M7 section 7.1 | Pursuit to the last-seen place, `LOST` one tick after arrival, no outcome when the target is seen again first, the same path wherever the hidden target is. A target that steps behind a wall is followed only if the fighter's team sees where it went. | `tests/test_combat.py`, `tests/test_vision.py` |
| A dead champion returns at the fountain after the ruleset's timer | 10 s at level 1 | `tests/test_combat.py`, `tests/test_world_intents.py` |
| One attack capacity across targets | A champion that fights kills no minion in its reach, and on every tick its damage goes to one class. Over switches between minions, a champion, a camp, and idling, the attacks delivered plus the credit kept equal the credit at the start plus attack speed times the time, on every tick. A ready attack lands whole on the first tick against a champion and against a camp. A carry that has just hit a minion deals 70 to a champion on the next tick, and one that idled deals 135. Damage on a champion over 6 s is the same at ticks of 0.25 s and 0.5 s. | `tests/test_combat.py` |
| Simultaneous deaths pay every killer | Two champions that kill each other on one tick get 300 and 400 gold and 42 XP each, and one of them first blood | `tests/test_combat.py` |
| Self-defence and retreat for a returning laner, with the restriction on and off | `FIGHT` against the attacker is legal for 5 s after its last hit, on and off the lane. The return actions stay legal. | `tests/test_combat.py` |
| Leak test | Every field of every enemy that a team does not see is changed. Its observations and masks stay identical for 40 ticks. | `tests/test_combat.py` |

## 9. Vision, memory, and wards (C6)

### 9.1 What exists

`riftgame/vision.py` owns sight, memory, the observation, and its encoding. `remember` is the only function that writes a team's memory, once a tick in step 7 (M7 section 6.2). Ward placement and charges are in `riftgame/champions.py`, and the ward limit in `World.ward`.

| Rule | Built | Status |
| --- | --- | --- |
| Sight sources | A team sees with its living champions (1,350 units), lane minions (1,200), standing towers (1,350), Stealth Wards (900), and shrines (525), by the straight line with clear terrain between (`vision.sources`, `vision.sees`). | M7 section 6.1. Radii Sourced. |
| Sight along a lane | A source on a lane sees that lane's minions, and a lane minion sees places on its own lane, along the lane coordinate as far as its radius (`LaneSim.sighted`, `vision._wave_seen`). Along a lane the straight line is never longer than the lane coordinate, so this never claims sight that the map's measure denies. | Assumed simplification. Its soundness is Tested. It can miss a minion just inside the radius where the lane bends (Reported). |
| Minions and other lanes | A team's minions of one lane reveal no enemy minion of another lane. They reveal enemy champions anywhere by the map's measure. No place on a lane is within minion sight of a camp. | The first is Assumed, because lanes are further apart than a minion sees except inside a base. The last is Tested. |
| Wave memory | Per team and lane a `WaveMemory`: the enemy lead minion that the team last saw, the enemy minions by kind within 1,500 units behind it, and the tick. It freezes out of view. A team that sees the remembered lead's place with no enemy minion in view learns that the wave is gone. | M7 section 6.2. The 1,500 units are Assumed. |
| Observation | Besides the fields of C1 to C5, `enemies` (seen now), `remembered` (last seen, with its age), `rivals` (each enemy's level and death timer, which are public), `lanes`, and `wards` (the team's own). A `LaneView` holds the team's own lead and wave size, the enemy lead and wave size as last seen with their age, contact, the health of the team's towers, and the number of standing enemy towers. Each champion view adds `ward_charges` and `ward_ready_s`. | M7 section 6.3. Enemy tower health is left out. |
| Encoding | `vision.encode` turns an observation into one flat tuple of 358 numbers, unscaled, with -1.0 for a value the team does not have. `observe_team` builds a team's five observations in one pass. | M7 section 10.1, C6 row. The length changes when a field is added. |
| `WARD` | The champion walks until its spot is within 625 units by the straight line, places a Stealth Ward on the spot, and ends with `PLACED`. The 14 spots are the 12 camps and the 2 river nodes. | M7 section 6.4. The spots are Assumed. |
| Charges and limits | 1 charge at 0:00 and at most 2. The recharge falls from 210 s to 90 s and the duration rises from 90 s to 120 s with the average champion level. At most 3 wards per champion, and a fourth removes that champion's oldest. | The ends, the 2 charges, and the 3 wards are Sourced. The start charge, the straight lines between the ends, and the removal of the oldest are Assumed. |
| Enemy wards | A ward cannot be seen or destroyed. An enemy ward is in no observation. | M7 section 6.4. Clearing is M11. |
| Automation on team knowledge | `stance` reads `champions.known_front` in `lane_post` and `economy.lane_inputs`. `FIGHT` pursues by team memory and `vision.watches`. `combat.collect` hits only a target that the team sees. The mask is computed from the observation. | M7 section 6.3 |
| Scripted policies | `farmer`, `jungler`, `brawler`, `roamer`, `random_legal`, and the wave plans read only the observation. None places a ward. | Owner requirement |
| Wards and the role rule | A laner with allowance may ward and is charged as roaming while it is off its lane. A returning laner may not ward. Self-defence, the return actions, and `RECALL` stay legal, and `Config.roam_restricted` turns the restriction off. | Owner requirement. Tested. |

### 9.2 Departures and limits

**One leak is open** (Reported by the independent review, read in `champions._to_enemy`, not fixed). Pursuers move after everyone else. A fighter therefore heads for the new place of a target that has already moved and for the old place of a target that is itself a pursuer. Which one happens depends on the intent kind of a visible enemy, and an intent is in no team's view. In the reviewer's probe two worlds gave the fighter's team equal observations and put the target at the same place, and the fighter ended at 8,287.0 against a target with `MOVE` and at 8,409.5 against one with `FOLLOW`. The difference is one tick of lag. No test catches it, because the leak tests change only enemies that the team does not see. Section 11 keeps the requirement.

Beside that leak and the Assumed rows of section 9.1, five limits stand. A team knows only which enemy towers stand, even while it sees one, so enemy tower health is not in the observation. The last-seen record keeps no enemy upgrades, though M7 section 6.2 lists them (Inference from the `EnemyMemory` fields). The encoding is unscaled, and its layout follows the observation's fields. A direct `World.ward` call between ticks gives combat sight one tick before team memory, which the `WARD` action does not (Reported). The map has no brush and no height, and the wall terrain is the constructed terrain of M7 section 5.1.

### 9.3 What the fog hides, measured

[`experiments/m8/vision.py`](../../experiments/m8/vision.py) runs the comparisons of `tests/test_vision.py` and reports their sizes in [`vision.json`](../../experiments/m8/results/vision.json). The assertions are in the tests.

| Measure | Value |
| --- | --- |
| Hidden-state comparison | 32 worlds: 4 games, both teams, 4 snapshot ticks. Every observation, encoding, and mask is unchanged in 32 of 32. The changes cover 89 living enemy champions, 15 dead ones, 305 minions, 215 camps, and 352 wards. |
| Behaviour comparison | 32 comparisons and 515 compared ticks, from 4 to 60 per comparison. 31 reach a reveal. The compared ticks cover `CAMP`, `FIGHT`, `FOLLOW`, `HOLD`, `LANE`, and `WARD`, and 53 champion ticks in a fight whose target is out of view. |
| Scripted farming and jungling, 5 games of 600 s | Blue sees the enemy jungler on 2.6 percent of ticks [2.0 to 9.8] and red on 1.0 [0.8 to 10.6]. Each enemy laner is seen on 86.8 to 90.3 percent as a median, and each enemy wave on 88.3 to 92.6. No ward is placed. |
| Random legal actions, 5 games of 600 s | Each enemy champion is seen on 22.5 to 50.6 percent of ticks as a median, and each enemy wave on 91.1 to 92.3. A team has 0.301 and 0.273 wards on the map on average. |

### 9.4 Acceptance criteria of C6

The criteria are those of M7 section 10.1 for C6. `tests/test_vision.py` holds 80 tests, and the mutation runner has 35 entries that this file must catch.

| Criterion | Result | Test |
| --- | --- | --- |
| The hidden-state test: change every field hidden from a team, and its observations and masks stay identical | 32 worlds with the encodings identical too. Every field of `Champion` is either changed in a hidden enemy or named with the reason it is not hidden. The other team is told of every change. | `test_changing_every_field_hidden_from_a_team_changes_none_of_its_observations_encodings_or_masks`, `test_the_scramble_changes_every_hidden_field_and_names_the_ones_it_leaves` |
| The behaviour test: under the same change, the team's champions follow identical trajectories until something is revealed | Each champion of the team is equal as a whole `Champion` on every tick before the first exposure. Exposure is decided from the map's sight measure by a check that shares no code with `vision.py`. | `test_a_teams_champions_do_the_same_in_two_worlds_that_differ_only_in_what_is_hidden_from_it`, `test_the_behaviour_comparison_covers_every_automatic_movement_and_enough_ticks` |
| The junction, open-ground, and wall cases hold for champions in a running game | Two arms of a junction see each other. Mid lane and the river see each other over open ground though the walk is longer than sight. A lane and the camp behind the lane wall do not. A champion that walks out from behind the wall is seen from the tick the map gives. A team never sees a place that its sources do not see by the map's measure. | The five sight tests of `tests/test_vision.py` |
| A ranged attack reaches a target behind a wall only while the attacker's team sees it | Damage lands on exactly the ticks on which a ward of the attacker's team stands | `test_a_ranged_attack_reaches_a_target_behind_a_wall_on_exactly_the_ticks_on_which_a_ward_of_the_attackers_team_stands` |
| An enemy Stealth Ward never appears in a team's view | Enemy wards placed anywhere change nothing that the team is told, then or later | `test_enemy_stealth_wards_placed_anywhere_change_nothing_that_a_team_is_told_now_or_later` |
| Last-seen records freeze out of vision | A record keeps place and health while the enemy walks off and heals, and its age grows by the clock. A remembered wave keeps its lead and size out of sight and is forgotten when the team sees its place empty. | `test_a_last_seen_record_keeps_place_and_health_while_the_enemy_walks_off_and_heals_and_its_age_grows_by_the_clock`, `test_a_remembered_wave_keeps_its_lead_and_size_out_of_sight_and_is_forgotten_when_the_team_sees_its_place_empty` |
| A ward reveals and then expires | A ward shows a hidden enemy for exactly its duration at the average champion level. Placement range, recharge, the two charges, and the fourth ward are tested apart. | `test_a_ward_shows_a_hidden_enemy_for_exactly_its_duration_at_the_average_champion_level` and four ward tests |
| Positioning and pursuit read team knowledge (owner requirement, M7 section 6.3) | A laner walks with its own wave wherever an unseen enemy wave is, and takes its stance against the wave once a ward, an ally, or a minion of its team sees it. A wave plan reads its champion's observation and nothing else. | The two stance tests, the wall pursuit test, `test_a_plan_reads_its_champions_observation_and_nothing_else` |

**What the leak tests do not show.** The behaviour test changes only what is hidden by a margin of 1,500 units beyond every sight radius and its slack of 300, so that the comparison lasts. It leaves the enemy's wards and its current memory alone and replays the enemy's actions from the first world, so it never tests what the enemy would do differently. Its thresholds against a vacuous pass, such as at least 450 compared ticks, depend on the trajectories of four scripted games, and a change elsewhere in the kernel can move them (Inference). These three are read from `tests/test_vision.py`. The leak of a stance that reads the true front is caught by the targeted stance tests, not by the behaviour comparison (Reported).

## 10. Assumptions, internal correctness, and real-game validation

**Assumed.** Nothing has checked these against the game.

- Every champion number: the five capability profiles, level growth of 8 percent, the 15 placeholder upgrades, camp damage rates, and the numbers of section 8.
- Lateral slots after the first wave, the hold line 300 units outside tower range, the stand-off of 550 units, and that a champion that stepped aside hits nothing.
- That a cancelled cast starts again and a missile to a dead target is lost. That tower shots and champion hits are instant. A missile on its way to a champion lands even if the champion steps aside.
- That red's minions walk the game's one polyline per lane reversed.
- The roam cap of 90 s and the refill of 0.25, and the end of assignments at 14:00 or with an outer tower.
- The straight-line decay of Homeguard, the leash of 800 units, straight-line camp scaling, and the Scuttler's timer window.
- Sight along a lane by the lane coordinate, the 1,500 units of a remembered wave, the 14 ward spots, the start charge, and the straight lines of ward duration and recharge.
- The jungle paths and the sight terrain of M7 section 5.1, unchanged.

**Internally correct.** A test in this repository shows it, and a mutation run shows that the test can fail.

- The kernel contracts of section 3.3, the lane rules of section 4.1, the ledger, and the criteria of sections 6.3, 7.3, 8.3, and 9.4.
- The port of M7's lane (section 5.1).
- `pytest -q tests` runs 613 kernel tests, and all pass. The whole suite, with the wave tests of `experiments/m8/waves`, gives 713 passed and 7 expected failures: M7's known prototype defect and the six wave bars of section 5.3. The mutation runner breaks the code in 248 ways, and the tests catch all 248.

This is correctness inside the simulator. It says nothing about strategy or the real game.

**Throughput.** One process runs a 600 s game of random legal actions at 543 simulated seconds per wall second [499 to 554, 7 runs], scripted farming at 523 [486 to 536], and scripted farming with jungling at 520 [481 to 532] (`kernel.json`). A run of the same code earlier on the same day gave 586, 561, and 552 (Reported, that file was replaced), so the machine's noise is about 7 percent. Campaign 2 measured 620, 573, and 539, before C6. The first campaign measured 1,183 and 945 for the first two, on a kernel without attack timing, camps, sight, or fights. The lanes take 50.2 percent of a farming game, where they took 53, team memory 19.0 percent, where it took 6.7, and the observation 7.3 percent, where it took 15. Every figure is above M7's gate of 300, which applies at C7. A snapshot at 600 s is 24,650 bytes pickled.

**Validated against the real game.** Nothing. Constants are Sourced, which means read from a document or a data file, not measured. The first real-game validation that M8 needs is still the three measurements of section 5.8. Until wave fidelity is settled, any conclusion that the simulator supports about recall timing, denial, or gank opportunities is provisional, because each depends on where a wave is and how long it stays there.

## 11. Requirements kept for later checkpoints

| For | Requirement |
| --- | --- |
| C7 | The sweep over tick lengths and decision intervals, with the wave results of section 5 in it as distributions over settings, not as every-seed verdicts on single settings (section 5.5). The throughput gate. Pinned replays of an integrated game. |
| C7 | Scripted policies for all ten seats, among them a laner that recalls and a champion that wards. Under `farmer` no laner ever spends its gold, and no scripted policy places a ward. |
| Before C7 | A move order that does not let a fighter's walk depend on its target's intent kind (section 9.2), with a test that changes a visible enemy's intent. Bend pairs in the `bends` sweep, to say why the M8 map holds (section 4.2). The wave runs with the plan on red. |
| C8 | The complete hidden-state hypothesis generator of M7 section 9.3 and its three acceptance tests. Nothing of it exists in `riftgame`. |
| M9 | Champion numbers, armor in `damage`, movement-speed soft caps, and whether purchase thresholds change recall timing. |
| M11 | Wards that can be seen and cleared, Control Wards, and sweeping. |
| Open, C2 | Wave fidelity (section 2). The real-game measurements of section 5.8. The later one-way drift of an untouched top lane. |
| Open, lane | Unit collision in a lane with width. The first wave's indifference to champions and its ghosting, which matter to none of the cases of section 5.4 (section 5.7). The retarget cadence. The caster's acquisition range. Tower shot timing. |
| Open, C5 and C6 | The area damage of `push` outside the attack credit. Sight along a lane by the straight line, and minions that reveal other lanes' minions inside a base. Enemy tower health while a tower is in view. A scaled encoding with a stable layout. Enemy upgrades in the last-seen record. |

## 12. How to rerun the evidence

Every command starts with `.venv/Scripts/python.exe` from the repository root (M7 section 13 has the setup).

| Command | What it shows | What it writes |
| --- | --- | --- |
| `-m pytest -q` | Every test of M7 and M8 | Nothing |
| `-m experiments.m8.waves.capabilities` | Stacking, holding from the first and the third wave, and bouncing through the action table, the diagnostics, and the tick sweep. About 33 minutes on 8 processes. | `experiments/m8/waves/results/capabilities.json` |
| `-m experiments.m8.waves.capabilities --report` | The counts and rows of `capabilities.json` that section 5 quotes. A few seconds. | Nothing |
| `-m experiments.m8.waves.investigate` | The lane without champions: fights, arrivals, attack timing counters, the untouched lanes, the bend sweep, the level lead. About 1 minute. | `experiments/m8/waves/results/investigation.json` |
| `-m experiments.m8.waves.m7_tests` | M7's cases and verdicts on the M8 lane, the port check, M7's tick sweep. About 3 minutes. | `experiments/m8/waves/results/m7_tests_on_m8_lane.json` |
| `-m experiments.m8.waves.incentives` | The incentive screen. About 1 minute. | `experiments/m8/waves/results/incentives.json` |
| `-m experiments.m8.waves.trace "S0 fight 6v6" "m8 lane" 0 0.5 0 100` | A tick-level trace of one M7 case | Nothing |
| `-m experiments.m8.recall` | Round trips from the outer towers | `experiments/m8/results/recall.json` |
| `-m experiments.m8.jungle` | The scripted jungler's first clear and its sweep. About 1 minute. | `experiments/m8/results/jungle.json` |
| `-m experiments.m8.combat` | The fight scenarios of M7 section 5.9 on the M8 kernel | `experiments/m8/results/combat.json` |
| `-m experiments.m8.vision` | The sizes of the two leak comparisons, and how often a team sees each enemy and each enemy wave. Under a minute. | `experiments/m8/results/vision.json` |
| `-m experiments.m8.kernel` | The kernel measurements. Under a minute. | `experiments/m8/results/kernel.json` |
| `-m experiments.m8.mutations` | Breaks the code in a temporary copy and counts the tests that notice | Nothing |
| `-m experiments.m8.provenance` | Whether each of the nine M8 results files still matches the working tree | Nothing |
| `-m experiments.m7.provenance` | The same for M7. All five files stay current. | Nothing |
