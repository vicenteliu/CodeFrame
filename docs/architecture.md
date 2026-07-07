# Architecture

CodeFrame is organized around a staged workflow:

1. Residential project input files define the intended building scenario.
2. Python modules validate and normalize project data.
3. Future FreeCAD scripts generate 2D CAD geometry and drawing sheets.
4. Future Blender scripts generate 3D massing, model views, and renders.
5. Generated files are written to `outputs/` and kept out of source control.

## Current Components

- `src/codeframe/`: minimal Python package and project configuration loader.
- `examples/`: sample structured inputs.
- `scripts/freecad/`: reserved for FreeCAD automation entry points.
- `scripts/blender/`: reserved for Blender automation entry points.
- `docs/`: project planning and guardrail documentation.
- `outputs/`: local generated artifacts.

## Future Integration Boundaries

FreeCAD and Blender automation should remain scriptable and reproducible. The
core Python package should focus on project data, validation, orchestration, and
shared utilities rather than embedding tool-specific assumptions everywhere.
