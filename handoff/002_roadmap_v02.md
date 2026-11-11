# Handoff 002: ROADMAP v0.2 from the owner's decisions

| | |
|---|---|
| Number | 002 |
| Date | 2026-11-11 |
| Type | Documentation revision. I wrote no code and ran no experiments. |
| Responds to | The owner's v0.2 decisions (pasted prompt, 2026-11-11) and [`docs/ROADMAP.md`](../docs/ROADMAP.md) v0.1 |
| Status | Delivered. Waiting for review of v0.2 by the user and the planning assistant. |
| Author | Claude Code (Opus 5.5), the implementing assistant |

**Reading guide.** The user can read §1, §6 and §7. The planning assistant should read all of it before writing
`docs/design/M7_architecture.md`. §5 records which items of handoff 001 the decisions adopted, changed or overruled.

## 1. Summary

- [`docs/ROADMAP.md`](../docs/ROADMAP.md) is now v0.2, rewritten as one document rather than v0.1 plus appended
  instructions.
- It follows the owner's decisions where they differ from handoff 001. M8 is a full-map foundation with ten
  champions, and its gate requires the components to work together. Basic evaluation doesn't depend on learning.
  Consequences are reported separately until complete games exist.
- A script traces each decision to the section that owns it. All 124 checks pass, and none of the five phrases it
  forbids appears. Another check found no wording that fixes a choice the decisions leave open.
- An independent reviewer on a different model found 13 issues. I fixed 11, kept one wording on purpose, and
  rejected one (§3.4).
- I added a few things the decisions didn't ask for, mostly statements of who owns what (§4). The user can strike
  any of them.
- The roadmap roughly doubled, from 1,915 to 3,951 words. Most of the growth is content the decisions mandate.

## 2. Scope

I read these before writing:

- `docs/ROADMAP.md` v0.1, `README.md` and `handoff/001_roadmap_review.md`
- The owner's decisions, saved verbatim from the session as `decisions_v02_prompt.md` in the session scratchpad,
  so the reviewer could read them

This repository has no instruction files such as `CLAUDE.md`, so `README.md` was the only repository guidance.

I changed `docs/ROADMAP.md` and added this handoff. I didn't write `docs/design/M7_architecture.md`, didn't touch the
laning repository, and committed nothing. `git status` shows only `docs/ROADMAP.md` modified and `handoff/`
untracked.

## 3. Results

### 3.1 What changed, section by section

| v0.2 section | change from v0.1 |
|---|---|
| Header | Bold lead-ins on separate lines. The status points to §10. |
| [§1 Vision](../docs/ROADMAP.md#L9) | States the guiding principle (abstract execution, consequential outcomes). Adds the jungler destination question. Calls the tool an evaluator throughout. |
| [§2 Scope](../docs/ROADMAP.md#L27) | Names ten champions, two junglers and a two-champion bot lane. Combat outcome models no longer include a separate gank model. Manual scenarios are the initial input. |
| [§3 Principles](../docs/ROADMAP.md#L55) | Principles 1 to 9 keep their numbers, with new detail on information sources, interfaces, information boundaries, timing, snapshots and reuse. Principles 10 (versioned rules, pinned replays) and 11 (abstract execution, consequential outcomes) are new. |
| [§4 Scenarios](../docs/ROADMAP.md#L69) | Adds four rows covering jungler destinations, side lane against grouping, bot-lane allocation, and unusual states. Recall now covers arrival timing. The definition list now asks for decision-time information and separates individual from team alternatives. |
| [§5 Milestones](../docs/ROADMAP.md#L95) | Rewritten per decision 2. Adds a dependencies paragraph. |
| [§6 Comparing decisions](../docs/ROADMAP.md#L242) | New section for decisions 3 and 5. |
| [§7 Validation](../docs/ROADMAP.md#L259) | Was §6. Adds snapshot and anti-leakage tests from M8, exploitability, ranking sensitivity and the external track, and keeps the baselines. |
| [§8 Risks](../docs/ROADMAP.md#L278) | Was §7. Adds continuation dependence and integration risk. |
| [§9 Next actions](../docs/ROADMAP.md#L291) | Was §8. The next step is to review v0.2, then write M7. |
| [§10 Revision summary](../docs/ROADMAP.md#L300) | New. |

v0.1 §6 to §8 are now §7 to §9. Handoff 001 cites v0.1 section numbers, and those citations still refer to v0.1.

### 3.2 Where each decision lives

| decision | v0.2 location |
|---|---|
| 1. Vision, M7 to M13, full-map foundation, integration gate | [§1](../docs/ROADMAP.md#L9), [M8 deliverables and done-when](../docs/ROADMAP.md#L127) |
| 2. M7 additions | [M7 deliverables](../docs/ROADMAP.md#L101) |
| 2. M8 supporting mechanics | [M8 deliverables](../docs/ROADMAP.md#L127) |
| 2. M9, combat from M8, purchase thresholds | [M9](../docs/ROADMAP.md#L153) |
| 2. M10, towers already in M8, rushing and stalling, termination | [M10](../docs/ROADMAP.md#L172) |
| 2. M11, builds on M8 fog, no belief model fixed | [M11](../docs/ROADMAP.md#L189) |
| 2. M12, early pilot placed by M7, empirical shaping | [M12](../docs/ROADMAP.md#L206), [pilot](../docs/ROADMAP.md#L210) |
| 2. M13, quality and external validation, no real-game claim | [M13](../docs/ROADMAP.md#L225) |
| 3. Evaluation independent of learning | [§6](../docs/ROADMAP.md#L242), [principle 3](../docs/ROADMAP.md#L59) |
| 4. Scenario validation and added checks | [§4](../docs/ROADMAP.md#L69), [§7](../docs/ROADMAP.md#L259) |
| 5. Rewards separate from evaluation outputs | [principle 7](../docs/ROADMAP.md#L63), [§6](../docs/ROADMAP.md#L242) |
| 6. Abstraction requirements | [principles 2, 5 and 11](../docs/ROADMAP.md#L58), [M7 combat considerations](../docs/ROADMAP.md#L101) |
| 7. Reuse and reproducibility | [principles 6, 9 and 10](../docs/ROADMAP.md#L62) |
| 8. Choices left open | [§10 list](../docs/ROADMAP.md#L300), [principle 4](../docs/ROADMAP.md#L60), and the Open lines of M9, M11 and M12 |
| Revision summary and next actions | [§10](../docs/ROADMAP.md#L300), [§9](../docs/ROADMAP.md#L291) |

### 3.3 Checks

| check | result | label |
|---|---|---|
| Decision trace, 124 patterns, each required inside its owning section | 124 of 124 pass. v0.1 passed 18 of the original 116. | Verified |
| Absence checks for 5 phrases the review fixes removed | None present. | Verified |
| Wording that fixes something left open, such as time values, filters, combat formulas, win-probability models, network types, slices, spikes, or camp counts | 0 hits. v0.1 had 1 ("six standard camps"). | Verified |
| Style lint (dashes, semicolons, mid-sentence colons, slashes, Latin abbreviations, curly quotes, sentences over 25 words) | 0. v0.1 had 101. | Verified |
| Links in v0.2 and in this handoff | All resolve. | Verified |
| Independent review of meaning, on Claude Sonnet 5.5 | 13 findings, handled as §3.4 describes. | Verified |

I wrote the trace patterns from my own reading of the decisions, and the reviewer pointed that out. A pattern
checks that a phrase is in the right section, not that the sentence around it is right. The independent review is
what checks meaning.

### 3.4 Independent review

The reviewer worked read-only. It got the decisions, v0.1, v0.2, handoff 001 and the decision log, but not my
conclusions.

| finding | severity | action |
|---|---|---|
| M7 pointed to "the combat considerations of principle 11", which lists none | Defect | Fixed. M7 lists them, and M9 takes the ones M7 defers. |
| No milestone owned how comparisons get plausible hidden states | Should-fix | Fixed. M7 designs it, the M8 harness runs across them, and M11's inference can supply them. No method is named. |
| Basic warding had no owner | Judgment call | Fixed. Placing it is now an M7 deliverable, and M11's richer wards build on whatever M7 assigns. |
| The length had doubled, with rules repeated in several places | Should-fix | Partly fixed. I removed repetition from principles 3, 5 and 6. The rest of the growth is mandated (V4). |
| Missing dependencies: M10 on M9's combat, the M12 campaign on M9 and M11, the pilot's interface, and M8's stand-ins before M9 | Should-fix | Fixed in the §5 dependencies paragraph, the pilot paragraph and the M7 checkpoint plan. |
| Validation checks and §4 scenarios had no starting milestone | Should-fix | Fixed. M7's validation plan assigns each one to the milestone that first tests it. |
| Both M7 and M8 owned the clock values | Should-fix | Fixed. M8's Open line no longer lists them. |
| Four phrases might commit to detail. They are one shared wave system, "the random state" in snapshots, an interface M8 never introduced, and "role-aware". | Judgment call | The first three are fixed. "Role-aware" stays, because it is v0.1 wording about the interface, not about the policy architecture the decisions leave open. |
| v0.1 content dropped without a mention | Judgment call | Fixed. The revision summary now lists it. |
| Principle 7 pointed training rewards at §6, and "state construction" had no definition | Should-fix | Fixed. |
| The revision summary undercounted the reworked principles | Judgment call | Fixed. |
| M12's done-when made attacker lower bounds a gate | Judgment call | Removed. Attacker evaluation stays a deliverable and a §7 check. |
| The log had weak evidence, rows logged after the fact, a blank row 9, and unlogged forks | Should-fix | The log now has rows that supersede the wrong ones and add the missing forks. I rejected the blank-row claim, because the log had no ninth row. |

## 4. Departures from the decisions

I made no change that contradicts a decision. These are the places where I added to the decisions:

1. **Dependencies paragraph (§5).** The decisions asked me to check for missing dependencies, and v0.1 stated none.
2. **The pilot before complete games (M12).** A pilot that runs before M10 can't learn from wins, so M7 decides what
   it learns from. The pilot uses the same interface as M8's scripted agents.
3. **Risks 5 and 6 (§8).** Continuation dependence and integration risk.
4. **Scope note (§2).** M8 builds minimal versions of most of the listed scope, and later milestones develop them.
5. **New M7 ownership items, from the review.** M7 now covers:
   - where plausible hidden states come from
   - where basic warding belongs
   - what M8 uses for champion capability and spending until M9
   - which milestone first tests each §4 scenario and §7 check

These follow from the decisions but change v0.1 wording:

6. **M9 completion criterion.** v0.1 said the model "can sometimes favor a fed solo champion against two weaker
   enemies". v0.2 says that uneven outcomes follow from capabilities and context, and that the conditions for winning
   a 1v2 come from stated assumptions. This follows decision 4 ("not force a named strategy to win").
7. **M9 profiles.** v0.1 said "role-independent archetype profiles". v0.2 says "champion capability profiles" and
   leaves their representation to M9, per decision 8 ("do not fix champion archetypes").
8. **Camp count.** v0.1 said "six standard camps per jungle". v0.2 says "the standard camps of both jungles".

## 5. Handoff 001 items after the decisions

| 001 item | status in v0.2 |
|---|---|
| R1 input contract | Adopted. M7 lists information needs and sources, with manual scenarios as the input. |
| R2 vertical slices | Overruled. M8 is a full-map foundation, and M7 plans its checkpoints. |
| R3 evaluation independent of RL | Adopted, with the owner's conditions in §6 of v0.2. |
| R4 time model | Partly adopted. M7 defines the semantics and the relation between clocks, and no value is fixed. My 15-second inference isn't used. |
| R5 currency versus reward | Adopted in a changed form. Consequences are reported separately, and no win-probability model or shaping guarantee is prescribed. |
| R6 oracle rules | Adopted in a changed form as principle 11. Execution skill is left open. |
| R7 reproducibility regime | Adopted as principle 10. |
| R8 external data | Adopted as a small track in §7. M7's validation plan places it. |
| R9 completion criteria | Adopted in a changed form. Attackers and ranking sensitivity were added as checks, and the baselines stay. |
| D3 rank-typical opponents | Changed. Styles aren't labelled rank-typical without validation. |
| D5 spikes during M7 | Overruled. There are no prototypes now, and a pilot runs once M8 is usable. |
| C8 item purchases | Overruled. M9 tests purchase thresholds, and the predecessor isn't treated as evidence against them. |

## 6. Decisions needed from the user

| ID | decision | options | recommendation |
|---|---|---|---|
| D1 | The additions in §4, items 1 to 5 | Keep them all, or strike any | Keep them all. Each one states a dependency, a risk or an owner the decisions imply. |
| D2 | Who places basic warding | (a) M7 decides, as v0.2 says. (b) Put basic warding in M8 now. (c) Put it in M11. | (a) |

## 7. Concerns that stay open

None of these reopens a settled choice.

- **C1. The M8 gate is large.** The foundation integrates about a dozen subsystems before any learning. v0.2 gives
  M7's checkpoint plan the job of keeping each step testable (risk 6). The plan will need a measurable gate at each
  checkpoint, or M8 has no intermediate evidence of progress (Inference).
- **C2. Comparisons before M10 may often give no clear ranking.** Long-horizon decisions, such as trading an
  objective or holding a side lane, pay off later than any pre-M10 horizon can measure. A "no clear ranking" result
  for them is expected, not a defect. M7 should say so, so that nobody reads it as failure (Inference).
- **C3. Manual scenarios must carry what each player knew.** Snapshots include observation history or memory, and
  many target decisions depend on last-seen information. So a manually specified scenario has to encode each
  player's knowledge and any actions in progress, not only positions and resources. This is a design point for M7's
  scenario format (Inference).

## 8. Where to push back

- **V1.** I wrote the trace patterns myself, and they check phrases, not meaning. §3.4 covers meaning.
- **V2.** The additions in §4, items 1 to 5, go beyond the decisions. Strike any that read as scope.
- **V3.** The reworded M9 criterion in §4, item 6, changes v0.1's wording, which the decisions didn't explicitly ask
  for.
- **V4.** Length. v0.2 is about twice v0.1. Most of the growth is content the decisions mandate. That content is
  the new M7 and M8 items, §6, four scenario rows, the validation checks, two principles, and the revision summary.
  The review fixes added ownership lines on top. If v0.2 reads as too long, the M7 and M8 deliverable lists are
  where to cut.
- **V5.** I wrote the roadmap myself, though the workflow in `handoff/README.md` gives that role to the planning
  assistant. I followed the request as given, so the planning assistant should review v0.2 as if another author
  wrote it.

The scripts are `roadmap_check.py` (the decision trace and the commitment check) and `handoff_check.py` (lint and
links). Both are in the session scratchpad, and the user can ask to copy them into the repository.

## 9. Next steps

- **User.** Review v0.2 and decide D1 and D2.
- **Planning assistant.** Review v0.2, then write `docs/design/M7_architecture.md`. Address C1 to C3 there.
- **Implementing assistant (me).** Wait for an approved M7 specification. I won't start implementation before then.
