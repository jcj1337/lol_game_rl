"""Keyed, stateless randomness.

A draw is a pure function of (seed, key). No generator object advances, so a
snapshot stores only the seed, and a counterfactual branch that changes one
champion's action leaves every draw with a different key unchanged.
"""

from enum import IntEnum

_MASK = (1 << 64) - 1


class Stream(IntEnum):
    """First key component. One member per source of randomness in the rules."""

    MINION_TARGET = 1
    MINION_DAMAGE = 2
    LAST_HIT = 3
    COMBAT = 4
    CAMP = 5
    HIDDEN_STATE = 6
    POLICY = 7


def _mix(z: int) -> int:
    z = (z + 0x9E3779B97F4A7C15) & _MASK
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK
    return z ^ (z >> 31)


def keyed_u64(seed: int, *key: int) -> int:
    h = _mix(seed & _MASK)
    for part in key:
        h = _mix(h ^ (part & _MASK))
    return h


def keyed_uniform(seed: int, *key: int) -> float:
    """Uniform float in [0, 1) for this (seed, key)."""
    return (keyed_u64(seed, *key) >> 11) * (1.0 / (1 << 53))
