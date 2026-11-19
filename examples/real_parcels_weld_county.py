"""Real-data check with public parcels from the Weld County, Colorado open data service.

Downloads a small block of parcels (geometry, parcel number, subdivision, block,
lot and the county's GIS acreage; no owner names or addresses), projects them to
NAD83 / Colorado North (ftUS), EPSG:2231, and describes every parcel in the block
with the toolkit. The data are not stored in the repository; this script fetches
them again.

Checks reported:
* closure of each description as written (bearings to the second, distances to
  0.01 ft);
* toolkit area against the county's own GIS_Acres attribute (a different
  computation, so small differences are expected);
* how many digitised vertices each parcel needed.
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from boundary_toolkit.geo import describe_parcels, write_outputs

SERVICE = "https://services.arcgis.com/ewjSqmSyHJnkfBLL/arcgis/rest/services/Parcels_open_data/FeatureServer/0/query"
BBOX = (-104.7000, 40.4100, -104.6960, 40.4130)      # a few residential blocks in Greeley (lon/lat)
FIELDS = "PARCEL,SUBNAME,BLOCK,LOT,GIS_Acres"
OUT = Path(__file__).resolve().parent / "output_weld"


def fetch() -> gpd.GeoDataFrame:
    q = {"where": "1=1", "geometry": ",".join(map(str, BBOX)), "geometryType": "esriGeometryEnvelope", "inSR": 4326,
         "spatialRel": "esriSpatialRelIntersects", "outFields": FIELDS, "outSR": 4326, "f": "geojson"}
    with urllib.request.urlopen(SERVICE + "?" + urllib.parse.urlencode(q), timeout=120) as r:
        raw = r.read()
    print(f"downloaded {len(raw) / 1024:.1f} KB from the Weld County open data service")
    return gpd.GeoDataFrame.from_features(json.loads(raw)["features"], crs="EPSG:4326")


def main() -> None:
    g = fetch().to_crs("EPSG:2231")
    g = g[g.geometry.notna() & g.PARCEL.notna()].reset_index(drop=True)
    g["label"] = "Parcel " + g.PARCEL.astype(str)
    env = gpd.GeoSeries([box(*BBOX)], crs="EPSG:4326").to_crs("EPSG:2231").iloc[0]
    target = g[~g.geometry.intersects(env.boundary)]                          # parcels whose neighbours were all downloaded
    if target.empty:
        raise SystemExit("no parcel lies fully inside the download box; enlarge BBOX")
    res = describe_parcels(g, "PARCEL", list(target.PARCEL), "label", tolerance=0.1)
    write_outputs(res, OUT, label_template="Parcel {id}, Weld County, Colorado")
    rows = []
    for r in res:
        b = r["boundary"]
        county = float(g.loc[g.PARCEL == r["id"], "GIS_Acres"].iloc[0] or 0)
        rows.append({"parcel": r["id"], "vertices": b.original_vertices, "points": len(b.points),
                     "acres_toolkit": round(b.area / 43560, 4), "acres_county": county,
                     "area_diff_pct": round(100 * (b.area / 43560 - county) / county, 3) if county else None,
                     "max_offset_ft": round(b.max_deviation(), 3), "misclosure_ft": round(b.closure_written.misclosure, 4),
                     "closure": b.closure_written.ratio_text()})
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "summary.csv", index=False)
    pd.set_option("display.width", 200)
    print(f"{len(g)} parcels downloaded, {len(t)} described (those not cut by the edge of the download box)")
    print(t.describe().loc[["min", "50%", "max"], ["vertices", "points", "area_diff_pct", "max_offset_ft", "misclosure_ft"]].round(4))
    print("worst written closure:", t.sort_values("misclosure_ft").iloc[-1][["parcel", "closure"]].to_dict())


if __name__ == "__main__":
    sys.exit(main())
