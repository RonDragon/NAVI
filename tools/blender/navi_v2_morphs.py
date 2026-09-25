# Fixed eyeballs. Blink deforms only solid lids, never retracts an eye.
obj.shape_key_add(name='Basis')
MORPHS=['Blink','Happy','MouthOpen','Surprised','Sad']
for name in MORPHS:obj.shape_key_add(name=name)
keys=mesh.shape_keys.key_blocks
for i,(v,tags) in enumerate(zip(mesh.vertices,semantic)):
    x,y,z=v.co/S; sign=1 if x>=0 else -1
    if 'LidTop' in tags or 'LidBottom' in tags:
        top='LidTop' in tags;side=1 if top else -1
        u=next(int(t[-1])/3 for t in tags if t.startswith('LidRow'))
        dx=(x-sign*.079)/(.051*1.12*math.sqrt(.90))
        arc=math.sqrt(max(0,1-dx*dx))
        # Both lid edges meet on a gently smiling seam in front of the fixed eye.
        seam=.669-.003*arc
        closed_z=z*(1-u)+(seam+( .0002 if top else -.0002))*u
        cap=math.sqrt(max(0,1-dx*dx-((closed_z-.672)/(.068*1.12))**2))
        closed_y=min(y,-.136-.049*cap)+.0012*('LidBack' in tags)
        keys['Blink'].data[i].co=Vector((x,closed_y,closed_z))*S
        h=.55 if not top else .18
        keys['Happy'].data[i].co=v.co.lerp(keys['Blink'].data[i].co,h)
        keys['Surprised'].data[i].co.z+=side*.006*S*u*arc
        keys['Sad'].data[i].co=v.co.lerp(keys['Blink'].data[i].co,.30 if top else .08)
        keys['Sad'].data[i].co.z+=.007*S*u*(-sign*dx)*arc
    if 'Brow' in tags:
        keys['Surprised'].data[i].co.z+=.013*S
        keys['Sad'].data[i].co.z+=(.008-.022*min(1,abs(x)/.1))*S
        keys['Happy'].data[i].co.z+=.004*S
    if 'FaceSkin' in tags or 'MouthCavity' in tags:
        # Compact lower-face influence keeps eyes/head envelope untouched.
        influence=math.exp(-((x/.072)**4)-((z-.585)/.034)**4)
        if y<-.14:
            center=.586+.008*(abs(x)/.047)**2
            lower=max(0,min(1,(center-z+.003)/.007))
            keys['MouthOpen'].data[i].co.z-=.023*S*influence*lower
            keys['MouthOpen'].data[i].co.z+=.003*S*influence*(1-lower)
            corner=min(1,(abs(x)/.047)**2)*influence
            keys['Happy'].data[i].co.z+=.007*S*corner
            keys['Sad'].data[i].co.z-=.018*S*corner
            keys['Surprised'].data[i].co.z-=.009*S*influence*lower
