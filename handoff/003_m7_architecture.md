# Handoff 003: M7 architecture, prototypes, and the plan for M8

| | |
|---|---|
| Number | 003 |
| Date | 2026-11-11 |
| Type | Design and experiment. I wrote a design document, reusable code, and two feasibility prototypes. I trained nothing. |
| Responds to | [`docs/ROADMAP.md`](../docs/ROADMAP.md) v0.2, milestone M7, and the owner's M7 decisions (session prompt, 2026-11-11) |
| Status | Delivered. Waiting for review by the user and the planning assistant. |
| Author | Claude Code (Fable 5.2), the implementing assistant |
| Revised | 2026-11-11, before review. An independent review found 3 defects and 11 items to fix in my first draft. §8 lists them and what I did. |

**Reading guide.** The user can read §1 and §6. The planning assistant should read all of it, then
[`docs/design/M7_architecture.md`](../docs/design/M7_architecture.md). §7 holds the recommended roadmap changes. §8
lists the claims I am least sure of and the review's findings.

## 1. Summary

- [`docs/design/M7_architecture.md`](../docs/design/M7_architecture.md) is written. It covers the 15 M7 deliverables
  of the roadmap, eight M8 checkpoints with acceptance criteria, and the pilot's placement and budget.
- New reusable code in `riftgame/` holds a ruleset for patch 26.22, a route-graph map built from the game's map
  file, and keyed randomness. Two prototypes in `experiments/m7/` test the contracts. All 77 tests pass.
- Verified in a ten-champion prototype: fog with no leak into observations, exact snapshot replay, and paired
  randomness. The map is consistent with a second derivation within 3 percent.
- Not shown: the owner decided that freezes and slow pushes emerge. At a 0.5 s tick a freeze-like hold appears, but
  only under an assumed rule and at an impossible health cost. No stacked wave appeared (D1).
- One conflict of fact: a camp's respawn counts from its last death, not from a fixed clock (D2).
- The machine is an i5-11600K with 6 cores, 15.9 GB of memory, and an RTX 3060. An overnight pilot run is feasible.
- I wrote the M7 document myself, because the owner asked me to. The planning assistant should review it as another
  author's work.
- My first draft misreported three things. An independent review caught them, and I corrected them (§8).
- Nothing is committed. The predecessor repository is untouched. Seven decisions wait for the user (§6).

## 2. Scope

**Done.**

- Read `README.md`, the roadmap, and handoffs 001 and 002.
- Read the predecessor through a read-only delegate at commit `dbea191c`: its wave kernel, time model, economy,
  combat, counterfactual tools, and training numbers.
- Researched the reference patch through two delegates with web access.
- Compared two designs for the kernel contracts. One was mine. A delegate on Claude Opus 5.5 wrote the other
  without seeing mine.
- Wrote and tested `riftgame/ruleset.py`, `riftgame/map.py`, and `riftgame/rng.py`.
- Ran a wave prototype in two rounds and a kernel prototype. Delegates wrote the prototype code to my written
  briefs. I reran every test and read the results files.
- Measured kernel throughput and learner throughput.
- Had the document, this handoff, and the decision log reviewed by a delegate on Claude Opus 5.5.

**Not done.**

- No M8 code. Everything under `experiments/m7/` is prototype code.
- No training run of any size.
- No GPU measurement. `torch` with CUDA is not installed.
- I did not read all 3,700 lines of prototype code line by line. I read the results, the tests, and the parts that
  the delegates and the reviewer pointed at.
- I did not open the wiki pages myself. The delegates read them through a fetch tool that summarizes.
- I did not rerun any predecessor test.
- I did not rebuild the flawed slow-push scenario (§8, item 4).

**Repository state.** `git status` shows these untracked paths: `.gitignore`, `pyproject.toml`, `riftgame/`,
`tests/`, `experiments/`, `docs/design/`, `docs/reference/`, and three files in `handoff/`. A local `.venv/`
exists and is ignored.

## 3. Results

### 3.1 Where each M7 deliverable lives

| Roadmap deliverable | Section of the M7 document |
|---|---|
| State, observation, action, and timing contracts | 5.3, 6.3, 7.1 to 7.4 |
| Simulation time and decision frequency | 5.2 |
| Subsystem boundaries and interfaces | 5.11 |
| Faithful and approximate mechanics, combat considerations | 5.12, 5.9 |
| Scenario requirements matrix | 9.5 |
| Format of manual scenarios | 9.1 |
| Individual and coordinated alternatives | 9.2 |
| Snapshot requirements | 8.2 |
| Plausible hidden states | 9.3 |
| Basic warding in M8 or M11 | 6.4. The owner placed it in M8. |
| M8 checkpoint plan, and stand-ins until M9 | 10.1, 5.4, 5.5 |
| Pilot placement and scope | 10.2, 10.3 |
| Validation and reproducibility plan | 11.1 |
| Audit plan for the laning project | 10.5 |
| Risk and open-question register | 11.2, 11.3 |

### 3.2 Findings

| ID | Finding | Label | Evidence |
|---|---|---|---|
| F1 | The reference patch is 26.22. Its early clock runs 35 s ahead of pre-2026 knowledge: minions at 0:30, first camps at 0:55, Scuttler at 2:55. | Reported | Delegate research from the wiki and Riot's 26.1 notes, in [`docs/reference/`](../docs/reference/). Values and status tags are in [`patch_26_22.toml`](../riftgame/rulesets/patch_26_22.toml). |
| F2 | Many rules differ from older knowledge. Outer towers have 9000 health, plates no longer fall at 14:00, and the wave interval drops to 25 s at 14:00. | Reported | Same research. M7 document, section 3. |
| F3 | The route graph is consistent with a second derivation from the same map file. Fountain to outer tower is within 3 percent on all lanes. | Verified as a consistency check. It does not measure the real game. | [`tests/test_map.py`](../tests/test_map.py) |
| F4 | With orders that do not end inside the window, trajectories are identical at decision intervals of 1, 5, and 10 ticks. | Verified, in the prototype's form only. The prototype's orders never end, which is not the contract (§3.3). | [`test_kernel.py`](../experiments/m7/kernel/test_kernel.py), `kernel.json` `q1_timing` |
| F5 | Hidden state does not reach observations. 155 pairs of blue observations were byte-identical across two worlds that differed in two hidden fields. | Verified. The run is narrow: two fields, 31 ticks. | `kernel.json` `q3_information` |
| F6 | A restored snapshot replays with equal digests for 300 ticks. A changed action in top lane left bot lane identical for 300 s. | Verified | `kernel.json` `q4_snapshot_real_lane` |
| F7 | Fight outcomes change with distance to a tower, reinforcement distance, and speed. | Verified that outcomes respond. The numbers are placeholders, and the scripted chaser never gives up, so the escape counts overstate retreats. | `kernel.json` `q2_fights` |
| F8 | The kernel prototype runs 634 simulated seconds per wall second on one process at a 0.5 s tick and 2 s decisions (598 to 640, 7 runs). Five processes give 12,940 agent decisions per second. | Verified | [`bench.py`](../experiments/m7/kernel/bench.py) with the argument `start`, `kernel.json` `q5_starting_values` |
| F9 | On CPU, a two-layer network of 256 units infers 39,863 decisions per second at batch 10 and updates at 120,465 transitions per second on one thread. | Verified | [`bench_learner.py`](../experiments/m7/bench_learner.py), `learner.json` |
| F10 | An overnight run of 10 hours would produce 150 to 400 million agent decisions, bound by the kernel. | Inference from F8 and F9 | M7 document, section 10.3 |
| F11 | Wave timing and economy work at a 0.5 s tick: first contact at 51.5 s in mid, creep score 0.90, and creep score falling with attack capacity. | Verified | [`test_waves.py`](../experiments/m7/waves/test_waves.py), `waves.json` |
| F12 | At a 0.5 s tick, a champion that stands at the wave holds it outside its tower for 219 s of 240 when the enemy has 6 surplus casters. The champion absorbs about 19,700 damage. With 2 to 4 surplus casters the hold fails. | Verified. I reran the cases at 0.5 s myself. | `waves.json`, case `A+B`, `S5b k=6 hold` |
| F13 | No stacked wave forms. A lane one caster short reaches the enemy tower at 101.5 s with 5 minions. | Verified for that case. The scenario built to test a slow push was flawed and shows nothing. | `waves.json`, `S1b one caster short mid` |
| F14 | Hold times change by a factor of 2 to 5 between ticks of 0.25, 0.5, and 1.0 s. | Verified | `waves.json`, `S7b_tick_sensitivity` |
| F15 | The two designs agreed on route distance, individual minions, keyed randomness, no fight object, and masks from observations alone. | Verified by reading both. The owner decisions fixed much of this for both. | M7 document, section 12 |
| F16 | The predecessor's lane uses 9 integer cells and 2 ticks per turn of about 15 s. | Reported | Delegate read of the predecessor |

### 3.3 What the prototypes taught about the contracts

- The kernel prototype kept every order standing after it completed. That departs from the owner's rule that
  intents persist until completed or changed. The M7 document keeps the owner's rule, and C1 retests the timing
  contract (Verified by reading the prototype's results, section 7.2 of the document).
- Pursuers must move after everyone else, and all damage must be collected from the state at the start of the
  tick. Otherwise seat order biases fights (Reported by the delegate. No test permutes the seats yet.).
- Automatic execution can leak as easily as an observation. The lane's true front and a fogged target's true
  position were both read by accident before the delegate caught them (Reported).
- A digest must hash values. One that used object identity matched 241 of 300 replayed ticks (Reported).
- The kernel prototype shows enemy wards in sight to the other team. The real game does not
  (Verified, [`observe.py:88`](../experiments/m7/kernel/observe.py#L88)). I left the prototype as it is and wrote
  the rule into section 6.4.

### 3.4 Validation performed

| Check | Result | Label |
|---|---|---|
| `.venv/Scripts/python.exe -m pytest -q` | 77 passed: 24 in `tests/`, 36 wave, 17 kernel | Verified |
| Every ruleset and map value carries a status tag | Enforced by `tests/test_ruleset.py` | Verified |
| Document lint: placeholders, dashes, semicolons, links | No placeholder, no broken link | Verified |
| Predecessor working tree | Clean | Verified |
| Independent review, including a comparison of over 40 numbers with their source files | 3 defects, 11 should-fix, 7 judgment calls, 12 notes. See §8. | Verified |

### 3.5 Limitations

- All capability numbers are placeholders. Fight results show that the mechanics respond, not that they are right.
- Several tests take their expected values from the ruleset constants that the code also reads. They check wiring,
  not correctness.
- The kernel prototype uses the first-round lane rules and outer towers only. Its support income is passive gold
  only, and its minions never damage champions.
- The starting-clock benchmark began at 24 percent background CPU load.
- The jungle's path graph and its detour factor of 1.15 are my assumptions.
- Results files carry no timestamp and no code version. The first-round wave results were overwritten.

## 4. Departures from the specification

1. **Prototypes during M7.** Handoff 002 recorded that the owner overruled spikes during M7. The owner's M7 prompt
   asks for "targeted prototypes, tests, benchmarks". I followed the newer instruction. The prototypes came to
   about 3,700 lines.
2. **Authorship.** `handoff/README.md` gives design documents to the planning assistant. The owner asked me to
   write this one.
3. **Freezes and slow pushes.** The owner decided that they emerge. M7 shows less than that (F12, F13). I did not
   add a rule to force them.
4. **Camp spawns.** The owner decided that spawns follow the game clock. The reference does that for first spawns
   only. The design follows the reference for respawns and says so.
5. **Intent completion.** The kernel prototype departs from the owner's rule (§3.3). The document does not.
6. **Differential tests.** Handoff 001 §5 proposed that the new lane reproduce the old lane's trajectories. The new
   coordinates make that impossible. The audit plan uses property-level agreement.
7. **Rules I added.** The design restricts `LANE` actions to the home lane until an outer tower falls or 14:00. It
   gives champions a mana pool. It treats enemy level as public. It reads "lane towers" as three towers per lane
   and team. Each is marked Assumed in the document.
8. **Rules I left out.** Role quests, bounties, buff effects, the support item's poke income, and seven smaller
   rules of the reference patch (section 3.4 of the document).

## 5. Decision trail

I kept a decision log during the run. It has one row per decision, with the reason and a pointer to evidence. It is
[`003_m7_decisions.tsv`](003_m7_decisions.tsv). Some evidence pointers name files in the session scratchpad, which
is temporary. The independent review is [`003_m7_independent_review.md`](003_m7_independent_review.md). It
describes my first draft, before the corrections of §8. The two design candidates are still only in the scratchpad.

## 6. Decisions needed from the user

| ID | Decision | Options | Recommendation |
|---|---|---|---|
| D1 | How to settle wave behaviour | (a) Someone measures six things in a custom game on patch 26.22 (listed in section 5.6), and C2 starts from them. (b) The planning assistant supplies trusted numbers with sources. (c) Accept the simulator's wave behaviour without ground truth. | (a). Without ground truth nobody can tell a wrong model from a wrong test. |
| D2 | Camp respawns | (a) Follow the reference: respawn counts from the camp's last death. (b) Respawn on a fixed clock. | (a) |
| D3 | Starting clock | (a) 0.5 s tick and 2 s decisions, tested again at C7. (b) 1.0 s tick and 5 s decisions, which doubles throughput. | (a). A 1.0 s tick turns an 8.5 s recall into 9.0 s and changes wave results. The 2 s interval rests on arithmetic only. |
| D4 | Lane assignment | (a) Forbid `LANE` actions outside the home lane until an outer tower falls or 14:00. (b) No restriction, and add the reference's off-lane penalties. | (a) for M8. It is simpler. It also removes lane swaps from the pilot's first 14 minutes. |
| D5 | Omitted reference rules | Name any rule of section 3.4 that must return before the pilot. | None before the pilot. Bounties before M10. |
| D6 | Prototype code and names | (a) Keep `experiments/m7/` as evidence and keep the package name `riftgame`. (b) Delete the prototypes after review, or rename the package. | (a) |
| D7 | Lane towers in M8 | (a) Three towers per lane and team, with waves removed at the base until M10. (b) Outer towers only. | (a). A second and third tower make a lost outer tower matter. It adds work to C2 and C5. |

## 7. Open questions and recommendations for the planning assistant

**Open questions.**

- **Q1.** Should M8 carry mana, or should M9 add it?
- **Q2.** What does the real scoreboard reveal about enemies out of vision? The design assumes level only.
- **Q3.** One trusted jungle full-clear time on the 2026 clock would calibrate the jungle graph.
- **Q4.** Does the support item's second tier matter for bot-lane decisions?

**Recommended changes to the master roadmap.** I applied none of them.

- **R1.** M8 "Open" line. Remove "exact map representation", which is now a route graph. Add "ground truth for wave
  behaviour".
- **R2.** M8 deliverables. Add Scuttler capture with shrine vision and basic ward placement, as the owner decided.
  State how many lane towers M8 has (D7).
- **R3.** M8 "Done when". Add the throughput gate of section 10.4.
- **R4.** M7 deliverables. Mark the warding question as decided.
- **R5.** §10 "Choices deliberately left open". Tick length and decision interval now have starting values that C7
  confirms.
- **R6.** M9. Add the chase model as a named item (risk RK4 of the document), and say that the purchase-threshold
  test uses M8's discrete upgrades.
- **R7.** M12 pilot paragraph. State the placement after checkpoint C7, the pilot reward, and the overnight budget.
- **R8.** §7 external calibration. Start it in M8 with the wave measurements, not later.
- **R9.** Principle 10. Name the reference patch and the status tags on ruleset values.
- **R10.** §8 risks. Add that wave dynamics have no ground truth yet.
- **R11.** Assign bounties and role quests to a milestone. They are in no milestone now.
- **R12.** `README.md`. Its status line says "Planning and design stage". Update it when M7 is approved, and add
  one line on the layout of `riftgame/`, `tests/`, and `experiments/`.
- **R13.** M7 "Not in scope: Large-scale coding". M7 wrote about 3,700 lines of prototype. Say whether a later
  design milestone may do the same.

## 8. Where to push back

- **V1.** The reference values were read through a fetch tool that summarizes pages. A value tagged `F1` rests on
  one page. Spot-check any constant before relying on it.
- **V2.** I wrote both wave briefs and designed the scenarios. One scenario was flawed, and my first verdict used
  the wrong tick. A reviewer who knows the game should read `scenarios.py` before accepting F12 and F13.
- **V3.** The lane that is one caster short may behave correctly. I do not know what a real lane does.
- **V4.** The throughput gate of 300 is a judgment. The prototype lacks many M8 rules.
- **V5.** F10 is arithmetic on two measurements. No end-to-end training loop ran.
- **V6.** The starting clock rests on thin evidence: recall rounding and wave sensitivity for the tick, and
  arithmetic alone for the decision interval.
- **V7.** The second design came from a Claude model of another tier, not from another vendor, and both read the
  same owner decisions.
- **V8.** Delegates wrote the prototypes. I reviewed results and reran tests, not every line.
- **V9.** The M7 document is long, about 14,000 words with its tables. If it is too long, sections 3.4, 5.12, and
  12 are where to cut.
- **V10.** The lane-assignment rule, the mana pool, the public-level assumption, and the three tower tiers are
  mine (§4, item 7).
- **V11.** The independent review ran on my first draft. Nobody has reviewed the corrections below.

**What the independent review found, and what I did.**

| # | Finding | Severity | Action |
|---|---|---|---|
| 1 | My freeze verdict used a 1.0 s tick. At the 0.5 s tick that M8 starts from, a hold passes the prototype's own test. | Defect | Fixed. I reran the cases at 0.5 s and confirmed it. Section 5.6 now reports 0.5 s numbers and restates the conflict. `waves.json` is regenerated at 0.5 s. |
| 2 | The gank scenario does not test decision intervals. I had cited it for the 2 s interval. | Defect | Fixed. I read the scenario code and removed the claim. Section 5.2 says the 2 s value rests on arithmetic. |
| 3 | The document kept orders standing after completion, against the owner's rule, and did not say so. | Defect | Fixed. Section 7.2 follows the owner's rule. The prototype's difference is stated, and C1 retests. |
| 4 | The slow-push scenario cannot succeed by construction. | Should-fix | Disclosed in section 5.6. Not rebuilt. C2 rebuilds it. |
| 5 | Wave tables mixed tick lengths. | Should-fix | Fixed. Every row is at 0.5 s. |
| 6 | The quoted health cost of a hold came from failed holds. | Should-fix | Fixed. Section 5.6 gives 19,700 and names the assumed standing rule. |
| 7 | I claimed that both designs chose the hidden-state sampler. Only one did. | Should-fix | Fixed in section 12. |
| 8 | I called lateral slots a real-game rule. They are an assumption added after a failed round. | Should-fix | Fixed in section 5.6. |
| 9 | Sources, the log, and the candidates lived only in the scratchpad. | Should-fix | Partly fixed. The research notes are in `docs/reference/`. The log and the review are beside this handoff. |
| 10 | Section 3.4 missed three omitted rules. | Should-fix | Fixed. |
| 11 | The sampler could change a public level. | Should-fix | Fixed. The M8 sampler changes positions only (section 9.3). |
| 12 | Several acceptance criteria could not pass or fail, and two roadmap clauses had none. | Should-fix | Fixed in section 10.1 for C1, C2, C4, C5, and C7. |
| 13 | The pilot volume was optimistic, and its reward weights and baseline were undefined. | Should-fix | Fixed. The volume is a range, and the baseline measure is defined. The weights are left to the pilot's plan, and the document says so. |
| 14 | The rerun commands missed the starting-clock benchmark, and results have no provenance. | Should-fix | The command is added. The provenance gap is stated, not fixed. |
| 15 to 21 | Seven judgment calls: thin fight evidence, the map check, the cohort variant, pilot placement, three tower tiers, the lane restriction, and the amount of M7 code. | Judgment call | Each is now stated where it applies: F7, F3, section 5.6, section 10.2, D7, D4, and R13. |
| 22 to 33 | Twelve notes. | Note | Fixed: three map figures, the scenario example, the plates wording, colliding ids (document risks are now RK, questions OQ), a scaling figure, missing log rows, and the package's `numpy` dependency. Stated but not fixed: wiring tests and the narrow leak run (§3.5). |

## 9. Next steps

- **User.** Decide D1 to D7. Say whether to commit.
- **Planning assistant.** Review the M7 document as another author's work. Answer Q1 to Q4 and R1 to R13. Approve,
  or revise, the C1 and C2 acceptance criteria first, because they gate the start of M8.
- **Implementing assistant (me).** Wait for an approved M7 and for D1. I will not start M8 before then.
