# 225 Sunroom — Build Reference (v2)

Rebuilt against `225-Assembly.dxf` and `225 SunRoom Assembly.txt`.
Supersedes v1 entirely — v1's orientation rules were reverse-engineered without ground truth and are **withdrawn**.
Written to be read cold: assume no memory of how any of this was derived.

## Authority — which file decides what

| question | source |
|---|---|
| part order, orientation, joint engagement | `225-Assembly.dxf` cross sections |
| overall dimensions, panel counts | `225-Room-Description.dxf` |
| assembly rules | `225 SunRoom Assembly.txt` |
| profile cross-sections | `DXF FILES FOR DIES/` |

When these disagree, the assembly DXF wins on geometry, the text wins on rules.

---
## 1. Rules (from the assembly notes)

- Perimeter is wall channels A62420 vertical at the house, top and bottom channels A62421
  horizontally around the perimeter, corner posts A26952 at each corner.
- **Overall dimensions are to the OUTSIDE of these channels.**
- No bottom channel across a door opening, so the door sits at floor level. A stub bottom
  channel remains under a vertical channel adjacent to a wall channel.
- Panels run **female A26948 on the left, male A26949 on the right**, always.
  Female channels separate panels within a run.
- Panel types: solid (foam between aluminium skins), glass, prefab door, slider window.
  Solid and door panels need no adaptor. Glass panels need A26950 all round.
- Slider window: A33863 bottom sill, A33861 top sill, A33864 side track, A45216 locking side track.
  Sashes are mitred, from A29389 sash frame, A45217 locking pull sash, A22445 and A22446 CMR pieces.
- Patio door adds 3 mitred 1x1 tubes (A7116) as exterior trim.
- Front top channel runs outside-to-outside of the corner posts; side wall channels **butt** into
  the posts, with mitre cuts on the vertical legs for the side wall slope. Same at the bottom.

### Section reading convention

- horizontal (plan) sections: **outside is at the BOTTOM**
- vertical sections: **outside is to the RIGHT**

---
## 2. Measured joint engagements

Measured directly off the assembly sections, not assumed.

| joint | value | confidence |
|---|---|---|
| A26952 post -> A26948 female | 0.127 | 5 samples, zero variance |
| A26949 male -> A26952 post | 0.127 | |
| A26949 male -> A26948 female | 0.1173 | bimodal: also 0.1377. notes say ~0.137 |
| A26950 adaptor -> A26949 male | 0.2196 | 7 samples, near-zero variance |
| A26948 female -> A26950 adaptor | 0.2196 | |
| A26948 -> A33864 side track | 0.2166 | |
| A26948 -> A45216 lock track | 0.2192 | |
| A26948 -> A33861 top sill (vert) | 0.2191 | |
| A33863 bottom sill -> A26948 (vert) | 0.2287 | |
| A26949 male NESTED in A62420 wall channel | 0.2071 inset | 3 samples, zero variance |

**The wall channel joint is a NEST, not an edge butt.** The male sits inside the wall channel,
its outer edge 0.2071 in from the channel's outer face. Getting this wrong puts the
side wall out by exactly the corner-post engagement, which looks like a rounding error and is not.

---
## 3. Derived layout

```
front wall : 4 panels   clear 211.1960   panel width 52.9505
side walls : 2 panels   clear 141.5279   panel width 70.8861
corner post presents 2.402 along the FRONT wall, 2.265 along the SIDE walls
channel 2.4050 deep x 1.6875 high
```
Both runs close to **exactly zero error** against 216.0000 and 144.0000 outside-to-outside.
That closure is the main check — if a change breaks it, the change is wrong.

---
## 4. Measured orientations

Rotation is CCW about the section normal; `M` = mirrored. Counted across all identified instances.

| part | role | depth x face | orientations seen |
|---|---|---|---|
| A26948 | female channel | 2.280 x 1.125 | 270x16  0x5  90x4  180Mx4 |
| A26950 | glass adaptor | 2.250 x 0.803 | 270x8  90Mx8  0x3  180Mx3 |
| A26949 | male channel | 2.280 x 1.262 | 90x20 |
| A26952 | corner post | 2.265 x 2.402 | 0Mx5  270Mx5 |
| A7116 | 1x1 patio door trim tube | 1.000 x 1.000 | 0x9 |
| A62421 | top & bottom channel | 2.405 x 1.688 | 180x4  0x3 |
| A62420 | wall channel, vertical at the house | 2.438 x 1.250 | 270x3  90x3 |
| A29389 | sash frame | 0.425 x 1.000 | 0x2  180Mx2  90Mx1 |
| A33864 | slider side track | 2.250 x 0.897 | 270x1  90Mx1 |
| A33861 | slider top sill | 2.250 x 0.991 | 180x2 |
| A45216 | slider locking side track | 2.250 x 1.022 | 90x1  270Mx1 |
| A33863 | slider bottom sill | 2.250 x 1.023 | 0Mx2 |
| A22445 | centre meeting rail, sash | 0.575 x 1.250 | 90Mx1 |
| A22446 | centre meeting rail, lock side | 0.953 x 1.000 | 270Mx1 |
| A45217 | locking pull sash | 0.853 x 1.000 | 270Mx1 |

A26949 male is rot90 unmirrored in **all 20 instances** — the female-left/male-right rule, confirmed.
A26952 corner post is mirrored in every instance: rot0M on side walls, rot270M on the front.

**Open:** A26948 female appears at both rot270 (16) and rot90 (4). The profile is *not*
180-degree symmetric (self-distance 0.1308, far above the 0.02 match tolerance), so this is a real
difference, not a matcher artefact. The model currently uses rot270 throughout. Worth resolving.

---
## 5. Profile extraction — the traps

`extract_profiles.py` handles three encodings across the die files. Carried over from v1, unchanged.

- closed LWPOLYLINE on layer `0` — straightforward
- LINE+ARC wires — stitch endpoint to endpoint
- ACIS **REGION** — ezdxf's `acis.load()` FAILS. Use low-level `sab.parse_sab()` and walk
  `loop -> coedge -> edge -> vertex -> point`. **Apply the coedge `sense` flag** or every loop has gaps.
- Do NOT use FreeCAD's DXF importer: importing `importDXF` triggers a library download that
  hangs the RPC server. Build faces from explicit `Part` geometry instead.
- Layer `0` is the profile; `DIM`, `DIMENSION`, `IMP`, `APROVAL` are annotation.
- **A26949** is drawn without the closed flag and with a zero-length closing segment. That
  degenerate edge hangs FreeCAD. `clean_loops()` strips it.
- A26948 and A26949 need `.fix(1e-7,1e-7,1e-7)` before they are valid faces.
- `Part.Face.cutHoles()` mutates in place and returns None.

---
## 6. Placement method

Each member carries a basis `[u v w]`: world directions of die-local +x, +y, and the run.
Build it by composing the part's section orientation with the wall's section-to-world transform,
rather than deriving it — the drawing already knows.

```
plan (vertical members):   FRONT (sx,sy)->(X,Y)   LEFT (sx,sy)->(-Y,X)   RIGHT (sx,sy)->(Y,-X)
vertical section (horizontal members):  sy->Z,  sx-> outward normal of the wall
```
Anchor the **outside face** of the finished solid onto the member origin — min on FRONT and LEFT,
max in X on RIGHT. Anchoring bbox-min everywhere puts the right wall out by one channel depth.

---
## 7. Bugs already paid for — do not repeat

| bug | symptom | fix |
|---|---|---|
| `Placement` set after `translate()` | profiles at raw DXF coords | fold centring into the placement |
| roll left to `Rotation(Z,d)` | channels upside down on some walls | drive orientation from the sections |
| through-wall axis from run direction | 7 members backwards | take it from the sections |
| `makeHalfSpace` mitre | members silently deleted | explicit rotated cutting boxes |
| mitre origin at wall centreline | zero overlap but an OPEN joint | check gap AND overlap |
| corner-post engagement at the house end | side wall out by exactly 0.1270 | it is a nest, not a butt |
| bbox-min anchor on the right wall | X overshoot of exactly 2.438 | anchor the outside face |

Every one of these was silent. The checks that caught them: overall extents against expectation,
`common().Volume` for interference AND `distToShape()` for contact, left/right symmetry to 0.00000,
and run closure to zero.

---
## 8. Still to do

1. Panel infill: solid, glass with A26950 all round, prefab door, slider window.
2. Slider sash assembly: A29389, A45217, A22445, A22446, mitred corners.
3. Patio door: 3 mitred A7116 trim tubes, and the bottom channel omitted across the opening.
4. Side wall top/bottom channels: butt to posts with mitred vertical legs for the rake. Not yet cut.
5. Resolve the A26948 rot270 / rot90 question.
6. Individual panels as separate documents, assembled by snapping.
7. Roof.