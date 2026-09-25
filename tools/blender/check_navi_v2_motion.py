import bpy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/models/navi-v2.blend'))
obj=bpy.data.objects['Navi'];rig=bpy.data.objects['NaviRig'];sk=obj.data.shape_keys
tail_ids=[v.index for v in obj.data.vertices if any(obj.vertex_groups[g.group].name=='S_Tail' for g in v.groups)]
tip_ids=[i for i in tail_ids if obj.data.vertices[i].co.y>.47]
for name,frame in [('Idle',0),('Stretch',45)]:
    rig.animation_data.action=bpy.data.actions[name];sk.animation_data.action=bpy.data.actions[name+'_Face'];bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
    e=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh()
    print('TAIL HEIGHT',name,sum(m.vertices[i].co.z for i in tip_ids)/len(tip_ids))
    e.to_mesh_clear()
