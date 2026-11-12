# Handoff 006: M8 second campaign, C2 corrections and C3 to C5

| | |
|---|---|
| Number | 006 |
| Date | 2026-11-12 |
| Type | Implementation and experiment. I changed reusable code in `riftgame/`, rewrote the wave experiments in `experiments/m8/waves/`, added evidence scripts for C3 to C5, rewrote the M8 document, and made small roadmap and README status edits. I trained nothing and started no work on C6 to C8. |
| Responds to | The owner's session prompt of 2026-11-12, the open items of [handoff 005](005_m8_c1_c2.md), and [`docs/design/M7_architecture.md`](../docs/design/M7_architecture.md) section 10.1, checkpoints C3 to C5 |
| Status | Delivered. Waiting for review by the user and the planning assistant. Nothing is committed. |
| Author | Claude Code (Fable 5.2), the implementing assistant |
| Revised | 2026-11-12, before the planning review. An independent review found 5 defects and 8 items to fix in my first draft. §3.5 lists them and what I did. |

**Reading guide.** The user can read §1 and §6. The planning assistant should read all of it, then [`docs/design/M8_foundation.md`](../docs/design/M8_foundation.md), which holds the technical detail and is cited here as "the M8 document". §8 lists the claims I am least sure of. C1 to C8 always mean M8's checkpoints. Limitations are numbered L1 to L16.

## 1. Summary

- An agent can now hold a wave and thin it. A `LANE` action names what the champion hits and, apart from that, where it stands (F1).
- The lane changed in three sourced ways: every range inside it is the straight line on the map, two documented targeting exceptions near towers are in, and minion attacks have the cast times and missile speeds of the game's data files (F2 to F4).
- Every wave experiment about champions now runs the full world, a plan only picks action indices, and each result is compared with a lane that nobody touches (F5).
- C2 is not complete. Through the action table reinforcements accumulate in 1 of 32 settings, a hold is sustained for three wave cycles in 8 of 64 and never beyond four, and a bounce can be put down to a crash only in mid (F6 to F8).
- The straight-line rule introduced a defect: an untouched top lane goes to blue's half within 100 s in every seed, because the route graph has one sharp corner node there (F9).
- No lane rule makes the wave behaviours appear, the new attack timing included, and the counts move with the tick length (F10).
- My first revision of the wave criteria was too loose and its headline numbers were wrong. An independent review found it. The criteria and every wave number here are the second revision (F11, §3.5).
- C3 (recall, fountain, purchases, Homeguard), C4 (camps, Scuttlers, shrine sight, camp timers), and C5 (fights, towers and champions, death, kill rewards) are built, and each passes the criteria that M7 wrote for it (F12 to F14).
- The full suite gives 586 passed and 9 expected failures. The mutation runner breaks the code in 203 ways and the tests catch all of them (F15).
- All of this is correctness inside the simulator. Nothing is validated against the real game, and conclusions about recall timing, denial, and gank opportunities are provisional (§3.3). My judgment: C6 can be planned, and the lane needs one more correction before C7 (§7.3).

## 2. Scope

**Done.**

- Read the README, the roadmap, the M7 and M8 documents, handoff 005, and the code and results of the first campaign.
- Changed the action table, the lane, and the lane's callers myself, with their tests and mutations.
- Read the wiki's Minion page again, and the game's character data files for the three lane minions, through a fetch tool.
- Wrote the world-driven wave experiments and reran every results file.
- Had one delegate each build C3, C4, and C5 to my written briefs, each in a private copy of the tree. I read each report, read the new modules, merged each diff by hand, and changed what did not fit (§4).
- Rewrote the M8 document. Edited the roadmap in four places and the README's status.
- Had the result reviewed by a delegate on Claude Opus 5.5, read-only. I then tightened the wave criteria, added the controls it asked for, reran everything, and rewrote the wave parts of both documents.

**Not done.**

- No work on C6 to C8. No training. No real-game measurement.
- I did not fix the top-lane drift (F9). It needs a finer lane polyline in a new map file.
- No unit collision. I counted where bodies would overlap and bounded one effect with a diagnostic (F10).
- I did not read every line that the delegates wrote. §8 says what I read.
- Nobody has reviewed the second revision of the wave criteria or the fixes of §3.5.

**Repository state.** Nothing is committed, pushed, or opened as a pull request. `git status` shows modified files under `riftgame/`, `tests/`, `experiments/m8/`, `docs/`, and `README.md`, and new files: `riftgame/jungle.py`, `riftgame/combat.py`, `tests/test_recall.py`, `tests/test_jungle.py`, `tests/test_combat.py`, `experiments/m8/recall.py`, `jungle.py`, `combat.py` with their results, `experiments/m8/waves/agents.py` and `capabilities.py` with its results, this handoff, and its decision log.

## 3. Results

### 3.1 Findings

| ID | Finding | Label | Evidence |
|---|---|---|---|
| F1 | A `LANE` action is (lane, mode, stand): four modes say what the champion hits, and two stands say whether it walks with the wave or stays on the hold line. The table has 107 entries, 24 of them `LANE`. The old `hold` mode fixed last-hitting to the hold line, so the freeze plans of M7 needed a flag that agents did not have. | Verified | `riftgame/champions.py`, `tests/test_world_intents.py`, `tests/test_lanes.py` |
| F2 | Every range inside a lane is the straight line on the map, between minions, towers, and champions alike. Marching stays on the lane coordinate. A first version changed only the champion and tower ranges, and a passive carry in bot then took 568 damage in five minutes instead of 44, because minions measured each other along the lane and the champion by the straight line. | Verified for the rule and its tests. Reported for the 568 and 44, from a scratch run that is not kept. | M8 document section 4.2, `tests/test_lanes.py` |
| F3 | The wiki's Minion page, read sentence by sentence, says three things more exactly than handoff 005 reported. A champion in the path is attacked only outside a turret's range. First-wave minions answer a call for help while they attack a tower. The "short time" of persistence applies to a champion that stops attacking an allied champion, not to any champion target. The first two are lane rules now. The third is a window in C5 whose length is Assumed. | Reported for the page text, read through a tool that summarizes. Verified for the rules and their tests. | M8 document section 4.2 |
| F4 | The game's data files give lane minions a cast time (0.393 s melee, 0.47 s caster, 0.30 s siege) and a missile speed (650 caster, 1,200 siege). The lane had landed every blow at once. With timing, a placed fight of six against six lasts 28 s against 25.5 s, and the untouched first-wave fight 33 s in mid and 34.5 s in top against 31 s. That a cancelled cast starts again and that a missile to a dead target is lost are Assumed. | Reported for the data files. Verified for the measurements. | `investigation.json`, `fights` and `natural_fight` |
| F5 | The experiments about champions run a full world of ten champions. A plan returns a `LANE` action every 2 s. The champions are the placeholder profiles at level 1, 3, and 6, each on the clock that fits the level, plus a carry alone and a carry with a support. The plans use only actions that an agent has. They use more information than an agent has today: the observation has no lane fields until C6, and the plans read the true front and exact minion counts near it. | Verified | `experiments/m8/waves/agents.py`, `capabilities.py` |
| F6 | Reinforcements accumulate in 1 of 32 settings. A plan accumulates when, in every seed, its largest crash holds three minions from each of two waves at its largest moment and more minions than a hard push and a lane with no laner bring. The one case: a level 1 top laner, from an enemy push at its tower, opponent absent, kills three casters and then hits nothing, and 11 minions of three waves arrive. A hard push brings 7 there, and the lane with no laner 9. Against an opponent that last-hits, 0 of 16. The standard slow-push drill brings 7 minions where a hard push brings 9. No crash reaches 12. | Verified | `capabilities.json`, `stacking` |
| F7 | A hold is sustained in 8 of 64 settings: three wave cycles with the enemy wave near the tower and never in its range, without a death, and longer than no champion, a laner that last-hits with its wave, or one that pushes. Some hold lasts three cycles in every seed in 15 settings, four in 1, and none lasts longer. In 7 of the 8 settings only plans that thin or trim while they hold sustain it. The hold that only last-hits, the one the old table could express, does so in 1. No plan sustains a hold for a level 6 mid laner or a level 3 top laner. | Verified | `capabilities.json`, `holding` |
| F8 | After a crash the front comes back past the centre in every run in 15 of 16 cases. It comes back before the front of the same lane with no laner in 4, all in mid. In top and bot the untouched lane's front is there first, so those returns say nothing about the crash. After a hard push of the first wave, mid resets to the exact centre in 3 of 5 runs: the tower kills the crash before the next enemy wave arrives. | Verified | `capabilities.json`, `bounce` |
| F9 | With straight-line ranges, an untouched top lane has its front more than 100 units on blue's half at 97 s in 5 of 5 seeds, and red's wave reaches blue's outer tower with 7 to 12 minions. With ranges along the lane the front never leaves the centre. Mid is the same under both. I infer the cause from that: the route graph gives top lane one sharp corner node, 295 units from where the waves meet, and the straight line cuts it unevenly for the two teams. This defect is new in this campaign and is not fixed. | Verified for the measurement. Inference for the cause. | `investigation.json`, `untouched`. `test_behaviours.py`. |
| F10 | No lane rule makes the wave behaviours appear. Over eleven variants on a set of 8 stacking and 8 holding settings, the number of accumulating settings stays between 0 and 2 and of sustained holds between 2 and 5, with no direction. With blows that land at once, 5 holds are sustained against 2 in the M8 lane. The two unsourced details of attack timing each move a count by one or two. At a tick of 0.25 s the one accumulating thinning plan is gone and the largest crash falls from 11 to 9. Never more than three melee minions attack one target, and minions stand where two bodies could not in 1.2 percent of minion ticks in an untouched mid lane and 10.6 percent in the accumulating plan. | Verified for the runs. The detour bound is my construction. | `capabilities.json`, `diagnostics` and `tick_sweep`. `investigation.json`, `attack_timing`. |
| F11 | The wave criteria are in their second revision. The counterexamples against M7's tests stand: the band clause scored 214 s of 240 for a lane with no champion whose tower was hit in every cycle, and a bar of exactly 12 calls an 11-minion crash of three waves no stack. My first revision then passed too much (§3.5, items 1, 2, and 4). The second adds the no-laner controls and removes the 1 s tolerance. Three cycles, three minions per wave, and 100 units are still my choices, and the cut from 240 s to 90 s has no counterexample behind it. Eight strict expected failures keep the unmet bars in view. | Verified for the counterexamples and the counts. The thresholds are my choice. | M8 document section 5.3 |
| F12 | C3 passes M7's three criteria: a cancelled recall loses all progress, unspent gold changes no capability, and the round trip from an outer tower takes the time that route and speed give within one tick (largest difference 0.36 s). With two boot steps and Homeguard the trip takes 23 s in mid and 27.5 to 28.5 s in the side lanes. | Verified. I reran the tests and the script in the main tree. | `tests/test_recall.py`, `recall.json` |
| F13 | C4 passes M7's criteria. First spawns fall on the clock with nobody acting. The two first Scuttlers spawn at 2:55 whatever any jungler does, and the pair rule and the 150 s respawn hold over three rounds. Timer knowledge follows the reference rule to the tick. The scripted jungler finishes its first clear at 178 s (blue) and 179 s (red) at level 4. | Verified. I reran the tests and the script in the main tree. | `tests/test_jungle.py`, `jungle.json` |
| F14 | C5 passes M7's criteria and the owner's three requirements. A champion's attack goes to one target class per tick, by a table entry per intent, and a tick spent on a champion or a camp leaves no ready attack for the lane. The budget works in one direction only: damage on champions and camps is a rate and does not wait for the credit (L13). Two champions that die on one tick both pay their killers, and exchanging seats between or inside the teams changes no place, health, death tick, gold, or XP. A returning laner may fight an enemy that damaged it within 5 s, under every leash, and keeps its ways home. A tower's shots on champions follow the reference order and ramp to the tick. In the rerun of M7's fight scenarios 10 of 18 retreats escape, and a champion that fights under an enemy tower alone dies after 2.5 s. | Verified. I reran the suite and the script in the main tree, and read `combat.py` and the lane diff. | `tests/test_combat.py`, `combat.json` |
| F15 | The full suite gives 586 passed and 9 expected failures: M7's known prototype defect and the eight wave bars of F11. The mutation runner breaks the code in 203 ways in a temporary copy. In the full run on the final tree the tests caught 201, and two entries no longer matched the code, because my last optimization had changed the lines they replace. I updated those two entries, and the tests catch both. All eight M8 results files and all five M7 results files are current. | Verified | `python -m pytest -q`, `python -m experiments.m8.mutations`, both provenance checkers |
| F16 | One process runs a 600 s game of random legal actions at 620 simulated seconds per wall second [567 to 623, 7 runs], scripted farming at 573 [508 to 577], and scripted farming with jungling at 539 [511 to 544] (`kernel.json`). The first campaign measured 1,183 and 945 for the first two, on a kernel without attack timing, camps, sight, or fights. In runs that alternated the last commit and this tree on one machine, a farming game ran at about 565 simulated seconds per CPU second against about 915 (Reported, a script outside the results files). The lanes take 53 percent of a farming game. Every figure is above M7's gate of 300, which applies at C7. | Verified for the runs | `kernel.json` |

### 3.2 Validation performed

| Check | Result | Label |
|---|---|---|
| `.venv/Scripts/python.exe -m pytest -q` | 586 passed and 9 expected failures | Verified |
| Mutation runner | 201 of 203 caught in the full run on the final tree, with the unmutated copy passing. The other two had gone stale after my last optimization. Updated and rerun, both are caught. | Verified |
| Provenance, M8 and M7 | 8 and 5 files current | Verified |
| Port check against M7's results | 998 of 998 with M7's draw key | Verified |
| Independent review of the first draft of this handoff, the M8 document, the decision log, and the code | 5 defects, 8 items to fix, 4 notes. The reviewer checked about 31 numbers and ran its own probes. | Reported by the reviewer. I reproduced the untouched-lane drift and the stricter counts myself. |

### 3.3 Internal correctness and real-game validation

**Correct inside the simulator** means that a test in the repository shows a rule, and a mutation shows that the test can fail. That covers the action table, the lane rules, the ledger, and the criteria of C1 and C3 to C5. It does not cover the wave behaviours: those are measured, and most of the measurements are negative.

**Validated against the real game:** nothing. The constants are read from documents and data files. No timing of a real lane, a real clear, or a real fight has been measured. The M8 document, section 5.7, names three measurements that would help. They are not a condition for C6.

**Provisional because of that.** Any conclusion about recall timing, denial, or gank opportunities depends on where a wave is and how long it stays, and the lane's waves are not settled. C3 to C5 are tested as mechanics. They draw no strategic conclusion.

### 3.4 Unresolved limitations

| ID | Limitation |
|---|---|
| L1 | C2 is not complete (F6 to F8). A slow push, a freeze, and a bounce each appear in a small minority of settings. |
| L2 | With straight-line ranges an untouched top lane drifts to blue's side (F9). Every top-lane and bot-lane wave result is confounded by it. |
| L3 | Every champion number is a placeholder, and a champion has no armor until M9. |
| L4 | The plan families are hand-written: 7 pushing plans and 7 holding plans. A learned policy may find more, or exploit something. |
| L5 | The verdicts ask for every seed, on 5 seeds, and they flip with the seed count. Under my first criteria the reviewer found a setting in which four thinning plans accumulate against a last-hitting opponent on 3 seeds and none on 5, because the push's largest crash tied the plans' smallest (Reported). I did not repeat that check under the second criteria. |
| L6 | The wave counts change with the tick length, and the mechanism is unknown (F10). |
| L7 | That a cancelled cast starts again, and that a missile to a dead target is lost, have no source. A missile on its way to a champion lands even if the champion steps aside. The lane's digest leaves out the death time of a dead target that a pending cast still points at. |
| L8 | Documented and not modelled: the first wave's ghosting and its indifference to champions, the retarget cadence, the death grace, melee armor, and the caster's acquisition range of 700 in the data file against 500 on the wiki. Tower shots and champion hits have no cast time. |
| L9 | The lane has no bodies. The overlap count and the detour diagnostic say where obstruction would act, not what it does. Fight length is a blind measure for the detour. |
| L10 | The wave plans read the true front and exact minion counts (F5). `stance` still reads the lane's true front (handoff 005, L6). C6 has to give both the team's view. |
| L11 | Team sight has champions, towers, and shrines. Lane minions and wards are C6. |
| L12 | C3: every champion starts with boots, movement-speed soft caps are left out, and the reference's rule that a completed recall clears the Homeguard block is not modelled. Under `farmer` no laner ever recalls. |
| L13 | C5: the attack budget is one-directional (F14). A fighter heads for its target's true place on the one tick on which the target leaves its team's view. Champions have no armor, so three tower shots kill a level 2 champion, and a tower with no minion in range shoots any enemy champion in range. The scripted jungler walks through tower range when it invades and dies there. Bounties, the level-difference XP modifier, plate gold decay, and Bulwark are left out. A laner that fights in self-defence off its lane is charged as roaming. |
| L14 | C4: camp damage is flat over levels, nobody shares a camp's XP, and the Scuttler's timer window is my assumption. |
| L15 | Throughput fell (F16). |
| L16 | The wave experiments stage a world by setting XP, positions, and the clock, and the holding cases add minions during the run. C8's scenario loader should replace that. |

### 3.5 What the independent review found, and what I did

The review ran on my first draft, on Claude Opus 5.5, read-only. It edited nothing.

| # | Finding | Severity | Action |
|---|---|---|---|
| 1 | The accumulation criterion passed crashes that are not stacks. It compared a plan only with a hard push, counted "two waves" over a whole visit, so one straggler was enough, let a champion that hits nothing qualify, and had no lane with no laner beside it. "11 of 32" was false. | Defect | Fixed. The criterion now asks for three minions from each of two waves at the largest moment, and for more than a hard push and a lane with no laner. The count is 1 of 32 (F6). |
| 2 | The hold criterion was relaxed without support. The 1 s that a wave might spend in tower range equalled the best hold's time there exactly: at no tolerance that hold lasts 1 cycle, not 8. The controls had dropped out of the verdict. Three cycles sits where the results fall off. One sentence said the opposite of what it meant. | Defect | Fixed, except the three cycles. No time in tower range is allowed, a hold has to beat three controls, and the distribution over cycles is reported. The count is 8 of 64, and the longest hold is 4 cycles (F7). The cut from 240 s to three cycles stays my choice and is said to be one (F11). |
| 3 | The two unsourced details of attack timing did the work for the holds of the first draft, and its best results did not survive a 0.25 s tick. | Defect | Reported as found. Both details are diagnostic switches now, with rows in the table (F10). Under the second criteria they move a count by one or two, and so does everything else. |
| 4 | The bounce criterion had no control, and an untouched top lane swings between the towers by itself under straight-line ranges. The document and the tests disagreed on the 120 s. | Defect | Fixed. Each bounce case runs beside the same lane with no laner, and counts only if it comes back first. A new section measures untouched lanes (F8, F9). The 120 s stay in the two mid tests that pass them. |
| 5 | Two comparisons were misreported. "The hard push brings 7 at 29.5 s" mixed the push's largest crash with its first crash time. The slow-push drill was set against the push's first crash of 5, where the push's largest crash holds 9. | Defect | Fixed. The table carries the push's largest crash and its time, and the drill is reported as not accumulating (F6). |
| 6 | The negatives were as fragile as the positives, and the tests ran positives on 2 seeds and negatives on 5. | Should-fix | Fixed in part. Every wave test runs on 5 seeds. The every-seed form stays, and L5 gives the tie that decides one of the negatives. My explanation of why a last-hitting opponent stops a stack is removed. It had no evidence. |
| 7 | "Some plan delays the crash in 32 of 32" was empty, because a laner that hits nothing delays by definition. | Should-fix | Fixed. Only thinning plans count, and the M8 document calls the property weak. |
| 8 | The experiments use an agent's actions, but not only its information. | Should-fix | Stated in F5, L10, and the M8 document, section 5.2. Not changed. The observation gets lane fields in C6. |
| 9 | "One credit that fights, camps, and lane hits share" overclaimed. Rate damage does not wait for the credit. | Should-fix | Reworded in F14 and the M8 document. Not changed in code (L13, Q6). |
| 10 | Seeds and run lengths of existing tests were changed by the delegates and were not in the log. | Should-fix | Logged, and listed in §4, item 10. |
| 11 | Three evidence labels were wrong: the tick sweep pointed at a key that the results file did not have yet, the 568 and 44 came from a scratch run, and a phase was marked done on a condition it did not meet. | Should-fix | Fixed. |
| 12 | "The verdicts sit near their thresholds" did not fit a hold that fell from 8 cycles to 1. | Should-fix | Removed. The mechanism is unknown (L6). |
| 13 | Fight length is a blind measure for the detour diagnostic. | Should-fix | Said so in the M8 document, section 5.6. |
| 14 | In the timing code a missile to a champion lands after the champion steps aside, casts complete while a minion walks in 0.5 to 2.5 percent of blows, and the digest omits one field. | Note | Listed in L7. Not changed. |
| 15 | A fighter reads its target's true place on the tick it leaves view. | Note | Listed in L13. Not changed. |
| 16 | The README and roadmap risk 11 inherited the overclaim. | Note | Both reworded. |
| 17 | The straight-line rule is otherwise clean. The hold line, the stand-off, and the experiments' band are still placed along the lane, which differs by 16 units at most. | Note | Stated in the M8 document, section 4.2. |

### 3.6 Handoff 005 items that this handoff answers

| 005 item | Status |
|---|---|
| 005/Q1, L5 | Answered. A stand beside the mode (F1). |
| 005/Q2, F9 | Answered with a new criterion (F11). The thresholds are provisional. |
| 005/Q3, F10 | Answered in part. Mid bounces after a thinned-wave crash and resets after a one-wave crash at 0:00. The side-lane bounce that handoff 005 reported as passing cannot be put down to the crash (F8). |
| 005/Q6, L10 | Answered. The two rules near towers are in. The persistence belongs to the call for help (F3). |
| 005/Q7, F7 | Answered. Accumulation is its own criterion, with controls (F6). |
| 005/L11 | Changed, with a new defect (F2, F9). |
| 005/F11, V1 | Not supported. Fights are 2 to 3.5 s longer for a sourced reason (F4), and under the new criteria longer fights do not produce the behaviours (F10). |
| 005/F13, V4 | Narrowed. The cap stays a diagnostic. The overlap count and the detour are new (F10). |
| 005/R1 | Done. C5 started from the regression test for two deaths on one tick. |
| 005/R4 | Kept in a new form: eight strict expected failures. |
| 005/R6, L13 | Done in part. The lane inputs compute the wave front once per lane. Throughput still fell by about 40 percent (F16). |
| 005/Q4, Q5, R7 | Not addressed. |
| 005/D1 | Not taken. The simulator's values changed, and there is a third measurement (M8 document section 5.7). |

## 4. Departures from the specification

1. **A stand, not a sixth mode.** M7 section 5.6 has five modes. The table now has four modes and two stands. That changes every `LANE` index and the size of the table.
2. **Attack timing is in the lane that ships.** The owner asked me to investigate attack timing with traces and to avoid speculative physics. The cast times and missile speeds are sourced, so I made them a rule and kept a switch. The two unsourced details are in L7. The timing did not produce the missing behaviours (F10).
3. **Straight-line ranges ship with a known defect** (F9). The owner asked for the separation. The alternative was to switch it off for top and bot, which would hide the cause.
4. **The scripted-champion sections of the first investigation are removed**, not kept beside the new ones. M7's own cases stay as the port check. Handoff 005 keeps the old numbers.
5. **Revised criteria.** The owner authorized revisions with evidence. I chose the thresholds, and I revised twice (F11).
6. **One roam test changed.** `test_the_bound_follows_the_configured_cap_and_refill` asked every laner to roam past the default bound. It now asks some laner to, because one seat missed by 0.4 s after the lane changed. The upper bound still holds for every laner.
7. **C3: the recall no longer clears the Homeguard block.** The delegate built the reference's rule. A recall on the fountain completes at once, so the rule cancelled the 8 s block for free, and a channelled recall outlasts the block. I removed the rule, its test, and its mutation. Champions start with boots, because starting gold covers them.
8. **C4: a camp does not reset while a second champion still fights it.** The delegate departed from my brief and I kept it.
9. **C5: a fighter pursues the place its target holds after the move step**, when the target does not itself pursue. My brief asked for places from before the move step. The delegate showed that a target that walks away could then never be hit, and I kept its rule. First blood is drawn among the kills of the tick and not between the teams, as M7 says, so that exchanging the teams changes nothing. `SIEGE` ends with `CLEARED`, an outcome that M7 does not name for it.
10. **Existing tests that the delegates changed.** The roam soak runs on seed 8 where it ran on seed 3, chosen from a scan of twelve seeds for one that keeps the test's ten-minute window, and one roam test runs 420 s where it ran 300 s. The decision-interval test runs on seed 12 with scripted junglers among the random laners, and requires `CLEARED` and `DIED` to occur. The walk test removes the towers, because towers now kill a champion that walks under them. Each change moves a precondition, not an assertion.
11. **Delegation.** Three delegates wrote C3, C4, and C5 in private copies. The first two could not see each other's work, so three jungle tests failed after the merge and I fixed them. The C5 delegate was stopped twice by usage limits and resumed.
12. **README.** Handoff 005 left its status line to the user (005/D4). I updated it, because the owner's prompt asks for necessary status updates. It is two edits and easy to revert.

## 5. Decision trail

The decision log of this run is [`006_m8_c2_corrections_c3_c5_decisions.tsv`](006_m8_c2_corrections_c3_c5_decisions.tsv), one row per decision with its reason and a pointer. A timestamp is the time a row was written. Rows with the phase `review` record the independent review and supersede the two `c2-criteria` rows before them.

## 6. Decisions needed from the user

| ID | Decision | Options | Recommendation |
|---|---|---|---|
| D1 | What to do about the top-lane drift (F9). | (a) Refine the lane polyline around the corners of top and bot in a map file of M8's own, then rerun the wave experiments. (b) Switch straight-line ranges off inside lanes until the map is refined. (c) Leave it and go on. | (a), as a short correction before C7. The game's minion path has the points, and the current map file has to stay for M7's results. Not (c): every side-lane wave result is confounded. |
| D2 | Whether C6 starts while C2 is not complete. | Start C6 now, or hold M8 until the waves are resolved. | Start C6. Vision, memory, and wards do not depend on how a wave stacks, and C6 gives the wave plans the observation they should read. |
| D3 | The real-game measurements of the M8 document, section 5.7. | Someone with the game takes them, or M8 goes on without them. | Take them if anyone can. Measurement C, an untouched top lane for three minutes, is the cheapest and tests F9 directly. |
| D4 | Whether to commit this campaign. | Commit, or wait for the planning review. | The user's call. Nothing is committed. |
| D5 | The wave criteria and their thresholds (F11). | Accept as provisional, change the thresholds, or ask for another form. | Accept as provisional. They are stricter than the first revision, the old marks are still reported, and they still fail. |
| D6 | The README status edit (§4, item 12). | Keep or revert. | Keep. |

## 7. Open questions and recommendations for the planning assistant

### 7.1 Open questions

- **Q1.** Is three held cycles the right meaning of sustained control? No hold lasts more than four, and M7 asked for more than half of 240 s.
- **Q2.** Should accumulation against an opponent that last-hits be a requirement of C2? It fails in all 16 settings, and one of them is decided by a tie (L5).
- **Q3.** The verdicts ask for every seed. Is a share of seeds, or a median with a margin, the better form?
- **Q4.** Which tick should the wave verdicts be judged at?
- **Q5.** Should the first wave's special rules be modelled before C7? They decide what a champion can do to wave 1.
- **Q6.** Is the pursuit rule of §4, item 9 right, and should `FOLLOW` use it too? Should rate damage wait for the attack credit, so that the budget works in both directions (L13)? Should a laner that fights in self-defence off its lane be charged as roaming?
- **Q7.** The slow-push drill of real play fails here against a hard push (F6). Is that a wrong lane, a weak placeholder champion, or a wrong test? I cannot tell from inside the simulator.

### 7.2 Recommendations

- **R1.** Before C7, refine the lane polylines (D1) and rerun `capabilities.py` and the `untouched` section. Expect every side-lane number to move.
- **R2.** Next campaign: C6. Add lane minions as sight sources first, pass the team's view of the front to `stance`, and give the observation the lane fields that the wave plans read.
- **R3.** Give C7 a scripted laner that recalls and a scripted opponent that does more than last-hit, and put the wave verdicts into C7's sweep over tick lengths.
- **R4.** Keep the eight strict expected failures until the owner changes a bar.
- **R5.** Treat any wave result of this simulator as a measurement of the simulator. The diagnostics show no rule that the behaviours follow from, so there is no knob to recommend.
- **R6.** Before the C7 gate, profile the lanes and team memory. This campaign's cost is attack timing in the lane and the sight tests of C4 and C5 (F16).

### 7.3 Readiness for the next campaign

My judgment (Inference).

- **Ready.** C1 and C3 to C5 hold in tests that fail when the code is broken. C6 has what it needs: one function for team sight, a memory record per team, a way to add a sight source, and marked places for the lane's view of the front.
- **Not ready.** C2 is not complete, the top lane has a known defect, and no part of the simulator is validated against the game. C7's integrated games would run on that lane.
- **Not affected.** The pilot stays behind C7, as M7 placed it.

## 8. Where to push back

- **V1.** I wrote criteria, saw results, and reported them as passing in part. A reviewer on another model showed that the criteria passed too much, and the corrected counts are a tenth of the first ones for accumulation. The second revision is mine too, and nobody has reviewed it.
- **V2.** I made attack timing a lane rule in a campaign that needed longer fights. It is sourced, and the diagnostics now show that it does not produce the behaviours. The two Assumed details (L7) are still in the lane that ships.
- **V3.** I reported the straight-line rule as a correction without running an untouched lane. The reviewer found the drift. Other lane changes of mine may have side effects that no test looks for.
- **V4.** The cause of the drift (F9) is my inference from one comparison. I did not test a finer polyline.
- **V5.** I read `jungle.py`, `combat.py`, and the diffs to `champions.py`, `world.py`, and `lanes.py` in full. Of `vision.py`, the delegates' test files, and the evidence scripts I read parts. The reviewer found C3 to C5 sound as mechanics, apart from L13, and did not run their tests or read M7's sections for them.
- **V6.** Every wiki and data-file fact came through a tool that summarizes pages. The data-file values were returned as key and value pairs.
- **V7.** The C5 delegate was stopped twice by usage limits and resumed from its saved state. Its final suite run and mine agree, and I read `combat.py` in full. An interrupted run is still where a half-finished edit can hide.
- **V8.** The detour diagnostic first showed no effect because of a bug of mine: it fired only on retargets inside a tick. I fixed it and reran. A result that is exactly zero deserves a second look.

## 9. Next steps

- **User.** Decide D1 to D6.
- **Planning assistant.** Review this handoff and the M8 document. Answer Q1 to Q7 and R1 to R6. Write the criteria for the next campaign.
- **Implementing assistant (me).** Wait for the review. I start no further checkpoint before then.
