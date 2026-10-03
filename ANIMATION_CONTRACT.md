# Ambient animation contract

> Historical notice: the ambient descriptions and regression thresholds below,
> through the browser-verification paragraph, describe a superseded implementation.
> Current Twinkle strengthens coverage with an alpha-gamma envelope; it does not
> dim glyphs. Breathing is no longer a menu animation; option 12 is Digital Rain.
> These historical notes must not override current code/tests. The Mosaic
> contract at the end of this document describes the current implementation.

`animations.opacity_plan(config, grid)` is the shared authority for Twinkle and
Breathing. It returns immutable targets, normalized keyframes, cycle duration,
and repeat semantics. SVG emits these keyframes on artwork groups. GIF samples
the same piecewise-linear envelopes and uses the plan's duration/repeat state.
The other eleven animation types keep their existing geometry and timelines.

## Artwork and timing

- Grid selection, glyphs, source alpha, positions and colours are immutable.
  Animation only multiplies existing ink opacity; it never adds replacement ink.
- A cycle starts and ends at full original intensity. `loop=no` plays once and
  keeps that completed state. SVG uses `fill="freeze"`; GIF omits the loop
  extension. `loop=yes` uses indefinite SVG repetition / GIF loop value zero.
- Slow, Normal and Fast last 9, 5.5 and 2.8 seconds. GIF includes the completed
  endpoint for a single cycle and excludes the duplicate endpoint when looping.
  Centisecond rounding and merged identical frames must preserve total duration.
- One static glyph set per SVG. No copied frames, persistent metric caches,
  runtime randomness, colour changes or glyph substitutions.

## Twinkle

Half of deterministic 2×2 cell clusters are eligible to pulse, assigned to at
most 12 staggered groups. Each group dips from 1 to .65 and returns to 1 over
30% of the cycle. Most artwork remains at full intensity at any instant.
Grouping scales with the artwork instead of selecting at most 80 glyphs.
Blank/transparent cells are excluded, including custom ramps with nonblank index
zero. Sparse artwork gets at least one target if any visible glyph exists.

SVG wraps each target group once. GIF builds one byte-per-pixel group map at
export resolution and applies a small lookup table per frame. Target ownership
is deterministic; local pulses must not become one uniform global fade.

## Breathing

One global envelope runs 1 → .82 → 1, with its minimum halfway through the
cycle. Seventeen piecewise-linear samples describe a smooth sinusoidal envelope.
The .82 minimum was selected after comparing .90, .86, .82 and .80 on actual SVG
and decoded GIF output. This remains a gentle global intensity change, distinct
from localized Twinkle, travelling Sparkle Wave, and Fade In.

## Regression gates

Run `.venv/bin/python -m unittest -v`. Permanent tests cover both effects across
five colour modes, three speeds, two loop states and both SVG/GIF (120 exports
in total), plus a default 120×64 transparent-source Twinkle case.

Tests inspect emitted SVG target ownership, varying envelopes, bounded animation
nodes, unchanged glyph content, durations, endpoint/repeat behavior and locality.
GIF tests decode RGB pixels, require multiple unique frames and no identical
consecutive decoded frames, check total delays and loop metadata, and measure
contrast/coverage against the background. A change exceeding 8/255 in at least
4% of visible-ink pixels is the local-motion regression floor. Breathing must
change over half the ink (including faint antialias pixels) and reduce aggregate
contrast against the decoded background by at least 10%, with a
minimum no lower than 76% after rasterization and quantization. Twinkle must
retain over 85% aggregate contrast and affect less than 60% of ink at peak.
These are behavioral budgets, not exact bytes or equality to renderer formulas.

The default-size case is essential: the former sparse selection passed tiny
fixtures and any-pixel-difference tests while looking static at export size.
Empty, invisible, or background-matching artwork cannot promise visible motion.
GIF colour quantization may merge equal holds near breathing extrema; removing
all or most motion must fail the frame count, unique-frame and contrast gates.

Browser verification complements these tests: inspect computed target opacity
at start, midpoint, end and beyond one cycle, then observe actual playback.
An SVG parsing successfully is insufficient evidence of browser animation.

## Mosaic (current)

Option 14, `mosaic`, changes visibility over time and never changes the artwork.
`animations.mosaic_plan(config, grid)` is the shared immutable SVG/GIF authority.
Cells retain index, colour, alpha, tone, ramp identity, coordinates and metrics.
There is one artwork layer; tiles contain geometry, not cloned glyphs.

- At most 512 rectangular macrotiles. Starting at `h=4`, choose
  `w=max(1,floor(h*cell_h/cell_w+0.5))`; increase `h` until
  `ceil(cols/w)*ceil(rows/h)<=512`. Half-open ranges own every cell exactly once,
  including blank/transparent cells. Outer apertures include canvas padding.
- Reveal order sorts SHA-256 digest bytes of
  `mosaic-v1:C:R:cw:ch:x0:y0:x1:y1`, with row-major tie-breaking. No artwork
  content, paths, mutable randomness, speed or loop state affects grouping/order.
- Rank `r` of `P` opens from `0.75*r/max(1,P-1)` through 0.25 progress later.
  Rectangular width/height grow linearly about the tile center. Glyphs stay fixed.
- Durations are 9/5.5/2.8 seconds. Non-looping progress opens then freezes.
  Looping progress opens over 65%, holds fully open through 80%, then closes.
  Empty endpoints and complete-hold boundaries are explicit exact states.
- SVG uses one user-space clip union, four numeric animations per tile, a
  discrete full-canvas completion aperture, and a discrete clip bypass during
  completion. Removing the clip avoids browser alpha-rounding changes even when
  the aperture is fully open. The guard adds no painted layer. Its transition
  times include a two-microsecond tolerance for browser float32 conversion and
  microsecond clock truncation at boundaries;
  tile geometry/timing retain the shared reveal envelope.
  Additional nodes are bounded by `5P+6`; animation nodes by `4P+2`.
  Unanimated base attributes provide an unclipped, complete static fallback.
- GIF uses one 2x fitted-resolution L mask, BOX downsampling, and one alpha
  multiplication. Shared half-open pixel boundaries prevent tile-edge gaps.
  Completion returns the original foreground unchanged. RGB is untouched until
  normal background compositing. Existing palette, sizing and encoding remain.
- Non-looping decoded GIF completion equals the fitted static foreground
  flattened through the same background path and quantized with the GIF palette.
  Looping samples omit the duplicate endpoint; encoded identical frames may merge
  while preserving total centisecond duration.

`test_mosaic.py` covers ownership, geometry, hash-seed independence, endpoints,
colour/alpha preservation, SVG structure, decoded GIFs and the 50,000-cell bound.
Browser playback and completion screenshots supplement structural tests; neither
XML parsing nor source-frame tests alone establish rendered correctness.
