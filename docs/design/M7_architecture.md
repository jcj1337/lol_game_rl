# M7 architecture and research specification

**Status.** Second version, revised after the planning review. [Handoff 004](../../handoff/004_m7_corrections.md) records what changed and why. Nothing here is approved until the owner and the planning assistant review it.

**Date.** 2026-11-11, revised the same day.

**Answers.** [ROADMAP v0.2](../ROADMAP.md), milestone M7, plus the owner decisions of 2026-11-11 on map, timing, waves, recalls, combat, roles, information, camps, scope, and compute, and the owner's clarifications after the review.

**Reference patch.** League of Legends 26.22, Summoner's Rift.

**Evidence labels.** Each claim in this document carries one of these labels.

- **Tested** means that a test or script in this repository shows it. The claim names the file. A results file carries the command, seeds, and code identity of its run (section 13).
- **Sourced** means that it comes from the reference patch research. The ruleset file tags each value `F2` (read on two pages), `F1` (read on one page), `D` (derived), or `M` (from memory).
- **Assumed** means that it is a design choice or a placeholder number. Nothing has checked it yet.
- **Reported** means that the evidence is not in the repository: a delegate's account, or a run that was not kept.
- **Unresolved** marks a known limit that this document does not remove.

## 1. Summary

M7 fixes the contracts that M8 builds on and tests the claims that were least certain. This second version corrects seven issues that the planning review found in the first.

**Contracts fixed.**

- Space is a route graph built from the game's own map file. Movement follows routes, ranges are straight lines, and sight is a straight line that terrain can block (section 5.1).
- Time is a fixed tick with a separate decision interval. M8 starts from a 0.5 s tick and a decision every 2 s. Both are starting values, not validated constants (section 5.2).
- An action sets an intent that persists until it completes or is replaced. Routine execution is automatic. Attacks compete for one capacity (section 7).
- A laner has a fixed lane and a bounded allowance for roams. When the allowance is spent, the laner can only choose to walk back (section 5.10).
- Fights have no fight object. They unfold over ticks from range, speed, lockdown, and towers (section 5.9).
- A policy sees only its observation, and masks are built from the observation alone (section 6).
- Randomness is keyed and stateless. A snapshot restores and replays exactly (section 8).
- Scenarios are written by hand over a generated base. A comparison runs on what the deciding team knows plus stated hypotheses about what is hidden. It reports each consequence separately (section 9).

**Tested in M7.** 135 tests pass, and one test of a known prototype defect is expected to fail. The map's lane lengths agree with a second derivation within 3 percent. Range and sight behave as intended at junctions, on nearby paths, and across walls. In a ten-champion prototype these hold: intents that end on completion, the decision-interval contract, the `FIGHT` rule for lost vision, the roam bound, fog with no leak into observations, exact snapshot replay, and a comparison that does not change with hidden truth. The prototype runs 591 simulated seconds per wall second on one process at the starting clock values.

**Not shown.** The owner decided that freezes and slow pushes emerge. Three rounds of wave tests do not show it. With the reference patch's numbers, a champion that can die, and no added rule, neither behaviour passes the test written for it. Section 5.6 gives the mechanism and the six real-game measurements that are missing.

**Not claimed.** This document does not claim that the simulator's waves are realistic. It does not claim that training is feasible end to end. No training loop ran, and the overnight budget is arithmetic on two separate benchmarks (section 10.3).

**Plan for M8.** Eight checkpoints with acceptance criteria, audited in this version for contradictions and forced conclusions. The learning pilot runs after the integrated-game checkpoint C7, in overnight runs of at most 10 hours on the inspected machine (section 10).

**What this document does not establish.** Capability numbers are placeholders until M9. The jungle's path graph and the sight terrain are assumptions. The hypothesis generator of section 9.3 is designed, not built. The prototypes under `experiments/m7/` are evidence, not M8 code.

## 2. Phases and results

M7 ran as nine phases. Each phase ended in a check.

| Phase | Question | Check | Result |
| --- | --- | --- | --- |
| P0 Ground | What do the roadmap, the handoffs, and the predecessor fix, and what hardware is there? | Sources read. Hardware queried. | Done. Section 10.3 lists the machine. |
| P1 Reference patch | What are the real clocks, rewards, and ranges? | Every ruleset value has a source status. A test enforces it. | Done. Patch 26.22. One conflict and six gaps (section 3). |
| P2 Contracts | What are the state, action, observation, and timing contracts? | Two independent designs compared. | Done. Section 12 records the decisions. |
| P3 Map | Do route lengths give the right travel times? | Graph distances against an independent derivation. | Verified within 3 percent. The correction added the range and sight measures (section 5.1). |
| P4 Waves | Do freezes and slow pushes emerge from mechanics? | Scenario runs over 5 seeds, three rounds, with a tick sweep. | No. Timing, economy, and capacity work. Neither behaviour passes its test with a champion that can die (section 5.6). |
| P5 Kernel | Do the timing, fight, information, and snapshot contracts hold in code? | A ten-champion prototype with its tests. | Information and snapshots verified. Timing verified after the correction (section 5.2). Fights carry caveats (section 5.9). |
| P6 Compute | What can this machine run overnight? | Benchmarks with run counts, ranges, and limiters. | Measured. Budget in section 10.3. |
| P7 Plan | How is M8 divided, and where does the pilot go? | Each checkpoint has acceptance criteria. | Done. Section 10. |
| P8 Review | Does the trail hold up? | Handoff 003 and an independent review on a different model. | The review found 3 defects and 11 items to fix. The first version included the corrections. |
| P9 Correction | Do the seven issues of the planning review hold, and what fixes them? | Each issue checked against the code, fixed, and tested again. All evidence rerun with run metadata. | All seven held. Handoff 004 lists what changed, what was rerun, and what stays unresolved. |

To rerun all evidence, see [section 13](#13-how-to-rerun-the-evidence).

## 3. Reference patch

The simulator takes its clocks, rewards, and ranges from one documented patch. The values live in [`riftgame/rulesets/patch_26_22.toml`](../../riftgame/rulesets/patch_26_22.toml), one per line with a status tag. `tests/test_ruleset.py` fails if a value has no tag. Map coordinates live in [`riftgame/rulesets/map_summoners_rift.toml`](../../riftgame/rulesets/map_summoners_rift.toml).

### 3.1 Sources

The research used the official League wiki, Riot's patch notes for 26.1, 26.7, and 26.22, Data Dragon 16.22.1, and Community Dragon build 16.22. Wiki pages were read through a fetch tool that summarizes, so a single-page value (`F1`) is a reading of the page, not a byte copy. The map coordinates were parsed directly from Community Dragon's `base_srx.materials.bin.json`, so they are exact file values. The research notes, with one source link per value, are in [`docs/reference/`](../reference/).

### 3.2 Timings that the simulator uses

| Rule | Value in 26.22 | Status |
| --- | --- | --- |
| First minion wave | 0:30 | F2 |
| Wave interval | 30 s, 25 s from 14:00, 20 s from 30:00 | F2 |
| Siege minion | First on wave 3, then every 3 waves, every 2 from 14:00, every wave from 25:00 | F2 |
| Minion move speed | 350 | F2 |
| Minion gold | Melee 20, caster 14, siege 50 plus 1 per upgrade | F2 |
| Minion XP | Melee 62, caster 31, siege 75 | F2 |
| Minion XP sharing | Range 1500. One champion gets 100 percent, two get 65 percent each | F2 |
| Blue Sentinel, Red Brambleback, Murk Wolves, Raptors | First spawn 0:55 | F2 |
| Gromp, Krugs | First spawn 1:07 | F2 |
| Camp respawn | 5:00 for the two buff camps, 2:15 for the other four | F2 |
| Rift Scuttler | Two spawn at 2:55. After both die, one respawns 2:30 later | F2 for the spawn, F1 for the respawn rule |
| Speed Shrine | 90 s, sight radius 525 for the killer's team | F1 |
| Recall | 8 s channel after a 0.5 s cast. Damage or movement interrupts it | F1 |
| Fountain | 8 percent of maximum health per second | F2 |
| Outer tower | 9000 health, range 750, 0.833 attacks per second | F2, F1 |
| Sight radius | Champion 1350, minion 1200, tower 1350, Stealth Ward 900 | F1 |
| Death timer | 10 s at level 1, rising to 52.5 s at level 18, no time scaling before 15:00 | F2 |

### 3.3 Points where the reference needed a ruling

**Camp respawns (resolved).** The owner decision says "Spawns follow the game clock, not completion of a jungler's clear." The owner has since clarified that this sentence concerned first spawns. Every camp first appears at a fixed clock time, whatever any jungler does. Respawns follow real League. The wiki's Monster page says that the respawn timer "does not start until all monsters in the camp are dead" (F1). A camp therefore respawns at the game time of its last death plus the delay. No conflict remains.

**Timer visibility.** The reference gives a team a camp's respawn timer in two cases (F2). The team saw the clear. Or the team sees the camp's location in the last 60 s before the respawn for a buff camp, or the last 10 s for another camp. The design copies this rule, because it is what keeps an unseen counterjungle hidden.

**The 14:00 boundary.** In 26.22, tower plates no longer fall at 14:00 (F2). The wave interval, the siege cadence, and the Homeguard rule do change at 14:00. This design uses 14:00 only where the reference does.

### 3.4 Reference rules that M8 leaves out

M7 left out these rules of the reference patch, and M8 leaves out all but the ones marked below. Each is a stated simplification, and section 11 lists the ones that carry risk.

- Role quests, including the level cap of 20 and the early off-lane penalties for mid and support.
- Bounties, shutdowns, and the assist-gold timing rules.
- The minion "pushing advantage" bonus that depends on team level difference. M7 left it out. C2 adds it (section 5.6).
- Unit collision between minions, and the call-for-help rule that draws minions onto a champion who attacks an allied champion. M7 left them out. C2 adds them (section 5.6).
- The side-lane speed boost for minions, and minion speed growth after 10:00. C2 adds the speed boost (section 5.6). The speed growth stays out.
- Buff effects of the Crest of Insight and the Crest of Cinders.
- Crystalline Overgrowth, Bulwark, and Faelight sites.
- Brush, and Control Wards and Oracle Lens. Section 6 covers the vision model.
- The smaller waves of the mid game: one fewer melee minion on siege waves from 14:00, and one fewer caster from 30:00.
- The support item's income from hitting enemy champions and towers. M8 models only the shared minion kills and the passive gold.
- The larger Homeguard bonus (150 percent) after 14:00 or after a lane's tower falls.
- The Homeguard endpoint that tracks the wave after 14:00. M8 uses the first rule only: the speed bonus ends 500 units behind the lane's outer tower.

### 3.5 What the research could not verify

- No fetched page states when the first waves meet. The route graph gives 21.8 s after spawn for mid and about 31 s for the side lanes, which matches the researcher's independent figure (Tested, `tests/test_map.py`).
- Per-upgrade minion stat growth. The ruleset interpolates linearly between the documented endpoints (Assumed).
- A full-clear time on the 2026 clock.
- Per-level camp health and XP curves. The ruleset holds the endpoints.
- Whether a team needs vision to get the Scuttler's respawn timer.
- The live date of 26.22 was seen in one search result only.

## 4. From observable state to comparison

The roadmap asks how an observable game state becomes a legal macro action, a simulated consequence, and a counterfactual comparison. This section gives the path in one place. Sections 5 to 9 define each step.

1. **Observable state.** The world holds the full state. `observe(world, seat)` builds one champion's observation from its own state, its teammates, its team's current view, its team's memory, and public facts. Nothing else reads the world on a policy's behalf.
2. **Legal macro action.** A policy returns one action from a fixed table, such as `LANE top last_hit` or `RECALL`. The legal mask is a function of the observation, not of the world.
3. **Simulated consequence.** The action sets the champion's intent. The intent persists across fixed simulation ticks. Routine execution (walking, last-hitting, attacking a target in range) is automatic. Consequences come from mechanics: route lengths, minion fights, tower shots, attack capacity, and clocks.
4. **Counterfactual comparison.** The harness takes what the deciding team knows, adds one hypothesis about what is hidden, substitutes one action (or one team plan), and runs paired continuations under stated policies. It reports each consequence separately, for each hypothesis.

## 5. World model

### 5.1 Space: routes for movement, straight lines for range, terrain for sight

**Decision.** The map is a graph of 39 named nodes and 56 straight edges. A position is `Pos(edge, offset)`, a distance along one edge. Every position also has map coordinates. Three questions about two positions get three separate answers (`riftgame/map.py`).

| Question | Measure | Function |
| --- | --- | --- |
| Movement. How long is the walk from a to b? | The shortest route on the graph | `distance`, `advance`, `travel_time` |
| Interaction. Is b within attack, XP, tower, or ward-placement range of a? | The straight line between the map coordinates. Terrain does not block it. | `separation` |
| Visibility. Does a source at a see b? | The straight line is within the sight radius, and the segment between them crosses no terrain | `sees`, `sight_clear` |

The first version of this document used route distance for all three. The planning review objected, and the objection holds. A walking distance says nothing about range or sight. Two champions on either side of a wall are close and cannot see each other. Two champions on nearby paths with open ground between them see each other, however long the walk between them is.

The kernel combines the measures by three rules.

- A targeted attack needs both. The target is within range by `separation`, and the target is in the view of the attacker's team. A ranged attack therefore reaches over a wall when a ward or an ally sees the target, as in the game.
- XP range, tower range, and ward-placement range use `separation` alone.
- Minions of one lane keep the lane coordinate `s` among themselves. On a lane edge the straight line and the route are the same length.

The graph itself is unchanged.

- Each lane is a chain of nodes taken from the game's own minion path waypoints. A lane has a lane coordinate `s`, the distance from its blue end. Waves live on `s`. Towers sit at the projection of their real coordinates onto the lane.
- Each of the four jungle quadrants has three camp nodes at the real camp coordinates. Two river nodes sit at the two Scuttler positions.
- Jungle and river edges join camps to each other, to lane nodes, and to the river. Which nodes are joined, and a detour factor of 1.15 on the walking length of those edges, are Assumed. The map file gives positions but no walkable-path graph.

**Terrain model (Assumed).** The map file has coordinates and no walls, so sight terrain is built from the graph.

- Open ground is every point within a half-width of an edge's straight segment: 600 for a lane, 500 for the river, 250 for a jungle path. The lane and jungle values are League scale without a source. The river value rests on one datum: two sites that the map file names `RiverWall` lie 468 and 547 units off the river edges (Derived. That the name marks the bank is an inference.).
- A sight line is clear when sample points every 50 units along it all lie on open ground, and it crosses none of four wall segments.
- The four walls screen the Gromp and Raptor camps of each side from the lane beside them. They are the only camps within a champion's sight radius of a lane line. Corridors alone cannot hide the Raptors at any width, because the graph joins the camp to mid lane by one straight edge. Each wall is built by one rule from the camp and lane coordinates. It runs parallel to the lane, one lane half-width from the lane line, for 500 units either side of the point nearest the camp.

All these values are in [`map_summoners_rift.toml`](../../riftgame/rulesets/map_summoners_rift.toml) with the tag `A`.

**Tested** (`tests/test_sight.py`, 34 cases). The expected answers were worked by hand from node coordinates and League geography before the code ran. The red-side mirror of each case gives the same answer.

| Case | Straight line | Route | Seen at radius 1350 |
| --- | --- | --- | --- |
| Junction. Two positions 400 units out on two arms that meet at `mid_river`. | 475 | 800 | Yes |
| Corner. Two positions 290 units out on each arm of `top_corner`, against a caster's range of 550. | 534 | 580 | Yes. In range by the straight line, out of range by the route. |
| Nearby paths, open ground. Mid lane 800 units from the river crossing, and the river 920 walked units out. | 1,013 | 1,720 | Yes, although the walk is longer than the sight radius |
| Nearby paths, wall between. Mid lane beside the blue Raptors. | 1,171 | 1,448 | No |
| Wall. Top lane beside the blue Gromp. | 954 | 4,476 | No |
| Ward over a wall. A position 705 walked units from the Raptor camp, against the placement range of 625. | 613 | 705 | No. In range and not seen, so range and sight are separate questions. |
| Terrain without a wall. Two Krug exits, 920 walked units out on each. | 1,236 | 1,840 | No |
| One straight lane edge, gaps of 1,349 and 1,351 | the gap | the gap | Yes and no |

The tests' author broke the code in four ways to check that the tests can fail. Removing the walls failed 7 cases, and calling all ground open failed 2. Using route distance for `separation` failed 29, and calling every sight line clear failed 16. These four counts are Reported by the delegate that wrote the tests. The mutation script is not in the repository.

**The graph's lengths** are checked against a second derivation from the same map file (spawn point, barracks, and the full minion path polyline) in `tests/test_map.py`. It is a consistency check on the graph's down-sampling. It does not measure travel time in the real game. The test tolerance is 4 percent.

| Quantity | Route graph | Second derivation | Difference |
| --- | --- | --- | --- |
| Blue fountain to blue top outer tower | 10,450 | 10,184 | +2.6 percent |
| Blue fountain to blue mid outer tower | 8,061 | 8,095 | -0.4 percent |
| Blue fountain to blue bot outer tower | 10,639 | 10,333 | +3.0 percent |
| Fountain to fountain through mid | 19,762 | 19,791 | -0.1 percent |

At a move speed of 335 the walk from the fountain to an outer tower is about 31 s in a side lane and 24 s in mid, before Homeguard.

**Limits (Unresolved).**

- The walls are constructions, not terrain data. The game's navigation grid would replace them behind the same `sight_clear` function.
- A jungle path that runs beside a lane is open to the lane. Between top lane and the blue Gromp path, 1,548 of 2,071 sampled pairs within range see each other. The real map has a wall along most of that length (from memory, not checked). A jungler on such a path is seen from the lane earlier than in the game.
- There is no brush, no lateral position inside a lane, and no height. A jungle edge is straight for sight and 1.15 times longer for walking, so the model does not know where a path bends.
- Terrain thinner than the 50-unit sample step can be stepped over.
- `sees` costs about 6.4 microseconds for a pair inside the radius, against 0.6 for `distance` (one run on a busy machine, a rough figure). A pair outside the radius costs the same as `distance`.
- The M7 kernel prototype has not been moved to these measures. It still uses route distance for sight and for attack range. Its fight and vision results (sections 5.9 and 6.3) therefore test the contracts in the old geometry, and its throughput does not include the cost of `sees`. C5 and C6 measure again on the new geometry.

### 5.2 Time is a fixed tick with a separate decision interval

**Decision.** The simulation advances in fixed ticks of `tick_s` seconds. Policies decide every `decision_ticks` ticks. Both are configuration values. M8 starts from `tick_s = 0.5` and `decision_ticks = 4`, so a champion decides every 2 s.

**Why 0.5 s.** Durations round up to whole ticks. At a 1.0 s tick the 8.5 s recall takes 9.0 s, and at 0.5 s it takes 8.5 s (Tested, `experiments/m7/kernel/results/scenarios.json`, `q1_timing`). Tower shots (1.2 s apart), lockdown durations, and the 3 to 4 s between seeing a ganker and contact are all a small number of seconds, so a 1.0 s tick is a coarse unit for them. Wave results move with the tick too. With both laners last-hitting, creep score is 0.91 at ticks of 0.125 and 0.25 s, 0.90 at 0.5 s, and 0.80 at 1.0 s. Of 17 wave metrics, 15 are within 10 percent of a 0.125 s reference at a 0.5 s tick, and 13 at a 1.0 s tick (section 5.6). At the same decision interval, the 0.5 s tick costs 41 percent of simulated seconds per wall second in the prototype (728 against 1,239 on one process).

**Why 2 s.** This rests on arithmetic, not on a test. A champion sees an approaching enemy at 1350 units. At a closing speed near 350 that leaves under 4 s before contact. A 5 s interval can pass without one decision in that window, so a gank could succeed because of the interval and not because of the map. The second design candidate raised this argument (Reported, section 12). The prototype's gank scenario does not test it. That scenario varies only the laner's reaction, and only by one second.

**Tested** in the kernel prototype (`experiments/m7/kernel/results/scenarios.json`, `q1_timing`). A run at decision interval n equals, digest for digest over 300 ticks, a run at interval 1 whose policy returns `KEEP` on the other ticks. This holds for n of 2, 4, and 10 and with both lane models. Orders do complete inside these runs. At interval 2, 84 intents ended: 31 `ABSENT`, 14 `CLEARED`, 7 `DIED`, 2 `KILLED`, 4 `PLACED`, and 26 `RECALLED`. A run at interval 1 without `KEEP` differs from a run at interval 10, for a reactive policy and for fixed orders alike. That dependence is intended. A champion whose order completes waits for its next decision (section 7.2).

**Starting values, not validated constants.** The owner accepted the pair (0.5 s, 2 s) as starting values. C7 runs a sweep over tick lengths 0.25, 0.5, and 1.0 s and decision intervals 1, 2, and 5 s before the pilot (section 10.1).

One tick runs these steps in this order. The order is part of the contract, because pinned replays depend on it.

1. Apply the actions that policies submitted for this tick (decision ticks only).
2. Spawn on the game clock: waves, camps, Scuttlers, champion respawns.
3. Move. Champions that are not pursuing move first. Pursuers then move against the positions that their targets held before this step.
4. Collect every attack of this tick from the state at the start of the tick: minions, towers, camps, and champions.
5. Apply all damage at once. Then resolve deaths, gold, XP, and level-ups.
6. Advance channels, record intent outcomes, and apply fountain regeneration and purchases.
7. Update each team's view and memory.
8. Advance the clock.

Steps 3 to 5 are meant to make the result independent of the order in which the code visits champions. The prototype now tests this. It stages four fights twice, with the two sides' seats exchanged (`q2_fights.e_seat_order`).

- Positions, health, and death ticks are identical in all four fights (Tested).
- Kill rewards are not. When both fighters die on one tick, the killer of the champion that the code visits first gets the first-blood bonus of 100 gold and the kill XP. The other killer gets neither. This is a defect of the prototype. It stays visible as a test that is expected to fail.
- M8 resolves all deaths of one tick from the state before any of them. Each killer gets its kill gold and XP, and a keyed draw on the tick picks the team that gets first blood (C5).
- The test exchanges the two teams only. Order inside one team is untested.

Policies read the view of step 7, so a policy always acts on what its team saw at the end of the previous tick. Automatic execution obeys the same limit (section 6.3).

### 5.3 State contract

The world owns every mutable fact. There is no state anywhere else, and no random generator state.

| Entity | Fields |
| --- | --- |
| World | Ruleset id, map id, seed, tick, and the entities below |
| Champion (10) | Seat, team, role, profile, home lane, position, health, mana, XP, unspent gold, upgrades bought, intent, intent phase, tick the intent started, channel progress, outcome of the last finished intent and its tick, roam allowance, attack credit, slow end tick, respawn tick, ward charges, support-item charges, tallies |
| Minion | Unique id (wave number and index), team, type, health, lane coordinate, attack credit |
| Tower (18) | Lane, team, tier, health, attack credit, damage ramp state |
| Camp (12) and Scuttler (2) | Node, kind, health or next spawn tick, engaged champion |
| Ward or shrine | Team, position, expiry tick, owner |
| Team memory (2) | Last-seen record per enemy champion, last-observed state and timer knowledge per camp, last-seen enemy wave per lane |

Level is derived from XP. Liveness is derived from health. Neither is stored twice.

### 5.4 Champions and capability

Each team has five fixed seats: top, jungle, mid, carry, support. Each seat has a capability profile. A profile is a small table of numbers that scale with level and with upgrades bought.

| Capability | Used by |
| --- | --- |
| Maximum health, health regeneration | Combat, recall decisions |
| Mana and its costs | Wave clear, lockdown, recall decisions |
| Sustained damage per second against champions, attack range | Combat |
| Lockdown: a slow or stop, its duration, and its cooldown | Combat, escapes |
| Move speed | Travel, chases |
| Wave numbers: hit damage, attack speed, area damage per second | Lanes |
| Camp damage per second | Jungle |

**Until M9.** The owner accepted one simple mana pool per champion as a working choice. M8 uses five placeholder profiles in one table (Assumed). The numbers only need to be distinct and plausible. M9 replaces the table and the damage function behind the same two interfaces, `capability(profile, level, upgrades)` and `damage(raw, target)`. All ten champions use the same execution competence. No skill parameter exists yet.

### 5.5 Recall and purchases

- `RECALL` is a channel of 8.5 s in place. Damage, or any new action, cancels it and discards all progress. A restarted recall takes the full time again.
- On completion the champion appears at its fountain. The fountain restores health and mana at the reference rate.
- At the fountain the champion buys the next upgrades of its profile's fixed progression while its gold covers them. A progression is a short ordered list of `(cost, capability changes)`. The first entries follow real anchors: boots for 300 gold give +25 move speed (Sourced), and second-tier boots give +45. The other entries are Assumed until M9.
- Capability reads the upgrades bought and never reads unspent gold. Unspent gold has no combat value.
- The return to lane is ordinary travel along routes, with the Homeguard speed bonus of the reference.

Purchases are automatic in M8. The decision the player controls is when to recall. M9 tests whether purchase thresholds change recall timing.

### 5.6 Lanes, waves, and economy

One `LaneSim` class serves all three lanes. It owns the lane's minions and towers.

**Decision.** M8 models each minion individually: type, health, lane coordinate, a lateral slot in its wave, and attack credit. The rules below are the whole wave model. All are Sourced unless marked.

- Waves spawn on the reference clock with the reference composition and stats.
- A minion marches at 350 until an enemy minion or tower is within 500 units. It then closes to its attack range and attacks.
- A minion attacks the nearest enemy minion. Among enemies equally far along the lane, it picks the one in the nearest lateral slot (Assumed geometry). A keyed draw breaks any tie that remains.
- A hit deals attack damage plus a share of the target's current health: 2 percent for a melee minion, 3.5 percent for a caster, 5 percent for a siege minion. The two wiki pages for the first two values were read a second time during the correction, and the quoted sentences agree with the ruleset.
- With no enemy minion or tower in range, a minion attacks the closest enemy champion in range that stands in its path, at 60 percent damage. "In its path" is defined below (Assumed).
- Towers act as in section 5.7.

A cheaper variant that pools each wave's minions into cohorts was built in the first round and not chosen. It cannot express a per-minion rule such as champion aggro. Its cost and accuracy figures were never written to a results file, so this document no longer quotes them.

**Three rounds of tests** (`experiments/m7/waves/`, results in `results/waves.json`).

- **Round 1** used a specification in which minions ignored champions and had no lateral slots. It failed on freezes, slow pushes, and lane stability. Its results file was overwritten and nothing in this document rests on it (Reported).
- **Round 2** added one documented rule, champion aggro, and one assumption, lateral slots. Lateral slots were added after a failed round, so they need the same scrutiny as any rule that might exist only to produce an outcome. The planning review then found that the round's slow-push scenario could not succeed, and that its freeze rested on a champion that could not die.
- **Round 3** is the correction. It changed scenarios only. No lane rule was added or tuned. The pass tests for a slow push and a freeze are the ones written before round 2's results. The freeze test has one addition, that the champion must neither die nor retreat.

**What round 3 checked and fixed.** The lane code was read against the documented rules first. They are the target priority (minion, then tower, then champion), the 500-unit acquisition range, the damage per hit, and the tower shots. No rule error was found. Four scenario errors were found and fixed.

1. The holding champion could not die. It absorbed 19,700 damage in four minutes. The scenario champion now has 650 health, 30 armor, 1.5 health regeneration per second, and move speed 335 (all Assumed placeholders for a level 1 to 3 laner). Below 30 percent health it walks to its own tower and stays out until it is back above 60 percent.
2. The champion jumped to its chosen spot every tick. It now walks there at its move speed.
3. The champion stood ahead of its own minions and inside the enemy wave's acquisition range. It now stays behind its own lead minion, except when it holds on purpose.
4. The slow-push scenario started at an unnatural phase of the wave clock, thinned one wave, and stopped at the first arrival. It now runs on the game's own clock from 0:00, from two starts, and continues for 20 s after the crash.

**In the path or aside.** Fix 3 exposed a gap in the model, not only in the scenario. A lane coordinate has no width, so a champion cannot step out of an advancing wave's way, and minions at 350 outrun a champion at 335. In an intermediate run of the correction, a champion that stood 550 units off still fell to 29 percent health in a symmetric last-hit lane (Reported, that run is not kept). The scenarios therefore use this rule (Assumed): a champion is in the minions' path, and a valid target for them, only while the waves are in contact or while it holds. Otherwise it has stepped aside. M8 needs the same rule in the `LANE` action, which is why the mode table below gains a fifth mode.

Every number below is at the 0.5 s tick that M8 starts from, over 5 seeds. A range in brackets is the minimum and maximum across seeds.

What the mechanics produce (Tested):

| Behaviour | Result at a 0.5 s tick |
| --- | --- |
| First contact | 51.5 s in mid and 60.5 s in top, as the geometry predicts |
| Hard push | A pushed wave of 6 reaches the enemy tower 9 s after first contact in mid and 10.5 s in top |
| Both laners last-hit | Creep score is 0.90 and 0.89. The front stays within 95 units of centre for 10 minutes in mid. |
| Attack capacity | Creep score falls from 0.90 to 0.55 to 0.42 as capacity falls from 1 to 0.5 to 0.25. Under the own tower it is 0.50. |
| Lateral slots | An undisturbed lane leaves both towers untouched for 10 minutes in 5 of 10 runs, and in 0 of 10 without slots. |
| An even fight | Six minions against six kill each other to the last minion in 25.5 s. One extra caster wins in 18 s with 4 of 7 left. |
| Minion aggro on a champion in the path | A champion that holds 9 to 12 minions off its tower is hit for 4.5 s, loses 557 health after armor [534 to 578], and retreats at 20 percent health (case `S5c k=3 hold`). |

What they do not produce (Tested, negative):

| Behaviour | Result at a 0.5 s tick |
| --- | --- |
| A stacked wave | Not shown in 32 cases: two lanes, two starts, four plans, the enemy laner absent or last-hitting. The test asks for a thinning plan that reaches the enemy tower later than a hard push, with 12 or more minions. The largest thinned wave at the tower has 4. |
| A freeze that a mortal champion holds | Not shown in 40 holding cases: five surplus sizes and eight holding plans. The test asks for the front to stay within 1,500 units outside the tower's range for over half of 240 s in every seed, with both controls below that and no death or retreat. No case passes. |
| Stability under a small change | A lane that is one caster short reaches the enemy tower at 101.5 s in mid and 111.5 s in top with 5 minions, then swings back and reaches the other tower by 170 s. Whether a real lane does that is unknown. |
| Bounce after a crash | Seen in 4 of 10 runs. |

**The slow-push cases.** Each row is top lane with the enemy laner absent. "Crash" is the time from the start of the plan to the first minion in the enemy tower's range, and "wave" is the number of minions within 1,500 units of the lead at that moment. The last two columns repeat the run with the current-health share of minion damage switched off, as a sensitivity run.

| Start | Plan | Crash | Wave | Crash, flat damage | Wave, flat damage |
| --- | --- | --- | --- | --- | --- |
| First contact | Push | 10.5 s | 6 | 11 s | 6 |
| First contact | Thin 3 casters, then last-hit | 22 s | 3 | 24 s | 5 |
| First contact | Last-hit only | 50.5 s | 5 | 52 s | 9 [7 to 9] |
| After an enemy crash | Push | 30.5 s | 6 | 30.5 s | 6 |
| After an enemy crash | Thin 3 casters, then last-hit | 74.5 s | 4 | 93.5 s | 10 [10 to 11] |
| After an enemy crash | Last-hit only | 74.5 s | 4 | 86.5 s | 12 |

Three things follow from the table and the traces (Tested).

- **Fights end before reinforcements arrive.** An even fight lasts 25.5 s and the wave interval is 30 s. In top lane the centre is about 1,600 units from the enemy tower's range, which is under 5 s of marching. A wave that wins at the centre reaches the tower and dies there before its next wave can join it.
- **Thinning costs the pusher its own melee line.** A champion with 65 damage and 0.65 attacks per second needs about 20 s to kill three casters. The thinned wave loses most of its own melee line before those casters are dead. In the traced run, two of three allied melee minions died within 12 s of contact. The thinned wave arrives with 3 or 4 minions. A hard push arrives with 6.
- **The fight length decides stacking.** Without the current-health share, an even fight lasts 31.5 s, which is longer than the wave interval. A wave that bounces back from an enemy crash then arrives 12 strong by last-hitting alone. With the share it arrives 4 strong. The test still fails in the flat configuration, because the largest thinned wave there has 10. The share is a sourced rule of the reference patch, so the flat run is a diagnosis and not a candidate model.

**The freeze cases.** The built state has full waves in contact 300 units outside the blue tower's range in top lane, with k surplus enemy casters. "Band" is the time the front stays within 1,500 units outside the tower's range, out of 240 s.

| Surplus k | Plan | Band | Lowest health | Retreats | How it ends |
| --- | --- | --- | --- | --- | --- |
| 3 | Champion absent | 89.5 s [82 to 103.5] | not applicable | not applicable | The wave crashes into the tower for 25.5 s, then the lane is pushed out |
| 3 | Push | 10.5 s | 100 percent | 0 | Pushed out |
| 3 | Hold, last-hit only | 110.5 s [90.5 to 116.5] | 20 percent | 1 | The champion retreats, the wave crashes, then the lane is pushed out |
| 3 | Hold, thin while the enemy leads by more than 1 | 58.5 s [57.5 to 62] | 62 percent | 0 | Pushed out |
| 3 | Hold, thin while the enemy leads by more than 3 | 60 s [56.5 to 64] | 37 percent | 0 | Pushed out |
| 4 | Hold, last-hit only | 148.5 s [146 to 168.5] | 20 percent | 1 | As for k of 3 |
| 4 | Hold, thin while the enemy leads by more than 3 | 59 s | 33 percent | 0 | Pushed out |
| 6 | Hold, last-hit only | 127.5 s [126.5 to 130] | 16 percent | 1 | As for k of 3 |

- **A hold without thinning costs too much health.** Six casters deal 93 damage per volley before armor, every 1.5 s (trace from `python -m experiments.m7.waves.diagnose "S5c k=3 hold" "A+B" 0 0.5 50`). The champion retreats on the first cycle. The band time after that is not the champion's doing. It sits at its tower for about 170 s while it regenerates. If health is ignored, `k=4 hold` and `k=6 hold` pass the band test, which is what round 2 reported.
- **A hold with thinning loses the surplus.** Near the blue tower the blue wave arrives 8 s before the red one (26.8 s against 34.8 s after spawn). In the traced run, the fresh blue wave killed 4 of the 6 remaining casters in those 8 s. Whatever surplus the champion trimmed to save its health is gone one cycle later, and the lane is pushed out. Every holding run ends with the blue wave past the lane centre.
- **An enemy laner who pushes breaks every hold**, as expected. The wave then sits under the tower for 89 to 119 s.

**Tick sensitivity.** The sweep now includes a 0.125 s reference. Of 17 metrics, 15 are within 10 percent of the reference at a 0.5 s tick (`S7b_tick_sensitivity`). In round 2, hold times changed by a factor of 2 to 5 between ticks. They now agree. `k=3 hold` stays 116, 113, 110, and 127 s in the band at ticks of 0.125, 0.25, 0.5, and 1.0 s. The old spread came from the champion that jumped each tick. Three metrics still move. They are the band time of `k=6 hold` (83, 110, 128, 105 s), the band time under a push (9.9, 8.5, 10.5, 24 s), and the size of the one-caster-short wave (6, 6, 5, 5).

**Conflict with the owner decision.** The decision says "Freezes and slow pushes emerge." M7 does not show that. With the reference patch's own numbers, a mortal champion, and no added rule, neither behaviour passes the test that was written for it. This document makes no claim that the simulator's waves are realistic.

**What is missing, precisely.** The model already uses every per-hit rule that the reference documents. What no document states is how long things take in a real lane. These are emergent quantities. Someone has to measure them in a custom game on the reference patch.

| Measurement | The simulator's value | Why it decides something |
| --- | --- | --- |
| Time from first contact to the death of the last minion in an untouched first-wave fight in mid | 25.5 s | A fight of 31.5 s instead of 25.5 s turns a 4-minion bounce into a 12-minion stack |
| Wave size and time at the enemy outer tower after a laner kills the three casters of wave 1 and then only last-hits, top lane | 3 minions, 22 s after first contact | This is the standard slow-push drill. It tests fight length and thinning together. |
| Number of wave cycles that a wave with 3 or 4 surplus casters stays outside the tower's range against a laner who holds and last-hits, and the health lost per cycle | Under 2 cycles. 557 health in the first cycle when the whole wave is held. | It separates a wrong damage scale from a wrong reinforcement rule |
| Whether minions keep attacking a champion that walks out of their path | Assumed: they stop | The in-path rule above rests on it |
| Time at which the first waves meet in mid and in a side lane | 51.5 s and 60.5 s | Checks the map and the spawn stagger |
| Front position of an undisturbed lane over 10 minutes | Towers untouched in 5 of 10 runs | Checks lateral slots, which are an assumption |

**What C2 does first.** Section 10.1 makes this C2's first task.

1. Rerun the three experiments on the M8 lane with the pass tests unchanged.
2. Add the four documented rules that bear on fight length and reinforcement and that M7 did not model. They are unit collision, which limits how many melee minions reach one target, the call-for-help rule, the pushing advantage from team level difference, and the side-lane speed boost. Each is a rule of the reference patch. Each still has to pass the predecessor's test for a new mechanic: it must not exist only to produce a named outcome.
3. Compare with the measurements above if someone has taken them. A mismatch is corrected only through a rule or a constant that the reference documents.
4. Add no rule whose purpose is to make a freeze or a slow push appear. If neither appears after steps 1 to 3, M8 keeps the lane as it is. The evaluation of section 9.5 then reports what holding, thinning, and pushing do in this simulator, and states that limit.

**Champion wave modes.** A champion with a `LANE` action stands at the wave and spends its attack capacity in one of five modes. The first four differ only in which minions the champion hits. In those four, the champion is in the minions' path while the waves are in contact and steps aside once its own wave is gone.

| Mode | What the champion hits | Where it stands with its own wave gone |
| --- | --- | --- |
| `passive` | Nothing. The champion stays in XP range. | Aside |
| `last_hit` | Only an enemy minion that one hit will kill. | Aside |
| `thin` | Enemy casters first, lowest health first, plus any last hit. | Aside |
| `push` | Any enemy minion, plus area damage on every enemy minion in range. | Aside |
| `hold` | As `last_hit`. | In the path, on a line that stops the enemy's lead minion 300 units outside the range of the champion's own tower |

`hold` is new in this revision (Assumed). Without it, no action lets a champion keep a wave off its tower, so a freeze could not emerge whatever the wave rules were. With it, a freeze is still not an action. Whether the wave stays depends on the minions, and in M7's tests it does not. No action is called freeze or slow push.

**Gold and XP.**

- A champion gets a minion's gold only for its own killing blow. A minion that dies to anything else gives no gold.
- XP for a minion's death is shared among enemy champions within 1500 units of the death, using the reference split. The lane reports the death and its position. The world grants the XP, because only the world knows where every champion is.
- **Bot lane.** Carry and support share one lane. Either can take a last hit. XP splits, and each minion's gold is paid once, so two champions cannot both collect a solo laner's minion income.
- **Support income.** The support holds the support item of the reference: 3 gold per 10 s, and a charge every 20 s (maximum 3, first at 1:05). With a charge and an ally within 1050 units, the support's attack executes a low minion. The support gets 18 gold and the nearest ally gets the minion's gold (Sourced). This income is new gold. It is why a carry and support together can earn more gold than a solo laner, by at most the item's income (section 10.1, C2). Without a charge, a support in `last_hit` mode takes farm from its carry, and a support in `passive` mode does not. The item's later upgrade tiers are left out (Assumed simplification).
- Passive gold, starting gold, kill gold by victim level, and the XP curve follow the reference. Bounties are left out.

### 5.7 Lane towers

M8 has the three lane towers of each lane and team: outer, inner, and inhibitor tower. Inhibitors, nexus towers, and the nexus belong to M10. The owner accepted three tiers as a working choice.

- A tower can take damage only after the tower in front of it has fallen (Sourced).
- A tower shoots enemy minions in range, siege first, then melee, then caster. Each shot removes a fixed share of the minion's maximum health (Sourced).
- A tower shoots an enemy champion in range that damaged one of the tower's allied champions, and its damage ramps with consecutive hits (Sourced). A tower with no minion in range also shoots a champion in range.
- Minions and champions damage towers. Without enemy minions near the tower, damage to it is cut by 80 percent (Sourced).
- Tower plates give 120 local gold each at the reference's health thresholds. A tower kill gives the reference's global gold.
- A wave that passes a team's last lane tower reaches that team's base and is removed there. This is a stand-in until M10 adds inhibitors and the nexus (Assumed).

A fallen tower has consequences that later decisions feel. Enemy waves march further, the Homeguard run is shorter, the lane loses a safe farming spot and a vision source, and the lane's role assignment ends (section 5.10).

### 5.8 Jungle camps and Scuttlers

- Each quadrant has three camps, as the owner decided: Gromp, Blue Sentinel, and Murk Wolves in one, Raptors, Red Brambleback, and Krugs in the other.
- A camp is one pool of health with a damage rate against the champion that fights it. A camp's gold and XP are the reference totals.
- A `CAMP` action walks to the camp and attacks it. Leaving is only a new action. The camp keeps attacking while the champion is inside its leash distance. After that it resets to full health.
- First spawns and respawns follow section 3.3.
- **Scuttler.** Killing a Scuttler creates a Speed Shrine at that river node. The shrine is a vision source of radius 525 for 90 s for the killer's team. It uses the same code path as a ward. The shrine's speed effect is left out of M8 (Assumed simplification).

### 5.9 Combat

**Decision.** There is no fight object and no fight outcome roll. A fight is what happens when champions with attacking intents are within range of each other over several ticks.

- A champion with a `FIGHT` action closes to its attack range, then deals its damage rate each tick.
- A champion's lockdown slows or stops the target for its duration, then goes on cooldown.
- **Retreat.** Leaving a fight is a new action, such as `MOVE` toward a tower. The pursuer keeps dealing damage while the target stays within its range and in its team's view. Whether the retreat works depends on speed, slows, the distance to safety, and towers.
- **Reinforcement.** An ally joins a fight by arriving. Arrival time is route length over speed.
- **Remaining resources.** Health and mana persist after a fight. They return only through regeneration or the fountain.
- **What agents see.** An observation holds combat facts: health, level, upgrades, positions, and who is nearby. It never holds a win probability.

**Tested** in the kernel prototype (`experiments/m7/kernel/scenarios.py`, results in `results/scenarios.json` under `q2_fights`). All capability numbers in these runs are placeholders, so the outcomes show that the mechanics respond, not that they are calibrated. The runs measure range by route distance (section 5.1). The rerun after the correction reproduced the first run's values in every field.

| Scenario | Result |
| --- | --- |
| A champion retreats at half health. Sweep of speed difference, lockdown, and distance to its own tower (18 cases). | 15 escapes and 3 deaths. No runner died from 1,000 or 2,500 units. From 4,000 units the slower runner died, the equal-speed runner escaped on 18 health without lockdown and died with it, and the faster runner always escaped. |
| A champion loses a 1v1 alone. An ally walks in from d units away. | The side wins when the ally starts within 2,000 units and loses from 2,250. |
| The same duel in open lane and under the defender's outer tower. | The attacker wins in open lane with 97 health left. Under the tower the defender wins with 472 left. |
| An enemy jungler leaves fog toward a laner. | A laner at its own outer tower is never touched. A laner at the enemy outer tower with 390 health dies, or survives on 30 health when it reacts one second later. The scenario does not test decision intervals (section 5.2). |

So outcomes change with distance, speed, lockdown, towers, and arrival time. The counts overstate how often a retreat works. The scripted chaser never gives up, and in 11 of the 15 escapes it died, mostly under the runner's tower. In the reinforcement sweep the first champion died in every case, and its side won when the ally arrived in time.

**Caveat.** With a speed advantage of 20 the runner escaped in every case. On a one-dimensional route, a chase is close to binary in the sign of the speed difference. Section 11 lists this as risk RK4.

**Settled in M7.** Fight duration, disengagement, and reinforcement timing come from per-tick mechanics, not from a formula.

**Deferred to M9.** The capability representation and its calibration. Burst, attack windup, dashes, and crowd-control detail. The execution-skill parameter. The conditions under which a strong champion wins a 1v2. Whether M9 needs an engagement entity to calibrate fights (section 11, risk RK4).

### 5.10 Roles, roams, and when assignments end

**Interpretation of the owner decision.** The decision is "fixed laning assignments with temporary roams allowed". This document reads it as follows. A laner's place is its lane. A roam is a bounded absence. When the bound is used up, the only thing the laner can choose is to go back, and it goes back on foot. Nothing teleports a champion, and no reward term punishes absence.

The first version only forbade `LANE` actions for another lane. The planning review pointed out that a laner could then leave its lane forever through `MOVE`, `FIGHT`, or `CAMP`. That is correct, and this section replaces the rule.

**Duty state.** Top, mid, carry, and support each have a home lane. Junglers have none and are unrestricted. At every tick a laner is in exactly one of three states, and each state does one thing to the laner's roam allowance.

| State | The laner is in it when | Roam allowance |
| --- | --- | --- |
| On lane | Its position is on an edge of its home lane | Refills by 0.25 s per second, up to the cap |
| Returning | It is off its lane, and its intent is a `LANE` action for its home lane or `RECALL`, or it stands on its fountain, or it is dead | Unchanged |
| Roaming | Anything else | Drains by 1 s per second, and may run below zero |

- The allowance starts full, at a cap of 90 s. The cap and the refill rate are starting values (Assumed). The refill rate bounds the long-run share of time a laner can spend roaming at 20 percent.
- The allowance and the state are fields of the champion's own state, so they are in its observation.

**The mask applies the role.** It is computed from the observation alone, like every mask.

- A laner may issue `LANE` actions only for its home lane.
- While the allowance is positive, every other action is legal anywhere. A roam is any such action away from the home lane.
- With an allowance of zero or less and off its lane, a laner's legal actions are the `LANE` actions for its home lane, `RECALL`, and `KEEP` when its current intent is already one of those.
- With an allowance of zero or less and on its lane, a laner may do anything whose target lies on its home lane. That covers `LANE`, `HOLD`, `RECALL`, `FIGHT` against a visible enemy on that lane, `MOVE` or `WARD` to a node of that lane, and `KEEP` of any of these. Actions that leave the lane are illegal until the allowance is positive again.

A laner whose allowance runs out in the middle of an intent keeps that intent until its next decision, which is at most one decision interval away. The allowance runs below zero during that time, and the laner has to earn the debt back on its lane. At that decision it has to choose a return action, and it walks back by ordinary travel along routes.

**What a roam still costs.** The duty state only bounds the absence. The cost of a roam stays mechanical. While the laner is away, its lane keeps running. Minions die without gold for it, it gets no XP outside 1500 units, and its tower takes damage.

**When assignments end.** A lane's assignment ends when either outer tower of that lane falls. All assignments end at 14:00, the reference patch's own mid-game boundary. After that a champion has no duty state and may issue `LANE` actions for any lane (Assumed, unchanged from the first version).

Junglers may issue `LANE` actions for any lane at any time. The reference's jungle-item XP penalty on lane minions applies to them. There are no team commands and no pings. Each champion chooses its own action.

**Tested** in the kernel prototype (`results/scenarios.json`, `role_duty`). Each run is 30 game minutes, at both clock settings.

- A policy that leaves its lane whenever the mask allows spends 16.7 to 19.1 percent of its time roaming once its first allowance is used up. The bound is 20 percent. It never roams longer than 92 s between two visits to its lane.
- No champion's position changes by more than its speed times the tick, except on death and on recall.
- A jungler under the same policy is never restricted.
- A realistic roam is legal from start to finish. A mid laner walks 4,387 units to the bot river, waits 15 s, and walks back. It is charged 30 s of allowance and is back on its lane 47.5 s after it left.
- The scripted policy makes no illegal choice in 30 minutes. Only the supports roam, on ward trips.

**The test corrected the rule.** The first form of the rule stopped the allowance at zero. Under it, the same policy roamed 22 to 50 percent of the time. The time between the allowance reaching zero and the laner's next decision was free, and it added up. The debt described above closes that gap.

**Limits (Unresolved).**

- A returning laner with no allowance cannot issue `FIGHT` outside its lane, even against a champion that attacks it. Whether a learned policy exploits that is a question for the pilot.
- The bound is on time charged as roaming, not on absence. The walk back is not charged, so the policy above is off its lane for 27 to 36 percent of the time. A laner may also stand on its fountain without limit. That is not a roam, and the lane's losses are its only cost.
- The prototype has no rule for the end of assignments. C1 adds it.
- The two constants are untested against learned behaviour. C7's sweep and the pilot report how often laners hit the bound.

### 5.11 Subsystems and the interfaces between them

M8 has ten modules. Each owns one body of rules. There is no plugin framework.

| Module | Owns |
| --- | --- |
| `ruleset` | The versioned constants of the reference patch |
| `map` | The route graph, positions, lanes, and the three measures of section 5.1 |
| `rng` | Keyed draws |
| `world` | All state, the tick order, snapshots, the digest, the invariant checker |
| `lanes` | Minions and towers of one lane, and champion wave inputs |
| `champions` | Capability profiles, intents, movement, recall, purchases |
| `jungle` | Camps, Scuttlers, shrines |
| `combat` | Collecting attacks and applying damage, including the `damage` function |
| `vision` | Team view, team memory, wards, `observe`, `legal_mask` |
| `harness` | Scenario loading, hypothesis generation, comparisons, scripted policies |

Seven interfaces connect them. M9 and M11 replace what sits behind an interface without changing it.

| Interface | Shape | Replaced later by |
| --- | --- | --- |
| Policy | `act(observation, noise) -> action` | M12 learned policies |
| Observation | `observe(world, seat) -> Observation` and `legal_mask(observation)` | M11 adds fields |
| Lane | `LaneSim.step(champion_inputs) -> events` | C2 may change rules inside |
| Capability | `capability(profile, level, upgrades)` and `damage(raw, target)` | M9 |
| Snapshot | `world.snapshot()`, `World.restore(snapshot)`, `world.digest()` | Stable |
| Hidden state | `hypothesis(info, rollout) -> hidden fields`, where `info` is one team's information state | M11 |
| Randomness | `keyed_uniform(seed, stream, ids...)` | Stable |

Three ownership rules came out of the prototype.

- A subsystem reports events. The world applies anything that crosses subsystems. The lane reports a minion's death, and the world grants the XP.
- Only `vision` writes team memory.
- Only `observe` reads the world for a policy, and automatic execution reads enemies only through the team view.

### 5.12 What is faithful and what is approximate

| Mechanic | Treatment | Status |
| --- | --- | --- |
| Game clock, spawn and respawn times, gold and XP values, XP curve, death timers | Faithful to the reference patch | Sourced |
| Lane lengths, tower positions, lane travel times | Faithful within 3 percent | Tested |
| Minion stats and targeting priority | Faithful stats. Stat growth is interpolated. Formation is one-dimensional with lateral slots. | Sourced and Assumed |
| Wave dynamics: freezes, slow pushes, bounces | Unknown fidelity. Freezes and slow pushes do not pass their tests. | Tested, negative (RK1) |
| Tower health, damage, range, aggro, plates | Faithful. Bulwark and Crystalline Overgrowth are left out. | Sourced |
| Recall and fountain | Faithful timings. Homeguard is simplified. | Sourced |
| Jungle geography | Approximate. Camp positions are real. Paths between them are assumed. | Assumed (RK3) |
| Camps | Approximate. One health pool and one damage rate per camp. | Assumed |
| Champions | Approximate. Five placeholder capability profiles. | Assumed until M9 |
| Combat | Approximate. Damage per tick within range, equal execution. | Assumed until M9 (RK4) |
| Items | Approximate. Discrete upgrades on a fixed progression. | Assumed until M9 |
| Vision | Approximate. Real radii in a straight line, sight terrain built from the graph and four constructed walls, no brush, invisible wards. | Tested geometry, Assumed terrain (RK5) |
| Support income | Approximate. First item tier only. | Sourced, simplified |
| Bounties, role quests, buffs | Left out | Section 3.4 |

## 6. Information

### 6.1 Team view

A team sees an enemy champion, minion, or camp when one of its vision sources sees it by the sight measure of section 5.1. The target is within the source's sight radius in a straight line, with no terrain between them. Vision sources are the team's living champions (1350), minions (1200), living towers (1350), wards (900), and shrines (525). Teammates share one view. An enemy Stealth Ward is never in a team's view.

A champion that damages an enemy champion is visible to the victim's team on that tick.

### 6.2 Team memory

Memory changes only in step 7 of the tick, and only from what the team sees.

- **Enemy champions.** While an enemy is visible, the team's record of it is current. When it leaves vision, the record freezes: position, tick, health, level, upgrades.
- **Camps.** The team records a camp's state when it sees the camp's location. It knows a respawn time only under the reference rule of section 3.3.
- **Enemy waves.** The team records a lane's enemy front and counts when it sees them.

Hidden movement and hidden camp changes stay hidden. A team learns about an unseen clear only by seeing the empty camp, or by inference that the policy makes for itself.

### 6.3 Observation and action mask

`observe(world, seat)` reads only these inputs.

- The champion's own state, including the outcome of its last finished intent.
- Its teammates' state.
- Its team's current view.
- Its team's memory.
- Public facts: the game clock, tower destructions, champion kills and deaths, and each champion's level (Assumed to be public, as the scoreboard shows it).

Positions are encoded in the team's own frame, so that one policy can play both sides.

`legal_mask(observation)` takes the observation, not the world. A mask therefore cannot use anything that the observation lacks.

- `FIGHT` may be issued only against an enemy that is visible now. A `FIGHT` that is already running continues after the target leaves the view (section 7.1).
- `CAMP` is always legal. Walking to a camp that turns out to be empty is a legal mistake, and the intent ends with the outcome `ABSENT`.
- `WARD` needs a charge. `RECALL` needs a living champion. On the fountain it completes at once.
- The role rule of section 5.10 removes further actions from a laner's mask.

**Automatic execution has the same boundary.** The routine that carries out an intent reads enemy state only through the team's view and memory. The prototype found two places where this is easy to get wrong.

- Positioning for a `LANE` action must use the wave front that the team sees, not the lane's true front.
- A `FIGHT` order against a target that has entered fog walks to the last-seen position in team memory, never to the target's true position.

**Tested** in the kernel prototype (`experiments/m7/kernel/test_kernel.py`, results in `results/scenarios.json` under `q3_information`). The prototype measures sight by route distance (section 5.1).

- Two worlds were identical in everything the blue team had seen. They differed in the red jungler's position in fog (7,558 units apart) and in one red camp cleared unseen. Over 31 ticks, all 155 pairs of encoded blue observations and masks were byte-identical. After the red jungler entered blue vision in one world, all 5 blue observations differed.
- A last-seen record froze at the last visible tick while the enemy moved 7,140 units.
- The team that cleared a camp knew its respawn time at once. The other team learned it 10 s before the respawn for Gromp and 60 s before for the Blue Sentinel.
- A ward revealed a hidden enemy for exactly 90 s.
- A pursuer whose target entered fog walked to within its attack range (175 units) of the last-seen position, 16,353 units from the target's true position. Its intent ended with `LOST` one second after it arrived. Its path was identical with the target hidden in two different places.
- A target that reappeared before the pursuer arrived was fought again, and no outcome was recorded.

### 6.4 Wards

Basic wards belong to M8, as the owner decided. A `WARD` action walks to within 625 units of the target and places a Stealth Ward. The ward is a vision source of radius 900 for 90 to 120 s. A champion holds up to 2 charges and may have 3 wards on the map (Sourced). Wards cannot be seen or destroyed in M8. M11 adds ward clearing, Control Wards, and sweeping.

The kernel prototype put enemy wards in sight into the team's view. A Stealth Ward is invisible in the real game, so the M8 view leaves enemy wards out (C6).

## 7. Actions and timing

### 7.1 Action table

A policy returns one index into a fixed table.

| Kind | Target | End condition and outcome |
| --- | --- | --- |
| `KEEP` | none | Never. It leaves the current intent and its progress alone. |
| `HOLD` | none | Never. The champion stands and defends itself. |
| `MOVE` | A named map node | The champion arrives (`ARRIVED`). |
| `LANE` | A lane and one of five modes (section 5.6) | Never by itself. |
| `CAMP` | A camp or Scuttler | The camp dies while the champion stands at it (`CLEARED`), or the champion arrives and finds it empty (`ABSENT`). |
| `FIGHT` | An enemy champion that is visible when the action is issued | The target dies (`KILLED`). Or the champion reaches the target's last-seen position and the target is still out of the team's view (`LOST`). |
| `FOLLOW` | An allied champion | Never by itself. The champion stays near the ally and attacks what attacks it. |
| `SIEGE` | A lane | No enemy tower in that lane can take damage. |
| `WARD` | A ward spot | The ward is placed (`PLACED`). |
| `RECALL` | none | The channel completes (`RECALLED`) or is interrupted (`INTERRUPTED`). |

The table has about 95 entries.

**`FIGHT` and lost vision.** The first version contradicted itself. This table said that `FIGHT` ends when the target leaves the team's view, and section 6.3 said that the champion walks on to the last-seen position. The contract is now one rule in three parts.

1. While the target is in the team's view, the champion pursues and attacks the target's current position.
2. When the target leaves the view, the champion walks to the target's last-seen position, taken from team memory. If the target comes back into view on the way, the fight resumes and no outcome is recorded.
3. If the champion arrives within its attack range of the last-seen position and the target is still out of view, the intent ends with `LOST`. The champion then holds until its next decision, like after any completed intent.

Ending the intent at the moment vision is lost was the other option. It was not chosen, because `MOVE` targets named nodes only, so a policy could not order the walk to the place where the target vanished.

### 7.2 Persistence, completion, and replanning

- A champion holds one intent. The intent persists until it completes or a new action replaces it. This is the owner's rule.
- `KEEP`, or the same action again while the intent is running, keeps the intent and its progress.
- Any other action replaces the intent at once and discards its progress. A replaced intent records no outcome.
- When an intent completes, the kernel records its outcome and the tick in the champion's state. The champion then holds position and defends itself until its next decision, which is at most one decision interval away.
- `LANE`, `FOLLOW`, and `HOLD` do not complete by themselves.
- Outcomes are `ARRIVED`, `CLEARED`, `ABSENT`, `KILLED`, `LOST`, `PLACED`, `RECALLED`, `INTERRUPTED`, and `DIED`. The observation includes the last outcome, so a policy can tell an interrupted recall from a finished one.
- Policies decide on a fixed cadence, all champions on the same ticks. No event triggers a decision.

**Tested.** The first kernel prototype kept every order standing after its end condition, against this rule. A `CAMP` order attacked the camp again when it respawned, and a recall hit by damage started again by itself. The correction changed the prototype to follow the rule, and the tests now run against it (`experiments/m7/kernel/test_kernel.py`).

- `KEEP` and a repeated action leave progress alone. Any other action discards it.
- An intent that ends leaves the champion holding until it gets a new action.
- A recall hit by damage ends with `INTERRUPTED` and does not restart. The champion still stands in the same place 17 s later.
- The interval contract holds in the form that survives completion (section 5.2).

### 7.3 Interruption

| Action in progress | What interrupts it | What is lost |
| --- | --- | --- |
| `MOVE` | A new action | Nothing. The champion re-routes from where it stands. |
| `RECALL` | Damage, a stop effect, or a new action | All channel progress. Damage or a stop effect ends the intent with `INTERRUPTED`. A new action replaces it and records no outcome. |
| `CAMP` | A new action | Nothing at once. The camp keeps attacking inside its leash, then resets its health. |
| `FIGHT` | A new action | Nothing at once. Pursuers keep attacking while in range and in view. |
| Any | Death | The intent. The champion respawns with `HOLD`. |

### 7.4 Attack capacity

Each champion earns attack credit at its attack speed and spends it one hit at a time. Its intent decides the target class: minions for `LANE`, a champion for `FIGHT`, a camp for `CAMP`, a tower for `SIEGE`. One hit cannot go to two targets. A champion that trades while farming loses last hits, and a champion that farms under attack does not hit back unless its intent says so.

Movement and farming can coexist when they are compatible. A champion with a `LANE` action walks with the wave and keeps attacking.

## 8. Randomness and snapshots

### 8.1 Keyed randomness

**Decision.** Every random draw is a pure function `keyed_uniform(seed, stream, ids...)`. No generator object exists.

- The key names the event: a stream (such as minion targeting or last hits) and stable ids (lane, minion id, champion seat, tick).
- The same event draws the same number in every branch. An event that a changed action causes or moves draws a different number, and nothing else changes.
- A snapshot stores only the seed.
- A sampling policy takes its noise from the same function, keyed by seat and tick. A continuation policy whose observation did not change therefore picks the same action in both branches.

**Tested.** `tests/test_rng.py` checks determinism, independence from call order, key sensitivity, uniformity, and the absence of correlation between adjacent ticks.

Both design candidates chose this independently.

### 8.2 Snapshot contents

A snapshot holds everything needed to restore and replay a decision point.

- The ruleset id and the map id. Restoring into a different ruleset is an error.
- The seed and the tick.
- Every entity of section 5.3, including each champion's intent, phase, channel progress, and last outcome.
- Both teams' memory.
- The internal state of each policy that has any. A policy with memory must expose it. The scripted policies of M8 have none.

`world.digest()` is a hash of the full state. A restored world must produce the same digest at every later tick as the world it was taken from.

**Tested** in the kernel prototype (`results/scenarios.json` under `q4_snapshot` and `q4_snapshot_real_lane`).

- A world ran 300 ticks, was snapshotted, ran 300 more, was restored, and ran 300 again. All 300 digests matched, with both lane models.
- From one snapshot, only the blue top laner's action changed. The top lane differed at once. Every entity in the bot lane stayed identical for the whole 300 s window.
- A snapshot of the ten-champion world is about 17 KB. It takes 250 microseconds to take and 211 to restore.

**A lesson for M8.** The digest must hash values. The prototype's first digest depended on object identity and matched only 241 of 300 replayed ticks.

## 9. Evaluation

### 9.1 Manually specified scenarios

The initial evaluation input is a scenario file that a person writes. Automated ingestion stays deferred.

A full ten-champion state is too large to type. A scenario therefore starts from a generated base and overrides what matters.

```toml
ruleset = "ref-26.22-r1"
seed = 11
base = { policy = "scripted_v0", seed = 3, until_s = 420 }

[[champion]]
seat = "blue_top"
pos = { lane = "top", s = 9700 }
health = 0.55
gold = 870
intent = "LANE top last_hit"

[[lane]]
name = "top"
front_s = 9900
blue = { melee = 2, caster = 3 }
red = { melee = 3, caster = 6, siege = 1 }

[knowledge.blue]
red_jungle = { last_seen = "bot_river", at_s = 385, health = 0.9 }
red_gromp = "unknown"

[decision]
seat = "blue_top"
kind = "individual"
horizon_s = 120
rollouts = 32
hidden = "activity_v0"
continuation = { blue = "scripted_v0", red = "scripted_v0" }
alternatives = ["LANE top last_hit", "LANE top push", "RECALL"]

[[hypothesis]]
name = "jungler took gromp"
weight = 0.5
red_jungle = { activity = "clear", path = ["red_gromp"] }

[[hypothesis]]
name = "jungler walked top"
weight = 0.5
red_jungle = { activity = "move", to = "top_river" }
```

- `base` runs a scripted game to a clock time. Without it, the scenario starts from the game's opening state. Only the part of the base state that the deciding team can see or remembers is kept. The hidden part is discarded.
- Entity tables override what the deciding team can see: its own champions and anything in its view. A loader rejects a state that breaks an invariant, such as a minion past a living tower.
- `knowledge` states the deciding team's memory. This answers concern C3 of handoff 002. By default the memory is whatever the team would have seen in the base run. An override replaces a record, for example the place and time the enemy jungler was last seen.
- `[[hypothesis]]` blocks state what is hidden, with weights. Without any, the generator named in `hidden` supplies the hypotheses. A scenario holds no true value for a hidden field (section 9.3).
- `decision` names the deciding seat, the alternatives, the continuation policies, the horizon, and the hypothesis generator.

Scenarios are also the tool for the unusual and lopsided states of roadmap section 4. An author sets levels, gold, and upgrades directly.

### 9.2 Individual and coordinated alternatives

- An **individual alternative** changes one seat's action at the decision tick. Teammates do not cooperate automatically. They respond through their own policies and their own observations.
- A **coordinated alternative** changes the actions of several seats on one team at the decision tick. The report labels it as a team plan.
- Both kinds may hold the substituted action for a stated commit time. After that the seat's continuation policy decides again.
- The baseline alternative is the continuation policy's own choice.

### 9.3 Hidden state: hypotheses, not hindsight

A comparison must not use what the deciding team could not know.

The first version sampled only the positions of unseen enemies. It kept every other hidden field of the source state: health, gold, upgrades, camps. Its acceptance test asked that the deciding team's observations stay identical. The planning review objected on both counts, and the objection holds. A rollout that keeps the true unseen health and gold uses hindsight, and the observation test passes anyway, because those fields are not in the observation.

**Tested** in the kernel prototype (`experiments/m7/kernel/hindsight.py`, `results/scenarios.json` under `hindsight`). The decision belongs to the blue top laner at 240 s, with 55 percent health. It farms or retreats for 45 s. The red jungler was last seen 6 s earlier. Two source worlds, W1 and W2, differ only in what blue cannot see: the jungler's health (518 against 194), its gold and upgrades, one red camp, and red's memory of the blue jungler. Every blue observation and mask is identical between them.

| Method | Source world | Laner survives while farming | Laner's gold while farming | Same report for both worlds |
| --- | --- | --- | --- | --- |
| Positions only, the first version | W1 | 56 percent | 541 | No. 7 of 16 rollouts differ. |
| Positions only, the first version | W2 | 100 percent | 921 | |
| Truth-blind hypotheses | W1 and W2 | 31 percent | 435 | Yes |

- The first version's method passes the first version's acceptance test in every rollout world, and it still gives two different answers. The review's objection is confirmed for this prototype.
- The 7 rollouts are exactly those in which the sampled jungler stands within its gank reach of 3,000 units. In W2 the weakened jungler recalls and never ganks.
- The truth-blind number is not more accurate than the others. It is lower because its hypotheses also move the red top laner, which in truth stood on its fountain (Inference from four dumped hypotheses). The answer now depends on the generator, which the report states, and not on hidden truth, which it cannot state.
- The prototype's generator is a stand-in with three weighted beliefs for each enemy. It is not the `activity_v0` generator described below.

**Contract.**

1. **Information state.** The input of a comparison is what the deciding team knows at the decision tick: the full state of its own champions, its current view, its memory, and public facts. This is exactly what `observe` exposes to its five seats.
2. **Hypothesis.** Everything else is hidden. Each rollout runs in a full world made of the information state and one hypothesis. A hypothesis gives a value to every hidden field. The hidden fields are:
   - for each enemy champion out of view: position, health, mana, unspent gold, upgrades bought, XP within the band of its public level, intent and its progress, lockdown and attack state, and ward charges
   - enemy wards and their expiry
   - the state and timers of every camp the team has not seen, under the timer rule of section 3.3
   - minions and tower health in the parts of lanes that the team does not see
   - the enemy team's memory, including what it knows about the deciding team
3. **Truth-blind by signature.** The generator of hypotheses receives the information state and a rollout index, and nothing else: `hypothesis(info, rollout) -> hidden fields`. It never receives the source world. It cannot copy a value it should not know, in the same way that `legal_mask` cannot.
4. **Consistent by construction.** A hypothesis is generated as a history, not field by field. For each unseen enemy the generator picks one activity since the champion was last seen. Every hidden field of that champion, and everything it touched, follows from the activity, the last-seen record, and the elapsed time.
5. **Explicit hypotheses.** A scenario author may write hypotheses by hand, with weights (section 9.1). The loader fills what the author leaves out from the generator's default activity and applies the same checks. A scenario holds no true value for a hidden field. An author who knows what really happened, for example from a replay, enters it as a hypothesis named `actual`. The report shows it on a separate hindsight line and leaves it out of the comparison.

**Activities in M8 (Assumed).** The generator `activity_v0` has five activities.

| Activity | Who | What follows from it |
| --- | --- | --- |
| Stay | Anyone | Position near the last-seen position. Health regenerates. Gold grows by passive income. |
| Farm the home lane | Laners | Position at the wave front that the deciding team remembers. Gold and XP grow at a stated rate per second. |
| Clear camps on a path | Junglers | Position at the end of the path. Each camp on the path is cleared at its time, and the clearer has its gold and XP. |
| Recall and return | Anyone | Full health and mana. Upgrades bought with the gold. Position on the way back from the fountain. |
| Move unseen to a named place | Anyone | Position on the route there. Nothing else changes. |

Four checks reject a hypothesis, each with a named reason.

- The position is not reachable from the last-seen position in the elapsed time.
- The position is in the deciding team's view at the decision tick.
- The XP leaves the band of the champion's public level.
- A camp is cleared that no path in the hypothesis visits, or upgrades change without a visit to the fountain.

**What a comparison claims.** A report states the consequences of each alternative from one information state, under one generator with its weights, and under stated continuation policies. It is not an expectation over what the opponent was really doing. M8's weights are the author's, or the generator's stated defaults. They are not calibrated beliefs. The report therefore gives the consequences for each hypothesis as well as the weighted result, and it says when the ranking of the alternatives changes between hypotheses. "The answer depends on where the jungler was" is a result, and often the most useful one.

**Acceptance tests for M8 (C8).**

- **Truth-blind.** Take a source world. Change every field that is hidden from the deciding team. Run the comparison again. The hypotheses and the report are identical.
- **Consistent.** Every generated world passes the invariant checker, and the deciding team's observations and masks at the decision tick equal those of the information state. This is the first version's test. It stays as a necessary condition.
- **Rejection.** A hand-written hypothesis that breaks one of the four checks is rejected with its reason.

**Limits (Unresolved).**

- The activities are few and their weights are guesses. Real opponents are not drawn from this table. M11 replaces the generator behind the same signature.
- The view check covers the decision tick only. A hypothesis could pass through a place that the team watched 20 s earlier.
- The enemy's memory is rebuilt by a rule: the enemy knows what it sees at the decision tick, and public facts. What the enemy saw earlier is lost.
- The more that is hidden, the more a report says about the generator and the less about the decision. The report states how many enemy champions were hidden.

### 9.4 What a comparison reports

For each alternative and each rollout, the harness records consequences for the deciding champion and its team at the horizon.

- Gold earned, XP earned, level, and upgrades bought.
- Health and mana.
- Deaths, and seconds absent from the map (dead, recalling, or walking back).
- Minions killed and minions missed.
- Tower damage dealt and taken, plates, and towers lost.
- Camps taken by each team.
- Arrival times at named places, where the scenario asks for them.

The report gives paired differences against the baseline with their standard errors, for each hypothesis and weighted across them. It states the continuation policies, the hypothesis generator and its weights, the number of hidden enemy champions, the horizon, the ruleset, and the capability table.

The report does not combine the consequences into one score. When one alternative is at least as good on every consequence, the report says that it dominates. Otherwise the report says that the alternatives trade off. For decisions whose payoff lies beyond any horizon that M8 can measure, such as trading an objective, "no clear ranking" is the expected result and not a defect. This answers concern C2 of handoff 002.

### 9.5 Scenario requirements matrix

For each target decision, this table lists the information that an evaluation needs and where a scenario author could plausibly get it.

| Decision | Information needed at decision time | Plausible source for a manual scenario | Hidden from the decider |
| --- | --- | --- | --- |
| Freeze, slow push, or shove | Wave front position, minion counts by type on both sides, next wave timing, own and enemy laner health and level, tower health | The player's screen at that moment, or a replay paused at that time | Enemy jungler position, enemy cooldowns |
| Recall now or stay | Own gold against the next upgrade cost, health and mana, wave state, clock, travel time back | Screen. Upgrade costs come from the ruleset. | Enemy laner's gold, enemy jungler position |
| Jungler last seen botside | Where and when each enemy was last seen, own wave position, own ward coverage, clock | Minimap and memory of the player. A replay gives the exact last-seen time. | The enemy jungler's actual position and camps |
| Gank, clear, counterjungle, or move | Own camps' states and timers, last-seen enemy positions, each lane's wave state as seen, allies' health | Screen and minimap | Enemy camps cleared unseen, enemy wards |
| Side lane, group, or objective | Tower states, wave states in all lanes, positions of all visible champions, objective timers | Screen and scoreboard. Needs M10 objectives. | Enemy positions in fog |
| Strong bruiser against two | Levels, upgrades, and health of the three champions, distance to towers, nearby allies | Screen and scoreboard | Whether a third enemy is near |
| Contest dragon or trade | Objective timer, arrival times of both teams, wave states, tower health | Screen. Needs M10. | Enemy vision of the pit |
| Bot-lane allocation | Carry and support positions, support charges, wave state | Screen | Nothing material |
| Unusual and lopsided states | Levels, gold, and upgrades set far from typical values | The author sets them directly | As above |

Two facts limit what any future automatic ingestion could fill. Riot's match timeline has no minion-wave or camp state (handoff 001, C1, not rechecked). The first two rows therefore need a manual scenario or a replay parser, not the public API.

## 10. Plan for M8

### 10.1 Checkpoints

M8 has eight checkpoints. Each one ends with tests that pass and a short handoff note. Observation code starts at the first checkpoint, and each later checkpoint adds its own observation fields together with its own leak test.

| Id | Checkpoint | Builds | Acceptance criteria |
| --- | --- | --- | --- |
| C1 | Kernel base | World, tick loop, decision interval, champions on routes, action table, intents with outcomes, the role duty state, `observe` and `legal_mask` for own state and teammates, snapshot and digest, invariant checker | A run at decision interval n equals a run at interval 1 whose policy returns `KEEP` on the other ticks, for n of 2, 4, and 10, with orders that complete inside the run. A redirected move continues from the current position, and the distance walked equals speed times time. Restore and replay give equal digests at every tick for 1,000 ticks. Under a policy that always prefers a legal action away from its lane, no laner roams for longer than the cap plus one decision interval at a stretch, each laner's roaming share over 10 minutes stays within the bound of section 5.10, and no position changes by more than speed times the tick except on death and on recall. A soak of random legal actions runs 10 games with no invariant failure. The invariants are: health and mana within bounds, gold not negative, every position on a valid edge, a non-empty legal mask, a clock that only advances, and no action by a dead champion. |
| C2 | Lanes and economy | The wave experiments of section 5.6 on the M8 lane first, then the documented rules that M7 left out. Then `LaneSim` for all three lanes, towers against minions, the five wave modes with the in-path rule, gold and XP, bot-lane sharing, support item | The handoff reports the three wave experiments on the M8 lane with M7's pass tests unchanged, and each measurement of section 5.6 beside the simulator's value where someone has taken it. C2 does not require a freeze or a slow push to appear, and no rule is added to produce one. M8 tests re-assert on the M8 lane what the M7 wave tests cover: minion conservation, mirror symmetry, gold only for a champion's own killing blow, the XP split, and independence between lanes. First waves meet at the time that route length and minion speed give, within one tick, and within 5 percent of the measured real-game time once that exists. In bot lane each minion's gold is paid at most once, so the minion gold of carry and support together never exceeds the gold of the minions that died. The pair's XP is 1.3 times a solo laner's in the same lane state, within 2 percent, and neither gets more XP than the solo laner. The support item's gold is counted separately. It equals 3 per 10 s plus 18 per charge used, with at most one charge per 20 s. The pair's total gold exceeds a solo laner's by no more than that. An incentive screen reports the gold plus XP that a scripted laner earns in 5 minutes under each wave mode, over at least 10 lane states. The screen has no pass condition on which mode earns most. If one mode earns most in every state, the handoff traces the cause to named mechanics. The tick sweep of risk RK2 is reported. |
| C3 | Recall and purchases | Recall channel, fountain, Homeguard, upgrade progressions | A cancelled recall loses all progress. Unspent gold changes no capability. The round trip from an outer tower (recall, buy, walk back) takes the time that route length and speed give, within one tick. |
| C4 | Jungle | Camps, Scuttlers, shrine vision, camp timers in memory, a scripted jungler | Each first spawn falls on the ruleset's clock time, and each respawn falls on the camp's last death plus the ruleset's delay, to the tick. Timer knowledge follows the reference rule for seen and unseen clears. A clear takes the camp's health over the champion's camp damage rate, within one tick, and travel between camps takes route length over speed. The handoff reports the time and reward of each destination for the scripted jungler over a sweep of start positions and camp states. No destination is required to win. The handoff reports the scripted first-clear time. That time becomes a pass or fail criterion once a reference exists (question OQ8). |
| C5 | Combat and death | Per-tick fights, lockdown, tower against champions, death, respawn, kill rewards | Damage is monotone in capability. An ally's arrival tick equals route length over speed. A champion takes champion damage only on ticks when an attacker is within range by the straight line and sees it. A tower's damage on a champion follows the reference aggro and ramp rule to the tick. Permuting the seat order changes no outcome. `FIGHT` follows section 7.1: pursuit to the last-seen position, `LOST` on arrival, and no outcome when the target is seen again first. A dead champion returns at the fountain after the ruleset's timer. |
| C6 | Vision, memory, wards | Team view on the sight measure of section 5.1, memory, ward placement, timer rule, full observation encoding | The hidden-state test: randomize every field hidden from a team, and that team's observations and masks stay identical. The behaviour test: under the same randomization, that team's champions follow identical trajectories until something is revealed. The junction, open-ground, and wall cases of `tests/test_sight.py` hold for champions in a running game. A ranged attack reaches a target behind a wall only while the attacker's team sees it. An enemy Stealth Ward never appears in a team's view. Last-seen records freeze out of vision. A ward reveals and then expires. |
| C7 | Integrated game | All subsystems in one world, scripted policies for all ten seats, pinned replays, throughput gate | Scripted games of 20 game minutes run for 50 seeds with no invariant failure. Three pinned replays reproduce their digests. Every C1 to C6 test still passes. Throughput stays above the gate of section 10.4. In the event log of an integrated game, every wave spawn, camp spawn, camp respawn, and champion respawn falls on the tick that the ruleset gives. No minion moves past a living enemy tower. A champion that damages an enemy champion inside the range of that enemy's tower takes tower damage under the reference rule. After an outer tower falls, the enemy wave's furthest advance in that lane increases. As the roadmap's baseline check, a scripted team beats a random-action team on gold and XP at 15 minutes on at least 45 of 50 seeds. A sweep over tick lengths of 0.25, 0.5, and 1.0 s and decision intervals of 1, 2, and 5 s reports which scripted outcomes change, and the handoff confirms or revises the starting values of section 5.2. |
| C8 | Scenarios and harness | Scenario loader, hypothesis generator, comparison harness, saved scenarios | Saved scenarios load, restore, and replay exactly. The generator passes the three tests of section 9.3. A comparison rerun gives identical output. The harness reports the first four rows of section 9.5 under two scripted continuation styles and at least two hypotheses each, and the report states where rankings differ between styles and between hypotheses. |

C2, C3, C4, and C5 depend only on C1 and can overlap. C6 needs C2, C4, and C5. C7 needs all of them. C8 needs C7.

The M8 gate of the roadmap is met when C8 passes. C7 carries the roadmap's two clauses on timings that interact coherently and on towers that constrain waves and champions.

**Audit of the criteria.** The planning review asked for an audit of these criteria for contradictions, for tests shaped by one implementation, and for rules that force a strategic conclusion. Eleven criteria changed.

| Criterion in the first version | Problem | Now |
| --- | --- | --- |
| C2. A carry and support together earn no more minion gold than a solo laner, and each earns less. | Contradiction. The support item creates gold, and the carry can take every last hit a solo laner takes. | Three separate statements: minion gold is paid once, XP splits by the reference rule, and the item's gold is counted apart and bounded. |
| C2. Pushing does not earn more in every state. | Forced conclusion. A faithful lane in which pushing pays everywhere would fail. | The screen reports. A mode that wins everywhere is traced to mechanics, not forbidden. |
| C2. The handoff records the owner's choice on freezes, including one rule labelled approximate. | Forced conclusion. It offered a rule whose purpose was to make a behaviour appear. | Removed. No rule is added to produce a named behaviour. |
| C2. First waves meet within 5 percent of the measured times. | Could not be checked without a measurement. | Route arithmetic now, and the measurement once it exists. |
| C4. Camp choice changes with distance and camp state. | It tested the scripted jungler and asked for a result. | The kernel's clear and travel times are tested. The sweep reports. |
| C5. The same duel favours the defender under its tower. | Forced conclusion, on placeholder capability numbers. | Tower damage follows the reference rule to the tick. |
| C5. A retreat's outcome changes with speed and distance. | It could not fail. | Damage lands only while the attacker is in range and sees the target. |
| C5. The reinforcement threshold is monotone in distance. | It tested the outcome of a fight, which need not be monotone. | The arrival tick equals route length over speed. |
| C7. An enemy wave without champion support never passes a living tower. | It read as a claim about strategy. A large wave may destroy the tower. | Stated as the movement rule it is. |
| C8. The sampler keeps the deciding team's observations identical. | Not sufficient (section 9.3). | The truth-blind test is added, and the old test stays as a necessary condition. |
| C1 and C5 had no criterion for the role rule or for `FIGHT`. | Two contracts were untested. | Both have criteria. |

Two criteria rest on judgment and stay: the throughput gate of 300, and the count of 45 of 50 seeds for the scripted team. A failure of either is a reason to investigate, not proof of a defect.

### 10.2 The early learning pilot

**Placement.** The pilot runs after C7 and in parallel with C8. C7 is the first point at which ten champions play an integrated game with real opportunity costs. The pilot does not rerun after each later deliverable. An earlier pilot on lanes, recall, and combat alone was considered and not chosen. Without junglers and fog it would train on a different game, and its throughput would not carry over.

**Scope.**

- One shared policy with a role input, trained by self-play with PPO. The PPO core comes from the predecessor (section 10.5).
- Episodes are the first 14 game minutes. No game result exists before M10.
- The observation and action interface is exactly the one the scripted policies use.

**What it learns from.** The owner allows explicit experimental rewards for the pilot. The pilot's reward is the change in a team's total gold and XP minus the opposing team's change, plus a bonus for tower plates and towers, minus a penalty for deaths. It is zero-sum between teams and shared within a team. It is a training signal for the pilot only. It is not the evaluation output of section 9.4 and not the M12 reward. M7 does not fix the weights of the bonus and the penalty. The pilot's own plan sets them before the first run.

**Questions the pilot answers.**

1. What are the environment and learner throughput on this machine, end to end?
2. Does a learned policy beat the scripted baseline within an overnight budget? The measure is team gold plus XP at 14:00 against the scripted team, over 200 held-out seeds with sides swapped, and the bar is a higher total on at least 60 percent of them.
3. Which exploits does learning find in the game's incentives? The predecessor found its worst incentive bugs this way (handoff 001, F12).
4. Is the decision interval adequate, and is the action table usable?

**Not in the pilot.** Reward-shaping studies, attacker evaluations, recurrent policies, and any claim about strategy.

### 10.3 Hardware and compute budget

The machine was inspected on 2026-11-11 (Tested, by system query).

| Component | Value |
| --- | --- |
| CPU | Intel Core i5-11600K, 6 cores, 12 threads |
| Memory | 15.9 GB |
| GPU | NVIDIA GeForce RTX 3060, 12 GB |
| Python | 3.14.7 |

**Kernel throughput** (Tested, `experiments/m7/kernel/bench.py`, results in `results/bench_tick1.0_decision5.json` and `results/bench_tick0.5_decision2.json`). The load is a scripted 15-minute game with ten champions and the kernel prototype's lane model. Every run of one seed did identical work. At the starting values that is 1,073 minion deaths, 51 camp clears, 29 champion deaths, and 70 recalls.

| Setting | One process | 5 processes | 6 processes |
| --- | --- | --- | --- |
| 1.0 s tick, decision every 5 s | 1,239 simulated seconds per second (range 1,206 to 1,256, 7 runs) | not measured | 26,250 games per hour, 13,125 agent decisions per second |
| 0.5 s tick, decision every 2 s (the starting values) | 591 simulated seconds per second (578 to 605, 7 runs) | 10,637 games per hour, 13,296 agent decisions per second | 11,696 games per hour, 14,620 agent decisions per second |

- **What bounds it.** One CPython core per process. In the profile, lanes take 50 percent of the time and vision 25 percent. Twelve processes gave 5.44 times one process against 5.24 times for six, so the six physical cores are the limit and hyperthreads add little.
- **What it leaves out.** No policy network ran. The policy was a scripted function. The prototype lacks rules that M8 adds: inner and inhibitor towers, minion damage to champions, and the support item's charges. Its lane is the first-round lane model, and it measures sight by route distance, so the cost of `sees` is not in these numbers (section 5.1).
- Building and encoding one observation with its mask takes 53 microseconds.
- **Background load moves the one-process figure.** The run at the starting values began at 11 percent CPU load, and the run at a 1.0 s tick at 25 percent. Another program of the owner's runs on this machine. Four runs at the starting values on this day gave 634, 626, 540, and 591 simulated seconds per second, at 24, 5, 34, and 11 percent load. Only the last is in the results file. The other three are Reported.
- The first of those four is the first version's figure, from before intents ended on completion. The spread between runs is larger than any effect of that change.

**Learner throughput** (Tested, `experiments/m7/bench_learner.py`, results in `experiments/m7/results/learner.json`). The network is the predecessor's shape scaled up: two hidden layers of 256 units, 256 inputs, 64 actions. The prototype's observation and action table are of the same order, and the difference does not matter at this size. CPU only, 7 runs each.

| Operation | 1 thread | 6 threads |
| --- | --- | --- |
| Inference, batch of 10 (one decision point) | 44,132 decisions per second | 40,518 |
| Inference, batch of 640 | 203,672 | 392,270 |
| PPO update, minibatch of 2,048 | 130,109 transitions per second | 326,236 |

The GPU was not measured. `torch` with CUDA is not installed, and at this network size the CPU numbers already exceed the kernel's output.

**What bounds an overnight run.** This is derived from the two tables. It is not measured end to end, and no training loop has run.

- Five worker processes produce about 13,300 agent decisions per second with a scripted policy.
- Inference on one thread inside each worker adds about 0.23 ms to a decision point that costs about 3.4 ms to simulate, so about 7 percent.
- Four PPO epochs at 130,000 transitions per second let one learner thread absorb about 33,000 new decisions per second.
- The kernel is therefore the limit, at roughly 12,000 agent decisions per second, if the learner runs beside the workers. A loop that alternates collection and updates, as the predecessor's did, gives about 8,600.

**Budget for the pilot.**

| Item | Value |
| --- | --- |
| One run | At most 10 hours of wall time, overnight |
| Processes | 5 environment workers and 1 learner, CPU only at first |
| Expected volume per run | 150 to 400 million agent decisions, or 35,000 to 95,000 episodes of 14 game minutes (Derived). The top assumes the prototype's rate and a learner that runs beside the workers. The bottom assumes the C7 gate rate and a learner that alternates with them. |
| For scale | The predecessor's main runs used 32.8 million transitions each (Reported) |
| Whole pilot | One 30-minute smoke run, then at most three overnight runs |
| Approval | Each overnight run needs the owner's go-ahead, behind a confirm flag |

The pilot's first task is to replace the derived figure with a measured one.

### 10.4 Throughput gate

The M7 prototype sets the reference: 591 simulated seconds per wall second on one process at the starting clock values, with scripted policies.

- **Gate at C7.** The integrated M8 kernel reaches at least 300 simulated seconds per wall second on one process, measured with the same benchmark method (7 runs, median and range, work counts checked). That is about half the prototype's rate and leaves room for the rules the prototype lacks. At 300, five workers still give about 200 million agent decisions in 10 hours.
- **Below the gate.** Profile first. Move the lane loop, then the vision loop, to arrays or compiled code before the pilot starts.
- **Between checkpoints.** A checkpoint that lowers the benchmark by more than 20 percent explains why in its handoff.

### 10.5 Audit plan for the laning project

The predecessor stays untouched and is never imported by `riftgame`. It was inspected at commit `dbea191c`.

| Component | Plan | When | Check |
| --- | --- | --- | --- |
| Natural-wave kernel (`engine/mechanics.py`) | Do not port the code. It uses 9 integer cells and 2 ticks per turn, which cannot map onto route coordinates and seconds. Use it as a source of properties. | C2 | Property tests: a neutral lane stays put, conservation, mirror symmetry, a wave bounces after a crash |
| Wave lessons (`docs/archive/history.md`) | Read the rejected rules before changing any wave rule. Keep the predecessor's test for a new mechanic: it must not exist only to produce a named outcome. | C2 | Review step in the C2 handoff |
| Economy lessons (`docs/findings.md`) | Rebuild the incentive screen that exposed Shove dominance. | C2 | The screen of C2's acceptance criteria |
| `diagnostics/branch.py`, `lane_exit.py` | Rewrite against the new world. Keep the semantics: commit plans, policy plans, paired rollouts, a readout that is a vector. | C8 | Paired-rollout test |
| `rl/ppo.py`, masked categorical, checkpoint digests | Port nearly unchanged. | Pilot | The predecessor's reference test, ported |
| `exact/matrix_game.py` | Port only if a small exact arena is built. | M11 or M13 | None yet |
| Test patterns (`tests/test_invariants.py` and others) | Port the patterns, not the files: conservation, mirror equivariance, replay exactness, random soaks with an invariant checker, digest pins. | Each checkpoint | Listed in section 10.1 |
| Process | Keep confirm flags on expensive runs, and keep results apart from run outputs. | Pilot | None |
| Resolvers, action codes, observation encoders, gank probability, config chain | Do not port. | Never | None |

**Departure from handoff 001.** Handoff 001 proposed differential tests in which the new lane reproduces the old lane's trajectories. Continuous coordinates make that impossible. The audit uses property-level agreement instead.

## 11. Validation plan, risks, and open questions

### 11.1 Where each scenario and check is first tested

| Roadmap section 4 scenario | First tested | Later |
| --- | --- | --- |
| Freeze, slow push, or shove | C2 as mechanics, C8 as a comparison | M9 for sensitivity to capability |
| Recall now or stay | C8 | M9 for purchase thresholds |
| Jungler last seen botside | C8 with the hypothesis generator | M11 |
| Gank, clear, counterjungle, or move | C4 as a sweep, C8 as a comparison | M9, M11 |
| Side lane, group, or objective | M10 | M13 |
| Strong bruiser against two | M9 | M13 |
| Contest dragon or trade | M10 | M13 |
| Bot-lane resource allocation | C2 | M9 |
| Unusual and lopsided states | C8, through the scenario format | M12, M13 |

| Roadmap section 7 check | First tested | Later |
| --- | --- | --- |
| Rules tests | C1 | Every checkpoint |
| Snapshot, replay, anti-leakage | C1 (snapshot), C6 (leakage), C8 (truth-blind test) | M11 |
| Component sweeps | C2 (waves), C4 (jungle) | M9 (combat) |
| Integrated scenarios | C8 | M10 |
| Baseline comparison | C7 (scripted against random) | M10, M12 |
| Exploitability | M12 | M13 |
| Ranking sensitivity | C8 (continuation style, hidden state, horizon) | M9 (combat), M13 |
| Learning diagnostics | Pilot (held-out seeds only) | M12 |
| External calibration | C2 and C4 (clocks and travel times against the reference) | M9, M13 |
| Evaluator safety | C8 (the "no clear ranking" output) | M13 |

**Reproducibility.** Each checkpoint pins three replays by digest. A change that alters a pinned digest must either be a bug fix or carry a new ruleset id. Benchmarks record run count, range, and the limiter.

### 11.2 Risks

Risks are ordered by how much they could change the plan.

| Id | Risk | Evidence so far | What reduces it |
| --- | --- | --- | --- |
| RK1 | Freezes and slow pushes do not emerge from the wave rules, against the owner decision. | Tested, three rounds (section 5.6). With a mortal champion, no thinning plan brings more than 4 minions to the tower against a test of 12, and no holding plan passes the freeze test. An even fight ends in 25.5 s against a wave interval of 30 s. | C2's first task: the same experiments on the M8 lane, the four documented rules that M7 left out, and the measurements of section 5.6 if someone takes them. No rule is added to force either behaviour. |
| RK2 | Wave outcomes are sensitive to tie-breaks and, less than first reported, to the tick. | Tested (`waves.json`, `S7b_tick_sensitivity`). At a 0.5 s tick, 15 of 17 metrics are within 10 percent of a 0.125 s reference. A lane that is one caster short still swings from tower to tower. | A 0.5 s tick as the starting value. C2 repeats the sweep on the M8 lane and reports every metric that moves more than 10 percent. |
| RK3 | The jungle graph is an assumption. Which camps connect, and the 1.15 detour factor, set every jungle travel time. No source gives a full-clear time on the 2026 clock. | Assumed. Lane distances are tested, jungle distances are not. | C4 reports the scripted first-clear time. The owner or the planning assistant supplies one trusted clear time, or measures one in a custom game. |
| RK4 | Chases on a one-dimensional route are close to binary in the sign of the speed difference, and fights without a fight object may not calibrate. | Tested: a runner 20 units faster escaped in all 6 of its cases. | M9 tests candidate B's attack windup and dash rules first. If a strong champion's 1v2 cannot be made to follow from capability and `damage` alone, M9 adds an engagement entity. |
| RK5 | Sight terrain is constructed, not read from the game. A jungle path beside a lane is open to it, there is no brush, and a lane has no width. | Tested geometry (`tests/test_sight.py`). Assumed terrain (section 5.1). | M11 owns brush and ward clearing. The fix that keeps the design is to build `sight_clear` from the game's navigation grid. |
| RK6 | The reference rules that M8 omits change incentives. Without bounties a lead compounds faster. Without the early off-lane penalties a roam is cheaper than in the real game. | Sourced rules, omitted on purpose (section 3.4). | Each omission is listed. M9 and M10 decide which return. The pilot report names any exploit that an omitted rule would have blocked. |
| RK7 | The learner, not the kernel, may bound the pilot. Or the kernel may, once a policy network adds its cost to every decision. | Section 10.3. | The pilot's first task is an end-to-end throughput measurement. Lanes and vision are the two loops to move to arrays or compiled code. |
| RK8 | Comparisons depend on continuation policies, and M8's scripted policies are weak. Many comparisons will report no clear ranking or a ranking that flips with the style. | Reported from the predecessor (handoff 001, F11, F16). | C8 reports every comparison under two scripted styles and states where they disagree. M12 adds learned continuations. |
| RK9 | The hypothesis generator has five activities with guessed weights. Real opponents are not drawn from it. | Assumed (section 9.3). | Every report gives results for each hypothesis and says when the ranking depends on one. The scenario format accepts explicit hypotheses. M11 replaces the generator. |
| RK10 | Many `F1` values were read through a tool that summarizes pages. A wrong constant would pass every test. | Sourced, single page. | C2 and C4 spot-check each `F1` value they use against the page, and promote it to `F2` or correct it. |
| RK11 | M8 is large: eight checkpoints before the roadmap gate. | Inference. The two M7 prototypes are about 3,000 lines and cover each subsystem only thinly. | Each checkpoint has its own acceptance tests and handoff. C2 to C5 can overlap. |
| RK12 | The first prototype's timing evidence used orders that never end. | Resolved in the correction. The prototype ends intents on completion, and the interval contract holds in its `KEEP` form (section 5.2). | C1 repeats the test on M8 code. |
| RK13 | The pilot reward pays for gold and XP. A policy may learn to farm and never fight. | Inference. | That is one of the exploits the pilot exists to find. The pilot report states it. The reward is not reused for M12 without review. |
| RK14 | Writing scenarios by hand may be too slow to be useful, even with a generated base. | Assumed. | C8 records the time taken to write the first four scenarios. |
| RK15 | The role bound of section 5.10 (a 90 s cap and a refill of 0.25) is untested against learned behaviour, and a laner with no allowance cannot fight outside its lane. | Assumed constants. The mechanism is tested in the prototype. | The pilot reports how often laners reach the bound and whether opponents exploit it. |
| RK16 | A lane has no width, so the in-path rule of section 5.6 decides when minions may attack a champion. The rule is an assumption. | Assumed. Found in the round 3 wave tests. | The fourth measurement of section 5.6. C2 implements the rule and the `hold` mode and reports what a learned or scripted laner does with them. |
| RK17 | `sees` costs about ten times `distance` for a pair inside the sight radius, and the M7 throughput was measured without it. | One rough measurement (section 5.1). | The gate at C7. A table by edge pair is the first optimization. |

### 11.3 Open questions

**Resolved by the owner on 2026-11-11, after the planning review.**

- **OQ1. Camp respawns** follow real League: a respawn counts from the camp's last death (section 3.3).
- **OQ2. Starting clock.** A 0.5 s tick and a 2 s decision interval are acceptable starting values. They are not validated constants, and C7 tests them.
- **OQ5. Names and layout.** The package name `riftgame` and the organized prototypes under `experiments/m7/` are accepted as working choices.
- **OQ6. Mana.** One simple mana pool per champion is accepted as a working choice.
- **OQ10. Lane towers.** Three tiers per lane and team are accepted as a working choice.

**Resolved in this revision.**

- **OQ3. Lane assignment rule.** Replaced by the duty state of section 5.10. Its two constants stay open under risk RK15.

**Still open.** The owner has said that routine technical choices need no further questionnaire, so these go to the planning assistant unless it passes one on.

- **OQ4. Omitted reference rules.** Which rules of section 3.4 must return before the pilot, if any? Unit collision and the pushing advantage now move into C2 through section 5.6.
- **OQ7. Public information.** The design treats enemy level as public and enemy upgrades and health as last seen. The real scoreboard rules were not researched. The answer changes the hypothesis checks of section 9.3.
- **OQ8. Jungle clear time.** Risk RK3 needs one trusted number.
- **OQ9. Support item tiers.** M8 keeps the support item at its first tier. Decide whether the 400-gold upgrade matters for bot-lane decisions.
- **OQ11. The `hold` wave mode and the in-path rule.** Both are new and assumed (section 5.6). Confirm them, or name another way for a champion to stand in a wave's path.
- **OQ12. Wave measurements.** Someone has to take the six measurements of section 5.6 in a custom game on the reference patch. The implementing assistant cannot.

## 12. Where the contracts came from

M7 compared two independent designs before it fixed the contracts. Candidate A came from the session that wrote this document. Candidate B came from a second Claude model that saw the roadmap and the owner decisions but not candidate A. Both read the same owner decisions, which already fix much of the design, so their agreement is weak evidence.

Neither candidate text is in the repository. They were session files. This section therefore keeps only the decisions whose evidence is in the repository. What it says about a candidate's content is Reported.

| Fork | Decision | Evidence in the repository |
| --- | --- | --- |
| State layout: one object per entity, or arrays with a leading game axis | Objects for M8 | The object kernel's measured rate (section 10.3) |
| Parallelism: one process per core, or one batched process | Processes | The scaling rows of section 10.3 |
| Position: a continuous offset along an edge, or stations every 50 units | Continuous for M8 | `riftgame/map.py` and its tests |
| Tick and decision interval | 0.5 s and 2 s as starting values | Section 5.2 |
| Intent end | End on completion, record an outcome, then hold | Section 7.2 |

**Why objects.** M8 will change rules often. The predecessor rejected about 40 wave rules before its lane behaved (handoff 001, F12), and M7 needed three rounds of wave tests (section 5.6). Rules written as plain per-entity code are quick to change and to test. M8 keeps the option of arrays open. It gives every entity a fixed seat or slot id and keeps the state flat, so the two hottest loops, lanes and vision, can move to arrays or compiled code without a redesign.

**Left for M9.** An attack windup that costs the attacker movement, a separate spell resource with a hit roll, and dashes. These were candidate B's answer to chases that are binary in speed (risk RK4).

## 13. How to rerun the evidence

Set up once, from the repository root.

```
uv venv .venv --python 3.14
uv pip install --python .venv/Scripts/python.exe numpy pytest
```

Every command below starts with `.venv/Scripts/python.exe`.

| Command | What it shows | What it writes |
| --- | --- | --- |
| `-m pytest -q` | Every test: ruleset tags, map lengths, sight, keyed randomness, wave behaviour, kernel contracts, roles, hindsight | Nothing |
| `-m experiments.m7.waves.scenarios` | The wave cases of section 5.6. Takes about 2.5 minutes. | `experiments/m7/waves/results/waves.json` |
| `-m experiments.m7.waves.diagnose "S5c k=3 hold" "A+B" 0 0.5 50` | A tick-by-tick trace of one wave case | Nothing |
| `-m experiments.m7.kernel.scenarios` | Timing, fight, information, snapshot, role, and hindsight results | `experiments/m7/kernel/results/scenarios.json` |
| `-m experiments.m7.kernel.bench` | Kernel throughput and process scaling at a 1.0 s tick with 5 s decisions. Wants an idle machine. | `experiments/m7/kernel/results/bench_tick1.0_decision5.json` |
| `-m experiments.m7.kernel.bench start` | The same at the starting clock values. This is the source of the gate in section 10.4. | `experiments/m7/kernel/results/bench_tick0.5_decision2.json` |
| `-m experiments.m7.bench_learner` | Learner throughput. Needs `torch` (`uv pip install torch --index-url https://download.pytorch.org/whl/cpu`). | `experiments/m7/results/learner.json` |
| `-m experiments.m7.provenance` | Whether each results file still matches the code in the working tree | Nothing |

**Provenance.** Each results file holds the output of one invocation and a `run` block. The block records the command, the UTC time, the git head, whether the tree had uncommitted changes, the seeds, the configuration, the Python and package versions, and a content hash of every source file that the run loaded. A short code id summarizes those hashes. The checker recomputes the hashes and reports a file as `STALE` when a recorded source has changed since the run.

The runs behind this version were made on an uncommitted tree on top of commit `8108294`. The content hashes, not the commit, identify their code.

| Results file | Code id | Run at (UTC) | Seeds |
| --- | --- | --- | --- |
| `experiments/m7/waves/results/waves.json` | `8474bf3fd115e0c3` | 2026-11-11 18:47:42 | 0 to 4 |
| `experiments/m7/kernel/results/scenarios.json` | `44ed41ff46723432` | 2026-11-11 18:48:16 | 0 to 15 |
| `experiments/m7/kernel/results/bench_tick0.5_decision2.json` | `4bb490c2863edf55` | 2026-11-11 18:55:20 | 0 |
| `experiments/m7/kernel/results/bench_tick1.0_decision5.json` | `4bb490c2863edf55` | 2026-11-11 18:51:39 | 0 |
| `experiments/m7/results/learner.json` | `adbf658da63741f3` | 2026-11-11 18:53:07 | 0 |

**What has no surviving evidence.** These items were in the first version, or came up during the correction. Each is now removed or labelled Reported.

- The first-round wave results. The second round overwrote them.
- The cost and accuracy figures of the cohort lane variant. They were never written to a file.
- The two design candidate texts of section 12. They were session files.
- The four mutation runs of the sight tests, and one intermediate wave run (sections 5.1 and 5.6).
- Three of the four throughput runs of section 10.3. Each rerun overwrote the file.
- The first version's `kernel.json`. It merged several runs without metadata. Every number that this document keeps from it has been rerun.

**Reusable code and prototype code.** `riftgame/` holds what M8 builds on: the ruleset loader and files, the route-graph map with its three measures, and keyed randomness. `tests/` covers it. Everything under `experiments/m7/` is prototype code that exists to answer M7's questions. M8 rewrites it against the contracts in this document and does not import it.
