"""Run metadata for M8 results files, with the same record and check as M7.

Run: python -m experiments.m8.provenance
"""

import json
import sys

from experiments.m7.provenance import ROOT, changed_sources, stamp

RESULTS_GLOB = "experiments/m8/**/results/*.json"

__all__ = ["stamp", "main"]


def main() -> int:
    stale = 0
    for path in sorted(ROOT.glob(RESULTS_GLOB)):
        run = json.loads(path.read_text(encoding="utf-8")).get("run")
        name = path.relative_to(ROOT).as_posix()
        changed = ["no run block"] if run is None else changed_sources(run)
        stale += bool(changed)
        print(f"{'STALE' if changed else 'current':<8} {name}" + ("" if run is None else f"  code {run['code_id']}  {run['created_utc']}  {run['command']}"))
        for source in changed:
            print(f"         changed since the run: {source}")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
