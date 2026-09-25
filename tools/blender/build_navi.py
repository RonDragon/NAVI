"""Reproducible, offline Navi character build. Blender 5.2, no dependencies.

blender --background --python tools/blender/build_navi.py -- --iteration 5 --final
Iterations retain their own turnaround renders. Use --final to export and render poses.
"""
import bpy, bmesh, math, sys, json, argparse
from pathlib import Path
from mathutils import Vector
from math import sin, cos, pi

ROOT = Path(__file__).resolve().parents[2]
args = argparse.ArgumentParser()
args.add_argument('--iteration', type=int, default=5)
args.add_argument('--final', action='store_true')
args.add_argument('--resolution', type=int, default=800)
A = args.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
IT = A.iteration
for d in ('assets/models', 'renders', 'tools/blender/qa'):
    (ROOT/d).mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
if hasattr(bpy.context.preferences.filepaths,'use_save_preview'):
    bpy.context.preferences.filepaths.use_save_preview=False
bpy.context.preferences.filepaths.save_version=0
bpy.context.preferences.filepaths.file_preview_type='NONE'

def linear(h):
    vals = [int(h[i:i+2], 16)/255 for i in (0,2,4)]
    return tuple(v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in vals)+(1,)

materials=[]
def material(name, color, rough=.45, emission=0, metal=0):
    m=bpy.data.materials.new(name); m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=linear(color)
    p.inputs['Roughness'].default_value=rough
    p.inputs['Metallic'].default_value=metal
    if emission:
        p.inputs['Emission Color'].default_value=linear(color)
        p.inputs['Emission Strength'].default_value=emission
    m.diffuse_color=linear(color); materials.append(m)
    return len(materials)-1
NAVY=material('Navi_Navy','10183A',.52 if IT>=2 else .38)
CREAM=material('Navi_Cream','F1E9DC',.55)
GLOW=material('Navi_Glow','18E0E8',.28,1.0 if IT>=3 else 1.6)
EYE=material('Navi_Eye','07122D',.13)
WHITE=material('Navi_EyeHighlight','FFFFFF',.19)
NOSE=material('Navi_Nose','060B19',.27)
BLUE=material('Navi_AccentBlue','075CDE',.32,.16)
TAIL=material('Navi_TailGradient','FFFFFF',.46)
# Tiny, packed generated texture: shared across the ears, irises and tail.
im=bpy.data.images.new('Navi_BlueCyan_32x128',width=32,height=128,alpha=True)
stops=[(0,'10183A'),(.30,'153987'),(.49,'075CDE'),(.68,'029FEA'),(.84,'18E0E8'),(1,'D6F7ED')]
pixels=[]
for j in range(128):
    t=j/127
    lo,hi=next(((a,b) for a,b in zip(stops,stops[1:]) if a[0]<=t<=b[0]),(stops[-2],stops[-1]))
    u=(t-lo[0])/(hi[0]-lo[0]); c0=linear(lo[1]); c1=linear(hi[1])
    pixels.extend([c0[k]*(1-u)+c1[k]*u for k in range(4)]*32)
im.pixels=pixels; im.pack()
p=materials[TAIL].node_tree.nodes.get('Principled BSDF')
tex=materials[TAIL].node_tree.nodes.new('ShaderNodeTexImage'); tex.image=im
materials[TAIL].node_tree.links.new(tex.outputs['Color'],p.inputs['Base Color'])
if IT>=3:
    materials[TAIL].node_tree.links.new(tex.outputs['Color'],p.inputs['Emission Color'])
    p.inputs['Emission Strength'].default_value=.22

class Geo:
    def __init__(self): self.v=[]; self.f=[]; self.m=[]; self.uv=[]; self.weights=[]; self.tags=[]
    def vertex(self,co,w,tags=(),uv=(.5,.5)):
        self.v.append(tuple(co)); self.weights.append(w.copy()); self.tags.append(tags); self.uv.append(uv)
        return len(self.v)-1
    def face(self,ids,mat): self.f.append(ids); self.m.append(mat)
    def ell(self,c,r,mat,w,tags=(),n=20,rings=12,clampz=None):
        if IT>=2:
            if IT>=3 and 'Eye' in tags:
                n=max(12,n);rings=max(4,round(rings*(.32 if IT>=5 else .40)))
            else:
                n=max(8,2*round(n*(.65 if IT>=3 and n!=32 else .73)/2));rings=max(4,round(rings*(.60 if IT>=3 and n!=24 else .70)))
        c=Vector(c); rows=[]
        for j in range(rings+1):
            a=-pi/2+pi*j/rings
            # Small pole rings keep quads and smooth, closed rounded surfaces.
            rr=max(.001,cos(a)); row=[]
            for i in range(n):
                b=2*pi*i/n
                if IT>=3 and 'Eye' in tags:
                    co=c+Vector((r[0]*rr*cos(b)*1.12,r[1]*sin(a),r[2]*rr*sin(b)))
                else:co=c+Vector((r[0]*rr*cos(b),r[1]*rr*sin(b),r[2]*sin(a)))
                if clampz is not None: co.z=max(clampz,co.z)
                ww=w(co) if callable(w) else w
                row.append(self.vertex(co,ww,tags,(i/n,j/rings)))
            rows.append(row)
        for j in range(rings):
            for i in range(n): self.face([rows[j][i],rows[j][(i+1)%n],rows[j+1][(i+1)%n],rows[j+1][i]],mat)
        self.face(list(reversed(rows[0])),mat); self.face(rows[-1],mat)
    def tube(self,pts,radii,mat,w,tags=(),n=10,uvrange=(0,1)):
        if IT>=2:n=max(6,2*round(n*(.60 if IT>=3 else .72)/2))
        maxradius=max(max(r) if isinstance(r,(tuple,list)) else r for r in radii)
        if IT>=2 and len(pts)>2 and not (len(pts)>20) and not (IT>=4 and maxradius<.006):
            # Catmull-Rom longitudinal interpolation removes angular hair/ear bends.
            outp=[];outr=[]
            rr=[Vector((r,r)) if isinstance(r,(float,int)) else Vector(r) for r in radii]
            pp=[Vector(p) for p in pts]
            for j in range(len(pts)-1):
                for k in range(2):
                    t=k/2
                    def cat(arr):
                        a,b,c,d=[arr[max(0,min(len(arr)-1,q))] for q in (j-1,j,j+1,j+2)]
                        return .5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t)
                    outp.append(tuple(cat(pp)));outr.append(tuple(max(.0003,v) for v in cat(rr)))
            outp.append(pts[-1]);outr.append(tuple(rr[-1]));pts=outp;radii=outr
        rows=[];prevu=None
        for j,p in enumerate(pts):
            p=Vector(p); tan=Vector(pts[min(j+1,len(pts)-1)])-Vector(pts[max(j-1,0)])
            tan.normalize(); u=tan.cross(Vector((0,1,0)))
            if u.length<.1: u=tan.cross(Vector((1,0,0)))
            if IT>=2 and prevu is not None:u=prevu-tan*prevu.dot(tan)
            u.normalize();prevu=u.copy(); v=tan.cross(u).normalized()
            r=radii[j]; r=(r,r) if isinstance(r,(float,int)) else r
            row=[]
            for i in range(n):
                a=2*pi*i/n; co=p+u*cos(a)*r[0]+v*sin(a)*r[1]
                ww=w(j/(len(pts)-1),co) if callable(w) else w
                row.append(self.vertex(co,ww,tags,(i/n,uvrange[0]+(uvrange[1]-uvrange[0])*j/(len(pts)-1))))
            rows.append(row)
        for j in range(len(rows)-1):
            for i in range(n): self.face([rows[j][i],rows[j][(i+1)%n],rows[j+1][(i+1)%n],rows[j+1][i]],mat)
        self.face(list(reversed(rows[0])),mat); self.face(rows[-1],mat)
    def patch(self,outline,center,depth,mat,w,tags=(),levels=4):
        # Rounded, closed leaf / badge. Outline lies on the visible front.
        rows=[]; c=Vector(center); N=len(outline)
        for k in range(levels+1):
            a=pi*k/levels
            rad=max(.003,sin(a)); off=depth*cos(a)
            rows.append([self.vertex(c+(Vector(p)-c)*rad+Vector((0,off,0)),w,tags) for p in outline])
        for k in range(levels):
            for i in range(N): self.face([rows[k][i],rows[k][(i+1)%N],rows[k+1][(i+1)%N],rows[k+1][i]],mat)
        self.face(list(reversed(rows[0])),mat); self.face(rows[-1],mat)

g=Geo()
def W(name): return {name:1.0}
def blend(a,b,t): return {a:1-max(0,min(1,t)),b:max(0,min(1,t))}
def body_w(co):
    if co.z<.34:return blend('Hips','Spine',(co.z-.25)/.09)
    return blend('Spine','Chest',(co.z-.34)/.13)

# Soft pear-shaped body, neck, and broad head.
g.ell((0,.008,.362),(.108,.076,.147),NAVY,body_w,n=24,rings=16)
g.ell((0,-.053,.341),(.087,.038,.112),CREAM,body_w,n=24,rings=14)
g.ell((0,0,.509),(.040,.044,.050),CREAM,W('Neck'),n=16,rings=8)
g.ell((0,0,.662),(.197 if IT>=2 else .183,.124,.157),NAVY,W('Head'),n=32,rings=22)
# Cheeks and muzzle: masks taper toward the central brow.
for s,suffix in [(1,'L'),(-1,'R')]:
    g.ell((s*.079,-.103,.677),(.070,.035,.100),CREAM,W('Head'),('Mask',),n=24 if IT>=4 else 20,rings=14)
    g.ell((s*.050,-.117,.585),(.111,.060,.054),CREAM,W('Head'),n=20,rings=10)
    for dz,x in [(0,.183),(-.037,.166)]:
        outline=[(s*.116,-.082,.620+dz),(s*x,-.041,.616+dz),(s*.154,-.066,.585+dz),(s*.107,-.114,.580+dz)]
        g.patch(outline,(s*.140,-.075,.600+dz),.027,CREAM,W('Head'),levels=4)
    # Oval black sockets, ivory sclera, saturated iris, dark pupil and highlights.
    x=s*.079; z=.672
    g.ell((x,-.136,z),(.051,.018,.071),NOSE,W('Head'),('Eye',),n=24,rings=14)
    g.ell((x,-.148,z),(.046,.013,.065),WHITE,W('Head'),('Eye',),n=24,rings=14)
    g.ell((x-s*.007,-.160,z-.005),(.033,.010,.055),BLUE,W('Head'),('Eye',),n=24,rings=14)
    g.ell((x-s*.007,-.168,z+.004),(.024,.006,.044),EYE,W('Head'),('Eye',),n=20,rings=12)
    g.ell((x-s*.014,-.174,z+.030),(.010,.003,.014),WHITE,W('Head'),('Eye',),n=12,rings=8)
    g.ell((x+s*.008,-.173,z-.032),(.004,.002,.006),WHITE,W('Head'),('Eye',),n=8,rings=6)
    if IT>=5:
        g.tube([(x+dx,-.124,.669-.006*(1-(dx/.044)**2)) for dx in [-.044,-.022,0,.022,.044]],[.001,.0017,.0018,.0017,.001],NOSE,W('Head'),('Lid',),n=6)
    # Cyan brow slash, and tiny cheek data marks.
    g.tube([(s*.041,-.120,.759),(s*.060,-.128,.774),(s*.080,-.126,.779),(s*.098,-.119,.770)], [.002,.004,.004,.002],GLOW,W('Head'),n=6)
    g.patch([(s*.134,-.135,.612),(s*.155,-.115,.624),(s*.160,-.117,.613),(s*.138,-.142,.600)],(s*.146,-.127,.612),.0018,BLUE,W('Head'),levels=2)
    g.tube([(s*.139,-.143,.608),(s*.157,-.125,.616)],[.002,.001],GLOW,W('Head'),n=6)
# nose, philtrum and warm W smile.
g.patch([(-.019,-.172,.625),(0,-.185,.631),(.019,-.172,.625),(0,-.184,.610)],(0,-.180,.622),.007,NOSE,W('Head'),('Nose',),levels=4)
g.tube([(0,-.178,.613),(0,-.180,.595)],[.0015,.0012],NOSE,W('Head'),('Mouth',),n=6)
g.tube([(-.053,-.166,.593),(-.044,-.175,.585),(-.026,-.182,.583),(0,-.183,.592),(.026,-.182,.583),(.044,-.175,.585),(.053,-.166,.593)], [.0012,.0015,.0016,.0016,.0016,.0015,.0012],NOSE,W('Head'),('Mouth',),n=6)
g.ell((0,-.181,.583),(.026,.002,.0008),NOSE,W('Head'),('MouthHole',),n=16,rings=8)

# Curved tuft made from pointed, swept locks.
for s in [-1,1]:
    g.tube([(s*.038,-.065,.784),(s*.057,-.068,.813),(s*.066,-.046,.844),(s*.047,-.025,.862)],[(.031,.026),(.032,.025),(.018,.014),(.0008,.0008)],NAVY,W('Head'),n=12)
g.tube([(0,-.112,.763),(0,-.113,.801),(0 if IT>=3 else -.010,-.084,.851),(0 if IT>=3 else -.027,-.038,.888),(0 if IT>=3 else -.050,-.008,.916)],[(.004,.004),(.041,.025),(.042,.032),(.025,.020),(.0008,.0008)],NAVY,W('Head'),n=16)
g.tube([(0,-.133,.775),(0,-.141,.813),(0,-.119,.848),(0,-.074,.881)],[(.001,.001),(.014 if IT>=3 else .010,.003),(.013 if IT>=3 else .010,.003),(.0008,.0008)],GLOW,W('Head'),n=8)
# Layered nape fur, kept understated in front silhouette.
for s in [-1,1]:
    for x,z in [(.132,.663),(.095,.733),(.141,.599)]:
        g.tube([(s*x,.070,z+.038),(s*(x+.019),.101,z),(s*(x+.032),.076,z-.052)],[(.032,.024),(.029,.022),(.0007,.0007)],NAVY,W('Head'),n=10)

# Huge leaf-shaped ears: navy shell, continuous ivory rim, blue/cyan inset.
EARPTS=[(.139,-.002,.759),(.170,.002,.790),(.217,.012,.851),(.265,.025,.921),(.309,.040,1.000),(.329,.044,1.027)]
EARWIDTH=[.023,.072,.083,.068,.031,.0006] if IT>=2 else [.023,.057,.062,.050,.023,.0006]
if IT>=3:
    EARPTS=[(.153,-.002,.715),(.180,.002,.760),(.227,.012,.826),(.273,.025,.915),(.309,.040,1.000),(.329,.044,1.027)]
    EARWIDTH=[.023,.076,.087,.067,.029,.0006]
def ear_w(t,co,suf): return blend('Ear.'+suf+'.1','Ear.'+suf+'.2',(t-.34)/.50)
for s,suf in [(1,'L'),(-1,'R')]:
    pts=[(s*x,y,z) for x,y,z in EARPTS]
    g.tube(pts,[(w,.019 if i<5 else .0006) for i,w in enumerate(EARWIDTH)],NAVY,lambda t,c:ear_w(t,c,suf),('Ear.'+suf,),n=16)
    # Same longitudinal sweep, flattened forward overlays, with a navy medial border.
    pts2=[(s*(x+.004),y-.017,z+.001) for x,y,z in EARPTS]
    g.tube(pts2,[(w*.89,.007 if i<5 else .0003) for i,w in enumerate(EARWIDTH)],CREAM,lambda t,c:ear_w(t,c,suf),('Ear.'+suf,),n=16)
    pts3=[(s*(x+.001),y-.026,z) for x,y,z in EARPTS[:-1]]+[(s*.313,.011,.992)]
    g.tube(pts3,[(w*.67,.004 if i<5 else .0003) for i,w in enumerate(EARWIDTH)],TAIL,lambda t,c:ear_w(t,c,suf),('Ear.'+suf,),n=16,uvrange=(.86,.40))
    if IT>=3:
        g.tube([(s*.170,-.031,.744),(s*.188,-.032,.773),(s*.211,-.021,.807),(s*.225,-.015,.854)],[(.001,.001),(.025,.002),(.029,.002),(.0004,.0004)],GLOW,lambda t,c:ear_w(t*.60,c,suf),('Ear.'+suf,),n=10)

# T-pose arms. Longitudinal rings make bending smooth at elbow and wrist.
for s,suf in [(1,'L'),(-1,'R')]:
    ua='UpperArm.'+suf; la='LowerArm.'+suf; hand='Hand.'+suf
    if IT>=2:g.ell((s*.083,0,.483),(.046,.038,.040),NAVY,W(ua),n=18,rings=10)
    def aw(t,co,ua=ua,la=la,hand=hand):
        x=abs(co.x)
        return blend(ua,la,(x-.211)/.038) if x<.29 else blend(la,hand,(x-.320)/.027)
    pts=[(s*x,0,.493) for x in [.087,.116,.145,.183,.209,.225,.242,.263,.289,.313,.337,.350]]
    rs=[.023,.037,.033,.028,.026,.025,.026,.033,.036,.032,.024,.024]
    g.tube(pts,rs,NAVY,aw,n=14)
    g.ell((s*.315,-.008,.498),(.047,.034,.031),CREAM,W(la),n=16,rings=8)
    g.tube([(s*.280,-.025,.518),(s*.305,-.033,.527),(s*.329,-.027,.519)], [.003,.003,.003],GLOW,W(la),n=6)
    g.ell((s*.373,0,.491),(.048,.038,.041) if IT>=3 else (.044,.033,.035),NAVY,W(hand),n=16,rings=10)
    # Three softly rounded fingers, spread in the plane of the palm.
    for j in range(3):
        zz=.512-j*.023; end=.448-abs(j-1)*.008
        g.tube([(s*.391,-.003,zz),(s*.416,-.004,zz+(1-j)*.003),(s*end,-.004,zz+(1-j)*.008),(s*(end+.003),-.004,zz+(1-j)*.008)], [.013,.012,.010,.002],NAVY,W(hand),n=10)
    g.tube([(s*.361,0,.474),(s*.378,-.004,.447),(s*.397,-.003,.439)], [.015,.013,.002],NAVY,W(hand),n=10)
    # Wrist orb is on the back of the hand (+Y); a paired forward lens matches the front concept.
    for direction in [-1,1]:
        yy=direction*.032
        g.ell((s*.369,yy,.496),(.034,.013,.034),NAVY,W(hand),n=20,rings=10)
        g.ell((s*.369,yy+direction*.012,.496),(.023,.005,.023),BLUE,W(hand),n=16,rings=8)
        g.ell((s*.369,yy+direction*.017,.496),(.017,.005,.017),GLOW,W(hand),n=16,rings=8)
    # Organic shoulder accent.
    g.tube([(s*.097,-.015,.523),(s*.118,-.020,.530),(s*.144,-.011,.522)],[.002,.003,.002],GLOW,W(ua),n=6)
    # Thighs and calves blend across the knee.
    ul='UpperLeg.'+suf; ll='LowerLeg.'+suf; foot='Foot.'+suf
    def lw(t,co,ul=ul,ll=ll):return blend(ll,ul,(co.z-.165)/.048)
    g.tube([(s*.073,0,.302),(s*.084,0,.270),(s*.095,0,.233),(s*.104,0,.197),(s*.108,0,.171),(s*.112,.006,.135),(s*.114,.006,.104)],[(.041,.042),(.048,.048),(.046,.043),(.035,.035),(.032,.032),(.030,.029),(.029,.030)],NAVY,lw,n=16)
    g.tube([(s*.098,-.037,.260),(s*.113,-.035,.227),(s*.115,-.033,.191)],[.002,.003,.002],GLOW,W(ul),n=6)
    # Chunky boot, sole, cream cuff and rounded cream toe.
    if IT<2:
        g.ell((s*.116,-.028,.068),(.074,.098,.073),NAVY,W(foot),n=24,rings=12,clampz=.005)
        g.ell((s*.116,-.028,.015),(.074,.098,.016),NAVY,W(foot),n=24,rings=6,clampz=0)
    else:
        rows=[]
        shoe=[(.063,.003,.047),(.054,.050,.071),(.027,.067,.082),(-.014,.077,.075),(-.057,.078,.061),(-.061,.078,.060),(-.090,.072,.051),(-.120,.050,.035),(-.136,.001,.020)]
        for y,width,hh in shoe:
            rows.append([g.vertex((s*.116+width*cos(2*pi*i/24),y,max(0,hh*.92+hh*sin(2*pi*i/24))),W(foot)) for i in range(24)])
        for j in range(len(rows)-1):
            for i in range(24):g.face([rows[j][i],rows[j][(i+1)%24],rows[j+1][(i+1)%24],rows[j+1][i]],NAVY if j<4 else GLOW if j==4 else CREAM)
        g.face(list(reversed(rows[0])),NAVY);g.face(rows[-1],CREAM)
    g.ell((s*.114,.003,.130),(.040,.042,.036),CREAM,W(ll),n=16,rings=8)
    if IT<2:
        g.ell((s*.116,-.084,.044),(.060,.055,.045),GLOW,W(foot),n=20,rings=10,clampz=.003)
        g.ell((s*.116,-.090,.041),(.059,.053,.043),CREAM,W(foot),n=20,rings=10,clampz=0)
        for dx in [-.021,.021]:
            g.tube([(s*.116+dx,-.138,.008),(s*.116+dx,-.137,.027),(s*.116+dx,-.120,.055)],[.0012,.0011,.0006],CREAM,W(foot),n=5)
    # Hip flank seam.
    g.tube([(s*.092,-.034,.389),(s*.103,-.014,.366),(s*.104,.010,.350)],[.002,.003,.002],GLOW,W('Spine'),n=6)

# Cyan four-point star in a beveled navy/blue diamond.
g.patch([(0,-.079,.511),(.049,-.083,.451),(0,-.096,.385),(-.049,-.083,.451)],(0,-.090,.449),.005,NAVY,W('Chest'),levels=4)
g.patch([(0,-.099,.495),(.037,-.100,.451),(0,-.102,.405),(-.037,-.100,.451)],(0,-.103,.450),.002,BLUE,W('Chest'),levels=2)
star=[(0,-.108,.484),(.010,-.108,.460),(.031,-.108,.450),(.010,-.108,.440),(0,-.108,.416),(-.010,-.108,.440),(-.031,-.108,.450),(-.010,-.108,.460)]
g.patch(star,(0,-.109,.450),.0025,GLOW,W('Chest'),levels=2)
# Back: spine line and shoulder-blade ring.
if IT>=3:
    backpts=[(0,.011+.076*math.sqrt(max(0,1-((z-.362)/.147)**2)),z) for z in [.295,.32,.35,.38,.41,.44,.465,.485,.50]]
    g.tube(backpts,[.0025]*len(backpts),GLOW,lambda t,c:body_w(c),n=6)
    hpts=[(0,.003+.124*math.sqrt(max(0,1-((z-.662)/.157)**2)),z) for z in [.535,.565,.595,.625,.655,.685,.715,.745,.775]]
    g.tube(hpts,[.0025]*len(hpts),GLOW,W('Head'),n=6)
else:
    g.tube([(0,.070,.295),(0,.083,.344),(0,.077,.399),(0,.067,.448),(0,.047,.495),(0,.045,.534)],[.0025]*6,GLOW,lambda t,c:body_w(c),n=6)
    g.tube([(0,.123,.589),(0,.129,.646),(0,.113,.717),(0,.085,.768)],[.0025,.003,.003,.002],GLOW,W('Head'),n=6)
g.ell((0,.073,.466),(.038,.014,.038),NAVY,W('Chest'),n=20,rings=10)
ring=[(.025*cos(i*2*pi/32),.088,.466+.025*sin(i*2*pi/32)) for i in range(33)]
g.tube(ring,[.0035]*33,GLOW,W('Chest'),n=6)

# Swept tail sits clear of the legs and torso beyond its narrow root.
tailpts=[(0,.093,.304),(0,.135,.270),(0,.195,.233),(0,.263,.214),(0,.329,.218),(0,.389,.243),(0,.439,.284),(0,.480,.330),(0,.501,.365)]
tailrs=[(.013,.012),(.028,.028),(.050,.046),(.067,.058),(.070,.061),(.060,.057),(.043,.044),(.023,.026),(.0007,.0007)]
def tw(t,co):
    f=min(2.999,t*3); j=int(f)
    return blend('Tail.'+str(j+1),'Tail.'+str(j+2),f-j)
g.tube(tailpts,tailrs,TAIL,tw,('Tail',),n=20)
# A pair of tapered fur tips gives a fox brush silhouette instead of a tube.
for s in [-1,1]:
    g.tube([(s*.034,.281,.243),(s*.055,.353,.273),(s*.045,.427,.334)],[(.026,.026),(.035,.026),(.0006,.0006)],TAIL,lambda t,c:tw(.48+t*.39,c),('Tail',),n=10,uvrange=(.42,.84))

if IT>=4:
    for i,(co,tags) in enumerate(zip(g.v,g.tags)):
        x,y,z=co
        if 'Eye' in tags or 'Mask' in tags:
            x+=(1 if x>0 else -1)*.18*(z-.672)
        if 'Nose' in tags:x*=1.18;z=.622+(z-.622)*1.18
        if 'Tail' in tags:y+=.006
        if 'Mouth' in tags:z+=.003*(abs(x)/.053)**1.3
        g.v[i]=(x,y,z)

mesh=bpy.data.meshes.new('Navi_QuadSurface'); mesh.from_pydata(g.v,[],g.f); mesh.update()
obj=bpy.data.objects.new('Navi',mesh); bpy.context.collection.objects.link(obj)
for m in materials:mesh.materials.append(m)
for p,mi in zip(mesh.polygons,g.m):p.material_index=mi;p.use_smooth=True
uv=mesh.uv_layers.new(name='NaviUV')
for p in mesh.polygons:
    for li in p.loop_indices:uv.data[li].uv=g.uv[mesh.loops[li].vertex_index]
for i,(ww,tags) in enumerate(zip(g.weights,g.tags)):
    for key,value in ww.items():
        name='P_'+key
        vg=obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
        if value>0:vg.add([i],value,'REPLACE')
    for key in tags:
        name='S_'+key; vg=obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name);vg.add([i],1,'REPLACE')
# True half-mesh construction followed by an applied X mirror.
bpy.context.view_layer.objects.active=obj; obj.select_set(True)
bm=bmesh.new();bm.from_mesh(mesh)
bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.000001,plane_co=(0,0,0),plane_no=(1,0,0),clear_inner=True,clear_outer=False)
bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(mesh);bm.free()
mirror=obj.modifiers.new('Symmetry — applied before skin','MIRROR');mirror.use_clip=True;mirror.use_mirror_merge=True;mirror.merge_threshold=.00001
bpy.ops.object.modifier_apply(modifier=mirror.name)
mesh=obj.data
# Normalize all geometry to exactly one metre with feet at zero.
zmin=min(v.co.z for v in mesh.vertices); zmax=max(v.co.z for v in mesh.vertices)
S=1/(zmax-zmin)
for v in mesh.vertices:v.co.z-=zmin;v.co*=S
def P(co):return (co[0]*S,co[1]*S,(co[2]-zmin)*S)

# Humanoid rig with four tail bones and two bones per ear.
arm=bpy.data.armatures.new('NaviRig');rig=bpy.data.objects.new('NaviRig',arm);bpy.context.collection.objects.link(rig)
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.object.mode_set(mode='EDIT')
def bone(name,h,t,parent=None,connected=False):
    b=arm.edit_bones.new(name);b.head=P(h);b.tail=P(t)
    if parent:b.parent=arm.edit_bones[parent];b.use_connect=connected
    return b
bone('Hips',(0,0,.257),(0,0,.322))
bone('Spine',(0,0,.322),(0,0,.405),'Hips',True)
bone('Chest',(0,0,.405),(0,0,.498),'Spine',True)
bone('Neck',(0,0,.498),(0,0,.554),'Chest',True)
bone('Head',(0,0,.554),(0,0,.791),'Neck',True)
for s,suf in [(1,'L'),(-1,'R')]:
    bone('Shoulder.'+suf,(0,0,.486),(s*.106,0,.493),'Chest')
    bone('UpperArm.'+suf,(s*.106,0,.493),(s*.225,0,.493),'Shoulder.'+suf,True)
    bone('LowerArm.'+suf,(s*.225,0,.493),(s*.343,0,.493),'UpperArm.'+suf,True)
    bone('Hand.'+suf,(s*.343,0,.493),(s*.408,0,.493),'LowerArm.'+suf,True)
    bone('UpperLeg.'+suf,(s*.073,0,.286),(s*.105,0,.183),'Hips')
    bone('LowerLeg.'+suf,(s*.105,0,.183),(s*.114,.006,.094),'UpperLeg.'+suf,True)
    bone('Foot.'+suf,(s*.114,.006,.094),(s*.114,-.090,.036),'LowerLeg.'+suf,True)
    bone('Ear.'+suf+'.1',(s*EARPTS[0][0],0,EARPTS[0][2]),(s*.232,.016,.871),'Head')
    bone('Ear.'+suf+'.2',(s*.232,.016,.871),(s*.329,.044,1.027),'Ear.'+suf+'.1',True)
tpoints=[(0,.093,.304),(0,.195,.233),(0,.329,.218),(0,.439,.284),(0,.501,.365)]
if IT>=4:tpoints=[(x,y+.006,z) for x,y,z in tpoints]
for i in range(4):bone('Tail.'+str(i+1),tpoints[i],tpoints[i+1],'Hips' if i==0 else 'Tail.'+str(i),i>0)
bpy.ops.object.mode_set(mode='OBJECT');rig.show_in_front=True;arm.display_type='OCTAHEDRAL'

# Save authored anatomical constraints, then run Blender automatic heat weights.
planned=[];semantic=[]
for v in mesh.vertices:
    def side_name(name):
        if v.co.x<0:return name.replace('.L','.R')
        if v.co.x>0:return name.replace('.R','.L')
        return name
    planned.append({side_name(obj.vertex_groups[e.group].name[2:]):e.weight for e in v.groups if obj.vertex_groups[e.group].name.startswith('P_')})
    semantic.append([side_name(obj.vertex_groups[e.group].name[2:]) for e in v.groups if obj.vertex_groups[e.group].name.startswith('S_')])
bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=rig
auto_status='completed'
try:bpy.ops.object.parent_set(type='ARMATURE_AUTO')
except RuntimeError as e:auto_status=str(e)
bone_names=set(b.name for b in arm.bones)
def weights_for(v):return {obj.vertex_groups[e.group].name:e.weight for e in v.groups if obj.vertex_groups[e.group].name in bone_names and e.weight>1e-6}
before={'unweighted':0,'tail_foreign':0,'ear_foreign':0}
for v,tags in zip(mesh.vertices,semantic):
    ww=weights_for(v)
    before['unweighted']+=not bool(ww)
    before['tail_foreign']+=('Tail' in tags and any(not n.startswith('Tail.') for n in ww))
    before['ear_foreign']+=(any(t.startswith('Ear.') for t in tags) and any(not(n.startswith('Ear.') or n=='Head') for n in ww))
if before['unweighted']:auto_status='heat weights attempted; incomplete solution repaired anatomically'
# Correct all disconnected detail shells using continuous anatomical interpolation.
all_ids=list(range(len(mesh.vertices)))
for name in bone_names:
    vg=obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
    vg.remove(all_ids)
for i,ww in enumerate(planned):
    total=sum(ww.values())
    assert total>0,(i,semantic[i])
    for n,w in ww.items():obj.vertex_groups[n].add([i],w/total,'REPLACE')
for vg in list(obj.vertex_groups):
    if vg.name.startswith('P_'):obj.vertex_groups.remove(vg)
if not any(m.type=='ARMATURE' for m in obj.modifiers):obj.modifiers.new('Navi Skin','ARMATURE').object=rig

# Shape keys are applied to explicit facial regions, never to the head or body.
obj.shape_key_add(name='Basis')
for name in ['Blink','Happy','MouthOpen']:obj.shape_key_add(name=name)
keys=mesh.shape_keys.key_blocks
for i,(v,tags) in enumerate(zip(mesh.vertices,semantic)):
    if 'Eye' in tags:
        center=.672*S
        keys['Blink'].data[i].co.z=center+(v.co.z-center)*.025
        if IT>=5:keys['Blink'].data[i].co.y=-.120*S+(v.co.y+.120*S)*.003
        keys['Happy'].data[i].co.z=center+.009*S+(v.co.z-center)*.65
    if 'Lid' in tags:keys['Blink'].data[i].co.y-=.028*S
    if 'Mouth' in tags:
        keys['Happy'].data[i].co.z+=.011*S*(abs(v.co.x)/(.053*S))**1.3
        keys['MouthOpen'].data[i].co.z-=.008*S*(1-min(1,abs(v.co.x)/(.053*S)))
    if 'MouthHole' in tags:
        keys['MouthOpen'].data[i].co.z=.581*S+(v.co.z-.583*S)*20

# Actions: explicit frame-zero poses, local Euler channels, stable loop endpoints.
scene=bpy.context.scene;scene.render.fps=30
def clear_pose():
    for b in rig.pose.bones:b.rotation_mode='XYZ';b.rotation_euler=(0,0,0);b.location=(0,0,0);b.scale=(1,1,1)
def rot(name,xyz):rig.pose.bones[name].rotation_euler=[math.radians(a) for a in xyz]
def resting_arms():
    rot('UpperArm.L',(-62,0,0));rot('UpperArm.R',(-62,0,0))
    rot('LowerArm.L',(-8,0,0));rot('LowerArm.R',(-8,0,0))
actions={}
for name,length,step in [('Idle',120,10),('Wave',90,5),('HappyJump',60,5),('TailWag',60,5),('Listen',90,5),('Sleep',120,10)]:
    act=bpy.data.actions.new(name);act.use_fake_user=True;rig.animation_data_create();rig.animation_data.action=act
    for f in range(0,length+1,step):
        scene.frame_set(f);clear_pose();t=f/length;p=sin(t*2*pi)
        resting_arms()
        if name=='Idle':
            rig.pose.bones['Chest'].scale=(1+.013*p,1+.018*p,1+.012*p)
            rot('Tail.1',(2*p,4*p,3*p));rot('Tail.3',(0,5*p,0))
            rot('Ear.L.2',(2*p,0,2*p));rot('Ear.R.2',(-2*p,0,2*p))
        elif name=='Wave':
            env=sin(pi*min(1,t/.20)/2) if t<.2 else sin(pi*min(1,(1-t)/.20)/2) if t>.8 else 1
            rot('UpperArm.R',(-62+110*env,-12*env,0));rot('LowerArm.R',(-8+35*env,0,0))
            rot('Hand.R',(12*sin(t*pi*8)*env,0,18*sin(t*pi*8)*env));rot('Head',(0,-4*env,4*env))
            rot('Tail.2',(0,7*sin(t*2*pi),0))
        elif name=='HappyJump':
            height=max(0,sin(pi*(t-.18)/.64)) if .18<t<.82 else 0
            crouch=sin(pi*t/.18) if t<=.18 else sin(pi*(t-.82)/.18) if t>=.82 else 0
            rig.pose.bones['Hips'].location.y=(.16*height-.025*crouch)*S
            rot('UpperArm.L',(-62+112*height,0,0));rot('UpperArm.R',(-62+112*height,0,0))
            rot('LowerLeg.L',(-18*height-12*crouch,0,0));rot('LowerLeg.R',(-18*height-12*crouch,0,0))
            rot('Tail.1',(-15*height,0,0));rot('Ear.L.2',(0,0,8*height));rot('Ear.R.2',(0,0,-8*height))
        elif name=='TailWag':
            for i in range(1,5):rot('Tail.'+str(i),(2*p,0,(14 if i==1 else 10)*sin(t*4*pi-(i-1)*.3)))
        elif name=='Listen':
            e=sin(pi*t)**2;rot('Head',(0,8*e,16*e));rot('Neck',(0,0,4*e))
            rot('Ear.L.1',(-8*e,0,-10*e));rot('Ear.R.1',(-8*e,0,10*e));rot('Ear.L.2',(-6*e,0,-4*e));rot('Ear.R.2',(-6*e,0,4*e))
        elif name=='Sleep':
            rot('Spine',(17+1*p,0,0));rot('Chest',(12,0,0));rot('Head',(18,0,-7))
            rot('UpperArm.L',(-72,0,-15));rot('UpperArm.R',(-72,0,15))
            rot('Ear.L.1',(8,0,10));rot('Ear.R.1',(8,0,-10))
            for i in range(1,5):rot('Tail.'+str(i),(0,0,16+1*p))
            rig.pose.bones['Chest'].scale=(1+.007*p,1+.013*p,1+.007*p)
        for b in rig.pose.bones:
            b.keyframe_insert('rotation_euler',frame=f,group=b.name)
            b.keyframe_insert('location',frame=f,group=b.name)
            b.keyframe_insert('scale',frame=f,group=b.name)
    actions[name]=act
    act['loop']=name in ['Idle','TailWag','Sleep'];act['fps']=30
    act['description']={'Idle':'Breathing, ears and tail','Wave':'Right-hand greeting','HappyJump':'Anticipation, lift and landing','TailWag':'Independent four-bone tail sway','Listen':'Head tilt and ears perk','Sleep':'Slumped resting pose with breathing'}[name]
# Matching morph action names are merged by the glTF exporter with skeletal clips.
for name,length in [('Idle',120),('Wave',90),('HappyJump',60),('TailWag',60),('Listen',90),('Sleep',120)]:
    sk=mesh.shape_keys;sk.animation_data_create();a=bpy.data.actions.new(name+'_Face');a.use_fake_user=True;sk.animation_data.action=a
    for f in sorted(set([0,length//2,length]+([48,51,54] if name=='Idle' else []))):
        keys['Blink'].value=1 if name=='Sleep' or (name=='Idle' and f==51) else 0
        keys['Happy'].value=1 if name=='HappyJump' and 10<f<50 else .45 if name=='Wave' and 10<f<80 else 0
        keys['MouthOpen'].value=.65 if name=='HappyJump' and 10<f<50 else 0
        for k in ['Blink','Happy','MouthOpen']:keys[k].keyframe_insert('value',frame=f)
    tr=sk.animation_data.nla_tracks.new();tr.name=name;tr.strips.new(name,0,a)
    tr.mute=True
sk.animation_data.action=None
# Put each skeletal action on a named track for predictable independent glTF clips.
rig.animation_data.action=None
for name,act in actions.items():
    tr=rig.animation_data.nla_tracks.new();tr.name=name;tr.strips.new(name,0,act);tr.mute=True
clear_pose()
for k in keys:k.value=0
scene.frame_set(0)

report={'iteration':IT,'blender':bpy.app.version_string,'auto_weights':auto_status,'before_repair':before,'bones':list(bone_names),'vertices':len(mesh.vertices),'faces':len(mesh.polygons),'quads':sum(len(p.vertices)==4 for p in mesh.polygons),'triangles':sum(len(p.vertices)-2 for p in mesh.polygons),'height_m':max(v.co.z for v in mesh.vertices)-min(v.co.z for v in mesh.vertices),'mirror_applied':True,'actions':{n:list(a.frame_range) for n,a in actions.items()}}
after={'unweighted':0,'not_normalized':0,'tail_foreign':0,'ear_foreign':0,'tail_vertices':0,'ear_vertices':0,'max_influences':0}
for v,tags in zip(mesh.vertices,semantic):
    ww=weights_for(v);after['unweighted']+=not bool(ww);after['not_normalized']+=abs(sum(ww.values())-1)>1e-5;after['max_influences']=max(after['max_influences'],len(ww))
    if 'Tail' in tags:after['tail_vertices']+=1;after['tail_foreign']+=any(not n.startswith('Tail.') for n in ww)
    if any(t.startswith('Ear.') for t in tags):after['ear_vertices']+=1;after['ear_foreign']+=any(not(n.startswith('Ear.') or n=='Head') for n in ww)
report['after_repair']=after
print('NAVI WEIGHT REPORT',json.dumps(report,indent=2),flush=True)
(ROOT/f'tools/blender/qa/iteration-{IT}.json').write_text(json.dumps(report,indent=2))

# Neutral studio. All studio objects are excluded from GLB by explicit selection.
scene.render.engine='BLENDER_EEVEE'
scene.render.resolution_x=A.resolution;scene.render.resolution_y=A.resolution;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
scene.world=bpy.data.worlds.new('Navi dark studio');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.027,.037,.061,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.45
scene.view_settings.view_transform='Standard' if IT>=4 else 'AgX'
def area(name,loc,power,size,color):
    d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;d.color=color
    o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,.5))-o.location).to_track_quat('-Z','Y').to_euler()
area('Studio key',(-1.2,-1.8,2.3),70 if IT>=5 else 110,2.1,(1,.91,.82))
area('Studio fill',(1.5,-1,1),45 if IT>=5 else 80,2,(.72,.86,1))
area('Studio rim',(0,1.5,1.8),85 if IT>=5 else 125,1.5,(.45,.78,1))
camd=bpy.data.cameras.new('Navi Studio Camera');cam=bpy.data.objects.new('Navi Studio Camera',camd);bpy.context.collection.objects.link(cam);scene.camera=cam;camd.type='ORTHO';camd.ortho_scale=1.16
def view(name,deg,pose=None,frame=0,prefix=None,morph=None):
    rig.animation_data.action=None;sk.animation_data.action=None;clear_pose()
    for k in keys:k.value=0
    if pose:
        rig.animation_data.action=actions[pose]
        sk.animation_data.action=bpy.data.actions.get(pose+'_Face')
    scene.frame_set(frame);bpy.context.view_layer.update()
    if morph:keys[morph].value=1;bpy.context.view_layer.update()
    camd.ortho_scale=1.26 if pose in ['Wave','HappyJump','Listen'] else 1.16
    angle=math.radians(deg);target=Vector((0,.035,.65 if pose=='HappyJump' else .50))
    cam.location=target+Vector((2.8*sin(angle),-2.8*cos(angle),.10 if name=='threequarter' else 0))
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(ROOT/'renders'/f'{prefix or ("navi-v1-iter"+str(IT))}-{name}.png')
    bpy.ops.render.render(write_still=True)
for name,angle in [('front',0),('side',90),('back',180),('threequarter',35)]:view(name,angle,prefix='navi-v1' if A.final else None)
if A.final:
    view('wave',15,'Wave',45,'navi-v1');view('tailwag',135,'TailWag',35,'navi-v1')
    view('sleep',35,'Sleep',60,'navi-v1')
    if IT>=5:
        view('happyjump',15,'HappyJump',30,'navi-v1');view('listen',0,'Listen',45,'navi-v1')
        for morph in ['Blink','Happy','MouthOpen']:view(morph.lower(),0,prefix='navi-v1',morph=morph)
rig.animation_data.action=None;sk.animation_data.action=None;clear_pose();scene.frame_set(0)
for k in keys:k.value=0
bpy.context.view_layer.update()
obj['build_iteration']=IT;obj['symmetry']='X mirror applied before rigging';obj['front']='-Y';obj['height_m']=1.0
rig['loop_actions']='Idle, TailWag, Sleep';rig['authored_fps']=30
bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=rig
scene.frame_start=0;scene.frame_end=120
if A.final:
    # Export only unmuted named NLA tracks. Their time domains are deliberately shared.
    for tr in rig.animation_data.nla_tracks:tr.mute=False
    for tr in sk.animation_data.nla_tracks:tr.mute=False
    bpy.ops.export_scene.gltf(filepath=str(ROOT/'assets/models/navi-v1.glb'),export_format='GLB',use_selection=True,export_yup=True,export_animations=True,export_animation_mode='NLA_TRACKS',export_merge_animation='NLA_TRACK',export_force_sampling=True,export_frame_range=False,export_skins=True,export_morph=True,export_morph_animation=True,export_rest_position_armature=True,export_influence_nb=4,export_extras=True,export_materials='EXPORT',export_cameras=False,export_lights=False)
    for tr in rig.animation_data.nla_tracks:tr.mute=True
    for tr in sk.animation_data.nla_tracks:tr.mute=True
    rig.animation_data.action=None;sk.animation_data.action=None;clear_pose();scene.frame_set(0)
    for k in keys:k.value=0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/models'/('navi-v1.blend' if A.final else 'navi-v1-review.blend')))
print('NAVI BUILD COMPLETE',flush=True)
