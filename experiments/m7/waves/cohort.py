"""M7 wave prototype, bake-off variant: each wave's minions of one kind are one stack with pooled HP."""

from dataclasses import dataclass
from math import ceil, inf

from experiments.m7.waves.lane import (
    EPS,
    KINDS,
    TOWER_ATTACK_SPEED,
    TOWER_RANGE,
    ChampionInput,
    Kind,
    KindRules,
    Lane,
    Mode,
    Team,
    Tick,
    Tower,
    unit_stats,
)

FRONT_ORDER = {Kind.MELEE: 0, Kind.SIEGE: 1, Kind.CASTER: 2}


@dataclass(slots=True, eq=False)
class Stack:
    """n minions at one position. hp is the pool, wound is damage every member has taken, and one member absorbs the rest."""

    uid: int
    team: int
    rules: KindRules
    s: float
    n: int
    hp: float
    max_hp: float
    ad: float
    gold: float
    delay: float = 0.0
    wound: float = 0.0
    credit: float = 1.0
    target: "Stack | Tower | None" = None
    near: "Stack | None" = None
    near_gap: float = inf
    anchored: bool = False
    free_at: float = 0.0

    def front_hp(self) -> float:
        return self.hp - (self.n - 1) * (self.max_hp - self.wound)


@dataclass(slots=True, eq=False)
class _Champion:
    inp: ChampionInput
    credit: float


class CohortLane(Lane):
    """Stacks trade whole volleys once per tick, focused on the front member of the nearest enemy stack. No randomness."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._joining: dict[tuple[int, Kind], tuple[int, Stack]] = {}

    def add_minion(self, team: int, kind: Kind, s: float, when: float | None = None, delay: float = 0.0, count: int = 1) -> Stack:
        hp, ad, gold = unit_stats(kind, self.time if when is None else when)
        stack = Stack(self._next_uid(team), team, KINDS[kind], s, count, hp * count, hp, ad, gold, delay)
        self.bodies[team].append(stack)
        self.spawned += count
        return stack

    def units(self, team: int) -> list[tuple[float, int]]:
        return [(stack.s, stack.n) for stack in self.bodies[team]]

    def _spawn(self, team: int, kind: Kind, wave: int, when: float, delay: float, slot: int) -> None:
        joined_wave, stack = self._joining.get((team, kind), (0, None))
        if joined_wave == wave and stack.hp > 0:
            stack.n += 1
            stack.hp += stack.max_hp - stack.wound
            self.spawned += 1
        else:
            self._joining[team, kind] = wave, self.add_minion(team, kind, self.geometry.spawn_s(team), when, delay)

    def _pick(self, stack: Stack, tied: list) -> Stack:
        return min(tied, key=lambda foe: (FRONT_ORDER[foe.rules.kind], foe.uid))

    def _fight(self, tick: Tick) -> None:
        dt, end = self.dt, tick.t0 + self.dt
        volleys = []
        for team in Team:
            for stack in self.bodies[team]:
                target, speed = stack.target, stack.rules.attack_speed
                if target is None or abs(target.s - stack.s) > stack.rules.attack_range + EPS:
                    stack.credit = min(1.0, stack.credit + speed * dt)
                    continue
                start = max(stack.free_at, target.free_at)
                total = min(1.0, stack.credit + speed * start) + speed * (dt - start)
                stack.credit = total - int(total)
                if int(total):
                    volleys.append((target, stack, int(total) * stack.n))
        champions = []
        for inp in tick.inputs:
            credit = self._champion_credit.get(inp.champ_id, 1.0) + inp.attack_speed * inp.capacity * dt
            champions.append(_Champion(inp, credit))
        for champion in champions:
            inp = champion.inp
            if inp.mode is Mode.PUSH:
                for stack in self._in_range(inp):
                    self._burn(stack, inp.aoe_dps * inp.capacity * dt, inp.champ_id, end, tick)
        for tower in self.towers:
            in_range = any(abs(stack.s - tower.s) <= TOWER_RANGE + EPS for stack in self.bodies[1 - tower.team])
            total = tower.credit + TOWER_ATTACK_SPEED * dt
            if tower.hp <= 0 or not in_range:
                tower.credit = min(1.0, total)
                continue
            tower.credit = total - int(total)
            for _ in range(int(total)):
                stack = self._tower_target(tower)
                if stack is not None:
                    self._claim(stack, champions, end, tick)
                    self._damage(stack, stack.rules.tower_shot_pct * stack.max_hp, None, end, tick)
        volleys.sort(key=lambda volley: (volley[0].team, getattr(volley[0], "uid", -1), volley[1].uid))
        for target, stack, blows in volleys:
            if type(target) is Tower:
                self._hit_tower(target, blows * stack.ad * stack.rules.tower_multiplier, end, tick)
            elif target.hp > 0:
                self._claim(target, champions, end, tick)
                self._damage(target, blows * (stack.ad + stack.rules.pct_current_hp * max(0.0, target.front_hp())), None, end, tick)
        for champion in champions:
            inp = champion.inp
            for stack in self._in_range(inp):
                self._claim(stack, [champion], end, tick)
            while champion.credit >= 1.0 and inp.mode in (Mode.THIN, Mode.PUSH):
                foes = self._in_range(inp)
                if inp.mode is Mode.THIN:
                    foes = [stack for stack in foes if stack.rules.kind is Kind.CASTER] or foes
                if not foes:
                    break
                champion.credit -= 1.0
                self._damage(min(foes, key=lambda stack: (stack.front_hp(), stack.uid)), inp.hit_damage, inp.champ_id, end, tick)
            self._champion_credit[inp.champ_id] = min(1.0, champion.credit)

    def _in_range(self, inp: ChampionInput) -> list[Stack]:
        return [stack for stack in self.bodies[1 - inp.team] if stack.hp > 0 and abs(stack.s - inp.s) <= inp.attack_range + EPS]

    def _claim(self, stack: Stack, champions: list, t: float, tick: Tick) -> None:
        for champion in champions:
            inp = champion.inp
            if inp.team == stack.team or inp.mode is Mode.NONE or abs(stack.s - inp.s) > inp.attack_range + EPS:
                continue
            while champion.credit >= 1.0 and stack.hp > 0 and stack.front_hp() <= inp.hit_damage:
                champion.credit -= 1.0
                self._damage(stack, stack.front_hp(), inp.champ_id, t, tick)

    def _burn(self, stack: Stack, damage: float, killer: int, t: float, tick: Tick) -> None:
        front = stack.front_hp()
        stack.wound += damage
        if front <= damage or stack.wound >= stack.max_hp:
            lost = stack.n if stack.wound >= stack.max_hp else 1
            stack.n -= lost
            stack.hp = stack.n * (stack.max_hp - stack.wound)
            for _ in range(lost):
                self._death(stack, killer, t, tick)
        else:
            stack.hp -= damage * stack.n

    def _damage(self, stack: Stack, damage: float, killer: int | None, t: float, tick: Tick) -> None:
        stack.hp -= damage
        alive = max(0, ceil(stack.hp / (stack.max_hp - stack.wound) - 1e-9))
        for _ in range(stack.n - alive):
            self._death(stack, killer, t, tick)
        stack.n = alive
