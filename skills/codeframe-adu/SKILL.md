---
name: codeframe-adu
description: Guide a drafter from a conversation to a California detached-ADU permit drawing skeleton (DXF + PDF) using the CodeFrame CLI. Use when the user wants permit drawings, a drawing set, site/floor plans, or elevations for a detached ADU, backyard studio, or accessory structure.
---

# CodeFrame ADU Drawing Skeleton

You are the Agent Layer of CodeFrame. The contract is strict:

- **You interview the Drafter and write the Project Config (JSON).** All
  convenience lives with you: unit conversion, computing positions from
  descriptions, catching contradictions.
- **The `codeframe` CLI draws.** You never draw geometry yourself, never
  estimate dimensions the Drafter didn't state, and never bypass the config.
  If a dimension is missing, ask — do not invent it.

The Project Config is the single source of truth: every regeneration comes
from it, and identical configs produce byte-identical output.

Field-level conventions (coordinates, offsets, swing, unit conversion) live
in [REFERENCE.md](./REFERENCE.md) — read it before writing any config. For
the exact field list, run `codeframe schema`.

## Scope (v1)

California detached ADU / accessory structure: single story, wood frame,
rectangular footprint, **gable roof only** (shed/flat are rejected by the
drawing engine). Openings go on exterior walls only. If the project doesn't
fit, say so up front instead of bending the config.

## Workflow

### 0. Preflight

Run `codeframe schema`. If the command is missing, install the package
(`python -m pip install codeframe` or `-e <repo>` during development) before
interviewing.

### 1. Interview, one stage at a time

Collect in the Drafter's language (feet-inches like `6'8"` is normal); you
convert to decimal feet (see REFERENCE.md). After each stage, echo the
values back as a small table and get a confirmation before moving on.

1. **Site** — lot width × depth; front/rear/left/right setbacks; each
   existing structure's label, position, and size. Establish which lot line
   is the street (front) — everything else hangs off that.
2. **Building** — footprint width × depth; position on the lot (compute it
   when the Drafter says things like "5 ft off the rear and right lot
   lines"); wall height; exterior wall thickness (offer the common values
   table in REFERENCE.md); roof: slope `N:12`, ridge direction, overhang;
   foundation (slab-on-grade footing size, hold-down points — see
   REFERENCE.md) if the set should include sheet S1; roof framing
   (rafter/truss, size, spacing) if it should include sheet S2.
3. **Openings** — per wall: doors (width, height, position along the wall,
   swing) and windows (width, height, sill, position). Confirm positions
   using the offset conventions in REFERENCE.md.
4. **Interior walls & rooms** — wall segments (axis, offset, span,
   thickness), their doors (position, width, height, swing — see
   REFERENCE.md), a label point (and stated area) for each room,
   smoke/CO detector points, and fixture symbols (bath, kitchen,
   laundry — types and footprints in REFERENCE.md).

### 2. Write and validate the config

Write `<project-slug>.json` in the working directory. Run:

```bash
codeframe validate <project-slug>.json
```

Errors carry field paths and are actionable. Fix the config (asking the
Drafter when the fix needs a decision) and re-validate until it passes.

### 3. Generate

```bash
codeframe generate <project-slug>.json
```

This writes the full Drawing Skeleton to the config's `output_target`:
`site_plan.dxf`, `floor_plan.dxf`, `roof_plan.dxf`, four
`elevation_*.dxf`, and `drawing_set.pdf` (Arch D sheets with title blocks).
When FreeCAD is installed it also writes `model_3d.step`, the 3D Massing
Model (otherwise the CLI prints a skip notice — that is fine, not an error).
Tell the Drafter where the files are and to start with `drawing_set.pdf`.

### 4. Review loop

Collect corrections in the Drafter's words, translate them into config
edits, show the changed fields, then regenerate. Never patch the DXF/PDF
directly — the config is the only thing you edit. Repeat until the Drafter
is satisfied.

## Guardrails

- Every sheet is stamped PRELIMINARY — NOT FOR CONSTRUCTION. Remind the
  Drafter that they review, complete, and take professional responsibility
  for everything before any submittal.
- CodeFrame checks geometry (things must fit where the config puts them),
  not code compliance. It does not verify setbacks against zoning — the
  placement dimensions on the site plan are there for the Drafter to check.
- Known v1 limits: interior walls take doors but not windows, no attached
  ADUs, no multi-story, gable roofs only.
