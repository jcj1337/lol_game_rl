# M7 architecture and research specification

**Status.** Complete, waiting for review. Nothing here is approved until the owner and the planning assistant review it.

**Date.** 2026-11-11.

**Answers.** [ROADMAP v0.2](../ROADMAP.md), milestone M7, plus the owner decisions of 2026-11-11 on map, timing, waves, recalls, combat, roles, information, camps, scope, and compute.

**Reference patch.** League of Legends 26.22, Summoner's Rift.

**Evidence labels.** Each claim in this document carries one of three labels.

- **Tested** means that a test or script in this repository shows it. The claim names the file.
- **Sourced** means that it comes from the reference patch research. The ruleset file tags each value `F2` (read on two pages), `F1` (read on one page), `D` (derived), or `M` (from memory).
- **Assumed** means that it is a design choice or a placeholder number. Nothing has checked it yet.

## 1. Summary

M7 fixes the contracts that M8 builds on and tests the claims that were least certain.

**Contracts fixed.**

- Space is a route graph built from the game's own map file. A position is a distance along a route (section 5.1).
- Time is a fixed tick with a separate decision interval. M8 starts from a 0.5 s tick and a decision every 2 s (section 5.2).
- An action sets an intent that persists until it completes or is replaced. Routine execution is automatic. Attacks compete for one capacity (section 7).
- Fights have no fight object. They unfold over ticks from range, speed, lockdown, and towers (section 5.9).
- A policy sees only its observation, and masks are built from the observation alone (section 6).
- Randomness is keyed and stateless. A snapshot restores and replays exactly (section 8).
- Scenarios are written by hand over a generated base. A comparison reports each consequence separately (section 9).

**Tested in M7.** 77 tests pass. The map agrees with independent distances within 3 percent. Fog with no leak into observations, exact snapshot replay, and paired randomness hold in a ten-champion prototype. Its timing test used orders that never end, so C1 retests the timing contract (section 7.2). The prototype runs 634 simulated seconds per wall second on one process at the starting clock values.

**Not shown.** The owner decided that freezes and slow pushes emerge. Two rounds of wave tests support less than that. At the 0.5 s tick a freeze-like hold appears, but only with a large enemy surplus, under an assumed standing rule, and at a health cost no champion could pay. No stacked wave appeared, and the scenario built to test one was flawed. Section 5.6 explains it, and M8's checkpoint C2 starts with it.

**One conflict of fact.** Camp respawns count from the camp's last death, not from a fixed clock (section 3.3).

**Plan for M8.** Eight checkpoints with acceptance criteria. The learning pilot runs after the integrated-game checkpoint C7, in overnight runs of at most 10 hours on the inspected machine (section 10).

**What this document does not establish.** Capability numbers are placeholders until M9. The jungle's path graph is an assumption. The prototypes under `experiments/m7/` are evidence, not M8 code.

## 2. Phases and results

M7 ran as eight phases. Each phase ended in a check.

| Phase | Question | Check | Result |
| --- | --- | --- | --- |
| P0 Ground | What do the roadmap, the handoffs, and the predecessor fix, and what hardware is there? | Sources read. Hardware queried. | Done. Section 10.3 lists the machine. |
| P1 Reference patch | What are the real clocks, rewards, and ranges? | Every ruleset value has a source status. A test enforces it. | Done. Patch 26.22. One conflict and six gaps (section 3). |
| P2 Contracts | What are the state, action, observation, and timing contracts? | Two independent designs compared. | Done. Section 12 records the synthesis. |
| P3 Map | Do route lengths give the right travel times? | Graph distances against an independent derivation. | Verified within 3 percent (section 5.1). |
| P4 Waves | Do freezes and slow pushes emerge from mechanics? | Scenario runs over 5 seeds, two rounds, with a tick sweep. | Partly. Timing, economy, and capacity work. A hold appears under an assumed rule. No stacked wave (section 5.6). |
| P5 Kernel | Do the timing, fight, information, and snapshot contracts hold in code? | A ten-champion prototype with 17 tests. | Information and snapshots verified. Timing and fights carry caveats (sections 7.2 and 5.9). |
| P6 Compute | What can this machine run overnight? | Benchmarks with run counts, ranges, and limiters. | Measured. Budget in section 10.3. |
| P7 Plan | How is M8 divided, and where does the pilot go? | Each checkpoint has acceptance criteria. | Done. Section 10. |
| P8 Review | Does the trail hold up? | Handoff 003 and an independent review on a different model. | The review found 3 defects and 11 items to fix. This document includes the corrections. Handoff 003 lists them. |

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

### 3.3 Conflicts with the owner decisions

**Camp respawns.** The owner decision says "Spawns follow the game clock, not completion of a jungler's clear." The reference agrees for first spawns. Every camp first appears at a fixed clock time, whatever any jungler does. A respawn is different. The wiki's Monster page says that the respawn timer "does not start until all monsters in the camp are dead" (F1). The respawn time is therefore the game time of the camp's last death plus the delay. This design follows the reference for both. If the decision meant that respawns should ignore clears, that conflicts with the reference, and the owner should say which one wins.

**Timer visibility.** The reference gives a team a camp's respawn timer in two cases (F2). The team saw the clear. Or the team sees the camp's location in the last 60 s before the respawn for a buff camp, or the last 10 s for another camp. The design copies this rule, because it is what keeps an unseen counterjungle hidden.

**The 14:00 boundary.** In 26.22, tower plates no longer fall at 14:00 (F2). The wave interval, the siege cadence, and the Homeguard rule do change at 14:00. This design uses 14:00 only where the reference does.

### 3.4 Reference rules that M8 leaves out

M8 omits these rules of the reference patch. Each is a stated simplification, and section 11 lists the ones that carry risk.

- Role quests, including the level cap of 20 and the early off-lane penalties for mid and support.
- Bounties, shutdowns, and the assist-gold timing rules.
- The minion "pushing advantage" bonus that depends on team level difference.
- The side-lane speed boost for minions, and minion speed growth after 10:00.
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
4. **Counterfactual comparison.** The harness restores a snapshot, substitutes one action (or one team plan), samples the hidden state the deciding team could not know, and runs paired continuations under stated policies. It reports each consequence separately.

## 5. World model

### 5.1 Space is a route graph

**Decision.** The map is a graph of 39 named nodes and 56 straight edges. A position is `Pos(edge, offset)`, a distance along one edge. Every range in the rules is a route distance in League units, so champions, waves, towers, and vision share one coordinate system.

- Each lane is a chain of nodes taken from the game's own minion path waypoints. A lane has a lane coordinate `s`, the distance from its blue end. Waves live on `s`. Towers sit at the projection of their real coordinates onto the lane.
- Each of the four jungle quadrants has three camp nodes at the real camp coordinates. Two river nodes sit at the two Scuttler positions.
- Jungle and river edges join camps to each other, to lane nodes, and to the river. Which nodes are joined, and a detour factor of 1.15 on those edges, are Assumed. The map file gives positions but no walkable-path graph.

**Tested.** `tests/test_map.py` checks the graph against a second derivation from the same map file (spawn point, barracks, and the full minion path polyline). It is a consistency check on the graph's down-sampling. It does not measure travel time in the real game. The test tolerance is 4 percent.

| Quantity | Route graph | Second derivation | Difference |
| --- | --- | --- | --- |
| Blue fountain to blue top outer tower | 10,450 | 10,184 | +2.6 percent |
| Blue fountain to blue mid outer tower | 8,061 | 8,095 | -0.4 percent |
| Blue fountain to blue bot outer tower | 10,639 | 10,333 | +3.0 percent |
| Fountain to fountain through mid | 19,762 | 19,791 | -0.1 percent |

At a move speed of 335 the walk from the fountain to an outer tower is about 31 s in a side lane and 24 s in mid, before Homeguard.

**Limits.** Route distance treats every wall as opaque and every open area as a corridor. Two champions on parallel paths do not see each other, and a lane has no width. Section 11 lists this as a risk for vision and for escapes.

### 5.2 Time is a fixed tick with a separate decision interval

**Decision.** The simulation advances in fixed ticks of `tick_s` seconds. Policies decide every `decision_ticks` ticks. Both are configuration values. M8 starts from `tick_s = 0.5` and `decision_ticks = 4`, so a champion decides every 2 s.

**Why 0.5 s.** Durations round up to whole ticks. At a 1.0 s tick the 8.5 s recall takes 9.0 s, and at 0.5 s it takes 8.5 s (Tested, `experiments/m7/kernel/results/kernel.json`, `q1_timing`). Tower shots (1.2 s apart), lockdown durations, and the 3 to 4 s between seeing a ganker and contact are all a small number of seconds, so a 1.0 s tick is a coarse unit for them. Wave results move with the tick too. With both laners last-hitting, creep score is 0.90 at ticks of 0.25 and 0.5 s and 0.80 at 1.0 s. One hold lasts 222, 106, and 46 s at ticks of 0.25, 0.5, and 1.0 s (section 5.6). So 0.5 s is not converged for holds either. The 0.5 s tick costs 41 percent of simulated seconds per wall second in the prototype (780 against 1,328 on one process).

**Why 2 s.** This rests on arithmetic, not on a test. A champion sees an approaching enemy at 1350 units. At a closing speed near 350 that leaves under 4 s before contact. A 5 s interval can pass without one decision in that window, so a gank could succeed because of the interval and not because of the map. The second design candidate raised this argument (section 12). The prototype's gank scenario does not test it. That scenario varies only the laner's reaction, and only by one second.

**Tested.** The decision interval changes when policies may choose, not what an order does. With orders that did not end inside the window, trajectories were identical at decision intervals of 1, 5, and 10 ticks for 300 ticks, with both lane models. The prototype got there with orders that never end, which is not the contract of section 7.2. Section 7.2 explains the difference and how C1 retests it.

**Not yet tested.** The pair (0.5 s, 2 s) is a starting point, not a calibrated choice. C7 runs a sweep over tick lengths 0.25, 0.5, and 1.0 s and decision intervals 1, 2, and 5 s before the pilot (section 10.1).

One tick runs these steps in this order. The order is part of the contract, because pinned replays depend on it.

1. Apply the actions that policies submitted for this tick (decision ticks only).
2. Spawn on the game clock: waves, camps, Scuttlers, champion respawns.
3. Move. Champions that are not pursuing move first. Pursuers then move against the positions that their targets held before this step.
4. Collect every attack of this tick from the state at the start of the tick: minions, towers, camps, and champions.
5. Apply all damage at once. Then resolve deaths, gold, XP, and level-ups.
6. Advance channels, record intent outcomes, and apply fountain regeneration and purchases.
7. Update each team's view and memory.
8. Advance the clock.

Steps 3 to 5 are meant to make the result independent of the order in which the code visits champions. The prototype's author reported that pursuers moving in seat order biased fights, and added this rule. No test permutes the seats yet. C5 adds one.

Policies read the view of step 7, so a policy always acts on what its team saw at the end of the previous tick. Automatic execution obeys the same limit (section 6.3).

### 5.3 State contract

The world owns every mutable fact. There is no state anywhere else, and no random generator state.

| Entity | Fields |
| --- | --- |
| World | Ruleset id, map id, seed, tick, and the entities below |
| Champion (10) | Seat, team, role, profile, home lane, position, health, mana, XP, unspent gold, upgrades bought, intent, intent phase, tick the intent started, channel progress, outcome of the last finished intent, attack credit, slow end tick, respawn tick, ward charges, support-item charges, tallies |
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

**Until M9.** M8 uses five placeholder profiles in one table (Assumed). The numbers only need to be distinct and plausible. M9 replaces the table and the damage function behind the same two interfaces, `capability(profile, level, upgrades)` and `damage(raw, target)`. All ten champions use the same execution competence. No skill parameter exists yet.

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
- A hit deals attack damage plus a share of the target's current health.
- With no enemy minion in range, a minion attacks the closest enemy champion in range, at 60 percent damage.
- Towers act as in section 5.7.

A cheaper variant that pools each wave's minions into cohorts was built in the first round and not chosen. It cost roughly a third as much per lane tick, but it cannot express a per-minion rule such as champion aggro. Its numbers are no longer in a results file.

**Tested, two rounds** (`experiments/m7/waves/`, results in `results/waves.json`). The first round used my first specification, in which minions ignored champions and had no lateral slots. It failed on freezes, slow pushes, and lane stability. The second round first traced why. It then added one documented rule, champion aggro, and one assumption, lateral slots. Lateral slots were added after the first round failed. They therefore need the same scrutiny as any rule that might exist only to produce an outcome.

Every number below is at the 0.5 s tick that M8 starts from, over 5 seeds. A range in brackets is the minimum and maximum across seeds. `waves.json` holds these cases, and its `S7b_tick_sensitivity` block compares ticks of 0.25, 0.5, and 1.0 s.

What the mechanics produce:

| Behaviour | Result at a 0.5 s tick |
| --- | --- |
| First contact | 51.5 s in mid and 60.5 s in top, as the geometry predicts |
| Hard push | A pushed wave of 6 reaches the enemy tower 9 s after first contact in mid and 10.5 s in top |
| Both laners last-hit | Creep score is 0.90 and 0.89. The front stays within 95 units of centre for 10 minutes in mid. At a 1.0 s tick the creep score is 0.80 and the front wanders up to 1,570 units. |
| Attack capacity | Creep score falls from 0.90 to 0.55 to 0.42 as capacity falls from 1 to 0.5 to 0.25. Under the own tower it is 0.50. |
| Lateral slots | An undisturbed lane leaves both towers untouched for 10 minutes in 5 of 10 runs. At a 1.0 s tick it is 6 of 10, and without slots 0 of 10. |
| A hold by champion aggro | A champion standing at the wave holds it outside its tower when the enemy has 6 surplus casters. The front stays in the band for 219 s of 240 [194 to 230]. With the champion absent it stays 60 s, and with a push 15 s. This meets the prototype's own test for a freeze. |

What they do not produce:

| Behaviour | Result at a 0.5 s tick |
| --- | --- |
| A stacked wave | Not shown. A lane that is one red caster short pushes toward red for about 50 s after first contact. Blue reaches the red tower at 101.5 s in mid and 111.5 s in top, with 5 minions near its lead. That is less than one wave. |
| A freeze that a champion could hold | Not shown. The hold above rests on an assumed standing rule: the champion stands one melee range from the enemy's lead minion, is always a valid target, and cannot die. It absorbs 19,700 damage in 4 minutes [12,800 to 21,200]. With 2, 3, or 4 surplus casters the hold lasts 94, 106, and 111 s, which is close to the 90 to 97 s with the champion absent. |
| Convergence in the tick | Hold times change by a factor of 2 to 5 between ticks. For 3 surplus casters the hold lasts 222 s at 0.25 s, 106 s at 0.5 s, and 46 s at 1.0 s. No run finer than 0.25 s exists. |
| Stability under a small change | The lane that is one caster short swings from tower to tower after its first crash. Whether a real lane does that is unknown. |
| Bounce after a crash | Seen in 4 of 10 runs. |

**One scenario is flawed.** The scenario built to test a slow push from the player's own tower cannot show one. It starts about 3,000 units from the enemy tower, thins one wave, and stops when the first minion arrives. The thinned wave arrives in 24 s with 3 minions, before a second wave can join it. Its result is not evidence either way. The independent review found this (handoff 003).

**Conflict with the owner decision.** The decision says "Freezes and slow pushes emerge." M7's evidence is narrower. A freeze-like hold appears at ticks of 0.5 s and below, but only with a large surplus, under an assumed standing rule, and at a health cost that no champion could pay. No stacked wave appeared in the one fair case. The trace shows a mechanism that works against stacking. An uneven minion fight ends in 10 to 18 s against a 30 s wave interval. The winners then walk on and meet the next enemy wave alone, about 7 s ahead of their own reinforcements.

M7 cannot say whether the model or the scenarios are at fault, because it has no ground truth. The research found no source that states how long a real freeze holds, how large a real slow push grows, or what an undisturbed lane does over ten minutes. Tuning rules until the named behaviours appear would repeat the predecessor's mistake (handoff 001, F12).

**What C2 does first.** Section 10.1 makes this C2's first task.

1. Get ground truth from a custom game on the reference patch. Six measurements are enough to start:
   - the time at which the first waves meet in mid and in a side lane
   - the front position of an undisturbed lane over 10 minutes
   - the crash time and wave size after one extra minion kill
   - the size of a wave that a player slow-pushes from their own tower
   - the number of waves that a standard freeze holds
   - the health that a champion loses while holding it, when it steps out of minion range as its own wave arrives
2. Rebuild the slow-push scenario so that it can succeed: thin several waves from lane centre, and count the wave that reaches the tower.
3. Test the documented rules that M7 did not test. They are unit collision (which stops all melee minions from reaching one target), the call-for-help aggro rule, and the side-lane speed boost. The last two bear directly on the 7 s reinforcement gap.
4. If freezes and slow pushes still fail against the ground truth, the owner chooses. Either the project accepts the simulator's wave behaviour as it is, or it allows one rule that is labelled approximate.

**Champion wave modes.** A champion with a `LANE` action stands at the wave and spends its attack capacity in one of four modes. The modes differ only in which minions the champion hits.

| Mode | What the champion hits |
| --- | --- |
| `passive` | Nothing. The champion stays in XP range. |
| `last_hit` | Only an enemy minion that one hit will kill. |
| `thin` | Enemy casters first, lowest health first, plus any last hit. |
| `push` | Any enemy minion, plus area damage on every enemy minion in range. |

No action is called freeze or slow push.

**Gold and XP.**

- A champion gets a minion's gold only for its own killing blow. A minion that dies to anything else gives no gold.
- XP for a minion's death is shared among enemy champions within 1500 units of the death, using the reference split. The lane reports the death and its position. The world grants the XP, because only the world knows where every champion is.
- **Bot lane.** Carry and support share one lane. Either can take a last hit. Because XP splits and each minion's gold goes to one champion, two champions in one lane cannot each earn a solo lane's income.
- **Support income.** The support holds the support item of the reference: 3 gold per 10 s, and a charge every 20 s (maximum 3, first at 1:05). With a charge and an ally within 1050 units, the support's attack executes a low minion. The support gets 18 gold and the nearest ally gets the minion's gold (Sourced). Without a charge, a support in `last_hit` mode takes farm from its carry, and a support in `passive` mode does not. The item's later upgrade tiers are left out (Assumed simplification).
- Passive gold, starting gold, kill gold by victim level, and the XP curve follow the reference. Bounties are left out.

### 5.7 Lane towers

M8 has the three lane towers of each lane and team: outer, inner, and inhibitor tower. Inhibitors, nexus towers, and the nexus belong to M10. Three towers is my reading of the owner's "lane towers". The roadmap says "basic lane towers", and outer towers alone would be less work (question OQ10).

- A tower can take damage only after the tower in front of it has fallen (Sourced).
- A tower shoots enemy minions in range, siege first, then melee, then caster. Each shot removes a fixed share of the minion's maximum health (Sourced).
- A tower shoots an enemy champion in range that damaged one of the tower's allied champions, and its damage ramps with consecutive hits (Sourced). A tower with no minion in range also shoots a champion in range.
- Minions and champions damage towers. Without enemy minions near the tower, damage to it is cut by 80 percent (Sourced).
- Tower plates give 120 local gold each at the reference's health thresholds. A tower kill gives the reference's global gold.
- A wave that passes a team's last lane tower reaches that team's base and is removed there. This is a stand-in until M10 adds inhibitors and the nexus (Assumed).

A fallen tower has consequences that later decisions feel. Enemy waves march further, the Homeguard run is shorter, the lane loses a safe farming spot and a vision source, and the lane assignment ends (section 5.10).

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
- **Retreat.** Leaving a fight is a new action, such as `MOVE` toward a tower. The pursuer keeps dealing damage while the route distance stays within its range. Whether the retreat works depends on speed, slows, the distance to safety, and towers.
- **Reinforcement.** An ally joins a fight by arriving. Arrival time is route length over speed.
- **Remaining resources.** Health and mana persist after a fight. They return only through regeneration or the fountain.
- **What agents see.** An observation holds combat facts: health, level, upgrades, positions, and who is nearby. It never holds a win probability.

**Tested** in the kernel prototype (`experiments/m7/kernel/scenarios.py`, results in `kernel.json` under `q2_fights`). All capability numbers in these runs are placeholders, so the outcomes show that the mechanics respond, not that they are calibrated.

| Scenario | Result |
| --- | --- |
| A champion retreats at half health. Sweep of speed difference, lockdown, and distance to its own tower (18 cases). | 15 escapes and 3 deaths. No runner died from 1,000 or 2,500 units. From 4,000 units the slower runner died, the equal-speed runner escaped on 18 health without lockdown and died with it, and the faster runner always escaped. |
| A champion loses a 1v1 alone. An ally walks in from d units away. | The side wins when the ally starts within 2,000 units and loses from 2,250. |
| The same duel in open lane and under the defender's outer tower. | The attacker wins in open lane with 97 health left. Under the tower the defender wins with 472 left. |
| An enemy jungler leaves fog toward a laner. | A laner at its own outer tower is never touched. A laner at the enemy outer tower with 390 health dies or survives on 30 health, depending on the decision interval. |

So outcomes change with distance, speed, lockdown, towers, and arrival time. The counts overstate how often a retreat works. The scripted chaser never gives up, and in 11 of the 15 escapes it died, mostly under the runner's tower. In the reinforcement sweep the first champion died in every case, and its side won when the ally arrived in time.

**Caveat.** With a speed advantage of 20 the runner escaped in every case. On a one-dimensional route, a chase is close to binary in the sign of the speed difference. Section 11 lists this as risk RK4.

**Settled in M7.** Fight duration, disengagement, and reinforcement timing come from per-tick mechanics, not from a formula.

**Deferred to M9.** The capability representation and its calibration. Burst, attack windup, dashes, and crowd-control detail. The execution-skill parameter. The conditions under which a strong champion wins a 1v2. Whether M9 needs an engagement entity to calibrate fights (section 11, risk RK4).

### 5.10 Roles, roams, and when assignments end

- Top, mid, carry, and support each have a home lane. Junglers have none and path freely.
- **During the assignment.** A laner may issue `LANE` actions only for its home lane. Every other action is legal anywhere: `MOVE`, `FIGHT`, `FOLLOW`, `WARD`, `SIEGE`, `CAMP`, `RECALL`. A roam is any such action away from the home lane.
- **Roam cost.** Nothing forces a return. While the laner is away, its lane keeps running. Minions die without gold for it, it gets no XP outside 1500 units, and its tower takes damage. Those mechanical costs are the roam rule.
- **Return.** A roam ends when the laner issues a `LANE` action for its home lane again.
- **When assignments end.** A lane's assignment ends when either outer tower of that lane falls. All assignments end at 14:00, the reference patch's own mid-game boundary. After that a champion may issue `LANE` actions for any lane.
- Junglers may issue `LANE` actions for any lane at any time. The reference's jungle-item XP penalty on lane minions applies to them.
- There are no team commands and no pings. Each champion chooses its own action.

The assignment rule is Assumed. It stops lane swaps in the early game, which the reference patch itself penalizes, and it keeps the early action space small.

### 5.11 Subsystems and the interfaces between them

M8 has ten modules. Each owns one body of rules. There is no plugin framework.

| Module | Owns |
| --- | --- |
| `ruleset` | The versioned constants of the reference patch |
| `map` | The route graph, positions, distances, lanes |
| `rng` | Keyed draws |
| `world` | All state, the tick order, snapshots, the digest, the invariant checker |
| `lanes` | Minions and towers of one lane, and champion wave inputs |
| `champions` | Capability profiles, intents, movement, recall, purchases |
| `jungle` | Camps, Scuttlers, shrines |
| `combat` | Collecting attacks and applying damage, including the `damage` function |
| `vision` | Team view, team memory, wards, `observe`, `legal_mask` |
| `harness` | Scenario loading, hidden-state sampling, comparisons, scripted policies |

Seven interfaces connect them. M9 and M11 replace what sits behind an interface without changing it.

| Interface | Shape | Replaced later by |
| --- | --- | --- |
| Policy | `act(observation, noise) -> action` | M12 learned policies |
| Observation | `observe(world, seat) -> Observation` and `legal_mask(observation)` | M11 adds fields |
| Lane | `LaneSim.step(champion_inputs) -> events` | C2 may change rules inside |
| Capability | `capability(profile, level, upgrades)` and `damage(raw, target)` | M9 |
| Snapshot | `world.snapshot()`, `World.restore(snapshot)`, `world.digest()` | Stable |
| Hidden state | `sample(snapshot, team, rollout) -> snapshot` | M11 |
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
| Wave dynamics: freezes, slow pushes, bounces | Unknown fidelity | Tested, not shown (RK1) |
| Tower health, damage, range, aggro, plates | Faithful. Bulwark and Crystalline Overgrowth are left out. | Sourced |
| Recall and fountain | Faithful timings. Homeguard is simplified. | Sourced |
| Jungle geography | Approximate. Camp positions are real. Paths between them are assumed. | Assumed (RK3) |
| Camps | Approximate. One health pool and one damage rate per camp. | Assumed |
| Champions | Approximate. Five placeholder capability profiles. | Assumed until M9 |
| Combat | Approximate. Damage per tick within range, equal execution. | Assumed until M9 (RK4) |
| Items | Approximate. Discrete upgrades on a fixed progression. | Assumed until M9 |
| Vision | Approximate. Real radii measured along routes, no brush, invisible wards. | Assumed (RK5) |
| Support income | Approximate. First item tier only. | Sourced, simplified |
| Bounties, role quests, buffs | Left out | Section 3.4 |

## 6. Information

### 6.1 Team view

A team sees an enemy champion, minion, ward, or camp if one of its vision sources is within that source's sight radius by route distance. Vision sources are the team's living champions (1350), minions (1200), living towers (1350), wards (900), and shrines (525). Teammates share one view.

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

- `FIGHT` is legal only against an enemy that is visible now.
- `CAMP` is always legal. Walking to a camp that turns out to be empty is a legal mistake, and the intent ends with the outcome `ABSENT`.
- `WARD` needs a charge. `RECALL` needs a living champion away from its fountain.

**Automatic execution has the same boundary.** The routine that carries out an intent reads enemy state only through the team's view and memory. The prototype found two places where this is easy to get wrong.

- Positioning for a `LANE` action must use the wave front that the team sees, not the lane's true front.
- A `FIGHT` order against a target that has entered fog walks to the last-seen position, not to the target.

**Tested** in the kernel prototype (`experiments/m7/kernel/test_kernel.py`, results under `q3_information`).

- Two worlds were identical in everything the blue team had seen. They differed in the red jungler's position in fog (8,947 units apart) and in one red camp cleared unseen. Over 31 ticks, all 155 pairs of encoded blue observations and masks were byte-identical. After the red jungler entered blue vision in one world, all 5 blue observations differed.
- A last-seen record froze at the last visible tick while the enemy moved 7,140 units.
- The team that cleared a camp knew its respawn time at once. The other team learned it 10 s before the respawn for Gromp and 60 s before for the Blue Sentinel.
- A ward revealed a hidden enemy for exactly 90 s.
- A pursuer whose target entered fog stopped at the last-seen position, 16,178 units from the target's true position.

### 6.4 Wards

Basic wards belong to M8, as the owner decided. A `WARD` action walks to within 625 units of the target and places a Stealth Ward. The ward is a vision source of radius 900 for 90 to 120 s. A champion holds up to 2 charges and may have 3 wards on the map (Sourced). Wards cannot be seen or destroyed in M8. M11 adds ward clearing, Control Wards, and sweeping.

The kernel prototype put enemy wards in sight into the team's view. A Stealth Ward is invisible in the real game, so the M8 view must leave enemy wards out.

## 7. Actions and timing

### 7.1 Action table

A policy returns one index into a fixed table.

| Kind | Target | End condition and outcome |
| --- | --- | --- |
| `KEEP` | none | Never. It leaves the current intent and its progress alone. |
| `HOLD` | none | Never. The champion stands and defends itself. |
| `MOVE` | A named map node | The champion arrives (`ARRIVED`). |
| `LANE` | A lane and a mode | Never by itself. |
| `CAMP` | A camp or Scuttler | The camp dies (`CLEARED`), or its location is seen empty (`ABSENT`). |
| `FIGHT` | A visible enemy champion | The target dies (`KILLED`), or leaves the team's view (`LOST`). |
| `FOLLOW` | An allied champion | Never by itself. The champion stays near the ally and attacks what attacks it. |
| `SIEGE` | A lane | No enemy tower in that lane can take damage. |
| `WARD` | A ward spot | The ward is placed (`PLACED`). |
| `RECALL` | none | The channel completes (`RECALLED`) or is interrupted (`INTERRUPTED`). |

The table has about 90 entries. `FOLLOW` and `SIEGE` come from the second design candidate (section 12).

### 7.2 Persistence, completion, and replanning

- A champion holds one intent. The intent persists until it completes or a new action replaces it. This is the owner's rule.
- `KEEP`, or the same action again while the intent is running, keeps the intent and its progress.
- Any other action replaces the intent at once and discards its progress.
- When an intent completes, the kernel records its outcome and the tick in the champion's state. The champion then holds position and defends itself until its next decision, which is at most one decision interval away.
- `LANE`, `FOLLOW`, and `HOLD` do not complete by themselves.
- Outcomes are `ARRIVED`, `CLEARED`, `ABSENT`, `KILLED`, `LOST`, `PLACED`, `RECALLED`, `INTERRUPTED`, and `DIED`. The observation includes the last outcome, so a policy can tell an interrupted recall from a finished one.
- Policies decide on a fixed cadence, all champions on the same ticks. No event triggers a decision.

**The prototype differs, and M8 does not follow it.** The kernel prototype kept every order standing after its end condition. A champion with a `CAMP` order attacked the camp again when it respawned, and a recall hit by damage started again by itself. The prototype's author made that change because a switch to `HOLD` made a fixed-order test depend on the decision interval. That dependence is real and intended. A champion whose order completes waits for its next decision. M8 implements the owner's rule. C1 tests the interval contract in a form that survives completion: a run at interval n must equal a run at interval 1 whose policy returns `KEEP` on the other ticks.

### 7.3 Interruption

| Action in progress | What interrupts it | What is lost |
| --- | --- | --- |
| `MOVE` | A new action | Nothing. The champion re-routes from where it stands. |
| `RECALL` | Damage, a stop effect, or a new action | All channel progress. The intent ends with `INTERRUPTED`. |
| `CAMP` | A new action | Nothing at once. The camp keeps attacking inside its leash, then resets its health. |
| `FIGHT` | A new action | Nothing at once. Pursuers keep attacking while in range. |
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

**Tested** in the kernel prototype (results under `q4_snapshot` and `q4_snapshot_real_lane`).

- A world ran 300 ticks, was snapshotted, ran 300 more, was restored, and ran 300 again. All 300 digests matched, with both lane models.
- From one snapshot, only the blue top laner's action changed. The top lane differed at once. Every entity in the bot lane stayed identical for the whole 300 s window.
- A snapshot of the ten-champion world is about 16 KB. It takes 241 microseconds to take and 223 to restore.

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

[[camp]]
node = "red_gromp"
state = "cleared"
cleared_at_s = 395

[knowledge.blue]
red_jungle = { last_seen = "bot_river", at_s = 385 }
red_gromp = "unknown"

[decision]
seat = "blue_top"
kind = "individual"
horizon_s = 120
rollouts = 32
hidden = "reachable"
continuation = { blue = "scripted_v0", red = "scripted_v0" }
alternatives = ["LANE top last_hit", "LANE top push", "RECALL"]
```

- `base` runs a scripted game to a clock time. Without it, the scenario starts from the game's opening state.
- Entity tables override fields of the base state. A loader rejects a state that breaks an invariant, such as a minion past a living tower.
- `knowledge` states what each team knew at the decision time. This answers concern C3 of handoff 002. By default a team's memory is whatever it would have seen in the base run. An override replaces a record, for example the place and time the enemy jungler was last seen.
- An override that changes hidden state without changing `knowledge` is how an author builds a state where the truth and the team's belief differ.
- `decision` names the deciding seat, the alternatives, the continuation policies, the horizon, and the hidden-state mode.

Scenarios are also the tool for the unusual and lopsided states of roadmap section 4. An author sets levels, gold, and upgrades directly.

### 9.2 Individual and coordinated alternatives

- An **individual alternative** changes one seat's action at the decision tick. Teammates do not cooperate automatically. They respond through their own policies and their own observations.
- A **coordinated alternative** changes the actions of several seats on one team at the decision tick. The report labels it as a team plan.
- Both kinds may hold the substituted action for a stated commit time. After that the seat's continuation policy decides again.
- The baseline alternative is the continuation policy's own choice.

### 9.3 Plausible hidden states

A comparison must not use what the deciding team could not know. The harness therefore samples the hidden state.

- **Explicit.** The scenario lists hidden-state hypotheses with weights.
- **Reachable.** This is the M8 default. It applies to each enemy champion outside the deciding team's view. The sampler draws a position that the enemy could have reached from its last-seen position in the elapsed time. It rejects positions that the team's vision sources would have seen. Draws are keyed by rollout index. The M8 sampler changes positions only. It does not change a camp, a level, gold, or any other field, so every public fact stays as the team observed it. A hidden camp state enters only through an explicit hypothesis, and its author keeps it consistent with levels and gold.
- M11 replaces the sampler with better inference behind the same interface.

Sampling changes only fields that are hidden from the deciding team. Each policy in a rollout still receives observations built from the sampled world through `observe`. The enemy's continuation policy acts on the enemy's own view of the sampled world.

**Acceptance test for M8.** For every sampled hidden state, the deciding team's observations at the decision tick are byte-identical to those of the original state.

### 9.4 What a comparison reports

For each alternative and each rollout, the harness records consequences for the deciding champion and its team at the horizon.

- Gold earned, XP earned, level, and upgrades bought.
- Health and mana.
- Deaths, and seconds absent from the map (dead, recalling, or walking back).
- Minions killed and minions missed.
- Tower damage dealt and taken, plates, and towers lost.
- Camps taken by each team.
- Arrival times at named places, where the scenario asks for them.

The report gives paired differences against the baseline with their standard errors, across rollouts and hidden states. It states the continuation policies, the hidden-state mode, the horizon, the ruleset, and the capability table.

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
| C1 | Kernel base | World, tick loop, decision interval, champions on routes, action table, intents with outcomes, `observe` and `legal_mask` for own state and teammates, snapshot and digest, invariant checker | A run at decision interval n equals a run at interval 1 whose policy returns `KEEP` on the other ticks, for n of 2, 4, and 10. A redirected move continues from the current position, and the distance walked equals speed times time. Restore and replay give equal digests at every tick for 1,000 ticks. A soak of random legal actions runs 10 games with no invariant failure. The invariants are: health and mana within bounds, gold not negative, every position on a valid edge, a non-empty legal mask, a clock that only advances, and no action by a dead champion. |
| C2 | Lanes and economy | Wave ground truth and the remaining documented rules (section 5.6) first. Then `LaneSim` for all three lanes, towers against minions, wave modes, gold and XP, bot-lane sharing, support item | The handoff reports each ground-truth measurement beside the simulator's value, and records the owner's choice on freezes and slow pushes. M8 tests re-assert on the M8 lane what the M7 wave tests cover: minion conservation, mirror symmetry, gold only for a champion's own killing blow, the XP split, and independence between lanes. First waves meet within 5 percent of the measured real-game times. A carry and support together earn no more minion gold than a solo laner in the same lane state, and 1.3 times the solo laner's XP within 2 percent. Each earns less than the solo laner. An incentive screen compares the gold plus XP that a scripted laner earns in 5 minutes by last-hitting and by pushing, over at least 10 lane states, and pushing does not earn more in every state. The tick sweep of risk RK2 is reported. |
| C3 | Recall and purchases | Recall channel, fountain, Homeguard, upgrade progressions | A cancelled recall loses all progress. Unspent gold changes no capability. The round trip from an outer tower (recall, buy, walk back) takes the time that route length and speed give, within one tick. |
| C4 | Jungle | Camps, Scuttlers, shrine vision, camp timers in memory, a scripted jungler | First spawns and respawns match the ruleset to the tick. Timer knowledge follows the reference rule for seen and unseen clears. Camp choice changes with distance and camp state in a sweep, so the jungler chooses among competing destinations. The handoff reports the scripted first-clear time. That time becomes a pass or fail criterion once a reference exists (question OQ8). |
| C5 | Combat and death | Per-tick fights, lockdown, tower against champions, death, respawn, kill rewards | M8 tests re-assert on the M8 code the fight behaviours of section 5.9: the same duel favours the defender under its tower, the reinforcement threshold is monotone in distance, and a retreat's outcome changes with speed and distance. Damage is monotone in capability. Permuting the seat order changes no outcome. A dead champion returns at the fountain after the ruleset's timer. Tower aggro follows the reference rule. |
| C6 | Vision, memory, wards | Team view, memory, ward placement, timer rule, full observation encoding | The hidden-state test: randomize every field hidden from a team, and that team's observations and masks stay byte-identical. The behaviour test: under the same randomization, that team's champions follow identical trajectories until something is revealed. Last-seen records freeze out of vision. A ward reveals and then expires. |
| C7 | Integrated game | All subsystems in one world, scripted policies for all ten seats, pinned replays, throughput gate | Scripted games of 20 game minutes run for 50 seeds with no invariant failure. Three pinned replays reproduce their digests. Every C1 to C6 test still passes. Throughput stays above the gate of section 10.4. A scripted team beats a random-action team on gold and XP at 15 minutes on at least 45 of 50 seeds. In the event log of an integrated game, every wave spawn, camp spawn, camp respawn, and champion respawn falls on the tick that the ruleset gives. An enemy wave without champion support never passes a living tower. A champion that fights under an enemy tower takes tower damage. After an outer tower falls, the enemy wave's furthest advance in that lane increases. A sweep over tick lengths of 0.25, 0.5, and 1.0 s and decision intervals of 1, 2, and 5 s reports which scripted outcomes change, and the handoff confirms or revises the starting values of section 5.2. |
| C8 | Scenarios and harness | Scenario loader, reachable sampler, comparison harness, saved scenarios | Saved scenarios load, restore, and replay exactly. The sampler passes the test of section 9.3. A comparison rerun gives identical output. The harness reports the first four rows of section 9.5 under two scripted continuation styles, and the report states where rankings differ between styles. |

C2, C3, C4, and C5 depend only on C1 and can overlap. C6 needs C2, C4, and C5. C7 needs all of them. C8 needs C7.

The M8 gate of the roadmap is met when C8 passes. C7 carries the roadmap's two clauses on timings that interact coherently and on towers that constrain waves and champions.

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

**Kernel throughput** (Tested, `experiments/m7/kernel/bench.py`, results in `kernel.json`). The load is a scripted 15-minute game with ten champions and the M7 lane model. Every run of one seed did identical work: about 1,070 minion deaths, 50 camp clears, 29 champion deaths, and 70 recalls.

| Setting | One process | 5 processes | 6 processes |
| --- | --- | --- | --- |
| 1.0 s tick, decision every 5 s | 1,328 simulated seconds per second (range 1,215 to 1,359, 7 runs) | not measured | 27,006 games per hour, 13,503 agent decisions per second |
| 0.5 s tick, decision every 2 s (the starting values) | 634 simulated seconds per second (598 to 640, 7 runs) | 10,352 games per hour, 12,940 agent decisions per second | 10,774 games per hour, 13,468 agent decisions per second |

- **What bounds it.** One CPython core per process. In the profile, lanes take 50 percent of the time and vision 26 percent. Twelve processes gave 5.5 times one process against 5.0 times for six, so the six physical cores are the limit and hyperthreads add little.
- **What it leaves out.** No policy network ran. The policy was a scripted function. The prototype also lacks rules that M8 adds: inner and inhibitor towers, minion damage to champions, and the support item's charges. It used the first-round lane rules.
- Building and encoding one observation with its mask takes 47 microseconds.
- The starting-values run began at 24 percent CPU load from other programs, so it may understate an idle machine.

**Learner throughput** (Tested, `experiments/m7/bench_learner.py`, results in `experiments/m7/results/learner.json`). The network is the predecessor's shape scaled up: two hidden layers of 256 units, 256 inputs, 64 actions. The prototype's observation has 251 values and 108 actions, and section 7.1 expects about 90 actions. The difference does not matter at this size. CPU only, 7 runs each.

| Operation | 1 thread | 6 threads |
| --- | --- | --- |
| Inference, batch of 10 (one decision point) | 39,863 decisions per second | 35,606 |
| Inference, batch of 640 | 187,590 | 300,265 |
| PPO update, minibatch of 2,048 | 120,465 transitions per second | 235,522 |

The GPU was not measured. `torch` with CUDA is not installed, and at this network size the CPU numbers already exceed the kernel's output.

**What bounds an overnight run.** This is derived from the two tables, not measured end to end.

- Five worker processes produce about 12,900 agent decisions per second with a scripted policy.
- Inference on one thread inside each worker adds about 0.25 ms to a decision point that costs about 3.2 ms to simulate, so about 8 percent.
- Four PPO epochs at 120,000 transitions per second let one learner thread absorb about 30,000 new decisions per second.
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

The M7 prototype sets the reference: 634 simulated seconds per wall second on one process at the starting clock values, with scripted policies.

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
| Jungler last seen botside | C8 with the reachable sampler | M11 |
| Gank, clear, counterjungle, or move | C4 as a sweep, C8 as a comparison | M9, M11 |
| Side lane, group, or objective | M10 | M13 |
| Strong bruiser against two | M9 | M13 |
| Contest dragon or trade | M10 | M13 |
| Bot-lane resource allocation | C2 | M9 |
| Unusual and lopsided states | C8, through the scenario format | M12, M13 |

| Roadmap section 7 check | First tested | Later |
| --- | --- | --- |
| Rules tests | C1 | Every checkpoint |
| Snapshot, replay, anti-leakage | C1 (snapshot), C6 (leakage), C8 (sampler) | M11 |
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
| RK1 | Freezes and slow pushes are not shown to emerge from the wave rules, against the owner decision. | Tested, two rounds (section 5.6). A hold appears at ticks of 0.5 s and below, under an assumed standing rule and at an impossible health cost. No stacked wave forms, and one scenario was flawed. | C2's first task: ground truth from the real game, a fair slow-push scenario, the untested documented rules, then an owner choice. C2 does not pass without it. |
| RK2 | Wave outcomes are sensitive to the tick and to tie-breaks. Hold times change by a factor of 2 to 5 between ticks of 0.25, 0.5, and 1.0 s, and no run finer than 0.25 s exists. | Tested (`waves.json`, `S7b_tick_sensitivity`). First contact and crash times stay within 10 percent. Holds, thinned pushes, and one last-hit arrival time (33 percent) do not. | A 0.5 s tick as the starting value. C2 repeats the tick sweep on the M8 lane, adds a 0.125 s reference, and reports every metric that moves more than 10 percent. |
| RK3 | The jungle graph is an assumption. Which camps connect, and the 1.15 detour factor, set every jungle travel time. No source gives a full-clear time on the 2026 clock. | Assumed. Lane distances are tested, jungle distances are not. | C4 reports the scripted first-clear time. The owner or the planning assistant supplies one trusted clear time, or measures one in a custom game. |
| RK4 | Chases on a one-dimensional route are close to binary in the sign of the speed difference, and fights without a fight object may not calibrate. | Tested: a runner 20 units faster escaped in all 6 of its cases. | M9 tests candidate B's attack windup and dash rules first. If a strong champion's 1v2 cannot be made to follow from capability and `damage` alone, M9 adds an engagement entity. |
| RK5 | Route distance is a poor geometry for sight. Walls are opaque, lanes have no width, and there is no brush. | Assumed. Not tested. | M11 owns it. The fix that keeps the design is a second table of sight distances computed from the map's walls. |
| RK6 | The reference rules that M8 omits change incentives. Without bounties a lead compounds faster. Without the early off-lane penalties a roam is cheaper than in the real game. | Sourced rules, omitted on purpose (section 3.4). | Each omission is listed. M9 and M10 decide which return. The pilot report names any exploit that an omitted rule would have blocked. |
| RK7 | The learner, not the kernel, may bound the pilot. Or the kernel may, once a policy network adds its cost to every decision. | Section 10.3. | The pilot's first task is an end-to-end throughput measurement. Lanes and vision are the two loops to move to arrays or compiled code. |
| RK8 | Comparisons depend on continuation policies, and M8's scripted policies are weak. Many comparisons will report no clear ranking or a ranking that flips with the style. | Reported from the predecessor (handoff 001, F11, F16). | C8 reports every comparison under two scripted styles and states where they disagree. M12 adds learned continuations. |
| RK9 | The reachable sampler spreads hidden enemies uniformly over where they could be. Real opponents are not uniform. | Assumed. | The scenario format accepts explicit hypotheses. M11 replaces the sampler. |
| RK10 | Many `F1` values were read through a tool that summarizes pages. A wrong constant would pass every test. | Sourced, single page. | C2 and C4 spot-check each `F1` value they use against the page, and promote it to `F2` or correct it. |
| RK11 | M8 is large: eight checkpoints before the roadmap gate. | Inference. The two M7 prototypes are about 3,000 lines and cover each subsystem only thinly. | Each checkpoint has its own acceptance tests and handoff. C2 to C5 can overlap. |
| RK12 | The prototype's timing evidence used orders that never end, not the contract's rule that an intent ends on completion. | Tested only in the prototype's form (section 7.2). | C1 implements the owner's rule and tests the interval contract with `KEEP`. |
| RK13 | The pilot reward pays for gold and XP. A policy may learn to farm and never fight. | Inference. | That is one of the exploits the pilot exists to find. The pilot report states it. The reward is not reused for M12 without review. |
| RK14 | Writing scenarios by hand may be too slow to be useful, even with a generated base. | Assumed. | C8 records the time taken to write the first four scenarios. |

### 11.3 Open questions

For the owner.

- **OQ1. Camp respawns.** Section 3.3 follows the reference: a respawn counts from the camp's last death. Confirm, or say that respawns must ignore clears.
- **OQ2. Starting clock.** Are a 0.5 s tick and a 2 s decision interval acceptable as starting values, given that C7 tests them?
- **OQ3. Lane assignment rule.** Section 5.10 forbids `LANE` actions outside the home lane until an outer tower falls or 14:00. The alternative is no restriction, with the reference's off-lane penalties added instead.
- **OQ4. Omitted reference rules.** Which of the rules in section 3.4 must return before the pilot, if any?
- **OQ10. Lane towers.** Section 5.7 gives M8 three towers per lane and team. Outer towers alone would be a smaller M8.
- **OQ5. Package name.** The reusable package is called `riftgame`, after the predecessor's `lanegame`. It is one directory and one line in `pyproject.toml` to rename.

For the planning assistant.

- **OQ6. Mana.** This design gives each champion one mana pool that wave clear and lockdown spend, because the owner asked for resource restoration at base. M8 could also start without mana and add it in M9.
- **OQ7. Public information.** The design treats enemy level as public and enemy upgrades and health as last seen. The real scoreboard rules were not researched.
- **OQ8. Jungle clear time.** Risk RK3 needs one trusted number.
- **OQ9. Support item tiers.** M8 keeps the support item at its first tier. Decide whether the 400-gold upgrade matters for bot-lane decisions.

## 12. Design candidates and the synthesis

M7 compared two independent designs before fixing the contracts. Candidate A came from this session. Candidate B came from a second model that saw the roadmap and the owner decisions but not candidate A.

**Where they agreed.** Both chose route distance as the only geometry, individual minions, and keyed randomness with no generator state. Both chose fights without a fight object and masks computed from the observation alone. The agreement is weaker evidence than it sounds. Both candidates read the same owner decisions, which already fix route distances and observation-only information, and both came from Claude models.

**Where they differed, and what decided it.**

| Fork | Candidate A | Candidate B | Decision | Evidence |
| --- | --- | --- | --- | --- |
| State layout | One Python object per entity, one game per world | Arrays with a leading game axis, 256 games per process | Objects for M8 | B estimated 1 to 3 ms per tick for an object kernel. The prototype measured 0.75 ms (section 10.3). |
| Parallelism | One process per core | One batched process | Processes | 6 processes give 5.0 times one process at a 1.0 s tick, and 4.2 times at the starting clock values (Tested) |
| Position | Continuous offset along an edge | A station every 50 units with full distance tables | Continuous for M8 | Built and tested in M7. The station table is the first optimization to try if vision stays a top cost. |
| Tick and decision interval | 1.0 s and 5 s | 0.5 s and 2 s | B's values | Section 5.2 |
| Intent end | Switch to `HOLD` | Record an outcome, drop to idle | End on completion, record an outcome, then hold. Both candidates and the owner agree. | Section 7.2 |

**Why objects.** M8 will change rules often. The predecessor rejected about 40 wave rules before its lane behaved (handoff 001, F12), and M7's first wave round failed too (section 5.6). Rules written as plain per-entity code are quick to change and to test. Rules written as masked array operations are not, and candidate B named this as its own most likely failure. The measured object kernel is fast enough for an overnight pilot. M8 still keeps the option open. It gives every entity a fixed seat or slot id and keeps the state flat. The two hottest loops, lanes at 50 percent of run time and vision at 26 percent, can then move to arrays or compiled code without a redesign.

**Taken from candidate B.** The reachable-position sampler for hidden states, which candidate A lacked. The `KEEP` action. Recorded intent outcomes. `FOLLOW`, `SIEGE`, and the `passive` lane mode. Policy noise drawn from keyed randomness. Damage collected from the start-of-tick state and applied at once. The leak test that randomizes every hidden field. Observations in the team's own frame.

**Left for M9 from candidate B.** An attack windup that costs the attacker movement, a separate spell resource with a hit roll, and dashes. These are B's answer to chases that are binary in speed (risk RK4).

## 13. How to rerun the evidence

Set up once, from the repository root.

```
uv venv .venv --python 3.14
uv pip install --python .venv/Scripts/python.exe numpy pytest
```

| Command | What it shows |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest -q` | Every test: ruleset tags, map distances, keyed randomness, wave behaviour, kernel contracts |
| `.venv/Scripts/python.exe -m experiments.m7.waves.scenarios` | Wave scenarios. Writes `experiments/m7/waves/results/waves.json`. |
| `.venv/Scripts/python.exe -m experiments.m7.kernel.scenarios` | Fight, information, and snapshot scenarios. Writes into `experiments/m7/kernel/results/kernel.json`. |
| `.venv/Scripts/python.exe -m experiments.m7.kernel.bench` | Kernel throughput and process scaling at a 1.0 s tick with 5 s decisions. Takes several minutes and wants an idle machine. |
| `.venv/Scripts/python.exe -m experiments.m7.kernel.bench start` | The same at the starting clock values. This is the source of the 634 figure and of the gate in section 10.4. |
| `.venv/Scripts/python.exe -m experiments.m7.bench_learner` | Learner throughput. Needs `torch` (`uv pip install torch --index-url https://download.pytorch.org/whl/cpu`). |

**Provenance.** The results files carry no timestamp and no code version. `kernel.json` merges separate runs of the scenarios and the two benchmark modes. The first-round wave results were overwritten by the second round.

**Reusable code and prototype code.** `riftgame/` holds what M8 builds on: the ruleset loader and files, the route-graph map, and keyed randomness. `tests/` covers it. Everything under `experiments/m7/` is prototype code that exists to answer M7's questions. M8 rewrites it against the contracts in this document and does not import it.
