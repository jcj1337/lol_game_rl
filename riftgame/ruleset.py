"""Versioned rulesets. A ruleset is a TOML file of game constants, loaded once."""

import tomllib
from functools import cache
from pathlib import Path

RULESET_DIR = Path(__file__).parent / "rulesets"
REFERENCE = "patch_26_22"


@cache
def load(name: str = REFERENCE) -> dict:
    with open(RULESET_DIR / f"{name}.toml", "rb") as f:
        return tomllib.load(f)


def scheduled(schedule: list[list[float]], t: float) -> float:
    """Value of a [[start_s, value], ...] step schedule at game time t."""
    value = schedule[0][1]
    for start, v in schedule:
        if t >= start:
            value = v
    return value


def interpolated(endpoints: list[float], span_s: list[float], t: float) -> float:
    """Linear growth from endpoints[0] at span_s[0] to endpoints[1] at span_s[1], clamped."""
    lo, hi = endpoints
    t0, t1 = span_s
    frac = min(1.0, max(0.0, (t - t0) / (t1 - t0)))
    return lo + (hi - lo) * frac
