"""Boundary courses from a parcel polygon, in pure Python (no GIS dependency).

The input is the exterior ring of a parcel as (x, y) coordinates in a projected
CRS and, optionally, one adjoiner label per edge. The output is a set of
numbered boundary points and straight courses that a legal (metes and bounds)
description can follow:

* points are numbered clockwise from a chosen point of beginning;
* a point is always kept where the adjoining owner changes;
* between those points, only the vertices needed to keep every original vertex
  within ``tolerance`` of a straight course are kept (minimal breaks).

Keeping the module free of GeoPandas, Shapely and ArcPy lets the same code run
in a plain Python environment and inside the ArcGIS Pro Python environment.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .bearings import azimuth, closure, rounded_azimuth, Closure

Coord = tuple[float, float]


def signed_area(ring: list[Coord]) -> float:
    """Shoelace area; positive for counter-clockwise rings. Open ring expected."""
    n = len(ring)
    return 0.5 * sum(ring[i][0] * ring[(i + 1) % n][1] - ring[(i + 1) % n][0] * ring[i][1] for i in range(n))


def open_ring(coords: list[Coord]) -> list[Coord]:
    """Drop the closing vertex and consecutive duplicates."""
    out: list[Coord] = []
    for c in coords:
        c = (float(c[0]), float(c[1]))
        if not out or math.dist(out[-1], c) > 1e-9:
            out.append(c)
    if len(out) > 1 and math.dist(out[0], out[-1]) <= 1e-9:
        out.pop()
    if len(out) < 3:
        raise ValueError("a parcel boundary needs at least three distinct vertices")
    return out


def clockwise(ring: list[Coord], labels: list[str] | None = None) -> tuple[list[Coord], list[str] | None]:
    """Return the ring (and its edge labels) in clockwise order.

    Edge i joins vertex i to vertex i + 1. Reversing the ring turns edge i into
    edge n - 2 - i (mod n), so the labels are permuted accordingly."""
    if signed_area(ring) < 0:
        return ring, labels
    n = len(ring)
    rev = ring[::-1]
    if labels is None:
        return rev, None
    return rev, [labels[(n - 2 - j) % n] for j in range(n)]


def start_index(ring: list[Coord], start: str | int = "northwest") -> int:
    """Index of the point of beginning: 'northwest' (largest y - x), 'north'
    (largest y, then smallest x) or an explicit vertex index."""
    if isinstance(start, int):
        return start % len(ring)
    if start == "north":
        return max(range(len(ring)), key=lambda i: (ring[i][1], -ring[i][0]))
    if start == "northwest":
        return max(range(len(ring)), key=lambda i: (ring[i][1] - ring[i][0], ring[i][1]))
    raise ValueError(f"unknown start rule: {start!r}")


def point_segment_distance(p: Coord, a: Coord, b: Coord) -> float:
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.dist(p, (ax + t * dx, ay + t * dy))


def minimal_breaks(stretch: list[Coord], tolerance: float) -> list[int]:
    """Douglas-Peucker on an open polyline: indices of the vertices to keep so that
    every vertex lies within ``tolerance`` of the kept straight courses. The two
    end vertices are always kept."""
    keep = {0, len(stretch) - 1}
    stack = [(0, len(stretch) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        k, dmax = max(((m, point_segment_distance(stretch[m], stretch[i], stretch[j])) for m in range(i + 1, j)), key=lambda t: t[1])
        if dmax > tolerance:
            keep.add(k)
            stack += [(i, k), (k, j)]
    return sorted(keep)


@dataclass
class Course:
    number: int
    from_point: int
    to_point: int
    azimuth: float
    distance: float
    adjoiner: str | None
    max_deviation: float      # largest offset of an original vertex from this straight course


@dataclass
class Boundary:
    points: list[tuple[int, float, float]]          # (point number, x, y), clockwise from the point of beginning
    courses: list[Course]
    area: float                                     # area of the original polygon
    area_described: float                           # area enclosed by the numbered points
    original_vertices: int
    tolerance: float
    closure_written: Closure | None = None          # closure of the description as written (rounded values)
    notes: list[str] = field(default_factory=list)

    def max_deviation(self) -> float:
        return max((c.max_deviation for c in self.courses), default=0.0)


def describe_ring(coords: list[Coord], edge_labels: list[str] | None = None, tolerance: float = 0.1,
                  start: str | int = "northwest", seconds_decimals: int = 0, distance_decimals: int = 2) -> Boundary:
    """Build numbered points and courses for one exterior ring.

    ``edge_labels[i]`` names the adjoiner along the edge from vertex i to vertex
    i + 1 of ``coords`` (closing vertex optional). ``tolerance`` is in CRS units."""
    ring = open_ring(coords)
    if edge_labels is not None and len(edge_labels) != len(ring):
        raise ValueError(f"expected {len(ring)} edge labels, got {len(edge_labels)}")
    area = abs(signed_area(ring))
    ring, labels = clockwise(ring, edge_labels)
    s = start_index(ring, start)
    ring = ring[s:] + ring[:s]
    if labels is not None:
        labels = labels[s:] + labels[:s]
    n = len(ring)

    # fixed points: the point of beginning and every vertex where the adjoiner changes
    fixed = [0] + ([i for i in range(1, n) if labels[i] != labels[i - 1]] if labels is not None else [])
    kept: list[int] = []
    for a, b in zip(fixed, fixed[1:] + [n]):
        stretch = [ring[i % n] for i in range(a, b + 1)]
        kept += [a + k for k in minimal_breaks(stretch, tolerance)[:-1]]
    kept = sorted(set(kept))
    if len(kept) < 3:                                  # a polygon needs at least three corners
        far = max((i for i in range(n) if i not in kept), key=lambda i: min(math.dist(ring[i], ring[k]) for k in kept))
        kept = sorted(set(kept) | {far})
        if len(kept) < 3:
            kept = sorted(set(kept) | {max((i for i in range(n) if i not in kept), key=lambda i: point_segment_distance(ring[i], ring[kept[0]], ring[kept[1]]))})

    points = [(k + 1, ring[i][0], ring[i][1]) for k, i in enumerate(kept)]
    courses: list[Course] = []
    for k, i in enumerate(kept):
        j = kept[(k + 1) % len(kept)]
        between = [ring[m % n] for m in range(i + 1, j if j > i else j + n)]
        dev = max((point_segment_distance(p, ring[i], ring[j]) for p in between), default=0.0)
        courses.append(Course(k + 1, k + 1, (k + 1) % len(kept) + 1, azimuth(*ring[i], *ring[j]),
                              math.dist(ring[i], ring[j]), labels[i] if labels is not None else None, dev))

    written = [(rounded_azimuth(c.azimuth, seconds_decimals), round(c.distance, distance_decimals)) for c in courses]
    b = Boundary(points, courses, area, abs(signed_area([ring[i] for i in kept])), n, tolerance, closure(written))
    if b.max_deviation() > tolerance + 1e-9:
        b.notes.append("a course exceeds the tolerance: a corner was added only to keep at least three points")
    return b
