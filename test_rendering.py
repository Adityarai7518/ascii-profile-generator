"""Rendering invariants; run with: python -m unittest -v test_rendering."""

import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from PIL import Image, ImageChops

import ascii_generator as cli
import ascii_renderer as renderer
import exporter


class RenderingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = dict(
            src=str(self.root / "source.png"), out=str(self.root / "out.svg"),
            mode="light", cols=40, rows=20, cell_w=8, cell_h=8,
            ramp=renderer.DEFAULT_RAMP, contrast=1.0, brightness=1.0,
            gamma=1.0, background=None, foreground="#111111",
            palette=["#ff0000", "#0000ff"], animation="instant",
            speed="normal", loop="no",
        )

    def grid(self, image, **settings):
        image.save(self.config["src"])
        return renderer.build_grid(dict(self.config, **settings))

    def gradient(self):
        image = Image.new("RGBA", (40, 20))
        image.putdata([(20 + x * 5,) * 3 + (255,) for y in range(20) for x in range(40)])
        return image

    def svg(self, grid):
        with patch.object(renderer, "parse_args", return_value=self.config), \
                patch.object(renderer, "build_grid", return_value=grid), \
                contextlib.redirect_stdout(io.StringIO()):
            renderer.main()
        return ET.parse(self.config["out"]).getroot()

    def test_quantizer_preserves_positive_support_and_order(self):
        for ramp in [renderer.DEFAULT_RAMP, " .@", "   .:@", " ."]:
            indices = [renderer.density_to_index(n / 10000, ramp) for n in range(10001)]
            self.assertEqual(indices, sorted(indices))
            self.assertEqual(indices[0], 0)
            self.assertTrue(all(not ramp[i].isspace() for i in indices[1:]))
            self.assertEqual(indices[-1], len(ramp) - 1)

    def test_normalization_cannot_erase_nonzero_source_tone(self):
        self.assertEqual(renderer.density_to_index(0, " .:@", .02), 1)
        self.assertEqual(renderer.density_to_index(0, " .:@", 0), 0)

    def test_custom_ramp_without_leading_space_and_internal_space(self):
        self.assertEqual(renderer.density_to_index(0, ".:@"), 0)
        self.assertEqual(renderer.density_to_index(.5, ". @"), 1)
        self.assertEqual(renderer.density_to_index(0, "  .@", .1), 2)

    def test_previously_representable_levels_are_unchanged(self):
        ramp = renderer.DEFAULT_RAMP
        for i in range(1, len(ramp)):
            self.assertEqual(renderer.density_to_index(i / (len(ramp) - 1), ramp), i)

    def test_sample_missing_forehead_cell_has_sparse_ink(self):
        config = dict(self.config, src=str(Path(__file__).parent / "sample.png"),
                      cols=120, rows=64, cell_w=8, cell_h=15, contrast=1.1)
        grid = renderer.build_grid(config)
        self.assertEqual(config["ramp"][grid[11][54]["index"]], ".")
        self.assertEqual(grid[11][54]["alpha"], 1.0)

    def test_clipped_bright_plateau_keeps_source_support(self):
        image = self.gradient()
        for y in range(8, 12):
            for x in range(18, 22):
                image.putpixel((x, y), (250, 250, 250, 255))
        grid = self.grid(image)
        self.assertEqual(grid[9][19]["tone"], 1.0)
        self.assertEqual(self.config["ramp"][grid[9][19]["index"]], ".")

    def test_clipped_shadow_plateau_keeps_source_support(self):
        image = self.gradient()
        for y in range(8, 12):
            for x in range(18, 22):
                image.putpixel((x, y), (2, 2, 2, 255))
        grid = self.grid(image, mode="dark")
        self.assertEqual(grid[9][19]["tone"], 0.0)
        self.assertEqual(self.config["ramp"][grid[9][19]["index"]], ".")

    def test_genuine_zero_tone_is_not_filled(self):
        for mode, color in [("light", "white"), ("dark", "black")]:
            grid = self.grid(Image.new("RGBA", (40, 20), color), mode=mode)
            self.assertTrue(all(cell["index"] == 0 for row in grid for cell in row))

    def test_transparent_cells_stay_empty_even_without_space_in_ramp(self):
        image = self.gradient()
        for y in range(20):
            for x in range(10):
                image.putpixel((x, y), (255, 0, 255, 0))
        grid = self.grid(image, ramp=".@")
        config = dict(self.config, ramp=".@")
        foreground = exporter.render_foreground(config, grid)
        for y in range(20):
            for x in range(10):
                self.assertEqual(grid[y][x]["alpha"], 0.0)
        self.assertIsNone(foreground.getchannel("A").crop((0, 0, 95, 200)).getbbox())

    def test_light_background_does_not_change_grid(self):
        image = self.gradient()
        self.assertEqual(self.grid(image, background=None),
                         self.grid(image, background="#ffffff"))

    def test_palette_changes_only_color(self):
        image = self.gradient()
        for background in [None, "#ffffff", "#000000"]:
            a = self.grid(image, mode="multicolour", background=background)
            b = self.grid(image, mode="multicolour", background=background,
                          palette=["#005500", "#ffff00", "#cc00ff"])
            self.assertTrue(any(x["color"] != y["color"] for ar, br in zip(a, b) for x, y in zip(ar, br)))
            for ar, br in zip(a, b):
                for x, y in zip(ar, br):
                    self.assertEqual({k: x[k] for k in ("index", "alpha", "tone")},
                                     {k: y[k] for k in ("index", "alpha", "tone")})

    def test_multicolour_preserves_alpha_and_light_structure(self):
        image = self.gradient()
        image.putalpha(64)
        a = self.grid(image, mode="light")
        b = self.grid(image, mode="multicolour")
        for ar, br in zip(a, b):
            for x, y in zip(ar, br):
                self.assertEqual(x["index"], y["index"])
                self.assertEqual(x["alpha"], y["alpha"])
                self.assertAlmostEqual(y["alpha"], 64 / 255)

    def test_hidden_rgb_does_not_leak_through_premultiplied_resize(self):
        a = Image.new("RGBA", (400, 200), (0, 0, 0, 0))
        b = Image.new("RGBA", (400, 200), (255, 0, 255, 0))
        tile = self.gradient().resize((200, 200))
        a.paste(tile, (100, 0)); b.paste(tile, (100, 0))
        self.assertEqual(self.grid(a, mode="original"), self.grid(b, mode="original"))

    def test_valid_faint_ink_survives_svg_and_raster(self):
        image = self.gradient()
        grid = self.grid(image)
        for row in grid:
            for cell in row:
                cell.update(alpha=0, index=0)
        grid[5][5].update(alpha=.04, index=len(self.config["ramp"]) - 1)
        root = self.svg(grid)
        spans = root.findall(".//{*}tspan")
        self.assertEqual(len(spans), 1)
        self.assertAlmostEqual(float(spans[0].get("opacity")), .04)
        self.assertIsNotNone(exporter.render_foreground(self.config, grid).getbbox())
        self.assertTrue(renderer.get_twinkle_cells(40, 20, grid, len(self.config["ramp"]) - 1))

    def test_svg_and_pillow_consume_the_same_glyph_sequence(self):
        grid = self.grid(self.gradient())
        expected = [self.config["ramp"][c["index"]] for row in grid for c in row
                    if c["alpha"] > 0 and self.config["ramp"][c["index"]] != " "]
        root = self.svg(grid)
        self.assertEqual([n.text for n in root.findall(".//{*}tspan")], expected)
        with patch.object(exporter.ImageDraw.ImageDraw, "text") as draw:
            exporter.render_foreground(self.config, grid)
        self.assertEqual([call.args[1] for call in draw.call_args_list], expected)

    def test_png_retains_alpha_and_jpeg_flattens(self):
        grid = self.grid(self.gradient())
        fg = exporter.render_foreground(self.config, grid)
        exporter.save_png(fg, str(self.root / "out.png"), None, None)
        exporter.save_jpeg(fg, str(self.root / "out.jpg"), None, None)
        with Image.open(self.root / "out.png") as png:
            self.assertIsNone(ImageChops.difference(png.getchannel("A"), fg.getchannel("A")).getbbox())
        with Image.open(self.root / "out.jpg") as jpg:
            self.assertEqual(jpg.mode, "RGB")

    def test_cli_back_sentinels_and_instant_skips(self):
        stages = [("dimensions", lambda: cli.BACK)]
        self.assertIs(cli.run_stages(stages, {}, cli.BACK_TO_FLAG_THEME), cli.BACK_TO_FLAG_THEME)
        self.assertTrue(cli.stage_is_skipped([("speed", None)], 0, {"animation": "instant"}))
        self.assertIsNot(cli.BACK, cli.SKIP)
        self.assertIsNot(cli.ADDITIONAL, cli.BACK_TO_FLAG_THEME)

    def test_github_preset_defaults(self):
        with patch.object(cli, "command_input", return_value=""), \
                patch.object(cli, "generate") as generate, \
                contextlib.redirect_stdout(io.StringIO()):
            cli.run_preset("source.png")
        values = generate.call_args.args[1]
        self.assertEqual(values["dimensions"], (100, 50))
        self.assertEqual(values["animation"], "twinkle")
        self.assertEqual(values["loop"], "yes")
        self.assertEqual(values["color"]["mode"], "original")
        self.assertIsNone(values["color"]["background"])
        self.assertEqual(values["output_format"], "svg")


if __name__ == "__main__":
    unittest.main()
