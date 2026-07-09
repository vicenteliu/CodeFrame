# Architecture

CodeFrame is two layers with a hard boundary (terms defined in `CONTEXT.md`):

1. **Agent Layer** — Claude Code skills that interview the Drafter, fill the
   Project Config, and orchestrate the core. Conversational convenience lives
   here: unit conversions, computing opening positions from a description,
   checking a config for completeness. It never draws geometry and never
   bypasses the Project Config.
2. **Deterministic Core** — the `codeframe` Python package. Project Config
   in, Drawing Skeleton out. No AI, no network, no auto-layout. Runs
   standalone: `python -m codeframe <config>`.

## Core modules

A single package with clear internal boundaries; split into separate packages
only if and when a real need appears:

- `codeframe.schema` — Project Config models, validation, schema versioning.
- `codeframe.geometry` — plan/elevation/roof geometry math (pure functions).
- `codeframe.dxf` — DXF output via ezdxf.
- `codeframe.sheets` — PDF sheet composition and title blocks.

## Rules

- Every artifact must be reproducible from the Project Config alone.
- Geometry is explicit in the config; the core never infers or arranges
  (see `docs/adr/0002-explicit-geometry-no-auto-layout.md`).
- Golden-file tests pin DXF/PDF outputs for the example configs.
- Generated files go to `outputs/` and stay out of source control.
