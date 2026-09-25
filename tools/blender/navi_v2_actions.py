CLIPS=[('Idle',120,5),('Wave',90,5),('HappyJump',60,3),('TailWag',60,3),('Listen',90,5),('Sleep',120,5),('Notice',60,3),('Stretch',90,3),('Inspect',120,5),('Celebrate',75,3),('Concerned',90,3)]
LOOPS={'Idle','TailWag','Sleep','Inspect','Concerned'}
actions={}
def aim(name,target):
    # Solve FK orientation against a concrete pose-space target; keep bone lengths.
    bpy.context.view_layer.update()
    b=rig.pose.bones[name];mat=b.matrix.copy()
    q=(b.tail-b.head).rotation_difference(Vector(target)-b.head)
    mat=q.to_matrix().to_4x4()@mat;mat.translation=b.head
    b.matrix=mat;bpy.context.view_layer.update()
def relative(parent,point):
    b=rig.pose.bones[parent]
    return b.matrix@b.bone.matrix_local.inverted()@Vector(P(point))
def ease(t):return max(0,min(1,t))**2*(3-2*max(0,min(1,t)))
def squat(amount):
    for suf in ['L','R']:
        rot('UpperLeg.'+suf,(-65*amount,0,0));rot('LowerLeg.'+suf,(100*amount,0,0));rot('Foot.'+suf,(-35*amount,0,0))
    rig.pose.bones['Hips'].location.y=-.080*amount*S
for name,length,step in CLIPS:
    act=bpy.data.actions.new(name);act.use_fake_user=True;rig.animation_data_create();rig.animation_data.action=act
    for f in sorted(set(range(0,length+1,step))|{length}):
        scene.frame_set(f);clear_pose();t=f/length;p=sin(t*2*pi);resting_arms()
        if name=='Idle':
            rig.pose.bones['Chest'].scale=(1+.013*p,1+.018*p,1+.012*p)
            rot('Tail.1',(2*p,4*p,3*p));rot('Tail.3',(0,5*p,0));rot('Ear.L.2',(2*p,0,2*p));rot('Ear.R.2',(-2*p,0,2*p))
        elif name=='Wave':
            env=ease(t/.2)*ease((1-t)/.2)
            rot('UpperArm.R',(-62+110*env,-12*env,0));rot('LowerArm.R',(-8+35*env,0,0));rot('Hand.R',(12*sin(t*pi*8)*env,0,18*sin(t*pi*8)*env));rot('Head',(0,-4*env,4*env))
        elif name=='HappyJump':
            h=max(0,sin(pi*(t-.18)/.64)) if .18<t<.82 else 0
            c=sin(pi*t/.18) if t<=.18 else sin(pi*(t-.82)/.18) if t>=.82 else 0
            squat(.3*c);rig.pose.bones['Hips'].location.y=(.16*h-.024*c)*S
            for suf in ['L','R']:rot('UpperArm.'+suf,(-62+112*h,0,0))
            rot('Tail.1',(-15*h,0,0))
        elif name=='TailWag':
            for i in range(1,5):rot('Tail.'+str(i),(2*p,0,(14 if i==1 else 10)*sin(t*4*pi-(i-1)*.3)))
        elif name=='Listen':
            e=sin(pi*t)**2;rot('Head',(0,8*e,16*e));rot('Neck',(0,0,4*e))
            for sign,suf in [(1,'L'),(-1,'R')]:rot('Ear.'+suf+'.1',(-8*e,0,-10*sign*e));rot('Ear.'+suf+'.2',(-6*e,0,-4*sign*e))
        elif name=='Sleep':
            # Seated curl: hips low, legs forward, face nestled over hands.
            rig.pose.bones['Hips'].location.y=-.142*S
            for sign,suf in [(1,'L'),(-1,'R')]:
                rot('UpperLeg.'+suf,(-78,0,sign*12));rot('LowerLeg.'+suf,(35,0,0));rot('Foot.'+suf,(43,0,0))
                rot('UpperArm.'+suf,(-73,sign*22,sign*20));rot('LowerArm.'+suf,(-35,0,-sign*25))
                rot('Ear.'+suf+'.1',(25,0,-sign*27));rot('Ear.'+suf+'.2',(30,0,-sign*28))
            rot('Spine',(16+1*p,0,0));rot('Chest',(13,0,0));rot('Head',(22,0,-9))
            rig.pose.bones['Chest'].scale=(1+.007*p,1+.013*p,1+.007*p)
            bpy.context.view_layer.update()
            for sign,suf in [(1,'L'),(-1,'R')]:
                aim('UpperArm.'+suf,relative('Chest',(sign*.13,-.05,.380)))
                aim('LowerArm.'+suf,relative('Chest',(sign*.07,-.14,.335)))
            for i,pt in enumerate([(.115,.10,.285),(.19,.005,.24),(.14,-.1,.235),(.045,-.14,.25)],1):
                aim('Tail.'+str(i),relative('Hips',(pt[0],pt[1],pt[2]+.002*p)))
        elif name=='Notice':
            e=ease((t-.08)/.35);step=ease((t-.32)/.43);lift=sin(pi*max(0,min(1,(t-.32)/.43)))
            rot('Head',(0,24*(1-e),-9*(1-e)));rot('Chest',(0,8*(1-e),0))
            rig.pose.bones['Hips'].location.z=.035*step*S
            rot('UpperLeg.L',(-14*lift,0,0));rot('LowerLeg.L',(20*lift,0,0));rot('Foot.L',(-6*lift,0,0))
            for sign,suf in [(1,'L'),(-1,'R')]:rot('Ear.'+suf+'.1',(8*(1-e),0,sign*(10-18*e)))
            rot('Tail.2',(0,0,8*e));rot('UpperArm.R',(-62+12*lift,0,0))
        elif name=='Stretch':
            e=ease(t/.28)*ease((1-t)/.25)
            for sign,suf in [(1,'L'),(-1,'R')]:rot('UpperArm.'+suf,(-62+132*e,0,0));rot('LowerArm.'+suf,(-8+20*e,0,0));rot('Hand.'+suf,(0,0,sign*12*e))
            rot('Chest',(-12*e,0,0));rot('Head',(-13*e,0,0))
            for i in range(1,5):rot('Tail.'+str(i),(-14*e,0,4*e))
        elif name=='Inspect':
            squat(.82);rot('Spine',(20,0,0));rot('Chest',(9,0,0));rot('Head',(28,0,12+5*p))
            rot('UpperArm.L',(-78,-18,0));rot('LowerArm.L',(-26,0,0));rot('UpperArm.R',(-78,18,0));rot('LowerArm.R',(-26,0,0))
            rot('Ear.L.2',(7*sin(4*pi*t),0,-10));rot('Ear.R.1',(12,0,15));rot('Tail.2',(8,0,7*p))
        elif name=='Celebrate':
            env=ease(t/.12)*ease((1-t)/.16);h=abs(sin(3*pi*t))**1.2*env
            squat(.22*(1-h)*env);rig.pose.bones['Hips'].location.y=(.20*h-.018*(1-h)*env)*S
            for suf in ['L','R']:rot('UpperArm.'+suf,(-62+135*env+7*p,0,0));rot('LowerArm.'+suf,(-8+24*env,0,0))
            rot('Head',(-8*env,0,7*p*env))
            for i in range(1,5):rot('Tail.'+str(i),(-12*env,0,(22 if i==1 else 17)*sin(8*pi*t-i*.4)*env))
        elif name=='Concerned':
            rot('Spine',(8+1*p,0,0));rot('Head',(7,0,-7+2*p))
            for sign,suf in [(1,'L'),(-1,'R')]:
                rot('UpperArm.'+suf,(-68,sign*35,sign*28));rot('LowerArm.'+suf,(85,0,-sign*45));rot('Hand.'+suf,(12,0,0))
                rot('Ear.'+suf+'.1',(15,0,-sign*24));rot('Ear.'+suf+'.2',(18,0,-sign*17))
            rot('Tail.1',(12,0,4*p))
            bpy.context.view_layer.update()
            for sign,suf in [(1,'L'),(-1,'R')]:
                aim('UpperArm.'+suf,relative('Chest',(sign*.125,-.070,.390)))
                aim('LowerArm.'+suf,relative('Chest',(sign*.055,-.130,.450)))
                aim('Hand.'+suf,relative('Chest',(sign*.030,-.145,.477)))
        # Grounding: vertical root compensation for FK crouches and seated poses.
        if name in {'Sleep','Inspect','Concerned','Stretch','Notice'}:
            bpy.context.view_layer.update()
            ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mm=ev.to_mesh()
            floor=min(v.co.z for v in mm.vertices)
            ev.to_mesh_clear();rig.pose.bones['Hips'].location.y-=floor
        for b in rig.pose.bones:
            b.keyframe_insert('rotation_euler',frame=f,group=b.name);b.keyframe_insert('location',frame=f,group=b.name);b.keyframe_insert('scale',frame=f,group=b.name)
    actions[name]=act;act['loop']=name in LOOPS;act['fps']=30
    act['description']={'Sleep':'Seated curled rest, limp ears, wrapped tail and breathing','Notice':'Turn toward Operator, ears perk, step forward','Stretch':'Arms and tail rise into a full stretch','Inspect':'Crouch, downward gaze, head tilt and ear twitch','Celebrate':'Three joyful bounces, raised hands and strong tail wag','Concerned':'Lowered ears, hands held near chest, forward lean'}.get(name,name)
for name,length,step in CLIPS:
    sk=mesh.shape_keys;sk.animation_data_create();a=bpy.data.actions.new(name+'_Face');a.use_fake_user=True;sk.animation_data.action=a
    frames=sorted(set([0,length//2,length]+([48,51,54] if name=='Idle' else [])))
    for f in frames:
        for k in MORPHS:keys[k].value=0
        keys['Blink'].value=1 if name=='Sleep' or (name=='Idle' and f==51) else .65 if name=='Stretch' and f==length//2 else 0
        keys['Happy'].value=(.8 if name=='Celebrate' else .7 if name=='HappyJump' else .45 if name=='Wave' else 0) if 0<f<length else 0
        keys['MouthOpen'].value=.65 if name in {'Celebrate','HappyJump'} and 0<f<length else 0
        keys['Surprised'].value=.6 if name=='Notice' and 0<f<length else 0
        keys['Sad'].value=.75 if name=='Concerned' else 0
        for k in MORPHS:keys[k].keyframe_insert('value',frame=f)
    tr=sk.animation_data.nla_tracks.new();tr.name=name;tr.strips.new(name,0,a);tr.mute=True
sk.animation_data.action=None
