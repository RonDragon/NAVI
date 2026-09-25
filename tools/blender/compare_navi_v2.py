"""Offline, labeled review sheets; requires the already installed Pillow."""
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw
import argparse
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--iteration',type=int,default=2);args=p.parse_args()
for view in ['front','side','back']:
    sources=[('CONCEPT',ROOT/f'assets/concept/navi-{view}.png'),('V1',ROOT/f'renders/navi-v1-{view}.png'),(f'V2 / FACE PASS {args.iteration}',ROOT/f'renders/navi-v2-iter{args.iteration}-{view}.png')]
    out=Image.new('RGB',(1536,558),'#202733');draw=ImageDraw.Draw(out)
    for i,(label,path) in enumerate(sources):
        im=Image.open(path).convert('RGB');im=ImageOps.contain(im,(512,512))
        out.paste(im,(i*512+(512-im.width)//2,40+(512-im.height)//2));draw.text((i*512+20,14),label,fill='white')
    out.save(ROOT/f'renders/navi-v2-comparison-{args.iteration}-{view}.png')
