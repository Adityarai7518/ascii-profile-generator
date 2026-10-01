"""Cross-export animation invariants, not snapshots of implementation text."""

import contextlib
import io
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from PIL import Image, ImageChops

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
        for name in ["twinkle", "sparkle-wave", "breathing"]:
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
        for animation in ["instant", "fade", "flag-wave", "typewriter", "dissolve", "breathing"]:
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
        for animation in ["typewriter", "dissolve", "breathing"]:
            a = self.frame(animation, .37)
            self.assert_same(a, self.frame(animation, .37))
            frames.append(a.tobytes())
        self.assertEqual(len(set(frames)), 3)

    def test_new_cli_choices_keep_existing_numbers(self):
        self.assertEqual(cli.ANIMATIONS["7"][1], "twinkle")
        self.assertEqual(cli.ANIMATIONS["9"][1], "instant")
        for key, animation in [("10", "typewriter"), ("11", "dissolve"), ("12", "breathing")]:
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


if __name__ == "__main__":
    unittest.main()
