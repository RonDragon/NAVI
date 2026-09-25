"""Generate the standalone v2 builder from the untouched v1 source, offline."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
s=(ROOT/'tools/blender/build_navi.py').read_text()
s=s.replace('tools/blender/build_navi.py','tools/blender/build_navi_v2.py')
s=s.replace('# Save authored anatomical constraints, then run Blender automatic heat weights.','# Save authored anatomical constraints and apply deterministic skin weights.')
s=s.replace('navi-v1','navi-v2').replace("default=5)","default=2)",1)
s=s.replace('IT = A.iteration','PASS = A.iteration\nIT = 5')
s=s.replace("'Navi_QuadSurface'","'Navi_SoftSurface'")
s=s.replace("f'tools/blender/qa/iteration-{IT}.json'","f'tools/blender/qa/v2-iteration-{PASS}.json'")
s=s.replace("'iteration':IT","'iteration':PASS")
s=s.replace("obj['build_iteration']=IT","obj['build_iteration']=PASS")
s=s.replace('str(IT))','str(PASS))')
s=s.replace("# Cheeks and muzzle: masks taper toward the central brow.","# Cheeks and muzzle: masks taper toward the central brow.")
start=s.index('# Cheeks and muzzle:')
end=s.index('# Curved tuft',start)
s=s[:start]+(ROOT/'tools/blender/navi_v2_face.py').read_text()+ '\n'+s[end:]
# Preserve the head envelope, increase distal arm dimensions by 12 percent.
start=s.index('# Cyan four-point star')
end=s.index('# Back:',start)
s=s[:start]+'''# A shallow core panel follows the torso surface; its seam flows into the belly.
def chest_y(x,z):
    torso=.008-.076*math.sqrt(max(0,1-(x/.108)**2-((z-.362)/.147)**2))
    belly=-.053-.038*math.sqrt(max(0,1-(x/.087)**2-((z-.341)/.112)**2))
    return min(torso,belly)-.003
def chest_patch(outline,mat,offset):
    pts=[(x,chest_y(x,z)-offset,z) for x,z in outline]
    g.patch(pts,(0,chest_y(0,.435)-offset,.435),.0015,mat,W('Chest'),levels=4)
chest_patch([(0,.479),(.039,.437),(0,.392),(-.039,.437)],NAVY,.002)
chest_patch([(0,.470),(.030,.437),(0,.401),(-.030,.437)],BLUE,.004)
chest_patch([(0,.461),(.007,.444),(.023,.436),(.007,.429),(0,.410),(-.007,.429),(-.023,.436),(-.007,.444)],GLOW,.006)
for sign in [-1,1]:
    pts=[(sign*x,chest_y(x,z)-.002,z) for x,z in [(0,.399),(.022,.382),(.048,.369),(.070,.353),(.080,.338)]]
    g.tube(pts,[.0015,.0017,.0016,.0013,.0005],GLOW,lambda t,c:body_w(c),n=6)
''' + s[end:]
s=s.replace('(.013,.012),(.028,.028),(.050,.046),(.067,.058),(.070,.061),(.060,.057),(.043,.044),(.023,.026)',
            '(.016,.015),(.032,.031),(.055,.049),(.065,.056),(.061,.054),(.048,.047),(.030,.032),(.012,.016)')
s=s.replace("f=min(2.999,t*3); j=int(f)\n    return blend('Tail.'+str(j+1),'Tail.'+str(j+2),f-j)","""# Cubic B-spline blend gives smooth derivatives across all four joints.
    u=t*3
    ww={}
    for j in range(4):
        d=abs(u-j)
        w=(2/3-d*d+.5*d*d*d) if d<1 else ((2-d)**3/6 if d<2 else 0)
        if w>0:ww['Tail.'+str(j+1)]=w
    total=sum(ww.values())
    return {n:w/total for n,w in ww.items()}""")
s=s.replace("g.tube(tailpts,tailrs,TAIL,tw,('Tail',),n=20)","""# Densify the centreline before sweeping: 33 longitudinal rings.
pp=[Vector(p) for p in tailpts]; rr=[Vector(r) for r in tailrs]
tailpts=[];tailrs=[]
for j in range(len(pp)-1):
    for k in range(4):
        t=k/4
        def cat(arr):
            a,b,c,d=[arr[max(0,min(len(arr)-1,q))] for q in (j-1,j,j+1,j+2)]
            return .5*(2*b+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t)
        tailpts.append(tuple(cat(pp)));tailrs.append(tuple(max(.0007,r) for r in cat(rr)))
tailpts.append(tuple(pp[-1]));tailrs.append(tuple(rr[-1]))
g.tube(tailpts,tailrs,TAIL,tw,('Tail',),n=24)""")
# Avoid the old extra brush shells: use a single flowing tail surface.
start=s.index('# A pair of tapered fur tips')
end=s.index('mesh=bpy.data.meshes',start)
s=s[:start]+'''# Distal limb scaling, before mirror and normalization.
for i,(co,ww,tags) in enumerate(zip(g.v,g.weights,g.tags)):
    x,y,z=co
    if any(n.startswith(('LowerArm.','Hand.')) for n in ww):
        hand=sum(w for n,w in ww.items() if n.startswith('Hand.'))
        ramp=max(0,min(1,(abs(x)-.225)/.06))
        scale=1+.12*ramp
        y*=scale; z=.493+(z-.493)*scale
        if hand>.99:x=(1 if x>=0 else -1)*(.343+(abs(x)-.343)*1.12)
    if 'Tail' in tags:y+=.006
    g.v[i]=(x,y,z)

''' +s[end:]
s=s.replace("if before['unweighted']:auto_status='heat weights attempted; incomplete solution repaired anatomically'","# Planned anatomical weights applied below.")
# Use deterministic weights directly; v1 already established failed heat solve.
start=s.index("auto_status='completed'")
end=s.index('bone_names=',start)
s=s[:start]+"auto_status='deterministic anatomical weights (v1 repair preserved)'\nobj.parent=rig\n"+s[end:]
start=s.index('# Shape keys are applied')
end=s.index('# Actions:',start)
s=s[:start]+(ROOT/'tools/blender/navi_v2_morphs.py').read_text()+'\n'+s[end:]
start=s.index('actions={}');end=s.index('# Put each skeletal action',start)
s=s[:start]+(ROOT/'tools/blender/navi_v2_actions.py').read_text()+'\n'+s[end:]
s=s.replace("rig['loop_actions']='Idle, TailWag, Sleep'","rig['loop_actions']='Idle, TailWag, Sleep, Inspect, Concerned'")
start=s.index("    camd.ortho_scale=1.26")
end=s.index("    scene.render.filepath=",start)
s=s[:start]+'''    angle=math.radians(deg)
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get()); em=evaluated.to_mesh()
    coords=[obj.matrix_world@v.co for v in em.vertices];evaluated.to_mesh_clear()
    low=Vector(tuple(min(v[k] for v in coords) for k in range(3)))
    high=Vector(tuple(max(v[k] for v in coords) for k in range(3)))
    target=(low+high)/2
    cam.location=target+Vector((2.8*sin(angle),-2.8*cos(angle),.22 if pose=='Sleep' else .10 if deg==35 else 0))
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    bpy.context.view_layer.update()
    local=[cam.matrix_world.inverted()@v for v in coords]
    camd.ortho_scale=max(max(v[k] for v in local)-min(v[k] for v in local) for k in [0,1])*1.15
    shift=cam.matrix_world.to_3x3()@Vector(tuple((max(v[k] for v in local)+min(v[k] for v in local))/2 for k in [0,1])+(0,))
    cam.location+=shift
''' +s[end:]
start=s.index('if A.final:\n    view(');end=s.index('rig.animation_data.action=None;sk.animation_data.action=None;clear_pose();scene.frame_set(0)',start)
s=s[:start]+'''if A.final:
    for name,frame,deg in [('Sleep',60,35),('Notice',42,10),('Stretch',45,15),('Inspect',60,35),('Celebrate',36,15),('Concerned',45,0),('Wave',45,15),('HappyJump',30,15),('TailWag',35,135),('Listen',45,0),('Idle',0,15)]:
        view(name.lower(),deg,name,frame,'navi-v2')
    for morph in ['Blink','Happy','MouthOpen','Surprised','Sad']:view(morph.lower(),0,prefix='navi-v2',morph=morph)
else:
    for morph in ['Blink','MouthOpen','Sad']:view(morph.lower(),0,morph=morph)
''' + s[end:]
(ROOT/'tools/blender/build_navi_v2.py').write_text(s)
