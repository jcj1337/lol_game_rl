# Handoffs

This folder holds the reports that pass work between the three participants in this project:

- **The user** makes every decision. Each handoff opens with a summary and the decisions it needs, so the user can
  stop reading there.
- **The planning assistant** writes the roadmap, the design documents and the specifications in `docs/`. It also
  reviews every handoff.
- **The implementing assistant** (Claude Code) implements the approved specifications. After each piece of work, it
  writes a handoff here that reports what it did, what it found and what it recommends.

The planning assistant answers a handoff in the next document it writes. It can also add a review file to this
folder, named after the handoff with `_review` appended, such as `001_roadmap_review_review.md`. Either way, it cites
the item IDs it accepts, rejects or changes, and gives the reason for each.

## Conventions

- **Names.** Name each file `NNN_short-slug.md`, numbered in order.
- **Frozen after review.** Once the planning assistant has reviewed a handoff, nobody edits it. A correction goes
  into a later handoff that names the item it corrects. An edit made before review adds a revision row to the
  header table.
- **Item IDs.** Each item has an ID that is unique within its handoff. From another document, cite an item as
  `001/R3`. The letter gives the kind of item:
  - F is a finding.
  - C is a concern.
  - R is a recommendation.
  - D is a decision for the user.
  - Q is an open question.
  - V is a claim to verify.
- **Evidence labels.** Every claim carries one of three labels:
  - **Verified** means checked directly in code, data or a run, with a reference.
  - **Reported** means taken from a document without a second check.
  - **Inference** means the author's own judgement.
- **References.** Each reference links a file and, where it helps, a line. Links are relative to the handoff file,
  so `../../lol_gt_laning/` is the predecessor project and `../docs/` holds this project's documents. Both projects
  sit in the same parent folder.

## Contents of a handoff

Each handoff covers these parts in this order. Add a section when the work needs one, and write "none" for a part
with nothing to report.

1. A header table with the number, the date, the type (review, implementation or experiment), the specification it
   answers and the status
2. A summary for the user of ten lines at most
3. The scope, meaning what was done and inspected and what was not
4. The results, with evidence labels
5. Departures from the specification, with the reasons
6. Decisions needed from the user
7. Open questions and recommendations for the planning assistant
8. The claims the reviewer should check hardest
9. Next steps for each participant
