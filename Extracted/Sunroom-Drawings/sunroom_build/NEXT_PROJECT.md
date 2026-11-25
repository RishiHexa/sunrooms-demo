# Sunroom modelling — what transfers to the next project

Written at the end of the 225-series build, for starting a 4-season room with a different
profile set. Read this before writing any code.

---

## 1. What this project actually produced

A parametric FreeCAD model of a 225-series sunroom: 64 members across three walls, built
from the real die cross-sections, with every joint engagement measured rather than assumed.

The useful output is **not the model**. It's the ~900 lines in `v2/` and the method behind
them. The model regenerates in about two minutes; the method took the whole project.

---

## 2. The architecture that emerged — engine vs data

This split is the single most important thing to carry forward. It wasn't designed up front;
it fell out of repeated rework. Start the next project with it already in place.

### Engine — profile-agnostic, reuse unchanged (~440 lines)

| file | what it does | depends on the profile set? |
|---|---|---|
| `v2/extract_profiles.py` | die DXF → closed loops → JSON | no |
| `v2/solve.py` | identify + orient every instance in an assembly DXF | no |
| the FreeCAD builder (inline) | basis → extrude → anchor → enforce opening → cut | no |

### Data — re-measure for the new system

`profiles_all.json`, `layout.json`, the engagement table. All numbers, no logic.

### Config — rewrite for the new system (~270 lines)

`layout2.py` (panel runs, handedness), `members.py` (what parts go where).

**For a new profile set the engine runs untouched. You re-measure the data and rewrite the
config.** Budget accordingly: the expensive-looking part is the cheap part.

---

## 3. The one thing that changed everything

Mid-project you supplied `225-Assembly.dxf` — labelled cross sections with every profile
drawn in its installed orientation.

Before it, I was reverse-engineering orientation from profile geometry: centroid offsets to
find the open side, rib detection to orient corner posts. All of it was guesswork dressed up
as inference, and all of it was eventually wrong.

After it, `solve.py` matched 119 of 128 instances against the die files and solved each one's
rotation and mirror automatically. Orientation stopped being a question.

**Ask for the assembly cross-sections before modelling anything.** One drawing is worth more
than any amount of reasoning about what a profile "should" do. If it doesn't exist, ask for
a few sections to be drawn — it is far cheaper than the rework.

---

## 4. Order of operations for the next project

1. **Collect** — die DXFs, assembly cross-sections, a room/elevation drawing, and the written
   assembly rules. Do not start without the cross-sections.
2. **Extract** — run `extract_profiles.py` over the new die set. Expect the three encodings
   (see §6). Verify every loop closes with zero gap.
3. **Measure** — run `solve.py` on the assembly DXF. This gives orientation per part AND
   joint engagement per joint type, straight off the drawing.
4. **Lay out** — compute panel widths from outside-to-outside dimensions and the measured
   engagements. **The run must close to zero error.** If it doesn't, a joint type is wrong.
5. **Build** — basis per member, then verify.
6. **Iterate on screenshots** — every correction in this project came from you looking at a
   render. Build the cheap render loop early.

---

## 5. The orientation lessons — these cost the most

Nearly every correction in this project was an orientation bug, and they were all the same
bug wearing different clothes.

- **An extrusion cannot be mirrored.** Opposite walls use the *same* die. Handed parts must
  be rotated, never mirrored. I assumed mirror symmetry at least three times.
- **Never let orientation fall out of the run direction.** `Rotation(Z, direction)` leaves
  roll arbitrary, so the same code lands differently depending on which way a member runs.
  This produced members that were correct on one wall and inverted on another.
- **State orientation as a physical requirement, then enforce it.** Each member carries a
  required opening direction (bottom channels open up, wall channels open into the room).
  The builder measures the finished solid and corrects it. Rules beat constants.
- **Correct orientation by rebuilding the basis, not rotating the solid.** Rotating a
  finished solid 180° about a *sloped* run axis tips the profile out of vertical and skews
  the end cuts by twice the rake angle. Negate `u` and `v`, re-extrude.
- **Handedness comes from the viewer, not the geometry.** "Female left, male right" is
  defined looking at each wall *from outside*: `right = forward × up`, forward = inward
  normal. That reverses between the two side walls and is derivable — don't hard-code it.
- **Non-square parts change footprint when rotated.** The corner post is 2.265 × 2.402, so
  rotating it swapped which dimension faced which wall and silently opened a joint.

---

## 6. Die-file traps (carried over, still true)

- Three encodings: closed LWPOLYLINE, LINE+ARC wires needing stitching, and ACIS **REGION**.
- For REGION, ezdxf's high-level `acis.load()` fails. Use `sab.parse_sab()` and walk
  `loop → coedge → edge → vertex → point`. **Apply the coedge `sense` flag** or every loop
  has gaps.
- **Do not use FreeCAD's DXF importer.** Importing `importDXF` triggers a library download
  that hangs the RPC server — it cost two restarts. Build faces from explicit `Part` geometry.
- Layer `0` is the profile; `DIM`, `DIMENSION`, `IMP`, `APROVAL` are annotation.
- Expect at least one profile drawn without its closed flag, with a zero-length closing
  segment. That degenerate edge hangs FreeCAD. Strip it.
- Expect some faces to need `.fix(1e-7,1e-7,1e-7)` before they are valid.

---

## 7. Verification that actually caught things

Every bug in this project was **silent** — nothing threw an exception. These checks found them:

- **Overall extents against expectation.** Caught a 233-vs-217 placement bug and a 2.438
  anchor error, both instantly.
- **Run closure to zero.** Caught a wrong joint type at the house end; the error was exactly
  0.127000, the corner-post engagement, applied where no corner post exists.
- **Overlap AND gap together.** `common().Volume` alone cannot tell a closed mitre from two
  members that merely don't collide. Check `distToShape()` as well.
- **Left/right symmetry to 0.00000.** Caught 14 inconsistent members at once.
- **Implied section area** (volume ÷ length) as a sanity check on every member.

Treat a result of exactly zero as the pass condition. Near-zero means something is wrong.

---

## 8. What a 4-season room adds that is NOT in this project

The original brief was a lean-to 4-season room with a foam panel roof. This build covers the
**wall frame only**. None of the following is modelled or analysed:

- **Roof** — foam panel assembly, rafters, ridge/ledger, gutter, the raked-to-flat transition.
- **Thermal** — thermal breaks in the profiles, IGU glazing makeup, U-factor and SHGC,
  condensation and dew point, continuity of the air and vapour barrier.
- **Loads** — snow (including drift surcharge where a lean-to meets a taller wall), wind,
  frost depth. These size the structure and must come from the local authority.
- **Panel infill** — solid foam-core panels and glass are not modelled, only their frames.
- **Floor** — the most commonly missed R-value in a 4-season conversion.

The 225 profiles are not thermally broken. If the next system is, the profile geometry will
include a polyamide strut or poured-and-debridged channel, which may read as **multiple
disjoint loops per die file**. The extractor currently assumes one outer loop plus holes —
that is the one place the engine will likely need real work.

---

## 9. Files worth opening first

```
v2/extract_profiles.py   die DXF -> closed loops          (reuse as-is)
v2/solve.py              assembly DXF -> orientation      (reuse as-is)
v2/layout2.py            panel runs and handedness        (rewrite, read first)
v2/members.py            member list                      (rewrite, read first)
v2/BUILD_REFERENCE.md    the 225 system's measured data   (template for the new one)
```

`v1/` is superseded. It is kept only because its mistakes are documented in §5.
