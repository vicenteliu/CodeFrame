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
ROOM_TEXT_HEIGHT = 0.5625  # room names; reads as 9/64" at 1/4" = 1'-0"
TITLE_TEXT_HEIGHT = 0.75  # view titles; reads as 3/16" at 1/4" = 1'-0"
_TEXT_ASPECT = 0.8  # approximate char width / height of the default font

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

FOUNDATION_LAYERS = {
    "S-FNDN": {"color": 7, "lineweight": 35},
    "S-FNDN-FTNG": {"color": 8, "lineweight": 25, "linetype": "DASHED"},
    "A-ANNO-TEXT": {"color": 7, "lineweight": 18},
    "A-ANNO-DIMS": {"color": 3, "lineweight": 13},
}

FRAMING_LAYERS = {
    "S-FRAM": {"color": 7, "lineweight": 35},
    "S-FRAM-RAFT": {"color": 8, "lineweight": 18},
    "S-FRAM-RIDG": {"color": 7, "lineweight": 50},
    "A-ANNO-TEXT": {"color": 7, "lineweight": 18},
    "A-ANNO-DIMS": {"color": 3, "lineweight": 13},
}


def format_feet_inches(feet: float) -> str:
    """Format decimal feet as a feet-inches dimension string (6.67 -> 6'-8")."""

    total_inches = round(feet * 12)
    whole_feet, inches = divmod(total_inches, 12)
    return f"{whole_feet}'-{inches}\""


def _format_dim_text(feet: float) -> str:
    """Feet-inches to the nearest 1/16" for dimension text (5.8125 ->
    5'-9 3/4"). Dimensions carry exact geometry, so unlike the schedule
    labels they keep the fractional inch."""

    sixteenths = round(feet * 12 * 16)
    whole_inches, numerator = divmod(sixteenths, 16)
    whole_feet, inches = divmod(whole_inches, 12)
    if numerator:
        divisor = math.gcd(numerator, 16)
        fraction = f" {numerator // divisor}/{16 // divisor}"
    else:
        fraction = ""
    return f"{whole_feet}'-{inches}{fraction}\""


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


def _add_label(msp, layer: str, text: str, at: tuple[float, float], height: float = TEXT_HEIGHT):
    msp.add_text(
        text, dxfattribs={"layer": layer, "height": height}
    ).set_placement(at, align=TextEntityAlignment.MIDDLE_CENTER)


def _add_underlined_text(
    msp, layer: str, text: str, at: tuple[float, float], height: float
) -> None:
    """Centered text with an underline sized from the font aspect ratio."""

    msp.add_text(
        text, dxfattribs={"layer": layer, "height": height}
    ).set_placement(at, align=TextEntityAlignment.MIDDLE_CENTER)
    half = len(text) * height * _TEXT_ASPECT / 2
    y = at[1] - 0.7 * height
    msp.add_line((at[0] - half, y), (at[0] + half, y), dxfattribs={"layer": layer})


def _add_view_title(
    msp, layer: str, title: str, at: tuple[float, float],
    scale_label: str | None = None,
) -> None:
    """Underlined view title with the print scale written beneath it. The
    scale is only known at sheet-composition time; standalone DXF output
    (model space, no paper scale) omits the line."""

    _add_underlined_text(msp, layer, title, at, TITLE_TEXT_HEIGHT)
    if scale_label is not None:
        _add_label(msp, layer, f"SCALE: {scale_label}", (at[0], at[1] - 1.5))


def _add_leader(
    msp, layer: str, text: str,
    tail: tuple[float, float], target: tuple[float, float],
    *, height: float = TEXT_HEIGHT, arrow: float = 0.6,
) -> None:
    """Label with a leader arrow: the text sits at the tail, on the side
    away from the target, and the open arrowhead lands on the target."""

    dx, dy = target[0] - tail[0], target[1] - tail[1]
    msp.add_line(tail, target, dxfattribs={"layer": layer})
    back = math.atan2(-dy, -dx)
    for wing in (math.radians(20), -math.radians(20)):
        msp.add_line(
            target,
            (
                target[0] + arrow * math.cos(back + wing),
                target[1] + arrow * math.sin(back + wing),
            ),
            dxfattribs={"layer": layer},
        )
    gap = 0.8 * height
    if abs(dx) >= abs(dy):
        if dx >= 0:
            at, align = (tail[0] - gap, tail[1]), TextEntityAlignment.MIDDLE_RIGHT
        else:
            at, align = (tail[0] + gap, tail[1]), TextEntityAlignment.MIDDLE_LEFT
    elif dy >= 0:
        at, align = (tail[0], tail[1] - gap), TextEntityAlignment.TOP_CENTER
    else:
        at, align = (tail[0], tail[1] + gap), TextEntityAlignment.BOTTOM_CENTER
    msp.add_text(
        text, dxfattribs={"layer": layer, "height": height}
    ).set_placement(at, align=align)


def _add_solid_hatch(msp, layer: str, corners: list[tuple[float, float]]) -> None:
    """Solid-fill poché for cut walls (drafting convention: walls read as
    filled bands, lines stay for CAD editing)."""

    hatch = msp.add_hatch(dxfattribs={"layer": layer})
    hatch.paths.add_polyline_path(corners, is_closed=True)


def section_sheet_number(index: int) -> str:
    """Sheet number the index-th section lands on in the PDF set; the
    floor plan's section bubbles reference it (single source of truth
    shared with codeframe.sheets)."""

    return f"A6.{index}"


def _add_dim(msp, layer: str, p1: tuple[float, float], p2: tuple[float, float], *, angle: float, base: tuple[float, float]):
    """Linear dimension between p1 and p2; `base` fixes the dimension line.
    Text is overridden with the feet-inches convention (8'-6", not 8.5')."""

    radians = math.radians(angle)
    direction = (math.cos(radians), math.sin(radians))
    measurement = abs(
        (p2[0] - p1[0]) * direction[0] + (p2[1] - p1[1]) * direction[1]
    )
    dim = msp.add_linear_dim(
        base=base,
        p1=p1,
        p2=p2,
        angle=angle,
        text=_format_dim_text(measurement),
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


def build_site_plan(
    project: ProjectConfig, scale_label: str | None = None
) -> Drawing:
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
        _draw_north_arrow(
            msp, "C-ANNO-TEXT", project.site.north_rotation,
            (lot.width + 6.0, lot.depth - 5.0),
        )
    _draw_scale_bar(msp)
    _add_view_title(msp, "C-ANNO-TEXT", "SITE PLAN", (lot.width / 2, -10.0), scale_label)

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


def _draw_north_arrow(
    msp, layer: str, north_rotation: float, center: tuple[float, float]
) -> None:
    """North arrow at `center`: circle, shaft, arrowhead, N label."""

    radians = math.radians(north_rotation)
    direction = (-math.sin(radians), math.cos(radians))
    radius = 2.0

    def along(scale: float) -> tuple[float, float]:
        return (center[0] + direction[0] * scale, center[1] + direction[1] * scale)

    msp.add_circle(center=center, radius=radius, dxfattribs={"layer": layer})
    tip = along(radius)
    msp.add_line(along(-radius), tip, dxfattribs={"layer": layer})
    for wing in (140, -140):
        wing_radians = math.radians(north_rotation + wing)
        wing_end = (
            tip[0] - math.sin(wing_radians) * 0.8,
            tip[1] + math.cos(wing_radians) * 0.8,
        )
        msp.add_line(tip, wing_end, dxfattribs={"layer": layer})
    _add_label(msp, layer, "N", along(radius + 1.2))


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


def _draw_section_bubble(
    msp, name: str, sheet: str,
    center: tuple[float, float], direction: tuple[float, float],
) -> None:
    """Split section bubble: view letter over destination sheet number,
    plus a filled triangle pointing the view direction."""

    radius = 1.0
    cx, cy = center
    msp.add_circle(center=center, radius=radius, dxfattribs={"layer": "A-ANNO-SECT"})
    msp.add_line(
        (cx - radius, cy), (cx + radius, cy), dxfattribs={"layer": "A-ANNO-SECT"}
    )
    for text, dy in ((name, 0.45), (sheet, -0.45)):
        msp.add_text(
            text, dxfattribs={"layer": "A-ANNO-SECT", "height": TEXT_HEIGHT},
        ).set_placement((cx, cy + dy), align=TextEntityAlignment.MIDDLE_CENTER)
    ux, uy = direction
    px, py = -uy, ux
    apex = (cx + ux * (radius + 0.8), cy + uy * (radius + 0.8))
    base_1 = (cx + ux * 0.5 + px * 0.7, cy + uy * 0.5 + py * 0.7)
    base_2 = (cx + ux * 0.5 - px * 0.7, cy + uy * 0.5 - py * 0.7)
    msp.add_solid([base_1, base_2, apex], dxfattribs={"layer": "A-ANNO-SECT"})


def write_floor_plan(project: ProjectConfig, path: Path) -> None:
    """Write the floor plan DXF: walls, openings, room labels, overall dims."""

    _save(build_floor_plan(project), path)


def build_floor_plan(
    project: ProjectConfig, scale_label: str | None = None
) -> Drawing:
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

        # Poché between the faces; front/rear own the corner squares so the
        # side walls fill between the inner corners without doubling up.
        if wall_name in ("front", "rear"):
            hatch_span = (0.0, frame.length)
        else:
            hatch_span = (thickness, frame.length - thickness)
        for piece_start, piece_end in subtract_intervals(hatch_span, cuts):
            _add_solid_hatch(msp, "A-WALL", [
                frame.point(piece_start, 0), frame.point(piece_end, 0),
                frame.point(piece_end, thickness), frame.point(piece_start, thickness),
            ])

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
        for piece_lo, piece_hi in subtract_intervals((lo, hi), door_cuts):
            if wall.axis == "x":
                corners = [
                    (piece_lo, wall.offset - half), (piece_hi, wall.offset - half),
                    (piece_hi, wall.offset + half), (piece_lo, wall.offset + half),
                ]
            else:
                corners = [
                    (wall.offset - half, piece_lo), (wall.offset - half, piece_hi),
                    (wall.offset + half, piece_hi), (wall.offset + half, piece_lo),
                ]
            _add_solid_hatch(msp, "A-WALL-INTR", corners)
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

    # Room names read a tier above the annotation text: larger, underlined,
    # uppercase, with the stated area beneath.
    for room in project.rooms:
        _add_underlined_text(
            msp, "A-ANNO-TEXT", room.name.upper(),
            (room.label_at.x, room.label_at.y), ROOM_TEXT_HEIGHT,
        )
        if room.area is not None:
            _add_label(
                msp, "A-ANNO-TEXT", f"{room.area:g} SF",
                (room.label_at.x, room.label_at.y - 1.4),
            )

    for fixture in project.fixtures:
        _draw_fixture(msp, fixture)

    for callout in project.callouts:
        _add_leader(
            msp, "A-ANNO-TEXT", callout.text.upper(),
            (callout.at.x, callout.at.y), (callout.target.x, callout.target.y),
        )

    for detector in project.detectors:
        at = (detector.at.x, detector.at.y)
        msp.add_circle(center=at, radius=0.75, dxfattribs={"layer": "A-FIRE"})
        msp.add_text(
            DETECTOR_LABELS[detector.type],
            dxfattribs={"layer": "A-FIRE", "height": TEXT_HEIGHT},
        ).set_placement(at, align=TextEntityAlignment.MIDDLE_CENTER)

    # Section cut lines run across the plan, bubbled at both ends. Each
    # bubble is split — view letter over destination sheet — with a filled
    # triangle pointing the view direction (toward the rising ridge-axis
    # coordinate, matching build_section).
    for index, cut in enumerate(project.sections):
        if building.roof.ridge_axis == "y":
            ends = [(-5.0, cut.at), (footprint.width + 5.0, cut.at)]
            bubbles = [(-6.2, cut.at), (footprint.width + 6.2, cut.at)]
            direction = (0.0, 1.0)
        else:
            ends = [(cut.at, -5.0), (cut.at, footprint.depth + 5.0)]
            bubbles = [(cut.at, -6.2), (cut.at, footprint.depth + 6.2)]
            direction = (1.0, 0.0)
        msp.add_line(*ends, dxfattribs={"layer": "A-ANNO-SECT"})
        for bubble in bubbles:
            _draw_section_bubble(
                msp, cut.name, section_sheet_number(index), bubble, direction
            )

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

    # Overall dims: always on front and left, plus any other side that
    # carries an opening chain (references dimension every worked side).
    _add_dim(
        msp, "A-ANNO-DIMS", (0, 0), (footprint.width, 0),
        angle=0, base=(0, -3.75),
    )
    _add_dim(
        msp, "A-ANNO-DIMS", (0, 0), (0, footprint.depth),
        angle=90, base=(-3.75, 0),
    )
    walls_with_openings = {opening.wall for opening in project.openings}
    if "rear" in walls_with_openings:
        _add_dim(
            msp, "A-ANNO-DIMS", (0, footprint.depth), (footprint.width, footprint.depth),
            angle=0, base=(0, footprint.depth + 3.75),
        )
    if "right" in walls_with_openings:
        _add_dim(
            msp, "A-ANNO-DIMS", (footprint.width, 0), (footprint.width, footprint.depth),
            angle=90, base=(footprint.width + 3.75, 0),
        )

    if project.site.north_rotation is not None:
        _draw_north_arrow(
            msp, "A-ANNO-TEXT", project.site.north_rotation,
            (footprint.width + 7.0, footprint.depth + 6.0),
        )
    # An x-ridge section runs vertically and bubbles below the plan; drop
    # the title clear of it.
    if project.sections and building.roof.ridge_axis == "x":
        title_y = -9.0
    else:
        title_y = -6.0
    _add_view_title(
        msp, "A-ANNO-TEXT", "FLOOR PLAN", (footprint.width / 2, title_y), scale_label
    )

    return doc


def _require_gable(roof: Roof) -> None:
    if roof.type != "gable":
        raise UnsupportedRoofError(
            f"roof type '{roof.type}' is not supported by the drawing engine "
            "yet; v1 draws gable roofs only"
        )


def _add_slope_marker(
    msp, slope: str, eave: tuple[float, float], apex: tuple[float, float]
) -> None:
    """Roof pitch symbol riding the left roof slope: a right triangle with
    the horizontal run labeled 12 and the vertical leg labeled with the rise."""

    rise = parse_slope(slope)
    run = 2.0
    x0 = (eave[0] + apex[0]) / 2 - run / 2
    p0 = (x0, eave[1] + (x0 - eave[0]) * rise + 1.0)
    p1 = (p0[0] + run, p0[1])
    p2 = (p1[0], p1[1] + run * rise)
    for a, b in ((p0, p1), (p1, p2), (p2, p0)):
        msp.add_line(a, b, dxfattribs={"layer": "A-ANNO-TEXT"})
    _add_label(msp, "A-ANNO-TEXT", "12", (p0[0] + run / 2, p0[1] - 0.55))
    _add_label(
        msp, "A-ANNO-TEXT", slope.split(":")[0],
        (p1[0] + 0.55, (p1[1] + p2[1]) / 2),
    )


def write_elevation(project: ProjectConfig, wall: str, path: Path) -> None:
    """Write one elevation DXF, drawn as seen from outside `wall`."""

    _save(build_elevation(project, wall), path)


def build_elevation(
    project: ProjectConfig, wall: str, scale_label: str | None = None
) -> Drawing:
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
        _add_slope_marker(msp, roof.slope, (-overhang, eave_z), apex)
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

    _add_view_title(
        msp, "A-ANNO-TEXT", f"{wall.upper()} ELEVATION", (length / 2, -2.5),
        scale_label,
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


def write_foundation_plan(project: ProjectConfig, path: Path) -> None:
    """Write the slab-on-grade foundation plan DXF (sheet S1)."""

    _save(build_foundation_plan(project), path)


def build_foundation_plan(
    project: ProjectConfig, scale_label: str | None = None
) -> Drawing:
    building = project.building
    foundation = building.foundation
    assert foundation is not None, "caller checks building.foundation"

    doc = _new_document(FOUNDATION_LAYERS)
    msp = doc.modelspace()

    footprint = building.footprint
    width, depth = footprint.width, footprint.depth
    thickness = building.exterior_wall_thickness
    half_footing = foundation.footing_width / 2

    # Building outline at the exterior face; continuous perimeter footing
    # centered under the walls, hidden-line convention.
    _add_rectangle(msp, "S-FNDN", 0, 0, width, depth)
    outer = thickness / 2 - half_footing  # negative: projects past the face
    inner = thickness / 2 + half_footing
    _add_rectangle(
        msp, "S-FNDN-FTNG", outer, outer, width - 2 * outer, depth - 2 * outer
    )
    _add_rectangle(
        msp, "S-FNDN-FTNG", inner, inner, width - 2 * inner, depth - 2 * inner
    )

    # Interior bearing walls get a footing band along their clipped extent.
    for wall in project.interior_walls:
        if not wall.bearing:
            continue
        along = width if wall.axis == "x" else depth
        lo = max(wall.from_, thickness)
        hi = min(wall.to, along - thickness)
        if hi <= lo:
            continue
        if wall.axis == "x":
            _add_rectangle(
                msp, "S-FNDN-FTNG",
                lo, wall.offset - half_footing, hi - lo, foundation.footing_width,
            )
        else:
            _add_rectangle(
                msp, "S-FNDN-FTNG",
                wall.offset - half_footing, lo, foundation.footing_width, hi - lo,
            )
        _add_label(
            msp, "A-ANNO-TEXT", "BEARING WALL FOOTING",
            ((lo + hi) / 2, wall.offset + 1.2) if wall.axis == "x"
            else (wall.offset + 1.2, (lo + hi) / 2),
        )

    # Hold-downs: solid triangle symbol plus the stated label.
    for hold_down in foundation.hold_downs:
        x, y = hold_down.at.x, hold_down.at.y
        msp.add_lwpolyline(
            [(x, y + 0.5), (x - 0.45, y - 0.35), (x + 0.45, y - 0.35)],
            close=True, dxfattribs={"layer": "S-FNDN"},
        )
        _add_label(msp, "A-ANNO-TEXT", hold_down.label, (x, y + 1.3))

    _add_dim(
        msp, "A-ANNO-DIMS", (0, 0), (width, 0), angle=0, base=(0, -3),
    )
    _add_dim(
        msp, "A-ANNO-DIMS", (0, 0), (0, depth), angle=90, base=(-3, 0),
    )
    _add_view_title(msp, "A-ANNO-TEXT", "FOUNDATION PLAN", (width / 2, -5.5), scale_label)

    # Notes block beside the plan.
    notes = [
        "CONCRETE: MIN 2,500 PSI AT 28 DAYS (CRC R402.2).",
        f"CONTINUOUS FOOTING: {format_feet_inches(foundation.footing_width)} WIDE "
        f"x {format_feet_inches(foundation.footing_depth)} DEEP MIN, BOTTOM 12 IN",
        "MIN BELOW UNDISTURBED GRADE (CRC R403.1.4). REINF: (1) #4 TOP,",
        "(1) #4 BOTTOM (CRC R403.1.3, SDC D0-D2).",
        f"SLAB: {foundation.slab_thickness_inches:g} IN CONCRETE SLAB (CRC R506.1) "
        f"OVER {foundation.vapor_retarder_mil}-MIL VAPOR RETARDER",
        "(ASTM E1745 CLASS A, CRC R506.2.3 AS LOCALLY AMENDED) OVER 4 IN BASE.",
        "ANCHOR BOLTS: 1/2 IN DIA AT 6'-0\" O.C. MAX, 7 IN MIN EMBEDMENT, MIN 2",
        "PER PLATE SECTION, ONE WITHIN 12 IN OF EACH PLATE END (CRC R403.1.6);",
        "3x3x0.229 IN PLATE WASHERS AT BRACED WALL LINES (CRC R602.11.1).",
        "HOLD-DOWNS PER PLAN; SIZE, MODEL, AND EMBEDMENT BY DRAFTER, KEYED",
        "TO THE BRACED WALL SCHEDULE.",
        "SOIL: 1,500 PSF ASSUMED BEARING; VERIFY. SOILS REPORT WHERE REQUIRED.",
        "PRELIMINARY SKELETON: A QUALIFIED PROFESSIONAL MUST VERIFY ALL",
        "FOUNDATION SIZES, REINFORCING, AND HARDWARE BEFORE SUBMITTAL.",
    ]
    note_x = width + 6.0
    cursor = depth - 2.0
    _add_note_line(msp, "FOUNDATION NOTES", (note_x, cursor))
    cursor -= 1.6
    for line in notes:
        _add_note_line(msp, line, (note_x, cursor))
        cursor -= 1.2

    return doc


def write_roof_framing_plan(project: ProjectConfig, path: Path) -> None:
    """Write the roof framing plan DXF (sheet S2)."""

    _save(build_roof_framing_plan(project), path)


def _framing_callout(framing) -> str:
    """Member callout text ("2x8 DF #2 RAFTERS @ 24\" O.C.")."""

    spacing_inches = framing.spacing * 12
    member_name = "RAFTERS" if framing.member == "rafter" else "TRUSSES"
    grade = f" {framing.species_grade}" if framing.species_grade else ""
    return f"{framing.size}{grade} {member_name} @ {spacing_inches:g}\" O.C."


def _framing_stations(length: float, spacing: float) -> list[float]:
    """Member stations at `spacing` o.c. plus a closing member at the end."""

    stations = []
    station = 0.0
    while station < length - 1e-9:
        stations.append(station)
        station += spacing
    stations.append(length)
    return stations


def build_roof_framing_plan(
    project: ProjectConfig, scale_label: str | None = None
) -> Drawing:
    building = project.building
    roof = building.roof
    framing = roof.framing
    assert framing is not None, "caller checks roof.framing"
    _require_gable(roof)

    doc = _new_document(FRAMING_LAYERS)
    msp = doc.modelspace()

    footprint = building.footprint
    width, depth = footprint.width, footprint.depth
    overhang = roof.overhang
    ridge_is_y = roof.ridge_axis == "y"
    ridge_run = depth if ridge_is_y else width

    # Supporting walls, the ridge member, and the member layout. Members
    # span across the ridge, laid out along it at the stated spacing.
    _add_rectangle(msp, "S-FRAM", 0, 0, width, depth)
    if ridge_is_y:
        msp.add_line(
            (width / 2, -overhang), (width / 2, depth + overhang),
            dxfattribs={"layer": "S-FRAM-RIDG"},
        )
        for station in _framing_stations(ridge_run, framing.spacing):
            msp.add_line(
                (-overhang, station), (width + overhang, station),
                dxfattribs={"layer": "S-FRAM-RAFT"},
            )
    else:
        msp.add_line(
            (-overhang, depth / 2), (width + overhang, depth / 2),
            dxfattribs={"layer": "S-FRAM-RIDG"},
        )
        for station in _framing_stations(ridge_run, framing.spacing):
            msp.add_line(
                (station, -overhang), (station, depth + overhang),
                dxfattribs={"layer": "S-FRAM-RAFT"},
            )

    # Member callout with a span arrow perpendicular to the ridge.
    callout = _framing_callout(framing)
    if ridge_is_y:
        arrow = ((width / 2 + 2, depth / 2), (width - 2, depth / 2))
        label_at = (3 * width / 4, depth / 2 + 1.5)
    else:
        arrow = ((width / 2, depth / 2 + 2), (width / 2, depth - 2))
        label_at = (width / 2, 3 * depth / 4 + 1.5)
    msp.add_line(*arrow, dxfattribs={"layer": "A-ANNO-TEXT"})
    for end, sign in ((arrow[0], 1), (arrow[1], -1)):
        axis = 0 if ridge_is_y else 1
        for wing in (0.5, -0.5):
            head = list(end)
            head[axis] += sign * 1.0
            head[1 - axis] += wing
            msp.add_line(end, tuple(head), dxfattribs={"layer": "A-ANNO-TEXT"})
    _add_label(msp, "A-ANNO-TEXT", callout, label_at)
    if framing.ridge:
        ridge_label_at = (
            (width / 2, depth + overhang + 1.5) if ridge_is_y
            else (width + overhang + 4, depth / 2)
        )
        _add_label(msp, "A-ANNO-TEXT", f"RIDGE: {framing.ridge}", ridge_label_at)

    _add_dim(msp, "A-ANNO-DIMS", (0, 0), (width, 0), angle=0, base=(0, -3))
    _add_dim(msp, "A-ANNO-DIMS", (0, 0), (0, depth), angle=90, base=(-3, 0))
    _add_view_title(msp, "A-ANNO-TEXT", "ROOF FRAMING PLAN", (width / 2, -5.5), scale_label)

    notes = [
        "MEMBER SPANS: VERIFY PER CRC TABLES R802.4.1(1)-(9).",
        "BLOCKING: SOLID BLOCK ALL MEMBERS AT EXTERIOR WALLS (CRC R802.8).",
        "SHEATHING: NAILING 8d @ 6 IN EDGES / 12 IN FIELD PER CRC TABLE",
        "R602.3(1); PANEL EDGES NAILED TO BLOCKING.",
        "UPLIFT CONNECTORS WHERE UPLIFT EXCEEDS 200 LB PER MEMBER",
        "(CRC TABLE R802.11).",
        "ATTIC VENTILATION: 1/150 (OR 1/300 PER R806.2 EXCEPTIONS).",
        "HEADERS PER CRC TABLE R602.7 UNLESS NOTED.",
    ]
    if framing.member == "rafter":
        notes += [
            "RAFTER TIES MIN 2x4 @ 48 IN O.C. MAX (CRC R802.5.2.2) OR RIDGE",
            "BEAM WITH SUPPORTS; COLLAR TIES PER CRC R802.4.6.",
        ]
    else:
        notes += [
            "TRUSS PACKAGE IS A DEFERRED SUBMITTAL: CA-ENGINEER-STAMPED",
            "TRUSS CALCS AND LAYOUT REQUIRED (CRC R802.10.1).",
        ]
    notes += [
        "PRELIMINARY SKELETON: A QUALIFIED PROFESSIONAL MUST VERIFY ALL",
        "MEMBER SIZES, SPANS, AND CONNECTIONS BEFORE SUBMITTAL.",
    ]
    note_x = width + overhang + 6.0
    cursor = depth - 2.0
    _add_note_line(msp, "FRAMING NOTES", (note_x, cursor))
    cursor -= 1.6
    for line in notes:
        _add_note_line(msp, line, (note_x, cursor))
        cursor -= 1.2

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
    "A-ANNO-TABL": {"color": 7, "lineweight": 25},
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

    # Area summary: stated room areas only (rooms are label points; the
    # core never computes areas). Plan checkers read it against ADU limits.
    areas = [
        (room.name.upper(), room.area)
        for room in project.rooms
        if room.area is not None
    ]
    if areas:
        rows = [(name, f"{area:g}") for name, area in areas]
        rows.append(("TOTAL", f"{sum(area for _name, area in areas):g}"))
        _draw_table(
            msp, "AREA SUMMARY", ["ROOM", "AREA (SF)"], rows,
            (1.0, cursor - 2.5), col_widths=[14.0, 7.0],
        )

    return doc


STRUCTURAL_NOTES: list[list[str]] = [
    ["DESIGN BASIS (VERIFY ALL FOR THE PROJECT SITE): ROOF LL 20 PSF,",
     "ROOF DL 15 PSF, WIND 110 MPH EXPOSURE C, SEISMIC DESIGN CATEGORY D,",
     "SOIL BEARING 1,500 PSF ASSUMED."],
    ["THIS PROJECT IS DESIGNED UNDER THE CONVENTIONAL LIGHT-FRAME",
     "CONSTRUCTION PROVISIONS OF CRC R301.1.3 (OR THE LOCAL PRESCRIPTIVE",
     "PROGRAM, E.G. LA COUNTY WFPP). ENGINEERING IS REQUIRED WHERE THE",
     "DESIGN DEVIATES FROM THOSE PROVISIONS."],
    ["BRACED WALL LINES: SPACING 25 FT MAX; PANEL LOCATIONS, LENGTHS,",
     "AND SCHEDULE BY DRAFTER PER CRC R602.10, KEYED TO THE HOLD-DOWNS",
     "ON THE FOUNDATION PLAN."],
    ["WOOD: DF-L, MEMBER GRADES PER PLAN CALLOUTS (MIN NO. 2 UNLESS",
     "NOTED). SILL PLATES IN CONTACT WITH CONCRETE: PRESERVATIVE-TREATED",
     "(CRC R317)."],
    ["FASTENING PER CRC TABLE R602.3(1) UNLESS NOTED."],
    ["CONCRETE: MIN 2,500 PSI AT 28 DAYS (CRC R402.2)."],
    ["MANUFACTURED TRUSSES (WHERE USED): STAMPED TRUSS PACKAGE IS A",
     "DEFERRED SUBMITTAL (CRC R802.10.1)."],
    ["PRELIMINARY SKELETON: A QUALIFIED PROFESSIONAL MUST VERIFY THE",
     "DESIGN BASIS AND ALL STRUCTURAL CONTENT BEFORE SUBMITTAL."],
]


def write_structural_notes(project: ProjectConfig, path: Path) -> None:
    """Write the structural general notes DXF (sheet S0)."""

    _save(build_structural_notes(project), path)


def build_structural_notes(project: ProjectConfig) -> Drawing:
    doc = _new_document(NOTES_LAYERS)
    msp = doc.modelspace()

    cursor = 0.0
    _add_note_line(msp, "STRUCTURAL GENERAL NOTES", (0.0, cursor))
    cursor -= 1.6
    for number, note_lines in enumerate(STRUCTURAL_NOTES, start=1):
        _add_note_line(msp, f"{number}. {note_lines[0]}", (1.0, cursor))
        cursor -= _NOTE_LINE_SPACING
        for continuation in note_lines[1:]:
            _add_note_line(msp, continuation, (2.0, cursor))
            cursor -= _NOTE_LINE_SPACING
    return doc


_COMPLIANCE_COLS = [10.0, 6.0, 14.0, 14.0, 5.0]


def write_code_compliance(project: ProjectConfig, path: Path) -> None:
    """Write the code compliance table DXF."""

    _save(build_code_compliance(project), path)


def _compliance_rows(project: ProjectConfig) -> list[tuple]:
    """Requirement-vs-provided rows from stated config values. Arithmetic
    only — anything CodeFrame cannot compute is marked BY DRAFTER."""

    building = project.building
    footprint = building.footprint
    rows: list[tuple] = []

    height_ok = building.wall_height >= 7.0
    rows.append((
        "CEILING HEIGHT", "R305.1", "7'-0\" MIN HABITABLE",
        format_feet_inches(building.wall_height),
        "OK" if height_ok else "CHECK",
    ))

    for opening in project.openings:
        if opening.type != "window" or not opening.egress:
            continue
        sill = opening.sill or 0.0
        rows.append((
            f"EGRESS ({opening.wall.upper()} WALL)", "R310",
            "5.7 SF NET, 20\"W x 24\"H, SILL 44\" MAX",
            f"{opening.width * opening.height:.1f} SF GROSS, "
            f"{format_feet_inches(opening.width)} x "
            f"{format_feet_inches(opening.height)}, SILL "
            f"{format_feet_inches(sill)}",
            "OK*",
        ))

    # R303 light/vent: total glazing is arithmetic on stated openings; the
    # per-room split (and operable fraction) stays the Drafter's.
    total_glazing = sum(
        o.width * o.height for o in project.openings if o.type == "window"
    )
    rows.append((
        "LIGHT (GLAZING)", "R303.1", "8% OF FLOOR AREA PER HABITABLE ROOM",
        f"{total_glazing:g} SF TOTAL GLAZING SHOWN", "BY DRAFTER",
    ))
    rows.append((
        "VENTILATION", "R303.1", "4% OPENABLE PER HABITABLE ROOM",
        "OPENABLE AREA PER WINDOW TYPE", "BY DRAFTER",
    ))

    smoke = sum(1 for d in project.detectors if d.type in ("smoke", "combo"))
    co = sum(1 for d in project.detectors if d.type in ("co", "combo"))
    rows.append((
        "SMOKE ALARMS", "R314", "EACH SLEEPING ROOM, OUTSIDE, EACH STORY",
        f"{smoke} SHOWN ON FLOOR PLAN", "BY DRAFTER",
    ))
    rows.append((
        "CO ALARMS", "R315", "OUTSIDE SLEEPING AREAS, EACH STORY",
        f"{co} SHOWN ON FLOOR PLAN", "BY DRAFTER",
    ))

    attic_area = footprint.width * footprint.depth
    rows.append((
        "ATTIC VENTILATION", "R806.2", "1/150 OF ATTIC AREA",
        f"{attic_area / 150:.1f} SF NET FREE REQUIRED", "BY DRAFTER",
    ))
    return rows


def build_code_compliance(project: ProjectConfig) -> Drawing:
    doc = _new_document(SCHEDULE_LAYERS)
    msp = doc.modelspace()

    bottom = _draw_table(
        msp, "CODE COMPLIANCE SUMMARY",
        ["ITEM", "CRC", "REQUIRED", "PROVIDED", "STATUS"],
        _compliance_rows(project), (0.0, 0.0), col_widths=_COMPLIANCE_COLS,
    )
    _add_note_line(
        msp,
        "* NET CLEAR OPENING DEPENDS ON WINDOW TYPE - VERIFY. THIS TABLE IS",
        (0.0, bottom - 1.5),
    )
    _add_note_line(
        msp,
        "ARITHMETIC ON STATED VALUES, NOT A CODE COMPLIANCE APPROVAL.",
        (0.0, bottom - 1.5 - _NOTE_LINE_SPACING),
    )
    return doc


def write_schedules(project: ProjectConfig, path: Path) -> None:
    """Write the door and window schedules DXF."""

    _save(build_schedules(project), path)


_SCHEDULE_COLS = [3.0, 4.5, 4.5, 5.5, 3.0, 5.0]
_WINDOW_SCHEDULE_COLS = [3.0, 4.5, 4.5, 5.5, 4.5, 3.0, 5.0]
_SCHEDULE_ROW_H = 1.5


def _draw_table(
    msp, title: str, headers: list[str], rows: list[tuple], top_left,
    col_widths: list[float] | None = None,
) -> float:
    """Draw one table; returns the y of its bottom edge."""

    widths = col_widths if col_widths is not None else _SCHEDULE_COLS
    x0, y0 = top_left
    total_w = sum(widths)
    _add_label(msp, "A-ANNO-TEXT", title, (x0 + total_w / 2, y0 + 1.0))

    n_grid_rows = len(rows) + 1  # header + data
    bottom = y0 - n_grid_rows * _SCHEDULE_ROW_H
    for i in range(n_grid_rows + 1):
        y = y0 - i * _SCHEDULE_ROW_H
        msp.add_line((x0, y), (x0 + total_w, y), dxfattribs={"layer": "A-ANNO-TABL"})
    x = x0
    for width in [0.0, *widths]:
        x += width
        msp.add_line((x, y0), (x, bottom), dxfattribs={"layer": "A-ANNO-TABL"})

    for row_index, cells in enumerate([tuple(headers), *rows]):
        y_mid = y0 - (row_index + 0.5) * _SCHEDULE_ROW_H
        x = x0
        for width, cell in zip(widths, cells):
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
    # Glazed area per mark: plan checkers read it against CRC R303
    # light/vent minimums, so the window schedule carries it.
    window_cells = [
        (mark, format_feet_inches(w), format_feet_inches(h), f"SILL {sill}",
         f"{w * h:g} SF", count, "EGRESS" if egress else "")
        for mark, w, h, sill, count, egress in window_rows
    ]

    bottom = _draw_table(
        msp, "DOOR SCHEDULE",
        ["MARK", "WIDTH", "HEIGHT", "TYPE", "QTY", "REMARKS"], door_cells, (0.0, 0.0),
    )
    _draw_table(
        msp, "WINDOW SCHEDULE",
        ["MARK", "WIDTH", "HEIGHT", "SILL", "AREA", "QTY", "REMARKS"], window_cells,
        (0.0, bottom - 3.5), col_widths=_WINDOW_SCHEDULE_COLS,
    )
    return doc


def write_section(project: ProjectConfig, section: SectionCut, path: Path) -> None:
    """Write one transverse building section DXF."""

    _save(build_section(project, section), path)


def build_section(
    project: ProjectConfig, section: SectionCut, scale_label: str | None = None
) -> Drawing:
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
        _add_solid_hatch(msp, "A-WALL", [
            (band_lo, 0), (band_lo + thickness, 0),
            (band_lo + thickness, wall_height), (band_lo, wall_height),
        ])

    # Interior walls crossed by the cut plane.
    crossing_axis = "y" if ridge_is_y else "x"
    for wall in project.interior_walls:
        if wall.axis != crossing_axis or not wall.from_ <= section.at <= wall.to:
            continue
        half = wall.thickness / 2
        lo = min(h(wall.offset - half), h(wall.offset + half))
        _add_rectangle(msp, "A-WALL-INTR", lo, 0, wall.thickness, wall_height)
        _add_solid_hatch(msp, "A-WALL-INTR", [
            (lo, 0), (lo + wall.thickness, 0),
            (lo + wall.thickness, wall_height), (lo, wall_height),
        ])

    # Ceiling line at the plate, then the roof profile up to the ridge.
    msp.add_line((0, wall_height), (span, wall_height), dxfattribs={"layer": "A-ROOF"})
    apex = (span / 2, ridge_z)
    msp.add_line((-overhang, eave_z), apex, dxfattribs={"layer": "A-ROOF"})
    msp.add_line(apex, (span + overhang, eave_z), dxfattribs={"layer": "A-ROOF"})
    _add_slope_marker(msp, roof.slope, (-overhang, eave_z), apex)

    _add_view_title(
        msp, "A-ANNO-TEXT",
        f"SECTION {section.name}-{section.name}", (span / 2, -2.5), scale_label,
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


def build_roof_plan(
    project: ProjectConfig, scale_label: str | None = None
) -> Drawing:
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

    _add_view_title(
        msp, "A-ANNO-TEXT", "ROOF PLAN", (width / 2, -overhang - 2.5), scale_label
    )

    return doc


# --- Typical details (sheet S3) -----------------------------------------
#
# Prescriptive connection / footing / header details drawn from stated
# config values. Geometry is representative (member depths are drawn at a
# nominal size); every structural size CodeFrame does not know is called
# out BY DRAFTER with its CRC reference. The sheet renders at a fixed
# detail scale, so detail annotation uses its own text height.

DETAIL_SCALE_LABEL = "1\" = 1'-0\""
DETAIL_TEXT_HEIGHT = 0.09375  # reads as 3/32" at 1" = 1'-0"

DETAIL_LAYERS = {
    "S-DETL": {"color": 7, "lineweight": 35},
    "S-DETL-FINE": {"color": 8, "lineweight": 18},
    "S-DETL-HIDN": {"color": 8, "lineweight": 13, "linetype": "DASHED"},
    "S-DETL-PATT": {"color": 8, "lineweight": 13},
    "A-ANNO-TEXT": {"color": 7, "lineweight": 18},
}

# Details fill these cells in order: three across the top row, two below.
_DETAIL_POSITIONS = [(0.0, 0.0), (9.0, 0.0), (18.0, 0.0), (0.0, -9.0), (9.0, -9.0)]


def _add_earth_hatch(
    msp, layer: str, x0: float, y0: float, x1: float, y1: float
) -> None:
    """Earth poché: 45-degree lines clipped to a rectangle. Drawn as plain
    lines, not a HATCH pattern fill — ezdxf's pattern renderer emits lines
    in a nondeterministic order, which breaks byte-identical PDFs."""

    step = 0.17 * math.sqrt(2)
    start = y0 - x1
    count = int((y1 - x0 - start) / step)
    for index in range(count + 1):
        c = start + index * step
        from_x = max(x0, y0 - c)
        to_x = min(x1, y1 - c)
        if to_x > from_x:
            msp.add_line(
                (from_x, from_x + c), (to_x, to_x + c), dxfattribs={"layer": layer}
            )


def _break_symbol(msp, start: tuple[float, float], end: tuple[float, float]) -> None:
    """Zigzag cut mark across a member that continues beyond the detail."""

    (x0, y0), (x1, y1) = start, end
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    px, py = -dy / length * 0.1, dx / length * 0.1
    msp.add_lwpolyline(
        [
            start,
            (x0 + dx * 0.4 + px, y0 + dy * 0.4 + py),
            (x0 + dx * 0.6 - px, y0 + dy * 0.6 - py),
            end,
        ],
        dxfattribs={"layer": "S-DETL"},
    )


def _detail_leader(msp, text: str, tail, target) -> None:
    _add_leader(
        msp, "A-ANNO-TEXT", text, tail, target,
        height=DETAIL_TEXT_HEIGHT, arrow=0.15,
    )


def _add_detail_title(msp, number: int, title: str, at: tuple[float, float]) -> None:
    """Detail marker: circled number, underlined title, detail scale."""

    x, y = at
    radius = 0.3
    height = DETAIL_TEXT_HEIGHT * 1.4
    msp.add_circle(center=(x, y), radius=radius, dxfattribs={"layer": "A-ANNO-TEXT"})
    msp.add_text(
        str(number), dxfattribs={"layer": "A-ANNO-TEXT", "height": height}
    ).set_placement((x, y), align=TextEntityAlignment.MIDDLE_CENTER)
    center_x = x + radius + 0.25 + len(title) * height * _TEXT_ASPECT / 2
    _add_underlined_text(msp, "A-ANNO-TEXT", title, (center_x, y), height)
    _add_label(
        msp, "A-ANNO-TEXT", f"SCALE: {DETAIL_SCALE_LABEL}",
        (center_x, y - 0.45), height=DETAIL_TEXT_HEIGHT,
    )


def _detail_exterior_footing(msp, thickness: float, foundation, number: int, origin) -> None:
    """Monolithic slab edge: turned-down footing, sill, anchor bolt, wall."""

    ox, oy = origin

    def P(x: float, y: float) -> tuple[float, float]:
        return (ox + x, oy + y)

    fw, fd = foundation.footing_width, foundation.footing_depth
    ts = foundation.slab_thickness_inches / 12
    x_left = thickness / 2 - fw / 2
    x_right = x_left + fw
    interior = 3.5

    # Concrete profile: slab top, turned-down edge, footing, slab underside.
    msp.add_lwpolyline(
        [
            P(interior, 0), P(x_left, 0), P(x_left, -fd),
            P(x_right, -fd), P(x_right, -ts), P(interior, -ts),
        ],
        close=True, dxfattribs={"layer": "S-DETL"},
    )
    # Grade at the exterior face with earth poché below.
    msp.add_line(P(x_left - 2.4, -0.5), P(x_left, -0.5), dxfattribs={"layer": "S-DETL"})
    _add_earth_hatch(
        msp, "S-DETL-PATT", ox + x_left - 2.4, oy - fd, ox + x_left, oy - 0.5
    )
    # Base course (solid) and vapor retarder (hidden) under the slab.
    msp.add_line(P(x_right, -ts - 0.33), P(interior, -ts - 0.33), dxfattribs={"layer": "S-DETL-FINE"})
    msp.add_line(P(x_right, -ts - 0.05), P(interior, -ts - 0.05), dxfattribs={"layer": "S-DETL-HIDN"})
    for bar_y in (-ts - 0.15, -fd + 0.15):
        msp.add_circle(center=P(thickness / 2, bar_y), radius=0.045, dxfattribs={"layer": "S-DETL-FINE"})
    # PT sill on the slab, anchor bolt with hook, stud wall broken above.
    _add_rectangle(msp, "S-DETL-FINE", ox, oy, thickness, 0.125)
    msp.add_line(P(thickness / 2, 0.125), P(thickness / 2, -0.58), dxfattribs={"layer": "S-DETL-FINE"})
    msp.add_line(P(thickness / 2, -0.58), P(thickness / 2 + 0.1, -0.58), dxfattribs={"layer": "S-DETL-FINE"})
    msp.add_line(P(0, 0.125), P(0, 2.1), dxfattribs={"layer": "S-DETL"})
    msp.add_line(P(thickness, 0.125), P(thickness, 2.1), dxfattribs={"layer": "S-DETL"})
    _break_symbol(msp, P(0, 2.1), P(thickness, 2.1))

    _detail_leader(msp, "2x STUD WALL", P(1.9, 1.7), P(thickness, 1.5))
    _detail_leader(msp, "PT SILL PLATE (R317)", P(-1.2, 1.0), P(thickness * 0.25, 0.07))
    _detail_leader(
        msp, "1/2\" DIA A.B. @ 6'-0\" O.C. MAX, 7\" EMBED (R403.1.6)",
        P(1.9, 1.1), P(thickness / 2 + 0.02, -0.2),
    )
    _detail_leader(
        msp,
        f"{foundation.slab_thickness_inches:g}\" SLAB OVER "
        f"{foundation.vapor_retarder_mil}-MIL VAPOR RETARDER OVER 4\" BASE",
        P(2.2, -1.2), P(2.0, -ts - 0.05),
    )
    _detail_leader(
        msp, "(1) #4 TOP & (1) #4 BOT (R403.1.3)",
        P(2.4, -fd - 0.6), P(thickness / 2 + 0.05, -fd + 0.15),
    )
    _add_label(
        msp, "A-ANNO-TEXT",
        f"{format_feet_inches(fw)} W x {format_feet_inches(fd)} D FOOTING",
        P(0, -fd - 1.1), height=DETAIL_TEXT_HEIGHT,
    )
    _add_detail_title(msp, number, "EXTERIOR FOOTING AT SLAB EDGE", P(-2.4, -3.2))


def _detail_interior_footing(msp, wall_thickness: float, foundation, number: int, origin) -> None:
    """Thickened slab under an interior bearing wall."""

    ox, oy = origin

    def P(x: float, y: float) -> tuple[float, float]:
        return (ox + x, oy + y)

    fw, fd = foundation.footing_width, foundation.footing_depth
    ts = foundation.slab_thickness_inches / 12
    half = wall_thickness / 2

    msp.add_lwpolyline(
        [
            P(-2.4, 0), P(2.4, 0), P(2.4, -ts), P(fw / 2, -ts),
            P(fw / 2, -fd), P(-fw / 2, -fd), P(-fw / 2, -ts), P(-2.4, -ts),
        ],
        close=True, dxfattribs={"layer": "S-DETL"},
    )
    _add_rectangle(msp, "S-DETL-FINE", ox - half, oy, wall_thickness, 0.125)
    msp.add_line(P(0, 0.125), P(0, -0.58), dxfattribs={"layer": "S-DETL-FINE"})
    msp.add_line(P(0, -0.58), P(0.1, -0.58), dxfattribs={"layer": "S-DETL-FINE"})
    msp.add_line(P(-half, 0.125), P(-half, 1.9), dxfattribs={"layer": "S-DETL"})
    msp.add_line(P(half, 0.125), P(half, 1.9), dxfattribs={"layer": "S-DETL"})
    _break_symbol(msp, P(-half, 1.9), P(half, 1.9))
    for bar_y in (-ts - 0.15, -fd + 0.15):
        msp.add_circle(center=P(0, bar_y), radius=0.045, dxfattribs={"layer": "S-DETL-FINE"})

    _detail_leader(msp, "INTERIOR BEARING WALL", P(1.8, 1.5), P(half, 1.3))
    _detail_leader(msp, "PT SILL + A.B. PER R403.1.6", P(1.8, 0.9), P(half * 0.5, 0.07))
    _detail_leader(
        msp, "(1) #4 TOP & (1) #4 BOT", P(1.9, -fd - 0.6), P(0.05, -fd + 0.15)
    )
    _add_label(
        msp, "A-ANNO-TEXT",
        f"{format_feet_inches(fw)} W x {format_feet_inches(fd)} D THICKENED SLAB",
        P(0, -fd - 1.1), height=DETAIL_TEXT_HEIGHT,
    )
    _add_detail_title(msp, number, "INTERIOR BEARING FOOTING", P(-2.4, -3.2))


def _detail_eave(msp, building, framing, number: int, origin) -> None:
    """Member-to-plate connection at the eave, overhang per config."""

    ox, oy = origin

    def P(x: float, y: float) -> tuple[float, float]:
        return (ox + x, oy + y)

    thickness = building.exterior_wall_thickness
    rise = parse_slope(building.roof.slope)
    overhang = building.roof.overhang
    depth = 0.65  # representative member depth; the callout is authoritative
    ridge_x = thickness + 2.6

    msp.add_line(P(0, -2.1), P(0, -0.25), dxfattribs={"layer": "S-DETL"})
    msp.add_line(P(thickness, -2.1), P(thickness, -0.25), dxfattribs={"layer": "S-DETL"})
    _break_symbol(msp, P(0, -2.1), P(thickness, -2.1))
    _add_rectangle(msp, "S-DETL-FINE", ox, oy - 0.25, thickness, 0.125)
    _add_rectangle(msp, "S-DETL-FINE", ox, oy - 0.125, thickness, 0.125)

    # Underside with birdsmouth (seat across the plate, plumb heel cut),
    # then the parallel top edge and the tail plumb cut at the overhang.
    msp.add_lwpolyline(
        [
            P(-overhang, -overhang * rise), P(0, 0), P(thickness, 0),
            P(thickness, thickness * rise), P(ridge_x, ridge_x * rise),
        ],
        dxfattribs={"layer": "S-DETL"},
    )
    msp.add_line(
        P(-overhang, -overhang * rise + depth), P(ridge_x, ridge_x * rise + depth),
        dxfattribs={"layer": "S-DETL"},
    )
    msp.add_line(
        P(-overhang, -overhang * rise), P(-overhang, -overhang * rise + depth),
        dxfattribs={"layer": "S-DETL"},
    )
    _break_symbol(
        msp, P(ridge_x, ridge_x * rise), P(ridge_x, ridge_x * rise + depth)
    )

    _detail_leader(
        msp, _framing_callout(framing), P(3.4, 2.4), P(2.0, 2.0 * rise + depth)
    )
    _detail_leader(msp, "SOLID BLOCKING (R802.8)", P(3.2, 0.35), P(thickness + 0.2, 0.2))
    _detail_leader(
        msp, "UPLIFT CONNECTOR (R802.11) - BY DRAFTER",
        P(3.4, -0.6), P(thickness + 0.05, -0.05),
    )
    _detail_leader(msp, "DBL 2x TOP PLATE", P(-1.1, -1.0), P(0.05, -0.19))
    _detail_leader(msp, "2x STUD WALL", P(-1.1, -1.6), P(0, -1.4))
    _add_detail_title(msp, number, "EAVE CONNECTION AT TOP PLATE", P(-2.4, -3.2))


def _detail_ridge(msp, roof, framing, number: int, origin) -> None:
    """Rafter pair on a ridge board with collar ties (rafter roofs only —
    truss connections belong to the deferred truss package)."""

    ox, oy = origin

    def P(x: float, y: float) -> tuple[float, float]:
        return (ox + x, oy + y)

    rise = parse_slope(roof.slope)
    depth = 0.65
    half = 0.0625  # half of a 1.5 in ridge board

    _add_rectangle(msp, "S-DETL", ox - half, oy - 0.9, 2 * half, 0.9)
    for side in (1, -1):
        outer = side * 2.5
        drop = rise * (2.5 - half)
        msp.add_line(P(side * half, 0), P(outer, -drop), dxfattribs={"layer": "S-DETL"})
        msp.add_line(
            P(side * half, -depth), P(outer, -drop - depth),
            dxfattribs={"layer": "S-DETL"},
        )
        msp.add_line(P(side * half, 0), P(side * half, -depth), dxfattribs={"layer": "S-DETL"})
        _break_symbol(msp, P(outer, -drop), P(outer, -drop - depth))
    _add_rectangle(msp, "S-DETL-FINE", ox - 1.6, oy - 0.92, 3.2, 0.12)

    ridge_text = framing.ridge if framing.ridge else "RIDGE BOARD - BY DRAFTER"
    _detail_leader(msp, ridge_text, P(2.4, 0.5), P(half, -0.2))
    _detail_leader(msp, _framing_callout(framing), P(2.6, -2.0), P(1.5, -1.0))
    _detail_leader(msp, "COLLAR TIES PER R802.4.6", P(2.5, -1.5), P(1.2, -0.86))
    _add_label(
        msp, "A-ANNO-TEXT", "RAFTER TIES OR CEILING JOISTS PER R802.5.2",
        P(0, -2.6), height=DETAIL_TEXT_HEIGHT,
    )
    _add_detail_title(msp, number, "RIDGE CONNECTION", P(-2.4, -3.2))


def _detail_header(msp, number: int, origin) -> None:
    """Typical opening frame: king + trimmer studs, header, cripples."""

    ox, oy = origin

    def P(x: float, y: float) -> tuple[float, float]:
        return (ox + x, oy + y)

    for side in (-1, 1):
        king_x = side * 1.5 - (0.125 if side > 0 else 0)
        trimmer_x = side * 1.375 - (0.125 if side > 0 else 0)
        _add_rectangle(msp, "S-DETL", ox + king_x, oy, 0.125, 3.0)
        _add_rectangle(msp, "S-DETL", ox + trimmer_x, oy, 0.125, 2.2)
        _break_symbol(msp, P(side * 1.5, 0), P(side * 1.25, 0))
    _add_rectangle(msp, "S-DETL", ox - 1.375, oy + 2.2, 2.75, 0.5)
    msp.add_line(P(-1.375, 2.2), P(1.375, 2.7), dxfattribs={"layer": "S-DETL-FINE"})
    msp.add_line(P(-1.375, 2.7), P(1.375, 2.2), dxfattribs={"layer": "S-DETL-FINE"})
    for cripple_x in (-0.7, 0.0, 0.7):
        _add_rectangle(msp, "S-DETL-FINE", ox + cripple_x - 0.0625, oy + 2.7, 0.125, 0.7)
    _break_symbol(msp, P(-1.5, 3.4), P(1.5, 3.4))

    _detail_leader(
        msp, "HEADER PER CRC TABLE R602.7 - SIZE BY DRAFTER",
        P(2.6, 3.0), P(1.0, 2.45),
    )
    _detail_leader(msp, "KING STUD + TRIMMER EACH SIDE", P(2.4, 1.2), P(1.31, 1.0))
    _detail_leader(msp, "CRIPPLES TO TOP PLATE", P(2.5, 3.7), P(0.72, 3.05))
    _add_label(
        msp, "A-ANNO-TEXT", "FLASH EXTERIOR OPENINGS PER R703.4",
        P(0, -0.6), height=DETAIL_TEXT_HEIGHT,
    )
    _add_detail_title(msp, number, "TYPICAL HEADER AT OPENING", P(-2.4, -3.2))


def write_details(project: ProjectConfig, path: Path) -> None:
    """Write the typical details DXF (sheet S3)."""

    _save(build_details(project), path)


def build_details(project: ProjectConfig) -> Drawing:
    building = project.building
    foundation = building.foundation
    framing = building.roof.framing

    doc = _new_document(DETAIL_LAYERS)
    msp = doc.modelspace()

    details = []
    if foundation is not None:
        details.append(
            lambda n, at: _detail_exterior_footing(
                msp, building.exterior_wall_thickness, foundation, n, at
            )
        )
        bearing = [wall for wall in project.interior_walls if wall.bearing]
        if bearing:
            details.append(
                lambda n, at, wall=bearing[0]: _detail_interior_footing(
                    msp, wall.thickness, foundation, n, at
                )
            )
    if framing is not None:
        details.append(lambda n, at: _detail_eave(msp, building, framing, n, at))
        if framing.member == "rafter":
            details.append(
                lambda n, at: _detail_ridge(msp, building.roof, framing, n, at)
            )
    details.append(lambda n, at: _detail_header(msp, n, at))

    for index, draw in enumerate(details):
        draw(index + 1, _DETAIL_POSITIONS[index])

    note_y = -13.6 if len(details) > 3 else -4.8
    msp.add_text(
        "ALL CONNECTOR MODELS, MEMBER SIZES, AND EMBEDMENTS ARE THE "
        "DRAFTER'S - PRELIMINARY SKELETON",
        dxfattribs={"layer": "A-ANNO-TEXT", "height": DETAIL_TEXT_HEIGHT * 1.2},
    ).set_placement((0.0, note_y), align=TextEntityAlignment.MIDDLE_LEFT)
    return doc
