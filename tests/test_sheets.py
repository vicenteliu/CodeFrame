"""Tests for the PDF sheet-set seam."""

import os
from pathlib import Path

import pytest
from pypdf import PdfReader

from codeframe.schema import load_project_config
from codeframe.sheets import write_sheet_set

DEMO_CONFIG = Path(__file__).parent.parent / "examples" / "demo_residential_project.json"
GOLDEN_DIR = Path(__file__).parent / "golden"

ARCH_D_LANDSCAPE_POINTS = (36 * 72, 24 * 72)


@pytest.fixture()
def demo_project():
    return load_project_config(DEMO_CONFIG)


@pytest.fixture()
def sheet_set(demo_project, tmp_path):
    out_path = tmp_path / "drawing_set.pdf"
    write_sheet_set(demo_project, out_path)
    return out_path


def test_sheet_set_has_eight_arch_d_pages(sheet_set):
    reader = PdfReader(sheet_set)
    assert len(reader.pages) == 8
    for page in reader.pages:
        box = page.mediabox
        assert (float(box.width), float(box.height)) == ARCH_D_LANDSCAPE_POINTS


def test_sheets_carry_titles_numbers_and_stamp(sheet_set):
    reader = PdfReader(sheet_set)
    texts = [page.extract_text() for page in reader.pages]

    for text, title, number in zip(
        texts,
        ("GENERAL NOTES", "SITE PLAN", "FLOOR PLAN", "ELEVATIONS", "ROOF PLAN",
         "SCHEDULES", "SECTION A-A", "FOUNDATION PLAN"),
        ("A0.1", "A1.0", "A2.0", "A3.0", "A4.0", "A5.0", "A6.0", "S1.0"),
    ):
        assert title in text
        assert number in text
        assert "Demo Backyard Studio" in text
        assert "NOT FOR CONSTRUCTION" in text
        assert "SCALE" in text


def test_sheet_set_is_deterministic(demo_project, tmp_path):
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    write_sheet_set(demo_project, first)
    write_sheet_set(demo_project, second)
    assert first.read_bytes() == second.read_bytes()


def test_sheet_set_matches_golden(demo_project, tmp_path):
    produced = tmp_path / "drawing_set.pdf"
    write_sheet_set(demo_project, produced)

    golden = GOLDEN_DIR / "drawing_set.pdf"
    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN_DIR.mkdir(exist_ok=True)
        golden.write_bytes(produced.read_bytes())

    assert golden.exists(), "golden file missing; bless with UPDATE_GOLDEN=1 pytest"
    assert produced.read_bytes() == golden.read_bytes(), (
        "drawing_set.pdf no longer matches its golden. Review the change and "
        "bless intentional updates with UPDATE_GOLDEN=1 pytest"
    )
