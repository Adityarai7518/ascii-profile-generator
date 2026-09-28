
import argparse
import math
import os
import platform
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFont, ImageOps

SCRIPT_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from ascii_renderer import (  # noqa: E402
    ALPHA_THRESHOLD,
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
    source_has_transparency,
    get_twinkle_cells,
    background_is_dark,
    infer_original_background,
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
        max(
            8,
            int(round(font_size)),
        )
    )

    for y in range(rows):
        baseline = (
            PAD
            + y * cell_h
            + cell_h * 0.78
        )

        for x in range(cols):
            item = grid[y][x]

            if item["alpha"] <= ALPHA_THRESHOLD:
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

def reveal_mask(
    size,
    progress,
    animation,
):
    width, height = size

    mask = Image.new(
        "L",
        size,
        0,
    )

    draw = ImageDraw.Draw(mask)

    progress = max(
        0.0,
        min(1.0, progress),
    )

    if animation == "row-reveal":
        draw.rectangle(
            (
                0,
                0,
                width,
                int(height * progress),
            ),
            fill=255,
        )

    elif animation == "column-reveal":
        draw.rectangle(
            (
                0,
                0,
                int(width * progress),
                height,
            ),
            fill=255,
        )

    elif animation == "diagonal-reveal":
        band_width = max(
            1.0,
            math.hypot(width, height) * 0.22,
        )
        travel = width + height + band_width * 2.0
        center_x = -height + progress * travel
        center_y = height / 2.0

        points = [
            (-band_width, 0),
            (band_width, 0),
            (width + band_width, height),
            (width - band_width, height),
        ]
        points = [
            (x + center_x, y)
            for x, y in points
        ]
        draw.polygon(points, fill=255)

    elif animation in {
        "aperture-reveal",
        "circular-reveal",
    }:
        cx = width / 2.0
        cy = height / 2.0
        radius = (
            math.hypot(
                width,
                height,
            )
            * progress
        )

        if animation == "aperture-reveal":
            points = []

            for index in range(8):
                angle = (
                    -math.pi / 2
                    + index
                    * (math.tau / 8)
                )

                points.append(
                    (
                        cx
                        + math.cos(angle)
                        * radius,
                        cy
                        + math.sin(angle)
                        * radius,
                    )
                )

            draw.polygon(
                points,
                fill=255,
            )

        else:
            draw.ellipse(
                (
                    cx - radius,
                    cy - radius,
                    cx + radius,
                    cy + radius,
                ),
                fill=255,
            )

    else:
        draw.rectangle(
            (
                0,
                0,
                width,
                height,
            ),
            fill=int(
                255 * progress
            ),
        )

    return mask


def apply_mask(
    foreground,
    mask,
):
    image = foreground.copy()
    alpha = image.getchannel("A")

    combined = Image.new(
        "L",
        image.size,
        0,
    )

    # Multiply the original glyph alpha
    # by the animation visibility mask.
    from PIL import ImageChops

    combined = ImageChops.multiply(
        alpha,
        mask,
    )

    image.putalpha(
        combined
    )

    return image


def apply_flag_wave(foreground, progress, strips=12):
    width, height = foreground.size
    result = Image.new("RGBA", foreground.size, (0, 0, 0, 0))

    base_amplitude = max(2.0, width * 0.035)
    for index in range(strips):
        x0 = int(round(index * width / strips))
        x1 = int(round((index + 1) * width / strips))
        if x1 <= x0:
            continue

        t = index / max(1, strips - 1)
        amplitude = base_amplitude * (t ** 1.7)
        phase = progress * math.tau - t * math.pi * 1.4
        dx = int(round(math.sin(phase) * amplitude))

        strip = foreground.crop((x0, 0, x1, height))
        result.paste(strip, (x0 + dx, 0), strip)

    return result


def apply_twinkle(foreground, config, progress, grid):
    width, height = foreground.size
    cols = config["cols"]
    rows = config["rows"]
    cell_w = config["cell_w"]
    cell_h = config["cell_h"]

    bg_config = config.get("background")
    if config["mode"] == "dark":
        bg_is_dark = True
    elif config["mode"] == "light":
        bg_is_dark = False
    else:
        if bg_config == "original":
            bg_config = infer_original_background(config["src"])
        if bg_config is not None:
            bg_is_dark = background_is_dark(bg_config)
        else:
            bg_is_dark = True

    ramp = config["ramp"]
    ramp_last = len(ramp) - 1

    cells = get_twinkle_cells(cols, rows, grid, ramp_last)
    if not cells:
        return foreground

    result = foreground.copy().convert("RGBA")
    glint_layer = Image.new("RGBA", foreground.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(glint_layer)

    font_size = min(cell_h * 0.86, cell_w / 0.60)
    font = find_font(max(8, int(round(font_size))))

    duration = {
        "slow": 9.0,
        "normal": 5.5,
        "fast": 2.8,
    }[config["speed"]]

    t = progress * duration

    for i, tcell in enumerate(cells):
        x, y = tcell["x"], tcell["y"]
        item = grid[y][x]
        
        delay = (i / max(1, len(cells) - 1)) * min(1.2, duration * 0.35)
        sparkle_duration = 0.60 + (i % 5) * 0.10

        try:
            base_rgb = parse_hex(item["color"])
        except (ValueError, TypeError, IndexError):
            base_rgb = (17, 17, 17)

        if config["mode"] == "dark":
            enhanced_rgb = (255, 255, 255)
        else:
            amount = 0.88
            if bg_is_dark:
                enhanced_rgb = (
                    int(base_rgb[0] + (255 - base_rgb[0]) * amount),
                    int(base_rgb[1] + (255 - base_rgb[1]) * amount),
                    int(base_rgb[2] + (255 - base_rgb[2]) * amount),
                )
            else:
                target_r, target_g, target_b = base_rgb[0] * 0.15, base_rgb[1] * 0.15, base_rgb[2] * 0.15
                enhanced_rgb = (
                    int(base_rgb[0] + (target_r - base_rgb[0]) * amount),
                    int(base_rgb[1] + (target_g - base_rgb[1]) * amount),
                    int(base_rgb[2] + (target_b - base_rgb[2]) * amount),
                )

        intensity = 0.0
        if t >= delay:
            dt = t - delay
            if config["loop"] == "yes" or dt <= sparkle_duration:
                cycle_t = dt % sparkle_duration
                
                if cycle_t < 0.20 * sparkle_duration:
                    intensity = cycle_t / (0.20 * sparkle_duration)
                else:
                    intensity = 1.0 - (cycle_t - 0.20 * sparkle_duration) / (0.80 * sparkle_duration)
                
                intensity = max(0.0, min(1.0, intensity))

        char = ramp[tcell["glyph_index"]]

        r = int(base_rgb[0] + (enhanced_rgb[0] - base_rgb[0]) * intensity)
        g = int(base_rgb[1] + (enhanced_rgb[1] - base_rgb[1]) * intensity)
        b = int(base_rgb[2] + (enhanced_rgb[2] - base_rgb[2]) * intensity)

        alpha = int(round(255 * item["alpha"]))
        baseline = PAD + y * cell_h + cell_h * 0.78
        px = PAD + x * cell_w

        draw.text(
            (px, baseline),
            char,
            font=font,
            fill=(r, g, b, alpha),
            anchor="ls",
        )

    result.alpha_composite(glint_layer)
    return result


def apply_sparkle_wave(foreground, progress):
    width, height = foreground.size
    stripe_width = max(24.0, height * 0.22)
    center_x = -stripe_width + progress * (width + stripe_width * 2.0)

    mask = Image.new("L", foreground.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rectangle(
        (
            center_x - stripe_width / 2.0,
            -height,
            center_x + stripe_width / 2.0,
            height * 2.0,
        ),
        fill=210,
    )
    mask = mask.rotate(
        -24,
        resample=Image.Resampling.BICUBIC,
        center=(width / 2.0, height / 2.0),
        expand=False,
    )

    bright = ImageEnhance.Brightness(foreground).enhance(1.65)
    bright_alpha = ImageChops.multiply(
        foreground.getchannel("A"),
        mask,
    )
    bright.putalpha(bright_alpha)

    result = foreground.copy()
    result.alpha_composite(bright)
    return result


def make_gif_frame(
    foreground,
    background,
    progress,
    animation,
    config,
    grid,
):
    if animation == "flag-wave":
        visible = apply_flag_wave(
            foreground,
            progress,
        )
    elif animation == "twinkle":
        visible = apply_twinkle(
            foreground,
            config,
            progress,
            grid,
        )
    elif animation == "sparkle-wave":
        visible = apply_sparkle_wave(
            foreground,
            progress,
        )
    elif animation == "instant":
        visible = foreground.copy()
    else:
        visible = apply_mask(
            foreground,
            reveal_mask(
                foreground.size,
                progress,
                animation,
            ),
        )

    if background is None:
        background = "#ffffff"

    return flatten_background(
        visible,
        background,
    ).convert("RGB")


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


def save_gif(
    foreground,
    output,
    background,
    animation,
    speed,
    loop,
    config,
    grid,
):
    if animation == "instant":
        progress_values = [1.0]
        repeat = False
    else:
        frame_count = DEFAULT_GIF_FRAMES
        start_progress = 0.0 if animation == "twinkle" else 0.18
        forward = [
            start_progress
            + (1.0 - start_progress) * index / float(frame_count - 1)
            for index in range(frame_count)
        ]
        repeat = loop == "yes" or animation == "flag-wave"
        
        if animation == "twinkle":
            progress_values = forward
        else:
            progress_values = (
                forward + list(reversed(forward[1:-1]))
                if repeat
                else forward
            )

    if animation == "twinkle":
        twinkle_duration_ms = {
            "slow": 9000,
            "normal": 5500,
            "fast": 2800,
        }[speed]
        duration = max(
            20,
            round(twinkle_duration_ms / DEFAULT_GIF_FRAMES)
        )
    else:
        duration = {
            "slow": 180,
            "normal": 110,
            "fast": 70,
        }[speed]

    frames = [
        fit_image(
            make_gif_frame(
                foreground,
                background,
                progress,
                animation,
                config,
                grid,
            ),
            DEFAULT_GIF_SIZE,
        )
        for progress in progress_values
    ]
    os.makedirs(
        os.path.dirname(output)
        or ".",
        exist_ok=True,
    )
    frames[0].save(
        output,
        "GIF",
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0 if repeat else 1,
        optimize=False,
    )

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
        elif background is None and not source_has_transparency(config["src"]):
            # Preserve the original opaque background state without drawing
            # the original source image itself.
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
