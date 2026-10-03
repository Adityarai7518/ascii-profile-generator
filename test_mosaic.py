"""Mosaic ownership, shared geometry, artwork preservation and encoded output."""
import copy
from dataclasses import FrozenInstanceError
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

import animations as a
import ascii_renderer as r
import exporter as e


def config(cols=20, rows=10, **changes):
    return dict(dict(cols=cols, rows=rows, cell_w=8, cell_h=15,
                     ramp=' <&jW', animation='mosaic', speed='normal', loop='no',
                     foreground='#eeeeee', background=None, mode='original'), **changes)


def grid_for(c):
    return [[dict(index=(x + y) % len(c['ramp']), alpha=(0., .25, .65, 1.)[(x+2*y) % 4],
                  color=('#ca8345' if x % 2 else '#3596b2'), tone=(y+1)/(c['rows']+1))
             for x in range(c['cols'])] for y in range(c['rows'])]


class MosaicPlanTests(unittest.TestCase):
    def test_partition_ownership_at_all_sizes_and_extreme_aspects(self):
        sizes = [(1,1), (2,2), (3,2), (4,3), (5,5), (7,9), (80,40),
                 (120,64), (160,90), (200,120), (300,166), (250,200)]
        for cols, rows in sizes:
            for cw, ch in [(8,15), (3,40), (30,5)]:
                with self.subTest(size=(cols, rows), cells=(cw, ch)):
                    plan = a.mosaic_plan(config(cols, rows, cell_w=cw, cell_h=ch), [])
                    self.assertLessEqual(len(plan.tiles), 512)
                    owners = set()
                    area = 0
                    for tile in plan.tiles:
                        x0,y0,x1,y1 = tile.cells
                        self.assertTrue(0 <= x0 < x1 <= cols and 0 <= y0 < y1 <= rows)
                        cells = {(x,y) for y in range(y0,y1) for x in range(x0,x1)}
                        self.assertFalse(owners & cells)
                        owners.update(cells)
                        X0,Y0,X1,Y1 = tile.bounds
                        area += (X1-X0)*(Y1-Y0)
                        self.assertEqual(X0, 0 if x0 == 0 else 20+x0*cw)
                        self.assertEqual(Y0, 0 if y0 == 0 else 20+y0*ch)
                        self.assertEqual(X1, plan.width if x1 == cols else 20+x1*cw)
                        self.assertEqual(Y1, plan.height if y1 == rows else 20+y1*ch)
                    self.assertEqual(len(owners), cols*rows)
                    self.assertEqual(area, plan.width*plan.height)

    def test_expected_counts_and_versioned_digest_order(self):
        for dims, count in [((120,64),240), ((160,90),460), ((200,120),380),
                            ((300,166),420), ((250,200),425)]:
            c = config(*dims); plan = a.mosaic_plan(c, [])
            self.assertEqual(len(plan.tiles), count)
            keys = []
            for tile in plan.tiles:
                x0,y0,x1,y1 = tile.cells
                seed = f'mosaic-v1:{dims[0]}:{dims[1]}:8:15:{x0}:{y0}:{x1}:{y1}'
                keys.append((hashlib.sha256(seed.encode('ascii')).digest(), y0, x0))
            self.assertEqual(keys, sorted(keys))

    def test_plan_is_immutable_and_independent_of_artwork(self):
        c = config(); g = grid_for(c); frozen = copy.deepcopy(g)
        plan = a.mosaic_plan(c, g)
        self.assertEqual(plan, a.mosaic_plan(c, g))
        self.assertEqual(g, frozen)
        with self.assertRaises(FrozenInstanceError):
            plan.seconds = 1
        with self.assertRaises(FrozenInstanceError):
            plan.tiles[0].start = 1
        for changes in [dict(ramp='@'), dict(mode='multicolour', palette=['#00ff00']),
                        dict(src='/other/image', out='/other/output'), dict(speed='fast'),
                        dict(loop='yes')]:
            changed = a.mosaic_plan(dict(c, **changes), [])
            self.assertEqual(changed.tiles, plan.tiles)
        for row in g:
            for cell in row:
                cell.update(index=0, alpha=0, color='#000000', tone=0)
        self.assertEqual(a.mosaic_plan(c, g), plan)

    def test_python_hash_seed_does_not_change_plan(self):
        code = ('import animations, json; from dataclasses import asdict; '
                f'print(json.dumps(asdict(animations.mosaic_plan({config(7,9)!r}, [])), sort_keys=True))')
        outputs = [subprocess.check_output([sys.executable, '-c', code],
                   cwd=Path(__file__).parent,
                   env=dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE='1'))
                   for seed in ['1', '27', 'random']]
        self.assertEqual(len(set(outputs)), 1)

    def test_exact_envelope_and_timing(self):
        for speed, seconds, count in [('slow',9.,90), ('normal',5.5,55), ('fast',2.8,28)]:
            for loop in ['yes', 'no']:
                plan = a.mosaic_plan(config(speed=speed, loop=loop), [])
                self.assertEqual(plan.seconds, seconds)
                self.assertEqual(plan.progress(0), 0)
                self.assertEqual(plan.progress(1), 0 if loop == 'yes' else 1)
                if loop == 'yes':
                    for p in [.65, .7, .8]:
                        self.assertEqual(plan.progress(p), 1)
                positions, delays = a.gif_timeline('mosaic', speed, loop, plan)
                self.assertEqual(len(positions), count)
                self.assertEqual(sum(delays), int(seconds*1000))
                self.assertTrue(all(d >= 20 and d % 10 == 0 for d in delays))
                self.assertEqual(positions[-1] == 1, loop == 'no')

    def test_single_tile_and_center_expansion(self):
        plan = a.mosaic_plan(config(1,1), [])
        tile, = plan.tiles
        self.assertEqual((tile.start, tile.end), (0, .25))
        self.assertEqual(tile.rectangle(0)[2:], (0,0))
        self.assertEqual(tile.rectangle(.25), (0,0,plan.width,plan.height))
        for p in [.01, .1, .2]:
            x,y,w,h = tile.rectangle(p)
            self.assertEqual(x+w/2, plan.width/2)
            self.assertEqual(y+h/2, plan.height/2)

    def test_completion_guard_survives_browser_clock_truncation(self):
        # Chromium can report setCurrentTime(2.8) as 2.7999989986. The
        # completion bypass must remain open despite that clock conversion.
        from bisect import bisect_right
        for speed in ['slow','normal','fast']:
            for loop in ['no','yes']:
                plan = a.mosaic_plan(config(speed=speed,loop=loop),[])
                times,widths = plan.completion_keyframes()
                boundaries = [1] if loop=='no' else [.65,.80]
                for boundary in boundaries:
                    for error_seconds in [-1.1e-6,0,1.1e-6]:
                        p = min(1,boundary+error_seconds/plan.seconds)
                        self.assertEqual(widths[bisect_right(times,p)-1],plan.width)
                for p in [0,.3,.5] + ([.9,1] if loop=='yes' else []):
                    self.assertEqual(widths[bisect_right(times,p)-1],0)

    def test_keyframes_interpolate_the_same_geometry_as_sampling(self):
        for loop in ['no','yes']:
            plan = a.mosaic_plan(config(80,40,loop=loop), [])
            for tile in plan.tiles:
                times, rects = tile.keyframes(plan.repeat)
                self.assertEqual(tuple(sorted(set(times))), times)
                self.assertEqual((times[0],times[-1]), (0,1))
                for i in range(len(times)-1):
                    p = (times[i]+times[i+1])/2
                    expected = tile.rectangle(plan.progress(p))
                    for value, lo, hi in zip(expected,rects[i],rects[i+1]):
                        self.assertAlmostEqual(value, (lo+hi)/2, places=9)


class MosaicRenderingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.c = config(); self.grid = grid_for(self.c)
        self.fg = e.render_foreground(self.c, self.grid)

    def test_matte_preserves_rgb_and_applies_alpha_once(self):
        plan = a.mosaic_plan(self.c, self.grid)
        fg = Image.new('RGBA', self.fg.size, (63,127,199,128))
        original = fg.tobytes()
        out = e.apply_mosaic(fg, self.c, self.grid, .37)
        mask = e.mosaic_mask(fg.size, plan, .37)
        self.assertEqual(out.convert('RGB').tobytes(), fg.convert('RGB').tobytes())
        self.assertEqual(out.getchannel('A').tobytes(),
                         ImageChops.multiply(fg.getchannel('A'),mask).tobytes())
        self.assertIn(128, out.getchannel('A').getdata())
        self.assertEqual(fg.tobytes(), original)

    def test_exact_rgba_completion_and_hidden_endpoints(self):
        frozen = copy.deepcopy(self.grid)
        for loop in ['no','yes']:
            c = dict(self.c, loop=loop)
            complete = [1] if loop == 'no' else [.65,.7,.8]
            hidden = [0] if loop == 'no' else [0,1]
            for p in complete:
                self.assertEqual(e.apply_mosaic(self.fg,c,self.grid,p).tobytes(),self.fg.tobytes())
            for p in hidden:
                out = e.apply_mosaic(self.fg,c,self.grid,p)
                self.assertIsNone(out.getchannel('A').getbbox())
                self.assertEqual(out.convert('RGB').tobytes(),self.fg.convert('RGB').tobytes())
        self.assertEqual(self.grid, frozen)

    def test_mask_monotonicity_and_reverse_closure(self):
        plan = a.mosaic_plan(self.c,self.grid)
        loop = a.mosaic_plan(dict(self.c,loop='yes'),self.grid)
        previous = Image.new('L',self.fg.size)
        for i in range(21):
            q = i/20
            mask = e.mosaic_mask(self.fg.size,plan,q)
            self.assertIsNone(ImageChops.subtract(previous,mask).getbbox())
            self.assertEqual(mask.tobytes(), e.mosaic_mask(self.fg.size,loop,1-.2*q).tobytes())
            previous = mask

    def test_completed_tile_union_covers_padding_without_seams(self):
        # Exercise the union itself, independent of the completion shortcut.
        from PIL import ImageDraw
        for dims in [(7,9),(120,64),(250,200)]:
            plan = a.mosaic_plan(config(*dims),[])
            mask = Image.new('L',(plan.width,plan.height))
            draw = ImageDraw.Draw(mask)
            for tile in plan.tiles:
                x,y,w,h = tile.rectangle(1)
                draw.rectangle((x,y,x+w-1,y+h-1),fill=255)
            self.assertEqual(mask.getextrema(),(255,255))

    def test_svg_identity_resources_bounds_and_fallback(self):
        for dims in [(7,9),(120,64),(300,166),(250,200)]:
            for loop in ['no','yes']:
                c = config(*dims,loop=loop); g = grid_for(c); frozen = copy.deepcopy(g)
                root = ET.fromstring(r.render_svg(c,g))
                static = ET.fromstring(r.render_svg(dict(c,animation='instant'),g))
                glyphs = lambda node: [ET.tostring(t) for t in node.findall('.//{*}text')]
                self.assertEqual(glyphs(root),glyphs(static))
                self.assertEqual(root.attrib,static.attrib)
                self.assertEqual(g,frozen)
                plan = a.mosaic_plan(c,g); n = len(plan.tiles)
                self.assertEqual(len(list(root.iter()))-len(list(static.iter())),5*n+6)
                self.assertEqual(len(root.findall('.//{*}animate')),4*n+2)
                self.assertFalse(root.findall('.//{*}script'))
                self.assertFalse(root.findall('.//{*}use'))
                self.assertFalse(root.findall('.//{*}image'))
                clip, = root.findall('.//{*}clipPath')
                self.assertEqual(clip.get('clipPathUnits'),'userSpaceOnUse')
                art, = root.findall(".//{*}g[@id='artwork']")
                self.assertEqual(art.get('clip-path'),'none')
                bypass, = art.findall('{*}animate')
                self.assertEqual(bypass.get('attributeName'),'clip-path')
                self.assertEqual(bypass.get('calcMode'),'discrete')
                self.assertIn('url(#'+clip.get('id')+')',bypass.get('values'))
                guard = clip[-1]
                self.assertEqual((float(guard.get('width')),float(guard.get('height'))),
                                 (plan.width,plan.height))
                self.assertEqual(guard[0].get('calcMode'),'discrete')
                for node in root.findall('.//{*}animate'):
                    times = [float(t) for t in node.get('keyTimes').split(';')]
                    self.assertEqual(times,sorted(set(times)))
                    self.assertEqual((times[0],times[-1]),(0,1))
                    self.assertEqual(len(times),len(node.get('values').split(';')))
                    self.assertEqual(node.get('repeatCount')=='indefinite',loop=='yes')
                    if loop == 'no': self.assertEqual(node.get('fill'),'freeze')

    def test_all_colour_modes_backgrounds_and_custom_ramps(self):
        source = Image.new('RGBA',(60,40))
        source.putdata([(x*4,y*6,170,(0,64,128,255)[x%4]) for y in range(40) for x in range(60)])
        source.save(self.path/'source.png')
        for mode in ['original','light','dark','custom','multicolour']:
            for background in [None,'#ffffff','#080d15','#723355']:
                c = dict(self.c,src=str(self.path/'source.png'),mode=mode,background=background,
                         contrast=1.,brightness=1.,gamma=1.,palette=['#ffaa00','#00aaff'])
                g = r.build_grid(c); frozen = copy.deepcopy(g); fg = e.render_foreground(c,g)
                expected = e.flatten_background(fg,background or '#ffffff').convert('RGB')
                self.assertEqual(e.make_gif_frame(fg,background,1,'mosaic',c,g).tobytes(),expected.tobytes())
                empty = e.make_gif_frame(fg,background,0,'mosaic',c,g)
                self.assertEqual(empty.tobytes(),Image.new('RGB',fg.size,background or '#ffffff').tobytes())
                self.assertEqual(g,frozen)
        for ramp in [' .:@','<&jW',' \t<&jW',' .░▒▓█']:
            c = dict(self.c,ramp=ramp); g = grid_for(c)
            fg = e.render_foreground(c,g)
            self.assertEqual(e.apply_mosaic(fg,c,g,1).tobytes(),fg.tobytes())
            self.assertEqual(ET.fromstring(r.render_svg(c,g)).tag,'{http://www.w3.org/2000/svg}svg')

    def test_empty_ink_grid_and_fitted_foreground(self):
        g = grid_for(self.c)
        for row in g:
            for cell in row: cell['alpha'] = 0
        fg = e.render_foreground(self.c,g)
        for p in [0,.37,1]:
            self.assertIsNone(e.apply_mosaic(fg,self.c,g,p).getchannel('A').getbbox())
        c = config(120,64); g = grid_for(c)
        fitted = e.fit_image(e.render_foreground(c,g),640)
        self.assertEqual(max(fitted.size),640)
        self.assertEqual(e.apply_mosaic(fitted,c,g,1).tobytes(),fitted.tobytes())

    def test_decoded_gifs_match_every_sample_and_final_static(self):
        for speed in ['slow','normal','fast']:
            for loop in ['no','yes']:
                c = dict(self.c,speed=speed,loop=loop)
                path = self.path/f'{speed}-{loop}.gif'
                e.save_gif(self.fg,str(path),None,'mosaic',speed,loop,c,self.grid)
                positions,delays = a.gif_timeline('mosaic',speed,loop)
                with Image.open(path) as gif:
                    self.assertEqual(gif.info.get('loop'),0 if loop=='yes' else None)
                    self.assertGreater(gif.n_frames,1)
                    self.assertLessEqual(gif.n_frames,len(positions))
                    palette = gif.copy(); idx=0; remaining=gif.info['duration']
                    for p,delay in zip(positions,delays):
                        expected = e.make_gif_frame(self.fg,None,p,'mosaic',c,self.grid)
                        expected = expected.quantize(palette=palette,dither=Image.Dither.NONE).convert('RGB')
                        self.assertEqual(gif.convert('RGB').tobytes(),expected.tobytes())
                        self.assertEqual(gif.disposal_method,1)
                        remaining -= delay
                        if remaining == 0 and idx+1 < gif.n_frames:
                            idx+=1; gif.seek(idx); remaining=gif.info['duration']
                    self.assertEqual(remaining,0)
                    self.assertEqual(idx+1,gif.n_frames)
                    if loop=='no':
                        static = e.flatten_background(self.fg,'#ffffff').convert('RGB')
                        static = static.quantize(palette=palette,dither=Image.Dither.NONE).convert('RGB')
                        self.assertEqual(gif.convert('RGB').tobytes(),static.tobytes())

    def test_gif_bytes_deterministic(self):
        for loop in ['no','yes']:
            paths = [self.path/f'{loop}-{i}.gif' for i in range(2)]
            for path in paths:
                e.save_gif(self.fg,str(path),None,'mosaic','fast',loop,self.c,self.grid)
            self.assertEqual(paths[0].read_bytes(),paths[1].read_bytes())


if __name__ == '__main__':
    unittest.main()
