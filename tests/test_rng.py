from riftgame.rng import Stream, keyed_u64, keyed_uniform


def test_same_seed_and_key_give_the_same_draw():
    assert keyed_uniform(7, Stream.COMBAT, 3, 120) == keyed_uniform(7, Stream.COMBAT, 3, 120)


def test_draws_do_not_depend_on_call_order():
    keys = [(Stream.MINION_DAMAGE, lane, tick) for lane in range(3) for tick in range(50)]
    forward = {k: keyed_uniform(11, *k) for k in keys}
    backward = {k: keyed_uniform(11, *k) for k in reversed(keys)}
    assert forward == backward


def test_changing_one_key_part_changes_the_draw():
    base = keyed_u64(5, Stream.COMBAT, 1, 10)
    assert keyed_u64(6, Stream.COMBAT, 1, 10) != base
    assert keyed_u64(5, Stream.CAMP, 1, 10) != base
    assert keyed_u64(5, Stream.COMBAT, 2, 10) != base
    assert keyed_u64(5, Stream.COMBAT, 1, 11) != base
    assert keyed_u64(5, Stream.COMBAT, 10, 1) != base


def test_uniform_draws_fill_the_unit_interval_evenly():
    n = 20000
    draws = [keyed_uniform(3, Stream.LAST_HIT, i) for i in range(n)]
    assert all(0.0 <= u < 1.0 for u in draws)
    bins = [0] * 10
    for u in draws:
        bins[int(u * 10)] += 1
    expected = n / 10
    chi_square = sum((b - expected) ** 2 / expected for b in bins)
    assert chi_square < 27.9  # 99.9th percentile of chi-square with 9 degrees of freedom


def test_adjacent_ticks_are_uncorrelated():
    n = 20000
    a = [keyed_uniform(9, Stream.COMBAT, 0, t) for t in range(n)]
    b = a[1:]
    mean = sum(a) / n
    cov = sum((x - mean) * (y - mean) for x, y in zip(a, b)) / (n - 1)
    var = sum((x - mean) ** 2 for x in a) / n
    assert abs(cov / var) < 0.03
