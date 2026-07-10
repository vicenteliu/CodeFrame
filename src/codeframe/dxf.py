"""DXF output for the Deterministic Core.

Site plans are drawn in lot coordinates, floor plans in building-local
coordinates (see `codeframe.schema` for both conventions). All output is
DXF R2010 with volatile header fields pinned so that identical Project
Configs produce byte-identical files.
"""

from __future__ import annotations

import math
from pathlib import Path

import ezdxf
from ezdxf.document import Drawing
from ezdxf.enums import TextEntityAlignment

from .geometry import (
    WallFrame,
    elevation_interval,
    elevation_length,
    parse_slope,
    subtract_intervals,
    wall_frame,
)
from .schema import Fixture, ProjectConfig, Roof, SectionCut


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
    "A-FIRE": {"color": 1, "lineweight": 25},
    "A-FIXT": {"color": 8, "lineweight": 18},
    "A-ANNO-SECT": {"color": 6, "lineweight": 25, "linetype": "DASHED"},
    "A-ANNO-TEXT": {"color": 7, "lineweight": 18},
    "A-ANNO-DIMS": {"color": 3, "lineweight": 13},
}

SECTION_LAYERS = {
    "A-WALL": {"color": 7, "lineweight": 50},
    "A-WALL-INTR": {"color": 7, "lineweight": 35},
    "A-ROOF": {"color": 7, "lineweight": 50},
    "A-ELEV": {"color": 7, "lineweight": 35},
    "A-ANNO-TEXT": {"color": 7, "lineweight": 18},
    "A-ANNO-DIMS": {"color": 3, "lineweight": 13},
}

DETECTOR_LABELS = {"smoke": "S", "co": "CO", "combo": "S/CO"}

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

SCHEDULE_LAYERS = {
    "A-ANNO-TABL": {"color": 7, "lineweight": 25},
    "A-ANNO-TEXT": {"color": 7, "lineweight": 18},
}


def format_feet_inches(feet: float) -> str:
    """Format decimal feet as a feet-inches dimension string (6.67 -> 6'-8")."""

    total_inches = round(feet * 12)
    whole_feet, inches = divmod(total_inches, 12)
    return f"{whole_feet}'-{inches}\""


def _schedule_data(project: ProjectConfig):
    """Group openings into schedule rows and assign deterministic marks.

    Identical doors share a D-mark (exterior types first, then largest
    first); identical windows share a W-mark. Returns (door_rows,
    window_rows, marks) where rows are (mark, width, height, extra, count)
    and marks maps opening keys — ("ext", wall, offset) for exterior
    openings, ("int", wall_index, at) for interior doors — to their mark.
    """

    door_groups: dict = {}
    window_groups: dict = {}
    for opening in project.openings:
        if opening.type == "door":
            key = ("EXTERIOR", opening.width, opening.height)
            door_groups.setdefault(key, []).append(("ext", opening.wall, opening.offset))
        else:
            key = (opening.width, opening.height, opening.sill or 0.0, opening.egress)
            window_groups.setdefault(key, []).append(("ext", opening.wall, opening.offset))
    for wall_index, wall in enumerate(project.interior_walls):
        for door in wall.doors:
            key = ("INTERIOR", door.width, door.height)
            door_groups.setdefault(key, []).append(("int", wall_index, door.at))

    marks: dict = {}
    door_rows = []
    door_order = sorted(
        door_groups,
        key=lambda k: (0 if k[0] == "EXTERIOR" else 1, -k[1], -k[2]),
    )
    for number, key in enumerate(door_order, start=1):
        mark = f"D{number}"
        kind, width, height = key
        refs = door_groups[key]
        door_rows.append((mark, width, height, kind, len(refs)))
        for ref in refs:
            marks[ref] = mark

    window_rows = []
    window_order = sorted(
        window_groups, key=lambda k: (-k[0], -k[1], k[2], not k[3])
    )
    for number, key in enumerate(window_order, start=1):
        mark = f"W{number}"
        width, height, sill, egress = key
        refs = window_groups[key]
        window_rows.append(
            (mark, width, height, format_feet_inches(sill), len(refs), egress)
        )
        for ref in refs:
            marks[ref] = mark

    return door_rows, window_rows, marks


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


class _SymbolFrame:
    """Draws fixture primitives in symbol-local coords (centered at the
    origin, back toward +y) rotated CCW and translated onto the plan."""

    def __init__(self, msp, at, rotation_degrees: int):
        self.msp = msp
        radians = math.radians(rotation_degrees)
        self._cos, self._sin = math.cos(radians), math.sin(radians)
        self._origin = (at.x, at.y)

    def point(self, x: float, y: float) -> tuple[float, float]:
        return (
            self._origin[0] + x * self._cos - y * self._sin,
            self._origin[1] + x * self._sin + y * self._cos,
        )

    def rect(self, cx: float, cy: float, w: float, d: float) -> None:
        corners = [
            self.point(cx - w / 2, cy - d / 2), self.point(cx + w / 2, cy - d / 2),
            self.point(cx + w / 2, cy + d / 2), self.point(cx - w / 2, cy + d / 2),
        ]
        self.msp.add_lwpolyline(corners, close=True, dxfattribs={"layer": "A-FIXT"})

    def line(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.msp.add_line(
            self.point(x1, y1), self.point(x2, y2), dxfattribs={"layer": "A-FIXT"}
        )

    def circle(self, cx: float, cy: float, radius: float) -> None:
        self.msp.add_circle(
            center=self.point(cx, cy), radius=radius, dxfattribs={"layer": "A-FIXT"}
        )

    def ellipse(self, cx: float, cy: float, rx: float, ry: float) -> None:
        # DXF wants the major axis with ratio = minor/major <= 1.
        if rx >= ry:
            tip, ratio = (cx + rx, cy), ry / rx
        else:
            tip, ratio = (cx, cy + ry), rx / ry
        center = self.point(cx, cy)
        tip_point = self.point(*tip)
        major = (tip_point[0] - center[0], tip_point[1] - center[1])
        self.msp.add_ellipse(
            center=center, major_axis=major, ratio=ratio,
            dxfattribs={"layer": "A-FIXT"},
        )

    def label(self, text: str, cx: float = 0.0, cy: float = 0.0) -> None:
        _add_label(self.msp, "A-FIXT", text, self.point(cx, cy))


def _draw_fixture(msp, fixture: Fixture) -> None:
    sym = _SymbolFrame(msp, fixture.at, fixture.rotation)
    kind = fixture.type
    if kind == "toilet":
        sym.rect(0, 0.79, 1.5, 0.75)                # tank against the wall
        sym.ellipse(0, -0.29, 0.58, 0.83)           # bowl
    elif kind == "lavatory":
        sym.ellipse(0, 0, 0.8, 0.65)
    elif kind == "bathtub":
        sym.rect(0, 0, 5.0, 2.5)
        sym.rect(0, 0, 4.5, 2.0)
        sym.circle(-1.85, 0, 0.15)                  # drain
    elif kind == "shower":
        sym.rect(0, 0, 3.0, 3.0)
        sym.line(-1.5, -1.5, 1.5, 1.5)
        sym.line(-1.5, 1.5, 1.5, -1.5)
    elif kind == "kitchen-sink":
        sym.rect(0, 0, 2.75, 1.83)
        sym.rect(-0.65, 0, 1.05, 1.33)
        sym.rect(0.65, 0, 1.05, 1.33)
    elif kind == "range":
        sym.rect(0, 0, 2.5, 2.17)
        for bx in (-0.62, 0.62):
            for by in (-0.54, 0.54):
                sym.circle(bx, by, 0.29)
    elif kind == "refrigerator":
        sym.rect(0, 0, 3.0, 2.5)
        sym.label("REF")
    elif kind == "washer-dryer":
        sym.rect(-1.125, 0, 2.25, 2.25)
        sym.rect(1.125, 0, 2.25, 2.25)
        sym.label("W", -1.125, 0)
        sym.label("D", 1.125, 0)
    elif kind == "water-heater":
        sym.circle(0, 0, 1.0)
        sym.label("WH")
    elif kind == "counter":
        assert fixture.size is not None
        sym.rect(0, 0, fixture.size.width, fixture.size.depth)


def _add_tag(msp, mark: str, at: tuple[float, float]) -> None:
    """Schedule mark: text in a circle, pointing back to the schedule row."""

    msp.add_circle(center=at, radius=0.7, dxfattribs={"layer": "A-ANNO-TEXT"})
    _add_label(msp, "A-ANNO-TEXT", mark, at)


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

    if project.site.north_rotation is not None:
        _draw_north_arrow(msp, project.site.north_rotation, lot)
    _draw_scale_bar(msp)

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


def _draw_north_arrow(msp, north_rotation: float, lot) -> None:
    """North arrow beside the lot: circle, shaft, arrowhead, N label."""

    radians = math.radians(north_rotation)
    direction = (-math.sin(radians), math.cos(radians))
    center = (lot.width + 6.0, lot.depth - 5.0)
    radius = 2.0

    def along(scale: float) -> tuple[float, float]:
        return (center[0] + direction[0] * scale, center[1] + direction[1] * scale)

    msp.add_circle(center=center, radius=radius, dxfattribs={"layer": "C-ANNO-TEXT"})
    tip = along(radius)
    msp.add_line(along(-radius), tip, dxfattribs={"layer": "C-ANNO-TEXT"})
    for wing in (140, -140):
        wing_radians = math.radians(north_rotation + wing)
        wing_end = (
            tip[0] - math.sin(wing_radians) * 0.8,
            tip[1] + math.cos(wing_radians) * 0.8,
        )
        msp.add_line(tip, wing_end, dxfattribs={"layer": "C-ANNO-TEXT"})
    _add_label(msp, "C-ANNO-TEXT", "N", along(radius + 1.2))


def _draw_scale_bar(msp) -> None:
    """Graphic scale bar below the lot; stays true at any print scale."""

    y = -4.0
    msp.add_line((0, y), (40, y), dxfattribs={"layer": "C-ANNO-TEXT"})
    for station in (0, 10, 20, 40):
        msp.add_line(
            (station, y), (station, y + 0.8), dxfattribs={"layer": "C-ANNO-TEXT"}
        )
        _add_label(msp, "C-ANNO-TEXT", str(station), (station, y - 1.2))
    _add_label(msp, "C-ANNO-TEXT", "GRAPHIC SCALE (FEET)", (20, y - 2.8))


def _draw_door(msp, frame, s_start: float, width: float, swing: str, wall_thickness: float) -> None:
    """Door leaf drawn open 90 degrees plus its quarter-circle swing arc."""

    inward = swing.startswith("in")
    hinge_left = swing.endswith("left")

    face_d = wall_thickness if inward else 0.0
    leaf_sign = 1 if inward else -1
    hinge_s = s_start if hinge_left else s_start + width

    hinge = frame.point(hinge_s, face_d)
    leaf_tip = frame.point(hinge_s, face_d + leaf_sign * width)
    msp.add_line(hinge, leaf_tip, dxfattribs={"layer": "A-DOOR"})

    strike_angle = frame.angle(0 if hinge_left else 180)
    leaf_angle = frame.angle(90 if inward else 270)
    if (leaf_angle - strike_angle) % 360 == 90:
        start_angle, end_angle = strike_angle, leaf_angle
    else:
        start_angle, end_angle = leaf_angle, strike_angle
    msp.add_arc(
        center=hinge,
        radius=width,
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
    _door_rows, _window_rows, marks = _schedule_data(project)

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
                assert opening.swing is not None
                _draw_door(msp, frame, opening.offset, opening.width, opening.swing, thickness)
            else:
                msp.add_line(
                    frame.point(opening.offset, thickness / 2),
                    frame.point(opening.offset + opening.width, thickness / 2),
                    dxfattribs={"layer": "A-GLAZ"},
                )
            _add_tag(
                msp,
                marks[("ext", opening.wall, opening.offset)],
                frame.point(opening.offset + opening.width / 2, -1.0),
            )
            if opening.egress:
                _add_label(
                    msp, "A-ANNO-TEXT", "EGRESS",
                    frame.point(opening.offset + opening.width / 2, thickness + 1.0),
                )

    for wall_index, wall in enumerate(project.interior_walls):
        half = wall.thickness / 2
        along = footprint.width if wall.axis == "x" else footprint.depth
        # The drawn extent stops at the exterior walls' inner faces.
        lo = max(wall.from_, thickness)
        hi = min(wall.to, along - thickness)
        door_cuts = [(door.at, door.at + door.width) for door in wall.doors]
        for face in (wall.offset - half, wall.offset + half):
            for piece_lo, piece_hi in subtract_intervals((lo, hi), door_cuts):
                if wall.axis == "x":
                    msp.add_line(
                        (piece_lo, face), (piece_hi, face),
                        dxfattribs={"layer": "A-WALL-INTR"},
                    )
                else:
                    msp.add_line(
                        (face, piece_lo), (face, piece_hi),
                        dxfattribs={"layer": "A-WALL-INTR"},
                    )
        # Interior doors: jambs across the thickness, then leaf and swing.
        # The door frame's s axis runs along the wall, d across it, with d=0
        # on the negative-side face so "in" swings toward the positive side.
        if wall.axis == "x":
            door_frame = WallFrame((0, wall.offset - half), (1, 0), (0, 1), along)
        else:
            door_frame = WallFrame((wall.offset - half, 0), (0, 1), (1, 0), along)
        for door in wall.doors:
            for jamb_s in (door.at, door.at + door.width):
                msp.add_line(
                    door_frame.point(jamb_s, 0),
                    door_frame.point(jamb_s, wall.thickness),
                    dxfattribs={"layer": "A-WALL-INTR"},
                )
            _draw_door(msp, door_frame, door.at, door.width, door.swing, wall.thickness)
            _add_tag(
                msp,
                marks[("int", wall_index, door.at)],
                door_frame.point(door.at + door.width / 2, -1.0),
            )
        # Cap any free-standing end (one that never reaches an exterior wall).
        for end, is_free in ((lo, wall.from_ > thickness), (hi, wall.to < along - thickness)):
            if is_free:
                if wall.axis == "x":
                    cap = ((end, wall.offset - half), (end, wall.offset + half))
                else:
                    cap = ((wall.offset - half, end), (wall.offset + half, end))
                msp.add_line(*cap, dxfattribs={"layer": "A-WALL-INTR"})
        # Locate the wall from the nearest exterior face, at its mid-span.
        station = (lo + hi) / 2
        across = footprint.depth if wall.axis == "x" else footprint.width
        near_face = wall.offset - half
        if wall.offset > across / 2:
            span = (wall.offset + half, across)
        else:
            span = (0.0, near_face)
        if wall.axis == "x":
            _add_dim(
                msp, "A-ANNO-DIMS", (station, span[0]), (station, span[1]),
                angle=90, base=(station, span[0]),
            )
        else:
            _add_dim(
                msp, "A-ANNO-DIMS", (span[0], station), (span[1], station),
                angle=0, base=(span[0], station),
            )

    for room in project.rooms:
        _add_label(msp, "A-ANNO-TEXT", room.name, (room.label_at.x, room.label_at.y))
        if room.area is not None:
            _add_label(
                msp, "A-ANNO-TEXT", f"{room.area:g} SF",
                (room.label_at.x, room.label_at.y - 1.0),
            )

    for fixture in project.fixtures:
        _draw_fixture(msp, fixture)

    for detector in project.detectors:
        at = (detector.at.x, detector.at.y)
        msp.add_circle(center=at, radius=0.75, dxfattribs={"layer": "A-FIRE"})
        msp.add_text(
            DETECTOR_LABELS[detector.type],
            dxfattribs={"layer": "A-FIRE", "height": TEXT_HEIGHT},
        ).set_placement(at, align=TextEntityAlignment.MIDDLE_CENTER)

    # Section cut lines run across the plan, bubbled at both ends.
    for cut in project.sections:
        if building.roof.ridge_axis == "y":
            ends = [(-5.0, cut.at), (footprint.width + 5.0, cut.at)]
            bubbles = [(-5.8, cut.at), (footprint.width + 5.8, cut.at)]
        else:
            ends = [(cut.at, -5.0), (cut.at, footprint.depth + 5.0)]
            bubbles = [(cut.at, -5.8), (cut.at, footprint.depth + 5.8)]
        msp.add_line(*ends, dxfattribs={"layer": "A-ANNO-SECT"})
        for bubble in bubbles:
            msp.add_circle(center=bubble, radius=0.7, dxfattribs={"layer": "A-ANNO-SECT"})
            msp.add_text(
                cut.name, dxfattribs={"layer": "A-ANNO-SECT", "height": TEXT_HEIGHT},
            ).set_placement(bubble, align=TextEntityAlignment.MIDDLE_CENTER)

    # Opening location chains: corner -> jamb -> jamb -> corner along each
    # exterior wall that has openings, one dimension row outside the face.
    chain_rows = {
        "front": (lambda s: (s, 0), 0, (0, -2.25)),
        "rear": (lambda s: (s, footprint.depth), 0, (0, footprint.depth + 2.25)),
        "left": (lambda s: (0, s), 90, (-2.25, 0)),
        "right": (lambda s: (footprint.width, s), 90, (footprint.width + 2.25, 0)),
    }
    for wall_name, (to_point, angle, base) in chain_rows.items():
        openings = sorted(
            (o for o in project.openings if o.wall == wall_name),
            key=lambda o: o.offset,
        )
        if not openings:
            continue
        length = elevation_length(wall_name, footprint.width, footprint.depth)
        stations = [0.0]
        for opening in openings:
            stations += [opening.offset, opening.offset + opening.width]
        stations.append(length)
        for s0, s1 in zip(stations, stations[1:]):
            if s1 > s0:
                _add_dim(
                    msp, "A-ANNO-DIMS", to_point(s0), to_point(s1),
                    angle=angle, base=base,
                )

    _add_dim(
        msp, "A-ANNO-DIMS", (0, 0), (footprint.width, 0),
        angle=0, base=(0, -3.75),
    )
    _add_dim(
        msp, "A-ANNO-DIMS", (0, 0), (0, footprint.depth),
        angle=90, base=(-3.75, 0),
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
        msp, "A-ANNO-DIMS", (0, 0), (0, wall_height),
        angle=90, base=(-overhang - 1.75, 0),
    )
    _add_dim(
        msp, "A-ANNO-DIMS", (0, 0), (0, ridge_z),
        angle=90, base=(-overhang - 3, 0),
    )

    return doc


GENERAL_NOTES: list[list[str]] = [
    ["ALL WORK SHALL COMPLY WITH THE CALIFORNIA RESIDENTIAL CODE (CRC), CBC,",
     "CEC, CMC, CPC, CALIFORNIA ENERGY CODE (TITLE 24 PART 6), AND CALGREEN AS",
     "AMENDED BY THE LOCAL JURISDICTION. VERIFY THE ENFORCED CODE CYCLE",
     "BEFORE SUBMITTAL."],
    ["WRITTEN DIMENSIONS GOVERN OVER SCALED DIMENSIONS."],
    ["VERIFY ALL DIMENSIONS AND SITE CONDITIONS BEFORE CONSTRUCTION."],
    ["SMOKE ALARMS PER CRC R314; CARBON MONOXIDE ALARMS PER CRC R315."],
    ["EMERGENCY ESCAPE AND RESCUE OPENINGS PER CRC R310."],
    ["CONTRACTOR SHALL VERIFY ALL UTILITY LOCATIONS BEFORE EXCAVATION."],
    ["THIS SET IS A PRELIMINARY DRAWING SKELETON. A QUALIFIED PROFESSIONAL",
     "MUST REVIEW, COMPLETE, AND APPROVE EVERY SHEET BEFORE ANY PERMIT",
     "SUBMITTAL."],
]

NOTES_LAYERS = {
    "A-ANNO-TEXT": {"color": 7, "lineweight": 18},
}

_NOTE_LINE_SPACING = 1.2


def write_general_notes(project: ProjectConfig, path: Path) -> None:
    """Write the general notes and project data DXF."""

    _save(build_general_notes(project), path)


def _add_note_line(msp, text: str, at: tuple[float, float]) -> None:
    msp.add_text(
        text, dxfattribs={"layer": "A-ANNO-TEXT", "height": TEXT_HEIGHT}
    ).set_placement(at, align=TextEntityAlignment.MIDDLE_LEFT)


def build_general_notes(project: ProjectConfig) -> Drawing:
    doc = _new_document(NOTES_LAYERS)
    msp = doc.modelspace()

    lot = project.site.lot
    footprint = project.building.footprint
    lot_area = lot.width * lot.depth
    footprint_area = footprint.width * footprint.depth
    roof = project.building.roof

    cursor = 0.0

    def emit(text: str, indent: float = 0.0) -> None:
        nonlocal cursor
        _add_note_line(msp, text, (indent, cursor))
        cursor -= _NOTE_LINE_SPACING

    emit("GENERAL NOTES")
    cursor -= 0.4
    for number, note_lines in enumerate(GENERAL_NOTES, start=1):
        emit(f"{number}. {note_lines[0]}", indent=1.0)
        for continuation in note_lines[1:]:
            emit(continuation, indent=2.0)

    cursor -= 1.2
    emit("PROJECT DATA")
    cursor -= 0.4
    for line in (
        f"PROJECT: {project.name.upper()}",
        f"LOCATION: {project.location.upper()}",
        f"LOT: {lot.width:g} x {lot.depth:g} FT ({lot_area:g} SF)",
        f"BUILDING FOOTPRINT: {footprint.width:g} x {footprint.depth:g} FT "
        f"({footprint_area:g} SF)",
        f"LOT COVERAGE: {100 * footprint_area / lot_area:.1f}%",
        f"WALL HEIGHT: {format_feet_inches(project.building.wall_height)}",
        f"ROOF: {roof.type.upper()} {roof.slope}, {roof.overhang:g} FT OVERHANG",
        "OCCUPANCY / CONSTRUCTION TYPE: BY DRAFTER",
    ):
        emit(line, indent=1.0)

    if project.notes:
        cursor -= 1.2
        emit("PROJECT NOTES")
        cursor -= 0.4
        for number, note in enumerate(project.notes, start=1):
            emit(f"{number}. {note.upper()}", indent=1.0)

    return doc


def write_schedules(project: ProjectConfig, path: Path) -> None:
    """Write the door and window schedules DXF."""

    _save(build_schedules(project), path)


_SCHEDULE_COLS = [3.0, 4.5, 4.5, 5.5, 3.0, 5.0]
_SCHEDULE_ROW_H = 1.5


def _draw_table(msp, title: str, headers: list[str], rows: list[tuple], top_left) -> float:
    """Draw one schedule table; returns the y of its bottom edge."""

    x0, y0 = top_left
    total_w = sum(_SCHEDULE_COLS)
    _add_label(msp, "A-ANNO-TEXT", title, (x0 + total_w / 2, y0 + 1.0))

    n_grid_rows = len(rows) + 1  # header + data
    bottom = y0 - n_grid_rows * _SCHEDULE_ROW_H
    for i in range(n_grid_rows + 1):
        y = y0 - i * _SCHEDULE_ROW_H
        msp.add_line((x0, y), (x0 + total_w, y), dxfattribs={"layer": "A-ANNO-TABL"})
    x = x0
    for width in [0.0, *_SCHEDULE_COLS]:
        x += width
        msp.add_line((x, y0), (x, bottom), dxfattribs={"layer": "A-ANNO-TABL"})

    for row_index, cells in enumerate([tuple(headers), *rows]):
        y_mid = y0 - (row_index + 0.5) * _SCHEDULE_ROW_H
        x = x0
        for width, cell in zip(_SCHEDULE_COLS, cells):
            if str(cell):
                _add_label(msp, "A-ANNO-TEXT", str(cell), (x + width / 2, y_mid))
            x += width
    return bottom


def build_schedules(project: ProjectConfig) -> Drawing:
    doc = _new_document(SCHEDULE_LAYERS)
    msp = doc.modelspace()

    door_rows, window_rows, _marks = _schedule_data(project)
    door_cells = [
        (mark, format_feet_inches(w), format_feet_inches(h), kind, count, "")
        for mark, w, h, kind, count in door_rows
    ]
    window_cells = [
        (mark, format_feet_inches(w), format_feet_inches(h), f"SILL {sill}",
         count, "EGRESS" if egress else "")
        for mark, w, h, sill, count, egress in window_rows
    ]

    bottom = _draw_table(
        msp, "DOOR SCHEDULE",
        ["MARK", "WIDTH", "HEIGHT", "TYPE", "QTY", "REMARKS"], door_cells, (0.0, 0.0),
    )
    _draw_table(
        msp, "WINDOW SCHEDULE",
        ["MARK", "WIDTH", "HEIGHT", "SILL", "QTY", "REMARKS"], window_cells,
        (0.0, bottom - 3.5),
    )
    return doc


def write_section(project: ProjectConfig, section: SectionCut, path: Path) -> None:
    """Write one transverse building section DXF."""

    _save(build_section(project, section), path)


def build_section(project: ProjectConfig, section: SectionCut) -> Drawing:
    building = project.building
    roof = building.roof
    _require_gable(roof)

    doc = _new_document(SECTION_LAYERS)
    msp = doc.modelspace()

    footprint = building.footprint
    wall_height = building.wall_height
    thickness = building.exterior_wall_thickness
    rise = parse_slope(roof.slope)
    overhang = roof.overhang

    # The view spans the axis perpendicular to the ridge. Looking toward
    # the rising ridge coordinate: x maps straight for a y ridge; for an
    # x ridge the viewer's horizontal runs against y.
    ridge_is_y = roof.ridge_axis == "y"
    span = footprint.width if ridge_is_y else footprint.depth

    def h(value: float) -> float:
        return value if ridge_is_y else span - value

    ridge_z = wall_height + (span / 2) * rise
    eave_z = wall_height - overhang * rise

    # Grade line and cut exterior walls.
    msp.add_line(
        (-overhang - 3, 0), (span + overhang + 3, 0), dxfattribs={"layer": "A-ELEV"}
    )
    for band_lo in (0.0, span - thickness):
        _add_rectangle(msp, "A-WALL", band_lo, 0, thickness, wall_height)

    # Interior walls crossed by the cut plane.
    crossing_axis = "y" if ridge_is_y else "x"
    for wall in project.interior_walls:
        if wall.axis != crossing_axis or not wall.from_ <= section.at <= wall.to:
            continue
        half = wall.thickness / 2
        lo = min(h(wall.offset - half), h(wall.offset + half))
        _add_rectangle(msp, "A-WALL-INTR", lo, 0, wall.thickness, wall_height)

    # Ceiling line at the plate, then the roof profile up to the ridge.
    msp.add_line((0, wall_height), (span, wall_height), dxfattribs={"layer": "A-ROOF"})
    apex = (span / 2, ridge_z)
    msp.add_line((-overhang, eave_z), apex, dxfattribs={"layer": "A-ROOF"})
    msp.add_line(apex, (span + overhang, eave_z), dxfattribs={"layer": "A-ROOF"})

    _add_label(
        msp, "A-ANNO-TEXT",
        f"SECTION {section.name}-{section.name}", (span / 2, -2.5),
    )
    _add_dim(
        msp, "A-ANNO-DIMS", (0, 0), (0, wall_height),
        angle=90, base=(-overhang - 1.75, 0),
    )
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
