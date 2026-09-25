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
args.add_argument('--iteration', type=int, default=2)
args.add_argument('--final', action='store_true')
args.add_argument('--resolution', type=int, default=800)
A = args.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
PASS = A.iteration
IT = 5
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
# One continuous cream face: annular skin topology around a real mouth opening.
# No image textures, separate cheek balls, or painted mouth strokes.
N=48; R=12 if PASS>=2 else 11
rows=[]
def face_y(x,z):
    return -.111-.073*math.exp(-((z-.587)/.055)**2)-.025*math.exp(-((abs(x)-.079)/.066)**2-((z-.685)/.068)**2)+.014*(abs(x)/.177)**2
for j in range(R+1):
    t=j/R; row=[]
    for i in range(N):
        a=2*pi*i/N
        ox=.177*cos(a)
        oz=.625+sin(a)*(.09+.070*math.exp(-((abs(ox)-.080)/.052)**2)) if sin(a)>0 else .625+.087*sin(a)
        ix=.047*cos(a);iz=.586+.0034*sin(a)+.008*(abs(ix)/.047)**2
        x=ix*(1-t)+ox*t;z=iz*(1-t)+oz*t
        y=face_y(x,z)
        edge=max(0,(t-.80)/.20)
        y=y*(1-edge*edge)+(-.069)*edge*edge
        row.append(g.vertex((x,y,z),W('Head'),('FaceSkin',),(.5+x*2,.5+z-.63)))
    rows.append(row)
for j in range(R):
    for i in range(N):g.face([rows[j][i],rows[j][(i+1)%N],rows[j+1][(i+1)%N],rows[j+1][i]],CREAM)
# Rounded perimeter closes into the head, hiding its join inside the navy shell.
back=[g.vertex((g.v[v][0]*.94,-.040,g.v[v][2]),W('Head'),('FaceSkin',)) for v in rows[-1]]
for i in range(N):g.face([rows[-1][i],rows[-1][(i+1)%N],back[(i+1)%N],back[i]],CREAM)
g.face(list(reversed(back)),CREAM)
# Actual lip thickness and dark cavity walls; mouth opening is part of the skin.
last=rows[0]
for depth,shrink in [(.0025,.98),(.009,.91),(.023,.66),(.030,.025)]:
    nxt=[]
    for i in range(N):
        x,y,z=g.v[rows[0][i]]
        nxt.append(g.vertex((x*shrink,y+depth,.586+(z-.586)*shrink),W('Head'),('MouthCavity',)))
    for i in range(N):g.face([last[(i+1)%N],last[i],nxt[i],nxt[(i+1)%N]],CREAM if depth<.003 else NOSE)
    last=nxt
g.face(last,NOSE)
# Rounded nose settles into the muzzle.
g.ell((0,-.183,.616),(.019,.009,.011),NOSE,W('Head'),('Nose',),n=24,rings=12)
# Small cheek tips preserve fox silhouette; their roots are buried in the skin.
for s,suf in [(1,'L'),(-1,'R')]:
    for dz,x in [(0,.184),(-.027,.166)]:
        g.patch([(s*.124,-.080,.623+dz),(s*x,-.045,.617+dz),(s*.148,-.067,.591+dz),(s*.117,-.092,.590+dz)],(s*.141,-.065,.607+dz),.016,CREAM,W('Head'),levels=4)
    x=s*.079;z=.672;q=math.sqrt(.90)
    # Same eye silhouette scaled by sqrt(.90): exactly ten percent less area.
    eye_start=len(g.v)
    for c,r,mat,n in [((x,-.136,z),(.051,.018,.071),NOSE,24),((x,-.148,z),(.046,.013,.065),WHITE,24),((x-s*.007,-.160,z-.005),(.033,.010,.055),BLUE,24),((x-s*.007,-.168,z+.004),(.024,.006,.044),EYE,20),((x-s*.014,-.174,z+.030),(.010,.003,.014),WHITE,10),((x+s*.008,-.173,z-.032),(.004,.002,.006),WHITE,10)]:
        g.ell(c,r,mat,W('Head'),('Eye',),n=n,rings=14)
    for k in range(eye_start,len(g.v)):
        xx,yy,zz=g.v[k];g.v[k]=(x+(xx-x)*q,yy+.003,z+(zz-z)*q)
    # Solid upper/lower eyelid ribbons, with a rounded edge and thickness.
    rx=.051*1.12*q;rz=.071*q
    for side in [1,-1]:
        layers=[]
        for backface in [False,True]:
            grid=[]
            for j in range(4):
                u=j/3;row=[]
                for i in range(25):
                    a=pi*i/24;dx=rx*cos(a)
                    zz=z+side*rz*sin(a)*(1.12-.16*u)
                    yy=-.137-.028*u*sin(a)+( .0012 if backface else 0)
                    row.append(g.vertex((x+dx,yy,zz),W('Head'),('LidTop' if side==1 else 'LidBottom','LidRow'+str(j),'LidBack' if backface else 'LidFront')))
                grid.append(row)
            layers.append(grid)
            for j in range(3):
                for i in range(24):
                    face=[grid[j][i],grid[j][i+1],grid[j+1][i+1],grid[j+1][i]]
                    g.face(face if not backface else list(reversed(face)),CREAM)
        for j in [0,3]:
            for i in range(24):g.face([layers[0][j][i],layers[1][j][i],layers[1][j][i+1],layers[0][j][i+1]],CREAM)
        for i in [0,24]:
            for j in range(3):g.face([layers[0][j][i],layers[0][j+1][i],layers[1][j+1][i],layers[1][j][i]],CREAM)
    # Brows retain the cyan identity and get their own expressive geometry tags.
    g.tube([(s*.038,-.111,.755),(s*.058,-.119,.769),(s*.079,-.117,.774),(s*.098,-.106,.766)],[.0015,.0027,.0028,.0015],GLOW,W('Head'),('Brow',),n=8)
    g.tube([(s*.137,-.140,.611),(s*.152,-.127,.617)],[.002,.001],GLOW,W('Head'),n=6)

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

# A shallow core panel follows the torso surface; its seam flows into the belly.
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
tailrs=[(.016,.015),(.032,.031),(.055,.049),(.065,.056),(.061,.054),(.048,.047),(.030,.032),(.012,.016),(.0007,.0007)]
def tw(t,co):
    # Cubic B-spline blend gives smooth derivatives across all four joints.
    u=t*3
    ww={}
    for j in range(4):
        d=abs(u-j)
        w=(2/3-d*d+.5*d*d*d) if d<1 else ((2-d)**3/6 if d<2 else 0)
        if w>0:ww['Tail.'+str(j+1)]=w
    total=sum(ww.values())
    return {n:w/total for n,w in ww.items()}
# Densify the centreline before sweeping: 33 longitudinal rings.
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
g.tube(tailpts,tailrs,TAIL,tw,('Tail',),n=24)
# Distal limb scaling, before mirror and normalization.
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

mesh=bpy.data.meshes.new('Navi_SoftSurface'); mesh.from_pydata(g.v,[],g.f); mesh.update()
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
auto_status='deterministic anatomical weights (v1 repair preserved)'
obj.parent=rig
bone_names=set(b.name for b in arm.bones)
def weights_for(v):return {obj.vertex_groups[e.group].name:e.weight for e in v.groups if obj.vertex_groups[e.group].name in bone_names and e.weight>1e-6}
before={'unweighted':0,'tail_foreign':0,'ear_foreign':0}
for v,tags in zip(mesh.vertices,semantic):
    ww=weights_for(v)
    before['unweighted']+=not bool(ww)
    before['tail_foreign']+=('Tail' in tags and any(not n.startswith('Tail.') for n in ww))
    before['ear_foreign']+=(any(t.startswith('Ear.') for t in tags) and any(not(n.startswith('Ear.') or n=='Head') for n in ww))
# Planned anatomical weights applied below.
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

# Actions: explicit frame-zero poses, local Euler channels, stable loop endpoints.
scene=bpy.context.scene;scene.render.fps=30
def clear_pose():
    for b in rig.pose.bones:b.rotation_mode='XYZ';b.rotation_euler=(0,0,0);b.location=(0,0,0);b.scale=(1,1,1)
def rot(name,xyz):rig.pose.bones[name].rotation_euler=[math.radians(a) for a in xyz]
def resting_arms():
    rot('UpperArm.L',(-62,0,0));rot('UpperArm.R',(-62,0,0))
    rot('LowerArm.L',(-8,0,0));rot('LowerArm.R',(-8,0,0))
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

# Put each skeletal action on a named track for predictable independent glTF clips.
rig.animation_data.action=None
for name,act in actions.items():
    tr=rig.animation_data.nla_tracks.new();tr.name=name;tr.strips.new(name,0,act);tr.mute=True
clear_pose()
for k in keys:k.value=0
scene.frame_set(0)

report={'iteration':PASS,'blender':bpy.app.version_string,'auto_weights':auto_status,'before_repair':before,'bones':list(bone_names),'vertices':len(mesh.vertices),'faces':len(mesh.polygons),'quads':sum(len(p.vertices)==4 for p in mesh.polygons),'triangles':sum(len(p.vertices)-2 for p in mesh.polygons),'height_m':max(v.co.z for v in mesh.vertices)-min(v.co.z for v in mesh.vertices),'mirror_applied':True,'actions':{n:list(a.frame_range) for n,a in actions.items()}}
after={'unweighted':0,'not_normalized':0,'tail_foreign':0,'ear_foreign':0,'tail_vertices':0,'ear_vertices':0,'max_influences':0}
for v,tags in zip(mesh.vertices,semantic):
    ww=weights_for(v);after['unweighted']+=not bool(ww);after['not_normalized']+=abs(sum(ww.values())-1)>1e-5;after['max_influences']=max(after['max_influences'],len(ww))
    if 'Tail' in tags:after['tail_vertices']+=1;after['tail_foreign']+=any(not n.startswith('Tail.') for n in ww)
    if any(t.startswith('Ear.') for t in tags):after['ear_vertices']+=1;after['ear_foreign']+=any(not(n.startswith('Ear.') or n=='Head') for n in ww)
report['after_repair']=after
print('NAVI WEIGHT REPORT',json.dumps(report,indent=2),flush=True)
(ROOT/f'tools/blender/qa/v2-iteration-{PASS}.json').write_text(json.dumps(report,indent=2))

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
    angle=math.radians(deg)
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
    scene.render.filepath=str(ROOT/'renders'/f'{prefix or ("navi-v2-iter"+str(PASS))}-{name}.png')
    bpy.ops.render.render(write_still=True)
for name,angle in [('front',0),('side',90),('back',180),('threequarter',35)]:view(name,angle,prefix='navi-v2' if A.final else None)
if A.final:
    for name,frame,deg in [('Sleep',60,35),('Notice',42,10),('Stretch',45,15),('Inspect',60,35),('Celebrate',36,15),('Concerned',45,0),('Wave',45,15),('HappyJump',30,15),('TailWag',35,135),('Listen',45,0),('Idle',0,15)]:
        view(name.lower(),deg,name,frame,'navi-v2')
    for morph in ['Blink','Happy','MouthOpen','Surprised','Sad']:view(morph.lower(),0,prefix='navi-v2',morph=morph)
else:
    for morph in ['Blink','MouthOpen','Sad']:view(morph.lower(),0,morph=morph)
rig.animation_data.action=None;sk.animation_data.action=None;clear_pose();scene.frame_set(0)
for k in keys:k.value=0
bpy.context.view_layer.update()
obj['build_iteration']=IT;obj['symmetry']='X mirror applied before rigging';obj['front']='-Y';obj['height_m']=1.0
rig['loop_actions']='Idle, TailWag, Sleep, Inspect, Concerned';rig['authored_fps']=30
bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=rig
scene.frame_start=0;scene.frame_end=120
if A.final:
    # Export only unmuted named NLA tracks. Their time domains are deliberately shared.
    for tr in rig.animation_data.nla_tracks:tr.mute=False
    for tr in sk.animation_data.nla_tracks:tr.mute=False
    bpy.ops.export_scene.gltf(filepath=str(ROOT/'assets/models/navi-v2.glb'),export_format='GLB',use_selection=True,export_yup=True,export_animations=True,export_animation_mode='NLA_TRACKS',export_merge_animation='NLA_TRACK',export_force_sampling=True,export_frame_range=False,export_skins=True,export_morph=True,export_morph_animation=True,export_rest_position_armature=True,export_influence_nb=4,export_extras=True,export_materials='EXPORT',export_cameras=False,export_lights=False)
    for tr in rig.animation_data.nla_tracks:tr.mute=True
    for tr in sk.animation_data.nla_tracks:tr.mute=True
    rig.animation_data.action=None;sk.animation_data.action=None;clear_pose();scene.frame_set(0)
    for k in keys:k.value=0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/models'/('navi-v2.blend' if A.final else 'navi-v2-review.blend')))
print('NAVI BUILD COMPLETE',flush=True)
