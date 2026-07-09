---
status: accepted
---

# Add an optional 3D massing model generated via headless FreeCAD

ADR 0001 kept v1 on ezdxf and said to re-evaluate FreeCAD if 3D output
returned to scope. It has: the Drawing Skeleton gains an optional 3D massing
model (`model_3d.step`) — wall shell with openings cut out, interior walls,
gable roof prism — useful for owner communication and design review.

The model is generated from the Project Config (never reconstructed from the
DXF, which would discard semantics) by `codeframe.massing`: a pure-Python
solid-spec layer plus a generated macro run under headless `freecadcmd`.
Roof math matches the elevation views exactly. FreeCAD stays optional at
runtime: `codeframe generate` skips the model with a notice when
`freecadcmd` is missing, and the FreeCAD-dependent tests skip likewise, so
the Deterministic Core remains pip-installable and CI-friendly. STEP output
is canonicalized (timestamp pinned) for byte-determinism and golden tests.

## Considered options

- **cli-anything-freecad harness** — evaluated hands-on (2026-07-09) and
  rejected: its export path emits raw primitives only, silently dropping
  boolean results and wedge solids; live preview needs OpenGL that headless
  macOS lacks.
- **Native freecadcmd macro (chosen)** — full Part API, ~0.4 s per export,
  one generated self-contained macro file.
- **Pure-Python mesh libraries (trimesh etc.)** — no B-rep STEP output;
  drafters' CAD tools need STEP, not tessellated meshes.
