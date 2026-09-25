"""Render selected poses from the saved working file, with automatic camera framing.

blender --background --python tools/blender/render_navi_pose.py -- HappyJump
"""
import bpy, math, sys
from mathutils import Vector
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
bpy.ops.wm.open_mainfile(filepath=str(ROOT/('assets/models/navi-v2.blend' if (ROOT/'assets/models/navi-v2.blend').exists() else 'assets/models/navi-v2-review.blend')))
rig=bpy.data.objects['NaviRig'];obj=bpy.data.objects['Navi'];scene=bpy.context.scene
keys=obj.data.shape_keys;cam=scene.camera
poses={'Idle':(60,15),'Wave':(45,15),'HappyJump':(30,15),'TailWag':(35,135),'Listen':(45,0),'Sleep':(60,35),'Notice':(42,10),'Stretch':(45,15),'Inspect':(60,35),'Celebrate':(36,15),'Concerned':(45,0)}
names=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else list(poses)
for name in names:
    frame,deg=poses[name]
    rig.animation_data.action=bpy.data.actions[name]
    keys.animation_data.action=bpy.data.actions[name+'_Face']
    scene.frame_set(frame);bpy.context.view_layer.update()
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
    coords=[obj.matrix_world@v.co for v in mesh.vertices];evaluated.to_mesh_clear()
    low=Vector(tuple(min(v[k] for v in coords) for k in range(3)))
    high=Vector(tuple(max(v[k] for v in coords) for k in range(3)))
    target=(low+high)/2;angle=math.radians(deg)
    cam.location=target+Vector((2.8*math.sin(angle),-2.8*math.cos(angle),.25 if name=='Sleep' else 0))
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    bpy.context.view_layer.update()
    local=[cam.matrix_world.inverted()@v for v in coords]
    cam.data.ortho_scale=max(max(v[k] for v in local)-min(v[k] for v in local) for k in [0,1])*1.15
    shift=cam.matrix_world.to_3x3()@Vector(tuple((max(v[k] for v in local)+min(v[k] for v in local))/2 for k in [0,1])+(0,))
    cam.location+=shift
    scene.render.filepath=str(ROOT/'renders'/('navi-v2-'+name.lower()+'.png'))
    bpy.ops.render.render(write_still=True)
