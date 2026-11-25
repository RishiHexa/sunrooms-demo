"""Full member list in world coordinates.
Section conventions: horizontal (plan) = outside at BOTTOM ; vertical = outside to the RIGHT.
"""
import json, math
L=json.load(open('layout.json')); P=json.load(open('profiles_all.json'))
def dims(n):
    xs=[];ys=[]
    for lp in P[n]['loops']:
        for s in lp:
            for p in s[1:]: xs.append(p[0]); ys.append(p[1])
    return max(xs)-min(xs), max(ys)-min(ys)

FW,DP,HL,HH = L['front_w'],L['depth'],L['h_low'],L['h_high']
CH_D,CH_H = L['ch_d'],L['ch_h']
P_SIDE={'LEFT':L['post_left'],'RIGHT':L['post_right']}   # post is not square; per-wall
FEMW,MALW,WCW = L['fem_w'],L['male_w'],L['wc_w']
E=lambda a,b: L['engage'][f"{a}|{b}"]
RAIL_H = dims('A26948')[1]
Z_LO, Z_HI = 24.00, 79.50           # glass opening, from 225-Room-Description.dxf
# Vertical members (female, male, corner posts, wall channels) do NOT run to the outside
# faces of the top/bottom channels. They sit INSIDE them, overlapping by SEAT at each end.
# Measured from Top-Bottom-Channel_placement.dxf: 1.1256 at the bottom and 1.1256 at the top.
SEAT = 1.1256
Z_V0 = CH_H - SEAT                  # 0.5624  bottom end of every vertical member
def z_v1(wall,y):                   # top end: SEAT up inside the top channel
    return z_top(wall,y) - CH_H + SEAT

def mat(rot,mir):
    c,s={0:(1,0),90:(0,1),180:(-1,0),270:(0,-1)}[rot]
    Mx=-1 if mir else 1
    return ((c*Mx,-s),(s*Mx,c))
PLAN={'FRONT':((1,0),(0,1)),'LEFT':((0,1),(-1,0)),'RIGHT':((0,-1),(1,0))}
SECX={'FRONT':(0,-1),'LEFT':(-1,0),'RIGHT':(1,0)}
def cplan(wall,rot,mir):
    M=mat(rot,mir); T=PLAN[wall]
    ap=lambda v:(T[0][0]*v[0]+T[0][1]*v[1], T[1][0]*v[0]+T[1][1]*v[1])
    a=ap((M[0][0],M[1][0])); b=ap((M[0][1],M[1][1]))
    return (a[0],a[1],0.0),(b[0],b[1],0.0),(0.0,0.0,1.0)
def csect(wall,rot,mir,run):
    M=mat(rot,mir); sx=SECX[wall]
    ap=lambda v:(sx[0]*v[0], sx[1]*v[0], v[1])
    a=ap((M[0][0],M[1][0])); b=ap((M[0][1],M[1][1]))
    n=math.sqrt(sum(c*c for c in run)); w=tuple(c/n for c in run)
    return a,b,w

MEM=[]
def add(wall,tag,part,u,v,w,origin,length,note="",anchor=None,req=None,mitre=None):
    """req = required world direction of the profile's OPEN side. The builder rotates the
       member 180 about its own run axis if the opening comes out facing the wrong way.
       This is the only reliable way to keep LEFT and RIGHT consistent: an extrusion cannot
       be mirrored, so a fixed section rotation lands differently on opposite walls."""
    MEM.append({'wall':wall,'tag':tag,'part':part,'u':list(u),'v':list(v),'w':list(w),
                'origin':[round(x,5) for x in origin],'length':round(length,5),
                'note':note,'anchor':anchor,'req':req,'mitre':mitre})

O_FEM,O_MALE,O_WC = (270,False),(90,False),(270,False)
O_POST={'LEFT':(180,True),'RIGHT':(90,True),'FRONT':(270,True)}   # LEFT +180 CCW, RIGHT +90 CCW: ribs to the outside
O_BOT,O_TOP = (0,False),(180,False)
O_RAIL_HI,O_RAIL_LO = (0,False),(180,True)     # above / below the glass
z_top=lambda wall,y: HL if wall=='FRONT' else HL+(HH-HL)*(y/DP)

# ---------------- corner posts ----------------
for tag,(px,py),wall in (('CP_L',(0.0,0.0),'LEFT'),('CP_R',(FW,0.0),'RIGHT')):
    u,v,w=cplan(wall,*O_POST[wall])
    add('CORNER',tag,'A26952',u,v,w,(px,py,Z_V0),z_v1('FRONT',0.0)-Z_V0,'corner post, seated in the channels')

# ---------------- vertical channels ----------------
# female LEFT / male RIGHT as seen from OUTSIDE each wall (see layout2.py)
SEQ={'FRONT':L['front_seq'],'LEFT':L['left_seq'],'RIGHT':L['right_seq']}
AT ={'FRONT':lambda t:(t,0.0),'LEFT':lambda t:(0.0,t),'RIGHT':lambda t:(FW,t)}
def verts(wall):
    for i,(f0,m1) in enumerate(SEQ[wall]):
        d = 1 if m1>f0 else -1
        fy0 = min(f0, f0+d*FEMW); my0 = min(m1-d*MALW, m1)
        for part,o,pos in (('A26948',O_FEM,fy0),('A26949',O_MALE,my0)):
            u,v,w=cplan(wall,*o); p=AT[wall](pos)
            add(wall,f"P{i+1}_{'F' if part=='A26948' else 'M'}",part,u,v,w,(p[0],p[1],Z_V0),
                z_v1(wall,p[1])-Z_V0,f"panel {i+1}")
for _w in ('FRONT','LEFT','RIGHT'): verts(_w)

# ---------------- wall channels at the house ----------------
for wall,x in (('LEFT',0.0),('RIGHT',FW)):
    u,v,w=cplan(wall,*O_WC); add(wall,'WC','A62420',u,v,w,(x,DP-WCW,Z_V0),z_v1(wall,DP)-Z_V0,'wall channel at house',req=[0,-1,0])

# ---------------- perimeter channels ----------------
u,v,w=csect('FRONT',*O_BOT,(1,0,0)); add('FRONT','BC','A62421',u,v,w,(0.0,0.0,0.0),FW,'front bottom channel',req=[0,0,1],mitre='FL|FR')
u,v,w=csect('FRONT',*O_TOP,(1,0,0)); add('FRONT','TC','A62421',u,v,w,(0.0,0.0,HL-CH_H),FW,'front top channel',req=[0,0,-1],mitre='FL|FR')

def house_panel(wall):
    "index of the panel at the house end (Y=DP) - that is the patio door"
    seq=SEQ[wall]
    return max(range(len(seq)), key=lambda i: max(seq[i]))
def panel_span(wall,i):
    "clear opening of panel i along the wall axis (between the vertical channels)"
    f0,m1=SEQ[wall][i]; d = 1 if m1>f0 else -1
    a = f0 + d*FEMW; b = m1 - d*MALW
    return (min(a,b), max(a,b))

for wall,x in (('LEFT',0.0),('RIGHT',FW)):
    di = house_panel(wall)
    door_lo, door_hi = panel_span(wall, di)
    cn = 'FL' if wall=='LEFT' else 'FR'
    u,v,w=csect(wall,*O_BOT,(0,1,0))
    add(wall,'BC1','A62421',u,v,w,(x,0.0,0.0),door_lo,'bottom channel, mitred at the corner',req=[0,0,1],mitre=cn)
    add(wall,'BC2','A62421',u,v,w,(x,door_hi,0.0),DP-door_hi,'stub bottom channel under the wall channel',req=[0,0,1])
    z0,z1 = z_top(wall,0.0)-CH_H, z_top(wall,DP)-CH_H
    run=(0.0, DP, z1-z0); ln=math.hypot(DP, z1-z0)
    u,v,w=csect(wall,*O_TOP,run)
    add(wall,'TC','A62421',u,v,w,(x,0.0,z0),ln,'side top channel, raked, mitred at the corner',req=[0,0,-1],mitre=cn)

# ---------------- horizontal rails ----------------
def rail(wall,tag,a,b,z,o,at,note):
    u,v,w=csect(wall,*o,(1,0,0) if wall=='FRONT' else (0,1,0))
    p0=at(a); add(wall,tag,'A26948',u,v,w,(p0[0],p0[1],z),b-a,note,
                  req=[0,0,-1] if 'RHI' in tag else [0,0,1])
for i in range(len(SEQ['FRONT'])):
    lo,hi = panel_span('FRONT',i)
    rail('FRONT',f"P{i+1}_RLO",lo,hi,Z_LO-RAIL_H,O_RAIL_LO,lambda t:(t,0.0),f"rail below glass, panel {i+1}")
    rail('FRONT',f"P{i+1}_RHI",lo,hi,Z_HI,       O_RAIL_HI,lambda t:(t,0.0),f"rail above glass, panel {i+1}")
for wall,x in (('LEFT',0.0),('RIGHT',FW)):
    allp=[panel_span(wall,i) for i in range(len(SEQ[wall]))]
    a0=min(p[0] for p in allp); b1=max(p[1] for p in allp)
    rail(wall,'RHI',a0,b1,Z_HI,O_RAIL_HI,lambda t:(x,t),'head rail, full run')
    si = 1-house_panel(wall)                      # the slider panel is the other one
    sa,sb = panel_span(wall,si)
    rail(wall,'RLO',sa,sb,Z_LO-RAIL_H,O_RAIL_LO,lambda t:(x,t),'sill under the slider panel')

# ---------------- glass adaptors around each glass panel ----------------
# A26950 all round, per the assembly notes. Engagements measured from the sections:
#   female -> adaptor 0.2196 | adaptor -> male 0.2196 | rail -> adaptor 0.2196
ADP_W = dims('A26950')[1]          # 0.803 face width
E_ADP = E('A26948','A26950')
def adaptors(wall, i, at, axis_is_x):
    lo,hi = panel_span(wall,i)                       # clear opening along the wall
    # horizontal adaptors: span the clear opening, engage the rails
    zb0 = Z_LO - E_ADP                               # bottom adaptor, opens UP toward the glass
    zt1 = Z_HI + E_ADP                               # top adaptor, opens DOWN toward the glass
    zt0 = zt1 - ADP_W
    u,v,w=csect(wall,0,False,(1,0,0) if axis_is_x else (0,1,0))
    p=at(lo); add(wall,f"P{i+1}_ADP_B",'A26950',u,v,w,(p[0],p[1],zb0),hi-lo,'glass adaptor, bottom',req=[0,0,1])
    u,v,w=csect(wall,180,False,(1,0,0) if axis_is_x else (0,1,0))
    p=at(lo); add(wall,f"P{i+1}_ADP_T",'A26950',u,v,w,(p[0],p[1],zt0),hi-lo,'glass adaptor, top',req=[0,0,-1])
    # vertical adaptors: run between the horizontal ones, engage the female and male
    zv0, zv1 = zb0+ADP_W, zt0
    inward = [1,0,0] if axis_is_x else [0,1,0]
    for tag,pos,rq in ((f"P{i+1}_ADP_L", lo-E_ADP,          inward),
                       (f"P{i+1}_ADP_R", hi+E_ADP-ADP_W, [-c for c in inward])):
        u,v,w=cplan(wall,270,False)
        p=at(pos); add(wall,tag,'A26950',u,v,w,(p[0],p[1],zv0),zv1-zv0,'glass adaptor, side',req=rq)

for i in range(len(SEQ['FRONT'])):
    adaptors('FRONT', i, lambda t:(t,0.0), True)

# ---------------- slider window frame ----------------
# A33863 bottom sill, A33861 top sill, A33864 side track BOTH sides.
for wall,x in (('LEFT',0.0),('RIGHT',FW)):
    si = 1-house_panel(wall)
    lo,hi = panel_span(wall,si)
    trk = dims('A33864')[1]
    zb0 = Z_LO - E('A33863','A26948')
    zt1 = Z_HI + E('A26948','A33861')
    zt0 = zt1 - dims('A33861')[1]
    e_trk = E('A33864','A26949')
    t0 = lo - e_trk                                   # track at the low end
    t1 = hi + e_trk - trk                             # track at the high end
    u,v,w=csect(wall,0,False,(0,1,0))
    add(wall,'SL_BOT','A33863',u,v,w,(x,t0+trk,zb0),(t1)-(t0+trk),'slider bottom sill',req=[0,0,1])
    u,v,w=csect(wall,180,False,(0,1,0))
    add(wall,'SL_TOP','A33861',u,v,w,(x,t0+trk,zt0),(t1)-(t0+trk),'slider top sill',req=[0,0,-1])
    u,v,w=cplan(wall,270,False)
    add(wall,'SL_TRK_A','A33864',u,v,w,(x,t0,zb0),zt1-zb0,'slider side track (low end)',req=[0,1,0])
    u,v,w=cplan(wall,90,False)
    add(wall,'SL_TRK_B','A33864',u,v,w,(x,t1,zb0),zt1-zb0,'slider side track (high end)',req=[0,-1,0])

json.dump(MEM,open('members.json','w'),indent=1)
import collections
print(f"{len(MEM)} members")
print("parts:", dict(sorted(collections.Counter(m['part'] for m in MEM).items())))
for wall in ('LEFT','RIGHT'):
    di=house_panel(wall); lo,hi=panel_span(wall,di)
    print(f"  {wall:5s} patio door = panel {di+1} (house end)  opening Y {lo:.4f}..{hi:.4f} = {hi-lo:.4f}\"")
