# CodeFrame

CodeFrame is an early-stage experimental project for AI-assisted residential
CAD and 3D modeling workflows.

The long-term idea is to explore how Claude Code, Codex, FreeCAD, Blender, and
structured project inputs can help generate simple architectural drawings, 3D
building models, and supporting materials for residential permit preparation.

This repository is currently only a framework. It does not yet produce permit
sets, construction documents, code-compliance determinations, or professional
design outputs.

## Current Scope

- Maintain a clean Python project structure.
- Store residential project inputs in structured example files.
- Reserve clear locations for future FreeCAD and Blender automation scripts.
- Document the product vision, rough architecture, roadmap, and limitations.
- Keep generated CAD/model/render outputs out of source control.

## Repository Layout

```text
CodeFrame/
  docs/                 Project vision, architecture, roadmap, disclaimers
  examples/             Example residential project input files
  outputs/              Generated local files, ignored by git except .gitkeep
  scripts/
    blender/            Future Blender automation scripts
    freecad/            Future FreeCAD automation scripts
  src/codeframe/        Minimal Python package skeleton
```

## Development

This project uses a `src/` Python package layout.

```bash
python -m pip install -e .
python -m codeframe examples/demo_residential_project.json
```

The command currently validates and summarizes a project configuration. Future
work will connect this input layer to FreeCAD and Blender automation.

## Status

Experimental pre-prototype. Do not rely on CodeFrame for legal, engineering,
architectural, or permit-submission decisions.
