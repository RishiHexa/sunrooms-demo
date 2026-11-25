"""225 sunroom - room definition v2.
X = along front wall 0->216 | Y = depth, front 0 -> house 144 | Z = height.
Rules applied:
  * ~2.25" profile dimension is the THROUGH-WALL depth (local +x -> wall outward normal)
  * verticals sit ON the bottom channel; channels stack, they do not interpenetrate
  * at patio-door openings the bottom channel stops at the door-side face of the
    flanking verticals; a short stub remains under the wall channel
  * one corner post per corner, shared by side wall and front wall
"""
import json, math

P = json.load(open('profiles_225.json'))
def dims(n):
    xs=[];ys=[]
    for lp in P[n]['loops']:
        for s in lp:
            for p in s[1:]: xs.append(p[0]); ys.append(p[1])
    return max(xs)-min(xs), max(ys)-min(ys)      # (depth ~2.25, face width)

FRONT_W, DEPTH, H_LOW, H_HIGH = 216.00, 144.00, 84.00, 96.00
OVERLAP = 0.137                                   # male/female snap engagement
CH   = dims('A62421')[1]                          # 1.688 channel height
CP_D, CP_W = dims('A26952')                       # corner post
MULL_W = dims('A26949')[1]                        # 1.262
WC_W   = dims('A62420')[1]                        # 1.250

Z_BOT   = CH                                      # top of bottom channel
def rake_z(y):  return H_LOW + (H_HIGH-H_LOW)*(y/DEPTH)
def top_u(y):   return rake_z(y) - CH             # underside of raked top channel

WALL_Y = 143.25                                   # wall-channel centreline (from drawing)
MULL_Y = 69.00                                    # side-wall mullion centreline
CP_C   = CP_W/2                                   # corner post half width

door_face_m = MULL_Y + MULL_W/2                   # 69.631
door_face_w = WALL_Y - WC_W/2                     # 142.625

members=[]
def add(wall,tag,part,p0,p1,note="",normal=None):
    members.append({"wall":wall,"tag":tag,"part":part,
                    "start":[round(v,4) for v in p0],"end":[round(v,4) for v in p1],
                    "note":note,"normal":normal})

# ---------- corner posts (shared) ----------
add("CORNER","CP_L","A26952",[CP_C,CP_C,Z_BOT],[CP_C,CP_C,H_LOW-CH],"front-left corner post",[0,0,1])
add("CORNER","CP_R","A26952",[FRONT_W-CP_C,CP_C,Z_BOT],[FRONT_W-CP_C,CP_C,H_LOW-CH],"front-right corner post",[0,0,1])

# ---------- side walls ----------
def side_wall(name, X, nx):
    n=[nx,0,0]
    add(name,"WC","A62420",[X,WALL_Y,Z_BOT],[X,WALL_Y,top_u(WALL_Y)],"wall channel at house",n)
    add(name,"MULL","A26949",[X,MULL_Y,Z_BOT],[X,MULL_Y,top_u(MULL_Y)],"mullion panel 1|2",n)
    # bottom channel: corner post -> door-side face of mullion  (runs under the mullion)
    add(name,"BC1","A62421",[X,CP_W,CH/2],[X,door_face_m,CH/2],"bottom channel (panel 2 run)",n)
    # stub under the wall channel; gap between = the patio door opening
    add(name,"BC2","A62421",[X,door_face_w,CH/2],[X,WALL_Y+WC_W/2,CH/2],"bottom channel stub at wall",n)
    # raked top channel, offset one channel-height below the roof line
    add(name,"TC","A62421",[X,DEPTH,rake_z(DEPTH)-CH/2],[X,CP_W,rake_z(CP_W)-CH/2],"top channel (raked)",n)
    add(name,"HEAD","A26948",[X,door_face_w,79.50],[X,CP_W,79.50],"head / transom rail",n)
    # S-S slider sash frame inside panel 2
    y0,y1,z0,z1 = CP_W, MULL_Y-MULL_W/2, 24.00, 79.50
    add(name,"S1","A33863",[X,y1,z0],[X,y0,z0],"slider bottom sill",n)
    add(name,"S2","A33861",[X,y1,z1],[X,y0,z1],"slider top sill",n)
    add(name,"S3","A33864",[X,y0,z0],[X,y0,z1],"slider side track (corner end)",n)
    add(name,"S4","A45216",[X,y1,z0],[X,y1,z1],"slider lock track (mullion end)",n)
side_wall("LEFT", 0.0, -1)
side_wall("RIGHT", FRONT_W, +1)

# ---------- front wall ----------
n=[0,-1,0]
x0, x1 = CP_W, FRONT_W-CP_W
add("FRONT","BC","A62421",[x0,0,CH/2],[x1,0,CH/2],"bottom channel",n)
add("FRONT","TC","A62421",[x0,0,H_LOW-CH/2],[x1,0,H_LOW-CH/2],"top channel",n)
span=(x1-x0)/4
for i in range(1,4):
    add("FRONT",f"MULL{i}","A26949",[x0+i*span,0,Z_BOT],[x0+i*span,0,H_LOW-CH],f"mullion {i}",n)
add("FRONT","R_LO","A26948",[x0,0,24.00],[x1,0,24.00],"rail below glass",n)
add("FRONT","R_HI","A26948",[x0,0,79.50],[x1,0,79.50],"rail above glass",n)

json.dump({"front_width":FRONT_W,"depth":DEPTH,"h_low":H_LOW,"h_high":H_HIGH,
           "overlap":OVERLAP,"channel_h":CH,"members":members},
          open('room_def2.json','w'), indent=1)

print(f"channel height {CH:.3f}   corner post {CP_D:.3f} x {CP_W:.3f}   overlap {OVERLAP}")
print(f"patio door opening  {door_face_w-door_face_m:.3f}\"  (Y {door_face_m:.3f} -> {door_face_w:.3f})   x2 walls")
print(f"front bay span {span:.3f}\"  x4")
print(f"\n{len(members)} members")
for m in members:
    print(f"  {m['wall']:6s} {m['tag']:6s} {m['part']:8s} "
          f"({m['start'][0]:7.2f},{m['start'][1]:7.2f},{m['start'][2]:6.2f}) -> "
          f"({m['end'][0]:7.2f},{m['end'][1]:7.2f},{m['end'][2]:6.2f})  {m['note']}")
