"""Adaptive Tetris bounds and ambient edge cases; no source processing changes."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

from PIL import Image, ImageChops
import animations as plans
import ascii_renderer as svg
import exporter


def config(cols, rows, **changes):
    return dict(dict(cols=cols, rows=rows, cell_w=8, cell_h=15, ramp=' .:AX',
                     animation='tetris', speed='normal', loop='no',
                     mode='dark', foreground='#ffffff', background='#080d15'), **changes)


def grid_for(c, sparse=False):
    return [[dict(index=1+(x+y)% (len(c['ramp'])-1),
                  alpha=0. if sparse and (x+3*y)%7 else .65,
                  color=('#e1ad79' if (x+y)%2 else '#73a8cc'))
             for x in range(c['cols'])] for y in range(c['rows'])]


class TetrisScalabilityTests(unittest.TestCase):
    def test_exact_ownership_and_trajectory_for_tiny_odd_and_legal_limits(self):
        for cols,rows in [(1,1),(2,2),(3,2),(4,3),(5,5),(7,9),(120,64),
                          (160,90),(200,120),(300,166),(250,200)]:
            with self.subTest(dimensions=(cols,rows)):
                c=config(cols,rows);g=grid_for(c)
                plan=plans.tetris_plan(c,g)
                self.assertEqual(plan,plans.tetris_plan(c,g))
                cells=[cell for piece in plan.pieces for cell in piece.cells]
                self.assertEqual(len(cells),cols*rows)
                self.assertEqual(set(cells),{(x,y) for y in range(rows) for x in range(cols)})
                self.assertLessEqual(len(plan.pieces),plans.TETRIS_MAX_PIECES)
                for piece in plan.pieces:
                    self.assertTrue(piece.cells)
                    self.assertEqual(piece.offset(1),0.)
                    self.assertEqual(tuple(sorted(set(piece.times))),piece.times)
                    self.assertLess(piece.times[-2],1.)
                    self.assertLess(20+(max(y for _,y in piece.cells)+1)*15+piece.offset(0),0)
                    reachable={piece.cells[0]};pending=set(piece.cells)-reachable
                    while pending:
                        adjacent={p for p in pending if any((p[0]+dx,p[1]+dy) in reachable
                                                           for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)])}
                        self.assertTrue(adjacent,'Clipped formation disconnected')
                        reachable.update(adjacent);pending-=adjacent

    def test_normal_plans_match_pre_scaling_baseline_exactly(self):
        # Recorded from the stable implementation before this stabilization.
        expected={(80,40):'71ac6a531ec54760ec8c19412eb5ed5e0e5594dcd4213cd96cd1a947c0f75234',
                  (120,64):'42c81b5807e619d7472eda0fcb2aee697b4e0f407e381e05cc674ffa13e9eeb5',
                  (160,90):'c7a73298cf0699c68f2a3dccda4ba07d35d19cbe86152f41688b95e05cfb4d43'}
        for dimensions,digest in expected.items():
            self.assertEqual(hashlib.sha256(repr(plans.tetris_plan(config(*dimensions),[]).pieces).encode()).hexdigest(),digest)

    def test_large_formations_keep_nonrectangular_shapes_with_bounded_count(self):
        for cols,rows in [(200,120),(300,166),(250,200)]:
            pieces=plans.tetris_plan(config(cols,rows),[]).pieces
            self.assertLess(len(pieces),cols*rows//6)
            self.assertLessEqual(len(pieces),plans.TETRIS_MAX_PIECES)
            self.assertTrue(any(len(p.cells)==16 for p in pieces))
            self.assertTrue(any(len(p.cells)==12 and
                                (max(x for x,_ in p.cells)-min(x for x,_ in p.cells)+1)*
                                (max(y for _,y in p.cells)-min(y for _,y in p.cells)+1)>12
                                for p in pieces),'Scaled L formations disappeared')

    def test_maximum_svg_is_bounded_and_preserves_each_original_glyph(self):
        c=config(300,166,ramp=' <&A');g=grid_for(c)
        frozen=copy.deepcopy(g)
        root=ET.fromstring(svg.render_svg(c,g))
        static=ET.fromstring(svg.render_svg(dict(c,animation='instant'),g))
        def glyphs(root):
            return sorted((text.get('y'),s.get('x'),s.text,s.get('fill'),s.get('opacity'))
                          for text in root.findall('.//{*}text') for s in text.findall('{*}tspan'))
        self.assertEqual(glyphs(root),glyphs(static))
        nodes=root.findall('.//{*}animate')
        # One positional animation per existing glyph; the shared piece plan
        # remains capped independently (tested above), with no repeated art.
        self.assertEqual(len(nodes),len(glyphs(static)))
        self.assertLessEqual(len(nodes),c['cols']*c['rows'])
        self.assertEqual(len(root.findall('{*}text')),c['rows'])
        self.assertEqual(len(root.findall('.//{*}text')),c['rows'])
        self.assertFalse(root.findall('.//{*}script'))
        self.assertEqual(g,frozen)
        for text in root.findall('{*}text'):
            for node in text.findall('.//{*}animate'):
                self.assertEqual(node.get('attributeName'),'y')
                self.assertEqual(float(node.get('values').split(';')[-1]),float(text.get('y')))
                self.assertEqual(node.get('fill'),'freeze')

    def test_completion_is_byte_exact_across_coverage_modes_and_dimensions(self):
        cases=[(1,1,'dark',None,False),(7,9,'light','#ffffff',True),
               (120,64,'original',None,True),(200,120,'multicolour','#101820',False),
               (300,166,'dark','#080d15',True)]
        for cols,rows,mode,bg,sparse in cases:
            c=config(cols,rows,mode=mode,background=bg,ramp=' .<&@')
            g=grid_for(c,sparse);frozen=copy.deepcopy(g)
            foreground=exporter.fit_image(exporter.render_foreground(c,g),640)
            before=foreground.tobytes()
            result=exporter.apply_tetris(foreground,c,g,1)
            self.assertEqual(result.tobytes(),before)
            self.assertIsNone(exporter.apply_tetris(foreground,c,g,0).getbbox())
            self.assertEqual(g,frozen);self.assertEqual(foreground.tobytes(),before)
        c=config(2,2);g=grid_for(c)
        for row in g:
            for cell in row:cell['alpha']=0.
        fg=exporter.render_foreground(c,g)
        for p in [0,.5,1]:self.assertIsNone(exporter.apply_tetris(fg,c,g,p).getbbox())

    def test_scaled_timing_and_svg_repeat_contract_for_every_speed(self):
        c=config(200,120);g=grid_for(c,True)
        baseline=plans.tetris_plan(c,g).pieces
        for speed,seconds in [('slow',9.),('normal',5.5),('fast',2.8)]:
            for loop in ['yes','no']:
                actual=dict(c,speed=speed,loop=loop)
                plan=plans.tetris_plan(actual,g)
                self.assertEqual(plan.pieces,baseline)
                self.assertEqual((plan.seconds,plan.repeat),(seconds,loop=='yes'))
                positions,delays=plans.gif_timeline('tetris',speed,loop,plan)
                self.assertEqual(sum(delays),round(seconds*1000))
                self.assertEqual(positions[-1]==1,loop=='no')
                root=ET.fromstring(svg.render_svg(actual,g))
                for node in root.findall('.//{*}animate'):
                    self.assertEqual(node.get('dur'),f'{seconds:.3f}s')
                    self.assertEqual(node.get('repeatCount'),'indefinite' if loop=='yes' else None)
                    if loop=='no':self.assertEqual(node.get('fill'),'freeze')

    def test_scaled_gif_is_deterministic_and_decoded_frames_have_no_residue(self):
        c=config(200,120);g=grid_for(c,True)
        fg=exporter.fit_image(exporter.render_foreground(c,g),160)
        c['_tetris_plan']=plan=plans.tetris_plan(c,g)
        c['_tetris_patches']=exporter.tetris_patches(fg,c,plan)
        with tempfile.TemporaryDirectory() as directory:
            for loop in ['no','yes']:
                path=Path(directory)/f'{loop}.gif'
                exporter.save_gif(fg,str(path),c['background'],'tetris','fast',loop,c,g)
                duplicate=Path(directory)/f'{loop}-repeat.gif'
                exporter.save_gif(fg,str(duplicate),c['background'],'tetris','fast',loop,c,g)
                self.assertEqual(path.read_bytes(),duplicate.read_bytes())
                positions,delays=plans.gif_timeline('tetris','fast',loop)
                with Image.open(path) as gif:
                    palette=gif.copy();index=0;remaining=gif.info['duration']
                    self.assertEqual(gif.info.get('loop'),0 if loop=='yes' else None)
                    for p,delay in zip(positions,delays):
                        expected=exporter.make_gif_frame(fg,c['background'],p,'tetris',c,g)
                        expected=expected.quantize(palette=palette,dither=Image.Dither.NONE).convert('RGB')
                        self.assertIsNone(ImageChops.difference(gif.convert('RGB'),expected).getbbox())
                        remaining-=delay
                        if remaining==0 and index+1<gif.n_frames:
                            index+=1;gif.seek(index);remaining=gif.info['duration']
                    self.assertEqual(remaining,0)
                    static=exporter.flatten_background(fg,c['background']).convert('RGB')
                    static=static.quantize(palette=palette,dither=Image.Dither.NONE).convert('RGB')
                    self.assertIsNone(ImageChops.difference(gif.convert('RGB'),static).getbbox())

    def test_rain_tiny_portrait_wide_and_unusual_ramps_keep_periodic_backdrop(self):
        for cols,rows,ramp,bg in [(1,1,' ░█',None),(5,19,' <&A','#ffffff'),
                                  (100,10,' .:@','#080d15'),(20,50,' .X',None)]:
            c=config(cols,rows,animation='digital-rain',ramp=ramp,background=bg)
            g=grid_for(c,True);frozen=copy.deepcopy(g)
            streams=plans.rain_streams(c,g)
            self.assertEqual(streams,plans.rain_streams(c,g));self.assertLessEqual(len(streams),24)
            root=ET.fromstring(svg.render_svg(c,g))
            art=root.find("{*}g[@id='artwork']")
            static=ET.fromstring(svg.render_svg(dict(c,animation='instant'),g))
            self.assertEqual([ET.tostring(n) for n in art],[ET.tostring(n) for n in static if n.tag.endswith('text')])
            fg=exporter.render_foreground(c,g)
            for stream in streams:
                self.assertTrue(20<=stream.x<=20+(cols-1)*8)
                self.assertAlmostEqual(stream.position(0),stream.position(1))
                self.assertTrue(all(33<=ord(ch)<=126 for ch in stream.glyphs))
            first=exporter.make_gif_frame(fg,bg,0,'digital-rain',c,g)
            last=exporter.make_gif_frame(fg,bg,1,'digital-rain',c,g)
            self.assertEqual(first.tobytes(),last.tobytes());self.assertEqual(g,frozen)


if __name__=='__main__':
    unittest.main()
