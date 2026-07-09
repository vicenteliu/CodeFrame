# Project Config Reference

Run `codeframe schema` for the exact field list and types. This file covers
what the JSON Schema cannot express: coordinate conventions, offset
directions, and the translations you do for the Drafter. The demo config at
`examples/demo_residential_project.json` (in the CodeFrame repo) is a
complete worked example.

## Units

All dimensions are **decimal feet**. The Drafter speaks feet-inches; you
convert and round to two decimals:

| Spoken | Config |
|--------|--------|
| 6'8"   | 6.67   |
| 3'6"   | 3.5    |
| 10'0"  | 10     |
| 4½"    | 0.375  |

## Coordinate system

Lot coordinates: origin at the lot's **front-left corner** (front = street
side), x runs right across the lot width, y runs toward the rear.

```
        rear
   +-----------+
   |           |            y
   |   lot     |            ^
   |           |            |
   +-----------+            +--> x
  front (street)
```

- `site.existing_structures[].x/y` and `building.position` place each
  structure's own front-left corner in lot coordinates.
- Building-local coordinates (interior walls, room label points) use the
  same axes with the origin at the footprint's front-left corner.
- The core rejects anything that doesn't fit inside the lot or footprint.

## Walls, elevations, and opening offsets

Exterior walls are named `front`, `rear`, `left`, `right` — left/right as
seen **from the street facing the building**. Each wall maps to the
elevation of the same name.

Opening `offset` runs along the wall:

| Wall  | Offset measured from | Wall length equals |
|-------|----------------------|--------------------|
| front | left end (x = 0)     | footprint width    |
| rear  | left end (x = 0)     | footprint width    |
| left  | front end (y = 0)    | footprint depth    |
| right | front end (y = 0)    | footprint depth    |

So "a 3-ft door centered on the front wall of a 16-ft-wide building" is
`offset = (16 − 3) / 2 = 6.5`.

## Door swing

`swing` is required on doors, forbidden on windows. Format:
`in`/`out` (opens into or out of the building) + `left`/`right` (hinge at
the lower-offset or higher-offset end of the opening).

| Value      | Hinge                    | Opens          |
|------------|--------------------------|----------------|
| `in-left`  | lower-offset end         | into building  |
| `in-right` | higher-offset end        | into building  |
| `out-left` | lower-offset end         | outward        |
| `out-right`| higher-offset end        | outward        |

## Interior doors

Interior walls take a `doors` list. `at` is the near jamb's position along
the wall's axis, in the same building-local coordinate as the wall's
`from`/`to` (NOT distance from the wall's start). Doors need `width`,
`height`, and `swing`. Swing reuses the exterior vocabulary with this
mapping: `left`/`right` = hinge at the lower/higher-coordinate jamb;
`in` opens toward the positive side of the cross axis (+y for an axis-x
wall, +x for an axis-y wall), `out` toward the negative side. Windows on
interior walls are not supported.

## Roof

Gable only in v1. `slope` is `"N:12"` (e.g. `"4:12"`). `ridge_axis` is the
direction the ridge runs: `"y"` (front-to-back — gable triangles face the
street) or `"x"` (side-to-side — triangles face left/right). `overhang` is
uniform on all sides.

## Common wall thickness values

| Construction                     | `exterior_wall_thickness` |
|----------------------------------|---------------------------|
| 2×4 studs + sheathing + finishes | 0.42                      |
| 2×6 studs + sheathing + finishes | 0.58                      |
| Simple placeholder               | 0.5                       |
| Interior 2×4 partition           | 0.375                     |

Placeholders are fine at skeleton stage — the Drafter refines them in CAD.

## Windows

`sill` (height of the window bottom above the floor) is required on
windows. Typical: 3.0 for standard windows, 3.5–4.0 over counters. The core
rejects windows that rise above the wall height.

Set `egress: true` on the designated escape window of every sleeping room.
It draws an EGRESS callout on the floor plan and in the window schedule,
and the core rejects geometry that can never satisfy CRC R310 (sill over
44", clear width under 20", clear height under 24", gross opening under
5.7 sq ft). Net clear opening depends on the window type — the Drafter
still verifies it.

## Room areas

`rooms[].area` (square feet) is optional and STATED, never computed —
compute it yourself from the wall geometry during the interview and
confirm it with the Drafter. It renders under the room label as "329 SF".

## What the core will NOT do

- No auto-layout: rooms are labels only; walls and openings are drawn
  exactly where the config puts them.
- No inferred dimensions: missing values are validation errors, not
  guesses. Ask the Drafter.
- No compliance checks: setback distances are drawn as dimensions for the
  Drafter to verify, never approved or rejected.
