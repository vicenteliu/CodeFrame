"""PDF sheet composition: Arch D landscape sheets with title blocks.

Each sheet carries a border, a title block, and a PRELIMINARY — NOT FOR
CONSTRUCTION stamp. Drawings are placed at standard architectural or
engineering scales (largest that fits), never scaled arbitrarily to fit.
Output is deterministic: identical Project Configs produce byte-identical
PDFs.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
from ezdxf import bbox
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.document import Drawing
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from .dxf import build_elevation, build_floor_plan, build_roof_plan, build_site_plan
from .schema import ProjectConfig

SHEET_WIDTH = 36.0  # inches, Arch D landscape
SHEET_HEIGHT = 24.0
MARGIN = 0.5
TITLE_BLOCK_HEIGHT = 1.5
CELL_GAP = 0.75

# (label, feet of model space per inch of paper)
ARCHITECTURAL_SCALES = [
    ("1/4\" = 1'-0\"", 4.0),
    ("3/16\" = 1'-0\"", 16 / 3),
    ("1/8\" = 1'-0\"", 8.0),
]
ENGINEERING_SCALES = [
    ("1\" = 10'", 10.0),
    ("1\" = 20'", 20.0),
    ("1\" = 30'", 30.0),
]

STAMP = "PRELIMINARY — NOT FOR CONSTRUCTION"

RENDER_CONFIG = Configuration(
    background_policy=BackgroundPolicy.WHITE,
    color_policy=ColorPolicy.BLACK,
)


def _extents(doc: Drawing):
    return bbox.extents(doc.modelspace(), fast=True)


def _pick_scale(scales, extent_w: float, extent_h: float, avail_w: float, avail_h: float):
    for label, feet_per_inch in scales:
        if extent_w / feet_per_inch <= avail_w and extent_h / feet_per_inch <= avail_h:
            return label, feet_per_inch
    return scales[-1]


def _place_drawing(fig: Figure, doc: Drawing, rect, feet_per_inch: float) -> None:
    """Render `doc` centered in `rect` (sheet inches) at the given scale."""

    x0, y0, width, height = rect
    ax = fig.add_axes(
        [x0 / SHEET_WIDTH, y0 / SHEET_HEIGHT, width / SHEET_WIDTH, height / SHEET_HEIGHT]
    )
    backend = MatplotlibBackend(ax, adjust_figure=False)
    Frontend(RenderContext(doc), backend, config=RENDER_CONFIG).draw_layout(
        doc.modelspace(), finalize=True
    )
    extent = _extents(doc)
    center_x = (extent.extmin.x + extent.extmax.x) / 2
    center_y = (extent.extmin.y + extent.extmax.y) / 2
    # The axes box and the data spans share the same aspect by construction,
    # so a box-adjustable equal aspect keeps the paper scale exact.
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(center_x - width * feet_per_inch / 2, center_x + width * feet_per_inch / 2)
    ax.set_ylim(center_y - height * feet_per_inch / 2, center_y + height * feet_per_inch / 2)
    ax.axis("off")


def _decorate_sheet(
    fig: Figure, project: ProjectConfig, title: str, number: str, scale_label: str
) -> None:
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, SHEET_WIDTH)
    ax.set_ylim(0, SHEET_HEIGHT)
    ax.axis("off")
    ax.patch.set_visible(False)

    ax.add_patch(
        Rectangle(
            (MARGIN, MARGIN),
            SHEET_WIDTH - 2 * MARGIN,
            SHEET_HEIGHT - 2 * MARGIN,
            fill=False, edgecolor="black", linewidth=2,
        )
    )

    strip_top = MARGIN + TITLE_BLOCK_HEIGHT
    ax.plot(
        [MARGIN, SHEET_WIDTH - MARGIN], [strip_top, strip_top],
        color="black", linewidth=1,
    )
    inner_width = SHEET_WIDTH - 2 * MARGIN
    dividers = [MARGIN + inner_width * f for f in (0.35, 0.62, 0.78, 0.90)]
    for x in dividers:
        ax.plot([x, x], [MARGIN, strip_top], color="black", linewidth=0.75)

    mid_y = MARGIN + TITLE_BLOCK_HEIGHT / 2
    cells = [MARGIN, *dividers, SHEET_WIDTH - MARGIN]

    def cell_center(index: int) -> float:
        return (cells[index] + cells[index + 1]) / 2

    ax.text(
        cell_center(0), mid_y, f"{project.name}\n{project.location}",
        ha="center", va="center", fontsize=10,
    )
    ax.text(
        cell_center(1), mid_y, STAMP,
        ha="center", va="center", fontsize=10, fontweight="bold",
    )
    ax.text(
        cell_center(2), mid_y, title,
        ha="center", va="center", fontsize=13, fontweight="bold",
    )
    ax.text(
        cell_center(3), mid_y, f"SCALE: {scale_label}",
        ha="center", va="center", fontsize=9,
    )
    ax.text(
        cell_center(4), mid_y, number,
        ha="center", va="center", fontsize=18, fontweight="bold",
    )


def write_sheet_set(project: ProjectConfig, path: Path) -> None:
    """Write the multi-page PDF drawing set (site, floor, elevations, roof)."""

    site = build_site_plan(project)
    floor = build_floor_plan(project)
    roof = build_roof_plan(project)
    walls = ("front", "rear", "left", "right")
    elevations = [build_elevation(project, wall) for wall in walls]

    content = (
        MARGIN,
        MARGIN + TITLE_BLOCK_HEIGHT,
        SHEET_WIDTH - 2 * MARGIN,
        SHEET_HEIGHT - 2 * MARGIN - TITLE_BLOCK_HEIGHT,
    )
    _, _, content_w, content_h = content

    def single_doc_page(pdf: PdfPages, doc: Drawing, title: str, number: str, scales) -> None:
        extent = _extents(doc)
        scale_label, feet_per_inch = _pick_scale(
            scales, extent.size.x, extent.size.y, content_w, content_h
        )
        fig = Figure(figsize=(SHEET_WIDTH, SHEET_HEIGHT))
        fig.patch.set_facecolor("white")
        _place_drawing(fig, doc, content, feet_per_inch)
        _decorate_sheet(fig, project, title, number, scale_label)
        pdf.savefig(fig)

    metadata = {
        "CreationDate": None,
        "Producer": "CodeFrame",
        "Creator": "CodeFrame",
        "Title": f"{project.name} — Drawing Set",
    }
    with mpl.rc_context({"pdf.fonttype": 42}):
        with PdfPages(path, metadata=metadata) as pdf:
            single_doc_page(pdf, site, "SITE PLAN", "A1.0", ENGINEERING_SCALES)
            single_doc_page(pdf, floor, "FLOOR PLAN", "A2.0", ARCHITECTURAL_SCALES)

            # Elevations: 2x2 grid sharing one scale, standard practice.
            cell_w = (content_w - CELL_GAP) / 2
            cell_h = (content_h - CELL_GAP) / 2
            extents = [_extents(doc) for doc in elevations]
            scale_label, feet_per_inch = _pick_scale(
                ARCHITECTURAL_SCALES,
                max(extent.size.x for extent in extents),
                max(extent.size.y for extent in extents),
                cell_w, cell_h,
            )
            fig = Figure(figsize=(SHEET_WIDTH, SHEET_HEIGHT))
            fig.patch.set_facecolor("white")
            x0, y0 = content[0], content[1]
            positions = [
                (x0, y0 + cell_h + CELL_GAP),               # front: top-left
                (x0 + cell_w + CELL_GAP, y0 + cell_h + CELL_GAP),  # rear: top-right
                (x0, y0),                                    # left: bottom-left
                (x0 + cell_w + CELL_GAP, y0),                # right: bottom-right
            ]
            for doc, (cell_x, cell_y) in zip(elevations, positions):
                _place_drawing(fig, doc, (cell_x, cell_y, cell_w, cell_h), feet_per_inch)
            _decorate_sheet(fig, project, "ELEVATIONS", "A3.0", scale_label)
            pdf.savefig(fig)

            single_doc_page(pdf, roof, "ROOF PLAN", "A4.0", ARCHITECTURAL_SCALES)
