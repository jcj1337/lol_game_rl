# Strategic League Simulator master roadmap

**Status.** Draft v0.3.4, planning document. M7 is closed and M8 has started. §10 summarizes the changes from earlier versions.

**Predecessor.** [Laning as a Two-Player Game](https://github.com/jcj1337/lol_laning_gt_rl)

**Scope.** Independent successor research project. This document is not a commitment to particular formulas, algorithms, or timelines.

## 1. Vision

Build a strategically faithful, mechanically abstract simulation of League of Legends in which teams of agents learn macro decisions through self-play. The simulator abstracts mechanical execution but keeps the strategic consequences that make macro decisions matter.

The ultimate application is a **post-game decision evaluator**. It reconstructs what a player could have known, compares plausible alternative actions, and highlights good decisions and missed opportunities.

Examples of questions the evaluator should eventually investigate:

- Should the player freeze, slow push, or crash this wave?
- Was this a good recall window?
- Given the enemy jungler's last known location, was pushing safe?
- Should the jungler gank this lane, keep clearing, counterjungle, or move toward another lane?
- Should the player stay in a side lane, group, or rotate to an objective?
- Could a sufficiently strong sidelaner plausibly hold or win an uneven fight, making the split push viable?
- Should the team contest an objective or trade it for pressure elsewhere?

The aim is to model the rules and consequences from which strategy can emerge. It is not to encode coaching rules such as "always slow push when the enemy jungler is bot."

## 2. Scope and boundaries

### In scope for the first research simulator

M8 builds minimal versions of most of these, and later milestones develop them.

- The full map, with three lanes and their wave economies, both jungles and their camps, and travel time between regions.
- Ten champions, including two independent junglers and a two-champion bot lane.
- Gold, XP, levels, recalls, deaths and respawns, item purchases, and broad champion capabilities.
- Towers, neutral objectives, strategic map pressure, and a genuine team win condition.
- Fog of war, vision, last-seen information, observation history, and uncertainty about hidden opponents.
- High-level agent actions. Examples are managing a wave, farming, recalling, warding, rotating, and ganking. Others are pressuring a structure, contesting or trading an objective, and engaging or avoiding a fight at a strategic level.
- Replaceable abstract outcome models for combat and other execution-heavy events.
- Comparison of alternative decisions under scripted or learned continuation policies.
- Team-aligned learning toward winning.

### Explicitly deferred

- Individual skillshots, precise targeting and combos, animation timing, pixel-accurate movement, and teamfight execution.
- Champion-by-champion reproduction of abilities, exact builds and passives, and exact matchup or positioning models.
- Real-time coaching, automated recording, parsing, or gameplay ingestion, and a conversational assistant. The initial evaluation input is a manually specified scenario.

These are not forbidden future capabilities. The architecture should leave room for finer-grained state, actions, and outcome models without implementing them in the first simulator.

### Important distinction

An abstract model may estimate what a champion or team could accomplish under stated execution assumptions. That estimate is not a prediction of exactly what would happen in a real fight. The evaluator should expose uncertainty, not label every decision categorically.

## 3. Architectural principles

1. **Outcome-driven design.** Start from the decisions the evaluator must assess, and use them to prioritize mechanics. For each target decision, identify the information needed to evaluate it and where that information could plausibly come from.
2. **Stable boundaries, replaceable approximations.** Keep waves, jungle, movement, economy, combat and outcome models, objectives, observations, policies, and evaluation logically separate. Prefer a small set of clear subsystem interfaces. Do not build a general plugin framework without evidence of need.
3. **World state is not player observation.** Every policy, scripted or learned, receives only the information its player could have, plus relevant observation history. Hidden state must not leak through action masks, timers, or events. §6 applies this rule to comparisons.
4. **A shared clock with appropriate granularity.** Different processes may update at different frequencies, but travel, waves, camps, recalls, respawns, and objectives must stay temporally consistent. Simulation time and policy decision frequency are related but separate choices. M7 defines their relationship, and this roadmap fixes neither value.
5. **Actions with explicit timing.** Start with macro choices. Many of them take time, such as traveling, clearing a camp, or recalling, so M7 defines their timing semantics. Leave room to refine a high-level intent into detailed actions later, without implementing a full action hierarchy up front.
6. **Reproducible counterfactuals.** Support seeded simulation, controlled randomness for paired comparisons, state snapshots, controlled alternative actions, and multiple continuation rollouts. A snapshot holds everything needed to restore and replay a decision point, and M7 defines its contents. Distinguish model uncertainty from stochastic outcomes.
7. **Team winning is the ultimate objective.** Gold and objectives are means, not the final score. Training rewards (M12) and evaluation outputs (§6) are separate questions. Reward shaping and credit assignment remain open for experiment.
8. **Testability before scale.** Build component tests, scenario sweeps, and scripted baselines before expensive self-play. Keep the simplest implementation that passes the relevant validation.
9. **Learn from the earlier research without inheriting its architecture.** Keep the laning repository independent and reproducible. Treat it as a source of selected mechanics, formulas, utilities, research findings, and test patterns. Port parts only after the new interfaces are designed. Use differential tests where this project intentionally preserves a behavior. Do not require exact agreement where the new model deliberately changes an assumption.
10. **Versioned rules and pinned reference replays.** Preserve seeded determinism and replayability. Version the rulesets, and pin reference replays at milestone boundaries. Historical mechanics do not need to stay behind permanent configuration flags.
11. **Abstract execution, consequential outcomes.** Combat can stay abstract, but its consequences must support macro decisions. Once junglers are agents, ganks come from their movement and choices, and no independent gank-hazard system serves as the primary model. Vision, including basic warding, provides information that agents can act on. It does not directly reduce gank risk.

## 4. Scenario-led acceptance tests

The following are design targets, not hand-coded policy rules or claims of correctness in real League.

| Scenario | Model needs to distinguish | Key dependencies |
| --- | --- | --- |
| Freeze, slow push, or shove | Timing of crashes, missed farm, vulnerability, and tempo | Waves, lane threat, economy, travel |
| Recall now or stay | Missed farm and wave losses from recalling, and when the player arrives back in lane or at an objective | Economy, waves, movement, timers |
| Jungler last seen botside | Updating possible enemy locations and risk over time | Jungle, fog, memory, pathing |
| Gank, clear, counterjungle, or move to another lane | Opportunity costs of competing destinations, travel time, lane states, and the information each choice reveals | Jungle, map travel, waves, fog, abstract combat |
| Side lane, group, or objective | Pressure gained against arrival time and team contest strength, and the waves, camps, or structures left exposed elsewhere | Movement, waves, towers, objectives, abstract combat |
| Strong bruiser against two weaker defenders | A 1v2 is not automatically lost. Capabilities and context matter. | Capabilities, levels, items, abstract combat |
| Contest dragon or trade for a tower | Alternative paths to winning, not only immediate gold | Objectives, structures, team outcome |
| Bot-lane resource allocation | Two champions sharing one lane's gold and XP, without each receiving full solo-lane income | Waves, economy, allocation rules |
| Unusual and lopsided states | Decision quality in states that ordinary self-play rarely visits, including large advantages and deficits | Building such states, comparison harness, continuation policies |

For each scenario, define:

- (a) the observable inputs and the information available at decision time
- (b) the available actions, separating individual alternatives from coordinated team alternatives
- (c) the expected qualitative relationships
- (d) counterexamples
- (e) sensitivity tests

Tests should establish grounded mechanics and opportunity costs. They should not force a named strategy to win. Do not invent expected win-rate percentages to make a test pass.

## 5. Milestone overview

Milestones are planning boundaries, not hard walls. Component tests and integration tests will overlap. Before starting the next major subsystem, document what the previous one established and what remains uncertain.

**Dependencies.** M8 needs an approved M7. M9, M10, and M11 build on M8 and may overlap, and M10's exploit checks rerun when M9 changes combat. The early learning pilot needs a usable M8. The main M12 campaign needs the complete games of M10 and uses whichever M9 and M11 versions exist when it starts. M13 builds on the M8 harness and uses M12's learned policies where they exist.

### M7: Architecture and research specification

**Goal.** Design the full-game model around the post-game macro evaluation use case.

**Deliverables.**

- State, observation, action, and timing contracts, including how actions last, persist, get interrupted, and get replanned.
- The relationship between simulation time and policy decision frequency. M7's design may set the values, and this roadmap does not.
- Subsystem boundaries and the small set of interfaces between them.
- Decisions on which mechanics are faithful and which are approximate. These include combat considerations such as fight duration, remaining resources, disengagement, and reinforcement timing, which M7 settles or defers to M9.
- A scenario requirements matrix that lists, for each target decision, the information needed to evaluate it and plausible sources for that information.
- The format of manually specified scenarios, the initial evaluation input. Automated ingestion stays deferred.
- The distinction between changing one player's action and changing a coordinated team plan.
- Snapshot requirements covering world state, relevant observation history or memory, actions in progress, and reproducibility.
- How a comparison obtains the plausible hidden states it uses, without giving any policy hidden information.
- Whether basic warding belongs in M8 or M11.
- A checkpoint plan that divides M8 into component and integration checkpoints. It includes what M8 uses for champion capability and for spending gold until M9 provides them.
- The placement and scope of an early learning and throughput pilot (see M12).
- An initial validation and reproducibility plan that assigns each §4 scenario and each §7 check to the milestone that first tests it.
- An audit plan for code and tests from the laning project.
- A risk and open-question register.

**Done when.** The design explains how an observable game state becomes a legal macro action, a simulated consequence, and a counterfactual comparison. Key uncertainties are explicit. M8's checkpoints and the pilot's placement are defined. The first checkpoints can be planned without committing to all future mechanics.

**Not in scope.** Large-scale coding or training.

**Closed on 2026-11-11.** The owner judged M7 sufficient to begin implementation. Its result is [`docs/design/M7_architecture.md`](design/M7_architecture.md), corrected in [handoff 004](../handoff/004_m7_corrections.md). M7 fixed the contracts for space, time, intents, roles, information, randomness, snapshots, and comparisons, and it divided M8 into eight checkpoints, C1 to C8. One finding stays open and passes to M8: M7's wave tests did not show a freeze or a slow push. §8, risk 11, tracks it.

### M8: Full-map foundation

**Goal.** Build a time-consistent full-map world in which ten champions make integrated macro decisions with real opportunity costs.

**Deliverables.**

- Map regions, routes, and travel times.
- Three lane instances, or an equivalent shared wave system, without special-case copies of lane logic.
- The standard camps of both jungles, with configurable spawn, respawn, and clear profiles.
- Two independent junglers whose pathing chooses among competing destinations across the map.
- Ten champions, with both bot-lane champions taking part in their lane.
- Shared team and player state, with gold, XP, levels, recalls, and the economy.
- Basic gold and XP allocation in the bot lane.
- Basic lane towers and their consequences for waves and champions.
- Minimal abstract combat.
- Death, respawn, and return to the map.
- Basic fog of war and last-seen information.
- State restoration and a basic harness that compares alternative actions under scripted or learned continuation policies, across plausible hidden states (§6).
- Scripted baseline agents, and saved scenarios that replay.

These are minimal versions, not the final implementations of later subsystems. Components may be built and tested separately, following M7's checkpoint plan.

**Done when.** The components work together in one integrated environment, not only in isolation. Scripted ten-champion games run on the full map. Junglers choose among competing destinations. Wave, jungle, recall, and respawn timings interact coherently. Fog limits what each agent observes, and anti-leakage tests pass. Bot-lane income does not duplicate full solo-lane income for both players. Towers constrain waves and champions. Saved states restore and replay exactly, and the harness compares alternatives reproducibly.

**Open.** Exact map representation, calibration data, and how best to port existing wave rules.

**Progress.** M8 runs as campaigns over M7's checkpoints. [`docs/design/M8_foundation.md`](design/M8_foundation.md) holds the phases, the acceptance criteria, and the technical detail of each campaign. The first campaign covers C1 (kernel base) and C2 (lanes and economy). The second campaign corrected C2 and built C3 (recall and purchases), C4 (jungle), and C5 (combat and death). The third campaign corrected five review findings and built C6 (vision, memory, and wards). The fourth campaign corrected what the third left open, among them a leak through pursuit, ran every wave experiment with the plan on each team, and built C7 (integrated games). The fifth fixed a pursuit that could not recover contact, removed three places where lanes acted only at the start of a tick, moved the research clock to a 0.25 s tick with a decision every 2 s, and built C8 (scenarios and the comparison harness). C1 and C3 to C6 pass M7's criteria. C7 meets them at the research clock apart from throughput: the gate gives 267 simulated seconds per wall second there, against 300, and a 0.5 s tick passes with 467. C8 is built, and the M8 document maps each of its criteria to a test. None of C8's four scenarios names a best option. One ranking is uncertain, and three are stable trade-offs. C2 is built and is not complete.

**Decisions that bind M8.** The owner settled these on 2026-11-11.

- The full map with ten champion slots is the architecture from the first checkpoint. A single-lane experiment is a tool for validation, never the product.
- Movement, interaction range, and visibility are three separate measures.
- Laners have fixed lanes and may roam for a limited time. The roam allowance of 90 s and 20 percent is an experimental restriction that stays configurable. It is not an approved permanent rule. A champion that has to return keeps sensible choices to defend itself and to retreat.
- Ordinary minion gold, support-generated income, and passive income are accounted for separately.
- Freezing, slow pushing, crashing, and bouncing stay required capabilities under appropriate conditions. They are not removed from the foundation's goals. No rule may be added solely to force them, and a test for one of them may be revised only with evidence and counterexamples, never by lowering a threshold until it passes.
- The corrected intent lifecycle and the information boundaries of M7 are preserved.
- Every result separates what is assumed, what is correct inside the simulator, and what is validated against the real game.

### M9: Archetypes, items, and combat

**Goal.** Develop, calibrate, and validate the basic combat introduced in M8, so that relative strength has strategic consequences without modeling mechanical execution.

**Deliverables.**

- Champion capability profiles at the level macro decisions need. Their representation is an M9 design choice.
- Level-driven and item-driven changes in capability, with itemization expanded where it materially affects macro decisions.
- A calibrated, context-aware engagement model behind the combat interface that M7 defines and M8 implements. It covers 1v1 fights, ganks, and uneven fights.
- The combat considerations that M7 deferred.
- Engage and disengage capability, and the model's uncertainty.
- Isolated scenario sweeps and documented sensitivities.

Detailed builds and champion-by-champion mechanics are not required. The predecessor used continuous investment instead of item purchases. That choice is not evidence that purchase thresholds are irrelevant, so M9 tests whether they affect decisions such as recall timing.

**Done when.** Broad trends behave sensibly across 1v1, 2v1, and uneven fights. Uneven outcomes follow from capabilities and context, so a 1v2 is not automatically lost. The conditions under which it is won come from stated assumptions. Assumptions and sensitivities are documented.

**Open.** Formulas, parameterization, calibration, execution-skill parameterization, and how detailed itemization needs to be.

### M10: Objectives and complete games

**Goal.** Turn the full-map world into a game with a genuine team-level outcome.

**Deliverables.**

- Simplified neutral objectives.
- Structure progression beyond the basic lane towers built in M8.
- Win-condition rules and enough game progression for matches to finish.
- An analysis of deadlocks and of incentives to rush or stall.
- A clear separation between the game's own termination and experimental time limits.
- Scripted team policies and baseline diagnostics.

**Done when.** Scripted teams complete seeded matches without deadlocks or trivial dominant exploits. Experimental time limits do not create incentives to rush or stall that the game itself lacks. Macro choices create consequential differences in map state and eventual wins.

**Open.** Objective fidelity, match duration calibration, and how much structure detail useful decisions need.

### M11: Richer vision and tracking

**Goal.** Extend the basic fog from M8 so that decisions depend on richer information about what each player could know.

**Deliverables.**

- Richer ward interactions, beyond any basic warding that M7 assigns to M8.
- Inference and memory about hidden opponents and camps, which can also supply plausible hidden states for comparisons.
- Experiments that measure the value of information, comparing scenarios with and without it.
- Anti-leakage tests for the new interactions.

**Done when.** Agents still cannot observe hidden enemy locations directly. Observation histories support legitimate jungle-tracking inference. Experiments measure what specific information is worth in representative scenarios.

**Open.** The belief model or filtering method, if one is needed. This roadmap does not prescribe one.

**Note.** M7 designs the separation of state and observation, and M8 implements it from the start. M11 improves its fidelity. It does not retrofit it.

### M12: Multi-agent learning and strategy experiments

**Goal.** Learn cooperative-competitive macro policies that improve a team's chance of winning.

**Early pilot.** A smaller learning and throughput pilot runs once the M8 foundation is usable, before this milestone's main campaign. M7 decides its exact placement and scope. It uses the same observation and action interface as M8's scripted agents. The pilot informs feasibility, training interfaces, and compute budgets. If it runs before complete games exist (M10), it cannot learn from wins, so M7 also decides what it learns from.

**Deliverables.**

- A role-aware multi-agent policy and training interface.
- Scripted and historical opponent baselines.
- A team-level terminal win reward, with experiments on reward shaping and credit assignment.
- Repeatable multi-seed evaluation.
- Dedicated attacker evaluations as lower bounds on exploitability.
- Strategy probes and ablations, including states that ordinary self-play rarely visits.

**Done when.** Learned agents outperform relevant baselines on held-out seeds and scenarios. At least some macro behaviors are supported by controlled counterfactual or ablation evidence, not just anecdotes from one replay.

**Open.** How hard learning from terminal outcomes alone is, and which shaping helps, are empirical questions. Also open are policy sharing versus role-specific networks, the PPO variant, recurrence, centralized training, curriculum, and training budget.

### M13: Evaluator development and transfer validation

**Goal.** Turn the basic comparison harness from M8 into an evidence-based macro decision evaluator.

**Deliverables.**

- Evaluation quality and candidate coverage, meaning which individual and coordinated team alternatives get compared.
- Robustness checks across continuation policies, plausible hidden states, combat parameters, and evaluation horizons.
- Readable explanations and reason codes.
- Uncertainty reporting, including withholding a recommendation when the evidence is insufficient.
- External validation, with held-out cases where practical.
- An offline evaluation suite.

**Done when.** The evaluator compares actions for representative scenario states, identifies unstable or uncertain recommendations, and shows how conclusions depend on assumptions. Strong performance inside the simulator does not establish real-game correctness. Any claim about real games requires separate external validation.

**Deferred.** Automated recording, parsing, and ingestion, the user interface, and the chatbot. These belong to a later product roadmap once decision quality has been demonstrated.

## 6. Comparing decisions

From M8 on, a harness compares alternative actions from a restored state. It accepts scripted or learned continuation policies, so basic evaluation does not depend on reinforcement learning.

Early comparisons are instruments for inspecting the simulator's incentives. They are not authoritative coaching. Every result depends on these factors, and reports them:

- the continuation policies, including how teammates respond
- the plausible hidden states consistent with what was known at decision time
- the combat and execution assumptions
- the rollout horizon and any approximation of terminal value

An individual alternative changes one player's action. A coordinated team alternative changes a team plan. Each comparison states which kind it makes. Teammates do not automatically cooperate with a changed individual action. They respond according to their own policies.

Every simulated policy respects its information boundary. Sampling plausible hidden states must not give a continuation policy access to hidden information. Comparisons may use different scripted styles, but do not label a style "rank-typical" without validation.

Before complete games exist, report the relevant consequences separately. Examples are gold, XP, health, deaths and time absent, arrival times, and structure damage. A comparison may conclude that the alternatives trade off against each other, or that there is no clear ranking. Do not invent a scalar score, and do not present these outputs as calibrated win probabilities.

## 7. Validation strategy

Use several complementary checks instead of a single "looks like League" test:

- **Rules tests.** Determinism under seeded runs, and invariants for time, resources, observations, and legal actions.
- **Snapshot, replay, and anti-leakage tests.** These start in M8. Restored states reproduce exactly, and no policy can read hidden information.
- **Component sweeps.** Jungle routes and clear progression, wave timings, stat and item advantages, and outcome-model sensitivity.
- **Integrated scenarios.** The §4 scenarios, with their counterexamples and sensitivity tests.
- **Baseline comparison.** Scripted policies, randomized policies, and deliberately exploitable strategies.
- **Exploitability.** Dedicated attackers give lower bounds on how exploitable a policy is.
- **Ranking sensitivity.** How rankings change across continuation policies, hidden-state assumptions, combat parameters, and evaluation horizons.
- **Learning diagnostics.** Multi-seed held-out outcomes, opponents not seen in training, and ablations of memory, vision, and mechanics.
- **External calibration and validation.** A small track that compares broad simulator relationships with trustworthy real-game knowledge or permitted data, with held-out cases where practical. It distinguishes validated mechanics from assumed ones.
- **Evaluator safety.** Report uncertainty, and withhold strong recommendations when observations or model assumptions are insufficient.

Exploitability and ranking stability add to the other checks. Neither establishes correctness alone.

The purpose of validation is not to script desired strategic conclusions. It is to test whether sensible conclusions follow robustly from grounded mechanics.

## 8. Principal risks and open questions

1. **Sim-to-real gap.** A model can discover optimal play in a flawed simulation. How will we test transfer, rather than simply reward internal consistency?
2. **Combat abstraction.** Which combat capabilities do macro decisions need, and which execution assumptions should be explicit?
3. **Reward and credit assignment.** Can terminal win or loss alone support learning across long ten-champion games, and when is shaping warranted? The early pilot tests throughput and training interfaces. Evidence about learning from wins needs the complete games of M10.
4. **Partial information.** What information does each target decision need, and where could it come from? Which parts could a future recording reconstruct reliably, and which must remain uncertain?
5. **Continuation dependence.** Comparison results depend on continuation policies and teammate responses. Self-play may rarely visit unusual or lopsided states, which are where the evaluator most needs competent continuations.
6. **Integration risk.** The first integrated environment combines many subsystems at once. M7's checkpoint plan has to keep each step testable.
7. **Calibration.** How should real-game timings and champion parameters be estimated and versioned without relying on a comprehensive replay dataset?
8. **Compute and scope.** What simulator throughput, training budget, and quality threshold are realistically achievable? The pilot informs the budget.
9. **Policy and product constraints.** Review Riot's current developer and third-party tool policies before releasing a public simulator-derived coaching application or using game assets.
10. **Reuse.** Which laning mechanics and tests carry over, and which embed two-player, one-lane, or perfect-information assumptions?
11. **Wave fidelity.** The simulator's wave behaviour is not settled. When agents act through the action table, reinforcement accumulation and a sustained hold each appear in a minority of settings, with the plan on either team. A lane near balance amplifies small differences. M8's fifth campaign found three places where a minion took a target or marched only at the start of a tick and moved them inside the tick, so an untouched first-wave fight now plays out the same at every tick from 0.125 s to 1.0 s. Single results still flip with the tick length, the decision interval, and two unsourced details of minion attack timing, because each every-seed verdict is a strict comparison on small counts. No affordable tick gives every-seed wave verdicts that hold at the others. Per case, a tick of 0.25 s stays within 0.6 s of 0.125 s in crash times on both teams. M8 now runs at a 0.25 s tick with a decision every 2 s, chosen on fidelity, and reports its throughput against the gate apart. In integrated ten-champion games every scripted outcome at 0.25 s and at 0.5 s stays within seed noise of 0.125 s. An untouched side lane no longer drifts early since M8 traces its corners with the game's own waypoints. Its later drift goes toward a side that depends on the tick, the same in nearly every seed, and at 0.5 s on the seed. Four regression pins of the fourth campaign no longer hold at the new clock. They stay as expected failures, and no threshold was lowered. Whether a real lane on the reference patch behaves the same is unknown, and nothing in the lane is validated against the game. Conclusions about recall timing, denial, and gank opportunities stay provisional until then. [`docs/design/M8_foundation.md`](design/M8_foundation.md) states the finding and the real-game measurements that bear on it.

## 9. Immediate next actions

1. Review the handoff of M8's fifth campaign and the M8 document, and record any disagreements.
2. Commission the independent audit of M8, and after it the lightweight visual inspection demo, as the owner intends.
3. Decide whether someone takes the real-game wave measurements that the M8 document names.
4. Decide how C2's open wave questions are carried at the research clock: as shares of settings or paired medians with seed counts, or into a further correction.
5. Answer the open questions of handoff 008 on whether a slow is observable and whether the mana placeholders hold until M9.
6. Plan the training pilot. M7 placed it after C7 and beside C8, and the owner put the audit and the demo first.

This roadmap is intentionally revisable. Write a milestone's detailed plan when that milestone begins, not months in advance.

## 10. Revision summary

### v0.3.4 (2026-11-13)

This version records the state after M8's fifth campaign. It changes no milestone's scope and no decision.

- The M8 progress note adds C8, the pursuit and lane timing fixes, and the research clock, and says that C2 is still not complete.
- Risk 11 states the wave finding after the in-tick lane fixes, at the research clock.
- §9 lists the actions that follow M8's fifth campaign.

### v0.3.3 (2026-11-13)

This version records the state after M8's fourth campaign. It changes no milestone's scope and no decision.

- The M8 progress note adds C7 and says that C2 is still not complete.
- Risk 11 states the wave finding on both teams and the tick sensitivity that the wave and integrated sweeps measured.
- §9 lists the actions that follow M8's fourth campaign.

### v0.3.2 (2026-11-12)

This version records the state after M8's third campaign. It changes no milestone's scope and no decision.

- The M8 progress note adds C6 and says that C2 is still not complete.
- Risk 11 states the wave finding after the corrections.
- §9 lists the actions that follow M8's third campaign.

### v0.3.1 (2026-11-12)

This version records the state after M8's second campaign. It changes no milestone's scope and no decision.

- The M8 progress note names the checkpoints that are built and says that C2 is not complete.
- Risk 11 states the current wave finding.
- §9 lists the actions that follow M8's second campaign.

### v0.3 (2026-11-11)

This version records the closeout of M7 and the decisions that the owner settled when M8 started. It changes no milestone's scope.

- M7 is marked closed, with a pointer to its document and its one open finding.
- M8 gains a progress note, a pointer to its own document, and the seven decisions that bind it.
- §8 gains risk 11 on wave fidelity.
- §9 lists the actions that follow M8's first campaign.

### v0.2 (2026-11-11)

Substantive changes:

- M8 is a full-map foundation with all ten champions. It adds basic fog, minimal combat, respawn, bot-lane allocation, lane towers, and a comparison harness, and its gate requires them to work together.
- M7 adds action timing, decision frequency, information sources, manual scenarios, and team alternatives. It also covers snapshot contents, M8's checkpoints, and the pilot's placement.
- Basic evaluation no longer depends on learning, and it reports consequences separately rather than as one score (§6).
- M9 calibrates M8's combat and tests purchase thresholds. M10 handles termination, deadlocks, and rushing or stalling. M11 builds on M8's fog. M12 gains an early pilot and attacker evaluations. M13 focuses on evaluation quality.
- Principles 10 and 11 are new. They cover versioned rules with pinned replays, ganks that come from jungler agents, and wards that provide information. Principles 3, 5, 6, and 9 gain detail on information boundaries, action timing, snapshots, and reuse.
- The scenario table and the validation strategy gain the cases and checks listed in §4 and §7.
- Respawns move from M10 to M8. M9 loses its note about overlapping M8, its "role-independent" profiles, and v0.1's camp count. The v0.1 action to audit the laning repository is complete, and the M7 audit plan continues it.
- The tool is called an evaluator throughout.

Choices deliberately left open:

- Tick length and decision interval
- Combat formulas and execution-skill parameterization
- Champion archetypes and detailed item systems
- Policy architecture, recurrence, centralized critics, and the PPO variant
- Reward shaping
- Automated recording, parsing, and ingestion
- The pilot's exact placement, and whether basic warding belongs in M8 or M11, which M7 decides

### v0.1

Initial draft.
