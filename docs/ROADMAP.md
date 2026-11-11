# Strategic League Simulator — Master Roadmap

**Status:** Draft v0.1 · Planning document  
**Predecessor:** [Laning as a Two-Player Game](https://github.com/jcj1337/lol_laning_gt_rl)  
**Scope:** Independent successor research project; not a commitment to particular formulas, algorithms, or timelines.

## 1. Vision

Build a strategically faithful, mechanically abstract simulation of League of Legends in which teams of agents learn macro decisions through self-play. The ultimate application is a **post-game decision reviewer** that reconstructs what a player could have known, compares plausible alternative actions, and highlights good decisions and missed opportunities.

Examples of questions the reviewer should eventually investigate:

- Should the player freeze, slow push, or crash this wave?
- Was this a good recall window?
- Given the enemy jungler's last known location, was pushing safe?
- Should the player stay in a side lane, group, or rotate to an objective?
- Could a sufficiently strong sidelaner plausibly hold or win an uneven fight, making the split push viable?
- Should the team contest an objective or exchange it for pressure elsewhere?

The aim is **to model the rules and consequences from which strategy can emerge**, not to encode coaching rules such as “always slow push when the enemy jungler is bot.”

## 2. Scope and boundaries

### In scope for the first research simulator

- Three lanes and their wave economies, jungles with independent pathing and camps, map movement and travel time.
- Gold, XP, levels, recalls, item purchases, and broad champion archetypes.
- Towers, objectives, strategic map pressure, and a genuine team win condition.
- Vision, last-seen information, observation history, and uncertainty about hidden opponents.
- High-level agent actions: manipulate wave, farm, recall, ward, rotate, gank, pressure structure, contest or trade objectives, engage/avoid a fight at a strategic level.
- Replaceable **abstract outcome models** for combat, ganks, and other execution-heavy events.
- Team-aligned learning toward winning, followed by counterfactual decision evaluation.

### Explicitly deferred

- Individual skillshots, precise targeting and combos, animation timing, pixel-accurate movement, and teamfight execution.
- Champion-by-champion reproduction of abilities, exact builds and passives, or exact matchup/positioning models.
- Real-time coaching, automated video ingestion, desktop recording, and a conversational assistant.

These are not forbidden future capabilities. The architecture should leave room for finer-grained state, actions, and outcome models **without implementing them in v1**.

### Important distinction

An abstract model may estimate what a champion or team *could accomplish under stated execution assumptions*. This is not the same as predicting exactly what would happen in a real fight. The eventual reviewer should expose uncertainty, not label every decision categorically.

## 3. Architectural principles

1. **Outcome-driven design.** Start from decisions the eventual reviewer must evaluate; use these scenarios to prioritize mechanics.
2. **Stable boundaries, replaceable approximations.** Keep waves, jungle, movement, economy, combat/outcome models, objectives, observations, policies, and evaluation logically separate. Do not build an elaborate plugin framework without evidence of need.
3. **World state ≠ player observation.** Policies receive only player-available information and relevant observation history; hidden state must not leak via action masks, timers, or events.
4. **A shared clock with appropriate granularity.** Different processes may update at different frequencies, but travel, waves, camps, recalls, and objectives must remain temporally consistent. Exact tick size is undecided.
5. **Hierarchical/extensible actions.** Start with macro choices; leave room to refine a high-level intent into more detailed actions later.
6. **Reproducible counterfactuals.** Support seeded simulation, state snapshots, controlled alternative actions, and multiple continuation rollouts. Distinguish model uncertainty from stochastic outcomes.
7. **Team winning is the ultimate objective.** Gold and objectives are means, not the final score. Intermediate shaping is a research question, not a fixed assumption.
8. **Testability before scale.** Build component tests, scenario sweeps, and scripted baselines before expensive self-play; keep the simplest implementation that passes the relevant validation.
9. **Preserve the earlier research.** Keep the laning repository intact. Audit and selectively port validated mechanics/tests only after new interfaces are designed.

## 4. Scenario-led acceptance tests

The following are **design targets**, not hand-coded policy rules or claims of correctness in real League.

| Scenario | Model needs to distinguish | Key dependencies |
| --- | --- | --- |
| Freeze vs. slow push vs. shove | Timing of crashes, missed farm, vulnerability, tempo | Waves, lane threat, economy, travel |
| Recall now vs. stay | Opportunity cost of recalling and future wave losses | Economy, waves, movement |
| Jungler last seen botside | Updating possible enemy locations and risk over time | Jungle, visibility, memory, pathing |
| Side lane vs. objective | Pressure gained versus arrival time and team contest strength | Movement, towers, objectives, abstract combat |
| Strong bruiser vs. two weaker defenders | A 1v2 is not automatically losing; capabilities and context matter | Archetypes, levels, items, abstract combat |
| Contest dragon vs. trade for tower | Alternative paths to winning, not only immediate gold | Objectives, structures, team outcome |

For each scenario, define (a) observable inputs, (b) available actions, (c) expected qualitative relationships, (d) counterexamples, and (e) sensitivity tests. No arbitrary expected win-rate percentages should be invented to make a test pass.

## 5. Milestone overview

Milestones are **planning boundaries**, not hard walls. Component tests and integration tests will overlap. Do not start the next major subsystem without documenting what the previous one established and what remains uncertain.

### M7 — Architecture and research specification

**Goal:** Design the full-game model around the post-game macro-evaluation use case.

**Deliverables:** State/observation/action and timing contracts; subsystem boundaries; decisions about faithful vs. approximate mechanics; scenario requirements matrix; initial validation and reproducibility plan; audit plan for code/tests from the laning project; risk and open-question register.

**Done when:** The design explains how an observable game state becomes a legal macro action, a simulated consequence, and a counterfactual evaluation; key uncertainties are explicit; the first implementation slice can be planned without committing to all future mechanics.

**Not in scope:** Large-scale coding or training.

### M8 — Map, lanes, and jungle foundation

**Goal:** Create a time-consistent world connecting lanes, map travel, jungle farming, recalls, and economy.

**Deliverables:** Three lane instances or equivalent shared wave system; regions/routes/travel times; six standard camps per jungle with configurable spawn, respawn, and clear profiles; independent jungler schedules; shared team/player state; scripted baseline actors.

**Done when:** Scripted actors can clear, move, recall, and affect multiple lanes; wave and jungle timing interact coherently; test scenarios can be saved/replayed; extending one lane to three does not require special-case copies of lane logic.

**Open:** Exact map representation, clock frequency, calibration data, and how best to port existing wave rules.

### M9 — Archetypes, items, and abstract combat capability

**Goal:** Represent strategic consequences of relative strength without modeling mechanical execution.

**Deliverables:** Role-independent archetype profiles; level/item-driven stat changes; replaceable context-aware fight/gank outcome model; basic engage/disengage capability and uncertainty; isolated scenario sweep tests.

**Done when:** Broad trends behave sensibly across 1v1, 2v1, and uneven fights; the model can sometimes favor a fed solo champion against two weaker enemies and can distinguish other archetype matchups; output assumptions and sensitivities are documented.

**Open:** Exact formula, parameterization, calibration, and execution assumptions. This milestone may overlap M8 to support meaningful gank tests.

### M10 — Objectives and complete games

**Goal:** Convert the map simulator into a game with a genuine team-level outcome.

**Deliverables:** Towers and structure progression; simplified neutral objectives; win-condition rules, respawns, and enough game progression to finish; scripted team policies and baseline diagnostics.

**Done when:** Scripted teams can complete seeded matches without deadlocks or trivial dominant exploits; macro choices create consequential differences in map state and eventual wins.

**Open:** Objective fidelity, match duration calibration, and how much structure detail is necessary for useful decisions.

### M11 — Vision and partial observability

**Goal:** Make decisions depend on information each player could actually know.

**Deliverables:** Visibility and last-seen rules, observation histories, hidden camp/jungler information, anti-leakage tests, and scenario comparisons with/without tracking information.

**Done when:** Agents cannot directly observe hidden enemy locations; observation histories allow legitimate jungle-tracking inference; tests cover accidental information leaks.

**Important:** State/observation separation is designed in M7 and implemented from the outset. M11 improves its fidelity; it does not retrofit it.

### M12 — Multi-agent learning and strategy experiments

**Goal:** Learn cooperative-competitive macro policies that improve a team's chance of winning.

**Deliverables:** Role-aware multi-agent policy/training interface, scripted and historical opponent baselines, team-level terminal win reward, experiments on reward shaping and credit assignment, repeatable multi-seed evaluation, strategy probes and ablations.

**Done when:** Learned agents outperform relevant baselines on held-out seeds/scenarios, and at least some macro behaviors are supported by controlled counterfactual or ablation evidence—not just anecdotes from one replay.

**Open:** Policy sharing versus role-specific networks, PPO variant, recurrence, centralized training, curriculum, training budget, and rewards beyond the terminal outcome.

### M13 — Decision evaluator and transfer validation

**Goal:** Turn a trained policy/simulator into an evidence-based macro decision comparison system.

**Deliverables:** Snapshot/restoration API, candidate-action comparison, counterfactual rollouts from plausible hidden states, uncertainty and sensitivity reporting, readable reason codes, and an offline evaluation suite.

**Done when:** The system can compare actions for representative scenario states, identify unstable/uncertain recommendations, and show how conclusions depend on assumptions. Any claims about real-game correctness require separate external validation.

**Deferred:** Automated video parsing, recorder, UI, and chatbot; these belong to a subsequent product roadmap once decision quality has been demonstrated.

## 6. Validation strategy

Use multiple complementary checks instead of a single “looks like League” test:

- **Rules tests:** Determinism under seeded runs; invariants for time, resources, observations, and legal actions.
- **Component sweeps:** Jungle routes and clear progression; wave timings; stat/item advantages; outcome model sensitivity.
- **Integrated scenarios:** Gank timing versus wave crash; recall versus objective arrival; split pressure versus grouping.
- **Baseline comparison:** Scripted policies, randomized policies, and deliberately exploitable strategies.
- **Learning diagnostics:** Multi-seed held-out outcomes, opponents not seen in training, and ablations of memory/vision/mechanics.
- **Transfer checks:** When possible, compare broad simulator relationships to trustworthy real-game knowledge or permitted data; explicitly distinguish validated from assumed mechanics.
- **Reviewer safety:** Report uncertainty and withhold strong recommendations when observations or model assumptions are insufficient.

The purpose of validation is **not** to script desired strategic conclusions. It is to test whether sensible conclusions follow robustly from grounded mechanics.

## 7. Principal risks and open questions

1. **Sim-to-real gap:** A model can discover optimal play in a flawed simulation. How will we test transfer rather than simply reward internal consistency?
2. **Combat abstraction:** Which combat capabilities are necessary for macro decisions, and which execution assumptions should be explicit?
3. **Reward and credit assignment:** Can terminal win/loss alone support learning across long 5v5 games? When is shaping warranted?
4. **Partial information:** Which information can be reconstructed reliably from a future recording, and which must remain uncertain?
5. **Calibration:** How should real-game timings and champion archetype parameters be estimated and versioned without relying on a comprehensive replay dataset?
6. **Compute and scope:** What simulator throughput, training budget, and quality threshold are realistically achievable?
7. **Policy/product constraints:** Review Riot's current developer and third-party tool policies before releasing a public simulator-derived coaching application or using game assets.
8. **Reuse:** Which laning mechanics/tests are portable, and which embed two-player or gold-lead assumptions?

## 8. Immediate next actions

1. Review this roadmap for omissions, overcommitment, and milestone dependencies.
2. Ask a code-aware reviewer to audit the old laning repository **against the roadmap**, without editing the original code or prematurely copying it.
3. Revise this document to v0.2, recording substantive changes and unresolved disagreements.
4. Create `docs/design/M7_architecture.md` and define the first narrow, end-to-end scenario and its interfaces/tests.
5. Begin implementation only after M7 has clear acceptance criteria.

This roadmap is intentionally revisable. A milestone's detailed plan should be written when that milestone begins—not months in advance.
