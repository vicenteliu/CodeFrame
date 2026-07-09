# CodeFrame

CodeFrame turns structured residential project inputs into permit-drawing
skeletons for California detached ADUs.

It is built for drafters, designers, and design-build firms who prepare
residential permit packages: describe the project in a guided Claude Code
conversation, get an editable DXF + PDF drawing set at 60–70% completeness,
then finish, check, and sign it in your own CAD tool.

This is a private, closed-source, pre-prototype project. See
`docs/disclaimer.md` before relying on any output.

## How it works

CodeFrame has two layers with a hard boundary between them (terms defined in
`CONTEXT.md`):

- **Agent Layer** — Claude Code skills that interview the Drafter, fill in a
  Project Config, and orchestrate generation. It never draws geometry.
- **Deterministic Core** — the `codeframe` Python package that turns a
  Project Config into a Drawing Skeleton with no AI involvement. Same input,
  same output. Runs standalone from the CLI.

The Project Config (JSON) is the single source of truth. Geometry in it is
always explicit — footprint, wall segments, opening positions — never
inferred or auto-laid-out.

## v1 scope

- California detached ADUs and accessory structures: single story, wood frame.
- Deliverable: site plan, floor plan, four elevations, and roof plan as
  editable DXF plus a PDF sheet set.
- 2D generation in pure Python via ezdxf; no FreeCAD or Blender dependency
  (see `docs/adr/0001-ezdxf-over-freecad.md`).

## Repository layout

```text
CodeFrame/
  CONTEXT.md            Ubiquitous language (canonical domain terms)
  docs/                 Vision, architecture, roadmap, ADRs, disclaimer
  examples/             Example Project Config files
  outputs/              Generated local files, ignored by git
  skills/               Agent Layer (Claude Code skills)
  src/codeframe/        Deterministic Core (Python package)
  tests/                Test suite incl. golden DXF/PDF snapshots
```

## Development

```bash
python -m pip install -e ".[dev]"
python -m codeframe validate examples/demo_residential_project.json
python -m codeframe generate examples/demo_residential_project.json
pytest
```

`validate` checks a Project Config and prints a summary; `generate` writes
the full Drawing Skeleton to the config's `output_target` (or `--out DIR`):
site plan, floor plan, roof plan, and four elevations as DXF, plus
`drawing_set.pdf` — Arch D sheets with title blocks, standard scales, and a
PRELIMINARY stamp. `schema` prints the Project Config JSON Schema. Output
is deterministic — identical configs produce byte-identical files, pinned
by golden tests (`UPDATE_GOLDEN=1 pytest` blesses intentional changes).

### Agent Layer

The guided workflow lives in `skills/codeframe-adu/` (a Claude Code skill):
it interviews the Drafter, writes the Project Config, and drives
`validate`/`generate` — the skill never draws geometry itself. To use it in
this repo, symlink it into `.claude/skills/`:

```bash
ln -s ../../skills/codeframe-adu .claude/skills/codeframe-adu
```

See `docs/roadmap.md` for what lands next and each phase's verification
gate.

## Status

Experimental pre-prototype. CodeFrame is not a licensed professional and its
outputs are not construction documents. See `docs/disclaimer.md`.
