# 225 Sunroom — Build Reference

Working reference for the FreeCAD model of the 225-series sunroom.
Written to be read cold: assume no memory of how any of this was derived.

Source drawing: `Sunroom-Drawings/225-Room-Description.dxf`  
Profiles: `DXF FILES FOR DIES/DXF FILES FOR DIES/`  
Scripts: `sunroom_build/` — `extract_profiles.py`, `room_def3.py`, `gen_reference.py`

---

## 1. Coordinate system

```
X  along the front wall,  0 -> 216   (left corner to right corner)
Y  depth,  front wall = 0,  house wall = 144
Z  height,  floor = 0
```
Front wall is the LOW eave at 84.0. House end is HIGH at 96.0. Rake 1:12 over 144.0.

Outward normals: LEFT `(-1,0,0)` · RIGHT `(+1,0,0)` · FRONT `(0,-1,0)`

---

## 2. Orientation rules — READ BEFORE PLACING ANY PART

Every profile is drawn in its die file on a local XY plane and extruded along local +z.
Placement is a frame `[u v w]` where `u` = world direction of local +x, `v` = local +y, `w` = the run.

**Rule 1 — local +x is the THROUGH-WALL axis.**  
The ~2.25" dimension of every profile is the system depth. The smaller dimension is the visible face width.

**Rule 2 — local +x must point OUT of the room.**  
Applies to every member except corner posts. If `u · outward < 0`, reverse the member's run direction
(swap start/end). That flips `u` while preserving `v`. Do NOT flip `v` to fix it.

**Rule 3 — local +y is the profile's OPEN side.**  
Detect it geometrically: `bbox_centre - area_centroid` points toward the opening. Then:

| member | opening faces |
|---|---|
| bottom channels | UP `(0,0,+1)` |
| top channels | DOWN `(0,0,-1)` |
| rail below glass | UP |
| rail above glass | DOWN |
| slider bottom sill | UP |
| slider top sill | DOWN |

**Rule 4 — corner posts are oriented by their RIBS, not by the wall normal.**  
A26952 carries ribs on local **-x** and local **-y** — the two outer legs of the L.
Those two faces must point out of the room.

| post | rotation | `normal` arg | ribs face |
|---|---|---|---|
| front-left | none | `[1,0,0]` | -X and -Y |
| front-right | 90 deg CCW | `[0,1,0]` | +X and -Y |

**Rule 5 — the right wall is NOT a mirror of the left.**  
You cannot mirror an extrusion; it is the same die. Handed parts must be ROTATED.
Symmetric parts (channels, mullions) happen to look the same either way — which is exactly why
a mirroring bug here stays invisible until someone checks the through-wall axis.

---

## 3. Key dimensions

| quantity | value | where it comes from |
|---|---|---|
| channel height | 1.6875 | A62421 face width |
| channel depth | 2.4050 | A62421 through-wall |
| channel leg thickness | 0.0620 | scanline through A62421 |
| post outside face offset | 1.1405 | half channel depth minus leg |
| vertical seat into bottom channel | 1.1260 | given |
| male/female snap overlap | 0.1370 | given — NOT YET APPLIED |
| patio door clear opening | 72.994 | computed, matches the 6 ft door |
| vertical ZMin | 0.5615 | channel height minus seat |

Verticals currently STOP at the underside of the top channel. Whether they seat up into it
by the same 1.126 is **still unconfirmed**.

---

## 4. Part inventory

| part | role | depth | face | area in^2 | die file encoding |
|---|---|---|---|---|---|
| A62420 | wall channel (at house) | 2.438 | 1.250 | 0.3019 | closed polyline |
| A62421 | top & bottom channel | 2.405 | 1.688 | 0.4097 | line+arc wire |
| A26948 | female channel | 2.280 | 1.125 | 0.4210 | closed polyline |
| A26949 | male channel | 2.280 | 1.262 | 0.4385 | polyline (UNCLOSED flag) |
| A26952 | corner post | 2.265 | 2.402 | 0.4308 | closed polyline |
| A26950 | glass adaptor | 2.250 | 0.803 | 0.2851 | closed polyline |
| A33861 | slider top sill | 2.250 | 0.991 | 0.3985 | closed polyline |
| A33863 | slider bottom sill | 2.250 | 1.023 | 0.3666 | line+arc wire |
| A33864 | slider side track | 2.250 | 0.897 | 0.3210 | closed polyline |
| A45216 | slider locking side track | 2.250 | 1.022 | 0.3803 | closed polyline |

---

## 5. Profile extraction — the traps

Three different encodings exist across the 47 die files. `extract_profiles.py` handles all three.

- **32 files**: closed LWPOLYLINE on layer `0`. Straightforward.
- **7 files**: LINE+ARC wires on layer `0`. Must be stitched endpoint-to-endpoint.
- **5 files**: ACIS **REGION** entities. ezdxf's high-level `acis.load()` FAILS on these
  (chokes on a transform record). Use the low-level `sab.parse_sab()` and walk
  `loop -> coedge -> edge -> vertex -> point` by hand. **The coedge `sense` flag must be applied** —
  without it every loop has gaps. FreeCAD's own DXF importer is NOT needed and should be avoided:
  importing `importDXF` triggers a library download that hangs the RPC server.

- Layer `0` is always the profile. `DIM`, `DIMENSION`, `IMP`, `APROVAL` are annotation.
- **A26949** has its profile polyline drawn WITHOUT the closed flag and with a zero-length
  closing segment. That degenerate edge hung FreeCAD twice. `clean_loops()` strips it.
- A26948 and A26949 build invalid faces until `.fix(1e-7,1e-7,1e-7)` is called.
- A65733 / A65734 (3125 series) are hollow — nested inner loop. Use `Part.Face(outer).cutHoles([inner])`;
  `cutHoles` mutates IN PLACE and returns None.

---

## 6. Bugs already paid for — do not repeat

| bug | symptom | fix |
|---|---|---|
| `Placement` set after `translate()` | profiles at raw DXF coords, extents 233 not 217 | fold centring in: `t = p0 - rot*c` |
| roll left to `Rotation(Z, d)` | channels upside down on some walls only | drive `v` from the opening direction |
| through-wall axis left to run direction | 7 members backwards inc. RIGHT_TC | enforce Rule 2, reverse run |
| `makeHalfSpace` mitre | 4 channels silently deleted entirely | use explicit rotated cutting boxes |
| mitre origin at wall centreline | zero overlap but also an OPEN joint | origin at outer corner; check gap AND overlap |
| corner post placed at wall line | post proud of the channels | outside face at `OFF` from wall line |
| duplicate corner posts | one per wall = 4 posts | one shared post per corner = 2 |

**Verification habit that caught most of these:** check overall extents against expected,
and check BOTH `common().Volume` (no interference) AND `distToShape()` (actually touching).
Left/right volume delta and X-symmetry error should both be exactly 0.00000.

---

## 7. Member schedule

| wall | tag | part | start | end | orientation |
|---|---|---|---|---|---|
| CORNER | CP_L | A26952 | (-0.01, 0.06, 0.56) | (-0.01, 0.06, 82.31) | normal [1, 0, 0] |
| CORNER | CP_R | A26952 | (215.94, -0.01, 0.56) | (215.94, -0.01, 82.31) | normal [0, 1, 0] |
| LEFT | WC | A62420 | (0.00, 143.25, 0.56) | (0.00, 143.25, 94.25) | normal [-1, 0, 0] |
| LEFT | MULL | A26949 | (0.00, 69.00, 0.56) | (0.00, 69.00, 88.06) | normal [-1, 0, 0] |
| LEFT | BC1 | A62421 | (0.00, -1.20, 0.84) | (0.00, 69.63, 0.84) | vdir [0, 0, 1] |
| LEFT | BC2 | A62421 | (0.00, 142.62, 0.84) | (0.00, 143.88, 0.84) | vdir [0, 0, 1] |
| LEFT | TC | A62421 | (0.00, 144.00, 95.16) | (0.00, -1.20, 83.06) | vdir [0, 0, -1] |
| LEFT | HEAD | A26948 | (0.00, 142.62, 79.50) | (0.00, 2.40, 79.50) | normal [-1, 0, 0] |
| LEFT | S1 | A33863 | (0.00, 68.37, 24.00) | (0.00, 2.40, 24.00) | vdir [0, 0, 1] |
| LEFT | S2 | A33861 | (0.00, 68.37, 79.50) | (0.00, 2.40, 79.50) | vdir [0, 0, -1] |
| LEFT | S3 | A33864 | (0.00, 2.40, 24.00) | (0.00, 2.40, 79.50) | normal [-1, 0, 0] |
| LEFT | S4 | A45216 | (0.00, 68.37, 24.00) | (0.00, 68.37, 79.50) | normal [-1, 0, 0] |
| RIGHT | WC | A62420 | (216.00, 143.25, 0.56) | (216.00, 143.25, 94.25) | normal [1, 0, 0] |
| RIGHT | MULL | A26949 | (216.00, 69.00, 0.56) | (216.00, 69.00, 88.06) | normal [1, 0, 0] |
| RIGHT | BC1 | A62421 | (216.00, -1.20, 0.84) | (216.00, 69.63, 0.84) | vdir [0, 0, 1] |
| RIGHT | BC2 | A62421 | (216.00, 142.62, 0.84) | (216.00, 143.88, 0.84) | vdir [0, 0, 1] |
| RIGHT | TC | A62421 | (216.00, 144.00, 95.16) | (216.00, -1.20, 83.06) | vdir [0, 0, -1] |
| RIGHT | HEAD | A26948 | (216.00, 142.62, 79.50) | (216.00, 2.40, 79.50) | normal [1, 0, 0] |
| RIGHT | S1 | A33863 | (216.00, 68.37, 24.00) | (216.00, 2.40, 24.00) | vdir [0, 0, 1] |
| RIGHT | S2 | A33861 | (216.00, 68.37, 79.50) | (216.00, 2.40, 79.50) | vdir [0, 0, -1] |
| RIGHT | S3 | A33864 | (216.00, 2.40, 24.00) | (216.00, 2.40, 79.50) | normal [1, 0, 0] |
| RIGHT | S4 | A45216 | (216.00, 68.37, 24.00) | (216.00, 68.37, 79.50) | normal [1, 0, 0] |
| FRONT | BC | A62421 | (-1.20, 0.00, 0.84) | (217.20, 0.00, 0.84) | vdir [0, 0, 1] |
| FRONT | TC | A62421 | (-1.20, 0.00, 83.16) | (217.20, 0.00, 83.16) | vdir [0, 0, -1] |
| FRONT | MULL1 | A26949 | (55.20, 0.00, 0.56) | (55.20, 0.00, 82.31) | normal [0, -1, 0] |
| FRONT | MULL2 | A26949 | (108.00, 0.00, 0.56) | (108.00, 0.00, 82.31) | normal [0, -1, 0] |
| FRONT | MULL3 | A26949 | (160.80, 0.00, 0.56) | (160.80, 0.00, 82.31) | normal [0, -1, 0] |
| FRONT | R_LO | A26948 | (2.40, 0.00, 24.00) | (213.60, 0.00, 24.00) | vdir [0, 0, 1] |
| FRONT | R_HI | A26948 | (2.40, 0.00, 79.50) | (213.60, 0.00, 79.50) | vdir [0, 0, -1] |

---

## 8. Next iteration — individual panels

Plan: draw each panel as its own document, then assemble by snapping male into female.

- Snap engagement is **0.137"**. Panel pitch = panel width minus 0.137 per joint.
- Male = A26949, female = A26948. Each panel carries female on one edge, male on the other.
- The top and bottom channels and the corner posts are NOT part of a panel. They are room-level
  parts and must be re-cut to suit the final assembled panel run:
  - channels run corner to corner and mitre at 45 from the OUTER corner
  - channels extend to +/-1.2025 past the wall lines
  - corner post outside faces sit at 1.1405 from the wall line
- At patio/entrance door openings the bottom channel STOPS at the door-side face of the flanking
  verticals so the door sits on the floor. A short stub remains under the wall channel.
- Accumulated snap overlap shortens the total run. Re-derive channel lengths from the assembled
  panels rather than from nominal wall length, or the mitres will not close.

---

## 9. Open questions

1. Do verticals seat UP into the top channel by 1.126, as they do at the bottom?
2. Slider sills A33861 / A33863 currently lean outward through the wall. Correct for an OX slider,
   or should they flip? They are symmetric left-to-right either way.
3. The 0.137 snap is recorded but NOT yet applied anywhere in the model.
4. Glass, patio doors, slider sashes and the roof are not modelled.
5. Wall planes currently straddle X=0 / X=216 rather than those being outside faces.