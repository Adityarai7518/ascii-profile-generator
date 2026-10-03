"""Small shared timelines and geometry for SVG and Pillow animations."""

import math
import hashlib
from bisect import bisect_right
from dataclasses import dataclass


SPEED_SETTINGS = {
    "slow": {"reveal": 9.0, "loop": 9.0},
    "normal": {"reveal": 5.5, "loop": 5.5},
    "fast": {"reveal": 2.8, "loop": 2.8},
}
REVEALS = {
    "row-reveal", "column-reveal", "diagonal-reveal", "aperture-reveal",
    "circular-reveal", "fade", "typewriter", "dissolve", "mosaic",
}
VALID_ANIMATIONS = REVEALS | {
    "instant", "twinkle", "sparkle-wave", "flag-wave", "digital-rain", "tetris",
}
DISSOLVE_GROUPS = 32
TWINKLE_GROUPS = 12
TETRIS_MAX_PIECES = 5000
MOSAIC_MAX_TILES = 512
RAIN_COLOUR = "#91b6ad"


def mosaic_progress(progress, repeat=False):
    """The reveal envelope with exact empty/complete boundary states."""
    p = clamp(progress)
    if p == 0 or (repeat and p == 1):
        return 0.
    if (not repeat and p == 1) or (repeat and .65 <= p <= .80):
        return 1.
    return reveal_progress(p, repeat)


@dataclass(frozen=True)
class MosaicTile:
    cells: tuple  # Half-open (x0, y0, x1, y1), including blank cells.
    bounds: tuple  # Canvas coordinates, extended through outer padding.
    start: float
    end: float

    def rectangle(self, amount):
        x0, y0, x1, y1 = self.bounds
        f = clamp((amount - self.start) / (self.end - self.start))
        if amount >= self.end:
            return x0, y0, x1 - x0, y1 - y0
        width, height = (x1 - x0) * f, (y1 - y0) * f
        return (x0 + x1 - width) / 2, (y0 + y1 - height) / 2, width, height

    def keyframes(self, repeat):
        times = tuple(reveal_times(self.start, self.end, repeat))
        return times, tuple(self.rectangle(mosaic_progress(t, repeat)) for t in times)


@dataclass(frozen=True)
class MosaicPlan:
    seconds: float
    repeat: bool
    width: int
    height: int
    tiles: tuple  # Digest order is reveal rank.

    def progress(self, progress):
        return mosaic_progress(progress, self.repeat)

    def completion_keyframes(self):
        # SMIL currentTime is a float32 in browsers. Protect exact boundary
        # seeks from float conversion plus microsecond clock truncation,
        # including the final freeze. Two microseconds cover both errors.
        # Only the completion guard uses this tolerance; tile timing stays
        # on the shared linear reveal envelope.
        epsilon = 2e-6 / self.seconds
        if self.repeat:
            return (0., .65 - epsilon, .80 + epsilon, 1.), (0, self.width, 0, 0)
        return (0., 1. - epsilon, 1.), (0, self.width, self.width)


def mosaic_plan(config, grid):
    """Bounded geometry only: no cell content affects ownership or order."""
    cols, rows = config['cols'], config['rows']
    cw, ch = config['cell_w'], config['cell_h']
    h = 4
    while True:
        w = max(1, math.floor(h * ch / cw + .5))
        if math.ceil(cols / w) * math.ceil(rows / h) <= MOSAIC_MAX_TILES:
            break
        h += 1
    width, height = cols * cw + 40, rows * ch + 40
    regions = []
    for y0 in range(0, rows, h):
        for x0 in range(0, cols, w):
            x1, y1 = min(cols, x0 + w), min(rows, y0 + h)
            seed = f'mosaic-v1:{cols}:{rows}:{cw}:{ch}:{x0}:{y0}:{x1}:{y1}'
            regions.append((hashlib.sha256(seed.encode('ascii')).digest(),
                            y0, x0, x1, y1))
    regions.sort()
    tiles = []
    for rank, (_, y0, x0, x1, y1) in enumerate(regions):
        start = .75 * rank / max(1, len(regions) - 1)
        bounds = (0 if x0 == 0 else 20 + x0 * cw,
                  0 if y0 == 0 else 20 + y0 * ch,
                  width if x1 == cols else 20 + x1 * cw,
                  height if y1 == rows else 20 + y1 * ch)
        tiles.append(MosaicTile((x0, y0, x1, y1), bounds, start, start + .25))
    return MosaicPlan(duration('mosaic', config['speed']),
                      repeats('mosaic', config['loop']), width, height, tuple(tiles))


@dataclass(frozen=True)
class RainStream:
    x: float
    phase: float
    travel: float
    gap: float
    glyphs: tuple
    opacities: tuple
    speed: int = 1

    def position(self, progress):
        """Head baseline; recycle only while the complete trail is offscreen."""
        return ((self.phase + self.speed * clamp(progress)) % 1.) * self.travel - self.gap

    def keyframes(self):
        # The offscreen reset occupies a negligible interval, avoiding duplicate
        # keyTimes while preserving continuous downward motion inside the clip.
        times = [0.]
        for cycle in range(1, self.speed + 1):
            reset = (cycle - self.phase) / self.speed
            times.extend((reset - 1e-6, reset))
        times.append(1.)
        times = tuple(times)
        return times, tuple(self.position(t) for t in times)


def rain_streams(config, grid):
    """A small deterministic backdrop, independent of artwork glyph selection."""
    cols, rows = config["cols"], config["rows"]
    cw, ch = config["cell_w"], config["cell_h"]
    height = rows * ch + 40
    alphabet = ''.join(dict.fromkeys(c for c in config["ramp"] if 33 <= ord(c) <= 126)) or '.:irsA'
    digest = hashlib.sha256(f'{cols}:{rows}:{cw}:{ch}:{config["ramp"]}'.encode())
    for row in grid:
        for cell in row:
            digest.update(f'{cell["index"]}:{cell["alpha"]:.6f}:{cell["color"]};'.encode())
    seed = digest.digest()
    count = max(1, min(24, cols // 8))
    streams = []
    for i in range(count):
        bits = hashlib.sha256(seed + i.to_bytes(2, 'big')).digest()
        length = 12 + bits[0] % 14
        phase = .05 + .90 * bits[1] / 255
        gap = height * (.08 + .12 * bits[2] / 255)
        column = (i + .15 + .70 * bits[3] / 255) * cols / count
        x = 20 + min(cols - 1, column) * cw
        glyphs = tuple(alphabet[bits[4 + j] % len(alphabet)] for j in range(length))
        streams.append(RainStream(x, phase, height + length * ch + gap, gap,
                                  glyphs, (1.,) + tuple(.8 * .75 ** j for j in range(length - 1)),
                                  # Whole traversals keep the loop seam exact;
                                  # path length adds finer velocity variation.
                                  1 + bits[29] % 2))
    return tuple(streams)


@dataclass(frozen=True)
class TetrisPiece:
    cells: tuple
    times: tuple
    offsets: tuple

    def offset(self, progress):
        p = clamp(progress)
        i = max(0, min(len(self.times) - 2, bisect_right(self.times, p) - 1))
        fraction = (p - self.times[i]) / (self.times[i + 1] - self.times[i])
        return self.offsets[i] + fraction * (self.offsets[i + 1] - self.offsets[i])


@dataclass(frozen=True)
class TetrisPlan:
    seconds: float
    repeat: bool
    pieces: tuple


def tetris_plan(config, grid):
    """Partition cells into small rigid chunks; lower chunks lock first."""
    cols, rows, ch = config['cols'], config['rows'], config['cell_h']
    # Preserve the original pieces/timing through 160x90. Above the bound,
    # enlarge each shape's constituent blocks equally in both dimensions:
    # bars, squares and Ls retain their silhouettes, with every cell retained.
    scale = 1
    while 2 * math.ceil(cols / (3 * scale)) * math.ceil(rows / (2 * scale)) > TETRIS_MAX_PIECES:
        scale += 1
    # Each tile is partitioned exactly once. Clip edge formations to the grid.
    shapes = (
        (((0, 0), (1, 0), (2, 0)), ((0, 1), (1, 1), (2, 1))),
        (((0, 0), (0, 1), (1, 1)), ((1, 0), (2, 0), (2, 1))),
        (((0, 0), (1, 0), (0, 1), (1, 1)), ((2, 0), (2, 1))),
    )
    pieces = []
    for y in range(0, rows, 2 * scale):
        for x in range(0, cols, 3 * scale):
            seed = hashlib.sha256(f'tetris:{cols}:{rows}:{x}:{y}'.encode()).digest()
            for j, shape in enumerate(shapes[seed[0] % len(shapes)]):
                cells = tuple((x + dx * scale + bx, y + dy * scale + by)
                              for dx, dy in shape for by in range(scale) for bx in range(scale)
                              if x + dx * scale + bx < cols and y + dy * scale + by < rows)
                if not cells:
                    continue
                bottom = max(cy for _, cy in cells)
                start = .02 + .56 * (rows - 1 - bottom) / max(1, rows - 1) + .06 * seed[1 + j] / 255
                end = start + .20 + .08 * seed[3 + j] / 255
                initial = -(20 + (bottom + 2) * ch)
                times = (0., start, start + .3 * (end - start), end, 1.)
                pieces.append(TetrisPiece(cells, times, (initial, initial, initial * .91, 0., 0.)))
    return TetrisPlan(duration('tetris', config['speed']), repeats('tetris', config['loop']), tuple(pieces))


@dataclass(frozen=True)
class OpacityEnvelope:
    """Alpha-transfer exponents emitted by SVG and sampled by GIF."""

    times: tuple
    values: tuple

    def at(self, progress):
        p = clamp(progress)
        i = max(0, min(len(self.times) - 2, bisect_right(self.times, p) - 1))
        fraction = (p - self.times[i]) / (self.times[i + 1] - self.times[i])
        return self.values[i] + fraction * (self.values[i + 1] - self.values[i])


@dataclass(frozen=True)
class OpacityTarget:
    cells: tuple
    envelope: OpacityEnvelope


@dataclass(frozen=True)
class OpacityPlan:
    """An immutable plan over the static grid; no glyph or colour replacement.

    Bounded, staggered cell groups use an alpha-gamma transfer. Exponent 1
    is identity; an exponent below 1 strengthens existing fractional coverage
    without changing RGB, zero coverage, or fully opaque ink. This is a visual
    treatment of the rasterized glyph, never a change to grid/source alpha.
    """

    seconds: float
    repeat: bool
    targets: tuple


def twinkle_group(x, y, seed=20260926):
    # Small spatial clusters remain perceptible after GIF downsampling. Half
    # the clusters stay static, and only a subset pulse concurrently. Coverage
    # scales with ink instead of vanishing behind a fixed 80-character cap.
    value = ((x // 2 + 1) * 0x45D9F3B) ^ ((y // 2 + 1) * 0x119DE1F3) ^ seed
    value = (value ^ (value >> 16)) * 0x45D9F3B
    return (value ^ (value >> 16)) % (2 * TWINKLE_GROUPS)


def opacity_plan(config, grid, seed=20260926):
    """Define Twinkle timing, ownership and alpha transfer for both exporters."""
    name = config["animation"]
    if name == "twinkle":
        groups = [[] for _ in range(TWINKLE_GROUPS)]
        eligible = [(x, y) for y, row in enumerate(grid) for x, cell in enumerate(row)
                    if cell["alpha"] > 0 and not config["ramp"][cell["index"]].isspace()]
        for x, y in eligible:
            group = twinkle_group(x, y, seed)
            if group < TWINKLE_GROUPS:
                groups[group].append((x, y))
        if eligible and not any(groups):
            groups[0].append(eligible[0])
        targets = []
        for group, cells in enumerate(groups):
            if not cells:
                continue
            start = .70 * group / (TWINKLE_GROUPS - 1)
            peak, end = start + .15, min(1., start + .30)
            times = tuple(sorted({0., start, peak, end, 1.}))
            values = tuple(.16 if t == peak else 1. for t in times)
            targets.append(OpacityTarget(tuple(cells), OpacityEnvelope(times, values)))
        targets = tuple(targets)
    else:
        raise ValueError(f"No Twinkle plan for {name}")
    return OpacityPlan(duration(name, config["speed"]),
                       repeats(name, config["loop"]), targets)


def clamp(value):
    return max(0.0, min(1.0, value))


def repeats(animation, loop):
    return animation != "instant" and (animation == "flag-wave" or loop == "yes")


def duration(animation, speed):
    value = SPEED_SETTINGS[speed]["loop"]
    return max(4.0, value) if animation == "flag-wave" else value


def reveal_progress(progress, repeat=False):
    p = clamp(progress)
    if not repeat:
        return p
    if p < .65:
        return p / .65
    if p < .80:
        return 1.0
    return (1.0 - p) / .20


def reveal_times(start=0.0, end=1.0, repeat=False):
    if repeat:
        return sorted({0.0, .65 * start, .65 * end,
                       1 - .20 * end, 1 - .20 * start, 1.0})
    return sorted({0.0, start, end, 1.0})


def interpolate(values, progress):
    position = clamp(progress) * (len(values) - 1)
    left = min(len(values) - 2, int(position))
    return values[left] + (values[left + 1] - values[left]) * (position - left)


def dissolve_group(x, y):
    # Stable integer mixing; neither Python's randomized hash nor mutable RNG.
    value = ((x + 1) * 0x45D9F3B) ^ ((y + 1) * 0x119DE1F3)
    value = (value ^ (value >> 16)) * 0x45D9F3B
    return (value ^ (value >> 16)) % DISSOLVE_GROUPS


def group_visibility(progress, group, count):
    return clamp(progress * count - group)


def aperture_points(width, height, progress):
    radius = math.hypot(width / 2, height / 2) / math.cos(math.pi / 8) * progress
    return [(width / 2 + math.cos(-math.pi / 8 + i * math.pi / 4) * radius,
             height / 2 + math.sin(-math.pi / 8 + i * math.pi / 4) * radius)
            for i in range(8)]


def flag_strips(cols, cell_h, pad=20):
    count = min(20, max(8, cols // 6))
    result = []
    for i in range(count):
        x0, x1 = round(i * cols / count), round((i + 1) * cols / count)
        t = ((x0 + x1 - 1) / 2) / max(1, cols - 1)
        amplitude = min(pad - 1, cell_h * 1.25) * (max(0, (t - .16) / .84) ** 1.65)
        values = [amplitude * math.sin(math.tau * (j / 16 - t * .8)) for j in range(17)]
        result.append((x0, x1, values))
    return result


def gif_timeline(animation, speed, loop, plan=None):
    if animation == "instant":
        return [1.0], [100]
    ticks = round((plan.seconds if plan is not None else duration(animation, speed)) * 100)
    count = max(24, min(90, math.ceil(ticks / (5 if animation in {"digital-rain", "tetris"} else 10))))
    repeat = plan.repeat if plan is not None else repeats(animation, loop)
    positions = [i / (count if repeat else count - 1) for i in range(count)]
    # GIF stores hundredths of a second. Distribute whole ticks without drift.
    boundaries = [round(i * ticks / count) for i in range(count + 1)]
    durations = [(boundaries[i + 1] - boundaries[i]) * 10 for i in range(count)]
    return positions, durations
