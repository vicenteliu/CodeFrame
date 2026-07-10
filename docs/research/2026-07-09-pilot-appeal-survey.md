# Pilot-Appeal Survey: What Would Make CodeFrame Compelling to CA ADU Drafters

**Date:** 2026-07-09
**Question:** Before recruiting 1–3 practicing CA ADU drafters as pilot testers (roadmap Phase 5), what features and examples would make CodeFrame most compelling — in particular, are a foundation plan and roof framing plan the right next sheets, and what must they contain?
**Method:** Four parallel research passes against primary sources — GitHub repos/READMEs, the California Residential Code and city/county plan-check checklists (PDFs fetched and read), government pre-approved ADU plan-set PDFs (downloaded, sheet indexes extracted), and first-party commercial tool sites. Every claim cites its owning source.

---

## 1. Open-source landscape: programmatic residential drawing generators

**Headline: CodeFrame's exact niche is unoccupied, and foundation/framing plan generation is an open gap across all of OSS.** The GitHub topic `floorplan-generator` has zero public repos ([github.com/topics/floorplan-generator](https://github.com/topics/floorplan-generator)); `construction-drawings` has two tiny AI-parsing repos (6 and 4 stars), not generators ([github.com/topics/construction-drawings](https://github.com/topics/construction-drawings)). GitHub API searches for "house plan dxf generator" and "foundation plan dxf" return nothing.

The adjacent space splits into four clusters:

### 1.1 BIM tools that can produce 2D documentation (interactive, not deterministic)

| Project | What it does | Showcase | Activity |
|---|---|---|---|
| [Bonsai / IfcOpenShell](https://github.com/IfcOpenShell/IfcOpenShell) (2,591★, LGPL, very active) | Plans/sections/elevations from IFC models with dimensions, tags, room labels, hatching, legends, sheet composition (SVG via Inkscape). Docs call the drawings module "incomplete and in early development" ([docs](https://docs.bonsaibim.org/guides/drawings/index.html)) | Four banner screenshots + full-project tutorials ending in drawing production ([bonsaibim.org](https://bonsaibim.org/), [tutorials](https://docs.bonsaibim.org/tutorials/index.html)) | Very active |
| [FreeCAD BIM Workbench](https://github.com/yorikvanhavre/BIM_Workbench) (merged into FreeCAD 1.0, 32,020★) | BIM authoring; README: 2D printable sheets "possible, but still not fully optimized"; exports SVG/DXF/DWG | Single banner image | Active |
| [Homemaker add-on](https://github.com/brunopostle/homemaker-addon) (159★, GPL-3.0) | Crude Blender massing → full IFC building in one click (no 2D itself; pairs with Bonsai) | Two before/after images — a very effective minimal pattern | Active (2026-05) |
| [ThatOpen engine_components](https://github.com/ThatOpen/engine_components) (680★, MIT) | Browser BIM toolkit: dimensions, floorplan navigation, DXF export | Live deployed demo apps | Very active |
| [Archipack](https://github.com/s-leger/archipack) (380★, GPL) | Parametric Blender walls/windows/roofs/trusses **with dimensioned 2D SVG export** | YouTube video | Dormant since 2020 |

### 1.2 Framing/structural generators — CodeFrame's stated gap

- [timber_framing_generator](https://github.com/a01110946/timber_framing_generator) (3★): Revit walls → complete stud/plate/header/cripple framing via Rhino.Inside. Output is 3D geometry, **not framing-plan sheets**; README has zero images.
- [COMPAS Timber](https://github.com/gramaziokohler/compas_timber) (40★, MIT, ETH Gramazio Kohler, active): timber structures and joinery — fabrication-oriented, not permit plans.
- [FreeCAD-Timber](https://github.com/j-wiedemann/FreeCAD-Timber) (19★, dormant 2019). The only literal "framing-plan-generator" repo on GitHub is empty (0★, README 404).

**No OSS tool renders framing as 2D plan sheets, and foundation plans are effectively absent everywhere** — the sole domain analog is [egress-window-permit-sketch](https://github.com/itsjwill/egress-window-permit-sketch) (1★, static SVG permit sheets with an IRC R310 **code-compliance table as a sheet** — an idea worth stealing).

### 1.3 Open-source house designs (static plan sets with strong showcases)

- [WikiHouse Skylark](https://github.com/wikihouseproject/Skylark) (238★) and especially [Microhouse](https://github.com/wikihouseproject/Microhouse) (309★): iso renders, embedded interactive Sketchfab 3D model, real DXF CNC cutting files, assembly manual, quantity/costing engine — the credibility comes from real artifacts sitting in the repo.
- [open-source-tiny-home](https://github.com/EddieOne/open-source-tiny-home) (67★): free 308 sf plans, V2 ships **framing blueprints**; framed against "$1,000+ per plan" commercial sets — the same economic anchor CodeFrame can use.
- [Scaffold](https://github.com/NicklasVraa/Scaffold) (59★): CSV + model → shopping lists, cutting diagrams, cost estimates — a direction CodeFrame schedules could extend toward.

### 1.4 ML floorplan generators (high stars, not construction-relevant)

[HouseGAN](https://github.com/ennauata/housegan) (293★) / [HouseGAN++](https://github.com/ennauata/houseganpp) (249★, live demo at houseganpp.com) / [house_diffusion](https://github.com/aminshabani/house_diffusion) (231★): bubble diagram → colored room-layout polygons; no dimensions, structure, or code content; research-frozen. [FloorplanToBlender3d](https://github.com/grebtsew/FloorplanToBlender3d) (598★) goes the inverse direction (image → 3D) but has the most showcase-rich README in the space: multiple GIFs of the script running and the result opening.

### Lessons for an attractive showcase (from the strongest/weakest READMEs)

1. **Hero image of the actual output first** — a full title-blocked plan sheet, not architecture diagrams ([Microhouse](https://github.com/wikihouseproject/Microhouse) vs. [timber_framing_generator](https://github.com/a01110946/timber_framing_generator)'s zero images).
2. **Input → output as a pair** — Homemaker's two-image "crude massing → full building" is the single most persuasive pattern seen ([homemaker-addon](https://github.com/brunopostle/homemaker-addon)); CodeFrame's version is "20-line config / one conversation → 10-sheet permit set."
3. **GIF of the generation run** — motion sells "automated" ([FloorplanToBlender3d](https://github.com/grebtsew/FloorplanToBlender3d)).
4. **Ship a complete downloadable sample set in the repo** (DXF + PDF + STEP), like WikiHouse's real cutting files ([Microhouse](https://github.com/wikihouseproject/Microhouse)).
5. **One-line economic pitch** ("companies charge a minimum of $1,000 a plan" — [open-source-tiny-home](https://github.com/EddieOne/open-source-tiny-home); "skip the $500 architect fee" — [egress-window-permit-sketch](https://github.com/itsjwill/egress-window-permit-sketch)).
6. **A hosted/live demo multiplies reach** ([houseganpp.com](https://github.com/ennauata/houseganpp), [ThatOpen demos](https://github.com/ThatOpen/engine_components)).

---

## 2. CA permit-level content: foundation plan (slab-on-grade) and roof framing plan

Primary sources fetched: CRC 2022 chapters via [UpCodes Ch.4](https://up.codes/viewer/california/ca-residential-code-2022/chapter/4/foundations), [Ch.5](https://up.codes/viewer/california/ca-residential-code-2022/chapter/5/floors), [Ch.6](https://up.codes/viewer/california/ca-residential-code-2022/chapter/6/wall-construction), [Ch.8](https://up.codes/viewer/california/ca-residential-code-2022/chapter/8/roof-ceiling-construction) and [ICC IRC 2021 R802.11](https://codes.iccsafe.org/s/IRC2021P3/chapter-8-roof-ceiling-construction/IRC2021P3-Pt03-Ch08-SecR802.11); checklists: [LA County LARUCP Residential Minimum Plan Submittal Requirements](https://dpw.lacounty.gov/bsd/lib/fp/Building/Residential/Residential%20Minimum%20Plan%20Submittal%20Requirements.pdf), [LA County ADU Step-by-Step Guide](https://pw.lacounty.gov/bsd/lib/fp/Building/Residential/Accessory%20Dwelling%20Units/ADU%20Step-by-Step-Guide.pdf), [LADBS ADU Plan Check Correction Sheet](https://dbs.lacity.gov/sites/default/files/efs/forms/pc17/adu-correction-sheet.pdf), [Sacramento County CO-06](https://building.saccounty.gov/Public%20Documents/CO-06%20Residential%20New%20Buildings%20and%20Additions%20Submittal%20List.pdf), [Morgan Hill SFD Plan Content Checklist](https://ca-morganhill2.civicplus.com/DocumentCenter/View/47577/Plan-Content-Checklist---SFD-and-TFD), [Redding SFR Plans Examiner Checklist](https://files.cityofredding.gov/Document%20Center/Departments/Development%20Services/Building/Building%20Resources%20And%20Learning/Complete%20Permit%20Application%20Packages/New%20Single%20Family%20Residential%20Checklist.pdf), [San Diego IB 400](https://www.sandiego.gov/sites/default/files/dsdib400.pdf).

### 2.1 Are these sheets explicitly required for ADUs? Yes, nearly everywhere

- **LA County:** minimum ADU submittal = architectural plans + "Structural plans (**foundation plan, framing plan**, and structural calcs, if required)" + Title 24 ([ADU Step-by-Step Guide](https://pw.lacounty.gov/bsd/lib/fp/Building/Residential/Accessory%20Dwelling%20Units/ADU%20Step-by-Step-Guide.pdf)).
- **LA City (LADBS):** "Provide the following with each set of plans: Floor plans, **Foundation plans, Framing plans**, … Construction section, Two elevations…" ([ADU correction sheet, item 5](https://dbs.lacity.org/sites/default/files/efs/forms/pc17/adu-correction-sheet.pdf)).
- **Sacramento County:** "Structural Plan (if applicable): **Foundation plan, floor & roof framing plans**, truss calculation sheets and structural details" ([CO-06, A.5](https://building.saccounty.gov/Public%20Documents/CO-06%20Residential%20New%20Buildings%20and%20Additions%20Submittal%20List.pdf)).
- **Morgan Hill / Redding:** dedicated "Foundation Plan" and "Roof Framing Plan" checklist sections ([Morgan Hill](https://ca-morganhill2.civicplus.com/DocumentCenter/View/47577/Plan-Content-Checklist---SFD-and-TFD), [Redding](https://files.cityofredding.gov/Document%20Center/Departments/Development%20Services/Building/Building%20Resources%20And%20Learning/Complete%20Permit%20Application%20Packages/New%20Single%20Family%20Residential%20Checklist.pdf)).
- **San Diego (city):** generic "Structural plans and details; Structural calculations and/or truss calculations (as applicable)" ([IB 400](https://www.sandiego.gov/sites/default/files/dsdib400.pdf)).

### 2.2 Foundation plan (slab-on-grade) — minimum content

Linework / plan view:
1. **Location of all footings, stem walls, piers, grade beams, slabs** ([Morgan Hill](https://ca-morganhill2.civicplus.com/DocumentCenter/View/47577/Plan-Content-Checklist---SFD-and-TFD); [Redding](https://files.cityofredding.gov/Document%20Center/Departments/Development%20Services/Building/Building%20Resources%20And%20Learning/Complete%20Permit%20Application%20Packages/New%20Single%20Family%20Residential%20Checklist.pdf)). No checklist prescribes linetypes — dashed hidden footing lines are drafting convention, not a sourced requirement.
2. **Full dimensions** — grid-to-grid, footing widths/lengths (Redding item "Dimensions"; LA County LARUCP item 12: structural plans "fully dimensioned").
3. **North arrow** (Redding).
4. **Post pads / spread footings at point loads** ("Main posts and correspondent spread footings" — Redding item 7).
5. **Hold-down locations on the foundation plan**, keyed to the shear/braced-wall schedule (Redding item 5; Morgan Hill "Hold-down anchor size and locations"; LADBS J.12 "Show hold-down locations on the foundation plan").
6. **Section/detail cut callouts** to typical and specific details on separate sheets (Redding item 6; LA County item 12).
7. **Bearing-wall shading/tagging** (Redding item 4) and **stepped footings** where ground slopes >10:1 (Redding, citing CRC R403.1.5).

Annotations / schedules / notes:
8. **Anchor bolts:** min 1/2"-dia, **max 6 ft o.c.** (not 7 ft — the "7" is the 7-inch min embedment), ≥2 per plate section, one bolt ≤12" and ≥7 bolt diameters from each plate end, middle third of plate ([CRC R403.1.6 via UpCodes](https://up.codes/s/foundation-anchorage)); 3"×3"×0.229" plate washers on braced wall lines in SDC D0–D2 ([CRC R602.11.1](https://up.codes/viewer/california/ca-residential-code-2022/chapter/6/wall-construction); Redding restates both).
9. **Footing size/depth:** Table R403.1(1) — 12" min width × 6" min thickness for one-story light-frame on 1,500–3,000 psf soil; bottom ≥12" below undisturbed grade (R403.1.4) ([CRC Ch.4](https://up.codes/viewer/california/ca-residential-code-2022/chapter/4/foundations)); LADBS J.4 requires dimensioned foundations + embedment depth shown.
10. **Slab:** min 3-1/2" thick (CRC R506.1); reinforcement size/spacing/location callouts (Morgan Hill; LA County item 12). Footing rebar in SDC D0–D2: one #4 top of stem wall, one #4 near bottom of footing; #4 verticals @ 4 ft o.c. if not monolithic (CRC R403.1.3/.1.3.1).
11. **Vapor retarder:** 2022 CRC R506.2.3 = **10-mil ASTM E1745 Class A**, laps ≥6", over a 4" base course ([CRC Ch.5](https://up.codes/viewer/california/ca-residential-code-2022/chapter/5/floors)). Jurisdictions vary — LADBS correction sheet still says 6-mil ([J.1](https://dbs.lacity.gov/sites/default/files/efs/forms/pc17/adu-correction-sheet.pdf)), Redding amends to 15-mil — so **make this note a jurisdiction parameter, default 10-mil**.
12. **Schedules + notes blocks:** hold-down, anchor-bolt, footing, wall-type schedules; foundation notes; concrete min 2,500 psi (Redding, citing R402.2; LADBS J.6).
13. **Soils note:** soil type and bearing value on plans (LA County item 18); soils report only when bearing >1,500 psf assumed or expansive/questionable soils (Sacramento CO-06 C.1).
14. UFER/grounding note appears in **no** fetched checklist as foundation-plan content (it is a CEC electrical item); underfloor vents apply only to the raised-floor alternative (1 sf/150 sf, R408 — Redding).

### 2.3 Roof framing plan — minimum content

1. **Rafter layout: location, direction arrows, spacing, span, size callouts** ("Rafter location, dimension, direction, spacing and span" — [Morgan Hill](https://ca-morganhill2.civicplus.com/DocumentCenter/View/47577/Plan-Content-Checklist---SFD-and-TFD); "size, spacing, species and grade of all framing members" — Sacramento CO-06 A.5; LADBS J.9 "size, spacing and direction of girders, floor joists, ceiling joists, rafters, beam over ___, post under ___"). Spans per CRC Tables R802.4.1(1)–(9).
2. **Ridge / hip / valley members: location, direction, size** (Morgan Hill; Redding). Ridge board ≥1" nominal, depth ≥ cut end of rafter; a supported **ridge beam** is required where ceiling joists/rafter ties don't provide continuous ties (CRC R802.3).
3. **Ceiling joists** (layout + span; heel-joint connection per Table R802.5.2(1)) and **rafter/collar ties** with locations and connection details (Morgan Hill) — rafter ties min 2x4 @ 24" o.c. max (CRC R802.5.2.2); collar ties min 1x4 @ 4 ft o.c. max, upper third of attic (CRC R802.4.6). Without ties: "trusses shall be used or engineering shall be provided" (Redding, citing R802.3 & R802.10).
4. **Headers/beams with sizes and grade/engineered-wood type** (Redding; headers per Table R602.7).
5. **Roof sheathing thickness, type, and nailing** — 8d @ 6"/12" per Table R602.3(1); panels nailed to blocking (Morgan Hill; Redding).
6. **Blocking at exterior walls** — solid block all rafters/trusses, (3) 8d toenails per block or clips (Redding, citing CRC R802.8).
7. **Connection callouts:** rafter-to-wall, rafter-to-ridge details (Morgan Hill); uplift connectors required where uplift per rafter exceeds 200 lb per Table R802.11 ([IRC R802.11 via ICC](https://codes.iccsafe.org/s/IRC2021P3/chapter-8-roof-ceiling-construction/IRC2021P3-Pt03-Ch08-SecR802.11)).
8. **Overhang dimensions, roof slopes, north arrow** (Redding; Morgan Hill puts overhang/slope on the architectural roof plan).
9. **Attic ventilation locations and calcs** — 1/150 or 1/300 (Morgan Hill; Redding, citing R806.2).
10. **If trusses:** truss layout plan stamped/reviewed by the engineer of record; CA-engineer-stamped truss calc package + acceptance letter; truss design-drawing content per CRC/IRC R802.10.1 (Morgan Hill; Redding; [Sacramento CO-06](https://building.saccounty.gov/Public%20Documents/CO-06%20Residential%20New%20Buildings%20and%20Additions%20Submittal%20List.pdf); [UpCodes R802.10.1](https://up.codes/s/irc-r802-10-1-truss-design-drawings)).

**Companion sheet plan checkers expect:** a braced-wall/shear-wall plan — panel locations, lengths, schedule (sheathing, nailing, anchor-bolt spacing, hold-down type, top-plate transfer hardware), BWL spacing ≤25 ft — with the foundation plan's hold-downs keyed to it (Morgan Hill; Redding per R602.10.1; LADBS J.10/J.16).

### 2.4 Engineering trigger vs. prescriptive path

A single-story detached ADU can normally stay prescriptive/conventional: engineering is required only when "deviating from the conventional construction provisions" (LA County LARUCP item 13; Sacramento CO-06 B.1; LADBS J.7 citing R301.1.3). LA even allows "standard notes and details" (LARUCP Wood Frame Prescriptive Provisions) in lieu of calcs — with WFPP compliance note, BWL spacing ≤25 ft, and min bracing lengths ([LA County ADU guide](https://pw.lacounty.gov/bsd/lib/fp/Building/Residential/Accessory%20Dwelling%20Units/ADU%20Step-by-Step-Guide.pdf); LADBS J.16–17). Triggers that break the prescriptive path: irregular plan, BWL >25 ft, unsupported ridge beams, steep slopes (LADBS J.19), expansive soils, and manufactured trusses (always a stamped deferred package).

Drawing standards: min 1/8" scale (1/4" recommended), sheets ≥18"×24" (24"×36" recommended) (LA County LARUCP items 3–4); Morgan Hill min 24"×36". Checklists mandate *what* appears, never linetypes; the closest sourced styling rule is Redding's wall-type "shading" and "shaded and tagged" braced-wall panels.

---

## 3. County pre-approved / standard ADU plan programs (the reference for "complete attractive example")

Four actual government plan-set PDFs were downloaded and their sheet indexes extracted.

### 3.1 Programs and what they publish

- **LA County** ([pre-approved page](https://pw.lacounty.gov/building-and-safety/adu/pre-approved)): three free county-owned plans — A: 1,200 sf/3BR, B: 1,200 sf/2BR, C: 800 sf/1BR ([Plan A PDF](https://planning.lacounty.gov/wp-content/uploads/2024/10/adu_standard_plan_a.pdf), [Plan C PDF](https://planning.lacounty.gov/wp-content/uploads/2024/10/adu_standard_plan_c.pdf)). **Plan A is a 9-sheet set:** SP-1 Site Plan (cover doubling as a template — "PLACE YOUR SITE PLAN ON THIS SHEET" — with sheet index, vicinity map, code list, design basis: roof LL 20 psf, DL 12 psf, wind 110 mph Exp. C, conventional light-frame), A1 Floor Plan, A2 Electrical Plan, A3/A4 Elevations, A5 Roof Plan/Truss Layout, A6 Sections, **S1 Foundation Plan, S2 Roof Framing**, CS-1 Min. Construction Specifications. (The sheets carry San Diego County "PDS 659" references — LA County adapted SD County's sets.)
- **LA City LADBS** ([gallery](https://dbs.lacity.gov/adu/approved-standard-plans)): ~96 designer plans (≈20 currently approved), each card = thumbnail rendering + plan number + designer + stories/BR/sf + status; 200–1,200 sf. The free city-owned **YOU-ADU** (455 sf 1BR, [page](https://dbs.lacity.gov/approved-standard-plans/you-adu)) is presented with four styling personas (In-Law, Guest, Renter, Artist) and is a **21-sheet set** ([PDF](https://dbs.lacity.gov/sites/default/files/efs/pdf/publications/adu/you-adu/YOU-ADU-Standard-Plan.pdf)): G-0.0 Cover (applicant plot plan), G-0.1–G-0.2 General/Green notes, G-0.3/G-0.4 Title 24, A-2.0 Floor, A-2.1 Roof, A-3.0/A-3.1 Elevations, A-4.0 Sections, A-5.0 Interior Elevations, A-7.0 Schedules, A-8.0/A-8.1 Details/Casework, S0.00 Structural General Notes, S0.10 Concrete Details, S0.20–S0.23 Wood Details, **S1.00 Foundation and Roof Framing Plans**, S8.1.
- **San Diego County** ([adu_plans page](https://www.sandiegocounty.gov/content/sdc/pds/bldg/adu_plans.html)): eight free plans (600–1,728 sf), "approximately 85% complete," each as 36"×24" and 17"×11" PDF — **Plans G/H also ship as CAD .dwg files** (government precedent for CAD deliverables). [Plan F](https://www.sandiegocounty.gov/content/dam/sdc/pds/bldg/adu_info/pds671_24x36.pdf) (600 sf 1BR) is 13 pages: cover/SP-1 site template → stormwater/BMP sheets → A1–A6 → **S1 Foundation Plan & Details → S2 Roof Framing & Details** → CS-1 (2 pp.). A fill-in **Dwelling Unit Checklist (pds607)** itemizes what the owner completes. The City of San Diego accepts these under AB 1332 with 30-day review ([city page](https://www.sandiego.gov/development-services/news-programs/programs/companion-junior-units)).
- **Sacramento City** ([Shelf Ready plans](https://adu.cityofsacramento.org/Shelf-ready-plans)): three free all-electric plans — Studio 367 sf, 1BR 559 sf, 2BR 747 sf. The [Studio set](https://adu.cityofsacramento.org/content/dam/cityofsacramento/adu/plan/ADU_STUDIO.pdf) is 17 sheets: T1.1 Title, C1.1 Site (applicant-provided), FSD.1 Fire Separation Details, A1.1 Code Requirements, A2.1 Floor/Dimensioned/Roof/Electrical, A3.1 Elevations, **S1.1 Foundation, Wall and Roof/Ceiling Framing Plans**, S2.1 Structural Section, SN.1 Structural Notes, SD.1 Structural Details, EN.1–EN.5 Energy (alternate sheets per HVAC choice), GB.1–GB.2 CALGreen. **Sacramento County** publishes five named models — A1 "Laurel"/A2 "Willow" 460 sf, B "Redwood" 870 sf, C "Elderberry" 1,000 sf, D "Magnolia" 1,184 sf — fully engineered incl. truss and energy calcs ([county page](https://development.saccounty.gov/us/en/building-permits-inspection/news/shelf-ready-adu-plans-now-available.html)).
- **San Jose** ([program page](https://www.sanjoseca.gov/business/development-services-permit-center/accessory-dwelling-units-adus/preapproved-adus)): 21 pre-approved **vendors** (Acton ADU, Abodu, CityPaks…), plans kept **under 750 sf so no impact fees apply**; presented as a vendor list, not downloads ([San Jose Spotlight](https://sanjosespotlight.com/san-jose-program-to-build-develop-construct-accessory-dwelling-granny-units-adus-backyard-homes-is-thriving/)).
- **Seattle ADUniverse** ([gallery](https://aduniverse-seattlecitygis.hub.arcgis.com/pages/gallery), [program summary PDF](https://www.seattle.gov/documents/Departments/OPCD/OngoingInitiatives/EncouragingBackyardCottages/OPCDPreApprovedDADUOnePageSummary.pdf)): 6–10 designer-owned pre-approved DADUs; homeowner pays a designer royalty (e.g. CAST "Cedar Cottage" 467 sf, $1,000 license per [ballardbackyardcottages.com](https://ballardbackyardcottages.com/seattle-pre-approved-dadu-plans/)); headline metric: permitting drops from **4–8 months to 2–6 weeks**.
- **Others:** HEART of San Mateo County GLADUR free plans, 400–800 sf ([heartofsmc.org](https://www.heartofsmc.org/programs/adu-center/)); Sonoma "ADU Ready" pre-*reviewed* vendor plans, ~60 → ~30-day review ([permitsonoma.org/aduready](https://permitsonoma.org/aduready)); Encinitas PRADU — eight free sets, 2 firms × 4 unit types, each with **three exterior schemes (A/B/C)** varying siding/roofing/trim, "approximately 85% complete," accepted by Encinitas/La Mesa/San Diego ([DZN Partners](https://dznpartners.com/projects/499-sf-encinitas-pradu/), [snapadu](https://snapadu.com/adu-plans/encinitas-pradu-adu-floorplan-dzn-2-bedroom-990-sf/)). Statewide: **AB 1332** required every CA local agency to run a preapproved-plans process by Jan 1, 2025 ([HCD ADU handbook update](https://ahcd.assembly.ca.gov/system/files/2025-03/adu-handbook-update.pdf)).

### 3.2 Canonical ADU permit-set sheet index (union of the extracted sets)

1. Cover/Title (project data, code list, sheet index, vicinity map, design criteria)
2. Site plan — **always an applicant-completed template sheet**
3. General notes & code requirements
4. CALGreen notes
5. Fire-separation-distance details (near-lot-line)
6. Stormwater/BMP (county sets)
7. Floor plan (dimensioned)
8. Electrical (+M/P) plan
9. Roof plan / truss layout
10. Elevations (all four)
11. Building sections
12. Interior elevations (city sets only)
13. Door/window schedules
14. Architectural details/casework
15. Structural general notes + typical concrete/wood details
16. **Foundation plan (S1)**
17. **Roof (and wall/ceiling) framing plan (S2)**
18. Structural sections/details
19. Title 24 energy sheets

**Minimum viable government-approved skeleton = the LA/SD County 10-sheet set: cover+site template, A1–A6, S1–S2, CS-1.** Every government set includes S1 and S2; none omits them.

### 3.3 Presentation patterns

1. Rendering-first gallery cards with a stat strip (sf/BR/stories/designer/status) — LADBS, ADUniverse.
2. A free government "anchor" plan beside a licensed designer catalog — YOU-ADU, LA County A/B/C.
3. Named personas / style variants resell one floor plan (YOU-ADU's In-Law/Guest/Renter/Artist; DZN's A/B/C exterior schemes; Sacramento County's tree names).
4. Explicit "what's left for you" honesty: site-plan template baked into the set, fill-in checklists, **"approximately 85% complete"** — near-identical to CodeFrame's "60–70% skeleton" framing, and quantified payoffs ($8k–14k design savings; 4–8 months → 2–6 weeks).
5. Spec tables + cost estimates live in the nonprofit/aggregator layer (e.g. [Housing Innovation Collaborative](https://housinginnovation.co/backyardhome/encinitas-1-bed-adu/)).

---

## 4. Commercial AI floor-plan / permit-drawing tools

| Tool | Positioning | What the site leads with | CodeFrame-relevant |
|---|---|---|---|
| [Maket](https://www.maket.ai/) | AI floor plans for homeowners/pros | 3-step workflow narrative, free trial; freemium ~$20/mo ([pricing](https://www.maket.ai/pricing)) | DXF/PDF/PNG export, zoning setback checks ([features](https://www.maket.ai/features)); **its own blog concedes no AI generator produces permit-review-ready drawings** ([blog](https://www.maket.ai/blog/ai-floor-plan-generator-guide)) |
| [Higharc](https://www.higharc.com/) | "Homebuilding AI for design to construction" (production builders) | Business metrics: "15% margin increase," "2 weeks from plan concept to permit," "$30M ROI"; demo gated | Closest analog: one live model → plans/BIM/CDs auto-update; "10x faster than traditional CAD line drawing"; "permit-ready drawing set… with one click" ([Studio page](https://www.higharc.com/product/studio), [blog](https://www.higharc.com/blog/the-right-platform-for-production-homebuilders)) |
| [TestFit](https://www.testfit.io/) | Real-estate feasibility/site plans | Hero demo video, customer logos, "4x faster," "6,200+ active users" | Export to Revit/AutoCAD/SketchUp/Excel/PDF is a headline feature |
| [ArchiLabs](https://www.archilabs.ai/) | Browser BIM automation with **deterministic validation** | Capability list; recruits via **pilot programs**, no public pricing | Automated sheets/annotations/schedules; DXF-to-3D; validates the pilot-recruiting model CodeFrame is using |
| [Hypar](https://hypar.io/) | Generative building "functions" platform | Interactive in-browser generator + open function marketplace ([aecmag](https://aecmag.com/ai/hypar-text-to-bim-and-beyond/), [github](https://github.com/hypar-io)) | Revit-compatible exports |
| [Snaptrude](https://www.snaptrude.com/) | "From brief to BIM" design OS | Animated hero + case studies ("4-day workflows to 4 hours") | Code/zoning analysis, Revit/Rhino export |
| [Arcol](https://arcol.io/) | Browser massing/floorplans for architects | Conversion-focused page, no metric claims | — |
| [Cove](https://cove.inc/) | "Architecture firm built around AI" | "200+ on-time projects," 12 months → 3; cost-of-delay storytelling | Consultation model, no pricing |
| [Symbium](https://symbium.com/) | "Instant permitting" (B2G) | Consumer tool: "Learn instantly if you can have an ADU on your property" — **address-search instant feasibility** ([build.symbium.com](https://build.symbium.com/)) | The killer ADU-specific hook: parcel-keyed zero-commitment demo |
| [Abodu](https://www.abodu.com/) | Prefab ADUs | "Pre-Approved Plans. Fixed Pricing." — six state-pre-approved plans 340–1,200 sf; sells skipping plan-check delay | Plan catalog as product |
| [Villa](https://villahomes.com/) | CA's leading ADU builder | Fixed plans 440–1,200 sf from ~$225k incl. permitting; **setback-aware lot-placement map** at app.villahomes.com/map ([Dwell](https://www.dwell.com/article/villa-prefab-california-adu-builder-backyard-homes-0d286d46)) | In LA's standard-plan catalog ([LADBS listing](https://dbs.lacity.gov/approved-standard-plans/villa-homes)) |
| [Samara](https://www.samara.com/) | Premium prefab ("Backyard") | Lifestyle photography + 3D configurator, from $152k | — |
| Cottage | ADU design/permit marketplace | **Dead** (cottage.co HTTP 525; acquired by RenoFi per [LinkedIn](https://www.linkedin.com/company/cottageadus)); legacy = [LADBS standard plans](https://dbs.lacity.gov/approved-standard-plans/cottage) | Cautionary: standalone drafting-marketplace model didn't survive |
| [PermitFlow](https://www.permitflow.com/) | Permit *paperwork* automation | "Construction's AI Workforce," 7K+ AHJs, "2.5X faster approvals" | Adjacent, not drawing generation |
| [Chief Architect](https://www.chiefarchitect.com/products/home-design/) | Established resi CAD, $1,995/yr | **Gold-standard showcase:** [samples gallery](https://www.chiefarchitect.com/products/samples.html) with complete downloadable sample PDF plan sets + project files + 3D models + video walkthroughs | Claims automatic stick/truss **framing**, auto materials lists and schedules — the incumbent feature bar |
| [SoftPlan](https://ww2.softplan.com/) | "A better way to draw houses," ~$169/mo | Trial-first funnel | Working drawings + dimensioning, auto materials lists |
| AutoCAD Architecture | Toolset upsell | Markets almost entirely on a productivity study: "**75% time saved on elevations**, 65% sections, 71% sheet layouts" ([study](https://autocadresources.autodesk.com/architecture/architecture-toolset-productivity-study)) | Task-level time metrics as the whole pitch |

### Demo/showcase patterns that work

1. **Publish real, complete output** — downloadable full sample plan sets are the strongest proof for drafters (Chief Architect samples; Abodu/Villa plan catalogs).
2. **Quantify time-to-deliverable per task**, not vaguely ("75% faster elevations"; "2 weeks from plan concept to permit"; "4x faster").
3. **Short animated GIF/clip of a change propagating into drawings**, not a long hero film (Higharc Studio, Snaptrude).
4. **"Fits your existing workflow" as a headline** — DXF/Revit/AutoCAD export fidelity is the credibility test for drafters (TestFit, Maket).
5. **Instant parcel-keyed demo is the ADU-specific hook** (Symbium, Villa's map).
6. **Honesty about the permit line differentiates** — only enterprise Higharc claims one-click permit-ready; Maket disclaims it; "deterministic skeletons a CA drafter finishes" occupies open ground, and ArchiLabs shows deterministic-validation + pilot-program recruiting is a live playbook.

---

## Implications for CodeFrame

### Candidate features, ranked by appeal-to-drafters vs. build cost

1. **Foundation plan sheet (S1) — highest appeal, low-to-moderate cost. Build it.** Explicitly required by LA County, LADBS, and Sacramento ADU checklists (§2.1); present in every government pre-approved set (§3.2); absent from all of OSS (§1.2). For a rectangular single-story slab-on-grade ADU, the linework derives from the existing footprint (perimeter footing offset from `exterior_wall_thickness`), plus config-driven anchor-bolt/hold-down callouts, footing/slab schedule, detail-cut placeholders, and a foundation-notes block (concrete 2,500 psi, vapor retarder as a jurisdiction parameter defaulting to 10-mil per 2022 CRC R506.2.3). §2.2 is effectively the sheet spec.
2. **Roof framing plan sheet (S2) — highest appeal, moderate cost. Build it.** Same checklist/government-set evidence; the schema's `Roof` (type/`ridge_axis`/slope/overhang) already determines rafter direction for the drawn gable case. Needs new config fields (rafter size/spacing/species-grade, ridge member, connector callouts) rendered as layout arrows + callouts + notes per §2.3. Support both stick-framed (rafter + ceiling-joist callouts) and trussed (layout + "deferred submittal, stamped truss package" note) variants — government sets show truss layouts on A5 with S2 framing.
3. **Structural general-notes sheet (SN.1/S0.00) — medium appeal, very low cost.** Same machinery as the existing general-notes sheet; makes S1/S2 read as a credible structural package (every city set carries one, §3.2). Include the LA WFPP compliance note option (§2.4).
4. **Code-compliance table as a sheet — medium-high appeal, low cost, distinctive.** Requirement vs. provided vs. PASS with CRC citations (egress, ceiling height, smoke/CO, attic vent 1/150). Seen only in [egress-window-permit-sketch](https://github.com/itsjwill/egress-window-permit-sketch); no competitor does it; CodeFrame already computes room areas and egress callouts.
5. **Electrical plan (A2) — medium appeal, moderate cost.** In every government set as its own sheet (or combined, per Sacramento). Fixture/outlet symbols from the existing fixtures machinery; defer detailed circuiting.
6. **Braced-wall/shear-wall plan — high appeal, high cost. Defer, but leave hooks.** Checkers expect hold-downs on S1 keyed to a braced-wall schedule (§2.2 item 5, §2.3 companion); full R602.10 bracing-length math is a large feature. V1: accept explicit hold-down locations in the config and emit the schedule skeleton.
7. **Material takeoffs/cost estimates, IFC export, interactive 3D embeds — low priority.** Nice showcase garnish (Scaffold, WikiHouse, §1.3) but not what plan checkers or the pilot gate need.
8. **Title 24 / CALGreen sheets — do not build.** Energy compliance comes from consultant-generated documents (Sacramento ships alternate EN sheets per HVAC choice); at most reserve sheet numbers in the index.

### Which examples would make compelling showcases

- **Model the flagship example on the LA/SD County 10-sheet skeleton** (cover+site template, A1–A6, S1–S2, CS-1) — the leanest officially-approved sheet list (§3.2). With S1/S2 added, CodeFrame's output maps 1:1 onto a government-approved set; that comparison ("same sheet index as LA County Standard Plan A") is the single most persuasive artifact for a CA drafter.
- **Ship 2–3 named example configs mirroring the government catalogs:** a ~400 sf studio (cf. Sacramento Studio 367 sf, HEART 400 sf), a ~750 sf 1BR (San Jose's <750 sf no-impact-fee threshold), and an ~800–1,000 sf 2BR (LA County Plan C is 800 sf) — with memorable names, following the persona/tree-name pattern (§3.3).
- **README: hero image = one full title-blocked PDF sheet; input→output pair** (20-line config → 10-sheet set contact sheet); **GIF of `python -m codeframe generate` producing the set**; a committed downloadable sample DXF+PDF+STEP set (§1 lessons; Chief Architect samples pattern).
- **Lead with task-level numbers and the honesty line:** "a plan-check-shaped 10-sheet skeleton in N seconds — approximately the same '85% complete' the counties themselves publish, you finish and stamp." The government programs' own "approximately 85% complete" language (§3.1) is external validation of the skeleton pitch; quantified time claims should be per-sheet, AutoCAD-study style (§4).
- **Longer-term hook:** a parcel-keyed instant demo (Symbium/Villa pattern, §4) — out of v1 scope but the strongest ADU-specific acquisition device observed.

### Two corrections to internalize before building S1/S2

- Anchor bolt max spacing is **6 ft o.c.** (CRC R403.1.6) — 7" is the embedment depth, not spacing.
- The 2022 CRC vapor retarder is **10-mil ASTM E1745 Class A** (R506.2.3), but LADBS still writes 6-mil and Redding amends to 15-mil — make it a jurisdiction parameter with a 10-mil default.

---

*Reference copies of the downloaded government plan sets (LA County Plans A/C, SD County Plan F, LADBS YOU-ADU, Sacramento Studio) were kept in the session scratchpad, not committed.*
