"""Pure geometry math for plan generation.

Everything works in building-local coordinates: origin at the footprint's
front-left corner, x across the width, y toward the rear (see
`codeframe.schema` for the full convention).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Interval = tuple[float, float]
Point = tuple[float, float]


def subtract_intervals(span: Interval, cuts: list[Interval]) -> list[Interval]:
    """Remove `cuts` from `span`, returning the remaining pieces in order."""

    start, end = span
    pieces: list[Interval] = []
    cursor = start
    for cut_start, cut_end in sorted(cuts):
        if cut_start > cursor:
            pieces.append((cursor, min(cut_start, end)))
        cursor = max(cursor, cut_end)
    if cursor < end:
        pieces.append((cursor, end))
    return pieces


@dataclass(frozen=True)
class WallFrame:
    """Maps wall-local coordinates to plan coordinates.

    `s` runs along the wall from its offset origin (the left end on
    front/rear walls, the front end on left/right walls); `d` runs across
    the wall thickness, inward positive, with d=0 on the outer face.
    """

    origin: Point
    s_dir: Point
    d_dir: Point
    length: float

    def point(self, s: float, d: float) -> Point:
        return (
            self.origin[0] + s * self.s_dir[0] + d * self.d_dir[0],
            self.origin[1] + s * self.s_dir[1] + d * self.d_dir[1],
        )

    def angle(self, local_degrees: float) -> float:
        """Transform a wall-local direction angle into plan space."""

        radians = math.radians(local_degrees)
        x = math.cos(radians) * self.s_dir[0] + math.sin(radians) * self.d_dir[0]
        y = math.cos(radians) * self.s_dir[1] + math.sin(radians) * self.d_dir[1]
        return math.degrees(math.atan2(y, x)) % 360


def wall_frame(wall: str, width: float, depth: float) -> WallFrame:
    frames = {
        "front": WallFrame((0, 0), (1, 0), (0, 1), width),
        "rear": WallFrame((0, depth), (1, 0), (0, -1), width),
        "left": WallFrame((0, 0), (0, 1), (1, 0), depth),
        "right": WallFrame((width, 0), (0, 1), (-1, 0), depth),
    }
    return frames[wall]


def parse_slope(slope: str) -> float:
    """Convert 'N:12' roof slope notation into a rise/run ratio."""

    rise, _run = slope.split(":")
    return float(rise) / 12.0


def elevation_length(wall: str, width: float, depth: float) -> float:
    """Horizontal extent of a wall's elevation view."""

    return width if wall in ("front", "rear") else depth


def elevation_interval(
    wall: str, start: float, end: float, width: float, depth: float
) -> Interval:
    """Map an along-wall interval into elevation view coordinates.

    Elevations are drawn as seen from outside the wall, so rear and left
    views mirror the along-wall axis.
    """

    if wall in ("front", "right"):
        return (start, end)
    length = elevation_length(wall, width, depth)
    return (length - end, length - start)
