import re

from riftgame.ruleset import REFERENCE, RULESET_DIR, interpolated, load, scheduled

STATUS_TAG = re.compile(r"#\s*(F2|F1|D|M|A)\s*$")


def test_every_value_line_carries_a_status_tag():
    untagged = []
    for path in sorted(RULESET_DIR.glob("*.toml")):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped[0] in "#[]":
                continue
            if not STATUS_TAG.search(stripped):
                untagged.append((path.name, number))
    assert untagged == []


def test_wave_interval_follows_the_reference_schedule():
    schedule = load()["minions"]["interval_schedule"]
    assert scheduled(schedule, 30) == 30
    assert scheduled(schedule, 839) == 30
    assert scheduled(schedule, 840) == 25
    assert scheduled(schedule, 1800) == 20


def test_minion_stats_grow_between_their_endpoints_and_clamp():
    melee = load()["minions"]["melee"]
    assert interpolated(melee["hp"], melee["hp_span_s"], 0) == 465
    assert interpolated(melee["hp"], melee["hp_span_s"], 10_000) == 1550
    mid = interpolated(melee["hp"], melee["hp_span_s"], 1470)
    assert 465 < mid < 1550


def test_ordinary_camps_are_three_per_buff_quadrant_with_clock_spawns():
    camps = load()["camps"]
    names = [k for k, v in camps.items() if isinstance(v, dict)]
    assert sorted(names) == sorted(
        ["blue_sentinel", "gromp", "murk_wolves", "raptors", "red_brambleback", "krugs"]
    )
    assert {camps[n]["first_spawn_s"] for n in names} == {55, 67}
    assert camps["blue_sentinel"]["respawn_s"] == 300
    assert camps["raptors"]["respawn_s"] == 135
