import os
import platform
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(ROOT, ".venv")
SCRIPT = os.path.join(ROOT, "ascii_renderer.py")
EXPORTER = os.path.join(ROOT, "exporter.py")
SVG_OUTPUT = os.path.join(ROOT, "avi-ascii.svg")
PNG_OUTPUT = os.path.join(ROOT, "avi-ascii.png")
JPEG_OUTPUT = os.path.join(ROOT, "avi-ascii.jpg")
GIF_OUTPUT = os.path.join(ROOT, "avi-ascii.gif")

DEFAULT_COLS, DEFAULT_ROWS = 120, 64
DEFAULT_CELL_W, DEFAULT_CELL_H = 8, 15
DEFAULT_RAMP = " .,:;irsXA253hMHGS#9B&@"
DEFAULT_CONTRAST, DEFAULT_BRIGHTNESS, DEFAULT_GAMMA = 1.10, 1.00, 1.00

MIN_COLS, MAX_COLS = 20, 300
MIN_ROWS, MAX_ROWS = 10, 200
MAX_CELLS = 50000
MIN_CELL_W, MAX_CELL_W = 3, 30
MIN_CELL_H, MAX_CELL_H = 5, 40

BACK = object()
SKIP = object()
ADDITIONAL = object()
BACK_TO_FLAG_THEME = object()

COLOR_PRESETS = {
    "1": ("Black", "#000000"),
    "2": ("White", "#ffffff"),
    "3": ("Red", "#ff0000"),
    "4": ("Orange", "#ff8800"),
    "5": ("Yellow", "#ffff00"),
    "6": ("Green", "#00aa44"),
    "7": ("Blue", "#0066ff"),
    "8": ("Purple", "#8800ff"),
    "9": ("Pink", "#ff1493"),
    "10": ("Cyan", "#00cfff"),
    "11": ("Gold", "#ffd700"),
}

PALETTES = {
    "1": (
        "Rainbow",
        [
            "#ff0000",
            "#ff8800",
            "#ffff00",
            "#00cc44",
            "#0088ff",
            "#4400ff",
            "#cc00ff",
        ],
    ),
    "2": (
        "Sunset",
        [
            "#ff3b30",
            "#ff6b35",
            "#ff9500",
            "#ffcc00",
            "#ff2d55",
        ],
    ),
    "3": (
        "Ocean",
        [
            "#003f5c",
            "#0077b6",
            "#00b4d8",
            "#48cae4",
            "#90e0ef",
        ],
    ),
    "4": (
        "Forest",
        [
            "#143d2b",
            "#1f7a4d",
            "#2eae62",
            "#72c94a",
            "#b7df73",
        ],
    ),
    "5": (
        "Diwali",
        [
            "#ff2400",
            "#ff6600",
            "#ffd700",
            "#ff1493",
            "#8a2be2",
            "#00cfff",
        ],
    ),
}

ANIMATIONS = {
    "1": ("Row Reveal", "row-reveal"),
    "2": ("Column Reveal", "column-reveal"),
    "3": ("Diagonal Reveal", "diagonal-reveal"),
    "4": ("Iris Aperture", "aperture-reveal"),
    "5": ("Circular Reveal", "circular-reveal"),
    "6": ("Fade In", "fade"),
    "7": ("Twinkle", "twinkle"),
    "8": ("Sparkle Wave", "sparkle-wave"),
    "9": ("Instant", "instant"),
}


def resolve_venv_python():
    if platform.system() == "Windows":
        candidates = [
            os.path.join(VENV_DIR, "Scripts", "python.exe"),
            os.path.join(VENV_DIR, "Scripts", "python3.exe"),
        ]
    else:
        candidates = [
            os.path.join(VENV_DIR, "bin", "python"),
            os.path.join(VENV_DIR, "bin", "python3"),
        ]

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    return None


PYTHON = resolve_venv_python()


def command_input(prompt):
    try:
        raw = input(prompt)
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")
        raise SystemExit(0)

    command = raw.strip().lower()

    if command in ("q", "quit"):
        print("\nExiting.")
        raise SystemExit(0)

    if command in ("b", "back"):
        return BACK

    return raw.strip()


def ramp_input(prompt):
    try:
        raw = input(prompt)
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")
        raise SystemExit(0)

    command = raw.strip().lower()

    if command in (":q", ":quit"):
        print("\nExiting.")
        raise SystemExit(0)

    if command in (":b", ":back"):
        return BACK

    return raw


def valid_hex(value):
    if len(value) != 7 or not value.startswith("#"):
        return False

    try:
        int(value[1:], 16)
        return True
    except ValueError:
        return False


def choose_color(title, default="1"):
    while True:
        print()
        print(title)

        for key, (name, _) in COLOR_PRESETS.items():
            print(f"{key}. {name}")

        print("12. Custom HEX")
        print("b. Back")
        print("q. Quit")

        choice = command_input(
            f"\nChoose an option (1-12, Enter = {default}): "
        )

        if choice is BACK:
            return BACK

        if choice == "":
            choice = default

        if choice in COLOR_PRESETS:
            return COLOR_PRESETS[choice][1]

        if choice == "12":
            while True:
                value = command_input(
                    "Enter HEX color (example: #ff6600): "
                )

                if value is BACK:
                    return BACK

                if valid_hex(value):
                    return value.lower()

                print("Invalid HEX color. Use #RRGGBB.")

        else:
            print("Please enter a valid option.")


def choose_palette():
    while True:
        print()
        print("Multicolour Palette")

        for key, (name, _) in PALETTES.items():
            print(f"{key}. {name}")

        print("6. Custom palette")
        print("b. Back")
        print("q. Quit")

        choice = command_input(
            "\nChoose an option (1-6, Enter = 1): "
        )

        if choice is BACK:
            return BACK

        if choice == "":
            choice = "1"

        if choice in PALETTES:
            name, colors = PALETTES[choice]
            return name, colors

        if choice == "6":
            while True:
                value = command_input(
                    "Enter HEX colours separated by commas:\n"
                    "Example: #ff0000,#ffd700,#00ff00\n"
                    "Palette: "
                )

                if value is BACK:
                    return BACK

                colors = [
                    item.strip().lower()
                    for item in value.split(",")
                    if item.strip()
                ]

                if len(colors) < 2:
                    print("Please enter at least two colours.")
                    continue

                if not all(valid_hex(color) for color in colors):
                    print("Invalid palette. Use #RRGGBB values.")
                    continue

                return "Custom", colors

        else:
            print("Please enter a valid option.")


def choose_color_mode():
    while True:
        print()
        print("Color & Theme")
        print("1. Original    - preserve source colours")
        print("2. Light       - white background + black ASCII")
        print("3. Dark        - black background + white ASCII")
        print("4. Custom      - choose foreground + background")
        print("5. Multicolour - choose palette + background")
        print("6. Additional")
        print("b. Back")
        print("q. Quit")

        choice = command_input(
            "\nChoose an option (1-6, Enter = 1): "
        )

        if choice is BACK:
            return BACK

        if choice in ("", "1"):
            background = choose_background(
                "Background"
            )

            if background is BACK:
                continue

            return {
                "mode": "original",
                "background": background,
                "foreground": "#111111",
                "palette": [],
                "palette_name": "",
            }

        if choice == "2":
            return {
                "mode": "light",
                "background": "#ffffff",
                "foreground": "#111111",
                "palette": [],
                "palette_name": "",
            }

        if choice == "3":
            return {
                "mode": "dark",
                "background": "#000000",
                "foreground": "#ffffff",
                "palette": [],
                "palette_name": "",
            }

        if choice == "4":
            while True:
                foreground = choose_color(
                    "ASCII / Foreground",
                    "1",
                )

                if foreground is BACK:
                    break

                background = choose_color(
                    "Background",
                    "2",
                )

                if background is BACK:
                    continue

                return {
                    "mode": "custom",
                    "background": background,
                    "foreground": foreground,
                    "palette": [],
                    "palette_name": "",
                }

            continue

        if choice == "5":
            while True:
                palette = choose_palette()

                if palette is BACK:
                    break

                background = choose_color(
                    "Multicolour Background",
                    "2",
                )

                if background is BACK:
                    continue

                palette_name, colors = palette

                return {
                    "mode": "multicolour",
                    "background": background,
                    "foreground": "#111111",
                    "palette": colors,
                    "palette_name": palette_name,
                }

            continue

        if choice == "6":
            return ADDITIONAL

        print("Please enter a valid option.")


def choose_additional():
    while True:
        print()
        print("Additional")
        print("1. Flag")
        print("2. GitHub Profile Preset")
        print("b. Back")
        print("q. Quit")

        choice = command_input(
            "\nChoose an option (1-2, Enter = 1): "
        )

        if choice is BACK:
            return BACK

        if choice in ("", "1"):
            return "flag"

        if choice == "2":
            return "github"

        print("Please enter 1 or 2.")




def choose_flag_theme():
    while True:
        print()
        print("Flag Colours")
        print(
            "1. Original Colour - preserve source colours"
        )
        print(
            "2. Black & White   - white background + black ASCII"
        )
        print("b. Back")
        print("q. Quit")

        choice = command_input(
            "\nChoose an option (1-2, Enter = 1): "
        )

        if choice is BACK:
            return BACK_TO_FLAG_THEME

        if choice in ("", "1"):
            return {
                "mode": "original",
                "background": None,
                "foreground": "#111111",
                "palette": [],
                "palette_name": "",
            }

        if choice == "2":
            return {
                "mode": "light",
                "background": "#ffffff",
                "foreground": "#111111",
                "palette": [],
                "palette_name": "",
            }

        print("Please enter 1 or 2.")


def choose_animation(default_choice="1"):
    while True:
        print()
        print("Animation")

        labels = {
            "1": "Row Reveal       - top → bottom",
            "2": "Column Reveal    - left → right",
            "3": "Diagonal Reveal  - diagonal sweep",
            "4": "Iris Aperture    - camera aperture open/close",
            "5": "Circular Reveal  - centre → outside",
            "6": "Fade In          - gradual appearance",
            "7": "Twinkle          - scattered ASCII sparkles",
            "8": "Sparkle Wave     - smooth travelling highlight wave",
            "9": "Instant          - no animation",
        }

        for key in ANIMATIONS:
            print(f"{key}. {labels[key]}")

        print("b. Back")
        print("q. Quit")

        choice = command_input(
            f"\nChoose an option (1-9, Enter = {default_choice}): "
        )

        if choice is BACK:
            return BACK

        if choice == "":
            choice = default_choice

        if choice in ANIMATIONS:
            return ANIMATIONS[choice][1]

        print("Please enter a valid option.")


def choose_loop(default_choice="2"):
    while True:
        print()
        print("Loop Animation")
        print("1. Yes - repeat continuously")
        print("2. No  - play once and stop")
        print("b. Back")
        print("q. Quit")

        choice = command_input(
            f"\nChoose an option (1-2, Enter = {default_choice}): "
        )

        if choice is BACK:
            return BACK

        if choice == "":
            choice = default_choice

        if choice == "2":
            return "no"

        if choice == "1":
            return "yes"

        print("Please enter 1 or 2.")


def choose_speed(default_choice="2"):
    while True:
        print()
        print("Animation Speed")
        print("1. Slow")
        print("2. Normal")
        print("3. Fast")
        print("b. Back")
        print("q. Quit")

        choice = command_input(
            f"\nChoose an option (1-3, Enter = {default_choice}): "
        )

        if choice is BACK:
            return BACK

        if choice == "":
            choice = default_choice

        mapping = {
            "1": "slow",
            "2": "normal",
            "3": "fast",
        }

        if choice in mapping:
            return mapping[choice]

        print("Please enter 1, 2 or 3.")


def choose_dimensions(def_cols=DEFAULT_COLS, def_rows=DEFAULT_ROWS):
    while True:
        print()
        print(
            f"ASCII Dimensions\n"
            f"1. Default: {def_cols} × {def_rows}\n"
            "2. Custom\n"
            "b. Back\n"
            "q. Quit"
        )

        choice = command_input(
            "\nChoose an option (1-2, Enter = 1): "
        )

        if choice is BACK:
            return BACK

        if choice in ("", "1"):
            return def_cols, def_rows

        if choice != "2":
            print("Please enter 1 or 2.")
            continue

        while True:
            cols_raw = command_input(
                f"Columns ({MIN_COLS}-{MAX_COLS}): "
            )

            if cols_raw is BACK:
                return BACK

            try:
                cols = int(cols_raw)
            except ValueError:
                print("Please enter a whole number for columns.")
                continue

            if not MIN_COLS <= cols <= MAX_COLS:
                print(
                    f"Columns must be between "
                    f"{MIN_COLS} and {MAX_COLS}."
                )
                continue

            break

        while True:
            rows_raw = command_input(
                f"Rows ({MIN_ROWS}-{MAX_ROWS}, "
                f"max {MAX_CELLS} cells): "
            )

            if rows_raw is BACK:
                return BACK

            try:
                rows = int(rows_raw)
            except ValueError:
                print("Please enter a whole number for rows.")
                continue

            if not MIN_ROWS <= rows <= MAX_ROWS:
                print(
                    f"Rows must be between "
                    f"{MIN_ROWS} and {MAX_ROWS}."
                )
                continue

            if cols * rows > MAX_CELLS:
                print(
                    f"That size creates {cols * rows:,} cells. "
                    f"Maximum is {MAX_CELLS:,}."
                )
                continue

            return cols, rows


def choose_character_size(def_w=DEFAULT_CELL_W, def_h=DEFAULT_CELL_H):
    while True:
        print()
        print(
            f"Character Size\n"
            f"1. Default: {def_w} × {def_h}\n"
            "2. Custom\n"
            "b. Back\n"
            "q. Quit"
        )

        choice = command_input(
            "\nChoose an option (1-2, Enter = 1): "
        )

        if choice is BACK:
            return BACK

        if choice in ("", "1"):
            return def_w, def_h

        if choice != "2":
            print("Please enter 1 or 2.")
            continue

        while True:
            width_raw = command_input(
                f"Character width ({MIN_CELL_W}-{MAX_CELL_W}): "
            )

            if width_raw is BACK:
                return BACK

            try:
                width = int(width_raw)
            except ValueError:
                print("Please enter a whole number for width.")
                continue

            if not MIN_CELL_W <= width <= MAX_CELL_W:
                print(
                    f"Width must be between "
                    f"{MIN_CELL_W} and {MAX_CELL_W}."
                )
                continue

            break

        while True:
            height_raw = command_input(
                f"Character height ({MIN_CELL_H}-{MAX_CELL_H}): "
            )

            if height_raw is BACK:
                return BACK

            try:
                height = int(height_raw)
            except ValueError:
                print("Please enter a whole number for height.")
                continue

            if not MIN_CELL_H <= height <= MAX_CELL_H:
                print(
                    f"Height must be between "
                    f"{MIN_CELL_H} and {MAX_CELL_H}."
                )
                continue

            return width, height


def choose_ramp(def_ramp=DEFAULT_RAMP):
    while True:
        print()
        print(
            f'Character Density\n'
            f'1. Default: "{def_ramp}"\n'
            "2. Custom\n"
            "b. Back\n"
            "q. Quit"
        )
        print(
            "Custom ramp: use :b to go back or :q to quit."
        )

        choice = command_input(
            "\nChoose an option (1-2, Enter = 1): "
        )

        if choice is BACK:
            return BACK

        if choice in ("", "1"):
            return def_ramp

        if choice != "2":
            print("Please enter 1 or 2.")
            continue

        while True:
            ramp = ramp_input(
                "Enter characters from light → dark: "
            )

            if ramp is BACK:
                return BACK

            if not ramp.strip():
                print("Please enter at least 2 visible characters.")
                continue

            if len(ramp) < 2:
                print("Please enter at least 2 characters.")
                continue

            if len(ramp) > 32:
                print("Please use 32 characters or fewer.")
                continue

            if any(not ch.isprintable() for ch in ramp):
                print("Please use printable characters only.")
                continue

            if len(set(ramp)) < 2:
                print("Please use at least 2 different characters.")
                continue

            return ramp


def choose_number(name, default):
    while True:
        print()
        print(name)
        print(f"1. Default: {default}")
        print("2. Custom")
        print("b. Back")
        print("q. Quit")

        choice = command_input(
            "\nChoose an option (1-2, Enter = 1): "
        )

        if choice is BACK:
            return BACK

        if choice in ("", "1"):
            return default

        if choice != "2":
            print("Please enter 1 or 2.")
            continue

        while True:
            raw = command_input(
                f"Enter {name.lower()} (0.05-4.0): "
            )

            if raw is BACK:
                return BACK

            try:
                value = float(raw)
            except ValueError:
                print("Please enter a valid number.")
                continue

            if not 0.05 <= value <= 4.0:
                print(
                    "Please enter a value between "
                    "0.05 and 4.0."
                )
                continue

            return value


def stage_is_skipped(stages, index, values):
    if index < 0 or index >= len(stages):
        return False

    name = stages[index][0]

    return (
        values.get("animation") == "instant"
        and name in {"loop", "speed"}
    )


def run_stages(
    stages,
    values,
    back_at_start,
    start_index=0,
):
    index = start_index

    while index < len(stages):
        name, chooser = stages[index]

        if stage_is_skipped(stages, index, values):
            index += 1
            continue

        value = chooser()

        if value is BACK:
            if index == 0:
                return back_at_start

            index -= 1

            while (
                index >= 0
                and stage_is_skipped(
                    stages,
                    index,
                    values,
                )
            ):
                index -= 1

            if index < 0:
                return back_at_start

            continue

        if value is SKIP:
            index += 1
            continue

        values[name] = value
        index += 1

    return values


def build_shared_stages(preset="standard"):
    if preset == "github":
        def_cols, def_rows = 100, 50
        def_cw, def_ch = 8, 15
        def_ramp = DEFAULT_RAMP
        def_con, def_bri, def_gam = 1.10, 1.00, 1.00
    else:
        def_cols, def_rows = DEFAULT_COLS, DEFAULT_ROWS
        def_cw, def_ch = DEFAULT_CELL_W, DEFAULT_CELL_H
        def_ramp = DEFAULT_RAMP
        def_con, def_bri, def_gam = DEFAULT_CONTRAST, DEFAULT_BRIGHTNESS, DEFAULT_GAMMA

    return [
        ("dimensions", lambda: choose_dimensions(def_cols, def_rows)),
        ("character_size", lambda: choose_character_size(def_cw, def_ch)),
        ("ramp", lambda: choose_ramp(def_ramp)),
        ("contrast", lambda: choose_number("Contrast", def_con)),
        ("brightness", lambda: choose_number("Brightness", def_bri)),
        ("gamma", lambda: choose_number("Gamma", def_gam)),
    ]



def print_configuration(values, flag=False):
    color = values["color"]
    cols, rows = values["dimensions"]
    cell_w, cell_h = values["character_size"]

    print()
    print("----------------------------------------")
    print("Configuration")
    print("----------------------------------------")
    print(f"Color:       {color['mode']}")

    if color["background"] is None:
        print("Background:  transparent")
    elif color["background"] == "original":
        print("Background:  original")
    else:
        print(f"Background:  {color['background']}")

    if color["mode"] == "original":
        print("Foreground:  sampled from image")
    elif color["mode"] == "multicolour":
        print(
            f"Palette:     {color['palette_name']} "
            f"({len(color['palette'])} colours)"
        )
    else:
        print(
            f"Foreground:  {color['foreground']}"
        )

    if flag:
        print("Animation:   flag-wave")
        print("Loop:        yes (Flag is continuous)")
    else:
        print(
            f"Animation:   {values['animation']}"
        )
        print(
            f"Loop:        {values['loop']}"
        )

    print(f"Speed:       {values['speed']}")
    print(f"Dimensions:  {cols} × {rows}")
    print(f"Character:   {cell_w} × {cell_h}")
    print(f"Characters:  {values['ramp']}")
    print(f"Contrast:    {values['contrast']}")
    print(f"Brightness:  {values['brightness']}")
    print(f"Gamma:        {values['gamma']}")
    print(f"Format:      {values['output_format'].upper()}")
    print("----------------------------------------")


def choose_background(title="Background"):
    while True:
        print()
        print(title)
        print("1. Preserve Transparent (if available)")
        print("2. Original")
        print("3. White")
        print("4. Black")
        print("5. Custom HEX")
        print("b. Back")
        print("q. Quit")

        choice = command_input(
            "\nChoose an option (1-5, Enter = 2): "
        )

        if choice is BACK:
            return BACK

        if choice == "1":
            return None

        if choice in ("", "2"):
            return "original"

        if choice == "3":
            return "#ffffff"

        if choice == "4":
            return "#000000"

        if choice == "5":
            while True:
                value = command_input(
                    "Enter HEX background "
                    "(example: #f5f5f5): "
                )

                if value is BACK:
                    break

                if valid_hex(value):
                    return value.lower()

                print(
                    "Invalid HEX color. "
                    "Use #RRGGBB."
                )

            continue

        print("Please enter a valid option.")


        if choice == "4":
            return "gif"

        print("Please enter 1, 2, 3 or 4.")

def choose_output_format(default_choice="1"):
    while True:
        print()
        print("Output Format")
        print("1. SVG  - vector, preserves animation and selected background")
        print("2. PNG  - best general-purpose image")
        print("3. JPEG - smaller, solid background")
        print("4. GIF  - animated image")
        print("b. Back")
        print("q. Quit")

        choice = command_input(
            f"\nChoose an option (1-4, Enter = {default_choice}): "
        )

        if choice is BACK:
            return BACK

        if choice == "":
            choice = default_choice

        if choice == "1":
            return "svg"

        if choice == "2":
            return "png"

        if choice == "3":
            return "jpeg"

        if choice == "4":
            return "gif"

        print("Please enter 1, 2, 3 or 4.")


def build_normal_stages(preset="standard"):
    if preset == "github":
        anim_def = "7" # Twinkle
        loop_def = "1" # Yes
        speed_def = "2" # Normal
        fmt_def = "1"  # SVG
    else:
        anim_def = "1"
        loop_def = "2"
        speed_def = "2"
        fmt_def = "1"

    return [
        ("animation", lambda: choose_animation(anim_def)),
        ("loop", lambda: choose_loop(loop_def)),
        ("speed", lambda: choose_speed(speed_def)),
        *build_shared_stages(preset),
        ("output_format", lambda: choose_output_format(fmt_def)),
    ]


def build_flag_stages():
    return [
        ("speed", lambda: choose_speed("2")),
        *build_shared_stages(),
        ("output_format", lambda: choose_output_format("1")),
    ]


def renderer_command(
    image,
    output_path,
    values,
):
    color = values["color"]
    cols, rows = values["dimensions"]
    cell_w, cell_h = values["character_size"]

    background_value = color["background"]
    background = (
        "none"
        if background_value is None
        else background_value
    )

    palette = (
        ",".join(color["palette"])
        if color["palette"]
        else "none"
    )

    animation = values["animation"]
    speed = values["speed"]
    loop = (
        "yes"
        if animation == "flag-wave"
        else values["loop"]
    )

    return [
        PYTHON,
        SCRIPT,
        image,
        output_path,
        color["mode"],
        str(cols),
        str(rows),
        values["ramp"],
        str(values["contrast"]),
        str(values["brightness"]),
        str(values["gamma"]),
        str(cell_w),
        str(cell_h),
        background,
        color["foreground"],
        palette,
        animation,
        speed,
        loop,
    ]


def exporter_command(
    image,
    output_path,
    values,
):
    color = values["color"]
    cols, rows = values["dimensions"]
    cell_w, cell_h = values["character_size"]

    background_value = color["background"]
    background = (
        "none"
        if background_value is None
        else background_value
    )

    palette = (
        ",".join(color["palette"])
        if color["palette"]
        else "none"
    )

    animation = values["animation"]
    speed = values["speed"]
    loop = (
        "yes"
        if animation == "flag-wave"
        else values["loop"]
    )

    return [
        PYTHON,
        EXPORTER,
        image,
        output_path,
        "--format",
        values["output_format"],
        "--mode",
        color["mode"],
        "--cols",
        str(cols),
        "--rows",
        str(rows),
        "--ramp",
        values["ramp"],
        "--contrast",
        str(values["contrast"]),
        "--brightness",
        str(values["brightness"]),
        "--gamma",
        str(values["gamma"]),
        "--cell-w",
        str(cell_w),
        "--cell-h",
        str(cell_h),
        "--background",
        background,
        "--foreground",
        color["foreground"],
        "--palette",
        palette,
        "--animation",
        animation,
        "--speed",
        speed,
        "--loop",
        loop,
    ]


def generate(image, values):
    output_format = values["output_format"]

    if output_format == "svg":
        output_path = SVG_OUTPUT
        command = renderer_command(
            image,
            output_path,
            values,
        )
        label = "SVG"

    else:
        if output_format == "png":
            output_path = PNG_OUTPUT
            label = "PNG"
        elif output_format == "jpeg":
            output_path = JPEG_OUTPUT
            label = "JPEG"
        else:
            output_path = GIF_OUTPUT
            label = "GIF"

        command = exporter_command(
            image,
            output_path,
            values,
        )

    print()
    print(
        f"Generating {label}..."
    )
    print()

    try:
        subprocess.run(
            command,
            check=True,
        )
    except FileNotFoundError as exc:
        print(
            f"Could not start exporter/renderer: {exc}"
        )
        raise SystemExit(1)
    except subprocess.CalledProcessError as exc:
        print(
            "Generation failed "
            f"(exit code {exc.returncode})."
        )
        raise SystemExit(1)

    print()
    print("Done!")
    print(f"Generated: {output_path}")


def run_normal(image, color):
    values = {
        "color": color,
    }

    stages = build_normal_stages()

    result = run_stages(
        stages,
        values,
        BACK,
    )

    if result is BACK:
        return BACK

    values = result

    if values.get("animation") == "instant":
        values["loop"] = "no"
        values["speed"] = "normal"

    while True:
        print_configuration(values)

        confirm = command_input(
            "Generate with these settings? [Y/n]: "
        )

        if confirm is BACK:
            edited = run_stages(
                stages,
                values,
                BACK,
                len(stages) - 1,
            )

            if edited is BACK:
                return BACK

            values = edited

            if values.get("animation") == "instant":
                values["loop"] = "no"
                values["speed"] = "normal"

            continue

        if confirm.lower() in (
            "",
            "y",
            "yes",
        ):
            generate(
                image,
                values,
            )
        else:
            print("Generation cancelled.")

        return None


def run_preset(image):
    values = {
        "color": {
            "mode": "original",
            "background": None, # Transparent fallback to source/SVG defaults
            "foreground": "#111111",
            "palette": [],
            "palette_name": "",
        },
        "animation": "twinkle",
        "loop": "yes",
        "speed": "normal",
        "dimensions": (100, 50),
        "character_size": (8, 15),
        "ramp": DEFAULT_RAMP,
        "contrast": DEFAULT_CONTRAST,
        "brightness": DEFAULT_BRIGHTNESS,
        "gamma": DEFAULT_GAMMA,
        "output_format": "svg",
    }

    stages = build_normal_stages(preset="github")

    while True:
        print_configuration(values)

        confirm = command_input(
            "Generate with these GitHub Profile settings? [Y/n/edit]: "
        )

        if confirm is BACK:
            return BACK

        if confirm.lower() in ("e", "edit"):
            while True:
                color = choose_color_mode()

                if color is BACK:
                    break

                if color is ADDITIONAL:
                    while True:
                        additional = choose_additional()
                        if additional is BACK:
                            break
                        if additional == "flag":
                            while True:
                                flag_theme = choose_flag_theme()
                                if flag_theme is BACK_TO_FLAG_THEME:
                                    break
                                result = run_flag(image, flag_theme)
                                if result is BACK_TO_FLAG_THEME:
                                    continue
                                return None
                    continue

                values["color"] = color
                edited = run_stages(
                    stages,
                    values,
                    BACK,
                    0,
                )

                if edited is BACK:
                    continue

                values = edited

                if values.get("animation") == "instant":
                    values["loop"] = "no"
                    values["speed"] = "normal"

                break

            continue

        if confirm.lower() == "n":
            edited = run_stages(
                stages,
                values,
                BACK,
                len(stages) - 1,
            )

            if edited is BACK:
                continue

            values = edited
            continue

        if confirm.lower() in ("", "y", "yes"):
            generate(image, values)
        else:
            print("Generation cancelled.")

        return None


def run_flag(image, flag_theme):
    values = {
        "color": flag_theme,
        "animation": "flag-wave",
        "loop": "yes",
    }

    stages = build_flag_stages()

    while True:
        result = run_stages(
            stages,
            values,
            BACK_TO_FLAG_THEME,
        )

        if result is BACK_TO_FLAG_THEME:
            return BACK_TO_FLAG_THEME

        values = result

        print_configuration(
            values,
            flag=True,
        )

        confirm = command_input(
            "Generate with these settings? [Y/n]: "
        )

        if confirm is BACK:
            edited = run_stages(
                stages,
                values,
                BACK_TO_FLAG_THEME,
                len(stages) - 1,
            )

            if edited is BACK_TO_FLAG_THEME:
                return BACK_TO_FLAG_THEME

            values = edited
            continue

        if confirm.lower() in (
            "",
            "y",
            "yes",
        ):
            generate(
                image,
                values,
            )
        else:
            print("Generation cancelled.")

        return None


def main():
    global PYTHON

    if PYTHON is None:
        PYTHON = resolve_venv_python()

    if PYTHON is None:
        print(
            "Virtual environment Python was not found."
        )
        print("Run: python3 setup.py")
        raise SystemExit(1)

    if not os.path.isfile(SCRIPT):
        print(
            f"Renderer not found: {SCRIPT}"
        )
        raise SystemExit(1)

    if not os.path.isfile(EXPORTER):
        print(
            f"Exporter not found: {EXPORTER}"
        )
        raise SystemExit(1)

    if len(sys.argv) < 2:
        print("Usage:")
        print(
            "  python ascii_generator.py "
            "<path-to-image>"
        )
        print()
        print("Example:")
        print(
            "  python ascii_generator.py "
            "my-photo.png"
        )
        raise SystemExit(1)

    image = os.path.abspath(
        sys.argv[1]
    )

    if not os.path.isfile(image):
        print(
            f"Image not found: {image}"
        )
        raise SystemExit(1)

    while True:
        color = choose_color_mode()

        if color is BACK:
            return

        if color is ADDITIONAL:
            while True:
                additional = choose_additional()

                if additional is BACK:
                    break

                if additional == "github":
                    result = run_preset(image)
                    if result is BACK:
                        continue
                    return

                if additional == "flag":
                    while True:
                        flag_theme = choose_flag_theme()

                        if flag_theme is BACK_TO_FLAG_THEME:
                            break

                        result = run_flag(
                            image,
                            flag_theme,
                        )

                        if result is BACK_TO_FLAG_THEME:
                            continue

                        return

            continue

        result = run_normal(
            image,
            color,
        )

        if result is BACK:
            continue

        return


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")
