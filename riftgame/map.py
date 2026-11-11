"""Route-graph map. A position is a distance along a route.

Nodes are named junctions with League coordinates. An edge is a straight route
between two nodes. `Pos(edge, offset)` is `offset` units from the edge's first
node. A lane is a chain of edges from the blue base to the red base, so waves,
towers, and champions on a lane share one lane coordinate `s`. Every range in
the rules (attack, XP, sight) is a route distance in the same units.
"""

import math
import tomllib
from dataclasses import dataclass
from functools import cache
from pathlib import Path

MAP_DIR = Path(__file__).parent / "rulesets"
REFERENCE_MAP = "map_summoners_rift"


@dataclass(frozen=True, slots=True)
class Pos:
    edge: int
    offset: float


@dataclass(frozen=True, slots=True)
class Edge:
    a: int
    b: int
    length: float


@dataclass(frozen=True, slots=True)
class Lane:
    name: str
    edges: tuple[int, ...]
    starts: tuple[float, ...]
    length: float


class RiftMap:
    def __init__(self, nodes: dict[str, tuple[float, float]], edges: list[tuple[str, str, float]],
                 lanes: dict[str, list[str]]):
        self.node_names = list(nodes)
        self.node_xy = [nodes[n] for n in self.node_names]
        self._node_id = {n: i for i, n in enumerate(self.node_names)}
        self.edges: list[Edge] = []
        self._edge_between: dict[tuple[int, int], int] = {}
        for a_name, b_name, detour in edges:
            a, b = self._node_id[a_name], self._node_id[b_name]
            (ax, ay), (bx, by) = self.node_xy[a], self.node_xy[b]
            self._edge_between[(a, b)] = self._edge_between[(b, a)] = len(self.edges)
            self.edges.append(Edge(a, b, math.hypot(bx - ax, by - ay) * detour))
        self._solve_all_pairs()
        self.lanes = {name: self._build_lane(name, chain) for name, chain in lanes.items()}
        self._lane_of_edge = {e: lane for lane in self.lanes.values() for e in lane.edges}

    def _solve_all_pairs(self) -> None:
        n = len(self.node_names)
        dist = [[math.inf] * n for _ in range(n)]
        hop = [[-1] * n for _ in range(n)]
        for i in range(n):
            dist[i][i] = 0.0
            hop[i][i] = i
        for e in self.edges:
            if e.length < dist[e.a][e.b]:
                dist[e.a][e.b] = dist[e.b][e.a] = e.length
                hop[e.a][e.b], hop[e.b][e.a] = e.b, e.a
        for k in range(n):
            dk = dist[k]
            for i in range(n):
                dik = dist[i][k]
                if dik == math.inf:
                    continue
                di, hi = dist[i], hop[i]
                for j in range(n):
                    through = dik + dk[j]
                    if through < di[j]:
                        di[j] = through
                        hi[j] = hi[k]
        self.node_dist = dist
        self._next_hop = hop

    def _build_lane(self, name: str, chain: list[str]) -> Lane:
        ids = [self._node_id[n] for n in chain]
        edge_ids, starts, total = [], [], 0.0
        for a, b in zip(ids, ids[1:]):
            e = self._edge_between[(a, b)]
            if self.edges[e].a != a:
                raise ValueError(f"lane {name}: edge {chain} must be declared from blue to red")
            edge_ids.append(e)
            starts.append(total)
            total += self.edges[e].length
        return Lane(name, tuple(edge_ids), tuple(starts), total)

    def at(self, node: str) -> Pos:
        """A position at a named node."""
        n = self._node_id[node]
        for i, e in enumerate(self.edges):
            if e.a == n:
                return Pos(i, 0.0)
            if e.b == n:
                return Pos(i, e.length)
        raise KeyError(node)

    def xy(self, pos: Pos) -> tuple[float, float]:
        e = self.edges[pos.edge]
        (ax, ay), (bx, by) = self.node_xy[e.a], self.node_xy[e.b]
        f = pos.offset / e.length
        return ax + (bx - ax) * f, ay + (by - ay) * f

    def _route(self, src: Pos, dst: Pos) -> tuple[float, int, int]:
        """Shortest route length, the node to leave `src`'s edge by, and the node to enter `dst`'s edge by.

        Exit node -1 means both positions are on one edge and the direct route is shortest.
        """
        es, ed = self.edges[src.edge], self.edges[dst.edge]
        best, exit_node, entry_node = math.inf, -1, -1
        if src.edge == dst.edge:
            best = abs(dst.offset - src.offset)
        for out_node, out_cost in ((es.a, src.offset), (es.b, es.length - src.offset)):
            row = self.node_dist[out_node]
            for in_node, in_cost in ((ed.a, dst.offset), (ed.b, ed.length - dst.offset)):
                total = out_cost + row[in_node] + in_cost
                if total < best:
                    best, exit_node, entry_node = total, out_node, in_node
        return best, exit_node, entry_node

    def distance(self, a: Pos, b: Pos) -> float:
        return self._route(a, b)[0]

    def travel_time(self, a: Pos, b: Pos, speed: float) -> float:
        return self.distance(a, b) / speed

    def advance(self, pos: Pos, dest: Pos, step: float) -> Pos:
        """Move up to `step` units from `pos` along the shortest route to `dest`."""
        total, exit_node, entry_node = self._route(pos, dest)
        if total <= step:
            return dest
        if exit_node == -1:
            return Pos(pos.edge, pos.offset + math.copysign(step, dest.offset - pos.offset))
        e = self.edges[pos.edge]
        to_exit = pos.offset if exit_node == e.a else e.length - pos.offset
        if to_exit > step:
            return Pos(pos.edge, pos.offset + (-step if exit_node == e.a else step))
        step -= to_exit
        node = exit_node
        while node != entry_node:
            following = self._next_hop[node][entry_node]
            edge_id = self._edge_between[(node, following)]
            edge = self.edges[edge_id]
            if edge.length > step:
                return Pos(edge_id, step if edge.a == node else edge.length - step)
            step -= edge.length
            node = following
        last = self.edges[dest.edge]
        return Pos(dest.edge, step if last.a == node else last.length - step)

    def lane_s(self, lane: str, pos: Pos) -> float | None:
        """Lane coordinate of `pos` (distance from the lane's blue end), or None if off that lane."""
        ln = self.lanes[lane]
        if self._lane_of_edge.get(pos.edge) is not ln:
            return None
        return ln.starts[ln.edges.index(pos.edge)] + pos.offset

    def lane_pos(self, lane: str, s: float) -> Pos:
        ln = self.lanes[lane]
        s = min(max(s, 0.0), ln.length)
        for e, start in zip(reversed(ln.edges), reversed(ln.starts)):
            if s >= start:
                return Pos(e, s - start)
        return Pos(ln.edges[0], 0.0)


    def project_to_lane(self, lane: str, x: float, y: float) -> float:
        """Lane coordinate of the point on the lane nearest to (x, y)."""
        ln = self.lanes[lane]
        best_gap, best_s = math.inf, 0.0
        for e, start in zip(ln.edges, ln.starts):
            edge = self.edges[e]
            (ax, ay), (bx, by) = self.node_xy[edge.a], self.node_xy[edge.b]
            dx, dy = bx - ax, by - ay
            f = min(1.0, max(0.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
            gap = math.hypot(x - (ax + f * dx), y - (ay + f * dy))
            if gap < best_gap:
                best_gap, best_s = gap, start + f * edge.length
        return best_s


@dataclass(frozen=True, slots=True)
class TowerSite:
    name: str
    team: str
    lane: str
    tier: str
    s: float


@dataclass(frozen=True, slots=True)
class MapData:
    """The reference map plus the fixed sites on it."""

    rift: RiftMap
    towers: tuple[TowerSite, ...]
    minion_spawn_s: dict[tuple[str, str], float]
    camps: dict[str, str]
    scuttlers: dict[str, str]


@cache
def load_map(name: str = REFERENCE_MAP) -> MapData:
    with open(MAP_DIR / f"{name}.toml", "rb") as f:
        data = tomllib.load(f)
    nodes = {n: (xy[0], xy[1]) for n, xy in data["nodes"].items()}
    detour = data["detour"]
    edges = [(a, b, detour["lane"]) for chain in data["lanes"].values() for a, b in zip(chain, chain[1:])]
    edges += [(a, b, detour["lane"]) for a, b in data["edges"]["base"]]
    edges += [(a, b, detour["jungle"]) for a, b in data["edges"]["jungle"]]
    rift = RiftMap(nodes, edges, data["lanes"])
    towers = []
    for tower_name, (x, y) in data["towers"].items():
        team, lane, tier = tower_name.split("_")
        towers.append(TowerSite(tower_name, team, lane, tier, rift.project_to_lane(lane, x, y)))
    spawns = {}
    for barracks_name, (x, y) in data["barracks"].items():
        team, lane = barracks_name.split("_")
        spawns[(team, lane)] = rift.project_to_lane(lane, x, y)
    return MapData(rift, tuple(towers), spawns, dict(data["camps"]), dict(data["scuttlers"]))
