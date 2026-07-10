#!/usr/bin/env python3
"""Advisory layout checks for a CodeFrame Project Config.

Catches the layout mistakes the Deterministic Core deliberately does not
judge (it draws exactly what the config states): doorways blocked by
fixtures, fixtures clashing with each other or poking through walls, and
sleeping rooms without a designated egress window. Warnings, not law —
exit 1 when anything needs a look.

Usage:
    python check_layout.py <project-config.json> [--render out.png]
"""

from __future__ import annotations

import sys
from pathlib import Path

from codeframe.schema import ProjectConfig, load_project_config

# Standard symbol footprints (feet), matching codeframe.dxf._draw_fixture.
FIXTURE_SIZES = {
    "toilet": (1.5, 2.33),
    "lavatory": (1.6, 1.3),
    "bathtub": (5.0, 2.5),
    "shower": (3.0, 3.0),
    "kitchen-sink": (2.75, 1.83),
    "range": (2.5, 2.17),
    "refrigerator": (3.0, 2.5),
    "washer-dryer": (4.5, 2.25),
    "water-heater": (2.0, 2.0),
}

Box = tuple[float, float, float, float]  # xmin, ymin, xmax, ymax


def fixture_box(fixture) -> Box:
    if fixture.type == "counter":
        assert fixture.size is not None  # schema validation guarantees it
        w, d = fixture.size.width, fixture.size.depth
    else:
        w, d = FIXTURE_SIZES[fixture.type]
    if fixture.rotation in (90, 270):
        w, d = d, w
    x, y = fixture.at.x, fixture.at.y
    return (x - w / 2, y - d / 2, x + w / 2, y + d / 2)


def overlaps(a: Box, b: Box, tolerance: float = 0.05) -> bool:
    return (
        a[0] < b[2] - tolerance and b[0] < a[2] - tolerance
        and a[1] < b[3] - tolerance and b[1] < a[3] - tolerance
    )


def door_zones(project: ProjectConfig) -> list[tuple[str, Box, Box]]:
    """(label, swing-side zone, far-side landing zone) for every door.

    The swing zone is a square of the door's width on the side the leaf
    opens toward; the landing zone is a shallower strip on the other face.
    Both must be clear floor.
    """

    width = project.building.footprint.width
    depth = project.building.footprint.depth
    thickness = project.building.exterior_wall_thickness
    zones = []

    def zone(span_lo, span_hi, face, extent, along_x: bool) -> Box:
        lo, hi = sorted((face, face + extent))
        if along_x:
            return (span_lo, lo, span_hi, hi)
        return (lo, span_lo, hi, span_hi)

    for opening in project.openings:
        if opening.type != "door":
            continue
        assert opening.swing is not None  # schema validation guarantees it
        frames = {
            "front": (0.0, 1, True), "rear": (depth, -1, True),
            "left": (0.0, 1, False), "right": (width, -1, False),
        }
        face, inward, along_x = frames[opening.wall]
        label = f"exterior door on the {opening.wall} wall @ {opening.offset}"
        span = (opening.offset, opening.offset + opening.width)
        sign = inward if opening.swing.startswith("in") else -inward
        swing_face = face + (thickness * inward if sign == inward else 0)
        zones.append((
            label,
            zone(*span, swing_face, sign * opening.width, along_x),
            zone(*span, face + (thickness * inward if sign != inward else 0),
                 -sign * 1.5, along_x),
        ))

    for wall in project.interior_walls:
        along_x = wall.axis == "x"
        half = wall.thickness / 2
        for door in wall.doors:
            label = f"interior door @ {door.at} in the {wall.axis}-wall at {wall.offset}"
            span = (door.at, door.at + door.width)
            sign = 1 if door.swing.startswith("in") else -1
            swing_face = wall.offset + half * sign
            landing_face = wall.offset - half * sign
            zones.append((
                label,
                zone(*span, swing_face, sign * door.width, along_x),
                zone(*span, landing_face, -sign * 1.5, along_x),
            ))
    return zones


def check(project: ProjectConfig) -> list[str]:
    warnings: list[str] = []
    boxes = [(f, fixture_box(f)) for f in project.fixtures]

    for label, swing, landing in door_zones(project):
        for fixture, box in boxes:
            if overlaps(swing, box):
                warnings.append(
                    f"{label}: swing zone overlaps the {fixture.type} at "
                    f"({fixture.at.x}, {fixture.at.y})"
                )
            elif overlaps(landing, box):
                warnings.append(
                    f"{label}: landing side is blocked by the {fixture.type} "
                    f"at ({fixture.at.x}, {fixture.at.y})"
                )

    for i, (fixture_a, box_a) in enumerate(boxes):
        for fixture_b, box_b in boxes[i + 1:]:
            # Counters host appliances and sinks by design.
            if "counter" in (fixture_a.type, fixture_b.type):
                continue
            if overlaps(box_a, box_b):
                warnings.append(
                    f"{fixture_a.type} at ({fixture_a.at.x}, {fixture_a.at.y}) "
                    f"overlaps the {fixture_b.type} at "
                    f"({fixture_b.at.x}, {fixture_b.at.y})"
                )

    for wall in project.interior_walls:
        half = wall.thickness / 2
        if wall.axis == "x":
            band = (wall.from_, wall.offset - half, wall.to, wall.offset + half)
        else:
            band = (wall.offset - half, wall.from_, wall.offset + half, wall.to)
        door_spans = [(d.at, d.at + d.width) for d in wall.doors]
        for fixture, box in boxes:
            if not overlaps(band, box):
                continue
            along = (box[0], box[2]) if wall.axis == "x" else (box[1], box[3])
            in_doorway = any(lo <= along[0] and along[1] <= hi
                             for lo, hi in door_spans)
            if not in_doorway:
                warnings.append(
                    f"{fixture.type} at ({fixture.at.x}, {fixture.at.y}) pokes "
                    f"through the {wall.axis}-wall at {wall.offset}"
                )

    sleeping_rooms = [
        room.name for room in project.rooms
        if "bedroom" in room.name.lower() or room.name.lower() == "studio"
    ]
    egress_count = sum(
        1 for o in project.openings if o.type == "window" and o.egress
    )
    if len(sleeping_rooms) > egress_count:
        warnings.append(
            f"{len(sleeping_rooms)} sleeping room(s) ({', '.join(sleeping_rooms)}) "
            f"but only {egress_count} egress window(s) designated"
        )

    return warnings


def render(project_path: Path, out_path: Path) -> None:
    import subprocess
    import tempfile

    import ezdxf
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import BackgroundPolicy, Configuration
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [sys.executable, "-m", "codeframe", "generate",
             str(project_path), "--out", tmp],
            check=True, capture_output=True,
        )
        doc = ezdxf.readfile(Path(tmp) / "floor_plan.dxf")
    fig = plt.figure(figsize=(12, 12))
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_axis_off()
    Frontend(
        RenderContext(doc), MatplotlibBackend(ax),
        config=Configuration(background_policy=BackgroundPolicy.WHITE),
    ).draw_layout(doc.modelspace(), finalize=True)
    fig.savefig(out_path, dpi=110, facecolor="white", bbox_inches="tight")
    print(f"rendered {out_path}")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    project_path = Path(args[0])
    project = load_project_config(project_path)

    warnings = check(project)
    for warning in warnings:
        print(f"WARNING: {warning}")
    if not warnings:
        print("Layout checks passed: doorways clear, no fixture clashes.")

    if "--render" in sys.argv:
        out = args[1] if len(args) > 1 else "layout_review.png"
        render(project_path, Path(out))

    return 1 if warnings else 0


if __name__ == "__main__":
    sys.exit(main())
