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
                    a=pi*i/24;dx=rx*cos(a)*(1.025-.025*u)
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
