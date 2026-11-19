"""Adjoining parcels along each edge, in pure Python (shared by GeoPandas and ArcPy front ends)."""
from __future__ import annotations

import math

from .core import Coord, point_segment_distance


def _project_t(p: Coord, a: Coord, b: Coord) -> tuple[float, float]:
    """Parameter t of the projection of p on segment ab, and the distance to it."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2 if L2 else 0.0
    return t, math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def insert_junctions(ring: list[Coord], neighbour_rings: list[list[Coord]], snap: float) -> list[Coord]:
    """Add to the ring the vertices of neighbouring parcels that fall on its edges,
    so that every change of adjoiner happens at a vertex."""
    cand = [c for r in neighbour_rings for c in r]
    out: list[Coord] = []
    n = len(ring)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        extra = set()
        for c in cand:
            t, d = _project_t(c, a, b)
            if d <= snap and 0.0 < t < 1.0 and math.dist(c, a) > snap and math.dist(c, b) > snap:
                extra.add((t, (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))))
        out.append(a)
        out += [q for _, q in sorted(extra)]
    return out


def ring_distance(p: Coord, ring: list[Coord]) -> float:
    n = len(ring)
    return min(point_segment_distance(p, ring[i], ring[(i + 1) % n]) for i in range(n))


def edge_adjoiners(ring: list[Coord], neighbour_rings: list[list[Coord]], labels: list[str], snap: float,
                   unknown: str = "unknown") -> list[str]:
    """Label of the neighbouring parcel along each edge (vertex i to i + 1): the
    nearest neighbour boundary to the edge midpoint, if within ``snap``."""
    res = []
    n = len(ring)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        best, best_d = unknown, snap
        for r, lab in zip(neighbour_rings, labels):
            d = ring_distance(mid, r)
            if d <= best_d:
                best, best_d = lab, d
        res.append(best)
    return res
