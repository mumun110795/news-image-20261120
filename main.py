#!/usr/bin/env python3
"""Draw one poster image summing up the world news of Friday 20 November 2026.

Standard library only, no network. Writes $MAKEFUN_OUTPUT_DIR/entry.png
(default /output). The PNG encoder, the bitmap typeface and every drawing
primitive below are implemented in this file. Output is deterministic:
same bytes on every run.
"""

import os
import struct
import zlib

W = 1024
H = 1024

# --------------------------------------------------------------------------
# 5x7 bitmap typeface, drawn by hand for this program.
# Each glyph is 7 rows of 5 pixels; '#' is ink, '.' is blank.
# --------------------------------------------------------------------------

FONT = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", ".#.#.", "..#..", "..#..", "..#..", ".#.#.", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "0": (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "2": (".###.", "#...#", "....#", "..##.", ".#...", "#....", "#####"),
    "3": (".###.", "#...#", "....#", "..##.", "....#", "#...#", ".###."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", "..#..", "..#..", "..#.."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    ".": (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
    ",": (".....", ".....", ".....", ".....", ".##..", ".##..", ".#..."),
    ":": (".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."),
    "'": (".##..", ".##..", ".#...", ".....", ".....", ".....", "....."),
    "&": (".##..", "#..#.", "#.#..", ".#...", "#.#.#", "#..#.", ".##.#"),
    "$": ("..#..", ".####", "#.#..", ".###.", "..#.#", "####.", "..#.."),
    "%": ("##..#", "##.#.", "....#", "...#.", "..#..", ".#...", "#.##."),
    "+": (".....", "..#..", "..#..", ".###.", "..#..", "..#..", "....."),
    "-": (".....", ".....", ".....", ".####", ".....", ".....", "....."),
    "·": (".....", ".....", ".....", ".##..", ".##..", ".....", "....."),
    "/": ("....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."),
    "(": ("...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."),
    ")": (".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."),
    "!": ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
    "?": (".###.", "#...#", "....#", "..##.", "..#..", ".....", "..#.."),
}

GLYPH_W = 5
GLYPH_H = 7


def clean(text):
    """Map fancy punctuation onto glyphs this font carries."""
    return (
        text.replace("—", "-")
        .replace("–", "-")
        .replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .upper()
    )


# --------------------------------------------------------------------------
# Canvas: a plain RGB byte buffer with rectangle / text primitives.
# --------------------------------------------------------------------------


class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(bytes(bg) * (w * h))

    def fill_rect(self, x, y, rw, rh, color):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + rw)
        y1 = min(self.h, y + rh)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1 - x0)
        stride = self.w * 3
        off = (y0 * self.w + x0) * 3
        for _ in range(y0, y1):
            self.px[off : off + len(row)] = row
            off += stride

    def text_width(self, text, scale):
        if not text:
            return 0
        return len(text) * (GLYPH_W + 1) * scale - scale

    def draw_text(self, x, y, text, scale, color):
        text = clean(text)
        cx = x
        for ch in text:
            glyph = FONT.get(ch, FONT[" "])
            for gy, rowbits in enumerate(glyph):
                for gx, bit in enumerate(rowbits):
                    if bit == "#":
                        self.fill_rect(
                            cx + gx * scale, y + gy * scale, scale, scale, color
                        )
            cx += (GLYPH_W + 1) * scale
        return cx - scale - x

    def wrap(self, text, scale, max_width):
        """Greedy word wrap; returns a list of lines that fit max_width."""
        words = clean(text).split()
        lines = []
        cur = ""
        for word in words:
            trial = word if not cur else cur + " " + word
            if self.text_width(trial, scale) <= max_width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines

    def draw_block(self, x, y, text, scale, color, max_width, line_gap):
        """Draw wrapped text; returns the y just past the last line."""
        lines = self.wrap(text, scale, max_width)
        step = GLYPH_H * scale + line_gap
        for i, line in enumerate(lines):
            self.draw_text(x, y + i * step, line, scale, color)
        return y + len(lines) * step - line_gap


# --------------------------------------------------------------------------
# Colours
# --------------------------------------------------------------------------

BG = (13, 20, 32)
PANEL = (23, 36, 55)
PANEL_EDGE = (44, 62, 88)
INK = (242, 245, 249)
SUB = (186, 199, 216)
AMBER = (246, 183, 66)
RED = (226, 66, 66)
ORANGE = (242, 145, 52)
VIOLET = (166, 116, 224)
TEAL = (56, 196, 182)
BLUE = (84, 152, 250)
GREEN = (96, 204, 116)
PINK = (242, 114, 172)


# --------------------------------------------------------------------------
# Poster composition
# --------------------------------------------------------------------------

MARGIN = 28
INNER_W = W - 2 * MARGIN


def panel(cv, x, y, w, h, accent):
    cv.fill_rect(x, y, w, h, PANEL)
    cv.fill_rect(x, y, w, 3, PANEL_EDGE)
    cv.fill_rect(x, y + h - 3, w, 3, PANEL_EDGE)
    cv.fill_rect(x, y, 3, h, PANEL_EDGE)
    cv.fill_rect(x + w - 3, y, 3, h, PANEL_EDGE)
    cv.fill_rect(x, y, w, 9, accent)


def story(cv, x, y, w, h, accent, tag, headline, sub):
    """One news panel: accent bar, small tag, big headline, short sub-line."""
    panel(cv, x, y, w, h, accent)
    pad = 20
    tx = x + pad
    tw = w - 2 * pad
    cy = y + 20
    cv.draw_text(tx, cy, tag, 2, accent)
    cy += GLYPH_H * 2 + 6
    cy = cv.draw_block(tx, cy, headline, 4, INK, tw, 4)
    cy += 8
    cv.draw_block(tx, cy, sub, 2, SUB, tw, 5)


def build_poster():
    cv = Canvas(W, H, BG)

    # ---- header -----------------------------------------------------------
    cv.draw_text(MARGIN, 30, "THE WORLD IN ONE DAY", 8, INK)
    cv.draw_text(MARGIN, 104, "FRIDAY, 20 NOVEMBER 2026", 4, AMBER)
    right = "THE DAY'S NEWS"
    cv.draw_text(W - MARGIN - cv.text_width(right, 4), 104, right, 4, SUB)
    cv.fill_rect(MARGIN, 146, INNER_W, 4, AMBER)

    # ---- lead story -------------------------------------------------------
    lx, ly, lw, lh = MARGIN, 166, INNER_W, 322
    panel(cv, lx, ly, lw, lh, RED)
    pad = 26
    tx = lx + pad
    tw = lw - 2 * pad
    cy = ly + 26
    cv.draw_text(tx, cy, "LEAD · SHENZHEN SUMMIT", 3, RED)
    cy += GLYPH_H * 3 + 10
    cy = cv.draw_block(
        tx, cy, "TRUMP, XI & PUTIN ISSUE JOINT DECLARATION", 6, INK, tw, 8
    )
    cy += 12
    for line in (
        "UN reform · nuclear restraint · more oil output.",
        "Europe's coalition of the willing meets in Berlin: UK, France, "
        "Germany and Ukraine call for a winter energy ceasefire.",
        "Trump says he will meet Kim Jong-un.",
    ):
        cy = cv.draw_block(tx, cy, line, 3, SUB, tw, 6)
        cy += 8

    # ---- grid of six stories ----------------------------------------------
    gx = MARGIN
    gy = 512
    gap = 14
    col_w = (INNER_W - gap) // 2
    row_h = 148
    stories = [
        (
            ORANGE,
            "UKRAINE WAR",
            "KYIV HIT BY FOUR MISSILES",
            "Dutch embassy damaged; Netherlands summons Russia's ambassador.",
        ),
        (
            VIOLET,
            "MIDDLE EAST",
            "HOUTHIS STRIKE SAUDI TARGETS",
            "Drone and missile strikes claimed on four Saudi Arabian targets.",
        ),
        (
            TEAL,
            "ENERGY · HORMUZ",
            "TANKER AFIRE AT HORMUZ",
            "A tanker catches fire after hitting a mine east of the strait.",
        ),
        (
            BLUE,
            "MARKETS · AI",
            "ANTHROPIC: $1.8 TRILLION",
            "Stock leaps 17% in the debut of the first pure AI company listed.",
        ),
        (
            GREEN,
            "INDIA · CLIMATE",
            "80,000 FLEE CYCLONE AKVAN",
            "India evacuates its coast as storm Dana nears Odisha-Andhra.",
        ),
        (
            PINK,
            "EUROPE · TRAVEL",
            "DRONES HALT GENOA FLIGHTS",
            "Genoa airport suspends flights after unidentified drones detected.",
        ),
    ]
    for i, (accent, tag, head, sub) in enumerate(stories):
        x = gx + (i % 2) * (col_w + gap)
        y = gy + (i // 2) * (row_h + gap)
        story(cv, x, y, col_w, row_h, accent, tag, head, sub)

    # ---- footer ticker ------------------------------------------------------
    fy = gy + 3 * row_h + 2 * gap + 12
    cv.fill_rect(MARGIN, fy, INNER_W, 3, PANEL_EDGE)
    cv.draw_text(
        MARGIN,
        fy + 10,
        "VOYAGER 1 REACHES ONE LIGHT-DAY · DENMARK APPROVES GREENLAND "
        "DEFENCE PACT · SERBIA ELECTS A NEW PARLIAMENT SPEAKER",
        1,
        AMBER,
    )
    return cv


# --------------------------------------------------------------------------
# Minimal PNG writer (filter 0 rows, zlib stream, CRC per chunk).
# --------------------------------------------------------------------------


def _chunk(tag, data):
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def encode_png(cv):
    stride = cv.w * 3
    raw = bytearray()
    for y in range(cv.h):
        raw.append(0)
        raw += cv.px[y * stride : (y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    data = encode_png(build_poster())
    with open(os.path.join(out_dir, "entry.png"), "wb") as fh:
        fh.write(data)


if __name__ == "__main__":
    main()
