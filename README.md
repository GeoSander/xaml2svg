# XAML2SVG Converter

Python CLI tool to convert a `.xaml` file with a WPF `ResourceDictionary` with `DrawingImage` icons to individual SVG files in an output directory.

:warning: The tool assumes that all `DrawingImage` elements are **square icons** and contain a `Key` attribute formatted like `{name}{size}`, where `{size}` is the width or height of the icon in pixels.
The size is then used to define the SVG `viewBox`.

## Usage

```cmd
python -m xaml2svg input.xaml /svg/output/directory
```

The script will output any conversion issues (e.g. skipped images) to the console.

## Todo

Only `path`, `ellipse`, and (non-rounded) `rect` geometries are supported.
Furthermore, only basic/solid color fills are supported, but not yet `linearGradient` and `radialGradient` for example.
If a gradient is encountered, this shows in the console and the `fill` will then be set to `red`.
