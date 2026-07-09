# CodeFrame — Ubiquitous Language

Glossary of domain terms. Terms here are canonical: code, docs, and
conversation should use them exactly as defined.

## Terms

### Drafter（绘图从业者）
The paying user: an independent drafter, designer, or design-build firm in
California who prepares residential permit drawing packages for clients. The
Drafter reviews, completes, and takes professional responsibility for
everything CodeFrame generates. CodeFrame never submits anything itself.

### Detached ADU
The v1 business scope: a single-story, wood-frame, detached accessory
dwelling unit or accessory structure (studio, storage) on a California
residential lot. Attached ADUs, additions, remodels, multi-story buildings,
and non-California jurisdictions are out of scope for v1.

### Project Config
A structured JSON file describing one Detached ADU project: site, building
geometry, openings, roof, and assumptions. Geometry is always explicit —
footprint, wall segments, and opening positions are stated, never inferred.
It is the single source of truth — every generated artifact must be
reproducible from the Project Config alone.

### Drawing Skeleton（报建图骨架）
The v1 deliverable: site plan, floor plan, four elevations, and roof plan,
exported as editable DXF plus a PDF sheet set. Deliberately incomplete
(~60–70%): the Drafter finishes details, checks compliance, and signs off.
Not a permit set, not construction documents.

### Massing Model（体量模型）
An optional 3D companion to the Drawing Skeleton: `model_3d.step`, the
building as a few solids (exterior wall shell with openings cut out,
interior walls, roof prism), generated from the same Project Config — never
reconstructed from the DXF. For owner communication and design review only:
not a BIM model, carries no materials or assemblies. Requires FreeCAD
(`freecadcmd`) at generation time; `codeframe generate` skips it with a
notice when FreeCAD is absent (see ADR 0003).

### Deterministic Core
The Python package that turns a Project Config into a Drawing Skeleton with
no AI involvement. Same input, same output, fully testable offline. It must
run standalone from the CLI without any agent present, and it never invents
geometry: no auto-layout, no filling in unstated dimensions.

### Wall / Elevation Names
Exterior walls are named front, rear, left, and right, where front is the
side facing the street. Each wall maps one-to-one onto the drawing of the
same name (Front Elevation, Rear Elevation, …), and left/right are as seen
when facing the building from the street.

### Agent Layer
The Claude Code skills that interview the Drafter, fill in the Project
Config, and orchestrate the Deterministic Core. The Agent Layer never draws
geometry and never bypasses the Project Config.
