import math

import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from boundary_toolkit import Units, describe_ring, format_area, quadrant_bearing
from boundary_toolkit.bearings import closure
from boundary_toolkit.geo import describe_parcels

M = Units("meters", "meter")


@pytest.mark.parametrize("az, text", [
    (45, "N 45°00'00\" E"), (135, "S 45°00'00\" E"), (225, "S 45°00'00\" W"), (315, "N 45°00'00\" W"),
    (0, "Due North"), (90, "Due East"), (180, "Due South"), (270, "Due West"),
    (30 - 1e-7, "N 30°00'00\" E"),                  # 59.9996" must carry into the next degree
    (12.5, "N 12°30'00\" E"), (359.9999999, "Due North"),
])
def test_quadrant_bearings(az, text):
    assert quadrant_bearing(az).format() == text


def test_bearing_roundtrip():
    for az in (1.2345, 89.9, 90.1, 179.99, 181, 269.5, 300.25):
        assert math.isclose(quadrant_bearing(az).to_azimuth(), az, abs_tol=1e-9)


def test_square_is_clockwise_from_northwest():
    ccw = [(0, 0), (100, 0), (100, 100), (0, 100)]
    b = describe_ring(ccw)
    assert [(x, y) for _, x, y in b.points] == [(0, 100), (100, 100), (100, 0), (0, 0)]
    assert [quadrant_bearing(c.azimuth).format() for c in b.courses] == ["Due East", "Due South", "Due West", "Due North"]
    assert [round(c.distance, 6) for c in b.courses] == [100] * 4
    assert b.area == 10000 and math.isinf(b.closure_written.precision)


def test_collinear_vertex_is_dropped_but_a_real_bend_is_kept():
    straight = [(0, 0), (0, 100), (50, 100), (100, 100), (100, 0)]
    assert len(describe_ring(straight).points) == 4
    bent = [(0, 0), (0, 100), (50, 100.05), (100, 100), (100, 0)]
    assert len(describe_ring(bent, tolerance=0.1).points) == 4      # 5 cm offset, inside a 10 cm tolerance
    b = describe_ring(bent, tolerance=0.01)
    assert len(b.points) == 5 and b.max_deviation() == 0             # 1 cm tolerance keeps the bend


def test_change_of_adjoiner_keeps_a_collinear_vertex():
    ring = [(0, 0), (0, 100), (50, 100), (100, 100), (100, 0)]      # clockwise already
    labels = ["West", "North A", "North B", "East", "South"]
    b = describe_ring(ring, labels)
    assert len(b.points) == 5
    assert [c.adjoiner for c in b.courses] == ["North A", "North B", "East", "South", "West"]


def test_labels_follow_edges_when_the_ring_is_reversed():
    ccw = [(0, 0), (100, 0), (100, 100), (0, 100)]
    labels = ["South", "East", "North", "West"]                     # edge i goes from vertex i to i + 1
    b = describe_ring(ccw, labels)
    assert [c.adjoiner for c in b.courses] == ["North", "East", "South", "West"]


def test_written_closure_is_finite_and_tight_for_an_irregular_parcel():
    ring = [(0, 0), (12.3456, 87.6543), (93.21, 101.11), (140.5, 33.3), (70.123, -20.456)]
    b = describe_ring(ring)
    assert 0 < b.closure_written.misclosure < 0.05
    assert b.closure_written.precision > 10000


def test_closure_detects_a_bad_course():
    good = [(90, 100), (180, 100), (270, 100), (0, 100)]
    assert math.isinf(closure(good).precision)
    assert math.isclose(closure([(90, 100), (180, 100), (270, 101), (0, 100)]).misclosure, 1.0)


@pytest.mark.parametrize("m2, text", [(1402003, "140 ha + 2003 m²"), (30037, "3 ha + 0037 m²"), (9999.6, "1 ha + 0000 m²")])
def test_area_ha_m2(m2, text):
    assert format_area(m2, M, "ha-m2") == text


def test_feet_area_in_acres():
    assert format_area(43560, Units("feet", "foot")).startswith("1.000 acres")


def test_t_junction_with_neighbours_creates_a_point():
    a = Polygon([(0, 0), (0, 100), (100, 100), (100, 0)])
    b = Polygon([(100, 0), (100, 50), (200, 50), (200, 0)])         # its corner falls in the middle of A's east edge
    c = Polygon([(100, 50), (100, 100), (200, 100), (200, 50)])
    g = gpd.GeoDataFrame({"pid": ["A", "B", "C"], "owner": ["Ana", "Beto", "Carla"]}, geometry=[a, b, c], crs="EPSG:32618")
    r = describe_parcels(g, "pid", ["A"], "owner")[0]["boundary"]
    assert len(r.points) == 5
    assert [c.adjoiner for c in r.courses] == ["unknown", "Carla", "Beto", "unknown", "unknown"]


def test_geographic_crs_is_rejected():
    g = gpd.GeoDataFrame({"pid": ["A"]}, geometry=[Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])], crs="EPSG:4326")
    with pytest.raises(ValueError, match="projected"):
        describe_parcels(g, "pid")
