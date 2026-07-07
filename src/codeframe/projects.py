"""Residential project configuration helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProjectConfig:
    """Minimal structured input for future CAD/model generation workflows."""

    name: str
    location: str
    project_type: str
    stories: int
    output_target: str
    raw: dict[str, Any]


def load_project_config(path: Path) -> ProjectConfig:
    """Load a residential project configuration from JSON."""

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    required_fields = ["name", "location", "project_type", "stories", "output_target"]
    missing = [field for field in required_fields if field not in data]
    if missing:
        missing_list = ", ".join(missing)
        raise ValueError(f"Missing required project config field(s): {missing_list}")

    return ProjectConfig(
        name=str(data["name"]),
        location=str(data["location"]),
        project_type=str(data["project_type"]),
        stories=int(data["stories"]),
        output_target=str(data["output_target"]),
        raw=data,
    )
