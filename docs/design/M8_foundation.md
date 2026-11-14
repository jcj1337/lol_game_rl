# M8 foundation

**Status.** Five campaigns have run. Checkpoints C1 (kernel base), C3 (recall and purchases), C4 (jungle), C5 (combat and death), and C6 (vision, memory, and wards) are built and pass the criteria that M7 wrote for them. C7 (integrated games) meets M7's C7 row at the research clock apart from throughput, which section 10.4 reports at that clock. C8 (scenarios and the comparison harness) is built, and section 11.4 maps each criterion of M7's C8 row to its test. C2 (lanes and economy) is built and is not complete. The research clock is now a 0.25 s tick with a decision every 2 s (section 10.5). At that clock reinforcements accumulate in 0 of 48 settings with the plan on blue and in 1 with it on red, a hold is sustained in 6 of 64 on blue and 10 on red, and single wave verdicts still flip with the tick (section 2). C8's four scenarios give one uncertain ranking and three stable trade-offs, so no scenario names a best option, and C8 makes no recommendation (section 11). Nothing was trained. [Handoff 005](../../handoff/005_m8_c1_c2.md) reports the first campaign, [handoff 006](../../handoff/006_m8_c2_corrections_c3_c5.md) the second, [handoff 007](../../handoff/007_m8_corrections_c6.md) the third, and [handoff 008](../../handoff/008_m8_c7.md) the fourth. The decision trail of the fifth is [`009_m8_c8_decisions.tsv`](../../handoff/009_m8_c8_decisions.tsv).

**Date.** 2026-11-13.

**Builds on.** [`M7_architecture.md`](M7_architecture.md). This document does not repeat M7. It names the M7 section that a piece of M8 implements, and it states every place where M8 departs from M7.

**Evidence labels.** The labels are M7's. **Tested** names a test or a script in this repository. **Sourced** comes from the reference patch research. **Assumed** is a design choice or a placeholder number. **Reported** has no evidence in the repository. **Inference** is a conclusion drawn from tested facts. **Unresolved** marks a known limit.

## 1. Summary

- The kernel of M7 section 5 exists as reusable code in `riftgame/`: ten champions on the full map, a fixed tick with a separate decision interval, intents that end with an outcome, the role duty state, an observation boundary, snapshots, replays, and an invariant checker (section 3). Since the third campaign it also has team sight from every source of M7 section 6.1, team memory of camps, enemy champions, and enemy waves, the full observation with a flat encoding, and wards (section 9). Since the fourth, every champion picks where it walks from one state before the move step, and a fighter reads only its team's record of its target. Since the fifth, a fighter leads a target that steps away from it on and off the lanes, so a faster fighter closes by its speed edge on every tick (section 3.2).
- One `LaneSim` class runs all three lanes. Every range inside a lane is the straight line on the map, minion attacks have the cast times and missile speeds of the game's data files, and a `LANE` action names what the champion hits and where it stands. The third campaign moved the M8 lane onto a map file of its own, which traces each side-lane corner with the game's four waypoints, after a test showed that one bend off the centre tips an untouched lane. The fourth added a rule that stops a minion at a standing enemy tower. The fifth found three places where a minion took a target or marched only at the start of a tick, and three rules now do both inside the tick, so the untouched first-wave fight kills the same minions at the same times, within 0.02 s, at four tick lengths (sections 4.1 and 5.5).
- Every wave plan reads its champion's observation and picks entries of the action table in a full world, once with the plan on blue and once on red. Each result stands beside a laner on its fountain, a laner under its tower, and a lane that nobody touches. At the research clock a plan accumulates reinforcements in 0 of 48 settings on blue and 1 on red, and in none against an opponent that last-hits. A hold keeps a larger wave out of the tower's range for three wave cycles in 6 of 64 settings on blue and 10 on red from the first wave, and in 1 and 0 of 32 from the third. After a crash the front comes back before an untouched lane's front in 7 of 24 cases on blue and 16 on red (section 5.4).
- C2 is still not complete. No hold plan lasts five wave cycles in every seed on either team. Per case, crash sizes and crash times move more across tick lengths from 0.125 s to 1.0 s than across seeds in most cases on both teams, and verdicts flip even between 0.125 s and 0.25 s. The in-tick fixes removed the peak of blue's first-crash times at 0.5 s and did not make the verdicts stable (section 5.5).
- The acceptance criteria for waves keep the form of campaign 2's second revision and stay provisional. Four strict expected failures keep the unmet bars in view (section 5.3). Four more are regression pins of campaign 4 that no longer hold at the research clock. No threshold changed (section 4.6).
- Recall, fountain, purchases, and Homeguard (C3), camps, Scuttlers, shrine sight, and camp timers (C4), and per-tick fights, towers against champions, death, and kill rewards (C5) are built behind the interfaces of M7 section 5.11. One attack credit pays for every class of target. The area damage of `push` and the lockdown are separate abilities that cost mana. A scripted fighter that chases under a lethal tower makes a policy mistake, which a tower rule of the policy now keeps apart from movement (sections 6 to 8).
- C6 passes every criterion of M7's C6 row. In 32 worlds, changing everything hidden from a team changes none of its observations, encodings, or masks, and its champions act the same until something is revealed. Changing the private fields of the enemies that a team sees, their intents among them, changes none of its observations and none of its moves. That closes the leak that handoff 007 left open. Team memory now keeps enemy tower health and enemy upgrades (section 9).
- At the research clock C7 meets every criterion of M7's C7 row apart from throughput. Scripted policies for all ten seats play 50 games of 20 minutes with no invariant error and no fault that a referee finds in the event log. They beat a team of random legal actions on gold plus XP at 15:00 in 50 of 50 seeds on each side. The throughput gate at the research clock gives 267 [265 to 269] simulated seconds per wall second against M7's 300, so C7 fails it by 11 percent, as in campaign 4. A 0.5 s tick passes with 467. The clock was chosen on fidelity, not on throughput (section 10).
- C8 is built: an information state, a hypothesis generator, scenario recipes and saved scenarios, a refinement of one state to a finer clock, and a comparison harness with two continuation styles. Four scenarios of M7 section 9.5 run under both styles. One ranking is uncertain, by style and tick, and three are trade-offs at both research ticks. Half of the 14 relations of an alternative to the baseline are uncertain, depending on the style, the hypothesis, or the tick. C8 reports that uncertainty and makes no recommendation. These are simulator comparisons, not calibrated advice or win probabilities (section 11).
- Nothing is validated against the real game. Every champion number is a placeholder. Conclusions about recall timing, denial, and gank opportunities are provisional while wave fidelity is open (section 12).

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
- A profile of team memory before the gate (007/R4). It took 23.5 percent of the integrated game (handoff 008, F11).

**Campaign 5, 2026-11-13.** This campaign fixed the pursuit that handoff 008 left open, diagnosed the tick dependence of the wave verdicts, moved the research clock, and built C8. The decision trail is [`009_m8_c8_decisions.tsv`](../../handoff/009_m8_c8_decisions.tsv).

| Phase | Work | Acceptance | State |
| --- | --- | --- | --- |
| T0 Ground | Read the documents, handoff 008, and the kernel. Capture the baseline. | Every M8 and M7 results file current at commit `2a503e2` (decision trail). | Done |
| T1 Pursuit | A fighter leads a target that steps away from it, on a lane and along an edge off the lanes, and stops short of the led place by a reach that keeps a slowed target in range. A chase under a lethal tower is a mistake of the scripted policy, and a tower rule of the policy handles it. | The pursuit tests of section 3.2 on a lane, a jungle path, and a base edge. The private-field tests of section 9.4 still pass. | Done |
| T2 Timing | Diagnose the tick dependence of the wave verdicts before adding mechanics or tuning values. Three in-tick lane rules. Probes and traces as tools. | The untouched first-wave fight kills the same minions at the same times at four ticks. The port check still gives 998 of 998. | Done (section 5.5) |
| T3 Clock | `Config()` moves to a 0.25 s tick with a decision every 2 s. Kernel tests state their own clock. Every experiment holds the decision interval at 2 s while it compares ticks. | The reasons of section 10.5. | Done |
| T4 C8 information and hypotheses | `riftgame/info.py`, `riftgame/hypotheses.py`, and `vision.remember_team`. | The three tests of M7 section 9.3. | Done |
| T5 C8 scenarios and comparisons | `riftgame/scenario.py`, `riftgame/clock.py`, `riftgame/compare.py`, two continuation styles, and `experiments/m8/c8.py` with four scenarios. | The criteria of section 11.4. | Done |
| T6 Evidence | Rerun every results file at the research clock, the mutation runner, and the suite. | Every number comes from a current results file or carries the label Reported. | Done. Section 12 has the suite, the mutation run, and provenance. |

**What campaign 5 closed from handoff 008.**

- The pursuit lag (008/Q2). A faster fighter recovers contact after a gap or a slow ends, on a lane, a jungle path, and a base edge (section 3.2).
- A profile of the lanes and team memory (008/R1). Section 10.4 reports it.
- The docstring of `LaneSim.front_tower` (008/R2). It now says that every standing tower shoots (section 4.1).
- The decision interval in experiments that compare (008/R3). Every tick sweep holds a decision every 2 s (sections 5.5 and 10.3).
- C8's criteria against the new memory fields (008/R4). `info.FIELDS` classifies tower memory with its age, enemy upgrades, and `was` (section 11.1).
- The clock (008/D1). A 0.25 s tick is the research clock, chosen on fidelity (section 10.5).

**Still open.** Wave fidelity, below. The drift of an untouched top lane, which since campaign 5 goes toward either half by seed, and the drift of a lane with no bend at all, which is not traced (section 4.2). The tick sensitivity of the wave verdicts, which the in-tick fixes reduced in crash times and did not remove (section 5.5). A champion's walk, which the lane takes from the front at the start of the tick (section 5.5). The first wave's indifference to champions and its ghosting, unit collision, and the real-game measurements of section 5.8. One tick of reaction lag when a visible target turns to flee (section 3.2). Handoff 008's Q1, Q3, and Q4 (section 13).

**C2 is not complete.** The owner requires freezing, slow pushing, crashing, and bouncing as capabilities, and C2 may not be called complete while one is unresolved. A crash works. The other three are unresolved. Every count below is at the research clock, a 0.25 s tick with a decision every 2 s, once with the plan on blue and once with it on red. The two runs of a setting differ only in which team the plan plays and so in which side of the map it starts from. The counts are not averaged.

1. **Slow push.** A plan accumulates reinforcements in 0 of 48 settings on blue and 1 on red. On red it is top at level 1 from its own tower against an absent opponent, with 11 minions [10 to 11] under `thin 2, then last hit`. No plan accumulates against an opponent that last-hits, on either team. A thinning plan delays the first crash in 45 of 48 settings on blue, 44 on red, and 42 on both. The slow-push drill brings 7 minions on both teams, where a hard push brings 9.
2. **Freeze.** A hold is sustained for three wave cycles from the first wave in 6 of 64 settings on blue and 10 on red, and the same plan sustains on both teams in 3. Those three are mid at level 1 against 2 surplus casters and an opponent that last-hits, mid at level 1 against 3 and no opponent, and the carry alone at level 3 against 3 and an opponent that last-hits. From the third wave it is 1 of 32 on blue and 0 on red. Some hold plan lasts four cycles in every seed in 1 setting on each team, and none lasts five. From the first wave no plan holds for a level 6 mid laner on either team.
3. **Bounce.** After a crash the front comes back in every run in 21 of 24 cases on each team, and before the untouched lane's front in every run in 7 on blue and 16 on red. The difference is in top at levels 3 and 6 and in bot, where with the plan on blue the untouched lane gets back first in some run under every plan. After a hard push of the first wave mid comes back in 1 of 5 runs on both teams.
4. **The lane itself.** A verdict that must hold in every seed of one setting can flip with the tick length and with the decision interval, on both teams, after the in-tick fixes as before them (section 5.5). An untouched top lane leaves the centre in every seed of 600 s, toward red's half in 6 of 12 and toward blue's in 6, after its two sides first differ in one blow at 72.0 s (section 4.2).

## 3. Kernel base (C1)

### 3.1 What exists

| Module | Owns | Checkpoint |
| --- | --- | --- |
| [`world.py`](../../riftgame/world.py) | The state, the eight-step tick of M7 section 5.2, `Config`, snapshots, the digest, the invariant checker, the ward limit per champion | C1, C6 |
| [`champions.py`](../../riftgame/champions.py) | Seats, placeholder capability and progressions, the action table, intents with a rule per kind, the duty state, the fountain's rules, the attack credit (`attack_worth`), the front a team knows (`known_front`), ward charges | C1, C3, C5, C6 |
| [`vision.py`](../../riftgame/vision.py) | `observe`, `observe_team`, `legal_mask`, `encode`, team sight from every source, team memory of camps, enemy champions, enemy waves, and enemy towers | C1, C4, C5, C6 |
| [`harness.py`](../../riftgame/harness.py) | The policy interface, scripted policies that read only the observation, replays. `tick` takes one policy or one per seat. | C1, C4, C5, C7 |
| [`policies.py`](../../riftgame/policies.py) | Scripted policies for all ten seats, built per side and per style, that read only the observation (sections 10.1 and 11.1) | C7, C8 |
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
| Every champion picks where it walks from the state at the start of the move step, and then all move at once. A fighter reads only its team's record of its target, never where the target is now or what it intends. If the team saw the target on this tick and on the one before (`EnemyMemory.was`), and that step took the target farther from the fighter, the fighter heads for the place where one more such step puts the target. On a lane that place is along the lane coordinate, and off the lanes it is along the target's edge, in both cases no further than the end of the lane or the edge. The fighter stops short of it by `max(0, _lead_short(reach, step) - cut)`, where `_lead_short(reach, step) = min(reach, max(reach - step, 2 step - reach))` and `cut` is the part of the step that the end cut off (`champions._to_enemy`). Otherwise it closes to its range of the place where its team saw the target. A fighter therefore answers a visible target that turns to flee one tick late, and then closes by its speed edge on every tick. This replaces the order of M7 section 5.2, step 3, in which champions that do not pursue move first and pursuers after. | M7's order lets a fighter's walk depend on whether its target pursues, and an intent is private (handoff 007, F14). With one state no walk reads another champion's move on the tick, so neither the seat order nor an enemy's intent changes where anyone goes (Tested, `tests/test_pursuit.py`). Through campaign 4 the fighter stopped at its full range short of the led place, so a target that stepped steadily away moved one step after the aim was fixed, and a faster fighter ended every tick about one step short (handoff 008, Q2). The stop of `_lead_short` keeps in range a target that stops, turns back by its step, or steps up to twice as far, as one does when a slow ends, while its step is at most two thirds of the range (the function's docstring). On a lane, a jungle path, and a base edge, a faster fighter closes by its speed edge on every tick and then hits on every tick, a slower one falls behind by its deficit and stops hitting, a faster fighter in contact keeps a target that steps steadily away by 60 to 175 units in range on every tick, and a faster fighter keeps a slowed target in range on every tick after the slow ends (Tested, `test_a_faster_fighter_closes_by_its_speed_edge_on_every_tick_and_then_hits_on_every_tick`, `test_a_slower_fighter_falls_behind_by_its_speed_deficit_on_every_tick_and_stops_hitting`, `test_a_faster_fighter_in_contact_keeps_a_target_that_steps_steadily_away_in_range_on_every_tick`, `test_a_faster_fighter_keeps_a_slowed_target_in_range_on_every_tick_after_the_slow_ends`). A fighter heads for its range of where its team saw a target that walks toward it, and does not lead it (Tested, `test_a_fighter_heads_for_its_range_of_where_its_team_saw_a_target_that_walks_toward_it`). A led target that stops or turns back stays in range unless its step is longer than the range, and at a fork the fighter walks the same on every branch until its team sees which one the target took (Tested, `test_a_led_target_that_stops_or_turns_back_stays_in_range_unless_its_step_is_longer_than_the_range`, `test_at_a_fork_a_fighter_keeps_the_target_in_range_on_any_branch_and_walks_the_same_until_its_team_sees_which`). Campaign 4 wrote here that on the jungle paths a faster melee fighter kept a target with a step of up to 201 units without a lead. The test behind that claim let the fighter hit again only after the target had stopped, and campaign 5 restated it to assert the gap on every tick (Tested, `test_off_the_lanes_a_faster_melee_fighter_also_keeps_hitting_a_target_whose_step_is_longer_than_its_range`). The information boundary is unchanged. The lead reads only the team's record. |
| The research clock is a 0.25 s tick with a decision every 2 s (`Config` defaults `tick_s=0.25`, `decision_ticks=8`). Kernel tests that measure per-tick behaviour state their own clock, either a 0.5 s tick with 4 decision ticks or `EVERY_TICK` of `tests/worlds.py`, a 0.5 s tick with a decision on every tick. | M7 section 5.2 started from a 0.5 s tick and asked C7 to confirm or revise it. Section 10.5 gives the reasons for 0.25 s. |

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

**Measured, not criteria.** `kernel.json` holds the throughput of one process over 600 s games, and section 12 gives the figures. M7's gate of 300 simulated seconds per wall second is measured on the integrated game in section 10.4.

## 4. Lanes and economy (C2)

### 4.1 The lane model

`riftgame/lanes.py` holds one class, `LaneSim`. It owns a lane's minions, its six towers, and its wave clock, on the lane coordinate of M7 section 5.1. A champion enters a lane tick as a `ChampionInput`. Everything that leaves the lane is an event. The world applies the events (M7 section 5.11).

`LaneRules` names each optional rule. `M8_LANE` is the lane that M8 ships. `M7_LANE` switches off what M7 did not model and runs on M7's route graph, so that M7's results can be reproduced. Six fields are diagnostics and are off in both.

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
| `acquire_on_arrival`: a minion that stops walking inside a tick with nothing in reach takes a target at the moment it stops, and a minion with no target stops where a champion in its path comes within its stop range | Yes, new in campaign 5. Off in `M7_LANE`. | A numerical correction, so that the tick only samples the fight (section 5.5). Tested, `test_a_minion_that_stops_in_reach_inside_a_tick_attacks_from_the_moment_it_stops`, `test_a_caster_that_comes_upon_a_champion_in_its_path_stops_where_it_takes_it`. |
| `walk_on_loss`: a minion whose target dies inside a tick, and that finds no other in reach, walks on from the later of the death and the moment it stopped walking | Yes, new in campaign 5. Off in `M7_LANE`. | A numerical correction (section 5.5). A first version let a minion that was still walking when its target died walk that time twice, 37.45 units too far in 2 s, which the independent review found (Reported). Tested, `test_a_minion_whose_target_dies_inside_a_tick_walks_on_from_that_moment`, and at four ticks `test_a_minion_still_walking_toward_its_target_when_the_target_dies_walks_no_faster_than_its_speed`. |
| `march_to_standing`: a minion whose nearest enemy stands still walks all the way to it, and not at most half its gap to the enemy's lead walker | Yes, new in campaign 5. Off in `M7_LANE`. | A numerical correction (section 5.5). Tested, `test_a_minion_walks_all_the_way_to_a_standing_enemy_while_another_enemy_walks_up_behind_that_one`. |
| `melee_cap`: at most n melee minions on one target | Diagnostic, off | Section 5.5 |
| `minion_damage_scale`: scales minion blows on minions | Diagnostic, off | Section 5.5 |
| `free_cancel` and `missiles_turn`: a cancelled cast costs nothing, and a missile to a dead target lands on what its shooter can reach | Diagnostics, off | Section 5.5 |
| `detour_s`: a melee minion that turns to a new minion target loses this long before its cast | Diagnostic, off | Section 5.6 |
| `tie_by_set`: a minion that draws between equally near enemies keys the draw on the tied set, so the same tie gives the same choice however many ticks it lasts | Diagnostic, off, new in campaign 5 | Section 5.5 |

Campaign 5 fixed the docstring of `LaneSim.front_tower`, which said that only the front tower could fight. It now says that every standing tower shoots (handoff 008, R2).

The added constants live in a second ruleset file, [`patch_26_22_m8.toml`](../../riftgame/rulesets/patch_26_22_m8.toml), with the numbers of the hypothesis generator in its `[hypotheses]` section (section 11.1), and the M8 map in `map_summoners_rift_m8.toml`. `patch_26_22.toml`, `map_summoners_rift.toml`, `map.py`, `ruleset.py`, and `rng.py` stay byte-identical, because M7's results files record their hashes.

### 4.2 The rules that campaigns 2 and 3 added, the drift, and what the sources say

**Straight-line ranges.** M7 section 5.1 measures movement by the route and interaction by the straight line. Campaign 1 left every range inside a lane on the lane coordinate. On M7's route graph, two points 290 units either side of the top-lane corner are 580 units apart along the lane and 534 in a straight line. Campaign 2 first changed only the ranges between champions or towers and minions. That made things worse. A passive carry in bot lane took 568 damage in five minutes where it had taken 44, because a caster behind the corner counted enemy minions along the lane, found none in range, and turned on the champion that it measured by the straight line (Reported, a scratch run of campaign 2). One measure for every interaction removes the inconsistency. Acquisition, attack, tower, and call ranges all use the map coordinates of the two units. Only marching uses the lane coordinate (Tested, `tests/test_lanes.py`, two corner tests). The hold line, the stand-off, and the experiments' band and tower checks are still placed along the lane. Towers stand on straight stretches, so that differs from the straight line by 16 units at most (Reported by the review of campaign 2, on M7's graph).

**The corner, tested and replaced.** With straight-line ranges on M7's graph, an untouched top lane went to blue's half within 100 s in every seed. Handoff 006 put that down to the graph's one sharp corner node, from one comparison. Campaign 3 tested the diagnosis on top lane's length, towers, and spawn points with other shapes, over 12 seeds of 600 s (Tested, `investigate.py` section `bends`, and `test_a_bend_tips_an_untouched_lane_toward_its_own_side_and_a_bend_at_the_centre_or_no_bend_does_not`). One bend of 46 degrees 150 or 295 units off the centre tips the lane toward the bend's side at 97 s in every seed, and the mirrored bend tips it the other way. A bend of 10 or 20 degrees does the same as one of 46. So the cause of the early tip is a bend off the centre inside the first fight, not its sharpness. Through campaign 4 a lane with no bend, with one bend at the centre, or with a bend of 5 degrees never left the centre in 600 s. Since the in-tick rules of campaign 5 each leaves it later, in 6 to 12 of 12 seeds, toward either half, and never before 161 s (section 5.4). Within 150 s the lane with no bend and the lane with a bend at the centre stay at the centre (Tested, the same test, on 3 seeds). Section 5.4 has the table.

**Why a bend tips the lane** (Reported, one scratch trace recorded in the decision trail of campaign 3). With straight-line ranges a caster across the bend acquires its target one tick earlier and stops 1.2 units short of where it stops on a straight lane. On a straight lane later retargets sit exactly on a range threshold. Across the bend they fall outside it, the minion waits a tick before it walks, and the symmetric fight is no longer a draw. Campaign 3 tried a rule that let a minion acquire a target on arrival inside the tick, for this symptom. It left the tip at 97 s in 12 of 12 seeds on M7's graph and changed the first-wave fight by under 0.5 s at four tick lengths, so campaign 3 removed it (Reported). Campaign 5 kept such a rule, `acquire_on_arrival`, for another reason. It removes the quantisation of acquisition to the tick's start, which the four-tick test of the first-wave fight shows (section 5.5). It does not remove the tip on M7's graph, which still comes at 97 s in every seed (`investigation.json`, `bends`).

**The M8 map.** `map_summoners_rift_m8.toml` is M7's map file with the game's other three waypoints at each side-lane corner (reference rows A4b and A4c). M7's graph kept one of four, which made one bend of 46 degrees 295 units from where the waves meet and cut 98 units off top lane and 109 off bot (the map file's header). On the M8 map no bend of top lane between the outer towers turns more than about 21 degrees, and the bends nearest the centre are 319 units on blue's side and 669 on red's (`investigation.json`, `bends`). The added points are not collinear, so they change the lane's length and shape. Marching and champion walks use the route, and every range uses the straight line. `LaneRules.m7_map` keeps `M7_LANE` on M7's graph, so the port check still gives 998 of 998 (section 5.1).

With the M8 map an untouched lane keeps its front within 100 units of the centre for the first 150 s in all three lanes and every seed (Tested, `test_an_untouched_lane_keeps_its_front_at_the_centre_for_the_first_150_seconds`). Over 12 seeds of 600 s an untouched top lane first leaves the centre at a median of 263.25 s [187 to 339.5], where it leaves at 97 s on M7's graph, and it has 38 crashes where M7's graph has 64. Since campaign 5 the drift goes toward red's half in 6 seeds, at 187 to 188.5 s, and toward blue's half in 6, at 338 to 339.5 s. Through campaign 4 it went toward red's half in every seed, at 247 to 281 s. Every number of this section is from `investigation.json`, which runs the lane alone at a 0.5 s tick.

**What starts the drift, and what delays it** (Tested, `investigation.json`, `drift` and `bends`, 12 seeds of 600 s). In all 12 seeds an untouched top lane on the M8 map first differs from its mirror image at 72.0 s, where a blow lands with a different damage or at a different time. On the tick before, blue's casters stand 493.5 units from their targets by the straight line and red's 500.0, so blue's missiles fly 0.759 s and red's 0.769 s. The bend of 21 degrees 319 units on blue's side of the centre puts the difference there (Inference). Campaign 4 found the first difference at 70.0 s, with the same casters. On the M8 map mirrored about the lane's centre the two sides swap these numbers, the first difference also falls at 72.0 s, and each seed leaves toward the other half at about the same time, so blue's half comes first in 6 of 12 seeds, where in campaign 4 it came first in 12 of 12. With paths symmetric about the centre, where red walks the mirror of blue's polyline and spawns and keeps its towers where the mirror puts blue's, the front leaves the centre in 2 of 12 seeds, at 249 s. With no bend at all the two sides first differ at 122.5 s or later, in a target that a minion acquires, and the front leaves the centre in 6 of 12 seeds, late and toward either half. That lane is symmetric, so the keyed draws between tied targets separate the sides, not the geometry (Inference). The path from those draws to the drift is not traced (Unresolved).

The map's bends do not cancel each other. Its bend at 319 units alone, its two nearest bends, its four bends within 2,000 units of the centre, and all its bends on M7's length each tip the lane at 97 s in 12 of 12 seeds, as one bend of 46 degrees does. Two equal bends placed symmetrically about the centre do not tip it at 97 s. They leave the centre later in 7 and 6 of 12 seeds, toward either half. Where the waves meet delays the drift on the M8 map. The M8 polyline makes each wave's walk to the centre 49.4 units longer than on M7's graph. With both spawn points moved 49.4 units nearer the centre, so that the walk is M7's, the M8 map tips at 97 s in 12 of 12 seeds. M7's graph with spawn points 49.4 units further out also tips at 97 s, where in campaign 4 it first tipped at 133 s. Spawn shifts of 10 to 100 units move the median first departure anywhere from 97 s to 349.25 s. The tick moves it to 76.875 s at 0.125 s, toward red's half in 12 of 12 seeds, to 276.5 s at 0.25 s, toward blue's in 11, and to 120 s at 1.0 s, toward red's in 12. So the M8 map moves the meeting and does not remove the asymmetry, and a lane this near balance turns a hundredth of a second into a drift whose side depends on the seed and the tick (Inference). On the owner's instruction no symmetry was forced and no noise was added. The game's file has one polyline per lane, linked from the blue barracks. That red's minions walk it reversed is Assumed.

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
| The tick sweep of risk RK2 is reported | 11 of 17 of M7's metrics within 10 percent at 0.5 s, and the world-driven verdicts and measures per case at ticks of 0.125, 0.25, 0.5, and 1.0 s on both teams | Sections 5.5 and 5.9 |

C2 stays open. These rows are what M7 asked of C2. The owner's requirement of freezing, slow pushing, and bouncing as capabilities is not met (section 2).

**Four regression pins, now expected failures.** Campaign 4 pinned four every-seed results of section 5.4 on single settings as plain tests, with the plan on blue, at a 0.5 s tick. None holds at the research clock. Each is now a strict expected failure whose reason names handoff 009 (Tested, [`test_behaviours.py`](../../experiments/m8/waves/test_behaviours.py)).

| Test | What it pinned | At the research clock |
| --- | --- | --- |
| `test_a_thinning_plan_brings_three_minions_from_each_of_two_waves_and_more_than_a_push_an_empty_lane_or_a_laner_under_its_tower` | The carry alone at level 3 accumulates from its own tower under `thin 3, then last hit` | No plan accumulates in that setting |
| `test_a_champion_that_holds_and_thins_keeps_a_larger_wave_out_of_its_towers_range_for_three_wave_cycles` | `hold, thin over 1` sustains control for mid at level 1 against 2 surplus casters and an opponent that last-hits | It does not. `hold, thin` sustains there, on both teams. |
| `test_a_hold_is_also_sustained_when_the_surplus_arrives_with_the_third_wave` | `hold, thin` sustains control from the third wave for mid at level 3 against 3 surplus casters and an opponent that last-hits | It does not |
| `test_after_a_crash_of_a_thinned_wave_mid_lane_comes_back_past_the_centre_before_an_untouched_lane_does`, for mid at level 3 | After a crash of a thinned wave, mid at level 3 comes back past the centre before the untouched lane in every run | The untouched lane gets back first in some run. The same test for mid at level 1 still passes. |

The timing delegate ran the lane of campaign 4 at a 0.25 s tick and found three of the four already failing there, so three of the pins recorded results that held only at a 0.5 s tick (Reported, decision trail). The pins stay as expected failures. They were not deleted, and no new setting was searched for that passes. No threshold of section 5.3 changed.

## 5. Wave behaviour through the action table

Every number in this section is at the research clock, a 0.25 s tick with a decision every 2 s, over 5 seeds unless it says otherwise. Campaign 4 counted at a 0.5 s tick, and a campaign 4 number appears only where the text compares the two. `investigation.json` runs the lane alone at a 0.5 s tick, as before. Since campaign 4 every stacking, holding, and bounce case runs twice, with the plan on blue and with the plan on red, and the two are reported apart. A range in brackets is the minimum and maximum across seeds. The results files are in [`experiments/m8/waves/results/`](../../experiments/m8/waves/results/). `python -m experiments.m8.waves.capabilities --report` prints the counts of `capabilities.json` that this section quotes.

### 5.1 The port still reproduces M7

[`m7_tests.py`](../../experiments/m8/waves/m7_tests.py) runs M7's 103 wave cases on the lane. With `M7_LANE`, which runs on M7's route graph, and M7's draw key, 998 of 998 metrics equal M7's results file (Tested, `port_check_with_m7_draw_key`). In campaign 2 a separate check stepped the lane under M7's rules beside the lane of the commit before for 600 s on 3 seeds, and every minion's position and health agreed on every tick (Reported, that script is not kept).

### 5.2 How the experiments run now

[`agents.py`](../../experiments/m8/waves/agents.py) stages a full world of ten champions, and every champion starts on its fountain. A `Laner` puts the lane's champion of each team at its outer tower at a chosen level, the same on both teams, so that no team leads in level. The plan plays one team's laner and the opponent setting plays the other's. A plan is a function from what the laner's observation holds to a `LANE` action, called on decision ticks every 2 s. It reads the champion's own health and caster kills, and its lane as the team sees it: the team's minions within 1,500 units behind its lead, the enemy minions near the enemy lead while the team sees one, and whether the waves are in contact. The world does the rest: the walk, the stance, the hits, minion damage, death.

With the plan on blue the team does not see the enemy lead minion on a median of 7.0 percent of ticks in the stacking cases, 6.5 percent in holding from the first wave, and 7.0 percent from the third, and the largest share in one case is 61.5 percent. With the plan on red the shares are 7.0, 6.3, and 7.1 percent, and the largest is 62.1. Below 30 percent health a laner walks to its own outer tower with a `MOVE` and comes back above 60 percent. The staging sets a champion's level, place, and the clock at the start, and the holding cases add the surplus casters during the run. Nothing else is edited in a run.

**Two controls.** `absent` is a laner on its fountain. Its plan word `leave` is a `MOVE` to `own_fountain`. `under tower` is a laner that stands at its own outer tower and does nothing. There it gains XP, which feeds its team's level and so the pushing advantage from 3:30, and it may be hit. In campaign 2 `absent` stood at the tower, so it was the under-tower control under another name. The two now differ in XP in every seed of the test setting (Tested, `test_a_champion_under_its_tower_gains_xp_and_an_absent_one_gains_none_after_it_left`). In the wave counts they give the same held cycles in all 96 holding settings on both teams. Their largest crashes differ in some seed in 12 of 48 stacking settings on each team. Both stand beside every plan in stacking and holding. The untouched lane beside each bounce case has nobody near it.

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

The owner asked for criteria that keep the meaning of each capability: sustained wave control, reinforcement accumulation, delayed crashes, and bounce. A first revision in campaign 2 was too loose, and the independent review showed where (handoff 006, §3.5). The criteria below are the second revision. Campaigns 3 to 5 kept their form and every threshold, and they stay provisional. Campaign 3 changed only the lists of controls, because the old `absent` was not absent (section 5.2). Campaign 4 changed nothing in them and applies each to both teams apart. Campaign 5 changed nothing in them and applies them at the research clock. Each criterion compares a plan with a lane that nobody touches, because an untouched lane does not stand still (section 5.4).

| Capability | Old criterion | What is wrong with it | Criterion now |
| --- | --- | --- | --- |
| Crash | A hard push reaches the tower before the second enemy wave can. | Nothing. | Kept. |
| Delayed crash | A thinning plan reaches the tower later than a push, with 12 minions. | Two properties in one verdict. | Its own verdict: a thinning plan's first crash comes later than the push's in every seed. This is a weak property, since thinning is slower than pushing by construction. |
| Reinforcement accumulation | 12 or more minions near the lead at the first tick in tower range. | Twelve is two full waves of six. A wave with a siege minion has seven, a thinned wave has lost some of its own, and a crash can hold parts of three waves. A bar of exactly 12 calls a crash of 11 minions from three waves no stack. | In every seed the plan's largest crash holds, at its largest moment, at least three minions from each of two spawn waves, and more minions than the largest crash of a hard push, of a laner on its fountain, and of a laner under its tower in the same setting. The count of 12 is reported beside it. |
| Sustained wave control | The front stays within 1,500 units outside the tower's range for over half of 240 s, and both controls stay below half. | The band does not measure a hold. With no champion the front was in the band for 214 s of 240 against a last-hitting opponent in mid, while the enemy wave reached the tower in every cycle and dealt 445 damage to it. The control clause also blocked the test at three of five surplus sizes (handoff 005, F9). | A wave cycle of 30 s is held when the front is in the band for at least half of it and the enemy wave is never in the tower's range during it. A hold plan sustains control when, in every seed, the champion does not die, the first three cycles are held, and that is more cycles than a laner on its fountain, a laner under its tower, a laner that last-hits with its wave, or a laner that pushes holds in any seed. |
| Bounce | After a hard push of one wave, the contact point is back past the centre within 120 s, in every run, in mid and top. | One wave of six is the weakest crash. A lane that meets again exactly at the centre counted as not bounced without being named. And an untouched lane can drift to one side by itself, so a return proves nothing about the crash unless it beats that lane. | After a crash, the front comes back more than 100 units past the centre in every run, and in every run before the front of the same lane with no laner gets there. The crash is tried with one hard-pushed wave, with a thinned wave, and with a hard push after two last-hit waves. A lane that meets again within 100 units of the centre is called a reset. |

**What these criteria still choose.** Three cycles is 90 s, where M7's test asked for more than half of 240 s. No counterexample supports that cut. It is where the results have something to show. Some hold lasts one, two, three, and four cycles in every seed in 52, 35, 10, and 1 of 64 settings on blue and in 52, 39, 12, and 1 on red, and none lasts longer. Three minions per wave and 100 units are choices too. All are named constants in [`capabilities.py`](../../experiments/m8/waves/capabilities.py).

**Expected failures.** Four strict expected failures in [`test_behaviours.py`](../../experiments/m8/waves/test_behaviours.py) keep the unmet bars in view. Each asserts one of the bars below and fails, and the suite reports it if it starts to pass. Each bar is a strategic requirement of the owner, freezing or slow pushing, or a direct test of M7.

1. The slow-push drill of a level 1 top laner brings more minions than a hard push in every seed.
2. Some plan accumulates reinforcements in every seed against an opponent that last-hits.
3. A hold lasts all eight wave cycles of the 240 s run, as M7's freeze test asks.
4. A plan holds a first wave of 6:00 for a level 6 mid laner.

Section 4.6 lists four more, the regression pins of campaign 4 that fail at the research clock. Campaign 3 had six bars. Campaign 4 dropped two as requirements that ask for a particular result. "12 minions at the enemy tower" repeated the bar that this section replaced by three minions from each of two waves, and the count stays reported. "A mid bounce after a hard push of the first wave" would force one particular crash to bounce, where the lane resets by symmetric waves (section 5.4), and the owner asked that no criterion force every crash to bounce. Campaign 2 had eight, and two of those pass as plain tests since campaign 3.

### 5.4 Results

**An untouched lane first** (`investigation.json`, `untouched`, 300 s at a 0.5 s tick, no champion). Everything below is read against this.

| Lane | With the M8 lane | On M7's route graph | With ranges along the lane |
| --- | --- | --- | --- |
| Top | The front stands more than 100 units on red's half at 188.5 s [187 to 188.5], in 3 of 5 seeds. Blue's wave reaches red's outer tower in 2 seeds and red's reaches blue's in 1, with 8 minions at most. | The front is on blue's half at 97 s in 5 of 5 seeds. Red's wave reaches blue's outer tower twice in every seed, with 8 minions [8 to 9] at most. | The front leaves the centre in 3 of 5 seeds, at 186.5 s, toward blue's half in 2 and red's in 1. |
| Mid | The front leaves the centre toward red's half in 2 of 5 seeds, at 220 s. | The same | The same |
| Bot | The front leaves the centre in 1 of 5 seeds, at 224 s. | 3 of 5, at 187 s | 1 of 5, at 224 s |

**The bend sweep** (`investigation.json`, `bends`). An untouched lane with top lane's length, towers, and spawn points, the M8 lane rules, 12 seeds of 600 s at a 0.5 s tick. A crash is a wave at the enemy outer tower.

| Shape | Front on a half first, blue and red, of 12 | Leaves the centre, median | Crashes in the 12 runs, by blue's and by red's waves |
| --- | --- | --- | --- |
| No bend | 2 and 4 | 325 s [161 to 426.5], in 6 seeds | 10 and 4 |
| One bend of 46 degrees at the centre | 3 and 3 | 245 s [223.5 to 245], in 6 seeds | 14 and 12 |
| One bend of 5 degrees, 295 units on blue's side | 8 and 4 | 451.5 s [161 to 476.5] | 10 and 4 |
| One bend of 46 degrees, 295 or 150 units on blue's side | 12 and 0 | 97 s | 21 and 43, 24 and 38 |
| One bend of 46 degrees, 150 or 295 units on red's side | 0 and 12 | 97 s | 42 and 25, 48 and 26 |
| One bend of 10 or 20 degrees, 295 units on blue's side | 12 and 0 | 97 s | 31 and 38, 34 and 37 |
| M7's route graph | 12 and 0 | 97 s | 21 and 43 |
| The M8 map | 6 and 6 | 263.25 s [187 to 339.5] | 24 and 14 |
| The M8 map with ranges along the lane, or its length, towers, and spawn points with no bend | 3 and 3 | 186.5 s, in 6 seeds | 9 and 7 in each |
| The M8 map's bend 319 units on blue's side alone, its two nearest bends, its four bends within 2,000 units, or all its bends on M7's length | 12 and 0 | 97 s | 36 and 37 in each |
| The same two or four bends mirrored | 0 and 12 | 97 s | 42 and 29 in each |
| The M8 map's bend 669 units on red's side alone, or two equal bends placed symmetrically at 669 units | 2 and 4 | 325 s [161 to 426.5], in 6 seeds | 9 and 5, 8 and 5 |
| Two equal bends placed symmetrically at 319 units | 3 and 4 | 125.5 s [125.5 to 429.5], in 7 seeds | 19 and 14 |
| The M8 map mirrored about the lane's centre | 6 and 6 | 263.25 s [187 to 339.5] | 16 and 23 |
| Paths symmetric about the centre, with spawn points and towers mirrored too | 1 and 1 | 249 s, in 2 seeds | 2 and 2 |
| Red on the mirror of blue's polyline, with spawn points and towers as on the M8 map | 0 and 0 | Never | 0 and 0 |
| The M8 map with both spawn points 49.4 units nearer the centre, and M7's graph with them 49.4 units further out | 12 and 0, 12 and 0 | 97 s, 97 s | 30 and 40, 33 and 41 |
| The M8 map at a tick of 0.125, 0.25, and 1.0 s | 0 and 12, 11 and 1, 0 and 12 | 76.875 s, 276.5 s, 120 s | 25 and 31, 14 and 25, 38 and 29 |
| Mid on the M8 map, for comparison | 2 and 3 | 220 s, in 5 seeds | 8 and 10 |
| Bot on the M8 map, and on M7's route graph | 0 and 1, 3 and 3 | 224 s in 1 seed, 187 s in 6 | 2 and 1, 13 and 10 |

M7's graph gives exactly the numbers of one bend of 46 degrees 295 units on blue's side. The M8 map delays the first departure of top lane from 97 s to a median of 263.25 s and cuts its crashes from 64 to 38, against 18 in mid, which has no corner. Since campaign 5 one shape alone keeps the front at the centre for 600 s in every seed, red on the mirror of blue's polyline with the M8 map's spawn points and towers. Section 4.2 reads the rows.

**Accumulation and delay** (`capabilities.json`, `stacking`). Seven plans, a hard push, a laner on its fountain, and a laner under its tower. Three starts (first contact, the moment an enemy push reaches the laner's tower, and the meeting of the third waves), an opponent that is absent or last-hits, 8 champion settings: 48 settings in all, on each team.

| Result | Plan on blue | Plan on red |
| --- | --- | --- |
| Settings in which some plan accumulates reinforcements | 0 of 48 | 1 of 48. By start, 0, 1, and 0 of 16 from first contact, the own tower, and the third wave. None against an opponent that last-hits. |
| From the own tower | None. The largest crashes hold 9 minions as a median, under `last hit` for top at level 1 and under `thin 1, then last hit` for the carry alone at level 3, both against an absent opponent. Neither counts, because in some seed each holds 7, fewer than a control there. | Top, level 1, opponent absent. `thin 2, then last hit` brings 11 [10 to 11] of three waves, three from the second-largest wave, 76 s [76 to 77] after the plan starts. The hard push brings 8 [7 to 8] at 161.5 s, and a laner on its fountain or under its tower 8 [7 to 8]. `last hit` crashes 11 as a median there too and does not count, because in one seed its crash holds 8 with 2 from the second-largest wave. |
| From the third wave, and from first contact | None | None |
| Largest crash | 9, in the two settings above. With no laner the largest crash holds 8. No crash holds 12. | 11, in the top setting above. With no laner the largest crash holds 8. No crash holds 12. |
| The slow-push drill: top, level 1, from first contact, kill 3 casters, then last-hit | 7 minions of two waves, six and one, 37 s after contact. The hard push there crashes first with 5 at 17 s and brings 9 of two waves at 28.75 s. The drill does not accumulate. | 7 of two waves, six and one, at 37.25 s. The hard push crashes 5 at 17.25 s and 9 at 29.25 s. |
| Settings in which some thinning plan delays the first crash | 45 of 48: 16, 14, and 15 of 16 by start | 44 of 48: 16, 16, and 12. 42 delay on both teams. |
| Paired with a hard push, the largest crash of a plan in the same seed | Larger in every seed in 38 of 288 pairs of a setting and a plan, smaller in every seed in 88 | 36 and 112 |

**Holding from the first wave** (`capabilities.json`, `holding`). The experiment places 2, 3, 4, or 6 surplus enemy casters at the hold line when the laner's wave arrives, and the opponent is absent or last-hits: 64 settings on each team, 7 hold plans and 4 controls each, 240 s.

| Result | Plan on blue | Plan on red |
| --- | --- | --- |
| Settings in which some hold plan sustains control | 6 of 64 | 10 of 64. The same plan sustains on both teams in 3. |
| By champion setting, of 8 each | Top 0, 1, 1 at levels 1, 3, 6. Mid 3, 0, 0. Carry alone 1. Carry and support 0. | Top 2, 2, 0. Mid 2, 2, 0. Carry alone 1. Carry and support 1. |
| Settings in which some hold lasts at least 1, 2, 3, 4 cycles in every seed | 52, 35, 10, 1. None lasts 5. | 52, 39, 12, 1. None lasts 5. On both teams, 52, 32, 4, and 0. |
| With a laner on its fountain, and with one under its tower | The same in every setting. 0 cycles in 55 settings, 1 in 4, 2 in 5. | The same in every setting. 0 in 54, 1 in 5, 2 in 5. |
| With a laner that last-hits with its wave | 0 cycles in 43 settings, 1 in 12, 2 in 8, 3 in 1 | 0 in 44, 1 in 13, 2 in 7 |
| With a laner that pushes | 0 cycles in 8 settings, 1 in 48, 2 in 8 | 0 in 6, 1 in 52, 2 in 6 |
| Longest hold by a hold plan | Four cycles in every seed, by four plans, `hold, last hit` among them, for top at level 6 against 4 surplus casters and an opponent that last-hits. Each retreats once in some seed, its lowest health falls to 23 percent, and it keeps the wave out for at least 134.5 s. The four sustain control there. | Four cycles in every seed, by four plans, `hold, last hit` among them, for top at level 1 against 3 surplus casters and no opponent, with no retreat, lowest health 76 percent, and the wave kept out for all 240 s. They do not sustain control, because a laner that last-hits with its wave holds four cycles there in some seed. |
| Sustaining plans | `hold, last hit` sustains in 1 of the 6 settings, top at level 6, together with three plans that thin or trim. In the other 5 only `hold, thin` or `hold, thin over 1` sustains. | `hold, thin over 1` sustains in 7 of the 10 settings and `hold, thin` in 2. In top at level 3 against 3 surplus casters and no opponent, `hold, last hit` sustains together with three plans that thin or trim. |
| What a hold costs | In 3 of the 6 settings the sustaining plans retreat once in some seed, and their lowest health falls to 21 to 24 percent. In the other 3 there is no retreat, and lowest health is 52 to 85 percent. | In 4 of the 10, with lowest health 23 to 29 percent. In the other 6 there is no retreat, and lowest health is 32 to 87 percent. |
| Paired with a laner on its fountain, the time a plan keeps the wave out in the same seed | Longer in every seed in 444 of 448 pairs of a setting and a plan, shorter in every seed in 0 | 431 and 0 |
| Paired with a laner that pushes, the held cycles | More in every seed in 111 of 448, fewer in every seed in 110 | 108 and 100 |

**Holding from the third wave** (`capabilities.json`, `holding_from_the_third_wave`). With 3 or 4 surplus casters over 32 settings, a hold plan sustains control in 1 on blue and in none on red. Some hold lasts at least 1, 2, 3, 4 cycles in every seed in 28, 16, 1, and 0 settings on blue and in 28, 15, 0, and 0 on red. On blue, in mid at level 1 against 3 surplus casters and an opponent that last-hits, four plans sustain control, `hold, last hit` among them. Each retreats once in some seed, its lowest health falls to 19 percent, and it keeps the wave out for at least 118.75 s. A laner on its fountain or under its tower holds 0 cycles in all 32 settings on both teams.

**Bounce** (`capabilities.json`, `bounce`). A laner follows a plan from first contact until its wave is in the enemy tower's range, then walks to its fountain. Each cell gives the median seconds from the crash until the front is back more than 100 units past the centre and the runs in which it is, then the same for the untouched lane, then whether the case counts. The first table has the plan on blue.

| Champion setting, plan on blue | Hard push | `thin 3, then last hit` | Last hit two waves, then hard push |
| --- | --- | --- | --- |
| Top, level 1 | 76.25 s in 5 of 5. Untouched 197.5 s in 5. Counts. | 70.25 s in 5. Untouched 177.75 s in 5. Counts. | 61.5 s in 5. Untouched 168.75 s in 5. Counts. |
| Top, level 3 | 51.75 s in 5. Untouched 83.75 s in 5, first in 1 run. No. | 46.75 s in 5. Untouched 78.75 s in 5, first in 1 run. No. | 107 s in 5. Untouched 46.75 s in 5, first in 5 runs. No. |
| Top, level 6 | 111.75 s in 5. Untouched 309.75 s in 5, first in 1 run. No. | 30 s in 5. Untouched 286.5 s in 5, first in 1 run. No. | 39.25 s in 5. Untouched 280.5 s in 5, first in 1 run. No. |
| Mid, level 1 | 227.25 s in 1 of 5, on the same tick as the untouched lane. The other 4 reset. No. | 50 s in 5. Untouched 214.25 s in 1. Counts. | 53.75 s in 5. Untouched 191.75 s in 1. Counts. |
| Mid, level 3 | 37.5 s in 3 of 5, on the same tick as the untouched lane in each. No. | 45.75 s in 5. Untouched 25.25 s in 3, first in 2 runs. No. | 77.5 s in 5. Untouched 0.25 s in 3, first in 3 runs. No. |
| Mid, level 6 | 45.5 s in 5. Untouched never. Counts. | 35.25 s in 5. Untouched never. Counts. | Never. Every run resets. No. |
| Carry alone, level 3 | 52 s in 5. Untouched 24.25 s in 2, first in 2 runs. No. | 46.25 s in 5. Untouched 19.125 s in 2, first in 2 runs. No. | 93.75 s in 5. Untouched 45.5 s in 2, first in 2 runs. No. |
| Carry and support, level 3 | 52 s in 5. Untouched 24.25 s in 2, first in 2 runs. No. | 46.25 s in 5. Untouched 19.125 s in 2, first in 2 runs. No. | 74 s in 5. Untouched 45.125 s in 2, first in 1 run. No. |

| Champion setting, plan on red | Hard push | `thin 3, then last hit` | Last hit two waves, then hard push |
| --- | --- | --- | --- |
| Top, level 1 | 89.75 s in 5 of 5. Untouched 271.5 s in 5. Counts. | 69.75 s in 5. Untouched 251.75 s in 5. Counts. | 61.5 s in 5. Untouched 243 s in 5. Counts. |
| Top, level 3 | 52.25 s in 5. Untouched 177 s in 5. Counts. | 46.5 s in 5. Untouched 172 s in 5. Counts. | 93.5 s in 5. Untouched 141 s in 5, first in 1 run. No. |
| Top, level 6 | 110.5 s in 5. Untouched 338.75 s in 5. Counts. | 44 s in 5. Untouched 315.25 s in 5. Counts. | 38.75 s in 5. Untouched 309.25 s in 5. Counts. |
| Mid, level 1 | 92 s in 1 of 5, on the same tick as the untouched lane. The other 4 reset. No. | 49.5 s in 5. Untouched 79 s in 1. Counts. | 52 s in 5. Untouched 53.5 s in 1. Counts. |
| Mid, level 3 | 91 s in 3 of 5, on the same tick as the untouched lane in each. No. | 46 s in 5. Untouched 79 s in 3, first in 1 run. No. | 75.5 s in 5. Untouched 48.5 s in 3, first in 2 runs. No. |
| Mid, level 6 | 45.75 s in 5. Untouched never. Counts. | 35.75 s in 5. Untouched never. Counts. | Never. Every run resets. No. |
| Carry alone, level 3 | 53.75 s in 5. Untouched 55.5 s in 2. Counts. | 46.75 s in 5. Untouched 50.625 s in 2. Counts. | 120.25 s in 5. Untouched 17.625 s in 2, first in 2 runs. No. |
| Carry and support, level 3 | 53.75 s in 5. Untouched 55.5 s in 2. Counts. | 46.75 s in 5. Untouched 50.625 s in 2. Counts. | 91.25 s in 5. Untouched 17.625 s in 2, first in 2 runs. No. |

The front comes back in every run in 21 of 24 cases on each team, and before the untouched lane's front in every run in 7 on blue and 16 on red. The three that do not come back in every run are mid at levels 1 and 3 after a hard push and mid at level 6 after two last-hit waves. In the runs that do not come back the front stays at the centre on 92 to 100 percent of the ticks in contact (`front_at_centre_share`). In top at levels 3 and 6 and in bot, with the plan on blue, the untouched lane gets back first in some run under every plan, so none of those cases counts. With the plan on red it gets back first there only after two last-hit waves. In mid at level 3 no case counts on either team. In top at level 1 every plan beats the untouched lane on both teams, by at least 54.75 s on blue and 78 s on red. In mid at level 6 the untouched lane never gets there within the run, so those returns beat it by default. Through campaign 4 fewer cases counted with the plan on red, 15 against 18, and since campaign 5 fewer count with the plan on blue, 7 against 16. Nothing here traces why.

**Why mid resets at 0:00.** The level 1 mid laner crashes 5 minions into the tower 63 s into the game in every seed with the plan on blue, and 62.75 s with it on red. In a run traced in campaign 2, the tower killed them before red's second wave arrived, both second waves then walked the same distance, met at the exact centre with six minions each, and stayed equal for about two minutes, until tie-breaking draws separated them (Reported, one trace, handoff 006). In the 1 run that comes back now, on either team, the front returns on the same tick as the untouched lane's front. Whether a real mid lane resets after a first-wave crash is unknown.

### 5.5 Diagnostics: one rule at a time, the tick, and the decision interval

A diagnostic changes one lane rule for one table. It shows which rule a verdict rests on. It is not a candidate for the lane. Two champion settings (top at level 1, mid at level 3), 3 seeds, 8 stacking settings, 8 holding settings with 3 and 4 surplus casters, and 4 bounce cases, with the plan on blue (`capabilities.json`, `diagnostics`).

| Lane | Untouched first-wave fight, mid and top | A plan accumulates (a thinning plan), of 8 | Largest crash (with no laner) | A hold sustains (longest, cycles), of 8 | Bounces in every run (before the untouched lane), of 4 |
| --- | --- | --- | --- | --- | --- |
| The M8 lane | 32.5 s, 33 s | 1 (1) | 9 (8) | 1 (3) | 3 (2) |
| M7's route graph | 32.5 s, 34 s | 2 (2) | 9 (8) | 1 (3) | 3 (0) |
| Blows land at once | 31 s, 31.5 s | 0 (0) | 8 (5) | 3 (3) | 3 (0) |
| Ranges along the lane | 32.5 s, 33 s | 1 (1) | 9 (8) | 1 (3) | 3 (2) |
| No tower shelter | 32.5 s, 33 s | 2 (2) | 9 (8) | 1 (3) | 3 (2) |
| At most 2 melee minions on a target | 32.5 s, 32.5 s | 2 (2) | 12 (7) | 3 (3) | 3 (2) |
| A cancelled cast costs nothing | 32.5 s, 33 s | 1 (1) | 9 (8) | 2 (3) | 3 (2) |
| A missile to a dead target turns to another | 32 s, 32.5 s | 0 (0) | 9 (7) | 2 (3) | 3 (3) |
| Both of those | 32 s, 32.5 s | 1 (0) | 9 (8) | 1 (3) | 3 (3) |
| Detour of 0.3 s | 32.5 s, 33 s | 2 (2) | 10 (8) | 3 (3) | 3 (3) |
| Detour of 0.6 s | 32.5 s, 33 s | 0 (0) | 9 (7) | 3 (4) | 3 (3) |
| Minion blows at 0.85 | 38 s, 38 s | 0 (0) | 11 (10) | 4 (4) | 3 (0) |

**What the table shows.** No rule produces the behaviours. Every variant moves a count by three settings at most, and not in one direction. M7's route graph leaves no bounce that beats the untouched lane, because the untouched top lane then tips at 97 s (Inference from section 5.4). With blows that land at once, no plan accumulates and three holds are sustained, where the M8 lane has one and one. Attack timing is a sourced correction of how long fights last, and it moves the two counts by one and two settings in opposite directions. So it does not decide whether a hold or a stack appears. Weaker minion blows lengthen the fight by 5 to 5.5 s and leave no bounce that beats the untouched lane.

**The tick dependence, diagnosed.** The lane times every blow inside the tick (section 4.2). Through campaign 4 a minion still took a target and marched only once per tick, at the tick's start. A probe of single cases found three such quantisations, and each was tested alone (Reported by the timing delegate). The levers `tick_probe`, `tick_trace`, and `tick_sweep` of section 14 rerun the probes. Three rules of `LaneRules` now do those steps inside the tick (section 4.1).

| Quantisation | What the lane did | Rule now |
| --- | --- | --- |
| Acquisition only at the tick's start | A minion that stopped in reach inside a tick attacked only from the next tick's start. A caster with no target walked past the point where it would take a champion in its path. One 800 units from a champion stood 485 or 450 units off, against 500 on a continuous clock (Reported). | `acquire_on_arrival`. The caster now stands 500 units off and lands its first blow at 2.096 s at all four ticks (Reported). |
| A target that dies inside the tick | A minion with no other target in reach stood until the next tick. | `walk_on_loss`. Its next march starts at the moment of the death. |
| The half-gap rule | A minion walked at most half its gap to the enemy's lead walker, even when that walker could come no nearer than a standing enemy in front of it, so the walk took more ticks the longer the tick. | `march_to_standing`. A minion whose nearest enemy stands still walks all the way to it. |

With the three rules the untouched first-wave fight kills the same minions at the same times at 0.125, 0.25, 0.5, and 1.0 s, to a millionth of a second in mid and within 0.02 s in top (Tested, `test_the_first_wave_fight_of_an_untouched_lane_kills_the_same_minions_at_the_same_times_at_every_tick`). With the first rule alone, or with the first two, top still differed by 0.17 s at 0.5 s, and the third alone moved nothing (Reported). All three are on in `M8_LANE` and off in `M7_LANE`, and the port check still gives 998 of 998 (section 5.1). A fourth diagnostic, `tie_by_set`, keys a tie draw on the tied set and not on the minion's count of draws. Runs at two ticks make different numbers of draws, so they do not share draws. In the probe the key narrowed the spread across seeds and left the spread across ticks where it was, so it stays off (Reported).

**What still amplifies a small difference.** Three amplifiers sit in the experiments and in M7's tick order. They are classified, not fixed (Reported by the timing delegate, from `tick_trace`).

- The own-tower start of a stacking case is a threshold on a stalled front, read at a decision tick. In the traced case red's lead stood 76 units apart at 0.125 s and 0.5 s across that threshold, so the plan began at 80.0 s at one tick and 94.0 s at the other. After the fixes it begins at 80.0 s at both.
- `thin_then` counts caster kills from the run's start, so a later start turns three thinning plans into one.
- A champion's walk is computed from the front at the start of the tick, the latency of M7's order of moving before collecting. Removing it needs an arrival time from `World._move`.

**Tick length** (`capabilities.json`, `tick_sweep` and `tick_sweep_sensitivity`). The diagnostic settings at ticks of 0.125, 0.25, 0.5, and 1.0 s, with a decision every 2 s at each, 3 seeds, and the plan on each team. A case is a setting and a plan. The reference is 0.125 s, and it is a reference, not ground truth. The first table counts the cases in which each verdict holds at each tick, and the cases that keep the same verdict at all four.

| Verdict | Cases | Blue, same at every tick | Blue, holds at 0.125, 0.25, 0.5, 1.0 s | Red, same at every tick | Red, holds at 0.125, 0.25, 0.5, 1.0 s |
| --- | --- | --- | --- | --- | --- |
| A plan accumulates | 56 | 50 | 5, 1, 0, 3 | 53 | 2, 1, 0, 1 |
| A thinning plan delays the first crash | 40 | 38 | 40, 40, 40, 38 | 33 | 38, 37, 39, 34 |
| A hold sustains control | 56 | 50 | 7, 1, 3, 2 | 51 | 7, 3, 4, 3 |
| A crash bounces before the untouched lane | 4 | 0 | 0, 2, 2, 4 | 0 | 3, 3, 2, 2 |

The second table takes each case that has a value in every run. Its shift at a tick is its mean over seeds there less its mean at 0.125 s. A case moves more across ticks than across seeds when the range of its four means exceeds its range across seeds, averaged over the ticks.

| Measure, team | Cases | Move more across ticks than across seeds | Median absolute shift at 0.25, 0.5, 1.0 s | Mean over cases at 0.125, 0.25, 0.5, 1.0 s |
| --- | --- | --- | --- | --- |
| Largest crash, minions, blue | 80 | 48 | 0.33, 0.67, 1 | 5.25, 5.08, 5.29, 5.51 |
| Largest crash, minions, red | 80 | 53 | 0.33, 0.67, 1 | 4.82, 4.75, 5.38, 5.25 |
| First crash, s, blue | 55 | 55 | 0.33, 1.12, 1.62 | 41.74, 40.43, 41.89, 44.88 |
| First crash, s, red | 54 | 51 | 0.56, 2.46, 3.33 | 48.73, 50.62, 54, 55.58 |
| Held cycles, blue | 88 | 22 | 0, 0, 0 | 0.95, 0.95, 1.00, 0.99 |
| Held cycles, red | 88 | 13 | 0, 0, 0 | 1.00, 0.99, 1.02, 1.01 |
| Kept out, s, blue | 88 | 55 | 0.27, 0.62, 0.6 | 89.68, 88.33, 90.29, 90.07 |
| Kept out, s, red | 88 | 44 | 0.21, 0.25, 0.79 | 90.93, 88.54, 90.85, 88.91 |
| Bounce back, s, blue | 3 | 3 | 1, 4.62, 0.25 | 68.99, 64.03, 63.28, 68.67 |
| Bounce back, s, red | 3 | 2 | 1.17, 0.33, 0.83 | 66.06, 68.61, 64.33, 69.44 |

**Before and after the fixes.** Campaign 4's results file gave blue's mean first crash as 42.3, 41.7, 56.3, and 50.8 s at the four ticks, and the median shift from 0.125 s as 0.5, 8.7, and 5.4 s at 0.25, 0.5, and 1.0 s. The fixes removed that peak at 0.5 s, which campaign 4 could not explain. Blue's shift is now 0.33, 1.12, and 1.62 s. Red's shift was 0.4, 2.5, and 5.2 s and is now 0.56, 2.46, and 3.33 s, so red's changed little at 0.25 s and 0.5 s and fell at 1.0 s. Crash sizes and crash times still move more across ticks than across seeds in most cases on both teams, and held cycles do not.

**Verdicts still flip**, even between 0.125 s and 0.25 s, on both teams, and no bounce case keeps its verdict at all four ticks on either team. An every-seed verdict is a strict comparison against a control's bar on counts of 7 to 11 minions, so any small change in a near-balanced lane can flip it, the tick among them (Inference from the probe). Changing only the draw key moved one probed verdict as much as the tick does (Reported, decision trail). No tick gives every-seed verdicts that hold at the others. Section 5.4 counts at 0.25 s, and its every-seed verdicts on single settings are not stable in the tick.

Blue's top laner at level 1 from its own tower, against an opponent that last-hits, accumulates reinforcements under five of its seven plans at 0.125 s, under none at 0.25 s and 0.5 s, and under three at 1.0 s. With the plan on red the same setting accumulates under four plans with a decision every 1 s at 0.25 s, and under none with one every 2 s (`decision_sweep_sensitivity`). So the statement of section 5.4 that no plan accumulates against an opponent that last-hits holds at the research clock and not at every clock.

**Side bias, measured and not forced.** Per case and seed, blue's first crash less red's has a median of -0.25, -0.62, -0.5, and -1.0 s at the four ticks, and blue's comes first in 117 of 189, 125 of 184, 126 of 200, and 112 of 188 pairs (Tested, `tick_sweep --from experiments/m8/waves/results/capabilities.json`). Split by lane, from the same `tick_sweep` blocks, top's median is -1.25, -1.5, -0.5, and -3.5 s, with blue first in 83 of 101, 82 of 98, 80 of 105, and 78 of 110 pairs, and mid's median lies within 0.25 s of 0 at every tick (Tested). The M8 top polyline is not symmetric about the centre (section 4.2), so the bias is the map's and not the tick's (Inference). On the owner's instruction no symmetry was forced and no noise was added.

**Decision interval** (`capabilities.json`, `decision_sweep` and `decision_sweep_sensitivity`). The same settings and seeds at the research tick of 0.25 s, with a decision every 1, 2, and 5 s and the plan on each team. Through campaign 4 this sweep ran at a 0.5 s tick. The reference is 1 s.

| Verdict | Cases | Blue, same at every interval | Blue, holds at 1, 2, 5 s | Red, same at every interval | Red, holds at 1, 2, 5 s |
| --- | --- | --- | --- | --- | --- |
| A plan accumulates | 56 | 55 | 1, 1, 0 | 49 | 5, 1, 2 |
| A thinning plan delays the first crash | 40 | 35 | 40, 40, 35 | 33 | 39, 37, 32 |
| A hold sustains control | 56 | 55 | 2, 1, 1 | 54 | 3, 3, 4 |
| A crash bounces before the untouched lane | 4 | 4 | 2, 2, 2 | 4 | 3, 3, 3 |

| Measure, team | Cases | Move more across intervals than across seeds | Median absolute shift at 2, 5 s | Mean over cases at 1, 2, 5 s |
| --- | --- | --- | --- | --- |
| Largest crash, minions, blue | 80 | 28 | 0, 0 | 5.24, 5.08, 4.62 |
| Largest crash, minions, red | 80 | 36 | 0.33, 0.33 | 5.01, 4.75, 4.10 |
| First crash, s, blue | 56 | 35 | 0, 1.62 | 44.57, 44.23, 54.5 |
| First crash, s, red | 48 | 48 | 1.88, 5.17 | 40.11, 42.94, 54.17 |
| Held cycles, blue | 88 | 10 | 0, 0 | 0.91, 0.95, 1.01 |
| Held cycles, red | 88 | 8 | 0, 0 | 0.93, 0.99, 1.05 |
| Kept out, s, blue | 88 | 21 | 0, 0 | 89.72, 88.33, 91.29 |
| Kept out, s, red | 88 | 12 | 0, 0 | 88.47, 88.54, 89.06 |
| Bounce back, s, blue | 3 | 0 | 0, 0 | 64.03, 64.03, 64.03 |
| Bounce back, s, red | 3 | 0 | 0, 0 | 68.61, 68.61, 68.61 |

Verdicts change less with the decision interval than with the tick, and most hold lengths do not move at all. Crash times do. Against a decision every 1 s, one every 5 s delays the first crash by a median of 1.62 s on blue and 5.17 s on red, and the mean over cases by about 10 s and 14 s. On red the accumulation verdict changes in 7 of 56 cases, all of them in top at level 1 from its own tower. The interval is how fast a plan answers its lane, so a wave result must name it as it names the tick.

### 5.6 Attack timing and movement obstruction, from traces

The owner asked for traces of attack timing and movement obstruction, and noted that a cap on attackers does not test obstruction.

**Attack timing.** The lane counts cancelled casts and lost missiles. In an untouched lane over five minutes at a 0.5 s tick (`investigation.json`, `attack_timing`):

| Lane | Minion deaths | Casts cancelled | Missiles lost |
| --- | --- | --- | --- |
| Mid | 104 | 34 | 48 |
| Top | 100 | 50 | 58 |

A placed fight of six against six lasts 27 s with timing and 25.5 s without. The untouched first-wave fight lasts 32.5 s in mid and 33 s in top, against 31 s and 31.5 s without timing. When wave 2 reaches the fight in mid, 29 s after the first blow, the six minions of wave 1 that are alive hold 17 percent of their health on average, against 7 percent without timing. Those are the effects of timing that this document can stand behind. Section 5.5 shows that the wave verdicts do not follow from them.

**Movement obstruction.** The lane has no bodies, and two bodies of the sourced pathing radius cannot stand within 71.5 units of each other in one lateral slot. The experiments count where the lane puts them there.

| Run | Minions that overlap an ally, share of minion ticks in contact | Most melee minions on one target |
| --- | --- | --- |
| Untouched mid lane, 5 minutes at a 0.5 s tick | 1.0 percent | 2 |
| Untouched top lane, 5 minutes at a 0.5 s tick | 2.5 percent | 3 |
| The accumulating plan, top at level 1 from its own tower under `thin 2, then last hit` (11 minions), plan on red | 5.7 percent | 3 |
| Blue's largest crashes, top at level 1 from its own tower under `last hit` and the carry alone from its own tower under `thin 1, then last hit` (9 minions each) | 5.0 and 1.3 percent | 3 |
| A hard push in each of those three settings | 0.9, 1.1, and 0.0 percent | 3 |

Never more than three melee minions attack one target, and six bodies fit around one, so the place where bodies would matter is not the target. It is the walk to the next target inside a crowd, and the crowd grows with the stack. The `detour_s` diagnostic charges that walk. A melee minion that turns to a new minion target loses 0.3 s or 0.6 s before its cast. One body's detour at minion speed is about 0.25 s (Assumed geometry on the sourced radius). The length of a fight does not show the detour. A placed fight of six against six stays at 28 s even with a detour of 5 s (Reported by the review of campaign 2). The verdict counts of section 5.5 are the evidence, and they move by two settings at most. This bounds one effect of obstruction in a lane without width. It does not show what bodies do.

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
| **A. The untouched first wave in mid.** Nobody touches the lane. When the minions of wave 2 reach the fight, count the minions of wave 1 that are still alive and note how healthy they look. | Wave 2 arrives 29 s after the first blow. Six minions of wave 1 are alive, at 17 percent of their health on average. Left alone, the fight would end 32.5 s after the first blow. |
| **B. The slow-push drill in top.** A level 1 laner kills the three casters of wave 1 and then only last-hits, with no opponent. Count the minions that reach the enemy outer tower and time their arrival from first contact. | 7 minions of two waves, six and one, 37 s after contact with the plan on blue and 37.25 s with it on red. The placeholder top laner needs longer for the casters than a real champion might. |
| **C. An untouched top lane.** Nobody touches the lane for five minutes. Note whether the waves keep meeting near the centre or one side reaches a tower. | The front stays within 100 units of the centre for the first 150 s in every run. Within 300 s it leaves toward red's half in 3 of 5 runs, at 187 to 188.5 s. Blue's wave reaches red's outer tower in 2 runs and red's reaches blue's in 1, with 8 minions at most. Over 600 s it leaves toward either half, by seed. On M7's route graph the front is on blue's half at 97 s in every run. |

A match in A would confirm one timing. B and C test results that this document does not trust.

### 5.9 Incentive screen and M7's tick sweep

**Incentives** (Tested, [`incentives.json`](../../experiments/m8/waves/results/incentives.json)). A level 1 laner plays one `LANE` action for 5 minutes in each of 12 lane states, in a full world. No action earns most in every state. `last_hit` with the wave earns most gold plus XP in 7 states. `last_hit` from the hold line earns most in top after a crash at the own tower against an opponent that last-hits and in mid after a crash with no opponent. `thin` with the wave earns most in top from first contact against an opponent that pushes, `push` with the wave in mid from first contact against an opponent that pushes, and `push` from the hold line in mid after a crash against an opponent that pushes. A hold that last-hits earns as much as last-hitting with the wave in top after a crash with no opponent, 76 more in top after a crash against an opponent that last-hits, 6 less in mid from first contact with no opponent, 6 more in mid after a crash with no opponent, and less in the other eight. In each of those eight the holding laner retreats at least once in the median run. The laner's numbers are placeholders, so this is a screen of the mechanics.

**M7's tick sweep** (Tested, `m7_tests_on_m8_lane.json`, `tick_sensitivity_m8_lane`). On M7's scripted cases, 11 of 17 metrics are within 10 percent of the 0.125 s reference at a 0.5 s tick. Campaign 1 measured 13 of 17 before cast times existed, campaign 2 measured 9, campaign 3 measured 10, and campaign 4 measured 9. The six that move are the crash time and the wave of one top-lane case, and the band time or the champion's lowest health in three of M7's hold cases.

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
| Sixth camp dead at | 170.75 s | 167.75 s |
| Level, camp gold, health then | 4, 529, 320 of 744 | 4, 529, 315 of 744 |

The numbers are at the research clock. Each jungler kills its Blue Sentinel at 66.5 s. Campaign 4 measured the sixth camp at 168.5 s and 167.5 s at a 0.5 s tick, and campaign 2 at 178 s and 179 s. The step from campaign 2 is the ready attack, which now lands at once on a camp (Inference, from the change in section 7.1). No reference gives a clear time on the 2026 clock (M7 question OQ8), so this time has no pass condition. In the sweep the jungler's pick equals the destination with the most gold plus XP per second in 25 of 27 starts and states. No destination is required to win, and every champion number is a placeholder.

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
| `FIGHT` | The fighter heads for its target by its team's record of it alone, with the lead of section 3.2. While the team sees the target, the record is where the target stood at the end of the last tick. Out of view, the fighter walks to the last-seen place in team memory. Seen again on the way, the fight resumes with no outcome. One tick after it arrives within attack range of the last-seen place with the target still unseen, the intent ends with `LOST`. The target's death ends it with `KILLED`, whoever killed it. | M7 section 7.1 |
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

- Pursuit follows the contract of section 3.2. Every walk is picked from one state before the move step and all champions move at once. A fighter reads only its team's record of its target. A target that walks away is led by one seen step along its lane or its edge, and the fighter stops short of the led place by `_lead_short`. A fighter answers a visible target that turns to flee one tick late and then closes by its speed edge. `FOLLOW` is unchanged.
- First blood is drawn among the kills of the tick, ordered by the victim's place. M7 said a draw picks the team, and that flips when the teams exchange seats.
- `SIEGE` ends with `CLEARED`, or with `ABSENT` when the lane has no tower to damage. M7 names no outcome.
- A laner that fights in self-defence off its lane is still charged as roaming.
- Left out: bounties and shutdown gold, the level-difference modifier on kill XP, the early growth of the assist pool, the 3 s before backdoor protection returns, plate gold decay, Bulwark, and the armor penetration of tower shots. A tower keeps a champion as target only while that champion is harassing.

### 8.2 The fight scenarios of M7 section 5.9, on the M8 kernel

[`combat.json`](../../experiments/m8/results/combat.json) reruns M7's four scenarios at the research clock with policies that only choose actions. Every champion number is a placeholder, so the outcomes show that the mechanics respond. They do not show who wins a real fight.

| Scenario | Result |
| --- | --- |
| A champion retreats at half health. Speed edge, lockdown, and distance to its own tower, 18 cases. | 14 escapes and 4 deaths. From 1,000 units every runner escapes. From 2,500 and 4,000 units the runner whose speed is 20 lower than the chaser's dies, with and without the lockdown, and the others escape. The chaser dies under the tower in all 14 escapes. The lockdown changes no outcome. Campaign 4, at a 0.5 s tick and before the pursuit fix, had 16 escapes and 2 deaths, with the slower runner from 2,500 units among the escapes. A faster chaser that closes by its speed edge on every tick (section 3.2) accounts for the change (Inference). The tick changed too, and no run separates the two. |
| A level 1 fighter loses to a level 7 enemy alone. Its jungler walks in from d units. | Alone the fighter dies and the enemy keeps 523 health. The side kills the enemy with the jungler from up to 2,500 units, at every distance in steps of 250, and the first fighter survives with it from up to 1,250. From 2,750 to 4,250 units both of the side's champions die and the enemy survives with 4 to 99 health. From 4,500 the enemy dies after all, 44.75 to 82.25 s in, because the first fighter has respawned and walked back by then (Inference). |
| The same duel in open lane and under the defender's outer tower. | In open lane the attacker wins with 99 health after 11.75 s. Under the tower it dies after 2.5 s to three tower shots of 820 damage in all. |
| A jungler leaves fog toward a laner, 24 cases. The laner stands at its own or at the enemy outer tower, starts with 650 or 390 health, and decides every 1, 2, or 5 s. The jungler plays the brawler with or without the tower rule. | Without the tower rule, a laner at its own outer tower is never touched and the jungler dies under the tower, in all 6 cases. A laner at the enemy outer tower dies and the jungler survives, in all 6. With the tower rule the jungler survives in all 12. The laner survives in all of them except the laner with 390 health at the enemy outer tower, which dies in all 3. With 650 health there its lowest health is 66, 37, and 8 for a decision every 1, 2, and 5 s. In campaign 4 the laner at the enemy outer tower survived and the jungler died, because the jungler fell behind when the lockdown's slow ended and then followed the laner under the laner's own tower (Reported, a scratch probe recorded in the decision trail of campaign 4). The pursuit of section 3.2 keeps a slowed target in range after the slow ends, so the jungler now catches the laner before it reaches its tower (Inference). |

Two things in these runs come from the rules and would mislead if read as strategy. A tower with no minion in range shoots any enemy champion in range, so a champion that walks under an enemy tower alone dies within seconds. And conclusions about ganks depend on where the wave stands, which section 5 leaves open.

**The tower rule is a rule of the policy, not of movement.** A chase under a lethal tower is a mistake of a scripted policy. Campaign 5 keeps it apart from the movement defect of section 3.2. `harness.brawler(retreat_below, side, decision_s)` with a side given holds instead of fighting at a decision on a lane from which it could walk into the range of a standing enemy tower before its next decision, while no minion of its own stands in that range. It reads only its observation and where the towers stand. The C7 policies carry the same rule as `Style.tower_rule` (section 10.1). Movement is the same with the rule on or off. Without the rule a scripted champion fights where a tower can reach it, and with it neither style does (Tested, `test_no_scripted_style_fights_where_the_tower_rule_forbids_it_and_both_fight_where_an_own_minion_covers_them`). The rule is Assumed.

### 8.3 Acceptance criteria of C5

| Criterion (M7 section 10.1, and the owner's requirements) | Result | Test |
| --- | --- | --- |
| Damage is monotone in capability | Never falls with a level or an upgrade, for five profiles | `tests/test_combat.py` |
| An ally's arrival tick equals route length over speed | From 600, 1,500, and 3,000 units the first hit falls on the tick that the arithmetic gives | `tests/test_combat.py` |
| A champion takes champion damage only on ticks when an attacker is within range by the straight line and the target is in the view of the attacker's team | Open lane: hits on 5 of 30 ticks, exactly those in range. Over a wall: hits on exactly the 7 of 12 ticks with an ally's sight. 494 units in a straight line against a walk of 568 is inside a range of 550. | `tests/test_combat.py` |
| A tower's damage on a champion follows the reference aggro and ramp rule to the tick | No shot at 751 units. Multipliers 1.0, 1.5, 2.0, 2.5, 2.5 on consecutive shots. The ramp is kept after 4.5 s without a shot and starts again after 5 s. The tower turns from minions to a champion that damages an ally and back when the call has run out. | `tests/test_combat.py` |
| Permuting the seat order changes no outcome | Five fights, seats exchanged between the teams and inside a team. Equal on every tick. | `tests/test_combat.py` |
| `FIGHT` follows M7 section 7.1 | Pursuit to the last-seen place, `LOST` one tick after arrival, no outcome when the target is seen again first, the same path wherever the hidden target is. A target that steps behind a wall is followed only if the fighter's team sees where it went. On a lane, a jungle path, and a base edge a faster fighter closes by its speed edge on every tick and then hits on every tick, also against a target whose step is longer than its range, and a fighter never leads a target that walks toward it. A target that walks, follows, or fights from equal observations draws the same moves from the fighter's team. | `tests/test_combat.py`, `tests/test_vision.py`, `tests/test_pursuit.py` |
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

Beside the Assumed rows of section 9.1, four limits stand. The encoding is unscaled, and its layout follows the observation's fields. A direct `World.ward` call between ticks gives combat sight one tick before team memory, which the `WARD` action does not (Reported). Pursuit by the team's record answers a visible target that turns to flee one tick late (section 3.2). The map has no brush and no height, and the wall terrain is the constructed terrain of M7 section 5.1.

### 9.3 What the fog hides, measured

[`experiments/m8/vision.py`](../../experiments/m8/vision.py) runs the comparisons of `tests/test_vision.py` and reports their sizes in [`vision.json`](../../experiments/m8/results/vision.json). The assertions are in the tests.

| Measure | Value |
| --- | --- |
| Hidden-state comparison | 32 worlds: 4 games, both teams, 4 snapshot ticks. Every observation, encoding, and mask is unchanged in 32 of 32. The changes cover 84 living enemy champions, 17 dead ones, 310 minions, 223 camps, and 352 wards. |
| Behaviour comparison | 32 comparisons and 642 compared ticks, from 5 to 60 per comparison. 31 reach a reveal. The compared ticks cover `CAMP`, `FIGHT`, `FOLLOW`, `HOLD`, `LANE`, `MOVE`, and `WARD`, and 56 champion ticks in a fight whose target is out of view. |
| Scripted farming and jungling, 5 games of 600 s | Blue sees the enemy jungler on 13.5 percent of ticks [10.4 to 14.8] and red on 11.8 [9.1 to 13.1]. Each enemy laner is seen on 88.5 to 91.2 percent as a median, and each enemy wave on 90.0 to 93.5. These policies place no ward. |
| Random legal actions, 5 games of 600 s | Each enemy champion is seen on 27.3 to 58.7 percent of ticks as a median, and each enemy wave on 90.4 to 92.7. A team has 0.150 and 0.305 wards on the map, as a median over the games. |

The numbers are at the research clock. Campaign 4's ran at a 0.5 s tick, where the enemy jungler was seen on 2.6 and 1.0 percent of ticks. The rise comes with the clock and not with the code. On scripted games of 600 s from seeds 0 to 2 the share is 0.140, 0.125, and 0.125 at 0.25 s, 0.017, 0.071, and 0.095 at 0.5 s on the final code, and 0.015, 0.102, and 0.014 at 0.5 s on the code of campaign 4 (Reported, probes of the coordinator outside the repository). At 0.25 s red sees blue's jungler mostly at blue's own camps (Reported), so the two junglers' routes cross (Inference). The C7 policies ward. In their 50 soak games each game places a median of 53 wards (section 10.2).

### 9.4 Acceptance criteria of C6

The criteria are those of M7 section 10.1 for C6, and the owner's requirement that no automatic behaviour reads hidden state. The tests are in `tests/test_vision.py`, `tests/test_memory.py`, and `tests/test_pursuit.py`, and the mutation runner has entries that each file must catch.

| Criterion | Result | Test |
| --- | --- | --- |
| The hidden-state test: change every field hidden from a team, and its observations and masks stay identical | 40 worlds, four games for each team at five moments, with the encodings identical too. `vision.json` reports the same comparison over the first four moments, 32 worlds (section 9.3). Every field of `Champion` is either changed in a hidden enemy or named with the reason it is not hidden. The other team is told of every change. | `test_changing_every_field_hidden_from_a_team_changes_none_of_its_observations_encodings_or_masks`, `test_the_scramble_changes_every_hidden_field_and_names_the_ones_it_leaves` |
| The behaviour test: under the same change, the team's champions follow identical trajectories until something is revealed | Each champion of the team is equal as a whole `Champion` on every tick before the first exposure. Since campaign 4 the team's whole memory is equal too on every such tick: camps, enemy records with their places, `was`, and upgrades, waves, and towers. Exposure is decided from the map's sight measure by a check that shares no code with `vision.py`. | `test_a_teams_champions_do_the_same_in_two_worlds_that_differ_only_in_what_is_hidden_from_it`, `test_the_behaviour_comparison_covers_every_automatic_movement_and_enough_ticks` |
| The private fields of a visible enemy stay private (closes handoff 007, F14) | In a copy, every enemy that the team sees gets new values in its 18 private fields, among them intent and how the last one ended, XP within the level, gold, attack credit, channel, and mana. The team's observations, encodings, and masks are identical, and so are its champions' moves on the next step. That holds for each team in the four games of the behaviour test, with at least 15 compared moments and 25 changed enemies in each, and in random legal games with rings of fights and chains of followers, compared every 16th tick. Stance, lane inputs, combat targeting, and retaliation read none of the 15 either. The comparison lasts one step, because after it the changed enemy acts differently, which the team may see. Since campaign 5 the visible-enemy test asserts that deaths are equal in both worlds and skips a moment with a death. | `test_changing_the_private_fields_of_the_enemies_a_team_sees_changes_none_of_its_observations_and_none_of_its_moves`, `test_stance_lane_inputs_targeting_and_retaliation_read_no_private_field_of_a_visible_enemy`, `test_random_legal_games_give_both_teams_moves_that_no_private_field_of_a_visible_enemy_changes`, `test_a_fighter_moves_the_same_against_a_target_that_walks_follows_or_fights_from_equal_observations` |
| The junction, open-ground, and wall cases hold for champions in a running game | Two arms of a junction see each other. Mid lane and the river see each other over open ground though the walk is longer than sight. A lane and the camp behind the lane wall do not. A champion that walks out from behind the wall is seen from the tick the map gives. A team never sees a place that its sources do not see by the map's measure. | The five sight tests of `tests/test_vision.py` |
| A ranged attack reaches a target behind a wall only while the attacker's team sees it | Damage lands on exactly the ticks on which a ward of the attacker's team stands | `test_a_ranged_attack_reaches_a_target_behind_a_wall_on_exactly_the_ticks_on_which_a_ward_of_the_attackers_team_stands` |
| An enemy Stealth Ward never appears in a team's view | Enemy wards placed anywhere change nothing that the team is told, then or later | `test_enemy_stealth_wards_placed_anywhere_change_nothing_that_a_team_is_told_now_or_later` |
| Last-seen records freeze out of vision | A record keeps place and health while the enemy walks off and heals, and its age grows by the clock. A remembered wave keeps its lead and size out of sight and is forgotten when the team sees its place empty. An enemy tower's health shows while the team sees it, freezes out of view, and reads 0 once the tower falls. An enemy's upgrades show while it is seen and stay in the record, and `was` needs two ticks of sight. | `test_a_last_seen_record_keeps_place_and_health_while_the_enemy_walks_off_and_heals_and_its_age_grows_by_the_clock`, `test_a_remembered_wave_keeps_its_lead_and_size_out_of_sight_and_is_forgotten_when_the_team_sees_its_place_empty`, the two record tests of `tests/test_memory.py` |
| A ward reveals and then expires | A ward shows a hidden enemy for exactly its duration at the average champion level. Placement range, recharge, the two charges, and the fourth ward are tested apart. | `test_a_ward_shows_a_hidden_enemy_for_exactly_its_duration_at_the_average_champion_level` and four ward tests |
| Positioning and pursuit read team knowledge (owner requirement, M7 section 6.3) | A laner walks with its own wave wherever an unseen enemy wave is, and takes its stance against the wave once a ward, an ally, or a minion of its team sees it. A wave plan reads its champion's observation and nothing else. | The two stance tests, the wall pursuit test, `test_a_plan_reads_its_champions_observation_and_nothing_else` |

**What the leak tests do not show.** The behaviour test changes only what is hidden by a margin of 1,500 units beyond every sight radius and its slack of 300, so that the comparison lasts. It leaves the enemy's wards and its current memory alone and replays the enemy's actions from the first world, so it never tests what the enemy would do differently. Its thresholds against a vacuous pass depend on the trajectories of four scripted games, and a change elsewhere in the kernel can move them. The pursuit change of campaign 4 moved them, and campaign 5 moved them again. They now ask for at least 30 compared ticks per team and game and 450 in all, at least 3 hidden tower changes, and a snapshot replay that sees a ward placed and a fight end by `LOST` or `KILLED`. The hidden-state test sums its floors, among them 4 changed enemy champions, over five moments, the four snapshots and a fifth at tick 1,600 (`LATE`). These are read from `tests/test_vision.py`. The visible-enemy tests compare one step only. The leak of a stance that reads the true front is caught by the targeted stance tests, not by the behaviour comparison (Reported).

## 10. Integrated games, sweeps, and throughput (C7)

### 10.1 What exists

[`riftgame/policies.py`](../../riftgame/policies.py) holds scripted policies for all ten seats, and [`experiments/m8/integrated.py`](../../experiments/m8/integrated.py) plays them under a referee. Every number of this section is in [`integrated.json`](../../experiments/m8/results/integrated.json) unless it names [`kernel.json`](../../experiments/m8/results/kernel.json).

| Part | Built | Status |
| --- | --- | --- |
| Policies | One policy per seat, built per side with `Side(team, style, decision_s)`. A player knows which side it plays, so a policy can turn a place of its team's frame back into a map position. `policy(team)` holds one rule per role, with the laner's rule for top, mid, and the carry. `team_policies()` builds one policy per seat, and `harness.tick` takes one policy or one per seat. Each policy reads only its champion's observation and public facts, walks down a list of wants, and takes the first that its mask allows. A `Style` holds every threshold below. The C7 games play `STANDARD`, which is the C7 policy of campaign 4 with the tower rule. `policies.C7` keeps the campaign 4 policy, with the rule off. | Tested, `test_every_scripted_choice_is_legal_and_reads_only_the_observation` |
| Tower rule | At a decision on a lane from which a champion could walk into the range of a standing enemy tower before its next decision, while no minion of its own stands in that range, it starts no fight, keeps none, hits back at nobody, and ganks nobody (section 8.2). `Style.tower_rule` turns it on. | Assumed. Tested, `test_no_scripted_style_fights_where_the_tower_rule_forbids_it_and_both_fight_where_an_own_minion_covers_them`. |
| Laner | Last-hits with its wave. Below 30 percent health it recalls, or first walks to its own tower when an enemy is seen within 1,400 units. When an enemy other than its lane opponent shows up within 1,800 units, it walks to its own tower, keeps that walk under way, and holds within 300 units of the tower. At 40 percent health or more it keeps a fight under way and hits back at an enemy that hurt it, before any retreat. A walk to a ward spot goes on before shopping and trading. It recalls to buy once its next upgrade is affordable and no enemy is near, and buys on its fountain by the kernel's rule. It trades with its lane opponent at 60 percent health or more, when it is at least as healthy as the opponent and away from the enemy tower. From 75 s it wards the river beside its lane. After 600 s it pushes and sieges a lane whose opponent is dead or unseen for 20 s. | Every threshold Assumed |
| Support | Stays with its carry, spends its item's charges on the wave, wards the bot-side river, and joins the carry's fights. | Assumed |
| Jungler | Clears camps as `harness.jungler` does. At 70 percent health or more it ganks the most hurt enemy laner below 60 percent that its team sees within a walk of 3,500 units, away from the enemy tower. It wards a river spot within a walk of 2,500 units and leaves for its fountain when an enemy with a larger share of its health shows up within 1,800 units. | Assumed |
| Referee | `Referee` watches the world after every tick and checks the event log against the ruleset's numbers, not against the functions of `riftgame` that schedule the events. It checks every minion's spawn tick against the wave schedule, every minion's place against the standing enemy front tower, every camp spawn and respawn with the Scuttler pair rule, and every champion respawn against the timer of the level the champion had before the tick. Every tower shot on a champion is checked, at the places where the lane held each champion when the towers fired, so a champion that died on the tick counts where it stood. While a tower has a provoker, a shot on a champion must go to a provoker, and a provoked stretch of one attack period plus a tick must contain a shot. A provoker is an enemy champion in the tower's range that hit, on the tick or within the call-for-help window before it, a champion of the tower's team that stood within the switch range. Without a provoker, a shot must go to a champion in range while no enemy minion is in range. Minions do not move while towers fire, so a minion alive in range after the tick was in range then. At the end of a game the referee also faults a wave, a camp, or a champion respawn that was due and never came. Five entries of the mutation runner break the tower rule, a respawn, a camp respawn, and the wave clock, and the referee's test fails on each. Under the policies' tower rule few games provoke a tower, so the referee's test plays seeds 35, 23, and 11. Of seeds 0 to 49, 14 games shoot a provoker, and these three shoot one most often, four, three, and two times (`tests/test_integrated.py`). The referee counts only new orders, so a retreat or a gank order kept over several decisions counts once. | The referee reads the world, which no policy does. |

### 10.2 Acceptance criteria of C7

The criteria are those of M7 section 10.1 for C7. Each game is 1,200 s at the research clock, a 0.25 s tick with a decision every 2 s, with the invariant checker on every tick. The soak has the scripted policies on both teams, and the baseline has them on one team against random legal actions on the other.

| Criterion (M7 section 10.1) | Result | Test |
| --- | --- | --- |
| Scripted games of 20 game minutes run for 50 seeds with no invariant failure | 50 games, 0 invariant errors, 0 referee faults | `integrated.json`, `soak`. `test_a_scripted_game_of_20_minutes_breaks_no_invariant_and_no_rule_of_the_referee` |
| Three pinned replays reproduce their digests | Scripted teams on seed 7, scripted blue against random red on seed 11, and random teams on seed 13, 4,800 ticks each, which is 20 game minutes at the research clock. Each reruns equal on every tick, and the final digests are pinned. The pins moved on purpose with the clock and the tower rule. | `integrated.json`, `replays`. `test_three_pinned_replays_reproduce_their_digests_on_every_tick` |
| Every C1 to C6 test still passes | The whole suite gives 982 passed and 9 expected failures (section 12). | `-m pytest -q` |
| Throughput stays above the gate of M7 section 10.4 | Not met at the research clock: 267 [265 to 269] simulated seconds per wall second against 300. A 0.5 s tick gives 467 (section 10.4). | `kernel.json`, `c7_gate` (section 10.4) |
| In the event log, every wave spawn, camp spawn, camp respawn, and champion respawn falls on the tick that the ruleset gives | 80,700 minion spawns, 3,326 camp spawns and respawns, and 1,467 champion respawns checked in the soak. 0 faults. | `integrated.json`, `soak`, `checked` |
| No minion moves past a living enemy tower | 13,295,395 minion places checked against the standing enemy front tower in the soak. 0 faults, with the lane rule `tower_blocks` of section 4.1. | `integrated.json`, `soak`. `tests/test_lanes.py` |
| A champion that damages an enemy champion inside the range of that enemy's tower takes tower damage under the reference rule | In the soak, every one of the 1,193 tower shots on champions is checked. On 87 ticks a tower had a provoker. The 25 shots fired then went to a provoker, and 16 provoked stretches were answered by a shot. The other 1,168 shots went to a champion in range with no enemy minion in range. No tick is skipped, and there are 0 faults. The baseline games add 5,441 checked shots, 122 of them with a provoker, with 0 faults. Campaign 4's soak had 498 ticks with a provoked tower, and the policies' tower rule of section 10.1 accounts for the drop (Inference). The rule itself is tested to the tick in C5. | `integrated.json`, `soak` and `baseline`. Section 8.3. |
| After an outer tower falls, the enemy wave's furthest advance in that lane increases | 169 outer towers fell in the soak and baseline games, 83 of them with a full 120 s window after the fall. The attacking wave's furthest advance in that lane is larger after the fall in 83 of 83, by a median of 3,698 units and at least 762. | `integrated.json`, `towers`. `test_after_an_outer_tower_falls_the_attacking_wave_advances_further_in_that_lane` |
| A scripted team beats a random-action team on gold and XP at 15 minutes on at least 45 of 50 seeds | 50 of 50 with the scripted team on blue, by a median of 32,380 gold plus XP and at least 26,277. 50 of 50 on red, by 28,448 and at least 24,547. No invariant error and no referee fault. | `integrated.json`, `baseline`. `test_a_scripted_team_beats_a_random_team_on_gold_and_xp_at_15_minutes` |
| A sweep over ticks of 0.25, 0.5, and 1.0 s and decision intervals of 1, 2, and 5 s reports which scripted outcomes change, and the handoff confirms or revises the starting values | Section 10.3, with 0.125 s added as the reference tick and the decision sweep at the research tick. Campaign 5 revises the starting tick to 0.25 s and keeps a decision every 2 s (section 10.5). | `integrated.json`, `sweep` |

**What the policies did.** Over the 50 soak games, the policies' work as a median per game is 21.5 kills, 62 camp clears, 63 ended recalls, 53 wards placed, 81.5 `FIGHT` orders, 8 interrupted recalls, 9 gank orders, 9 `SIEGE` orders, and 346.5 retreats on a sighting. In all there are 1,120 kills, 395 executions, 78 fights ended by `LOST`, and 16 towers destroyed. Each of the ten behaviours that the soak requires occurs in every game except `LOST`, which is missing in 12 of 50 (`games_missing_a_behaviour`). `test_the_scripted_policies_exercise_every_subsystem_over_a_few_games` checks the same over a few games.

### 10.3 The sweeps

20 seeds of 1,200 s each, with the scripted policies on both teams. Each cell gives the paired median, the median over seeds of the value less the reference's value in the same seed, and in brackets the seeds higher and lower than the reference. The noise is the interquartile range of the reference across seeds. Gold, XP, minion gold, and tower health are per team, and tower health is the summed health of the team's towers at the end. The counts are over both teams, and orders count only when new.

**Tick, with a decision every 2 s.** The reference is a tick of 0.125 s.

| Measure | Median at 0.125 s | Noise | 0.25 s | 0.5 s | 1.0 s |
| --- | --- | --- | --- | --- | --- |
| Gold, blue | 27,637 | 1,879 | -642 (7, 13) | -482 (9, 11) | -1,997 (3, 17) |
| Gold, red | 27,211 | 2,492 | -466 (8, 12) | -103 (10, 10) | -1,081 (7, 13) |
| XP, blue | 36,867 | 2,241 | -163 (10, 10) | -167 (8, 12) | -418 (10, 10) |
| XP, red | 36,419 | 3,605 | -993 (9, 11) | -1,393 (7, 13) | +739 (11, 9) |
| Minion gold, blue | 5,488 | 441 | -90 (9, 11) | -97 (7, 13) | -439 (5, 15) |
| Minion gold, red | 5,309 | 509 | -130 (8, 12) | -115 (7, 13) | -72 (9, 11) |
| Tower health, blue | 48,548 | 4,280 | +411 (13, 7) | -1,019 (8, 12) | -2,500 (6, 14) |
| Tower health, red | 47,093 | 3,934 | +1,270 (12, 8) | -1,716 (6, 14) | -890 (9, 11) |
| Kills | 22.5 | 4.5 | -3 (5, 15) | 0 (9, 9) | -8 (0, 19) |
| Camp clears | 63 | 4 | -2 (9, 11) | -1 (7, 10) | -1 (7, 12) |
| Recalls ended | 62 | 5.75 | +4 (13, 6) | +4.5 (13, 7) | -1.5 (6, 13) |
| Wards placed | 51 | 3.5 | +1.5 (12, 4) | +1 (11, 6) | -5 (4, 15) |
| `FIGHT` orders | 79.5 | 8.25 | +2 (12, 7) | -1 (6, 12) | -10 (3, 17) |
| Minions killed by champions | 535 | 42 | +2 (10, 9) | -9.5 (7, 13) | -15.5 (9, 11) |
| Retreats on a sighting | 359.5 | 40 | -16.5 (7, 13) | -28 (4, 16) | -16.5 (7, 13) |
| Gank orders | 10 | 3.75 | +0.5 (10, 8) | -3.5 (3, 17) | 0 (7, 8) |

At 0.25 s and at 0.5 s every paired median is inside the noise. The most lopsided seed counts are kills at 0.25 s, lower in 15 of 20 seeds, and gank orders at 0.5 s, lower in 17. At 1.0 s blue's gold falls by 1,997 in 17 of 20 seeds against a noise of 1,879, kills by 8 in 19 against 4.5, `FIGHT` orders by 10 in 17 against 8.25, and wards placed by 5 in 15 against 3.5. Blue's minion gold falls by 439 in 15, just inside its noise of 441. The tick changes the kernel's fidelity, and at 0.25 s and 0.5 s the integrated outcomes stay within seed noise of 0.125 s. Campaign 4's sweep, before the pursuit fix, the in-tick rules, and the tower rule, found blue's minion gold and the camp clears beyond the noise at 0.5 s.

**Decision interval, at the research tick of 0.25 s.** The reference is a decision every 2 s. Through campaign 4 this sweep ran at a 0.5 s tick.

| Measure | Median at 2 s | Noise | 1 s | 5 s |
| --- | --- | --- | --- | --- |
| Gold, blue | 26,919 | 2,468 | -620 (6, 14) | +1,372 (17, 3) |
| Gold, red | 26,798 | 1,507 | -1,107 (4, 16) | +1,921 (18, 2) |
| XP, blue | 35,859 | 3,049 | -1,088 (5, 15) | -305 (10, 10) |
| XP, red | 35,490 | 2,539 | -1,391 (6, 14) | +280 (11, 9) |
| Minion gold, blue | 5,470 | 545 | +119 (13, 7) | -1,180 (0, 20) |
| Minion gold, red | 5,192 | 658 | -28 (9, 11) | -1,068 (0, 20) |
| Tower health, blue | 48,530 | 6,214 | -259 (10, 10) | -275 (10, 10) |
| Tower health, red | 47,480 | 2,714 | -804 (7, 13) | +328 (11, 9) |
| Kills | 20.5 | 6 | -4.5 (3, 16) | +16.5 (20, 0) |
| Camp clears | 62 | 5.5 | -3 (7, 13) | -1.5 (6, 11) |
| Recalls ended | 64.5 | 4.75 | +3 (17, 2) | -15 (0, 19) |
| Wards placed | 53 | 2 | -2 (2, 15) | 0 (9, 9) |
| `FIGHT` orders | 81 | 9 | +5.5 (15, 5) | -17.5 (0, 20) |
| Minions killed by champions | 540.5 | 39.25 | +3 (10, 10) | -119 (0, 20) |
| Retreats on a sighting | 347.5 | 39.5 | +285 (20, 0) | -193.5 (0, 20) |
| Gank orders | 9 | 3.75 | -0.5 (9, 10) | -5 (0, 20) |

A decision every 1 s gives 4.5 fewer kills in 16 of 20 seeds, inside the noise, 3 more recalls in 17, less gold for red in 16, less XP for both teams in 14 and 15, and 285 more retreats on a sighting in every seed, because more decisions issue more new retreat orders. A decision every 5 s gives 16.5 more kills, 17.5 fewer `FIGHT` orders, 193.5 fewer retreats, 119 fewer minions killed by champions, 5 fewer gank orders, and less minion gold on both teams, 1,180 on blue and 1,068 on red, in every seed, and 15 fewer recalls in 19. Red's gold still rises, by 1,921 in 18 seeds, beyond its noise, and blue's by 1,372 in 17, inside it, with the extra kills (Inference). The decision interval changes what the scripted policies do. At 5 s they react later, and more champions die (Inference). The interval is a property of the agent's reaction time, not of the kernel.

### 10.4 The throughput gate

M7 section 10.4 sets a gate of 300 simulated seconds per wall second for the integrated game on one process. `kernel.json` measures it with the scripted policies on both teams for 15 game minutes from seed 0, with 7 runs per clock and the clocks alternating run by run. Every run of a clock does the same work, and the script asserts it. Since campaign 5 the clocks are the research clock, a 0.25 s tick with a decision every 2 s, and a 0.5 s tick with a decision every 2 s and every 1 s.

The rerun at the research clock gives 267 [265 to 269] simulated seconds per wall second, over 7 runs on a quiet machine (total CPU 3 to 7 percent, with the owner's idle `collect_drafts` processes alive). That fails the gate by 11 percent. A 0.5 s tick with a decision every 2 s gives 467 [463 to 475], and with one every 1 s 427 [422 to 431] (Tested, `kernel.json`, `c7_gate`). A first rerun while the mutation runner held one core gave 238 and 422, about 11 percent lower at both clocks. The quiet numbers match campaign 4's 268 and 476 within 2 percent, so campaign 5's code costs at most that much (Inference).

Campaign 4 measured 476 [447 to 490] at a 0.5 s tick with a decision every 2 s, 428 [373 to 436] with one every 1 s, and 268 [264 to 270] at a 0.25 s tick, which failed the gate by 11 percent (handoff 008, F11). The gate is reported here. It did not choose the clock (section 10.5).

**The profile at the research clock** (Reported, a cProfile run of the timing delegate over 900 s of seed 0 with the scripted teams, on a loaded machine, read as shares only). `LaneSim.step` takes 46.9 percent of the time, team memory (`vision.remember`) 26.2, lane inputs (`economy.lane_inputs`) 8.0, movement (`World._move`) 5.9, `World._settle` 4.9, and the observation (`observe_team`) 3.8. Work done once per tick is over 80 percent of the time, so halving the tick about halves the rate (Inference). The three in-tick lane rules cost nothing that the spread can separate. Five alternating runs of 300 s at 0.25 s gave 249 [236 to 260] simulated seconds per wall second before them and 243 [238 to 256] after, on a loaded machine (Reported). No speedup was attempted.

In the sweep of section 10.3, with the referee on and 8 games at a time on a loaded machine, a game of 1,200 s took a median of 65.1 s of wall time at 0.125 s, 32.5 s at 0.25 s, 18.5 s at 0.5 s, and 12.3 s at 1.0 s, and 36.5 s and 26.4 s at 0.25 s with a decision every 1 s and every 5 s (`integrated.json`, `sweep`, `wall_s_per_game`). These wall times are not the gate.

### 10.5 The research clock

Campaign 5 moved `Config()` to a 0.25 s tick with a decision every 2 s. Through campaign 4 it kept M7's starting values, a 0.5 s tick with a decision every 2 s, for throughput. The new clock rests on fidelity. Throughput is reported and did not choose it. The reasons follow.

1. Wave timings favour 0.25 s. After the in-tick fixes of section 5.5, per case over 3 seeds, the median shift of a first crash from 0.125 s at 0.25 s is 0.33 s on blue and 0.56 s on red, against 1.12 s and 2.46 s at 0.5 s (`capabilities.json`, `tick_sweep_sensitivity`).
2. The tick now only samples the lane's first-wave fight. Its deaths fall at the same times at 0.125, 0.25, 0.5, and 1.0 s, to a millionth of a second in mid and within 0.02 s in top (section 5.5). The fixes did not make every-seed wave verdicts stable at any tick.
3. The integrated outcomes do not choose between 0.25 s and 0.5 s. At both every paired median of section 10.3 lies inside the seed noise of the 0.125 s reference.
4. 0.125 s is a reference, not ground truth. A champion's walk still starts from the front at the tick's start (section 5.5), so the finest tick keeps a latency of its own.
5. The decision interval is the agent's reaction time. At the research tick a decision every 5 s moves kills, `FIGHT` orders, retreats, minion kills, gank orders, and both teams' minion gold in all 20 seeds, and recalls in 19. So each experiment fixes the interval and reports it, and 2 s is the middle of the tested range.

Kernel tests that measure per-tick behaviour state their own clock (section 3.2), and `recall.json` stays at a 0.5 s tick with a decision on every tick by design. The gate at the research clock is in section 10.4, and the profile there says what limits it. The gate leaves out the flat encoding that a learner reads, which the independent review of campaign 4 measured at about 8 percent of the wall time (Reported).

## 11. Scenarios, hypotheses, and comparisons (C8)

C8 implements the contracts of M7 section 4, step 4, section 8.2, and sections 9.1 to 9.5, against the C8 row of M7 section 10.1. Its output is uncertainty about alternatives under stated policies and hypotheses. It makes no recommendation, and its comparisons are simulator comparisons, not calibrated real-game advice or win probabilities.

### 11.1 What exists

| Module | Owns |
| --- | --- |
| [`info.py`](../../riftgame/info.py) | `redact(world, team)` returns an `InfoState(team, snapshot, seen)`, with `.world()` and `.digest()`. The `FIELDS` table classifies every field of every dataclass of the state once, as `Known.PUBLIC`, `SEEN`, `HIDDEN`, `SCRATCH`, or `UNITS`, and `redact` reads the table. A hidden field gets a canonical blank that depends on nothing hidden, such as `band_floor` for XP and `KILL_MARK` for a kill in the ledger. The world seed is blanked to 0. The team's own memory is kept in full, so enemy tower health with its age, enemy upgrades, and `was` reach the hypotheses. Each champion's `respawned_tick` and `respawned_level` are public, because kills and respawns are public (M7 section 6.3). The world sets them at a respawn and reads them nowhere, and 14,400 per-tick lines of four games of 20 minutes are equal with and without them (Reported). |
| [`hypotheses.py`](../../riftgame/hypotheses.py) | `Activity` (`STAY`, `FARM`, `CLEAR`, `RECALL`, `MOVE`), `Plan(activity, path, to, xp, upgrades, watched)`, `Hypothesis(name, weight, plans, cleared)`, `Reason`, and `Rejected`. `activity_v0`, `generate`, `complete`, `check`, and `realize(info, hypothesis, rollout)`. Every function takes the information state and nothing else. The numbers are in the `[hypotheses]` section of `patch_26_22_m8.toml` (section 12). |
| [`vision.py`](../../riftgame/vision.py) | `remember_team`, split out of `remember` so that a built world can rebuild one team's memory. The split is bit-identical. |
| [`scenario.py`](../../riftgame/scenario.py) | The TOML recipe of M7 section 9.1: `parse`, `load`, `build`, `save`, and `restore`, and `Scenario(meta, decision, info, hypotheses, rejected, hindsight)`. A recipe's base game runs on its own tick, `base.tick_s`, 0.5 s by default. |
| [`clock.py`](../../riftgame/clock.py) | `refine(world, tick_s)`: the same state on a finer clock by a whole factor k. Every count of ticks is multiplied by k, `respawned_tick` among them, sentinels are kept, and `was` is interpolated. |
| [`compare.py`](../../riftgame/compare.py) | Rollouts, paired statistics, verdicts, rankings, sensitivity, and the report, with `VERDICT_RULE`, `STABILITY_RULE`, and `NOTE` |
| [`policies.py`](../../riftgame/policies.py) | `Style` with `STANDARD`, the C7 thresholds and the tower rule, and `AGGRESSIVE`: retreat below 0.20 of health, leave a fight below 0.25, leave the fountain at 0.80, trade above 0.45 with no lead needed, a danger radius of 1,200, gank a laner below 1.01 from 0.55, push from 420 s, and place no ward. `C7`, `STYLES`, and `Side(team, style, decision_s)`. |
| [`c8.py`](../../experiments/m8/c8.py), [`scenarios/`](../../experiments/m8/scenarios/) | The four recipes and the run. The results are in [`c8.json`](../../experiments/m8/results/c8.json), and the 12 saved scenarios, four at each of 0.125, 0.25, and 0.5 s, in `experiments/m8/results/c8_scenarios/`. |

### 11.2 How a comparison runs

1. The recipe's base game runs at `base.tick_s`, 0.5 s, to the first decision tick at or after `until_s`, and the overrides apply there. That is the one decision state.
2. The state is compared at 0.25 s, at 0.5 s, and at the 0.125 s reference. `refine` makes each tick finer than 0.5 s from it, so every tick compares one decision state. An earlier version reran the base game at each tick and so compared different states, and campaign 5 replaced it (decision trail).
3. The state is saved, restored from the file, and redacted for the deciding team.
4. `activity_v0` proposes hypotheses for the unseen enemies, with the enemy jungler in focus, and drops each that fails a check, with its reason: `UNREACHABLE`, `IN_VIEW`, `XP_BAND`, `CAMP_UNVISITED`, `UPGRADES_WITHOUT_FOUNTAIN`, or `INCONSISTENT`. An enemy whose respawn came after the team last saw it starts from that respawn on its fountain, at full health and mana and able to shop. Before that fix it was rebuilt near death at its place before the death, in 108 of 208 sampled states and in two of the four scenarios (Reported). When a role's default activity fails, the generator falls back to a stay, a recall, a move out of view, the longest start of a jungler's clear that passes, and last a recall that the team watched begin, `Plan(RECALL, watched=True)`, which it allows only when the team did not see the enemy move on the tick of the sighting.
5. `realize` builds a full world for each hypothesis as a history. The enemy's memory is rebuilt by rule.
6. For each style, hypothesis, rollout, and alternative, the alternative is substituted at the decision tick and held for the commit time. The continuation policies of both teams play to the horizon from their observations alone. The alternatives of one rollout start from copies of one world, so their differences are paired.
7. The verdict rule (`compare.VERDICT_RULE`). An option is better or worse than another on a consequence when the paired mean difference lies beyond a threshold in that direction. The threshold is the two-sided Student t quantile, with one degree of freedom fewer than the rollouts, at a family level of 5 percent shared out over the consequences (Bonferroni), in standard errors. The count of consequences depends on the places that a scenario names. With 16 rollouts the threshold is 3.82 standard errors for 30 consequences and 3.85 for 32 (section 11.3). The weighted line weights the hypotheses' paired differences rollout by rollout, because a rollout's worlds share their seed, and takes the mean and the standard error of those sums. The consequences of M7 section 9.4 are reported apart and never summed. A line's ranking is a dominance when one option dominates every other, a trade-off when some pair trades off, a partial order when some option dominates another and no pair trades off, and no clear ranking when no pair differs clearly.
8. The stability rule. A verdict, a relation, or a ranking is stable only if it is the same on every hypothesis line and the weighted line, under both styles, and at both research ticks. Otherwise the report calls it uncertain and names what it depends on. A line that one research tick has and the other lacks counts as absent at that tick, which makes the ranking uncertain.
9. The 0.125 s reference is reported apart, with whether the rankings at 0.25 s agree with it, and changes no stability verdict. The hindsight line runs from the source world and is reported apart. It enters no weight, verdict, ranking, or stability rule.

Every report carries the note that its comparisons are simulator comparisons under stated policies and hypotheses, not calibrated advice or win probabilities.

**Departures from M7.**

| Departure | Reason |
| --- | --- |
| A ranking has four outcomes: a dominance, a trade-off, a partial order, and no clear ranking. M7 section 9.4 labels a ranking a dominance or a trade-off, and it expects no clear ranking for a decision whose payoff lies beyond the horizon. | A refinement of M7's two labels. Some option can dominate another while no pair trades off and no option dominates every other, and neither of M7's labels fits that case. |
| A difference is clear only beyond a family-wise threshold, not beyond a fixed count of standard errors. M7 section 9.4 asks for paired differences with their standard errors and states no threshold. | A line compares 30 or 32 consequences at once. Two standard errors per consequence would call some difference clear by chance on most lines with no real difference (Inference). The threshold is Assumed at a family level of 5 percent (`compare.FAMILY`). |
| `[[lane]]` tables of M7 section 9.1 are refused. | A lane's minions carry targets, casts, and missiles in flight that counts per kind cannot restore. A wave state comes from the base game. |
| The base game runs at a 0.5 s tick, and `refine` makes the research ticks from its one state. M7 section 9.1 names no tick. | So that every tick compares one decision state (step 2). |

### 11.3 The four scenarios

The four scenarios are the first four rows of M7 section 9.5 (Tested, `c8.json`). Each runs 16 rollouts per line over a horizon of 90 s, under the standard and the aggressive style on both teams. The generator draws nothing, so the rollouts of one hypothesis differ only by the world seed, which the kernel draws on for minion targets, last-hit order, combat order, and camps (`c8.py`). Of the 6,424 paired cells of the hypothesis lines, 2,269 have a standard error above zero. `python -m experiments.m8.c8 --workers 6` took 1,527 s of wall time on 6 processes (`c8.json`, `run`).

| Scenario | Base game, decision | Deciding seat, commit | Hidden enemies | Hypotheses | Rejected by the checks | Threshold | Overall ranking | 0.125 s reference |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `freeze_push_shove` | Seed 6, 480 s | `blue_top`, 30 s | 3 | 5 | Move to `top_river`: `IN_VIEW` | 3.82, 30 consequences | Uncertain, depends on style and tick | Differs. Agrees on 0 of 12 lines and 30 of 36 relations. |
| `recall_or_stay` | Seed 2, 580 s | `blue_mid`, 20 s | 3 | 3 | Clear: `UNREACHABLE`. Move to `mid_river` and to `bot_river`: `IN_VIEW` | 3.82, 30 | Stable: trade-off | Agrees. 8 of 8, and 25 of 32. |
| `jungler_botside` | Seed 4, 540 s | `blue_carry`, 20 s | 2 | 6 | None | 3.82, 30 | Stable: trade-off | Agrees. 14 of 14, and 27 of 42. |
| `jungle_options` | Seed 5, 490 s | `blue_jungle`, 25 s | 4 | 2 | Clear: `UNREACHABLE`. Move to `top_river`, `mid_river`, and `bot_river`: `IN_VIEW` | 3.85, 32 | Stable: trade-off | Agrees. 6 of 6, and 24 of 24. |

**What the report says.** "Stable: trade-off" means that the ranking is a trade-off on every line, under both styles, and at both research ticks, so no option dominates every other option. In `freeze_push_shove` the scripted baseline holds in place (`HOLD`) under both styles. There `LANE top last_hit hold` dominates the baseline on every line, under both styles, and at both research ticks. The ranking of all options is still uncertain. `LANE top last_hit hold` dominates every other option on the standard lines at 0.5 s, `LANE top thin wave` on the aggressive lines at 0.25 s, and the options trade off on the rest. The 0.125 s reference ranks none of the 12 lines as 0.25 s does. Of the 14 relations of an alternative to the baseline, 7 are stable: that dominance, 5 trade-offs, and 1 with no clear difference. The other 7 are uncertain, depending on the tick, on the style, on the style and tick, or on the hypothesis, style, and tick. Most verdicts on single consequences are uncertain too. So no scenario names a best option. The one stable dominance says that, under these policies and hypotheses, one alternative beats the scripted policy's own choice of holding in place. It is a statement about the simulator's scripted baseline, not advice for the real game. `python -m experiments.m8.c8 --report` prints every line, verdict, and factor. `python -m experiments.m8.c8 --report` prints every line, verdict, and factor.

### 11.4 Acceptance criteria of C8

The criteria are those of M7's C8 row, with the three tests of M7 section 9.3 and the owner's terms for the clock and the report. Every row is Tested.

| Criterion | Result | Evidence |
| --- | --- | --- |
| Saved scenarios load, restore, and replay exactly | A saved scenario restores memory and pending effects and replays with equal digests on every tick. One made under another ruleset, map, or code stamp is refused. `c8.py` compares from the restored copy of each of its 12 saved scenarios. | `test_a_saved_scenario_restores_memory_and_pending_effects_and_replays_with_equal_digests_on_every_tick`, `test_a_saved_scenario_made_under_another_ruleset_map_or_code_is_refused`, `experiments/m8/results/c8_scenarios/` |
| The recipe of M7 section 9.1 parses at a boundary | Each action has one spelling. An unknown key anywhere, a format error, and a contradiction with the base game are refused with the key or the reason. The decision falls on the first decision tick at or after `until_s`. Overrides keep every invariant. `[[lane]]` tables are refused. | `test_every_action_has_one_spelling_and_the_parser_takes_nothing_else`, `test_a_recipe_with_an_unknown_key_anywhere_is_refused_with_the_key_named`, `test_a_recipe_that_breaks_the_format_is_refused_with_its_reason`, `test_a_recipe_that_contradicts_its_base_game_is_refused_when_it_is_materialised`, `test_the_decision_falls_on_the_first_decision_tick_at_or_after_until_s`, `test_overrides_set_the_deciding_teams_champions_and_memory_and_keep_every_invariant` |
| The information state is what the team knows (M7 section 9.3, contract 1) | Every field of the state is classified once. The information state tells each team what the source tells it, also in random legal games, changes with what the team sees, and redacts to itself. Changing every field hidden from a team changes nothing in it. An unseen enemy holds only blanks and the public facts. | `tests/test_info.py`, among them `test_every_field_of_the_state_is_classified_once`, `test_changing_every_field_hidden_from_a_team_changes_nothing_in_its_information_state`, `test_an_unseen_enemy_holds_only_blanks_and_the_public_facts_and_the_enemy_holds_no_ward_and_the_starting_memory` |
| Truth-blind (M7 section 9.3) | Changing every hidden field changes neither the hypotheses nor any world built from them. A builder that copies one true hidden value fails the same comparison, so the test can fail. In a full comparison the same change moves the hindsight line and nothing else in the report, and the lines never read the source world. | `test_changing_every_hidden_field_changes_neither_the_hypotheses_nor_any_world_built_from_them`, `test_the_truth_blind_comparison_fails_for_a_builder_that_copies_one_true_hidden_value`, `test_changing_every_field_hidden_from_the_deciding_team_changes_the_hindsight_line_and_nothing_else_in_the_report`, `test_the_comparison_lines_never_read_the_source_world` |
| Consistent (M7 section 9.3) | Every built world is valid and shows the deciding team exactly its information state. Unseen minions and camps follow the team's memory and the timer rule, and a camp seen empty respawns at the same game second on every tick of one refined state. An enemy killed after the team last saw it is built from its respawn on its fountain. An enemy gone from where the team watched it stand recalled from before the sighting. The enemy's memory is what it sees at the decision tick and the public facts. | `test_every_built_world_is_valid_and_shows_the_team_exactly_its_information_state`, `test_unseen_camps_that_no_path_clears_follow_the_teams_memory_and_the_timer_rule`, `test_a_camp_that_the_team_saw_empty_respawns_at_the_same_game_second_on_every_tick_of_one_refined_state`, `test_on_a_clock_of_one_second_a_camp_seen_empty_died_two_ticks_before_the_sighting`, `test_an_enemy_killed_after_the_team_last_saw_it_is_built_from_its_respawn_on_its_fountain`, `test_an_enemy_gone_from_where_the_team_watched_it_stand_recalled_from_before_the_sighting`, `test_the_enemys_memory_is_what_it_sees_at_the_decision_tick_and_the_public_facts_and_nothing_of_the_source` |
| Rejection (M7 section 9.3) | Each check is tested in both directions, rejected and passed. The generator drops the activities that fail, says why, and its weights sum to 1. Hand-written hypotheses replace the generator and are completed, checked, and weighted. | `test_a_path_out_of_reach_is_rejected_and_a_path_in_reach_passes`, `test_a_place_in_the_teams_view_is_rejected_and_one_out_of_it_passes`, `test_xp_outside_the_public_level_is_rejected_and_xp_inside_it_passes`, `test_a_camp_cleared_that_no_path_visits_is_rejected_and_one_on_the_path_passes`, `test_upgrades_bought_without_a_visit_to_the_fountain_are_rejected_and_the_seen_ones_pass`, `test_the_generator_drops_the_activities_that_fail_and_says_why_and_its_weights_sum_to_one`, `test_hand_written_hypotheses_replace_the_generator_and_are_completed_checked_and_weighted` |
| A comparison rerun gives identical output | Byte-identical with workers and without. | `test_a_comparison_rerun_gives_byte_identical_output_with_workers_and_without` |
| Individual and coordinated alternatives (M7 section 9.2) | An individual alternative changes one seat at the decision tick, and every other choice is a policy's. A coordinated one changes several seats of one team, and the report calls it a team plan. Continuation policies receive observations and noise and nothing else. | `test_an_individual_alternative_changes_one_seat_at_the_decision_tick_and_every_other_choice_is_a_policys`, `test_a_coordinated_alternative_changes_several_seats_of_one_team_and_the_report_calls_it_a_team_plan`, `test_continuation_policies_receive_observations_and_noise_and_nothing_else` |
| The harness reports the first four rows of M7 section 9.5 under two scripted continuation styles and at least two hypotheses each | Four scenarios, two styles, and 5, 3, 6, and 2 hypotheses (section 11.3). The aggressive style differs from the standard one on the same observations. The C7 style reproduces its pinned replays. | `c8.json`. `test_the_aggressive_style_trades_without_a_lead_ganks_unhurt_laners_places_no_ward_and_differs_on_the_same_observations`, `test_the_c7_style_reproduces_its_pinned_replays`, `test_no_scripted_style_fights_where_the_tower_rule_forbids_it_and_both_fight_where_an_own_minion_covers_them` |
| The report states where rankings differ between styles and between hypotheses | The verdict rule and the ranking categories are tested. A ranking that changes with a factor is uncertain and names the factor. The report states its terms and gives every consequence apart. | `test_the_verdict_rule_is_a_paired_mean_beyond_the_threshold_in_the_good_direction`, `test_the_threshold_is_the_student_t_quantile_at_the_family_level_shared_over_the_consequences`, `test_the_weighted_line_weights_the_hypotheses_rollout_by_rollout_so_lines_that_move_together_keep_their_error`, `test_a_ranking_is_a_dominance_a_trade_off_or_no_clear_ranking_by_the_stated_rule`, `test_a_ranking_that_changes_with_a_factor_is_uncertain_and_names_the_factor`, `test_a_line_that_one_tick_has_and_another_lacks_makes_the_ranking_uncertain`, `test_the_report_states_its_terms_and_gives_every_consequence_apart` |
| One decision state at every tick, and the reference apart (owner requirement) | A recipe materialised at finer ticks describes its one decision state at each. `refine` refuses a tick that does not divide the world's own, gives a copy with the same digest at the same tick, keeps every tick at the same game second and every timer's end, keeps the invariants and the observations, keeps decision ticks, and keeps a Homeguard walk. The reference tick is reported apart, changes no stability verdict, and its agreement counts the lines and relations that rank alike. | `test_a_recipe_materialised_at_finer_ticks_describes_its_one_decision_state_at_each`, `tests/test_clock.py`, `test_a_reference_tick_is_reported_apart_and_changes_no_stability_verdict`, `test_agreement_with_a_reference_tick_counts_the_lines_and_relations_that_rank_alike_and_names_the_rest` |
| The source world stays apart | It differs from the information state only in what the team cannot know, and it feeds only the hindsight line. | `test_the_source_world_is_kept_apart_and_differs_from_the_information_state_only_in_what_the_team_cannot_know` |

The mutation runner has 413 entries, among them entries for C8, the pursuit, the in-tick lane rules, and the clock. Its run is in section 12.

### 11.5 Limits

- The generator has five activities, and its weights are guesses (M7 section 9.3). One activity cannot explain a level that rose while every farm spot is in view, so a laner may farm from the fog, and a jungler seen low that has levelled may recall and then clear. Farming does not touch the lane's state.
- The generator can find no hypothesis at all. Over 416 sampled states it gives up in 6, where it gave up in 16 before the fallbacks of section 11.2, and the code before campaign 5's fixes fails in all 6 too. The causes are a Scuttler's XP and a jungler unseen long enough to need a second pass of camps (Reported). One test state is named as refused, `REFUSED` in `tests/test_hypotheses.py`: game (8, varied), team 0, at 600 s. There the enemy jungler respawned at 564.5 s and in truth killed `red_gromp` at 598.5 s. The generator's clear walks from the fountain without Homeguard, lands no ready attack, and gives the camp the average level of now, so it ends at 605.2 s, after the decision (the test's note).
- The state keeps no kill or assist events, so the generator cannot count an enemy's XP from them.
- A slow is a private field, so the hypotheses do not see it (handoff 008, Q3).
- The view check applies at the decision tick only, not along the history.
- The truth-blind tests are as strong as the scrambles they apply.
- A position override takes no new look. The team's sight is not recomputed for it, and in 2 of 5 probed moves the camp records disagree with what the new place would show (Reported). No recipe uses one.
- An arrival that never happens counts as the horizon.
- `[[lane]]` overrides of M7 section 9.1 are refused. A wave state comes from the base game.
- Saved scenarios are pickles, so a file is read only by code that trusts it.
- The second style is aggressive, not the cautious one that the design note suggested. The two differ in behaviour, and neither is labelled typical of a rank.
- The tower rule reads a lane's towers only for a champion on that lane.
- Keyed draws use the tick index, so runs at two ticks share no noise, and a difference between the research ticks includes the noise of the draws (Inference).
- The pursuit lead can overshoot by one step through a fork inside a lane.
- `refine` interpolates `was`, maps Homeguard to the finer ticks, ends a `LOST` intent one fine tick later, and rounds `dead_s`.
- Several tests of the hypotheses read one fixed game, game (8, varied) at tick 824 of a 0.5 s tick, through `hidden_jungler`, so a change of policy can break them.

## 12. Assumptions, internal correctness, and real-game validation

**Assumed.** Nothing has checked these against the game.

- Every champion number: the five capability profiles, level growth of 8 percent, the 15 placeholder upgrades, camp damage rates, and the numbers of section 8.
- The mana that area damage costs per second (`area_mana_s`), the mana regeneration (`mana_regen`), and the target that a full bar pays for pushing five or six waves (section 8.1).
- Lateral slots after the first wave, the hold line 300 units outside tower range, the stand-off of 550 units, and that a champion that stepped aside hits nothing.
- That a cancelled cast starts again and a missile to a dead target is lost. That tower shots and champion hits are instant. A missile on its way to a champion lands even if the champion steps aside.
- That red's minions walk the game's one polyline per lane reversed.
- The roam cap of 90 s and the refill of 0.25, and the end of assignments at 14:00 or with an outer tower.
- The straight-line decay of Homeguard, the leash of 800 units, straight-line camp scaling, and the Scuttler's timer window.
- The pursuit lead of one seen step along a lane or an edge, and the stop short of the led place by `_lead_short` (section 3.2).
- Sight along a lane by the lane coordinate, the 1,500 units of a remembered wave, the 18 ward spots with the 4 on the river edges, the start charge, and the straight lines of ward duration and recharge.
- Every threshold of the C7 policies, among them retreat below 30 percent health, leave a fight below 40, leave the fountain at 90, trade at 60, gank a laner below 60 from 70, the radii of 1,400, 1,800, 2,500, and 3,500 units, the first ward at 75 s, and the push after 600 s (section 10.1). The thresholds of the aggressive style (section 11.1).
- The tower rule of the scripted brawler and of both styles (sections 8.2 and 10.1).
- The numbers of the hypothesis generator, in `[hypotheses]` of `patch_26_22_m8.toml`. The weights of the activities are 1 for stay, 2 for farm, 2 for clear, 1 for recall, and 1 for move. The gold and XP that an enemy earns per second by role from `farm_from_s` are rounded from the C7 policies over four games of 900 s. An enemy has `mana_share`, 1.0, of its full mana, a recalled enemy walks back toward `recall_return`, and a moving enemy goes to `top_river`, `mid_river`, or `bot_river`. A camp that the team saw empty without learning its spawn died `unseen_death_s`, 1.0 s, before the sighting, and at least two ticks before it.
- The activity rules of `riftgame/hypotheses.py`, which its docstring lists as simulator guesses, among them farming from the fog, a jungler's clear after a recall, the start from a respawn, and the fallbacks of section 11.2.
- That an enemy minion or enemy tower that the team sees is kept in full in the information state, attack state included, because a player sees the attack (`riftgame/info.py`).
- That a realized world holds no enemy ward and no enemy shrine, and that the enemy's memory is what it sees at the decision tick and the public facts (M7 section 9.3, limits).
- That the two continuation styles stand for nothing beyond themselves. Neither is labelled typical of a rank (section 11.5).
- The family level of 5 percent of C8's verdict rule (`compare.FAMILY`), and the 300 units within which a champion has arrived at a named place (`compare.ARRIVED`).
- The jungle paths and the sight terrain of M7 section 5.1, unchanged.

**Implementation correctness.** A test in this repository shows each of these, and a mutation run shows that the test can fail.

- The kernel contracts of section 3.3, the lane rules of section 4.1, the ledger, and the criteria of sections 6.3, 7.3, 8.3, 9.4, 10.2, and 11.4.
- The port of M7's lane (section 5.1).
- The whole suite, with the kernel tests and the wave tests of `experiments/m8/waves`, gives 982 passed and 9 expected failures in 14 min 23 s. The expected failures are M7's known prototype defect, the four wave bars of section 5.3, and the four regression pins of section 4.6. The mutation runner breaks the code in 413 ways, and the tests catch all 413, with the unmutated copy passing. Both provenance checkers report every results file current, and the five frozen files of M7's provenance are byte-identical to the last commit.

This is correctness inside the simulator. It says that the code does what this document says, and nothing about strategy or the real game.

**Strategic validation.** The scripted policies beat random legal actions on gold plus XP at 15:00 in 50 of 50 seeds on each side, and in their own games they clear camps, ward, recall, fight, gank, retreat on sightings, and siege (section 10.2). That is a sanity check that the mechanics respond to decisions. It is not evidence of good strategy. The policies are hand-written, every threshold is Assumed, and they play against themselves or against random actions. C8's comparisons show that the harness reports what it compares under stated policies and hypotheses. They say nothing about which decision is good in the real game (section 11). The wave capabilities that the owner requires remain mostly negative (section 2).

**Throughput.** `kernel.json` measures one process on 600 s games of random legal actions, scripted farming, and scripted farming with jungling, with a profile of the farming game and the size of a snapshot. It runs at the research clock since campaign 5, with the gate of section 10.4. At the research clock it gives 300, 281, and 278 simulated seconds per wall second, against campaign 4's 531, 519, and 516 at a 0.5 s tick, and a snapshot at 600 s of 25,584 bytes pickled (Tested, `kernel.json`). The profile of the farming game gives lanes 47.7 percent, team memory 24.4, and lane inputs 9.6.

**Real-game validation.** Nothing. Constants are Sourced, which means read from a document or a data file, not measured. The first real-game validation that M8 needs is still the three measurements of section 5.8. Until wave fidelity is settled, any conclusion that the simulator supports about recall timing, denial, or gank opportunities is provisional, because each depends on where a wave is and how long it stays there.

## 13. Requirements kept for later work

| For | Requirement |
| --- | --- |
| The independent audit | The owner's next step. An audit of C1 to C8 against M7's criteria, of the criteria themselves for tests shaped by one implementation and rules that force a conclusion (M7 section 10.1), and of this document's evidence labels. Its inputs are the suite, the mutation runner, the provenance checkers, and the commands of section 14. It needs every placeholder of this document filled from the final runs. |
| The visual inspection demo | The owner's step after the audit, lightweight and not built. It can read the pinned replays, which reproduce on every tick (section 10.2), and the saved scenarios, which restore and replay (section 11.4). It must show what each team sees apart from the true state, because the information boundary is what C6 and C8 test. |
| M9 | Champion numbers, mana costs and regeneration, armor in `damage`, movement-speed soft caps, and whether purchase thresholds change recall timing. |
| M11 | Wards that can be seen and cleared, Control Wards, and sweeping. A generator that replaces `activity_v0` behind the same signature (M7 section 9.3). |
| Open, C2 | Wave fidelity (section 2). The real-game measurements of section 5.8. The drift of an untouched side lane toward either half by seed, and of a lane with no bend (section 4.2). A tick, or a form of verdict, at which the wave results are stable (section 5.5). Whether C2's criteria become shares of settings or paired medians with seed counts (handoff 008, Q1). |
| Open, lane | Unit collision in a lane with width. The first wave's indifference to champions and its ghosting, which matter to none of the cases of section 5.4 (section 5.7). The retarget cadence. The caster's acquisition range. Tower shot timing. A champion's walk from the front at the tick's start, which needs an arrival time from `World._move` (section 5.5). |
| Open, pursuit | The one tick of reaction lag when a visible target turns to flee (section 3.2). A slow is a private field, where in the game it shows on the champion, so neither the team nor the hypotheses see it (handoff 008, Q3). |
| Open, abilities | Whether the mana numbers of section 8.1 are reasonable placeholders until M9 (handoff 008, Q4). |
| Open, C6 | Sight along a lane by the straight line, and minions that reveal other lanes' minions inside a base. A scaled encoding with a stable layout. |
| Open, C8 | The limits of section 11.5, among them the states where the generator finds no hypothesis, the XP of kills and assists, the view check at the decision tick only, refused `[[lane]]` overrides, saved scenarios as pickles, and the generator tests on one fixed game. |

## 14. How to rerun the evidence

Every command starts with `.venv/Scripts/python.exe` from the repository root (M7 section 13 has the setup). Every experiment runs at the research clock of `Config()`, a 0.25 s tick with a decision every 2 s, unless the row says otherwise.

| Command | What it shows | What it writes |
| --- | --- | --- |
| `-m pytest -q` | Every test of M7 and M8 | Nothing |
| `-m experiments.m8.waves.capabilities` | Stacking, holding from the first and the third wave, and bouncing through the action table with the plan on each team, the diagnostics, the tick sweep with a decision every 2 s, and the decision-interval sweep at the research tick. About 2 hours 10 minutes on 8 processes. | `experiments/m8/waves/results/capabilities.json` |
| `-m experiments.m8.waves.capabilities --report` | The counts and rows of `capabilities.json` that section 5 quotes, per team. A few seconds. | Nothing |
| `-m experiments.m8.waves.investigate` | The lane without champions, at a 0.5 s tick: fights, arrivals, attack timing counters, the untouched lanes, the bend sweep with its pairs and spawn shifts, the drift trace, the level lead. About 4 minutes. | `experiments/m8/waves/results/investigation.json` |
| `-m experiments.m8.waves.tick_probe [--rules NAME] [--cases NAME,...] [--ticks 0.125,0.5] [--json PATH] [--fights]` | The wave cases whose accumulation verdict flips with the tick, at four ticks with a decision every 2 s: each seed's first crash, the largest crash with its waves, each laner's last hits by time, and the verdict. `--fights` prints the deaths of an untouched lane's first waves at each tick instead. `--rules` names the M8 lane, the C7 lane without the three in-tick rules, the C7 lane with one of them, or the tie-key diagnostic. | Nothing, or the file that `--json` names |
| `-m experiments.m8.waves.tick_sweep [--rules NAME] [--json PATH] [--from PATH]` | The tick sweep of `capabilities` under a named lane, per side, with blue's value less red's per case and seed at each tick. `--from experiments/m8/waves/results/capabilities.json` reads the sweep from the results file instead of running it. | Nothing, or the file that `--json` names |
| `-m experiments.m8.waves.tick_trace CASE PLAN SEED [--ticks 0.125,0.5] [--rules NAME] [--until S]` | One stacking case at two ticks side by side: every minion death with its wave, its killer, and its time, and the laners' places and the leads every half second | Nothing |
| `-m experiments.m8.waves.m7_tests` | M7's cases and verdicts on the M8 lane, the port check, M7's tick sweep. About 5 minutes. | `experiments/m8/waves/results/m7_tests_on_m8_lane.json` |
| `-m experiments.m8.waves.incentives` | The incentive screen. About 3 minutes. | `experiments/m8/waves/results/incentives.json` |
| `-m experiments.m8.integrated` | The C7 games of section 10: the soak, the baseline against random legal actions, the tower falls of those two, the three replays, and the tick and decision-interval sweeps. Name `soak`, `baseline`, `replays`, or `sweep` to run some of them. The tower falls are computed whenever the file holds both the soak and the baseline. On 8 processes. | `experiments/m8/results/integrated.json` |
| `-m experiments.m8.c8 [--workers N] [--report]` | The four C8 scenarios of section 11 under both styles at 0.25 s and 0.5 s, with the 0.125 s reference apart. About 25 minutes on 6 processes. `--report` prints the report from `c8.json` again, about 400 lines. | `experiments/m8/results/c8.json`, `experiments/m8/results/c8_scenarios/` |
| `-m experiments.m8.waves.trace "S0 fight 6v6" "m8 lane" 0 0.5 0 100` | A tick-level trace of one M7 case | Nothing |
| `-m experiments.m8.recall` | Round trips from the outer towers, at a 0.5 s tick with a decision on every tick | `experiments/m8/results/recall.json` |
| `-m experiments.m8.jungle` | The scripted jungler's first clear and its sweep. About 1 minute. | `experiments/m8/results/jungle.json` |
| `-m experiments.m8.combat` | The fight scenarios of M7 section 5.9 on the M8 kernel | `experiments/m8/results/combat.json` |
| `-m experiments.m8.vision` | The sizes of the two leak comparisons, and how often a team sees each enemy and each enemy wave. Under a minute. | `experiments/m8/results/vision.json` |
| `-m experiments.m8.kernel` | The kernel measurements and the C7 throughput gate of section 10.4, at the research clock and at a 0.5 s tick. Run it on an otherwise idle machine. | `experiments/m8/results/kernel.json` |
| `-m experiments.m8.mutations` | Breaks the code in 413 ways in a temporary copy and counts the tests that notice | Nothing |
| `-m experiments.m8.provenance` | Whether each of the eleven M8 results files still matches the working tree | Nothing |
| `-m experiments.m7.provenance` | The same for M7. All five files stay current. | Nothing |
