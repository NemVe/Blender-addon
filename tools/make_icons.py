"""Draw the panel's icons: gold line icons, PNG 64x64, on transparent.

    python tools/make_icons.py            writes rigmoves/icons/*.png
    python tools/make_icons.py sheet.png  also writes a contact sheet to look at

Needs Pillow. Each icon is drawn eight times too big and brought down, so the
edges are smooth; every stroke has the same weight and round ends, so the set
reads as one at the 16 to 24 pixels Blender draws it at. The gold is the
add-on's: #C9A76A.
"""

import math
import os
import sys

from PIL import Image, ImageDraw

GOLD = (0xC9, 0xA7, 0x6A)
SIZE = 64
SCALE = 8
STROKE = 6.5

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "rigmoves", "icons")


class Pen:
    """A mask drawn with a round pen, in the 64 by 64 units of the icon."""

    def __init__(self):
        big = SIZE * SCALE
        self.mask = Image.new("L", (big, big), 0)
        self.draw = ImageDraw.Draw(self.mask)

    def dot(self, x, y, r, fill=255):
        s = SCALE
        self.draw.ellipse([(x - r) * s, (y - r) * s, (x + r) * s, (y + r) * s], fill=fill)

    def line(self, points, width=STROKE, closed=False, fill=255):
        points = list(points) + ([points[0]] if closed else [])
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            self.draw.line([x0 * SCALE, y0 * SCALE, x1 * SCALE, y1 * SCALE],
                           fill=fill, width=round(width * SCALE))
        for x, y in points:
            self.dot(x, y, width / 2, fill)

    def polygon(self, points, fill=255):
        self.draw.polygon([(x * SCALE, y * SCALE) for x, y in points], fill=fill)

    def ring(self, cx, cy, r, width=STROKE):
        self.line(arc(cx, cy, r, 0, 360), width, closed=True)

    def image(self):
        small = self.mask.resize((SIZE, SIZE), Image.LANCZOS)
        icon = Image.new("RGBA", (SIZE, SIZE), GOLD + (0,))
        icon.putalpha(small)
        return icon


def arc(cx, cy, r, start, end, step=2.0):
    count = max(int(abs(end - start) / step), 2)
    return [(cx + r * math.cos(math.radians(start + (end - start) * i / count)),
             cy + r * math.sin(math.radians(start + (end - start) * i / count)))
            for i in range(count + 1)]


def capsule(cx, cy, length, width, degrees):
    """The outline of a pill, as a closed run of points."""
    half = (length - width) / 2
    turn = math.radians(degrees)
    out = []
    for centre, a0 in (((half, 0.0), -90.0), ((-half, 0.0), 90.0)):
        for x, y in arc(centre[0], centre[1], width / 2, a0, a0 + 180):
            out.append((cx + x * math.cos(turn) - y * math.sin(turn),
                        cy + x * math.sin(turn) + y * math.cos(turn)))
    return out


def bezier(p0, p1, p2, p3, count=60):
    out = []
    for i in range(count + 1):
        t = i / count
        out.append(tuple((1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * b
                         + 3 * (1 - t) * t ** 2 * c + t ** 3 * d
                         for a, b, c, d in zip(p0, p1, p2, p3)))
    return out


def petal(cx, cy, along, across, degrees, distance):
    """A petal: an ellipse standing `distance` from the centre, along the angle."""
    turn = math.radians(degrees)
    mx, my = cx + distance * math.cos(turn), cy + distance * math.sin(turn)
    out = []
    for i in range(0, 360, 4):
        u, v = along * math.cos(math.radians(i)), across * math.sin(math.radians(i))
        out.append((mx + u * math.cos(turn) - v * math.sin(turn),
                    my + u * math.sin(turn) + v * math.cos(turn)))
    return out


def logo(p):
    # Six petals round an open middle: the flower of the promo, as a mark.
    for degrees in range(-90, 270, 60):
        p.polygon(petal(32, 32, 14.5, 8.6, degrees, 17.5))
    p.dot(32, 32, 5.6, fill=0)


def new_move(p):
    p.line([(32, 13), (32, 51)])
    p.line([(13, 32), (51, 32)])


def record_before(p):
    p.line([(12, 14), (12, 50)])
    p.ring(40, 32, 14)
    p.dot(40, 32, 4.4)


def record_after(p):
    p.line([(52, 14), (52, 50)])
    p.ring(24, 32, 14)
    p.dot(24, 32, 4.4)


def build(p):
    p.line(rounded_square(32, 32, 24, 11), closed=True)
    p.polygon([(26, 21), (26, 43), (45, 32)])
    p.line([(26, 21), (26, 43), (45, 32)], width=3.0, closed=True)


def rounded_square(cx, cy, half, radius):
    out = []
    for (x, y), a0 in (((cx + half - radius, cy - half + radius), -90),
                       ((cx + half - radius, cy + half - radius), 0),
                       ((cx - half + radius, cy + half - radius), 90),
                       ((cx - half + radius, cy - half + radius), 180)):
        out += arc(x, y, radius, a0, a0 + 90)
    return out


def slider(p):
    p.line([(8, 32), (56, 32)])
    p.dot(39, 32, 11.5)
    p.dot(39, 32, 5.2, fill=0)


def ring(p):
    for i in range(6):
        x = 32 + 21.5 * math.cos(math.radians(-90 + 60 * i))
        y = 32 + 21.5 * math.sin(math.radians(-90 + 60 * i))
        p.dot(x, y, 7.0)


def spread(p):
    p.line([(8, 17), (31, 17)])
    p.line([(19, 32), (43, 32)])
    p.line([(32, 47), (56, 47)])


def chain(p):
    p.line(capsule(24, 24, 34, 18, 45), closed=True)
    p.line(capsule(40, 40, 34, 18, 45), closed=True)


def curl(p):
    turns = 1.55
    points = []
    for i in range(0, 121):
        t = i / 120
        angle = math.radians(-90 + 360 * turns * t)
        radius = 3.5 + 20 * t
        points.append((31 + radius * math.cos(angle), 34 + radius * math.sin(angle)))
    p.line(points)


def curve(p):
    p.line(bezier((12, 48), (12, 14), (52, 50), (52, 16)), width=STROKE - 1.0)
    p.dot(12, 48, 6.4)
    p.dot(52, 16, 6.4)


def steps(p):
    p.line([(8, 52), (8, 41), (23, 41), (23, 29), (38, 29), (38, 17), (56, 17)])


def mirror(p):
    for y in (12, 32, 52):
        p.dot(32, y, 3.3)
    p.polygon([(22, 15), (22, 49), (6, 49)])
    p.line([(42, 15), (42, 49), (58, 49)], closed=True)


def combine(p):
    p.ring(23, 32, 15)
    p.ring(41, 32, 15)


def animate(p):
    p.line([(32, 8), (56, 32), (32, 56), (8, 32)], closed=True)


def timing(p):
    p.ring(32, 32, 23)
    p.line([(32, 17), (32, 32), (43, 39)])


def pivot(p):
    p.ring(32, 32, 14)
    p.dot(32, 32, 4.6)
    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        p.line([(32 + 14 * dx, 32 + 14 * dy), (32 + 25 * dx, 32 + 25 * dy)])


ICONS = [logo, new_move, record_before, record_after, build, slider, ring, spread,
         chain, curl, curve, steps, mirror, combine, animate, timing, pivot]


def main():
    os.makedirs(OUT, exist_ok=True)
    drawn = []
    for function in ICONS:
        pen = Pen()
        function(pen)
        image = pen.image()
        image.save(os.path.join(OUT, function.__name__ + ".png"), optimize=True)
        drawn.append((function.__name__, image))
    print("{:d} icons in {:s}".format(len(drawn), OUT))
    if len(sys.argv) > 1:
        sheet(drawn, sys.argv[1])


def sheet(drawn, path):
    """The icons large, and at the sizes Blender draws them, on the panel's grey."""
    cell = 150
    image = Image.new("RGB", (cell * 6, cell * 3 + 10), (45, 45, 45))
    for number, (name, icon) in enumerate(drawn):
        x, y = number % 6 * cell, number // 6 * cell
        image.paste(icon.resize((96, 96), Image.LANCZOS), (x + 6, y + 6), icon.resize((96, 96), Image.LANCZOS))
        for step, size in enumerate((16, 20, 24)):
            small = icon.resize((size, size), Image.LANCZOS)
            big = small.resize((size * 2, size * 2), Image.NEAREST)
            image.paste(big, (x + 6 + step * 50, y + 108 - (size - 16)), big)
    image.save(path)


if __name__ == "__main__":
    main()
