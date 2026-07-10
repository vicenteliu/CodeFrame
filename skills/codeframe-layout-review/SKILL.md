---
name: codeframe-layout-review
description: Review a CodeFrame Project Config's layout before drawings go out. Run after authoring or editing any config — catches doorways blocked by fixtures, fixture clashes, fixtures poking through walls, and missing egress designations, then walks a visual render check. Use before delivering, publishing, or screenshotting any CodeFrame output.
---

# CodeFrame Layout Review

The Deterministic Core draws exactly what the config states — it will
happily put a bathtub across a doorway (it did once, and the bad sheet
shipped publicly). Layout judgment is the Agent Layer's job. This skill is
that judgment, made mechanical. **No CodeFrame drawing goes to the Drafter,
the repo, or a screenshot without passing both gates below.**

## Gate 1 — mechanical checks

```bash
python skills/codeframe-layout-review/check_layout.py <project-config.json>
```

Exit 0 = clean. Any WARNING must be fixed in the config (or explicitly
accepted by the Drafter) before proceeding. It catches:

- **Door swing zones** overlapping a fixture (both exterior and interior
  doors), and **landing sides** blocked within 1.5 ft of the opening.
- **Fixture-on-fixture** overlaps.
- **Fixtures poking through interior walls** (outside a doorway).
- **Fewer egress windows than sleeping rooms** (rooms named Bedroom*/Studio).

The checks are advisory geometry, not code compliance — clearances like
CRC's 21 in fixture clearances stay the Drafter's.

## Gate 2 — render and look

```bash
python skills/codeframe-layout-review/check_layout.py <config.json> --render review.png
```

Open `review.png` and verify with your own eyes, in this order:

1. **Walk the plan**: from the entry door, trace a path into every room.
   No room may require passing through a fixture or another private room
   (bath-through-bedroom is acceptable only for that bedroom's ensuite;
   laundry-through-bath only when stated in the notes).
2. **Every door**: leaf and arc land on clear floor; the door does not
   swing into a fixture, a window, or another door's swing.
3. **Every fixture sits inside its room** and against a wall where its
   back should be (toilets, sinks, ranges face into the room).
4. **Labels and tags legible**: room names, areas, schedule tags, and
   detector symbols don't sit on top of walls, fixtures, or each other.
5. **Egress**: each sleeping room has its EGRESS callout visible.

If anything looks wrong, fix the config, regenerate, and re-run both
gates. Only a clean pass earns delivery.

## When this runs

- After the codeframe-adu interview writes or edits a config — before
  telling the Drafter the set is ready.
- Before committing any example config or regenerating README/showcase
  images from one.
- After any bulk edit that moves walls, doors, or fixtures.
