"""GeoPandas front end: read parcels, find adjoiners, write points, lines and reports."""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from shapely import STRtree
from shapely.geometry import LineString, Point

from .adjoin import edge_adjoiners, insert_junctions
from .core import describe_ring, open_ring
from .describe import Units, course_rows, point_rows
from .report import write_tables


def _exterior(g):
    if g.geom_type == "MultiPolygon":
        if len(g.geoms) > 1:
            raise ValueError("multipart parcel; describe each part separately")
        g = g.geoms[0]
    return g


def describe_parcels(parcels: gpd.GeoDataFrame, id_field: str, ids: list | None = None, adjoiner_field: str | None = None,
                     tolerance: float = 0.1, snap: float | None = None, start: str = "northwest", seconds_decimals: int = 0,
                     distance_decimals: int = 2, unknown_adjoiner: str = "unknown") -> list[dict]:
    """Describe the selected parcels. Returns one dict per parcel with the Boundary
    object and the inputs needed to write it."""
    if parcels.crs is None or not parcels.crs.is_projected:
        raise ValueError("parcels must be in a projected CRS (meters or feet); reproject them first")
    units = Units.from_unit_name(parcels.crs.axis_info[0].unit_name)
    snap = tolerance if snap is None else snap
    sel = parcels if not ids else parcels[parcels[id_field].astype(str).isin([str(i) for i in ids])]
    if sel.empty:
        raise ValueError("no parcel matches the requested ids")
    tree = STRtree(list(parcels.geometry))
    out = []
    for idx, row in sel.iterrows():
        try:
            geom = _exterior(row.geometry)
        except ValueError as e:
            raise ValueError(f"parcel {row[id_field]}: {e}") from None
        ring = open_ring(list(geom.exterior.coords))
        labels = None
        if adjoiner_field:
            near = [k for k in tree.query(geom.buffer(snap)) if parcels.index[k] != idx]
            rings = [open_ring(list(_exterior(parcels.geometry.iloc[k]).exterior.coords)) for k in near]
            ring = insert_junctions(ring, rings, snap)
            labels = edge_adjoiners(ring, rings, [str(parcels[adjoiner_field].iloc[k]) for k in near], snap, unknown_adjoiner)
        b = describe_ring(ring, labels, tolerance, start, seconds_decimals, distance_decimals)
        if len(geom.interiors):
            b.notes.append(f"the parcel has {len(geom.interiors)} interior ring(s) that are not described")
        out.append({"id": row[id_field], "boundary": b, "units": units, "crs_name": parcels.crs.name, "crs": parcels.crs})
    return out


def write_outputs(results: list[dict], out_dir: str | Path, seconds_decimals: int = 0, distance_decimals: int = 2,
                  area_style: str = "auto", label_template: str = "Parcel {id}") -> Path:
    """Tables and descriptions, plus points and courses in a GeoPackage."""
    out = Path(out_dir)
    write_tables(results, out, seconds_decimals, distance_decimals, area_style, label_template)
    pts, lns = [], []
    for r in results:
        b, u = r["boundary"], r["units"]
        for p in point_rows(b):
            pts.append({"parcel": str(r["id"]), **p, "geometry": Point(p["x"], p["y"])})
        xy = {p: (x, y) for p, x, y in b.points}
        for c in course_rows(b, u, seconds_decimals, distance_decimals):
            lns.append({"parcel": str(r["id"]), **c, "geometry": LineString([xy[c["from"]], xy[c["to"]]])})
    crs = results[0]["crs"]
    gpd.GeoDataFrame(pts, crs=crs).to_file(out / "boundaries.gpkg", layer="points", driver="GPKG")
    gpd.GeoDataFrame(lns, crs=crs).to_file(out / "boundaries.gpkg", layer="courses", driver="GPKG")
    return out
