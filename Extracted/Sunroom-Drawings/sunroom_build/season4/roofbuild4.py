"""Add the roof (roof4.json) to the open Sunroom_4Season document, replacing any previous roof, then save.
    exec(open(r'C:/DaVinci_Works/Lifestyle/sunroom_build/season4/roofbuild4.py').read())"""
import json, FreeCAD as App
BASE = r'C:/DaVinci_Works/Lifestyle/sunroom_build/season4/'
src = open(BASE + 'build4.py').read().split('def build():')[0]
ns = {}; exec(src, ns)
R = json.load(open(BASE + 'roof4.json'))['members']
doc = App.getDocument('Sunroom_4Season') if 'Sunroom_4Season' in App.listDocuments() else App.openDocument(BASE + 'Sunroom_4Season.FCStd')
old = doc.getObject('Roof')
if old:
    for o in list(old.Group): doc.removeObject(o.Name)
    doc.removeObject('Roof')
grp = doc.addObject('App::DocumentObjectGroup', 'Roof')
COLR = {'roofalu': (0.80, 0.80, 0.82), 'roofskin': (0.93, 0.93, 0.90), 'rooffoam': (0.98, 0.85, 0.35), 'wood': (0.60, 0.42, 0.22)}
for m in R:
    s = ns['member_solid'](m)
    o = doc.addObject('Part::Feature', m['name'].replace(' ', '_'))
    o.Label = m['name']; o.Shape = s; grp.addObject(o)
    if App.GuiUp:
        o.ViewObject.ShapeColor = COLR[m['group']]
doc.recompute()
doc.saveAs(BASE + 'Sunroom_4Season.FCStd')
print('roof added:', len(R), 'objects; saved')
