#!/usr/bin/env python
from __future__ import division
import sys, argparse, math, json, os, colorsys
from PIL import Image


""" TODO: index colors via bitshift representation
    rather than hex conversion """


def get_hex(color, mode='rgb'):
    """Get color hex value from rgb (or rgba)"""
    rgb = color[:3]
    return ''.join(map(lambda t: hex(int(t)).split('x', 1)[1], rgb))


def color_diff(c1, c2):
    """Calculates difference betwixt two colors."""
    return sum(map(lambda x: (x[0] - x[1]) ** 2, list(zip(c1[:3], c2[:3]))))


def average_pixel(data, mode='rgb'):
    """Takes a list of pixel data tuples and finds average."""
    return list(map(lambda x: int(round(sum(x) / len(data))), list(zip(*data))[:3]))


def get_closest_color(color, palette, hexdict, mode='rgb'):
    """Find the closest color in the current palette. TODO: optimize!"""
    hexval = get_hex(color, mode)
    if hexval not in hexdict:
        diff_func = color_diff
        hexdict[hexval] = min(palette, key=lambda c: diff_func(color, c))
    return list(hexdict[hexval])  # "list" looks redundant, but we want a *copy* of the color


""" TODO: There's probably a more efficient way to convert rgb => hsv and hls,
    perhaps with numpy """


def phixelate(img, palette, blockSize):
    """Takes a PIL image object, a palette, and a block-size and alters colors in-place. no return val."""
    width, height = img.size
    rgb = img.load()
    blockWidth = int(math.ceil(width / blockSize))
    blockHeight = int(math.ceil(height / blockSize))
    hexdict = {}  # store "closest" colors to avoid repeat computations.

    for x in range(blockWidth):
        xOffset = x * blockSize
        for y in range(blockHeight):
            yOffset = y * blockSize

            container = []  # represents one monochrome "block" of the image
            for xi in range(blockSize):
                if (xi + xOffset) >= width:
                    break
                for yi in range(blockSize):
                    if (yi + yOffset) >= height:
                        break
                    container.append(rgb[xi + xOffset, yi + yOffset])

            # alpha isn't used in finding the color so just pop it off for later
            avg_alpha = int(round(sum(list(zip(*container))[3]) / len(container)))

            # Convert a block to one color -- take the average, and find the closest palette color
            color = average_pixel(container)
            if palette:
                color = get_closest_color(color, palette, hexdict)

            # stick alpha channel back on and convert to tuple
            color.append(avg_alpha)
            color = tuple(map(lambda co: int(round(co)), color))

            for xi in range(blockSize):
                if (xi + xOffset) >= width: break
                for yi in range(blockSize):
                    if (yi + yOffset) >= height: break
                    rgb[xi + xOffset, yi + yOffset] = color


def generate_palette(img, mode='rgb'):
    """Generate a palette json file from an image. Image should NOT have an alpha value!"""
    transform = lambda _, rgb: list(rgb)
    return json.dumps(map(transform, img.getcolors(img.size[0] * img.size[1])))


def exit_script(args, code):
    args.infile.close()
    args.outfile.close()
    sys.exit(code)


def phixel_crop(img, block_size, orientation='tl'):
    """Crop the image so that it fits the block size evenly"""
    width, height = img.size
    newWidth = int((width // block_size) * block_size)
    newHeight = int((height // block_size) * block_size)
    if 'tl' == orientation:
        cropsize = (0, 0, newWidth, newHeight)
    elif 'tr' == orientation:
        cropsize = (width - newWidth, 0, width, newHeight)
    elif 'bl' == orientation:
        cropsize = (0, height - newHeight, newWidth, height)
    elif 'br' == orientation:
        cropsize = (width - newWidth, height - newHeight, width, height)
    return img.crop(cropsize)


if __name__ == "__main__":
    parse = argparse.ArgumentParser(description='Create "pixel art" from a photo', prog='phixelgator',
                                    epilog="Disclaimer: this does not *really* make pixel art,"
                                           " it just reduces the image resolution with preset color palettes.")
    parse.add_argument('-b', '--block', type=int, default=8,
                       help="Block size for phixelization. Default is 8 pixels.")
    parse.add_argument('-p', '--palette',
                       choices=['mario', 'hyrule', 'kungfu', 'tetris', 'contra', 'appleii',
                                'atari2600', 'commodore64', 'gameboy', 'grayscale', 'intellivision', 'nes', 'sega'],
                       help="The color palette to use.")
    parse.add_argument('-c', '--custom', type=argparse.FileType('r'),
                       help="A custom palette file to use instead of the defaults. "
                            "Should be plain JSON file with a single array of color triplets.")
    parse.add_argument('-d', '--dimensions', help="The dimensions of the new image (format: 10x10)")
    parse.add_argument('-t', '--type', choices=['png', 'jpeg', 'gif', 'bmp'], default='png',
                       help="Output file type. Default is 'png'.")
    parse.add_argument('-x', '--crop', choices=['tl', 'tr', 'bl', 'br'],
                       help="If this flag is set, the image will be cropped to conform to the Block Size. "
                            "The argument passed describes what corner to crop from.")
    parse.add_argument('-g', '--generate', action='store_true',
                       help="This flag overrides the default behaviour of "
                             "infile and outfile options -- instead of "
                             "converting the input to a new image, "
                             "a custom palette file will be generated from "
                             "all colors used in the infile photo. Other "
                             "options are ignored.")
    parse.add_argument('infile', nargs='?', type=argparse.FileType('rb'), default=sys.stdin,
                       help="the input file (defaults to stdin)")
    parse.add_argument('outfile', nargs='?', type=argparse.FileType('wb'), default=sys.stdout,
                       help="the output file (defaults to stdout)")
    args = parse.parse_args()

    """ If the -g flag is set, the behaviour of the utility is
      completely altered -- instead of generating a new image,
      a new color-palette json file is generated from the colors
      of the input file. """
    if args.generate is True:
        img = Image.open(args.infile).convert('RGB')
        palette = generate_palette(img)
        args.outfile.write(palette)
        exit_script(args, 0)

    """ Try to load the custom palette if provided:
      Should be formatted as json similar to the
      default palette definitions in this script. """
    palette = False
    if args.custom is not None:
        palette = json.loads(args.custom.read())
        args.custom.close()

    elif args.palette is not None:
        try:
            path = os.sep.join([os.path.dirname(os.path.realpath(__file__)), 'palettes', args.mode, args.palette])
            with open(path + '.json', 'r') as f:
                palette = json.loads(f.read())
        except Exception as e:
            sys.stderr.write("No palette loaded")
            palette = False

    img = Image.open(args.infile).convert('RGBA')

    if args.crop:
        img = phixel_crop(img, args.block, args.crop)

    phixelate(img, palette, args.block)

    """ Try to resize the image and fail gracefully """
    if args.dimensions:
        try:
            imgWidth, imgHeight = map(int, args.dimensions.split('x', 1))
            resized_img = img.resize((imgWidth, imgHeight))
            resized_img.save(args.outfile, args.type)
        except Exception as e:
            sys.stderr.write("Failed to resize image")
            img.save(args.outfile, args.type)
    else:
        img.save(args.outfile, args.type)

    exit_script(args, 0)
