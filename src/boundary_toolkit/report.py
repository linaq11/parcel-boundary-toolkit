"""Tables and description files, in pure Python (shared by GeoPandas and ArcPy front ends)."""
from __future__ import annotations

import csv
from pathlib import Path

from .describe import course_rows, legal_description, point_rows, quality_report


def write_tables(results: list[dict], out: Path, seconds_decimals: int = 0, distance_decimals: int = 2,
                 area_style: str = "auto", label_template: str = "Parcel {id}") -> None:
    """Coordinate and course tables (CSV) and the description with its checks (Markdown)."""
    out.mkdir(parents=True, exist_ok=True)
    for r in results:
        b, u = r["boundary"], r["units"]
        pid = str(r["id"]).replace("/", "_")
        for name, rows in (("points", point_rows(b)), ("courses", course_rows(b, u, seconds_decimals, distance_decimals))):
            with open(out / f"{pid}_{name}.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
        text = legal_description(b, u, label_template.format(id=r["id"]), r["crs_name"], seconds_decimals, distance_decimals, area_style)
        qa = "\n".join(f"| {k} | {v} |" for k, v in quality_report(b, u, area_style))
        (out / f"{pid}_description.md").write_text(f"{text}\n\n## Quality checks\n\n| Check | Value |\n|---|---|\n{qa}\n", encoding="utf-8")
