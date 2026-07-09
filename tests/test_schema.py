"""Tests for the Project Config loading/validation seam."""

import json
from pathlib import Path

import pytest

from codeframe.schema import ProjectConfigError, load_project_config

DEMO_CONFIG = Path(__file__).parent.parent / "examples" / "demo_residential_project.json"


def error_from_mutated_demo(tmp_path, mutate):
    """Mutate a copy of the demo config, load it, return the error message."""

    data = json.loads(DEMO_CONFIG.read_text(encoding="utf-8"))
    mutate(data)
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProjectConfigError) as exc_info:
        load_project_config(config_path)
    return str(exc_info.value)


def test_valid_demo_config_loads():
    project = load_project_config(DEMO_CONFIG)

    assert project.name == "Demo Backyard Studio"
    assert project.units == "feet"
    assert project.site.lot.width == 50
    assert project.site.setbacks.front == 20
    assert project.site.existing_structures[0].label == "Existing Dwelling"
    assert project.building.position.x == 25
    assert project.building.footprint.depth == 24
    assert project.building.roof.type == "gable"
    assert project.building.roof.slope == "4:12"
    assert project.interior_walls[0].offset == 18
    assert project.openings[0].wall == "front"
    assert project.openings[1].sill == 3
    assert project.rooms[0].name == "Studio"


def test_missing_required_field_names_the_path(tmp_path):
    message = error_from_mutated_demo(
        tmp_path, lambda data: data["building"].pop("wall_height")
    )
    assert "building.wall_height" in message
    assert "required" in message.lower()


def test_unknown_field_is_rejected_with_its_path(tmp_path):
    message = error_from_mutated_demo(
        tmp_path, lambda data: data["site"]["lot"].update(widht=50)
    )
    assert "site.lot.widht" in message


def test_wrong_type_names_the_path(tmp_path):
    message = error_from_mutated_demo(
        tmp_path,
        lambda data: data["building"]["footprint"].update(width="twenty"),
    )
    assert "building.footprint.width" in message


def test_non_positive_dimension_is_rejected(tmp_path):
    message = error_from_mutated_demo(
        tmp_path, lambda data: data["site"]["lot"].update(width=-5)
    )
    assert "site.lot.width" in message
    assert "greater than 0" in message


def test_units_other_than_feet_are_rejected(tmp_path):
    message = error_from_mutated_demo(
        tmp_path, lambda data: data.update(units="meters")
    )
    assert "units" in message
    assert "feet" in message


def test_unsupported_schema_version_is_rejected(tmp_path):
    message = error_from_mutated_demo(
        tmp_path, lambda data: data.update(schema_version=2)
    )
    assert "schema_version" in message


def test_opening_wider_than_its_wall_is_rejected(tmp_path):
    message = error_from_mutated_demo(
        tmp_path, lambda data: data["openings"][0].update(offset=18.5)
    )
    assert "openings[0]" in message
    assert "front wall" in message


def test_window_requires_sill(tmp_path):
    message = error_from_mutated_demo(
        tmp_path, lambda data: data["openings"][1].pop("sill")
    )
    assert "openings[1]" in message
    assert "sill" in message


def test_opening_taller_than_wall_is_rejected(tmp_path):
    message = error_from_mutated_demo(
        tmp_path, lambda data: data["openings"][0].update(height=10)
    )
    assert "openings[0]" in message
    assert "wall height" in message


def test_building_must_fit_within_lot(tmp_path):
    message = error_from_mutated_demo(
        tmp_path, lambda data: data["building"]["position"].update(x=35)
    )
    assert "building" in message
    assert "lot" in message


def test_existing_structure_must_fit_within_lot(tmp_path):
    message = error_from_mutated_demo(
        tmp_path,
        lambda data: data["site"]["existing_structures"][0].update(width=45),
    )
    assert "site.existing_structures[0]" in message
    assert "lot" in message


def test_interior_wall_must_fit_within_footprint(tmp_path):
    message = error_from_mutated_demo(
        tmp_path, lambda data: data["interior_walls"][0].update(to=25)
    )
    assert "interior_walls[0]" in message
    assert "footprint" in message


def test_room_label_must_be_inside_footprint(tmp_path):
    message = error_from_mutated_demo(
        tmp_path,
        lambda data: data["rooms"][0]["label_at"].update(x=30),
    )
    assert "rooms[0]" in message
    assert "footprint" in message


def test_all_geometry_violations_are_reported_together(tmp_path):
    def mutate(data):
        data["openings"][0].update(offset=18.5)
        data["rooms"][0]["label_at"].update(x=30)

    message = error_from_mutated_demo(tmp_path, mutate)
    assert "openings[0]" in message
    assert "rooms[0]" in message


def test_door_swing_is_loaded():
    project = load_project_config(DEMO_CONFIG)
    assert project.openings[0].swing == "in-left"


def test_door_requires_swing(tmp_path):
    message = error_from_mutated_demo(
        tmp_path, lambda data: data["openings"][0].pop("swing")
    )
    assert "openings[0]" in message
    assert "swing" in message


def test_window_must_not_set_swing(tmp_path):
    message = error_from_mutated_demo(
        tmp_path, lambda data: data["openings"][1].update(swing="in-left")
    )
    assert "openings[1]" in message
    assert "swing" in message


def test_gable_roof_requires_ridge_axis(tmp_path):
    message = error_from_mutated_demo(
        tmp_path, lambda data: data["building"]["roof"].pop("ridge_axis")
    )
    assert "roof" in message
    assert "ridge_axis" in message


def test_shed_roof_requires_high_side(tmp_path):
    def mutate(data):
        data["building"]["roof"].pop("ridge_axis")
        data["building"]["roof"].update(type="shed")

    message = error_from_mutated_demo(tmp_path, mutate)
    assert "roof" in message
    assert "high_side" in message


def test_slope_must_be_rise_over_twelve(tmp_path):
    message = error_from_mutated_demo(
        tmp_path, lambda data: data["building"]["roof"].update(slope="steep")
    )
    assert "slope" in message
    assert "4:12" in message


def test_file_that_is_not_json_reports_json_error(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text("not json {{", encoding="utf-8")
    with pytest.raises(ProjectConfigError) as exc_info:
        load_project_config(config_path)
    assert "JSON" in str(exc_info.value)


def test_interior_door_is_loaded():
    project = load_project_config(DEMO_CONFIG)
    door = project.interior_walls[0].doors[0]
    assert (door.at, door.width, door.swing) == (3, 2.5, "in-left")


def test_interior_door_must_fit_its_wall(tmp_path):
    message = error_from_mutated_demo(
        tmp_path,
        lambda data: data["interior_walls"][0]["doors"][0].update(at=18.5),
    )
    assert "interior_walls[0].doors[0]" in message
    assert "18.5" in message


def test_interior_door_must_fit_under_wall_height(tmp_path):
    message = error_from_mutated_demo(
        tmp_path,
        lambda data: data["interior_walls"][0]["doors"][0].update(height=9.5),
    )
    assert "interior_walls[0].doors[0]" in message
    assert "wall height" in message
