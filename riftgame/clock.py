"""One world's state on a finer clock, so that a decision state can be compared at several ticks (checkpoint C8).

`refine` copies a world to a tick that divides its own a whole number of times. Every count of ticks in the state
is multiplied by that number, which keeps every duration exact. It reads and writes the state's fields and changes
no rule of the kernel.
"""

from dataclasses import replace

from riftgame.champions import NO_HOMEGUARD, RIFT
from riftgame.world import World


def refine(world: World, tick_s: float) -> World:
    """A copy of `world` on a finer clock, whose tick `tick_s` is the world's own divided by a whole number k. Any
    other tick raises `ValueError`.

    Every count of ticks is multiplied by k, so each timer falls at the same game second as before. That holds for a
    recall channel, a respawn, a ward, a camp's spawn, a slow, a lockdown cooldown, Homeguard's block, the ages and
    known spawns of memory, and the decision interval, so a decision tick stays a decision tick. A negative tick is
    a sentinel (-1, `NEVER`, `NO_HOMEGUARD`) and stays. What the lanes hold in seconds stays too: minion attacks,
    missiles, and the wave clock. A timer that the old clock rounded up to a whole tick keeps that rounding.

    Three fields keep their meaning only in part.
    `EnemyMemory.was` is the place one tick before the last sighting. It moves to the share 1 - 1/k of the route
    from that place to the sighting, as if the champion walked at a constant speed (Assumed).
    Homeguard decays from the end of the move that began on the fountain. A move that has begun lasted one old tick,
    so its tick becomes the last of its k new ticks and the decay starts at the same game second. A move still to
    come begins on the new clock.
    A fight is lost after more than one tick within range of a target out of view. `channel` keeps its seconds, so a
    fight that has stood one tick in range is lost one new tick later instead of one old tick.

    Two values of an observation look one tick ahead and differ after a refinement. A dead champion's `dead_s`
    counts the tick of its respawn, so it is shorter by the difference of the two ticks. The Homeguard bonus is read
    at the middle of the coming tick.
    """
    k = round(world.config.tick_s / tick_s)
    if k < 1 or abs(k * tick_s - world.config.tick_s) > 1e-9:
        raise ValueError(f"a tick of {tick_s} s does not divide the world's tick of {world.config.tick_s} s a whole number of times")
    out = World.restore(world.snapshot())
    if k == 1:
        return out

    def at(tick: int) -> int:
        return tick * k if tick >= 0 else tick

    out.config = replace(out.config, tick_s=tick_s, decision_ticks=out.config.decision_ticks * k)
    out.tick *= k
    for c in out.champions:
        c.intent_tick, c.outcome_tick, c.respawn_tick = at(c.intent_tick), at(c.outcome_tick), at(c.respawn_tick)
        c.respawned_tick = at(c.respawned_tick)
        c.homeguard_block, c.slow_until = at(c.homeguard_block), at(c.slow_until)
        c.lockdown_tick, c.ward_tick = at(c.lockdown_tick), at(c.ward_tick)
        c.hurt_tick = [at(tick) for tick in c.hurt_tick]
        c.channel *= k
        if c.homeguard_tick != NO_HOMEGUARD:
            c.homeguard_tick = min(at(c.homeguard_tick) + k - 1, out.tick)
    for camp in out.camps:
        camp.spawn_tick = at(camp.spawn_tick)
    out.sights = [replace(s, expires=at(s.expires)) for s in out.sights]
    for memory in out.memory:
        for known in memory.camps:
            known.seen_tick, known.spawn_tick = at(known.seen_tick), at(known.spawn_tick)
        for record in memory.enemies:
            record.seen_tick = at(record.seen_tick)
            if record.was is not None:
                record.was = RIFT.advance(record.was, record.pos, RIFT.distance(record.was, record.pos) * (1 - 1 / k))
        for record in (*memory.waves, *memory.towers):
            record.seen_tick = at(record.seen_tick)
    for sim in out.lanes.values():
        sim.tick, sim.tick_s = sim.tick * k, tick_s
    return out
