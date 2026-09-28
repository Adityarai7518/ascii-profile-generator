# ASCII Profile Generator

Turn a normal image into ASCII art and export it as SVG, PNG, JPEG, or GIF.

The goal is simple: install Python, run the setup, choose your settings, and get the file you asked for.

## Try it

A sample image is included so you can test the project immediately.

### macOS / Linux

```bash
python3 setup.py
python3 ascii_generator.py sample.png
```

### Windows

```text
py setup.py
py ascii_generator.py sample.png
```

`setup.py` creates the virtual environment and installs the only Python dependency automatically.

## Color & Theme

```text
1. Original    - preserve source colours
2. Light       - white background + black ASCII
3. Dark        - black background + white ASCII
4. Custom      - choose foreground + background
5. Multicolour - choose palette + background
6. Additional
```

When `Original` is selected:

```text
Background
1. Preserve Transparent (if available)
2. Original
3. White
4. Black
5. Custom HEX
```

`Original` is the default. It does not force a new background. `Preserve Transparent (if available)` explicitly keeps transparent areas when the source provides them.

## Output Format

```text
1. SVG  - vector, preserves animation and selected background
2. PNG  - best general-purpose image
3. JPEG - smaller, solid background
4. GIF  - animated image
```

The format is selected during the same configuration flow. The program does not create an extra export stage and does not generate unused formats.

## Animations

Normal animations:

- Row Reveal
- Column Reveal
- Diagonal Reveal
- Iris Aperture
- Circular Reveal
- Fade In
- Twinkle
- Sparkle Wave
- Instant

Flag mode is available under `Additional`.

## Sample

`sample.png` is included as a quick example image.

`demo.gif` is included so visitors can see the idea immediately.

![ASCII Profile Generator demo](demo.gif)

## Project structure

Everything needed for the repository lives in the root directory:

```text
ascii-profile-generator/
├── ascii_generator.py
├── ascii_renderer.py
├── exporter.py
├── setup.py
├── requirements.txt
├── README.md
├── LICENSE
├── sample.png
└── demo.gif
```

Generated files such as `avi-ascii.svg`, `avi-ascii.png`, `avi-ascii.jpg`, and `avi-ascii.gif` stay local and are ignored by Git.

## GitHub profile picture

For a GitHub profile picture, PNG or JPEG is the most practical output. The project generates the image locally; it does not change your account automatically.

## License

See [LICENSE](LICENSE).
