# M8 foundation

**Status.** Two campaigns have run. Checkpoints C1 (kernel base), C3 (recall and purchases), C4 (jungle), and C5 (combat and death) are built and pass the criteria that M7 wrote for them. C2 (lanes and economy) is built and is not complete. Agents can now express a hold and a slow push through the action table, but reinforcements accumulate in 1 of 32 settings, a hold is sustained in 8 of 64, a bounce can be put down to a crash only in mid, and an untouched top lane drifts to one side (section 2). C6 to C8 have not started. Nothing was trained. [Handoff 005](../../handoff/005_m8_c1_c2.md) reports the first campaign and [handoff 006](../../handoff/006_m8_c2_corrections_c3_c5.md) the second.

**Date.** 2026-11-12.

**Builds on.** [`M7_architecture.md`](M7_architecture.md). This document does not repeat M7. It names the M7 section that a piece of M8 implements, and it states every place where M8 departs from M7.

**Evidence labels.** The labels are M7's. **Tested** names a test or a script in this repository. **Sourced** comes from the reference patch research. **Assumed** is a design choice or a placeholder number. **Reported** has no evidence in the repository. **Inference** is a conclusion drawn from tested facts. **Unresolved** marks a known limit.

## 1. Summary

- The kernel of M7 section 5 exists as reusable code in `riftgame/`: ten champions on the full map, a fixed tick with a separate decision interval, intents that end with an outcome, the role duty state, an observation boundary, snapshots, replays, and an invariant checker (section 3).
- One `LaneSim` class runs all three lanes. The second campaign changed four things in it. Every range inside a lane is now the straight line on the map. Two documented targeting exceptions near towers are in. Minion attacks have the cast times and missile speeds of the game's data files. A `LANE` action names what the champion hits and, apart from that, where it stands, so an agent can hold a wave and thin it at once (section 4).
- Every wave experiment about champions now runs a full world, and a plan only picks entries of the action table. Each result is compared with a lane that nobody touches. Over 8 champion settings and 5 seeds, a plan accumulates reinforcements in 1 of 32 settings, with a crash of 11 minions from three waves. A champion that holds keeps a larger wave out of its tower's range for three wave cycles in 8 of 64 settings, and in 7 of those only by thinning while it holds. After a crash the front comes back before an untouched lane's front does in 4 of 16 cases, all in mid (section 5.4).
- C2 is still not complete. No plan accumulates against an opponent that last-hits. No hold lasts longer than four wave cycles, and none works for a level 6 mid laner. With straight-line ranges an untouched top lane goes to blue's half within 100 s in every seed, because the route graph has one sharp corner node there. No lane rule, the new attack timing included, makes the behaviours appear, and the counts move with the tick length (sections 5.4 and 5.5).
- The acceptance criteria for waves were revised twice. The first revision was too loose, and an independent review showed it. The second compares every plan with a hard push and with an untouched lane. Twelve minions and 240 s are kept as reported marks that fail (section 5.3).
- Recall, fountain, purchases, and Homeguard (C3), camps, Scuttlers, shrine sight, and camp timers in team memory (C4), and per-tick fights, towers against champions, death, and kill rewards (C5) are built behind the interfaces of M7 section 5.11 (sections 6 to 8).
- Nothing is validated against the real game. Every champion number is a placeholder. Conclusions about recall timing, denial, and gank opportunities are provisional while wave fidelity is open (section 9).

## 2. Campaigns, phases, and progress

M8 has eight checkpoints (M7 section 10.1).

**Campaign 1, 2026-11-11.** Handoff 005 has the detail.

| Phase | Work | State |
| --- | --- | --- |
| P0 to P1 | Grounding, and the kernel (C1) | Done. Every C1 criterion passes. |
| P2 | `riftgame/lanes.py` as a port of M7's lane | Done. 998 of 998 metrics of M7's results file with M7's draw key. |
| P3 to P4 | Wave investigation with scripted champions, and lanes in the world (C2) | Built. Every criterion of M7's C2 row passes. Three wave behaviours did not appear. |
| P5 | Review and handoff 005 | Done |

**Campaign 2, 2026-11-12.** This campaign corrected C2 and built C3 to C5.

| Phase | Work | Acceptance | State |
| --- | --- | --- | --- |
| Q0 Ground | Read the documents and handoff 005. Capture the baseline. | 329 tests pass, 4 expected failures, all results files current. | Done |
| Q1 Action interface | A `LANE` action is (lane, mode, stand). | An agent can stand on the hold line and hit in any of the four modes. Tested in the lane and in the world. | Done |
| Q2 Lane rules | Straight-line ranges, the two targeting exceptions near towers, attack timing. | Each rule has a switch, a test, and a mutation. With M7's rules the lane stays bit-identical. | Done |
| Q3 Experiments through the action table | `experiments/m8/waves/agents.py` and `capabilities.py`. The scripted-champion sections of the old investigation are removed. | Every plan chooses action indices in a full world. Eight champion settings, three kinds of start. | Done |
| Q4 Criteria | Section 5.3. | Each revised criterion states what the old one got wrong, with a counterexample from a results file, and compares a plan with a lane that nobody touches. | Done, in a second revision after the review |
| Q5 Traces | Attack timing counters, a count of overlapping bodies, an untouched-lane baseline, five diagnostics, a tick sweep. | Reported. No rule is added to the lane from a diagnostic. | Done |
| Q6 C3 | Recall, fountain, purchases, Homeguard. | The C3 criteria of section 6.3. | Done. All pass. |
| Q7 C4 | Camps, Scuttlers, shrine sight, camp memory, a scripted jungler. | The C4 criteria of section 7.3. | Done. All pass. |
| Q8 C5 | Fights, lockdown, towers and champions, death, kill rewards. | The C5 criteria of section 8.3. | Done. All pass. |
| Q9 Evidence and handoff | Rerun every results file, the mutation runner, an independent review, handoff 006. | Every number comes from a results file that the checker reports as current, or carries the label Reported. | Done |

**C2 is not complete.** The owner requires freezing, slow pushing, crashing, and bouncing as capabilities, and C2 may not be called complete while one is unresolved. A crash works. The other three are unresolved.

1. **Slow push.** A plan accumulates reinforcements in 1 of 32 settings, and in none against an opponent that last-hits. The standard drill, killing the three casters of the first wave, brings fewer minions than a hard push.
2. **Freeze.** A hold is sustained for three wave cycles in 8 of 64 settings, for four in one, and never longer. No plan holds a wave for a level 6 mid laner.
3. **Bounce.** The front comes back after a crash in 15 of 16 cases, and before an untouched lane's front in 4, all in mid. After a hard push of the first wave mid resets to the centre.
4. **The lane itself.** With straight-line ranges an untouched top lane goes to blue's half at 97 s in every seed. The counts above also change with the tick length.

## 3. Kernel base (C1)

### 3.1 What exists

| Module | Owns | Checkpoint |
| --- | --- | --- |
| [`world.py`](../../riftgame/world.py) | The state, the eight-step tick of M7 section 5.2, `Config`, snapshots, the digest, the invariant checker | C1 |
| [`champions.py`](../../riftgame/champions.py) | Seats, placeholder capability and progressions, the action table, intents with a rule per kind, the duty state, the fountain's rules | C1, C3 |
| [`vision.py`](../../riftgame/vision.py) | `observe`, `legal_mask`, team sight, team memory | C1, C4, C5 |
| [`harness.py`](../../riftgame/harness.py) | The policy interface, scripted policies, replays | C1, C4, C5 |
| [`lanes.py`](../../riftgame/lanes.py) | Minions and towers of one lane, and the stance of a champion at a wave | C2, C5 |
| [`economy.py`](../../riftgame/economy.py) | Gold, XP, the support item, and the champion inputs of a lane | C2, C4 |
| [`jungle.py`](../../riftgame/jungle.py) | Camps, Scuttlers, and their fights | C4 |
| [`combat.py`](../../riftgame/combat.py) | Champion attacks and kill rewards | C5 |

The world always holds ten champions on the full route graph. Nothing in `riftgame` has a single-lane mode.

### 3.2 Contracts, and where the kernel departs from M7

The kernel implements M7 sections 5.2 (clock and tick order), 5.3 (state), 5.10 (roles), 6.3 (observation and mask), 7 (actions), and 8 (randomness and snapshots). It departs in these places.

| Departure | Reason |
| --- | --- |
| The roam allowance is a set of `Config` fields: the cap, the refill, the end time of assignments, whether a fallen outer tower ends one, and a switch that turns the restriction off. | Owner decision: the allowance is an experimental restriction, not a permanent rule. |
| A laner with no allowance may choose `LANE` for its lane, `RECALL`, and `MOVE` to a node of its lane, to its own base, or to its own fountain. All of these count as returning, not roaming. From C5 on it may also `FIGHT` an enemy that is attacking it. | Owner decision: a returning champion keeps retreat and self-defence choices. |
| The action table has 107 entries. A `LANE` action is (lane, mode, stand), with four modes and two stands (section 4.4). Targets are named in the acting team's frame. | M7 said about 95, with five modes. |
| An observation position is a `Place`: a lane with the distance from the team's own end, or one edge off the lanes. The mirror test is exact only for lane positions, bases, and fountains. | The map has no mirror symmetry that keeps roles. |
| The digest covers the state and not the config. | The decision-interval test compares two runs that differ only in the config. |
| `WARD` is in the table and masked off. | Wards are C6. |

### 3.3 Acceptance criteria of C1

The criteria are those of M7 section 10.1 for C1, plus the owner's two corrections on roles. Every row is Tested. The roam numbers are in [`experiments/m8/results/kernel.json`](../../experiments/m8/results/kernel.json).

| Criterion | Result | Test |
| --- | --- | --- |
| A run at decision interval n equals a run at interval 1 that keeps between decisions, for n of 2, 4, and 10, with intents that complete inside the run | Equal digest for digest over 600 ticks, with scripted junglers among random laners. The test requires `ARRIVED`, `ABSENT`, `CLEARED`, and `RECALLED` to occur inside each run. | `tests/test_world_clock.py` |
| A redirected move continues from the current position, and distance walked is speed times time | Every tick's walk is speed times the tick, before and after the redirect | `tests/test_world_clock.py` |
| Restore and replay give equal digests at every tick for 1,000 ticks | 1,000 of 1,000. A pickled snapshot also restores in a new process under two hash seeds. | `tests/test_world_snapshot.py` |
| No laner roams longer than the cap plus one decision interval at a stretch | Holds at both clock settings | `tests/test_world_roles.py` |
| Each laner's roaming share after its first allowance is spent stays within 20 percent plus one decision interval over the window | Holds at both clock settings | `tests/test_world_roles.py` |
| Junglers are never restricted. No position changes by more than the champion's speed times the tick, except on death and on recall. | Both hold in 840 s games in which champions die. The speed is the champion's speed on that tick, Homeguard included. | `tests/test_world_roles.py`, `tests/test_world_soak.py` |
| The restriction is configurable | With it off, no laner is ever sent home. With a cap of 30 s and a refill of 0.5, the bounds follow the configured values. | `tests/test_world_roles.py` |
| A returning laner keeps retreat choices | With an allowance below zero and off its lane, it may walk to its own tower, base, or fountain, and the allowance does not drain | `tests/test_world_roles.py` |
| A soak of random legal actions runs 10 games with no invariant failure | 10 games of 600 s, two policies, two clocks. No failure. | `tests/test_world_soak.py` |
| The invariants | Each one is broken on purpose and the checker raises. C3 adds gold equal to the ledger less the price of the upgrades. C4 adds the camp faults. | `tests/test_world_soak.py`, `tests/test_recall.py`, `tests/test_jungle.py` |
| Leak test for the observation boundary | Every field of every enemy champion is changed, and so are the minions and towers of every lane and every camp fact that the team has not seen. The team's five observations and masks stay identical. | `tests/test_world_observation.py`, `tests/test_economy.py` |
| A replay reproduces its digests, and one digest is pinned | 600 of 600. The pin moves with every change to the state, so it moved in each phase of this campaign. | `tests/test_world_snapshot.py` |

**Measured, not criteria.** `kernel.json` holds the throughput of one process over 600 s games, and section 9 gives the figures. M7's gate of 300 simulated seconds per wall second is measured at C7 on the integrated game.

## 4. Lanes and economy (C2)

### 4.1 The lane model

`riftgame/lanes.py` holds one class, `LaneSim`. It owns a lane's minions, its six towers, and its wave clock, on the lane coordinate of M7 section 5.1. A champion enters a lane tick as a `ChampionInput`. Everything that leaves the lane is an event. The world applies the events (M7 section 5.11).

`LaneRules` names each optional rule. `M8_LANE` is the lane that M8 ships. `M7_LANE` switches off what M7 did not model, so that M7's results can be reproduced. Five fields are diagnostics and are off in both.

| Rule | In the M8 lane | Status |
| --- | --- | --- |
| Waves on the reference clock, with reference stats and composition | Yes | Sourced |
| Target priority: enemy minion, then tower, then a champion in the path | Yes, at acquisition and on every retarget | Sourced |
| A blow on a minion adds 2, 3.5, or 5 percent of the target's current health | Yes | Sourced, read twice |
| Lateral slots that break ties between targets | Yes | Assumed. The wiki states it for the melee minions of the first waves only (section 4.2). |
| Side-lane speed for wave 2 and later, until 14:00 | Yes | Sourced, read twice |
| Call for help: minions within 1,000 units turn on an enemy champion that attacks an allied champion, unless they attack a tower | Yes. The world sets the trigger from C5 on. | Sourced |
| Pushing advantage from 3:30, by team level lead and tower lead | Yes | Sourced |
| Three tower tiers. Only the front tower fights and takes damage. | Yes | Sourced |
| A wave past the last lane tower is removed at the enemy base | Yes | Assumed stand-in until M10 |
| Champions that attack at the same instant are served in an order drawn by key, not by seat | Yes | Assumed |
| `straight_ranges`: every range inside the lane is the straight line on the map. Marching stays on the lane coordinate. | Yes, new in campaign 2 | Owner requirement, and the interaction measure of M7 section 5.1 |
| `tower_shelter`: a champion inside the range of a standing lane tower is not attacked for standing in the minions' path | Yes, new in campaign 2 | Sourced. That any standing lane tower counts is Assumed. |
| `first_wave_call`: minions of the first wave answer a call for help while they attack a tower | Yes, new in campaign 2 | Sourced |
| `attack_timing`: a blow leaves the minion one cast time after the attack starts, and a caster's or a siege minion's blow then flies to its target | Yes, new in campaign 2 | Sourced constants (section 4.2). The cancel and the lost missile are Assumed. |
| `melee_cap`: at most n melee minions on one target | Diagnostic, off | Section 5.5 |
| `minion_damage_scale`: scales minion blows on minions | Diagnostic, off | Section 5.5 |
| `free_cancel` and `missiles_turn`: a cancelled cast costs nothing, and a missile to a dead target lands on what its shooter can reach | Diagnostics, off | Section 5.5 |
| `detour_s`: a melee minion that turns to a new minion target loses this long before its cast | Diagnostic, off | Section 5.6 |

The added constants live in a second ruleset file, [`patch_26_22_m8.toml`](../../riftgame/rulesets/patch_26_22_m8.toml). `patch_26_22.toml`, `map_summoners_rift.toml`, `map.py`, `ruleset.py`, and `rng.py` stay byte-identical, because M7's results files record their hashes.

### 4.2 The rules that campaign 2 added, and what the sources say

**Straight-line ranges.** M7 section 5.1 measures movement by the route and interaction by the straight line. Campaign 1 left every range inside a lane on the lane coordinate. Around the corner of top lane, two points 290 units either side of the corner are 580 units apart along the lane and 534 in a straight line. Campaign 2 first changed only the ranges between champions or towers and minions. That made things worse: a passive carry in bot lane took 568 damage in five minutes where it had taken 44, because a caster behind the corner counted enemy minions along the lane, found none in range, and turned on the champion that it measured by the straight line (Reported, a scratch run that is not kept). One measure for every interaction removes the inconsistency. Acquisition, attack, tower, and call ranges all use the map coordinates of the two units. Only marching uses the lane coordinate (Tested, `tests/test_lanes.py`, two corner tests). The hold line, the stand-off, and the experiments' band and tower checks are still placed along the lane. Towers stand on straight stretches, so that differs from the straight line by 16 units at most (Reported by the review).

**The rule has a side effect that is a defect.** An untouched top lane now goes to blue's half within 100 s in every seed, where it stayed at the centre before (section 5.4). The route graph gives top lane one sharp corner node, 295 units from where the waves meet, and the straight line cuts that corner unevenly for the two teams. The port check cannot see this, because M7's rules switch the straight line off.

**Minion targeting, read again.** The wiki's Minion page was read a third time on 2026-11-12 through a fetch tool, sentence by sentence for its Behavior section. The readings of campaign 1 were less exact on three points.

| What the page says (Sourced) | The M8 lane |
| --- | --- |
| A champion that stands in the minion's path triggers a call for help when no other target is in attack range and the champion is outside a turret's range. | A minion attacks a champion in its path when no enemy minion and no tower is within 500 units, and the champion is outside the range of every standing tower of the lane. Using the acquisition range and not the attack range is Assumed. |
| A champion that damages an enemy champion triggers a call for help. With several sources, minions take the closest. | The `harassing` flag of a champion's lane input. The world sets it from C5 on. |
| Except for the first wave, a call for help is ignored by minions that are attacking a turret. | Modelled, with the exception. |
| A minion switches only to a target of higher priority, and cannot take a new target of the same priority. | A minion keeps a living minion target in reach. A minion on a champion turns to an enemy minion that comes within 500 units. |
| Minions re-evaluate their target between attack windups, "every few seconds". | The lane re-evaluates on every tick. Assumed, no number is given. |
| If an enemy champion stops attacking an allied champion, minions keep targeting it "for a short time". | A window after the champion's last blow (C5, section 8.2). The length is Assumed. Campaign 1 read this as persistence on any champion target. The page ties it to the call for help. |
| Targets must be within 500 units. A call for help reaches 1,000. | Both. The game's data file gives the caster an acquisition range of 700 and the melee minion none. The lane keeps 500 for all. Unresolved. |
| First-wave minions pass through units for 28 s in the side lanes and 18 s in mid, and ignore champions until one walks "much closer" or the waves meet. | Not modelled. |
| When the first waves meet, the melee minions spread their attacks across the three enemy melee minions "regardless of distance". | The lateral slots do this for every wave. For the first wave it is Sourced. For later waves it stays Assumed. |
| A minion that loses sight of its target takes a new one. A minion below 0.35 percent health gets 0.066 s of grace against a minion's killing blow. | Not modelled. |
| Minions respect unit collision. The minion pages give a pathing radius of 35.74 and a gameplay radius of 48. | Not modelled. Section 5.6 counts where bodies would overlap. |

**Attack timing.** In campaign 1 a minion's blow landed at the instant its attack was ready, and the first blow landed on arrival. The game's character data files (Community Dragon 16.22, read through the fetch tool on 2026-11-12) give each lane minion a cast time and, for ranged minions, a missile speed.

| Minion | Attack period | Cast time | Missile speed |
| --- | --- | --- | --- |
| Melee | 0.8 s | 0.393 s | none |
| Caster | 1.5 s | 0.47 s | 650 |
| Siege | 1.0 s | 0.30 s | 1,200 |

In the M8 lane an attack starts when the minion is ready and its target is in reach. The blow leaves the minion one cast time later. A melee blow lands then. A missile lands after its flight. Two details have no source and are Assumed, from how the game treats any attack: a cast whose target dies or leaves reach is cancelled and starts again on a new target, which costs the part of the cast spent on the old one, and a missile whose target dies in flight is lost. Tower shots and champion hits stay instant (Assumed simplification). A caster 500 units from its target lands its first blow 1.24 s after it starts, where campaign 1 landed it at once (Tested, `tests/test_lanes.py`, four timing tests).

**Carried over from campaign 1.** Side-lane speed, the pushing advantage, the priority on every retarget, and the keyed order of simultaneous champion attacks are unchanged. Handoff 005 has their history.

### 4.3 Reference rules that the lane still leaves out

- From M7's list: minion speed growth after 10:00, the smaller waves of the mid game, bounties, role quests, the support item's later tiers and its income from hitting champions.
- From the wiki readings: melee minion armor (0 at the start, 20 late), the first wave's ghosting and its indifference to champions, the retarget cadence, the death grace, and the caster's acquisition range of 700 in the data file.
- Unit collision. Bodies that block each other need a lane with width.
- Tower shots have no cast time or missile flight.

### 4.4 The `LANE` action: what the champion hits, and where it stands

M7 section 5.6 gave a `LANE` action five modes, and one of them, `hold`, fixed both the stand and the hits: a holding champion last-hit. M7's own freeze plans thin a wave while they hold it, so the experiments used a flag that agents did not have. A `LANE` action is now a triple.

| Part | Values | Meaning |
| --- | --- | --- |
| Lane | `top`, `mid`, `bot` | The role rule leaves a laner only its home lane. |
| Mode | `passive`, `last_hit`, `thin`, `push` | What the champion hits: nothing, only a minion that one hit kills, casters first, or everything with its area damage. |
| Stand | `wave`, `hold` | Where it stands once its own wave is gone. `wave` steps aside, or for `push` stays in the path at its attack range. `hold` stays in the path on the line that stops the enemy lead minion 300 units outside its own tower's range. |

While the waves are in contact, every action stands at the wave. That gives 24 `LANE` entries where M7 had 15. It is the smallest change that separates standing from hitting: one flag beside the mode. A sixth mode would have named one more combination and left the others out. `stance(lane, team, mode, attack_range, front, hold)` returns the stand and whether the champion is in the minions' path, and the world and the experiments call the same function (Tested, `tests/test_lanes.py`, `tests/test_world_intents.py`).

No action is called freeze or slow push. Whether a held wave stays is decided by the minions.

**For C6.** `stance` takes the front as an argument. Today the world passes the lane's true front. Once fog exists, the world has to pass the front that the champion's team sees (M7 section 6.3).

### 4.5 Gold, XP, and the ledger

`riftgame/economy.py` owns what a champion earns. Each champion has an unspent gold total and a ledger with one entry per source.

| Ledger entry | Paid when | Status |
| --- | --- | --- |
| `STARTING` | 500 at the start | Sourced |
| `PASSIVE` | 20.4 per 10 s from 1:05, to every champion | Sourced |
| `MINION` | A minion's gold, once. To the champion that lands the killing blow, or to the support's nearest ally when a charge shares the kill. | Sourced |
| `SUPPORT_ITEM` | 3 per 10 s to the support, plus 18 for each charge used | Sourced. The start at 0:00 is Assumed. |
| `CAMP` | A camp's gold, to its killer (section 7) | Sourced amounts |
| `KILL`, `ASSIST`, `PLATE`, `TOWER` | Kill gold to the killer, the assist pool to the assisters, plate gold and tower gold to the champions that the rules of section 8.1 name | Sourced amounts |

Gold spent is not stored. It is the price of the upgrades a champion owns, and the invariant checker asserts that unspent gold equals the ledger less that price.

### 4.6 Acceptance criteria of C2

The criteria are those of M7 section 10.1 for C2. Every row is Tested unless it says otherwise.

| Criterion | Result | Evidence |
| --- | --- | --- |
| The three wave experiments run on the M8 lane with M7's pass tests unchanged | Done. M7's verdicts are unchanged: no slow push and no freeze by M7's tests, with M7's scripted champion. | `m7_tests_on_m8_lane.json` |
| Each measurement of M7 section 5.6 stands beside the simulator's value where someone has taken it | Nobody has taken one. Section 5.7 lists the simulator's values. | Section 5.7 |
| No rule is added to produce a freeze or a slow push | The lane gained documented rules and the timing constants of the game's data files. The three diagnostics are off in the lane that ships. | Section 4.1, `tests/test_lanes.py` |
| Minion conservation, mirror symmetry, gold only for a champion's own killing blow, the XP split, independence between lanes | Hold | `tests/test_lanes.py`, `tests/test_economy.py` |
| First waves meet at the time that route length and minion speed give, within one tick | 51.5 s in mid and 60.5 s in top and bot | `tests/test_lanes.py` |
| In bot lane each minion's gold is paid at most once. The pair's XP is 1.3 times a solo laner's within 2 percent. The support item's gold is counted apart. | Hold | `tests/test_economy.py` |
| An incentive screen over at least 10 lane states, with no pass condition | 12 states and the 8 `LANE` actions, in a full world. No action earns most in every state. | Section 5.8 |
| The tick sweep of risk RK2 is reported | 9 of 17 of M7's metrics within 10 percent at 0.5 s, and the world-driven verdicts at 0.25 s | Sections 5.5 and 5.8 |

## 5. Wave behaviour through the action table

Every number in this section is at a 0.5 s tick over 5 seeds unless it says otherwise. A range in brackets is the minimum and maximum across seeds. The results files are in [`experiments/m8/waves/results/`](../../experiments/m8/waves/results/).

### 5.1 The port still reproduces M7

[`m7_tests.py`](../../experiments/m8/waves/m7_tests.py) runs M7's 103 wave cases on the lane. With `M7_LANE` and M7's draw key, 998 of 998 metrics equal M7's results file (Tested, `port_check_with_m7_draw_key`). A separate check stepped the lane under M7's rules beside the lane of the last commit for 600 s on 3 seeds, and every minion's position and health agreed on every tick (Reported, that script is not kept).

### 5.2 How the experiments run now

[`agents.py`](../../experiments/m8/waves/agents.py) stages a full world of ten champions. The lane's champions stand at their outer towers at a chosen level, on both teams, so that no team leads in level. A plan is a function from what a laner knows at its wave to a `LANE` action, called on decision ticks every 2 s. It knows its own health, its own caster kills, and the minion counts within 1,500 units of the front. The world does the rest: the walk, the stance, the hits, minion damage, death.

The plans use only actions that an agent has. They use more information than an agent has today: the observation has no lane fields until C6, and the plans read the true front and exact counts of both teams' minions near it. The staging sets a champion's level, place, and the clock at the start, and the holding cases add the surplus casters during the run. Nothing else is edited in a run. Below 30 percent health a laner walks to its own outer tower with a `MOVE` and comes back above 60 percent.

The champions are the profiles of `riftgame.champions`, which are placeholders. A level goes with a clock: level 1 from 0:00, level 3 from 2:30, level 6 from 6:00. The lanes start empty at that clock, so the minions have that time's stats and siege waves.

| Champion setting | Lane |
| --- | --- |
| Top at level 1, 3, and 6 | top |
| Mid at level 1, 3, and 6 | mid |
| Carry alone at level 3, and carry with a support that stands with it and hits nothing | bot |

Campaign 1's scripted champion had 30 armor, a pushing area damage of 70 per second, and an opponent that could not die and jumped to its spot. None of that is left in the experiments about champions. M7's own cases keep it, because they are the port check.

### 5.3 Revised criteria, and the evidence against the old ones

The owner asked for criteria that keep the meaning of each capability: sustained wave control, reinforcement accumulation, delayed crashes, and bounce. A first revision in this campaign was too loose, and the independent review showed where (handoff 006, §3.5). The criteria below are the second revision. Each compares a plan with a lane that nobody touches, because an untouched lane does not stand still (section 5.4).

| Capability | Old criterion | What is wrong with it | Criterion now |
| --- | --- | --- | --- |
| Crash | A hard push reaches the tower before the second enemy wave can. | Nothing. | Kept. |
| Delayed crash | A thinning plan reaches the tower later than a push, with 12 minions. | Two properties in one verdict. | Its own verdict: a thinning plan's first crash comes later than the push's in every seed. This is a weak property, since thinning is slower than pushing by construction. |
| Reinforcement accumulation | 12 or more minions near the lead at the first tick in tower range. | Twelve is two full waves of six. A wave with a siege minion has seven, a thinned wave has lost some of its own, and a crash can hold parts of three waves. The largest crash in the results holds 11 minions of three waves. A bar of exactly 12 calls that no stack. | In every seed the plan's largest crash holds, at its largest moment, at least three minions from each of two spawn waves, and more minions than the largest crash of a hard push and of a lane with no laner in the same setting. The count of 12 is reported beside it. |
| Sustained wave control | The front stays within 1,500 units outside the tower's range for over half of 240 s, and both controls stay below half. | The band does not measure a hold. With no champion the front was in the band for 214 s of 240 against a last-hitting opponent in mid, while the enemy wave reached the tower in every cycle and dealt 445 damage to it. The control clause also blocked the test at three of five surplus sizes (handoff 005, F9). | A wave cycle of 30 s is held when the front is in the band for at least half of it and the enemy wave is never in the tower's range during it. A hold plan sustains control when, in every seed, the champion does not die, the first three cycles are held, and that is more cycles than no champion, a laner that last-hits with its wave, or a laner that pushes holds in any seed. |
| Bounce | After a hard push of one wave, the contact point is back past the centre within 120 s, in every run, in mid and top. | One wave of six is the weakest crash. A lane that meets again exactly at the centre counted as not bounced without being named. And an untouched top lane goes to one side by itself, so a return there proves nothing about the crash. | After a crash, the front comes back more than 100 units past the centre in every run, and in every run before the front of the same lane with no laner gets there. The crash is tried with one hard-pushed wave and with a thinned wave. A lane that meets again within 100 units of the centre is called a reset. |

**What these criteria still choose.** Three cycles is 90 s, where M7's test asked for more than half of 240 s. No counterexample supports that cut. It is where the results have something to show: some hold lasts one cycle in every seed in 52 of 64 settings, two in 40, three in 15, four in 1, and none lasts longer. Three minions per wave and 100 units are choices too. All are named constants in [`capabilities.py`](../../experiments/m8/waves/capabilities.py). Eight strict expected failures in [`test_behaviours.py`](../../experiments/m8/waves/test_behaviours.py) keep the unmet bars in view: 12 minions, the slow-push drill, accumulation against a last-hitting opponent, a hold for all 240 s, a hold for a level 6 mid laner, a mid bounce after a one-wave crash at 0:00, a top-lane bounce that beats the untouched lane, and an untouched top lane that stays at the centre.

### 5.4 Results

**An untouched lane first** (`investigation.json`, `untouched`, 300 s, no champion). Everything below is read against this.

| Lane | With the M8 lane | With ranges along the lane |
| --- | --- | --- |
| Top | The front stands more than 100 units on blue's half at 97 s, in 5 of 5 seeds. Red's wave reaches blue's outer tower once or twice, with 8 minions [7 to 12] at most. | The front never leaves the centre, and no wave reaches a tower. |
| Mid | The front leaves the centre in 2 of 5 seeds, at 243 s. | The same. |
| Bot | The front leaves the centre in 1 or 2 of 5 seeds. | The same. |

So the straight-line rule of section 4.2 tips an untouched top lane toward blue's tower within the first 100 s, the same way in every seed. The cause is the route graph (Inference from the table): top lane has one sharp corner node, 295 units on blue's side of the point where the waves meet, and a straight line cuts that corner for one team's formation and not for the other's. The real lane's corner is rounded and symmetric. With ranges along the lane the corner did not matter. This is a defect of the lane that ships, introduced in this campaign, and it stays open (section 10).

**Accumulation and delay** (`capabilities.json`, `stacking`). Seven plans, a hard push, and an absent laner. Two starts (first contact, and the moment an enemy push reaches the laner's tower), an opponent that is absent or last-hits, 8 champion settings: 32 settings in all.

| Result | Value |
| --- | --- |
| Settings in which some plan accumulates reinforcements | 1 of 32 |
| That setting | Top, level 1, from the own tower, opponent absent, `thin 3, then passive`: 11 minions [11 to 11] from three waves, three of them from the second-largest wave, 76.5 s after the plan starts. The hard push there brings 7 at most, at 41.5 s. With no laner the lane brings 9 [8 to 10]. |
| The same, opponent last-hits | 0 of 16 |
| Plans with a crash of 12 or more | None |
| The slow-push drill: top, level 1, from first contact, kill 3 casters, then last-hit | 7 minions 38.5 s after contact, six of wave 2 and one of wave 1. The hard push there crashes first with 5 at 18 s and brings 9 of two waves at 30 s. The drill does not accumulate. |
| Settings in which some thinning plan delays the first crash | 32 of 32 |

**Holding** (`capabilities.json`, `holding`). The experiment places 2, 3, 4, or 6 surplus enemy casters at the hold line when the laner's wave arrives, and the opponent is absent or last-hits: 64 settings, 7 hold plans and 3 controls each, 240 s.

| Result | Value |
| --- | --- |
| Settings in which some hold plan sustains control | 8 of 64 |
| By champion setting, of 8 each | Top 1, 0, 1 at levels 1, 3, 6. Mid 2, 1, 0. Carry alone 1. Carry and support 2. |
| Settings in which some hold lasts at least 1, 2, 3, 4 cycles in every seed | 52, 40, 15, 1. None lasts 5. |
| With no champion, cycles held | 0 in 49 settings, 1 in 7, 2 to 4 in 8 |
| With a laner that last-hits with its wave | 0 in 39 settings, 3 or more in 8 |
| Longest hold | 4 cycles: mid, level 1, 2 surplus casters, opponent last-hits, `hold, thin over 1`. No retreat, lowest health 34 percent. No champion and a laner with its wave hold 0 cycles there. |
| Sustaining plans | In 7 of the 8 settings only plans that thin or trim while they hold sustain control. `hold, last hit`, the only hold that the old action table could express, sustains in 1. |

**Bounce** (`capabilities.json`, `bounce`). A laner follows a plan until its wave is in the enemy tower's range, then leaves. Seconds from the crash until the front is back more than 100 units past the centre, and the same for the lane with no laner.

| Champion setting | After a hard push of one wave | After `thin 3, then last hit` | The untouched lane gets there |
| --- | --- | --- | --- |
| Top, level 1 | 90.5, 5 of 5 runs | 69.5, 5 of 5 | 17.5 to 22.5 s after the crash time, 5 of 5 |
| Top, level 3 | 53, 5 of 5 | 48.5, 5 of 5 | 18 to 22.5, 5 of 5 |
| Top, level 6 | 109, 5 of 5 | 44, 5 of 5 | 13 to 37.5, 5 of 5 |
| Mid, level 1 | 267 in 2 of 5 runs. The other 3 reset to the centre. | 61, 5 of 5 | 254 to 267 in 2 of 5 |
| Mid, level 3 | 148.5 [60.5 to 149.5], 5 of 5 | 47.5, 5 of 5 | 138 to 149.5, 5 of 5 |
| Mid, level 6 | 46.5, 5 of 5 | 34, 5 of 5 | Never |
| Carry alone, and carry with support, level 3 | 53.5, 5 of 5 | 49, 5 of 5 | 38 to 43 in 2 of 5 |

The front comes back in every run in 15 of 16 cases. It comes back before the untouched lane's front in 4: mid at level 1 and level 3 after a thinned-wave crash, and mid at level 6 after either crash. In top and bot the untouched lane is there first, so those returns say nothing about the crash.

**Why mid resets at 0:00** (Tested, one traced run). The level 1 mid laner crashes 5 minions into the tower 63 s into the game. The tower kills them before red's second wave arrives. Both second waves then walk the same distance, meet at the exact centre with six minions each, and stay equal for about two minutes, until tie-breaking draws separate them. Whether a real mid lane resets after a first-wave crash is unknown.

### 5.5 Diagnostics: one rule at a time, and the tick

A diagnostic changes one lane rule for one table. It shows which rule a verdict rests on. It is not a candidate for the lane. Two champion settings (top at level 1, mid at level 3), 3 seeds, 8 stacking settings, 8 holding settings with 3 and 4 surplus casters, 4 bounce cases (`capabilities.json`, `diagnostics`).

| Lane | Untouched first-wave fight, mid and top | A plan accumulates (a thinning plan) | Largest crash (with no laner) | A hold sustains (longest, cycles) | Bounces in every run (before the untouched lane) |
| --- | --- | --- | --- | --- | --- |
| The M8 lane | 33 s, 34.5 s | 1 (1) of 8 | 11 (10) | 2 of 8 (3) | 4 (1) of 4 |
| Blows land at once | 31 s, 31 s | 1 (0) | 9 (8) | 5 (8) | 3 (1) |
| Ranges along the lane | 33 s, 33 s | 0 (0) | 8 (6) | 2 (3) | 3 (3) |
| No tower shelter | 33 s, 34.5 s | 1 (1) | 11 (10) | 2 (3) | 4 (1) |
| At most 2 melee minions on a target | 33 s, 34.5 s | 2 (1) | 11 (10) | 3 (3) | 3 (0) |
| A cancelled cast costs nothing | 33 s, 34.5 s | 0 (0) | 11 (10) | 2 (3) | 3 (1) |
| A missile to a dead target turns to another | 33 s, 33 s | 1 (1) | 9 (9) | 3 (4) | 3 (1) |
| Both of those | 33 s, 33 s | 1 (0) | 10 (8) | 4 (3) | 3 (1) |
| Detour of 0.3 s | 33 s, 34.5 s | 1 (1) | 11 (8) | 3 (3) | 3 (1) |
| Detour of 0.6 s | 33 s, 34.5 s | 1 (0) | 10 (10) | 4 (3) | 3 (1) |
| Minion blows at 0.85 | 38 s, 39.5 s | 0 (0) | 11 (10) | 4 (3) | 4 (0) |

**What the table shows.** No rule produces the behaviours. Every variant moves a count by a few settings at most, and not in one direction. With blows that land at once, more holds are sustained than in the M8 lane, and one lasts all eight cycles. Attack timing is therefore a sourced correction of how long fights last. It is not what makes a hold or a stack appear. The two unsourced details of timing each move a count by one or two. Ranges along the lane remove the one accumulating setting and make three of four bounces beat the untouched lane, because that lane then stays at the centre. Weaker minion blows, the diagnostic that the first campaign built its inference on, lengthen the fight by 5 s and leave no accumulating setting under these criteria.

**Tick length** (`capabilities.json`, `tick_sweep`). The same counts at two ticks, with a decision every 2 s at both.

| Tick | A plan accumulates (a thinning plan) | Largest crash | A hold sustains (longest, cycles) | Bounces in every run (before the untouched lane) |
| --- | --- | --- | --- | --- |
| 0.5 s | 1 (1) of 8 | 11 | 2 of 8 (3) | 4 (1) of 4 |
| 0.25 s | 1 (0) | 9 | 2 (3) | 3 (0) |

The one thinning plan that accumulates at 0.5 s does not at 0.25 s, and the largest crash falls from 11 to 9. The fight lengths do not explain that: a placed fight of six against six lasts 28 s at 0.5 s and 27.25 s at 0.25 s (Reported, a run outside the results files). The mechanism is unknown. The reviewer measured that 80 percent of the blows released in a tick come from casts started in an earlier tick, so the path that carries a cast across ticks is a candidate (Reported). C7 owns the sweep over tick lengths (M7 risk RK2), and until then every count in section 5.4 is a count at 0.5 s.

### 5.6 Attack timing and movement obstruction, from traces

The owner asked for traces of attack timing and movement obstruction, and noted that a cap on attackers does not test obstruction.

**Attack timing.** The lane counts cancelled casts and lost missiles. In an untouched lane over five minutes (`investigation.json`, `attack_timing`):

| Lane | Minion deaths | Casts cancelled | Missiles lost |
| --- | --- | --- | --- |
| Mid | 104 | 43 | 46 |
| Top | 99 | 89 | 79 |

A placed fight of six against six lasts 28 s with timing and 25.5 s without. The untouched first-wave fight lasts 33 s in mid and 34.5 s in top, against 31 s. When wave 2 reaches the fight in mid, 29 s after the first blow, the six minions of wave 1 that are alive hold 23 percent of their health on average, against 7 percent before. Those are the effects of timing that this campaign can stand behind. Section 5.5 shows that the wave verdicts do not follow from them.

**Movement obstruction.** The lane has no bodies, and two bodies of the sourced pathing radius cannot stand within 71.5 units of each other in one lateral slot. The experiments count where the lane puts them there.

| Run | Minions that overlap an ally, share of minion ticks in contact | Most melee minions on one target |
| --- | --- | --- |
| Untouched mid lane, 5 minutes | 1.2 percent | 2 |
| Untouched top lane, 5 minutes | 8.8 percent | 3 |
| The one accumulating plan (11 minions) | 10.6 percent | 3 |
| A hard push in the same setting | 0.2 percent | 3 |

Never more than three melee minions attack one target, and six bodies fit around one, so the place where bodies would matter is not the target. It is the walk to the next target inside a crowd, and the crowd grows with the stack. The `detour_s` diagnostic charges that walk: a melee minion that turns to a new minion target loses 0.3 s or 0.6 s before its cast. One body's detour at minion speed is about 0.25 s (Assumed geometry on the sourced radius). The length of a fight is a blind measure for it: a placed fight of six against six stays at 28 s even with a detour of 5 s (Reported by the review). The verdict counts of section 5.5 are the evidence, and they move by one or two settings. This bounds one effect of obstruction in a lane without width. It does not show what bodies do.

### 5.7 What is known, what is not, and two measurements

**Read and equal to the ruleset** (Sourced): minion health, damage, attack speed, range, and the on-hit share. **Read in the game's data files this campaign** (Sourced): cast times and missile speeds. **Documented and not modelled:** section 4.3. **Not documented anywhere read so far:** how long bodies take to walk around each other, the retarget cadence, and the length of the short time that minions keep a harassing champion as target.

Two measurements in a custom game on patch 26.22 bear on the open behaviours. The simulator's values changed with the corrections.

| Measurement | The simulator's value |
| --- | --- |
| **A. The untouched first wave in mid.** Nobody touches the lane. When the minions of wave 2 reach the fight, count the minions of wave 1 that are still alive and note how healthy they look. | Wave 2 arrives 29 s after the first blow. Six minions of wave 1 are alive, at 23 percent of their health on average. Left alone, the fight would end 33 s after the first blow. |
| **B. The slow-push drill in top.** A level 1 laner kills the three casters of wave 1 and then only last-hits, with no opponent. Count the minions that reach the enemy outer tower and time their arrival from first contact. | 7 minions, six of wave 2 and one of wave 1, 38.5 s after contact. The placeholder top laner needs longer for the casters than a real champion might. |
| **C. An untouched top lane.** Nobody touches the lane for three minutes. Note whether the waves keep meeting at the corner or one side reaches a tower. | The front is on blue's half at 97 s in every run, and red's wave reaches blue's outer tower. With ranges along the lane it stays at the centre. |

A match in A would confirm one timing. B and C test results that this document does not trust.

### 5.8 Incentive screen and M7's tick sweep

**Incentives** (Tested, [`incentives.json`](../../experiments/m8/waves/results/incentives.json)). A level 1 laner plays one `LANE` action for 5 minutes in each of 12 lane states, in a full world. No action earns most in every state. `last_hit` with the wave earns most gold plus XP in 10 states, and `push` in the two mid states in which the opponent pushes. A hold that last-hits earns the same as last-hitting with the wave when the opponent is absent, and less against an opponent, because the laner retreats. The laner's numbers are placeholders, so this is a screen of the mechanics.

**M7's tick sweep** (Tested, `m7_tests_on_m8_lane.json`, `tick_sensitivity_m8_lane`). On M7's scripted cases, 9 of 17 metrics are within 10 percent of the 0.125 s reference at a 0.5 s tick. Campaign 1 measured 13 of 17 before cast times existed. The metrics that move are sizes and times of thinned waves and the band time of M7's hold cases.

## 6. Recall, fountain, and purchases (C3)

### 6.1 What exists

The rules are in `riftgame/champions.py`, called from the tick's last step (M7 section 5.5).

| Rule | Built | Status |
| --- | --- | --- |
| Recall | 8.5 s in place. Damage or a new action discards the progress. On the fountain it completes at once. | Sourced. Existed since C1. |
| Fountain | A living champion within 1,100 units of its own fountain regains 8 percent of maximum health and 10 percent of maximum mana per second. | Sourced |
| Purchases | Each profile has a fixed progression of five entries. On its fountain a champion buys the next entries while its gold covers them, several in a tick if it can. Dead champions shop too. | The two boot steps are Sourced: 300 gold for +25 move speed, then 800 more for +45 in all. The other 15 entries are Assumed. |
| Capability | `capability(profile, level, upgrades)` is a pure function. It never reads gold. | M7 section 5.5 |
| Homeguard, first rule only | From 0:20 a champion that leaves its fountain moves 80 percent faster, falling to 40 percent over 4 s, until 500 units before the outer tower site of its lane. Leaving for a jungle or river edge ends it. Damage ends it and blocks it for 8 s. | Sourced values. The straight-line decay and the tick at which it starts are Assumed. |

**State.** Two integers per champion: the tick of its last move that began on the fountain with Homeguard, and the first tick on which it may have Homeguard again. Gold spent is derived from the upgrades owned.

**Departures from M7 and the reference.**

- Every champion starts with boots. Starting gold is 500 and boots cost 300, so the purchase rule fires at 0:00. The M7 prototype did the same on its first tick.
- The reference lets a completed recall clear the 8 s block. That rule is not modelled. A channelled recall takes 8.5 s, so the block has run out by then, and a recall on the fountain would have cleared it at once.
- Movement-speed soft caps, the 150 percent tier, the endpoint that tracks the wave, and the respawn and game-start bonuses are left out (M7 section 3.4).

### 6.2 What a recall costs, measured

[`recall.json`](../../experiments/m8/results/recall.json) holds 36 round trips from an outer tower: recall, buy, walk back. With two boot steps and Homeguard the trip takes 23 s in mid and 27.5 to 28.5 s in the side lanes. Without Homeguard it takes 29.5 to 30 s and 36 to 37.5 s. A wave spawns every 30 s, so a trip spans zero to two waves by its length and its start. These are route lengths and speeds. What a recall costs in farm depends on the wave, and section 5 says how far the waves can be trusted.

### 6.3 Acceptance criteria of C3

| Criterion (M7 section 10.1) | Result | Test |
| --- | --- | --- |
| A cancelled recall loses all progress | Cancelled at 8.0 s of 8.5 s by damage and by a new action. The channel reads 0, and a restarted recall takes 8.5 s again. | `tests/test_recall.py` |
| Unspent gold changes no capability | 10,000 gold off the fountain changes nothing for 20 ticks. After the recall the champion owns all five upgrades. | `tests/test_recall.py` |
| The round trip from an outer tower takes the time that route length and speed give, within one tick | 12 cases, both teams, three lanes, before and after Homeguard starts. The largest difference is 0.36 s against a tick of 0.5 s. | `tests/test_recall.py` |

The test file holds 58 tests. They measure Homeguard as distance walked per tick, not through its state.

## 7. Jungle (C4)

### 7.1 What exists

`riftgame/jungle.py` owns the camps (M7 section 5.8). Team sight and camp memory are in `riftgame/vision.py`.

| Rule | Built | Status |
| --- | --- | --- |
| Camps | Six per side at the map file's camp nodes. A camp is one pool of health with a damage rate against the champion it fights. | M7 section 5.8 |
| First spawns | On the clock, whatever any champion does: 0:55 for eight camps, 1:07 for Gromp and Krugs. | Sourced |
| Respawns | The camp's death plus 300 s for the two buff camps and 135 s for the others. | Sourced |
| Level | A camp spawns at the average champion level, a half rounding up. Health and XP run in a straight line between the ruleset's two ends over levels 1 to 18. | The level rule is Sourced. The line is Assumed. |
| Scuttlers | Two spawn at 2:55, one on each river node, at 65 percent health. Nothing else is a condition. When both are dead, one Scuttler spawns 150 s after the last death on a river node drawn by key, and from then on the river holds one at a time. | Sourced |
| Fighting | A champion with a `CAMP` action walks to the camp node and removes its camp damage rate while it stands there. The camp hits the champion that engaged it first, from the tick after the first blow. | Rates are Assumed placeholders. |
| Leash | The camp keeps hitting its champion within 800 units. When that champion dies or leaves, the camp returns to full health, unless another champion is still fighting it. | The 800 units are Assumed. |
| Rewards | Gold and XP go to the killer: the champion that dealt most on the last tick, with a keyed draw between equals. A jungler gets the item's 80 XP per camp and 150 once for its first. | Amounts Sourced. That nobody shares is Assumed. |
| Shrine | A dead Scuttler leaves its killer's team 90 s of sight within 525 units of that river node. The speed effect is left out. | Sourced |
| Team sight | `vision.sees` answers whether a team sees a position: one of its living champions within 1,350 units, or one of its sight sources, with clear terrain between. C5 adds towers. Minions and wards are C6. | M7 section 6.1, in part |
| Camp memory | Per team and camp: what the team last saw there, and the respawn time if it knows it. The team knows the time when it saw the camp die, or sees the camp's location in the last 60 s before the respawn for a buff camp and the last 10 s for another. A team learns of an unseen clear only by seeing the empty camp. | Sourced (M7 section 3.3). The Scuttler uses the 10 s window, Assumed. |
| Observation | 14 camp views from the team's memory, in the order of the `CAMP` actions, each with the walk from the champion. | M7 section 6.3 |

**One departure from the brief of this campaign.** A camp whose champion leaves does not reset while another champion is fighting it. It turns on that champion and keeps its wounds. A full reset would let a camp heal when an invader kills the jungler at it.

### 7.2 The scripted jungler, reported

`harness.jungler` reads only its observation. It goes to the camp with the best known gold plus XP per second of walking, waiting, and clearing, starts no camp that would take it below 25 percent health, and recalls below 35 percent. [`jungle.json`](../../experiments/m8/results/jungle.json) holds its first clear and a sweep of 9 start positions and 3 camp states.

| First clear | Blue | Red |
| --- | --- | --- |
| Sixth camp dead at | 178 s | 179 s |
| Level, camp gold, health then | 4, 529, 275 of 744 | 4, 529, 277 of 744 |

The first fight starts at 56 s, one decision after the spawn at 55 s. No reference gives a clear time on the 2026 clock (M7 question OQ8), so this time has no pass condition. In the sweep the jungler's pick equals the measured best destination from every start in every state. No destination is required to win, and every champion number is a placeholder.

### 7.3 Acceptance criteria of C4

| Criterion (M7 section 10.1) | Result | Test |
| --- | --- | --- |
| Each first spawn falls on the ruleset's clock time | 55.0 s, 67.0 s, and 175.0 s, with nobody acting and in a scripted game | `tests/test_jungle.py` |
| The Scuttlers' first spawn does not depend on a clear (owner requirement) | Both at 175.0 s with 1,007.5 health, with nobody acting and with a jungler in the middle of a clear | `tests/test_jungle.py` |
| Each respawn falls on the camp's last death plus the ruleset's delay, to the tick | 12 camps. The Scuttler pair rule holds over three rounds. | `tests/test_jungle.py` |
| Timer knowledge follows the reference rule for seen and unseen clears | The watching team's timer reads 60.0 s for a buff camp and 10.0 s for the others at the first tick it knows. | `tests/test_jungle.py` |
| A clear takes the camp's health over the champion's camp damage rate, within one tick | Five roles. The jungler needs 12.5 s against 12.1 s of arithmetic. | `tests/test_jungle.py` |
| Travel between camps takes route length over speed | Within one tick | `tests/test_jungle.py` |
| Leak test | Every camp fact that a team has not seen is changed. Its observations and masks stay identical until it sees a changed camp. | `tests/test_world_observation.py` |
| The handoff reports the scripted jungler's destinations and first-clear time | Section 7.2 | `jungle.json` |

## 8. Combat and death (C5)

### 8.1 What exists

`riftgame/combat.py` collects champion attacks and settles kills (M7 section 5.9). Tower shots on champions and champion hits on towers are in `riftgame/lanes.py`, because a tower has one attack for minions and champions. There is no fight object and no outcome roll.

| Rule | Built | Status |
| --- | --- | --- |
| One attack capacity | A table entry per intent kind names the one class that a champion's attack goes to on a tick: minions for `LANE`, a champion for `FIGHT`, a camp for `CAMP`, a tower for `SIEGE`, and for `HOLD`, `FOLLOW`, and a finished intent the enemy champion that is attacking it. `Champion.attack_credit` is the budget for whole hits on minions and towers. A tick that damaged a champion or a camp uses the attack up, so the next lane hit waits. The lane takes the credit in with the champion's input and hands back what its hits left. An idle tick earns attack speed times the tick, up to one ready attack. The budget works in one direction: damage on champions and camps is a rate and does not wait for the credit, so a champion that has just last-hit deals a full tick of it on its next tick (Unresolved). | M7 section 7.4, owner requirement |
| Champion against champion | A fighter closes to its attack range and deals its damage rate times the tick on every tick on which the target is alive, within range by the straight line, and in the view of the fighter's team. All hits of a tick are collected before any lands. | M7 section 5.9. The rates are Assumed placeholders. |
| Hitting back | A champion that holds or follows hits the enemy that deals it the most damage on that tick, if that enemy is within its own range. | M7 section 7.1 |
| Lockdown | Used when it is ready, the mana covers it, and the champion hits a champion. It takes a share of the target's move speed for its duration. | Numbers Assumed, from the M7 prototype |
| `FIGHT` | While the target is in the team's view the fighter pursues it. Out of view, it walks to the last-seen place in team memory. Seen again on the way, the fight resumes with no outcome. One tick after it arrives within attack range of the last-seen place with the target still unseen, the intent ends with `LOST`. The target's death ends it with `KILLED`, whoever killed it. | M7 section 7.1 |
| Sight | Living towers are sight sources of 1,350 units. A champion that damages an enemy champion is visible to the victim's team on that tick. Each team's memory holds a last-seen record per enemy champion. | M7 sections 6.1 and 6.2, in part |
| Observation and mask | The observation gains the enemies that the team sees now and which enemies damaged this champion recently. `FIGHT` is offered only against a living enemy in view. A running fight with a hidden target is kept with `KEEP`. | M7 section 6.3 |
| Self-defence | `FIGHT` against a visible enemy that damaged this champion within 5 s stays legal under every leash, on and off the lane. The return actions stay legal. | Owner requirement. The 5 s are Assumed. |
| Towers against champions | A tower shoots first an enemy champion in range that damaged an allied champion standing within 1,400 units of the tower, then minions in their order, and with no minion in range the closest enemy champion. A shot deals the tower's attack damage at that game time, plus half of it for each consecutive shot on a champion before it, up to one and a half times more. The ramp starts again 5 s after the last shot on a champion. | Sourced |
| `SIEGE` | The champion walks to its attack range of the lane's enemy front tower and hits it with whole attacks from the shared credit. A hit is cut by the tower's armor, raised by 20 percent for a melee champion, and cut by 80 percent while none of the champion's minions is within 750 units of the tower. It ends with `CLEARED` when the lane's last tower falls. | Sourced factors. The armor formula is from memory, and the 750 units are Assumed. |
| Plates and tower gold | Each time a tower's missing health crosses a plate threshold, 120 gold is split among the living enemy champions within 1,200 units, whoever dealt the damage. A fallen tower pays its global gold to every enemy champion, and the first tower of the game pays 300 more, split among those near. | Sourced |
| Call for help | A champion that damages an enemy champion is harassing for the lane on that tick and for 2 s after. Minions and towers answer for that long. | The trigger is Sourced. The 2 s are Assumed. |
| Death and rewards | All deaths of a tick are settled from the hits collected before any of them. The killer is the enemy champion that dealt the victim the most damage on that tick, or else the one that damaged it last within 10 s. With neither the death is an execution and pays nothing. Kill gold is 300, plus 10 per victim level from 7. Other champions that damaged the victim within 10 s share half of the kill gold. The first kill adds 100. Kill XP runs in a straight line from the reference's two ends over victim levels. Ties are drawn by key on the places of the champions, never by seat. | Amounts Sourced. The 10 s and the straight line are Assumed. |

**Simultaneous deaths.** M7's prototype paid only the killer that the code visited first when two champions died on one tick. Here each killer gets its kill gold and XP, and of several first kills on one tick a keyed draw picks the one that is first blood. The tests stage five fights and exchange the seats, between the teams and inside a team, and compare places, health, death ticks, gold, and XP on every tick.

**Departures from M7 and the brief of this campaign.**

- A fighter heads for where a target that does not pursue stands after it has moved. With places from before the move step, a target that walks away is never hit by any chaser at any speed, because the gap after both moves is the range plus the target's step. `FOLLOW` is unchanged.
- First blood is drawn among the kills of the tick, ordered by the victim's place. M7 said a draw picks the team, and that flips when the teams exchange seats.
- `SIEGE` ends with `CLEARED`, or with `ABSENT` when the lane has no tower to damage. M7 names no outcome.
- A laner that fights in self-defence off its lane is still charged as roaming.
- Left out: bounties and shutdown gold, the level-difference modifier on kill XP, the early growth of the assist pool, the 3 s before backdoor protection returns, plate gold decay, Bulwark, and the armor penetration of tower shots. A tower keeps a champion as target only while that champion is harassing.

### 8.2 The fight scenarios of M7 section 5.9, on the M8 kernel

[`combat.json`](../../experiments/m8/results/combat.json) reruns M7's four scenarios with policies that only choose actions. Every champion number is a placeholder, so the outcomes show that the mechanics respond. They do not show who wins a real fight.

| Scenario | Result |
| --- | --- |
| A champion retreats at half health. Speed edge, lockdown, and distance to its own tower, 18 cases. | 10 escapes and 8 deaths. From 1,000 units every runner escapes. From 2,500 and 4,000 units only the faster runner does. The chaser dies under the tower in all 10 escapes. The lockdown changes no case: it fires on the first hit, and its cooldown is not over when the runner turns. |
| A level 1 fighter loses to a level 7 enemy alone. Its jungler walks in from d units. | The side wins with the jungler from up to 2,750 units, all three die at 3,000, and the enemy survives from 3,250 to 5,000. From 5,250 the enemy dies after all: the first fighter has respawned and walked back by then. |
| The same duel in open lane and under the defender's outer tower. | In open lane the attacker wins with 91 health after 13.5 s. Under the tower it dies after 2.5 s to three tower shots. |
| A jungler leaves fog toward a laner. | A laner at its own outer tower is never touched, and the jungler dies under the tower. A laner at the enemy outer tower with 650 health survives on 9 health when it decides every second and dies when it decides every 2 s or 5 s. |

Two things in these runs come from the rules and would mislead if read as strategy. A tower with no minion in range shoots any enemy champion in range, so a champion that walks under an enemy tower alone dies within seconds. And conclusions about ganks depend on where the wave stands, which section 5 leaves open.

### 8.3 Acceptance criteria of C5

| Criterion (M7 section 10.1, and the owner's requirements) | Result | Test |
| --- | --- | --- |
| Damage is monotone in capability | Never falls with a level or an upgrade, for five profiles | `tests/test_combat.py` |
| An ally's arrival tick equals route length over speed | From 600, 1,500, and 3,000 units the first hit falls on the tick that the arithmetic gives | `tests/test_combat.py` |
| A champion takes champion damage only on ticks when an attacker is within range by the straight line and the target is in the view of the attacker's team | Open lane: hits on 5 of 30 ticks, exactly those in range. Over a wall: hits on exactly the 7 of 12 ticks with an ally's sight. 494 units in a straight line against a walk of 568 is inside a range of 550. | `tests/test_combat.py` |
| A tower's damage on a champion follows the reference aggro and ramp rule to the tick | No shot at 751 units. Multipliers 1.0, 1.5, 2.0, 2.5, 2.5 on consecutive shots. The ramp is kept after 4.5 s without a shot and starts again after 5 s. The tower turns from minions to a champion that damages an ally and back when the call has run out. | `tests/test_combat.py` |
| Permuting the seat order changes no outcome | Five fights, seats exchanged between the teams and inside a team. Equal on every tick. | `tests/test_combat.py` |
| `FIGHT` follows M7 section 7.1 | Pursuit to the last-seen place, `LOST` one tick after arrival, no outcome when the target is seen again first, the same path wherever the hidden target is | `tests/test_combat.py` |
| A dead champion returns at the fountain after the ruleset's timer | 10 s at level 1 | `tests/test_combat.py`, `tests/test_world_intents.py` |
| One attack capacity across targets | A champion that fights kills no minion in its reach. After a fight or a camp, its first lane hit waits for the credit. On every tick its damage goes to one class. | `tests/test_combat.py` |
| Simultaneous deaths pay every killer | Two champions that kill each other on one tick get 300 and 400 gold and 42 XP each, and one of them first blood | `tests/test_combat.py` |
| Self-defence and retreat for a returning laner, with the restriction on and off | `FIGHT` against the attacker is legal for 5 s after its last hit, on and off the lane. The return actions stay legal. | `tests/test_combat.py` |
| Leak test | Every field of every enemy that a team does not see is changed. Its observations and masks stay identical for 40 ticks. | `tests/test_combat.py` |

## 9. Assumptions, internal correctness, and real-game validation

**Assumed.** Nothing has checked these against the game.

- Every champion number: the five capability profiles, level growth of 8 percent, the 15 placeholder upgrades, camp damage rates, and the numbers of section 8.
- Lateral slots after the first wave, the hold line 300 units outside tower range, the stand-off of 550 units, and that a champion that stepped aside hits nothing.
- That a cancelled cast starts again and a missile to a dead target is lost. That tower shots and champion hits are instant. A missile on its way to a champion lands even if the champion steps aside.
- The lane polyline of the route graph, which has one corner node in top and in bot.
- The roam cap of 90 s and the refill of 0.25, and the end of assignments at 14:00 or with an outer tower.
- The straight-line decay of Homeguard, the leash of 800 units, straight-line camp scaling, and the Scuttler's timer window.
- The jungle paths and the sight terrain of M7 section 5.1, unchanged.

**Internally correct.** A test in this repository shows it, and a mutation run shows that the test can fail.

- The kernel contracts of section 3.3, the lane rules of section 4.1, the ledger, and the criteria of sections 6.3, 7.3, and 8.3.
- The port of M7's lane (section 5.1).
- The mutation runner breaks the code in 203 ways, and the tests catch all of them.

**Throughput.** One process runs a 600 s game of random legal actions at 620 simulated seconds per wall second [567 to 623, 7 runs], scripted farming at 573 [508 to 577], and scripted farming with jungling at 539 [511 to 544] (`kernel.json`). The first campaign measured 1,183 and 945 for the first two, on a kernel without attack timing, camps, sight, or fights. In runs that alternated the last commit and this tree on one machine, a farming game ran at about 565 simulated seconds per CPU second against about 915 (Reported, a script outside the results files). The lanes take 53 percent of a farming game, the observation 15 percent, and team memory 7 percent. Every figure is above M7's gate of 300, which applies at C7. A snapshot at 600 s is 24,118 bytes pickled.

**Validated against the real game.** Nothing. Constants are Sourced, which means read from a document or a data file, not measured. The first real-game validation that M8 needs is still the pair of measurements of section 5.7. Until wave fidelity is settled, any conclusion that the simulator supports about recall timing, denial, or gank opportunities is provisional: each depends on where a wave is and how long it stays there.

## 10. Requirements kept for later checkpoints

| For | Requirement |
| --- | --- |
| C6 | `stance` gets the wave front that the champion's team sees, not the true front. Team sight gains lane minions and wards, and the observation gains the lane fields with their leak tests. `World.light` adds a ward as a sight source. |
| C6 | The first-wave rules of section 4.2 need a view of who is near a minion. |
| C7 | The sweep over tick lengths and decision intervals, with the wave verdicts of section 5.5 in it. The throughput gate. Pinned replays of an integrated game. |
| C7 | A scripted laner that recalls. Under `farmer` no laner ever spends its gold. |
| C8 | The complete hidden-state hypothesis generator of M7 section 9.3 and its three acceptance tests. Nothing of it exists in `riftgame`. |
| M9 | Champion numbers, armor in `damage`, movement-speed soft caps, and whether purchase thresholds change recall timing. |
| Before C7 | A finer lane polyline around the corners of top and bot, in a map file of M8's own, so that straight-line ranges do not tip an untouched lane. The game's minion path has the points. The current map file has to stay as it is for M7's results. |
| C5 follow-up | A fighter heads for its target's true place on the one tick on which the target leaves its team's view. Rate damage does not wait for the attack credit. |
| Open | Unit collision in a lane with width. The retarget cadence. The caster's acquisition range. Tower shot timing. |

## 11. How to rerun the evidence

Every command starts with `.venv/Scripts/python.exe` from the repository root (M7 section 13 has the setup).

| Command | What it shows | What it writes |
| --- | --- | --- |
| `-m pytest -q` | Every test of M7 and M8 | Nothing |
| `-m experiments.m8.waves.capabilities` | Stacking, holding, and bouncing through the action table, the diagnostics, and the tick sweep. About 15 minutes on 8 processes. | `experiments/m8/waves/results/capabilities.json` |
| `-m experiments.m8.waves.investigate` | The lane without champions: fights, arrivals, attack timing counters, the level lead. About 5 minutes. | `experiments/m8/waves/results/investigation.json` |
| `-m experiments.m8.waves.m7_tests` | M7's cases and verdicts on the M8 lane, the port check, M7's tick sweep. About 5 minutes. | `experiments/m8/waves/results/m7_tests_on_m8_lane.json` |
| `-m experiments.m8.waves.incentives` | The incentive screen. About 1 minute. | `experiments/m8/waves/results/incentives.json` |
| `-m experiments.m8.waves.trace "S0 fight 6v6" "m8 lane" 0 0.5 0 100` | A tick-level trace of one M7 case | Nothing |
| `-m experiments.m8.recall` | Round trips from the outer towers | `experiments/m8/results/recall.json` |
| `-m experiments.m8.jungle` | The scripted jungler's first clear and its sweep. About 1 minute. | `experiments/m8/results/jungle.json` |
| `-m experiments.m8.combat` | The fight scenarios of M7 section 5.9 on the M8 kernel | `experiments/m8/results/combat.json` |
| `-m experiments.m8.kernel` | The kernel measurements | `experiments/m8/results/kernel.json` |
| `-m experiments.m8.mutations` | Breaks the code in a temporary copy and counts the tests that notice | Nothing |
| `-m experiments.m8.provenance` | Whether each M8 results file still matches the working tree | Nothing |
| `-m experiments.m7.provenance` | The same for M7. All five files stay current. | Nothing |
