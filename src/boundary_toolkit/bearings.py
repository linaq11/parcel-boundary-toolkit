"""Grid bearings, distances and traverse closure for boundary courses.

Bearings are grid bearings in the projected CRS of the input data (not true or
magnetic bearings). Azimuths are measured clockwise from grid north.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


def azimuth(x0: float, y0: float, x1: float, y1: float) -> float:
    """Grid azimuth in degrees, clockwise from north, in [0, 360)."""
    return math.degrees(math.atan2(x1 - x0, y1 - y0)) % 360.0


def _dms(angle: float, seconds_decimals: int = 0) -> tuple[int, int, float]:
    """Split a non-negative angle into degrees, minutes and seconds, rounding the
    seconds first so that 59.9999" carries into the next minute."""
    scale = 10 ** seconds_decimals
    total = round(angle * 3600.0 * scale)
    deg, rem = divmod(total, 3600 * scale)
    mins, secs = divmod(rem, 60 * scale)
    return int(deg), int(mins), secs / scale


@dataclass(frozen=True)
class Bearing:
    ns: str          # "N" or "S"
    angle: float     # 0 to 90 degrees
    ew: str          # "E" or "W"

    def format(self, seconds_decimals: int = 0) -> str:
        d, m, s = _dms(self.angle, seconds_decimals)
        if d == 90:                                   # rounding reached a cardinal direction
            return "Due East" if self.ew == "E" else "Due West"
        if d == 0 and m == 0 and s == 0:
            return "Due North" if self.ns == "N" else "Due South"
        sec = f"{s:0{3 + seconds_decimals if seconds_decimals else 2}.{seconds_decimals}f}"
        return f"{self.ns} {d:02d}°{m:02d}'{sec}\" {self.ew}"

    def to_azimuth(self) -> float:
        if self.ns == "N":
            return self.angle if self.ew == "E" else (360.0 - self.angle) % 360.0
        return 180.0 - self.angle if self.ew == "E" else 180.0 + self.angle


def quadrant_bearing(az: float) -> Bearing:
    """Convert an azimuth (degrees from north) to a quadrant bearing."""
    az = az % 360.0
    if az <= 90.0:
        return Bearing("N", az, "E")
    if az <= 180.0:
        return Bearing("S", 180.0 - az, "E")
    if az <= 270.0:
        return Bearing("S", az - 180.0, "W")
    return Bearing("N", 360.0 - az, "W")


def rounded_azimuth(az: float, seconds_decimals: int = 0) -> float:
    """Azimuth after rounding its quadrant bearing to whole (or decimal) seconds,
    i.e. the direction a reader recovers from the written description."""
    b = quadrant_bearing(az)
    d, m, s = _dms(b.angle, seconds_decimals)
    return Bearing(b.ns, d + m / 60.0 + s / 3600.0, b.ew).to_azimuth()


@dataclass(frozen=True)
class Closure:
    misclosure: float     # linear misclosure, CRS units
    perimeter: float
    precision: float      # perimeter / misclosure (inf if exact)

    def ratio_text(self) -> str:
        return "exact" if math.isinf(self.precision) else f"1:{self.precision:,.0f}"


def closure(courses: list[tuple[float, float]]) -> Closure:
    """Closure of a traverse given as (azimuth in degrees, distance) courses."""
    lat = sum(d * math.cos(math.radians(a)) for a, d in courses)
    dep = sum(d * math.sin(math.radians(a)) for a, d in courses)
    mis = math.hypot(lat, dep)
    per = sum(d for _, d in courses)
    return Closure(mis, per, math.inf if mis < 1e-12 else per / mis)
