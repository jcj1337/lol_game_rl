# Handoff 007: M8 third campaign, five corrections and C6

| | |
|---|---|
| Number | 007 |
| Date | 2026-11-12 |
| Type | Implementation and experiment. I changed reusable code in `riftgame/`, rewrote the wave experiments, added an evidence script for C6, updated the M8 document, and made small roadmap and README status edits. I trained nothing and started no work on C7 or C8. |
| Responds to | The owner's session prompt of 2026-11-12 with five review findings on [handoff 006](006_m8_c2_corrections_c3_c5.md), and [`docs/design/M7_architecture.md`](../docs/design/M7_architecture.md) section 10.1, checkpoint C6 |
| Status | Delivered. Waiting for review by the user and the planning assistant. Nothing is committed. |
| Author | Claude Code (Fable 5.2), the implementing assistant |

**Reading guide.** The user can read §1 and §6. The planning assistant should read all of it, then [`docs/design/M8_foundation.md`](../docs/design/M8_foundation.md), cited here as "the M8 document". §8 lists the claims I am least sure of. C1 to C8 are M8's checkpoints.

## 1. Summary

- All five review findings are corrected in code, each with a test that fails when the correction is removed (F1 to F5).
- The early top-lane drift is gone. Its cause was an off-centre bend in the lane, not the bend's sharpness. M8 now traces each side-lane corner with the game's four waypoints, in a map file of its own. M7's map is untouched (F2).
- A later drift remains. An untouched top lane still leaves the centre the same way in every seed, at 281 s where it was 97 s (F2).
- The wave comparisons were rerun with an absent champion and a champion that stands under its tower as two separate controls. A top-lane bounce can now be put down to the crash (F6 to F8).
- C2 is still not complete. Reinforcements accumulate in 2 of 48 settings and a hold is sustained in 9 of 64. Single results flip with the tick length (F6, F7, F9).
- Wave results move more with the tick length than with the seed. Averaged over settings, the size of a crash and the time of a bounce agree from 0.5 s down. Crash times and hold lengths do not (F9).
- C6 is built: fog, wards, minion vision, shared team knowledge, and last-seen memory. Observations, masks, running intents, automatic positioning, and every scripted policy read the same team knowledge, with one exception that the independent review found and that is not fixed (F10 to F12, F14).
- The hidden-state test changes 976 hidden things over 32 worlds and no observation, encoding, or mask changes. The behaviour test compares 515 ticks (F11).
- The suite gives 713 passed and 7 expected failures. The mutation runner breaks the code in 248 ways and the tests catch all 248. All nine M8 and all five M7 results files are current (F13).
- All of this is correctness inside the simulator. Nothing is validated against the real game, and no strategic conclusion is drawn. My judgment: C7 can be planned (§7.3).

## 2. Scope

**Done.**

- Read the README, the roadmap, the M7 and M8 documents, handoff 006, and the code and results of the second campaign. Ran the suite at the last commit first: 586 passed and 9 expected failures.
- Made every kernel change myself: the map, the attack credit, pursuit, the digest, and C6.
- Rewrote the wave experiments and reran every results file once on the final tree.
- Had one delegate repair the 114 tests that the kernel changes broke and write the tests for F1 to F5. Had a second delegate write `tests/test_vision.py` for C6. Both worked in the main tree on separate files. I read their reports, ran their tests, and merged the C6 mutations.
- Had a third delegate, on Claude Opus 5.5, update the M8 document from my fact sheet and the results files. I read its summary, its campaign table, and its C6 section, and it reported three places where my fact sheet disagreed with the results files.
- Had the result reviewed by a fourth delegate on Claude Opus 5.5, read-only. It checked about 45 numbers, which matched, and returned 2 defects, 5 items to fix, and 3 notes. §3.4 lists them and what I did.

**Not done.**

- No work on C7 or C8. No training. No real-game measurement.
- No change to any wave criterion or threshold.
- No scripted policy that places wards.
- I did not read every line of the delegates' test files (§8).

**Repository state.** Nothing is committed, pushed, or opened as a pull request. New files: `riftgame/rulesets/map_summoners_rift_m8.toml`, `tests/test_vision.py`, `experiments/m8/vision.py` with its results file, this handoff, and its decision log.

## 3. Results

### 3.1 Findings

| ID | Finding | Label | Evidence |
|---|---|---|---|
| F1 | **Controls.** Every champion now starts on its fountain, and only a champion under a plan stands at a lane. `absent` is a champion on its fountain. `under tower` is a separate control that stands at its outer tower. A champion under its tower ends with more XP than an absent one in every seed, so the old `absent` control was not absent. | Verified | `experiments/m8/waves/agents.py`, `test_behaviours.py` |
| F2 | **Geometry.** A sweep of lane shapes tested the corner hypothesis of 006/F9. A straight lane and a bend at the centre never tip the lane. One bend 150 or 295 units off the centre tips it toward the bend's side at 97 s in 12 of 12 seeds, and to the other side when the bend is mirrored. A bend of 10 degrees does the same as one of 46. So an off-centre bend inside the fight is the cause, and its sharpness is not. M7's graph kept one of the game's four corner waypoints. The M8 map has all four. On it an untouched top lane first leaves the centre at 281 s (median of 12 seeds) and has 20 crashes in 12 runs of 600 s, where M7's graph gives 97 s and 68. Mid has 25. The later drift still goes to red's half in 12 of 12 seeds. | Verified for the sweep and the counts. The mechanism in §4, item 2, is Reported from one traced run. | `investigation.json`, `bends`. `test_behaviours.py`. |
| F3 | **Attack capacity.** One credit is one attack on any target class: a hit on a minion or a tower, `champion_dps / attack_speed` on a champion, `camp_dps / attack_speed` on a camp. A tick against a champion or a camp spends all the credit there is. Delivered attacks plus credit kept equal the credit at the start plus `attack_speed` times the time, on every tick, across switches between classes. The lane's area damage of the `push` mode and the lockdown stay outside the credit. | Verified | `champions.attack_worth`, `tests/test_combat.py`, `tests/test_jungle.py` |
| F4 | **Pursuit.** A fighter follows its target's move only where its team sees the new place inside the move step. A target that stepped out of view is pursued to the last-seen place. | Verified | `champions._to_enemy`, `vision.watches`, `tests/test_combat.py`, `tests/test_vision.py` |
| F5 | **Digest.** A minion target in the lane digest carries whether it lives and when it died, and each minion its spawn delay. The fields still left out are set again on every tick before they are read. | Verified for the two fields and their test. The audit of the other fields is my reading. | `lanes._target_code`, `tests/test_lanes.py` |
| F6 | **Accumulation.** A plan accumulates in 2 of 48 settings: 1 of 16 from first contact, 1 of 16 from the own tower, 0 of 16 from the third wave. Both are bot-lane carries at level 3 with the opponent absent. In the clearer one, `thin 3, then last hit` brings 3 more minions than an absent champion or one under its tower and 4 more than a hard push in 5 of 5 seeds, and earns 26 less minion gold than last-hitting. The largest crash holds 10 minions, and none holds 12. No plan accumulates against an opponent that last-hits. | Verified | `capabilities.json`, `stacking` and its `paired` rows |
| F7 | **Holding.** A hold is sustained in 9 of 64 settings from the first wave and 3 of 32 when the surplus arrives with the third wave. Some hold lasts 1, 2, 3, 4 cycles in every seed in 52, 40, 13, 1 settings from the first wave, and none lasts 5. One hold from the third wave works for a level 6 mid laner, which no first-wave hold does. In the best case (mid, level 1, 3 surplus casters, opponent absent, `hold, thin over 1`) the wave stays out 215 s longer than with an absent champion or one under its tower in 5 of 5 seeds. A champion that pushes also keeps that wave out for the whole run, by sending it away. | Verified | `capabilities.json`, `holding`, `holding_from_the_third_wave` |
| F8 | **Bounce.** After a crash the front comes back past the centre in every run in 23 of 24 cases, and before the untouched lane's front in 18. The six that fail are all three top cases at level 6 and three mid cases after a hard push. In top at level 1 and level 3 every plan now beats the untouched lane in 5 of 5 seeds, by 42 s at least. Mid at level 1 still resets after a one-wave crash. | Verified | `capabilities.json`, `bounce` |
| F9 | **Tick.** With a decision every 2 s, at ticks of 0.125, 0.25, 0.5, and 1.0 s, a result moves more with the tick than with the seed: a first crash time by 30.1 s on average against 4.0 s, a largest crash by 2.9 minions against 1.0. Means over all cases agree from 0.5 s down for the largest crash (4.9, 4.9, 4.9, then 6.0 at 1.0 s) and the bounce time (68 to 70 s at every tick). Held cycles rise slowly with the tick (0.97, 1.01, 1.10, 1.12), the time a wave is kept out is 93, 92, 98, 96 s, and the first crash time does not agree (42, 42, 57, 51 s). In one traced case a laner lands 3 last hits by 75 s at 0.25 s and 2 at 0.5 s, and the first crash comes at 42 s or at 193 s. The simplest case, a hard push in mid at level 3, moves by 1.6 s over the four ticks. | Verified for the sweep. The traced case is Reported, from a scratch probe. | `capabilities.json`, `tick_sweep`. `capabilities.py --report`. |
| F10 | **C6, what exists.** Sight sources are champions, lane minions, towers, wards, and shrines. Team memory holds camps, enemy champions, and each lane's enemy wave. The observation gains last-seen enemies with their age, public rival facts, lane fields, the team's wards, and a flat encoding. `WARD` places a Stealth Ward within 625 units by the straight line. A champion's stance at a wave uses the front that its team sees. Wave plans read only the observation. | Verified | `riftgame/vision.py`, M8 document |
| F11 | **C6, criteria.** Every criterion of M7's C6 row has a test. The hidden-state test changes 89 enemy champions, 15 dead ones, 305 minions, 215 camps, and 352 wards over 32 worlds, and all 32 leave every observation, encoding, and mask unchanged. The behaviour test runs 32 comparisons over 515 ticks and 31 reach a reveal. 35 mutations that reintroduce a leak or break a ward rule are all caught. | Verified. I ran the test file and the evidence script. The 35 mutations are in the final mutation run. | `tests/test_vision.py`, `vision.json` |
| F12 | **What fog does.** In scripted games a team sees the enemy jungler 1 to 3 percent of the time, each enemy laner 87 to 90 percent, and each enemy wave 88 to 93 percent. In the wave experiments a team does not see the enemy lead minion on 6 to 7 percent of ticks (median). No minion hits a champion before the first waves meet in any of 1,440 cases, so the unmodelled rule that the first wave ignores champions changes none of these results. | Verified | `vision.json`, `capabilities.json` |
| F14 | **One leak is open.** The independent review found it. A fighter heads for the new place of a target that has already moved and for the old place of a target that moves after it. Pursuers move last, so which of the two happens depends on whether the visible target's own intent is a pursuing kind (`FIGHT` or `FOLLOW`). The reviewer's probe gave two worlds with equal observations for the fighter's team and the target at the same place in both. The fighter ended at 8,287.0 against a target with `MOVE` and at 8,409.5 against one with `FOLLOW`. No test catches it, because the leak tests change only enemies that the team does not see. The difference is one tick of lag. Removing it means a new rule for the order of moves, which I did not want to choose inside a correction pass (D6). | Reported by the reviewer. I read `champions._to_enemy` and agree with the reading. I did not rerun the probe. | `riftgame/champions.py`, `_to_enemy` |
| F13 | **State of the evidence.** The suite gives 713 passed and 7 expected failures. The mutation runner breaks the code in 248 ways and the tests catch all 248. The port check gives 998 of 998 with M7's draw key. One process runs 543 simulated seconds per wall second under random actions [499 to 554, 7 runs], 523 under scripted farming [486 to 536], and 520 with jungling [481 to 532]. An earlier run of the same code on the same day gave 586, 561, and 552, so the machine's noise is about 7 percent. Campaign 2 measured 620, 573, and 539. Team memory takes 19 percent of a farming game, where it took 7, and the observation 7 percent. | Verified | `pytest -q`, `experiments.m8.mutations`, both provenance checkers, `kernel.json` |

### 3.2 Implementation correctness, strategic validation, real-game validation

**Correct inside the simulator.** A test shows each rule, and a mutation shows that the test can fail. That covers F1 to F5, C6, and the earlier checkpoints C1 and C3 to C5.

**Not validated strategically.** The wave behaviours are measured, and most measurements are negative or unstable. No scripted policy uses wards, so nothing here says that warding pays. The champion numbers are placeholders.

**Not validated against the real game.** Nothing is. The three measurements of the M8 document's wave section would test the lane. They are not a condition for C7.

### 3.3 Unresolved limitations

| ID | Limitation |
|---|---|
| L0 | A fighter's walk depends on the intent kind of its visible target (F14). |
| L1 | C2 is not complete. Accumulation and a sustained hold appear in a small minority of settings, and single results flip with the tick (F6, F7, F9). |
| L2 | An untouched side lane still drifts one way late (F2). The lane has no noise, and the polyline is not symmetric about the centre. |
| L3 | Inside one lane, sight runs along the lane coordinate. It never shows more than the map's straight-line measure, and at a corner it can hide a minion up to about 40 units inside the radius (Inference of the delegate). A team's minions in one lane do not reveal enemy minions of another lane. |
| L4 | Ward spots (the 12 camps and 2 river nodes), one charge at 0:00, and the straight lines for duration and recharge over the average level are Assumed. Wards cannot be seen or cleared until M11. |
| L5 | The behaviour test changes only what is hidden by a 1,500 unit margin, leaves enemy wards and enemy memory alone, and replays the enemy's actions from the first world. It does not catch a stance that reads the true front. A separate stance test does. The hidden-state test reads the observations on the tick of the change without running team memory again, so it shows that `observe_team` reads no hidden field and nothing about what a later tick records. Its count of 976 changed things says how much was changed, not how strong the test is. The median comparison of the behaviour test lasts 14 ticks. A snapshot copies each lane's cached minion sight, and a test that moves minions by hand does not clear it, so the first tick after such a change uses stale sight (Reported by the reviewer). |
| L6 | Enemy tower health is not in the observation, only how many enemy towers stand. |
| L10 | Every stacking, holding, and bounce run puts the plan on blue. An untouched top lane drifts toward red's half first, which helps blue's top-lane bounce. The mirror case was not run. |
| L11 | The last-seen record of an enemy keeps no upgrades, though M7 section 6.2 lists them. |
| L7 | `capabilities.json` is 6.5 MB, five times its old size, because it holds every seed's value and the paired rows. |
| L8 | A laner that fights in self-defence off its lane is still charged as roaming. Self-defence, the return moves, and `RECALL` stay legal under every leash, as before. |
| L9 | The limitations L3 to L16 of handoff 006 that this campaign did not touch still hold: placeholder champions, no bodies, unsourced cast cancel and lost missile, hand-written plan families, and the staging of the wave experiments. |

### 3.4 What the independent review found, and what I did

| # | Finding | Severity | Action |
|---|---|---|---|
| 1 | A fighter's walk depends on the intent kind of its visible target. | Defect | Not fixed. Reported as F14, L0, and D6. |
| 2 | The mutation totals were placeholders while F11 said Verified. | Defect | Fixed. The totals are from the finished run (F13). |
| 3 | The bend sweep does not explain why the M8 map works. | Should-fix | Said so in V1 and in the M8 document, section 4.2. No pair of bends was tested. |
| 4 | "Most averages agree from 0.5 s down" held for one measure, and "not one faulty rule" rested on one trace. | Should-fix | Reworded in §1, F9, Q2, V2, the M8 document, and roadmap risk 11. |
| 5 | The leak tests are narrower than the summary said. | Should-fix | Stated in L5. The summary no longer quotes the count as strength. The cache was not changed. |
| 6 | Two wave tests were pointed at other settings without saying so. | Should-fix | Stated in §4, item 7. |
| 7 | The kernel profile no longer measured the observation. | Should-fix | Fixed in `experiments/m8/kernel.py`, and `kernel.json` rerun. |
| 8 | Every wave run puts the plan on blue. | Note | Listed as L10. |
| 9 | The decision trail stopped before the final runs and had no audit rows. | Note | Rows added. |
| 10 | Smaller points: a hold's gain against the push control, the word "passive", `stance` falling back to the true front when no front is passed, no mutation on the known front in `lane_inputs`, a plan test that checks an annotation, mid and bot leaving the centre near 150 s over 12 seeds. | Note | The first two are reworded. The others stand as the reviewer wrote them. |

## 4. Departures from the specification

1. **A map file of M8's own.** M7 section 5.1 has 39 nodes. The M8 map has 45. The six added nodes shape a lane and are no `MOVE` target, so the action table keeps 107 entries. `M7_LANE` keeps M7's graph through a new rule, `m7_map`.
2. **The drift's mechanism is a traced inference, and one fix was tried and removed.** Across a bend a caster acquires its target a tick early and stops 1.2 units short. Later retargets that sit exactly on a range threshold in a straight lane then fall outside it, and the minion waits for the next tick to walk. I tried acquisition on arrival inside the tick. It left the drift at 97 s in 12 of 12 seeds and changed the first-wave fight by under 0.5 s at four tick lengths, so I removed it.
3. **C4's clear-time criterion changes with F3.** A clear now takes the camp's health less one attack's worth for a ready attack, over the rate. The scripted jungler's first clear ends at 168.5 s where it ended at 178 s.
4. **Level and death timer of an enemy are public.** M7 section 6.3 says so. The leak tests of earlier campaigns changed them and now hold them equal.
5. **The observation has two enemy fields.** `enemies` holds what the team sees now, as before. `remembered` holds the last-seen record with its age. M7 names one team memory and no layout.
6. **Sight inside a lane uses the lane coordinate** (L3). M7 section 6.1 names the straight line. A test shows that the shortcut never claims sight that the map's measure denies.
7. **No wave criterion changed, and two tests point at other settings.** Only the control lists grew by `under tower`. The strict expected failures are six, down from eight: the two about the top lane's drift now pass and are plain tests. Campaign 2's one accumulating case (top, level 1, from the own tower, 11 minions) no longer accumulates on the M8 map with the new controls. The accumulation test now pins the bot-lane carry setting that does, and a new test pins the one mid setting in which a hold from the third wave is sustained. Both are regression pins on settings that I picked after I saw the results. They say that the code still does what it did, and nothing about how often the behaviour appears.
8. **Delegation.** Two test delegates worked in the main tree at once on separate files. I changed `encode` after the second one finished, to close two gaps that it reported, and edited its test to match.

## 5. Decision trail

[`007_m8_corrections_c6_decisions.tsv`](007_m8_corrections_c6_decisions.tsv) holds one row per decision with its reason and a pointer. Rows of the phase `audit` correct earlier rows, and rows of the phase `review` record the independent review.

## 6. Decisions needed from the user

| ID | Decision | Options | Recommendation |
|---|---|---|---|
| D1 | Whether C7 starts while C2 is not complete. | Start C7, or hold M8 for another wave correction. | Start C7. Its tick and decision sweep is where the wave verdicts belong, as distributions over settings. |
| D2 | What to do about the later one-way drift of an untouched side lane (F2). | (a) Leave it and report it. (b) Mirror the corner waypoints about the lane's centre in the M8 map. (c) Add keyed noise to minion formation. | (a) for now. (b) invents geometry and (c) is a rule with no source. A real-game measurement of an untouched top lane would decide. |
| D3 | The real-game measurements of the M8 document. | Someone takes them, or M8 goes on without. | Take them if anyone can. |
| D4 | Whether to commit this campaign. | Commit, or wait for the planning review. | The user's call. Nothing is committed. |
| D6 | The pursuit leak of F14. | (a) Every fighter chases where its target stood before the move step. That removes the leak and needs a new rule so that a target that walks away can still be hit. (b) Pursuers move in the order of who chases whom, and only rings move against one snapshot. That shrinks the leak to rings. (c) Leave it and report it. | (a) or (b) before C7, chosen by the planning assistant, with a test that changes a visible enemy's intent. It is one tick of lag, so it does not block planning C7. |
| D5 | The size of `capabilities.json` (L7). | Keep, or drop the per-seed values and paired rows from the file. | Keep. The owner asked for distributions and paired comparisons, and they are what a reviewer checks. |

## 7. Open questions and recommendations for the planning assistant

### 7.1 Open questions

- **Q1.** Should a wave verdict be a statement about every seed of one setting at all? F9 says that such a verdict flips with the tick. A share of settings, or a paired median with a count of seeds, is stable where I measured.
- **Q2.** Which tick should C7 use? 1.0 s differs from the finer ticks on the largest crash. 0.5 s differs from 0.25 s on the first crash time (57 s against 42 s), the time a wave is kept out (98 s against 92 s), and the held cycles (1.10 against 1.01).
- **Q3.** Are the 14 ward spots the right set, and should a ward on a lane or at a tower be possible?
- **Q4.** Should the area damage of the `push` mode draw on the attack credit (F3)?
- **Q5.** Should enemy tower health be observable while a team sees the tower (L6)?
- **Q6.** 006/Q1, Q2, Q5, and Q7 are still open. 006/Q6 is answered in part: rate damage now draws on the credit, and pursuit is fixed.

### 7.2 Recommendations

- **R1.** Give C7 a scripted policy that wards and a scripted laner that recalls. Without the first, C7's games never use C6's wards.
- **R2.** Put the wave numbers into C7's sweep as distributions: the `tick_spread` table of `capabilities.py` is the form.
- **R3.** Keep the six strict expected failures until the owner changes a bar.
- **R4.** Before the C7 gate, profile team memory. It is 19 percent of a farming game now.
- **R5.** Treat every wave result as a measurement of the simulator. A lane near balance amplifies a quarter second, so a single run proves little.

### 7.3 Readiness for C7

My judgment (Inference).

- **Ready.** C1 and C3 to C6 hold in tests that fail when the code is broken. One information boundary serves observations, masks, running intents, automatic positioning, and scripted policies. Snapshots and replays cover wards and wave memory.
- **Missing for C7 itself.** Scripted policies for all ten seats that use every subsystem, pinned replays of integrated games, the throughput gate on the integrated game, and the sweep.
- **Open beside it.** C2's wave fidelity (L1, L2) and any real-game check.

## 8. Where to push back

- **V1.** The sweep does not explain the fix. The M8 map's nearest bend turns 21 degrees, 319 units on blue's side. The sweep says that one bend of 10 or 20 degrees there tips the lane at 97 s, and the reviewer saw that single bend do so in 3 of 3 seeds. The map with all its bends holds until 247 s. I did not test pairs of bends. The M8 polyline may only have moved the bends to a luckier place, and the cause, a lane that amplifies any asymmetry, is still there.
- **V2.** The mechanism of F2 and the traced case of F9 come from scratch probes that are not in the repository. The sweeps are. I varied no rule across ticks, so F9 does not show that no single rule is at fault. The once-per-tick march is a candidate.
- **V3.** `attack_worth` gives a champion with a ready attack a burst on its first tick against a champion or a camp. That is consistent with a lane hit. It also moved every fight and clear number, and nobody has reviewed whether the fights still read sensibly.
- **V4.** I wrote the C6 kernel and the briefs for its tests. The delegate that wrote the tests found no kernel defect, which can mean that the tests share my blind spots. The exposure test in the behaviour comparison shares no code with `vision.py`, and I did not check that claim line by line.
- **V5.** I read the delegates' reports, ran their files, and read parts of `tests/test_vision.py`. I did not read all of the repaired tests. The repair delegate changed the meaning of eleven assertions, and its report lists each.
- **V6.** The pursuit test in `tests/test_combat.py` hides the difference between its two worlds in a slow on the target, not in a different route, because the delegate found no junction where two routes give different walks.
- **V7.** The accumulation and hold counts are about as low as in handoff 006. I changed the controls and the map, not the lane's fights, so this is no surprise. It also means that this campaign did not move C2 forward except for the bounce.

## 9. Next steps

- **User.** Decide D1 to D5.
- **Planning assistant.** Review this handoff and the M8 document. Answer Q1 to Q6 and R1 to R5. Write the criteria for C7.
- **Implementing assistant (me).** Wait for the review. I start no further checkpoint before then.
