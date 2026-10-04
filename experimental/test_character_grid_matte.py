"""Focused invariants for the opt-in experiment; production tests stay intact."""
import copy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from PIL import Image, ImageChops

import ascii_renderer as renderer
import exporter
from . import character_grid_matte as cgm
from .compare import configuration


def grid_for(config):
    return [[dict(index=(x+3*y)%len(config['ramp']), alpha=(0.,.25,.65,1.)[(x+y)%4],
                  color='#3a719d' if x%2 else '#ab7146', tone=(y+1)/(config['rows']+1))
             for x in range(config['cols'])] for y in range(config['rows'])]


class CharacterGridMatteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)
        image=Image.new('RGBA',(128,96));image.putdata([(x*2,y*2,120,0 if x<24 else 140 if x<60 else 255) for y in range(96) for x in range(128)])
        self.source=self.path/'source.png';image.save(self.source)
        self.c=configuration(self.source,24,13)

    def test_deterministic_layers_and_serialized_outputs(self):
        baseline=cgm.build_baseline(self.c);frozen=copy.deepcopy(baseline)
        a=cgm.build_experiment(self.c,baseline);b=cgm.build_experiment(self.c,baseline)
        self.assertEqual(a,b);self.assertEqual(a.compose(),b.compose())
        self.assertEqual(renderer.render_svg(self.c,a.compose()),renderer.render_svg(self.c,b.compose()))
        for name,result in [('a',a),('b',b)]:
            exporter.render_foreground(self.c,result.compose()).save(self.path/(name+'.png'))
        self.assertEqual((self.path/'a.png').read_bytes(),(self.path/'b.png').read_bytes())
        self.assertEqual(baseline,frozen)

    def test_reproducible_across_process_hash_seeds(self):
        code='''import hashlib,json
from dataclasses import asdict
from experimental.character_grid_matte import build_experiment
from experimental.compare import configuration
import ascii_renderer as r
c=configuration(SOURCE,24,13)
e=build_experiment(c)
print(hashlib.sha256(json.dumps(asdict(e),sort_keys=True).encode()+r.render_svg(c,e.compose()).encode()).hexdigest())
'''.replace('SOURCE',repr(str(self.source)))
        values=[]
        for seed in ['1','314159']:
            env=dict(os.environ,PYTHONHASHSEED=seed,PYTHONDONTWRITEBYTECODE='1')
            values.append(subprocess.check_output([sys.executable,'-c',code],env=env,text=True))
        self.assertEqual(*values)

    def test_shape_ownership_at_small_extreme_and_large_dimensions(self):
        for cols,rows in [(1,1),(1,200),(300,1),(3,2),(7,9),(120,64),(160,90),(200,120),(300,166)]:
            with self.subTest(dimensions=(cols,rows)):
                c=dict(self.c,cols=cols,rows=rows,ramp=' .:@');g=grid_for(c)
                shapes=cgm.build_grid_shapes(c,g)
                self.assertLessEqual(len(shapes.regions),cgm.MAX_REGIONS)
                counts=[[0]*cols for _ in range(rows)]
                for i,region in enumerate(shapes.regions):
                    x0,y0,x1,y1=region.bounds
                    self.assertTrue(0<=x0<x1<=cols and 0<=y0<y1<=rows)
                    self.assertLessEqual(region.depth,cgm.MAX_DEPTH)
                    for y in range(y0,y1):
                        for x in range(x0,x1):
                            counts[y][x]+=1;self.assertEqual(shapes.owners[y][x],i)
                self.assertTrue(all(n==1 for row in counts for n in row))

    def test_regions_follow_data_boundary_and_leave_flat_regions_whole(self):
        c=dict(self.c,cols=11,rows=7,ramp=' .:@')
        g=[[dict(index=1 if x<3 else 3,alpha=1.,color='#111111',tone=.2 if x<3 else .8)for x in range(11)]for _ in range(7)]
        regions=cgm.build_grid_shapes(c,g).regions
        self.assertEqual([s.bounds for s in regions],[(0,0,3,7),(3,0,11,7)])
        for row in g:
            for cell in row:cell['index']=1
        self.assertEqual(len(cgm.build_grid_shapes(c,g).regions),1)

    def test_region_budget_bounds_complex_input(self):
        c=dict(self.c,cols=40,rows=30,ramp=' .:@');g=grid_for(c)
        shapes=cgm.build_grid_shapes(c,g,max_regions=8)
        self.assertEqual(len(shapes.regions),8)
        self.assertTrue(all(i>=0 for row in shapes.owners for i in row))
        with self.assertRaises(ValueError):cgm.build_grid_shapes(c,g,max_regions=cgm.MAX_REGIONS+1)

    def test_character_layer_preserves_colour_alpha_tone_and_valid_ramp(self):
        g=cgm.build_baseline(self.c);e=cgm.build_experiment(self.c,g)
        self.assertEqual(e.characters.ramp,self.c['ramp'])
        self.assertEqual(len(e.characters.glyph_coverage),len(self.c['ramp']))
        for before,after in zip(g,e.characters.cells):
            for b,a in zip(before,after):
                self.assertEqual((a.alpha,a.color,a.tone),(b['alpha'],b['color'],b['tone']))
                self.assertTrue(0<=a.index<len(self.c['ramp']))
                if self.c['ramp'][b['index']].isspace() or b['alpha']==0:self.assertEqual(a.index,b['index'])
                self.assertGreaterEqual(e.characters.glyph_coverage[a.index],e.characters.glyph_coverage[b['index']])

    def test_matte_is_bounded_and_composition_conserves_calibrated_ink(self):
        g=cgm.build_baseline(self.c);e=cgm.build_experiment(self.c,g);composed=e.compose()
        for y,row in enumerate(g):
            for x,old in enumerate(row):
                a=e.characters.cells[y][x];m=e.matte.coverage[y][x];c=composed[y][x]
                self.assertTrue(0<=m<=1)
                self.assertEqual(c['alpha'],a.alpha*m)
                self.assertEqual((c['index'],c['color'],c['tone']),(a.index,a.color,a.tone))
                self.assertAlmostEqual(old['alpha']*e.characters.glyph_coverage[old['index']],
                                       c['alpha']*e.characters.glyph_coverage[c['index']],places=14)
                if old['alpha']==0:self.assertEqual(m,0)
        # Character data remains independent and unchanged after composition.
        self.assertNotEqual(e.characters.as_grid(),composed)

    def test_invalid_matte_does_not_silently_clip(self):
        e=cgm.build_experiment(self.c)
        for value in [-.01,1.01,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):
                cgm.compose_ascii(e.characters,cgm.Matte(tuple(tuple(value for _ in row)for row in e.characters.cells)))
        with self.assertRaises(ValueError):cgm.compose_ascii(e.characters,cgm.Matte(((1.,),)))

    def test_matte_identity_and_zero_are_exact(self):
        e=cgm.build_experiment(self.c)
        identity=cgm.Matte(tuple(tuple(1. for _ in row)for row in e.characters.cells))
        zero=cgm.Matte(tuple(tuple(0. for _ in row)for row in e.characters.cells))
        self.assertEqual(cgm.compose_ascii(e.characters,identity),e.characters.as_grid())
        empty=exporter.render_foreground(self.c,cgm.compose_ascii(e.characters,zero))
        self.assertIsNone(empty.getchannel('A').getbbox())

    def test_svg_and_raster_dimensions_glyphs_and_single_artwork(self):
        e=cgm.build_experiment(self.c);g=e.compose();root=ET.fromstring(renderer.render_svg(self.c,g))
        self.assertEqual((int(root.get('width')),int(root.get('height'))),exporter.canvas_size(self.c))
        self.assertEqual(exporter.render_foreground(self.c,g).size,exporter.canvas_size(self.c))
        expected=[self.c['ramp'][c['index']]for row in g for c in row if c['alpha']>0 and not self.c['ramp'][c['index']].isspace()]
        self.assertEqual([s.text for s in root.findall('.//{*}tspan')],expected)
        for tag in ['mask','clipPath','use','image','animate','animateTransform']:
            self.assertFalse(root.findall('.//{*}'+tag))
        self.assertEqual(len(root.findall('{*}text')),sum(any(c['alpha']>0 and not self.c['ramp'][c['index']].isspace()for c in row)for row in g))
        character_image=exporter.render_foreground(self.c,e.characters.as_grid())
        final_image=exporter.render_foreground(self.c,g)
        self.assertIsNone(ImageChops.subtract(final_image.getchannel('A'),character_image.getchannel('A')).getbbox())

    def test_fully_transparent_and_faint_input_stays_empty_locally(self):
        for alpha in [0,1,15]:
            Image.new('RGBA',(10,10),(255,0,255,alpha)).save(self.source)
            e=cgm.build_experiment(self.c);grid=e.compose()
            self.assertTrue(all(c['alpha']==0 for row in grid for c in row))
            self.assertEqual(len(e.shapes.regions),1)
            self.assertIsNone(exporter.render_foreground(self.c,grid).getchannel('A').getbbox())

    def test_hidden_rgb_does_not_change_layers(self):
        image=Image.open(self.source).convert('RGBA');other=image.copy()
        other.putdata([(255,0,255,0) if a==0 else (r,g,b,a)for r,g,b,a in image.getdata()])
        a=cgm.build_experiment(self.c);other.save(self.source);b=cgm.build_experiment(self.c)
        self.assertEqual(a,b)

    def test_nonempty_baseline_is_exactly_production_for_all_colour_modes(self):
        for mode in sorted(renderer.VALID_MODES):
            c=dict(self.c,mode=mode)
            self.assertEqual(cgm.build_baseline(c),renderer.build_grid(c))
            e=cgm.build_experiment(c)
            self.assertEqual(len(e.compose()),c['rows'])

    def test_custom_ramp_and_small_extreme_rendering(self):
        for cols,rows in [(1,1),(1,90),(160,1),(3,2)]:
            for ramp in ['.@',' <&jW',' . @']:
                c=dict(self.c,cols=cols,rows=rows,ramp=ramp)
                e=cgm.build_experiment(c);g=e.compose()
                self.assertEqual((len(g[0]),len(g)),(cols,rows))
                self.assertEqual(exporter.render_foreground(c,g).size,exporter.canvas_size(c))
                ET.fromstring(renderer.render_svg(c,g))

    def test_invalid_dimensions_grid_and_animation_fail_explicitly(self):
        for changes in [dict(cols=0),dict(rows=-1),dict(cols=301),dict(cols=300,rows=200),
                        dict(cell_w=0),dict(cols=True),dict(animation='mosaic'),dict(ramp='   ')]:
            with self.assertRaises(ValueError):cgm.build_experiment(dict(self.c,**changes))
        g=cgm.build_baseline(self.c)
        with self.assertRaises(ValueError):cgm.build_experiment(self.c,g[:-1])
        g[0][0]['alpha']=float('nan')
        with self.assertRaises(ValueError):cgm.build_experiment(self.c,g)


if __name__=='__main__':
    unittest.main()
