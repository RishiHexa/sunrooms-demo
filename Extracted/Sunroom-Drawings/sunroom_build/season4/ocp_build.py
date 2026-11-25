import json, time, itertools, sys
from OCP.gp import gp_Pnt, gp_Vec
from OCP.GC import GC_MakeArcOfCircle, GC_MakeSegment
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Common
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.TopoDS import TopoDS
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_VERTEX
from OCP.BRep import BRep_Tool
from OCP.BRepCheck import BRepCheck_Analyzer
J=json.load(open('members4.json'))
P=lambda p: gp_Pnt(*p)
def wire(L):
    w=BRepBuilderAPI_MakeWire()
    for s in L['segs']:
        if s[0]=='line':
            if sum((a-b)**2 for a,b in zip(s[1],s[2]))<1e-14: continue
            e=BRepBuilderAPI_MakeEdge(P(s[1]),P(s[2])).Edge()
        else:
            e=BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(P(s[1]),P(s[2]),P(s[3])).Value()).Edge()
        w.Add(e)
    return w.Wire()
def bb_of(L):
    pts=[p for s in L['segs'] for p in s[1:]]
    return [min(p[i] for p in pts) for i in range(3)]+[max(p[i] for p in pts) for i in range(3)]
def inside(a,b): return all(a[i]>=b[i]-1e-6 for i in range(3)) and all(a[i+3]<=b[i+3]+1e-6 for i in range(3))
def vol(s):
    g=GProp_GProps(); BRepGProp.VolumeProperties_s(s,g); return g.Mass()
def cut(a,b):
    op=BRepAlgoAPI_Cut(a,b); op.SetFuzzyValue(1e-7); op.Build(); return op.Shape()
def common(a,b):
    op=BRepAlgoAPI_Common(a,b); op.Build(); return op.Shape()
def bbox(s):
    b=Bnd_Box(); BRepBndLib.AddOptimal_s(s,b,False,False); mn=b.CornerMin(); mx=b.CornerMax(); return (mn.X(),mn.Y(),mn.Z(),mx.X(),mx.Y(),mx.Z())
def member_solid(m):
    outs=[L for L in m['loops'] if L['depth']%2==0]; holes=[L for L in m['loops'] if L['depth']%2==1]
    from OCP.TopoDS import TopoDS_Compound
    from OCP.BRep import BRep_Builder
    B=BRep_Builder(); comp=TopoDS_Compound(); B.MakeCompound(comp)
    vec=gp_Vec(*m['extrude'])
    for o in outs:
        f=BRepBuilderAPI_MakeFace(wire(o),True)
        ob=bb_of(o)
        for h in holes:
            if inside(bb_of(h),ob):
                hw=wire(h); hw.Reverse(); f.Add(hw)
        face=f.Face()
        from OCP.ShapeFix import ShapeFix_Face
        sf=ShapeFix_Face(face); sf.Perform(); face=sf.Face()
        B.Add(comp, BRepPrimAPI_MakePrism(face,vec).Shape())
    s=comp
    for c in m['cuts']:
        pg=BRepBuilderAPI_MakePolygon()
        for p in c['poly']: pg.Add(P(p))
        pg.Close()
        pr=BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(pg.Wire()).Face(), gp_Vec(*c['vec'])).Shape()
        s=cut(s,pr)
    return s
t=time.time()
S={m['name']:member_solid(m) for m in J['members']}
verts=[m['name'] for m in J['members'] if m['part'] in ('T02','T03') and not m['meta'].get('cope')]
def bbi(a,b,e=0.0):
    A=bbox(a); Bb=bbox(b)
    return all(A[i]-e<=Bb[i+3] and Bb[i]-e<=A[i+3] for i in range(3))
for m in J['members']:
    if not m['meta'].get('cope'): continue
    for n in verts:
        if bbi(S[m['name']],S[n]): S[m['name']]=cut(S[m['name']],S[n])
print('built in %.1fs'%(time.time()-t))
