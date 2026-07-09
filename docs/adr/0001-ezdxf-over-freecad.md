---
status: accepted
---

# Use ezdxf (pure Python), not FreeCAD, for v1 2D drawing generation

The repo originally reserved `scripts/freecad/` and `scripts/blender/` and
planned FreeCAD-based drawing generation. v1's deliverable is a 2D Drawing
Skeleton (DXF + PDF) for rectangular single-story detached ADUs, which
pure-Python ezdxf can generate deterministically with no external
application — keeping the Deterministic Core pip-installable, unit-testable,
and CI-friendly, and sparing every Drafter a FreeCAD install. FreeCAD's
parametric 3D and TechDraw only pay off for 3D models and sections, which are
out of v1 scope; re-evaluate if those return.

## Considered options

- **FreeCAD scripting** — parametric modeling and TechDraw sheets for free,
  but a heavyweight install for every user, notorious version churn, and
  hard to test in CI.
- **ezdxf + PDF composition (chosen).**
- **Abstraction layer over both backends** — rejected as speculative
  abstraction for a single current use.
