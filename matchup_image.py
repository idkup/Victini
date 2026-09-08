"""Renders a draft matchup as a PNG in the style of a speed-tier chart:

  [ You: 3-wide grid ] [ your speeds | opp speeds ] [ Opponent: 3-wide grid ]

Each side shows large sprites (3 per row) with names. The centre holds two
independent Speed ladders -- one per side, one row per mon (icon + value),
sorted fastest first -- so tied speeds never collide and the block stays short.

Pure rendering: callers pass already-fetched sprite bytes and speed values (base
or level-50, the caller's choice), so this module makes no network calls.
"""
from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

# palette
BLUE = (33, 97, 179)
BLUE_DK = (23, 71, 135)
BLUE_TINT = (225, 236, 249)
BLUE_ALT = (238, 244, 252)
RED = (190, 52, 52)
RED_DK = (147, 33, 33)
RED_TINT = (250, 227, 227)
RED_ALT = (252, 240, 240)
INK = (33, 39, 46)
MUTED = (250, 251, 253)
WHITE = (255, 255, 255)

LARGE = 96
SMALL = 34
GRID_COLS = 3
CELL_W = 150
CELL_H = 126
HEADER_H = 48
LADDER_COL_W = 108
LADDER_ROW_H = 42
PAD = 16


def _font(size, bold=False):
    for name in (("arialbd.ttf", "DejaVuSans-Bold.ttf") if bold else ("arial.ttf", "DejaVuSans.ttf")):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _img(data, size):
    if not data:
        return None
    try:
        resample = Image.NEAREST if size >= LARGE else Image.LANCZOS
        return Image.open(BytesIO(data)).convert("RGBA").resize((size, size), resample)
    except Exception:
        return None


def _fit(draw, text, font, max_w):
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return text + "…"


def _header(draw, x0, w, text, fill, font):
    draw.rectangle([x0, 0, x0 + w, HEADER_H], fill=fill)
    tb = draw.textbbox((0, 0), text, font=font)
    draw.text((x0 + (w - (tb[2] - tb[0])) / 2, (HEADER_H - (tb[3] - tb[1])) / 2 - tb[1]),
              text, font=font, fill=WHITE)


def _draw_grid(img, draw, x0, rows, accent, tint, n_rows, name_f):
    grid_w = GRID_COLS * CELL_W
    n = len(rows)
    draw.rectangle([x0, HEADER_H, x0 + grid_w, HEADER_H + n_rows * CELL_H], fill=tint)
    for i, r in enumerate(rows):
        col, row = i % GRID_COLS, i // GRID_COLS
        in_row = min(GRID_COLS, n - row * GRID_COLS)       # mons on this row
        row_offset = (GRID_COLS - in_row) * CELL_W // 2     # center a short (last) row
        cx, cy = x0 + row_offset + col * CELL_W, HEADER_H + row * CELL_H
        sp = _img(r.get("sprite"), LARGE)
        sx = cx + (CELL_W - LARGE) // 2
        if sp is not None:
            img.paste(sp, (sx, cy + 6), sp)
        else:
            draw.rectangle([sx, cy + 6, sx + LARGE, cy + 6 + LARGE], outline=accent, width=2)
        label = _fit(draw, r["species"], name_f, CELL_W - 8)
        draw.text((cx + (CELL_W - draw.textlength(label, font=name_f)) / 2, cy + LARGE + 8),
                  label, font=name_f, fill=INK)


def _draw_ladder(img, draw, x0, rows, accent, tint, alt, num_f, mirror):
    """One side's speed ladder. mirror=False -> icon left, value right (your side);
    mirror=True -> value left, icon right (opponent side)."""
    for i, r in enumerate(rows):
        y = HEADER_H + i * LADDER_ROW_H
        draw.rectangle([x0, y, x0 + LADDER_COL_W, y + LADDER_ROW_H], fill=(alt if i % 2 else tint))
        icon = _img(r.get("sprite"), SMALL)
        iy = y + (LADDER_ROW_H - SMALL) // 2
        s = str(r["speed"])
        sb = draw.textbbox((0, 0), s, font=num_f)
        tw, th = sb[2] - sb[0], sb[3] - sb[1]
        ty = y + (LADDER_ROW_H - th) / 2 - sb[1]
        if not mirror:
            if icon is not None:
                img.paste(icon, (x0 + 6, iy), icon)
            draw.text((x0 + LADDER_COL_W - 10 - tw, ty), s, font=num_f, fill=accent)
        else:
            draw.text((x0 + 10, ty), s, font=num_f, fill=accent)
            if icon is not None:
                img.paste(icon, (x0 + LADDER_COL_W - 6 - SMALL, iy), icon)


def render_matchup(p1_name, p1_rows, p2_name, p2_rows, speed_label="Speed") -> BytesIO:
    """rows: list of {species, speed, sprite(bytes|None)} (any order)."""
    p1_rows = sorted(p1_rows, key=lambda r: -r["speed"])
    p2_rows = sorted(p2_rows, key=lambda r: -r["speed"])

    grid_w = GRID_COLS * CELL_W
    center_w = 2 * LADDER_COL_W
    grid_rows = max((len(p1_rows) + GRID_COLS - 1) // GRID_COLS,
                    (len(p2_rows) + GRID_COLS - 1) // GRID_COLS, 1)
    body_h = max(grid_rows * CELL_H,
                 max(len(p1_rows), len(p2_rows), 1) * LADDER_ROW_H,
                 HEADER_H)
    w = PAD + grid_w + center_w + grid_w + PAD
    h = HEADER_H + body_h + PAD

    img = Image.new("RGB", (w, h), WHITE)
    draw = ImageDraw.Draw(img)
    name_f = _font(15, bold=True)
    num_f = _font(21, bold=True)
    head_f = _font(22, bold=True)

    left_x = PAD
    center_x = PAD + grid_w
    l2_x = center_x + LADDER_COL_W
    right_x = center_x + center_w

    _draw_grid(img, draw, left_x, p1_rows, BLUE, BLUE_TINT, grid_rows, name_f)
    _draw_ladder(img, draw, center_x, p1_rows, BLUE, BLUE_TINT, BLUE_ALT, num_f, mirror=False)
    _draw_ladder(img, draw, l2_x, p2_rows, RED, RED_TINT, RED_ALT, num_f, mirror=True)
    _draw_grid(img, draw, right_x, p2_rows, RED, RED_TINT, grid_rows, name_f)
    draw.line([(l2_x, HEADER_H), (l2_x, HEADER_H + body_h)], fill=(210, 214, 220), width=1)

    _header(draw, left_x, grid_w, p1_name, BLUE, head_f)
    _header(draw, center_x, LADDER_COL_W, speed_label, BLUE_DK, head_f)
    _header(draw, l2_x, LADDER_COL_W, speed_label, RED_DK, head_f)
    _header(draw, right_x, grid_w, p2_name, RED, head_f)

    out = BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    return out
