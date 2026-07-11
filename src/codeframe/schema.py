"""Project Config schema: explicit-geometry input for the Deterministic Core.

Coordinate conventions:
- Lot coordinates: origin at the lot's front-left corner (front = street
  side); x runs right across the lot width, y runs toward the rear.
- Building-local coordinates: origin at the footprint's front-left corner.
- Exterior walls are named front/rear/left/right and map one-to-one onto the
  four elevations. Opening offsets are measured from the left end on
  front/rear walls and from the front end on left/right walls.
- All dimensions are decimal feet.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

PositiveFeet = Annotated[float, Field(gt=0)]
NonNegativeFeet = Annotated[float, Field(ge=0)]


class ProjectConfigError(ValueError):
    """A Project Config failed to load; `errors` lists actionable messages."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        details = "\n".join(f"  - {error}" for error in errors)
        super().__init__(f"Invalid project config:\n{details}")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Lot(_Model):
    width: PositiveFeet
    depth: PositiveFeet


class Setbacks(_Model):
    front: NonNegativeFeet
    rear: NonNegativeFeet
    left: NonNegativeFeet
    right: NonNegativeFeet


class ExistingStructure(_Model):
    label: str
    x: NonNegativeFeet
    y: NonNegativeFeet
    width: PositiveFeet
    depth: PositiveFeet


class Site(_Model):
    lot: Lot
    setbacks: Setbacks
    existing_structures: list[ExistingStructure] = []
    # Degrees counterclockwise from plan-up (+y). Stated by the Drafter;
    # without it the site plan draws no north arrow.
    north_rotation: float | None = None


class Point(_Model):
    x: NonNegativeFeet
    y: NonNegativeFeet


class Footprint(_Model):
    width: PositiveFeet
    depth: PositiveFeet


class RoofFraming(_Model):
    """Roof framing parameters for sheet S2. All member sizes are stated
    by the Drafter — CodeFrame lays out and labels, never sizes."""

    member: Literal["rafter", "truss"]
    size: str
    spacing: PositiveFeet
    species_grade: str | None = None
    ridge: str | None = None


class Roof(_Model):
    type: Literal["gable", "shed", "flat"]
    slope: str
    ridge_axis: Literal["x", "y"] | None = None
    high_side: Literal["front", "rear", "left", "right"] | None = None
    overhang: NonNegativeFeet = 0
    framing: RoofFraming | None = None

    @field_validator("slope")
    @classmethod
    def _slope_is_rise_over_twelve(cls, value: str) -> str:
        if not re.fullmatch(r"\d+(\.\d+)?:12", value):
            raise ValueError("slope must be written as rise:12, like '4:12'")
        return value

    @model_validator(mode="after")
    def _directional_fields_match_type(self) -> "Roof":
        if self.type == "gable" and self.ridge_axis is None:
            raise ValueError("gable roof requires a ridge_axis ('x' or 'y')")
        if self.type == "shed" and self.high_side is None:
            raise ValueError(
                "shed roof requires a high_side (front, rear, left, or right)"
            )
        if self.framing is not None and self.ridge_axis is None:
            raise ValueError(
                "roof framing requires a gable roof with a ridge_axis"
            )
        return self


class HoldDown(_Model):
    """A hold-down anchor at an explicit point, keyed by its stated label."""

    at: Point
    label: str


class Foundation(_Model):
    """Slab-on-grade foundation parameters.

    `footing_width` (feet) is drawn — the continuous footing is centered
    under the exterior walls. Depth, slab thickness, and vapor retarder
    feed the notes block; the vapor retarder is a jurisdiction parameter
    (2022 CRC R506.2.3 says 10-mil, LADBS still writes 6, Redding 15).
    Hold-down sizes/models are the drafter's; CodeFrame only places and
    labels them.
    """

    type: Literal["slab-on-grade"]
    footing_width: PositiveFeet
    footing_depth: PositiveFeet
    slab_thickness_inches: float = 3.5
    vapor_retarder_mil: int = 10
    hold_downs: list[HoldDown] = []


class Building(_Model):
    position: Point
    footprint: Footprint
    wall_height: PositiveFeet
    exterior_wall_thickness: PositiveFeet
    roof: Roof
    foundation: Foundation | None = None


class InteriorDoor(_Model):
    """A door in an interior wall.

    `at` is the near jamb's position along the wall's axis, in the same
    building-local coordinate as the wall's `from`/`to`. Swing reuses the
    exterior vocabulary: `left`/`right` hinge at the lower/higher-coordinate
    jamb; `in` opens toward the positive side of the cross axis (+y for an
    axis-x wall, +x for an axis-y wall), `out` toward the negative side.
    """

    at: NonNegativeFeet
    width: PositiveFeet
    height: PositiveFeet
    swing: Literal["in-left", "in-right", "out-left", "out-right"]


class InteriorWall(_Model):
    axis: Literal["x", "y"]
    offset: NonNegativeFeet
    from_: NonNegativeFeet = Field(alias="from")
    to: NonNegativeFeet
    thickness: PositiveFeet
    # Bearing walls get a continuous footing on the foundation plan.
    bearing: bool = False
    doors: list[InteriorDoor] = []


class Opening(_Model):
    type: Literal["door", "window"]
    wall: Literal["front", "rear", "left", "right"]
    offset: NonNegativeFeet
    width: PositiveFeet
    height: PositiveFeet
    sill: NonNegativeFeet | None = None
    swing: Literal["in-left", "in-right", "out-left", "out-right"] | None = None
    egress: bool = False


class Room(_Model):
    name: str
    label_at: Point
    # Stated by the Drafter, never computed: rooms are label points only.
    area: PositiveFeet | None = None


class Detector(_Model):
    """A smoke / CO alarm at an explicit building-local point."""

    type: Literal["smoke", "co", "combo"]
    at: Point


class Fixture(_Model):
    """A plumbing fixture / appliance symbol at an explicit point.

    `at` is the symbol's center; `rotation` spins it counterclockwise
    (at 0 the fixture's back — tank, faucet, wall side — faces +y).
    `size` is required for counters and forbidden elsewhere: every other
    symbol has a standard footprint.
    """

    type: Literal[
        "toilet", "lavatory", "bathtub", "shower", "kitchen-sink",
        "range", "refrigerator", "washer-dryer", "water-heater", "counter",
    ]
    at: Point
    rotation: Literal[0, 90, 180, 270] = 0
    size: Footprint | None = None

    @model_validator(mode="after")
    def _counter_size(self) -> "Fixture":
        if self.type == "counter" and self.size is None:
            raise ValueError("counter requires an explicit size")
        if self.type != "counter" and self.size is not None:
            raise ValueError(f"{self.type} has a standard size; do not set one")
        return self


class Callout(_Model):
    """A text label with a leader arrow to an explicit point.

    `at` is the leader tail — the text sits just beyond it, on the side
    away from the target — and the arrowhead lands on `target`. Both are
    building-local points.
    """

    text: str
    at: Point
    target: Point


class SectionCut(_Model):
    """A transverse building section, cut perpendicular to the roof ridge.

    `at` is the station along the ridge axis. The view looks toward the
    rising ridge-axis coordinate (rear for a y ridge, right for an x ridge).
    """

    name: str
    at: NonNegativeFeet


class ProjectConfig(_Model):
    schema_version: Literal[1]
    name: str
    location: str
    output_target: str
    units: Literal["feet"]
    site: Site
    building: Building
    interior_walls: list[InteriorWall] = []
    openings: list[Opening] = []
    rooms: list[Room] = []
    detectors: list[Detector] = []
    fixtures: list[Fixture] = []
    callouts: list[Callout] = []
    sections: list[SectionCut] = []
    notes: list[str] = []


def load_project_config(path: Path) -> ProjectConfig:
    """Load and validate a Project Config from a JSON file."""

    with Path(path).open("r", encoding="utf-8") as handle:
        try:
            data = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ProjectConfigError([f"file is not valid JSON: {exc}"]) from exc

    try:
        project = ProjectConfig.model_validate(data)
    except ValidationError as exc:
        raise ProjectConfigError(
            [_format_validation_error(error) for error in exc.errors()]
        ) from exc

    geometry_errors = _geometry_errors(project)
    if geometry_errors:
        raise ProjectConfigError(geometry_errors)
    return project


def _geometry_errors(project: ProjectConfig) -> list[str]:
    """Cross-field checks: everything must fit where the config places it."""

    errors: list[str] = []
    lot = project.site.lot
    building = project.building
    footprint = building.footprint

    for index, structure in enumerate(project.site.existing_structures):
        if (
            structure.x + structure.width > lot.width
            or structure.y + structure.depth > lot.depth
        ):
            errors.append(
                f"site.existing_structures[{index}]: '{structure.label}' extends "
                f"beyond the {lot.width} x {lot.depth} ft lot"
            )

    if (
        building.position.x + footprint.width > lot.width
        or building.position.y + footprint.depth > lot.depth
    ):
        errors.append(
            f"building: footprint placed at ({building.position.x}, "
            f"{building.position.y}) extends beyond the {lot.width} x {lot.depth} ft lot"
        )

    wall_lengths = {
        "front": footprint.width,
        "rear": footprint.width,
        "left": footprint.depth,
        "right": footprint.depth,
    }
    for index, opening in enumerate(project.openings):
        wall_length = wall_lengths[opening.wall]
        if opening.offset + opening.width > wall_length:
            errors.append(
                f"openings[{index}]: {opening.type} spans offset {opening.offset} + "
                f"width {opening.width} ft but the {opening.wall} wall is "
                f"{wall_length} ft long"
            )
        if opening.type == "window" and opening.sill is None:
            errors.append(f"openings[{index}]: window requires a sill height")
        if opening.type == "door" and opening.sill is not None:
            errors.append(f"openings[{index}]: door must not set a sill")
        if opening.type == "door" and opening.swing is None:
            errors.append(f"openings[{index}]: door requires a swing direction")
        if opening.type == "window" and opening.swing is not None:
            errors.append(f"openings[{index}]: window must not set a swing")
        top = opening.height + (opening.sill or 0 if opening.type == "window" else 0)
        if top > building.wall_height:
            errors.append(
                f"openings[{index}]: {opening.type} reaches {top} ft, above the "
                f"{building.wall_height} ft wall height"
            )
        if opening.egress:
            if opening.type == "door":
                errors.append(f"openings[{index}]: egress applies to windows only")
            else:
                # Geometric necessities for a CRC R310 escape opening: the
                # gross opening can never satisfy limits its geometry breaks.
                # (Net clear opening still depends on the window type — the
                # Drafter verifies that.)
                sill = opening.sill or 0.0
                if sill > 44 / 12:
                    errors.append(
                        f"openings[{index}]: egress window sill is {sill} ft; "
                        "CRC R310 allows at most 44 in (3.67 ft)"
                    )
                if opening.width < 20 / 12:
                    errors.append(
                        f"openings[{index}]: egress window is {opening.width} ft "
                        "wide; CRC R310 needs at least 20 in of clear width"
                    )
                if opening.height < 2.0:
                    errors.append(
                        f"openings[{index}]: egress window is {opening.height} ft "
                        "tall; CRC R310 needs at least 24 in of clear height"
                    )
                if opening.width * opening.height < 5.7:
                    errors.append(
                        f"openings[{index}]: egress window opening is only "
                        f"{opening.width * opening.height:.2f} sq ft gross; CRC "
                        "R310 needs a 5.7 sq ft net clear opening"
                    )

    for index, wall in enumerate(project.interior_walls):
        across, along = (
            (footprint.depth, footprint.width)
            if wall.axis == "x"
            else (footprint.width, footprint.depth)
        )
        if wall.offset > across or wall.to > along or wall.from_ >= wall.to:
            errors.append(
                f"interior_walls[{index}]: wall (axis {wall.axis}, offset "
                f"{wall.offset}, from {wall.from_} to {wall.to}) does not fit the "
                f"{footprint.width} x {footprint.depth} ft footprint"
            )
        for door_index, door in enumerate(wall.doors):
            if door.at < wall.from_ or door.at + door.width > wall.to:
                errors.append(
                    f"interior_walls[{index}].doors[{door_index}]: door spans "
                    f"{door.at} to {door.at + door.width} ft but the wall runs "
                    f"from {wall.from_} to {wall.to}"
                )
            if door.height > building.wall_height:
                errors.append(
                    f"interior_walls[{index}].doors[{door_index}]: door is "
                    f"{door.height} ft tall, above the {building.wall_height} ft "
                    "wall height"
                )

    for index, room in enumerate(project.rooms):
        if room.label_at.x > footprint.width or room.label_at.y > footprint.depth:
            errors.append(
                f"rooms[{index}]: label for '{room.name}' at ({room.label_at.x}, "
                f"{room.label_at.y}) is outside the {footprint.width} x "
                f"{footprint.depth} ft footprint"
            )

    for index, detector in enumerate(project.detectors):
        if detector.at.x > footprint.width or detector.at.y > footprint.depth:
            errors.append(
                f"detectors[{index}]: {detector.type} alarm at ({detector.at.x}, "
                f"{detector.at.y}) is outside the {footprint.width} x "
                f"{footprint.depth} ft footprint"
            )

    if building.foundation is not None:
        for index, hold_down in enumerate(building.foundation.hold_downs):
            if (
                hold_down.at.x > footprint.width
                or hold_down.at.y > footprint.depth
            ):
                errors.append(
                    f"building.foundation.hold_downs[{index}]: "
                    f"'{hold_down.label}' at ({hold_down.at.x}, {hold_down.at.y}) "
                    f"is outside the {footprint.width} x {footprint.depth} ft "
                    "footprint"
                )

    for index, fixture in enumerate(project.fixtures):
        if fixture.at.x > footprint.width or fixture.at.y > footprint.depth:
            errors.append(
                f"fixtures[{index}]: {fixture.type} at ({fixture.at.x}, "
                f"{fixture.at.y}) is outside the {footprint.width} x "
                f"{footprint.depth} ft footprint"
            )

    for index, callout in enumerate(project.callouts):
        for field, point in (("at", callout.at), ("target", callout.target)):
            if point.x > footprint.width or point.y > footprint.depth:
                errors.append(
                    f"callouts[{index}]: {field} ({point.x}, {point.y}) is "
                    f"outside the {footprint.width} x {footprint.depth} ft "
                    "footprint"
                )
        if (callout.at.x, callout.at.y) == (callout.target.x, callout.target.y):
            errors.append(
                f"callouts[{index}]: at and target are the same point; the "
                "leader needs a direction"
            )

    if project.sections and building.roof.ridge_axis is None:
        errors.append("sections: section cuts require a gable roof with a ridge_axis")
    else:
        ridge_run = (
            footprint.depth if building.roof.ridge_axis == "y" else footprint.width
        )
        seen_section_names = set()
        for index, cut in enumerate(project.sections):
            if cut.at > ridge_run:
                errors.append(
                    f"sections[{index}]: station {cut.at} is beyond the "
                    f"{ridge_run} ft ridge run"
                )
            if cut.name in seen_section_names:
                errors.append(
                    f"sections[{index}]: duplicate section name '{cut.name}'"
                )
            seen_section_names.add(cut.name)

    return errors


def _format_validation_error(error: Mapping[str, Any]) -> str:
    path = ".".join(str(part) for part in error["loc"]) or "<root>"
    message = str(error["msg"]).removeprefix("Value error, ")
    return f"{path}: {message}"
