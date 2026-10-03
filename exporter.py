
import argparse
import math
import os
import platform
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont

SCRIPT_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from ascii_renderer import (  # noqa: E402
    MAX_CELLS,
    MAX_CELL_H,
    MAX_CELL_W,
    MAX_COLS,
    MAX_ROWS,
    MIN_CELL_H,
    MIN_CELL_W,
    MIN_COLS,
    MIN_ROWS,
    VALID_ANIMATIONS,
    VALID_LOOP,
    VALID_MODES,
    VALID_SPEEDS,
    build_grid,
    crop_to_cell_aspect,
    is_hex,
    load_source,
    infer_original_background,
)

from animations import (
    DISSOLVE_GROUPS, opacity_plan, repeats, reveal_progress,
    group_visibility, aperture_points, flag_strips, interpolate,
    dissolve_group, gif_timeline, rain_streams, RAIN_COLOUR, tetris_plan, mosaic_plan,
)

DEFAULT_SIZE = 1000
DEFAULT_GIF_SIZE = 640
DEFAULT_GIF_FRAMES = 18
DEFAULT_GIF_DURATION = 110
PAD = 20


def parse_background(value):
    value = value.strip().lower()

    if value in {
        "",
        "none",
        "transparent",
    }:
        return None

    if value == "original":
        return "original"

    if value == "white":
        return "#ffffff"

    if value == "black":
        return "#000000"

    if is_hex(value):
        return value

    raise ValueError(
        "Background must be #RRGGBB, original, none, "
        "or transparent."
    )


def parse_hex(value):
    if not is_hex(value):
        raise ValueError(
            f"Invalid HEX colour: {value!r}"
        )

    value = value.lstrip("#")
    return (
        int(value[0:2], 16),
        int(value[2:4], 16),
        int(value[4:6], 16),
    )


def find_font(size):

    candidates = []

    if platform.system() == "Darwin":
        candidates.extend(
            [
                (
                    "/System/Library/Fonts/"
                    "Menlo.ttc"
                ),
                (
                    "/System/Library/Fonts/"
                    "Monaco.ttf"
                ),
            ]
        )

    elif platform.system() == "Windows":
        candidates.extend(
            [
                r"C:\Windows\Fonts\consola.ttf",
                r"C:\Windows\Fonts\cour.ttf",
            ]
        )

    else:
        candidates.extend(
            [
                (
                    "/usr/share/fonts/truetype/"
                    "dejavu/DejaVuSansMono.ttf"
                ),
                (
                    "/usr/share/fonts/truetype/"
                    "liberation2/"
                    "LiberationMono-Regular.ttf"
                ),
            ]
        )

    for path in candidates:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(
                    path,
                    size=size,
                )
            except OSError:
                continue

    return ImageFont.load_default()


def make_config(args):
    try:
        cols = int(args.cols)
        rows = int(args.rows)
        cell_w = int(args.cell_w)
        cell_h = int(args.cell_h)
        contrast = float(args.contrast)
        brightness = float(args.brightness)
        gamma = float(args.gamma)
    except ValueError as exc:
        raise ValueError(
            f"Invalid numeric setting: {exc}"
        )

    if not MIN_COLS <= cols <= MAX_COLS:
        raise ValueError(
            f"Columns must be between {MIN_COLS} and {MAX_COLS}."
        )
    if not MIN_ROWS <= rows <= MAX_ROWS:
        raise ValueError(
            f"Rows must be between {MIN_ROWS} and {MAX_ROWS}."
        )
    if cols * rows > MAX_CELLS:
        raise ValueError(
            f"Maximum cell count is {MAX_CELLS:,}."
        )
    if not MIN_CELL_W <= cell_w <= MAX_CELL_W:
        raise ValueError(
            f"Cell width must be between {MIN_CELL_W} and {MAX_CELL_W}."
        )
    if not MIN_CELL_H <= cell_h <= MAX_CELL_H:
        raise ValueError(
            f"Cell height must be between {MIN_CELL_H} and {MAX_CELL_H}."
        )
    if not 0.05 <= contrast <= 4.0:
        raise ValueError("Contrast must be between 0.05 and 4.0.")
    if not 0.05 <= brightness <= 4.0:
        raise ValueError("Brightness must be between 0.05 and 4.0.")
    if not 0.05 <= gamma <= 4.0:
        raise ValueError("Gamma must be between 0.05 and 4.0.")

    ramp = args.ramp
    if not 2 <= len(ramp) <= 32:
        raise ValueError("Ramp must contain between 2 and 32 characters.")

    mode = args.mode.strip().lower()
    if mode not in VALID_MODES:
        raise ValueError(f"Unknown mode: {args.mode}")

    animation = args.animation.strip().lower()
    if animation not in VALID_ANIMATIONS:
        raise ValueError(f"Unknown animation: {args.animation}")

    speed = args.speed.strip().lower()
    if speed not in VALID_SPEEDS:
        raise ValueError(f"Unknown speed: {args.speed}")

    loop = args.loop.strip().lower()
    if loop not in VALID_LOOP:
        raise ValueError(f"Loop must be yes or no, not {args.loop!r}.")

    if animation == "instant":
        speed = "normal"
        loop = "no"
    elif animation == "flag-wave":
        loop = "yes"

    palette = []
    if args.palette.strip().lower() not in {"", "none"}:
        palette = [
            item.strip().lower()
            for item in args.palette.split(",")
            if item.strip()
        ]
        for item in palette:
            if not is_hex(item):
                raise ValueError(
                    f"Invalid palette colour: {item!r}"
                )

    foreground = args.foreground.strip().lower()
    if not is_hex(foreground):
        raise ValueError("Foreground must be #RRGGBB.")

    return {
        "src": os.path.abspath(args.input),
        "out": os.path.abspath(args.output),
        "mode": mode,
        "cols": cols,
        "rows": rows,
        "ramp": ramp,
        "contrast": contrast,
        "brightness": brightness,
        "gamma": gamma,
        "cell_w": cell_w,
        "cell_h": cell_h,
        "background": parse_background(args.background),
        "foreground": foreground,
        "palette": palette,
        "animation": animation,
        "speed": speed,
        "loop": loop,
    }

def canvas_size(config):
    return (
        config["cols"] * config["cell_w"] + PAD * 2,
        config["rows"] * config["cell_h"] + PAD * 2,
    )


def fit_image(image, max_size):
    if max_size is None:
        return image

    width, height = image.size
    longest = max(width, height)
    if longest <= max_size:
        return image

    scale = max_size / float(longest)
    new_size = (
        max(1, int(round(width * scale))),
        max(1, int(round(height * scale))),
    )
    return image.resize(
        new_size,
        Image.Resampling.LANCZOS,
    )


def load_original_background(config):
    return infer_original_background(
        config["src"]
    )


def render_foreground(config, grid):

    cols = config["cols"]
    rows = config["rows"]
    cell_w = config["cell_w"]
    cell_h = config["cell_h"]
    ramp = config["ramp"]

    width = (
        cols * cell_w
        + PAD * 2
    )
    height = (
        rows * cell_h
        + PAD * 2
    )

    image = Image.new(
        "RGBA",
        (width, height),
        (0, 0, 0, 0),
    )

    draw = ImageDraw.Draw(image)

    font_size = min(
        cell_h * 0.86,
        cell_w / 0.60,
    )

    font = find_font(
        max(1, font_size)
    )

    for y in range(rows):
        baseline = (
            PAD
            + y * cell_h
            + cell_h * 0.78
        )

        for x in range(cols):
            item = grid[y][x]

            # Source coverage was already tested by build_grid. A tone-scaled
            # glyph opacity below that cutoff is still valid visible ink.
            if item["alpha"] <= 0.0:
                continue

            char = ramp[
                item["index"]
            ]

            if char == " ":
                continue

            try:
                rgb = parse_hex(
                    item["color"]
                )
            except (
                ValueError,
                TypeError,
                IndexError,
            ):
                rgb = (17, 17, 17)

            alpha = max(
                0,
                min(
                    255,
                    int(
                        round(
                            item["alpha"]
                            * 255
                        )
                    ),
                ),
            )

            draw.text(
                (
                    PAD
                    + x * cell_w,
                    baseline,
                ),
                char,
                font=font,
                fill=(
                    rgb[0],
                    rgb[1],
                    rgb[2],
                    alpha,
                ),
                anchor="ls",
            )

    return image


def flatten_background(
    foreground,
    background,
):
    if background is None:
        return foreground

    if isinstance(background, Image.Image):
        canvas = background.copy().convert("RGBA")
        if canvas.size != foreground.size:
            canvas = canvas.resize(
                foreground.size,
                Image.Resampling.LANCZOS,
            )
    else:
        canvas = Image.new(
            "RGBA",
            foreground.size,
            background,
        )

    canvas.alpha_composite(foreground)
    return canvas

def reveal_mask(size, progress, animation):
    width, height = size
    progress = max(0.0, min(1.0, progress))
    if progress <= 0:
        return Image.new("L", size, 0)
    if progress >= 1:
        return Image.new("L", size, 255)
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    if animation == "row-reveal":
        draw.rectangle((0, 0, width, math.ceil(height * progress) - 1), fill=255)
    elif animation == "column-reveal":
        draw.rectangle((0, 0, math.ceil(width * progress) - 1, height), fill=255)
    elif animation == "diagonal-reveal":
        extent = (width + height) * progress
        draw.polygon([(0, 0), (extent, 0), (0, extent)], fill=255)
    elif animation == "aperture-reveal":
        draw.polygon(aperture_points(width, height, progress), fill=255)
    elif animation == "circular-reveal":
        radius = math.hypot(width / 2, height / 2) * progress
        draw.ellipse((width / 2 - radius, height / 2 - radius,
                      width / 2 + radius, height / 2 + radius), fill=255)
    else:
        mask.paste(round(255 * progress), (0, 0, width, height))
    return mask


def apply_mask(foreground, mask):
    image = foreground.copy()
    image.putalpha(ImageChops.multiply(foreground.getchannel("A"), mask))
    return image


def mosaic_mask(size, plan, progress):
    """One supersampled coverage union; never one full-size mask per tile."""
    amount = plan.progress(progress)
    if amount in (0., 1.):
        return Image.new('L', size, 255 if amount == 1. else 0)
    width, height = size[0] * 2, size[1] * 2
    mask = Image.new('L', (width, height))
    draw = ImageDraw.Draw(mask)
    sx, sy = width / plan.width, height / plan.height
    for tile in plan.tiles:
        x, y, w, h = tile.rectangle(amount)
        if w <= 0 or h <= 0:
            continue
        # Quantize common boundaries identically; Pillow's last pixel is
        # inclusive whereas the geometric rectangles are half-open.
        # Remove sub-nanopixel arithmetic noise before half-up ties, so the
        # reverse envelope selects the same pixels as the opening envelope.
        left, right = (math.floor(round(value * sx, 9) + .5) for value in (x, x + w))
        top, bottom = (math.floor(round(value * sy, 9) + .5) for value in (y, y + h))
        if right > left and bottom > top:
            draw.rectangle((left, top, right - 1, bottom - 1), fill=255)
    return mask.resize(size, Image.Resampling.BOX)


def apply_mosaic(foreground, config, grid, progress):
    plan = config.get('_mosaic_plan') or mosaic_plan(config, grid)
    if plan.progress(progress) == 1.:
        return foreground
    return apply_mask(foreground, mosaic_mask(foreground.size, plan, progress))


def cell_box(config, size, x, y):
    full_w, full_h = canvas_size(config)
    sx, sy = size[0] / full_w, size[1] / full_h
    return (round((PAD + x * config["cell_w"]) * sx),
            round((PAD + y * config["cell_h"]) * sy),
            round((PAD + (x + 1) * config["cell_w"]) * sx),
            round((PAD + (y + 1) * config["cell_h"]) * sy))


def apply_flag_wave(foreground, progress, strips=12, config=None):
    if config is None:
        config = {"cols": strips * 6, "rows": 1,
                  "cell_w": (foreground.width - PAD * 2) / (strips * 6),
                  "cell_h": foreground.height - PAD * 2}
    width, height = foreground.size
    full_w, full_h = canvas_size(config)
    sx, sy = width / full_w, height / full_h
    result = Image.new("RGBA", foreground.size)
    for col0, col1, values in flag_strips(config["cols"], config["cell_h"], PAD):
        x0 = round((PAD + col0 * config["cell_w"]) * sx)
        x1 = round((PAD + col1 * config["cell_w"]) * sx)
        dy = round(interpolate(values, progress) * sy)
        strip = foreground.crop((x0, 0, x1, height))
        # A straight-alpha image must not be used as its own paste mask.
        result.alpha_composite(strip, (x0, dy))
    return result


def opacity_target_map(config, size, plan):
    """Raster ownership for cell targets; 255 denotes untouched static cells."""
    groups = Image.new("L", size, 255)
    for i, target in enumerate(plan.targets):
        for x, y in target.cells:
            groups.paste(i, cell_box(config, size, x, y))
    return groups


def apply_opacity_plan(foreground, config, progress, grid):
    plan = config.get("_opacity_plan")
    if plan is None:
        plan = opacity_plan(config, grid)
    groups = config.get("_opacity_map")
    if groups is None:
        groups = opacity_target_map(config, foreground.size, plan)
    source_alpha = foreground.getchannel("A")
    alpha = source_alpha.copy()
    for i, target in enumerate(plan.targets):
        exponent = target.envelope.at(progress)
        if exponent == 1:
            continue
        # Same alpha-gamma transfer as SVG feFuncA; never redraw a character,
        # change its RGB, or fill previously transparent pixels.
        table = [round(255 * (value / 255) ** exponent) for value in range(256)]
        mask = groups.point([255 if group == i else 0 for group in range(256)])
        alpha.paste(source_alpha.point(table), (0, 0), mask)
    result = foreground.copy()
    result.putalpha(alpha)
    return result


def apply_sparkle_wave(foreground, progress):
    width, height = foreground.size
    span = width + .35 * height
    half = .12 * span
    center = -half + progress * (span + 2 * half)
    length = math.ceil(span) + 1
    line = Image.new("L", (length, 1))
    line.putdata([round(255 * (1 - .35 * max(0, 1 - abs(x - center) / half))) for x in range(length)])
    field = line.resize((length, height))
    mask = field.transform(foreground.size, Image.Transform.AFFINE,
                           (1, .35, 0, 0, 1, 0), Image.Resampling.BILINEAR)
    return apply_mask(foreground, mask)


def dissolve_map(config, size):
    groups = Image.new("L", size)
    for y in range(config["rows"]):
        for x in range(config["cols"]):
            groups.paste(dissolve_group(x, y), cell_box(config, size, x, y))
    return groups


def cell_reveal_mask(config, size, progress, animation):
    if progress >= 1:
        return Image.new("L", size, 255)
    if progress <= 0:
        return Image.new("L", size, 0)
    if animation == "dissolve":
        groups = config.get("_dissolve_map")
        if groups is None:
            groups = dissolve_map(config, size)
        return groups.point([round(255 * group_visibility(progress, i, DISSOLVE_GROUPS)) for i in range(256)])
    mask = Image.new("L", size)
    for y in range(config["rows"]):
        fraction = group_visibility(progress, y, config["rows"])
        if fraction <= 0:
            continue
        x0, y0, _, y1 = cell_box(config, size, 0, y)
        mask.paste(255, (0, y0, round(fraction * size[0]), y1))
    return mask


def tetris_patches(foreground, config, plan):
    """Partition the existing raster once, with no redraw or alpha multiplication.

    Use the same cell ownership boundaries as Twinkle. Outer cells include
    padding so that partitioning also retains the raster's boundary pixels.
    Only small cropped patches are retained, never a canvas per piece.
    """
    patches = []
    for piece in plan.pieces:
        boxes = []
        for x, y in piece.cells:
            x0, y0, x1, y1 = cell_box(config, foreground.size, x, y)
            boxes.append((0 if x == 0 else x0, 0 if y == 0 else y0,
                          foreground.width if x == config['cols'] - 1 else x1,
                          foreground.height if y == config['rows'] - 1 else y1))
        left, top = min(b[0] for b in boxes), min(b[1] for b in boxes)
        right, bottom = max(b[2] for b in boxes), max(b[3] for b in boxes)
        patch = Image.new('RGBA', (right - left, bottom - top))
        for box in boxes:
            patch.paste(foreground.crop(box), (box[0] - left, box[1] - top))
        if patch.getbbox():
            patches.append((piece, (left, top), patch))
    return tuple(patches)


def apply_tetris(foreground, config, grid, progress):
    plan = config.get('_tetris_plan') or tetris_plan(config, grid)
    # The settled state reuses the authoritative raster exactly, including
    # antialiasing and downsampling. No recomposition at the final frame.
    if all(piece.offset(progress) == 0 for piece in plan.pieces):
        return foreground
    patches = config.get('_tetris_patches')
    if patches is None:
        patches = tetris_patches(foreground, config, plan)
    result = Image.new('RGBA', foreground.size)
    sy = foreground.height / canvas_size(config)[1]
    for piece, (x, y), patch in patches:
        result.alpha_composite(patch, (x, y + round(piece.offset(progress) * sy)))
    return result


def render_rain_layer(size, config, grid, progress):
    """Rasterize only the sparse atmospheric glyphs at GIF export resolution."""
    layer = Image.new("RGBA", size)
    full_w, full_h = canvas_size(config)
    sx, sy = size[0] / full_w, size[1] / full_h
    streams = config.get("_rain_streams")
    if streams is None:
        streams = rain_streams(config, grid)
    font = config.get("_rain_font")
    if font is None:
        font = find_font(min(config["cell_h"] * .86, config["cell_w"] / .60) * sy)
    draw = ImageDraw.Draw(layer)
    colour = parse_hex(RAIN_COLOUR)
    for stream in streams:
        head = stream.position(progress)
        for j, (char, opacity) in enumerate(zip(stream.glyphs, stream.opacities)):
            y = (head - j * config["cell_h"]) * sy
            if -config["cell_h"] * sy <= y <= size[1] + config["cell_h"] * sy:
                draw.text((stream.x * sx, y), char, font=font, anchor="ls",
                          fill=(*colour, round(255 * opacity)))
    return layer


def make_gif_frame(foreground, background, progress, animation, config, grid):
    if animation == "digital-rain":
        backdrop = flatten_background(render_rain_layer(foreground.size, config, grid, progress),
                                      "#ffffff" if background is None else background).convert("RGBA")
        # Source-over artwork is always last. Its RGBA data is never modified.
        return Image.alpha_composite(backdrop, foreground).convert("RGB")
    if animation == "mosaic":
        visible = apply_mosaic(foreground, config, grid, progress)
    elif animation == "tetris":
        visible = apply_tetris(foreground, config, grid, progress)
    elif animation == "flag-wave":
        visible = apply_flag_wave(foreground, progress, config=config)
    elif animation == "twinkle":
        visible = apply_opacity_plan(foreground, dict(config, animation=animation), progress, grid)
    elif animation == "sparkle-wave":
        visible = apply_sparkle_wave(foreground, progress)
    elif animation == "instant":
        visible = foreground
    else:
        p = reveal_progress(progress, repeats(animation, config["loop"]))
        if animation in {"typewriter", "dissolve"}:
            mask = cell_reveal_mask(config, foreground.size, p, animation)
        else:
            mask = reveal_mask(foreground.size, p, animation)
        visible = apply_mask(foreground, mask)
    return flatten_background(visible, "#ffffff" if background is None else background).convert("RGB")


def save_png(
    foreground,
    output,
    background,
    size,
):
    image = flatten_background(
        foreground,
        background,
    )
    image = fit_image(image, size)

    os.makedirs(
        os.path.dirname(output)
        or ".",
        exist_ok=True,
    )

    image.save(output, "PNG")
    return image.size


def save_jpeg(
    foreground,
    output,
    background,
    size,
):
    if background is None:
        background = "#ffffff"

    image = flatten_background(
        foreground,
        background,
    ).convert("RGB")
    image = fit_image(image, size)

    os.makedirs(
        os.path.dirname(output)
        or ".",
        exist_ok=True,
    )

    image.save(
        output,
        "JPEG",
        quality=95,
        optimize=True,
    )
    return image.size


def save_gif(foreground, output, background, animation, speed, loop, config, grid):
    # Animate at the export resolution, rather than keeping dozens of huge
    # source-canvas RGB frames alive. Only palette frames are retained.
    foreground = fit_image(foreground, DEFAULT_GIF_SIZE)
    if isinstance(background, Image.Image):
        background = background.resize(foreground.size, Image.Resampling.LANCZOS)
    config = dict(config, animation=animation, speed=speed, loop=loop)
    plan = None
    if animation == "mosaic":
        config['_mosaic_plan'] = plan = mosaic_plan(config, grid)
    if animation == "tetris":
        config['_tetris_plan'] = plan = tetris_plan(config, grid)
        config['_tetris_patches'] = tetris_patches(foreground, config, plan)
    if animation == "twinkle":
        config["_opacity_plan"] = plan = opacity_plan(config, grid)
        config["_opacity_map"] = opacity_target_map(config, foreground.size, plan)
    if animation == "dissolve":
        config["_dissolve_map"] = dissolve_map(config, foreground.size)
    if animation == "digital-rain":
        config["_rain_streams"] = rain_streams(config, grid)
        scale = foreground.height / canvas_size(config)[1]
        config["_rain_font"] = find_font(min(config["cell_h"] * .86, config["cell_w"] / .60) * scale)
    positions, durations = gif_timeline(animation, speed, loop, plan)

    # One shared palette avoids unrelated colour changes between frames. Train
    # on the static image plus representative phases, including the background.
    samples = [flatten_background(foreground, background or "#ffffff").convert("RGB")]
    for p in (0.0, .25, .5, .75):
        samples.append(make_gif_frame(foreground, background, p, animation, config, grid))
    atlas = Image.new("RGB", (160 * len(samples), 160))
    for i, sample in enumerate(samples):
        atlas.paste(sample.resize((160, 160), Image.Resampling.NEAREST), (160 * i, 0))
    colours = atlas.quantize(colors=256).getpalette()
    # Fill unused slots with an existing colour: GIF otherwise pads them with
    # black, which would introduce colours absent from the trained palette.
    colours += colours[-3:] * ((768 - len(colours)) // 3)
    # A fresh palette avoids retaining the atlas quantizer's RGB lookup cache.
    palette = Image.new("P", (1, 1))
    palette.putpalette(colours)
    del samples
    frames = []
    for p in positions:
        rgb = make_gif_frame(foreground, background, p, animation, config, grid)
        frames.append(rgb.quantize(palette=palette, dither=Image.Dither.NONE))
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    # Keep the global palette fixed while encoding unchanged pixels as deltas.
    # disposal=1 retains those pixels; source transparency was flattened above.
    options = dict(save_all=True, append_images=frames[1:], duration=durations,
                   disposal=1, optimize=True, palette=palette.getpalette())
    if plan.repeat if plan is not None else repeats(animation, loop):
        options["loop"] = 0
    frames[0].save(output, "GIF", **options)
    return frames[0].size


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Create PNG, JPEG, or GIF "
            "ASCII artwork directly "
            "from the source image."
        )
    )

    parser.add_argument(
        "input",
    )

    parser.add_argument(
        "output",
    )

    parser.add_argument(
        "--format",
        choices=(
            "png",
            "jpeg",
            "gif",
        ),
        required=True,
    )

    parser.add_argument(
        "--mode",
        required=True,
    )

    parser.add_argument(
        "--cols",
        required=True,
    )

    parser.add_argument(
        "--rows",
        required=True,
    )

    parser.add_argument(
        "--ramp",
        required=True,
    )

    parser.add_argument(
        "--contrast",
        required=True,
    )

    parser.add_argument(
        "--brightness",
        required=True,
    )

    parser.add_argument(
        "--gamma",
        required=True,
    )

    parser.add_argument(
        "--cell-w",
        required=True,
    )

    parser.add_argument(
        "--cell-h",
        required=True,
    )

    parser.add_argument(
        "--background",
        default="none",
    )

    parser.add_argument(
        "--foreground",
        default="#111111",
    )

    parser.add_argument(
        "--palette",
        default="none",
    )

    parser.add_argument(
        "--animation",
        default="fade",
    )

    parser.add_argument(
        "--speed",
        default="normal",
    )

    parser.add_argument(
        "--loop",
        default="no",
    )

    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(
            f"Input image not found: "
            f"{args.input}"
        )
        raise SystemExit(1)

    try:
        config = make_config(
            args
        )

        grid = build_grid(
            config
        )

        foreground = render_foreground(
            config,
            grid,
        )

        # For JPEG and GIF, a transparent
        # source must become solid because
        # these formats are not our transparent
        # output path.
        background = config["background"]

        if background == "original":
            background = load_original_background(config)
        elif (
            background is None
            and args.format in {"jpeg", "gif"}
        ):
            background = "#ffffff"

        if args.format == "png":
            width, height = save_png(
                foreground,
                args.output,
                background,
                DEFAULT_SIZE,
            )

        elif args.format == "jpeg":
            width, height = save_jpeg(
                foreground,
                args.output,
                background,
                DEFAULT_SIZE,
            )

        else:
            width, height = save_gif(
                foreground,
                args.output,
                background,
                config["animation"],
                config["speed"],
                config["loop"],
                config,
                grid,
            )

    except Exception as exc:
        print(
            f"Export failed: {exc}"
        )
        raise SystemExit(1)

    if config["background"] == "original":
        background_label = "original"
    elif isinstance(background, str):
        background_label = background or "transparent"
    else:
        background_label = "original"

    print(
        f"Created "
        f"{os.path.abspath(args.output)} "
        f"{width}x{height}; "
        f"format={args.format}; "
        f"background={background_label}"
    )


if __name__ == "__main__":
    main()
