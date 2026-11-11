# Handoff 001: review of ROADMAP v0.1 against the laning project

| | |
|---|---|
| Number | 001 |
| Date | 2026-11-11 |
| Type | Review. I wrote no code and ran no experiments. |
| Responds to | [`lol_game_rl/docs/ROADMAP.md`](../docs/ROADMAP.md) v0.1, §8, actions 1 and 2 |
| Status | Delivered. Waiting for the user's decisions (§6) and the planning assistant's revision. |
| Author | Claude Code (Opus 5.5), the implementing assistant |
| Revised | 2026-11-11, before review. This was a style pass under the technical-writing and unslop skills, plus one fix. The spikes in §10 now run during M7, so their results can inform the specification. Item IDs, evidence labels, links and recommendations are unchanged. |

**Reading guide.** The user can read §1 and §6. The planning assistant should read all of it and answer the C, R
and Q items when it revises the roadmap. §8 lists what I need from the M7 specification before I can implement
anything. §9 lists the claims I'm least sure of.

## 1. Summary

- The roadmap aims at the right things. It puts decisions before mechanics, keeps state apart from observation, and
  compares counterfactuals. Its order is the problem. Five milestones of simulator come before any learning or
  evaluation, and the predecessor's history says that order costs the most rework.
- I recommend five changes:
  - Fix the reviewer's input contract first (R1).
  - Replace M8 to M13 with vertical slices, starting with two solo lanes and both junglers under fog (R2).
  - Build an evaluator that works without multi-agent RL (R3).
  - Decide the time model in M7 (R4).
  - Measure decisions in a currency that is separate from the training reward (R5).
- Little of the old engine carries over as code. It hardcodes two players, one lane, one tower per side and perfect
  information. Its wave kernel, counterfactual tools, PPO core and test patterns are worth keeping. Rewrite each one
  and check the rewrite against the old engine with differential tests (§5).
- The user needs to make six decisions before M7 can be specified (§6).

## 2. Scope

I inspected these files:

- In this project, `docs/ROADMAP.md` v0.1 and `README.md`.
- In the predecessor `lol_gt_laning`, at commit `dbea191c` with a clean working tree:
  - The documents `CLAUDE.md`, `README.md`, `docs/findings.md`, `docs/methodology.md`, `docs/design_philosophy.md`
    and `docs/archive/history.md`, plus §0, §1.1, §2.3, §3.1 and §6.4 of `docs/model.md`
  - All of `engine/state.py`, and `LaneEnv` in `env/core.py`
  - The header, `step_turn` and `TurnResult` in `engine/mechanics.py`
  - The header and the state types in `engine/champions_m4.py`
  - The structure, the geometry fields and the research preset in `engine/config.py`
  - The headers of `diagnostics/branch.py` and `rl/shared.py`, and the function indexes of `lane_exit.py`,
    `network.py` and `observation_m4.py`
  - The records `artifacts/m4/benchmark.md` and the summary of the M4.8 report

I did not inspect these:

- The GitHub repository. The local remote is `jcj1337/lol_game_theory_laning`, but the README links
  `lol_laning_gt_rl`. The repository was probably renamed, but I haven't checked.
- The per-study experiment packages and most archived reports. Numbers labelled **Reported** come from the
  predecessor's summary documents. I did not recompute them from raw artifacts.
- The test suites. I ran no tests in either repository.

There was no specification to depart from. I changed nothing outside this folder and committed nothing.

## 3. Findings from the predecessor project

### 3.1 Architecture

| ID | Finding | Label | Evidence |
|---|---|---|---|
| F1 | The state types hardcode two players in one lane. | Verified | [`state.py:31`](../../lol_gt_laning/lanegame/engine/state.py#L31) defines `State` as 12 fields for sides A and B. [`champions_m4.py:95`](../../lol_gt_laning/lanegame/engine/champions_m4.py#L95) and [`:110`](../../lol_gt_laning/lanegame/engine/champions_m4.py#L110) define `M4Side` and `M4State(a, b)`. The `state.py` docstring implements mirror symmetry as "swap the two side records". [`env/core.py:118`](../../lol_gt_laning/lanegame/env/core.py#L118) calls `LaneEnv` a "Two-player simultaneous-move environment". |
| F2 | There is one tower per side, on a lane of 5 champion cells and 9 minion cells. | Verified | [`config.py:180-181`](../../lol_gt_laning/lanegame/engine/config.py#L180-L181) sets `base = 4` and `tower = 2`. `docs/model.md` §0.1 draws the lane. |
| F3 | Perfect information is a design rule. | Verified | [`design_philosophy.md:43`](../../lol_gt_laning/docs/design_philosophy.md#L43) says "Hidden state is forbidden; the observation is decodable back to the state". `decode_m4` in [`observation_m4.py:267`](../../lol_gt_laning/lanegame/env/observation_m4.py#L267) exists to show it. |
| F4 | The jungle is a hand-set gank probability, not an agent. | Verified | §6.4 at [`model.md:1504`](../../lol_gt_laning/docs/model.md#L1504) gives p = clip(0.12(e+2)/4 + behaviour term + Shove term − strength term, 0, 0.30) × vision factor. §2.3 at [`model.md:347`](../../lol_gt_laning/docs/model.md#L347) says "no jungle state (ganks are a hazard rate)". |
| F5 | The configuration sprawls. It has about 160 annotated fields in 1,332 lines, a chain of 12 presets and two resolvers chosen by flags. | Verified | I counted the lines and fields of `engine/config.py`. `CLAUDE.md` lists the preset chain. The resolvers are `champions.resolve_turn` and `champions_m4.resolve_turn_m4`, and the environment picks one with `cfg.is_m4` and `cfg.champion_mode`. The cause is a rule in `design_philosophy.md` §4. Every mechanic is an opt-in field, and every old preset stays bit-identical. |

### 3.2 Reusable components

| ID | Finding | Label | Evidence |
|---|---|---|---|
| F6 | The natural-wave kernel already takes each side's champion contributions as inputs. It is not yet a clean kernel. | Verified | [`mechanics.py:793`](../../lol_gt_laning/lanegame/engine/mechanics.py#L793) has the signature `step_turn(..., champion_reach, champion_budget, champion_targets)`. Inside, it still calls `wave_of(acts[s])` and `objective_of(acts[s])` for Thin and Pressure. It allows one enemy target per side. `TurnResult` at [`mechanics.py:104`](../../lol_gt_laning/lanegame/engine/mechanics.py#L104) records kills per side, not per champion. |
| F7 | A two-player counterfactual evaluator exists, and it accepts any policies. | Verified | [`branch.py:54`](../../lol_gt_laning/lanegame/diagnostics/branch.py#L54) defines `Snapshot`. Lines 141 to 189 define `Plan`, `Commit`, `FollowPolicy` and `FunctionPlan`. [`branch.py:371`](../../lol_gt_laning/lanegame/diagnostics/branch.py#L371) defines `branch`. The module docstring says paired rollouts share three random streams per rollout index. [`lane_exit.py:179`](../../lol_gt_laning/lanegame/diagnostics/lane_exit.py#L179) computes the settled readout E_h. |
| F8 | Paired comparisons rely on a fixed chance vector of 10 random numbers per turn, drawn whatever happens. | Verified (fact). The scaling claim is Inference. | The header of `champions_m4.py` and `model.md` §1.1 describe the vector. My inference is that it can't serve 10 agents whose branches change which events occur. That case needs keyed random streams. |
| F9 | Several pieces are generic and tested. | Verified that they exist and what they do. I did not run their tests. | `exact/matrix_game.py` has 168 lines, with saddle detection and a HiGHS linear program. `rl/ppo.py` has 206 lines, with GAE and the clipped update, and `tests/test_rl_reference.py` checks it. `rl/agent.py` writes SHA-256 checkpoint digests. `tests/test_invariants.py` holds the invariant patterns, which are zero-sum payoffs, cached results equal to direct computation, and mirror symmetry. |

### 3.3 Research findings that bear on the new roadmap

| ID | Finding | Label | Evidence |
|---|---|---|---|
| F10 | Self-play policies are competent only on the states that self-play produces. | Reported | Power gaps of ×1.25 or more occur on 0.07% to 0.37% of turns. A specialist trained on gaps beat the policy by +2.11 ± 0.62. The critic's R² falls from 1.00 on the observation to 0.18 at its second layer ([`findings.md:156-166`](../../lol_gt_laning/docs/findings.md#L156-L166)). My inference is that reviewed real-game states, many of them gap states, fall outside this distribution. Roadmap scenario 5 is a gap state. |
| F11 | Counterfactual values depend on the policies that play out the continuation, and the trained policies are exploitable. | Reported | [`history.md:241`](../../lol_gt_laning/docs/archive/history.md#L241) says "E_h depends on the continuation policies". Attackers trained on a quarter of the target's budget won by +1.02 ± 0.48 ([`findings.md:138`](../../lol_gt_laning/docs/findings.md#L138)). In M5 the attackers won by +2.96 and +1.15 ([`findings.md:222`](../../lol_gt_laning/docs/findings.md#L222)). |
| F12 | Most of the work went into fixing the game's incentives, not the learner. | Reported | The predecessor fixed the dominance of Shove in the economy, not in the learner ([`findings.md:86-95`](../../lol_gt_laning/docs/findings.md#L86-L95)). It rejected about 40 rules for a single lane ([`history.md:110-144`](../../lol_gt_laning/docs/archive/history.md#L110-L144)). One fixed collection rate was "doing the work zoning should do, with the wrong sign" ([`findings.md:104-106`](../../lol_gt_laning/docs/findings.md#L104-L106)). |
| F13 | Raw leads mislead, and no single currency has been validated. | Reported | In about two thirds of lane-exit states, the lead changes materially over the next 20 turns ([`findings.md:174-176`](../../lol_gt_laning/docs/findings.md#L174-L176)). Gold leaders who were behind in XP or HP lost more than predicted. Nobody identified the cause ([`history.md:241-242`](../../lol_gt_laning/docs/archive/history.md#L241-L242)). |
| F14 | One lane with a dense reward needed 32.8M transitions per run and was still improving. | Reported | One thread runs about 8.8k environment turns per second with the lane cache ([`artifacts/m4/benchmark.md`](../../lol_gt_laning/artifacts/m4/benchmark.md)). That figure is for `m4()` at an older commit, and the research preset does more work per tick. M5 trained 6 seed pairs at 32.768M transitions per run ([`findings.md:206`](../../lol_gt_laning/docs/findings.md#L206)). The campaign took about 36 hours on 6 workers ([`README.md:167`](../../lol_gt_laning/README.md#L167)). Pure self-play was still improving at the end ([`findings.md:225`](../../lol_gt_laning/docs/findings.md#L225)). Every run used a dense per-turn reward. |
| F15 | Only the exactly solvable small game showed self-play growing more exploitable with training. | Reported | [`findings.md:57-59`](../../lol_gt_laning/docs/findings.md#L57-L59) and [`history.md:252-253`](../../lol_gt_laning/docs/archive/history.md#L252-L253). |
| F16 | Scripted policies have limits as an evaluation tool. | Reported | [`history.md:164-165`](../../lol_gt_laning/docs/archive/history.md#L164-L165) says "scripted equilibria describe the strategy set, not the game". This limit bounds R3. |

## 4. Assessment of the roadmap

### 4.1 What to keep

These parts of the roadmap are sound and should survive any revision:

- Observation kept separate from state and designed from the start (principle 3 and the note under M11)
- Reproducible counterfactuals (principle 6)
- Scenario tests that include counterexamples and sensitivity checks (§4)
- The rule against an elaborate plugin framework
- Deferred ingestion and user interface
- Detailed milestone plans written only when each milestone starts

### 4.2 Concerns, most consequential first

**C1. The reviewer's input is undefined, so the core scenarios may have nothing to fill them.** Deferring ingestion
is right, but the roadmap should fix its information contract now. My account of Riot's Match-v5 timeline is
Inference from memory, and I did not check it this session (V1). As I understand it, the timeline has one frame per
player per minute, with position, gold, XP, level and CS. It adds timestamped events such as kills, wards,
buildings, monsters and purchases. It has no minion-wave or jungle-camp state. If that holds, official data can't
reconstruct the first two scenarios in §4, which are freeze versus push and recall timing. The roadmap applies
principle 1, outcome-driven design, to mechanics but not to data.

**C2. Building layer by layer delays all feedback to M12 and M13.** Five milestones of mechanics come before any
agent learns or the evaluator judges any decision. In the predecessor, each problem in the game surfaced only when
downstream work touched it (F12). The work that exposed them included a PPO pilot, calibration screens and
counterfactuals. Integrating three lanes, the jungle, combat, objectives and vision before any such check maximizes
rework.

**C3. The evaluator depends on multi-agent RL succeeding.** M13 depends on M12, yet the evaluator's instruments
accept any policies (F7). The predecessor used them with learned continuations and in screens of scripted policies
against each other. RL doesn't remove the dependence on continuation policies (F11). It only makes one continuation
stronger. Under the current plan, the product waits on the hardest part, which also needs the most compute.

**C4. The time and action model is the costliest decision to reverse, and the roadmap frames it only as "tick
size".** The real choice is between synchronous turns and asynchronous options with durations, such as travel,
clears and recall. A second choice is whether an agent can change its intent partway through. These choices fix the
RL interface and credit assignment. They also fix what the reviewer counts as a decision, and how the random streams
work.

**C5. Training on terminal wins alone is probably infeasible at this scale.** This claim is Inference with no
measurement behind it (V4). A win is one bit per game, shared by 10 agents that each make over 100 decisions. The
predecessor needed 33M dense-reward transitions for one 1v1 lane (F14). The roadmap also merges two questions under
"team winning". One is what the evaluator measures, and the other is what the agents train on.

**C6. The combat outcome models are oracles, and the roadmap doesn't reconcile them with the rule against
proxies.** Oracles are acceptable for macro research, but they limit what anyone can claim. Whether a fed bruiser
can hold a 1v2 will be the oracle's answer, not an emergent one. M9's "can sometimes favor a fed solo champion"
invites tuning the oracle until it agrees, which §4 of the roadmap forbids.

**C7. Vision (M11) arrives after objectives (M10), but a jungle without fog is degenerate.** If the jungler and the
laners see everything, nobody has anything to track, and gank decisions collapse. M13's rollouts "from plausible
hidden states" also need a belief or sampling model. That model belongs in the same design as the observation model.

**C8. Some fidelity is premature, and some requirements are missing.** Two items are premature:

- Item purchases. The predecessor found item tiers inert and replaced them with one number for invested gold
  (M4.2c).
- Camp-by-camp profiles, before anyone knows what tracking needs.

These requirements are missing:

- Bot lane as a 2v2, and how its farm is split
- Several towers per lane
- Respawn and bounty rules
- An execution-skill parameter on outcome models, which makes "stated execution assumptions" concrete
- A throughput target

**C9. The M12 completion criterion is weak.** "Outperform relevant baselines" saturates, as fixed suites did in the
predecessor. Lower bounds on exploitability and the stability of rankings are the meaningful tests.

**C10. The README compares the reviewer to a chess engine (lower priority).** A chess engine searches a game whose
rules are exact and fully observed. Here the rules are a model, information is hidden, and the answer depends on the
opponent. The analogy fits how the evaluator works, which is search plus a value estimate. It doesn't fit how much
authority the answers carry, and public documents should say so.

### 4.3 Recommendations

**R1. Add a reviewer input contract to M7 (C1).** For each target decision, list the variables it needs and where
each one comes from at review time. Decide the v1 assumption explicitly (D1). I recommend a scenario evaluator, where
the user specifies the state and match data can prefill it. Automated ingestion comes later and must meet the same
contract.

**R2. Restructure M8 to M13 as vertical slices, each ending in an evaluated decision family (C2, C7).**

| slice | content | decisions evaluated | gate |
|---|---|---|---|
| 1 | Two solo lanes on opposite sides of the map and both junglers, under fog. It contains the ported wave kernel, a coarse jungle, and a map graph with travel times and last-seen memory. It also has a first engagement oracle, scripted policies, and the branch evaluator with hidden-state sampling and a settled readout. | Whether pushing is safe given the jungler's last sighting, when to gank, and whether to recall or stay | The evaluator ranks candidate actions and reports their robustness across continuation policies. Anti-leak tests pass. One small exactly solvable arena agrees with the evaluator. |
| 2 | PPO on slice 1, with one shared policy, a role embedding and memory | Whether a learned continuation changes slice 1's rankings, and lower bounds on exploitability | The result sets how much to invest in multi-agent RL. |
| 3 | The full map, bot lane as a 2v2, timed dragon and herald, and archetype capability vectors | Whether to contest an objective or trade it, and whether to rotate or stay | |
| 4 | Structures, complete games, the win condition and a win-probability model over the macro state | Whether to split push or group | |
| then | External validation and a scenario library | | |

Slice 1 is the smallest map that contains the most important new element, a jungler agent in place of the gank
probability (F4). D2 offers an alternative, a slice 0 that ports the old lane first.

**R3. Make the evaluator independent of RL, and report how robust each ranking is (C3).** Score each candidate
action under a population of continuation policies. The population holds scripted styles, variants with perturbed
skill, and learned policies once they exist. Results such as "A beats B under 6 of 6 continuations" and "it depends
on how the opponent plays" become part of the output. F16 sets the limit, because scripted continuations cover only
the strategies they contain. So R3 doesn't claim that scripted policies are enough. It claims that the evaluator
shouldn't need RL in order to exist, and that RL then extends the population. Keep the predecessor's rule that
critic values are never evidence in rare states.

**R4. Decide the time model in M7 (C4).** I recommend these choices:

- Synchronous fixed macro turns
- Intents that persist across turns and can change on any turn
- Random streams keyed by entity, event and time

The turn length is my inference (V2). The old lane spawns a wave every 2 turns. League spawns waves every 30
seconds, which implies about 15 seconds per turn. Level 14 arrives at turn 94, about 23.5 minutes, which fits. Keeping
that scale lets the wave kernel move over without retiming.

**R5. Separate the evaluation currency from the training reward (C5, F13).** Until complete games exist, evaluate on
a settled readout reported as a vector. Its components are gold, XP, deaths and respawn time, structures and
objectives. Where one action is at least as good on every component, it dominates and needs no weighting. Later, a
win-probability model becomes the currency, fitted to simulated games and possibly to real ones. It can also shape
training rewards as a potential, which leaves the optimal policies unchanged (Ng, Harada and Russell, 1999).

**R6. Rewrite the rule against proxies so that it covers oracles (C6).** An outcome model may sit outside the
simulation's physics, but it must meet five conditions:

- It depends on explicit state only.
- It is monotone in capability.
- It takes execution skill as a parameter.
- It sits behind one function signature, so a better model can replace it.
- Every reviewer claim that depends on it names it.

**R7. Lighten the reproducibility regime early (F5).** Keep determinism and common random numbers strict. Replace
"every rule is an opt-in field forever" with versioned rulesets and golden replays pinned at milestone boundaries.
D4 asks the user to choose.

**R8. Start an external-data track in M7.** The track covers three things:

- What data is available (D6)
- Calibration targets such as clear times, gold and XP curves, and objective timings
- A few broad relationships to check the simulator against

**R9. Strengthen the completion criteria (C9).** Replace "outperform baselines" with lower bounds on exploitability
and with the stability of rankings across continuation policies.

## 5. Code reuse plan

Treat the predecessor as a specification and a test oracle, not as a dependency. Install it read-only in a separate
environment and write differential tests against it. For example, in 1v1 configurations with one tower, the new lane
kernel must reproduce the lane trajectories of `m45_calibrated()` on recorded games. The comparison covers kills,
crashes and tower hits.

| component | decision | notes |
|---|---|---|
| The natural-wave kernel, meaning the natural path of `mechanics.py` with the half-wave Lanchester law, entry crash and tower fire | Rewrite, with differential tests | Drop the v1, v2 and siege modes. Generalize to several towers and to the contributions of several champions per side. |
| The `progression.py` formulas for the XP curve, H(L) and the saturating M(S) | Port the formulas and recalibrate | The parameters were tuned for the 1v1 abstraction. |
| The farm and collection rules | Port the concepts | The bot-lane split is new design. |
| `branch.py`, `lane_exit.py` and the statistics helpers | Rewrite against the new API and keep the semantics | They are the evaluator's core. |
| `rl/ppo.py`, the masked categorical distribution and the checkpoint digests | Port nearly as they are | Add a role embedding, memory and a centralized critic later. |
| `exact/matrix_game.py` | Port as it is | It serves small exact sub-arenas, such as tracking on a graph. |
| The test patterns for invariants, common random numbers, masks equal to legal sets, and replay digests | Port the patterns | Port the patterns, not the tests themselves. |
| The `champions*.py` resolvers, the 61-code action encoding, the observation encoders, the gank probability, the `GameConfig` chain, the demo and the opponent-modelling agents | Don't port | They assume two seats and perfect information, and they center on action codes. Opponent modelling may matter later as player-type inference. |
| The process, meaning pre-registration, confirm flags for expensive runs, the split between artifacts and runs, and the four-question test for a new mechanic | Keep | |

## 6. Decisions needed from the user

| ID | Decision | Options | Recommendation |
|---|---|---|---|
| D1 | Input to the v1 reviewer | (a) The user specifies the scenario state, and match data can prefill it. (b) Riot's match timeline only, which limits review to minute-level macro decisions and excludes wave management. (c) Parsing videos or replays, a large separate project. | (a) |
| D2 | First slice | (a) Two solo lanes and both junglers under fog (R2). (b) A slice 0 that rebuilds the old 1v1 lane in the new architecture and reproduces the old results before adding junglers. It is a safer port but delays anything new. (c) A slice built around objectives, which needs the full map. | (a), with the differential tests in §5 doing slice 0's job |
| D3 | Which opponents the reviewer assumes | (a) Report results under both competent and rank-typical continuations. (b) Competent only. (c) Rank-typical only. | (a). Ranking robustness (R3) gives this almost for free. |
| D4 | Reproducibility regime | (a) Strict determinism, golden replays at milestone boundaries, and versioned rulesets. (b) The predecessor's rule of opt-in fields kept forever. | (a) |
| D5 | Spikes in M7 | Allow three small throwaway prototypes during M7 (§10), in a `spikes/` folder outside the package, so their results can inform the specification? | Yes |
| D6 | External data | (a) Audit from the documentation only. (b) Call Riot's API, which needs the user's developer key and a policy review first. | (a) first, then (b) after the policy review |

## 7. Open questions for M7

- **Q1. Input.** Which scenario variables can a v1 reviewer realistically get, and from what source?
- **Q2. Time.** Is a synchronous turn of about 15 seconds fine enough for the target decisions? Those include gank
  arrival against crash timing, recall windows and objective arrival. Which decisions need finer timing?
- **Q3. Currency.** Which decision families can a settled readout over a medium horizon judge? Which need a win
  probability?
- **Q4. Policy dependence.** How often do rankings flip across a population of scripted continuations? This can be
  measured before any RL, and the answer should set a decision rule for how much to invest in RL.
- **Q5. Belief.** Find out whether last-seen memory is enough for jungle tracking and hidden-state sampling. Combine
  it with the map-graph nodes reachable since the last sighting and the evidence from camps. If that isn't enough, a
  particle filter is the alternative. Test both on a toy problem.
- **Q6. Oracle v0.** What goes into an engagement's context? Which family of formulas applies? How does execution
  skill enter? What calibration evidence exists?
- **Q7. Throughput.** What does one turn of a 10-champion graph world cost in Python? Does the project need a
  vectorized or compiled engine? Set the target from a spike measurement.
- **Q8. Wave kernel.** Can it handle three towers and several champions per side and still reproduce the old
  trajectories in the 1v1 case?
- **Q9. Opponent.** This is the product question behind D3. Should the reviewer assume competent opponents or
  rank-typical ones? M5's trade-off between exploiting styles and keeping competence shows that the two assumptions
  give different answers.
- **Q10. Kill criteria.** Which results would change the approach? One example is rankings that are unstable across
  continuations in most states. Another is key variables that nobody can observe at review time.

## 8. What I need from the M7 specification before implementing it

1. **Binding or advisory.** Mark each requirement as one or the other. List the choices I may make freely, such as
   internal data structures.
2. **Interfaces at the level of data shapes.** The specification should define these:
   - The entities in the world state
   - The observation each player gets, and its memory
   - The set of intents and actions, with their legality rules
   - The signature of the outcome model
   - The keys of the random streams
   - The contents of a snapshot
   - The inputs and outputs of the evaluator
3. **Acceptance tests with pass or fail criteria.** A criterion can be a number or a qualitative relationship. Include
   anti-leak tests and the differential tests against the predecessor. Give each one a tolerance, either bit-identical
   or approximate.
4. **An explicit list of what the slice leaves out.**
5. **Parameter values.** Give each value, or mark it as a placeholder with the method and milestone that will
   calibrate it.
6. **Compute budgets.** State which runs need the user's approval, as the predecessor's confirm flags did.
7. **A decision log.** Answer each C and R item of this handoff as accepted, rejected or changed, with the reason.
8. **Repository basics.** Name the Python version, the dependencies and the test framework. If the specification
   leaves these to me, I'll follow the predecessor. That means Python 3.10 or later, numpy and pytest, with torch as an
   optional extra.

## 9. Where to push back

The reviewer should check these claims hardest:

- **V1.** The contents of the Riot timeline in C1 come from my memory, and I didn't check them this session. If the
  timeline does carry wave or camp state, C1 weakens a great deal.
- **V2.** The 15-second turn in R4 is my inference from the wave cadence. The predecessor's documents state no
  mapping to real time.
- **V3.** R3 depends on scripted continuations producing informative rankings, and F16 argues against that. Judge
  whether a slice-1 evaluator without RL is worth building or would mislead.
- **V4.** C5's claim that training on wins alone is infeasible has no measurement behind it. The throughput spike,
  plus an estimate of the learning curve, could test it.
- **V5.** The choice of slice 1 (D2). Slice 0 is the conservative alternative.
- **V6.** R7 relaxes a regime that the predecessor treated as central to its rigour. Weigh what the project loses
  without per-rule bit-identity.
- **V7.** The predecessor's numbers are Reported, taken from its summaries. The throughput figure is for `m4()`, not
  the research preset.
- **V8.** This corrects my chat review, which said the evaluator "already worked with scripted policies". More
  precisely, the instruments accept any policies. Most published strategic evaluations used learned continuations,
  and the predecessor used scripted-against-scripted screens for calibration.

## 10. Next steps

- **User.** Decide D1 to D6.
- **Planning assistant.** Revise the roadmap to v0.2 and draft `docs/design/M7_architecture.md`. Answer the C, R and
  Q items, and meet the needs in §8.
- **Implementing assistant (me).** If the user approves D5, I'll run three spikes during M7. Handoff 002 will report
  them, so the planning assistant can use the results in the specification:
  - Compare the Match-v5 fields with the scenario variables, from the documentation only (D6).
  - Benchmark one Python turn of a 10-champion graph world.
  - Port the wave kernel on its own, and test it differentially against the old `step_turn`.

After the user approves the M7 specification, I'll implement slice 1.
