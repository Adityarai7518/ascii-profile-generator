"""Local deterministic evaluation scenes, not claimed to be natural photos."""
import math
from pathlib import Path

from PIL import Image, ImageDraw


def make_fixtures(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    sample = Path(__file__).resolve().parents[1] / 'sample.png'
    paths = []
    def save(name, image, description):
        path = directory / (name + '.png')
        image.save(path)
        paths.append((name, path, description))

    with Image.open(sample) as source:
        # A face crop from the repository's illustrated characters, not a
        # substitute for testing real human portraits in a later study.
        save('portrait', source.convert('RGBA').crop((510, 85, 1070, 735)),
             'Stylized face crop from repository sample.png; no human photograph.')
        transparent = source.convert('RGBA').copy()

    image = Image.new('RGB', (512, 512), '#e4e5e6')
    d = ImageDraw.Draw(image)
    d.ellipse((75, 382, 456, 422), fill='#b7b9bc')
    d.rounded_rectangle((67, 169, 449, 394), radius=24, fill='#42484e')
    d.rounded_rectangle((132, 133, 265, 204), radius=10, fill='#575f65')
    d.rectangle((94, 180, 420, 222), fill='#747b81')
    d.rectangle((324, 191, 395, 211), fill='#d9e1e2')
    for radius in range(98, 0, -1):
        value = (145 if radius > 84 else 38 if radius > 69 else 85 if radius > 61 else 20+radius//3)
        d.ellipse((245-radius, 289-radius, 245+radius, 289+radius), fill=(value, value+4, value+8))
    d.ellipse((208, 238, 249, 260), fill='#adbcc7')
    d.rounded_rectangle((94, 143, 117, 178), radius=3, fill='#353c42')
    save('object', image, 'Controlled camera/product scene with lens, body, highlight and shadow.')

    image = Image.new('RGB', (512, 512))
    image.putdata([(140+y//8, 178+y//12, 205+y//20) for y in range(512) for _ in range(512)])
    d = ImageDraw.Draw(image)
    d.ellipse((358, 59, 412, 113), fill='#f4e7b8')
    d.polygon([(0,280),(85,154),(168,256),(276,104),(402,284),(512,183),(512,512),(0,512)], fill='#6d8090')
    d.polygon([(202,197),(276,104),(342,196),(293,162),(274,186),(247,157)], fill='#dce5e5')
    d.polygon([(0,360),(103,283),(195,355),(296,256),(419,345),(512,293),(512,512),(0,512)], fill='#496358')
    d.polygon([(246,338),(285,338),(379,512),(72,512)], fill='#a6c5cc')
    for x,y,h in [(40,350,120),(448,380,132),(389,344,80),(105,345,56),(484,354,70)]:
        d.rectangle((x-3,y-h//2,x+3,y+20), fill='#363a30')
        for offset in [0,h//4,h//2]:
            d.polygon([(x,y-h+offset),(x-h//4,y-h//2+offset),(x+h//4,y-h//2+offset)],fill='#293f39')
    save('landscape', image, 'Controlled mountain, water and tree scene; no landscape photograph.')
    gray = image.convert('L').point(lambda v: 108+round(v*36/255)).convert('RGB')
    save('low-contrast', gray, 'Same landscape compressed to a narrow input tonal range.')

    image = Image.new('RGB', (512,512), 'white');d = ImageDraw.Draw(image)
    d.ellipse((61,67,378,384), fill='black')
    d.ellipse((141,141,300,301), fill='white')
    d.polygon([(360,105),(448,418),(283,418)],fill='black')
    d.line((30,466,480,466),fill='black',width=4)
    save('high-contrast',image,'Binary contours, ring, diagonal boundaries and a thin line.')

    image = Image.new('RGB',(512,512),'#eeeeee');d = ImageDraw.Draw(image)
    for box,value in [((30,30,250,230),55),((250,30,480,230),105),((30,230,250,480),155),((250,230,480,480),200)]:
        d.rectangle(box,fill=(value,)*3)
    d.ellipse((175,155,335,315),fill='#777777')
    save('flat-regions',image,'Broad constant-tone regions with a crossing circular boundary.')

    image = Image.new('RGB',(512,512));values=[]
    for y in range(512):
        for x in range(512):
            radius=math.hypot(x-256,y-256)
            value=round(128+52*math.sin(x*.34)*math.sin(y*.23)+48*math.cos(radius*.21))
            values.append((value,)*3)
    image.putdata(values)
    save('fine-detail',image,'Deterministic woven/radial fine-detail stress field; not natural texture.')
    save('transparent',transparent,'Unmodified repository RGBA sample with illustrated facial/object detail.')
    return paths
