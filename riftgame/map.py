"""Route-graph map. A position is a distance along a route.

Nodes are named junctions with League coordinates. An edge is a straight route
between two nodes. `Pos(edge, offset)` is `offset` units from the edge's first
node. A lane is a chain of edges from the blue base to the red base, so waves,
towers, and champions on a lane share one lane coordinate `s`.

Three measures, all in League units. Movement uses `distance`, the shortest
route. Interaction ranges (attack, XP, tower, ward placement) use `separation`,
the straight line between map coordinates, which terrain does not block. Sight
uses `sees`: within the radius by `separation` and `sight_clear`.

Sight terrain: open ground is every point within an edge's half-width of its
straight segment, and a wall is a segment no sight line may cross.
"""

import math
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path

MAP_DIR = Path(__file__).parent / "rulesets"
REFERENCE_MAP = "map_summoners_rift"
SIGHT_STEP = 50.0


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


def _in_corridor(corridor: tuple[float, ...], x: float, y: float) -> bool:
    ax, ay, dx, dy, per_length_sq, half_width_sq = corridor
    f = ((x - ax) * dx + (y - ay) * dy) * per_length_sq
    f = 0.0 if f < 0.0 else 1.0 if f > 1.0 else f
    ex, ey = x - ax - f * dx, y - ay - f * dy
    return ex * ex + ey * ey <= half_width_sq


def _crosses(ax: float, ay: float, bx: float, by: float, wall: tuple[float, ...]) -> bool:
    cx, cy, dx, dy = wall
    side_c = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    side_d = (bx - ax) * (dy - ay) - (by - ay) * (dx - ax)
    if side_c * side_d >= 0.0:
        return False
    side_a = (dx - cx) * (ay - cy) - (dy - cy) * (ax - cx)
    side_b = (dx - cx) * (by - cy) - (dy - cy) * (bx - cx)
    return side_a * side_b < 0.0


class RiftMap:
    def __init__(self, nodes: dict[str, tuple[float, float]], edges: list[tuple[str, str, float]],
                 lanes: dict[str, list[str]], half_widths: Sequence[float] | None = None,
                 walls: Sequence[Sequence[Sequence[float]]] = ()):
        """`half_widths` gives each edge's open ground, in the order of `edges`. Without it all ground is open."""
        self.node_names = list(nodes)
        self.node_xy = [nodes[n] for n in self.node_names]
        self._node_id = {n: i for i, n in enumerate(self.node_names)}
        self.edges: list[Edge] = []
        self._edge_between: dict[tuple[int, int], int] = {}
        self._corridors: list[tuple[float, ...]] = []
        for i, (a_name, b_name, detour) in enumerate(edges):
            a, b = self._node_id[a_name], self._node_id[b_name]
            (ax, ay), (bx, by) = self.node_xy[a], self.node_xy[b]
            self._edge_between[(a, b)] = self._edge_between[(b, a)] = len(self.edges)
            self.edges.append(Edge(a, b, math.hypot(bx - ax, by - ay) * detour))
            dx, dy = bx - ax, by - ay
            half_width = math.inf if half_widths is None else half_widths[i]
            self._corridors.append((ax, ay, dx, dy, 1.0 / (dx * dx + dy * dy), half_width * half_width))
        self._walls = [(x1, y1, x2, y2) for (x1, y1), (x2, y2) in walls]
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

    def separation(self, a: Pos, b: Pos) -> float:
        """Straight-line distance between two positions. Terrain does not shorten or block it."""
        (ax, ay), (bx, by) = self.xy(a), self.xy(b)
        return math.hypot(bx - ax, by - ay)

    def sight_clear(self, a: Pos, b: Pos) -> bool:
        """True when the straight segment between two positions crosses no wall and stays on open ground.

        Open ground is sampled every `SIGHT_STEP` units, so terrain thinner than that can be stepped over.
        """
        # One sample order for both argument orders keeps the answer exactly symmetric.
        if (b.edge, b.offset) < (a.edge, a.offset):
            a, b = b, a
        (ax, ay), (bx, by) = self.xy(a), self.xy(b)
        for wall in self._walls:
            if _crosses(ax, ay, bx, by, wall):
                return False
        if a.edge == b.edge:
            return True
        steps = math.ceil(math.hypot(bx - ax, by - ay) / SIGHT_STEP)
        near = self._corridors[a.edge]
        for i in range(1, steps):
            x, y = ax + (bx - ax) * i / steps, ay + (by - ay) * i / steps
            if not _in_corridor(near, x, y):
                for near in (self._corridors[b.edge], *self._corridors):
                    if _in_corridor(near, x, y):
                        break
                else:
                    return False
        return True

    def sees(self, a: Pos, b: Pos, radius: float) -> bool:
        """True when `b` is within `radius` of `a` in a straight line and no terrain lies between them."""
        return self.separation(a, b) <= radius and self.sight_clear(a, b)

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
    jungle = data["edges"]["jungle"]
    terrain = data["terrain"]
    half_width, river = terrain["half_width"], {frozenset(e) for e in terrain["river"]}
    if not river <= {frozenset(e) for e in jungle}:
        raise ValueError("terrain.river must name edges listed under edges.jungle")
    half_widths = [half_width["lane"]] * len(edges)
    half_widths += [half_width["river" if frozenset(e) in river else "jungle"] for e in jungle]
    edges += [(a, b, detour["jungle"]) for a, b in jungle]
    rift = RiftMap(nodes, edges, data["lanes"], half_widths, terrain["walls"])
    towers = []
    for tower_name, (x, y) in data["towers"].items():
        team, lane, tier = tower_name.split("_")
        towers.append(TowerSite(tower_name, team, lane, tier, rift.project_to_lane(lane, x, y)))
    spawns = {}
    for barracks_name, (x, y) in data["barracks"].items():
        team, lane = barracks_name.split("_")
        spawns[(team, lane)] = rift.project_to_lane(lane, x, y)
    return MapData(rift, tuple(towers), spawns, dict(data["camps"]), dict(data["scuttlers"]))
