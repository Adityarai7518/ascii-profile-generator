"""Cross-export animation invariants, not snapshots of implementation text."""

import contextlib
import copy
import io
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from PIL import Image, ImageChops, ImageStat

import animations as timeline
import ascii_renderer as renderer
import ascii_generator as cli
import exporter


class AnimationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        source = Image.new("RGBA", (80, 40))
        source.putdata([(x * 3, y * 6, 170, 128 if x < 40 else 255)
                        for y in range(40) for x in range(80)])
        source.save(self.path / "source.png")
        self.c = dict(src=str(self.path / "source.png"), out=str(self.path / "out.svg"),
                      mode="original", cols=20, rows=10, cell_w=8, cell_h=8,
                      ramp=" .,:@", contrast=1., brightness=1., gamma=1.,
                      foreground="#ffffff", background=None, palette=["#ff0000", "#00ff00"],
                      animation="instant", speed="normal", loop="no")
        self.grid = renderer.build_grid(self.c)
        self.fg = exporter.render_foreground(self.c, self.grid)
        self.static = exporter.flatten_background(self.fg, "#ffffff").convert("RGB")

    def frame(self, animation, progress, **changes):
        c = dict(self.c, animation=animation, **changes)
        return exporter.make_gif_frame(self.fg, c["background"], progress, animation, c, self.grid)

    def assert_same(self, a, b):
        self.assertEqual(a.size, b.size)
        self.assertIsNone(ImageChops.difference(a, b).getbbox())

    def test_all_reveals_finish_at_static_and_begin_empty(self):
        for animation in timeline.REVEALS:
            with self.subTest(animation=animation):
                self.assert_same(self.frame(animation, 1), self.static)
                self.assert_same(self.frame(animation, 0), Image.new("RGB", self.fg.size, "white"))

    def test_looping_reveals_hold_complete_image_then_close(self):
        for animation in timeline.REVEALS:
            with self.subTest(animation=animation):
                self.assert_same(self.frame(animation, .7, loop="yes"), self.static)
                self.assert_same(self.frame(animation, 0, loop="yes"), self.frame(animation, 1, loop="yes"))

    def test_diagonal_reveal_is_monotonic(self):
        last = Image.new("L", self.fg.size)
        for n in range(21):
            mask = exporter.reveal_mask(self.fg.size, n / 20, "diagonal-reveal")
            self.assertIsNone(ImageChops.subtract(last, mask).getbbox())
            last = mask

    def test_twinkle_selects_actual_characters_including_custom_index_zero(self):
        grid = [[dict(index=0, alpha=.4, color="#fff000", tone=.3) for _ in range(20)] for _ in range(10)]
        cells = renderer.get_twinkle_cells(20, 10, grid, 1, ramp=".@")
        self.assertTrue(cells)
        self.assertTrue(all(cell["glyph_index"] == 0 for cell in cells))
        self.assertEqual(cells, renderer.get_twinkle_cells(20, 10, grid, 1, ramp=".@"))
        self.assertEqual(renderer.get_twinkle_cells(20, 10, grid, 1, ramp=" @"), [])

    def test_twinkle_has_motion_and_returns_to_static_in_dark(self):
        c = dict(self.c, mode="dark", animation="twinkle", background="#000000")
        g = renderer.build_grid(c)
        fg = exporter.render_foreground(c, g)
        start = exporter.make_gif_frame(fg, c["background"], 0, "twinkle", c, g)
        mid = exporter.make_gif_frame(fg, c["background"], .3, "twinkle", c, g)
        end = exporter.make_gif_frame(fg, c["background"], 1, "twinkle", c, g)
        self.assertIsNotNone(ImageChops.difference(start, mid).getbbox())
        self.assert_same(start, end)

    def test_ambient_effects_return_to_static_without_erasing_ink(self):
        for name in ["twinkle", "sparkle-wave"]:
            with self.subTest(animation=name):
                self.assert_same(self.frame(name, 0), self.static)
                self.assert_same(self.frame(name, 1), self.static)
                self.assertIsNotNone(ImageChops.difference(self.frame(name, .4), self.static).getbbox())

    def test_flag_does_not_square_alpha(self):
        fg = Image.new("RGBA", self.fg.size)
        # The hoist strip has zero displacement and should retain exact alpha.
        fg.paste((200, 100, 50, 128), (21, 25, 23, 40))
        out = exporter.apply_flag_wave(fg, .2, config=self.c)
        self.assertEqual(out.getpixel((21, 30)), (200, 100, 50, 128))

    def test_flag_cycle_is_periodic(self):
        self.assert_same(exporter.apply_flag_wave(self.fg, 0, config=self.c),
                         exporter.apply_flag_wave(self.fg, 1, config=self.c))

    def test_gif_ticks_have_exact_total_duration(self):
        for animation in timeline.VALID_ANIMATIONS - {"instant"}:
            for speed in renderer.VALID_SPEEDS:
                for loop in ["no", "yes"]:
                    positions, durations = timeline.gif_timeline(animation, speed, loop)
                    self.assertEqual(len(positions), len(durations))
                    self.assertEqual(sum(durations), round(1000 * timeline.duration(animation, speed)))
                    self.assertTrue(all(d >= 20 and d % 10 == 0 for d in durations))
                    self.assertLessEqual(max(durations) - min(durations), 10)

    def test_actual_gif_loop_metadata_and_instant(self):
        for animation in ["instant", "fade", "flag-wave", "typewriter", "dissolve"]:
            for loop in ["no", "yes"]:
                path = self.path / f"{animation}-{loop}.gif"
                exporter.save_gif(self.fg, str(path), None, animation, "fast", loop, self.c, self.grid)
                with Image.open(path) as gif:
                    if timeline.repeats(animation, loop):
                        self.assertEqual(gif.info.get("loop"), 0)
                    else:
                        self.assertNotIn("loop", gif.info)
                    if animation == "instant":
                        self.assertEqual(gif.n_frames, 1)
                    else:
                        durations = []
                        for i in range(gif.n_frames):
                            gif.seek(i)
                            durations.append(gif.info["duration"])
                            self.assertEqual(gif.disposal_method, 1)
                        self.assertEqual(sum(durations), round(timeline.duration(animation, "fast") * 1000))

    def test_decoded_reveal_final_matches_static_under_same_palette(self):
        for animation in timeline.REVEALS:
            path = self.path / f"{animation}.gif"
            exporter.save_gif(self.fg, str(path), None, animation, "fast", "no", self.c, self.grid)
            with Image.open(path) as gif:
                palette = gif.copy()
                gif.seek(gif.n_frames - 1)
                expected = self.static.quantize(palette=palette, dither=Image.Dither.NONE).convert("RGB")
                self.assert_same(gif.convert("RGB"), expected)

    def test_delta_encoded_frames_match_their_authoritative_frames(self):
        # Validate actual decoded deltas, including merged holds and loop closure.
        for animation in timeline.VALID_ANIMATIONS:
            with self.subTest(animation=animation):
                path = self.path / f"delta-{animation}.gif"
                config = dict(self.c, animation=animation, speed="fast", loop="yes")
                exporter.save_gif(self.fg, str(path), None, animation, "fast", "yes", config, self.grid)
                positions, durations = timeline.gif_timeline(animation, "fast", "yes")
                with Image.open(path) as gif:
                    palette = gif.copy()
                    encoded_index, remaining = 0, gif.info["duration"]
                    for progress, duration in zip(positions, durations):
                        expected = exporter.make_gif_frame(self.fg, None, progress, animation, config, self.grid)
                        expected = expected.quantize(palette=palette, dither=Image.Dither.NONE).convert("RGB")
                        self.assert_same(gif.convert("RGB"), expected)
                        remaining -= duration
                        if remaining == 0 and encoded_index + 1 < gif.n_frames:
                            encoded_index += 1
                            gif.seek(encoded_index)
                            remaining = gif.info["duration"]
                    self.assertEqual(remaining, 0)

    def test_grayscale_palette_roundtrip_does_not_add_untrained_colours(self):
        config = dict(self.c, mode="light", foreground="#111111")
        grid = renderer.build_grid(config)
        foreground = exporter.render_foreground(config, grid)
        path = self.path / "gray.gif"
        exporter.save_gif(foreground, str(path), None, "instant", "normal", "no", config, grid)
        with Image.open(path) as gif:
            static = exporter.flatten_background(foreground, "#ffffff").convert("RGB")
            expected = static.quantize(palette=gif.copy(), dither=Image.Dither.NONE).convert("RGB")
            self.assert_same(gif.convert("RGB"), expected)

    def test_every_svg_keeps_exactly_one_copy_of_each_glyph(self):
        expected = sorted((20 + x * 8, 20 + y * 8 + 8 * .78, self.c["ramp"][cell["index"]], cell["color"])
                          for y, row in enumerate(self.grid) for x, cell in enumerate(row)
                          if cell["alpha"] > 0 and not self.c["ramp"][cell["index"]].isspace())
        for name in timeline.VALID_ANIMATIONS:
            root = ET.fromstring(renderer.render_svg(dict(self.c, animation=name), self.grid))
            actual = sorted((float(span.get("x")), float(text.get("y")), span.text, span.get("fill"))
                            for text in root.findall(".//{*}text") for span in text.findall("{*}tspan"))
            self.assertEqual(len(actual), len(expected), name)
            for a, b in zip(actual, expected):
                self.assertAlmostEqual(a[0], b[0]); self.assertAlmostEqual(a[1], b[1])
                self.assertEqual(a[2:], b[2:])
            self.assertFalse(root.findall(".//{*}script"))

    def test_svg_timing_and_repeat_semantics(self):
        for animation in timeline.VALID_ANIMATIONS:
            for loop in ["no", "yes"]:
                root = ET.fromstring(renderer.render_svg(dict(self.c, animation=animation, loop=loop), self.grid))
                nodes = root.findall(".//{*}animate") + root.findall(".//{*}animateTransform")
                self.assertEqual(bool(nodes), animation != "instant")
                for node in nodes:
                    self.assertEqual(node.get("repeatCount") == "indefinite", timeline.repeats(animation, loop))
                    times = list(map(float, node.get("keyTimes").split(";")))
                    self.assertEqual(times, sorted(set(times)))
                    self.assertEqual((times[0], times[-1]), (0, 1))
                    self.assertEqual(len(times), len(node.get("values").split(";")))

    def test_new_animations_are_deterministic_and_distinct(self):
        frames = []
        for animation in ["typewriter", "dissolve"]:
            a = self.frame(animation, .37)
            self.assert_same(a, self.frame(animation, .37))
            frames.append(a.tobytes())
        self.assertEqual(len(set(frames)), 2)

    def test_new_cli_choices_keep_existing_numbers(self):
        self.assertEqual(cli.ANIMATIONS["7"][1], "twinkle")
        self.assertEqual(cli.ANIMATIONS["9"][1], "instant")
        self.assertEqual(timeline.VALID_ANIMATIONS, timeline.REVEALS | {"instant", "twinkle", "sparkle-wave", "flag-wave", "digital-rain", "tetris"})
        self.assertEqual(set(cli.ANIMATIONS), {str(i) for i in range(1, 15)})
        for key, animation in [("10", "typewriter"), ("11", "dissolve"), ("12", "digital-rain"), ("13", "tetris"), ("14", "mosaic")]:
            with patch.object(cli, "command_input", return_value=key), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.choose_animation(), animation)

    def test_hidden_rgb_invariance_with_default_contrast(self):
        a = Image.new("RGBA", (400, 200), (0, 0, 0, 0))
        b = Image.new("RGBA", (400, 200), (255, 255, 255, 0))
        tile = Image.open(self.c["src"]).resize((200, 200))
        a.paste(tile, (100, 0)); b.paste(tile, (100, 0))
        a.save(self.path / "a.png"); b.save(self.path / "b.png")
        ga = renderer.build_grid(dict(self.c, src=str(self.path / "a.png"), contrast=1.1))
        gb = renderer.build_grid(dict(self.c, src=str(self.path / "b.png"), contrast=1.1))
        self.assertEqual(ga, gb)

    def test_small_cells_use_same_font_size_as_svg(self):
        c = dict(self.c, cell_w=3, cell_h=5)
        with patch.object(exporter, "find_font", wraps=exporter.find_font) as find:
            exporter.render_foreground(c, self.grid)
        self.assertAlmostEqual(find.call_args.args[0], 4.3)
        root = ET.fromstring(renderer.render_svg(c, self.grid))
        self.assertAlmostEqual(float(root.get("font-size")), 4.3)


class SvgRowSerializationTests(unittest.TestCase):
    def test_removing_only_animations_restores_exact_static_tree(self):
        # Sparse rows, whitespace, escaped characters, alpha extremes and
        # fractional metrics must retain the golden static serialization.
        for name in ['twinkle', 'tetris']:
            for loop in ['no', 'yes']:
                c = dict(cols=9, rows=7, cell_w=7.12345, cell_h=11.23456,
                         ramp=' <&jW', animation=name, speed='fast', loop=loop,
                         background=None)
                grid = [[dict(index=(x+y) % 5, color='#69a4d1',
                              alpha=0. if y == 3 else [0., .123456789, .65, 1.][x % 4])
                         for x in range(c['cols'])] for y in range(c['rows'])]
                static = ET.fromstring(renderer.render_svg(dict(c, animation='instant'), grid))
                animated = ET.fromstring(renderer.render_svg(c, grid))
                self.assertEqual(len(animated.findall('.//{*}text')), len(static.findall('{*}text')))
                self.assertEqual(len(animated.findall('.//{*}tspan')), len(static.findall('.//{*}tspan')))
                for span in animated.findall('.//{*}tspan'):
                    for child in list(span):
                        self.assertEqual(child.tag.split('}')[-1], 'animate')
                        span.remove(child)
                self.assertEqual(ET.tostring(animated), ET.tostring(static))

    def test_empty_grid_does_not_create_animation_rows_or_artwork_copies(self):
        for name in ['twinkle', 'tetris']:
            c = dict(cols=3, rows=2, cell_w=8, cell_h=15, ramp=' @',
                     animation=name, speed='normal', loop='no', background=None)
            grid = [[dict(index=1, color='#ffffff', alpha=0.) for _ in range(3)] for _ in range(2)]
            root = ET.fromstring(renderer.render_svg(c, grid))
            self.assertEqual(list(root), [])


class TwinkleContractTests(unittest.TestCase):
    """Focused direction/identity checks; no colour × speed × loop matrix."""

    setUp = AnimationTests.setUp
    assert_same = AnimationTests.assert_same

    def plan(self, **changes):
        return timeline.opacity_plan(dict(self.c, animation="twinkle", **changes), self.grid)

    def test_svg_keeps_same_glyphs_and_only_animates_alpha_transfer(self):
        c = dict(self.c, animation="twinkle")
        frozen = copy.deepcopy(self.grid)
        static = ET.fromstring(renderer.render_svg(dict(c, animation="instant"), self.grid))
        root = ET.fromstring(renderer.render_svg(c, self.grid))
        def glyphs(svg):
            return sorted((t.get('y'), s.get('x'), s.text, s.get('fill'), s.get('opacity'))
                          for t in svg.findall('.//{*}text') for s in t.findall('{*}tspan'))
        self.assertEqual(glyphs(root), glyphs(static))
        self.assertEqual(len(root.findall('.//{*}text')), len(static.findall('.//{*}text')))
        self.assertEqual(len(root.findall('{*}text')), len(root.findall('.//{*}text')))
        self.assertFalse(root.findall('.//{*}filter'))
        ownership = {cell: target.envelope for target in self.plan().targets for cell in target.cells}
        seen = set()
        for text in root.findall('{*}text'):
            y = round((float(text.get('y')) - 20 - c['cell_h'] * .78) / c['cell_h'])
            for span in text:
                x = round((float(span.get('x')) - 20) / c['cell_w'])
                nodes = span.findall('{*}animate')
                if (x, y) not in ownership:
                    self.assertFalse(nodes)
                    continue
                seen.add((x, y))
                self.assertEqual(len(nodes), 1)
                anim = nodes[0]
                self.assertEqual(anim.get('attributeName'), 'opacity')
                envelope = ownership[x, y]
                alpha = self.grid[y][x]['alpha']
                values = list(map(float, anim.get('values').split(';')))
                times = list(map(float, anim.get('keyTimes').split(';')))
                for expected in envelope.times:
                    self.assertTrue(any(abs(actual - expected) < 1e-8 for actual in times))
                self.assertEqual((values[0], values[-1]), (float(span.get('opacity')),)*2)
                for value, t in zip(values, times):
                    self.assertAlmostEqual(value, alpha ** envelope.at(t), places=6)
                self.assertGreaterEqual(max(values), alpha)
        self.assertEqual(seen, set(ownership))
        self.assertEqual(len(root.findall('.//{*}animate')), len(ownership))
        for tag in ['set', 'script', 'use', 'image']:
            self.assertFalse(root.findall('.//{*}' + tag))
        self.assertEqual(self.grid, frozen)

    def test_svg_interpolates_gamma_not_linear_opacity_between_plan_keyframes(self):
        envelope = self.plan().targets[0].envelope
        for alpha in [1e-8, .01, .1, .35, .65, .85, .999999, 1.]:
            values, times, curves = renderer._svg_twinkle_opacity(alpha, envelope)
            values = list(map(float, values))
            curves = [tuple(map(float, segment.split())) for segment in curves.split(';')]
            self.assertEqual(len(curves), len(times)-1)
            self.assertEqual((values[0], values[-1]), (float(f'{alpha:.6f}'),)*2)
            for i, (x1, y1, x2, y2) in enumerate(curves):
                self.assertTrue(0 <= x1 <= x2 <= 1)
                self.assertTrue(0 <= y1 <= y2 <= 1)
                for t in [.1, .25, .5, .75, .9]:
                    fraction = 3*(1-t)**2*t*y1 + 3*(1-t)*t*t*y2 + t**3
                    actual = values[i] + (values[i+1]-values[i])*fraction
                    expected = alpha ** envelope.at(times[i]+(times[i+1]-times[i])*t)
                    self.assertLessEqual(abs(actual-expected), 6e-7)

    def test_peak_strengthens_same_ink_without_redrawing_or_changing_support(self):
        c = dict(self.c, animation='twinkle')
        frozen = copy.deepcopy(self.grid)
        original = self.fg.tobytes()
        alpha = self.fg.getchannel('A')
        support = alpha.point([0] + [255] * 255)
        with patch.object(renderer, 'build_grid', side_effect=AssertionError('Grid regenerated')), \
             patch.object(exporter, 'render_foreground', side_effect=AssertionError('Glyphs rerendered')), \
             patch.object(exporter.ImageDraw.ImageDraw, 'text', side_effect=AssertionError('Glyph redrawn')):
            for progress in [0, .15, .5, .85, 1]:
                result = exporter.apply_opacity_plan(self.fg, c, progress, self.grid)
                self.assert_same(result.convert('RGB'), self.fg.convert('RGB'))
                self.assert_same(result.getchannel('A').point([0] + [255] * 255), support)
                self.assertIsNone(ImageChops.subtract(alpha, result.getchannel('A')).getbbox(), 'Ink dimmed')
                if progress in [0, 1]:
                    self.assertEqual(result.tobytes(), original)
                else:
                    change = ImageChops.difference(alpha, result.getchannel('A'))
                    changed = sum(change.histogram()[1:])
                    self.assertGreater(changed, 0, 'Pulse is static')
                    self.assertLess(changed, .5 * sum(alpha.histogram()[1:]), 'Pulse is not localized')
        self.assertEqual(self.grid, frozen)
        self.assertEqual(self.fg.tobytes(), original)

    def test_pulse_increases_contrast_for_light_and_dark_ink(self):
        c = dict(self.c, animation='twinkle')
        for ink, background in [('white', 'black'), ('black', 'white')]:
            fg = Image.new('RGBA', self.fg.size, ink)
            fg.putalpha(self.fg.getchannel('A'))
            visible = exporter.apply_opacity_plan(fg, c, .5, self.grid)
            bg = Image.new('RGB', fg.size, background)
            before = exporter.flatten_background(fg, background).convert('RGB')
            after = exporter.flatten_background(visible, background).convert('RGB')
            normal = ImageChops.difference(before, bg)
            peak = ImageChops.difference(after, bg)
            self.assertIsNone(ImageChops.subtract(normal, peak).getbbox(), 'Pulse weakened visual contrast')
            self.assertGreater(sum(ImageStat.Stat(peak).sum), sum(ImageStat.Stat(normal).sum))

    def test_plan_preserves_ownership_determinism_and_empty_input(self):
        c = dict(self.c, animation='twinkle', ramp='.@')
        grid = [[dict(index=0, alpha=1., color='#123456') for _ in range(20)] for _ in range(10)]
        plan = timeline.opacity_plan(c, grid)
        self.assertEqual(plan, timeline.opacity_plan(c, grid))
        cells = {cell for t in plan.targets for cell in t.cells}
        self.assertTrue(cells)
        self.assertEqual(len(cells), sum(len(t.cells) for t in plan.targets))
        # The established 2x2 ownership function is still authoritative.
        expected = {(x,y) for y in range(10) for x in range(20) if timeline.twinkle_group(x,y)<12}
        self.assertEqual(cells, expected)
        for row in grid:
            for cell in row:
                cell['alpha'] = 0
        self.assertEqual(timeline.opacity_plan(c, grid).targets, ())

    def test_twinkle_timing_and_svg_loop_semantics(self):
        for speed, loop, seconds in [('slow','yes',9.), ('normal','no',5.5), ('fast','yes',2.8)]:
            c = dict(self.c, animation='twinkle', speed=speed, loop=loop)
            plan = timeline.opacity_plan(c, self.grid)
            self.assertEqual(plan.seconds, seconds)
            self.assertEqual(plan.repeat, loop=='yes')
            positions, delays = timeline.gif_timeline('twinkle', speed, loop, plan)
            self.assertEqual(sum(delays), seconds*1000)
            self.assertEqual(positions[0], 0)
            if loop=='no': self.assertEqual(positions[-1], 1)
            else: self.assertLess(positions[-1], 1)
            root = ET.fromstring(renderer.render_svg(c, self.grid))
            for node in root.findall('.//{*}animate'):
                self.assertEqual(float(node.get('dur')[:-1]), seconds)
                self.assertEqual(node.get('repeatCount'), 'indefinite' if loop=='yes' else None)
                if loop=='no': self.assertEqual(node.get('fill'), 'freeze')

    def test_v2_peak_is_strong_and_untargeted_pixels_are_identical(self):
        c = dict(self.c, animation='twinkle')
        plan = self.plan()
        target = plan.targets[0]
        peak = target.envelope.times[target.envelope.values.index(min(target.envelope.values))]
        groups = exporter.opacity_target_map(c, self.fg.size, plan)
        # Controlled half-opaque ink isolates transfer strength from the source.
        fg = self.fg.copy()
        fg.putalpha(fg.getchannel('A').point([0]+[96]*255))
        result = exporter.apply_opacity_plan(fg, c, peak, self.grid)
        self.assertEqual(result.convert('RGB').tobytes(), fg.convert('RGB').tobytes())
        for before, after, owner in zip(fg.getchannel('A').getdata(), result.getchannel('A').getdata(), groups.getdata()):
            if owner == 255:
                self.assertEqual(after, before)
            if owner == 0 and before:
                self.assertGreaterEqual(after, 210, 'Peak should strongly strengthen selected ink')

    def test_decoded_twinkle_gif_brightens_and_returns_to_static(self):
        # Two representative exports only; preserve the existing palette policy.
        c = dict(self.c, mode='light', foreground='#111111', background='#ffffff',
                 animation='twinkle', speed='normal')
        grid = renderer.build_grid(c)
        fg = exporter.render_foreground(c, grid)
        static = exporter.flatten_background(fg, c['background']).convert('RGB')
        for loop in ['yes', 'no']:
            path = self.path / ('twinkle-'+loop+'.gif')
            exporter.save_gif(fg, str(path), c['background'], 'twinkle', 'normal', loop, c, grid)
            with Image.open(path) as gif:
                palette = gif.copy()
                self.assertEqual(gif.info.get('loop'), 0 if loop=='yes' else None)
                frames, delays = [], []
                for i in range(gif.n_frames):
                    gif.seek(i); frames.append(gif.convert('RGB')); delays.append(gif.info['duration'])
            expected = static.quantize(palette=palette, dither=Image.Dither.NONE).convert('RGB')
            self.assert_same(frames[0], expected)
            if loop=='no': self.assert_same(frames[-1], expected)
            self.assertEqual(sum(delays), 5500)
            self.assertGreater(len({f.tobytes() for f in frames}), 10)
            bg = Image.new('RGB', static.size, frames[0].getpixel((0,0)))
            strengths = [sum(ImageStat.Stat(ImageChops.difference(f,bg)).sum) for f in frames]
            self.assertGreater(max(strengths), strengths[0]*1.02, 'Decoded pulse does not intensify ink')
            self.assertGreaterEqual(min(strengths), strengths[0]*.995, 'Decoded pulse dims ink')
            peak = frames[strengths.index(max(strengths))]
            change = ImageChops.difference(peak, frames[0]).convert('L')
            ink = ImageChops.difference(frames[0],bg).convert('L')
            self.assertGreater(sum(change.histogram()[9:]), .04*sum(ink.histogram()[9:]))
            self.assertLess(sum(change.histogram()[1:]), .5*sum(ink.histogram()[1:]))



class DigitalRainTests(unittest.TestCase):
    setUp = AnimationTests.setUp
    assert_same = AnimationTests.assert_same

    def test_layout_is_deterministic_sparse_and_ascii(self):
        c = dict(self.c, animation='digital-rain')
        streams = timeline.rain_streams(c, self.grid)
        self.assertEqual(streams, timeline.rain_streams(dict(c, speed='fast', loop='yes', out='other.svg'), self.grid))
        self.assertEqual(len({s.x for s in streams}), len(streams))
        self.assertLessEqual(len(streams), max(1,c['cols']//8))
        large = timeline.rain_streams(dict(c, cols=240), self.grid)
        self.assertGreater(len(large), len(streams))
        self.assertLessEqual(len(large),24)
        self.assertEqual({s.speed for s in large}, {1, 2})
        self.assertEqual(len(timeline.rain_streams(dict(c, cols=3000), self.grid)),24)
        self.assertGreater(len({s.phase for s in large}),1)
        self.assertGreater(len({s.travel for s in large}),1)
        self.assertGreater(len({len(s.glyphs) for s in large}),1)
        for stream in streams:
            self.assertTrue(20 <= stream.x <= 20+(c['cols']-1)*c['cell_w'])
            self.assertTrue(12 <= len(stream.glyphs) <= 25)
            self.assertEqual(tuple(sorted(stream.opacities, reverse=True)),stream.opacities)
            self.assertEqual(stream.opacities[0],1.)
            self.assertEqual(stream.opacities[1],.8)
            self.assertLess(stream.opacities[-1],.05)
            self.assertTrue(all(char in c['ramp'] and 33<=ord(char)<=126 for char in stream.glyphs))
        fallback = timeline.rain_streams(dict(c,ramp=' ░█'),self.grid)
        self.assertTrue(all(33<=ord(ch)<=126 for stream in fallback for ch in stream.glyphs))

    def test_shared_motion_is_downward_and_recycles_offscreen(self):
        c = dict(self.c, animation='digital-rain')
        height = exporter.canvas_size(c)[1]
        for stream in timeline.rain_streams(c,self.grid):
            times, positions = stream.keyframes()
            self.assertEqual(times,tuple(sorted(set(times))))
            self.assertGreater(positions[1],height+(len(stream.glyphs)-1)*c['cell_h'])
            self.assertLess(positions[2],0)
            self.assertAlmostEqual(positions[0],positions[-1])
            p = (times[1])/2
            self.assertGreater(stream.position(p+.001),stream.position(p))
            self.assertAlmostEqual(stream.position(p),positions[0]+p*stream.travel*stream.speed)
            for reset in range(2,len(times)-1,2):
                self.assertGreater(positions[reset-1],height+(len(stream.glyphs)-1)*c['cell_h'])
                self.assertLess(positions[reset],0)
            # Every visible linear segment is consumed equivalently by SVG
            # keyframes and GIF position sampling, including the faster streams.
            for i in range(0,len(times)-1,2):
                mid=(times[i]+times[i+1])/2
                self.assertAlmostEqual(stream.position(mid),(positions[i]+positions[i+1])/2)
        # A controlled stream proves actual raster movement, not just metadata.
        stream = timeline.RainStream(40,.25,200,30,('A',':','.'),(.42,.25,.15))
        c['_rain_streams']=(stream,)
        a = exporter.render_rain_layer(self.fg.size,c,self.grid,0)
        b = exporter.render_rain_layer(self.fg.size,c,self.grid,.1)
        self.assertEqual(a.getbbox()[0],b.getbbox()[0])
        self.assertGreater(b.getbbox()[1],a.getbbox()[1])
        self.assertIsNotNone(ImageChops.difference(a,b).getbbox())

    def test_svg_backdrop_is_bounded_and_artwork_is_unchanged(self):
        c = dict(self.c, animation='digital-rain',loop='yes')
        frozen = copy.deepcopy(self.grid)
        root=ET.fromstring(renderer.render_svg(c,self.grid))
        static=ET.fromstring(renderer.render_svg(dict(c,animation='instant'),self.grid))
        rain=root.find("{*}g[@id='digital-rain']")
        artwork=root.find("{*}g[@id='artwork']")
        self.assertLess(list(root).index(rain),list(root).index(artwork))
        self.assertEqual([ET.tostring(n) for n in artwork], [ET.tostring(n) for n in static if n.tag.endswith('text')])
        self.assertFalse(artwork.findall('.//{*}animateTransform'))
        streams=timeline.rain_streams(c,self.grid)
        self.assertEqual(len(rain.findall('{*}g')),len(streams))
        self.assertEqual(len(rain.findall('.//{*}animateTransform')),len(streams))
        self.assertLessEqual(len(rain.findall('.//{*}text')),24*25)
        clip=root.find(".//{*}clipPath[@id='rain-bounds']/{*}rect")
        self.assertEqual((float(clip.get('width')),float(clip.get('height'))),exporter.canvas_size(c))
        self.assertEqual(self.grid,frozen)

    def test_gif_composites_artwork_last_without_mutating_it(self):
        c=dict(self.c,animation='digital-rain')
        frozen=copy.deepcopy(self.grid); pixels=self.fg.tobytes()
        for progress in [0,.3,1]:
            rain=exporter.render_rain_layer(self.fg.size,c,self.grid,progress)
            expected=Image.alpha_composite(exporter.flatten_background(rain,'white').convert('RGBA'),self.fg).convert('RGB')
            actual=exporter.make_gif_frame(self.fg,None,progress,'digital-rain',c,self.grid)
            self.assert_same(expected,actual)
            self.assertEqual(actual.size,self.fg.size)
        self.assertEqual(self.grid,frozen); self.assertEqual(self.fg.tobytes(),pixels)
        # A fully opaque foreground must occlude every rain pixel.
        opaque=Image.new('RGBA',self.fg.size,(40,80,120,255))
        for progress in [0,.3]:
            self.assert_same(exporter.make_gif_frame(opaque,None,progress,'digital-rain',c,self.grid),opaque.convert('RGB'))

    def test_speed_and_loop_contract(self):
        for speed,loop,seconds in [('slow','yes',9),('normal','no',5.5),('fast','yes',2.8)]:
            c=dict(self.c,animation='digital-rain',speed=speed,loop=loop)
            root=ET.fromstring(renderer.render_svg(c,self.grid))
            for node in root.findall('.//{*}animateTransform'):
                self.assertEqual(float(node.get('dur')[:-1]),seconds)
                self.assertEqual(node.get('repeatCount'),'indefinite' if loop=='yes' else None)
                if loop=='no':self.assertEqual(node.get('fill'),'freeze')
            positions,delays=timeline.gif_timeline('digital-rain',speed,loop)
            self.assertEqual(sum(delays),seconds*1000)
            self.assertLessEqual(len(positions),90)
            self.assertEqual(positions[-1]==1,loop=='no')

    def test_decoded_gifs_contain_motion_and_correct_completion(self):
        c=dict(self.c,animation='digital-rain')
        for loop in ['yes','no']:
            path=self.path/('rain-'+loop+'.gif')
            exporter.save_gif(self.fg,str(path),None,'digital-rain','normal',loop,c,self.grid)
            with Image.open(path) as gif:
                self.assertEqual(gif.info.get('loop'),0 if loop=='yes' else None)
                frames=[];durations=[]
                for i in range(gif.n_frames):
                    gif.seek(i);frames.append(gif.convert('RGB'));durations.append(gif.info['duration'])
            self.assertGreater(len({f.tobytes() for f in frames}),20)
            self.assertEqual(sum(durations),5500)
            self.assertIsNotNone(ImageChops.difference(frames[0],frames[len(frames)//2]).getbbox())
            self.assertTrue(all(ImageChops.difference(a,b).getbbox() for a,b in zip(frames,frames[1:])))
            if loop=='no':self.assert_same(frames[0],frames[-1])


class TetrisTests(unittest.TestCase):
    setUp = AnimationTests.setUp
    assert_same = AnimationTests.assert_same

    def config(self, **changes):
        return dict(self.c, **dict(animation='tetris', **changes))

    def test_partition_is_stable_contiguous_and_covers_each_cell_once(self):
        c = self.config()
        frozen = copy.deepcopy(self.grid)
        plan = timeline.tetris_plan(c, self.grid)
        self.assertEqual(plan, timeline.tetris_plan(c, self.grid))
        faster = timeline.tetris_plan(dict(c, speed='fast'), self.grid)
        self.assertEqual(plan.pieces, faster.pieces)
        all_cells = []
        for piece in plan.pieces:
            self.assertTrue(1 <= len(piece.cells) <= 4)
            connected = {piece.cells[0]}
            while True:
                more = {cell for cell in piece.cells if any(abs(cell[0]-a)+abs(cell[1]-b)==1 for a,b in connected)}
                if more <= connected: break
                connected |= more
            self.assertEqual(connected, set(piece.cells))
            all_cells.extend(piece.cells)
            self.assertEqual(piece.offset(1), 0)
            self.assertLess(20+(max(y for _,y in piece.cells)+1)*c['cell_h']+piece.offset(0), 0)
            self.assertEqual(piece.times, tuple(sorted(set(piece.times))))
            self.assertTrue(all(a<=b for a,b in zip(piece.offsets,piece.offsets[1:])))
        self.assertEqual(sorted(all_cells), sorted((x,y) for y in range(c['rows']) for x in range(c['cols'])))
        self.assertEqual(len(all_cells), len(set(all_cells)))
        lower = [p.times[-2] for p in plan.pieces if min(y for _,y in p.cells)>=c['rows']//2]
        upper = [p.times[-2] for p in plan.pieces if max(y for _,y in p.cells)<c['rows']//2]
        self.assertLess(sum(lower)/len(lower), sum(upper)/len(upper))
        self.assertEqual(self.grid,frozen)

    def test_svg_uses_shared_vertical_trajectories_and_original_glyphs(self):
        c = self.config()
        plan = timeline.tetris_plan(c,self.grid)
        root=ET.fromstring(renderer.render_svg(c,self.grid))
        static=ET.fromstring(renderer.render_svg(dict(c,animation='instant'),self.grid))
        def glyphs(svg):
            return sorted((text.get('y'),span.get('x'),span.text,span.get('fill'),span.get('opacity'))
                          for text in svg.findall('.//{*}text') for span in text.findall('{*}tspan'))
        self.assertEqual(glyphs(root),glyphs(static))
        self.assertEqual(len(root.findall('.//{*}text')), len(static.findall('.//{*}text')))
        self.assertEqual(len(root.findall('{*}text')), len(root.findall('.//{*}text')))
        self.assertFalse(root.findall('.//{*}g'))
        self.assertFalse(root.findall('.//{*}animateTransform'))
        ownership = {cell: piece for piece in plan.pieces for cell in piece.cells}
        self.assertEqual(len(root.findall('.//{*}animate')), len(glyphs(static)))
        for text in root.findall('{*}text'):
            baseline = float(text.get('y'))
            y = round((baseline - 20 - c['cell_h'] * .78) / c['cell_h'])
            for span in text:
                x = round((float(span.get('x')) - 20) / c['cell_w'])
                piece = ownership[x, y]
                self.assertEqual(len(span), 1)
                node = span[0]
                self.assertEqual(node.get('attributeName'), 'y')
                times = list(map(float, node.get('keyTimes').split(';')))
                values = list(map(float, node.get('values').split(';')))
                self.assertEqual(len(times), len(piece.times))
                for t, w in zip(times, piece.times): self.assertAlmostEqual(t, w, places=8)
                for actual, dy in zip(values, piece.offsets):
                    self.assertAlmostEqual(actual, baseline + dy, places=5)
                self.assertEqual(values[-1], baseline)
                for i in range(len(times)-1):
                    midpoint = (piece.times[i]+piece.times[i+1])/2
                    self.assertAlmostEqual(piece.offset(midpoint),
                                           (values[i]+values[i+1])/2-baseline, places=5)

    def test_raster_patches_preserve_pixels_and_only_translate_y(self):
        c=self.config()
        plan=timeline.tetris_plan(c,self.grid)
        patches=exporter.tetris_patches(self.fg,c,plan)
        rebuilt=Image.new('RGBA',self.fg.size)
        for _,xy,patch_image in patches:
            rebuilt.alpha_composite(patch_image,xy)
        # Source-over may discard RGB under zero alpha. Compare coverage and
        # visible colour on both backgrounds; the endpoint below is byte exact.
        self.assertEqual(rebuilt.getchannel('A').tobytes(),self.fg.getchannel('A').tobytes())
        for background in ['white', 'black']:
            self.assertEqual(exporter.flatten_background(rebuilt,background).tobytes(),
                             exporter.flatten_background(self.fg,background).tobytes())
        original=self.fg.tobytes();frozen=copy.deepcopy(self.grid)
        self.assertIsNone(exporter.apply_tetris(self.fg,c,self.grid,0).getbbox())
        self.assertEqual(exporter.apply_tetris(self.fg,c,self.grid,1).tobytes(),original)
        piece,xy,patch_image=next(p for p in patches if p[0].times[1]>.1)
        # Isolate one rigid group and compare to its exact integer translation.
        config=dict(c,_tetris_plan=plan,_tetris_patches=((piece,xy,patch_image),))
        progress=piece.times[-2]-.01
        expected=Image.new('RGBA',self.fg.size)
        expected.alpha_composite(patch_image,(xy[0],xy[1]+round(piece.offset(progress))))
        self.assertEqual(exporter.apply_tetris(self.fg,config,self.grid,progress).tobytes(),expected.tobytes())
        self.assertEqual(self.fg.tobytes(),original);self.assertEqual(self.grid,frozen)

    def test_timing_loop_restart_and_exact_completion(self):
        for speed,loop,seconds in [('slow','yes',9.),('normal','no',5.5),('fast','yes',2.8)]:
            c=self.config(speed=speed,loop=loop)
            plan=timeline.tetris_plan(c,self.grid)
            self.assertEqual((plan.seconds,plan.repeat),(seconds,loop=='yes'))
            positions,delays=timeline.gif_timeline('tetris',speed,loop,plan)
            self.assertEqual(sum(delays),seconds*1000)
            self.assertEqual(positions[-1]==1,loop=='no')
            first=exporter.make_gif_frame(self.fg,None,0,'tetris',c,self.grid)
            self.assert_same(first,Image.new('RGB',self.fg.size,'white'))
            self.assert_same(exporter.make_gif_frame(self.fg,None,1,'tetris',c,self.grid),self.static)
            self.assert_same(first,exporter.make_gif_frame(self.fg,None,0,'tetris',c,self.grid))
            self.assertIsNotNone(ImageChops.difference(first,exporter.make_gif_frame(self.fg,None,.5,'tetris',c,self.grid)).getbbox())

    def test_decoded_tetris_final_equals_static_and_no_stale_pixels(self):
        c=self.config()
        path=self.path/'tetris.gif'
        exporter.save_gif(self.fg,str(path),None,'tetris','normal','no',c,self.grid)
        with Image.open(path) as gif:
            palette=gif.copy()
            self.assertNotIn('loop',gif.info)
            self.assertGreater(gif.n_frames,15)
            gif.seek(gif.n_frames-1)
            expected=self.static.quantize(palette=palette,dither=Image.Dither.NONE).convert('RGB')
            self.assert_same(gif.convert('RGB'),expected)
        # Existing delta-frame test also validates every decoded Tetris frame.


if __name__ == "__main__":
    unittest.main()
