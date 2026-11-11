# M8 foundation

**Status.** First campaign: checkpoints C1 (kernel base) and C2 (lanes and economy). C1 is complete. C2 is built and is not complete, because three required wave behaviours are unresolved (section 2). C3 to C8 have not started. Nothing was trained. [Handoff 005](../../handoff/005_m8_c1_c2.md) reports the campaign and the independent review of it.

**Date.** 2026-11-11.

**Builds on.** [`M7_architecture.md`](M7_architecture.md). This document does not repeat M7. It names the M7 section that a piece of M8 implements, and it states every place where M8 departs from M7.

**Evidence labels.** The labels are M7's. **Tested** names a test or a script in this repository. **Sourced** comes from the reference patch research. **Assumed** is a design choice or a placeholder number. **Reported** has no evidence in the repository. **Inference** is a conclusion drawn from tested facts. **Unresolved** marks a known limit.

## 1. Summary

- The kernel of M7 section 5 now exists as reusable code in `riftgame/`: ten champions on the full map, a fixed tick with a separate decision interval, intents that end with an outcome, the role duty state, an observation boundary, snapshots, replays, and an invariant checker (section 3).
- One `LaneSim` class runs all three lanes with individual minions, three tower tiers, and the five wave modes. The world pays minion gold, support-item gold, and passive gold into separate ledger entries (section 4).
- The lane is a port of M7's lane. With M7's rules it reproduces all 998 metrics of M7's results file once the draw key is the same (section 5.1).
- M8 adds the documented rules that M7 left out. Side-lane speed changes the lane. The pushing advantage moves where waves crash and not how large they are. A cap on attackers, the one effect of unit collision that M8 tested, changes neither fight length nor any verdict (section 5.6).
- The independent review found two details in which M7's lane, and so the port, departed from the documented rules. Both are fixed in the M8 lane (section 4.2).
- Wave behaviours: a crash and a bounce in side lanes pass their tests. A delayed crash with one reinforcement appears in one setting of eight. A stack of two waves, a hold that a champion can sustain, and a bounce in mid within 120 s do not appear (section 5.4).
- What the traces show: a wave with an advantage wins its fight in 10 to 18 s, walks to the tower, and dies there before its reinforcement arrives. When a diagnostic weakens minion blows, stacks appear once the untouched first-wave fight lasts 36.5 s and M7's freeze test passes at 44.5 s. The reference lane's fight lasts 31 s. That fight length is the cause is an inference, not a tested fact (section 5.5).
- The constants behind those times were read a second time on the wiki and equal the ruleset. No document gives the times themselves. Two real-game measurements bear on them, and section 5.7 says what each outcome would and would not show.

## 2. Phases, acceptance criteria, and progress

M8 has eight checkpoints (M7 section 10.1). This campaign ran six phases over the first two.

| Phase | Work | Acceptance | State |
| --- | --- | --- | --- |
| P0 Ground | Read the roadmap, the M7 document, handoff 004, the M7 prototypes, and the reference notes. | Baseline suite of 138 tests passes with 1 expected failure. | Done |
| P1 Kernel (C1) | World, clock, routes, action table, intents, duty state, observation, snapshot, replay, invariants. | The C1 criteria of section 3.3. | Done. All pass. |
| P2 Lane port | `riftgame/lanes.py` from M7's lane, with each optional rule behind a switch. | With M7's rules, every metric of M7's `waves.json` is reproduced. | Done. 998 of 998 with M7's draw key. |
| P3 Wave investigation | Traces, the omitted rules, a review of M7's tests, a search over plans, a fight-speed diagnostic. | Each required behaviour passes a reviewed test, or carries a traced mechanism and the missing evidence by name. | Done as an investigation. Two behaviours pass, one appears in one setting, three do not appear. |
| P4 Lanes in the world (C2) | Wave-aware `LANE` intents, minion damage on champions, gold, XP, support item, passive gold. | The C2 criteria of section 4.6, and the wave capabilities of the owner's brief. | Built. Every criterion of section 4.6 passes. The wave capabilities do not all pass, so C2 is not complete. |
| P5 Review and handoff | Mutation runs, provenance, an independent review on another model, handoff 005. | Every number in the handoff comes from a results file that the checker reports as current. | Done |

**C2 is not complete.** M7's C2 row does not require a freeze or a slow push to appear, and every criterion of that row passes. The owner's brief for this campaign is stricter: freezing, slow pushing, crashing, and bouncing are required capabilities, and C2 may not be called complete while a core requirement is unresolved. Three are unresolved.

1. No plan brings a stack of two waves to the enemy tower.
2. No plan holds a wave off the champion's tower in a way that passes M7's freeze test.
3. Mid lane does not bounce within M7's 120 s.

## 3. Kernel base (C1)

### 3.1 What exists

| Module | Owns | Checkpoint |
| --- | --- | --- |
| [`world.py`](../../riftgame/world.py) | The state, the eight-step tick of M7 section 5.2, `Config`, snapshots, the digest, the invariant checker | C1 |
| [`champions.py`](../../riftgame/champions.py) | Seats, placeholder capability, the action table, intents with a rule per kind, the duty state | C1 |
| [`vision.py`](../../riftgame/vision.py) | `observe` and `legal_mask` | C1 |
| [`harness.py`](../../riftgame/harness.py) | The policy interface, three scripted policies, replays | C1 |
| [`lanes.py`](../../riftgame/lanes.py) | Minions and towers of one lane, and the stance of a champion at a wave | C2 |
| [`economy.py`](../../riftgame/economy.py) | Gold, XP, the support item, and the champion inputs of a lane | C2 |

The world always holds ten champions on the full route graph. Nothing in `riftgame` has a single-lane mode. The wave experiments drive a `LaneSim` directly, which is the validation tool, and the world drives the same class.

### 3.2 Contracts, and where the kernel departs from M7

The kernel implements M7 sections 5.2 (clock and tick order), 5.3 (state), 5.10 (roles), 6.3 (observation and mask), 7 (actions), and 8 (randomness and snapshots). It departs in these places.

| Departure | Reason |
| --- | --- |
| The roam allowance is a set of `Config` fields: the cap, the refill, the end time of assignments, whether a fallen outer tower ends one, and a switch that turns the restriction off. | Owner decision: the allowance is an experimental restriction, not a permanent rule. |
| A laner with no allowance may choose `LANE` for its lane, `RECALL`, and `MOVE` to a node of its lane, to its own base, or to its own fountain. All of these count as returning, not roaming. M7 allowed only `LANE` and `RECALL`. | Owner decision: a returning champion keeps retreat choices. The walk to the enemy base is excluded, because every lane ends there and the shortest route can leave the lane. |
| `FIGHT` in self-defence for a returning laner is not built. The mask has one marked place for it. | It needs combat and vision (C5). |
| The action table has 98 entries. Targets are named in the acting team's frame, so one index means the mirrored thing for red. | M7 said about 95. |
| An observation position is a `Place`: a lane with the distance from the team's own end, or one edge off the lanes. The mirror test is exact only for lane positions, bases, and fountains. | The map has no mirror symmetry that keeps roles. Its only symmetry swaps top and bot, and blue's and red's tower distances differ by up to 289 units (Reported by the delegate that built the kernel). |
| The digest covers the state and not the config. | The decision-interval test compares two runs that differ only in the config. |
| Death and respawn exist in a minimal form: a single damage function, the reference death timer, a return on the fountain. | Minion damage can kill, so C2 needs it. Kill rewards stay in C5. |
| `FIGHT`, `SIEGE`, and `WARD` are in the table and masked off. `CAMP` ends with `ABSENT` on arrival. | Their subsystems are C4 to C6. |
| The observation's public facts are the clock only. | Kills, deaths, and enemy levels arrive with C5 and C6. |
| These state fields of M7 section 5.3 do not exist yet: intent phase, slow end tick, ward charges, tallies. `attack_credit` exists and nothing reads it. | Nothing needs them before C5 and C6. The attack credit of lane hits lives in the lane until C5 gives a champion one capacity for every target class. |

### 3.3 Acceptance criteria of C1

The criteria are those of M7 section 10.1 for C1, plus the owner's two corrections on roles. Every row is Tested. The roam numbers are in [`experiments/m8/results/kernel.json`](../../experiments/m8/results/kernel.json).

| Criterion | Result | Test |
| --- | --- | --- |
| A run at decision interval n equals a run at interval 1 that keeps between decisions, for n of 2, 4, and 10, with intents that complete inside the run | Equal digest for digest over 600 ticks. The test requires `ARRIVED`, `ABSENT`, and `RECALLED` to occur inside each run. | `tests/test_world_clock.py` |
| A redirected move continues from the current position, and distance walked is speed times time | Every tick's walk is speed times the tick, before and after the redirect | `tests/test_world_clock.py` |
| Restore and replay give equal digests at every tick for 1,000 ticks | 1,000 of 1,000. A pickled snapshot also restores in a new process under two hash seeds. | `tests/test_world_snapshot.py` |
| No laner roams longer than the cap plus one decision interval at a stretch | Longest stretch 91.5 s against a bound of 92 s at the starting clock, and 93 s against 95 s at a 1 s tick with 5 s decisions | `tests/test_world_roles.py` |
| Each laner's roaming share after its first allowance is spent stays within 20 percent plus one decision interval over the window | 13.3 to 16.2 percent against 20.3, and 13.7 to 16.5 percent against 20.7 | `tests/test_world_roles.py` |
| Junglers are never restricted. No position changes by more than speed times the tick, except on death and on recall. | Both hold in 840 s games in which champions die | `tests/test_world_roles.py`, `tests/test_world_soak.py` |
| The restriction is configurable | With it off, no laner is ever sent home. With a cap of 30 s and a refill of 0.5, the bounds follow the configured values. | `tests/test_world_roles.py` |
| A returning laner keeps retreat choices | With an allowance below zero and off its lane, it may walk to its own tower, base, or fountain, and the allowance does not drain | `tests/test_world_roles.py` |
| A soak of random legal actions runs 10 games with no invariant failure | 10 games of 600 s, two policies, two clocks, with keyed damage so that champions die. No failure. | `tests/test_world_soak.py` |
| The invariants: health and mana in bounds, gold not negative, every position on a valid edge, a non-empty mask, a clock that only advances, no action by a dead champion | Each one is broken on purpose and the checker raises | `tests/test_world_soak.py`, `tests/test_world_intents.py` |
| Leak test for the C1 boundary | Every field of every enemy champion is changed, and so are the minions and towers of every lane. The team's five observations and masks stay identical. | `tests/test_world_observation.py`, `tests/test_economy.py` |
| A replay reproduces its digests, and one digest is pinned | 600 of 600. The pin is seed 2026, 600 ticks, digest `e7bb8a6c` and 56 more digits. It includes the lanes, so it moved twice in this campaign: when the lanes and the economy were wired in, and when the review fixed two details of the lane. | `tests/test_world_snapshot.py` |

The role bound limits time charged as roaming, as in M7. Time off the lane by position, walks home included, is 38 to 44 percent under the policy that always prefers to leave.

**Measured, not criteria.** One process, starting clock, 600 s games, 7 runs each (`kernel.json`). The machine's load was not recorded.

- Random legal actions: 1,183 simulated seconds per wall second [1,081 to 1,210].
- Scripted farming, with all eight laners in their lanes: 945 [923 to 960]. The lanes take 54% of that game, the lane inputs 17%, movement 14%, and `observe` 12%.

Both are above M7's gate of 300, which is measured at C7 on the integrated game and not here. The kernel has no fights, camps, or fog yet.

A snapshot of a world at 600 s is 12,197 bytes pickled and takes 0.8 ms to take and 0.8 ms to restore.

## 4. Lanes and economy (C2)

### 4.1 The lane model

`riftgame/lanes.py` holds one class, `LaneSim`. It owns a lane's minions, its six towers, and its wave clock, on the lane coordinate of M7 section 5.1. A champion enters a lane tick as a `ChampionInput`. Everything that leaves the lane is an event: `MinionDeath`, `MinionRemoved`, `TowerDamage`, `TowerDestroyed`, `ChampionDamage`. The world applies the events (M7 section 5.11).

`LaneRules` names each optional rule. `M8_LANE` is the lane that M8 ships. `M7_LANE` switches off what M7 did not model and resolves three details as M7 did, so that M7's results can be reproduced. Two fields are diagnostics and are off in both.

| Rule | In the M8 lane | Status |
| --- | --- | --- |
| Waves on the reference clock, with reference stats and composition | Yes | Sourced |
| Target priority: enemy minion, then tower, then a champion in the path | Yes, at acquisition and on every retarget | Sourced |
| A blow on a minion adds 2, 3.5, or 5 percent of the target's current health | Yes | Sourced, read twice |
| Lateral slots that break ties between targets | Yes | Assumed (M7 section 5.6) |
| Side-lane speed for wave 2 and later, until 14:00 | Yes, new in M8 | Sourced, read twice |
| Call for help: minions within 1,000 units turn on an enemy champion that attacks an allied champion, unless they attack a tower | Yes, new in M8 | Sourced. Nothing triggers it before C5. |
| Pushing advantage from 3:30, by team level lead and tower lead | Yes, new in M8 | Sourced |
| Three tower tiers. Only the front tower fights and takes damage. | Yes, new in M8 | Sourced |
| A wave past the last lane tower is removed at the enemy base | Yes, new in M8 | Assumed stand-in until M10 |
| Champions that attack at the same instant are served in an order drawn by key, not by seat | Yes, new in M8 | Assumed |
| `melee_cap`: at most n melee minions on one target | Diagnostic, off | Section 5.6 |
| `minion_damage_scale`: scales minion blows on minions | Diagnostic, off | Section 5.5 |

The added constants live in a second ruleset file, [`patch_26_22_m8.toml`](../../riftgame/rulesets/patch_26_22_m8.toml). `patch_26_22.toml` stays byte-identical, because every M7 results file records its hash. The ruleset id of M8 is `ref-26.22-r1+m8.1`.

### 4.2 How M8 treats the omitted rules, and two fixes to M7's lane

**Side-lane speed.** Part of the lane. Wave 2 reaches the centre of top lane 24.5 s after it spawns. Wave 1 needs 31 s (Tested, `investigation.json`, `arrivals`).

**Call for help.** The reference priority list has six tiers (Sourced, wiki Minion page, read 2026-11-11).

| Tier | Reference | M8 |
| --- | --- | --- |
| 1 | An enemy champion that attacks an allied champion | The `harassing` flag of `ChampionInput`. Tested in the lane. The world sets it from C5 on. |
| 2 | An enemy minion that attacks an allied champion | Cannot arise in the M8 lane. A minion attacks a champion only when no enemy minion is within 500 units of it, so no enemy minion can acquire it. |
| 3 | An enemy minion that attacks an allied minion | Inside a wave fight every engaged minion attacks, so this tier is the nearest-minion rule. |
| 4 | An enemy tower that attacks an allied minion | The tower is the target when no enemy minion is in range. |
| 5 | The closest enemy minion | The nearest-minion rule |
| 6 | The closest enemy champion | A champion in the path, when nothing else is in range |

**Fix 1: the priority holds on every retarget.** In M7's lane a minion whose target died inside a tick could hit a champion in its reach although an enemy minion stood within its acquisition range. The independent review counted 22 of 94 minion blows on a holding champion that came that way (Reported). The documented priority forbids it. In the M8 lane such a minion waits for the next tick and walks to the minion (Tested, `tests/test_lanes.py`). My first claim that tier 2 could not arise was wrong while this path existed. A form of tier 2 that I had built on top of it, and removed, moved the creep score of M7's last-hit case from 0.897 to 0.825 (Reported, that run is not kept).

**Fix 2: no seat wins every tie.** M7's lane served champions that attack at the same instant in input order. The review showed two equal bot laners splitting kills 81 to 28 by that order (Reported). The M8 lane draws the order by key on the tick and the seat, and the result no longer depends on the order of the inputs (Tested).

**Pushing advantage.** Part of the lane. The world passes blue's average level minus red's on every tick. The lane counts fallen towers itself. Details that the wiki does not state are Assumed: the tower lead never goes below zero, and the flat reduction applies only to the team with the level lead.

**Unit collision.** Not part of the lane. The wiki confirms that minions collide and gives a pathing radius of 35.7 units (Sourced). A hard queue on a one-dimensional lane would invent a frontage limit, because six such bodies fit around one target. M8 tests one effect that collision could have, a cap on melee attackers per target, as a diagnostic (section 5.6). It does not model bodies that block each other's movement, which would take two-dimensional minions.

### 4.3 Reference rules that the lane still leaves out

M7 section 3.4 lists the omissions. This campaign changes that list.

- Now in the lane: side-lane speed, call for help, the pushing advantage.
- Still out, from M7's list: minion speed growth after 10:00, the smaller waves of the mid game, bounties, role quests, the support item's later tiers and its income from hitting champions.
- New on the list, from the second wiki reading (Sourced):
  - Melee minion armor, which grows from 0 to 20. It is zero while the first waves decide a lane.
  - Minions re-evaluate their target between attacks "every few seconds" and keep a champion as target "for a short time afterwards". The lane re-evaluates every tick and drops a champion at once.
  - The call for help is ignored by minions that attack a tower, "except in the first wave". The lane has no exception.
  - A champion in a minion's path is attacked only "outside turret range". The lane has no such condition.
- New on the list, from M7 section 5.7: tower plates and their local gold. They need champions that damage towers, which is C5.
- A limit of the lane coordinate: ranges between a champion and a minion, and between a tower and a minion, are measured along the lane. Near the corners of top and bot a gap of 550 units along the lane is about 8 percent longer than the straight line (Reported by the review). M7 sanctioned the lane coordinate among minions only.

### 4.4 Wave modes and the stance of a champion

The five modes are M7's (section 5.6). `stance(lane, team, mode, attack_range, front)` returns where a champion in a mode wants to stand and whether it stands in the minions' path. The world and the lane experiments call the same function, so a scripted experiment and a `LANE` intent cannot disagree.

**The in-path rule is now Sourced in part.** M7 assumed that minions attack a champion in their path and ignore one that stepped aside. The wiki states that the call for help triggers "when a champion stands in a minion's path with no other targets in range". It also records that since patch 26.10 attacking a minion no longer draws minion aggro. The second half of M7's rule stays Assumed: a champion that has stepped aside hits nothing. In the game a ranged champion can hit a minion from outside its acquisition range. A lane coordinate has no width, so the lane cannot express how briefly that works against a marching wave.

**A limit of the action table.** M7's freeze plans thin a wave while they hold it. The five modes cannot say that. `hold` hits like `last_hit`, and `thin` steps aside once the champion's wave is gone. A policy that wants to trim a held wave has to switch to `push`. The experiments report both kinds of plan (section 5.4). Whether the table needs a sixth mode is question OQ11 of M7, still open.

**For C6.** `stance` takes the front as an argument. Today the world passes the lane's true front, so a champion's own walk is driven by enemy minions that its team may not see. Once fog exists, the world has to pass the front that the champion's team sees (M7 section 6.3).

### 4.5 Gold, XP, and the ledger

`riftgame/economy.py` owns what a champion earns. It is an eleventh module beside M7's ten, because gold and XP rules belong neither to the lane, which knows no champion state, nor to the tick loop.

Each champion has an unspent gold total and a ledger with one entry per source.

| Ledger entry | Paid when | Status |
| --- | --- | --- |
| `STARTING` | 500 at the start | Sourced |
| `PASSIVE` | 20.4 per 10 s from 1:05, to every champion | Sourced |
| `MINION` | A minion's gold, once. To the champion that lands the killing blow, or to the support's nearest ally when a charge shares the kill. | Sourced |
| `SUPPORT_ITEM` | 3 per 10 s to the support, plus 18 for each charge used | Sourced. The start of the 3 per 10 s at 0:00 is Assumed. |

- **Support charges.** A charge arrives at 1:05 and every 20 s after it, up to 3. A charge that finds the item full is lost (Assumed simplification of the reference timer). With a charge and a living ally within 1,050 units, the support's hit kills a minion at or below 30 percent of its health for a ranged support and 50 percent for a melee one.
- **XP.** For each minion death the world finds the living enemy champions within 1,500 units in a straight line and gives each the reference share. A jungler keeps 30 percent of lane-minion XP at 0:00, rising to all of it at 20:00.
- **Minion damage.** A minion blow on a champion goes through the world's single damage function, so it interrupts a recall and can kill. The kernel has death and respawn. Kill rewards are C5.
- **Regeneration.** A living champion regains its profile's health regeneration each tick. M7 did not list this in the tick order. It sits in step 6.

### 4.6 Acceptance criteria of C2

The criteria are those of M7 section 10.1 for C2. Every row is Tested unless it says otherwise.

| Criterion | Result | Evidence |
| --- | --- | --- |
| The three wave experiments run on the M8 lane with M7's pass tests unchanged | Done. M7's verdicts are unchanged: no slow push, no freeze, bounce not in every run. | `m7_tests_on_m8_lane.json`, section 5.4 |
| Each measurement of M7 section 5.6 stands beside the simulator's value where someone has taken it | Nobody has taken one. Handoff 005 lists the simulator's values. | Handoff 005 |
| No rule is added to produce a freeze or a slow push | The lane gained the documented rules of section 4.1 and two fixes toward documented behaviour. The two diagnostics are off in the lane that ships. | Section 4.1, `tests/test_lanes.py` |
| Minion conservation | Every spawned minion is alive, dead, or removed at the base | `tests/test_lanes.py` |
| Mirror symmetry | A reflected lane reflects every position, in mid and top, with a champion pushing | `tests/test_lanes.py` |
| Gold only for a champion's own killing blow | In the lane and in the world | `tests/test_lanes.py`, `tests/test_economy.py` |
| The XP split | 100 percent for one champion, 65 percent each for two, by straight-line range, living champions only | `tests/test_lanes.py`, `tests/test_economy.py` |
| Independence between lanes | A champion that pushes top changes nothing in mid or bot, or in any other champion, over 200 s. After 3:30 the pushing advantage couples the lanes through team level, by rule. | `tests/test_economy.py` |
| First waves meet at the time that route length and minion speed give, within one tick | 51.5 s in mid and 60.5 s in top and bot | `tests/test_lanes.py` |
| In bot lane each minion's gold is paid at most once | The pair's minion gold equals the gold of the minions that a champion killed | `tests/test_economy.py` |
| The pair's XP is 1.3 times a solo laner's within 2 percent, and neither gets more than the solo laner | Holds over 300 s | `tests/test_economy.py` |
| The support item's gold is counted apart: 3 per 10 s plus 18 per charge used, with at most one charge per 20 s | Holds. A support without an ally in range shares nothing and keeps 3 charges. | `tests/test_economy.py` |
| Minion gold, item gold, passive gold, and starting gold are the only sources, each accounted for apart | Every champion's gold equals the sum of its four ledger entries, and each entry equals its rule | `tests/test_economy.py` |
| An incentive screen over at least 10 lane states, with no pass condition | 12 states. No mode earns most in every state. | Section 5.8 |
| The tick sweep of risk RK2 is reported | 13 of 17 metrics within 10 percent at 0.5 s | Section 5.8 |

In a scripted game of 600 s in which every laner last-hits and junglers hold, a solo laner reaches level 9 and the two bot laners level 7. The support earns 666 gold from its item and 476 to 555 from minions, and passive gold is 1,091 for everyone (`kernel.json`). The champion numbers are placeholders, so these figures show that the accounting works, not what a game pays.

## 5. Wave investigation

Every number in this section is at a 0.5 s tick over 5 seeds unless it says otherwise. A range in brackets is the minimum and maximum across seeds. The results files are in [`experiments/m8/waves/results/`](../../experiments/m8/waves/results/).

### 5.1 The port reproduces M7

[`m7_tests.py`](../../experiments/m8/waves/m7_tests.py) runs M7's 103 wave cases, with M7's scripted plans and M7's two verdicts unchanged, on the M8 lane.

- With `M7_LANE` and M7's draw key, 998 of 998 metrics equal the `A+B` column of M7's `waves.json` (Tested, `port_check_with_m7_draw_key`).
- With M8's own draw key, 30 metrics differ, all in mid lane. M7 keyed every lane's tie-break draws with lane id 0. M8 keys them with the lane, so that three lanes of one world do not draw the same numbers.

### 5.2 What the traces show

Two traces were read tick by tick before any test changed (`python -m experiments.m8.waves.trace`).

**A placed fight and a natural fight.** Six minions placed in full contact with six kill each other in 25.5 s: 10.5 s for the melee lines and 15 s for the casters. That is M7's figure. On the natural clock the minions of a wave arrive 0.8 s apart, and the first-wave fight in mid lasts 31 s when it is left alone. Wave 2 comes into range 29.5 s after the first blow. At that moment six minions of wave 1 are alive, with 7 percent of their health left on average (Tested, `investigation.json`, `natural_fight`). So an even fight lasts about as long as the wave interval, not less.

**A thinned wave.** Top lane, first contact at 60.5 s. The champion kills the three enemy casters and then only last-hits.

| Time after contact | What happens |
| --- | --- |
| 18.5 s | The enemy wave is dead. Three full casters and one melee minion march on. |
| 21.5 s | They meet the next enemy wave 1,000 units outside the enemy tower's range. |
| 27 s | The champion's second wave joins: 9 against 6. |
| 36.5 s | The enemy wave is dead again. Seven minions march on. |
| 38 s | They enter the tower's range. The next enemy wave is 9 s away. Their own next wave is about 20 s away. |
| 53 s | The tower and the arriving enemy wave have killed all seven. |

So a wave with an advantage wins quickly, walks the 1,000 to 1,750 units to the tower in 3 to 5 s, and dies there about 5 s before its own reinforcement arrives. An uneven fight is short: six against nine ends in 12.5 to 13.5 s (`investigation.json`, `fights`).

**Arrivals** (Tested, `investigation.json`, `arrivals`). Seconds from a wave's spawn until its first minion reaches a mark, top lane, blue.

| Wave | Own tower edge | Centre | Enemy tower edge |
| --- | --- | --- | --- |
| 1 | 26 | 31 | 35.5 |
| 2 and later | 20.5 to 21 | 24.5 to 25 | 29 to 30 |

At a team's own tower edge its wave arrives 8.5 s before the enemy's. That head start is what a freeze has to cancel with surplus minions, and what makes a lane bounce.

### 5.3 Review of M7's tests

The owner asked whether M7's scenarios, plans, and criteria test what they claim. Each row states what the review found and what changed. No numeric bar of M7 was lowered: 12 minions, 120 s, and the band of 1,500 units stand.

| Behaviour | M7's test | Finding | What M8 does |
| --- | --- | --- | --- |
| Crash | A hard push reaches the tower before the second enemy wave can. | Sound. | Kept. |
| Delayed crash and stacking | One test for both: a thinning plan reaches the tower later than a push, with 12 minions near the lead at the first tick in range. Two plans. The run stops 20 s after that tick. | Two properties in one verdict. Two hand-written plans are not a search. The measure at the first tick misses stacks that assemble at the tower, but only once stacks exist (section 5.5), so it did not cause M7's negative result. | The stack test keeps the bar of 12 and reads the largest crash within 240 s, over ten plans, two starts, two lanes, and an opponent who is absent or last-hits. A second, new criterion reports a delayed crash with a reinforcement: later than a push, with minions of two waves. It is weaker than M7's test and is reported apart, not instead. |
| Holding | From a built state: the front stays within 1,500 units outside the tower's range for over half of 240 s in every seed, both controls stay below half, no retreat, no death. | The band clause does not measure holding. In a state aligned with the wave clock the front is in the band for 121 s [121 to 123.5] with no champion at all. On the M8 lane the controls of M7's built state exceed or reach 120 s at a surplus of 2, 3, and 6 casters (133.5, 120, and 163.5 s), so the test can pass only at a surplus of 0 or 4. | M7's test stays as the bar, unchanged. A second state is added, aligned with the clock: the surplus casters stand at the hold line when the champion's wave arrives. Every report gives time under the tower, health, retreats, and cycles in the band beside the band time. No threshold is set on them. That is a question for the planning assistant. |
| Bounce | After a hard push of one wave, the contact point crosses back over the centre within 120 s, in every run, in mid and top. | The 120 s are not derived from anything. One wave of six is the weakest crash there is. | Kept as it is, per lane, with the time of the return reported. |

Where M7's bar stays unmet, the test is a strict expected failure in [`test_behaviours.py`](../../experiments/m8/waves/test_behaviours.py), so the suite fails if the behaviour ever starts to pass unnoticed. Those tests run on 2 seeds to keep the suite short. The stack test uses M8's measure of the largest crash over all eight settings.

### 5.4 Results by behaviour

| Behaviour | Result on the M8 lane | Verdict |
| --- | --- | --- |
| Crash | A push of the first wave reaches the tower 10.5 s after contact in top and 9 s in mid, with 6 minions. The second enemy wave reaches its tower 20.5 s after contact in top. | Passes |
| Delayed crash, one reinforcement | In top lane from first contact with the opponent absent, a plan that kills one to three casters and then last-hits crashes 37.5 to 40 s after contact, against 10.5 s for a push, with 7 minions from two waves in every seed. In top lane against a last-hitting opponent the same plans reach two waves only in some cases, with 5 to 7 minions. In mid, and from the own tower with the opponent absent, their first crash holds 3 or 4 minions of one wave. | Appears in 1 setting of 8 |
| Stack of two waves | No plan of the ten brings 12 minions to the tower, in either lane, from either start. The largest crash of a plan that is not a push holds 8 minions. The largest wave anywhere on the lane holds 10. | Does not appear. Unresolved. |
| Holding, M7's built state | No surplus and plan passes. The longest hold is 115 s (`k=4 hold, trim to 4`), with one retreat. | Fails. Unresolved. |
| Holding, clock-aligned state | Three surplus casters, hold and last-hit: 136 s [126.5 to 142.5] in the band, 9.5 s under the tower, one retreat at 30 percent health. With no champion: 121 s in the band and 17 s under the tower. A champion with twice the health and regeneration holds for 123.5 s [120.5 to 140] without a retreat and with 3 s under the tower. | Fails M7's test for both champions. The placeholder laner retreats. The durable one does not, but the control without a champion is in the band for 121 s too, so the band clause cannot tell them apart. |
| Bounce, side lanes | Top and bot: the front is back past the centre 51 s and 54.5 s after the crash in 5 of 5 runs, and the answering wave reaches the pusher's tower after 65 s. With M7's rules top bounced in some runs only. | Passes |
| Bounce, mid | In 0 of 5 runs is the front back within 120 s. In 2 runs it is back after 139 and 158 s. In 3 runs it is not back when the run ends at 600 s. | Fails M7's 120 s. Unresolved. Mid has no speed rule. |

M7's two verdicts, rerun unchanged on the M8 lane, are the same as in M7: no slow push and no freeze (`m7_tests_on_m8_lane.json`, `verdicts`). The largest thinned wave at M7's first tick in range is 7, against 5 with M7's rules.

### 5.5 A diagnostic: weaker minion blows

A diagnostic rule scales every minion blow on a minion. It is not a candidate for the lane. It asks how the verdicts move when minion fights last longer. The tests are M7's, unchanged. Top lane, opponent absent, 3 seeds.

| Scale of minion blows | Placed fight | Natural first-wave fight, mid | Largest crash of a plan that is not a push | Plans with a stack of 12, of 18 | The same by M7's first-tick measure | M7's freeze test | Clock-aligned hold without a retreat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1.0, the reference | 25.5 s | 31 s | 8 | 0 | 0 | Fails | None |
| 0.85 | 30 s | 36.5 s | 12 | 1 | 1 | Fails | None |
| 0.7 | 36 s | 44.5 s | 12 | 3 | 3 | Passes | 3 surplus casters, 137.5 s |
| 0.6 | 42 s | 52 s | 14 | 9 | 6 | Passes | 3 surplus casters, 122 s |
| 0.5 | 55 s | 61 s | 16 | 16 | 13 | Passes | 3 surplus casters, 137 s |

**What the table shows (Tested).** Stacks first appear at a scale of 0.85 and M7's freeze test first passes at 0.7. Both become more common as fights lengthen. M7's first-tick measure misses 3 of 9 stacking plans at a scale of 0.6 and 3 of 16 at 0.5.

**What it suggests (Inference).** The length of minion fights against the wave interval decides whether these behaviours appear. This fits the trace of section 5.2 and M7's own hypothesis (handoff 004, F4). It is not proven by this table, for three reasons.

- The diagnostic weakens only minion blows on minions, so champions and towers become stronger relative to minions at the same time.
- It acts evenly on every blow. Real timing effects, such as windup or projectile flight, would not.
- The independent review shortened the wave interval instead, at reference damage, and found stacks in 2 of 18 plans at 25 s and 13 of 18 at 21 s (Reported, that run is not in the repository). A second knob that moves the result the same way supports the inference and does not replace a real measurement.

### 5.6 What the omitted mechanics change

| Mechanic | Effect | Evidence |
| --- | --- | --- |
| Side-lane speed | Large. It makes side lanes bounce in every run and raises the thinned wave from 5 to 7. It does not produce a stack of 12. | `m7_tests_on_m8_lane.json`, `investigation.json` `bounce` |
| A cap of 1, 2, or 3 melee attackers per target | No placed fight changes by more than 1.5 s. Under every cap the largest crash stays at 8, no plan stacks, and M7's freeze test fails. Bodies that block movement are not modelled, so this bounds one effect of collision and not collision. | `investigation.json`, `fights` and `attacker_cap` |
| Pushing advantage, level lead 0.5 to 2 | It moves crashes toward the team that is behind. In an untouched top lane over 10 minutes, the leading team's wave reaches the enemy tower 3.8 times at a lead of 2 against 1.2 times at no lead, and the other team's 0.2 times against 1.2. The largest crash stays at 8 minions or fewer. | `investigation.json`, `level_lead` |
| Call for help | None in C2. No champion attacks a champion before C5. | `tests/test_lanes.py` |
| Current-health share switched off | A placed fight lasts 31.5 s. This is M7's flat-damage run. | `investigation.json`, `fights` |

### 5.7 What is known, what is not, and two measurements

**Read twice and equal to the ruleset** (Sourced): minion health 465 and 284, damage 11 and 21, attack speed 1.25 and 0.667, range 110 and 550, and the on-hit share of 2 and 3.5 percent of current health.

**Documented and not modelled:** the four items of section 4.3 from the second reading. Two of them bear on holding: how long minions keep a champion as their target, and that a champion in tower range is not attacked for standing in the path.

**Not documented anywhere I read:** timing below the level of a rule, such as attack windup, projectile flight, and the time bodies take to walk around each other. Each lengthens a real fight by an unknown amount.

Two measurements in a custom game on patch 26.22 bear on the open behaviours. Each has a value in the simulator.

| Measurement | The simulator's value |
| --- | --- |
| **A. The untouched first wave in mid.** Nobody touches the lane. When the minions of wave 2 reach the fight, count the minions of wave 1 that are still alive and note how healthy they look. If wave 1 is dead before wave 2 arrives, time the fight from the first blow to the last death. | Wave 2 arrives 29.5 s after the first blow. Six minions of wave 1 are alive, all nearly dead (7 percent of their health on average). Left alone, the fight would end 31 s after the first blow. |
| **B. The slow-push drill in top.** The laner kills the three casters of wave 1 and then only last-hits. Count the minions that reach the enemy outer tower and time their arrival from first contact. Note whether any of them is alive when the laner's next wave arrives. | 7 minions arrive 37.5 to 38 s after contact. All are dead 15 s later, about 5 s before the next wave arrives. |

| Real-game result | What it shows | What it does not show |
| --- | --- | --- |
| Both match | The lane's fight length and its reinforcement timing are right for these two cases. | That stacks and long freezes are rare in the real game. Placeholder champions, a lane without width, lateral slots, and the in-path rule are all Assumed, and each could suppress them. |
| Minions of wave 1 are clearly healthier in A, or the fight is clearly longer | Real minion fights are slower than the lane's. The diagnostic says stacks appear from a natural fight of about 36.5 s and M7's freeze from about 44.5 s. | Which timing detail is missing. That needs minion attack timing data, not a new rule about waves. |
| In B the stack survives until the next wave | The lane kills a crashed wave too fast, or lets it arrive too early. | The same. |

The other measurements of M7 section 5.6 stay useful and are in handoff 005 beside the simulator's values.

### 5.8 Incentive screen and tick sweep

**Incentives** (Tested, [`incentives.json`](../../experiments/m8/waves/results/incentives.json)). A scripted laner plays one wave mode for 5 minutes in each of 12 lane states. No mode earns most in every state. `push` earns most in 6 states, `last_hit` in 4, and `hold` in 2. `push` earns most in both states in which the opponent pushes and in three of the four that start after a crash at the laner's own tower. XP barely moves between the four modes that stay at the wave, 3,015 to 3,294, because a laner in range gets XP whoever kills. `hold` drops to between 2,196 and 2,705 in 7 of the 12 states, because the laner retreats and leaves XP range. The laner's numbers are placeholders, so this is a screen of the mechanics, not a claim about the game.

**Tick sweep** (Tested, `m7_tests_on_m8_lane.json`, `tick_sensitivity_m8_lane`). At a 0.5 s tick, 13 of 17 metrics are within 10 percent of the 0.125 s reference. At a 1.0 s tick, 10 are. The four that move at 0.5 s are the size of the thinned wave after an enemy crash (3, 4, 4, 6 minions at ticks of 0.125, 0.25, 0.5, and 1.0 s), the band time of a hold at three surplus casters (110, 106.5, 91, 101 s), the band time with no champion at four surplus casters (93, 111, 117, 93 s), and the band time under a push (12.9, 12, 10.5, 24 s). Creep score with both laners last-hitting is 0.92, 0.91, 0.90, 0.81. The 0.5 s tick stays the starting value. C7 owns the full sweep (risk RK2 of M7).

**An untouched lane is not stable.** Over 10 minutes with no champion, both outer towers stay untouched in 3 of 5 runs in mid and in 1 of 5 in top. The wiki's Minion page says the same of the game: without champions, one team's minions eventually win, and which team is random (Sourced). M7 listed this as an open worry. It is expected behaviour.

## 6. Assumptions, internal correctness, and real-game validation

**Assumed.** Nothing has checked these against the game.

- Every champion number: the five capability profiles, level growth of 8 percent, and the scripted laner of the wave experiments.
- Lateral slots, the hold line 300 units outside tower range, the stand-off of 550 units, and that a champion that stepped aside hits nothing.
- The keyed order of champions that attack at the same instant.
- The roam cap of 90 s and the refill of 0.25, and the end of assignments at 14:00 or with an outer tower.
- The support item's gold from 0:00, charges on a fixed clock, and range as the test for a ranged support.
- The two unstated details of the pushing advantage (section 4.2).
- The jungle paths and the sight terrain of M7 section 5.1, unchanged.

**Internally correct.** A test in this repository shows it, and a mutation run shows that the test can fail.

- The kernel contracts of section 3.3.
- The lane rules of section 4.1.
- The ledger and the bot-lane rules of section 4.6.
- The port of M7's lane (section 5.1).
- Across kernel, lane, and economy, the mutation runner breaks the code in 57 ways, and the tests catch all 57.

**Validated against the real game.** Nothing yet. Constants are Sourced, which means read from a document, not measured. The first real-game validation that M8 needs is the pair of measurements of section 5.7.

## 7. Requirements kept for later checkpoints

These came up in this campaign and belong to a later checkpoint. None is implemented.

| For | Requirement |
| --- | --- |
| C3 | Fountain healing, purchases, and Homeguard. `RECALL` already channels and ends on the fountain. `capability` already takes the upgrade count and ignores it. |
| C5 | **Regression requirement from M7's prototype (handoff 004, F10).** When two champions die on one tick, each killer gets its kill gold and XP, and a keyed draw on the tick picks the team with first blood. A test permutes the seat order and asserts equal rewards. The prototype paid only the killer that the code visited first. |
| C5 | Self-defence for a returning laner. `legal_mask` has one marked place where `FIGHT` against an enemy that is attacking the champion stays legal under every leash. |
| C5 | The world sets `harassing` on a champion that damages an enemy champion, so that minions answer the call for help. |
| C5 | One attack capacity per champion across minions, champions, camps, and towers (M7 section 7.4). Today the credit for lane hits lives in the lane. |
| C5 | Champion damage to towers, the backdoor reduction, tower shots on champions, and tower plates with their local gold. |
| C5, C6 | `FIGHT`, `SIEGE`, and `WARD` are in the action table and masked off. Each rule names the checkpoint that enables it. |
| C6 | `stance` gets the wave front that the champion's team sees, not the true front. The observation gains the lane and enemy fields with their leak tests. |
| C7 | The sweep over tick lengths and decision intervals, the throughput gate, and pinned replays of an integrated game. This campaign pins one kernel replay. |
| C8 | The complete hidden-state hypothesis generator of M7 section 9.3 and its three acceptance tests. Nothing of it exists in `riftgame`. |
| Open | A sixth wave mode that thins while it holds (M7, OQ11). The four documented minion details of section 4.3. Ranges by straight line between champions, towers, and minions near lane corners. |

## 8. How to rerun the evidence

Every command starts with `.venv/Scripts/python.exe` from the repository root (M7 section 13 has the setup).

| Command | What it shows | What it writes |
| --- | --- | --- |
| `-m pytest -q` | Every test of M7 and M8 | Nothing |
| `-m experiments.m8.waves.m7_tests` | M7's cases and verdicts on the M8 lane, the port check, the tick sweep. About 5 minutes. | `experiments/m8/waves/results/m7_tests_on_m8_lane.json` |
| `-m experiments.m8.waves.investigate` | Fights, arrivals, the plan search, holding, bounce, the level lead, the attacker cap, the fight-speed diagnostic. About 10 minutes. | `experiments/m8/waves/results/investigation.json` |
| `-m experiments.m8.waves.incentives` | The incentive screen. About 1 minute. | `experiments/m8/waves/results/incentives.json` |
| `-m experiments.m8.waves.trace "S0 fight 6v6" "m8 lane" 0 0.5 0 100` | A tick-level trace of one M7 case | Nothing |
| `-m experiments.m8.kernel` | The kernel measurements of section 3.3 | `experiments/m8/results/kernel.json` |
| `-m experiments.m8.mutations` | Breaks the code in a temporary copy and counts the tests that notice | Nothing |
| `-m experiments.m8.provenance` | Whether each M8 results file still matches the working tree | Nothing |
| `-m experiments.m7.provenance` | The same for M7. All five files stay current, because M8 changed no file that M7 loaded. | Nothing |
