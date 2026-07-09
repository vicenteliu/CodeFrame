# Roadmap

Each phase ends with a verification gate; a phase is done only when its gate
passes.

## Phase 1: Explicit-geometry schema

- Project Config v1: site, footprint, wall segments, openings, roof, units.
- Validation with actionable error messages.
- Rewrite `examples/demo_residential_project.json` in explicit-geometry form.
- **Gate:** unit tests cover valid and invalid configs; the CLI validates the
  demo config end-to-end.

## Phase 2: Floor plan + site plan (DXF)

- Generate floor plan and site plan geometry as DXF via ezdxf.
- Layers, line weights, and dimension annotations.
- **Gate:** golden-file DXF tests pass; the demo config's output opens
  cleanly in a mainstream CAD tool.

## Phase 3: Elevations, roof plan, PDF sheet set

- Four elevations and roof plan from the same config.
- PDF sheet composition with title blocks.
- **Gate:** the full Drawing Skeleton generates end-to-end from the demo
  config in one command.

## Phase 4: Agent Layer

- Claude Code skills: guided intake interview → Project Config; a
  generate-and-review loop.
- **Gate:** a cold start (empty directory → finished Drawing Skeleton)
  completes in one conversation without hand-editing JSON.

## Phase 5: Pilot & pricing

- Put generated skeletons in front of 1–3 practicing California ADU drafters
  on real projects.
- **Gate:** at least one Drafter confirms the skeleton saves two or more
  hours on a real project and names a price they would pay. Choose per-seat
  vs per-project pricing from that evidence.
