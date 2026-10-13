# ASCII Profile Generator

I built this tool to turn images into customizable ASCII art. You can tweak the characters, colors, size, contrast, and animation, then export the result as SVG, PNG, JPEG, or GIF.

## Sample

The project ships with `sample.png`, the input image used to generate every example below.

<img src="./sample.png" width="320" alt="Sample input image" />

The idea is simple: **input image → ASCII artwork → optional animation or export.**

## Features

- Customizable ASCII character ramp (density)
- Image size and cell size controls
- Brightness, contrast, and gamma adjustments
- Color modes and custom palettes
- Export to SVG, PNG, JPEG, or GIF
- 15 animation styles
- A GitHub Profile preset

## Quick start

Install and run on the included sample:

```bash
python3 setup.py
python3 ascii_generator.py sample.png
```

On Windows, use `py` instead of `python3`. `setup.py` sets up a virtual environment and installs the one dependency, Pillow. From there the CLI walks you through color, size, animation, and output format.

## Animation showcase

Every GIF below comes from the same `sample.png`, so you can compare the styles directly.

### Reveal

| Row Reveal | Column Reveal | Diagonal Reveal | Iris Aperture | Circular Reveal |
| --- | --- | --- | --- | --- |
| ![Row Reveal](examples/animations/row-reveal.gif) | ![Column Reveal](examples/animations/column-reveal.gif) | ![Diagonal Reveal](examples/animations/diagonal-reveal.gif) | ![Iris Aperture](examples/animations/iris-aperture.gif) | ![Circular Reveal](examples/animations/circular-reveal.gif) |

- **Row Reveal** · Builds the image from top to bottom.
- **Column Reveal** · Builds it from left to right.
- **Diagonal Reveal** · Uncovers across a diagonal.
- **Iris Aperture** · Opens an eight-sided aperture.
- **Circular Reveal** · Expands a circular opening.

### Effects

| Fade In | Twinkle | Sparkle Wave | Typewriter | Dissolve |
| --- | --- | --- | --- | --- |
| ![Fade In](examples/animations/fade-in.gif) | ![Twinkle](examples/animations/twinkle.gif) | ![Sparkle Wave](examples/animations/sparkle-wave.gif) | ![Typewriter](examples/animations/typewriter.gif) | ![Dissolve](examples/animations/dissolve.gif) |

- **Fade In** · Fades the whole image into view.
- **Twinkle** · Adds subtle animated highlights.
- **Sparkle Wave** · Moves a soft shimmer across the glyphs.
- **Typewriter** · Types the image out line by line.
- **Dissolve** · Assembles the image from scattered groups.

### Dynamic

| Digital Rain | Tetris | Mosaic |
| --- | --- | --- |
| ![Digital Rain](examples/animations/digital-rain.gif) | ![Tetris](examples/animations/tetris.gif) | ![Mosaic](examples/animations/mosaic.gif) |

- **Digital Rain** · Adds falling streams around the artwork.
- **Tetris** · Reconstructs the image with falling blocks.
- **Mosaic** · Opens tiles that uncover the artwork.

### Static & Special

| Instant | Flag Wave |
| --- | --- |
| ![Instant](examples/animations/instant.gif) | ![Flag Wave](examples/animations/flag-wave.gif) |

- **Instant** · Shows the complete artwork with no animation.
- **Flag Wave** · Gives the artwork a waving flag effect.

## Color modes

Pick how the ASCII art is colored:

- **Original** · keep the source colors
- **Light** · white background, black characters
- **Dark** · black background, white characters
- **Custom** · choose your own foreground and background
- **Multicolour** · supply a palette

With `Original`, you can keep the canvas transparent (SVG and PNG) or flatten it to a background color. JPEG and GIF always use a solid background.

## GitHub Profile preset

A preset is included for creating ASCII art sized for a GitHub profile README. It starts you at Original colors on a transparent background, Twinkle animation set to loop, a 100 × 50 grid, and SVG output. These are just starting points — press `e` at the confirmation prompt to change anything before generating.

## Project structure

```text
ascii-profile-generator/
├── ascii_generator.py
├── ascii_renderer.py
├── exporter.py
├── animations.py
├── setup.py
├── requirements.txt
├── sample.png
├── examples/
│   └── animations/
└── tests/
```

Run the tests with `python3 -m unittest discover`.

## License

Released under the [MIT License](LICENSE).
