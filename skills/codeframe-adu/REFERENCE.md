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
- `site.north_rotation` (degrees counterclockwise from plan-up) orients the
  site plan's north arrow. Ask the Drafter; without it no arrow is drawn.
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

## Section cuts

`sections` is a top-level list of transverse building sections:
`{"name": "A", "at": <station>}`. The cut plane is perpendicular to the
roof ridge at that station along the ridge axis, looking toward the rising
coordinate (rear for a `y` ridge, right for an `x` ridge). Each cut adds a
`section_<name>.dxf`, a sheet in the PDF, and a dashed, bubbled cut line
on the floor plan. Gable roofs only (like the rest of the engine).

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

## Foundation (sheet S1)

`building.foundation` is optional; when present, `generate` adds a
slab-on-grade foundation plan (`foundation_plan.dxf`, PDF sheet S1.0).
`footing_width`/`footing_depth` in feet (typical 1.0 x 1.0; the footing is
drawn centered under the exterior walls). `slab_thickness_inches`
(default 3.5) and `vapor_retarder_mil` (default 10 per 2022 CRC R506.2.3;
ask which jurisdiction — LADBS writes 6-mil, Redding 15-mil) feed the
notes. `hold_downs` are explicit labeled points ({at, label} — e.g. HD1 at
braced-wall ends); sizes/models stay the drafter's. Mark load-carrying
interior walls `"bearing": true` to draw their footing band. CodeFrame
never sizes structure — all values are the Drafter's inputs.

## Fixtures

`fixtures` is a top-level list of plumbing/appliance symbols:
`{"type": ..., "at": {x, y}, "rotation": 0|90|180|270}`. `at` is the
symbol's CENTER; at rotation 0 the fixture's back (tank, faucet, wall
side) faces +y, and rotation spins it counterclockwise — so a toilet
against the rear wall is rotation 0, against the left wall 90. Types and
standard footprints (ft): toilet 1.5x2.33, lavatory 1.6x1.3, bathtub
5x2.5, shower 3x3, kitchen-sink 2.75x1.83, range 2.5x2.17, refrigerator
3x2.5, washer-dryer 4.5x2.25, water-heater d=2. `counter` instead
requires an explicit `size: {width, depth}`. Place them clear of walls —
CodeFrame draws exactly where the config says and checks only that the
center is inside the footprint.

## Detectors

`detectors` is a top-level list of smoke/CO alarms at explicit
building-local points: `{"type": "smoke" | "co" | "combo", "at": {x, y}}`.
Placement is the Drafter's decision (CRC R314/R315: sleeping rooms,
outside sleeping areas, each story) — CodeFrame draws the symbol (circle
with S / CO / S/CO) exactly where the config puts it, nothing more.

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
