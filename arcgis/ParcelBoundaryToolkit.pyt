# -*- coding: utf-8 -*-
"""ArcGIS Pro Python toolbox for the parcel boundary toolkit.

It reads parcels with ArcPy and calls the same pure-Python core as the command
line, so the numbered points, courses, closure and area checks are identical in
both. Requires ArcGIS Pro 3.x; no extra packages.
"""
import os
import sys

import arcpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from boundary_toolkit.adjoin import edge_adjoiners, insert_junctions  # noqa: E402
from boundary_toolkit.core import describe_ring, open_ring  # noqa: E402
from boundary_toolkit.describe import Units, course_rows, point_rows  # noqa: E402
from boundary_toolkit.report import write_tables  # noqa: E402


def _exterior_ring(geom):
    """Coordinates of the first ring of a single-part polygon (holes follow a None separator)."""
    if geom.partCount > 1:
        return None
    ring = []
    for p in geom.getPart(0):
        if p is None:
            break
        ring.append((p.X, p.Y))
    return ring


class Toolbox(object):
    def __init__(self):
        self.label = "Parcel Boundary Toolkit"
        self.alias = "parcelboundary"
        self.tools = [DescribeParcelBoundaries]


class DescribeParcelBoundaries(object):
    def __init__(self):
        self.label = "Describe Parcel Boundaries"
        self.description = ("Numbers the boundary points of each parcel clockwise from the northwest corner, keeps a point "
                            "wherever the adjoining parcel changes and only the bends needed to stay within the tolerance, and "
                            "writes the points, the courses, coordinate and course tables, a metes-and-bounds description and "
                            "its closure and area checks.")
        self.canRunInBackground = True

    def getParameterInfo(self):
        p_in = arcpy.Parameter(displayName="Parcels", name="in_features", datatype="GPFeatureLayer",
                               parameterType="Required", direction="Input")
        p_in.filter.list = ["Polygon"]
        p_id = arcpy.Parameter(displayName="Parcel ID field", name="id_field", datatype="Field",
                               parameterType="Required", direction="Input")
        p_id.parameterDependencies = [p_in.name]
        p_ids = arcpy.Parameter(displayName="Parcels to describe (empty: all)", name="parcel_ids", datatype="GPString",
                                parameterType="Optional", direction="Input", multiValue=True)
        p_adj = arcpy.Parameter(displayName="Adjoiner name field", name="adjoiner_field", datatype="Field",
                                parameterType="Optional", direction="Input")
        p_adj.parameterDependencies = [p_in.name]
        p_tol = arcpy.Parameter(displayName="Tolerance (map units)", name="tolerance", datatype="GPDouble",
                                parameterType="Required", direction="Input")
        p_tol.value = 0.1
        p_out = arcpy.Parameter(displayName="Output folder", name="out_folder", datatype="DEFolder",
                                parameterType="Required", direction="Input")
        p_area = arcpy.Parameter(displayName="Area format", name="area_style", datatype="GPString",
                                 parameterType="Optional", direction="Input")
        p_area.filter.type = "ValueList"; p_area.filter.list = ["auto", "ha-m2"]; p_area.value = "auto"
        p_pts = arcpy.Parameter(displayName="Boundary points", name="out_points", datatype="DEFeatureClass",
                                parameterType="Derived", direction="Output")
        p_crs = arcpy.Parameter(displayName="Boundary courses", name="out_courses", datatype="DEFeatureClass",
                                parameterType="Derived", direction="Output")
        return [p_in, p_id, p_ids, p_adj, p_tol, p_out, p_area, p_pts, p_crs]

    def execute(self, parameters, messages):
        fc, id_field = parameters[0].valueAsText, parameters[1].valueAsText
        ids = set(parameters[2].values or [])
        adj_field = parameters[3].valueAsText
        tol = float(parameters[4].value)
        out_folder, area_style = parameters[5].valueAsText, parameters[6].valueAsText or "auto"

        sr = arcpy.Describe(fc).spatialReference
        if sr.type != "Projected":
            raise arcpy.ExecuteError("Parcels must be in a projected coordinate system (meters or feet). Project them first.")
        units = Units.from_unit_name(sr.linearUnitName)

        fields = [id_field, "SHAPE@"] + ([adj_field] if adj_field else [])
        parcels = [(str(r[0]), r[1], str(r[2]) if adj_field else None) for r in arcpy.da.SearchCursor(fc, fields)]
        targets = [p for p in parcels if not ids or p[0] in {str(i) for i in ids}]
        if not targets:
            raise arcpy.ExecuteError("No parcel matches the requested IDs.")

        results = []
        for pid, geom, _ in targets:
            ring = _exterior_ring(geom)
            if ring is None:
                arcpy.AddWarning(f"Parcel {pid} has several parts and was skipped; describe each part separately.")
                continue
            ring = open_ring(ring)
            labels = None
            if adj_field:
                near = [(o_id, o_geom, lab) for o_id, o_geom, lab in parcels if o_id != pid and o_geom.distanceTo(geom) <= tol]
                rings = [open_ring(r) for r in (_exterior_ring(g) for _, g, _ in near) if r]
                ring = insert_junctions(ring, rings, tol)
                labels = edge_adjoiners(ring, rings, [lab for _, g, lab in near if _exterior_ring(g)], tol)
            b = describe_ring(ring, labels, tol)
            if geom.boundary().partCount > 1:
                b.notes.append("the parcel has interior rings that are not described")
            results.append({"id": pid, "boundary": b, "units": units, "crs_name": sr.name})
            arcpy.AddMessage(f"{pid}: {len(b.points)} points from {b.original_vertices} vertices, "
                             f"largest offset {b.max_deviation():.3f}, closure as written {b.closure_written.ratio_text()}")

        write_tables(results, __import__("pathlib").Path(out_folder), area_style=area_style)
        gdb = os.path.join(out_folder, "boundaries.gdb")
        if not arcpy.Exists(gdb):
            arcpy.management.CreateFileGDB(out_folder, "boundaries.gdb")
        pts_fc, crs_fc = os.path.join(gdb, "boundary_points"), os.path.join(gdb, "boundary_courses")
        for path, shape in ((pts_fc, "POINT"), (crs_fc, "POLYLINE")):
            if arcpy.Exists(path):
                arcpy.management.Delete(path)
            arcpy.management.CreateFeatureclass(gdb, os.path.basename(path), shape, spatial_reference=sr)
        for name, ftype in (("parcel", "TEXT"), ("point", "LONG"), ("x", "DOUBLE"), ("y", "DOUBLE")):
            arcpy.management.AddField(pts_fc, name, ftype)
        for name, ftype in (("parcel", "TEXT"), ("course", "LONG"), ("from_pt", "LONG"), ("to_pt", "LONG"), ("bearing", "TEXT"),
                            ("azimuth", "DOUBLE"), ("distance", "DOUBLE"), ("adjoiner", "TEXT"), ("max_offset", "DOUBLE")):
            arcpy.management.AddField(crs_fc, name, ftype)
        with arcpy.da.InsertCursor(pts_fc, ["parcel", "point", "x", "y", "SHAPE@XY"]) as cur:
            for r in results:
                for p in point_rows(r["boundary"]):
                    cur.insertRow([r["id"], p["point"], p["x"], p["y"], (p["x"], p["y"])])
        with arcpy.da.InsertCursor(crs_fc, ["parcel", "course", "from_pt", "to_pt", "bearing", "azimuth", "distance", "adjoiner", "max_offset", "SHAPE@"]) as cur:
            for r in results:
                b, u = r["boundary"], r["units"]
                xy = {p: (x, y) for p, x, y in b.points}
                for c in course_rows(b, u):
                    line = arcpy.Polyline(arcpy.Array([arcpy.Point(*xy[c["from"]]), arcpy.Point(*xy[c["to"]])]), sr)
                    cur.insertRow([r["id"], c["course"], c["from"], c["to"], c["bearing"], c["azimuth_deg"],
                                   c[f"distance_{u.name}"], c["adjoiner"], c[f"max_deviation_{u.name}"], line])
        parameters[7].value, parameters[8].value = pts_fc, crs_fc
