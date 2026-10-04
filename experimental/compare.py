"""Run one fixed A/B experiment: python -m experimental.compare --output PATH."""
import argparse
from dataclasses import asdict
import hashlib
import html
import json
from pathlib import Path
import statistics
import time

from PIL import Image, ImageDraw, ImageChops, ImageStat

import ascii_renderer as renderer
import exporter
from .character_grid_matte import build_baseline, build_experiment, calibrate_glyph_coverage
from .fixtures import make_fixtures


def configuration(source, cols=120, rows=64, mode='light'):
    return dict(src=str(source), cols=cols, rows=rows, cell_w=8, cell_h=15,
                ramp=renderer.DEFAULT_RAMP, contrast=renderer.DEFAULT_CONTRAST,
                brightness=1., gamma=1., mode=mode,
                foreground='#eeeeee' if mode == 'dark' else '#111111',
                background='#080d15' if mode == 'dark' else None if mode == 'original' else '#ffffff',
                palette=['#34537a','#ce775b','#e5ba67'], animation='instant', speed='normal', loop='no')


def background_for(config):
    return renderer.infer_original_background(config['src']) if config['background'] == 'original' else config['background']


def export(config, grid, stem):
    started = time.perf_counter()
    svg = renderer.render_svg(config, grid)
    foreground = exporter.render_foreground(config, grid)
    render_ms = (time.perf_counter()-started)*1000
    stem.with_suffix('.svg').write_text(svg)
    exporter.save_png(foreground, str(stem.with_suffix('.png')), background_for(config), None)
    return foreground, dict(render_ms=render_ms, svg_bytes=len(svg.encode()), png_bytes=stem.with_suffix('.png').stat().st_size)


def on_checker(image):
    checker = Image.new('RGBA',image.size,'#f5f5f5');d=ImageDraw.Draw(checker)
    for y in range(0,image.height,20):
        for x in range(0,image.width,20):
            if (x//20+y//20)%2:d.rectangle((x,y,x+19,y+19),fill='#e5e5e5')
    checker.alpha_composite(image.convert('RGBA'))
    return checker.convert('RGB')


def side_by_side(config, directory):
    source=renderer.load_source(config['src'])
    rgb,alpha,_=renderer.crop_to_cell_aspect(source.convert('RGB'),source.getchannel('A'),config)
    rgb.putalpha(alpha)
    source=rgb.resize((config['cols']*config['cell_w'],config['rows']*config['cell_h']),Image.Resampling.LANCZOS)
    canvas=Image.new('RGBA',exporter.canvas_size(config),background_for(config) or (0,0,0,0));canvas.alpha_composite(source,(20,20))
    canvas.save(directory/'source-cropped.png')
    images=[canvas]+[Image.open(directory/f'{name}.png').convert('RGBA') for name in ['baseline','experimental']]
    width=600;height=round(images[0].height*width/images[0].width)
    contact=Image.new('RGB',(3*width,height+40),'#f1f1ef');d=ImageDraw.Draw(contact)
    for i,(name,image) in enumerate(zip(['Source (same crop)','A · baseline','B · character + shapes + matte'],images)):
        d.text((i*width+12,12),name,fill='#222222')
        contact.paste(on_checker(image).resize((width,height),Image.Resampling.LANCZOS),(i*width,40))
    contact.save(directory/'comparison.png')


def diagnostics(config, experiment, directory):
    cols,rows=config['cols'],config['rows']
    matte=Image.new('L',(cols,rows));matte.putdata([round(v*255)for row in experiment.matte.coverage for v in row])
    matte.resize((cols*8,rows*8),Image.Resampling.NEAREST).save(directory/'matte.png')
    shapes=Image.new('RGB',(cols,rows))
    colours=[tuple(50+b%180 for b in hashlib.sha256(f'region-{i}'.encode()).digest()[:3])for i in range(len(experiment.shapes.regions))]
    shapes.putdata([colours[i]for row in experiment.shapes.owners for i in row])
    shapes.resize((cols*8,rows*8),Image.Resampling.NEAREST).save(directory/'shapes.png')
    (directory/'layers.json').write_text(json.dumps(asdict(experiment),sort_keys=True,separators=(',',':')))
    export(config,experiment.characters.as_grid(),directory/'character-only')


def measurements(config, baseline, result, experiment, a, b):
    coverage=experiment.characters.glyph_coverage
    changed=0;visible=0;max_error=0.;variation_a=variation_b=0
    for y,row in enumerate(baseline):
        for x,old in enumerate(row):
            new=result[y][x]
            if old['alpha']>0 and coverage[old['index']]>0:
                visible+=1;changed+=old['index']!=new['index']
            max_error=max(max_error,abs(old['alpha']*coverage[old['index']]-new['alpha']*coverage[new['index']]))
            for dx,dy in [(1,0),(0,1)]:
                if x+dx<config['cols'] and y+dy<config['rows']:
                    other=baseline[y+dy][x+dx];after=result[y+dy][x+dx]
                    if old['alpha']>0 and other['alpha']>0 and coverage[old['index']]>0 and coverage[other['index']]>0:
                        variation_a+=old['index']!=other['index'];variation_b+=new['index']!=after['index']
    # These are diagnostics, not a recognition score or decision rule.
    return dict(shape_count=len(experiment.shapes.regions),visible_cells=visible,changed_glyphs=changed,
                differing_glyph_neighbours_baseline=variation_a,differing_glyph_neighbours_experimental=variation_b,
                maximum_calibrated_ink_error=max_error,
                total_alpha_baseline=sum(a.getchannel('A').getdata()),total_alpha_experimental=sum(b.getchannel('A').getdata()))


def compare_case(name, source, description, config, output):
    directory=output/name;directory.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter();baseline=build_baseline(config);base_ms=(time.perf_counter()-started)*1000
    started=time.perf_counter();experiment=build_experiment(config,baseline);result=experiment.compose();extra_ms=(time.perf_counter()-started)*1000
    a,am=export(config,baseline,directory/'baseline');b,bm=export(config,result,directory/'experimental')
    diagnostics(config,experiment,directory);side_by_side(config,directory)
    entry=dict(name=name,source=str(source),description=description,config=config,baseline_build_ms=base_ms,
               experimental_extra_ms=extra_ms,baseline=am,experimental=bm,
               metrics=measurements(config,baseline,result,experiment,a,b))
    (directory/'metrics.json').write_text(json.dumps(entry,indent=2,sort_keys=True))
    print(name,'shapes',len(experiment.shapes.regions),'changed glyphs',entry['metrics']['changed_glyphs'],flush=True)
    return entry


def benchmark(source, output):
    results=[];directory=output/'performance';directory.mkdir(exist_ok=True)
    for cols,rows in [(120,64),(160,90),(200,120),(300,166)]:
        config=configuration(source,cols,rows)
        base_times=[];extra_times=[];a_times=[];b_times=[]
        for _ in range(3):
            t=time.perf_counter();grid=build_baseline(config);base_times.append((time.perf_counter()-t)*1000)
            t=time.perf_counter();experiment=build_experiment(config,grid);result=experiment.compose();extra_times.append((time.perf_counter()-t)*1000)
            t=time.perf_counter();sa=renderer.render_svg(config,grid);fa=exporter.render_foreground(config,grid);a_times.append((time.perf_counter()-t)*1000)
            t=time.perf_counter();sb=renderer.render_svg(config,result);fb=exporter.render_foreground(config,result);b_times.append((time.perf_counter()-t)*1000)
        stem=directory/f'{cols}x{rows}'
        fa.save(str(stem)+'-baseline.png');fb.save(str(stem)+'-experimental.png')
        entry=dict(cols=cols,rows=rows,regions=len(experiment.shapes.regions),
                   baseline_grid_ms=statistics.median(base_times),experiment_extra_ms=statistics.median(extra_times),
                   baseline_render_ms=statistics.median(a_times),experimental_render_ms=statistics.median(b_times),
                   baseline_svg_bytes=len(sa.encode()),experimental_svg_bytes=len(sb.encode()),
                   baseline_png_bytes=Path(str(stem)+'-baseline.png').stat().st_size,
                   experimental_png_bytes=Path(str(stem)+'-experimental.png').stat().st_size)
        results.append(entry);print('benchmark',cols,rows,flush=True)
    (output/'performance.json').write_text(json.dumps(results,indent=2))


def write_gallery(entries, output):
    parts=['<!doctype html><meta charset="utf-8"><title>Character / Shapes / Matte · experiment</title>',
           '<style>body{font:16px system-ui;margin:32px;background:#eee;color:#222}article{margin:40px 0}img{max-width:100%}a{color:#24558b}.layers{display:flex;gap:16px}.layers img{width:30%}p{max-width:80ch}</style>',
           '<h1>Character + Grid Shapes + Matte · first version</h1><p>A uses the untouched production grid. B changes glyph organization, then restores calibrated ink demand with a separate matte. All pairs share the source, crop, mode, ramp, metrics and preprocessing. The coloured regions and grayscale matte below are diagnostic views; neither is drawn into the final artwork.</p>']
    for entry in entries:
        name=entry['name'];metrics=entry['metrics']
        parts += [f'<article><h2>{html.escape(name)}</h2><p>{html.escape(entry["description"])}</p>',
                  f'<img src="{name}/comparison.png" alt="Source, baseline, experiment">',
                  f'<p>{metrics["shape_count"]} regions · {metrics["changed_glyphs"]}/{metrics["visible_cells"]} visible glyphs changed. Neighbour glyph transitions: {metrics["differing_glyph_neighbours_baseline"]} → {metrics["differing_glyph_neighbours_experimental"]}. This measures regularity, not recognizability.</p>',
                  f'<p><a href="{name}/baseline.svg">Baseline SVG</a> · <a href="{name}/experimental.svg">Experimental SVG</a> · <a href="{name}/baseline.png">Baseline PNG</a> · <a href="{name}/experimental.png">Experimental PNG</a> · <a href="{name}/layers.json">Layer data</a></p>',
                  f'<div class="layers"><img src="{name}/character-only.png" alt="Character layer without matte"><img src="{name}/shapes.png" alt="Shape ownership"><img src="{name}/matte.png" alt="Matte coverage"></div></article>']
    (output/'index.html').write_text('\n'.join(parts))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source',type=Path,help='Optional local image instead of the fixed eight-category suite')
    parser.add_argument('--cols',type=int,default=120);parser.add_argument('--rows',type=int,default=64)
    parser.add_argument('--mode',choices=sorted(renderer.VALID_MODES),default='light')
    parser.add_argument('--benchmark',action='store_true')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    fixtures=([('custom',args.source,'User-supplied local image')] if args.source else make_fixtures(args.output/'sources'))
    entries=[]
    for name,source,description in fixtures:
        entries.append(compare_case(name,source,description,configuration(source,args.cols,args.rows,args.mode),args.output))
    if not args.source:
        for name,mode in [('portrait','dark'),('transparent','original'),('object','multicolour')]:
            _,source,description=next(item for item in fixtures if item[0]==name)
            entries.append(compare_case(name+'-'+mode,source,description,configuration(source,args.cols,args.rows,mode),args.output))
    (args.output/'manifest.json').write_text(json.dumps(entries,indent=2,sort_keys=True))
    write_gallery(entries,args.output)
    if args.benchmark:benchmark(fixtures[0][1],args.output)


if __name__=='__main__':
    main()
