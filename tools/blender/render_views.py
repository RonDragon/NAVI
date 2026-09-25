"""Render front / side / back / 3-4 views of a GLB for quick visual QA.

Usage:
  blender --background --python tools/blender/render_views.py -- <in.glb> <out_prefix>
"""
import sys
import math
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
src, out_prefix = argv[0], argv[1]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)

meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
mins = Vector((1e9, 1e9, 1e9))
maxs = Vector((-1e9, -1e9, -1e9))
for o in meshes:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        mins = Vector(map(min, mins, w))
        maxs = Vector(map(max, maxs, w))
center = (mins + maxs) / 2
size = max(maxs - mins)
print("BBOX", tuple(round(v, 3) for v in mins), tuple(round(v, 3) for v in maxs))

scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "TEXTURE"
scene.render.resolution_x = 768
scene.render.resolution_y = 768
scene.world = bpy.data.worlds.new("w")
scene.world.color = (0.08, 0.1, 0.14)

cam_data = bpy.data.cameras.new("cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = size * 1.15
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

# glTF import is Y-up converted to Blender Z-up; model faces -Y (front) by convention
views = {"front": 0, "side": 90, "back": 180, "threequarter": 35}
for name, deg in views.items():
    a = math.radians(deg)
    d = size * 3
    cam.location = center + Vector((d * math.sin(a), -d * math.cos(a), 0))
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = f"{out_prefix}-{name}.png"
    bpy.ops.render.render(write_still=True)
print("DONE")
