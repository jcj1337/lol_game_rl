# Handoff 004: M7 corrections after the planning review

| | |
|---|---|
| Number | 004 |
| Date | 2026-11-11 |
| Type | Experiment and design correction. I changed prototype code, reusable map code, and the M7 document. I trained nothing and started no M8 work. |
| Responds to | The planning review of [handoff 003](003_m7_architecture.md) and of [`docs/design/M7_architecture.md`](../docs/design/M7_architecture.md), as seven issues in the owner's session prompt of 2026-11-11, plus the owner's clarifications in the same prompt |
| Status | Delivered. Waiting for review by the user and the planning assistant. |
| Author | Claude Code (Fable 5.2), the implementing assistant |
| Revised | 2026-11-11, before the planning review. An independent review found 5 defects and 10 items to fix in my first draft. §3.7 lists them and what I did. |

**Reading guide.** The user can read §1 and §6. The planning assistant should read all of it, then the changed
sections of the M7 document: 5.1, 5.6, 5.10, 7.1, 9.3, 10.1, and 13. §8 lists the claims I am least sure of.
Handoff 003 is frozen and I did not edit it. Where this handoff corrects one of its items, §3.6 says so.

## 1. Summary

- All seven issues of the planning review held against the code. I rebutted none. Each is fixed in the M7
  document, and six are backed by new tests or experiments.
- Waves: I rebuilt both experiments with a champion that can die and has to walk, and added no rule to produce an
  outcome. Neither a slow push nor a freeze passes the test written for it (F2, F3).
- The cause is measured. An even minion fight ends in 25.5 s and the wave interval is 30 s (F4). A documented rule
  that M7 had left out, the side-lane speed boost, more than doubles the thinned wave (F19). Three more documented
  rules come before the six real-game measurements (D1).
- Space: movement, range, and sight are now three separate measures, with tests at junctions, nearby paths, and
  walls (F7).
- Hidden state: the first version's method gave two answers for one information state. The corrected form gives
  one (F12).
- Roles and intents: a laner has a bounded roam allowance, `FIGHT` has one rule for lost vision, and the prototype
  now ends intents on completion (F8, F9, F11).
- Every results file records its command, seeds, and code hashes. I reran every number that the document keeps.
  138 tests pass, and 1 test of a known prototype defect is expected to fail (F10, F17, F18).
- An independent review found 5 defects in my first draft, among them a leak of hidden truth in the hindsight
  demonstration. All are corrected (§3.7).
- My judgment: M7 can guide the start of M8 at checkpoint C1. It makes no claim of realistic waves and no claim
  that training is feasible end to end (§7.3).
- The user committed my first draft as `6c37723` while the independent review ran. The fixes after that review
  are uncommitted. Two items wait for the user (§6).

## 2. Scope

**Done.**

- Read handoff 003, the M7 document, the independent review of 003, and the wave and map code in full.
- Checked each of the seven issues against the code before changing anything.
- Rebuilt the wave experiments myself: `experiments/m7/waves/scenarios.py`, five new tests, and two switches in
  `lane.py`, one for a sensitivity run and one for the side-lane speed rule.
- Had two delegates write code to my written briefs: the kernel prototype corrections, and the range and sight
  geometry in `riftgame/map.py`. I reran every test and compared their numbers with the results files.
- Wrote `experiments/m7/provenance.py` and reran the wave scenarios, the kernel scenarios, both kernel benchmarks,
  and the learner benchmark.
- Rewrote the affected sections of the M7 document, and audited the M8 acceptance criteria.
- Read three wiki pages through a fetch tool, for the current-health damage constant and the side-lane speed rule.
- Had the result reviewed by a delegate on Claude Opus 5.5, and corrected what it found.

**Not done.**

- No M8 code. No training run. No GPU measurement.
- I did not move the kernel prototype to the new range and sight measures. It still uses route distance (C2).
- I did not fix the seat-order defect in the prototype (F10).
- I did not build the hypothesis generator of section 9.3. The prototype has a stand-in (C3).
- I did not add unit collision, call-for-help, or the pushing advantage to the lane (C12).
- I did not read every line that the delegates wrote. I read the duty state machine, the `FIGHT` handling, the
  benchmark writer, and the whole map diff. Before the independent review I had not read `hindsight.py`. The
  review found a leak there, and I have since read its `known` and `hypothesis` functions. I have not read
  `tests/test_sight.py` line by line.
- I did not take any real-game measurement. I cannot run the game.
- I did not rerun any predecessor test, and the predecessor repository is untouched.

**Repository state.** Commit `6c37723` holds my first draft. The user made it. On top of it, `git status` shows
uncommitted changes to the M7 document, this handoff, the decision log, `experiments/m7/waves/` (code, tests,
results), `experiments/m7/kernel/hindsight.py` and its test, and the kernel results files.

## 3. Results

### 3.1 The seven issues

| # | Issue | Verdict | What I did | Where |
|---|---|---|---|---|
| 1 | Wave experiments | Held. The slow-push scenario was invalid, and the freeze rested on a champion that could not die. I found two more scenario errors, and one documented rule that the lane had left out. | Rebuilt both, and added the side-lane speed rule as a configuration. The result is still negative, now with its mechanism (F1 to F6, F19). | Document 5.6 |
| 2 | Spatial semantics | Held. Route distance decided sight and attack range. | Three measures in `riftgame/map.py`, with 34 tests (F7). | Document 5.1, 6.1 |
| 3 | Hidden-state evaluation | Held. An experiment in the prototype confirms it (F12). | New contract: an information state plus stated hypotheses, with a generator that takes only the information state. My first draft of the demonstration leaked enemy tower health. That is fixed and tested (§3.7, item 1). | Document 9.1, 9.3, 9.4 |
| 4 | Acceptance criteria | Held. The bot-income test contradicted the support item. The audit found ten more criteria to change. | Rewrote eleven criteria and listed each with its reason (F16). | Document 10.1 |
| 5 | Role locks | Held. A laner could leave forever through `MOVE`, `FIGHT`, or `CAMP`. | A duty state with a roam allowance, tested in the prototype. The test corrected my first form of the rule (F11). | Document 5.10 |
| 6 | Intent consistency | Held. Section 7.1 and section 6.3 contradicted each other. | One rule: pursue to the last-seen position, then `LOST`. The prototype now ends every intent on completion (F8, F9). | Document 7.1, 7.2, 6.3 |
| 7 | Reproducibility | Held. Results had no metadata, one file merged several runs, and evidence sat in a temporary folder. | A run block in every results file, a checker, separate benchmark files, and a rerun of everything retained (F17). | Document 13, 12 |

### 3.2 Findings

| ID | Finding | Label | Evidence |
|---|---|---|---|
| F1 | The lane code matches the documented rules for target priority, the 500-unit acquisition range, damage per hit, and tower shots. The faults were in the scenarios: a champion that could not die, that jumped to its spot each tick, and that stood inside the enemy wave's acquisition range, and a slow-push scenario at an unnatural phase of the wave clock. | Verified by reading | `experiments/m7/waves/lane.py`, functions `_acquire`, `_march`, `_minion_attack`. [`scenarios.py`](../experiments/m7/waves/scenarios.py), `Laner` and `post`. |
| F2 | No slow push. In 32 cases, the largest thinned wave at the enemy tower has 5 minions, and 7 with the side-lane speed rule. The test asks for 12 and for a later arrival than a hard push. | Verified | [`waves.json`](../experiments/m7/waves/results/waves.json), `emerged` for `A+B` and `A+B side speed`, cases `S4c` |
| F3 | No freeze that a champion with 650 health can hold. In 40 holding cases, none keeps the front in the band for over half of 240 s in every seed without a retreat. A hold without thinning costs 557 health in the first cycle. A hold with thinning is pushed out after about 60 s. The side-lane speed rule does not change this. | Verified | `waves.json`, cases `S5c` |
| F4 | An even six-on-six fight ends in 25.5 s, against a wave interval of 30 s. With the current-health share of minion damage switched off, it lasts 31.5 s. When both laners then only last-hit, a wave of 11 reaches the enemy tower 109 s after first contact. With the share, no wave reaches a tower in 300 s. The share is a rule of the reference patch, and both wiki pages state it. | Verified for the runs. Reported for the wiki text, which I read through a tool that summarizes. | `waves.json`, configurations `A+B` and `A+B flat damage`, cases `S0` and `S4c top from first contact, last hit, red last hit` |
| F5 | At a 0.5 s tick, 15 of 17 wave metrics are within 10 percent of a 0.125 s reference. Hold times no longer change by a factor of 2 to 5 between ticks. I attribute the old spread to the champion that jumped each tick. | Verified for the numbers. Inference for the cause. I ran no ablation that isolates it. | `waves.json`, `S7b_tick_sensitivity` |
| F6 | A lane coordinate has no width, so a champion cannot step out of a wave's way, and minions at 350 outrun a champion at 335. The scenarios use an in-path rule: a champion is a valid target while the waves are in contact, while it holds, or while it pushes, and a champion that has stepped aside hits nothing. The document adds a fifth wave mode, `hold`. Both are my assumptions. | Verified for the rule as coded and tested. Reported for the run that exposed the gap, which is not kept. | `scenarios.py`, `Laner.act`. `test_waves.py`, `test_a_champion_that_has_stepped_aside_kills_no_minion`. Document 5.6. |
| F7 | `riftgame/map.py` has `separation` for range and `sees` for sight, beside the unchanged route `distance`. Corridors around the graph's edges cannot hide the Raptor camp from mid lane, so four constructed wall segments were added. | Verified: I reran the 34 tests and read the diff. Reported: the distances in the document's table and the four mutation counts come from the delegate's scripts. The independent review recomputed the distances and three of the four counts. | [`tests/test_sight.py`](../tests/test_sight.py), [`map_summoners_rift.toml`](../riftgame/rulesets/map_summoners_rift.toml) |
| F8 | In the prototype, a run at decision interval n equals a run at interval 1 whose policy returns `KEEP` on the other ticks, for n of 2, 4, and 10, over 300 ticks, with both lane models. 84 intents ended inside the run at interval 2. | Verified | [`scenarios.json`](../experiments/m7/kernel/results/scenarios.json), `q1_timing`. `test_kernel.py`, `test_a_run_at_interval_n_equals_a_run_at_interval_1_that_keeps_between_decisions`. |
| F9 | A pursuer whose target enters fog walks to within its attack range of the last-seen position and ends with `LOST`. Its path is the same wherever the target hides. A target that reappears first is fought again. | Verified | `scenarios.json`, `q3_information.e_pursuit_of_a_target_in_fog` |
| F10 | Positions, health, and death ticks do not depend on which side the code visits first, in four staged fights. Kill rewards do. When both fighters die on one tick, one killer ends on 900 gold and 100 XP and the other on 800 and 0. | Verified. The defect is not fixed. A strict expected-failure test keeps it visible. | `scenarios.json`, `q2_fights.e_seat_order`. `test_kernel.py`, `test_kill_rewards_are_the_same_whichever_side_the_code_visits_first`. |
| F11 | A policy that leaves its lane whenever the mask allows roams 16.7 to 19.1 percent of the time after its first allowance is spent, against a bound of 20 percent, and never longer than 92 s at a stretch. With an allowance that stops at zero, which was my first rule, it roams 22 to 50 percent. The first allowance of 90 s comes on top. Over the first 10 minutes the share is 29 to 31 percent. | Verified, except the last sentence. That figure is Reported from the independent review's in-memory run. | `scenarios.json`, `role_duty` |
| F12 | For one information state and two source worlds that differ only in six hidden fields, the first version's method reports that the farming laner survives in 56 percent and in 100 percent of rollouts. It passes the first version's acceptance test in every rollout. The corrected method reports 31 percent for both. | Verified | `scenarios.json`, `hindsight`. [`test_hindsight.py`](../experiments/m7/kernel/test_hindsight.py). |
| F13 | The fight results of section 5.9 are unchanged. The rerun matches the first version's `kernel.json` in every field of `q2_fights`. | Verified by my own comparison | `git show 8108294:experiments/m7/kernel/results/kernel.json` against `scenarios.json` |
| F14 | Kernel throughput at the starting clock is 517 simulated seconds per wall second on one process (494 to 536, 7 runs, 34 percent CPU load at the start). Five processes give 9,460 agent decisions per second. The user was using the machine during this run. Commit `6c37723` holds a run of 591 at 11 percent load with 13,296 decisions per second on five processes, made before the last change to the lane code. Other runs on the same day gave between 504 and 634 at loads between 5 and 34 percent, so background load moves the figure more than the correction did. | Verified for the run in the file and for the committed run. The limiter is one CPython core per process. Reported for the other runs, whose files were overwritten. | [`bench_tick0.5_decision2.json`](../experiments/m7/kernel/results/bench_tick0.5_decision2.json) |
| F15 | Learner throughput on CPU with one thread is 44,132 decisions per second at batch 10, and 130,109 transitions per second in a PPO update at minibatch 2,048 (7 runs each). No environment is in that loop. | Verified | [`learner.json`](../experiments/m7/results/learner.json) |
| F16 | Eleven M8 acceptance criteria changed. One was a contradiction, five forced a strategic result, and the rest could not fail or tested a script. The independent review then found that my rewrite of the bot-lane gold criterion was still wrong, and that C1's roam criterion failed as worded. Both are fixed. | Verified by reading | Document 10.1, "Audit of the criteria" |
| F17 | The provenance checker reports all five results files as current against the working tree. | Verified | `.venv/Scripts/python.exe -m experiments.m7.provenance` |
| F18 | The full suite gives 138 passed and 1 expected failure. | Verified | `.venv/Scripts/python.exe -m pytest -q` |
| F19 | The side-lane speed rule of the reference patch moves the slow-push result. With it, the thinned wave from first contact in top lane reaches the tower with 7 minions after 38 s. Without it, 3 arrive after 23.5 s. Rounds 1 and 2 had no such rule, so their lane was not yet the reference patch's lane. | Verified for the runs. Reported for the rule's text, read through a tool that summarizes. | `waves.json`, configuration `A+B side speed`. `lane.py`, the `SIDE_SPEED` constants and `_speed`. |

### 3.3 What was rerun

| Evidence | Command | Result file and code id |
|---|---|---|
| Wave scenarios | `python -m experiments.m7.waves.scenarios` | `waves/results/waves.json`, code `16f6808d97cb34f6` |
| Kernel scenarios: timing, fights, information, snapshots, roles, hindsight | `python -m experiments.m7.kernel.scenarios` | `kernel/results/scenarios.json`, code `79954a4feb1dc4d6` |
| Kernel throughput at the starting clock | `python -m experiments.m7.kernel.bench start` | `kernel/results/bench_tick0.5_decision2.json`, code `191aadac553bfffd` |
| Kernel throughput at a 1.0 s tick | `python -m experiments.m7.kernel.bench` | `kernel/results/bench_tick1.0_decision5.json`, code `191aadac553bfffd` |
| Learner throughput | `python -m experiments.m7.bench_learner` | `results/learner.json`, code `adbf658da63741f3` |

All runs were made on an uncommitted tree. The content hashes in each run block identify the code. The checker
(F17) shows whether a file still matches the tree.

Not rerun: the reference patch research, the map consistency check's second derivation, and the hardware query.
The learner benchmark was not rerun after the independent review, because none of its sources changed.

### 3.4 Validation performed

| Check | Result | Label |
|---|---|---|
| `.venv/Scripts/python.exe -m pytest -q` | 138 passed, 1 expected failure: 58 in `tests/`, 41 wave, 40 kernel | Verified |
| Provenance checker | 5 files current | Verified |
| Fight numbers against the first version's committed file | Identical | Verified |
| Document lint: placeholders, dashes, semicolons, links | No placeholder, no broken link | Verified |
| Independent review of the first draft of this handoff, the document, and the decision log | 5 defects, 10 items to fix, 4 judgment calls, 8 notes. The reviewer compared about 70 numbers with the results files and found them equal except in the items of §3.7. | Reported by the reviewer. I reproduced or read each defect before I fixed it. |

Nobody has reviewed the fixes of §3.7.

### 3.5 Unresolved limitations

| ID | Limitation |
|---|---|
| C1 | Freezes and slow pushes do not emerge, against the owner decision. Whether a real lane behaves like this one is unknown until the three missing documented rules are in and someone takes the measurements of section 5.6. |
| C2 | The kernel prototype still measures sight and attack range by route distance. Its fight and vision results, and its throughput, are in the old geometry. `sees` costs 6 to 10 microseconds for a pair in range, against 0.6 for `distance` (two rough runs). |
| C3 | The hypothesis generator `activity_v0` is a design. The prototype's stand-in has three weighted beliefs for each enemy, and the truth-blind property is tested at one decision point, over six hidden fields and every enemy tower. |
| C4 | Sight terrain is constructed from corridors and four wall segments. A jungle path beside a lane is open to it. There is no brush. |
| C5 | The roam bound limits time charged as roaming, not absence. The abandoning policy is off its lane 27 to 36 percent of the time, and a laner may stand on its fountain without limit. The first 90 s come on top of the 20 percent. The two constants are untested against learned behaviour. |
| C6 | No training loop ran. The overnight volume is arithmetic on two benchmarks that leave out the policy network inside the loop, `sees`, and the rules that M8 adds. |
| C7 | The prototype's kill rewards depend on seat order when both fighters die on one tick (F10). |
| C8 | The wave result rests on placeholder champion numbers and on the plans I wrote: two thinning plans and eight holding plans. It is not a search over policies. |
| C9 | Values tagged `F1` were read through a tool that summarizes pages. That has not changed since handoff 003. |
| C10 | Only the blue champion of the slow-push and freeze cases can die and has to walk. The other wave cases, and the enemy laner in every case, still use the first scenario champion. The rows on creep score, attack capacity, and the hard push rest on it. |
| C11 | The owner decisions that the document quotes exist only in session prompts. They are not in the repository (R7). |
| C12 | Unit collision, the call-for-help rule, and the pushing advantage are rules of the reference patch that the lane does not model. Each bears on fight length or reinforcement. |
| C13 | The provenance checker identifies the code of a run. It does not hash a results file's own content, so it cannot detect a number edited by hand. The git history does that. |

### 3.6 Handoff 003 items that this handoff corrects

| 003 item | Status |
|---|---|
| 003/F4 | Replaced by 004/F8. The old test used orders that never end. |
| 003/F5 | The count of 155 identical observation pairs stands. The jungler distance in that run is now 7,558 units. |
| 003/F8, F9 | Rerun. See 004/F14 and F15. |
| 003/F12, F13, F14 | Replaced by 004/F2 to F5. The old hold of 219 s belonged to a champion that could not die. |
| 003/D1 | Replaced by 004/D1. |
| 003/D2, D3, D5 (names), D6, D7 | Decided by the owner's clarifications. Q1 on mana is decided the same way. |
| 003/D4 | Replaced by the duty state of section 5.10 (004/D2). |
| 003 §5 | The decision log of 003 still points at files in a temporary folder. I did not edit it. This handoff's log points only at files in the repository. |

### 3.7 What the independent review found, and what I did

The review ran on my first draft, on Claude Opus 5.5, read-only.

| # | Finding | Severity | Action |
|---|---|---|---|
| 1 | The hindsight generator copied the true health of every enemy tower into the information state. Taking 1,000 health off an unseen tower changed a rollout world while blue's observations stayed identical. | Defect | Fixed. The information state now holds only whether an enemy tower stands. A new test changes every enemy tower in turn, and the two source worlds now differ in a tower too. The kernel scenarios were rerun, and F12's numbers did not change. |
| 2 | The C1 roam criterion failed as worded. Over the first 10 minutes the abandoning policy roams 29 to 31 percent, not 20. My claim that every C1 criterion had a passing counterpart was too strong. | Defect | Fixed. The criterion, section 5.10, D2, and §7.3 now state the bound after the first allowance, and the 90 s on top. |
| 3 | The document said the scenario champion stays behind its own lead minion. It does not while it walks back. I had rewritten a failing test to check the spot it heads for, and logged nothing. | Defect | Fixed. The document says what the champion does, the test is renamed to what it asserts, and the log has the row. |
| 4 | My new bot-lane gold criterion still compared the pair's total gold with a solo laner's. Two champions get passive gold twice. | Defect | Fixed. The criterion now accounts for each source of gold apart and compares no totals. |
| 5 | The handoff held a placeholder labelled Verified. | Defect | Fixed. |
| 6 | I named measurements as the blocker while documented rules on the diagnosed mechanism were untried. | Should-fix | Fixed in part. I added the side-lane speed rule as a lane configuration and reran. It more than doubles the thinned wave (F19). The document now puts the three remaining rules before the measurements. I did not add those three (C12). |
| 7 | No test or number covered the release of minion aggro when reinforcements arrive. | Should-fix | Fixed. A new test covers it, and section 5.6 says that the plain holds retreat before that moment. |
| 8 | Under my in-path rule a lone champion cleared minions without taking damage. | Should-fix | Fixed. A champion that has stepped aside now hits nothing, and a pushing champion stays in the path. The waves were rerun. |
| 9 | The headline thinned wave came from a plan that did not thin. After an enemy crash the tower killed the casters. | Should-fix | Fixed. The plan now thins until the champion itself has killed three casters. The waves were rerun. |
| 10 | Several scenario champions are still immortal and jump. | Should-fix | Disclosed in section 5.6 and as C10. Not changed. |
| 11 | The derived compute figures were carried over, not recomputed. | Should-fix | Fixed. The fill script now derives them from the results files. |
| 12 | C5 said the attacker sees the target, where sections 5.1 and C6 say the attacker's team. | Should-fix | Fixed. |
| 13 | Two stale statements on travel times, and a wrong file cited for the snapshot size. | Should-fix | Fixed. |
| 14 | Labels missing or too strong: the hardware table, two figures of section 5.1, and one sentence of section 9.3. | Should-fix | Fixed. Each is now Reported. |
| 15 | The decision log lacked seven forks, and two rows disagreed. | Should-fix | Fixed by new rows. The log is append-only. |
| 16 to 19 | Four judgment calls: the hold line is a scenario constant, role assignments still end at 14:00 and at a tower's fall, the owner decisions are not in the repository, and the checker does not hash results. | Judgment call | Each is now stated where it applies: section 5.6, D2, C11 and R7, and C13. |
| 20 | Eight notes. | Note | Fixed: wording of two wave rows, two rounded distances, the Raptor width claim, the fourth mutation count, the rules named in OQ4, and the `KEEP` of a hidden `FIGHT`. Not changed: the position-only demonstration still moves only the jungler, where the first version's design moved every unseen enemy. |

## 4. Departures from the specification

1. **A fifth wave mode.** The prompt did not ask for a design change in the action table. I added the `hold` mode
   and the in-path rule to section 5.6, because the freeze experiment showed that no existing action lets a
   champion stand in a wave's path. Both are marked Assumed.
2. **All intents, not only `FIGHT`.** Issue 6 names `FIGHT`. I had the prototype end every intent on completion,
   because the `LOST` outcome needs that machinery, and because the old interval test rested on orders that never
   end.
3. **Four walls.** Issue 2 asks for a simple first implementation. Corridors alone failed the Raptor case, so the
   map has four constructed wall segments.
4. **Section 12 was cut, not preserved.** The two design candidate texts still exist in an old temporary folder. I
   did not copy 686 lines into the repository. The section now keeps only decisions with evidence in the
   repository.
5. **A sourced rule switched off, and one switched on.** The flat-damage run disables a rule of the reference
   patch. It is a diagnosis, not a proposed model. The side-lane speed run enables a rule of the reference patch
   that the lane had left out. The document reports all three configurations.
6. **The defect of F10 stays in the prototype.** The brief to the delegate said to report a seat-order failure and
   not to fix the kernel. M8 fixes it under C5.
7. **Delegated code.** Two delegates wrote the kernel and map changes. §2 says what I read.

## 5. Decision trail

The decision log of this run is [`004_m7_corrections_decisions.tsv`](004_m7_corrections_decisions.tsv). It has one
row per decision, with the reason and a pointer to a file in the repository. Rows with the phase `audit` add forks
that the independent review found missing, and correct two earlier rows.

## 6. Decisions needed from the user

| ID | Decision | Options | Recommendation |
|---|---|---|---|
| D1 | The six wave measurements of section 5.6 | (a) Someone with the game takes them in a custom game on patch 26.22, before or during C2. (b) M8 proceeds without them. C2 first adds the three documented rules that the lane lacks, and states that its waves are unverified. | (b) now, and (a) whenever someone can. The measurements do not block C1. Without them nobody can tell a wrong lane from a real one. |
| D2 | The reading of "fixed laning roles with temporary roams" | (a) A roam allowance. It starts at 90 s, which is also the longest single roam, and it refills so that roams take at most 20 percent of the time in the long run. When it is spent, the laner can only choose to walk back. The assignment ends at 14:00, or when an outer tower of the lane falls, as in the first version. (b) Another reading, in the owner's words, for example roles that outlast a fallen tower. | (a). It is applied in the document. The numbers are starting values. |

The fixes after the independent review are uncommitted. Committing them is the user's call. I pushed nothing and
opened no pull request.

## 7. Open questions and recommendations for the planning assistant

### 7.1 Open questions

- **Q1.** Is the `hold` wave mode acceptable, or is there a better way to let a champion stand in a wave's path
  (document OQ11)? The in-path rule also decides that a champion who has stepped aside hits nothing.
- **Q2.** What does the real scoreboard reveal about enemies out of vision (document OQ7)? The answer changes the
  hypothesis checks of section 9.3.
- **Q3.** For two deaths on one tick, the document proposes that each killer gets its reward and that a keyed draw
  picks the team with first blood. Is that acceptable?
- **Q4.** Should C8 build the five-activity generator, or start with hand-written hypotheses only?

### 7.2 Recommended changes to the master roadmap

Only substantive changes are listed. Technical detail stays in the M7 document. I applied none of them. The
recommendations of handoff 003 stand, except 003/R8 and 003/R10, which R2 and R1 replace.

- **R1.** M8 scope and gate. Record that "freezes and slow pushes emerge" is a goal that M7 did not reach. State
  that M8's gate does not depend on it, and that no rule may be added whose purpose is to produce a named wave
  behaviour.
- **R2.** External calibration (§7). Start it in M8 with the six wave measurements, and name who takes them. They
  need a person with the game client.
- **R3.** Evaluation principle. State that a comparison is conditioned on the deciding team's information and on
  stated hypotheses about what is hidden, never on the true hidden state, and that a report says when its ranking
  depends on a hypothesis.
- **R4.** M11. Add real sight terrain from the game's navigation grid, and brush. M8's terrain is constructed.
- **R5.** Roles. Record the bounded-roam reading once the owner confirms it (D2).
- **R6.** Pilot. State that the pilot's first task is an end-to-end throughput measurement, and that no
  feasibility claim precedes it.
- **R7.** Owner decisions. Write the owner decisions of 2026-11-11 and the later clarifications into the roadmap.
  They exist only in session prompts, and the M7 document quotes them.

### 7.3 Is M7 ready to guide M8?

My judgment is yes for the start of M8, with two stated limits (Inference).

- **Ready.** C1 can be planned and built from sections 5.2, 5.3, 5.10, 7, and 8. Four of its criteria have a
  passing counterpart in the prototype: the interval contract, intents that end, the roam bound after the first
  allowance, and snapshot replay. The invariant checker and the soak of random actions have none. C3 to C8 have
  criteria that can pass or fail.
- **Limit 1.** C2 starts as an investigation, not as an implementation of a settled lane. M7 does not show
  realistic waves, and the plan says so.
- **Limit 2.** The pilot's budget is derived, not measured. M7 does not show that training works end to end.
- **Before C1 starts**, the planning assistant should accept or change three things that are mine: the `hold` mode
  and the in-path rule (Q1), the roam rule (D2), and the hypothesis contract of section 9.3.

## 8. Where to push back

- **V1.** The wave negative depends on a laner with 650 health, 65 damage, and 0.65 attacks per second, and on
  plans that I wrote. A stronger champion or a better plan may hold a wave. C8 says the same.
- **V2.** The in-path rule and the `hold` mode are mine, and I got the rule wrong once. A reviewer who knows the
  game should check whether minions really stop attacking a champion that steps aside.
- **V3.** The four walls are built by a rule that I accepted from a delegate.
- **V4.** The truth-blind claim is tested at one decision point with a stand-in generator. My first draft leaked
  enemy tower health, and a reviewer found it, not my tests. The test now varies six hidden fields and every
  enemy tower. It does not vary every hidden field, so another leak of that kind may remain.
- **V5.** The roam constants are guesses. The debt rule came from one adversarial policy, not from a proof.
- **V6.** F5's explanation is an inference. The champion gained a speed, health, and a new position rule in one
  step.
- **V7.** Another program of the user's runs on this machine. The one-process rate moved between 504 and 634
  across the runs of one day, and the user was using the machine during the last ones (F14). Read every throughput figure with that spread in mind.
- **V8.** The M7 document grew to about 21,000 words. Section 5.6 is the longest part.
- **V9.** I audited the acceptance criteria myself, and I wrote most of them in the first place. The reviewer
  still found two wrong.
- **V10.** The first-blood rule for M8 is my proposal (Q3).
- **V11.** The side-lane speed constants come from one wiki page, read through a tool that summarizes. The rule
  changed the result, so it deserves a second reading before C2 relies on it.
- **V12.** Nobody has reviewed the fixes of §3.7.

## 9. Next steps

- **User.** Decide D1 and D2. Say whether to commit the fixes that follow `6c37723`.
- **Planning assistant.** Review sections 5.1, 5.6, 5.10, 7.1, 9.3, and 10.1 of the M7 document. Answer Q1 to Q4
  and R1 to R7. Approve or change the C1 criteria, because they gate the start of M8.
- **Implementing assistant (me).** Wait for an approved M7. I will not start M8 before then.
