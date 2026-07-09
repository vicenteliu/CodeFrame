"""Tests for the DXF writer seam (semantic read-back + determinism)."""

import os
from pathlib import Path

import ezdxf
import pytest

from codeframe.dxf import (
    UnsupportedRoofError,
    format_feet_inches,
    write_elevation,
    write_floor_plan,
    write_roof_plan,
    write_schedules,
    write_site_plan,
)
from codeframe.schema import load_project_config

DEMO_CONFIG = Path(__file__).parent.parent / "examples" / "demo_residential_project.json"
GOLDEN_DIR = Path(__file__).parent / "golden"

PLAN_WRITERS = [
    ("site_plan", write_site_plan),
    ("floor_plan", write_floor_plan),
    ("roof_plan", write_roof_plan),
    ("elevation_front", lambda project, path: write_elevation(project, "front", path)),
    ("elevation_rear", lambda project, path: write_elevation(project, "rear", path)),
    ("elevation_left", lambda project, path: write_elevation(project, "left", path)),
    ("elevation_right", lambda project, path: write_elevation(project, "right", path)),
    ("schedules", write_schedules),
]

# Demo roof: gable 4:12 over a 20 ft span, 1 ft overhang, 9 ft walls.
RIDGE_Z = 12.333333
EAVE_Z = 8.666667


@pytest.fixture()
def demo_project():
    return load_project_config(DEMO_CONFIG)


def rectangle_corners(polyline):
    return {(round(p[0], 6), round(p[1], 6)) for p in polyline.get_points()}


def test_site_plan_draws_lot_setbacks_and_buildings(demo_project, tmp_path):
    out_path = tmp_path / "site_plan.dxf"
    write_site_plan(demo_project, out_path)

    msp = ezdxf.readfile(out_path).modelspace()

    lot = msp.query("LWPOLYLINE[layer=='C-PROP']")
    assert len(lot) == 1
    assert rectangle_corners(lot[0]) == {(0, 0), (50, 0), (50, 120), (0, 120)}

    setbacks = msp.query("LWPOLYLINE[layer=='C-PROP-SBCK']")
    assert len(setbacks) == 1
    assert rectangle_corners(setbacks[0]) == {(5, 20), (45, 20), (45, 110), (5, 110)}

    existing = msp.query("LWPOLYLINE[layer=='C-BLDG-EXST']")
    assert len(existing) == 1
    assert rectangle_corners(existing[0]) == {(10, 25), (40, 25), (40, 65), (10, 65)}

    proposed = msp.query("LWPOLYLINE[layer=='C-BLDG-PROP']")
    assert len(proposed) == 1
    assert rectangle_corners(proposed[0]) == {(25, 86), (45, 86), (45, 110), (25, 110)}

    labels = {text.dxf.text for text in msp.query("TEXT")}
    assert "Existing Dwelling" in labels

    setback_dims = msp.query("DIMENSION")
    assert len(setback_dims) == 4


def test_site_plan_is_deterministic(demo_project, tmp_path):
    first = tmp_path / "first.dxf"
    second = tmp_path / "second.dxf"
    write_site_plan(demo_project, first)
    write_site_plan(demo_project, second)
    assert first.read_bytes() == second.read_bytes()


def line_segments(msp, layer):
    result = set()
    for line in msp.query(f"LINE[layer=='{layer}']"):
        start = (round(line.dxf.start.x, 6), round(line.dxf.start.y, 6))
        end = (round(line.dxf.end.x, 6), round(line.dxf.end.y, 6))
        result.add(tuple(sorted((start, end))))
    return result


def segment(x1, y1, x2, y2):
    return tuple(sorted(((x1, y1), (x2, y2))))


def test_floor_plan_walls_break_at_openings(demo_project, tmp_path):
    out_path = tmp_path / "floor_plan.dxf"
    write_floor_plan(demo_project, out_path)

    msp = ezdxf.readfile(out_path).modelspace()
    walls = line_segments(msp, "A-WALL")

    # Front wall (outer + inner face) breaks at the 8.5..11.5 door.
    assert segment(0, 0, 8.5, 0) in walls
    assert segment(11.5, 0, 20, 0) in walls
    assert segment(0.5, 0.5, 8.5, 0.5) in walls
    assert segment(11.5, 0.5, 19.5, 0.5) in walls
    # Door jambs close the wall across its thickness.
    assert segment(8.5, 0, 8.5, 0.5) in walls
    assert segment(11.5, 0, 11.5, 0.5) in walls
    # Left wall breaks at the 6..10 window.
    assert segment(0, 0, 0, 6) in walls
    assert segment(0, 10, 0, 24) in walls
    # Rear wall has no openings: unbroken faces.
    assert segment(0, 24, 20, 24) in walls
    assert segment(0.5, 23.5, 19.5, 23.5) in walls


def test_floor_plan_door_swing_window_and_interior_wall(demo_project, tmp_path):
    out_path = tmp_path / "floor_plan.dxf"
    write_floor_plan(demo_project, out_path)

    msp = ezdxf.readfile(out_path).modelspace()

    # In-left exterior door: leaf hinged at (8.5, 0.5) plus a swing arc; the
    # interior door adds a second leaf and arc.
    door_lines = line_segments(msp, "A-DOOR")
    assert segment(8.5, 0.5, 8.5, 3.5) in door_lines
    arcs = msp.query("ARC[layer=='A-DOOR']")
    assert len(arcs) == 2
    centers = {
        (round(arc.dxf.center.x, 6), round(arc.dxf.center.y, 6)) for arc in arcs
    }
    assert (8.5, 0.5) in centers

    # Window glazing line runs along the wall centerline.
    assert segment(0.25, 6, 0.25, 10) in line_segments(msp, "A-GLAZ")

    # Interior wall: double line clipped to the exterior inner faces and
    # broken at the 3..5.5 door, with jambs across the thickness.
    interior = line_segments(msp, "A-WALL-INTR")
    for face in (17.8125, 18.1875):
        assert segment(0.5, face, 3, face) in interior
        assert segment(5.5, face, 19.5, face) in interior
    assert segment(3, 17.8125, 3, 18.1875) in interior
    assert segment(5.5, 17.8125, 5.5, 18.1875) in interior
    # In-left interior door: leaf hinged at (3, 18.1875) opening toward +y.
    assert segment(3, 18.1875, 3, 20.6875) in door_lines

    labels = {text.dxf.text for text in msp.query("TEXT")}
    assert {"Studio", "Storage"} <= labels

    # 2 overall + front chain (3) + left chain (3) + interior wall locate (1).
    assert len(msp.query("DIMENSION")) == 9


def test_floor_plan_is_deterministic(demo_project, tmp_path):
    first = tmp_path / "first.dxf"
    second = tmp_path / "second.dxf"
    write_floor_plan(demo_project, first)
    write_floor_plan(demo_project, second)
    assert first.read_bytes() == second.read_bytes()


def test_front_elevation_shows_gable_end(demo_project, tmp_path):
    out_path = tmp_path / "elevation_front.dxf"
    write_elevation(demo_project, "front", out_path)

    msp = ezdxf.readfile(out_path).modelspace()

    # Gable-end wall face: pentagon up to the ridge.
    walls = msp.query("LWPOLYLINE[layer=='A-ELEV']")
    assert len(walls) == 1
    assert rectangle_corners(walls[0]) == {
        (0, 0), (20, 0), (20, 9), (10, RIDGE_Z), (0, 9),
    }

    # Rake lines from each eave tip (1 ft overhang) to the ridge.
    roof = line_segments(msp, "A-ROOF")
    assert segment(-1, EAVE_Z, 10, RIDGE_Z) in roof
    assert segment(10, RIDGE_Z, 21, EAVE_Z) in roof

    # Door as a rectangle standing on grade.
    doors = msp.query("LWPOLYLINE[layer=='A-DOOR']")
    assert len(doors) == 1
    assert rectangle_corners(doors[0]) == {
        (8.5, 0), (11.5, 0), (11.5, 6.67), (8.5, 6.67),
    }

    labels = {text.dxf.text for text in msp.query("TEXT")}
    assert "FRONT ELEVATION" in labels
    # Plate height and ridge height.
    assert len(msp.query("DIMENSION")) == 2


def test_left_elevation_is_mirrored_and_shows_eave_side(demo_project, tmp_path):
    out_path = tmp_path / "elevation_left.dxf"
    write_elevation(demo_project, "left", out_path)

    msp = ezdxf.readfile(out_path).modelspace()

    # Eave-side wall face: plain rectangle, 24 ft of depth.
    walls = msp.query("LWPOLYLINE[layer=='A-ELEV']")
    assert len(walls) == 1
    assert rectangle_corners(walls[0]) == {(0, 0), (24, 0), (24, 9), (0, 9)}

    # Seen from outside the left wall, the window at s=6..10 lands at h=14..18.
    windows = msp.query("LWPOLYLINE[layer=='A-GLAZ']")
    assert len(windows) == 1
    assert rectangle_corners(windows[0]) == {(14, 3), (18, 3), (18, 6), (14, 6)}

    # Eave and ridge run the full depth plus rake overhangs.
    roof = line_segments(msp, "A-ROOF")
    assert segment(-1, EAVE_Z, 25, EAVE_Z) in roof
    assert segment(-1, RIDGE_Z, 25, RIDGE_Z) in roof
    assert segment(-1, EAVE_Z, -1, RIDGE_Z) in roof
    assert segment(25, EAVE_Z, 25, RIDGE_Z) in roof


def test_roof_plan_shows_outline_ridge_and_slope(demo_project, tmp_path):
    out_path = tmp_path / "roof_plan.dxf"
    write_roof_plan(demo_project, out_path)

    msp = ezdxf.readfile(out_path).modelspace()

    outline = msp.query("LWPOLYLINE[layer=='A-ROOF']")
    assert len(outline) == 1
    assert rectangle_corners(outline[0]) == {(-1, -1), (21, -1), (21, 25), (-1, 25)}

    below = msp.query("LWPOLYLINE[layer=='A-WALL-BLW']")
    assert len(below) == 1
    assert rectangle_corners(below[0]) == {(0, 0), (20, 0), (20, 24), (0, 24)}

    # Ridge runs along y at mid-width, across both rake overhangs.
    assert segment(10, -1, 10, 25) in line_segments(msp, "A-ROOF")

    labels = [text.dxf.text for text in msp.query("TEXT")]
    assert labels.count("4:12") == 2
    assert "ROOF PLAN" in labels


def test_format_feet_inches():
    assert format_feet_inches(6.67) == "6'-8\""
    assert format_feet_inches(2.5) == "2'-6\""
    assert format_feet_inches(3) == "3'-0\""
    assert format_feet_inches(0.99) == "1'-0\""


def test_schedules_group_openings_with_marks(demo_project, tmp_path):
    out_path = tmp_path / "schedules.dxf"
    write_schedules(demo_project, out_path)

    msp = ezdxf.readfile(out_path).modelspace()
    labels = [text.dxf.text for text in msp.query("TEXT")]

    assert "DOOR SCHEDULE" in labels
    assert "WINDOW SCHEDULE" in labels
    # D1 = exterior 3'-0" x 6'-8" entry door; D2 = interior 2'-6" door.
    d1 = labels.index("D1")
    assert labels[d1:d1 + 5] == ["D1", "3'-0\"", "6'-8\"", "EXTERIOR", "1"]
    d2 = labels.index("D2")
    assert labels[d2:d2 + 5] == ["D2", "2'-6\"", "6'-8\"", "INTERIOR", "1"]
    # W1 = the 4'-0" x 3'-0" window on a 3'-0" sill.
    w1 = labels.index("W1")
    assert labels[w1:w1 + 5] == ["W1", "4'-0\"", "3'-0\"", "SILL 3'-0\"", "1"]


def test_floor_plan_tags_openings_with_schedule_marks(demo_project, tmp_path):
    out_path = tmp_path / "floor_plan.dxf"
    write_floor_plan(demo_project, out_path)

    msp = ezdxf.readfile(out_path).modelspace()
    labels = {text.dxf.text for text in msp.query("TEXT")}
    assert {"D1", "D2", "W1"} <= labels
    # One tag circle per opening: front door, interior door, window.
    assert len(msp.query("CIRCLE[layer=='A-ANNO-TEXT']")) == 3


def test_unsupported_roof_type_raises_clear_error(tmp_path):
    import json

    data = json.loads(DEMO_CONFIG.read_text(encoding="utf-8"))
    data["building"]["roof"] = {"type": "flat", "slope": "0:12", "overhang": 1}
    config_path = tmp_path / "flat.json"
    config_path.write_text(json.dumps(data), encoding="utf-8")
    project = load_project_config(config_path)

    with pytest.raises(UnsupportedRoofError) as exc_info:
        write_elevation(project, "front", tmp_path / "out.dxf")
    assert "flat" in str(exc_info.value)
    assert "not supported" in str(exc_info.value)


@pytest.mark.parametrize("name,writer", PLAN_WRITERS)
def test_output_matches_golden(demo_project, tmp_path, name, writer):
    produced = tmp_path / f"{name}.dxf"
    writer(demo_project, produced)

    golden = GOLDEN_DIR / f"{name}.dxf"
    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN_DIR.mkdir(exist_ok=True)
        golden.write_bytes(produced.read_bytes())

    assert golden.exists(), "golden file missing; bless with UPDATE_GOLDEN=1 pytest"
    assert produced.read_bytes() == golden.read_bytes(), (
        f"{name}.dxf no longer matches its golden. Review the change (render "
        "both, diff) and bless intentional updates with UPDATE_GOLDEN=1 pytest"
    )


@pytest.mark.parametrize("name,writer", PLAN_WRITERS)
def test_output_passes_dxf_audit(demo_project, tmp_path, name, writer):
    out_path = tmp_path / f"{name}.dxf"
    writer(demo_project, out_path)
    auditor = ezdxf.readfile(out_path).audit()
    assert not auditor.has_errors
