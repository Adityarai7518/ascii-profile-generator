# Character + Grid Shapes + Matte — first-version report

**Decision: NOT WORTH INTEGRATING.** This applies to the tested first implementation, not every possible interpretation of the proposed method. It works technically and reduces character variation, but the actual outputs show no meaningful recognition advantage and sometimes conspicuous rectangular texture. No visual tuning loop was performed after these comparisons.

## 1. Branch and isolation

Created `feature/ascii-character-grid-matte` from `2650358`. HEAD is still `2650358`. `feature/mosaic-tetris-ambient` remains at that commit and `main` remains at `9d0acbe`. No commits, pushes, merges, dependency installations or production changes were made.

All tracked baseline files and the two pre-existing untracked browser-check files match their start-of-task SHA-256 hashes. Those browser files were preserved, not incorporated into this experiment.

## 2. Baseline architecture

Source → existing loading/EXIF and aspect crop → alpha-aware premultiplied resizing, brightness/contrast and tone normalization → S curve/gamma and local contrast → density/ramp selection → authoritative index/alpha/colour/tone grid → existing SVG/Pillow exporters.

The stable renderer already includes local contrast. This is not a comparison against a purely global luminance mapper. PNG/JPEG flattening rules, GIF export and all animation plans remain unchanged. Existing Mosaic #14 is unrelated and untouched.

## 3. Experimental architecture

Source → unchanged baseline grid as a shared analysis input → image-dependent rectangular Grid Shapes → spatially coherent Character layer + separately computed Matte → alpha composition into a new grid → unchanged static SVG/Pillow serializers.

This first version intentionally inherits baseline preprocessing and initial quantization, rather than duplicating or extracting private preprocessing code. It cannot recover information already lost there. The experiment tests spatial glyph organization and coverage, not an entirely new source-analysis system.

## 4. Files added / modified

All additions are inside `experimental/`:

- `__init__.py`: opt-in package; not imported by the production CLI.
- `character_grid_matte.py`: typed character, shape and matte layers; deterministic decomposition, calibration and composition.
- `compare.py`: explicit A/B entry point, diagnostics, gallery and size benchmarks.
- `fixtures.py`: deterministic local evaluation inputs.
- `test_character_grid_matte.py`: 15 focused tests.
- `README.md`: design recorded before implementation, usage and limitations.
- `RESULTS.md`: this report.

No existing file was modified. Generated PNG/SVG/layer data and the gallery are separate review artifacts, not public demo assets.

## 5. Character

The original ramp, metrics, colour, baseline alpha (including mode-dependent tone opacity), and tone are retained. Ink coverage for each ramp character is measured through the unchanged Pillow glyph renderer. Each region selects the character at its 90th percentile of measured glyph coverage. A cell adopts it only when it is at least as dense as that cell's original glyph. Denser details retain their existing character; blank and transparent cells remain blank/transparent. Character-only PNG/SVG and JSON remain inspectable without the matte.

## 6. Grid Shapes

Four summed-area tables describe alpha-weighted normalized ramp density and alpha variation. Greedy axis-aligned cuts maximize variance reduction, with deterministic balanced/axis/coordinate tie breaks. The residual variation threshold is .06, maximum depth is 16, and region count is capped at 1,024. Every cell has exactly one owner, including empty space. Shapes follow the image's density structure and are not animation tiles.

Work is bounded by the cell limit, depth and region budget; no per-source-pixel segmentation is added. The decomposition operates at the ASCII-grid resolution. Shape maps are diagnostic only and are never coloured rectangles in the final artwork.

## 7. Matte and composition

For a visible cell, coverage = original glyph's measured ink / chosen glyph's measured ink. Coverage stays in [0,1]. The final grid retains the Character layer's index/colour/tone and multiplies its original alpha by that coverage. Blank/transparent contribution is zero. This is uniform coverage on each existing glyph, so no cell-edge clipping mask cuts off glyphs.

Calibrated ink demand is preserved per cell before output quantization (maximum observed floating-point error below 6e-17). Across the 11 generated cases, actual Pillow total-alpha changes remained below 0.04%. These establish compositing correctness, not superior recognizability. The matte cannot correct the perceptual effects of changing the glyph's shape.

## 8. A/B methodology and artifacts

Eight categories at 120×64, 8×15 cells, the default ramp, contrast 1.10, brightness/gamma 1.0, identical source/crop/configuration per pair. Main comparisons use Light mode; extra cases exercise Dark, Original with transparency, and Multicolour. Each pair is 1000×1000 pixels before gallery downscaling. Both baseline and experimental PNG/SVG files, source crop, character-only artwork, ownership image, matte and full layer JSON are available.

The face uses a crop of the repository's illustrated sample. The transparent case uses the unmodified RGBA sample. Object, landscape, high/low contrast, flat regions and fine detail use locally generated controlled scenes. No images were downloaded. There are no real human portrait or natural-scene photographs in this corpus; that limits generalization.

All eleven PNG comparison sheets were inspected at equal scale. Native-size WebKit face and Chromium fine-detail SVG screenshots were also inspected. Numerical diagnostics were not used as the perceptual decision rule.

## 9. Tests and validation

- Existing suite before implementation: **94 tests passed** in 25.344 s.
- Final full suite: **109 tests passed** in 27.947 s (94 existing + 15 experimental).
- Focused checks include same-process and cross-process/PYTHONHASHSEED reproducibility, dimensions, character validity, exact ownership, data-aligned cuts, region bounds, matte validity, calibrated composition, identity/zero coverage, empty/faint/transparent input, hidden RGB, small/extreme/large grids, colour modes and custom ramps.
- **44 SVG renders completed** in Chromium/WebKit: 11 cases × A/B × two engines. No animation or embedded artwork/image copies. Browser inspection confirms the patch texture is not merely a Pillow artifact.
- Compileall and whitespace checks passed. Every pre-existing file remains byte-identical; the baseline PNG/JPEG/GIF and Mosaic implementations were not changed.
- Completely transparent/below-threshold input is handled locally as empty artwork. Production's existing rejection of such an input is not changed or described as supported baseline behavior.

## 10. Performance

Medians of three local runs on the same illustrated face. Generation includes shared source/grid preparation, SVG string generation and Pillow RGBA rendering; excludes PNG encoding, file I/O and review diagnostics. Experimental total adds region construction, glyph calibration and matte composition. Sizes are native SVG and native RGBA foreground PNG, before background flattening or preview scaling. Both columns use identical formats. All four cases reach the 1,024-region cap.

| Grid | Baseline generation | Experimental generation | Added analysis/composition | SVG bytes A → B | RGBA PNG bytes A → B |
|---|---:|---:|---:|---:|---:|
| 120×64 | 211.5 ms | 298.7 ms | 77.9 ms | 405,156 → 405,076 | 133,739 → 173,010 |
| 160×90 | 357.5 ms | 500.3 ms | 123.2 ms | 748,399 → 748,179 | 213,557 → 301,592 |
| 200×120 | 561.1 ms | 773.0 ms | 181.5 ms | 1,227,011 → 1,226,651 | 315,300 → 464,282 |
| 300×166 | 1138.8 ms | 1541.4 ms | 323.7 ms | 2,595,074 → 2,595,186 | 511,833 → 801,261 |

Observed generation cost rises about 35–41%, and foreground PNG size about 29–57%. SVG size is essentially unchanged because both outputs still contain one glyph per visible cell. This is practical runtime, but no visual advantage currently justifies the added work.

## 11. Visual observations

| Case | Observed result |
|---|---|
| portrait | Eyes, goggles and mouth remain recognizable. Some character texture is quieter, but cheek/strap regions become patches of repeated letters; facial structure is not clearer. The 1,024-region cap is reached. |
| object | Camera silhouette and lens remain readable. The body acquires conspicuous rectangular runs of h/B/H; circular lens structure is not better. A small regularity benefit is outweighed by patch texture. |
| landscape | Mountains, water and tree silhouettes survive. Mountain faces gain rectangular glyph groups unrelated to the natural outline. No clear gain in hierarchy or edge definition. |
| low-contrast | Production normalization already recovers major forms from the narrow input range. B reduces some glyph changes but does not recover additional scene structure; patches remain. |
| high-contrast | Ring, triangular edge, inner negative space and thin line remain recognizable. Contour softness inherited from preprocessing remains. The experiment adds no compelling edge improvement. |
| flat-regions | Glyph repetition becomes more uniform inside constant-tone areas. The crossing circle remains visible but is not sharper; a quiet-texture benefit does not establish an overall perceptual advantage. |
| fine-detail | Strongest negative result: fewer glyph changes create large repetitive B/#/H blocks. The radial/weave detail is not more legible, and segmentation dominates the surface. The 1,024-region cap is reached. |
| transparent | Original illustrated-character silhouette and clear surrounding space remain intact. No new matte halo or cell-clipping seam is apparent; eyes, clothing and mouth are not materially easier to recognize. |
| portrait-dark | Dark-mode tone and contrast remain stable, but coherent letters do not produce a convincing recognition gain. Repeated patches are still apparent. |
| transparent-original | Source colours and source transparency survive. Colour helps recognition in both versions; B adds repeated glyph bands without a clear advantage. Checkerboard is a preview background only. |
| object-multicolour | Palette colours remain identical per cell. The lens/body remain recognizable; repeated glyph blocks persist and no new perceptual benefit appears. |

Glyph-neighbour transitions fall by 1.8–61.7% across the corpus. The greatest reduction occurs on fine detail, which is also the clearest visual regression: large repetitive glyph areas replace noisy character variation. Fewer different neighbours is therefore not sufficient evidence of better ASCII art.

No separate shape rectangles, extra artwork, obvious matte halos or cell-clipping seams were introduced. Individual characters remain readable. Nevertheless, their rectangular grouping becomes a distracting structure, particularly in fine texture and on the camera/mountain surfaces. Negative space and tone remain substantially stable rather than improved.

## 12. Decision

**NOT WORTH INTEGRATING.** The current implementation provides useful inspectable layers and correct coverage composition, but no meaningful visual advantage over the stable renderer. It sometimes trades irregular glyph texture for more objectionable spatial patches, costs more to generate, and grows PNG output. The experiment is complete at the requested first-version decision gate; there is no integration or additional tuning in this task.

## 13. Concrete limitations

- Small controlled corpus, one illustrated face source, no real human portraits, and no blinded human recognition study.
- All analysis begins with the existing quantized grid; it cannot restore subcell edges, natural details or structures lost during preprocessing.
- Axis-aligned regions can leave patch texture. The region cap is reached on the face/fine-detail cases and every large-grid benchmark.
- Equal integrated glyph ink does not imply equal perceived darkness, shape or readability. Calibration depends on the installed font/Pillow renderer; cross-font/platform byte equality is not promised.
- Matte coverage is uniform per glyph, not a higher-resolution object-boundary segmentation. It changes opacity, not character outlines.
- Existing tonal normalization and faint-signal background glyphs remain. This experiment does not solve them by retuning preprocessing.
- Static-only entry point deliberately rejects animation requests; production animations continue through the original renderer.

## Reproduce

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m experimental.compare \
  --output /private/tmp/character-grid-matte --benchmark
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m experimental.compare \
  --source /path/to/local/image.png --mode light \
  --output /private/tmp/character-grid-matte-custom
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -v
PYTHONPYCACHEPREFIX=/private/tmp/ascii-profile-generator-pycache .venv/bin/python -m compileall -q .
git diff --check
```

Open `index.html` from the generated output directory for the side-by-side gallery. Per-case baseline/experimental PNG and SVG links and independently inspectable layers are included. The gallery is local review material, not a production website update.

## Final working tree

```text
## feature/ascii-character-grid-matte
?? experimental/
?? verify_svg_browser.cjs
?? verify_svg_browser.py
```

`experimental/` is the new work. The two root browser-check files were already untracked when this experiment started and remain unchanged. There are no changes to tracked files.
