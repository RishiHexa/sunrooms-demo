"""225 sunroom - room definition v3.
Adds: deterministic channel opening direction, verticals seated INTO the bottom
channel by SEAT, channels run to the corners for mitring.
Orientation modes per member:
  'vdir'   -> local +y (the profile's OPEN side) maps to this world direction
  'normal' -> local +x (through-wall) maps to this world direction
"""
import json

P = json.load(open('profiles_225.json'))
def dims(n):
    xs=[];ys=[]
    for lp in P[n]['loops']:
        for s in lp:
            for p in s[1:]: xs.append(p[0]); ys.append(p[1])
    return max(xs)-min(xs), max(ys)-min(ys)

FRONT_W, DEPTH, H_LOW, H_HIGH = 216.00, 144.00, 84.00, 96.00
OVERLAP = 0.137
SEAT    = 1.126                      # verticals drop INTO the bottom channel by this
CH      = dims('A62421')[1]          # 1.688
CP_D, CP_W = dims('A26952')
MULL_W  = dims('A26949')[1]
WC_W    = dims('A62420')[1]

Z_V0 = CH - SEAT                     # 0.562  bottom of every vertical
def rake_z(y): return H_LOW + (H_HIGH-H_LOW)*(y/DEPTH)
def top_u(y):  return rake_z(y) - CH

WALL_Y, MULL_Y = 143.25, 69.00
CP_C = CP_W/2
door_m = MULL_Y + MULL_W/2
door_w = WALL_Y - WC_W/2

UP, DOWN = [0,0,1], [0,0,-1]
members=[]
def add(wall,tag,part,p0,p1,note="",vdir=None,normal=None,mitre=None):
    members.append({"wall":wall,"tag":tag,"part":part,
        "start":[round(v,4) for v in p0],"end":[round(v,4) for v in p1],
        "note":note,"vdir":vdir,"normal":normal,"mitre":mitre})

# corner posts
# corner posts: ribs are on local -x and -y, so those two faces must point out of the room.
# outside face sits on the INNER face of the channel's outer leg  =  HALF_CH - LEG from the wall line.
HALF_CH = dims('A62421')[0]/2.0        # 1.2025
LEG     = 0.0620                        # channel wall thickness
OFF     = HALF_CH - LEG                 # 1.1405
# CP_L: no rotation  -> ribs face -X and -Y
CPL = [-OFF + CP_D/2.0, -OFF + CP_W/2.0]
add("CORNER","CP_L","A26952",[CPL[0],CPL[1],Z_V0],[CPL[0],CPL[1],H_LOW-CH],
    "front-left corner post (ribs -X,-Y)",normal=[1,0,0])
# CP_R: 90 CCW -> local x maps to +Y, local y maps to -X, ribs face +X and -Y
CPR = [FRONT_W + OFF - CP_W/2.0, -OFF + CP_D/2.0]
add("CORNER","CP_R","A26952",[CPR[0],CPR[1],Z_V0],[CPR[0],CPR[1],H_LOW-CH],
    "front-right corner post (ribs +X,-Y)",normal=[0,1,0])

def side(name, X, nx, corner):
    n=[nx,0,0]
    add(name,"WC","A62420",[X,WALL_Y,Z_V0],[X,WALL_Y,top_u(WALL_Y)],"wall channel",normal=n)
    add(name,"MULL","A26949",[X,MULL_Y,Z_V0],[X,MULL_Y,top_u(MULL_Y)],"mullion",normal=n)
    add(name,"BC1","A62421",[X,-HALF_CH,CH/2],[X,door_m,CH/2],"bottom channel",vdir=UP,mitre=corner)
    add(name,"BC2","A62421",[X,door_w,CH/2],[X,WALL_Y+WC_W/2,CH/2],"bottom channel stub",vdir=UP)
    add(name,"TC","A62421",[X,DEPTH,rake_z(DEPTH)-CH/2],[X,-HALF_CH,rake_z(-HALF_CH)-CH/2],"top channel (raked)",vdir=DOWN,mitre=corner)
    add(name,"HEAD","A26948",[X,door_w,79.50],[X,CP_W,79.50],"head rail",normal=n)
    y0,y1,z0,z1 = CP_W, MULL_Y-MULL_W/2, 24.00, 79.50
    add(name,"S1","A33863",[X,y1,z0],[X,y0,z0],"slider bottom sill",vdir=UP)
    add(name,"S2","A33861",[X,y1,z1],[X,y0,z1],"slider top sill",vdir=DOWN)
    add(name,"S3","A33864",[X,y0,z0],[X,y0,z1],"slider side track",normal=n)
    add(name,"S4","A45216",[X,y1,z0],[X,y1,z1],"slider lock track",normal=n)
side("LEFT", 0.0, -1, "FL")
side("RIGHT", FRONT_W, +1, "FR")

n=[0,-1,0]
add("FRONT","BC","A62421",[-HALF_CH,0,CH/2],[FRONT_W+HALF_CH,0,CH/2],"bottom channel",vdir=UP,mitre="FL|FR")
add("FRONT","TC","A62421",[-HALF_CH,0,H_LOW-CH/2],[FRONT_W+HALF_CH,0,H_LOW-CH/2],"top channel",vdir=DOWN,mitre="FL|FR")
x0,x1 = CP_W, FRONT_W-CP_W
span=(x1-x0)/4
for i in range(1,4):
    add("FRONT",f"MULL{i}","A26949",[x0+i*span,0,Z_V0],[x0+i*span,0,H_LOW-CH],f"mullion {i}",normal=n)
add("FRONT","R_LO","A26948",[x0,0,24.00],[x1,0,24.00],"rail below glass",vdir=UP)
add("FRONT","R_HI","A26948",[x0,0,79.50],[x1,0,79.50],"rail above glass",vdir=DOWN)

json.dump({"front_width":FRONT_W,"depth":DEPTH,"h_low":H_LOW,"h_high":H_HIGH,
           "overlap":OVERLAP,"seat":SEAT,"channel_h":CH,"half_ch":HALF_CH,"leg":LEG,"off":OFF,"members":members},
          open('room_def3.json','w'), indent=1)
print(f"corner outer-leg offset OFF={OFF:.4f}  CP_L bbox X {-OFF:.4f}..{-OFF+CP_D:.4f} Y {-OFF:.4f}..{-OFF+CP_W:.4f}")
print(f"channel h {CH:.3f}  seat {SEAT}  vertical ZMin {Z_V0:.3f}  door opening {door_w-door_m:.3f}")
print(f"{len(members)} members;  mitred: {[m['tag']+'@'+str(m['mitre']) for m in members if m['mitre']]}")
