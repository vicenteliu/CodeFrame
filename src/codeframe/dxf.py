"""DXF output for the Deterministic Core.

Site plans are drawn in lot coordinates, floor plans in building-local
coordinates (see `codeframe.schema` for both conventions). All output is
DXF R2010 with volatile header fields pinned so that identical Project
Configs produce byte-identical files.
"""

from __future__ import annotations

from pathlib import Path

import ezdxf
from ezdxf.document import Drawing
from ezdxf.enums import TextEntityAlignment

from .geometry import (
    elevation_interval,
    elevation_length,
    parse_slope,
    subtract_intervals,
    wall_frame,
)
from .schema import Opening, ProjectConfig, Roof


class UnsupportedRoofError(ValueError):
    """The Project Config is valid but the drawing engine can't draw it yet."""

TEXT_HEIGHT = 0.375  # model-space feet; reads as 3/32" at 1/4" = 1'-0"

SITE_LAYERS = {
    "C-PROP": {"color": 7, "lineweight": 50},
    "C-PROP-SBCK": {"color": 8, "lineweight": 18, "linetype": "DASHED"},
    "C-BLDG-EXST": {"color": 8, "lineweight": 25},
    "C-BLDG-PROP": {"color": 7, "lineweight": 50},
    "C-ANNO-TEXT": {"color": 7, "lineweight": 18},
    "C-ANNO-DIMS": {"color": 3, "lineweight": 13},
}

FLOOR_LAYERS = {
    "A-WALL": {"color": 7, "lineweight": 50},
    "A-WALL-INTR": {"color": 7, "lineweight": 35},
    "A-DOOR": {"color": 4, "lineweight": 25},
    "A-GLAZ": {"color": 4, "lineweight": 25},
    "A-ANNO-TEXT": {"color": 7, "lineweight": 18},
    "A-ANNO-DIMS": {"color": 3, "lineweight": 13},
}

ELEVATION_LAYERS = {
    "A-ELEV": {"color": 7, "lineweight": 35},
    "A-ROOF": {"color": 7, "lineweight": 50},
    "A-DOOR": {"color": 4, "lineweight": 25},
    "A-GLAZ": {"color": 4, "lineweight": 25},
    "A-ANNO-TEXT": {"color": 7, "lineweight": 18},
    "A-ANNO-DIMS": {"color": 3, "lineweight": 13},
}

ROOF_PLAN_LAYERS = {
    "A-ROOF": {"color": 7, "lineweight": 50},
    "A-WALL-BLW": {"color": 8, "lineweight": 18, "linetype": "DASHED"},
    "A-ANNO-TEXT": {"color": 7, "lineweight": 18},
}


def _new_document(layers: dict[str, dict]) -> Drawing:
    # Pin GUIDs, dates, and the ezdxf marker at export time: identical
    # Project Configs must produce byte-identical DXF files.
    ezdxf.options.write_fixed_meta_data_for_testing = True
    doc = ezdxf.new("R2010", setup=True)

    for name, attribs in layers.items():
        doc.layers.add(name, **attribs)

    doc.dimstyles.new(
        "CODEFRAME",
        dxfattribs={
            "dimtxt": TEXT_HEIGHT,
            "dimasz": 0.1875,
            "dimexo": 0.25,
            "dimexe": 0.125,
            "dimgap": 0.09,
            "dimtad": 1,
            "dimtih": 0,
            "dimtoh": 0,
            "dimdec": 1,
            "dimzin": 8,
            "dimpost": "<>'",
            "dimblk": "ARCHTICK",
        },
    )
    return doc


def _save(doc: Drawing, path: Path) -> None:
    """Save and canonicalize: byte-identical output must not depend on
    process history, but ezdxf registers CLASSES entries in an order that
    does. CAD readers ignore CLASS order, so sort the section."""

    doc.saveas(path)
    lines = Path(path).read_text(encoding="utf-8").splitlines(keepends=True)

    def find_pair(first: str, second: str, start: int) -> int:
        for i in range(start, len(lines) - 1):
            if lines[i].strip() == first and lines[i + 1].strip() == second:
                return i
        return -1

    section = find_pair("SECTION", "2", 0)
    while section != -1 and lines[section + 2].strip() != "CLASSES":
        section = find_pair("SECTION", "2", section + 1)
    if section == -1:
        return

    first_class = find_pair("0", "CLASS", section)
    end_section = find_pair("0", "ENDSEC", section)
    if first_class == -1 or end_section == -1:
        return

    entries = []
    cursor = first_class
    while cursor != -1 and cursor < end_section:
        next_entry = find_pair("0", "CLASS", cursor + 1)
        stop = next_entry if next_entry != -1 and next_entry < end_section else end_section
        entries.append(lines[cursor:stop])
        cursor = next_entry if next_entry != -1 and next_entry < end_section else -1

    entries.sort(key=lambda entry: "".join(entry))
    flattened = [line for entry in entries for line in entry]
    Path(path).write_text(
        "".join(lines[:first_class] + flattened + lines[end_section:]),
        encoding="utf-8",
    )


def _add_rectangle(msp, layer: str, x: float, y: float, width: float, depth: float):
    corners = [(x, y), (x + width, y), (x + width, y + depth), (x, y + depth)]
    msp.add_lwpolyline(corners, close=True, dxfattribs={"layer": layer})


def _add_label(msp, layer: str, text: str, at: tuple[float, float]):
    msp.add_text(
        text, dxfattribs={"layer": layer, "height": TEXT_HEIGHT}
    ).set_placement(at, align=TextEntityAlignment.MIDDLE_CENTER)


def _add_dim(msp, layer: str, p1: tuple[float, float], p2: tuple[float, float], *, angle: float, base: tuple[float, float]):
    """Linear dimension between p1 and p2; `base` fixes the dimension line."""

    dim = msp.add_linear_dim(
        base=base,
        p1=p1,
        p2=p2,
        angle=angle,
        dimstyle="CODEFRAME",
        dxfattribs={"layer": layer},
    )
    dim.render()


def write_site_plan(project: ProjectConfig, path: Path) -> None:
    """Write the site plan DXF: lot, setbacks, structures, placement dims."""

    _save(build_site_plan(project), path)


def build_site_plan(project: ProjectConfig) -> Drawing:
    doc = _new_document(SITE_LAYERS)
    msp = doc.modelspace()

    lot = project.site.lot
    setbacks = project.site.setbacks
    building = project.building
    position = building.position
    footprint = building.footprint

    _add_rectangle(msp, "C-PROP", 0, 0, lot.width, lot.depth)
    _add_rectangle(
        msp,
        "C-PROP-SBCK",
        setbacks.left,
        setbacks.front,
        lot.width - setbacks.left - setbacks.right,
        lot.depth - setbacks.front - setbacks.rear,
    )

    for structure in project.site.existing_structures:
        _add_rectangle(
            msp, "C-BLDG-EXST", structure.x, structure.y, structure.width, structure.depth
        )
        _add_label(
            msp,
            "C-ANNO-TEXT",
            structure.label,
            (structure.x + structure.width / 2, structure.y + structure.depth / 2),
        )

    _add_rectangle(
        msp, "C-BLDG-PROP", position.x, position.y, footprint.width, footprint.depth
    )
    _add_label(
        msp,
        "C-ANNO-TEXT",
        "PROPOSED STRUCTURE",
        (position.x + footprint.width / 2, position.y + footprint.depth / 2),
    )

    # Placement dimensions: building face to each lot line, what plan
    # checkers read setbacks from. Measured at the building's right and
    # front faces so the dimension lines sit in clear corridors beside it.
    right = position.x + footprint.width
    rear = position.y + footprint.depth
    dim_x = right + 3
    dim_y = position.y - 3
    _add_dim(
        msp, "C-ANNO-DIMS", (right, 0), (right, position.y),
        angle=90, base=(dim_x, 0),
    )
    _add_dim(
        msp, "C-ANNO-DIMS", (right, rear), (right, lot.depth),
        angle=90, base=(dim_x, lot.depth),
    )
    _add_dim(
        msp, "C-ANNO-DIMS", (0, position.y), (position.x, position.y),
        angle=0, base=(0, dim_y),
    )
    _add_dim(
        msp, "C-ANNO-DIMS", (right, position.y), (lot.width, position.y),
        angle=0, base=(lot.width, dim_y),
    )

    return doc


def _draw_door(msp, frame, opening: Opening, wall_thickness: float) -> None:
    """Door leaf drawn open 90 degrees plus its quarter-circle swing arc."""

    assert opening.swing is not None
    inward = opening.swing.startswith("in")
    hinge_left = opening.swing.endswith("left")

    face_d = wall_thickness if inward else 0.0
    leaf_sign = 1 if inward else -1
    hinge_s = opening.offset if hinge_left else opening.offset + opening.width

    hinge = frame.point(hinge_s, face_d)
    leaf_tip = frame.point(hinge_s, face_d + leaf_sign * opening.width)
    msp.add_line(hinge, leaf_tip, dxfattribs={"layer": "A-DOOR"})

    strike_angle = frame.angle(0 if hinge_left else 180)
    leaf_angle = frame.angle(90 if inward else 270)
    if (leaf_angle - strike_angle) % 360 == 90:
        start_angle, end_angle = strike_angle, leaf_angle
    else:
        start_angle, end_angle = leaf_angle, strike_angle
    msp.add_arc(
        center=hinge,
        radius=opening.width,
        start_angle=start_angle,
        end_angle=end_angle,
        dxfattribs={"layer": "A-DOOR"},
    )


def write_floor_plan(project: ProjectConfig, path: Path) -> None:
    """Write the floor plan DXF: walls, openings, room labels, overall dims."""

    _save(build_floor_plan(project), path)


def build_floor_plan(project: ProjectConfig) -> Drawing:
    doc = _new_document(FLOOR_LAYERS)
    msp = doc.modelspace()

    building = project.building
    footprint = building.footprint
    thickness = building.exterior_wall_thickness

    for wall_name in ("front", "rear", "left", "right"):
        frame = wall_frame(wall_name, footprint.width, footprint.depth)
        openings = [o for o in project.openings if o.wall == wall_name]
        cuts = [(o.offset, o.offset + o.width) for o in openings]

        # Outer face runs corner to corner; inner face runs between the
        # inner corners. Both break at openings.
        faces = ((0.0, (0.0, frame.length)), (thickness, (thickness, frame.length - thickness)))
        for face_d, span in faces:
            for piece_start, piece_end in subtract_intervals(span, cuts):
                msp.add_line(
                    frame.point(piece_start, face_d),
                    frame.point(piece_end, face_d),
                    dxfattribs={"layer": "A-WALL"},
                )

        for opening in openings:
            for jamb_s in (opening.offset, opening.offset + opening.width):
                msp.add_line(
                    frame.point(jamb_s, 0),
                    frame.point(jamb_s, thickness),
                    dxfattribs={"layer": "A-WALL"},
                )
            if opening.type == "door":
                _draw_door(msp, frame, opening, thickness)
            else:
                msp.add_line(
                    frame.point(opening.offset, thickness / 2),
                    frame.point(opening.offset + opening.width, thickness / 2),
                    dxfattribs={"layer": "A-GLAZ"},
                )

    for wall in project.interior_walls:
        half = wall.thickness / 2
        along = footprint.width if wall.axis == "x" else footprint.depth
        # The drawn extent stops at the exterior walls' inner faces.
        lo = max(wall.from_, thickness)
        hi = min(wall.to, along - thickness)
        for face in (wall.offset - half, wall.offset + half):
            if wall.axis == "x":
                msp.add_line((lo, face), (hi, face), dxfattribs={"layer": "A-WALL-INTR"})
            else:
                msp.add_line((face, lo), (face, hi), dxfattribs={"layer": "A-WALL-INTR"})
        # Cap any free-standing end (one that never reaches an exterior wall).
        for end, is_free in ((lo, wall.from_ > thickness), (hi, wall.to < along - thickness)):
            if is_free:
                if wall.axis == "x":
                    cap = ((end, wall.offset - half), (end, wall.offset + half))
                else:
                    cap = ((wall.offset - half, end), (wall.offset + half, end))
                msp.add_line(*cap, dxfattribs={"layer": "A-WALL-INTR"})

    for room in project.rooms:
        _add_label(msp, "A-ANNO-TEXT", room.name, (room.label_at.x, room.label_at.y))

    _add_dim(
        msp, "A-ANNO-DIMS", (0, 0), (footprint.width, 0),
        angle=0, base=(0, -3),
    )
    _add_dim(
        msp, "A-ANNO-DIMS", (0, 0), (0, footprint.depth),
        angle=90, base=(-3, 0),
    )

    return doc


def _require_gable(roof: Roof) -> None:
    if roof.type != "gable":
        raise UnsupportedRoofError(
            f"roof type '{roof.type}' is not supported by the drawing engine "
            "yet; v1 draws gable roofs only"
        )


def write_elevation(project: ProjectConfig, wall: str, path: Path) -> None:
    """Write one elevation DXF, drawn as seen from outside `wall`."""

    _save(build_elevation(project, wall), path)


def build_elevation(project: ProjectConfig, wall: str) -> Drawing:
    building = project.building
    roof = building.roof
    _require_gable(roof)

    doc = _new_document(ELEVATION_LAYERS)
    msp = doc.modelspace()

    footprint = building.footprint
    wall_height = building.wall_height
    rise = parse_slope(roof.slope)
    overhang = roof.overhang
    length = elevation_length(wall, footprint.width, footprint.depth)

    # Gable ends are the walls the ridge runs away from.
    gable_end = (roof.ridge_axis == "y") == (wall in ("front", "rear"))
    ridge_span = footprint.width if roof.ridge_axis == "y" else footprint.depth
    ridge_z = wall_height + (ridge_span / 2) * rise
    eave_z = wall_height - overhang * rise

    if gable_end:
        face = [(0, 0), (length, 0), (length, wall_height),
                (length / 2, ridge_z), (0, wall_height)]
    else:
        face = [(0, 0), (length, 0), (length, wall_height), (0, wall_height)]
    msp.add_lwpolyline(face, close=True, dxfattribs={"layer": "A-ELEV"})

    if gable_end:
        apex = (length / 2, ridge_z)
        msp.add_line((-overhang, eave_z), apex, dxfattribs={"layer": "A-ROOF"})
        msp.add_line(apex, (length + overhang, eave_z), dxfattribs={"layer": "A-ROOF"})
    else:
        for z in (eave_z, ridge_z):
            msp.add_line(
                (-overhang, z), (length + overhang, z), dxfattribs={"layer": "A-ROOF"}
            )
        for h in (-overhang, length + overhang):
            msp.add_line((h, eave_z), (h, ridge_z), dxfattribs={"layer": "A-ROOF"})

    for opening in project.openings:
        if opening.wall != wall:
            continue
        h0, h1 = elevation_interval(
            wall,
            opening.offset,
            opening.offset + opening.width,
            footprint.width,
            footprint.depth,
        )
        bottom = 0.0 if opening.type == "door" else (opening.sill or 0.0)
        top = bottom + opening.height
        layer = "A-DOOR" if opening.type == "door" else "A-GLAZ"
        msp.add_lwpolyline(
            [(h0, bottom), (h1, bottom), (h1, top), (h0, top)],
            close=True,
            dxfattribs={"layer": layer},
        )

    # Grade line under everything, running past the roof overhangs.
    msp.add_line(
        (-overhang - 3, 0), (length + overhang + 3, 0), dxfattribs={"layer": "A-ELEV"}
    )

    _add_label(msp, "A-ANNO-TEXT", f"{wall.upper()} ELEVATION", (length / 2, -2.5))
    _add_dim(
        msp, "A-ANNO-DIMS", (0, 0), (0, ridge_z),
        angle=90, base=(-overhang - 3, 0),
    )

    return doc


def write_roof_plan(project: ProjectConfig, path: Path) -> None:
    """Write the roof plan DXF: roof outline, ridge, walls below, slope notes."""

    _save(build_roof_plan(project), path)


def build_roof_plan(project: ProjectConfig) -> Drawing:
    building = project.building
    roof = building.roof
    _require_gable(roof)

    doc = _new_document(ROOF_PLAN_LAYERS)
    msp = doc.modelspace()

    footprint = building.footprint
    overhang = roof.overhang
    width = footprint.width
    depth = footprint.depth

    _add_rectangle(
        msp, "A-ROOF", -overhang, -overhang,
        width + 2 * overhang, depth + 2 * overhang,
    )
    _add_rectangle(msp, "A-WALL-BLW", 0, 0, width, depth)

    if roof.ridge_axis == "y":
        msp.add_line(
            (width / 2, -overhang), (width / 2, depth + overhang),
            dxfattribs={"layer": "A-ROOF"},
        )
        slope_points = ((width / 4, depth / 2), (3 * width / 4, depth / 2))
    else:
        msp.add_line(
            (-overhang, depth / 2), (width + overhang, depth / 2),
            dxfattribs={"layer": "A-ROOF"},
        )
        slope_points = ((width / 2, depth / 4), (width / 2, 3 * depth / 4))

    for point in slope_points:
        _add_label(msp, "A-ANNO-TEXT", roof.slope, point)

    _add_label(msp, "A-ANNO-TEXT", "ROOF PLAN", (width / 2, -overhang - 2.5))

    return doc
