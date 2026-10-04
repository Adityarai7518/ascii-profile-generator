"""One deterministic spatial-glyph/coverage experiment; see README.md.

Production preprocessing and serializers are reused, never patched. Shapes
are analysis regions, not visible geometry and not animation pieces.
"""
from dataclasses import dataclass
import heapq
import math

from PIL import Image

import ascii_renderer as renderer
import exporter

MAX_REGIONS = 1024
MAX_DEPTH = 16
VARIATION_THRESHOLD = .06


@dataclass(frozen=True)
class GridShape:
    bounds: tuple  # Half-open cell coordinates x0, y0, x1, y1.
    mean_density: float
    mean_alpha: float
    variance: float
    depth: int


@dataclass(frozen=True)
class GridShapes:
    cols: int
    rows: int
    regions: tuple
    owners: tuple


@dataclass(frozen=True)
class CharacterCell:
    index: int
    alpha: float
    color: str
    tone: float


@dataclass(frozen=True)
class CharacterLayer:
    cells: tuple
    ramp: str
    glyph_coverage: tuple

    def as_grid(self):
        return [[dict(index=c.index, alpha=c.alpha, color=c.color, tone=c.tone)
                 for c in row] for row in self.cells]


@dataclass(frozen=True)
class Matte:
    coverage: tuple  # Per-existing-glyph opacity multiplier, not source alpha.


@dataclass(frozen=True)
class Experiment:
    shapes: GridShapes
    characters: CharacterLayer
    matte: Matte

    def compose(self):
        return compose_ascii(self.characters, self.matte)


def validate_config(config):
    for name, limit in [('cols', renderer.MAX_COLS), ('rows', renderer.MAX_ROWS)]:
        value = config[name]
        if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= limit:
            raise ValueError(f'{name} must be an integer in [1, {limit}]')
    if config['cols'] * config['rows'] > renderer.MAX_CELLS:
        raise ValueError('Experimental cell count exceeds the production limit')
    for name, limit in [('cell_w', renderer.MAX_CELL_W), ('cell_h', renderer.MAX_CELL_H)]:
        value = config[name]
        if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= limit:
            raise ValueError(f'{name} must be an integer in [1, {limit}]')
    ramp = config['ramp']
    if not 2 <= len(ramp) <= 32 or not ramp.strip() or any(ord(c) < 32 for c in ramp):
        raise ValueError('Use a 2–32 character ramp with visible glyphs and no controls')
    if config.get('animation', 'instant') != 'instant':
        raise ValueError('This experiment is static; animation behavior is outside its scope')
    if config['mode'] not in renderer.VALID_MODES:
        raise ValueError('Unknown colour mode')


def validate_grid(config, grid):
    if len(grid) != config['rows'] or any(len(row) != config['cols'] for row in grid):
        raise ValueError('Grid dimensions do not match configuration')
    for row in grid:
        for cell in row:
            if not isinstance(cell['index'], int) or not 0 <= cell['index'] < len(config['ramp']):
                raise ValueError('Invalid character index')
            if not math.isfinite(cell['alpha']) or not 0 <= cell['alpha'] <= 1:
                raise ValueError('Invalid cell alpha')
            if not math.isfinite(cell['tone']) or not 0 <= cell['tone'] <= 1:
                raise ValueError('Invalid cell tone')
            if not renderer.is_hex(cell['color']):
                raise ValueError('Invalid cell colour')


def build_baseline(config):
    """Reuse production verbatim for supported input, handle empty art locally.

    Production rejects images with no visible cells. The experiment returns an
    empty grid for this case, without changing the production policy.
    """
    validate_config(config)
    source = renderer.load_source(config['src'])
    _, alpha, _ = renderer.crop_to_cell_aspect(source.convert('RGB'), source.getchannel('A'), config)
    alpha = alpha.resize((config['cols'], config['rows']), Image.Resampling.LANCZOS)
    if alpha.getextrema()[1] / 255 <= renderer.ALPHA_THRESHOLD:
        return [[dict(index=0, alpha=0., color=config['foreground'], tone=0.)
                 for _ in range(config['cols'])] for _ in range(config['rows'])]
    return renderer.build_grid(config)


class _Statistics:
    """Four summed-area tables: O(cells) storage, constant-time region stats."""
    def __init__(self, grid, ramp):
        self.tables = [[[0.] * (len(grid[0]) + 1) for _ in range(len(grid) + 1)] for _ in range(4)]
        for y, row in enumerate(grid):
            running = [0.] * 4
            for x, cell in enumerate(row):
                a = cell['alpha']
                d = cell['index'] / (len(ramp) - 1)
                for i, value in enumerate((a, a*d, a*d*d, a*a)):
                    running[i] += value
                    self.tables[i][y+1][x+1] = self.tables[i][y][x+1] + running[i]

    def region(self, bounds):
        x0, y0, x1, y1 = bounds
        w, d, d2, a2 = [t[y1][x1]-t[y0][x1]-t[y1][x0]+t[y0][x0] for t in self.tables]
        n = (x1-x0)*(y1-y0)
        error = max(0., d2-d*d/w) if w > 1e-12 else 0.
        error += max(0., a2-w*w/n)
        return error, d/w if w > 1e-12 else 0., max(0., min(1., w/n))


def build_grid_shapes(config, baseline, max_regions=MAX_REGIONS):
    """Best variance-reducing rectangular cuts, with deterministic tie breaks."""
    validate_config(config)
    validate_grid(config, baseline)
    if not isinstance(max_regions, int) or not 1 <= max_regions <= MAX_REGIONS:
        raise ValueError(f'max_regions must be in [1, {MAX_REGIONS}]')
    stats = _Statistics(baseline, config['ramp'])
    bounds = (0, 0, config['cols'], config['rows'])
    leaves = {bounds: 0}
    pending = []

    def schedule(box, depth):
        x0, y0, x1, y1 = box
        error, _, _ = stats.region(box)
        area = (x1-x0)*(y1-y0)
        if depth >= MAX_DEPTH or area == 1 or error / area <= VARIATION_THRESHOLD**2:
            return
        best = None
        for axis in (0, 1):
            for cut in range((x0 if axis == 0 else y0)+1, x1 if axis == 0 else y1):
                left = (x0, y0, cut, y1) if axis == 0 else (x0, y0, x1, cut)
                right = (cut, y0, x1, y1) if axis == 0 else (x0, cut, x1, y1)
                gain = error - stats.region(left)[0] - stats.region(right)[0]
                left_area = (left[2]-left[0])*(left[3]-left[1])
                # Quantize only ranking noise from summed-area subtraction.
                # Balanced cuts, then x before y, then smaller coordinate win ties.
                rank = (round(gain, 10), -abs(area-2*left_area), -axis, -cut)
                if best is None or rank > best[0]:
                    best = rank, left, right
        if best is not None:
            heapq.heappush(pending, (-round(error, 10), box, depth, best[1], best[2]))

    schedule(bounds, 0)
    while pending and len(leaves) < max_regions:
        _, box, depth, left, right = heapq.heappop(pending)
        del leaves[box]
        for child in (left, right):
            leaves[child] = depth+1
            schedule(child, depth+1)
    regions = []
    owners = [[-1]*config['cols'] for _ in range(config['rows'])]
    for box, depth in sorted(leaves.items(), key=lambda item: (item[0][1], item[0][0], item[0][3], item[0][2])):
        x0, y0, x1, y1 = box
        error, density, alpha = stats.region(box)
        owner = len(regions)
        regions.append(GridShape(box, density, alpha, error/((x1-x0)*(y1-y0)), depth))
        for y in range(y0, y1):
            owners[y][x0:x1] = [owner]*(x1-x0)
    return GridShapes(config['cols'], config['rows'], tuple(regions), tuple(map(tuple, owners)))


def calibrate_glyph_coverage(config):
    """Measure existing ramp glyphs with the exact production font/metrics."""
    single = dict(config, cols=1, rows=1, animation='instant')
    result = []
    for index, char in enumerate(config['ramp']):
        if char.isspace():
            result.append(0.)
            continue
        image = exporter.render_foreground(single, [[dict(index=index, alpha=1., color='#ffffff', tone=1.)]])
        result.append(sum(image.getchannel('A').getdata()) / (255*config['cell_w']*config['cell_h']))
    return tuple(result)


def build_character_representation(config, baseline, shapes, glyph_coverage=None):
    """Choose region-coherent glyphs; keep alpha, colour and tone independent."""
    if (shapes.cols, shapes.rows) != (config['cols'], config['rows']):
        raise ValueError('Shape dimensions do not match configuration')
    coverage = calibrate_glyph_coverage(config) if glyph_coverage is None else tuple(glyph_coverage)
    if len(coverage) != len(config['ramp']) or any(not math.isfinite(v) or v < 0 for v in coverage):
        raise ValueError('Invalid glyph coverage calibration')
    representatives = []
    for shape in shapes.regions:
        x0, y0, x1, y1 = shape.bounds
        candidates = sorted((coverage[c['index']], c['index'])
                            for row in baseline[y0:y1] for c in row[x0:x1]
                            if c['alpha'] > 0 and coverage[c['index']] > 0)
        representatives.append(candidates[math.floor(.9*(len(candidates)-1))][1] if candidates else 0)
    cells = []
    for y, row in enumerate(baseline):
        output = []
        for x, cell in enumerate(row):
            original = cell['index']
            representative = representatives[shapes.owners[y][x]]
            selected = (representative if cell['alpha'] > 0 and coverage[original] > 0
                        and coverage[representative] >= coverage[original] else original)
            output.append(CharacterCell(selected, cell['alpha'], cell['color'], cell['tone']))
        cells.append(tuple(output))
    return CharacterLayer(tuple(cells), config['ramp'], coverage)


def build_matte(baseline, characters):
    if len(baseline) != len(characters.cells) or any(len(a) != len(b) for a, b in zip(baseline, characters.cells)):
        raise ValueError('Character and baseline dimensions differ')
    coverage = []
    for base_row, row in zip(baseline, characters.cells):
        line = []
        for original, chosen in zip(base_row, row):
            old = characters.glyph_coverage[original['index']]
            new = characters.glyph_coverage[chosen.index]
            line.append(min(1., max(0., old/new)) if original['alpha'] > 0 and new > 0 else 0.)
        coverage.append(tuple(line))
    return Matte(tuple(coverage))


def compose_ascii(characters, matte):
    grid = characters.as_grid()
    if len(grid) != len(matte.coverage) or any(len(a) != len(b) for a, b in zip(grid, matte.coverage)):
        raise ValueError('Matte and character dimensions differ')
    for row, mask in zip(grid, matte.coverage):
        for cell, amount in zip(row, mask):
            if not math.isfinite(amount) or not 0 <= amount <= 1:
                raise ValueError('Matte coverage must be finite and in [0, 1]')
            cell['alpha'] *= amount
    return grid


def build_experiment(config, baseline=None):
    validate_config(config)
    baseline = build_baseline(config) if baseline is None else baseline
    shapes = build_grid_shapes(config, baseline)
    characters = build_character_representation(config, baseline, shapes)
    return Experiment(shapes, characters, build_matte(baseline, characters))
