import bpy,bmesh,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/models/navi-v2.blend'))
o=bpy.data.objects['Navi'];bm=bmesh.new();bm.from_mesh(o.data)
for f in bm.faces:
    if f.calc_area()<1e-12:
        print('ZERO',f.index,[list(v.co) for v in f.verts],[(o.vertex_groups[g.group].name,g.weight) for g in o.data.vertices[f.verts[0].index].groups])
bm.free()
