"""FreeCAD builder for the 4-season sunroom.  Run inside FreeCAD:
    exec(open(r'C:/DaVinci_Works/Lifestyle/sunroom_build/season4/build4.py').read())
Reads members4.json (all geometry already in world coordinates, produced by members4.py).
No orientation logic here: faces -> extrude -> listed cuts -> cope horizontals around vertical fins."""
import json, FreeCAD as App, Part
from FreeCAD import Vector as V
BASE = r'C:/DaVinci_Works/Lifestyle/sunroom_build/season4/'
J = json.load(open(BASE + 'members4.json'))
DOC = 'Sunroom_4Season'
COL = {'male': (0.35, 0.55, 0.85), 'female': (0.85, 0.40, 0.40), 'wallchannel': (0.35, 0.70, 0.40),
       'post': (0.25, 0.25, 0.25), 'insidecorner': (0.55, 0.35, 0.70), 'channel': (0.70, 0.70, 0.72),
       'horizontal': (0.95, 0.65, 0.25)}

def wire(L):
    edges = []
    for s in L['segs']:
        if s[0] == 'line':
            a, b = V(*s[1]), V(*s[2])
            if (a - b).Length > 1e-7:
                edges.append(Part.LineSegment(a, b).toShape())
        else:
            edges.append(Part.Arc(V(*s[1]), V(*s[2]), V(*s[3])).toShape())
    w = Part.Wire(edges)
    if not w.isClosed():
        w.fixWire(None, 1e-6)
    return w

def member_solid(m):
    wires = [wire(L) for L in m['loops']]
    face = Part.makeFace(wires, 'Part::FaceMakerBullseye')
    if not face.isValid():
        face.fix(1e-7, 1e-7, 1e-7)
    sol = face.extrude(V(*m['extrude']))
    for c in m['cuts']:
        pts = [V(*p) for p in c['poly']]
        prism = Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(V(*c['vec']))
        sol = sol.cut(prism)
    return sol

def build():
    if DOC in App.listDocuments():
        App.closeDocument(DOC)
    doc = App.newDocument(DOC)
    shapes = {}
    for m in J['members']:
        shapes[m['name']] = member_solid(m)
    # cope horizontals around the vertical members they butt against (the panel-stop fins)
    verts = [m['name'] for m in J['members'] if m['part'] in ('T02', 'T03') and not m['meta'].get('cope')]
    for m in J['members']:
        if not m['meta'].get('cope'):
            continue
        h = shapes[m['name']]
        for n in verts:
            if h.BoundBox.intersect(shapes[n].BoundBox):
                h = h.cut(shapes[n])
        shapes[m['name']] = h
    groups = {}
    for m in J['members']:
        g = m['group']
        if g not in groups:
            groups[g] = doc.addObject('App::DocumentObjectGroup', g)
        o = doc.addObject('Part::Feature', m['name'].replace(' ', '_'))
        o.Label = m['name'] + ' ' + m['part']
        o.Shape = shapes[m['name']]
        groups[g].addObject(o)
        if App.GuiUp:
            o.ViewObject.ShapeColor = COL[g]
    doc.recompute()
    return doc, shapes

doc, SHAPES = build()
if App.GuiUp:
    import FreeCADGui as Gui
    Gui.ActiveDocument.ActiveView.viewIsometric()
    Gui.SendMsgToActiveView('ViewFit')
