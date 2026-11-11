"""Capability profiles and every constant the reference ruleset does not give. Every number in this file is an assumption."""

import math
from functools import cache

ROLES = ("top", "jungle", "mid", "carry", "support")
ROLE_LANE = {"top": "top", "mid": "mid", "carry": "bot", "support": "bot"}

STATS = ("max_hp", "dps", "range", "speed", "slow_frac", "slow_s", "slow_cd_s",
         "hit_damage", "attack_speed", "aoe_dps", "camp_dps")
LEVEL_SCALED = frozenset(("max_hp", "dps", "hit_damage", "aoe_dps", "camp_dps"))

PROFILES = {
    "top":     (650.0, 55.0, 175.0, 340.0, 0.30, 2.0, 10.0, 65.0, 0.65, 20.0, 60.0),
    "jungle":  (600.0, 60.0, 175.0, 345.0, 0.40, 2.0, 10.0, 62.0, 0.68, 25.0, 150.0),
    "mid":     (540.0, 65.0, 525.0, 335.0, 0.25, 2.0, 12.0, 55.0, 0.63, 40.0, 70.0),
    "carry":   (520.0, 70.0, 550.0, 325.0, 0.00, 0.0, 0.0, 60.0, 0.70, 10.0, 60.0),
    "support": (560.0, 35.0, 500.0, 335.0, 0.45, 2.5, 12.0, 50.0, 0.60, 5.0, 30.0),
}

# (cost in gold, fractional stat bonuses), bought in order at the fountain
UPGRADES = {
    "top":     ((300, {"speed": 0.07}), (800, {"max_hp": 0.25}), (1100, {"dps": 0.25}), (1300, {"max_hp": 0.20, "dps": 0.20})),
    "jungle":  ((300, {"speed": 0.07}), (800, {"dps": 0.20, "camp_dps": 0.30}), (1100, {"max_hp": 0.25}), (1300, {"dps": 0.25})),
    "mid":     ((300, {"speed": 0.07}), (800, {"dps": 0.25, "aoe_dps": 0.30}), (1100, {"dps": 0.25}), (1300, {"max_hp": 0.20, "dps": 0.20})),
    "carry":   ((300, {"speed": 0.07}), (800, {"dps": 0.30, "hit_damage": 0.30}), (1100, {"dps": 0.30, "attack_speed": 0.20}), (1300, {"dps": 0.30})),
    "support": ((300, {"speed": 0.07}), (500, {"max_hp": 0.20}), (800, {"slow_frac": 0.20}), (1100, {"max_hp": 0.25})),
}

ASSUMPTIONS = {
    "level_growth": 0.08,            # per level, on the LEVEL_SCALED stats
    "fight_standoff": 0.6,           # a pursuer closes to this fraction of its range
    "chase_dps_factor": 0.5,         # damage dealt on a tick in which the attacker had to move
    "camp_dps": 6.0,                 # every camp except the scuttler
    "camp_leash": 900.0,
    "kill_xp_base": 60.0,
    "kill_xp_per_level": 40.0,
    "stub_engage_gap": 300.0,        # distance at which two minion groups stop and fight
    "stub_wave_size": 6,             # three melee and three caster, no siege minion
    "stub_last_hit_chance": {"last_hit": 0.85, "thin": 0.70, "push": 0.55},
}


@cache
def stats(role: str, level: int, upgrades: int) -> tuple[float, ...]:
    bonus: dict[str, float] = {}
    for _, changes in UPGRADES[role][:upgrades]:
        for name, value in changes.items():
            bonus[name] = bonus.get(name, 0.0) + value
    growth = 1.0 + ASSUMPTIONS["level_growth"] * (level - 1)
    return tuple(base * (growth if name in LEVEL_SCALED else 1.0) * (1.0 + bonus.get(name, 0.0))
                 for name, base in zip(STATS, PROFILES[role]))


def next_cost(role: str, upgrades: int) -> float:
    return UPGRADES[role][upgrades][0] if upgrades < len(UPGRADES[role]) else math.inf
