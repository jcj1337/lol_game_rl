"""Run metadata for M7 results files.

A script calls `stamp(seeds, config)` after its work and stores the result under the key "run".
`python -m experiments.m7.provenance` then reports, for every results file, whether the source files
it recorded still have the same content in the working tree.
"""

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULESETS = ROOT / "riftgame" / "rulesets"
RESULTS_GLOB = "experiments/m7/**/results/*.json"
PACKAGES = ("numpy", "torch")


def _sha(path: Path) -> str:
    # line endings are normalized so that a checkout with another autocrlf setting hashes the same
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _loaded_sources() -> list[Path]:
    loaded = {Path(m.__file__).resolve() for m in list(sys.modules.values()) if getattr(m, "__file__", None)}
    # torch gives some modules a bare file name, which resolves to a path under ROOT that does not exist
    ours = {p for p in loaded if ROOT in p.parents and ".venv" not in p.parts and p.is_file()}
    # this module writes the record and produces no result, so a change to it makes no result stale
    return sorted((ours - {Path(__file__).resolve()}) | set(RULESETS.glob("*.toml")))


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def _command() -> str:
    spec = getattr(sys.modules["__main__"], "__spec__", None)
    head = f"-m {spec.name}" if spec else Path(sys.argv[0]).name
    return " ".join(["python", head, *sys.argv[1:]])


def code_id(sources: dict[str, str]) -> str:
    lines = "".join(f"{path}:{digest}\n" for path, digest in sorted(sources.items()))
    return hashlib.sha256(lines.encode()).hexdigest()[:16]


def stamp(seeds, config: dict) -> dict:
    """Metadata of the current run: command, time, code identity, environment, seeds, and configuration."""
    sources = {p.relative_to(ROOT).as_posix(): _sha(p) for p in _loaded_sources()}
    return {
        "command": _command(),
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_head": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "code_id": code_id(sources),
        "sources": sources,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "packages": {name: sys.modules[name].__version__ for name in PACKAGES if name in sys.modules},
        "seeds": list(seeds),
        "config": config,
    }


def changed_sources(run: dict) -> list[str]:
    """The recorded source files whose content differs in the working tree, or is gone."""
    return [path for path, digest in run["sources"].items() if not (ROOT / path).exists() or _sha(ROOT / path) != digest]


def main() -> int:
    stale = 0
    for path in sorted(ROOT.glob(RESULTS_GLOB)):
        run = json.loads(path.read_text(encoding="utf-8")).get("run")
        name = path.relative_to(ROOT).as_posix()
        if run is None:
            print(f"NO RUN BLOCK  {name}")
            stale += 1
            continue
        changed = changed_sources(run)
        stale += bool(changed)
        status = "STALE" if changed else "current"
        print(f"{status:<8} {name}  code {run['code_id']}  {run['created_utc']}  {run['command']}")
        for source in changed:
            print(f"         changed since the run: {source}")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
