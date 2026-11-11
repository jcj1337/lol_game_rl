"""M7 feasibility kernel: one game per World, a fixed tick, one intent per champion that ends when it completes.

A prototype, not the M8 build.
"""

import hashlib
import math
import pickle
from enum import IntEnum
from typing import NamedTuple

from riftgame import ruleset
from riftgame.map import Pos, load_map
from riftgame.rng import Stream, keyed_uniform
from riftgame.ruleset import interpolated

from experiments.m7.kernel.lanes import ChampionInput, StubLane
from experiments.m7.kernel.profiles import ASSUMPTIONS as A
from experiments.m7.kernel.profiles import ROAM_CAP_S, ROAM_REFILL, ROLE_LANE, ROLES, STATS, next_cost, stats

R = ruleset.load()
E, V, F, T = R["economy"], R["vision"], R["fountain"], R["towers"]
MAP = load_map()
RIFT = MAP.rift
LANES = ("top", "mid", "bot")
FOUNTAIN = (RIFT.at("blue_fountain"), RIFT.at("red_fountain"))
RECALL_S = R["recall"]["cast_s"] + R["recall"]["channel_s"]
TOWER_POS = {t.name: RIFT.lane_pos(t.lane, t.s) for t in MAP.towers}
TOWER_XY = {name: RIFT.xy(pos) for name, pos in TOWER_POS.items()}
BUFFS = ("blue_sentinel", "red_brambleback")


class Kind(IntEnum):
    HOLD = 0
    MOVE = 1
    FARM = 2
    CAMP = 3
    FIGHT = 4
    RECALL = 5
    WARD = 6
    KEEP = 7


class Intent(NamedTuple):
    """MOVE and WARD target a Pos, FARM a (lane, mode), CAMP a camp name, FIGHT an enemy champion id.

    KEEP is an action only. A champion never holds it.
    """

    kind: Kind
    target: object = None


HOLD = Intent(Kind.HOLD)
RECALL = Intent(Kind.RECALL)
KEEP = Intent(Kind.KEEP)


class Outcome(IntEnum):
    """How a champion's last finished intent ended. FARM and HOLD never finish by themselves."""

    NONE = 0
    ARRIVED = 1
    CLEARED = 2
    ABSENT = 3
    KILLED = 4
    LOST = 5
    PLACED = 6
    RECALLED = 7
    INTERRUPTED = 8
    DIED = 9


class CampInfo(NamedTuple):
    kind: str
    pos: Pos
    xy: tuple[float, float]
    hp: float
    gold: float
    xp: float
    first_spawn_s: float
    respawn_s: float
    window_s: float
    dps: float


def _camp_info(kind: str, node: str) -> CampInfo:
    scuttler = kind == "scuttler"
    rules = R["scuttler"] if scuttler else R["camps"][kind]
    window = R["camps"]["timer_window_buff_s" if kind in BUFFS else "timer_window_other_s"]
    pos = RIFT.at(node)
    return CampInfo(kind, pos, RIFT.xy(pos), rules["hp"][0] * (rules["first_spawn_hp_factor"] if scuttler else 1.0),
                    rules["gold"][0] if scuttler else rules["gold"], rules["xp"][0], rules["first_spawn_s"],
                    rules["respawn_s"], window, 0.0 if scuttler else A["camp_dps"])


CAMPS = {name: _camp_info(kind, name) for name, kind in MAP.camps.items()}
CAMPS |= {f"scuttle_{side}": _camp_info("scuttler", node) for side, node in MAP.scuttlers.items()}
# Towers and minions stay on lanes, and every route from a camp to a lane passes a lane node first.
# A camp farther than their sight from every lane node can only be seen by champions, wards, and shrines.
LANE_NODES = {RIFT.node_names[n] for lane in RIFT.lanes.values() for e in lane.edges for n in (RIFT.edges[e].a, RIFT.edges[e].b)}
LANE_SIGHT = max(T["sight_range"], R["minions"]["sight_range"])
OFF_LANE = frozenset(name for name, info in CAMPS.items()
                     if min(RIFT.distance(info.pos, RIFT.at(node)) for node in LANE_NODES) > LANE_SIGHT)


class Champion:
    __slots__ = ("id", "team", "role", "pos", "hp", "level", "xp", "gold", "upgrades", "intent", "channel", "slow",
                 "slow_until", "lockdown_at", "respawn_tick", "wards", "ward_timer", "kills", "deaths", "outcome", "outcome_tick",
                 "roam", *STATS)

    def __init__(self, cid: int):
        self.id, self.team, self.role, self.pos = cid, cid // 5, ROLES[cid % 5], FOUNTAIN[cid // 5]
        self.level, self.xp, self.gold, self.upgrades = 1, 0.0, float(E["starting_gold"]), 0
        self.intent, self.channel, self.outcome, self.outcome_tick = HOLD, 0.0, Outcome.NONE, -1
        self.roam = ROAM_CAP_S
        self.slow, self.slow_until, self.lockdown_at, self.respawn_tick = 0.0, 0, 0, -1
        self.wards, self.ward_timer, self.kills, self.deaths = V["ward_charges"], 0.0, 0, 0
        self.refresh()
        self.hp = self.max_hp

    def refresh(self) -> None:
        for name, value in zip(STATS, stats(self.role, self.level, self.upgrades)):
            setattr(self, name, value)


class Duty(IntEnum):
    """Where a champion stands against its laning role. `ROAM_RATE` is what each state does to the roam allowance."""

    FREE = 0      # a jungler, who has no home lane
    IN_LANE = 1   # on its home lane
    EXCUSED = 2   # off it, but dead, recalling, on its fountain, or under a FARM order for its home lane
    ROAMING = 3


ROAM_RATE = {Duty.FREE: 0.0, Duty.IN_LANE: ROAM_REFILL, Duty.EXCUSED: 0.0, Duty.ROAMING: -1.0}
LANE_EDGES = {name: frozenset(lane.edges) for name, lane in RIFT.lanes.items()}
LANE_NODE_IDS = {name: frozenset(n for e in edges for n in (RIFT.edges[e].a, RIFT.edges[e].b)) for name, edges in LANE_EDGES.items()}


def on_lane(lane: str, pos: Pos) -> bool:
    """True on an edge of the lane, and at one of its nodes even when the position names a neighbouring edge."""
    if pos.edge in LANE_EDGES[lane]:
        return True
    edge = RIFT.edges[pos.edge]
    return (pos.offset <= 0.0 and edge.a in LANE_NODE_IDS[lane]) or (pos.offset >= edge.length and edge.b in LANE_NODE_IDS[lane])


def duty(c: Champion) -> Duty:
    home = ROLE_LANE.get(c.role)
    if home is None:
        return Duty.FREE
    if c.respawn_tick >= 0:
        return Duty.EXCUSED
    if on_lane(home, c.pos):
        return Duty.IN_LANE
    returning = c.intent.kind == Kind.RECALL or (c.intent.kind == Kind.FARM and c.intent.target[0] == home)
    return Duty.EXCUSED if returning or RIFT.distance(c.pos, FOUNTAIN[c.team]) <= F["regen_radius"] else Duty.ROAMING


class Camp:
    __slots__ = ("name", "hp", "alive", "respawn_s", "aggro", "cleared_tick")

    def __init__(self, name: str):
        self.name, self.hp, self.alive, self.respawn_s = name, 0.0, False, CAMPS[name].first_spawn_s
        self.aggro, self.cleared_tick = -1, -1


class Source(NamedTuple):
    """A ward, or the shrine a scuttler leaves, as a vision source."""

    team: int
    pos: Pos
    x: float
    y: float
    sight: float
    expires: int
    ward: bool


class LastSeen(NamedTuple):
    pos: Pos
    tick: int
    hp: float
    level: int
    upgrades: int


class CampMemory:
    __slots__ = ("alive", "seen_tick", "respawn_s")

    def __init__(self, first_spawn_s: float):
        self.alive, self.seen_tick, self.respawn_s = False, -1, first_spawn_s


class TeamMemory:
    __slots__ = ("enemies", "camps")

    def __init__(self):
        self.enemies: dict[int, LastSeen] = {}
        self.camps = {name: CampMemory(info.first_spawn_s) for name, info in CAMPS.items()}


class View:
    """What one team sees this tick. `fronts[lane]` is (own front s, most advanced visible enemy minion s or -1)."""

    __slots__ = ("enemies", "camps", "fronts", "wards")


def in_sight(sources: list, x: float, y: float, pos: Pos) -> bool:
    # A route is never shorter than the straight line, so the cheap test can only reject.
    for sx, sy, spos, sight in sources:
        if (sx - x) ** 2 + (sy - y) ** 2 <= sight * sight and RIFT.distance(spos, pos) <= sight:
            return True
    return False


def _canon(o, visited: dict):
    if isinstance(o, (int, float, str, type(None))):
        return o
    if isinstance(o, dict):
        return tuple(sorted((repr(k), _canon(v, visited)) for k, v in o.items()))
    if isinstance(o, (list, tuple)):
        return tuple(_canon(v, visited) for v in o)
    if not getattr(getattr(o, "__dataclass_params__", None), "frozen", False):
        # The real wave model's minions point at each other, so a mutable object seen again becomes a back-reference.
        # A frozen value is written out every time, because a restored world may hold a copy where the original shares one.
        if id(o) in visited:
            return ("ref", visited[id(o)])
        visited[id(o)] = len(visited)
    names = getattr(o, "__slots__", None) or sorted(vars(o))
    return (type(o).__name__, *(_canon(getattr(o, n, None), visited) for n in names))


def fingerprint(state) -> str:
    """A stable hash of any part of the game state."""
    return hashlib.sha256(repr(_canon(state, {})).encode()).hexdigest()


class World:
    STATE = ("tick", "champs", "lanes", "camps", "sources", "views", "memory", "first_blood", "counts")
    __slots__ = ("seed", "dt", "decision_interval", "towers", *STATE)

    def __init__(self, seed: int = 0, dt: float = 1.0, decision_interval: int = 5, lane_factory=StubLane):
        self.seed, self.dt, self.decision_interval = seed, dt, decision_interval
        self.tick, self.first_blood = 0, False
        self.champs = [Champion(i) for i in range(10)]
        self.lanes = {name: lane_factory(name, dt, seed, i) for i, name in enumerate(LANES)}
        self.camps = {name: Camp(name) for name in CAMPS}
        self.sources: list[Source] = []
        self.views, self.memory = (View(), View()), (TeamMemory(), TeamMemory())
        self.counts = dict.fromkeys(("minion_deaths", "camp_clears", "champion_deaths", "recalls"), 0)
        self.towers = [t for lane in self.lanes.values() for t in lane.towers]
        self.see()

    def snapshot(self) -> bytes:
        state = [getattr(self, name) for name in self.STATE]
        return pickle.dumps((R["meta"]["id"], self.seed, self.dt, self.decision_interval, state), protocol=5)

    @classmethod
    def restore(cls, snapshot: bytes) -> "World":
        ruleset_id, seed, dt, decision_interval, state = pickle.loads(snapshot)
        if ruleset_id != R["meta"]["id"]:
            raise ValueError(f"snapshot is for ruleset {ruleset_id}")
        w = cls.__new__(cls)
        w.seed, w.dt, w.decision_interval = seed, dt, decision_interval
        for name, value in zip(cls.STATE, state):
            setattr(w, name, value)
        w.towers = [t for lane in w.lanes.values() for t in lane.towers]
        return w

    def digest(self) -> str:
        return fingerprint((self.seed, self.dt, [getattr(self, name) for name in self.STATE]))

    def submit(self, cid: int, action: Intent) -> None:
        c = self.champs[cid]
        if action.kind == Kind.KEEP or action == c.intent:
            return
        if action.kind == Kind.FIGHT and action.target not in self.views[c.team].enemies:
            raise ValueError(f"champion {cid} cannot start a fight with {action.target}, who is out of its team's view")
        c.intent, c.channel = action, 0.0

    def _finish(self, c: Champion, outcome: Outcome) -> None:
        c.intent, c.channel, c.outcome, c.outcome_tick = HOLD, 0.0, outcome, self.tick

    def step(self) -> None:
        now = self.tick * self.dt
        self._spawn(now)
        inputs, hits = self._act()
        self._lanes(inputs)
        self._combat(hits, now)
        self._resolve(hits, now)
        self.see()
        self.tick += 1

    def _spawn(self, now: float) -> None:
        for camp in self.camps.values():
            if not camp.alive and now >= camp.respawn_s:
                camp.alive, camp.hp = True, CAMPS[camp.name].hp
        for c in self.champs:
            if 0 <= c.respawn_tick <= self.tick:
                c.respawn_tick, c.hp = -1, c.max_hp

    def _approach(self, c: Champion, dest: Pos, within: float) -> bool:
        gap = RIFT.distance(c.pos, dest) - within
        if gap <= 1e-6:
            return True
        reach = c.speed * (1.0 - (c.slow if self.tick < c.slow_until else 0.0)) * self.dt
        c.pos = RIFT.advance(c.pos, dest, min(gap, reach))
        return gap <= reach

    def _act(self):
        """Each living champion spends its tick on its intent, so its attacks go to one of wave, camp, or champion."""
        dt, views = self.dt, self.views
        inputs: dict[str, list[ChampionInput]] = {name: [] for name in LANES}
        fighters = []
        for c in self.champs:
            if c.respawn_tick >= 0:
                continue
            kind, target = c.intent
            if kind == Kind.MOVE:
                if self._approach(c, target, 0.0):
                    self._finish(c, Outcome.ARRIVED)
            elif kind == Kind.FARM:
                lane, mode = target
                self._approach(c, RIFT.lane_pos(lane, views[c.team].fronts[lane][0]), 0.0)
                s = RIFT.lane_s(lane, c.pos)
                if s is not None:
                    inputs[lane].append(ChampionInput(c.id, c.team, s, mode, c.hit_damage, c.attack_speed, c.range, c.aoe_dps, 1.0))
            elif kind == Kind.CAMP:
                if self._approach(c, CAMPS[target].pos, c.range):
                    # The champion acts on what its team saw at the end of the last tick, as a policy does.
                    if self.memory[c.team].camps[target].alive:
                        camp = self.camps[target]
                        camp.hp -= c.camp_dps * dt
                        camp.aggro = c.id
                    else:
                        self._finish(c, Outcome.ABSENT)
            elif kind == Kind.RECALL:
                if RIFT.distance(c.pos, FOUNTAIN[c.team]) <= F["regen_radius"]:
                    self._finish(c, Outcome.RECALLED)
                else:
                    c.channel += dt
                    if c.channel >= RECALL_S - 1e-9:
                        c.pos = FOUNTAIN[c.team]
                        self.counts["recalls"] += 1
                        self._finish(c, Outcome.RECALLED)
            elif kind == Kind.WARD:
                if self._approach(c, target, V["ward_place_range"]) and c.wards > 0:
                    self._place_ward(c, target)
                    self._finish(c, Outcome.PLACED)
            elif kind == Kind.FIGHT:
                fighters.append(c)
        # Pursuers move after everyone else and aim at where each target stood before any pursuer moved,
        # so the result does not depend on champion order.
        stood = [c.pos for c in self.champs]
        for c in fighters:
            foe = c.intent.target
            if foe in views[c.team].enemies:
                self._approach(c, stood[foe], c.range * A["fight_standoff"])
                continue
            # The target is in fog, so the team's last-seen record is the only place the pursuer may go.
            # It gives up one tick after it arrives, so that the view it gives up on was taken from that spot.
            last_seen = self.memory[c.team].enemies[foe].pos
            if RIFT.distance(c.pos, last_seen) <= c.range + 1e-6:
                self._finish(c, Outcome.LOST)
            else:
                self._approach(c, last_seen, c.range)
        hits = []
        for c in fighters:
            if c.intent.kind != Kind.FIGHT:
                continue
            foe = self.champs[c.intent.target]
            if foe.id in views[c.team].enemies and RIFT.distance(c.pos, foe.pos) <= c.range:
                hits.append((c, foe, c.dps * dt * (1.0 if c.pos is stood[c.id] else A["chase_dps_factor"])))
        return inputs, hits

    def _place_ward(self, c: Champion, target: Pos) -> None:
        c.wards -= 1
        expires = self.tick + round(V["ward_duration_s"][0] / self.dt)
        self.sources.append(Source(c.team, target, *RIFT.xy(target), V["ward_sight_range"], expires, True))
        placed = [s for s in self.sources if s.ward and s.team == c.team]
        if len(placed) > V["ward_max_placed"]:
            self.sources.remove(placed[0])

    def _lanes(self, inputs) -> None:
        share = R["minions"]["xp_share"]
        for name, lane in self.lanes.items():
            for death in lane.step(inputs[name]):
                self.counts["minion_deaths"] += 1
                if death.killer >= 0:
                    self.champs[death.killer].gold += death.gold
                pos = RIFT.lane_pos(name, death.s)
                near = [c for c in self.champs if c.team != death.team and c.respawn_tick < 0
                        and RIFT.distance(c.pos, pos) <= R["minions"]["xp_range"]]
                for c in near:
                    self._gain_xp(c, death.xp * share[len(near) - 1])

    def _combat(self, hits: list, now: float) -> None:
        dt = self.dt
        duels = [(attacker, victim) for attacker, victim, _ in hits]
        for camp in self.camps.values():
            if camp.aggro < 0:
                continue
            info, c = CAMPS[camp.name], self.champs[camp.aggro]
            if camp.hp <= 0:
                self._clear(camp, c, now)
            elif c.respawn_tick < 0 and RIFT.distance(c.pos, info.pos) <= A["camp_leash"]:
                hits.append((None, c, info.dps * dt))
            else:
                camp.aggro, camp.hp = -1, info.hp
        for t in self.towers:
            if t.hp <= 0 or not (duels or t.target >= 0):
                continue
            divers = sorted({a.id for a, victim in duels if victim.team == t.team
                             and RIFT.distance(a.pos, TOWER_POS[t.name]) <= T["attack_range"]})
            if not divers:
                t.target, t.ramp = -1, 0.0
                continue
            if t.target not in divers:
                t.target, t.ramp = divers[0], 0.0
            ad = interpolated(T[t.tier]["ad"], T[t.tier]["ad_span_s"], now)
            ramp = 1.0 + min(T["champion_ramp_max"], T["champion_ramp_per_hit"] * t.ramp)
            hits.append((None, self.champs[t.target], ad * T["attack_speed"] * dt * ramp))
            t.ramp += T["attack_speed"] * dt

    def _clear(self, camp: Camp, killer: Champion, now: float) -> None:
        info = CAMPS[camp.name]
        camp.alive, camp.aggro, camp.cleared_tick, camp.respawn_s = False, -1, self.tick, now + info.respawn_s
        killer.gold += info.gold
        self._gain_xp(killer, info.xp)
        self.counts["camp_clears"] += 1
        # Only a champion standing at the camp learns of the clear this way. One still on its way finds the camp empty.
        for c in self.champs:
            if c.intent == (Kind.CAMP, camp.name) and RIFT.distance(c.pos, info.pos) <= c.range + 1e-6:
                self._finish(c, Outcome.CLEARED)
        if info.kind != "scuttler":
            return
        S = R["scuttler"]
        expires = self.tick + round(S["shrine_duration_s"] / self.dt)
        self.sources.append(Source(killer.team, info.pos, *info.xy, S["shrine_sight_radius"], expires, False))
        twin = self.camps["scuttle_bot" if camp.name == "scuttle_top" else "scuttle_top"]
        camp.respawn_s = math.inf
        if not twin.alive:
            lucky = camp if keyed_uniform(self.seed, Stream.CAMP, self.tick) < 0.5 else twin
            lucky.respawn_s = now + S["respawn_s"]

    def _gain_xp(self, c: Champion, xp: float) -> None:
        c.xp += xp
        while c.level < E["level_cap"] and c.xp >= (need := E["xp_first_level_up"] + E["xp_level_up_step"] * (c.level - 1)):
            c.xp -= need
            c.level += 1
            c.refresh()

    def _resolve(self, hits: list, now: float) -> None:
        tick, dt = self.tick, self.dt
        for attacker, victim, damage in hits:
            if damage <= 0:
                continue
            victim.hp -= damage
            if victim.intent.kind == Kind.RECALL:
                self._finish(victim, Outcome.INTERRUPTED)
            if attacker is not None and attacker.slow_frac > 0 and tick >= attacker.lockdown_at:
                victim.slow, victim.slow_until = attacker.slow_frac, tick + 1 + round(attacker.slow_s / dt)
                attacker.lockdown_at = tick + round(attacker.slow_cd_s / dt)
        for victim in self.champs:
            if victim.respawn_tick < 0 and victim.hp <= 0:
                blows = [(damage, -a.id) for a, v, damage in hits if v is victim and a is not None]
                self._die(victim, self.champs[-max(blows)[1]] if blows else None, now)
        passive = E["passive_gold_per_10s"] / 10 * dt if now >= E["passive_gold_start_s"] else 0.0
        for c in self.champs:
            c.gold += passive * (1.0 + R["support_item"]["passive_gold_per_10s"] / E["passive_gold_per_10s"] * (c.role == "support"))
            if c.wards < V["ward_charges"]:
                c.ward_timer += dt
                if c.ward_timer >= V["ward_recharge_s"][0]:
                    c.wards, c.ward_timer = c.wards + 1, 0.0
            if c.respawn_tick < 0 and RIFT.distance(c.pos, FOUNTAIN[c.team]) <= F["regen_radius"]:
                c.hp = min(c.max_hp, c.hp + F["hp_regen_per_s"] * c.max_hp * dt)
                while c.gold >= next_cost(c.role, c.upgrades):
                    c.gold -= next_cost(c.role, c.upgrades)
                    c.upgrades += 1
                    c.refresh()
            # No floor. A laner that overstays until its next decision goes into debt and repays it on its lane.
            c.roam = min(ROAM_CAP_S, c.roam + ROAM_RATE[duty(c)] * dt)

    def _die(self, victim: Champion, killer: Champion | None, now: float) -> None:
        D = R["death"]
        wait = D["respawn_s"][victim.level - 1] * (1.0 + D["time_scaling_per_30s"] * (max(0.0, now - D["time_scaling_start_s"]) // 30))
        spot = victim.pos
        victim.hp, victim.pos, victim.deaths = 0.0, FOUNTAIN[victim.team], victim.deaths + 1
        victim.respawn_tick = self.tick + 1 + math.ceil(wait / self.dt)
        self.counts["champion_deaths"] += 1
        for c in self.champs:
            if c.intent == (Kind.FIGHT, victim.id):
                self._finish(c, Outcome.KILLED)
        self._finish(victim, Outcome.DIED)
        if killer is None:
            return
        killer.kills += 1
        killer.gold += E["kill_gold_base"] + (0 if self.first_blood else E["first_blood_bonus"])
        self.first_blood = True
        near = [c for c in self.champs if c.team == killer.team and c.respawn_tick < 0
                and RIFT.distance(c.pos, spot) <= E["kill_xp_range"]]
        for c in near:
            self._gain_xp(c, (A["kill_xp_base"] + A["kill_xp_per_level"] * victim.level) / len(near))

    def _minions(self) -> list:
        return [(team, name, s, pos, *RIFT.xy(pos)) for name, lane in self.lanes.items() for team, s in lane.minions()
                for pos in (RIFT.lane_pos(name, s),)]

    def watchers(self, team: int, minions: list | None = None) -> tuple[list, list]:
        """A team's vision sources as (x, y, pos, sight) rows: those that see into the jungle, and all of them."""
        roaming = [(*RIFT.xy(c.pos), c.pos, R["champions"]["sight_range"]) for c in self.champs
                   if c.team == team and c.respawn_tick < 0]
        roaming += [(s.x, s.y, s.pos, s.sight) for s in self.sources if s.team == team]
        src = roaming + [(x, y, pos, R["minions"]["sight_range"])
                         for owner, _, _, pos, x, y in (self._minions() if minions is None else minions) if owner == team]
        src += [(*TOWER_XY[t.name], TOWER_POS[t.name], T["sight_range"]) for t in self.towers if t.team == team and t.hp > 0]
        return roaming, src

    def see(self) -> None:
        """Rebuild both teams' views and fold what they see into their memories."""
        tick, now = self.tick, self.tick * self.dt
        self.sources = [s for s in self.sources if s.expires > tick]
        alive = [c for c in self.champs if c.respawn_tick < 0]
        cxy = {c.id: RIFT.xy(c.pos) for c in alive}
        minions = self._minions()
        for team, sign in ((0, 1.0), (1, -1.0)):
            roaming, src = self.watchers(team, minions)

            def seen(x: float, y: float, pos: Pos, sources: list = src) -> bool:
                return in_sight(sources, x, y, pos)

            view, memory = self.views[team], self.memory[team]
            view.enemies = tuple(c.id for c in alive if c.team != team and seen(*cxy[c.id], c.pos))
            for cid in view.enemies:
                c = self.champs[cid]
                memory.enemies[cid] = LastSeen(c.pos, tick, c.hp, c.level, c.upgrades)
            view.camps = tuple(name for name, info in CAMPS.items()
                               if seen(*info.xy, info.pos, roaming if name in OFF_LANE else src))
            for name in view.camps:
                camp, m = self.camps[name], memory.camps[name]
                m.alive, m.seen_tick = camp.alive, tick
                if camp.alive:
                    m.respawn_s = None
                elif camp.cleared_tick == tick or camp.respawn_s - now <= CAMPS[name].window_s:
                    m.respawn_s = camp.respawn_s
                elif m.respawn_s is not None and m.respawn_s <= now:
                    m.respawn_s = None
            view.fronts = {}
            for name, lane in self.lanes.items():
                own = [sign * s for owner, ln, s, *_ in minions if owner == team and ln == name]
                own += [sign * t.s for t in lane.towers if t.team == team and t.hp > 0]
                foes = [sign * s for owner, ln, s, pos, x, y in minions if owner != team and ln == name and seen(x, y, pos)]
                home = -team * RIFT.lanes[name].length
                view.fronts[name] = (sign * max(own, default=home), sign * min(foes) if foes else -1.0)
            view.wards = tuple(s.pos for s in self.sources if s.ward and s.team != team and seen(s.x, s.y, s.pos))
