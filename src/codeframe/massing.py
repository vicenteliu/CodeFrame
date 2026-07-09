"""3D massing model output for the Deterministic Core.

Builds the ADU as a small set of solids — exterior wall shell with openings
cut out, interior walls, and a gable roof prism — in building-local
coordinates and decimal feet (see `codeframe.schema`), then exports STEP by
running a generated macro under headless `freecadcmd`.

FreeCAD is an optional runtime dependency: `massing_solids` is pure math and
always available; `write_massing_model` requires `freecadcmd` on PATH or in
the macOS application bundle. STEP files are canonicalized after export
(timestamp pinned) so identical Project Configs produce byte-identical files.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .dxf import UnsupportedRoofError
from .geometry import parse_slope, wall_frame
from .schema import Opening, ProjectConfig

XYZ = tuple[float, float, float]

# Cut tools poke this far (feet) past the faces they open, so boolean cuts
# never leave coplanar-face slivers.
CUT_CLEARANCE = 0.1

_MM_PER_FOOT = 304.8

_MACOS_FREECADCMD = "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"


class MassingExportError(RuntimeError):
    """The headless FreeCAD export failed or freecadcmd is unavailable."""


@dataclass(frozen=True)
class Box:
    """Axis-aligned box: `origin` is the minimum corner."""

    origin: XYZ
    size: XYZ


@dataclass(frozen=True)
class Prism:
    """Planar profile polygon swept along `direction`."""

    profile: tuple[XYZ, ...]
    direction: XYZ


@dataclass(frozen=True)
class Solid:
    name: str
    base: Box | Prism
    cuts: tuple[Box, ...] = ()


def massing_solids(project: ProjectConfig) -> list[Solid]:
    """Compute the massing solids for a project, in feet."""

    building = project.building
    roof = building.roof
    if roof.type != "gable":
        raise UnsupportedRoofError(
            f"roof type '{roof.type}' is not supported by the massing engine "
            "yet; v1 models gable roofs only"
        )

    width = building.footprint.width
    depth = building.footprint.depth
    height = building.wall_height
    thickness = building.exterior_wall_thickness

    shell_cuts = [
        Box(
            (thickness, thickness, 0.0),
            (width - 2 * thickness, depth - 2 * thickness, height),
        )
    ]
    shell_cuts += [
        _opening_cut(opening, width, depth, thickness)
        for opening in project.openings
    ]
    solids = [Solid("walls", Box((0.0, 0.0, 0.0), (width, depth, height)),
                    tuple(shell_cuts))]

    for index, wall in enumerate(project.interior_walls, start=1):
        along = width if wall.axis == "x" else depth
        # The modeled extent stops at the exterior walls' inner faces.
        lo = max(wall.from_, thickness)
        hi = min(wall.to, along - thickness)
        if hi <= lo:
            continue
        half = wall.thickness / 2
        if wall.axis == "x":
            base = Box((lo, wall.offset - half, 0.0), (hi - lo, wall.thickness, height))
        else:
            base = Box((wall.offset - half, lo, 0.0), (wall.thickness, hi - lo, height))
        solids.append(Solid(f"interior_wall_{index}", base))

    solids.append(Solid("roof", _roof_prism(building)))
    return solids


def _opening_cut(
    opening: Opening, width: float, depth: float, thickness: float
) -> Box:
    """Cut box for a door or window, poking past both wall faces."""

    frame = wall_frame(opening.wall, width, depth)
    p1 = frame.point(opening.offset, -CUT_CLEARANCE)
    p2 = frame.point(opening.offset + opening.width, thickness + CUT_CLEARANCE)
    x0, x1 = sorted((p1[0], p2[0]))
    y0, y1 = sorted((p1[1], p2[1]))

    if opening.type == "door":
        bottom = -CUT_CLEARANCE  # doors cut down through the slab line
        top = opening.height
    else:
        bottom = opening.sill or 0.0
        top = bottom + opening.height
    return Box((x0, y0, bottom), (x1 - x0, y1 - y0, top - bottom))


def _roof_prism(building) -> Prism:
    """Gable roof as a triangular prism, eave and ridge heights matching the
    elevation views: the ridge rises from the wall plate over half the span,
    and eaves drop below the plate across the overhang."""

    roof = building.roof
    width = building.footprint.width
    depth = building.footprint.depth
    overhang = roof.overhang
    rise = parse_slope(roof.slope)

    span = width if roof.ridge_axis == "y" else depth
    ridge_length = depth if roof.ridge_axis == "y" else width
    ridge_z = building.wall_height + (span / 2) * rise
    eave_z = building.wall_height - overhang * rise

    if roof.ridge_axis == "y":
        profile = (
            (-overhang, -overhang, eave_z),
            (width + overhang, -overhang, eave_z),
            (width / 2, -overhang, ridge_z),
        )
        direction = (0.0, ridge_length + 2 * overhang, 0.0)
    else:
        profile = (
            (-overhang, -overhang, eave_z),
            (-overhang, depth + overhang, eave_z),
            (-overhang, depth / 2, ridge_z),
        )
        direction = (ridge_length + 2 * overhang, 0.0, 0.0)
    return Prism(profile, direction)


def find_freecadcmd() -> str | None:
    """Locate the headless FreeCAD binary, or None if not installed."""

    found = shutil.which("freecadcmd")
    if found:
        return found
    if Path(_MACOS_FREECADCMD).is_file():
        return _MACOS_FREECADCMD
    return None


def freecadcmd_available() -> bool:
    return find_freecadcmd() is not None


_MACRO = '''\
"""Generated by codeframe.massing: build solids and export STEP."""
import json

import Part
from FreeCAD import Vector

SPEC = json.loads(r\'\'\'__SPEC_JSON__\'\'\')


def build_base(base):
    if base["kind"] == "box":
        return Part.makeBox(*base["size"], Vector(*base["origin"]))
    points = [Vector(*p) for p in base["profile"]]
    face = Part.Face(Part.makePolygon(points + points[:1]))
    return face.extrude(Vector(*base["direction"]))


solids = []
for spec in SPEC["solids"]:
    shape = build_base(spec["base"])
    for cut in spec["cuts"]:
        shape = shape.cut(Part.makeBox(*cut["size"], Vector(*cut["origin"])))
    solids.append(shape)

Part.makeCompound(solids).exportStep(SPEC["out"])
print("codeframe-massing-ok", len(solids))
'''


def write_massing_model(project: ProjectConfig, path: Path) -> None:
    """Write the 3D massing model as a STEP file via headless FreeCAD."""

    freecadcmd = find_freecadcmd()
    if freecadcmd is None:
        raise MassingExportError(
            "freecadcmd not found; install FreeCAD to export the 3D massing model"
        )

    spec = {
        "solids": [_solid_payload(solid) for solid in massing_solids(project)],
        "out": str(Path(path).resolve()),
    }
    macro_source = _MACRO.replace("__SPEC_JSON__", json.dumps(spec))

    with tempfile.TemporaryDirectory(prefix="codeframe-massing-") as tmp:
        macro_path = Path(tmp) / "massing_macro.py"
        macro_path.write_text(macro_source, encoding="utf-8")
        result = subprocess.run(
            [freecadcmd, str(macro_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
    if result.returncode != 0 or "codeframe-massing-ok" not in result.stdout:
        raise MassingExportError(
            f"freecadcmd export failed (exit {result.returncode}): "
            f"{result.stderr.strip()[-500:]}"
        )
    _pin_step_timestamp(Path(path))


def _solid_payload(solid: Solid) -> dict:
    if isinstance(solid.base, Box):
        base = {"kind": "box", "origin": _mm(solid.base.origin),
                "size": _mm(solid.base.size)}
    else:
        base = {"kind": "prism",
                "profile": [_mm(p) for p in solid.base.profile],
                "direction": _mm(solid.base.direction)}
    return {
        "name": solid.name,
        "base": base,
        "cuts": [
            {"origin": _mm(cut.origin), "size": _mm(cut.size)}
            for cut in solid.cuts
        ],
    }


def _mm(values: XYZ) -> list[float]:
    return [value * _MM_PER_FOOT for value in values]


def _pin_step_timestamp(path: Path) -> None:
    """Pin the FILE_NAME timestamp: identical Project Configs must produce
    byte-identical STEP files."""

    text = path.read_text(encoding="utf-8")
    text = re.sub(
        r"(FILE_NAME\('[^']*',')[^']*(')",
        r"\g<1>2000-01-01T00:00:00\g<2>",
        text,
        count=1,
    )
    path.write_text(text, encoding="utf-8")
