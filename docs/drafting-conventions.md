# Drafting Conventions Reference

Distilled 2026-07-11 from eleven real small-residential drawing sets (ADU
permit sets, professional CD sheets, hand-drawn structural sheets, and
app-generated plans) collected as visual references. Each rule is tagged
with CodeFrame's status:

- **HAVE** — the engine already does this.
- **ADOPT** — worth implementing next; concrete and in scope for v1.x.
- **LATER** — real convention, but out of scope until the roadmap reaches it.

## 1. Walls in plan

- Cut exterior walls read as solid dark poché (filled), not parallel lines.
  This is the single strongest "professional set" signal in every reference.
  Interior partitions are poché'd too, slightly lighter or same. **HAVE**
  (solid HATCH between the two wall faces on plan and section cut walls;
  the face lines stay for DXF editing).
- Openings break the poché completely; jamb lines cap the wall ends at each
  opening. **HAVE** (jamb lines exist; poché break comes with poché).
- New vs existing (remodels): existing walls hollow/light, new walls
  poché'd, `(E)` / `(N)` prefixes on labels, demolition dashed. CodeFrame
  draws new detached structures only, so this applies just to the site plan,
  which already draws existing structures on a lighter layer. **HAVE**
  (record the `(E)`/`(N)` vocabulary for future remodel support).

## 2. Doors and windows in plan

- Door = leaf open 90° + quarter-circle swing arc. **HAVE**
- Window = thin line(s) centered in the wall thickness across the opening.
  References often draw 2–3 parallel lines (frame + glass); one is
  acceptable at skeleton stage. **HAVE** (single line; multi-line is polish).
- Bifold/closet doors drawn as chevrons, sliders as two offset leaves.
  **LATER** (v1 swings only; schema has no door style field).
- Inline size callouts are a legitimate alternative to schedule marks on
  small plans: `D-30"x80"`, `W-5'x5' SLIDING`, or the WWHH shorthand
  (`4040 EGRESS`, `4010 XO`). CodeFrame uses circled marks + schedules,
  which is the more formal convention. **HAVE** (keep marks; no change).

## 3. Dimensions

- Feet-inches with hyphen (`9'-3"`), architectural tick marks, text above
  the line, aligned reading from bottom/right. **HAVE** (ARCHTICK,
  dimtad=1, dimtih/dimtoh=0; dimension text is overridden to feet-inches
  at 1/16" precision — ezdxf's renderer would otherwise write decimal
  feet).
- Tiered dimension strings, inner to outer on each side of the plan:
  1. openings/segments (corner → jamb → jamb → corner),
  2. wall/grid segments,
  3. overall.
  The references dimension **all four sides**; overall dims appear on at
  least two adjacent sides. **HAVE** (tier 1 per wall with openings;
  overall always on front + left, plus every other side that carries an
  opening chain, one tier further out).
- Interior room sizes dimensioned inside the room (`10'-6"`, `13'-2"`)
  when the plan has space. **LATER** (needs room extents, which the schema
  doesn't model — rooms are label points only, per ADR-0002).
- Fixture-locating dims (toilet centerline to wall, etc.) appear in permit
  sets for clearance proof. **LATER** (layout-review skill covers
  clearances conversationally instead).

## 4. Text and labels

- All annotation text is UPPERCASE. **HAVE**
- Room names: large text, underlined, area in smaller text beneath
  (`BEDROOM` / `162 SF`). **HAVE** (uppercase, 1.5× annotation height,
  underlined, stated area beneath).
- Narrow or crowded features get a leader (line + arrowhead) from a label
  placed in clear space: `WASHER/DRYER →`, `KITCHEN →`. **HAVE** (the
  `callouts` config list — `{text, at, target}`, explicitly placed per
  no-auto-layout; the leader tail is `at`, the arrowhead lands on
  `target`).
- Plan-note convention: short imperative all-caps notes placed near their
  subject (`PROVIDE BLOCKING AT TOILET WALLS AND SHOWER`, `LANDING SLOPE
  2%`). The schema's `notes` list currently renders only on the notes
  sheet. **LATER** (placed notes = `{text, at}`; useful, small schema
  addition).
- Finish-floor elevation callouts in boxes on the plan: `F.F. = 0.00`,
  `F.F. = +9"`. Matters for conversions and split levels; a flat new slab
  is implicitly 0.00. **LATER**

## 5. Tags, marks, and callouts

- Opening marks: text in a circle pointing to a schedule row. **HAVE**
- Richer window tags carry size + glazed area (`4'-0" x 3'-11 1/2",
  GLAZED AREA 12 SF`). Glazed area feeds CRC R303 light/vent (8% floor
  area glazing, 4% openable) and Title 24 checks — plan checkers look for
  it. **HAVE** (AREA column in the window schedule; R303 light and
  ventilation rows in the code-compliance table with total glazing
  computed and verdicts BY DRAFTER — the per-room split is not derivable
  from the config).
- Keynote hexagons keyed to a legend (wall types, assemblies). **LATER**
- Shear-wall / braced-panel tags: number in a triangle at the panel, keyed
  to a schedule with a stated length (`⟨1⟩ 10'-6"`). Pairs with §9.
  **LATER**

## 6. Section, grid, and detail markers

- Section marker = split bubble (view letter over destination sheet
  number, e.g. `B` / `A4.0`) with a **filled triangle** showing the view
  direction, at both ends of the cut line. **HAVE** (`section_sheet_number`
  is the single source of truth shared with the PDF composer; the triangle
  points toward the rising ridge-axis coordinate, matching the section
  view).
- Detail marker = circled number + underlined title + scale under the
  detail (`1 — EXTERIOR FOOTING`). **HAVE** (sheet S3 typical details;
  numbers assigned in drawing order).
- Structural grid: lettered bubbles one way, numbered the other, on
  dash-dot centerlines extended past the building. Overkill for a
  single-room ADU; standard above ~2 grid lines. **LATER**

## 7. View titles and sheet composition

- Every view carries an underlined title with the scale directly beneath:
  `FLOOR PLAN` / `SCALE: 1/4" = 1'-0"`. **HAVE** (uniform underlined
  title under every scaled view; the PDF composer probes extents, picks
  the scale, then rebuilds the view with the scale written under the
  title — standalone DXF output has no paper scale and omits the line).
- North arrow on the floor plan as well as the site plan, near the title.
  **HAVE** (drawn beyond the plan's top-right corner when
  `north_rotation` is set).
- One sheet may carry several related views (elevations 2×2, plan +
  foundation, etc.), sharing one scale per sheet. **HAVE** (elevations
  sheet).
- Title block: a bottom strip is acceptable; fuller sets use a right-edge
  vertical block with firm/project info, project number, date, and sheet
  index. **LATER** (bottom strip is fine for a skeleton; revisit for
  pilot feedback).
- `PRELIMINARY — NOT FOR CONSTRUCTION` stamp on every sheet. **HAVE**

## 8. Schedules and tables

- Door/window schedules with MARK / size / type / qty / remarks. **HAVE**
- Area summary table (per-room SF + total) near the plan or on the notes
  sheet; the references from consumer tools always include it and plan
  checkers use it for ADU size limits. **HAVE** (stated `rooms[].area`
  values + total on the general-notes sheet; skipped when no areas are
  stated).
- General-information table (project name, floor, unit, scale). Covered
  by the title block + project data block. **HAVE**

## 9. Structural sheet conventions

- Foundation plan: footings dashed under walls (hidden-line), hold-downs
  as solid triangles with labels, all-caps notes block beside the plan.
  **HAVE**
- Shear wall schedule table: TYPE | MATERIAL | EDGE NAILING | FIELD
  NAILING | BOUNDARY NAILING | ANCHOR BOLTS, keyed to triangle tags on
  the plan (§5). The values are engineering — CodeFrame could draw the
  empty table skeleton with BY DRAFTER cells. **LATER** (roadmap:
  braced-wall support).
- Footing, connection, and header details with earth hatch and rebar
  callouts. **HAVE** (sheet S3, fixed 1" = 1'-0" scale: slab-edge footing,
  interior bearing footing, eave connection, ridge connection — rafters
  only, trusses defer to the stamped package — and typical header. Earth
  hatch is drawn as explicit 45° lines, not a HATCH pattern: ezdxf's
  pattern renderer emits lines in nondeterministic order and breaks
  byte-identical PDFs. All connector models and member sizes BY DRAFTER.)
- Roof slope marker on elevations and sections: right triangle with the
  run (12) and rise numbers at the roof line. **HAVE** (triangle riding
  the left roof slope on gable-end elevations and sections).

## 10. Electrical (future sheet)

From the hand-drawn reference set: receptacle symbols on walls, GFI/WP
labels, 240V callouts at appliances, switch legs as curved dashed lines,
ceiling fixtures, `1 HR RATED FIREWALL` hatch where required, dryer vent.
**LATER** (no electrical layer in v1; detectors only).

## 11. 3D views

- A `3D MODEL RENDERING` sheet: four axonometric/perspective views in a
  2×2 grid, one from each corner. CodeFrame already builds the massing
  model (STEP/STL). **LATER** (render four axon views to a sheet via the
  FreeCAD path; nice pilot-appeal win, not a permit requirement).

## Adoption status

All nine adoption candidates from the 2026-07-11 review are implemented
(wall poché; view titles + scale + floor-plan north arrow; overall dims on
opening-bearing sides; split section bubbles with sheet reference and
direction triangle; room-name hierarchy; window glazed-area column + R303
rows; area summary table; `callouts` leaders; roof slope triangles), plus
one found during review: dimension text now renders feet-inches instead of
ezdxf's decimal feet.

A second pass (2026-07-11) added the typical-details sheet (S3.0): detail
markers per §6 and the footing / eave / ridge / header details per §9,
prompted by the gap between the skeleton and the construction details every
reference set carries.

Everything tagged LATER stays out until its roadmap line item; none of it
changes the two-layer architecture or the no-auto-layout rule.
