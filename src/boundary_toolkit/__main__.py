"""Command line: python -m boundary_toolkit parcels.gpkg --id-field APN --ids 101 102 --adjoiner-field OWNER --out out/"""
from __future__ import annotations

import argparse

import geopandas as gpd

from .geo import describe_parcels, write_outputs


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="boundary_toolkit", description="Numbered boundary points, courses and metes-and-bounds descriptions from parcel polygons.")
    p.add_argument("parcels", help="any file GeoPandas can read (GeoPackage, shapefile, GeoJSON)")
    p.add_argument("--layer", help="layer name inside the file")
    p.add_argument("--id-field", required=True, help="field that identifies each parcel")
    p.add_argument("--ids", nargs="*", help="parcels to describe (default: all)")
    p.add_argument("--adjoiner-field", help="field used to name the adjoining parcels")
    p.add_argument("--tolerance", type=float, default=0.1, help="largest offset of an original vertex from a course, in CRS units (default 0.1)")
    p.add_argument("--start", default="northwest", choices=["northwest", "north"], help="rule for the point of beginning")
    p.add_argument("--seconds-decimals", type=int, default=0)
    p.add_argument("--distance-decimals", type=int, default=2)
    p.add_argument("--area-style", default="auto", choices=["auto", "ha-m2"])
    p.add_argument("--to-crs", help="reproject before describing, e.g. EPSG:2227")
    p.add_argument("--out", default="boundary_output")
    a = p.parse_args(argv)
    gdf = gpd.read_file(a.parcels, layer=a.layer) if a.layer else gpd.read_file(a.parcels)
    if a.to_crs:
        gdf = gdf.to_crs(a.to_crs)
    res = describe_parcels(gdf, a.id_field, a.ids, a.adjoiner_field, a.tolerance, None, a.start, a.seconds_decimals, a.distance_decimals)
    out = write_outputs(res, a.out, a.seconds_decimals, a.distance_decimals, a.area_style)
    for r in res:
        b = r["boundary"]
        print(f"{r['id']}: {len(b.points)} points from {b.original_vertices} vertices, closure {b.closure_written.ratio_text()}")
    print(f"written to {out}")


if __name__ == "__main__":
    main()
