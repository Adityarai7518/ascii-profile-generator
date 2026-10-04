# Character + Grid Shapes + Matte: isolated experiment v1

This is a static image-generation experiment on `feature/ascii-character-grid-matte`, based on `2650358`. It has no connection to Mosaic animation #14 and does not change the default renderer, CLI, website, exports or animation plans.

## Baseline inspected before implementation

`ascii_renderer.build_grid` loads and EXIF-transposes the image, center-crops to the cell aspect ratio, applies brightness and alpha-weighted contrast, resizes premultiplied colour/luminance and source alpha with Lanczos, normalizes visible luminance with percentiles, applies the existing S curve/gamma, and mixes tone (86%) with local contrast (14%). The existing ramp quantizer preserves faint positive support. Mode-dependent colour and alpha produce the authoritative `index/alpha/color/tone` grid.

`ascii_renderer.render_svg` and `exporter.render_foreground` consume that grid using the same cell metrics and baselines. SVG emits one text row with explicitly positioned glyphs. Pillow renders glyph ink to RGBA; PNG preserves coverage, JPEG flattens it, and GIF applies separate animation plans. Animation geometry, especially `animations.mosaic_plan`, is outside this experiment.

## Predeclared first version and hypothesis

Hypothesis: spatially coherent glyph choices can reduce distracting character variation while a separate matte preserves the baseline's local ink demand. This is a test of glyph organization and coverage, not a claim that more segmentation automatically improves recognition.

1. **Grid Shapes:** deterministically partition the baseline density/alpha fields into non-overlapping rectangles. Prefix-sum statistics choose the axis-aligned cut with greatest variance reduction. A fixed residual-variation threshold, depth bound and 1,024-region budget bound work. Cuts depend on image structure, not animation geometry. Every cell, including negative space, has one owner.
2. **Character:** reuse the exact baseline ramp, colour, baseline alpha (including its mode-dependent tone factor) and tone. Measure each ramp glyph's ink coverage through the existing Pillow renderer at the configured metrics. Within a shape, choose the glyph whose coverage is the region's 90th percentile. Use it only where it has at least as much ink as the original glyph; denser cells retain their original glyph. Blank cells remain blank. This makes quiet regions more coherent without forcing strong details into a weaker character.
3. **Matte:** independently record `baseline_glyph_coverage / chosen_glyph_coverage`, clamped to [0,1], for visible glyphs. Blank/transparent cells have zero contribution. The matte attenuates only existing glyph alpha; it cannot add colour, ink outside glyphs, rectangles, or a second artwork.
4. **Composition:** copy the character layer and multiply each glyph's original alpha by matte coverage, then pass the resulting grid to the unchanged SVG/Pillow exporters. Uniform per-glyph coverage avoids clipping accents and seams at cell boundaries. The uncomposited character layer, shape ownership and matte remain separately inspectable.

This preserves each cell's calibrated integrated ink demand before output quantization. It deliberately does not sharpen, denoise or retone the source, and does not classify faces or objects. The calibration uses local font rendering; it is not a claim of pixel equality across fonts or browser engines.

## Evaluation, fixed before viewing outputs

Generate eight source categories with identical A/B configuration: stylized face from the existing sample, a controlled product/object scene, a controlled landscape, high contrast, low contrast, flat regions, fine detail, and transparency. Use locally generated deterministic fixtures; do not download images. Include monochrome comparisons and selected colour/transparency variants. Inspect source, A, B, character-only, shape ownership and matte. Check silhouettes, facial/object cues, negative space, edge continuity, readable glyphs, tonal hierarchy, noise, blockiness, halos and seams. Calibration/structure metrics support visual review but cannot establish recognition quality.

Run the existing suite plus focused experimental tests. Benchmark 120×64, 160×90, 200×120 and 300×166. Record actual output sizes and elapsed generation times. Make one decision: PROMISING, INCONCLUSIVE, or NOT WORTH INTEGRATING. Fix correctness defects only; do not tune repeated visual variants.

The completed first-version decision is **NOT WORTH INTEGRATING**. See [RESULTS.md](RESULTS.md) for visual observations, measurements and limitations. No production file was edited.

## Run explicitly

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m experimental.compare --output /private/tmp/character-grid-matte --benchmark
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m experimental.compare --source /path/to/image.png --output /private/tmp/character-grid-matte-custom
```

Open the generated `index.html`. Each case includes baseline/experimental PNG and SVG, character-only PNG/SVG, shape ownership, matte coverage and layer JSON. The normal CLI and default renderer remain unchanged.
