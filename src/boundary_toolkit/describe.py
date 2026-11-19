"""Legal description text, coordinate tables and quality checks for a Boundary."""
from __future__ import annotations

from dataclasses import dataclass

from .bearings import quadrant_bearing
from .core import Boundary

SQFT_PER_ACRE = 43560.0


@dataclass(frozen=True)
class Units:
    """Linear unit of the projected CRS."""
    name: str          # "feet" or "meters"
    singular: str

    @staticmethod
    def from_unit_name(unit_name: str) -> "Units":
        u = unit_name.lower()
        if "foot" in u or "feet" in u or u in ("ft", "us-ft"):
            return Units("feet", "foot")
        if "metre" in u or "meter" in u or u == "m":
            return Units("meters", "meter")
        raise ValueError(f"unsupported linear unit: {unit_name!r}; reproject to a CRS in meters or feet")


def format_area(area: float, units: Units, style: str = "auto") -> str:
    """'auto' gives acres for feet and hectares for meters; 'ha-m2' gives the
    'X ha + YYYY m2' notation used in Colombian land administration."""
    if units.name == "feet":
        return f"{area / SQFT_PER_ACRE:,.3f} acres ({area:,.0f} square feet)"
    if style == "ha-m2":
        ha = int(area // 10000)
        m2 = round(area - ha * 10000)
        if m2 == 10000:
            ha, m2 = ha + 1, 0
        return f"{ha} ha + {m2:04d} m²"
    return f"{area / 10000:,.4f} hectares ({area:,.0f} square meters)"


def course_rows(b: Boundary, units: Units, seconds_decimals: int = 0, distance_decimals: int = 2) -> list[dict]:
    rows = []
    for c in b.courses:
        rows.append({"course": c.number, "from": c.from_point, "to": c.to_point,
                     "bearing": quadrant_bearing(c.azimuth).format(seconds_decimals),
                     "azimuth_deg": round(c.azimuth, 6), f"distance_{units.name}": round(c.distance, distance_decimals),
                     "adjoiner": c.adjoiner or "", f"max_deviation_{units.name}": round(c.max_deviation, 3)})
    return rows


def point_rows(b: Boundary, coord_decimals: int = 3) -> list[dict]:
    return [{"point": p, "x": round(x, coord_decimals), "y": round(y, coord_decimals)} for p, x, y in b.points]


def legal_description(b: Boundary, units: Units, parcel_label: str, crs_name: str, seconds_decimals: int = 0,
                      distance_decimals: int = 2, area_style: str = "auto", unknown_adjoiner: str = "unknown") -> str:
    """Metes-and-bounds style description, one course per paragraph."""
    p1 = b.points[0]
    lines = [f"{parcel_label}", "",
             f"Beginning at Point 1, the point of beginning, with grid coordinates X = {p1[1]:,.3f} and Y = {p1[2]:,.3f};"]
    for c in b.courses:
        bearing = quadrant_bearing(c.azimuth).format(seconds_decimals)
        along = f", along {c.adjoiner}" if c.adjoiner and c.adjoiner != unknown_adjoiner else ""
        to = "the point of beginning" if c.to_point == 1 else f"Point {c.to_point}"
        lines.append(f"thence {bearing}, a distance of {c.distance:,.{distance_decimals}f} {units.name}{along}, to {to};")
    lines[-1] = lines[-1].rstrip(";") + "."
    lines += ["", f"Containing {format_area(b.area, units, area_style)}, more or less.",
              f"Bearings are grid bearings in {crs_name}. Distances are horizontal grid distances in {units.name}."]
    return "\n".join(lines)


def quality_report(b: Boundary, units: Units, area_style: str = "auto") -> list[tuple[str, str]]:
    """Checks a reviewer would ask for before signing the description."""
    u = units.name
    rows = [("Input vertices, including junctions with neighbouring parcels", f"{b.original_vertices}"),
            ("Numbered points", f"{len(b.points)}"),
            ("Simplification tolerance", f"{b.tolerance:g} {u}"),
            ("Largest offset of an original vertex from its course", f"{b.max_deviation():.3f} {u}"),
            ("Area of the parcel", format_area(b.area, units, area_style)),
            ("Area enclosed by the numbered points", format_area(b.area_described, units, area_style)),
            ("Area difference", f"{b.area_described - b.area:+,.2f} square {u} ({(b.area_described - b.area) / b.area:+.4%})"),
            ("Closure of the description as written", f"{b.closure_written.misclosure:.4f} {u} ({b.closure_written.ratio_text()})")]
    rows += [("Note", n) for n in b.notes]
    return rows
