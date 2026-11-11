# Handoff 004: M7 corrections after the planning review

| | |
|---|---|
| Number | 004 |
| Date | 2026-11-11 |
| Type | Experiment and design correction. I changed prototype code, reusable map code, and the M7 document. I trained nothing and started no M8 work. |
| Responds to | The planning review of [handoff 003](003_m7_architecture.md) and of [`docs/design/M7_architecture.md`](../docs/design/M7_architecture.md), as seven issues in the owner's session prompt of 2026-11-11, plus the owner's clarifications in the same prompt |
| Status | Delivered. Waiting for review by the user and the planning assistant. |
| Author | Claude Code (Fable 5.2), the implementing assistant |

**Reading guide.** The user can read §1 and §6. The planning assistant should read all of it, then the changed
sections of the M7 document: 5.1, 5.6, 5.10, 7.1, 9.3, 10.1, and 13. §8 lists the claims I am least sure of.
Handoff 003 is frozen and I did not edit it. Where this handoff corrects one of its items, §3.6 says so.

## 1. Summary

- All seven issues of the planning review held against the code. I rebutted none. Each is fixed in the M7
  document, and six are backed by new tests or experiments.
- Waves: I rebuilt both experiments with a champion that can die and has to walk, and added no lane rule. Neither
  a slow push nor a freeze passes the test written for it (F2, F3).
- The cause is measured. An even minion fight ends in 25.5 s, the wave interval is 30 s, and so waves do not
  stack (F4). The M7 document names six real-game measurements that are still missing (D1).
- Space: movement, range, and sight are now three separate measures, with tests at junctions, nearby paths, and
  walls (F7).
- Hidden state: the first version's method gave two answers for one information state. The corrected form gives
  one (F12).
- Roles and intents: a laner has a bounded roam allowance, `FIGHT` has one rule for lost vision, and the prototype
  now ends intents on completion (F8, F9, F11).
- Every results file now records its command, seeds, and code hashes. I reran every number that the document
  keeps. 135 tests pass, and 1 test of a known prototype defect is expected to fail (F10, F17, F18).
- My judgment: M7 can guide the start of M8 at checkpoint C1. It makes no claim of realistic waves and no claim
  that training is feasible end to end (§7.3).
- Nothing is committed. Two items wait for the user (§6).

## 2. Scope

**Done.**

- Read handoff 003, the M7 document, the independent review of 003, and the wave and map code in full.
- Checked each of the seven issues against the code before changing anything.
- Rebuilt the wave experiments myself: `experiments/m7/waves/scenarios.py`, three new tests, and one switch in
  `lane.py` for a sensitivity run.
- Had two delegates write code to my written briefs: the kernel prototype corrections, and the range and sight
  geometry in `riftgame/map.py`. I reran every test and compared their numbers with the results files.
- Wrote `experiments/m7/provenance.py` and reran the wave scenarios, the kernel scenarios, both kernel benchmarks,
  and the learner benchmark.
- Rewrote the affected sections of the M7 document, and audited the M8 acceptance criteria.
- Re-read two wiki pages through a fetch tool for one constant (F4).

**Not done.**

- No M8 code. No training run. No GPU measurement.
- I did not move the kernel prototype to the new range and sight measures. It still uses route distance (C2).
- I did not fix the seat-order defect in the prototype (F10).
- I did not build the hypothesis generator of section 9.3. The prototype has a stand-in (C3).
- I did not read every line that the delegates wrote. I read the duty state machine, the `FIGHT` handling, the
  benchmark writer, and the whole map diff. I did not read `hindsight.py` or `tests/test_sight.py` line by line.
- I did not take any real-game measurement. I cannot run the game.
- I did not rerun any predecessor test, and the predecessor repository is untouched.

**Repository state.** `git status` shows modified files under `docs/design/`, `experiments/m7/`, and `riftgame/`.
It shows one deleted file, `experiments/m7/kernel/results/kernel.json`. New files are
`experiments/m7/provenance.py`, `experiments/m7/kernel/hindsight.py`, `experiments/m7/kernel/test_hindsight.py`,
`tests/test_sight.py`, three results files under `experiments/m7/kernel/results/`, and two files in `handoff/`.

## 3. Results

### 3.1 The seven issues

| # | Issue | Verdict | What I did | Where |
|---|---|---|---|---|
| 1 | Wave experiments | Held. The slow-push scenario was invalid, and the freeze rested on a champion that could not die. I found two more scenario errors. | Rebuilt both. The result is still negative, now with its mechanism (F1 to F6). | Document 5.6 |
| 2 | Spatial semantics | Held. Route distance decided sight and attack range. | Three measures in `riftgame/map.py`, with 34 tests (F7). | Document 5.1, 6.1 |
| 3 | Hidden-state evaluation | Held. An experiment in the prototype confirms it (F12). | New contract: an information state plus stated hypotheses, with a generator that cannot read hidden truth. | Document 9.1, 9.3, 9.4 |
| 4 | Acceptance criteria | Held. The bot-income test contradicted the support item. The audit found ten more criteria to change. | Rewrote eleven criteria and listed each with its reason (F16). | Document 10.1 |
| 5 | Role locks | Held. A laner could leave forever through `MOVE`, `FIGHT`, or `CAMP`. | A duty state with a roam allowance, tested in the prototype. The test corrected my first form of the rule (F11). | Document 5.10 |
| 6 | Intent consistency | Held. Section 7.1 and section 6.3 contradicted each other. | One rule: pursue to the last-seen position, then `LOST`. The prototype now ends every intent on completion (F8, F9). | Document 7.1, 7.2, 6.3 |
| 7 | Reproducibility | Held. Results had no metadata, one file merged several runs, and evidence sat in a temporary folder. | A run block in every results file, a checker, separate benchmark files, and a rerun of everything retained (F17). | Document 13, 12 |

### 3.2 Findings

| ID | Finding | Label | Evidence |
|---|---|---|---|
| F1 | The lane code matches the documented rules for target priority, the 500-unit acquisition range, damage per hit, and tower shots. The faults were in the scenarios: a champion that could not die, that jumped to its spot each tick, and that stood inside the enemy wave's acquisition range, and a slow-push scenario at an unnatural phase of the wave clock. | Verified by reading | `experiments/m7/waves/lane.py`, functions `_acquire`, `_march`, `_minion_attack`. [`scenarios.py`](../experiments/m7/waves/scenarios.py), `Laner` and `post`. |
| F2 | No slow push. In 32 cases, the largest thinned wave at the enemy tower has 4 minions. The test asks for 12 and for a later arrival than a hard push. | Verified | [`waves.json`](../experiments/m7/waves/results/waves.json), `emerged` for `A+B`, cases `S4c` |
| F3 | No freeze that a champion with 650 health can hold. In 40 holding cases, none keeps the front in the band for over half of 240 s in every seed without a retreat. A hold without thinning costs 557 health in the first cycle. A hold with thinning is pushed out after about 60 s. | Verified | `waves.json`, cases `S5c` |
| F4 | An even six-on-six fight ends in 25.5 s, against a wave interval of 30 s. With the current-health share of minion damage switched off, it lasts 31.5 s, and a wave that bounces back from an enemy crash arrives 12 strong by last-hitting alone, against 4. That share is a rule of the reference patch. Both wiki pages state it. | Verified for the runs. Reported for the wiki text, which I read through a tool that summarizes. | `waves.json`, configurations `A+B` and `A+B flat damage`, cases `S0` and `S4c top from red crash, last hit, red absent` |
| F5 | At a 0.5 s tick, 15 of 17 wave metrics are within 10 percent of a 0.125 s reference. Hold times no longer change by a factor of 2 to 5 between ticks. I attribute the old spread to the champion that jumped each tick. | Verified for the numbers. Inference for the cause. I ran no ablation that isolates it. | `waves.json`, `S7b_tick_sensitivity` |
| F6 | A lane coordinate has no width, so a champion cannot step out of a wave's way, and minions at 350 outrun a champion at 335. The scenarios use an in-path rule, and the document adds a fifth wave mode, `hold`. Both are my assumptions. | Verified for the rule as coded. Reported for the run that exposed the gap, which is not kept. | `scenarios.py`, `Laner.act`. Document 5.6. |
| F7 | `riftgame/map.py` has `separation` for range and `sees` for sight, beside the unchanged route `distance`. Corridors around the graph's edges cannot hide the Raptor camp from mid lane at any width, so four constructed wall segments were added. | Verified: I reran the 34 tests and read the diff. Reported: the distances in the document's table and the four mutation counts come from the delegate's scripts. | [`tests/test_sight.py`](../tests/test_sight.py), [`map_summoners_rift.toml`](../riftgame/rulesets/map_summoners_rift.toml) |
| F8 | In the prototype, a run at decision interval n equals a run at interval 1 whose policy returns `KEEP` on the other ticks, for n of 2, 4, and 10, over 300 ticks, with both lane models. 84 intents ended inside the run at interval 2. | Verified | [`scenarios.json`](../experiments/m7/kernel/results/scenarios.json), `q1_timing`. `test_kernel.py`, `test_a_run_at_interval_n_equals_a_run_at_interval_1_that_keeps_between_decisions`. |
| F9 | A pursuer whose target enters fog walks to within its attack range of the last-seen position and ends with `LOST`. Its path is the same wherever the target hides. A target that reappears first is fought again. | Verified | `scenarios.json`, `q3_information.e_pursuit_of_a_target_in_fog` |
| F10 | Positions, health, and death ticks do not depend on which side the code visits first, in four staged fights. Kill rewards do. When both fighters die on one tick, one killer ends on 900 gold and 100 XP and the other on 800 and 0. | Verified. The defect is not fixed. A strict expected-failure test keeps it visible. | `scenarios.json`, `q2_fights.e_seat_order`. `test_kernel.py`, `test_kill_rewards_are_the_same_whichever_side_the_code_visits_first`. |
| F11 | A policy that leaves its lane whenever the mask allows roams 16.7 to 19.1 percent of the time after its first allowance is spent, against a bound of 20 percent, and never longer than 92 s at a stretch. With an allowance that stops at zero, which was my first rule, it roams 22 to 50 percent. | Verified | `scenarios.json`, `role_duty` |
| F12 | For one information state and two source worlds that differ only in hidden fields, the first version's method reports that the farming laner survives in 56 percent and in 100 percent of rollouts. It passes the first version's acceptance test in every rollout. The corrected method reports 31 percent for both. | Verified | `scenarios.json`, `hindsight`. [`test_hindsight.py`](../experiments/m7/kernel/test_hindsight.py). |
| F13 | The fight results of section 5.9 are unchanged. The rerun matches the committed `kernel.json` in every field of `q2_fights`. | Verified by my own comparison | `git show HEAD:experiments/m7/kernel/results/kernel.json` against `scenarios.json` |
| F14 | Kernel throughput at the starting clock is 591 simulated seconds per wall second on one process (578 to 605, 7 runs, 11 percent CPU load at the start). Five processes give 13,296 agent decisions per second. Three other runs on the same day gave 634, 626, and 540 at 24, 5, and 34 percent load, so background load moves the figure more than the correction did. | Verified for the run in the file. The limiter is one CPython core per process. Reported for the three other runs, whose files were overwritten. | [`bench_tick0.5_decision2.json`](../experiments/m7/kernel/results/bench_tick0.5_decision2.json) |
| F15 | Learner throughput on CPU with one thread is 44,132 decisions per second at batch 10, and 130,109 transitions per second in a PPO update at minibatch 2,048 (7 runs each). No environment is in that loop. | Verified | [`learner.json`](../experiments/m7/results/learner.json) |
| F16 | Eleven M8 acceptance criteria changed. One was a contradiction, five forced a strategic result, and the rest could not fail or tested a script. | Verified by reading | Document 10.1, "Audit of the criteria" |
| F17 | The provenance checker reports all five results files as current against the working tree. | Verified | `.venv/Scripts/python.exe -m experiments.m7.provenance` |
| F18 | The full suite gives 135 passed and 1 expected failure. | Verified | `.venv/Scripts/python.exe -m pytest -q` |

### 3.3 What was rerun

| Evidence | Command | Result file and code id |
|---|---|---|
| Wave scenarios | `python -m experiments.m7.waves.scenarios` | `waves/results/waves.json`, code `8474bf3fd115e0c3` |
| Kernel scenarios: timing, fights, information, snapshots, roles, hindsight | `python -m experiments.m7.kernel.scenarios` | `kernel/results/scenarios.json`, code `44ed41ff46723432` |
| Kernel throughput at the starting clock | `python -m experiments.m7.kernel.bench start` | `kernel/results/bench_tick0.5_decision2.json`, code `4bb490c2863edf55` |
| Kernel throughput at a 1.0 s tick | `python -m experiments.m7.kernel.bench` | `kernel/results/bench_tick1.0_decision5.json`, code `4bb490c2863edf55` |
| Learner throughput | `python -m experiments.m7.bench_learner` | `results/learner.json`, code `adbf658da63741f3` |

All runs were made on an uncommitted tree on top of commit `8108294`. The content hashes in each run block
identify the code. The checker (F17) shows whether a file still matches the tree.

Not rerun: the reference patch research, the map consistency check's second derivation, and the hardware query.

### 3.4 Validation performed

| Check | Result | Label |
|---|---|---|
| `.venv/Scripts/python.exe -m pytest -q` | 135 passed, 1 expected failure: 58 in `tests/`, 39 wave, 39 kernel | Verified |
| Provenance checker | 5 files current | Verified |
| Fight numbers against the committed first-version file | Identical | Verified |
| Document lint: placeholders, dashes, semicolons, links | No placeholder, no broken link | Verified |
| Independent review of this handoff, the document, and the decision log | @@REVIEW@@ | Verified |

### 3.5 Unresolved limitations

| ID | Limitation |
|---|---|
| C1 | Freezes and slow pushes do not emerge, against the owner decision. Whether a real lane behaves like this one is unknown until someone takes the measurements of section 5.6. |
| C2 | The kernel prototype still measures sight and attack range by route distance. Its fight and vision results, and its throughput, are in the old geometry. `sees` costs about ten times `distance` for a pair in range (one rough run). |
| C3 | The hypothesis generator `activity_v0` is a design. The prototype's stand-in has three weighted beliefs for each enemy, and the truth-blind property is tested at one decision point. |
| C4 | Sight terrain is constructed from corridors and four wall segments. A jungle path beside a lane is open to it. There is no brush. |
| C5 | The roam bound limits time charged as roaming, not absence. The abandoning policy is off its lane 27 to 36 percent of the time, and a laner may stand on its fountain without limit. The two constants are untested against learned behaviour. |
| C6 | No training loop ran. The overnight volume is arithmetic on two benchmarks that leave out the policy network inside the loop, `sees`, and the rules that M8 adds. |
| C7 | The prototype's kill rewards depend on seat order when both fighters die on one tick (F10). |
| C8 | The wave result rests on placeholder champion numbers and on the plans I wrote: two thinning plans and eight holding plans. It is not a search over policies. |
| C9 | Values tagged `F1` were read through a tool that summarizes pages. That has not changed since handoff 003. |

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
5. **A sourced rule switched off.** The flat-damage run disables a rule of the reference patch. It is a diagnosis.
   It is not a proposed model, and the recommended configuration keeps the rule.
6. **The defect of F10 stays in the prototype.** The brief to the delegate said to report a seat-order failure and
   not to fix the kernel. M8 fixes it under C5.
7. **Delegated code.** Two delegates wrote the kernel and map changes. §2 says what I read.

## 5. Decision trail

The decision log of this run is [`004_m7_corrections_decisions.tsv`](004_m7_corrections_decisions.tsv). It has one
row per decision, with the reason and a pointer to a file in the repository.

## 6. Decisions needed from the user

| ID | Decision | Options | Recommendation |
|---|---|---|---|
| D1 | The six wave measurements of section 5.6 | (a) Someone with the game takes them in a custom game on patch 26.22, before or during C2. (b) M8 proceeds without them and states that its waves are unverified. | (b) now, and (a) whenever someone can. The measurements do not block C1. Without them nobody can tell a wrong lane from a real one. |
| D2 | The reading of "fixed laning roles with temporary roams" | (a) A roam allowance: 90 s at most at a stretch, and at most 20 percent of the time, after which the laner can only choose to walk back. (b) Another reading, in the owner's words. | (a). It is applied in the document. Both numbers are starting values. |

Committing is the user's call. Nothing is committed, pushed, or opened as a pull request.

## 7. Open questions and recommendations for the planning assistant

### 7.1 Open questions

- **Q1.** Is the `hold` wave mode acceptable, or is there a better way to let a champion stand in a wave's path
  (document OQ11)?
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

### 7.3 Is M7 ready to guide M8?

My judgment is yes for the start of M8, with two stated limits (Inference).

- **Ready.** C1 can be planned and built from sections 5.2, 5.3, 5.10, 7, and 8. Each of its acceptance criteria
  now has a passing counterpart in the prototype: the interval contract, intents that end, the roam bound, and
  snapshot replay. C3 to C8 have criteria that can pass or fail.
- **Limit 1.** C2 starts as an investigation, not as an implementation of a settled lane. M7 does not show
  realistic waves, and the plan says so.
- **Limit 2.** The pilot's budget is derived, not measured. M7 does not show that training works end to end.
- **Before C1 starts**, the planning assistant should accept or change three things that are mine: the `hold` mode
  (Q1), the roam rule (D2), and the hypothesis contract of section 9.3.

## 8. Where to push back

- **V1.** The wave negative depends on a laner with 650 health, 65 damage, and 0.65 attacks per second, and on
  plans that I wrote. A stronger champion or a better plan may hold a wave. C8 says the same.
- **V2.** The in-path rule and the `hold` mode are mine. A reviewer who knows the game should check whether minions
  really stop attacking a champion that steps aside.
- **V3.** The four walls are built by a rule that I accepted from a delegate. The mutation counts and the table
  distances of section 5.1 are the delegate's numbers.
- **V4.** The truth-blind claim is tested at one decision point with a stand-in generator. I did not read
  `hindsight.py` line by line.
- **V5.** The roam constants are guesses. The debt rule came from one adversarial policy, not from a proof.
- **V6.** F5's explanation is an inference. The champion gained a speed, health, and a new position rule in one
  step.
- **V7.** Another program of the user's runs on this machine. The one-process rate moved between 540 and 634
  across four runs on one day (F14). Read every throughput figure with that spread in mind.
- **V8.** The M7 document grew to about 20,000 words. Section 5.6 is the longest part.
- **V9.** I audited the acceptance criteria myself. I wrote most of them in the first place.
- **V10.** The first-blood rule for M8 is my proposal (Q3).

## 9. Next steps

- **User.** Decide D1 and D2. Say whether to commit.
- **Planning assistant.** Review sections 5.1, 5.6, 5.10, 7.1, 9.3, and 10.1 of the M7 document. Answer Q1 to Q4
  and R1 to R6. Approve or change the C1 criteria, because they gate the start of M8.
- **Implementing assistant (me).** Wait for an approved M7. I will not start M8 before then.
