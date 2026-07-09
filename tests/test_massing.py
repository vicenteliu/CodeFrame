"""Tests for the 3D massing seam (solid specs + STEP export determinism)."""

import json
import os
from pathlib import Path

import pytest

from codeframe.dxf import UnsupportedRoofError
from codeframe.massing import (
    Box,
    Prism,
    freecadcmd_available,
    massing_solids,
    write_massing_model,
)
from codeframe.schema import load_project_config

DEMO_CONFIG = Path(__file__).parent.parent / "examples" / "demo_residential_project.json"
GOLDEN_DIR = Path(__file__).parent / "golden"

# Demo roof: gable 4:12 over a 20 ft span, 1 ft overhang, 9 ft walls.
RIDGE_Z = pytest.approx(12.333333, abs=1e-6)
EAVE_Z = pytest.approx(8.666667, abs=1e-6)

needs_freecad = pytest.mark.skipif(
    not freecadcmd_available(), reason="freecadcmd not found"
)


@pytest.fixture()
def demo_project():
    return load_project_config(DEMO_CONFIG)


def demo_variant(tmp_path, mutate):
    data = json.loads(DEMO_CONFIG.read_text(encoding="utf-8"))
    mutate(data)
    config_path = tmp_path / "variant.json"
    config_path.write_text(json.dumps(data), encoding="utf-8")
    return load_project_config(config_path)


def solid_named(solids, name):
    matches = [solid for solid in solids if solid.name == name]
    assert len(matches) == 1, f"expected one solid named {name!r}"
    return matches[0]


def test_wall_shell_cuts_void_and_openings(demo_project):
    walls = solid_named(massing_solids(demo_project), "walls")

    assert walls.base == Box((0.0, 0.0, 0.0), (20, 24, 9))
    void, door, window = walls.cuts
    assert void == Box((0.5, 0.5, 0.0), (19, 23, 9))
    # Front door at offset 8.5, 3 x 6.67 ft: pokes through the wall and grade.
    assert door.origin == (8.5, -0.1, -0.1)
    assert door.size == (3, pytest.approx(0.7), pytest.approx(6.77))
    # Left window at offset 6, 4 x 3 ft on a 3 ft sill.
    assert window.origin == (-0.1, 6, 3)
    assert window.size == (pytest.approx(0.7), 4, 3)


def test_openings_map_to_rear_and_right_walls(tmp_path):
    def mutate(data):
        data["openings"] = [
            {"type": "door", "wall": "rear", "offset": 2, "width": 3,
             "height": 6.67, "swing": "in-left"},
            {"type": "window", "wall": "right", "offset": 6, "width": 4,
             "height": 3, "sill": 3},
        ]

    solids = massing_solids(demo_variant(tmp_path, mutate))
    door, window = solid_named(solids, "walls").cuts[1:]

    # Rear wall offsets run from the left end; the cut straddles y=24.
    assert door.origin == (2, pytest.approx(23.4), -0.1)
    assert door.size == (3, pytest.approx(0.7), pytest.approx(6.77))
    # Right wall offsets run from the front end; the cut straddles x=20.
    assert window.origin == (pytest.approx(19.4), 6, 3)
    assert window.size == (pytest.approx(0.7), 4, 3)


def test_interior_wall_clipped_to_inner_faces(demo_project):
    interior = solid_named(massing_solids(demo_project), "interior_wall_1")
    assert interior.base == Box((0.5, 17.8125, 0.0), (19, 0.375, 9))
    assert interior.cuts == ()


def test_roof_prism_ridge_along_y(demo_project):
    roof = solid_named(massing_solids(demo_project), "roof")

    assert isinstance(roof.base, Prism)
    (left, right, apex) = roof.base.profile
    assert left == (-1, -1, EAVE_Z)
    assert right == (21, -1, EAVE_Z)
    assert apex == (10, -1, RIDGE_Z)
    assert roof.base.direction == (0.0, 26, 0.0)


def test_roof_prism_ridge_along_x(tmp_path):
    def mutate(data):
        data["building"]["roof"]["ridge_axis"] = "x"

    roof = solid_named(massing_solids(demo_variant(tmp_path, mutate)), "roof")

    assert isinstance(roof.base, Prism)
    # Span is now the 24 ft depth: ridge at 9 + 12 * 4/12 = 13 ft.
    (front, rear, apex) = roof.base.profile
    assert front == (-1, -1, EAVE_Z)
    assert rear == (-1, 25, EAVE_Z)
    assert apex == (-1, 12, 13)
    assert roof.base.direction == (22, 0.0, 0.0)


def test_unsupported_roof_type_raises_clear_error(tmp_path):
    def mutate(data):
        data["building"]["roof"] = {"type": "flat", "slope": "0:12", "overhang": 1}

    project = demo_variant(tmp_path, mutate)
    with pytest.raises(UnsupportedRoofError) as exc_info:
        massing_solids(project)
    assert "flat" in str(exc_info.value)
    assert "not supported" in str(exc_info.value)


@needs_freecad
def test_step_export_contains_three_solids(demo_project, tmp_path):
    out_path = tmp_path / "model_3d.step"
    write_massing_model(demo_project, out_path)
    assert out_path.read_text(encoding="utf-8").count("MANIFOLD_SOLID_BREP") == 3


@needs_freecad
def test_step_export_is_deterministic(demo_project, tmp_path):
    first = tmp_path / "first.step"
    second = tmp_path / "second.step"
    write_massing_model(demo_project, first)
    write_massing_model(demo_project, second)
    assert first.read_bytes() == second.read_bytes()


@needs_freecad
def test_step_export_matches_golden(demo_project, tmp_path):
    produced = tmp_path / "model_3d.step"
    write_massing_model(demo_project, produced)

    golden = GOLDEN_DIR / "model_3d.step"
    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN_DIR.mkdir(exist_ok=True)
        golden.write_bytes(produced.read_bytes())

    assert golden.exists(), "golden file missing; bless with UPDATE_GOLDEN=1 pytest"
    assert produced.read_bytes() == golden.read_bytes(), (
        "model_3d.step no longer matches its golden. Review the change (open "
        "both in a viewer, diff) and bless intentional updates with "
        "UPDATE_GOLDEN=1 pytest. FreeCAD version changes can also shift STEP "
        "output; re-bless after confirming geometry is unchanged."
    )
