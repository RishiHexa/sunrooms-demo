"""4-season sunroom member generator.  World: X along front 0->216, Y depth front(outside)=0 -> house=144,
Z up, floor=0.  Overall 216 x 144 = OUTSIDE of the corner posts (front) and post-to-house (sides).
All geometry is emitted in WORLD coordinates (profile loops already placed) so the FreeCAD side
does no orientation logic at all: build faces -> extrude -> apply listed cuts."""
import json, math, sys
sys.path.insert(0,'/home/claude/s4')
P=json.load(open('profiles.json')); INST=json.load(open('instances.json'))
def T(rot,mir,p):
    x,y=p
    if mir: x=-x
    return {0:(x,y),90:(-y,x),180:(-x,-y),270:(y,-x)}[rot%360]
def die_bb(k,rot,mir):
    pts=[T(rot,mir,p) for L in P[k]['loops'] for s in L['segs'] for p in s[1:]]
    return min(p[0] for p in pts),min(p[1] for p in pts),max(p[0] for p in pts),max(p[1] for p in pts)
def size(k,rot,mir):
    b=die_bb(k,rot,mir); return b[2]-b[0],b[3]-b[1]

# ---------------- world placement of PLAN members ----------------
# The plan drawing maps to world by a +90deg rotation:  drawing (x,y) -> (-y, x).
# Black parts = FRONT wall frame, red (BOX layer) parts = LEFT side wall frame.
def plan_loops(k,rot,mir,bbmin,mirrorX=None):
    """die loops in world XY, oriented (rot,mir), whole-die bbox min at bbmin.
       mirrorX: if given, mirror the result about X=mirrorX (right side of the room)."""
    b=die_bb(k,rot,mir); out=[]
    for L in P[k]['loops']:
        segs=[]
        for s in L['segs']:
            pts=[]
            for p in s[1:]:
                q=T(rot,mir,p); x=q[0]-b[0]+bbmin[0]; y=q[1]-b[1]+bbmin[1]
                if mirrorX is not None: x=2*mirrorX-x
                pts.append([x,y])
            segs.append([s[0]]+pts)
        out.append({'segs':segs,'depth':L['depth']})
    return out
def inst(part,rot,mir):
    for i in INST['PlanAssembly']:
        if i['part']==part and i['rot']==rot and i['mir']==mir: return i
def rot_bb(i, rot=None, mir=None):
    """world-rotated (unplaced) bbox of a drawing instance"""
    k=i['part']; w,h=size(k,i['rot'],i['mir']); x,y=i['pos']
    return (-(y+h), x, -y, x+w)          # (xmin,ymin,xmax,ymax) after (x,y)->(-y,x)
W_ORI=lambda i:((i['rot']+90)%360, i['mir'])

FW, DP = 216.0, 144.0
H_FRONT, H_HOUSE = 84.0, 96.0
TAN = (H_HOUSE-H_FRONT)/DP; COS=1/math.sqrt(1+TAN*TAN); SIN=TAN*COS
FIN = 1.6250-1.0446                          # fin projection of T02/T03 beyond the body face
FIN = P['T02']['size'][1] - 1.04462          # refined below from geometry
# exact body face: right-half loop height of T02
FIN = P['T02']['size'][1] - max(p[1] for s in P['T02']['loops'][3]['segs'] for p in s[1:])
FIN_F = P['T03']['size'][1] - max(p[1] for s in P['T03']['loops'][1]['segs'] for p in s[1:])
assert abs(FIN-FIN_F)<1e-3, (FIN,FIN_F)

# corner cluster (drawing): post, inside corner, black male (front), red male (left side)
post=inst('CornerPost',0,False); ic=inst('InsideCorner',0,False)
mF =inst('T02',180,True) if inst('T02',180,True)['pos'][1]>30 else None
mF =[i for i in INST['PlanAssembly'] if i['part']=='T02' and i['rot']==180 and i['mir'] and i['pos'][1]>30][0]
mL =[i for i in INST['PlanAssembly'] if i['part']=='T02' and i['rot']==270 and i['pos'][0]<70][0]
pb=rot_bb(post); OX,OY=-pb[0],-pb[1]            # post outer corner -> world origin
def placed(i): b=rot_bb(i); return (b[0]+OX,b[1]+OY,b[2]+OX,b[3]+OY)
POST=placed(post); IC=placed(ic); MF=placed(mF); ML=placed(mL)
DEPTH0 = MF[1]                                 # outer face of every wall member's bbox, from post face
print(f"post {POST}\nfront corner male {[round(v,4) for v in MF]}\nleft corner male {[round(v,4) for v in ML]}")
print(f"drawing asymmetry front vs side corner male: along {ML[1]-MF[0]:+.4f}  depth {ML[0]-MF[1]:+.4f}  (post is symmetric -> use FRONT values for both)")

# mullion clusters
mul_blk=[i for i in INST['PlanAssembly'] if i['part'] in('T02','T03') and 15<i['pos'][1]<30]
mul_red=[i for i in INST['PlanAssembly'] if i['part'] in('T02','T03') and 70<i['pos'][0]<80]
house_blk_M=[i for i in INST['PlanAssembly'] if i['part']=='T02' and i['pos'][1]<15][0]
house_red_M=[i for i in INST['PlanAssembly'] if i['part']=='T02' and i['pos'][0]>85][0]
# wall channel (matched on its halves only; the drawing used the T02 strut inside it)
WC_red={'part':'T01','rot':270,'mir':False,'pos':[88.0532,35.6577]}

# ---------------- heights from the vertical section ----------------
VS={ (i['part'],i['rot'],i['mir']):i for i in INST['VertSection']}
t05b=VS[('T05',180,True)]; t05t=VS[('T05',0,False)]; t04=VS[('T04',0,False)]
CH_H=P['T05']['size'][1]
VRECT=(24.2274,24.53492,28.39075,50.13484)
SEAT_B = VRECT[1]-t05b['pos'][1]                     # vertical bottom above channel underside
SEAT_T = (t05t['pos'][1]+CH_H)-VRECT[3]              # vertical top below channel top
LIP    = t04['pos'][0]-t05b['pos'][0]                # channel lip outboard of wall members
T04_BODY_TOP = max(p[1] for s in P['T04']['loops'][4]['segs'] for p in s[1:])   # 1.6696
T04_BODY_BOT = min(p[1] for s in P['T04']['loops'][4]['segs'] for p in s[1:])   # 0.625
print(f"seat bottom {SEAT_B:.5f}  seat top {SEAT_T:.5f}  channel lip outboard {LIP:.4f}  channel h {CH_H:.4f}  fin {FIN:.4f}")
Z0 = SEAT_B
Z1_FRONT = H_FRONT - SEAT_T
def z1_side(y): return H_FRONT + TAN*y - SEAT_T/COS
RAIL_TOPS=[24.0, 80.625]

MEM=[]
def add(name,part,group,loops,extrude,base=None,cuts=None,meta=None):
    MEM.append({'name':name,'part':part,'group':group,'loops':loops,'extrude':extrude,'cuts':cuts or [],
                'meta':meta or {}})
def to3(loops,z):   # plan loops -> 3D at height z
    return [{'segs':[[s[0]]+[[p[0],p[1],z] for p in s[1:]] for s in L['segs']],'depth':L['depth']} for L in loops]
def prism(poly2d, plane, lo, hi):
    """cutting prism: poly2d in the plane ('XY' extrude Z, 'YZ' extrude X) from lo to hi"""
    if plane=='XY': pts=[[p[0],p[1],lo] for p in poly2d]; v=[0,0,hi-lo]
    else:           pts=[[lo,p[0],p[1]] for p in poly2d]; v=[hi-lo,0,0]
    return {'poly':pts,'vec':v}
def side_top_cut(xlo,xhi):
    """remove everything above the vertical-member seat line under the raked side top channel"""
    z=lambda y: z1_side(y)
    return prism([[-20,z(-20)],[170,z(170)],[170,200],[-20,200]],'YZ',xlo,xhi)
def flat_top_cut(z):
    return prism([[-20,-20],[240,-20],[240,170],[-20,170]],'XY',z,200)

# ---------------- RUNS: list of vertical members per wall, as world bboxes ----------------
def shift(i, dx, dy, mirrorX=None, name='', part=None):
    rot,mir=W_ORI(i); b=rot_bb(i); k=part or i['part']
    bbmin=(b[0]+dx, b[1]+dy)
    return {'part':k,'rot':rot,'mir':mir,'bbmin':bbmin,'mirrorX':mirrorX,
            'bb':(bbmin[0],bbmin[1],bbmin[0]+(b[2]-b[0]),bbmin[1]+(b[3]-b[1]))}

walls={}
# FRONT: X along wall.  corner male fin tip at MF[2]; mirror at the right corner.
front=[]
front.append(('CP_L',shift(post,OX,OY)))
front.append(('IC_L',shift(ic,OX,OY)))
front.append(('M0',shift(mF,OX,OY)))
mb=[rot_bb(i) for i in mul_blk]; span_x=max(b[2] for b in mb)-min(b[0] for b in mb)
NF=4; gF=(FW-2*MF[2]-(NF-1)*span_x)/NF
for j in range(1,NF):
    x0=MF[2]+j*gF+(j-1)*span_x                       # left fin tip of mullion j
    dx=x0-min(b[0] for b in mb); dy=DEPTH0-min(b[1] for b in mb)
    for i in mul_blk: front.append((f"MU{j}_{'F' if i['part']=='T03' else 'M'}", shift(i,dx,dy)))
front.append(('M5',shift(mF,OX,OY,mirrorX=FW/2)))
front.append(('IC_R',shift(ic,OX,OY,mirrorX=FW/2)))
front.append(('CP_R',shift(post,OX,OY,mirrorX=FW/2)))
FRONT_OPEN=[(MF[2]+j*(gF+span_x), MF[2]+j*(gF+span_x)+gF) for j in range(NF)]   # fin-tip to fin-tip

# LEFT: Y along wall. corner male = front corner male reflected through the post diagonal (post is symmetric)
left=[]
cm=shift(mL,OX,OY); dyc=MF[0]-cm['bb'][1]; dxc=MF[1]-cm['bb'][0]
left.append(('M0',shift(mL,OX+dxc,OY+dyc)))
CORNER_TIP=MF[2]
rb=[rot_bb(i) for i in mul_red]; span_y=max(b[3] for b in rb)-min(b[1] for b in rb)
hm=rot_bb(house_red_M); hw=(-(WC_red['pos'][1]+size('T01',270,False)[1]), WC_red['pos'][0], -WC_red['pos'][1], WC_red['pos'][0]+size('T01',270,False)[0])
dyh=DP-hw[3]; dxh=DEPTH0-hm[0]
HOUSE_TIP=hm[1]+dyh
NS=2; gS=(HOUSE_TIP-CORNER_TIP-(NS-1)*span_y)/NS
for j in range(1,NS):
    y0=CORNER_TIP+j*gS+(j-1)*span_y
    dy=y0-min(b[1] for b in rb); dx=DEPTH0-min(b[0] for b in rb)
    for i in mul_red: left.append((f"MU{j}_{'F' if i['part']=='T03' else 'M'}", shift(i,dx,dy)))
left.append(('M3',shift(house_red_M,dxh,dyh)))
left.append(('WC',shift(WC_red,dxh,dyh)))
SIDE_OPEN=[(CORNER_TIP+j*(gS+span_y), CORNER_TIP+j*(gS+span_y)+gS) for j in range(NS)]

print(f"\nFRONT: {NF} openings, fin-tip width {gF:.4f}  body-to-body {gF+2*FIN:.4f}   mullion span {span_x:.4f}")
print(f"SIDE : {NS} openings, fin-tip width {gS:.4f}  body-to-body {gS+2*FIN:.4f}   house male fin tip at Y {HOUSE_TIP:.4f}")

# ---- closure checks (all must be exactly zero) ----
fr=[b for n,b in front]
print("closure FRONT  max X - 216 = %+.6f   min X = %+.6f" % (max(m['bb'][2] if m['mirrorX'] is None else 2*FW/2-m['bb'][0] for m in fr)-FW, min(m['bb'][0] for m in fr if m['mirrorX'] is None)))
print("closure SIDE   max Y - 144 = %+.6f" % (max(b['bb'][3] for n,b in left)-DP))

# ---------------- emit vertical members ----------------
GROUP={'T02':'male','T03':'female','T01':'wallchannel','CornerPost':'post','InsideCorner':'insidecorner','T04':'horizontal','T05':'channel'}
def emit_plan(wall,tag,m,side_mirror=None):
    mirrorX = m['mirrorX'] if side_mirror is None else side_mirror
    loops=plan_loops(m['part'],m['rot'],m['mir'],m['bbmin'],mirrorX)
    xs=[p[0] for L in loops for s in L['segs'] for p in s[1:]]
    if wall=='FRONT' or tag.startswith(('CP','IC')):
        add(f"{wall} {tag}",m['part'],GROUP[m['part']],to3(loops,Z0),[0,0,Z1_FRONT-Z0])
    else:
        add(f"{wall} {tag}",m['part'],GROUP[m['part']],to3(loops,Z0),[0,0,100-Z0],cuts=[side_top_cut(min(xs)-1,max(xs)+1)])
for n,m in front:
    emit_plan('CORNER' if n.startswith(('CP','IC')) else 'FRONT',n,m)
for n,m in left:
    emit_plan('LEFT',n,m)
    emit_plan('RIGHT',n,m,side_mirror=FW/2)

# ---------------- horizontals T04 (rot0 in the vertical section: slanted box OUTSIDE, fins vertical) ----------------
def section_loops(k, origin, u, v, flipy=False, yh=None):
    """die (px,py) -> origin + px*u + py'*v  where py' = py (or h-py if flipy)"""
    h=P[k]['size'][1]; out=[]
    for L in P[k]['loops']:
        segs=[]
        for s in L['segs']:
            pts=[]
            for p in s[1:]:
                py=(h-p[1]) if flipy else p[1]
                pts.append([origin[i]+p[0]*u[i]+py*v[i] for i in range(3)])
            segs.append([s[0]]+pts)
        out.append({'segs':segs,'depth':L['depth']})
    return out
WALLDEF={  # inward unit, along-wall unit, outer-face coordinate of member bbox along inward axis
 'FRONT':{'u':[0,1,0],'run':[1,0,0],'out':DEPTH0},
 'LEFT' :{'u':[1,0,0],'run':[0,1,0],'out':DEPTH0},
 'RIGHT':{'u':[-1,0,0],'run':[0,1,0],'out':FW-DEPTH0},
}
def at(wall,s,depth_from_out,z):
    d=WALLDEF[wall]; o=[0,0,z]
    ax=0 if d['run'][0] else 1; o[ax]=s
    inax=1-ax; o[inax]=d['out']+d['u'][inax]*depth_from_out
    return o
# Patio door: LEFT wall, house-end panel (index 1). No lower horizontal, no bottom channel
# across the opening (a stub/nib stays under the wall channel + house male), no bottom T02 receptor.
DOORS={'LEFT':[1]}
assert SIDE_OPEN[1][0]>SIDE_OPEN[0][0]          # index 1 is the house-end panel
for wall,opens in (('FRONT',FRONT_OPEN),('LEFT',SIDE_OPEN),('RIGHT',SIDE_OPEN)):
    d=WALLDEF[wall]
    for j,(a,b) in enumerate(opens):
        s0,s1=a-FIN,b+FIN                                    # body face to body face
        for r,zt in zip(('LO','HI'),RAIL_TOPS):
            if r=='LO' and j in DOORS.get(wall,[]): continue
            o=at(wall,s0,0.0,zt-T04_BODY_TOP)
            loops=section_loops('T04',o,d['u'],[0,0,1])
            add(f"{wall} P{j+1}_H{r}",'T04','horizontal',loops,[c*(s1-s0) for c in d['run']],
                meta={'cope':True,'span':[s0,s1]})

# ---------------- T02 receptors at the bottom and top of every panel ----------------
# Laid horizontally in the top/bottom channel exactly where a vertical's end sits: leg tips on the
# channel seat (SEAT_B / SEAT_T), body face toward the panel, fin on the outside side like the verticals.
# Run body face to body face between verticals, coped round the vertical fins (same as the T04s).
def vcut(wall, s, keep_above):
    """vertical plane cut across the run at along-wall coordinate s"""
    if wall=='FRONT':
        poly=[[s,-30],[s,40],[s-60 if keep_above else s+60,40],[s-60 if keep_above else s+60,-30]]
        return prism(poly,'XY',-5,120)
    x0,x1=(-30,40) if wall=='LEFT' else (FW-40,FW+30)
    e=s-60 if keep_above else s+60
    return prism([[x0,s],[x1,s],[x1,e],[x0,e]],'XY',-5,120)
for wall,opens in (('FRONT',FRONT_OPEN),('LEFT',SIDE_OPEN),('RIGHT',SIDE_OPEN)):
    d=WALLDEF[wall]
    for j,(a,b) in enumerate(opens):
        s0,s1=a-FIN,b+FIN
        if j not in DOORS.get(wall,[]):
            o=at(wall,s0,0.0,Z0)
            add(f"{wall} P{j+1}_RCV_B",'T02','male',section_loops('T02',o,d['u'],[0,0,1]),
                [c*(s1-s0) for c in d['run']],meta={'cope':True,'span':[s0,s1]})
        if wall=='FRONT':
            o=at(wall,s0,0.0,Z1_FRONT)
            add(f"{wall} P{j+1}_RCV_T",'T02','male',section_loops('T02',o,d['u'],[0,0,-1]),
                [c*(s1-s0) for c in d['run']],meta={'cope':True,'span':[s0,s1]})
        else:
            # raked head: section perpendicular to the rake, leg tips on the raked seat line
            t=[0,COS,SIN]; vdown=[0,SIN,-COS]
            ya=s0-1.0; o=at(wall,ya,0.0,0.0); o[2]=H_FRONT+TAN*ya-SEAT_T/COS
            Lr=(s1-s0+2.0)/COS
            add(f"{wall} P{j+1}_RCV_T",'T02','male',section_loops('T02',o,d['u'],vdown),
                [c*Lr for c in t],cuts=[vcut(wall,s0,True),vcut(wall,s1,False)],meta={'cope':True,'span':[s0,s1]})

# ---------------- top & bottom channels T05 ----------------
# bottom: rot180M (opening UP), top: rot0 (opening DOWN); lip (die x=0) OUTSIDE, LIP outboard of wall members.
MITRE_FL_FRONT=prism([[-30,-30],[-30,40],[40,40]],'XY',-5,120)      # removes X<Y  (front keeps X>=Y)
MITRE_FL_SIDE =prism([[-30,-30],[40,-30],[40,40]],'XY',-5,120)      # removes X>Y  (left keeps Y>=X)
MITRE_FR_FRONT=prism([[FW+30,-30],[FW+30,40],[FW-40,40]],'XY',-5,120)   # removes 216-X<Y
MITRE_FR_SIDE =prism([[FW+30,-30],[FW-40,-30],[FW-40,40]],'XY',-5,120)
HOUSE_CUT=prism([[-30,DP],[FW+30,DP],[FW+30,DP+30],[-30,DP+30]],'XY',-5,120)
for zname,flip,zb in (('BC',True,0.0),('TC',False,H_FRONT-CH_H)):
    o=at('FRONT',-2.0,-LIP,zb)
    add(f"FRONT {zname}",'T05','channel',section_loops('T05',o,[0,1,0],[0,0,1],flipy=flip),[FW+4,0,0],cuts=[MITRE_FL_FRONT,MITRE_FR_FRONT])
for wall,mit in (('LEFT',MITRE_FL_SIDE),('RIGHT',MITRE_FR_SIDE)):
    d=WALLDEF[wall]
    o=at(wall,-2.0,-LIP,0.0)
    cuts=[mit]
    for j in DOORS.get(wall,[]):          # door opening: channel removed between the mullion and the house nib
        a,b=SIDE_OPEN[j]; g0,g1=a-FIN,b+FIN
        x0,x1=(-30,40) if wall=='LEFT' else (FW-40,FW+30)
        cuts.append(prism([[x0,g0],[x1,g0],[x1,g1],[x0,g1]],'XY',-5,120))
        print(f"{wall} door opening: bottom channel removed Y {g0:.4f}..{g1:.4f} ({g1-g0:.4f}); house nib {g1:.4f}..{DP:.4f} ({DP-g1:.4f})")
    add(f"{wall} BC",'T05','channel',section_loops('T05',o,d['u'],[0,0,1],flipy=True),[0,DP+2,0],cuts=cuts)
    # raked top: section perpendicular to the run; top surface passes z=84 at Y=0, 96 at Y=144
    t=[0,COS,SIN]; v=[0,-SIN,COS]
    y0=-3.0; ztop=H_FRONT+TAN*y0
    base=[0,y0,ztop]; base[0]=d['out']+d['u'][0]*(-LIP)
    o=[base[i]-CH_H*v[i] for i in range(3)]           # die py=CH_H on the top surface
    L=(DP-y0+3)/COS
    add(f"{wall} TC",'T05','channel',section_loops('T05',o,d['u'],v),[c*L for c in t],cuts=[mit,HOUSE_CUT])

json.dump({'members':MEM,'layout':{'gF':gF,'gS':gS,'fin':FIN,'z0':Z0,'z1_front':Z1_FRONT,'lip':LIP,'depth0':DEPTH0,
           'front_open':FRONT_OPEN,'side_open':SIDE_OPEN,'tan':TAN}},open('members4.json','w'))
import collections
print(f"\n{len(MEM)} members:", dict(collections.Counter(m['part'] for m in MEM)))
