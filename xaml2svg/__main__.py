"""
python -m xaml2svg

Converts WPF ResourceDictionary DrawingImage icons to SVG files.
"""

# import uuid
import os
import sys
import argparse
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ETree

NS_ROOT = 'http://schemas.microsoft.com/winfx/2006/xaml/presentation'
NS_KEYS = 'http://schemas.microsoft.com/winfx/2006/xaml'

ATTR_KEY = f'{{{NS_KEYS}}}Key'
ATTR_X = 'X'
ATTR_Y = 'Y'
ATTR_ANGLE = 'Angle'
ATTR_RECT = 'Rect'
ATTR_GEOMETRY = 'Geometry'
ATTR_BRUSH = 'Brush'
ATTR_COLOR = 'Color'
ATTR_OPACITY = 'Opacity'
ATTR_CENTER = 'Center'
ATTR_OFFSET = 'Offset'
ATTR_RADIUS_X = 'RadiusX'
ATTR_RADIUS_Y = 'RadiusY'
ATTR_GRADIENT_ORIGIN = 'GradientOrigin'
ATTR_MAPPING_MODE = 'Absolute'
ATTR_TRANSFORM = 'Transform'
ATTR_STARTPOINT = 'StartPoint'
ATTR_ENDPOINT = 'EndPoint'
ATTR_SPREAD_METHOD = 'SpreadMethod'

ELEM_DRAWING_IMAGE = f'{{{NS_ROOT}}}DrawingImage'
ELEM_DRAWING_IMAGE_DRAWING = f'{{{NS_ROOT}}}DrawingImage.Drawing'
ELEM_DRAWING_GROUP = f'{{{NS_ROOT}}}DrawingGroup'
ELEM_DRAWING_GROUP_TRANSFORM = f'{ELEM_DRAWING_GROUP}.Transform'
ELEM_TRANSFORM_GROUP = f'{{{NS_ROOT}}}TransformGroup'
ELEM_TRANSFORM_ROTATE = f'{{{NS_ROOT}}}RotateTransform'
ELEM_TRANSFORM_TRANSLATE = f'{{{NS_ROOT}}}TranslateTransform'
ELEM_GEOMETRY_DRAWING = f'{{{NS_ROOT}}}GeometryDrawing'
ELEM_GEOMETRY_DRAWING_BRUSH = f'{ELEM_GEOMETRY_DRAWING}.{ATTR_BRUSH}'
ELEM_GEOMETRY_DRAWING_GEOMETRY = f'{ELEM_GEOMETRY_DRAWING}.{ATTR_GEOMETRY}'
ELEM_ELLIPSE = f'{{{NS_ROOT}}}EllipseGeometry'
ELEM_RECTANGLE = f'{{{NS_ROOT}}}RectangleGeometry'
ELEM_GEOMETRY_GROUP = f'{{{NS_ROOT}}}GeometryGroup'
ELEM_RADIAL_GRADIENT_BRUSH = f'{{{NS_ROOT}}}RadialGradientBrush'
ELEM_LINEAR_GRADIENT_BRUSH = f'{{{NS_ROOT}}}LinearGradientBrush'
ELEM_SOLID_COLOR_BRUSH = f'{{{NS_ROOT}}}SolidColorBrush'
ELEM_GRADIENT_STOP = f'{{{NS_ROOT}}}GradientStop'

NO_COLOR = 'none'
FULL_OPACITY = '1'


def scale(value, value_max, scaled_max):
    """ Scales a value using the same scale factor required to scale from value_max to scaled_max.
    The output is clamped between 0 and scaled_max, so negative values are not allowed.
    """
    if not value or value_max == 0:
        return 0
    factor = value / value_max
    return max(0, min(scaled_max * factor, scaled_max))


def svg_root(viewsize: int, name: str) -> ETree.Element:
    """ Creates the SVG root element. """
    return ETree.Element('svg', viewBox=f'0 0 {viewsize} {viewsize}', xmlns='http://www.w3.org/2000/svg', id=name)


def svg_group(parent: ETree.Element, tf_elem: Optional[ETree.Element]):
    """ Turns a DrawingGroup into an SVG group (g), optionally with a transformation applied to it. """
    transform = []
    if tf_elem is not None:
        tf_elem = tf_elem.find(ELEM_TRANSFORM_GROUP) or tf_elem
        translate = tf_elem.find(ELEM_TRANSFORM_TRANSLATE)
        if translate is not None:
            transform.append(f'translate({translate.attrib[ATTR_X]},{translate.attrib[ATTR_Y]})')
        rotate = tf_elem.find(ELEM_TRANSFORM_ROTATE)
        if rotate is not None:
            transform.append(f'rotate({rotate.attrib[ATTR_ANGLE]})')
    if transform:
        return ETree.SubElement(parent, 'g', transform=' '.join(transform))
    else:
        return ETree.SubElement(parent, 'g')


# TODO: support gradients?
# def svg_radial_gradient(brush: ETree.Element) -> ETree.Element:
#     cx, cy = brush.attrib.get(ATTR_CENTER, '0,0').split(',')
#     radius_x = brush.attrib.get(ATTR_RADIUS_X)
#     radius_y = brush.attrib.get(ATTR_RADIUS_Y)
#     fx, fy = brush.attrib.get(ATTR_GRADIENT_ORIGIN, '0,0').split(',')
#     mode = brush.attrib.get(ATTR_MAPPING_MODE, '').lower()
#     transform = brush.attrib.get(ATTR_TRANSFORM)
#     # spread = brush.attrib.get(ATTR_SPREAD_METHOD)  TODO (defaults to 'pad')
#
#     gradient = ETree.Element('radialGradient', cx=cx, cy=cy)
#     if mode == 'absolute':
#         gradient.attrib['gradientUnits'] = 'userSpaceOnUse'
#     elif mode == 'relativetoboundingbox':
#         gradient.attrib['gradientUnits'] = 'objectBoundingBox'
#     if transform is not None:
#         gradient.attrib['gradientTransform'] = transform
#
#
# def svg_linear_gradient(brush: ETree.Element) -> ETree.Element:
#     start = brush.attrib.get(ATTR_STARTPOINT)
#     stop = brush.attrib.get(ATTR_ENDPOINT)
#     mode = brush.attrib.get(ATTR_MAPPING_MODE)
#     # spread = brush.attrib.get(ATTR_SPREAD_METHOD)  TODO (defaults to 'pad')


def split_argb(color: str) -> tuple[str, str]:
    """ Converts WPF ARGB colors to SVG RGB and an opacity value.
    Leaves non-hexadecimal color types unchanged. The default opacity value is 1. """
    if not color.startswith('#') or (color.startswith('#') and len(color) == 7):
        # Named color or already RGB hex
        if color.lower() == 'transparent':
            color = NO_COLOR
        return color.lower(), FULL_OPACITY

    # Convert hex opacity to decimal
    opacity = scale(int.from_bytes(bytes.fromhex(color[1:3]), 'little'), 255, 1)
    return f'#{color[3:].lower()}', str(round(opacity, 2))


def process_brush(brush: ETree.Element, defs: ETree.Element) -> tuple[str, str]:
    """ Processes a GeometryDrawing.Brush element to turn it into an SVG fill and fill-opacity. """

    try:
        # Actual brush definition is first child
        brush = brush[0]
    except IndexError:
        print(f"Empty GeometryDrawing.Brush element encountered")
        return NO_COLOR, FULL_OPACITY

    if brush.tag == ELEM_SOLID_COLOR_BRUSH:
        # Process solid color brush
        color = brush.attrib.get(ATTR_COLOR, '')
        if not color or color.lower() == 'transparent' or not color.startswith('#'):
            # No supported color or transparent: output 'none'
            return NO_COLOR, FULL_OPACITY
        opacity = brush.attrib.get(ATTR_OPACITY, FULL_OPACITY)

    else:
        print('Gradient brushes are not supported yet: setting color to "red"')
        color = 'red'
        opacity = FULL_OPACITY
        # # Process gradient brush TODO
        # gradient = None
        # if brush.tag == ELEM_RADIAL_GRADIENT_BRUSH:
        #     gradient = svg_radial_gradient(brush)
        # elif brush.tag == ELEM_LINEAR_GRADIENT_BRUSH:
        #     gradient = svg_linear_gradient(brush)
        # if isinstance(gradient, ETree.Element):
        #     defs.append(gradient)
        #     result = f"url('#{gradient.attrib['id']}')"

    return color, opacity


def svg_path(parent: ETree.Element, path_elem: ETree.Element, defs: ETree.Element):
    """ Turns a GeometryDrawing into an SVG path, ellipsis, or rect. """
    fill = path_elem.attrib.get(ATTR_BRUSH, path_elem.find(ELEM_GEOMETRY_DRAWING_BRUSH))
    if isinstance(fill, str):
        fill, opacity = split_argb(fill)
    else:
        fill, opacity = process_brush(fill, defs)

    sub_elem = None
    geometry = path_elem.attrib.get(ATTR_GEOMETRY, path_elem.find(ELEM_GEOMETRY_DRAWING_GEOMETRY))
    if isinstance(geometry, str):
        sub_elem = ETree.SubElement(parent, 'path', d=geometry.removeprefix('F1 '), fill=fill)
    else:
        # First child is actual geometry object
        geometry = geometry[0]
        if geometry.tag == ELEM_GEOMETRY_GROUP and len(geometry) == 1:
            # Dig one level deeper (support GeometryGroup with 1 element)
            geometry = geometry[0]
        if geometry.tag == ELEM_ELLIPSE:
            # <ellipse cx="100" cy="50" rx="100" ry="50" />
            cx, cy = geometry.attrib.get(ATTR_CENTER, '0,0').split(',')
            radius_x = geometry.attrib.get(ATTR_RADIUS_X, '1')
            radius_y = geometry.attrib.get(ATTR_RADIUS_Y, '1')
            sub_elem = ETree.SubElement(parent, 'ellipse', cx=cx, cy=cy, rx=radius_x, ry=radius_y, fill=fill)
        elif geometry.tag == ELEM_RECTANGLE:
            # <rect x="120" y="5" width="100" height="100" />
            x, y, width, height = geometry.attrib.get(ATTR_RECT, '0,0,1,1')
            sub_elem = rectangle = ETree.SubElement(parent, 'rect', width=width, height=height, fill=fill)
            if x > 0:
                rectangle.attrib['x'] = x
            if y > 0:
                rectangle.attrib['y'] = y
        else:
            print(f'Encountered an unsupported geometry of type {geometry.tag}')

    # Set fill opacity if needed
    if sub_elem is not None and float(opacity) < 1:
        sub_elem.attrib['fill-opacity'] = opacity


def image_size(k: str) -> Optional[int]:
    """ Extracts the pixel size from a DrawingImage key.
    Supports sizes 8, 12, 16, 24, 32, 48, 96, and 128.
    """
    if isinstance(k, str):
        for s in (8, 12, 16, 24, 32, 48, 64, 96, 128):
            num = str(s)
            if k.endswith(num):
                return s
    return None


def walk(elem_in: ETree.Element, parent_out: ETree.Element, defs: ETree.Element):
    """ Walks all child elements of the DrawingImage and converts them into their SVG counterpart. """
    if elem_in.tag == ELEM_DRAWING_GROUP:
        transform = elem_in.find(ELEM_DRAWING_GROUP_TRANSFORM)
        parent_group = svg_group(parent_out, transform)
        for item in elem_in:
            walk(item, parent_group, defs)
    elif elem_in.tag == ELEM_GEOMETRY_DRAWING:
        svg_path(parent_out, elem_in, defs)


def drawing_to_svg(xaml: ETree.Element, viewsize: int, name: str) -> ETree.Element:
    """ Turns a DrawingImage into an SVG object. """
    root_out = svg_root(viewsize, name)
    defs = ETree.Element('defs')
    for item in xaml:
        walk(item, root_out, defs)
    # if len(defs) > 0: TODO: support gradient brushes
    #     root_out.insert(0, defs)
    return root_out


def main(xaml_file: Path, output_dir: Path):
    """ Reads the XAML file and converts DrawingImage children to SVG files. """

    with open(xaml_file) as fp:
        tree = ETree.parse(fp)

    # Get ResourceDictionary
    root = tree.getroot()

    # Iterate all DrawingImage objects
    for img in root.findall(ELEM_DRAWING_IMAGE):
        # Get image Key
        key = img.attrib.get(ATTR_KEY)
        if not key:
            print(f"Skipping element without name: {img}")
            continue

        # Extract size from key
        size = image_size(key)
        if size is None:
            print(f"Skipping element without valid size in Key attribute: {key}")
            continue

        # Get drawing
        drawing = img.find(ELEM_DRAWING_IMAGE_DRAWING)
        if drawing is None:
            print(f"Skipping element without Drawing content: {key}")
            continue

        # Convert drawing to SVG and write file
        svg_out = drawing_to_svg(drawing, size, key)
        tree_out = ETree.ElementTree(svg_out)
        ETree.indent(tree_out)
        tree_out.write(output_dir / Path(key).with_suffix('.svg'))


if __name__ == '__main__':
    # Check input arguments (XAML path and output directory)
    ap = argparse.ArgumentParser('xaml2svg', description='Converts WPF ResourceDictionary with DrawingImage '
                                                         'elements into separate SVG files.')
    ap.add_argument('xaml', type=Path, help='XAML input file')
    ap.add_argument('outdir', type=Path, help='SVG output directory')
    try:
        ns = ap.parse_args()
        if not ns.xaml.is_file() or ns.xaml.suffix != '.xaml':
            raise argparse.ArgumentError(ns.xaml, f"Input path argument does not exist or is not a XAML file.")
        if ns.outdir.is_file():
            raise argparse.ArgumentError(ns.outdir, f"Output directory argument is a file path.")
    except (argparse.ArgumentTypeError, argparse.ArgumentError) as e:
        print(str(e), file=sys.stderr)
        ap.print_help()
        exit(2)

    if not ns.outdir.exists():
        os.makedirs(ns.outdir)

    # Execute
    try:
        main(ns.xaml, ns.outdir)
    except Exception as e:
        raise
