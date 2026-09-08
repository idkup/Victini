"""Renders a draft matchup as a PNG in the style of a speed-tier chart:

  [ You: 3-wide sprite grid ] [ your speeds | opp speeds ] [ Opponent grid ]

Each side is a grid of large sprites in distinct square cells (no names). The
centre holds two independent Speed ladders -- one per side, one row per mon (icon
+ value), sorted fastest first -- stretched to the full height of the grids so
tied speeds never collide.

Pure rendering: callers pass already-fetched sprite bytes and speed values (base
or level-scaled, the caller's choice), so this module makes no network calls.
"""
from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

# palette
BLUE = (33, 97, 179)
RED = (190, 52, 52)
BLUE_TINT = (223, 235, 249)
BLUE_ALT = (236, 243, 251)
RED_TINT = (250, 226, 226)
RED_ALT = (252, 239, 239)
CELL_BG = (255, 255, 255)
CELL_BORDER = (196, 202, 210)
INK = (33, 39, 46)
WHITE = (255, 255, 255)

LARGE = 100         # big grid sprite
SMALL = 40          # ladder icon
GRID_COLS = 3
CELL_W = 150
GRID_ROW_H = 124
HEADER_H = 58
LADDER_COL_W = 126
LADDER_MIN_ROW = 46
PAD = 16


def _font(size, bold=False):
    for name in (("arialbd.ttf", "DejaVuSans-Bold.ttf") if bold else ("arial.ttf", "DejaVuSans.ttf")):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _sprite(data, size):
    if not data:
        return None
    try:
        resample = Image.NEAREST if size >= LARGE else Image.LANCZOS
        return Image.open(BytesIO(data)).convert("RGBA").resize((size, size), resample)
    except Exception:
        return None


def _header(draw, x0, w, text, fill, font):
    draw.rectangle([x0, 0, x0 + w, HEADER_H], fill=fill)
    tb = draw.textbbox((0, 0), text, font=font)
    draw.text((x0 + (w - (tb[2] - tb[0])) / 2, (HEADER_H - (tb[3] - tb[1])) / 2 - tb[1]),
              text, font=font, fill=WHITE)


def _draw_grid(img, draw, x0, rows, accent, tint, grid_rows, body_h):
    grid_w = GRID_COLS * CELL_W
    draw.rectangle([x0, HEADER_H, x0 + grid_w, HEADER_H + body_h], fill=tint)
    slot_h = body_h / grid_rows
    side = min(CELL_W, slot_h) - 16          # square cell size
    n = len(rows)
    for i, r in enumerate(rows):
        row, col = divmod(i, GRID_COLS)
        in_row = min(GRID_COLS, n - row * GRID_COLS)
        row_off = (GRID_COLS - in_row) * CELL_W / 2    # centre a short (last) row
        ccx = x0 + row_off + col * CELL_W + CELL_W / 2
        ccy = HEADER_H + (row + 0.5) * slot_h
        draw.rounded_rectangle([ccx - side / 2, ccy - side / 2, ccx + side / 2, ccy + side / 2],
                               radius=12, fill=CELL_BG, outline=CELL_BORDER, width=2)
        sp = _sprite(r.get("sprite"), LARGE)
        if sp is not None:
            img.paste(sp, (int(ccx - LARGE / 2), int(ccy - LARGE / 2)), sp)
        else:
            draw.text((ccx, ccy), "?", font=_font(28, bold=True), fill=accent, anchor="mm")


def _draw_ladder(img, draw, x0, rows, accent, tint, alt, num_f, mirror, body_h):
    k = max(len(rows), 1)
    slot_h = body_h / k
    for i, r in enumerate(rows):
        y0 = HEADER_H + i * slot_h
        draw.rectangle([x0, y0, x0 + LADDER_COL_W, y0 + slot_h], fill=(alt if i % 2 else tint))
        cy = y0 + slot_h / 2
        icon = _sprite(r.get("sprite"), SMALL)
        s = str(r["speed"])
        if not mirror:
            if icon is not None:
                img.paste(icon, (int(x0 + 8), int(cy - SMALL / 2)), icon)
            draw.text((x0 + LADDER_COL_W - 12, cy), s, font=num_f, fill=accent, anchor="rm")
        else:
            draw.text((x0 + 12, cy), s, font=num_f, fill=accent, anchor="lm")
            if icon is not None:
                img.paste(icon, (int(x0 + LADDER_COL_W - 8 - SMALL), int(cy - SMALL / 2)), icon)


def render_matchup(p1_name, p1_rows, p2_name, p2_rows, speed_label="Speed") -> BytesIO:
    """rows: list of {species, speed, sprite(bytes|None)} (any order)."""
    p1_rows = sorted(p1_rows, key=lambda r: -r["speed"])
    p2_rows = sorted(p2_rows, key=lambda r: -r["speed"])

    grid_w = GRID_COLS * CELL_W
    center_w = 2 * LADDER_COL_W
    grid_rows = max((len(p1_rows) + GRID_COLS - 1) // GRID_COLS,
                    (len(p2_rows) + GRID_COLS - 1) // GRID_COLS, 1)
    max_ladder = max(len(p1_rows), len(p2_rows), 1)
    body_h = max(grid_rows * GRID_ROW_H, max_ladder * LADDER_MIN_ROW)

    w = PAD + grid_w + center_w + grid_w + PAD
    h = HEADER_H + body_h + PAD

    img = Image.new("RGB", (w, h), WHITE)
    draw = ImageDraw.Draw(img)
    num_f = _font(30, bold=True)
    head_f = _font(34, bold=True)

    left_x = PAD
    center_x = PAD + grid_w
    l2_x = center_x + LADDER_COL_W
    right_x = center_x + center_w

    _draw_grid(img, draw, left_x, p1_rows, BLUE, BLUE_TINT, grid_rows, body_h)
    _draw_ladder(img, draw, center_x, p1_rows, BLUE, BLUE_TINT, BLUE_ALT, num_f, False, body_h)
    _draw_ladder(img, draw, l2_x, p2_rows, RED, RED_TINT, RED_ALT, num_f, True, body_h)
    _draw_grid(img, draw, right_x, p2_rows, RED, RED_TINT, grid_rows, body_h)
    draw.line([(l2_x, HEADER_H), (l2_x, HEADER_H + body_h)], fill=(210, 214, 220), width=1)

    _header(draw, left_x, grid_w, p1_name, BLUE, head_f)
    _header(draw, center_x, LADDER_COL_W, speed_label, (70, 70, 78), head_f)
    _header(draw, l2_x, LADDER_COL_W, speed_label, (70, 70, 78), head_f)
    _header(draw, right_x, grid_w, p2_name, RED, head_f)

    out = BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    return out
