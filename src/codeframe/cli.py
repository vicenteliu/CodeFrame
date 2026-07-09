"""Command-line entry points for the CodeFrame Deterministic Core."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .dxf import (
    UnsupportedRoofError,
    write_elevation,
    write_floor_plan,
    write_roof_plan,
    write_site_plan,
)
from .massing import MassingExportError, freecadcmd_available, write_massing_model
from .schema import ProjectConfig, ProjectConfigError, load_project_config
from .sheets import write_sheet_set


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codeframe",
        description="Deterministic drawing generation from a CodeFrame Project Config.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser(
        "validate", help="Validate a Project Config and print a summary."
    )
    validate.add_argument(
        "project_config", type=Path, help="Path to a Project Config JSON file."
    )

    generate = subparsers.add_parser(
        "generate", help="Generate site plan and floor plan DXF files."
    )
    generate.add_argument(
        "project_config", type=Path, help="Path to a Project Config JSON file."
    )
    generate.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory (default: the config's output_target).",
    )

    subparsers.add_parser(
        "schema", help="Print the Project Config JSON Schema."
    )
    return parser


def _load(path: Path) -> ProjectConfig | None:
    try:
        return load_project_config(path)
    except FileNotFoundError:
        print(f"Config file not found: {path}", file=sys.stderr)
    except ProjectConfigError as exc:
        print(exc, file=sys.stderr)
    return None


def _print_summary(project: ProjectConfig) -> None:
    building = project.building
    print(f"Project: {project.name}")
    print(f"Location: {project.location}")
    print(
        f"Building: {building.footprint.width} x {building.footprint.depth} ft, "
        f"{building.roof.type} roof {building.roof.slope}"
    )
    print(f"Lot: {project.site.lot.width} x {project.site.lot.depth} ft")
    print(
        f"Interior walls: {len(project.interior_walls)} | "
        f"Openings: {len(project.openings)} | Rooms: {len(project.rooms)}"
    )
    print(f"Output target: {project.output_target}")
    print("Config OK.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "schema":
        print(json.dumps(ProjectConfig.model_json_schema(), indent=2))
        return 0

    project = _load(args.project_config)
    if project is None:
        return 1

    if args.command == "validate":
        _print_summary(project)
        return 0

    writers = [
        ("site_plan.dxf", write_site_plan),
        ("floor_plan.dxf", write_floor_plan),
        ("roof_plan.dxf", write_roof_plan),
        *[
            (
                f"elevation_{wall}.dxf",
                lambda project, path, wall=wall: write_elevation(project, wall, path),
            )
            for wall in ("front", "rear", "left", "right")
        ],
        ("drawing_set.pdf", write_sheet_set),
    ]
    if freecadcmd_available():
        writers.append(("model_3d.step", write_massing_model))

    out_dir = args.out if args.out is not None else Path(project.output_target)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, writer in writers:
            out_path = out_dir / name
            writer(project, out_path)
            print(f"Wrote {out_path}")
    except (UnsupportedRoofError, MassingExportError) as exc:
        print(exc, file=sys.stderr)
        return 1
    if not freecadcmd_available():
        print("Skipped model_3d.step: freecadcmd not found (install FreeCAD to enable it)")
    return 0
