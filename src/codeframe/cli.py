"""Command-line entry points for the early CodeFrame framework."""

from __future__ import annotations

import argparse
from pathlib import Path

from .projects import load_project_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codeframe",
        description="Validate and summarize a CodeFrame residential project configuration.",
    )
    parser.add_argument(
        "project_config",
        type=Path,
        help="Path to a JSON residential project configuration.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    project = load_project_config(args.project_config)
    print(f"Project: {project.name}")
    print(f"Location: {project.location}")
    print(f"Project type: {project.project_type}")
    print(f"Stories: {project.stories}")
    print(f"Output target: {project.output_target}")
    return 0
