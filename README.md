# ASCII Profile Generator

Turn your photos into customizable ASCII-art portraits with color modes, palettes, and animated SVG effects.

The generator runs from the terminal and produces a standalone SVG file that can be opened directly in a browser.

## Features

* Convert photos into ASCII art
* Adjustable ASCII dimensions
* Adjustable character size
* Custom ASCII character density ramp
* Contrast, brightness, and gamma controls
* Original image colors with transparency
* Light mode
* Dark mode
* Custom foreground/background colors
* Multicolour palettes
* Custom HEX colors
* Animated SVG output
* Multiple animation styles
* Looping or one-time animations
* Slow, normal, and fast animation speeds
* Flag mode with fabric-style waving animation
* iPhone photo orientation handling through EXIF data

## Available Color Modes

### Original

Preserves the source image's colors and transparency.

### Light

White background with dark ASCII characters.

### Dark

Dark background with light ASCII characters.

### Custom

Choose your own foreground and background colors.

### Multicolour

Apply a color palette based on the image's luminance.

Available palettes include:

* Rainbow
* Sunset
* Ocean
* Forest
* Diwali
* Custom

## Available Animations

1. Row Reveal
2. Column Reveal
3. Diagonal Reveal
4. Iris Aperture
5. Circular Reveal
6. Fade In
7. Twinkle
8. Sparkle Wave
9. Instant

Additional Flag mode provides a fabric-style waving animation.

## Requirements

* Python 3
* Pillow
* macOS, Linux, or Windows

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/ascii-profile-generator.git
cd ascii-profile-generator
```

Replace `YOUR_USERNAME` with your GitHub username.

### 2. Create a virtual environment

#### macOS / Linux

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

#### Windows

```powershell
py -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

## Usage

Place the image you want to convert inside the project directory.

For example:

```text
ascii-profile-generator/
├── ascii_generator.py
├── my-photo.png
└── ...
```

Then run:

```bash
python ascii_generator.py my-photo.png
```

The program will guide you through the available settings.

The generated file will be:

```text
avi-ascii.svg
```

Open it in your browser.

### macOS

```bash
open avi-ascii.svg
```

### Linux

```bash
xdg-open avi-ascii.svg
```

### Windows

```powershell
start avi-ascii.svg
```

## Configuration

The interactive generator lets you configure:

### ASCII dimensions

Default:

```text
120 × 64
```

Allowed range:

```text
Columns: 20–300
Rows:    10–200
```

Maximum:

```text
50,000 cells
```

### Character size

Default:

```text
8 × 15
```

Allowed range:

```text
Width:  3–30
Height: 5–40
```

### Character density

The default ramp is:

```text
 .,:;irsXA253hMHGS#9B&@
```

You can also provide your own character ramp.

### Image adjustments

You can control:

* Contrast
* Brightness
* Gamma

## Animation Controls

Animated modes support:

```text
Slow
Normal
Fast
```

and:

```text
Loop: Yes / No
```

`Instant` does not require animation speed or loop selection.

Flag mode automatically uses continuous animation.

## Output

The generator creates an SVG rather than a raster image.

This means the output can be opened directly in a modern web browser and retains the animated SVG effects.

## Development

Clone the repository and create the development environment:

```bash
git clone https://github.com/YOUR_USERNAME/ascii-profile-generator.git
cd ascii-profile-generator

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

Check the Python files:

```bash
python -m py_compile \
    ascii_generator.py \
    scripts/ascii_renderer.py \
    setup.py
```

Run the generator:

```bash
python ascii_generator.py my-photo.png
```

## Project Structure

```text
ascii-profile-generator/
│
├── ascii_generator.py
│   └── Interactive terminal interface
│
├── scripts/
│   └── ascii_renderer.py
│       └── Image processing and SVG rendering
│
├── setup.py
│   └── Project packaging metadata
│
├── requirements.txt
│   └── Python dependencies
│
├── README.md
│   └── Documentation
│
├── LICENSE
│   └── Project license
│
└── .gitignore
    └── Files excluded from Git
```

## Notes

Generated SVG files and local input images are intentionally excluded from Git.

For best results, use a reasonably clear image with good contrast.

## License

This project is licensed under the MIT License. See `LICENSE` for details.

