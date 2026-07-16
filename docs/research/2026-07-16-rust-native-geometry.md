# Rust-Native Geometry: Should CodeFrame's 3D Side Leave Headless FreeCAD?

**Date:** 2026-07-16
**Question:** Should CodeFrame's 3D/massing side move off headless FreeCAD, and is a native-Rust geometry kernel a realistic destination in 2026? Specifically: what happened to Fornjot, is truck real, are the OCCT bindings usable — and does the reframing "our pain is the GUI-app-as-library layer, not C++, so bind OCCT directly" survive contact with evidence?
**Method:** Primary sources only — repo source code read directly (Fornjot, truck, opencascade-rs, cadrum, OCCT, FreeCAD), the OCCT/FreeCAD/opencascade-rs issue trackers and PR diffs, crates.io and PyPI release metadata (including unpacking published `.crate` tarballs to read the OCCT version they actually vendor), official specifications, and Hanno Braun's own shutdown post. Where a README and the source disagreed, the source won; where a doc comment and the code disagreed, both are reported. Claims about determinism and failure modes were tested empirically on this machine (FreeCAD 1.1.1 / OCCT 7.8.1, and OCCT 7.9.3 in-process via `cadquery-ocp`, macOS arm64); those runs are labelled **[measured]**. Every claim cites its owning source.

---

## 1. Fornjot: the author spent six years on exactly this question and called it

**Headline: Fornjot is archived, and its author's post-mortem does not blame Rust, the math, or C++ interop. It blames project management.** The repository was archived 2026-06-19. The README's first line, verbatim ([README.md](https://github.com/hannobraun/Fornjot/blob/main/README.md)):

> **⚠⚠⚠ This project has been shut down. Its goals were never reached. The rest of this README has been left as it was, for posterity. ⚠⚠⚠**

The Status section, verbatim (same file):

> "Fornjot's mainline code (i.e. what is available at the top level of this repository, specifically in the [`crates/` directory](crates)) has not been developed in over a year, in favor of [a series of experiments](experiments). … Both the mainline code and the more advanced experiments are usable for simple very models (see [`models/` directory](models), for the mainline code). **Currently, Fornjot lacks the features for anything more advanced, making it unsuited for real-world use cases.**"

Last release was v0.49.0 (2024-03-21); 2.6k stars.

### 1.1 The retrospective, in his words

The post-mortem is [**Shutting Down Fornjot**](https://archive.hannobraun.com/fornjot/blog/shutting-down-fornjot/), posted 2026-06-19 (the site has moved to `archive.hannobraun.com`; `fornjot.app` 308-redirects there). It opens:

> "Fornjot is ending; unfinished, incomplete. This is not what I wanted, not why I started this project. But it is the decision I have made."

The trigger was sponsorship ethics plus a time estimate:

> "My work was supported by sponsors. **I couldn't justify taking their money, if I didn't believe that I was on a path to create something meaningfully different** (and thus in some ways better) than what's already available."
>
> "It became clear to me that under current conditions, **it would have easily taken another 2-3 years to put the foundation in place to even start delivering such value.** After already being at it for almost 6 years, I realized that I couldn't commit to that. It's too much. **I no longer have it in me.**"

He dates the first commit to **2020-07-30** — so ~6 years to a shutdown without a usable kernel.

His own "Mistakes I Made" section names five causes, and the emphasis is worth noting because it is *not* what you would predict:

| His stated mistake | His words |
|---|---|
| **Extrapolating from early success** | "When I switched to boundary representation, that showed promise, and I expected linear progress from there. That linear progress never materialized. Instead, **I ran into a cliff.** Discovering in so many different ways why CAD kernels, specifically b-rep kernels, are considered hard." |
| **Seeking sponsorship too early** | "I was still on my way towards creating something useful. **Instead of selling a product, I had sold a dream.** … I don't intend to ever sell a dream again, at least not without an actual product to deliver alongside." |
| **Sticking to incremental improvements** | "As I tried to scale that cliff I had run into, I limited myself to incremental improvements. … Instead of convincing myself that a new idea was promising, then spending a long time implementing it in small steps, **I should have been prototyping. All the time.**" |
| **Responding to crisis with half-measures** (he calls this the single cause) | "Each time, I had exactly two reasonable options: continue with full commitment or quit right then and there. I did neither. And **if I had to trace back the project's failure to a single cause, that would be it.**" |
| **Allowing my vision to become muddled** | "An application can be focused. **A CAD kernel is a generic piece of infrastructure, with many use cases to consider.** … Something can be a kernel, a library, but still focus on specific use cases. Be a tool instead of a building block." |

His conclusion:

> "So there we have it. **An overambitious project, addled by mistakes at almost every turn.** … CAD kernels are notoriously difficult, but that's only a partial excuse."

**What this does and doesn't establish.** He explicitly declines to blame the math — "CAD kernels are notoriously difficult, but that's only a partial excuse" — and the one technical claim he does make is the "cliff" after b-rep showed early promise. He never names surface-surface intersection, robustness, or tolerance handling as the specific wall. **If you want a first-hand account of *which* math broke a from-scratch Rust b-rep kernel, this post does not contain it.** What it establishes is the *cost*: ~6 years, sponsor-funded, full-time-ish for stretches, and by his estimate still 2-3 years from a foundation that could start delivering value.

One line is directly load-bearing for CodeFrame, because it is the road not taken: **"(And building an application on top of an existing kernel was an option that never appealed to me.)"** — his framing, in parentheses, as a matter of appeal, not feasibility. CodeFrame is an application. The option he found unappealing is the one CodeFrame already took.

### 1.2 The "ticks only b-rep" claim — unverified as stated, but true in substance

**I could not verify the Reddit comment.** Reddit is not fetchable by this agent (`WebSearch` rejects the domain; `WebFetch` returns "unable to fetch"). I cannot confirm the wording that against "b-rep + booleans + STEP export" Fornjot ticks only "b-rep", nor the aside that "b-rep" can mean very much or very little. **Treat that quote as unsourced.**

The *substance* checks out against the repo, which is a better source anyway:

- **Booleans: absent from mainline.** `crates/fj/src/core/` contains `operations/sweep/` and `algorithms/intersect/`, but `intersect/` holds only `mod.rs` and `ray_segment.rs` — ray casting, not solid booleans. There is no union/subtract/intersect module.
- **STEP export: absent, and the export API is mesh-based.** [`crates/fj/src/export/mod.rs`](https://github.com/hannobraun/Fornjot/blob/main/crates/fj/src/export/mod.rs) has the signature `pub fn export(triangles: impl IntoIterator<Item = Triangle<3>>, path: impl AsRef<Path>)` and documents: *"Currently 3MF & STL file types are supported."* Zero occurrences of "step". The exporter consumes **triangles** — a tessellation — so even the b-rep it does have does not reach the file.
- `fj-export` as a standalone crate is deprecated: *"This library has been deprecated. Its contents have moved into [`fj`]."*

So for CodeFrame's requirement list — b-rep with booleans, exported as STEP — Fornjot supplies the first third, and its export path is meshes, which ADR 0003 already rejected ("drafters' CAD tools need STEP, not tessellated meshes").

---

## 2. truck: alive, genuinely engineered, and documents itself out of CodeFrame's use case

[ricosjp/truck](https://github.com/ricosjp/truck) — 1,512★, Apache-2.0, **not** archived, last push **2026-07-06** (10 days before this note). It is the healthiest Rust b-rep project in existence. It is also, by its own documentation, unable to do what CodeFrame needs.

### 2.1 Maintenance: active repo, stalled releases, one human

| Signal | Value |
|---|---|
| Last push | 2026-07-06 ([repo](https://github.com/ricosjp/truck)) |
| GitHub releases | **none** (releases API returns `[]`) |
| Last crates.io publish | **2024-09-20** for every core crate — `truck-modeling` 0.6.0, `truck-topology` 0.6.0, `truck-geometry` 0.5.0, `truck-stepio` 0.3.0, `truck-shapeops` 0.4.0 ([truck-stepio](https://crates.io/crates/truck-stepio), [truck-shapeops](https://crates.io/crates/truck-shapeops)) |
| Commit mix | Recent history is dominated by an automated `cargo upgrade` bot; substantive commits are almost entirely one person, Yoshinori Tanimura ([commits](https://github.com/ricosjp/truck/commits/master)) |

**~22 months with no published release** while the repo stays busy. Depending on truck means depending on a git revision, not a release. The bus factor is one.

### 2.2 Booleans: real, but only for transversal intersections — which excludes CodeFrame's wall shell

`truck-shapeops` exposes exactly two boolean entry points, `and` and `or` ([`transversal/integrate/mod.rs`](https://github.com/ricosjp/truck/blob/master/truck-shapeops/src/transversal/integrate/mod.rs)); there is no `not`/subtract — subtraction is `and(a, b.not())`, per the crate's own [`punched-cube-shapeops` example](https://github.com/ricosjp/truck/blob/master/truck-shapeops/examples/punched-cube-shapeops.rs). Both return `Option<Solid>`: failure is `None`, with no diagnostic.

The crate's own status note, verbatim ([`truck-shapeops/src/lib.rs`](https://github.com/ricosjp/truck/blob/master/truck-shapeops/src/lib.rs)):

> "## Boolean Operation
>
> **Boolean operations are currently supported only for shapes where faces intersect transversally. Cases where faces are tangent to each other are not yet supported.** Furthermore, performance optimization using BSP (Binary Space Partitioning) or similar methods remains a future task."

The implementation module is literally named `transversal/`.

**This is disqualifying for CodeFrame's first solid, not a distant edge case.** [`src/codeframe/massing.py`](../../src/codeframe/massing.py) builds the exterior wall shell as an outer box cut by an inner box spanning the identical z-range:

```python
shell_cuts = [Box((thickness, thickness, 0.0),
                  (width - 2*thickness, depth - 2*thickness, height))]
solids = [Solid("walls", Box((0.0, 0.0, 0.0), (width, depth, height)), tuple(shell_cuts))]
```

The cut box's bottom (`z=0`) and top (`z=height`) faces are **coplanar** with the outer box's — that coplanarity is what makes it a shell open top and bottom, i.e. it is intrinsic to the model, not an accident to be nudged away. Coplanar faces are the tangency case truck says it does not support. (CodeFrame's *opening* cuts are fine: `CUT_CLEARANCE = 0.1` deliberately pokes them past both wall faces — the code comment says so — making those transversal.) **[measured]** OCCT handles the same coplanar shell cut correctly, returning 1 solid.

### 2.3 `truck-stepio` writes STEP — but its own docs say not for boolean results

The crate description says "Reads/writes STEP files from/to truck", and the writer is real ([`truck-stepio/src/out/`](https://github.com/ricosjp/truck/tree/master/truck-stepio/src/out)). But the module docs, verbatim ([`truck-stepio/src/lib.rs`](https://github.com/ricosjp/truck/blob/master/truck-stepio/src/lib.rs)):

> "# Current Status
>
> It is possible to output data modeled by truck-modeling. **Shapes created by set operations cannot be output yet.** Input will come further down the road."

That is precisely CodeFrame's pipeline — boolean → STEP.

**Adversarial check, because this doc comment looks stale.** The CHANGELOG records "step output of open shell, worlds including several models, and `IntersectionCurve`" under **v0.5** (2022-12), and `truck-stepio/src/out/geometry.rs` does implement `StepCurve for IntersectionCurve<C, S0, S1>`, emitting a STEP `INTERSECTION_CURVE` entity. So the machinery to write boolean-derived geometry partly exists, and the doc may understate it. But:

- The `IntersectionCurve` written carries a `PolylineCurve` leader — an *approximation* of the true intersection curve, not an exact one.
- `truck-shapeops` is declared a **dev-dependency of `truck-stepio` and then never referenced by any test** (`grep -rn shapeops truck-stepio/` matches only `Cargo.toml`). **There is no test anywhere that exports a boolean result to STEP.**

So the honest reading: the doc says no, the code hints at partial yes, and **nothing verifies it either way**. That is a worse position than a clean "no" — it means the capability would have to be established by CodeFrame's own testing before it could be relied on.

### 2.4 One thing truck gets conspicuously right

truck's `ID` is pointer-derived — [`truck-base/src/id.rs`](https://github.com/ricosjp/truck/blob/master/truck-base/src/id.rs): *"ID structure with `Copy`, `Hash` and `Eq` using raw pointers"*, `ID(ptr as usize)`, hashing the address. Naively that would make any map iteration address-dependent. It doesn't leak: `truck-topology`'s serializer keys `FxHashMap` by `VertexID`/`EdgeID` but stores `(usize, T)` and re-sorts by the insertion index before emitting ([`compress.rs::map2vec`](https://github.com/ricosjp/truck/blob/master/truck-topology/src/compress.rs)). Determinism is deliberate, and the CHANGELOG shows why they care — under v0.4: *"In order to make meshing reproducible, we decided to implement random perturbations by means of a deterministic hash function."* ([CHANGELOG](https://github.com/ricosjp/truck/blob/master/CHANGELOG.md), [`truck-base/src/hash.rs`](https://github.com/ricosjp/truck/blob/master/truck-base/src/hash.rs)). Random perturbation as a robustness tactic, made reproducible by hashing the geometry, is a small window into what b-rep robustness actually costs.

---

## 3. OCCT bindings: the build story is genuinely good; the API coverage is thinner than advertised

### 3.1 opencascade-rs

[bschwind/opencascade-rs](https://github.com/bschwind/opencascade-rs) — 256★, 68 forks, 65 open issues, LGPL-2.1, created 2022-08-19, last push **2026-06-27** (active, but low-throughput and mostly one non-owner contributor). README, verbatim: *"Rust bindings to OpenCascade. **The code is currently a major work in progress.** I currently work a full-time job and work on this in my spare time, so please adjust timing expectations accordingly :)"* and *"the exact API is still in flux and subject to change."*

**The build story — and it answers the version-pinning question affirmatively.** It vendors OCCT as a git submodule and compiles it from source by default. [`.gitmodules`](https://github.com/bschwind/opencascade-rs/blob/main/.gitmodules), verbatim:

```
[submodule "crates/opencascade-sys/OCCT"]
	path = crates/occt-sys/OCCT
	url = https://github.com/Open-Cascade-SAS/OCCT.git
```

README: *"The `OCCT` codebase is included as a git submodule. Clone the repo with the `--recursive` flag… `cargo build --release`"*, and *"By default, the `builtin` feature is enabled which means compiling OCCT from source"*, with `--no-default-features` to link a system OCCT instead. Dependencies are just Rust + CMake + a C++11 compiler; the cmake invocation (in `crates/occt-sys/src/lib.rs`) builds static, `USE_OPENGL=FALSE`, Draw/VTK/TBB/FreeType all off — genuinely headless.

**Which OCCT? Two different answers, and that's the trap.** The submodule pins commit `bd2a789f15235755ce4d1a3b07379a2e062fdc2e` = OCCT tag `V7_8_1` (*"Update version to 7.8.1"*, 2024-03-31). But the **published crate vendors a different OCCT**. **[measured]** — downloading and unpacking the `.crate` files and reading `Standard_Version.hxx`:

| `occt-sys` | published | vendored OCCT |
|---|---|---|
| 0.2.0 | 2023-08 | **7.7.1** |
| 0.6.0 | 2024-11-30 | **7.8.1** |

Published `opencascade-sys` 0.2.0 depends on `occt-sys = "0.2"` → resolves to 0.2.x → **OCCT 7.7.1**. So `cargo add opencascade` silently builds 7.7.1 while git `main` builds 7.8.1. Credit where due: `occt-sys` vendors the entire OCCT tree into the published tarball (0.6.0 = 14 MB), so the crates.io path needs no submodule and is self-contained — the pin is real, it's just *a different pin than the README describes*.

**crates.io is ~3 years stale.** `opencascade` and `opencascade-sys` 0.2.0 both last published **2023-08-16**; **docs.rs for `opencascade` 0.2.0 failed to build**, so there is no rendered API doc for the published crate; `Shape::intersect` and `write_all_step` don't exist in 0.2.0 at all. [Issue #183](https://github.com/bschwind/opencascade-rs/issues/183) "Proper Release Versioning" (open since 2024-11-13) concedes: *"the version on crates (v0.2) is quite old… this repository does not contain any releases."* **Using this crate means a git dependency.** Tellingly, `occt-sys` (54,156 downloads) is used ~12× more than the wrapper `opencascade` (4,565) — people want the vendored OCCT build, not the API.

**API coverage (on git `main`).** Booleans and STEP write are both reachable:
- `Shape::subtract/union/intersect` → `BRepAlgoAPI_Cut/_Fuse/_Common` ([`primitives/solid.rs`](https://github.com/bschwind/opencascade-rs/blob/main/crates/opencascade/src/primitives/solid.rs))
- `Shape::write_step` / `write_all_step` → `STEPControl_Writer` ([`primitives/shape.rs`](https://github.com/bschwind/opencascade-rs/blob/main/crates/opencascade/src/primitives/shape.rs))

**🚩 But a failed boolean, fillet or chamfer aborts the process.** This is the single most important fact about the crate, and it is the opposite of "real return values":

1. `subtract()` returns a bare `BooleanShape`, never a `Result`, and **never calls `IsDone()`** — it goes straight to `.Shape()`. (`IsDone` *is* bound in the sys layer — `pub fn IsDone(self: &BRepAlgoAPI_Cut) -> bool;` — it is simply unused. Across the high-level crate `IsDone` appears **once**, in `mesh.rs`; `HasErrors` **never**.)
2. OCCT's `BRepBuilderAPI_MakeShape::Shape()` calls `Check()`, and `BRepBuilderAPI_Command::Check()` does `throw StdFail_NotDone("BRep_API: command not done")`.
3. The cxx bridge declares `pub fn Shape(self: Pin<&mut BRepAlgoAPI_Cut>) -> &TopoDS_Shape;` — **no `Result`**.
4. Per the [cxx book](https://github.com/dtolnay/cxx/blob/master/book/src/binding/result.md): *"If an exception is thrown from an `extern "C++"` function that is not declared by the CXX bridge to return Result, the program calls C++'s `std::terminate`."*

The maintainer's tracker confirms it — [**issue #172**](https://github.com/bschwind/opencascade-rs/issues/172), *"Sometimes the code crashes on operations like chamfer, fillet etc, instead of handling errors gracefully"*, **open since 2024-05-14**, verbatim:

> ```
> terminate called after throwing an instance of 'StdFail_NotDone'
> Aborted (core dumped)
> ```
> "Errors can happen obviously, there's nothing wrong with that, but there must be some way we can prevent the code from crashing."

Its repro is `box1.subtract(&sphere).chamfer(0.05)` then `write_step(…)` — a CodeFrame-shaped call. This is **not a catchable panic**; you cannot `catch_unwind` a `std::terminate`. For a tool that generates geometry from user-supplied configs — where degenerate input is the expected case — a core dump on a bad config is a materially worse failure mode than an exception. §4.3 shows FreeCAD handles this exact error class better.

Credit where due: `write_all_step` *does* check the thing FreeCAD throws away —

```rust
let status = ffi::step_control::transfer_shape(writer.pin_mut(), &shape.as_ref().inner);
if status != ffi::if_select::IFSelect_ReturnStatus::IFSelect_RetDone {
    return Err(Error::StepWriteTransferFailed);
}
if count == 0 { return Err(Error::StepWriteNoShapes); }
```

That is strictly better than FreeCAD's writer (§5.1). §4.3 shows why it still doesn't catch the case that matters.

### 3.2 cadrum — the alternative that has already solved opencascade-rs's worst problem

[lzpel/cadrum](https://github.com/lzpel/cadrum) — **39★**, 14 open issues, **MIT**, created **2026-03-01**, last push 2026-07-16 (today). crates.io [`cadrum`](https://crates.io/crates/cadrum) **0.8.15, published 2026-07-13**, 1,539 downloads. Four months old and shipping hard.

Three things it does that opencascade-rs does not, all **[measured]** from source:

- **OCCT 8.0.0**, not 7.8.1 — `build.rs`: `const OCCT_VERSION: &str = "V8_0_0";`
- **Downloads a prebuilt OCCT tarball by default** (7 targets incl. macOS arm64 and wasm32); building from source is an opt-in `source` feature. No CMake in your build.
- **It catches OCCT exceptions in its own C++ shim** — `cpp/wrapper.cpp` (2,198 lines) has **34** `catch (const Standard_Failure&)` sites, surfaced to Rust as `Err`. Its API is `Result`-first throughout (`boolean_build(...) -> Result<Vec<Solid>, Error>`, `write_step(...) -> Result<(), Error>`, `fillet_edges`/`chamfer_edges`/`loft`/`sweep`/`shell` all `Result`). This is the architecturally correct place to do it, and it is exactly the gap opencascade-rs has had open since 2024.

The tradeoffs are real: 39 stars, one maintainer, pre-1.0 with *"Minor-version bumps may include breaking changes until 1.0"*, and a different API shape. It supersedes the author's earlier `chijin` (crates.io: *"DEPRECATED: Use `cadrum` instead"*). **I did not build or run it** — these are source-verified claims, not benchmarks.

Every other Rust→OCCT candidate is a toy or dead: `occt-wasm` (28★, TS-first), `cascade-rs` (3★, not an OCCT binding at all despite the name), `occt-interop` (50 downloads, no repo field), plus a half-dozen 0–1★ repos.

### 3.3 The route the Rust-vs-FreeCAD framing omits: pip-installable OCCT

The question as posed is "Rust kernel or FreeCAD". There is a third option that neither the question nor ADR 0003 considers, and it is the one that best matches CodeFrame's existing constraints.

| Binding | What it is | Distribution | Stars / activity |
|---|---|---|---|
| [**cadquery-ocp**](https://pypi.org/project/cadquery-ocp/) | pip wheel of **OCCT itself**, via [CadQuery/OCP](https://github.com/CadQuery/OCP) (pybind11 + libclang codegen; *"Provide thin bindings to OCCT"*, explicit non-goal: *"Provide additional functionality not present in OCCT"*) | **PyPI binary wheels**, 25 of them: cp310–cp314 × {macOS arm64/x86_64, manylinux_2_31 aarch64/x86_64, win_amd64}. No sdist, no win_arm64, no musllinux. Versions track OCCT: `7.8.1.x`, `7.9.3.x` (latest 7.9.3.1.1, 2026-05-28) | OCP 186★, Apache-2.0, push 2026-06-14 |
| [pythonocc-core](https://github.com/tpaviot/pythonocc-core) | SWIG bindings to OCCT; pins OCCT **`EXACT`** in CMake, so its version number *is* the OCCT version | **conda-forge only.** Its PyPI entry returns HTTP 200 and reports `0.16`, but `"urls": []` — **zero distributions have ever been uploaded.** There is no `pip install` path at any version | 1,933★, LGPL-3.0, push 2026-06-25 |
| [build123d](https://github.com/gumyr/build123d) / [cadquery](https://github.com/CadQuery/cadquery) | High-level modeling APIs *on top of* OCP | pip. build123d depends on `cadquery-ocp-novtk >= 7.9, < 8.0` — and, notably, on **`ezdxf >= 1.1.0`**, the same 2D library CodeFrame already uses | 2,647★ / 5,463★, both active |

**[measured]** `pip install cadquery-ocp` gave a working OCCT 7.9.3 in-process on this machine in one command, no compiler, no FreeCAD. Booleans (`BRepAlgoAPI_Cut`), STEP write (`STEPControl_Writer`), and `SetRunParallel`/`SetFuzzyValue` are all exposed and working.

This route delivers every mechanical benefit the reframing wants — version-pinned OCCT (`cadquery-ocp==7.9.3.1.1`), in-process calls, no subprocess, no GUI application — **while preserving [ADR 0001](../adr/0001-ezdxf-over-freecad.md)'s constraint that the Deterministic Core stay pip-installable, unit-testable and CI-friendly.** A Rust kernel breaks that constraint; a Rust binding breaks it harder (it would put a CMake+C++ build, or a `git` dependency, in front of a `pip install`).

Two honest caveats, both **[measured]**: `pip install cadquery-ocp==7.8.1.1` **failed** on this machine's Python — *"Could not find a version that satisfies the requirement (from versions: 7.9.3.1.1)"*. Wheel availability is a function of Python version, so "pin OCCT 7.8.1" and "use current Python" can conflict; the pin is real but coupled to the interpreter. And the whole Python CAD ecosystem sits on **OCCT 7.9.3** — one maintenance release *ahead* of opencascade-rs's git pin (7.8.1) and two ahead of what crates.io actually gives you (7.7.1).

### 3.4 OCCT itself — and why every binding is a C++ build

[Open-Cascade-SAS/OCCT](https://github.com/Open-Cascade-SAS/OCCT) — 2,650★, LGPL-2.1, last push 2026-07-13, latest tag **V8_0_0** (7.9.3 and 7.8.1 also tagged). Actively developed on GitHub with a public tracker and PR review — a materially different governance picture from the Mantis era. FreeCAD lags it: FreeCAD 1.1.1 ships OCCT 7.8.1 **[measured]** while OCCT is at 8.0.0.

**There is no OCCT C API.** Verified by census of a `V8_0_0` checkout: 7,084 `.hxx` and 6,329 `.cxx` against **6 `.h` files**, none of them a public C surface (vendored flex/bison/Khronos headers, an internal IGES header, and `NCollection_Haft.h`, which opens `#error This file is usable only in C++/CLI (.NET) programs` — OCCT's own answer for a non-C++ host is a C++/CLI shim). The `extern "C"` hits are inbound glue (dlopen, FFmpeg) or plugin factories whose signatures take C++ references. The entire genuinely C-callable public surface is `Standard_VersionInfo.hxx` — five version-string functions. The README says it plainly: *"Most of OCCT functionality is available in the form of C++ libraries."*

This matters structurally: `Standard_Transient`'s intrusive refcount plus the `opencascade::handle<T>` template mean **every OCCT binding in every language is a C++ compilation, not an FFI shim**. That is why opencascade-rs vendors a CMake build, and why OCP needs `PYBIND11_DECLARE_HOLDER_TYPE`. "Bind OCCT from Rust" is not a cheaper operation than "bind OCCT from Python" — both are the same C++ build, and the Python one is already done, wheeled, and pinned.

---

## 4. The claim under test: does binding OCCT deliver what the rewrite was supposed to?

The reasoning to test: *CodeFrame's pain is the GUI-application-pretending-to-be-a-library layer, not C++ — so vendoring/binding OCCT (version pinned, in-process, real return values instead of silent failure) delivers what a rewrite was supposed to, without the multi-year kernel project that killed Fornjot.*

**Verdict: the version-pinning half is right and achievable. The "real return values instead of silent failure" half is wrong — and demonstrably so. The determinism premise is also wrong, but in CodeFrame's favour.**

### 4.1 Is OCCT deterministic? No documented guarantee — and the hazard is structural and real

**OCCT documents nothing.** Its official [Boolean Operations specification](https://dev.opencascade.org/doc/overview/html/specification__boolean_operations.html) ([source](https://github.com/Open-Cascade-SAS/OCCT/blob/master/dox/specification/boolean_operations/boolean_operations.md)) runs 3,563 lines and contains **zero** occurrences of "deterministic", "reproducible", "repeatable", or "stable". There is no reproducibility guarantee anywhere in OCCT's docs. Treat it as unspecified, not as promised.

**The structural hazard is real.** OCCT hashes shapes **by pointer address**. [`TopoDS_Shape.hxx`](https://github.com/Open-Cascade-SAS/OCCT/blob/master/src/ModelingData/TKBRep/TopoDS/TopoDS_Shape.hxx):

```cpp
template <> struct hash<TopoDS_Shape> {
  size_t operator()(const TopoDS_Shape& theShape) const noexcept {
    const size_t aHL = std::hash<TopLoc_Location>{}(theShape.Location());
    return aHL == 0 ? opencascade::hash(theShape.TShape().get())
                    : opencascade::MurmurHash::hash_combine(theShape.TShape().get(), sizeof(void*), aHL);
  }
};
```

`theShape.TShape().get()` is a raw pointer; `opencascade::hash` MurmurHashes it. `TopTools_ShapeMapHasher` just forwards to this. So **any hash container of shapes iterates in heap-address order**, which varies per process under ASLR.

**And it has bitten OCCT, in shipped code.** This is not hypothetical:

- [PR #584](https://github.com/Open-Cascade-SAS/OCCT/pull/584) "Shape Healing - Optimize FixFaceOrientation" (2025-06-24) — *"Rework algorithm with efficient data structures"* — introduced `std::unordered_map<TopoDS_Face, …, TopTools_ShapeMapHasher>` into `ShapeFix_Shell.cxx` and iterated it.
- [PR #753](https://github.com/Open-Cascade-SAS/OCCT/pull/753) "Shape Healing - Regression after #584" (2025-10-20) fixed it. Body, verbatim: *"**Fixed issue with unstable shape order after fixing.** Fixed reference data which was changed"*. The diff replaces `std::unordered_map` with insertion-ordered `NCollection_IndexedDataMap` and swaps pointer-order iteration for `for (Standard_Integer aFaceInd = 1; aFaceInd <= aFaceEdges.Size(); ++aFaceInd)`.

OCCT is also actively hardening this: [#140](https://github.com/Open-Cascade-SAS/OCCT/issues/140) "Update Map to store insert order" (2024-11 → closed 2025-12) and [#1072](https://github.com/Open-Cascade-SAS/OCCT/issues/1072) (2026-02) which added `NCollection_OrderedMap`/`OrderedDataMap` explicitly for *"O(1) hash lookup, O(1) append/remove, and **deterministic iteration in insertion order**"*. Plain `NCollection_Map` still has no insertion-order guarantee in master.

**Why the boolean path is nonetheless probably safe.** Reading `BOPAlgo_Builder.cxx` and `BOPAlgo_BuilderSolid.cxx`, every `NCollection_Map<TopoDS_Shape>` is a *membership fence* — `aMFence`, `aMFDone`, `AddedFacesMap`, `aMP` — used for dedup, where iteration order is irrelevant. Ordered output is driven by `NCollection_IndexedDataMap`, `NCollection_List`, and integer index loops. The pointer hash does not obviously reach the output.

**Parallelism is off by default — in OCCT.** [`BOPAlgo_Options.cxx`](https://github.com/Open-Cascade-SAS/OCCT/blob/master/src/ModelingAlgorithms/TKBO/BOPAlgo/BOPAlgo_Options.cxx) initialises `bool myGlobalRunParallel = false;`. **[measured]** confirmed via OCP: `BRepAlgoAPI_Cut(...).RunParallel()` → `False`, `FuzzyValue()` → `1e-07`.

**…but FreeCAD forces it on.** [`TopoShapeExpansion.cpp::makeElementBoolean`](https://github.com/FreeCAD/FreeCAD/blob/main/src/Mod/Part/App/TopoShapeExpansion.cpp) — the path Python `shape.cut()` reaches — does:

```cpp
mk->SetRunParallel(Standard_True);
OSD_Parallel::SetUseOcctThreads(Standard_True);
```

So **CodeFrame's booleans run multi-threaded today**, because FreeCAD overrides OCCT's safer default. This is the one place where "the GUI-app-as-library layer injects a determinism hazard" is *literally true*.

### 4.2 So is it deterministic in practice? **[measured] — yes, and this is the finding that most undercuts the premise**

The premise that byte-reproducibility "is hard to guarantee with a GUI application acting as a library" is not holding up empirically.

Same macro, 8 fresh `freecadcmd` processes, ADU-shaped geometry (wall shell with coplanar cut + 8 openings + gable prism), FreeCAD 1.1.1 / OCCT 7.8.1, parallel booleans **on**, only the `FILE_NAME` timestamp pinned exactly as `_pin_step_timestamp` does:

```
run 1..8   sha256=8d4a39801432eb2cfcce9d53   bytes=58581   (identical, 8/8)
```

This is meaningful only if addresses actually moved, so I checked: **[measured]** heap addresses across runs were `0xa8326f348`, `0x83505ea48`, `0x96305e608`, `0x93703e548`, `0x94305df88` — ASLR is live and wide. Despite randomized addresses feeding a pointer-derived shape hash, and despite multi-threaded booleans, the STEP output was byte-identical every time.

Pure OCCT 7.9.3 in-process via OCP, no FreeCAD, 6 runs: **6/6 byte-identical** (`sha256=9a33b9aa079d133c11048087`, 149,030 bytes).

**Honest limits.** N=8 and N=6, one machine, one geometry family (planar faces, axis-aligned boxes, one prism), two OCCT versions. This proves the pipeline *is* stable today for CodeFrame's shapes; it does not prove it *must* be, and says nothing about curved surfaces or tangencies. The real exposure is **version drift, not run-to-run**: [#1337](https://github.com/Open-Cascade-SAS/OCCT/issues/1337) is a `BRepMesh` regression *"between 7.9.3 and 8.0.0"* on boolean-trimmed faces; [#753](https://github.com/Open-Cascade-SAS/OCCT/pull/753) had to *"fix reference data which was changed"*; FreeCAD [#29183](https://github.com/FreeCAD/FreeCAD/issues/29183) is a **Blocker/Regression** where STEP export silently stopped working between 1.1.0 and 1.2.0dev. Pinning is what buys determinism — and pinning works equally well for a FreeCAD AppImage as for a vendored OCCT.

**Consequence for the goal:** byte-reproducibility of raw STEP is achievable and is currently achieved. The one-line timestamp normalization CodeFrame already does is the whole cost. Hashing a canonicalized form is not needed today — but note the header also embeds the kernel version (`'Open CASCADE STEP processor 7.8'`), so any byte-level golden test is implicitly a test of the pinned build, and will break on upgrade by design.

### 4.3 "Real return values instead of silent failure": **the premise is false — and inverted**

This is the part of the reframing that does not survive. There are two distinct failure modes, and binding OCCT improves neither. On one of them it is actively worse.

**Failure mode A — the degenerate-but-"successful" boolean. Silent on every route.** **[measured]** OCCT 7.9.3, in-process, no FreeCAD anywhere, cutting a wall with a tool that engulfs it:

```
OVERCUT: IsDone=True  IsNull=False  solids=0
OVERCUT Transfer status: IFSelect_RetDone   (RetDone=True)
```

**OCCT reports complete success while producing zero solids, and its STEP writer reports `RetDone` while transferring them.** The silent-empty-export mode is **OCCT's own behaviour**, inherited identically by every wrapper. Binding OCCT directly cannot fix it — the kernel says "done".

That also defeats opencascade-rs's otherwise-good `write_all_step` guard (§3.1): it checks `transfer_shape != RetDone`, but the transfer *returns* `RetDone`, and `count == 0` is false because one (empty) shape was passed. It would write the empty file too.

**Failure mode B — the genuinely failed boolean/fillet. FreeCAD catches it; opencascade-rs core-dumps.** **[measured]**, same error class (`StdFail_NotDone`), same shape as issue #172's repro, under FreeCAD 1.1.1:

```
CAUGHT: ValueError: Null input shape
CAUGHT: OCCError: 15StdFail_NotDone BRep_API: command not done
PROCESS-SURVIVED
```

FreeCAD translates OCCT's `Standard_Failure` into a catchable Python `OCCError` (its `PY_CATCH_OCC` macro) and **the process survives**. opencascade-rs lets the identical exception cross an undeclared cxx boundary → `std::terminate` → `Aborted (core dumped)`, open since 2024-05-14 (§3.1). **On error handling, the "GUI application pretending to be a library" is doing real, valuable work that the Rust binding does not.** cadrum (§3.2) is the only Rust route that has solved this, via 34 `catch (const Standard_Failure&)` sites in its own C++ shim.

**And OCCT's error API is largely unreachable everywhere:**

| Route | `IsDone()` checked on booleans? | `HasErrors()` | Genuinely failed boolean |
|---|---|---|---|
| FreeCAD `TopoShapeExpansion.cpp` | **No** — `makeElementBoolean` calls `Build()` then goes straight to `makeElementShape`. (11 `IsDone` checks exist elsewhere in the file; none in the boolean path.) | **0 occurrences** in the file, or in `TopoShape.cpp` | **[measured]** catchable `OCCError`, process survives |
| opencascade-rs | **No** — `subtract()` returns `BooleanShape`, not `Result`; `IsDone` *is* bound but unused | **0 occurrences** in the high-level crate | **`std::terminate`, core dump** ([#172](https://github.com/bschwind/opencascade-rs/issues/172)) |
| cadrum | via its C++ shim | — | `Result::Err` |
| OCP / cadquery-ocp | caller's choice | **[measured] not exposed at all.** `BRepAlgoAPI_Cut`'s full MRO surfaces `RunParallel`/`SetRunParallel`/`FuzzyValue`/`SetFuzzyValue` and `IsDone` — but **no `HasErrors`/`HasWarnings`** | caller's choice |

OCCT's own spec tells you to check: *"Check the presence of the Errors and Warnings"* via `HasErrors()`/`HasWarnings()`, with the sample `if (aBuilder.HasErrors()) { return; }`. **No route surveyed actually calls it, and the pip-installable one does not even expose it.**

**The corollary that matters:** for mode A — the one that actually bit CodeFrame — the only defense that works on any route is a **post-condition check on the geometry**: assert the expected solid count and non-zero volume before export, and grep the written file for `MANIFOLD_SOLID_BREP`/`ADVANCED_FACE` after. That defense is available **today, in the existing FreeCAD macro, at zero migration cost.** Migration buys nothing here, and on mode B it currently costs you a core dump.

### 4.4 The data-loss incident that motivated the question was not FreeCAD's

Worth stating plainly, because it is load-bearing for the framing. Per [ADR 0003](../adr/0003-freecad-massing-model.md)'s own record, the export that "silently dropped half the geometry" was the **cli-anything-freecad harness**, which was evaluated and rejected precisely because *"its export path emits raw primitives only, silently dropping boolean results and wedge solids"*. That was a third-party harness bug, already diagnosed and already fixed by moving to the native `freecadcmd` macro. It is not evidence against FreeCAD, and not evidence for leaving it.

That said — §4.3 shows an equivalent silent-drop is still reachable through the current design (§5.2). The premise is right that the risk exists; it's wrong about the cause and about what fixes it.

---

## 5. Staying put: what headless FreeCAD actually gets wrong

### 5.1 Silent export data loss — real, and it *is* FreeCAD's wrapper here

FreeCAD's entire STEP write path is 74 lines ([`src/Mod/Import/App/WriterStep.cpp`](https://github.com/FreeCAD/FreeCAD/blob/main/src/Mod/Import/App/WriterStep.cpp)) and has two defects:

```cpp
writer.Transfer(hDoc, STEPControl_AsIs);          // return value DISCARDED
...
IFSelect_ReturnStatus ret = writer.Write(name8bit.c_str());
if (ret == IFSelect_RetError || ret == IFSelect_RetFail || ret == IFSelect_RetStop) { throw ... }
```

`Transfer()` is where geometry moves into the STEP model and its status is thrown away — the exact value opencascade-rs checks. `Write()` is compared against only 3 of 5 `IFSelect_ReturnStatus` values, so **`RetVoid`** ("nothing done") passes silently. In `ExportOCAF2.cpp`, objects resolving to a null shape are dropped with `FC_WARN` only, and export continues.

Tracker corroboration is thinner than the source evidence but real: [#16292](https://github.com/FreeCAD/FreeCAD/issues/16292) *"STEP: export 'empty' STEP file for model, no errors in Check Geometry"* — **open since 2024-09-04, labelled Status: Confirmed**, re-confirmed 2026-04-25; reporter: *"No errors are reported in the console when exporting."* Also [#29183](https://github.com/FreeCAD/FreeCAD/issues/29183) (Blocker/Regression, silent export failure 1.1.0→1.2.0dev), [#20641](https://github.com/FreeCAD/FreeCAD/issues/20641), [#26994](https://github.com/FreeCAD/FreeCAD/issues/26994), [#20396](https://github.com/FreeCAD/FreeCAD/issues/20396).

**But it is not headless-specific, and no evidence says it is.** No tracker issue alleges headless export drops solids that GUI export keeps. The one on-point forum thread, [Ticket #6282 — freecadcmd exportStep breaking model](https://forum.freecad.org/viewtopic.php?f=3&t=67920), was answered by FreeCAD founder wmayer, verbatim: *"I can confirm a problem. However, **it's not a GUI vs. CMD issue** but a simplified vs. advanced STEP export."*

### 5.2 The gap that is actually open in CodeFrame today — **[measured]**

`freecadcmd` **exits 0 on unhandled macro exceptions and on a missing macro file**:

```
raise ValueError("BOOM")  → exit_code=0, stderr: "Exception while processing file: boom.py [BOOM]"
/nonexistent/macro.py     → exit_code=0, no output at all
```

CodeFrame is already defended against this, and the design is correct: `write_massing_model` requires `result.returncode == 0` **and** `"codeframe-massing-ok" in result.stdout`. The stdout sentinel catches both cases above where the exit code cannot.

**The residual gap is the geometry post-condition.** Reproducing CodeFrame's exact macro structure with an over-cutting opening:

```
exit_code=0
stdout: "codeframe-massing-ok 1"        ← sentinel printed
STEP written: 1640 bytes, 0 MANIFOLD_SOLID_BREP entities
→ CodeFrame's guard PASSES
```

The macro prints `len(solids)` — the *configured* count — after `exportStep` returns, and `exportStep` succeeds on empty geometry (§4.3). So a degenerate boolean yields a valid-looking, structurally correct, geometry-free STEP that passes every existing check. This is the same class of failure as the cli-anything-freecad incident (§4.4), reachable through the current design, and **it would be equally reachable after migrating to OCCT-in-Rust or OCCT-in-Python.** The fix is a post-condition, not a port.

### 5.3 Startup cost — **[measured]**, and it is not a real problem

FreeCAD publishes no startup benchmarks and the tracker has no freecadcmd startup-performance issues. Measured here (FreeCAD 1.1.1, macOS arm64):

| Workload | Wall clock |
|---|---|
| `freecadcmd` + no-op macro | **0.08–0.11 s** |
| Realistic massing: `import Part` + 6 boolean cuts on ADU-scale geometry + STEP export | **0.22–0.24 s** total — of which `import Part` 0.11 s, booleans 0.017 s, STEP export 0.004 s |

Per-run app startup costs roughly **0.1 s**, and the whole 3D export is a quarter-second. (A separate measurement using `Part::Cut` *document objects* plus `recompute()` came in at 1.42 s — but CodeFrame's macro uses the direct `Part` API and does not build a document, so 0.22 s is the representative figure.) **Startup cost does not justify anything.**

### 5.4 Version pinning is available, without a container

- **No official FreeCAD Docker runtime image exists.** [FreeCAD/Docker-packaging](https://github.com/FreeCAD/Docker-packaging) is explicitly build environments only: *"example Dockerfiles that can be used to create containers that have all the required dependencies pre-installed that are needed to **build FreeCAD from source**."* Docker Hub `freecad/freecad` is a dead placeholder (0 pulls, last touched 2021). The wiki's [FreeCAD Docker CLI mode](https://wiki.freecad.org/FreeCAD_Docker_CLI_mode) page documents a **third-party** image (`amrit3701/freecad-cli`), stuck at 1.0.2.
- **The official AppImage is a real pin.** Every GitHub release ships a versioned, SHA256-checksummed asset — `FreeCAD_1.1.1-Linux-x86_64-py311.AppImage` plus `…-SHA256.txt` — linked from [freecad.org/downloads](https://www.freecad.org/downloads.php). AppImages bundle `FreeCADCmd`. Pin = release tag + SHA256. (Weekly builds are tagged `weekly-YYYY.MM.DD` and marked prerelease — not pinnable material.)
- **conda-forge** [freecad](https://anaconda.org/conda-forge/freecad) supports `freecad=1.1.0`, but lags 1.1.1.

### 5.5 Headless caveats worth knowing

FreeCAD's only normative statement on headless limits, from [Start up and Configuration](https://wiki.freecad.org/Start_up_and_Configuration): *"you have the same functionality as the Python interpreter that runs inside the FreeCAD GUI, and access to all modules and plugins of FreeCAD, **except the FreeCADGui module. Be aware that modules that depend on FreeCADGui might also be unavailable.**"* That "might" is the entire official guidance — there is **no list** of headless-unavailable functionality, and the dedicated [Headless FreeCAD](https://wiki.freecad.org/Headless_FreeCAD) page is a stub. The one concrete exporter difference is that `ImportGui.export()` sources per-face colours from the view provider and is GUI-only — irrelevant to a massing model. TechDraw headless SVG/PDF export does *not* work ([#5710](https://github.com/FreeCAD/FreeCAD/issues/5710) open since 2022; [#24084](https://github.com/FreeCAD/FreeCAD/issues/24084) is titled "TechDraw (Phase 1 of 3): headless PDF/SVG export") — relevant only if CodeFrame ever wanted FreeCAD to draw sheets, which ADR 0001 rules out.

---

## What the evidence establishes

**On a Rust-native kernel as a destination.** Fornjot is the only serious attempt and its author archived it after ~6 years, estimating 2-3 more years to a foundation that could *start* delivering value, and concluding: *"An overambitious project, addled by mistakes at almost every turn."* It has no solid booleans and no STEP export; its exporter takes triangles. truck is alive and well-engineered but has published no release in ~22 months, has a bus factor of one, documents booleans as transversal-only — which excludes CodeFrame's coplanar wall-shell cut, its very first solid — and its own STEP writer docs say boolean results "cannot be output yet", with no test either way. Neither is a destination for a STEP-exporting ADU massing model in 2026.

**On the reframing.** It splits cleanly:
- **Version pinning — correct and achievable.** opencascade-rs genuinely vendors OCCT 7.8.1 as a submodule and builds it from source; `cadquery-ocp` genuinely pins OCCT by PyPI version. Both are real pins. But so is a FreeCAD AppImage release tag + SHA256, and pinning is what buys stability regardless of route. (Caveat: `cargo add opencascade` gets you OCCT **7.7.1**, not the 7.8.1 the README describes.)
- **"Not C++, just the GUI layer" — the premise mis-locates the cost.** OCCT has **no C API**; every binding in every language is a C++ compilation against `Standard_Transient` and `opencascade::handle<T>`. Binding OCCT from Rust is not cheaper than binding it from Python — it is the same C++ build, and the Python one is already done, wheeled, and pinned.
- **In-process calls — correct, and the one real determinism win is unexpected:** OCCT defaults `RunParallel` to `false`, and FreeCAD overrides it to `true` for every boolean. Calling OCCT directly would let CodeFrame keep the safer default.
- **"Real return values instead of silent failure" — false, and on one failure mode inverted.** OCCT itself returns `IsDone=True` and `IFSelect_RetDone` while producing and exporting zero solids; every route inherits that identically, and only a geometry post-condition catches it. Meanwhile, on a *genuinely* failed boolean, FreeCAD raises a catchable `OCCError` and survives while opencascade-rs calls `std::terminate` and core-dumps — a bug open since 2024. No wrapper surveyed calls `HasErrors()`; the pip-installable one doesn't expose it. The GUI-app-as-library layer is, on this axis, the *better* error handler.
- **Determinism as a motivation — not supported.** Byte-identical STEP is already achieved (8/8 through FreeCAD with ASLR live and parallel booleans on; 6/6 through pure OCCT) with the one-line timestamp pin CodeFrame already ships. The exposure is version drift, which pinning addresses on any route.

**If the 3D side did move**, the evidence points away from the framing's own options: not a Rust kernel (Fornjot, truck), and not opencascade-rs as it stands (git-only dependency, core dumps on degenerate input). The two candidates the evidence actually surfaces are **`cadquery-ocp`** — OCCT 7.9.3, pip-installable, version-pinned, preserves ADR 0001's constraints, and is what cadquery/build123d already stand on — and, for a Rust future, **cadrum**, which is the only Rust binding that has solved the exception-safety problem, at the cost of being four months old with 39 stars.

**On the three stated pain points**, measured rather than assumed: startup cost is ~0.1 s and is not a problem; the silent-drop incident was a third-party harness FreeCAD's ADR already rejected, not FreeCAD; and byte-reproducibility is already holding. The one genuinely open defect is CodeFrame's own — the `codeframe-massing-ok` sentinel is printed after an export that succeeds on empty geometry, so a degenerate boolean passes every current check — and it is a post-condition away from closed, on any kernel.

**Where the evidence is thin, and what I could not verify:**
- **Hanno's specific technical reasons.** His post-mortem is about scope, funding, sponsorship timing and commitment. He names a "cliff" after b-rep showed early promise but **never identifies surface-surface intersection, robustness, or tolerance handling as the wall.** If that reasoning exists in his own words, it is not in the shutdown post.
- **The Reddit "ticks only b-rep" comment is unverified** — reddit.com is unreachable from this agent. The substance is independently confirmed from the Fornjot repo; the quote itself should not be cited.
- **truck's boolean→STEP status is genuinely ambiguous**, not merely unsupported: the docs say no, `IntersectionCurve` has a `StepCurve` impl since v0.5, and no test exercises it. Only running it would settle it.
- **Determinism is established empirically, not by guarantee.** N=8/N=6, one machine, planar axis-aligned geometry, two OCCT versions. OCCT documents no reproducibility guarantee, its shape hash is pointer-derived, and PR #584→#753 proves "unstable shape order" from pointer-hash iteration is a bug class that *ships*. Nothing here promises the next OCCT version behaves the same.
- **Neither opencascade-rs nor cadrum was built or run.** Their build files, cxx bridges, submodule pins, catch sites and API surfaces are source-verified; the `std::terminate` chain is verified link-by-link *and* corroborated by the maintainer's own open issue — but I did not reproduce the core dump, and I have no build times or platform-greenness data for either. cadrum's prebuilt-tarball claim for its 7 targets is README/build-script only.
- **No evidence was found that headless export loses geometry that GUI export keeps** — I looked, and the founder explicitly rejected that framing in the one on-point thread.
- **Unresolved:** whether OCC SAS sells a private C API commercially (the public component list is C#/Java only); whether `HasErrors` is reachable in OCP via some path I did not find; and the exact commit count on opencascade-rs `main` since its 2023 crates.io publish.
