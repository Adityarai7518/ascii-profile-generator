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
import random
import sys


VALID_MODES = {
    "original",
    "light",
    "dark",
    "custom",
    "multicolour",
}

VALID_ANIMATIONS = {
    "row-reveal",
    "column-reveal",
    "diagonal-reveal",
    "aperture-reveal",
    "circular-reveal",
    "fade",
    "twinkle",
    "sparkle-wave",
    "flag-wave",
    "instant",
}

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

SPEED_SETTINGS = {
    "slow": {
        "reveal": 9.0,
        "loop": 9.0,
    },
    "normal": {
        "reveal": 5.5,
        "loop": 5.5,
    },
    "fast": {
        "reveal": 2.8,
        "loop": 3.0,
    },
}


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

    gray_original = (
        ImageEnhance.Contrast(
            gray_original
        ).enhance(
            config["contrast"]
        )
    )

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
    ramp_last = (
        len(ramp) - 1
    )

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

            if (
                config["mode"]
                == "original"
                and config["background"]
                is None
            ):

                index = (
                    1
                    + int(
                        round(
                            density
                            * (
                                ramp_last
                                - 1
                            )
                        )
                    )
                )

                index = min(
                    ramp_last,
                    index,
                )

            else:

                index = int(
                    density
                    * ramp_last
                    + 0.5
                )

                index = max(
                    0,
                    min(
                        ramp_last,
                        index,
                    ),
                )

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
                != "original"
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

    if not dark_mapping:
        updates = []
        for y in range(config["rows"]):
            for x in range(config["cols"]):
                if grid[y][x]["index"] == 0 and grid[y][x]["alpha"] > 0.0:
                    visible_neighbors = 0
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            if dy == 0 and dx == 0:
                                continue
                            ny, nx = y + dy, x + dx
                            if 0 <= ny < config["rows"] and 0 <= nx < config["cols"]:
                                if grid[ny][nx]["index"] > 0:
                                    visible_neighbors += 1
                    if visible_neighbors >= 5:
                        updates.append((x, y))
        
        for x, y in updates:
            grid[y][x]["index"] = 1

        # SECOND PASS: Structural opacity correction
        bg_rgb = None
        if config["mode"] == "light":
            bg_rgb = (255, 255, 255)
        else:
            bg_config = config.get("background")
            if bg_config == "original":
                bg_config = infer_original_background(config["src"])
            if bg_config is not None and bg_config != "none":
                try:
                    bg_rgb = hex_rgb(bg_config)
                except (ValueError, TypeError, IndexError):
                    pass

        if bg_rgb is not None:
            bg_luma = 0.2126 * bg_rgb[0] + 0.7152 * bg_rgb[1] + 0.0722 * bg_rgb[2]
            if bg_luma > 200:
                for y in range(config["rows"]):
                    for x in range(config["cols"]):
                        item = grid[y][x]
                        
                        if item["alpha"] <= 0.0:
                            continue
                            
                        if (
                            item["alpha"] < 0.50
                            and item["index"] < 4
                        ):
                            visible_neighbors = 0
                            for dy in (-1, 0, 1):
                                for dx in (-1, 0, 1):
                                    if dy == 0 and dx == 0:
                                        continue
                                    ny, nx = y + dy, x + dx
                                    if 0 <= ny < config["rows"] and 0 <= nx < config["cols"]:
                                        if grid[ny][nx]["index"] > 0:
                                            visible_neighbors += 1
                                            
                            if visible_neighbors >= 4:
                                if item["tone"] < 0.72:
                                    if item["alpha"] < 0.25:
                                        item["alpha"] = 0.55
                                    else:
                                        item["alpha"] = max(item["alpha"], 0.50)
                                elif item["tone"] < 0.88:
                                    item["alpha"] = max(item["alpha"], 0.42)

    return grid


# --------------------------------------------------
# SVG helpers
# --------------------------------------------------

def esc(text):
    return html.escape(text)


def get_twinkle_cells(cols, rows, grid, ramp_last, rng_seed=20260926):
    cells = [
        (x, y)
        for y in range(rows)
        for x in range(cols)
        if grid[y][x]["alpha"] > ALPHA_THRESHOLD and grid[y][x]["index"] > 0
    ]

    if not cells:
        return []

    limit = min(
        80,
        max(
            30,
            cols * rows // 110,
        ),
    )

    if len(cells) > limit:
        step = (len(cells) - 1) / max(1, limit - 1)
        cells = [
            cells[int(round(i * step))]
            for i in range(limit)
        ]

    rng = random.Random(rng_seed)
    rng.shuffle(cells)

    results = []
    for x, y in cells:
        item = grid[y][x]
        cell_rng = random.Random(f"{rng_seed}_{x}_{y}")
        choice = cell_rng.random()
        if choice < 0.25:
            offset = 1
        elif choice < 0.75:
            offset = 2
        else:
            offset = 3
            
        glyph_index = min(ramp_last, item["index"] + offset)
        results.append({
            "x": x,
            "y": y,
            "glyph_index": glyph_index,
        })

    return results


def main():

    config = parse_args()

    grid = build_grid(
        config
    )

    cols = config["cols"]
    rows = config["rows"]

    cell_w = config["cell_w"]
    cell_h = config["cell_h"]

    ramp = config["ramp"]
    ramp_last = len(ramp) - 1

    art_w = (
        cols * cell_w
    )

    art_h = (
        rows * cell_h
    )

    canvas_w = (
        art_w
        + PAD * 2
    )

    canvas_h = (
        art_h
        + PAD * 2
    )

    timing = SPEED_SETTINGS[
        config["speed"]
    ]

    repeat = (
        config["loop"]
        == "yes"
    )

    repeat_attr = (
        'repeatCount="indefinite"'
        if repeat
        else 'fill="freeze"'
    )

    font_size = min(
        cell_h * 0.86,
        cell_w / 0.60,
    )

    glyph_width = (
        font_size * 0.60
    )

    letter_spacing = max(
        0.0,
        cell_w - glyph_width,
    )

    def row_y(y):
        return (
            PAD
            + y * cell_h
            + cell_h * 0.78
        )

    def cell_span(item):
        if (
            item["alpha"]
            <= ALPHA_THRESHOLD
        ):
            return " "

        char = ramp[
            item["index"]
        ]

        if char == " ":
            return " "

        return (
            f'<tspan '
            f'fill="{item["color"]}" '
            f'opacity="{item["alpha"]:.3f}">'
            f'{esc(char)}'
            f'</tspan>'
        )

    def row_text(y):
        spans = [
            cell_span(item)
            for item in grid[y]
        ]

        return (
            f'<text '
            f'x="{PAD}" '
            f'y="{row_y(y):.1f}" '
            f'font-size="{font_size:.1f}" '
            f'letter-spacing="{letter_spacing:.3f}" '
            f'xml:space="preserve">'
            f'{"".join(spans)}'
            f'</text>'
        )

    def row_slice_text(
        y,
        x0,
        x1,
    ):
        spans = [
            cell_span(
                grid[y][x]
            )
            for x in range(
                x0,
                x1,
            )
        ]

        return (
            f'<text '
            f'x="{PAD + x0 * cell_w}" '
            f'y="{row_y(y):.1f}" '
            f'font-size="{font_size:.1f}" '
            f'letter-spacing="{letter_spacing:.3f}" '
            f'xml:space="preserve">'
            f'{"".join(spans)}'
            f'</text>'
        )

    def render_base():
        return "".join(
            row_text(y)
            for y in range(
                rows
            )
        )

    def highlight_color(
        item,
        amount=0.88,
    ):
        if config["mode"] == "dark":
            bg_is_dark = True
        elif config["mode"] == "light":
            bg_is_dark = False
        else:
            if background is not None:
                bg_is_dark = background_is_dark(background)
            else:
                bg_is_dark = True

        r, g, b = hex_rgb(item["color"])

        if bg_is_dark:
            return rgb_to_hex(
                (
                    r + (255 - r) * amount,
                    g + (255 - g) * amount,
                    b + (255 - b) * amount,
                )
            )
        else:
            target_r, target_g, target_b = r * 0.15, g * 0.15, b * 0.15
            return rgb_to_hex(
                (
                    r + (target_r - r) * amount,
                    g + (target_g - g) * amount,
                    b + (target_b - b) * amount,
                )
            )

    def denser(
        index,
        amount=2,
    ):
        return ramp[
            min(
                ramp_last,
                index + amount,
            )
        ]

    def visible_cells():
        return [
            (x, y)
            for y in range(
                rows
            )
            for x in range(
                cols
            )
            if (
                grid[y][x]["alpha"]
                > ALPHA_THRESHOLD
                and
                grid[y][x]["index"]
                > 0
            )
        ]

    # --------------------------------------------------
    # Twinkle
    # --------------------------------------------------

    def twinkle():

        twinkle_cells = get_twinkle_cells(
            cols,
            rows,
            grid,
            ramp_last,
        )

        if not twinkle_cells:
            return ""

        parts = []

        duration = timing[
            "loop"
        ]

        for i, tcell in enumerate(twinkle_cells):
            x = tcell["x"]
            y = tcell["y"]
            
            item = grid[y][x]

            px = (
                PAD
                + x * cell_w
            )

            py = row_y(y)

            char = ramp[tcell["glyph_index"]]

            color = highlight_color(
                item
            )

            delay = (
                i
                / max(1, len(twinkle_cells) - 1)
                * min(
                    1.2,
                    duration * 0.35,
                )
            )

            sparkle_duration = (
                0.60
                + (i % 5) * 0.10
            )

            base_color = item["color"]
            base_opacity = item["alpha"]

            parts.append(
                f'<text '
                f'x="{px}" '
                f'y="{py:.1f}" '
                f'fill="{base_color}" '
                f'font-size="'
                f'{font_size:.1f}" '
                f'opacity="{base_opacity:.3f}">'
                f'{esc(char)}'
                f'<animate '
                f'attributeName="fill" '
                f'values="{base_color};{color};{base_color}" '
                f'keyTimes="0;0.2;1" '
                f'dur="{sparkle_duration:.2f}s" '
                f'begin="{delay:.3f}s" '
                f'{repeat_attr}/>'
                f'</text>'
            )

        return "".join(
            parts
        )

    # --------------------------------------------------
    # Sparkle Wave
    # --------------------------------------------------

    def sparkle_wave():

        stripe_width = max(
            cell_w * 5.0,
            canvas_h * 0.22,
        )

        duration = timing[
            "loop"
        ]

        start_x = (
            -stripe_width
            - canvas_h * 0.5
        )

        end_x = (
            canvas_w
            + stripe_width
            + canvas_h * 0.5
        )

        if repeat:

            x_values = (
                f"{start_x:.1f};"
                f"{end_x:.1f};"
                f"{start_x:.1f}"
            )

            x_times = (
                "0;0.72;1"
            )

        else:

            x_values = (
                f"{start_x:.1f};"
                f"{end_x:.1f}"
            )

            x_times = "0;1"

        cells = visible_cells()

        limit = min(120, max(30, cols * rows // 70))
        if len(cells) > limit:
            step = (len(cells) - 1) / max(1, limit - 1)
            cells = [
                cells[int(round(i * step))]
                for i in range(limit)
            ]

        highlight_parts = []

        for x, y in cells:

            item = grid[y][x]

            char = denser(
                item["index"],
                2,
            )

            px = (
                PAD
                + x * cell_w
            )

            py = row_y(y)

            color = highlight_color(
                item,
                0.82,
            )

            highlight_parts.append(
                f'<text '
                f'x="{px}" '
                f'y="{py:.1f}" '
                f'fill="{color}" '
                f'opacity="{min(1.0, item["alpha"] * 1.10):.3f}" '
                f'font-size="{font_size:.1f}">'
                f'{esc(char)}'
                f'</text>'
            )

        return (
            f'<clipPath '
            f'id="sparkle-wave-clip">'
            f'<rect '
            f'x="{start_x:.1f}" '
            f'y="{-canvas_h:.1f}" '
            f'width="{stripe_width:.1f}" '
            f'height="{canvas_h * 3:.1f}" '
            f'transform="rotate('
            f'-24 '
            f'{canvas_w / 2:.1f} '
            f'{canvas_h / 2:.1f})">'
            f'<animate '
            f'attributeName="x" '
            f'values="{x_values}" '
            f'keyTimes="{x_times}" '
            f'dur="{duration:.2f}s" '
            f'{repeat_attr}/>'
            f'</rect>'
            f'</clipPath>'
            f'<g '
            f'clip-path="url(#sparkle-wave-clip)">'
            f'{"".join(highlight_parts)}'
            f'</g>'
        )

    # --------------------------------------------------
    # Iris Aperture
    # --------------------------------------------------

    def polygon_points(
        cx,
        cy,
        radius,
        sides=8,
        rotation=-22.5,
    ):
        points = []

        for i in range(
            sides
        ):

            angle = math.radians(
                rotation
                + i
                * (
                    360.0
                    / sides
                )
            )

            x = (
                cx
                + math.cos(angle)
                * radius
            )

            y = (
                cy
                + math.sin(angle)
                * radius
            )

            points.append(
                f"{x:.1f},{y:.1f}"
            )

        return " ".join(
            points
        )

    def iris_reveal():

        cx = (
            canvas_w / 2
        )

        cy = (
            canvas_h / 2
        )

        closed_radius = 1.5

        open_radius = (
            math.hypot(
                canvas_w / 2,
                canvas_h / 2,
            )
            * 1.08
        )

        closed = polygon_points(
            cx,
            cy,
            closed_radius,
        )

        opened = polygon_points(
            cx,
            cy,
            open_radius,
        )

        if repeat:

            point_values = (
                f"{closed};"
                f"{opened};"
                f"{closed}"
            )

            point_times = (
                "0;0.72;1"
            )

            rotation_values = (
                "0;7;0"
            )

            rotation_times = (
                "0;0.72;1"
            )

        else:

            point_values = (
                f"{closed};"
                f"{opened}"
            )

            point_times = "0;1"

            rotation_values = (
                "0;7"
            )

            rotation_times = "0;1"

        return (
            f'<clipPath '
            f'id="iris-reveal">'
            f'<polygon '
            f'points="{closed}">'
            f'<animate '
            f'attributeName="points" '
            f'values="{point_values}" '
            f'keyTimes="{point_times}" '
            f'dur="{timing["reveal"]:.2f}s" '
            f'{repeat_attr}/>'
            f'<animateTransform '
            f'attributeName="transform" '
            f'type="rotate" '
            f'values="'
            f'{rotation_values}" '
            f'keyTimes="'
            f'{rotation_times}" '
            f'dur="{timing["reveal"]:.2f}s" '
            f'{repeat_attr} '
            f'additive="sum"/>'
            f'</polygon>'
            f'</clipPath>'
            f'<g '
            f'clip-path="'
            f'url(#iris-reveal)">'
            f'{render_base()}'
            f'</g>'
        )

    # --------------------------------------------------
    # Flag Wave
    # --------------------------------------------------

    def flag_wave():

        duration = max(
            4.0,
            timing["loop"],
        )

        # Only a small number of vertical
        # fabric strips are animated.
        # This keeps the SVG practical while
        # retaining a convincing travelling wave.
        strip_count = min(
            20,
            max(
                8,
                cols // 6,
            ),
        )

        strip_width = (
            cols
            / strip_count
        )

        parts = []

        for strip in range(
            strip_count
        ):

            x0 = int(
                round(
                    strip
                    * strip_width
                )
            )

            x1 = int(
                round(
                    (strip + 1)
                    * strip_width
                )
            )

            x0 = max(
                0,
                min(
                    cols - 1,
                    x0,
                ),
            )

            x1 = max(
                x0 + 1,
                min(
                    cols,
                    x1,
                ),
            )

            center_x = (
                (
                    x0
                    + x1
                    - 1
                )
                / 2.0
            )

            progress = (
                center_x
                / max(
                    1,
                    cols - 1,
                )
            )

            # Keep the hoist/pole nearly
            # stable and make the free edge
            # move more strongly.
            fabric_progress = max(
                0.0,
                (
                    progress
                    - 0.16
                )
                / 0.84,
            )

            amplitude = (
                fabric_progress
                ** 1.65
            ) * (
                cell_h * 1.25
            )

            # Slightly different phase
            # for every strip creates
            # the travelling fabric wave.
            phase = (
                progress
                * duration
                * 0.80
            )

            strip_parts = []

            for y in range(
                rows
            ):
                strip_parts.append(
                    row_slice_text(
                        y,
                        x0,
                        x1,
                    )
                )

            if repeat:

                values = (
                    "0,0;"
                    f"0,{-amplitude:.2f};"
                    "0,0;"
                    f"0,{amplitude:.2f};"
                    "0,0"
                )

                key_times = (
                    "0;0.25;0.5;0.75;1"
                )

            else:

                values = (
                    "0,0;"
                    f"0,{-amplitude:.2f};"
                    f"0,{-amplitude * 0.35:.2f};"
                    "0,0"
                )

                key_times = (
                    "0;0.35;0.72;1"
                )

            parts.append(
                f'<g '
                f'transform="translate(0,0)">'
                f'{"".join(strip_parts)}'
                f'<animateTransform '
                f'attributeName="transform" '
                f'type="translate" '
                f'values="{values}" '
                f'keyTimes="{key_times}" '
                f'dur="{duration:.2f}s" '
                f'begin="-{phase:.3f}s" '
                f'{repeat_attr}/>'
                f'</g>'
            )

        return "".join(
            parts
        )

    # --------------------------------------------------
    # SVG document
    # --------------------------------------------------

    background = (
        config["background"]
    )

    parts = [
        f'<svg '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'width="{canvas_w}" '
        f'height="{canvas_h}" '
        f'viewBox="'
        f'0 0 {canvas_w} {canvas_h}" '
        f'font-family="Menlo, '
        f'SFMono-Regular, Consolas, '
        f'monospace">'
    ]

    if background == "original":
        background = infer_original_background(
            config["src"]
        )

    if background is not None:
        parts.append(
            f'<rect '
            f'width="{canvas_w}" '
            f'height="{canvas_h}" '
            f'fill="{background}"/>'
        )

    content = render_base()

    animation = config[
        "animation"
    ]

    reveal_duration = timing[
        "reveal"
    ]

    # --------------------------------------------------
    # Instant
    # --------------------------------------------------

    if animation == "instant":

        parts.append(
            content
        )

    # --------------------------------------------------
    # Flag
    # --------------------------------------------------

    elif animation == "flag-wave":

        parts.append(
            flag_wave()
        )

    # --------------------------------------------------
    # Fade
    # --------------------------------------------------

    elif animation == "fade":

        duration = timing[
            "loop"
        ]

        if repeat:

            values = (
                "0;1;1;0"
            )

            key_times = (
                "0;0.35;0.78;1"
            )

        else:

            values = "0;1"
            key_times = "0;1"

        parts.append(
            f'<g opacity="0">'
            f'{content}'
            f'<animate '
            f'attributeName="opacity" '
            f'values="{values}" '
            f'keyTimes="{key_times}" '
            f'dur="{duration:.2f}s" '
            f'{repeat_attr}/>'
            f'</g>'
        )

    # --------------------------------------------------
    # Row
    # --------------------------------------------------

    elif animation == "row-reveal":

        if repeat:

            values = (
                f"0;{canvas_h};0"
            )

            key_times = (
                "0;0.72;1"
            )

        else:

            values = (
                f"0;{canvas_h}"
            )

            key_times = "0;1"

        parts.append(
            f'<clipPath '
            f'id="row-reveal">'
            f'<rect '
            f'x="0" y="0" '
            f'width="{canvas_w}" '
            f'height="0">'
            f'<animate '
            f'attributeName="height" '
            f'values="{values}" '
            f'keyTimes="{key_times}" '
            f'dur="{reveal_duration:.2f}s" '
            f'{repeat_attr}/>'
            f'</rect>'
            f'</clipPath>'
            f'<g '
            f'clip-path="url(#row-reveal)">'
            f'{content}'
            f'</g>'
        )

    # --------------------------------------------------
    # Column
    # --------------------------------------------------

    elif animation == "column-reveal":

        if repeat:

            values = (
                f"0;{canvas_w};0"
            )

            key_times = (
                "0;0.72;1"
            )

        else:

            values = (
                f"0;{canvas_w}"
            )

            key_times = "0;1"

        parts.append(
            f'<clipPath '
            f'id="column-reveal">'
            f'<rect '
            f'x="0" y="0" '
            f'width="0" '
            f'height="{canvas_h}">'
            f'<animate '
            f'attributeName="width" '
            f'values="{values}" '
            f'keyTimes="{key_times}" '
            f'dur="{reveal_duration:.2f}s" '
            f'{repeat_attr}/>'
            f'</rect>'
            f'</clipPath>'
            f'<g '
            f'clip-path="'
            f'url(#column-reveal)">'
            f'{content}'
            f'</g>'
        )

    # --------------------------------------------------
    # Diagonal
    # --------------------------------------------------

    elif animation == "diagonal-reveal":

        diagonal = math.hypot(
            canvas_w,
            canvas_h,
        )

        cx = (
            canvas_w / 2
        )

        cy = (
            canvas_h / 2
        )

        if repeat:

            values = (
                f"0;"
                f"{diagonal * 2:.1f};"
                f"0"
            )

            key_times = (
                "0;0.72;1"
            )

        else:

            values = (
                f"0;"
                f"{diagonal * 2:.1f}"
            )

            key_times = "0;1"

        parts.append(
            f'<clipPath '
            f'id="diagonal-reveal">'
            f'<rect '
            f'x="{-diagonal:.1f}" '
            f'y="{-diagonal:.1f}" '
            f'width="0" '
            f'height="{diagonal * 2:.1f}" '
            f'transform="rotate('
            f'45 '
            f'{cx:.1f} '
            f'{cy:.1f})">'
            f'<animate '
            f'attributeName="width" '
            f'values="{values}" '
            f'keyTimes="{key_times}" '
            f'dur="{reveal_duration:.2f}s" '
            f'{repeat_attr}/>'
            f'</rect>'
            f'</clipPath>'
            f'<g '
            f'clip-path="'
            f'url(#diagonal-reveal)">'
            f'{content}'
            f'</g>'
        )

    # --------------------------------------------------
    # Iris Aperture
    # --------------------------------------------------

    elif animation == "aperture-reveal":

        parts.append(
            iris_reveal()
        )

    # --------------------------------------------------
    # Circular
    # --------------------------------------------------

    elif animation == "circular-reveal":

        radius = math.hypot(
            canvas_w / 2,
            canvas_h / 2,
        )

        cx = (
            canvas_w / 2
        )

        cy = (
            canvas_h / 2
        )

        if repeat:

            values = (
                f"0;"
                f"{radius:.1f};"
                f"0"
            )

            key_times = (
                "0;0.72;1"
            )

        else:

            values = (
                f"0;"
                f"{radius:.1f}"
            )

            key_times = "0;1"

        parts.append(
            f'<clipPath '
            f'id="circular-reveal">'
            f'<circle '
            f'cx="{cx:.1f}" '
            f'cy="{cy:.1f}" '
            f'r="0">'
            f'<animate '
            f'attributeName="r" '
            f'values="{values}" '
            f'keyTimes="{key_times}" '
            f'dur="{reveal_duration:.2f}s" '
            f'{repeat_attr}/>'
            f'</circle>'
            f'</clipPath>'
            f'<g '
            f'clip-path="'
            f'url(#circular-reveal)">'
            f'{content}'
            f'</g>'
        )

    # --------------------------------------------------
    # Twinkle
    # --------------------------------------------------

    elif animation == "twinkle":

        parts.append(
            content
        )

        parts.append(
            twinkle()
        )

    # --------------------------------------------------
    # Sparkle Wave
    # --------------------------------------------------

    elif animation == "sparkle-wave":

        parts.append(
            content
        )

        parts.append(
            sparkle_wave()
        )

    parts.append(
        "</svg>"
    )

    svg = "".join(
        parts
    )

    try:

        os.makedirs(
            os.path.dirname(
                config["out"]
            )
            or ".",
            exist_ok=True,
        )

        with open(
            config["out"],
            "w",
            encoding="utf-8",
        ) as fh:
            fh.write(svg)

    except OSError as exc:

        fail(
            "Could not write output SVG: "
            f"{exc}"
        )

    print(
        f"Created "
        f"{config['out']} "
        f"{len(svg)} bytes; "
        f"{canvas_w}x{canvas_h}; "
        f"mode={config['mode']}; "
        f"animation={animation}; "
        f"speed={config['speed']}; "
        f"loop={config['loop']}"
    )


# --------------------------------------------------
# Entry point
# --------------------------------------------------

if __name__ == "__main__":

    try:
        main()

    except (
        KeyboardInterrupt,
        EOFError,
    ):
        print(
            "\nGeneration cancelled."
        )

        raise SystemExit(130)