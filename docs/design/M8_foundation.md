# M8 foundation

**Status.** Four campaigns have run. Checkpoints C1 (kernel base), C3 (recall and purchases), C4 (jungle), C5 (combat and death), C6 (vision, memory, and wards), and C7 (integrated games) are built and pass the criteria that M7 wrote for them. C2 (lanes and economy) is built and is not complete. Every wave case now runs with the plan on each team, beside two separate controls. Reinforcements accumulate in 3 of 48 settings with the plan on blue and in 1 with it on red, a hold is sustained in 9 of 64 on blue and 7 on red, and on both teams the wave measures move more with the tick length than with the seed (section 2). C8 has not started. Nothing was trained. [Handoff 005](../../handoff/005_m8_c1_c2.md) reports the first campaign, [handoff 006](../../handoff/006_m8_c2_corrections_c3_c5.md) the second, [handoff 007](../../handoff/007_m8_corrections_c6.md) the third, and [handoff 008](../../handoff/008_m8_c7.md) the fourth.

**Date.** 2026-11-13.

**Builds on.** [`M7_architecture.md`](M7_architecture.md). This document does not repeat M7. It names the M7 section that a piece of M8 implements, and it states every place where M8 departs from M7.

**Evidence labels.** The labels are M7's. **Tested** names a test or a script in this repository. **Sourced** comes from the reference patch research. **Assumed** is a design choice or a placeholder number. **Reported** has no evidence in the repository. **Inference** is a conclusion drawn from tested facts. **Unresolved** marks a known limit.

## 1. Summary

- The kernel of M7 section 5 exists as reusable code in `riftgame/`: ten champions on the full map, a fixed tick with a separate decision interval, intents that end with an outcome, the role duty state, an observation boundary, snapshots, replays, and an invariant checker (section 3). Since the third campaign it also has team sight from every source of M7 section 6.1, team memory of camps, enemy champions, and enemy waves, the full observation with a flat encoding, and wards (section 9). Since the fourth, every champion picks where it walks from one state before the move step, and a fighter reads only its team's record of its target (section 3.2).
- One `LaneSim` class runs all three lanes. Every range inside a lane is the straight line on the map, minion attacks have the cast times and missile speeds of the game's data files, and a `LANE` action names what the champion hits and where it stands. The third campaign moved the M8 lane onto a map file of its own, which traces each side-lane corner with the game's four waypoints, after a test showed that one bend off the centre tips an untouched lane. The fourth added a rule that stops a minion at a standing enemy tower, and traced the later drift of an untouched top lane to a difference of 0.010 s in caster missile flight at 70 s (section 4).
- Every wave plan reads its champion's observation and picks entries of the action table in a full world, once with the plan on blue and once on red. Each result stands beside a laner on its fountain, a laner under its tower, and a lane that nobody touches. A plan accumulates reinforcements in 3 of 48 settings on blue and 1 on red, in no setting on both, and in none against an opponent that last-hits. A hold keeps a larger wave out of the tower's range for three wave cycles in 9 of 64 settings on blue and 7 on red from the first wave, and in 3 and 2 of 32 from the third. After a crash the front comes back before an untouched lane's front in 18 of 24 cases on blue and 15 on red (section 5.4).
- C2 is still not complete. No hold plan lasts longer than four wave cycles in every seed on either team. Per case, every wave measure moves more across tick lengths from 0.125 s to 1.0 s than across seeds on both teams, and verdicts flip even between 0.125 s and 0.25 s. Blue's top laner at level 1 from its own tower accumulates against an opponent that last-hits under six of its seven plans at 0.125 s and under none at 0.5 s (section 5.5).
- The acceptance criteria for waves keep the form of campaign 2's second revision and stay provisional. Four strict expected failures keep the unmet bars in view. Two others were dropped, because each asked for a particular result (section 5.3).
- Recall, fountain, purchases, and Homeguard (C3), camps, Scuttlers, shrine sight, and camp timers (C4), and per-tick fights, towers against champions, death, and kill rewards (C5) are built behind the interfaces of M7 section 5.11. One attack credit pays for every class of target. The area damage of `push` and the lockdown are separate abilities that cost mana (sections 6 to 8).
- C6 passes every criterion of M7's C6 row. In 32 worlds, changing everything hidden from a team changes none of its observations, encodings, or masks, and its champions act the same until something is revealed. Changing the private fields of the enemies that a team sees, their intents among them, changes none of its observations and none of its moves. That closes the leak that handoff 007 left open. Team memory now keeps enemy tower health and enemy upgrades (section 9).
- C7 passes every criterion of M7's C7 row. Scripted policies for all ten seats play 50 games of 20 minutes with no invariant error and no fault that a referee finds in the event log. They beat a team of random legal actions on gold plus XP at 15:00 in 50 of 50 seeds on each side. The integrated game runs at 476 simulated seconds per wall second against M7's gate of 300. C7 keeps the starting clock of a 0.5 s tick and a decision every 2 s (section 10).
- Nothing is validated against the real game. Every champion number is a placeholder. Conclusions about recall timing, denial, and gank opportunities are provisional while wave fidelity is open (section 11).

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

**Campaign 4, 2026-11-13.** This campaign corrected what handoff 007 left open, ran every wave case with the plan on each team, and built C7. The decision trail is [`008_m8_c7_decisions.tsv`](../../handoff/008_m8_c7_decisions.tsv), and [handoff 008](../../handoff/008_m8_c7.md) has the detail.

| Phase | Work | Acceptance | State |
| --- | --- | --- | --- |
| S0 Ground | Read the documents, handoff 007, and the kernel. Capture the baseline. | The wave tests at commit `f7e4106`, on a clean worktree, give 20 passed and 6 expected failures (decision trail). | Done |
| S1 Pursuit | Every champion picks its walk from one state before the move step. A fighter reads only its team's record, with a lead of one seen step on a lane. `Rule.pursues`, `vision.watches`, and `World.watches` are deleted. | Changing a visible enemy's intent and its other private fields changes no move of the team, in rings of fights, chains of followers, and with seats exchanged. All 10 pursuit mutations are caught. | Done |
| S2 Memory | Enemy tower health, enemy upgrades, and the place one tick before (`was`) in team memory. Lane caches that a copy, a pickle, or a minion moved by hand cannot leave stale. | The criteria of section 9.4. The invariant checker raises on a stale cache. | Done |
| S3 Abilities | The area damage of `push` costs mana, and living champions regenerate mana. | Attacks, area seconds, mana, and lockdowns stay within their budgets over random switches of intent. | Done |
| S4 Wards | Four ward spots on the river edges. | The action table has 111 entries. A ward order places the ward at the middle of its edge for both teams. | Done |
| S5 Wave experiments | Every stacking, holding, and bounce case with the plan on blue and on red. Tick and decision-interval sweeps per case on both teams. The drift traced. The strict expected failures assessed. | Criteria unchanged in form. Every number of section 5 from the final results files. | Done. C2 stays open. |
| S6 C7 | Scripted policies for ten seats, a referee on the event log, the lane rule `tower_blocks`, the soak, the baseline, tower falls, pinned replays, the sweeps, and the throughput gate. | The C7 criteria of section 10.2. | Done. All pass. |
| S7 Evidence and handoff | Rerun every results file and the mutation runner. Handoff 008. | Every number comes from a current results file or carries the label Reported. | Done |

**What campaign 4 closed from handoff 007.**

- The pursuit leak (007/F14, D6). A fighter's walk no longer depends on its target's intent or on the seat order (section 3.2).
- Enemy tower health in the observation (007/L6, Q5), and enemy upgrades in the last-seen record (007/L11) (section 9.1).
- The free area damage of `push` (007/Q4). It costs mana now (section 8.1).
- The stale lane caches (007/L5). A copy, a pickle, and `LaneSim.invalidate` derive them again, and the invariant checker raises on a stale one (Tested, `tests/test_memory.py`).
- Plans on blue only (007/L10). Every wave case runs on both teams (section 5).
- Ward spots and policies that use them (007/Q3, R1). Four river spots, and C7's scripted policies ward and recall (section 10.1).
- The open question of the bend sweep (007/V1). Pairs of bends, a mirrored map, and symmetric paths were run, and the drift is traced (section 4.2).
- A profile of team memory before the gate (007/R4). It takes 23.5 percent of the integrated game (section 10.4).

**Still open.** Wave fidelity, below. The later one-way drift of an untouched top lane, which is now traced and not removed (section 4.2). The tick sensitivity, which is now measured per case on both teams and in the integrated game (sections 5.5 and 10.3). The first wave's indifference to champions and its ghosting, unit collision, and the real-game measurements of section 5.8. A pursuit with no lead off the lanes and one tick of reaction lag (section 3.2). C8.

**C2 is not complete.** The owner requires freezing, slow pushing, crashing, and bouncing as capabilities, and C2 may not be called complete while one is unresolved. A crash works. The other three are unresolved. Every count below is at a 0.5 s tick, once with the plan on blue and once with it on red. The two runs of a setting differ only in which team the plan plays and so in which side of the map it starts from. The counts are not averaged.

1. **Slow push.** A plan accumulates reinforcements in 3 of 48 settings on blue and 1 on red, and in no setting on both. On blue all three are bot-lane carries at level 3 against an absent opponent. They are the carry alone from first contact (8 minions) and from its own tower (9), and the carry with its support from first contact (8). On red it is mid at level 1 from first contact against an absent opponent, with 10 minions under `thin 3, then passive`. That plan crashes 10 minions there on blue too, but 2 of 5 seeds hold 8 with only 2 from the second wave. No plan accumulates against an opponent that last-hits or from the third wave, on either team. A thinning plan delays the first crash in 43 of 48 settings on blue, 44 on red, and 41 on both. The slow-push drill brings 8 minions on both teams, where a hard push brings 9.
2. **Freeze.** A hold is sustained for three wave cycles from the first wave in 9 of 64 settings on blue and 7 on red, and the same plan sustains on both teams in 4. On blue alone a hold is sustained in the four bot-lane settings with 3 surplus casters. On red alone it is sustained in top at level 3 with 3 surplus casters and in mid at level 3 with 2, both against an opponent that last-hits. From the third wave it is 3 of 32 on blue and 2 on red, the same 2 on both. Some hold plan lasts four cycles in every seed in 1 setting on blue and 3 on red, and none lasts five. From the first wave no plan holds for a level 6 mid laner on either team.
3. **Bounce.** After a crash the front comes back in every run in 23 of 24 cases on each team, and before the untouched lane's front in 18 on blue and 15 on red. The three cases between them are top at level 3, where the untouched top lane drifts toward red's half and so shortens red's comparison (Inference). After a hard push of the first wave mid resets to the centre in 3 of 5 runs on both teams. In top at level 6 no plan beats the untouched lane in every run on either team.
4. **The lane itself.** A verdict that must hold in every seed of one setting can flip with the tick length and with the decision interval, on both teams (section 5.5). An untouched top lane still leaves the centre toward red's half at 247 to 281 s in every seed, and the root is a 0.010 s difference in caster missile flight at 70 s (section 4.2).

## 3. Kernel base (C1)

### 3.1 What exists

| Module | Owns | Checkpoint |
| --- | --- | --- |
| [`world.py`](../../riftgame/world.py) | The state, the eight-step tick of M7 section 5.2, `Config`, snapshots, the digest, the invariant checker, the ward limit per champion | C1, C6 |
| [`champions.py`](../../riftgame/champions.py) | Seats, placeholder capability and progressions, the action table, intents with a rule per kind, the duty state, the fountain's rules, the attack credit (`attack_worth`), the front a team knows (`known_front`), ward charges | C1, C3, C5, C6 |
| [`vision.py`](../../riftgame/vision.py) | `observe`, `observe_team`, `legal_mask`, `encode`, team sight from every source, team memory of camps, enemy champions, enemy waves, and enemy towers | C1, C4, C5, C6 |
| [`harness.py`](../../riftgame/harness.py) | The policy interface, scripted policies that read only the observation, replays. `tick` takes one policy or one per seat. | C1, C4, C5, C7 |
| [`policies.py`](../../riftgame/policies.py) | Scripted policies for all ten seats, built per side, that read only the observation (section 10.1) | C7 |
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
| The action table has 111 entries. A `LANE` action is (lane, mode, stand), with four modes and two stands (section 4.4). Targets are named in the acting team's frame. | M7 said about 95, with five modes. |
| An observation position is a `Place`: a lane with the distance from the team's own end, or one edge off the lanes. The mirror test is exact only for lane positions, bases, and fountains. | The map has no mirror symmetry that keeps roles. |
| The digest covers the state and not the config. | The decision-interval test compares two runs that differ only in the config. |
| `WARD` names one of 18 spots: the 12 camps, the 2 river nodes, and the middle of each of the 4 river edges between a Scuttler node and a side-lane corner or the mid river node (`[vision] river_ward_spots` in `patch_26_22_m8.toml`, section 9). | M7 lists no ward spots. The camp and river nodes are the nodes that the action table already named. They leave no ward that watches the river approach to mid or to a side lane, which the scripted reactions to sightings of C7 need. |
| M8 runs on its own map file, [`map_summoners_rift_m8.toml`](../../riftgame/rulesets/map_summoners_rift_m8.toml), which adds the game's other three waypoints at each side-lane corner. The six added nodes are no `MOVE` targets, so they add no entry to the table. | M7's route graph keeps one waypoint per corner, and that tips an untouched lane (section 4.2). M7's map file stays byte-identical for M7's results. |
| Every champion picks where it walks from the state at the start of the move step, and then all move at once. A fighter reads only its team's record of its target, never where the target is now or what it intends. If the team sees the target now and saw it the tick before, the target's last step took it farther from the fighter, and both places are on one lane, the fighter heads for its attack range short of where one more such step puts the target, by the lane coordinate and clipped to the lane. Otherwise it closes to its range of the place where its team saw the target. Off the lanes there is no lead. A fighter therefore answers a visible target that turns to flee one tick late. This replaces the order of M7 section 5.2, step 3, in which champions that do not pursue move first and pursuers after. | M7's order lets a fighter's walk depend on whether its target pursues, and an intent is private (handoff 007, F14). With one state no walk reads another champion's move on the tick, so neither the seat order nor an enemy's intent changes where anyone goes (Tested, `tests/test_pursuit.py`). On a lane without a lead, a target that walks away is never hit by a chaser of any speed, because the gap after both moves is the range plus the target's step. On the jungle paths the walk is 1.15 times the straight length and range is the straight line, so a faster melee fighter keeps a target whose step is up to 201 units without a lead (Tested, `tests/test_combat.py`). Edges inside a base have no detour, and there a target that walks away stays away from a faster melee fighter (Reported by the independent review, from `map.py`). |

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
| The invariants | Each one is broken on purpose and the checker raises. C3 adds gold equal to the ledger less the price of the upgrades. C4 adds the camp faults. C6 adds the ward charges and at most three wards per champion, and no test breaks those two on purpose. Campaign 4 adds a lane cache or a minion's map coordinates that disagree with the minions' lane coordinates (`LaneSim.stale`), and two tests break them on purpose. | `tests/test_world_soak.py`, `tests/test_recall.py`, `tests/test_jungle.py`, `tests/test_memory.py` |
| Leak test for the observation boundary | Every field of every enemy champion is changed, and so are the minions and towers of every lane and every camp fact that the team has not seen. The team's five observations and masks stay identical. C6 extends the test to every hidden field (section 9.4). | `tests/test_world_observation.py`, `tests/test_economy.py` |
| A replay reproduces its digests, and one digest is pinned | 600 of 600. The pin moves with every change to the state, so it moved in every campaign. | `tests/test_world_snapshot.py` |

**Measured, not criteria.** `kernel.json` holds the throughput of one process over 600 s games, and section 11 gives the figures. M7's gate of 300 simulated seconds per wall second is measured on the integrated game in section 10.4.

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
| Three tower tiers. Every standing tower of a lane shoots minions and champions in its range. Only the front tower takes damage, because minions march to, target, and hit only the enemy front tower, and `SIEGE` hits only it. | Yes. Campaigns 1 to 3 wrote here that only the front tower fights. The code reads otherwise (`LaneSim.step`, `_tower_attack`, `front_tower`, and `_siege_blow`), and the C7 referee checks every standing tower. | Sourced |
| A wave past the last lane tower is removed at the enemy base | Yes | Assumed stand-in until M10 |
| Champions that attack at the same instant are served in an order drawn by key, not by seat | Yes | Assumed |
| `straight_ranges`: every range inside the lane is the straight line on the map. Marching stays on the lane coordinate. | Yes, new in campaign 2 | Owner requirement, and the interaction measure of M7 section 5.1 |
| `tower_shelter`: a champion inside the range of a standing lane tower is not attacked for standing in the minions' path | Yes, new in campaign 2 | Sourced. That any standing lane tower counts is Assumed. |
| `first_wave_call`: minions of the first wave answer a call for help while they attack a tower | Yes, new in campaign 2 | Sourced |
| `attack_timing`: a blow leaves the minion one cast time after the attack starts, and a caster's or a siege minion's blow then flies to its target | Yes, new in campaign 2 | Sourced constants (section 4.2). The cancel and the lost missile are Assumed. |
| `m7_map`: the lane runs on M7's route graph, which traces each side-lane corner with one of the game's four waypoints | No. `M7_LANE` turns it on. New in campaign 3. | The M8 map's waypoints are Sourced (section 4.2). |
| `tower_blocks`: a minion never marches past the enemy front tower while it stands, whatever it walks to | Yes, new in campaign 4. Off in `M7_LANE`, so the port check is unchanged. Without it a minion that chased an enemy minion or a champion behind the tower walked up to 65 units past it, which the C7 referee found (Reported, decision trail). | The movement rule of M7's C7 row (Tested, `test_a_minion_that_chases_an_enemy_minion_behind_the_enemy_front_tower_stops_at_the_tower_while_it_stands`) |
| `melee_cap`: at most n melee minions on one target | Diagnostic, off | Section 5.5 |
| `minion_damage_scale`: scales minion blows on minions | Diagnostic, off | Section 5.5 |
| `free_cancel` and `missiles_turn`: a cancelled cast costs nothing, and a missile to a dead target lands on what its shooter can reach | Diagnostics, off | Section 5.5 |
| `detour_s`: a melee minion that turns to a new minion target loses this long before its cast | Diagnostic, off | Section 5.6 |

The docstring of `LaneSim.front_tower` still says that the front tower is the only one that can fight. Provenance hashes the raw source, so fixing that line alone would mark every results file stale for numbers that stay bit-identical. It changes with the next kernel change (section 12).

The added constants live in a second ruleset file, [`patch_26_22_m8.toml`](../../riftgame/rulesets/patch_26_22_m8.toml), and the M8 map in `map_summoners_rift_m8.toml`. `patch_26_22.toml`, `map_summoners_rift.toml`, `map.py`, `ruleset.py`, and `rng.py` stay byte-identical, because M7's results files record their hashes.

### 4.2 The rules that campaigns 2 and 3 added, the drift, and what the sources say

**Straight-line ranges.** M7 section 5.1 measures movement by the route and interaction by the straight line. Campaign 1 left every range inside a lane on the lane coordinate. On M7's route graph, two points 290 units either side of the top-lane corner are 580 units apart along the lane and 534 in a straight line. Campaign 2 first changed only the ranges between champions or towers and minions. That made things worse. A passive carry in bot lane took 568 damage in five minutes where it had taken 44, because a caster behind the corner counted enemy minions along the lane, found none in range, and turned on the champion that it measured by the straight line (Reported, a scratch run of campaign 2). One measure for every interaction removes the inconsistency. Acquisition, attack, tower, and call ranges all use the map coordinates of the two units. Only marching uses the lane coordinate (Tested, `tests/test_lanes.py`, two corner tests). The hold line, the stand-off, and the experiments' band and tower checks are still placed along the lane. Towers stand on straight stretches, so that differs from the straight line by 16 units at most (Reported by the review of campaign 2, on M7's graph).

**The corner, tested and replaced.** With straight-line ranges on M7's graph, an untouched top lane went to blue's half within 100 s in every seed. Handoff 006 put that down to the graph's one sharp corner node, from one comparison. Campaign 3 tested the diagnosis on top lane's length, towers, and spawn points with other shapes, over 12 seeds of 600 s (Tested, `investigate.py` section `bends`, and `test_a_bend_tips_an_untouched_lane_toward_its_own_side_and_a_bend_at_the_centre_or_no_bend_does_not`). With no bend, or one bend at the centre, the front never leaves the centre. One bend of 46 degrees 150 or 295 units off the centre tips the lane toward the bend's side at 97 s in every seed, and the mirrored bend tips it the other way. A bend of 10 or 20 degrees does the same as one of 46, and one of 5 degrees does not. So the cause is a bend off the centre inside the first fight, not its sharpness. Section 5.4 has the table.

**Why a bend tips the lane** (Reported, one scratch trace recorded in the decision trail). With straight-line ranges a caster across the bend acquires its target one tick earlier and stops 1.2 units short of where it stops on a straight lane. On a straight lane later retargets sit exactly on a range threshold. Across the bend they fall outside it, the minion waits a tick before it walks, and the symmetric fight is no longer a draw. A rule that let a minion acquire a target on arrival inside the tick was tried and removed. It left the drift at 97 s in 12 of 12 seeds on M7's graph and changed the first-wave fight by under 0.5 s at four tick lengths (Reported).

**The M8 map.** `map_summoners_rift_m8.toml` is M7's map file with the game's other three waypoints at each side-lane corner (reference rows A4b and A4c). M7's graph kept one of four, which made one bend of 46 degrees 295 units from where the waves meet and cut 98 units off top lane and 109 off bot (the map file's header). On the M8 map no bend of top lane between the outer towers turns more than about 21 degrees, and the bends nearest the centre are 319 units on blue's side and 669 on red's (`investigation.json`, `bends`). The added points are not collinear, so they change the lane's length and shape. Marching and champion walks use the route, and every range uses the straight line. `LaneRules.m7_map` keeps `M7_LANE` on M7's graph, so the port check still gives 998 of 998 (section 5.1).

With the M8 map an untouched lane keeps its front within 100 units of the centre for the first 150 s in all three lanes and every seed (Tested, `test_an_untouched_lane_keeps_its_front_at_the_centre_for_the_first_150_seconds`). Over 12 seeds of 600 s an untouched top lane first leaves the centre at 281 s (median, 247 to 281), where it left at 97 s on M7's graph, and it has 18 crashes where it had 63. The later drift goes toward red's half in every seed. Campaign 3 put that down to a lane with no noise and an M8 polyline that is not symmetric about the centre. The fourth campaign tested it.

**What starts the drift, and what delays it** (Tested, `investigation.json`, `drift` and `bends`, 12 seeds of 600 s). In all 12 seeds an untouched top lane on the M8 map first differs from its mirror image at 70.0 s, in the time at which a melee minion of wave 1 is ready to attack. On the tick before, blue's casters stand 493.5 units from their targets by the straight line and red's 500.0, so blue's missiles fly 0.759 s and red's 0.769 s. The bend of 21 degrees 319 units on blue's side of the centre puts the difference there (Inference). On the M8 map mirrored about the lane's centre the two sides swap these numbers, the first difference also falls at 70.0 s, and the lane drifts to blue's half instead, at 281 s in 11 seeds and 247 s in one. With paths symmetric about the centre, where red walks the mirror of blue's polyline and spawns and keeps its towers where the mirror puts blue's, the front leaves the centre in only 2 of 12 seeds, at 157.5 s and 429 s.

The map's bends do not cancel each other. Its bend at 319 units alone, its two nearest bends, its four bends within 2,000 units of the centre, and all its bends on M7's length each tip the lane at 97 s in 12 of 12 seeds, as one bend of 46 degrees does. Two equal bends placed symmetrically about the centre never tip it. What delays the drift on the M8 map is where the waves meet. The M8 polyline makes each wave's walk to the centre 49.4 units longer than on M7's graph. With both spawn points moved 49.4 units nearer the centre, so that the walk is M7's, the M8 map tips at 97 s in 12 of 12 seeds. M7's graph with spawn points 49.4 units further out first tips at 133 s. Spawn shifts of 10 to 100 units move the median first departure anywhere from 97 s to none within 600 s, and the tick moves it to 145 s at 0.125 s, 250.5 s at 0.25 s, and 191 s at 1.0 s. So the M8 map moves the meeting and does not remove the asymmetry, and a lane this near balance turns a hundredth of a second into a one-way drift (Inference). On the owner's instruction no symmetry was forced and no noise was added. The game's file has one polyline per lane, linked from the blue barracks. That red's minions walk it reversed is Assumed.

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
| The tick sweep of risk RK2 is reported | 9 of 17 of M7's metrics within 10 percent at 0.5 s, and the world-driven verdicts and measures per case at ticks of 0.125, 0.25, 0.5, and 1.0 s on both teams | Sections 5.5 and 5.9 |

## 5. Wave behaviour through the action table

Every number in this section is at a 0.5 s tick over 5 seeds unless it says otherwise. Since campaign 4 every stacking, holding, and bounce case runs twice, with the plan on blue and with the plan on red, and the two are reported apart. A range in brackets is the minimum and maximum across seeds. The results files are in [`experiments/m8/waves/results/`](../../experiments/m8/waves/results/). `python -m experiments.m8.waves.capabilities --report` prints the counts of `capabilities.json` that this section quotes.

### 5.1 The port still reproduces M7

[`m7_tests.py`](../../experiments/m8/waves/m7_tests.py) runs M7's 103 wave cases on the lane. With `M7_LANE`, which runs on M7's route graph, and M7's draw key, 998 of 998 metrics equal M7's results file (Tested, `port_check_with_m7_draw_key`). In campaign 2 a separate check stepped the lane under M7's rules beside the lane of the commit before for 600 s on 3 seeds, and every minion's position and health agreed on every tick (Reported, that script is not kept).

### 5.2 How the experiments run now

[`agents.py`](../../experiments/m8/waves/agents.py) stages a full world of ten champions, and every champion starts on its fountain. A `Laner` puts the lane's champion of each team at its outer tower at a chosen level, the same on both teams, so that no team leads in level. The plan plays one team's laner and the opponent setting plays the other's. A plan is a function from what the laner's observation holds to a `LANE` action, called on decision ticks every 2 s. It reads the champion's own health and caster kills, and its lane as the team sees it: the team's minions within 1,500 units behind its lead, the enemy minions near the enemy lead while the team sees one, and whether the waves are in contact. The world does the rest: the walk, the stance, the hits, minion damage, death.

With the plan on blue the team does not see the enemy lead minion on a median of 6.7 percent of ticks in the stacking cases, 6.0 percent in holding from the first wave, and 6.2 percent from the third, and the largest share in one case is 59.5 percent. With the plan on red the shares are 6.7, 6.2, and 6.4 percent, and the largest is 62.6. Below 30 percent health a laner walks to its own outer tower with a `MOVE` and comes back above 60 percent. The staging sets a champion's level, place, and the clock at the start, and the holding cases add the surplus casters during the run. Nothing else is edited in a run.

**Two controls.** `absent` is a laner on its fountain. Its plan word `leave` is a `MOVE` to `own_fountain`. `under tower` is a laner that stands at its own outer tower and does nothing. There it gains XP, which feeds its team's level and so the pushing advantage from 3:30, and it may be hit. In campaign 2 `absent` stood at the tower, so it was the under-tower control under another name. The two now differ in XP in every seed of the test setting (Tested, `test_a_champion_under_its_tower_gains_xp_and_an_absent_one_gains_none_after_it_left`). In the wave counts they give the same held cycles in all 96 holding settings on both teams. Their largest crashes differ in some seed in 7 of 48 stacking settings on blue and 11 on red. Both stand beside every plan in stacking and holding. The untouched lane beside each bounce case has nobody near it.

The champions are the profiles of `riftgame.champions`, which are placeholders. A level goes with a clock: level 1 from 0:00, level 3 from 2:30, level 6 from 6:00. The lanes start empty at that clock, so the minions have that time's stats and siege waves.

| Champion setting | Lane |
| --- | --- |
| Top at level 1, 3, and 6 | top |
| Mid at level 1, 3, and 6 | mid |
| Carry alone at level 3, and carry with a support that stands with it and hits nothing | bot |

**Later waves.** The first wave has rules of its own (section 5.7), so each experiment also starts later. Stacking starts at the meeting of the third waves, after both laners last-hit the first two. Holding places 3 or 4 surplus casters when the laner's third wave reaches the edge of its tower's range. A bounce follows a hard push after two last-hit waves.

**What a row reports.** Per setting and plan, `capabilities.json` holds every seed's value beside the median, the minimum, and the maximum. It reports durations (`kept_out_s`, `first_crash_s`, `largest_crash_s`) and costs (`minion_gold`, `xp`, `minion_damage_taken`, `champion_lowest_health`, `champion_retreats`, and the damage to the laner's own tower). Under `paired` it compares each plan with each control seed by seed: the median, minimum, and maximum of the plan's value less the control's, and the number of seeds in which the plan's is higher. Under `between_sides` it holds, per setting, plan, and metric, blue's value less red's in the same seed. `sides` holds the count of each verdict per team and on both. The file is about 17 MB.

Campaign 1's scripted champion had 30 armor, a pushing area damage of 70 per second, and an opponent that could not die and jumped to its spot. None of that is left in the experiments about champions. M7's own cases keep it, because they are the port check.

### 5.3 Revised criteria, and the evidence against the old ones

The owner asked for criteria that keep the meaning of each capability: sustained wave control, reinforcement accumulation, delayed crashes, and bounce. A first revision in campaign 2 was too loose, and the independent review showed where (handoff 006, §3.5). The criteria below are the second revision. Campaigns 3 and 4 kept their form and every threshold, and they stay provisional. Campaign 3 changed only the lists of controls, because the old `absent` was not absent (section 5.2). Campaign 4 changed nothing in them and applies each to both teams apart. Each criterion compares a plan with a lane that nobody touches, because an untouched lane does not stand still (section 5.4).

| Capability | Old criterion | What is wrong with it | Criterion now |
| --- | --- | --- | --- |
| Crash | A hard push reaches the tower before the second enemy wave can. | Nothing. | Kept. |
| Delayed crash | A thinning plan reaches the tower later than a push, with 12 minions. | Two properties in one verdict. | Its own verdict: a thinning plan's first crash comes later than the push's in every seed. This is a weak property, since thinning is slower than pushing by construction. |
| Reinforcement accumulation | 12 or more minions near the lead at the first tick in tower range. | Twelve is two full waves of six. A wave with a siege minion has seven, a thinned wave has lost some of its own, and a crash can hold parts of three waves. A bar of exactly 12 calls a crash of 11 minions from three waves no stack. | In every seed the plan's largest crash holds, at its largest moment, at least three minions from each of two spawn waves, and more minions than the largest crash of a hard push, of a laner on its fountain, and of a laner under its tower in the same setting. The count of 12 is reported beside it. |
| Sustained wave control | The front stays within 1,500 units outside the tower's range for over half of 240 s, and both controls stay below half. | The band does not measure a hold. With no champion the front was in the band for 214 s of 240 against a last-hitting opponent in mid, while the enemy wave reached the tower in every cycle and dealt 445 damage to it. The control clause also blocked the test at three of five surplus sizes (handoff 005, F9). | A wave cycle of 30 s is held when the front is in the band for at least half of it and the enemy wave is never in the tower's range during it. A hold plan sustains control when, in every seed, the champion does not die, the first three cycles are held, and that is more cycles than a laner on its fountain, a laner under its tower, a laner that last-hits with its wave, or a laner that pushes holds in any seed. |
| Bounce | After a hard push of one wave, the contact point is back past the centre within 120 s, in every run, in mid and top. | One wave of six is the weakest crash. A lane that meets again exactly at the centre counted as not bounced without being named. And an untouched lane can drift to one side by itself, so a return proves nothing about the crash unless it beats that lane. | After a crash, the front comes back more than 100 units past the centre in every run, and in every run before the front of the same lane with no laner gets there. The crash is tried with one hard-pushed wave, with a thinned wave, and with a hard push after two last-hit waves. A lane that meets again within 100 units of the centre is called a reset. |

**What these criteria still choose.** Three cycles is 90 s, where M7's test asked for more than half of 240 s. No counterexample supports that cut. It is where the results have something to show. Some hold lasts one, two, three, and four cycles in every seed in 52, 39, 12, and 1 of 64 settings on blue and in 52, 38, 10, and 3 on red, and none lasts longer. Three minions per wave and 100 units are choices too. All are named constants in [`capabilities.py`](../../experiments/m8/waves/capabilities.py).

**Expected failures.** Four strict expected failures in [`test_behaviours.py`](../../experiments/m8/waves/test_behaviours.py) keep the unmet bars in view. Each asserts one of the bars below and fails, and the suite reports it if it starts to pass. Each bar is a strategic requirement of the owner, freezing or slow pushing, or a direct test of M7.

1. The slow-push drill of a level 1 top laner brings more minions than a hard push in every seed.
2. Some plan accumulates reinforcements in every seed against an opponent that last-hits.
3. A hold lasts all eight wave cycles of the 240 s run, as M7's freeze test asks.
4. A plan holds a first wave of 6:00 for a level 6 mid laner.

Campaign 3 had six. Campaign 4 dropped two as requirements that ask for a particular result. "12 minions at the enemy tower" repeated the bar that this section replaced by three minions from each of two waves, and the count stays reported. "A mid bounce after a hard push of the first wave" would force one particular crash to bounce, where the lane resets by symmetric waves (section 5.4), and the owner asked that no criterion force every crash to bounce. Campaign 2 had eight, and two of those pass as plain tests since campaign 3.

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
| One bend of 46 degrees, 295 or 150 units on blue's side | 12 and 0 | 97 s | 25 and 38, 34 and 40 |
| One bend of 46 degrees, 150 or 295 units on red's side | 0 and 12 | 97 s | 39 and 35, 38 and 25 |
| One bend of 10 or 20 degrees, 295 units on blue's side | 12 and 0 | 97 s | 33 and 37, 31 and 38 |
| M7's route graph | 12 and 0 | 97 s | 25 and 38 |
| The M8 map, and with ranges along the lane | 0 and 12, 1 and 0 | 281 s [247 to 281], 430 s in 1 seed | 4 and 14, 0 and 0 |
| The M8 map's bend 319 units on blue's side alone, its two nearest bends, its four bends within 2,000 units, or all its bends on M7's length | 12 and 0 | 97 s | 30 and 38, 30 and 37, 34 and 36, 34 and 36 |
| The same two or four bends mirrored | 0 and 12 | 97 s | 38 and 31, 35 and 30 |
| The M8 map's bend 669 units on red's side alone, or two equal bends placed symmetrically at 319 or 669 units | 0 and 0 | Never | 0 and 0 in each |
| The M8 map mirrored about the lane's centre | 12 and 0 | 281 s [247 to 281] | 16 and 7 |
| Paths symmetric about the centre, with spawn points and towers mirrored too | 1 and 1 | 157.5 s and 429 s, in 2 seeds | 13 and 5 |
| The M8 map with both spawn points 49.4 units nearer the centre, and M7's graph with them 49.4 units further out | 12 and 0, 12 and 0 | 97 s, 133 s | 21 and 48, 34 and 29 |
| Mid on the M8 map, for comparison | 3 and 4 | 243 s, in 7 seeds | 16 and 9 |
| Bot on the M8 map, and on M7's route graph | 1 and 3, 3 and 4 | 158 s in 4 seeds, 224.5 s in 7 | 11 and 10, 9 and 16 |

M7's graph gives exactly the numbers of one bend of 46 degrees 295 units on blue's side. The M8 map delays the first departure of top lane from 97 s to 247 to 281 s and cuts its crashes from 63 to 18, against 25 in mid, which has no corner. Section 4.2 reads the rows that campaign 4 added.

**Accumulation and delay** (`capabilities.json`, `stacking`). Seven plans, a hard push, a laner on its fountain, and a laner under its tower. Three starts (first contact, the moment an enemy push reaches the laner's tower, and the meeting of the third waves), an opponent that is absent or last-hits, 8 champion settings: 48 settings in all, on each team.

| Result | Plan on blue | Plan on red |
| --- | --- | --- |
| Settings in which some plan accumulates reinforcements | 3 of 48. By start, 2 of 16 from first contact, 1 of 16 from the own tower, and 0 of 16 from the third wave. None of the 24 against an opponent that last-hits. | 1 of 48. By start, 1, 0, and 0 of 16. None against an opponent that last-hits. No setting accumulates on both teams. |
| From the own tower | Carry alone, level 3, opponent absent. Four thinning plans accumulate. `thin 2, then last hit` brings 9 minions [9 to 9], three of them from the second-largest wave in the crash, 45.5 s after the plan starts. The hard push brings 5, and a laner on its fountain and a laner under its tower 6 each. The plan's crash is the larger against each of the three in 5 of 5 seeds. | None. `thin 3, then passive` crashes 10 minions as a median for top at level 1 against an absent opponent, at 78 s. It does not count, because in one seed it is no larger than the crash of a laner on its fountain. |
| From first contact | The carry alone and the carry with its support, level 3, opponent absent. `thin 3, then passive` brings 8 [8 to 8] in both, three from the second-largest wave, at 174 s [172 to 175] and at 171.5 s [171.5 to 171.5]. The hard push brings 5 at 18 s. With the laner on its fountain or under its tower no wave reaches the tower. | Mid, level 1, opponent absent. `thin 3, then passive` brings 10 [9 to 10], three from the second-largest wave in every seed, at 187 s. The hard push brings 5 at 11.5 s. With the laner on its fountain or under its tower no wave reaches the tower. |
| Largest crash | 10 minions as a median, in that mid setting under `thin 3, then passive`. It does not count on blue, because in 2 of 5 seeds the crash holds 8 with 2 from the second-largest wave. With no laner the largest crash holds 8. No crash holds 12. | 10, in that mid setting, where it counts, and in the top setting above. With no laner the largest crash holds 8. No crash holds 12. |
| The slow-push drill: top, level 1, from first contact, kill 3 casters, then last-hit | 8 minions of two waves, six and two, 38.5 s after contact. The hard push there crashes first with 5 at 18 s and brings 9 of two waves at 30 s. The drill does not accumulate. | 8 of two waves, six and two, at 39 s. The hard push crashes 5 at 18.5 s and 9 at 30 s. |
| Settings in which some thinning plan delays the first crash | 43 of 48: 16, 15, and 12 of 16 by start | 44 of 48: 16, 16, and 12. 41 delay on both teams. Only red delays in top at level 1 from its own tower against an opponent that last-hits and in two top settings from the third wave. Only blue delays in two other top settings from the third wave. |
| Paired with a hard push, the largest crash of a plan in the same seed | Larger in every seed in 39 of 288 pairs of a setting and a plan, smaller in every seed in 119 | 39 and 111 |

**Holding from the first wave** (`capabilities.json`, `holding`). The experiment places 2, 3, 4, or 6 surplus enemy casters at the hold line when the laner's wave arrives, and the opponent is absent or last-hits: 64 settings on each team, 7 hold plans and 4 controls each, 240 s.

| Result | Plan on blue | Plan on red |
| --- | --- | --- |
| Settings in which some hold plan sustains control | 9 of 64 | 7 of 64. The same plan sustains on both teams in 4. |
| By champion setting, of 8 each | Top 1, 1, 0 at levels 1, 3, 6. Mid 2, 1, 0. Carry alone 2. Carry and support 2. | Top 1, 2, 0. Mid 2, 2, 0. Carry alone 0. Carry and support 0. |
| Settings in which some hold lasts at least 1, 2, 3, 4 cycles in every seed | 52, 39, 12, 1. None lasts 5. | 52, 38, 10, 3. None lasts 5. On both teams, 51, 34, 6, and 0. |
| With a laner on its fountain, and with one under its tower | The same in every setting. 0 cycles in 45 settings, 1 in 7, 2 to 6 in 12. | The same in every setting. 0 in 46, 1 in 8, 2 or 3 in 10. |
| With a laner that last-hits with its wave | 0 cycles in 38 settings, 1 in 9, 2 to 5 in 17 | 0 in 39, 1 in 7, 2 to 4 in 17. In one setting, mid at level 6 against 2 surplus casters and an opponent that last-hits, this control keeps the wave out for all eight cycles. |
| With a laner that pushes | 0 cycles in 2 settings, 1 in 56, 2 in 6 | 0 in 4, 1 in 57, 2 in 3 |
| Longest hold by a hold plan | Four cycles, by `hold, thin over 1` for mid at level 1 against 3 surplus casters and no opponent. No retreat, lowest health 52 percent, and the wave kept out for all 240 s. No control holds more than 1 cycle there. | Four cycles, in 3 settings. It sustains control in one, by `hold, thin over 1` for mid at level 1 against 2 surplus casters and an opponent that last-hits, with one retreat in some seed, lowest health 26 percent, and the wave kept out for at least 177 s. In the other two a control holds as long or longer. |
| Sustaining plans | In 7 of the 9 settings only plans that thin or trim while they hold sustain control. `hold, last hit` sustains in 2, both bot-lane carries at level 3 against 3 surplus casters and no opponent, where a laner that last-hits with its wave holds 2 cycles. | Only `hold, thin over 1`, in all 7 |
| What a hold costs | In 4 of the 9 settings every sustaining plan retreats once in some seed, and its lowest health falls to 17 to 28 percent. | In 4 of the 7, with lowest health 21 to 27 percent. In the other 3 there is no retreat, and lowest health is 46 to 52 percent. |
| Paired with a laner on its fountain, the time a plan keeps the wave out in the same seed | Longer in every seed in 428 of 448 pairs of a setting and a plan, shorter in every seed in 2 | 438 and 0 |
| Paired with a laner that pushes, the held cycles | More in every seed in 124 of 448, fewer in every seed in 100 | 124 and 67 |

**Holding from the third wave** (`capabilities.json`, `holding_from_the_third_wave`). With 3 or 4 surplus casters over 32 settings, a hold plan sustains control in 3 on blue and 2 on red, and the same plan sustains on both teams in 2. Some hold lasts at least 1, 2, 3, 4 cycles in every seed in 28, 17, 3, and 0 settings on blue and in 29, 18, 2, and 1 on red. In mid at level 3 against 3 surplus casters and an opponent that last-hits, `hold, thin` sustains control on both teams, with no retreat and the wave kept out for all 240 s. With the carry alone at level 3 against 4 surplus casters and an opponent that last-hits, four plans sustain control on both teams, `hold, last hit` among them. Each retreats once in some seed and keeps the wave out for at least 202 s on blue and 201 s on red, and on red they hold four cycles with health as low as 10 percent. On blue alone, `hold, thin over 3` sustains control for mid at level 6 against 3 surplus casters and no opponent, which no first-wave hold does. A laner on its fountain or under its tower holds 0 cycles in 28 of the 32 settings on blue and 30 on red.

**Bounce** (`capabilities.json`, `bounce`). A laner follows a plan from first contact until its wave is in the enemy tower's range, then walks to its fountain. Each cell gives the median seconds from the crash until the front is back more than 100 units past the centre and the runs in which it is, then the same for the untouched lane, then whether the case counts. The first table has the plan on blue.

| Champion setting, plan on blue | Hard push | `thin 3, then last hit` | Last hit two waves, then hard push |
| --- | --- | --- | --- |
| Top, level 1 | 91.5 s in 5 of 5. Untouched 318 s in 5. Counts. | 70 s in 5. Untouched 297.5 s in 5. Counts. | 62.5 s in 5. Untouched 289 s in 5. Counts. |
| Top, level 3 | 53 s in 5. Untouched 204 s in 5. Counts. | 48.5 s in 5. Untouched 200 s in 5. Counts. | 95 s in 5. Untouched 169 s in 5. Counts. |
| Top, level 6 | 109 s in 5. Untouched 124 s in 5, first in 2 runs. No. | 42.5 s in 5. Untouched 102 s in 5, first in 2 runs. No. | 52.5 s in 5. Untouched 68 s in 5, first in 2 runs. No. |
| Mid, level 1 | 268 s in 2 of 5, on the same tick as the untouched lane. The other 3 reset. No. | 61 s in 5. Untouched 254.5 s in 2. Counts. | 62.5 s in 5. Untouched 229 s in 2. Counts. |
| Mid, level 3 | 149.5 s in 5, on the same tick as the untouched lane in every run. No. | 47.5 s in 5. Untouched 138 s in 5. Counts. | 82.5 s in 5. Untouched 105.5 s in 5, first in 2 runs. No. |
| Mid, level 6 | 46.5 s in 5. Untouched never. Counts. | 34 s in 5. Untouched never. Counts. | 39.5 s in 5. Untouched never. Counts. |
| Carry alone, level 3 | 53.5 s in 5. Untouched never. Counts. | 48.5 s in 5. Untouched never. Counts. | 166.5 s in 5. Untouched never. Counts. |
| Carry and support, level 3 | 53.5 s in 5. Untouched never. Counts. | 48.5 s in 5. Untouched never. Counts. | 107.5 s in 5. Untouched never. Counts. |

| Champion setting, plan on red | Hard push | `thin 3, then last hit` | Last hit two waves, then hard push |
| --- | --- | --- | --- |
| Top, level 1 | 90.5 s in 5 of 5. Untouched 200.5 s in 5. Counts. | 69.5 s in 5. Untouched 180 s in 5. Counts. | 62 s in 5. Untouched 171.5 s in 5. Counts. |
| Top, level 3 | 53.5 s in 5. Untouched 87 s in 5, on the same tick in 1 run. No. | 49 s in 5. Untouched 83 s in 5, on the same tick in 1 run. No. | 65 s in 5. Untouched 52.5 s in 5, first in 4 runs. No. |
| Top, level 6 | 124 s in 5. Untouched 107.5 s in 5, first in 4 runs. No. | 43 s in 5. Untouched 83.5 s in 5, first in 2 runs. No. | 52.5 s in 5. Untouched 52 s in 5, first in 3 runs and on the same tick in 1. No. |
| Mid, level 1 | 179.5 s in 2 of 5, on the same tick as the untouched lane. The other 3 reset. No. | 61 s in 5. Untouched 166 s in 2. Counts. | 65 s in 5. Untouched 142 s in 2. Counts. |
| Mid, level 3 | 62 s in 5, on the same tick as the untouched lane in every run. No. | 48 s in 5. Untouched 50.5 s in 5. Counts. | 63.5 s in 5. Untouched 18.5 s in 5, first in 3 runs. No. |
| Mid, level 6 | 46.5 s in 5. Untouched never. Counts. | 34 s in 5. Untouched never. Counts. | 40 s in 5. Untouched never. Counts. |
| Carry alone, level 3 | 53 s in 5. Untouched never. Counts. | 48.5 s in 5. Untouched never. Counts. | 60.5 s in 5. Untouched never. Counts. |
| Carry and support, level 3 | 53 s in 5. Untouched never. Counts. | 48.5 s in 5. Untouched never. Counts. | 171 s in 5. Untouched never. Counts. |

The front comes back in every run in 23 of 24 cases on each team, and before the untouched lane's front in every run in 18 on blue and 15 on red. The difference is top at level 3. There every plan on blue beats the untouched lane by at least 60 s in every run. With the plan on red the untouched lane gets there after a median of 52.5 to 87 s, before the plan's front or on the same tick in some run. The untouched top lane drifts toward red's half, which shortens red's comparison (Inference). In top at level 1 every plan beats the untouched lane on both teams, by at least 180.5 s on blue and 76 s on red. In bot and in mid at level 6 the untouched lane never gets there within the run, so those returns beat it by default.

**Why mid resets at 0:00.** The level 1 mid laner crashes 5 minions into the tower 63.5 s into the game in every seed. In a run traced in campaign 2, the tower killed them before red's second wave arrived, both second waves then walked the same distance, met at the exact centre with six minions each, and stayed equal for about two minutes, until tie-breaking draws separated them (Reported, one trace, handoff 006). In the 2 runs that come back now, on either team, the front returns on the same tick as the untouched lane's front. Whether a real mid lane resets after a first-wave crash is unknown.

### 5.5 Diagnostics: one rule at a time, the tick, and the decision interval

A diagnostic changes one lane rule for one table. It shows which rule a verdict rests on. It is not a candidate for the lane. Two champion settings (top at level 1, mid at level 3), 3 seeds, 8 stacking settings, 8 holding settings with 3 and 4 surplus casters, and 4 bounce cases, with the plan on blue (`capabilities.json`, `diagnostics`).

| Lane | Untouched first-wave fight, mid and top | A plan accumulates (a thinning plan), of 8 | Largest crash (with no laner) | A hold sustains (longest, cycles), of 8 | Bounces in every run (before the untouched lane), of 4 |
| --- | --- | --- | --- | --- | --- |
| The M8 lane | 33 s, 33.5 s | 0 (0) | 8 (8) | 2 (4) | 4 (3) |
| M7's route graph | 33 s, 34.5 s | 1 (1) | 11 (10) | 2 (3) | 4 (1) |
| Blows land at once | 31 s, 31.5 s | 2 (2) | 9 (7) | 1 (3) | 3 (3) |
| Ranges along the lane | 33 s, 33.5 s | 0 (0) | 8 (6) | 2 (4) | 3 (3) |
| No tower shelter | 33 s, 33.5 s | 0 (0) | 8 (8) | 2 (4) | 4 (3) |
| At most 2 melee minions on a target | 33 s, 33.5 s | 3 (2) | 11 (6) | 2 (4) | 3 (2) |
| A cancelled cast costs nothing | 33 s, 33.5 s | 0 (0) | 8 (7) | 2 (3) | 3 (3) |
| A missile to a dead target turns to another | 33 s, 33.5 s | 1 (1) | 11 (7) | 0 (2) | 3 (3) |
| Both of those | 33 s, 33.5 s | 2 (1) | 9 (8) | 0 (2) | 3 (3) |
| Detour of 0.3 s | 33 s, 33.5 s | 0 (0) | 10 (10) | 3 (3) | 3 (3) |
| Detour of 0.6 s | 33 s, 33.5 s | 1 (1) | 11 (8) | 2 (3) | 3 (3) |
| Minion blows at 0.85 | 38 s, 38.5 s | 1 (0) | 10 (10) | 4 (3) | 4 (0) |

**What the table shows.** No rule produces the behaviours. Every variant moves a count by three settings at most, and not in one direction. The M8 lane accumulates in none of these 8 settings, because its three accumulating settings on blue are bot-lane carries, which the diagnostics do not run. M7's route graph brings back an accumulating setting and a crash of 11, and only 1 of 4 bounces beats the untouched lane there, because the untouched top lane then tips at 97 s (Inference from section 5.4). With blows that land at once, one hold is sustained where the M8 lane has two. Attack timing is therefore a sourced correction of how long fights last. It is not what makes a hold or a stack appear. A missile that turns to another target leaves no hold sustained. Weaker minion blows lengthen the fight by 5 s and leave no bounce that beats the untouched lane.

**Tick length** (`capabilities.json`, `tick_sweep` and `tick_sweep_sensitivity`). The diagnostic settings at ticks of 0.125, 0.25, 0.5, and 1.0 s, with a decision every 2 s at each, 3 seeds, and the plan on each team. A case is a setting and a plan. The reference is 0.125 s. The first table counts the cases in which each verdict holds at each tick, and the cases that keep the same verdict at all four.

| Verdict | Cases | Blue, same at every tick | Blue, holds at 0.125, 0.25, 0.5, 1.0 s | Red, same at every tick | Red, holds at 0.125, 0.25, 0.5, 1.0 s |
| --- | --- | --- | --- | --- | --- |
| A plan accumulates | 56 | 46 | 8, 2, 0, 2 | 53 | 2, 0, 0, 1 |
| A thinning plan delays the first crash | 40 | 32 | 38, 38, 36, 37 | 33 | 37, 37, 33, 36 |
| A hold sustains control | 56 | 48 | 3, 8, 2, 7 | 49 | 6, 3, 2, 5 |
| A crash bounces before the untouched lane | 4 | 1 | 0, 2, 3, 3 | 4 | 3, 3, 3, 3 |

The second table takes each case that has a value in every run. Its shift at a tick is its mean over seeds there less its mean at 0.125 s. A case moves more across ticks than across seeds when the range of its four means exceeds its range across seeds, averaged over the ticks.

| Measure, team | Cases | Move more across ticks than across seeds | Median absolute shift at 0.25, 0.5, 1.0 s | Mean over cases at 0.125, 0.25, 0.5, 1.0 s |
| --- | --- | --- | --- | --- |
| Largest crash, minions, blue | 80 | 65 | 0.33, 1.0, 1.0 | 4.98, 4.91, 4.81, 6.01 |
| Largest crash, minions, red | 80 | 68 | 0.33, 1.0, 1.0 | 4.97, 4.75, 5.27, 5.67 |
| First crash, s, blue | 48 | 47 | 0.5, 8.7, 5.4 | 42.3, 41.7, 56.3, 50.8 |
| First crash, s, red | 52 | 52 | 0.4, 2.5, 5.2 | 48.4, 50.1, 53.7, 47.4 |
| Held cycles, blue | 88 | 30 | 0, 0, 0 | 0.97, 1.01, 1.10, 1.12 |
| Held cycles, red | 88 | 25 | 0, 0, 0 | 1.02, 1.00, 1.08, 1.15 |
| Kept out, s, blue | 88 | 54 | 0.27, 0.40, 0.71 | 92.8, 91.7, 98.0, 96.3 |
| Kept out, s, red | 88 | 48 | 0.13, 0.42, 0.88 | 91.4, 90.4, 91.8, 94.5 |
| Bounce back, s, blue | 3 | 3 | 0.29, 0.88, 14.4 | 69.0, 67.6, 69.6, 68.7 |
| Bounce back, s, red | 3 | 3 | 0.63, 1.25, 1.54 | 64.5, 61.3, 69.3, 68.7 |

Per case, 0.25 s is much closer to 0.125 s than 0.5 s is. The median shift of a first crash on blue is 0.5 s at 0.25 s and 8.7 s at 0.5 s. Verdicts flip all the same, even between 0.125 s and 0.25 s, on both teams, so no tick gives every-seed verdicts that hold at the others. Section 5.4 counts at 0.5 s, so its crash times are not converged in the tick, and its every-seed verdicts on single settings are not stable in it.

Blue's top laner at level 1 from its own tower, against an opponent that last-hits, accumulates reinforcements under six of its seven plans at 0.125 s, every plan but `passive`. It accumulates under two at 0.25 s and under none at 0.5 s and 1.0 s. On red one case accumulates against an opponent that last-hits, at 0.125 s only: mid at level 3 from first contact under `thin 3, then last hit`. So the statement of section 5.4 that no plan accumulates against an opponent that last-hits holds at 0.5 s and not at 0.125 s.

**How one case flips.** In top at level 1 with both laners present and `thin 2, then last hit`, the first crash comes at a mean of 42 s at ticks of 0.125 and 0.25 s, and of 193 to 195 s at 0.5 and 1.0 s, with the plan on blue (`tick_sweep_sensitivity`). One trace of that case found the blue laner with 3 last hits by 75 s at 0.25 s and 2 at 0.5 s, and red with 3 and 5 by 90 s (Reported, a scratch probe recorded in the decision trail of campaign 3). A quarter second in a minion fight changes which last hits land, and a near-balanced lane amplifies the difference into a different crash (Inference from that one trace). No rule was varied across ticks, so this does not rule out a single rule. The once-per-tick march of section 4.2 is a candidate. Section 10.3 sweeps the tick and the decision interval in the integrated game.

**Decision interval** (`capabilities.json`, `decision_sweep` and `decision_sweep_sensitivity`). The same settings and seeds at a 0.5 s tick, with a decision every 1, 2, and 5 s and the plan on each team. The reference is 1 s.

| Verdict | Cases | Blue, same at every interval | Blue, holds at 1, 2, 5 s | Red, same at every interval | Red, holds at 1, 2, 5 s |
| --- | --- | --- | --- | --- | --- |
| A plan accumulates | 56 | 54 | 2, 0, 0 | 54 | 0, 0, 2 |
| A thinning plan delays the first crash | 40 | 33 | 39, 36, 32 | 33 | 39, 33, 34 |
| A hold sustains control | 56 | 55 | 2, 2, 1 | 54 | 2, 2, 2 |
| A crash bounces before the untouched lane | 4 | 4 | 3, 3, 3 | 3 | 3, 3, 2 |

| Measure, team | Cases | Move more across intervals than across seeds | Median absolute shift at 2, 5 s | Mean over cases at 1, 2, 5 s |
| --- | --- | --- | --- | --- |
| Largest crash, minions, blue | 80 | 35 | 0.33, 0.67 | 5.68, 4.81, 4.51 |
| Largest crash, minions, red | 80 | 29 | 0, 0.17 | 5.31, 5.27, 4.82 |
| First crash, s, blue | 55 | 52 | 1.0, 9.2 | 49.8, 59.6, 66.6 |
| First crash, s, red | 56 | 46 | 0, 11.7 | 52.3, 58.0, 66.4 |
| Held cycles, blue | 88 | 10 | 0, 0 | 1.02, 1.10, 1.08 |
| Held cycles, red | 88 | 5 | 0, 0 | 1.04, 1.08, 1.16 |
| Kept out, s, blue | 88 | 20 | 0, 0 | 95.5, 98.0, 95.1 |
| Kept out, s, red | 88 | 10 | 0, 0 | 91.1, 91.8, 93.0 |
| Bounce back, s, blue | 4 | 0 | 0, 0 | 74.9, 74.9, 74.9 |
| Bounce back, s, red | 4 | 1 | 0, 0 | 82.0, 82.0, 137.8 |

Verdicts change less with the decision interval than with the tick, and most hold lengths do not move at all. Crash times do. A decision every 5 s delays the first crash by a median of 9.2 s on blue and 11.7 s on red against one every 1 s. The interval is how fast a plan answers its lane, so a wave result must name it as it names the tick.

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
| The carry's accumulating plan from its own tower, `thin 2, then last hit` (9 minions), plan on blue | 2.7 percent | 3 |
| The carry's accumulating plan from first contact, `thin 3, then passive` (8 minions), plan on blue | 8.1 percent | 3 |
| The carry and support's accumulating plan, `thin 3, then passive` (8 minions), plan on blue | 7.5 percent | 3 |
| A hard push in the carry's setting from its own tower, and in the carry and support's | 0.0 percent | 3 |

Never more than three melee minions attack one target, and six bodies fit around one, so the place where bodies would matter is not the target. It is the walk to the next target inside a crowd, and the crowd grows with the stack. The `detour_s` diagnostic charges that walk. A melee minion that turns to a new minion target loses 0.3 s or 0.6 s before its cast. One body's detour at minion speed is about 0.25 s (Assumed geometry on the sourced radius). The length of a fight does not show the detour. A placed fight of six against six stays at 28 s even with a detour of 5 s (Reported by the review of campaign 2). The verdict counts of section 5.5 are the evidence, and they move by one setting. This bounds one effect of obstruction in a lane without width. It does not show what bodies do.

### 5.7 The first wave's exceptions

The wiki gives the first wave three exceptions (section 4.2). The M8 lane models one of them.

| Exception (Sourced) | In the M8 lane | What it changes in section 5.4 |
| --- | --- | --- |
| Minions of the first wave answer a call for help while they attack a tower. | Modelled by `first_wave_call` (Tested, `test_only_minions_of_the_first_wave_answer_a_call_for_help_while_they_attack_a_tower`). | Part of every result. |
| First-wave minions ignore champions until one walks much closer or the waves meet. | Not modelled. | Nothing measured. In 0 of 1,440 stacking and holding cases (480, 640, and 320 by section) on either team does a minion hit the champion before the first waves meet (`minion_blows_before_first_contact`). |
| First-wave minions pass through units for 28 s in the side lanes and 18 s in mid. | Not modelled. | Nothing can. The lane has no bodies (section 5.6). |

### 5.8 What is known, what is not, and three measurements

**Read and equal to the ruleset** (Sourced): minion health, damage, attack speed, range, and the on-hit share. **Read in the game's data files** (Sourced): cast times, missile speeds, and the corner waypoints of the M8 map. **Documented and not modelled:** section 4.3. **Not documented anywhere read so far:** how long bodies take to walk around each other, the retarget cadence, and the length of the short time that minions keep a harassing champion as target.

Three measurements in a custom game on patch 26.22 bear on the open behaviours. The simulator's values changed with the corrections.

| Measurement | The simulator's value |
| --- | --- |
| **A. The untouched first wave in mid.** Nobody touches the lane. When the minions of wave 2 reach the fight, count the minions of wave 1 that are still alive and note how healthy they look. | Wave 2 arrives 29 s after the first blow. Six minions of wave 1 are alive, at 23 percent of their health on average. Left alone, the fight would end 33 s after the first blow. |
| **B. The slow-push drill in top.** A level 1 laner kills the three casters of wave 1 and then only last-hits, with no opponent. Count the minions that reach the enemy outer tower and time their arrival from first contact. | 8 minions of two waves, six and two, 38.5 s after contact with the plan on blue and 39 s with it on red. The placeholder top laner needs longer for the casters than a real champion might. |
| **C. An untouched top lane.** Nobody touches the lane for five minutes. Note whether the waves keep meeting near the centre or one side reaches a tower. | The front stays within 100 units of the centre for the first 150 s in every run and first leaves toward red's half at 247 to 281 s. No wave reaches a tower within 300 s. On M7's route graph the front was on blue's half at 97 s in every run. |

A match in A would confirm one timing. B and C test results that this document does not trust.

### 5.9 Incentive screen and M7's tick sweep

**Incentives** (Tested, [`incentives.json`](../../experiments/m8/waves/results/incentives.json)). A level 1 laner plays one `LANE` action for 5 minutes in each of 12 lane states, in a full world. No action earns most in every state. `last_hit` with the wave earns most gold plus XP in 9 states. `push` with the wave earns most in mid from first contact against an opponent that pushes, `push` from the hold line in mid after a crash at the own tower against an opponent that pushes, and `last_hit` from the hold line in mid after a crash with no opponent. A hold that last-hits earns within 6 of last-hitting with the wave in the two first-contact states with no opponent, 46 more in mid after a crash with no opponent, and less in the other nine. In each of those nine the holding laner retreats at least once in the median run. The laner's numbers are placeholders, so this is a screen of the mechanics.

**M7's tick sweep** (Tested, `m7_tests_on_m8_lane.json`, `tick_sensitivity_m8_lane`). On M7's scripted cases, 9 of 17 metrics are within 10 percent of the 0.125 s reference at a 0.5 s tick. Campaign 1 measured 13 of 17 before cast times existed, campaign 2 measured 9, and campaign 3 measured 10. The eight that move are a wave metric in each of three top-lane cases, and the band time or the champion's lowest health in four of M7's hold cases.

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
| One attack capacity | A table entry per intent kind names the one class that a champion's attack goes to on a tick: minions for `LANE`, a champion for `FIGHT`, a camp for `CAMP`, a tower for `SIEGE`, and for `HOLD`, `FOLLOW`, and a finished intent the enemy champion that is attacking it. `Champion.attack_credit` is one budget for every class. One credit is one hit on a minion or a tower, or the damage rate over the attack speed on a champion or a camp (`champions.attack_worth`). A tick against a champion or a camp spends all the credit the champion has, what it brought and what the tick earns. So a ready attack lands at once on any class, and a champion that has just hit a minion deals only what it has earned since. The lane takes the credit in with the champion's input and hands back what its hits left. An idle tick earns attack speed times the tick, up to one ready attack. The area damage of the `push` mode and the lockdown are separate abstract abilities outside the credit, and both cost mana. Area damage costs `area_mana_s` mana for each second in which it hits a minion (8 for top and jungle, 12 for mid, 6 for carry and support). It runs only while it hits a minion, and for no more seconds than the champion's mana pays for (`ChampionInput.aoe_s`, the `AreaSpent` event). A living champion regenerates `mana_regen` mana per second (1.0, 1.0, 1.5, 1.1, and 1.4 in that order, scaled with level), so a full bar pays for pushing five or six waves. The lockdown costs mana and has a cooldown, as before. Over random switches among `LANE`, `FIGHT`, `CAMP`, `HOLD`, and `MOVE`, the attacks delivered plus the credit kept equal the credit at the start plus attack speed times the time, area seconds stay within the mana and the ticks of `push`, mana goes only to area damage and lockdowns, and lockdowns stay within their cooldown (Tested, `test_switching_among_lane_fight_camp_hold_and_move_never_delivers_more_than_the_attack_mana_and_lockdown_budgets`). | M7 section 7.4, owner requirement. The mana numbers and the design target of five or six waves are Assumed. |
| Champion against champion | A fighter closes to its attack range and deals one attack's worth for each credit it spends, on every tick on which the target is alive, within range by the straight line, and in the view of the fighter's team. All hits of a tick are collected before any lands. | M7 section 5.9. The rates are Assumed placeholders. |
| Hitting back | A champion that holds or follows hits the enemy that deals it the most damage on that tick, if that enemy is within its own range. | M7 section 7.1 |
| Lockdown | Used when it is ready, the mana covers it, and the champion hits a champion. It takes a share of the target's move speed for its duration. | Numbers Assumed, from the M7 prototype |
| `FIGHT` | The fighter heads for its target by its team's record of it alone, with the lead along a lane of section 3.2. While the team sees the target, the record is where the target stood at the end of the last tick. Out of view, the fighter walks to the last-seen place in team memory. Seen again on the way, the fight resumes with no outcome. One tick after it arrives within attack range of the last-seen place with the target still unseen, the intent ends with `LOST`. The target's death ends it with `KILLED`, whoever killed it. | M7 section 7.1 |
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

- Pursuit follows the contract of section 3.2. Every walk is picked from one state before the move step and all champions move at once. A fighter reads only its team's record of its target, a target that walks away along a lane is led by one seen step, and off the lanes there is no lead. A fighter answers a visible target that turns to flee one tick late. `FOLLOW` is unchanged.
- First blood is drawn among the kills of the tick, ordered by the victim's place. M7 said a draw picks the team, and that flips when the teams exchange seats.
- `SIEGE` ends with `CLEARED`, or with `ABSENT` when the lane has no tower to damage. M7 names no outcome.
- A laner that fights in self-defence off its lane is still charged as roaming.
- Left out: bounties and shutdown gold, the level-difference modifier on kill XP, the early growth of the assist pool, the 3 s before backdoor protection returns, plate gold decay, Bulwark, and the armor penetration of tower shots. A tower keeps a champion as target only while that champion is harassing.

### 8.2 The fight scenarios of M7 section 5.9, on the M8 kernel

[`combat.json`](../../experiments/m8/results/combat.json) reruns M7's four scenarios with policies that only choose actions. Every champion number is a placeholder, so the outcomes show that the mechanics respond. They do not show who wins a real fight.

| Scenario | Result |
| --- | --- |
| A champion retreats at half health. Speed edge, lockdown, and distance to its own tower, 18 cases. | 16 escapes and 2 deaths. From 1,000 and 2,500 units every runner escapes. From 4,000 units the runner whose speed is 20 lower than the chaser's dies, with and without the lockdown, and the others escape. The chaser dies under the tower in all 16 escapes. The lockdown changes no outcome. Campaign 3 had 10 escapes and 8 deaths. The runner of equal speed from 2,500 and 4,000 units and the slower runner from 2,500 units now escape where they died, because the chaser answers a turn to flee one tick late (Inference from the traces, section 3.2). |
| A level 1 fighter loses to a level 7 enemy alone. Its jungler walks in from d units. | The side wins with the jungler from up to 2,750 units. From 3,000 to 4,500 units both of the side's champions die and the enemy survives with 21 to 86 health. From 4,750 the enemy dies after all, 44.5 to 82 s in, because the first fighter has respawned and walked back by then (Inference). |
| The same duel in open lane and under the defender's outer tower. | In open lane the attacker wins with 86 health after 12 s. Under the tower it dies after 2.5 s to three tower shots. |
| A jungler leaves fog toward a laner. | A laner at its own outer tower is never touched, and the jungler dies under the tower. A laner at the enemy outer tower now survives whether it decides every 1, 2, or 5 s, with its lowest health 416 when it starts with 650 and 182 to 191 when it starts with 390, and the jungler dies in all six runs. In campaign 3 that laner died in all six and the jungler survived. One traced run of the 2 s case shows why (Reported, a scratch probe recorded in the decision trail). The jungler's lockdown slows the laner to 109.5 units a tick, and the jungler follows at its range of where that slowed step points. When the slow ends the laner steps 182.5 units and the jungler falls to 248 units behind. Its edge of 2.5 units a tick never closes that, and the brawler policy follows the laner under blue's outer tower, which kills it. This is the one-tick lag of section 3.2 when a target speeds up. Campaign 3's fighter read the target's place after its move, which was the leak. |

Two things in these runs come from the rules and would mislead if read as strategy. A tower with no minion in range shoots any enemy champion in range, so a champion that walks under an enemy tower alone dies within seconds. And conclusions about ganks depend on where the wave stands, which section 5 leaves open.

### 8.3 Acceptance criteria of C5

| Criterion (M7 section 10.1, and the owner's requirements) | Result | Test |
| --- | --- | --- |
| Damage is monotone in capability | Never falls with a level or an upgrade, for five profiles | `tests/test_combat.py` |
| An ally's arrival tick equals route length over speed | From 600, 1,500, and 3,000 units the first hit falls on the tick that the arithmetic gives | `tests/test_combat.py` |
| A champion takes champion damage only on ticks when an attacker is within range by the straight line and the target is in the view of the attacker's team | Open lane: hits on 5 of 30 ticks, exactly those in range. Over a wall: hits on exactly the 7 of 12 ticks with an ally's sight. 494 units in a straight line against a walk of 568 is inside a range of 550. | `tests/test_combat.py` |
| A tower's damage on a champion follows the reference aggro and ramp rule to the tick | No shot at 751 units. Multipliers 1.0, 1.5, 2.0, 2.5, 2.5 on consecutive shots. The ramp is kept after 4.5 s without a shot and starts again after 5 s. The tower turns from minions to a champion that damages an ally and back when the call has run out. | `tests/test_combat.py` |
| Permuting the seat order changes no outcome | Five fights, seats exchanged between the teams and inside a team. Equal on every tick. | `tests/test_combat.py` |
| `FIGHT` follows M7 section 7.1 | Pursuit to the last-seen place, `LOST` one tick after arrival, no outcome when the target is seen again first, the same path wherever the hidden target is. A target that steps behind a wall is followed only if the fighter's team sees where it went. A faster melee fighter keeps hitting a target whose step is longer than its range, on a lane by the lead and off the lanes by the detour, and a fighter never leads a target that walks toward it. A target that walks, follows, or fights from equal observations draws the same moves from the fighter's team. | `tests/test_combat.py`, `tests/test_vision.py`, `tests/test_pursuit.py` |
| A dead champion returns at the fountain after the ruleset's timer | 10 s at level 1 | `tests/test_combat.py`, `tests/test_world_intents.py` |
| One attack capacity across targets | A champion that fights kills no minion in its reach, and on every tick its damage goes to one class. Over switches between minions, a champion, a camp, and idling, the attacks delivered plus the credit kept equal the credit at the start plus attack speed times the time, on every tick. A ready attack lands whole on the first tick against a champion and against a camp. A carry that has just hit a minion deals 70 to a champion on the next tick, and one that idled deals 135. Damage on a champion over 6 s is the same at ticks of 0.25 s and 0.5 s. Since campaign 4 the switching test also bounds area seconds, mana, and lockdowns, and a champion that switches from a fight or a camp to the lane has no ready attack there. | `tests/test_combat.py`, `tests/test_lanes.py` |
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
| Enemy champion memory | Per team and enemy an `EnemyMemory`: the place, health, level, and upgrades that the team last saw, the tick, and `was`, the place where the team saw the enemy one tick before, or nothing unless it saw it on both ticks. It freezes out of view. A visible enemy's place, health, level, and upgrades are public. Its intent, gold, mana, and the other fields that the tests of section 9.4 change are private. | M7 section 6.2. Upgrades are kept since campaign 4. |
| Enemy tower memory | Per team 9 `TowerMemory` records, one per enemy lane tower: its health and the tick. The front tower's health updates while the team sees it. A tower behind the front is known at full health, because it takes no damage, and a fallen tower is known at zero, because a fall is public. At the start every tower is known at full health. | M7 section 6.2. New in campaign 4. |
| Observation | Besides the fields of C1 to C5, `enemies` (seen now), `remembered` (last seen, with its age), `rivals` (each enemy's level and death timer, which are public), `lanes`, and `wards` (the team's own). A `LaneView` holds the team's own lead and wave size, the enemy lead and wave size as last seen with their age, contact, the health of the team's towers, and each enemy tower's health as last seen with its age (`enemy_towers`, `enemy_towers_age_s`). Each champion view adds `ward_charges` and `ward_ready_s`, and each enemy view and last-seen record its upgrades. | M7 section 6.3 |
| Encoding | `vision.encode` turns an observation into one flat tuple of 393 numbers, unscaled, with -1.0 for a value the team does not have. Campaign 3 had 358. `observe_team` builds a team's five observations in one pass. | M7 section 10.1, C6 row. The length changes when a field is added. |
| `WARD` | The champion walks until its spot is within 625 units by the straight line, places a Stealth Ward on the spot, and ends with `PLACED`. The 18 spots are the 12 camps, the 2 river nodes, and the middle of 4 river edges (section 3.2). | M7 section 6.4. The spots are Assumed. |
| Charges and limits | 1 charge at 0:00 and at most 2. The recharge falls from 210 s to 90 s and the duration rises from 90 s to 120 s with the average champion level. At most 3 wards per champion, and a fourth removes that champion's oldest. | The ends, the 2 charges, and the 3 wards are Sourced. The start charge, the straight lines between the ends, and the removal of the oldest are Assumed. |
| Enemy wards | A ward cannot be seen or destroyed. An enemy ward is in no observation. | M7 section 6.4. Clearing is M11. |
| Automation on team knowledge | `stance` reads `champions.known_front` in `lane_post` and `economy.lane_inputs`. `FIGHT` reads only the team's record of its target (section 3.2). `combat.collect` hits only a target that the team sees. The mask is computed from the observation. Guard retaliation and minion calls for help follow an enemy's hits on the same tick, because a hit reveals its attacker to the victim's team on that tick (M7 section 6.1). | M7 section 6.3 |
| Scripted policies | `farmer`, `jungler`, `brawler`, `roamer`, `random_legal`, the wave plans, and the C7 policies of `riftgame.policies` read only the observation. Only the C7 policies place wards. | Owner requirement |
| Wards and the role rule | A laner with allowance may ward and is charged as roaming while it is off its lane. A returning laner may not ward. Self-defence, the return actions, and `RECALL` stay legal, and `Config.roam_restricted` turns the restriction off. | Owner requirement. Tested. |

### 9.2 Departures and limits

**The pursuit leak is closed.** Handoff 007 left open a fighter whose walk depended on the intent kind of its visible target (007/F14). Since campaign 4 a fighter reads only its team's record (section 3.2), and the tests of section 9.4 change the private fields of visible enemies, intent among them, and find no observation and no move of the team that changes.

Beside the Assumed rows of section 9.1, four limits stand. The encoding is unscaled, and its layout follows the observation's fields. A direct `World.ward` call between ticks gives combat sight one tick before team memory, which the `WARD` action does not (Reported). Pursuit by the team's record answers a visible target that turns to flee one tick late, and gives no lead off the lanes (section 3.2). The map has no brush and no height, and the wall terrain is the constructed terrain of M7 section 5.1.

### 9.3 What the fog hides, measured

[`experiments/m8/vision.py`](../../experiments/m8/vision.py) runs the comparisons of `tests/test_vision.py` and reports their sizes in [`vision.json`](../../experiments/m8/results/vision.json). The assertions are in the tests.

| Measure | Value |
| --- | --- |
| Hidden-state comparison | 32 worlds: 4 games, both teams, 4 snapshot ticks. Every observation, encoding, and mask is unchanged in 32 of 32. The changes cover 79 living enemy champions, 20 dead ones, 305 minions, 222 camps, and 352 wards. |
| Behaviour comparison | 32 comparisons and 597 compared ticks, from 2 to 60 per comparison. 29 reach a reveal. The compared ticks cover `CAMP`, `FIGHT`, `FOLLOW`, `HOLD`, `LANE`, `MOVE`, and `WARD`, and 22 champion ticks in a fight whose target is out of view. |
| Scripted farming and jungling, 5 games of 600 s | Blue sees the enemy jungler on 2.6 percent of ticks [2.0 to 9.8] and red on 1.0 [0.8 to 10.6]. Each enemy laner is seen on 86.8 to 90.3 percent as a median, and each enemy wave on 88.3 to 92.6. These policies place no ward. |
| Random legal actions, 5 games of 600 s | Each enemy champion is seen on 24.2 to 48.4 percent of ticks as a median, and each enemy wave on 91.0 to 93.4. A team has 0.153 and 0.158 wards on the map, as a median over the games. |

The C7 policies ward. In their 50 soak games each game places a median of 52 wards (section 10.2).

### 9.4 Acceptance criteria of C6

The criteria are those of M7 section 10.1 for C6, and the owner's requirement that no automatic behaviour reads hidden state. The tests are in `tests/test_vision.py`, `tests/test_memory.py`, and `tests/test_pursuit.py`, and the mutation runner has entries that each file must catch.

| Criterion | Result | Test |
| --- | --- | --- |
| The hidden-state test: change every field hidden from a team, and its observations and masks stay identical | 32 worlds with the encodings identical too. Every field of `Champion` is either changed in a hidden enemy or named with the reason it is not hidden. The other team is told of every change. | `test_changing_every_field_hidden_from_a_team_changes_none_of_its_observations_encodings_or_masks`, `test_the_scramble_changes_every_hidden_field_and_names_the_ones_it_leaves` |
| The behaviour test: under the same change, the team's champions follow identical trajectories until something is revealed | Each champion of the team is equal as a whole `Champion` on every tick before the first exposure. Since campaign 4 the team's whole memory is equal too on every such tick: camps, enemy records with their places, `was`, and upgrades, waves, and towers. Exposure is decided from the map's sight measure by a check that shares no code with `vision.py`. | `test_a_teams_champions_do_the_same_in_two_worlds_that_differ_only_in_what_is_hidden_from_it`, `test_the_behaviour_comparison_covers_every_automatic_movement_and_enough_ticks` |
| The private fields of a visible enemy stay private (closes handoff 007, F14) | In a copy, every enemy that the team sees gets new values in its 18 private fields, among them intent and how the last one ended, XP within the level, gold, attack credit, channel, and mana. The team's observations, encodings, and masks are identical, and so are its champions' moves on the next step. That holds for each team in the four games of the behaviour test, with at least 15 compared moments and 25 changed enemies in each, and in random legal games with rings of fights and chains of followers, compared every 16th tick. Stance, lane inputs, combat targeting, and retaliation read none of the 15 either. The comparison lasts one step, because after it the changed enemy acts differently, which the team may see. | `test_changing_the_private_fields_of_the_enemies_a_team_sees_changes_none_of_its_observations_and_none_of_its_moves`, `test_stance_lane_inputs_targeting_and_retaliation_read_no_private_field_of_a_visible_enemy`, `test_random_legal_games_give_both_teams_moves_that_no_private_field_of_a_visible_enemy_changes`, `test_a_fighter_moves_the_same_against_a_target_that_walks_follows_or_fights_from_equal_observations` |
| The junction, open-ground, and wall cases hold for champions in a running game | Two arms of a junction see each other. Mid lane and the river see each other over open ground though the walk is longer than sight. A lane and the camp behind the lane wall do not. A champion that walks out from behind the wall is seen from the tick the map gives. A team never sees a place that its sources do not see by the map's measure. | The five sight tests of `tests/test_vision.py` |
| A ranged attack reaches a target behind a wall only while the attacker's team sees it | Damage lands on exactly the ticks on which a ward of the attacker's team stands | `test_a_ranged_attack_reaches_a_target_behind_a_wall_on_exactly_the_ticks_on_which_a_ward_of_the_attackers_team_stands` |
| An enemy Stealth Ward never appears in a team's view | Enemy wards placed anywhere change nothing that the team is told, then or later | `test_enemy_stealth_wards_placed_anywhere_change_nothing_that_a_team_is_told_now_or_later` |
| Last-seen records freeze out of vision | A record keeps place and health while the enemy walks off and heals, and its age grows by the clock. A remembered wave keeps its lead and size out of sight and is forgotten when the team sees its place empty. An enemy tower's health shows while the team sees it, freezes out of view, and reads 0 once the tower falls. An enemy's upgrades show while it is seen and stay in the record, and `was` needs two ticks of sight. | `test_a_last_seen_record_keeps_place_and_health_while_the_enemy_walks_off_and_heals_and_its_age_grows_by_the_clock`, `test_a_remembered_wave_keeps_its_lead_and_size_out_of_sight_and_is_forgotten_when_the_team_sees_its_place_empty`, the two record tests of `tests/test_memory.py` |
| A ward reveals and then expires | A ward shows a hidden enemy for exactly its duration at the average champion level. Placement range, recharge, the two charges, and the fourth ward are tested apart. | `test_a_ward_shows_a_hidden_enemy_for_exactly_its_duration_at_the_average_champion_level` and four ward tests |
| Positioning and pursuit read team knowledge (owner requirement, M7 section 6.3) | A laner walks with its own wave wherever an unseen enemy wave is, and takes its stance against the wave once a ward, an ally, or a minion of its team sees it. A wave plan reads its champion's observation and nothing else. | The two stance tests, the wall pursuit test, `test_a_plan_reads_its_champions_observation_and_nothing_else` |

**What the leak tests do not show.** The behaviour test changes only what is hidden by a margin of 1,500 units beyond every sight radius and its slack of 300, so that the comparison lasts. It leaves the enemy's wards and its current memory alone and replays the enemy's actions from the first world, so it never tests what the enemy would do differently. Its thresholds against a vacuous pass depend on the trajectories of four scripted games, and a change elsewhere in the kernel can move them. The pursuit change of campaign 4 moved them, and they were restated: at least 25 compared ticks per team and game, at least 3 hidden tower changes, and a snapshot replay that sees a ward placed and a fight end by `LOST` or `KILLED` (decision trail). These are read from `tests/test_vision.py`. The visible-enemy tests compare one step only. The leak of a stance that reads the true front is caught by the targeted stance tests, not by the behaviour comparison (Reported).

## 10. Integrated games, sweeps, and throughput (C7)

### 10.1 What exists

[`riftgame/policies.py`](../../riftgame/policies.py) holds scripted policies for all ten seats, and [`experiments/m8/integrated.py`](../../experiments/m8/integrated.py) plays them under a referee. Every number of this section is in [`integrated.json`](../../experiments/m8/results/integrated.json) unless it names [`kernel.json`](../../experiments/m8/results/kernel.json).

| Part | Built | Status |
| --- | --- | --- |
| Policies | One policy per seat, built per side with `Side(team)`. A player knows which side it plays, so a policy can turn a place of its team's frame back into a map position. `policy(team)` holds one rule per role, with the laner's rule for top, mid, and the carry. `team_policies()` builds one policy per seat, and `harness.tick` takes one policy or one per seat. Each policy reads only its champion's observation and public facts, walks down a list of wants, and takes the first that its mask allows. | Tested, `test_every_scripted_choice_is_legal_and_reads_only_the_observation` |
| Laner | Last-hits with its wave. Below 30 percent health it recalls, or first walks to its own tower when an enemy is seen within 1,400 units. When an enemy other than its lane opponent shows up within 1,800 units, it walks to its own tower, keeps that walk under way, and holds within 300 units of the tower. At 40 percent health or more it keeps a fight under way and hits back at an enemy that hurt it, before any retreat. A walk to a ward spot goes on before shopping and trading. It recalls to buy once its next upgrade is affordable and no enemy is near, and buys on its fountain by the kernel's rule. It trades with its lane opponent at 60 percent health or more, when it is at least as healthy as the opponent and away from the enemy tower. From 75 s it wards the river beside its lane. After 600 s it pushes and sieges a lane whose opponent is dead or unseen for 20 s. | Every threshold Assumed |
| Support | Stays with its carry, spends its item's charges on the wave, wards the bot-side river, and joins the carry's fights. | Assumed |
| Jungler | Clears camps as `harness.jungler` does. At 70 percent health or more it ganks the most hurt enemy laner below 60 percent that its team sees within a walk of 3,500 units, away from the enemy tower. It wards a river spot within a walk of 2,500 units and leaves for its fountain when an enemy with a larger share of its health shows up within 1,800 units. | Assumed |
| Referee | `Referee` watches the world after every tick and checks the event log against the ruleset's numbers, not against the functions of `riftgame` that schedule the events. It checks every minion's spawn tick against the wave schedule, every minion's place against the standing enemy front tower, every camp spawn and respawn with the Scuttler pair rule, and every champion respawn against the timer of the level the champion had before the tick. Every tower shot on a champion is checked, at the places where the lane held each champion when the towers fired, so a champion that died on the tick counts where it stood. While a tower has a provoker, a shot on a champion must go to a provoker, and a provoked stretch of one attack period plus a tick must contain a shot. A provoker is an enemy champion in the tower's range that hit, on the tick or within the call-for-help window before it, a champion of the tower's team that stood within the switch range. Without a provoker, a shot must go to a champion in range while no enemy minion is in range. Minions do not move while towers fire, so a minion alive in range after the tick was in range then. At the end of a game the referee also faults a wave, a camp, or a champion respawn that was due and never came. Five entries of the mutation runner break the tower rule, a respawn, a camp respawn, and the wave clock, and the referee's test fails on each. The referee counts only new orders, so a retreat or a gank order kept over several decisions counts once. | The referee reads the world, which no policy does. |

### 10.2 Acceptance criteria of C7

The criteria are those of M7 section 10.1 for C7. Each game is 1,200 s at a 0.5 s tick with a decision every 2 s, with the invariant checker on every tick. The soak has the scripted policies on both teams, and the baseline has them on one team against random legal actions on the other.

| Criterion (M7 section 10.1) | Result | Test |
| --- | --- | --- |
| Scripted games of 20 game minutes run for 50 seeds with no invariant failure | 50 games, 0 invariant errors, 0 referee faults | `integrated.json`, `soak`. `test_a_scripted_game_of_20_minutes_breaks_no_invariant_and_no_rule_of_the_referee` |
| Three pinned replays reproduce their digests | Scripted teams on seed 7, scripted blue against random red on seed 11, and random teams on seed 13, 2,400 ticks each. Each reruns equal on every tick, and the final digests are pinned. | `integrated.json`, `replays`. `test_three_pinned_replays_reproduce_their_digests_on_every_tick` |
| Every C1 to C6 test still passes | The whole suite passes (section 11). | `-m pytest -q` |
| Throughput stays above the gate of M7 section 10.4 | 476 simulated seconds per wall second [447 to 490] against 300 | `kernel.json`, `c7_gate` (section 10.4) |
| In the event log, every wave spawn, camp spawn, camp respawn, and champion respawn falls on the tick that the ruleset gives | 80,700 minion spawns, 3,364 camp spawns and respawns, and 1,839 champion respawns checked in the soak. 0 faults. | `integrated.json`, `soak`, `checked` |
| No minion moves past a living enemy tower | 6,822,748 minion places checked against the standing enemy front tower in the soak. 0 faults, with the lane rule `tower_blocks` of section 4.1. | `integrated.json`, `soak`. `tests/test_lanes.py` |
| A champion that damages an enemy champion inside the range of that enemy's tower takes tower damage under the reference rule | In the soak, every one of the 1,598 tower shots on champions is checked. On 498 ticks a tower had a provoker. The 290 shots fired then went to a provoker, and 265 provoked stretches were answered by a shot. The other 1,308 shots went to a champion in range with no enemy minion in range. No tick is skipped, and there are 0 faults. The baseline games add 5,974 checked shots with 0 faults. Campaign 4's first referee compared only 55 of the 1,598 with a rule, which the independent review found. The rule itself is tested to the tick in C5. | `integrated.json`, `soak`. Section 8.3. |
| After an outer tower falls, the enemy wave's furthest advance in that lane increases | 140 outer towers fell in the soak and baseline games, 61 of them with a full 120 s window after the fall. The attacking wave's furthest advance in that lane is larger after the fall in 61 of 61, by a median of 3,698 units and at least 1,242. | `integrated.json`, `towers`. `test_after_an_outer_tower_falls_the_attacking_wave_advances_further_in_that_lane` |
| A scripted team beats a random-action team on gold and XP at 15 minutes on at least 45 of 50 seeds | 50 of 50 with the scripted team on blue, by a median of 31,372 gold plus XP and at least 25,705. 50 of 50 on red, by 29,287 and at least 22,697. No invariant error and no referee fault. | `integrated.json`, `baseline`. `test_a_scripted_team_beats_a_random_team_on_gold_and_xp_at_15_minutes` |
| A sweep over ticks of 0.25, 0.5, and 1.0 s and decision intervals of 1, 2, and 5 s reports which scripted outcomes change, and the handoff confirms or revises the starting values | Section 10.3, with 0.125 s added as the reference tick. The starting values stay for throughput, and fidelity does not confirm them (section 10.5). | `integrated.json`, `sweep` |

**What the policies did.** Over the 50 soak games, the policies' work as a median per game is 30 kills, 63 camp clears, 66 ended recalls, 52 wards placed, 87 `FIGHT` orders, 9 interrupted recalls, 7 gank orders, 7 `SIEGE` orders, and 339 retreats on a sighting. In all there are 1,525 kills, 375 executions, 93 fights ended by `LOST`, and 13 towers destroyed. Each of the ten behaviours that the soak requires occurs in every game except `LOST`, which is missing in 10 of 50 (`games_missing_a_behaviour`). `test_the_scripted_policies_exercise_every_subsystem_over_a_few_games` checks the same over a few games.

### 10.3 The sweeps

20 seeds of 1,200 s each, with the scripted policies on both teams. Each cell gives the paired median, the median over seeds of the value less the reference's value in the same seed, and in brackets the seeds higher and lower than the reference. The noise is the interquartile range of the reference across seeds. Gold, XP, minion gold, and tower health are per team, and tower health is the summed health of the team's towers at the end. The counts are over both teams, and orders count only when new.

**Tick, with a decision every 2 s.** The reference is a tick of 0.125 s.

| Measure | Median at 0.125 s | Noise | 0.25 s | 0.5 s | 1.0 s |
| --- | --- | --- | --- | --- | --- |
| Gold, blue | 26,909 | 1,900 | -99 (9, 11) | +411 (11, 9) | +87 (12, 8) |
| Gold, red | 27,960 | 2,047 | -137 (10, 10) | +610 (11, 9) | -1,313 (6, 14) |
| XP, blue | 34,426 | 2,363 | +183 (11, 9) | +707 (11, 9) | +1,584 (12, 8) |
| XP, red | 35,056 | 4,863 | +122 (10, 10) | +1,137 (14, 6) | -1,276 (9, 11) |
| Minion gold, blue | 4,890 | 215 | +43 (10, 10) | -330 (6, 14) | -942 (1, 19) |
| Minion gold, red | 4,917 | 677 | +42 (11, 9) | -76 (9, 11) | -557 (4, 16) |
| Tower health, blue | 47,540 | 6,027 | +101 (10, 10) | -691 (8, 12) | +335 (10, 10) |
| Tower health, red | 50,089 | 5,499 | -120 (9, 11) | -1,111 (7, 13) | -1,585 (6, 14) |
| Kills | 29 | 5.75 | -2 (5, 13) | +1 (11, 7) | +1.5 (11, 8) |
| Camp clears | 57 | 5.75 | +5 (17, 3) | +7 (16, 4) | +3 (16, 4) |
| Recalls ended | 66 | 5.75 | +3 (12, 8) | 0 (9, 9) | -1.5 (8, 11) |
| Wards placed | 52.5 | 3.75 | -1 (6, 12) | -0.5 (9, 10) | -1 (6, 11) |
| `FIGHT` orders | 85 | 5.75 | -3 (5, 15) | +2.5 (12, 7) | +2 (11, 9) |
| Minions killed by champions | 504 | 37.25 | +2 (10, 9) | -7.5 (8, 12) | -81 (2, 18) |
| Retreats on a sighting | 351.5 | 27.5 | -2 (9, 11) | -19.5 (6, 14) | -28 (3, 17) |
| Gank orders | 7 | 3 | -0.5 (8, 10) | +0.5 (10, 8) | -0.5 (7, 10) |

At 0.25 s every paired median is inside the noise, and the most lopsided seed counts are camp clears, 17 higher, and `FIGHT` orders, 15 lower. At 0.5 s blue's minion gold is 330 lower, 6.7 percent of 4,890, in 14 of 20 seeds against a noise of 215. Camp clears are 7 higher in 16 seeds, beyond their noise of 5.75. Retreats on a sighting are 19.5 fewer in 14, inside the noise, and so is every other measure. At 1.0 s minion gold falls by 942 on blue in 19 of 20 seeds and by 557 on red in 16, minions killed by champions by 81 in 18, retreats by 28 in 17, and red's gold by 1,313 in 14, and camp clears are 3 higher in 16. The tick changes the kernel's fidelity, and at 0.5 s the integrated outcomes stay near those of 0.125 s.

**Decision interval, with a 0.5 s tick.** The reference is a decision every 2 s.

| Measure | Median at 2 s | Noise | 1 s | 5 s |
| --- | --- | --- | --- | --- |
| Gold, blue | 27,644 | 2,656 | -1,423 (6, 14) | +2,493 (18, 2) |
| Gold, red | 28,489 | 1,782 | -1,920 (3, 17) | +2,017 (13, 7) |
| XP, blue | 35,093 | 3,235 | -1,248 (8, 12) | +1,979 (15, 5) |
| XP, red | 36,125 | 2,092 | -2,081 (6, 14) | +371 (13, 7) |
| Minion gold, blue | 4,710 | 521 | +41 (10, 10) | -671 (0, 20) |
| Minion gold, red | 4,775 | 471 | -17 (9, 11) | -810 (2, 18) |
| Tower health, blue | 48,325 | 4,503 | +517 (10, 10) | -130 (10, 10) |
| Tower health, red | 48,698 | 5,642 | +1,741 (13, 7) | -116 (10, 10) |
| Kills | 31 | 6.5 | -10 (1, 18) | +15 (20, 0) |
| Camp clears | 62 | 4.75 | 0 (9, 9) | +1 (11, 9) |
| Recalls ended | 66 | 5.75 | +11 (18, 2) | -20.5 (0, 20) |
| Wards placed | 52 | 3.75 | 0 (7, 9) | +0.5 (10, 9) |
| `FIGHT` orders | 86.5 | 6.75 | +4.5 (14, 6) | -19 (0, 20) |
| Minions killed by champions | 486 | 47.25 | -6 (9, 11) | -60.5 (1, 19) |
| Retreats on a sighting | 328.5 | 56.5 | +279.5 (20, 0) | -189 (0, 20) |
| Gank orders | 7 | 4.25 | +1.5 (13, 4) | -5 (0, 19) |

A decision every 1 s gives 10 fewer kills in 18 of 20 seeds, 11 more recalls in 18, less gold on both teams, and 279.5 more retreats on a sighting in every seed, because more decisions issue more new retreat orders. A decision every 5 s gives 15 more kills and 20.5 fewer recalls, 19 fewer `FIGHT` orders, and 189 fewer retreats in every seed, 5 fewer gank orders in 19, and less minion gold on both teams, 671 on blue in every seed and 810 on red in 18. Total gold still rises, by 2,493 on blue and 2,017 on red, with the extra kills (Inference). The decision interval changes what the scripted policies do. At 5 s they react later, and more champions die (Inference). The interval is a property of the agent's reaction time, not of the kernel.

### 10.4 The throughput gate

M7 section 10.4 sets a gate of 300 simulated seconds per wall second for the integrated game on one process. `kernel.json` measures it with the scripted policies on both teams for 15 game minutes from seed 0, with 7 runs per clock and the clocks alternating run by run. Every run of a clock does the same work, and the script asserts it. The machine was idle except for the owner's own collector of two processes (Reported, decision trail).

| Clock | Simulated s per wall s, median [range] | Gate | Work in each run |
| --- | --- | --- | --- |
| Tick 0.5 s, a decision every 2 s | 476 [447 to 490] | Passes | 1,072 minion deaths, 48 camp deaths, 28 champion deaths, 52 recalls, 37 wards placed, 1,800 ticks |
| Tick 0.5 s, a decision every 1 s | 428 [373 to 436] | Passes | 1,067, 50, 19, 63, 40, and 1,800 |
| Tick 0.25 s, a decision every 2 s | 268 [264 to 270] | Fails by 11 percent | 1,067, 50, 26, 57, 37, and 3,600 |

At 0.25 s the rate is 0.56 of the rate at 0.5 s. Twice the ticks cost a little less than twice the time, because the work done once per decision does not double (Inference). The profile of the integrated game gives the lanes 47.6 percent of the time, team memory 23.5, lane inputs 7.2, the observation 6.7, movement 5.1, `World._settle` 4.4, and the scripted policies 2.6. In the sweep of section 10.3, with the referee on and 8 games at a time on a loaded machine, a game of 1,200 s took a median of 21.7 s of wall time at 0.125 s, 11.7 s at 0.25 s, 6.1 s at 0.5 s, and 3.6 s at 1.0 s, and 9.5 s and 4.2 s with a decision every 1 s and every 5 s.

### 10.5 The clock that C7 keeps

C7 keeps the starting values of M7 section 5.2, a 0.5 s tick and a decision every 2 s, for throughput. Fidelity does not confirm them. The reasons follow.

1. A tick of 0.25 s fails the gate, at 268 against 300.
2. The integrated outcomes do not choose between 0.25 s and 0.5 s. At 0.5 s blue's minion gold is 7 percent lower than at 0.125 s, in 14 of 20 seeds, and camp clears are 7 higher, in 16. At 0.25 s camp clears are 5 higher, in 17, and `FIGHT` orders 3 fewer, in 15. The paired medians are compared with the spread across seeds, which pairing removes, so the sign counts are the better guide, and they are as lopsided at 0.25 s as at 0.5 s.
3. Wave timings favour 0.25 s. Per case, over 3 seeds, the median shift of a first crash from 0.125 s is 8.7 s at 0.5 s on blue, against 0.5 s at 0.25 s (section 5.5). Blue's mean first crash is 42.3, 41.7, 56.3, and 50.8 s at the four ticks, so 0.5 s is the worst tick for blue, and nothing explains that yet (Unresolved). Red's is monotone. Wave verdicts flip at every tick, 0.125 s against 0.25 s among them, so no affordable tick makes every-seed wave verdicts stable.
4. The decision interval is the agent's reaction time. A decision every 5 s moves kills, recalls, and `FIGHT` orders in all 20 seeds, and one every 1 s moves kills and recalls in 18 of 20. So each experiment must fix the interval and report it, and 2 s is the middle of the tested range.

A wave study that needs converged timings should run at 0.25 s or 0.125 s, which took about 1.9 and 3.6 times the wall time of 0.5 s in the sweep. The choice is to be revisited once the lanes and team memory are faster. A gain of about 12 percent would put 0.25 s over the gate. The gate leaves out the flat encoding that a learner reads, which the independent review measured at about 8 percent of the wall time (Reported).

## 11. Assumptions, internal correctness, and real-game validation

**Assumed.** Nothing has checked these against the game.

- Every champion number: the five capability profiles, level growth of 8 percent, the 15 placeholder upgrades, camp damage rates, and the numbers of section 8.
- The mana that area damage costs per second (`area_mana_s`), the mana regeneration (`mana_regen`), and the target that a full bar pays for pushing five or six waves (section 8.1).
- Lateral slots after the first wave, the hold line 300 units outside tower range, the stand-off of 550 units, and that a champion that stepped aside hits nothing.
- That a cancelled cast starts again and a missile to a dead target is lost. That tower shots and champion hits are instant. A missile on its way to a champion lands even if the champion steps aside.
- That red's minions walk the game's one polyline per lane reversed.
- The roam cap of 90 s and the refill of 0.25, and the end of assignments at 14:00 or with an outer tower.
- The straight-line decay of Homeguard, the leash of 800 units, straight-line camp scaling, and the Scuttler's timer window.
- The pursuit lead of one seen step along a lane, and no lead off the lanes (section 3.2).
- Sight along a lane by the lane coordinate, the 1,500 units of a remembered wave, the 18 ward spots with the 4 on the river edges, the start charge, and the straight lines of ward duration and recharge.
- Every threshold of the C7 policies, among them retreat below 30 percent health, leave a fight below 40, leave the fountain at 90, trade at 60, gank a laner below 60 from 70, the radii of 1,400, 1,800, 2,500, and 3,500 units, the first ward at 75 s, and the push after 600 s (section 10.1).
- The jungle paths and the sight terrain of M7 section 5.1, unchanged.

**Implementation correctness.** A test in this repository shows each of these, and a mutation run shows that the test can fail.

- The kernel contracts of section 3.3, the lane rules of section 4.1, the ledger, and the criteria of sections 6.3, 7.3, 8.3, 9.4, and 10.2.
- The port of M7's lane (section 5.1).
- `pytest -q tests` runs 683 kernel tests, and all pass. The whole suite, with the wave tests of `experiments/m8/waves`, gives 784 passed and 5 expected failures. The expected failures are M7's known prototype defect and the four wave bars of section 5.3. The mutation runner breaks the code in 278 ways, and the tests catch all 278.

This is correctness inside the simulator. It says that the code does what this document says, and nothing about strategy or the real game.

**Strategic validation.** The scripted policies beat random legal actions on gold plus XP at 15:00 in 50 of 50 seeds on each side, and in their own games they clear camps, ward, recall, fight, gank, retreat on sightings, and siege (section 10.2). That is a sanity check that the mechanics respond to decisions. It is not evidence of good strategy. The policies are hand-written, every threshold is Assumed, and they play against themselves or against random actions. The wave capabilities that the owner requires remain mostly negative (section 2).

**Throughput.** One process runs a 600 s game of random legal actions at 531 simulated seconds per wall second [501 to 554, 7 runs], scripted farming at 519 [482 to 525], and scripted farming with jungling at 516 [497 to 521] (`kernel.json`). Campaign 3 measured 543, 523, and 520. That is within the machine's noise of about 7 percent, so this campaign did not slow the kernel (Inference). Campaign 2 measured 620, 573, and 539, before C6. The lanes take 48.3 percent of a farming game, where they took 50.2, team memory 22.8 percent, where it took 19.0, lane inputs 8.8, movement 7.0, and the observation 6.9. Team memory grew with tower memory and `was` (Inference). The integrated game passes M7's gate at 476 (section 10.4). A snapshot at 600 s is 25,412 bytes pickled, where it was 24,650.

**Real-game validation.** Nothing. Constants are Sourced, which means read from a document or a data file, not measured. The first real-game validation that M8 needs is still the three measurements of section 5.8. Until wave fidelity is settled, any conclusion that the simulator supports about recall timing, denial, or gank opportunities is provisional, because each depends on where a wave is and how long it stays there.

## 12. Requirements kept for later checkpoints

| For | Requirement |
| --- | --- |
| C8 | The scenario loader, the comparison harness, and the complete hidden-state hypothesis generator of M7 section 9.3 with its three acceptance tests. Nothing of the generator exists in `riftgame`. |
| M9 | Champion numbers, mana costs and regeneration, armor in `damage`, movement-speed soft caps, and whether purchase thresholds change recall timing. |
| M11 | Wards that can be seen and cleared, Control Wards, and sweeping. |
| Open, C2 | Wave fidelity (section 2). The real-game measurements of section 5.8. The one-way drift of an untouched side lane, traced and not removed (section 4.2). A tick, or a form of verdict, at which the wave results are stable (section 5.5). |
| Open, lane | Unit collision in a lane with width. The first wave's indifference to champions and its ghosting, which matter to none of the cases of section 5.4 (section 5.7). The retarget cadence. The caster's acquisition range. Tower shot timing. |
| Open, pursuit | A lead off the lanes, and the one tick of reaction lag when a visible target turns to flee (section 3.2). |
| Open, C6 | Sight along a lane by the straight line, and minions that reveal other lanes' minions inside a base. A scaled encoding with a stable layout. |
| Next kernel change | The docstring of `LaneSim.front_tower`, which still says that only the front tower can fight (section 4.1). |

## 13. How to rerun the evidence

Every command starts with `.venv/Scripts/python.exe` from the repository root (M7 section 13 has the setup).

| Command | What it shows | What it writes |
| --- | --- | --- |
| `-m pytest -q` | Every test of M7 and M8 | Nothing |
| `-m experiments.m8.waves.capabilities` | Stacking, holding from the first and the third wave, and bouncing through the action table with the plan on each team, the diagnostics, and the tick and decision-interval sweeps. About 70 minutes on 8 processes. | `experiments/m8/waves/results/capabilities.json` |
| `-m experiments.m8.waves.capabilities --report` | The counts and rows of `capabilities.json` that section 5 quotes, per team. A few seconds. | Nothing |
| `-m experiments.m8.waves.investigate` | The lane without champions: fights, arrivals, attack timing counters, the untouched lanes, the bend sweep with its pairs and spawn shifts, the drift trace, the level lead. About 4 minutes. | `experiments/m8/waves/results/investigation.json` |
| `-m experiments.m8.waves.m7_tests` | M7's cases and verdicts on the M8 lane, the port check, M7's tick sweep. About 5 minutes. | `experiments/m8/waves/results/m7_tests_on_m8_lane.json` |
| `-m experiments.m8.waves.incentives` | The incentive screen. About 3 minutes. | `experiments/m8/waves/results/incentives.json` |
| `-m experiments.m8.integrated` | The C7 games of section 10: the soak, the baseline against random legal actions, the tower falls of those two, the three replays, and the tick and decision-interval sweeps. Name `soak`, `baseline`, `replays`, or `sweep` to run some of them. The tower falls are computed whenever the file holds both the soak and the baseline. About 7 minutes on 8 processes. | `experiments/m8/results/integrated.json` |
| `-m experiments.m8.waves.trace "S0 fight 6v6" "m8 lane" 0 0.5 0 100` | A tick-level trace of one M7 case | Nothing |
| `-m experiments.m8.recall` | Round trips from the outer towers | `experiments/m8/results/recall.json` |
| `-m experiments.m8.jungle` | The scripted jungler's first clear and its sweep. About 1 minute. | `experiments/m8/results/jungle.json` |
| `-m experiments.m8.combat` | The fight scenarios of M7 section 5.9 on the M8 kernel | `experiments/m8/results/combat.json` |
| `-m experiments.m8.vision` | The sizes of the two leak comparisons, and how often a team sees each enemy and each enemy wave. Under a minute. | `experiments/m8/results/vision.json` |
| `-m experiments.m8.kernel` | The kernel measurements and the C7 throughput gate of section 10.4. Run it on an otherwise idle machine. | `experiments/m8/results/kernel.json` |
| `-m experiments.m8.mutations` | Breaks the code in a temporary copy and counts the tests that notice | Nothing |
| `-m experiments.m8.provenance` | Whether each of the ten M8 results files still matches the working tree | Nothing |
| `-m experiments.m7.provenance` | The same for M7. All five files stay current. | Nothing |
