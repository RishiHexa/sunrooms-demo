import ezdxf, collections, re, math
from ezdxf.bbox import extents
p="/sessions/magical-sleepy-babbage/mnt/Lifestyle/Sunroom-Drawings/225-Room-Description.dxf"
doc=ezdxf.readfile(p); msp=doc.modelspace()
print("version",doc.dxfversion,"units",doc.header.get('$INSUNITS'))
print("entities",dict(collections.Counter(e.dxftype() for e in msp)))
print("layers",[l.dxf.name for l in doc.layers])
bb=extents(msp); print("extents",bb.extmin,bb.extmax,"size",bb.size)
print("\n=== per-layer ===")
lay=collections.defaultdict(collections.Counter)
for e in msp: lay[e.dxf.layer][e.dxftype()]+=1
for k,v in sorted(lay.items()): print(f"  {k:14s} {dict(v)}")
print("\n=== TEXT / MTEXT ===")
for e in msp.query('MTEXT TEXT'):
    t = e.text if e.dxftype()=='MTEXT' else e.dxf.text
    clean=re.sub(r'\\\\[A-Za-z][^;]*;','',t).replace('\\P',' | ')
    ip=e.dxf.insert
    print(f"  [{e.dxf.layer:12s}] ({ip.x:8.2f},{ip.y:8.2f}) {clean.strip()[:88]}")
