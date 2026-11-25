"""3D room definition for the 225 sunroom.
World axes:  X = along front wall (0 -> 216), Y = depth front(0) -> house(144), Z = height.
Front wall is the LOW eave (84).  House end is HIGH (96).  Rake = 1:12 over 144.
"""
import json
FRONT_W = 216.00
DEPTH   = 144.00
H_LOW   = 84.00
H_HIGH  = 96.00

def z_at(y):                       # rake along the side walls
    return H_LOW + (H_HIGH - H_LOW) * (y / DEPTH)

members = []
def add(wall, tag, part, p0, p1, note=""):
    members.append({"wall":wall,"tag":tag,"part":part,
                    "start":[round(v,4) for v in p0],"end":[round(v,4) for v in p1],"note":note})

# ---------------- LEFT WALL  (X = 0 plane, runs Y 0 -> 144) ----------------
# drawing x=-62.51 is the HOUSE end (h=96); x=81.49 is the FRONT corner (h=84)
def left(ydraw):                   # map drawing x -> world Y
    return DEPTH - (ydraw - (-62.51)) * (DEPTH / 144.00)

add("LEFT","M04","A62420", [0, left(-61.76), 0], [0, left(-61.76), H_HIGH], "wall channel at house")
add("LEFT","M06","A26952", [0, left(80.36),  0], [0, left(80.36),  H_LOW ], "corner post at front")
add("LEFT","M05","A26949", [0, left(12.49),  0], [0, left(12.49),  z_at(left(12.49))], "mullion, panel 1|2")
add("LEFT","M01","A62421", [0, left(-62.51), 0], [0, left(81.49),  0], "bottom channel")
add("LEFT","M03","A62421", [0, left(-62.51), H_HIGH], [0, left(81.49), H_LOW], "top channel, raked")
add("LEFT","M00","A26948", [0, left(-61.01), 79.50], [0, left(79.24), 79.50], "head / transom rail")
# --- S-S slider sash frame, sits INSIDE panel 2 opening (Y 2.25 -> 69.00, Z 24.00 -> 79.50) ---
SL_Y0, SL_Y1, SL_Z0, SL_Z1 = 2.25, 69.00, 24.00, 79.50
add("LEFT","S1","A33863", [0, SL_Y1, SL_Z0], [0, SL_Y0, SL_Z0], "slider bottom sill")
add("LEFT","S2","A33861", [0, SL_Y1, SL_Z1], [0, SL_Y0, SL_Z1], "slider top sill")
add("LEFT","S3","A33864", [0, SL_Y0, SL_Z0], [0, SL_Y0, SL_Z1], "slider side track (corner end)")
add("LEFT","S4","A45216", [0, SL_Y1, SL_Z0], [0, SL_Y1, SL_Z1], "slider locking side track (mullion end)")

# ---------------- RIGHT WALL  (mirror of LEFT about X = FRONT_W/2) ----------------
for m in [x for x in members if x["wall"]=="LEFT"]:
    add("RIGHT", m["tag"], m["part"],
        [FRONT_W - m["start"][0], m["start"][1], m["start"][2]],
        [FRONT_W - m["end"][0],   m["end"][1],   m["end"][2]],
        m["note"] + " (mirrored)")

# ---------------- FRONT WALL  (Y = 0 plane, runs X 0 -> 216, flat 84) ----------------
BAYS = 4
inner0, inner1 = 2.25, FRONT_W - 2.25      # inside faces of the corner posts
span = (inner1 - inner0) / BAYS
add("FRONT","M11","A26952", [0,        0, 0], [0,        0, H_LOW], "corner post left")
add("FRONT","M15","A26952", [FRONT_W,  0, 0], [FRONT_W,  0, H_LOW], "corner post right")
for i in range(1, BAYS):
    x = inner0 + i*span
    add("FRONT", f"M1{1+i}", "A26949", [x, 0, 0], [x, 0, H_LOW], f"mullion {i}")
add("FRONT","M07","A62421", [0, 0, 0],      [FRONT_W, 0, 0],      "bottom channel")
add("FRONT","M08","A62421", [0, 0, H_LOW],  [FRONT_W, 0, H_LOW],  "top channel")
add("FRONT","M09","A26948", [inner0, 0, 24.00], [inner1, 0, 24.00], "rail below glass")
add("FRONT","M10","A26948", [inner0, 0, 79.50], [inner1, 0, 79.50], "rail above glass")

json.dump({"front_width":FRONT_W,"depth":DEPTH,"h_low":H_LOW,"h_high":H_HIGH,
           "members":members}, open("room_def.json","w"), indent=1)

print(f"{'wall':6s} {'tag':5s} {'part':8s} {'start':>26s} {'end':>26s}  note")
for m in members:
    s="(%7.2f,%7.2f,%6.2f)"%tuple(m["start"]); e="(%7.2f,%7.2f,%6.2f)"%tuple(m["end"])
    print(f"{m['wall']:6s} {m['tag']:5s} {m['part']:8s} {s:>26s} {e:>26s}  {m['note']}")
print(f"\n{len(members)} members  |  footprint {FRONT_W} x {DEPTH}  |  height {H_LOW} front -> {H_HIGH} house")
