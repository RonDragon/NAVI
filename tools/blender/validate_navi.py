"""Offline GLB and Blender QA. Run in Blender after the final build."""
import bpy, bmesh, json, struct, math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[2]
path=ROOT/'assets/models/navi-v1.glb'
raw=path.read_bytes();magic,version,length=struct.unpack_from('<4sII',raw)
assert magic==b'glTF' and version==2 and length==len(raw)
size,kind=struct.unpack_from('<II',raw,12);g=json.loads(raw[20:20+size])
names=[a.get('name') for a in g.get('animations',[])]
expected={'Idle','Wave','HappyJump','TailWag','Listen','Sleep'}
assert set(names)==expected,(names,expected)
assert len(g.get('skins',[]))==1
assert g.get('meshes') and g.get('materials')
targets=set()
triangles=0
for m in g['meshes']:
    targets.update(m.get('extras',{}).get('targetNames',[]))
    for p in m['primitives']:
        assert {'POSITION','NORMAL','JOINTS_0','WEIGHTS_0'}<=set(p['attributes'])
        triangles+=g['accessors'][p['indices']]['count']//3
assert targets=={'Blink','Happy','MouthOpen'},targets
assert 8000<=triangles<=15000,triangles
emissive=[m for m in g['materials'] if m['name']=='Navi_Glow']
assert emissive and max(emissive[0].get('emissiveFactor',[0]))>0
assert not g.get('cameras')
def values(idx):
    acc=g['accessors'][idx];view=g['bufferViews'][acc['bufferView']]
    binstart=20+size+8
    n={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[acc['type']]
    fmt={5126:'f',5123:'H',5125:'I',5121:'B'}[acc['componentType']]
    stride=view.get('byteStride',struct.calcsize('<'+fmt*n))
    start=binstart+view.get('byteOffset',0)+acc.get('byteOffset',0)
    return [struct.unpack_from('<'+fmt*n,raw,start+i*stride) for i in range(acc['count'])]
loop_checks={}
for a in g['animations']:
    if a['name'] not in {'Idle','TailWag','Sleep'}:continue
    max_delta=0
    for channel in a['channels']:
        sam=a['samplers'][channel['sampler']];v=values(sam['output'])
        if channel['target']['path']=='weights':
            delta=max(abs(v[i][0]-v[-3+i][0]) for i in range(3))
        else:delta=max(abs(x-y) for x,y in zip(v[0],v[-1]))
        max_delta=max(max_delta,delta)
    loop_checks[a['name']]=max_delta
    assert max_delta<1e-5,(a['name'],max_delta)

bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/models/navi-v1.blend'))
obj=bpy.data.objects['Navi'];rig=bpy.data.objects['NaviRig']
assert len(rig.data.bones)==27
assert set(k.name for k in obj.data.shape_keys.key_blocks)=={'Basis','Blink','Happy','MouthOpen'}
assert not any(m.type=='MIRROR' for m in obj.modifiers)
vertices=obj.data.vertices
bm=bmesh.new();bm.from_mesh(obj.data)
topology={'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'loose_vertices':sum(not v.link_faces for v in bm.verts),'zero_area_faces':sum(f.calc_area()<1e-12 for f in bm.faces)}
bm.free()
assert not any(topology.values()),topology
height=max(v.co.z for v in vertices)-min(v.co.z for v in vertices)
assert abs(height-1)<1e-6 and abs(min(v.co.z for v in vertices))<1e-6
wrong=[];sums=[];tail_ids=[];leg_ids=[];ear_ids=[]
for v in vertices:
    wg={obj.vertex_groups[e.group].name:e.weight for e in v.groups}
    deform={n:w for n,w in wg.items() if n in rig.data.bones and w>1e-6}
    sums.append(sum(deform.values()))
    if 'S_Tail' in wg:
        tail_ids.append(v.index)
        if any(not n.startswith('Tail.') for n in deform):wrong.append(v.index)
    if any(n.startswith('S_Ear.') for n in wg):
        ear_ids.append(v.index)
        if any(not(n.startswith('Ear.') or n=='Head') for n in deform):wrong.append(v.index)
        for n in deform:
            if n.startswith('Ear.'):
                assert (v.co.x>0 and '.L.' in n) or (v.co.x<0 and '.R.' in n),(v.index,v.co[:],n)
    if any(n.startswith(('UpperLeg.','LowerLeg.','Foot.')) for n in deform):leg_ids.append(v.index)
assert not wrong and max(abs(s-1) for s in sums)<1e-5
tail_set=set(tail_ids);ear_set=set(ear_ids)
body_ids=set()
for v in vertices:
    for e in v.groups:
        name=obj.vertex_groups[e.group].name
        if e.weight>1e-6 and (name in {'Hips','Spine','Chest','Neck'} or name.startswith(('UpperLeg.','LowerLeg.','Foot.'))):body_ids.add(v.index)
coords=[v.co for v in vertices]
body_polys=[list(p.vertices) for p in obj.data.polygons if set(p.vertices)<=body_ids]
tail_polys=[list(p.vertices) for p in obj.data.polygons if set(p.vertices)<=tail_set]
body_bvh=BVHTree.FromPolygons(coords,body_polys)
tail_bvh=BVHTree.FromPolygons(coords,tail_polys)
tail_body_intersections=len(body_bvh.overlap(tail_bvh))
tail_clearance=min(body_bvh.find_nearest(coords[i])[3] for i in tail_ids)
ear_clearance=min(body_bvh.find_nearest(coords[i])[3] for i in ear_ids)
assert tail_body_intersections==0 and tail_clearance>.001 and ear_clearance>.01,(tail_body_intersections,tail_clearance,ear_clearance)
# Tail isolation proof: transform only tail bone channels, compare evaluated vertices.
def evaluated():
    bpy.context.view_layer.update();dep=bpy.context.evaluated_depsgraph_get()
    e=obj.evaluated_get(dep);m=e.to_mesh();out=[v.co.copy() for v in m.vertices];e.to_mesh_clear();return out
base=evaluated()
rig.pose.bones['Tail.1'].rotation_mode='XYZ';rig.pose.bones['Tail.1'].rotation_euler.z=.4
moved=evaluated()
leg_motion=max((base[i]-moved[i]).length for i in leg_ids)
tail_motion=max((base[i]-moved[i]).length for i in tail_ids)
assert leg_motion<1e-7 and tail_motion>.02,(leg_motion,tail_motion)
rig.pose.bones['Tail.1'].rotation_euler.z=0
# True mirror symmetry, ignoring UV seams and split normals.
positions={tuple(round(c,5) for c in v.co) for v in vertices}
unpaired=sum((-x,y,z) not in positions for x,y,z in positions)
assert unpaired==0,unpaired
result={'glb_bytes':len(raw),'triangles':triangles,'mesh_count':len(g['meshes']),'material_count':len(g['materials']),'animations':names,'shape_keys':sorted(targets),'height_m':height,'bones':len(rig.data.bones),'all_weights_normalized':True,'tail_vertices':len(tail_ids),'ear_vertices':len(ear_ids),'tail_only_test_max_leg_motion_m':leg_motion,'tail_only_test_max_tail_motion_m':tail_motion,'loop_endpoint_max_deltas':loop_checks,'symmetry_unpaired_vertices':unpaired,'embedded_images':len(g.get('images',[])),'status':'PASS'}
result['topology']=topology
result['rest_clearance']={'tail_body_intersections':tail_body_intersections,'tail_body_min_distance_m':tail_clearance,'ear_torso_min_distance_m':ear_clearance}
(ROOT/'tools/blender/qa/final-validation.json').write_text(json.dumps(result,indent=2))
print('NAVI FINAL VALIDATION',json.dumps(result,indent=2),flush=True)
# Import the exported asset in a fresh scene to prove round-trip compatibility.
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(path))
assert len([o for o in bpy.context.scene.objects if o.type=='ARMATURE'])==1
assert len([o for o in bpy.context.scene.objects if o.type=='MESH'])>=1
imported=[o for o in bpy.context.scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' for m in o.modifiers)]
assert len(imported)==1
rest=[o.matrix_world@v.co for o in imported for v in o.data.vertices]
import_height=max(v.z for v in rest)-min(v.z for v in rest)
assert abs(import_height-1)<1e-5,import_height
result['round_trip_height_m']=import_height;result['round_trip_import']='PASS'
(ROOT/'tools/blender/qa/final-validation.json').write_text(json.dumps(result,indent=2))
print('GLB ROUND TRIP PASS',flush=True)
