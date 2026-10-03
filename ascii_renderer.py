from PIL import (
    Image,
    ImageChops,
    ImageEnhance,
    ImageOps,
    ImageStat,
    UnidentifiedImageError,
)
import html
import math
import os
import sys


VALID_MODES = {
    "original",
    "light",
    "dark",
    "custom",
    "multicolour",
}

from animations import (
    VALID_ANIMATIONS, SPEED_SETTINGS, DISSOLVE_GROUPS, opacity_plan,
    repeats, duration, reveal_progress, reveal_times, group_visibility,
    dissolve_group, aperture_points, flag_strips, rain_streams, RAIN_COLOUR, tetris_plan,
    mosaic_plan,
)


VALID_SPEEDS = {
    "slow",
    "normal",
    "fast",
}

VALID_LOOP = {
    "yes",
    "no",
}


PAD = 20
ALPHA_THRESHOLD = 0.06

MIN_COLS, MAX_COLS = 20, 300
MIN_ROWS, MAX_ROWS = 10, 200
MAX_CELLS = 50000
MAX_SOURCE_PIXELS = 50_000_000

MIN_CELL_W, MAX_CELL_W = 3, 30
MIN_CELL_H, MAX_CELL_H = 5, 40

DEFAULT_COLS = 120
DEFAULT_ROWS = 64

DEFAULT_CELL_W = 8
DEFAULT_CELL_H = 15

DEFAULT_RAMP = (
    " .,:;irsXA253hMHGS#9B&@"
)

DEFAULT_CONTRAST = 1.10
DEFAULT_BRIGHTNESS = 1.00
DEFAULT_GAMMA = 1.00


# --------------------------------------------------
# Animation timing
# --------------------------------------------------

# --------------------------------------------------
# Validation helpers
# --------------------------------------------------

def fail(message):
    print(
        f"Error: {message}",
        file=sys.stderr,
    )
    raise SystemExit(1)


def is_hex(value):
    if (
        not isinstance(value, str)
        or len(value) != 7
        or not value.startswith("#")
    ):
        return False

    try:
        int(value[1:], 16)
        return True

    except ValueError:
        return False


def hex_rgb(value):
    value = value.lstrip("#")

    return (
        int(value[0:2], 16),
        int(value[2:4], 16),
        int(value[4:6], 16),
    )


def rgb_to_hex(rgb):
    r, g, b = [
        max(
            0,
            min(
                255,
                int(round(value)),
            ),
        )
        for value in rgb
    ]

    return (
        f"#{r:02x}{g:02x}{b:02x}"
    )


def background_is_dark(color):
    r, g, b = hex_rgb(color)

    luminance = (
        0.2126 * r
        + 0.7152 * g
        + 0.0722 * b
    ) / 255.0

    return luminance < 0.45


def lighten_color(
    color,
    amount=0.72,
):
    r, g, b = hex_rgb(color)

    return rgb_to_hex(
        (
            r + (255 - r) * amount,
            g + (255 - g) * amount,
            b + (255 - b) * amount,
        )
    )


def unpremultiply(
    premul,
    alpha,
):
    if alpha <= 0.001:
        return 0.0

    return min(
        255.0,
        (premul * 255.0)
        / alpha,
    )


# --------------------------------------------------
# Arguments
# --------------------------------------------------

def parse_args():

    if len(sys.argv) < 3:
        print(
            "Usage:\n"
            "  python ascii_renderer.py "
            "<input> <output> "
            "[mode] [cols] [rows] [ramp] "
            "[contrast] [brightness] [gamma] "
            "[cell_w] [cell_h] "
            "[background] [foreground] "
            "[palette] [animation] [speed] [loop]"
        )
        raise SystemExit(1)

    try:
        cols = (
            int(sys.argv[4])
            if len(sys.argv) > 4
            else DEFAULT_COLS
        )

        rows = (
            int(sys.argv[5])
            if len(sys.argv) > 5
            else DEFAULT_ROWS
        )

        contrast = (
            float(sys.argv[7])
            if len(sys.argv) > 7
            else DEFAULT_CONTRAST
        )

        brightness = (
            float(sys.argv[8])
            if len(sys.argv) > 8
            else DEFAULT_BRIGHTNESS
        )

        gamma = (
            float(sys.argv[9])
            if len(sys.argv) > 9
            else DEFAULT_GAMMA
        )

        cell_w = (
            int(sys.argv[10])
            if len(sys.argv) > 10
            else DEFAULT_CELL_W
        )

        cell_h = (
            int(sys.argv[11])
            if len(sys.argv) > 11
            else DEFAULT_CELL_H
        )

    except ValueError:
        fail(
            "One or more numeric "
            "arguments are invalid."
        )

    palette_arg = (
        sys.argv[14].strip()
        if len(sys.argv) > 14
        else "none"
    )

    if palette_arg.lower() in {
        "",
        "none",
    }:
        palette = []

    else:
        palette = [
            item.strip().lower()
            for item in
            palette_arg.split(",")
            if item.strip()
        ]

    config = {
        "src": os.path.abspath(
            sys.argv[1]
        ),
        "out": os.path.abspath(
            sys.argv[2]
        ),
        "mode": (
            sys.argv[3]
            if len(sys.argv) > 3
            else "light"
        ),
        "cols": cols,
        "rows": rows,
        "ramp": (
            sys.argv[6]
            if len(sys.argv) > 6
            else DEFAULT_RAMP
        ),
        "contrast": contrast,
        "brightness": brightness,
        "gamma": gamma,
        "cell_w": cell_w,
        "cell_h": cell_h,
        "background": (
            sys.argv[12]
            if len(sys.argv) > 12
            else "#ffffff"
        ),
        "foreground": (
            sys.argv[13]
            if len(sys.argv) > 13
            else "#111111"
        ),
        "palette": palette,
        "animation": (
            sys.argv[15]
            if len(sys.argv) > 15
            else "row-reveal"
        ),
        "speed": (
            sys.argv[16]
            if len(sys.argv) > 16
            else "normal"
        ),
        "loop": (
            sys.argv[17].strip().lower()
            if len(sys.argv) > 17
            else "no"
        ),
    }

    if not os.path.isfile(
        config["src"]
    ):
        fail(
            "Input image not found: "
            f"{config['src']}"
        )

    if (
        config["src"]
        == config["out"]
    ):
        fail(
            "Input and output paths "
            "must be different."
        )

    if (
        config["mode"]
        not in VALID_MODES
    ):
        fail(
            "Unknown color mode: "
            f"{config['mode']}"
        )

    if (
        config["animation"]
        not in VALID_ANIMATIONS
    ):
        fail(
            "Unknown animation: "
            f"{config['animation']}"
        )

    if (
        config["speed"]
        not in VALID_SPEEDS
    ):
        fail(
            "Unknown animation speed: "
            f"{config['speed']}"
        )

    if (
        config["loop"]
        not in VALID_LOOP
    ):
        fail(
            "Loop must be yes or no."
        )

    ramp = config["ramp"]

    if not 2 <= len(ramp) <= 32:
        fail(
            "Character ramp must contain "
            "2 to 32 characters."
        )

    if not ramp.strip():
        fail(
            "Character ramp cannot contain "
            "only whitespace."
        )

    if len(set(ramp)) < 2:
        fail(
            "Character ramp must contain "
            "at least 2 different characters."
        )

    if any(
        not char.isprintable()
        for char in ramp
    ):
        fail(
            "Character ramp must contain "
            "printable characters only."
        )

    if not (
        MIN_COLS
        <= cols
        <= MAX_COLS
    ):
        fail(
            f"Columns must be "
            f"{MIN_COLS}-{MAX_COLS}."
        )

    if not (
        MIN_ROWS
        <= rows
        <= MAX_ROWS
    ):
        fail(
            f"Rows must be "
            f"{MIN_ROWS}-{MAX_ROWS}."
        )

    if cols * rows > MAX_CELLS:
        fail(
            f"The maximum ASCII cell "
            f"count is {MAX_CELLS:,}."
        )

    if not (
        MIN_CELL_W
        <= cell_w
        <= MAX_CELL_W
    ):
        fail(
            f"Character width must be "
            f"{MIN_CELL_W}-{MAX_CELL_W}."
        )

    if not (
        MIN_CELL_H
        <= cell_h
        <= MAX_CELL_H
    ):
        fail(
            f"Character height must be "
            f"{MIN_CELL_H}-{MAX_CELL_H}."
        )

    if not (
        0.05
        <= contrast
        <= 4.0
    ):
        fail(
            "Contrast must be "
            "between 0.05 and 4.0."
        )

    if not (
        0.05
        <= brightness
        <= 4.0
    ):
        fail(
            "Brightness must be "
            "between 0.05 and 4.0."
        )

    if not (
        0.05
        <= gamma
        <= 4.0
    ):
        fail(
            "Gamma must be "
            "between 0.05 and 4.0."
        )

    background = (
        config["background"]
        .strip()
        .lower()
    )

    if background in {
        "",
        "none",
        "transparent",
    }:
        config["background"] = None

    elif background == "original":
        config["background"] = "original"

    elif is_hex(background):
        config["background"] = (
            background
        )

    else:
        fail(
            "Background must be "
            "#RRGGBB, original, none, "
            "or transparent."
        )

    foreground = (
        config["foreground"]
        .strip()
        .lower()
    )

    if not is_hex(foreground):
        fail(
            "Foreground must be "
            "#RRGGBB."
        )

    config["foreground"] = (
        foreground
    )

    if (
        config["mode"]
        == "multicolour"
        and len(config["palette"]) < 2
    ):
        fail(
            "Multicolour mode requires "
            "at least two palette colours."
        )

    for color in config["palette"]:
        if not is_hex(color):
            fail(
                f"Invalid palette color: "
                f"{color}"
            )

    return config


# --------------------------------------------------
# Source image
# --------------------------------------------------

def crop_to_cell_aspect(
    rgb,
    alpha,
    config,
):

    ratio = (
        config["cols"]
        / config["rows"]
    ) * (
        config["cell_w"]
        / config["cell_h"]
    )

    image_ratio = (
        rgb.width
        / rgb.height
    )

    if image_ratio > ratio:

        width = max(
            1,
            int(
                rgb.height
                * ratio
            ),
        )

        left = (
            rgb.width - width
        ) // 2

        box = (
            left,
            0,
            left + width,
            rgb.height,
        )

    else:

        height = max(
            1,
            int(
                rgb.width
                / ratio
            ),
        )

        top = (
            rgb.height - height
        ) // 2

        box = (
            0,
            top,
            rgb.width,
            top + height,
        )

    return (
        rgb.crop(box),
        alpha.crop(box),
        box,
    )


def load_source(src):
    try:
        with Image.open(src) as image:
            if image.width * image.height > MAX_SOURCE_PIXELS:
                fail(
                    "Input image is too large. "
                    f"Maximum supported size is {MAX_SOURCE_PIXELS:,} pixels."
                )

            image = ImageOps.exif_transpose(image)
            return image.convert(
                "RGBA"
            )

    except (
        FileNotFoundError,
        UnidentifiedImageError,
        OSError,
    ) as exc:

        fail(
            "Could not open input image: "
            f"{exc}"
        )


# --------------------------------------------------
# Build ASCII grid
# --------------------------------------------------


def source_has_transparency(src):
    """Return True when the source contains any transparency."""
    source = load_source(src)
    alpha = source.getchannel("A")
    minimum, maximum = alpha.getextrema()
    return minimum < 255


def infer_original_background(src):
    """Return a simple background representation without redrawing the source."""
    source = load_source(src)
    alpha = source.getchannel("A")
    minimum, maximum = alpha.getextrema()

    if minimum < 255:
        return None

    rgb = source.convert("RGB")
    width, height = rgb.size
    border = max(1, min(width, height) // 20)

    regions = [
        (0, 0, width, border),
        (0, height - border, width, height),
        (0, 0, border, height),
        (width - border, 0, width, height),
    ]

    means = [
        ImageStat.Stat(rgb.crop(box)).mean
        for box in regions
    ]

    if not means:
        return "#ffffff"

    count = len(means)
    r = sorted(value[0] for value in means)[count // 2]
    g = sorted(value[1] for value in means)[count // 2]
    b = sorted(value[2] for value in means)[count // 2]
    return rgb_to_hex((r, g, b))


def density_to_index(density, ramp, source_density=0.0):
    last = len(ramp) - 1
    index = max(0, min(last, int(density * last + 0.5)))

    # Nearest rounding gives the blank glyph a nonzero density interval.
    # Reserve that leading blank interval for zero signal. The pre-normalized
    # tone also matters: percentile clipping can erase nonzero source tone.
    # Choose the nearest nonblank level only in this interval; all other bins
    # (including intentional spaces later in a custom ramp) stay unchanged.
    if (density > 0.0 or source_density > 0.0) and not ramp[:index + 1].strip():
        index = next(i for i, char in enumerate(ramp) if not char.isspace())

    return index


def build_grid(config):

    source = load_source(
        config["src"]
    )

    rgb_original = (
        source.convert("RGB")
    )

    alpha_original = (
        source.getchannel("A")
    )

    (
        rgb,
        alpha,
        crop_box,
    ) = crop_to_cell_aspect(
        rgb_original,
        alpha_original,
        config,
    )

    gray_original = (
        ImageOps.grayscale(
            rgb_original
        )
    )

    gray_original = (
        ImageEnhance.Brightness(
            gray_original
        ).enhance(
            config["brightness"]
        )
    )

    if alpha_original.getextrema()[0] < 255:
        # Invisible RGB must not move the contrast pivot. Weight partial
        # coverage as well; a binary mask would overcount antialiased edges.
        alpha_sum = sum(alpha_original.getdata())
        mean = (
            sum(value * coverage for value, coverage in
                zip(gray_original.getdata(), alpha_original.getdata())) / alpha_sum
            if alpha_sum else 0.0
        )
        gray_original = Image.blend(
            Image.new("L", gray_original.size, int(mean + 0.5)),
            gray_original, config["contrast"],
        )
    else:
        gray_original = ImageEnhance.Contrast(gray_original).enhance(config["contrast"])

    gray = (
        gray_original.crop(
            crop_box
        )
    )

    size = (
        config["cols"],
        config["rows"],
    )

    alpha_small = (
        alpha.resize(
            size,
            Image.Resampling.LANCZOS,
        )
    )

    r_small = (
        ImageChops.multiply(
            rgb.getchannel("R"),
            alpha,
        ).resize(
            size,
            Image.Resampling.LANCZOS,
        )
    )

    g_small = (
        ImageChops.multiply(
            rgb.getchannel("G"),
            alpha,
        ).resize(
            size,
            Image.Resampling.LANCZOS,
        )
    )

    b_small = (
        ImageChops.multiply(
            rgb.getchannel("B"),
            alpha,
        ).resize(
            size,
            Image.Resampling.LANCZOS,
        )
    )

    gray_small = (
        ImageChops.multiply(
            gray,
            alpha,
        ).resize(
            size,
            Image.Resampling.LANCZOS,
        )
    )

    ap = alpha_small.load()
    rp = r_small.load()
    gp = g_small.load()
    bp = b_small.load()
    yp = gray_small.load()

    visible = []

    raw_luma = [
        [0.0] * config["cols"]
        for _ in range(config["rows"])
    ]

    alpha_grid = [
        [0.0] * config["cols"]
        for _ in range(config["rows"])
    ]

    for y in range(
        config["rows"]
    ):

        for x in range(
            config["cols"]
        ):

            a = (
                ap[x, y]
                / 255.0
            )

            alpha_grid[y][x] = a

            if (
                a
                > ALPHA_THRESHOLD
            ):

                luminance = (
                    unpremultiply(
                        yp[x, y],
                        ap[x, y],
                    )
                    / 255.0
                )

                raw_luma[y][x] = (
                    luminance
                )

                visible.append(
                    luminance
                )

    if not visible:
        fail(
            "The image contains no "
            "visible pixels."
        )

    visible.sort()

    low = visible[
        max(
            0,
            int(
                (
                    len(visible)
                    - 1
                )
                * 0.02
            ),
        )
    ]

    high = visible[
        min(
            len(visible) - 1,
            int(
                (
                    len(visible)
                    - 1
                )
                * 0.98
            ),
        )
    ]

    if (
        high - low
        < 0.08
    ):
        low = min(
            visible
        )

        high = max(
            visible
        )

    if (
        high - low
        < 1e-6
    ):
        low = max(
            0.0,
            low - 0.5,
        )

        high = min(
            1.0,
            high + 0.5,
        )

        if (
            high - low
            < 1e-6
        ):
            high = min(
                1.0,
                low + 1e-6,
            )

    normalized_grid = [
        [0.0] * config["cols"]
        for _ in range(config["rows"])
    ]

    for y in range(
        config["rows"]
    ):

        for x in range(
            config["cols"]
        ):

            if (
                alpha_grid[y][x]
                <= ALPHA_THRESHOLD
            ):
                continue

            normalized = (
                raw_luma[y][x]
                - low
            ) / (
                high - low
            )

            normalized = max(
                0.0,
                min(
                    1.0,
                    normalized,
                ),
            )

            # Apply S-curve for enhanced midtone separation
            normalized = (
                normalized
                * normalized
                * (3.0 - 2.0 * normalized)
            )

            normalized = (
                normalized
                ** config["gamma"]
            )

            normalized_grid[y][x] = (
                normalized
            )

    # --------------------------------------------------
    # Local contrast
    # --------------------------------------------------

    local_contrast = [
        [0.0] * config["cols"]
        for _ in range(config["rows"])
    ]

    for y in range(
        config["rows"]
    ):

        for x in range(
            config["cols"]
        ):

            if (
                alpha_grid[y][x]
                <= ALPHA_THRESHOLD
            ):
                continue

            center = (
                normalized_grid[y][x]
            )

            total = 0.0
            count = 0

            for dy in (
                -1,
                0,
                1,
            ):

                for dx in (
                    -1,
                    0,
                    1,
                ):

                    if (
                        dx == 0
                        and dy == 0
                    ):
                        continue

                    nx = x + dx
                    ny = y + dy

                    if not (
                        0 <= nx
                        < config["cols"]
                        and
                        0 <= ny
                        < config["rows"]
                    ):
                        continue

                    if (
                        alpha_grid[ny][nx]
                        <= ALPHA_THRESHOLD
                    ):
                        continue

                    total += abs(
                        center
                        - normalized_grid[
                            ny
                        ][
                            nx
                        ]
                    )

                    count += 1

            if count:
                local_contrast[y][x] = (
                    total / count
                )

    contrast_values = [
        local_contrast[y][x]
        for y in range(
            config["rows"]
        )
        for x in range(
            config["cols"]
        )
        if (
            alpha_grid[y][x]
            > ALPHA_THRESHOLD
        )
    ]

    contrast_values.sort()

    if contrast_values:
        contrast_high = (
            contrast_values[
                min(
                    len(
                        contrast_values
                    )
                    - 1,
                    int(
                        (
                            len(
                                contrast_values
                            )
                            - 1
                        )
                        * 0.95
                    ),
                )
            ]
        )

    else:
        contrast_high = 1.0

    if (
        contrast_high
        < 1e-6
    ):
        contrast_high = 1.0

    # --------------------------------------------------
    # Density direction
    # --------------------------------------------------

    if (
        config["mode"]
        == "dark"
    ):
        dark_mapping = True

    elif (
        config["mode"]
        in {
            "custom",
            "multicolour",
        }
        and is_hex(config["background"])
    ):
        dark_mapping = (
            background_is_dark(
                config["background"]
            )
        )

    else:
        dark_mapping = False

    ramp = config["ramp"]

    grid = []

    # --------------------------------------------------
    # Final cell conversion
    # --------------------------------------------------

    for y in range(
        config["rows"]
    ):

        row = []

        for x in range(
            config["cols"]
        ):

            alpha_value = (
                alpha_grid[y][x]
            )

            if (
                alpha_value
                <= ALPHA_THRESHOLD
            ):

                row.append({
                    "index": 0,
                    "alpha": 0.0,
                    "color": config[
                        "foreground"
                    ],
                    "tone": 0.0,
                })

                continue

            normalized = (
                normalized_grid[y][x]
            )

            edge_strength = max(
                0.0,
                min(
                    1.0,
                    local_contrast[y][x]
                    / contrast_high,
                ),
            )

            if dark_mapping:
                base_density = (
                    normalized
                )
            else:
                base_density = (
                    1.0
                    - normalized
                )

            density = (
                base_density * 0.86
                + edge_strength * 0.14
            )

            density = max(
                0.0,
                min(
                    1.0,
                    density,
                ),
            )

            source_density = (
                raw_luma[y][x]
                if dark_mapping
                else 1.0 - raw_luma[y][x]
            )
            index = density_to_index(density, ramp, source_density)

            # --------------------------------------------------
            # Colour selection
            # --------------------------------------------------

            if (
                config["mode"]
                == "original"
            ):

                color = rgb_to_hex(
                    (
                        unpremultiply(
                            rp[x, y],
                            ap[x, y],
                        ),
                        unpremultiply(
                            gp[x, y],
                            ap[x, y],
                        ),
                        unpremultiply(
                            bp[x, y],
                            ap[x, y],
                        ),
                    )
                )

            elif (
                config["mode"]
                == "multicolour"
            ):

                palette = (
                    config["palette"]
                )

                tone = max(
                    0.0,
                    min(
                        1.0,
                        normalized,
                    ),
                )

                scaled = (
                    tone
                    * (
                        len(palette)
                        - 1
                    )
                )

                left = int(
                    math.floor(
                        scaled
                    )
                )

                right = min(
                    len(palette) - 1,
                    left + 1,
                )

                mix = (
                    scaled - left
                )

                c1 = hex_rgb(
                    palette[left]
                )

                c2 = hex_rgb(
                    palette[right]
                )

                color = rgb_to_hex(
                    (
                        c1[0]
                        + (
                            c2[0]
                            - c1[0]
                        )
                        * mix,

                        c1[1]
                        + (
                            c2[1]
                            - c1[1]
                        )
                        * mix,

                        c1[2]
                        + (
                            c2[2]
                            - c1[2]
                        )
                        * mix,
                    )
                )

            else:

                color = config[
                    "foreground"
                ]

            if (
                config["mode"]
                not in ("original", "light", "multicolour")
            ):
                # Opacity as secondary luminance cue
                tone_opacity = (
                    0.35
                    + 0.65
                    * base_density
                )

                alpha_value = (
                    alpha_grid[y][x]
                    * tone_opacity
                )

            row.append({
                "index": index,
                "alpha": alpha_value,
                "color": color,
                "tone": normalized,
            })

        grid.append(row)

    return grid


# --------------------------------------------------
# SVG helpers
# --------------------------------------------------

def esc(text):
    return html.escape(text)


def _svg_twinkle_opacity(alpha, envelope):
    """Serialize a**e(t), including the curve between exponent keyframes.

    Linear opacity interpolation would change the shared gamma waveform.
    Cubic Hermite segments with linear Bezier time approximate the exponential
    with alpha error below 1e-7, before static six-decimal endpoint rounding.
    The Hermite remainder is bounded by max(alpha) * log_ratio**4 / 384.
    This is SVG serialization only; the shared envelope is never changed.
    """
    times = [envelope.times[0]]
    values = [f'{alpha:.6f}']
    splines = []
    for t0, t1, e0, e1 in zip(envelope.times, envelope.times[1:],
                             envelope.values, envelope.values[1:]):
        k = math.log(alpha) * (e1 - e0)
        maximum = max(alpha ** e0, alpha ** e1)
        count = max(1, math.ceil(abs(k) / 2),
                    math.ceil((maximum * k ** 4 / (384 * 1e-7)) ** .25))
        for step in range(count):
            left = e0 + (e1 - e0) * step / count
            right = e1 if step + 1 == count else e0 + (e1 - e0) * (step + 1) / count
            a, b = alpha ** left, alpha ** right
            if a == b:
                y1, y2 = 1 / 3, 2 / 3
            else:
                y1 = (k / count) * a / (3 * (b - a))
                y2 = 1 - (k / count) * b / (3 * (b - a))
            splines.append(f'0.333333333333 {y1:.12f} 0.666666666667 {y2:.12f}')
            times.append(t1 if step + 1 == count else t0 + (t1 - t0) * (step + 1) / count)
            values.append(f'{alpha:.6f}' if right == 1 else f'{b:.9f}')
    return values, times, ';'.join(splines)


def get_twinkle_cells(cols, rows, grid, ramp_last, rng_seed=20260926, ramp=None):
    """Compatibility helper: return the actual glyphs targeted by the plan."""
    config = dict(animation="twinkle", speed="normal", loop="no",
                  ramp=ramp if ramp is not None else " " + "@" * ramp_last)
    plan = opacity_plan(config, grid, rng_seed)
    return [dict(x=x, y=y, glyph_index=grid[y][x]["index"])
            for target in plan.targets for x, y in target.cells]


def render_svg(config, grid):
    """Serialize the authoritative grid once, then animate its existing ink."""
    cols, rows = config["cols"], config["rows"]
    cw, ch = config["cell_w"], config["cell_h"]
    width, height = cols * cw + PAD * 2, rows * ch + PAD * 2
    ramp, animation = config["ramp"], config["animation"]
    repeat = repeats(animation, config["loop"])
    seconds = duration(animation, config["speed"])
    repeat_attr = 'repeatCount="indefinite"' if repeat else 'fill="freeze"'
    font_size = min(ch * .86, cw / .60)
    background = config["background"]
    if background == "original":
        background = infer_original_background(config["src"])

    def animate(attribute, values, times, transform=False, extra=""):
        tag = "animateTransform" if transform else "animate"
        return (f'<{tag} attributeName="{attribute}" values="{";".join(map(str, values))}" '
                f'keyTimes="{";".join(f"{t:.9f}" for t in times)}" '
                f'dur="{seconds:.3f}s" {repeat_attr} {extra}/>')

    plan = opacity_plan(config, grid) if animation == "twinkle" else None
    if plan is not None:
        seconds = plan.seconds
        repeat_attr = 'repeatCount="indefinite"' if plan.repeat else 'fill="freeze"'
    glyph_animations = {}
    if plan is not None:
        for target in plan.targets:
            for x, y in target.cells:
                alpha = grid[y][x]["alpha"]
                # Envelopes contain gamma exponents, not opacity values.
                # Use the static serializer's exact alpha at identity, including
                # its precision, so frozen SMIL and unanimated ink agree.
                values, times, splines = _svg_twinkle_opacity(alpha, target.envelope)
                glyph_animations[x, y] = animate(
                    'opacity', values, times, extra=f'calcMode="spline" keySplines="{splines}"')
    elif animation == "tetris":
        assembly = tetris_plan(config, grid)
        seconds = assembly.seconds
        repeat_attr = 'repeatCount="indefinite"' if assembly.repeat else 'fill="freeze"'
        for piece in assembly.pieces:
            for x, y in piece.cells:
                # tspan transforms are ignored by Chromium and WebKit. Absolute
                # y animates one glyph without accumulating the preceding
                # glyph's offset, while retaining its original text row.
                baseline = float(f'{PAD + y * ch + ch * .78:.3f}')
                glyph_animations[x, y] = animate(
                    'y', [f'{baseline + dy:.6f}' for dy in piece.offsets], piece.times)

    dissolve_rows = None
    if animation == "dissolve":
        dissolve_rows = [[[] for _ in range(rows)] for _ in range(DISSOLVE_GROUPS)]
        for y in range(rows):
            for x in range(cols):
                dissolve_rows[dissolve_group(x, y)][y].append(x)

    def row_text(y, x0=0, x1=None, group=None):
        spans = []
        columns = dissolve_rows[group][y] if group is not None else range(x0, cols if x1 is None else x1)
        for x in columns:
            item = grid[y][x]
            char = ramp[item["index"]]
            if item["alpha"] <= 0 or char.isspace():
                continue
            # Explicit positions avoid cumulative font/fallback advance errors.
            spans.append(f'<tspan x="{PAD + x * cw:.3f}" fill="{item["color"]}" '
                         f'opacity="{item["alpha"]:.6f}">{esc(char)}'
                         + glyph_animations.get((x, y), '') + '</tspan>')
        if not spans:
            return ""
        return (f'<text y="{PAD + y * ch + ch * .78:.3f}" xml:space="preserve">'
                + "".join(spans) + '</text>')

    def base():
        return "".join(row_text(y) for y in range(rows))

    def points(values):
        return " ".join(f"{x:.4f},{y:.4f}" for x, y in values)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}" font-family="Menlo, SFMono-Regular, Consolas, monospace" '
             f'font-size="{font_size:.3f}" font-kerning="none" style="font-variant-ligatures:none">']
    if background is not None:
        parts.append(f'<rect width="{width}" height="{height}" fill="{background}"/>')
    times = reveal_times(repeat=repeat)
    progress = [reveal_progress(t, repeat) for t in times]

    if animation == "instant":
        parts.append(base())
    elif animation == "mosaic":
        mosaic = mosaic_plan(config, grid)
        seconds = mosaic.seconds
        repeat_attr = 'repeatCount="indefinite"' if mosaic.repeat else 'fill="freeze"'
        parts.append('<defs><clipPath id="mosaic-clip" clipPathUnits="userSpaceOnUse">')
        for tile in mosaic.tiles:
            times, rectangles = tile.keyframes(mosaic.repeat)
            attributes = ('x', 'y', 'width', 'height')
            # Unanimated fallback is complete; active SMIL supplies the empty
            # starting aperture. Artwork itself is serialized only below.
            full = tile.rectangle(1.)
            parts.append('<rect ' + ' '.join(f'{name}="{value:.6f}"'
                         for name, value in zip(attributes, full)) + '>')
            for i, name in enumerate(attributes):
                parts.append(animate(name, [f'{rect[i]:.6f}' for rect in rectangles], times))
            parts.append('</rect>')
        times, widths = mosaic.completion_keyframes()
        parts.append(f'<rect width="{width}" height="{height}">')
        parts.append(animate('width', widths, times, extra='calcMode="discrete"'))
        parts.append('</rect></clipPath></defs><g id="artwork" clip-path="none">')
        # Even an all-open clip can change browser text alpha rounding. Remove
        # clipping during completion so the static glyphs rasterize identically.
        parts.append(animate('clip-path', ['none' if w else 'url(#mosaic-clip)' for w in widths],
                             times, extra='calcMode="discrete"'))
        parts.append(base())
        parts.append('</g>')
    elif animation == "tetris":
        parts.append(base())
    elif animation == "digital-rain":
        parts.append(f'<defs><clipPath id="rain-bounds"><rect width="{width}" '
                     f'height="{height}"/></clipPath></defs>'
                     '<g id="digital-rain" clip-path="url(#rain-bounds)" '
                     f'fill="{RAIN_COLOUR}">')
        for stream in rain_streams(config, grid):
            times, positions = stream.keyframes()
            trail = ''.join(f'<text x="{stream.x:.6f}" y="{-j * ch:.6f}" '
                            f'opacity="{opacity:.6f}">{esc(char)}</text>'
                            for j, (char, opacity) in enumerate(zip(stream.glyphs, stream.opacities)))
            movement = animate('transform', [f'0 {y:.6f}' for y in positions], times,
                               transform=True, extra='type="translate"')
            parts.append('<g>' + trail + movement + '</g>')
        parts.append('</g><g id="artwork">' + base() + '</g>')
    elif animation == "twinkle":
        parts.append(base())
    elif animation == "fade":
        parts.append('<g opacity="0">' + base() + animate("opacity", progress, times) + '</g>')
    elif animation in {"row-reveal", "column-reveal", "diagonal-reveal", "aperture-reveal", "circular-reveal"}:
        if animation == "row-reveal":
            shape = (f'<rect width="{width}" height="0">' +
                     animate("height", [height * p for p in progress], times) + '</rect>')
        elif animation == "column-reveal":
            shape = (f'<rect width="0" height="{height}">' +
                     animate("width", [width * p for p in progress], times) + '</rect>')
        elif animation == "diagonal-reveal":
            values = [points([(0, 0), ((width + height) * p, 0), (0, (width + height) * p)]) for p in progress]
            shape = '<polygon points="0,0 0,0 0,0">' + animate("points", values, times) + '</polygon>'
        elif animation == "aperture-reveal":
            values = [points(aperture_points(width, height, p)) for p in progress]
            shape = f'<polygon points="{values[0]}">' + animate("points", values, times) + '</polygon>'
        else:
            values = [math.hypot(width / 2, height / 2) * p for p in progress]
            shape = f'<circle cx="{width / 2}" cy="{height / 2}" r="0">' + animate("r", values, times) + '</circle>'
        parts.append('<defs><clipPath id="reveal">' + shape + '</clipPath></defs>' +
                     '<g clip-path="url(#reveal)">' + base() + '</g>')
    elif animation == "typewriter":
        for y in range(rows):
            times = reveal_times(y / rows, (y + 1) / rows, repeat)
            values = [width * group_visibility(reveal_progress(t, repeat), y, rows) for t in times]
            # Each group contains one row, so full-canvas clipping also keeps
            # accents and fallback glyph overhang intact at the final state.
            parts.append(f'<clipPath id="row-{y}"><rect x="0" y="0" '
                         f'width="0" height="{height}">' + animate("width", values, times) + '</rect></clipPath>' +
                         f'<g clip-path="url(#row-{y})">' + row_text(y) + '</g>')
    elif animation == "dissolve":
        for group in range(DISSOLVE_GROUPS):
            times = reveal_times(group / DISSOLVE_GROUPS, (group + 1) / DISSOLVE_GROUPS, repeat)
            values = [group_visibility(reveal_progress(t, repeat), group, DISSOLVE_GROUPS) for t in times]
            content = "".join(row_text(y, group=group) for y in range(rows))
            parts.append('<g opacity="0">' + content + animate("opacity", values, times) + '</g>')
    elif animation == "sparkle-wave":
        span = width + .35 * height
        half = .12 * span
        movement = animate("gradientTransform", [f'{-half} 0', f'{span + half} 0'], [0, 1],
                           transform=True, extra='type="translate" additive="sum"')
        parts.append(f'<defs><linearGradient id="wave" gradientUnits="userSpaceOnUse" '
                     f'x1="{-half}" x2="{half}" y1="0" y2="0" gradientTransform="matrix(1 0 -.35 1 0 0)">'
                     '<stop offset="0" stop-color="white" stop-opacity="1"/>'
                     '<stop offset=".5" stop-color="white" stop-opacity=".65"/>'
                     '<stop offset="1" stop-color="white" stop-opacity="1"/>' + movement + '</linearGradient>'
                     f'<mask id="wave-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="{width}" height="{height}">'
                     f'<rect width="{width}" height="{height}" fill="url(#wave)"/></mask></defs>'
                     '<g mask="url(#wave-mask)">' + base() + '</g>')
    elif animation == "flag-wave":
        for x0, x1, values in flag_strips(cols, ch, PAD):
            content = "".join(row_text(y, x0, x1) for y in range(rows))
            times = [i / (len(values) - 1) for i in range(len(values))]
            movement = animate("transform", [f'0 {v:.6f}' for v in values], times,
                               transform=True, extra='type="translate"')
            parts.append('<g>' + content + movement + '</g>')
    parts.append('</svg>')
    return "".join(parts)


def main():
    config = parse_args()
    grid = build_grid(config)
    svg = render_svg(config, grid)
    try:
        os.makedirs(os.path.dirname(config["out"]) or ".", exist_ok=True)
        with open(config["out"], "w", encoding="utf-8") as fh:
            fh.write(svg)
    except OSError as exc:
        fail(f"Could not write output SVG: {exc}")
    width = config["cols"] * config["cell_w"] + PAD * 2
    height = config["rows"] * config["cell_h"] + PAD * 2
    print(f"Created {config['out']} {len(svg)} bytes; {width}x{height}; "
          f"mode={config['mode']}; animation={config['animation']}; "
          f"speed={config['speed']}; loop={'yes' if repeats(config['animation'], config['loop']) else 'no'}")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nGeneration cancelled.")
        raise SystemExit(130)
