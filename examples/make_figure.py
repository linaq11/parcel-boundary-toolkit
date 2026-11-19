"""Figure for the README: parcel A-101 before (all vertices) and after (numbered points and courses)."""
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt

from boundary_toolkit.bearings import quadrant_bearing
from boundary_toolkit.geo import describe_parcels

HERE = Path(__file__).resolve().parent
g = gpd.read_file(HERE / "data" / "example_parcels.gpkg", layer="parcels")
r = describe_parcels(g, "parcel_id", ["A-101"], "owner", tolerance=0.25)[0]["boundary"]
a = g[g.parcel_id == "A-101"].geometry.iloc[0]
x0, y0 = 500000.0, 1200000.0

fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), sharex=True, sharey=True)
for ax in axes:
    g.boundary.plot(ax=ax, color="#9aa5b1", lw=0.8)
    for _, row in g.iterrows():
        c = row.geometry.representative_point()
        if row.parcel_id != "A-101":
            ax.annotate(row.owner, (c.x, c.y), ha="center", va="center", fontsize=8, color="#5f6b7a")
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)

xs, ys = a.exterior.xy
axes[0].fill(xs, ys, color="#d8e8d4", lw=0)
axes[0].plot(xs, ys, color="#2f6b3a", lw=1)
axes[0].scatter(xs[:-1], ys[:-1], s=10, color="#2f6b3a", zorder=3)
axes[0].text(0.02, 0.02, f"{len(xs) - 1} original vertices", transform=axes[0].transAxes, fontsize=10)

px = [p[1] for p in r.points] + [r.points[0][1]]
py = [p[2] for p in r.points] + [r.points[0][2]]
axes[1].fill(xs, ys, color="#d8e8d4", lw=0)
axes[1].plot(px, py, color="#b5651d", lw=1.6)
for n, x, y in r.points:
    axes[1].scatter([x], [y], s=26, color="#b5651d", zorder=4)
    axes[1].annotate(str(n), (x, y), xytext=(4, 4), textcoords="offset points", fontsize=8, color="#7a3e0c")
for c in r.courses[8:]:                                        # label the four long courses
    (_, xa, ya), (_, xb, yb) = r.points[c.from_point - 1], r.points[c.to_point - 1]
    axes[1].annotate(f"{quadrant_bearing(c.azimuth).format()}\n{c.distance:.2f} m", ((xa + xb) / 2, (ya + yb) / 2),
                     ha="center", va="center", fontsize=7, color="#333333",
                     bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85))
axes[1].text(0.02, 0.02, f"{len(r.points)} numbered points, closure {r.closure_written.ratio_text()}", transform=axes[1].transAxes, fontsize=10)
axes[0].set_xlim(x0 - 15, x0 + 225); axes[0].set_ylim(y0 - 90, y0 + 125)
plt.tight_layout()
out = HERE.parent / "docs"; out.mkdir(exist_ok=True)
fig.savefig(out / "example.png", dpi=150, bbox_inches="tight")
print("saved", out / "example.png")
