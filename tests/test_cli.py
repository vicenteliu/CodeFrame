"""Tests for the CLI seam: codeframe validate / generate."""

import json
from pathlib import Path

from codeframe.cli import main

DEMO_CONFIG = Path(__file__).parent.parent / "examples" / "demo_residential_project.json"


def test_validate_valid_config_prints_summary_and_exits_zero(capsys):
    exit_code = main(["validate", str(DEMO_CONFIG)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Demo Backyard Studio" in captured.out
    assert "OK" in captured.out


def test_validate_invalid_config_lists_errors_and_exits_nonzero(tmp_path, capsys):
    data = json.loads(DEMO_CONFIG.read_text(encoding="utf-8"))
    data["building"].pop("wall_height")
    config_path = tmp_path / "bad.json"
    config_path.write_text(json.dumps(data), encoding="utf-8")

    exit_code = main(["validate", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "building.wall_height" in captured.err


def test_validate_missing_file_reports_cleanly(tmp_path, capsys):
    missing = tmp_path / "nope.json"

    exit_code = main(["validate", str(missing)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "nope.json" in captured.err


EXPECTED_OUTPUTS = (
    "general_notes.dxf",
    "code_compliance.dxf",
    "site_plan.dxf",
    "floor_plan.dxf",
    "roof_plan.dxf",
    "elevation_front.dxf",
    "elevation_rear.dxf",
    "elevation_left.dxf",
    "elevation_right.dxf",
    "section_a.dxf",
    "schedules.dxf",
    "structural_notes.dxf",
    "foundation_plan.dxf",
    "roof_framing_plan.dxf",
    "details.dxf",
    "drawing_set.pdf",
)


def test_generate_writes_the_full_drawing_skeleton(tmp_path, capsys):
    out_dir = tmp_path / "plans"

    exit_code = main(["generate", str(DEMO_CONFIG), "--out", str(out_dir)])

    captured = capsys.readouterr()
    assert exit_code == 0
    for name in EXPECTED_OUTPUTS:
        assert (out_dir / name).exists()
        assert name in captured.out
    # The 3D massing model is written when FreeCAD is installed and
    # announced as skipped when it is not.
    from codeframe.massing import freecadcmd_available

    if freecadcmd_available():
        assert (out_dir / "model_3d.step").exists()
        assert "model_3d.step" in captured.out
    else:
        assert "Skipped model_3d.step" in captured.out


def test_schema_prints_the_project_config_json_schema(capsys):
    exit_code = main(["schema"])

    captured = capsys.readouterr()
    assert exit_code == 0
    schema = json.loads(captured.out)
    assert schema["title"] == "ProjectConfig"
    assert "schema_version" in schema["properties"]
    assert "openings" in schema["properties"]


def test_generate_reports_unsupported_roof_cleanly(tmp_path, capsys):
    data = json.loads(DEMO_CONFIG.read_text(encoding="utf-8"))
    data["building"]["roof"] = {"type": "flat", "slope": "0:12", "overhang": 1}
    data["sections"] = []
    config_path = tmp_path / "flat.json"
    config_path.write_text(json.dumps(data), encoding="utf-8")

    exit_code = main(["generate", str(config_path), "--out", str(tmp_path / "plans")])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "flat" in captured.err
    assert "not supported" in captured.err


def test_generate_defaults_to_config_output_target(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)

    exit_code = main(["generate", str(DEMO_CONFIG)])

    assert exit_code == 0
    target = tmp_path / "outputs" / "demo-backyard-studio"
    assert (target / "site_plan.dxf").exists()
    assert (target / "drawing_set.pdf").exists()


def test_generate_invalid_config_exits_nonzero(tmp_path, capsys):
    data = json.loads(DEMO_CONFIG.read_text(encoding="utf-8"))
    data["openings"][0]["offset"] = 18.5
    config_path = tmp_path / "bad.json"
    config_path.write_text(json.dumps(data), encoding="utf-8")

    exit_code = main(["generate", str(config_path), "--out", str(tmp_path / "plans")])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "openings[0]" in captured.err
    assert not (tmp_path / "plans").exists()
