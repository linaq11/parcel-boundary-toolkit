"""Synthetic example: a small block of parcels in UTM zone 18N, with a curved road
frontage (many vertices), a T-junction between neighbours and named owners.
Writes examples/data/example_parcels.gpkg and a shapefile copy for ArcGIS Pro."""
import math
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Polygon

HERE = Path(__file__).resolve().parent
x0, y0 = 500000.0, 1200000.0

# parcel A: west side straight, north side follows a gentle curve (road frontage), east side shared with B and C
curve = [(x0 + 120 * t, y0 + 100 + 6 * math.sin(math.pi * t)) for t in [i / 24 for i in range(25)]]
a = Polygon([(x0, y0)] + curve + [(x0 + 120, y0)])
b = Polygon([(x0 + 120, y0), (x0 + 120, y0 + 45), (x0 + 210, y0 + 45), (x0 + 210, y0)])
c = Polygon([(x0 + 120, y0 + 45), (x0 + 120, y0 + 100), (x0 + 210, y0 + 104), (x0 + 210, y0 + 45)])
d = Polygon([(x0, y0 - 80), (x0, y0), (x0 + 120, y0), (x0 + 210, y0), (x0 + 210, y0 - 80)])
road = Polygon(curve + [(x0 + 210, y0 + 104), (x0 + 210, y0 + 120), (x0, y0 + 120)])

g = gpd.GeoDataFrame({"parcel_id": ["A-101", "B-102", "C-103", "D-104", "ROAD-1"],
                      "owner": ["Lot A-101", "Lot B-102", "Lot C-103", "Lot D-104", "Riverside Road"]},
                     geometry=[a, b, c, d, road], crs="EPSG:32618")
out = HERE / "data"; out.mkdir(exist_ok=True)
g.to_file(out / "example_parcels.gpkg", layer="parcels", driver="GPKG")
g.to_file(out / "example_parcels.shp")
print(g.assign(vertices=g.geometry.apply(lambda p: len(p.exterior.coords) - 1)).drop(columns="geometry"))
