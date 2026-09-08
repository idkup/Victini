"""Google Sheets integration for draft leagues.

Each league can optionally link a Google Sheet. When linked, a player's picks are
mirrored into their assigned "block" on the sheet: the plain species names are
written down the block's input column (rows 8-18), and the sheet's own formulas
fill in the rest of the block. Blocks are 5 columns apart; the owner name sits in
the merged region one column to the left, at row 5.

Sync is idempotent: a player's whole block column is rewritten from their current
roster on every change, so it self-heals against drift. Writes are best-effort and
run off the event loop by the caller (see bot.push_block).

gspread and a service-account key are only needed when a league actually links a
sheet, so both are imported/loaded lazily -- the bot runs normally without them.
"""
from __future__ import annotations

import os
import re

CREDS_FILE = "files/service_account_key.json"

# The dex sheet abbreviates Mega formes as "-M" (e.g. "Absol-M-Z"), while the
# ruleset JSON / bot use the full "-Mega" spelling. Convert on the way to the
# sheet so written names match its input validation.
_MEGA_RE = re.compile(r"-Mega(?=-|$)")


def to_sheet_name(name: str) -> str:
    """'Absol-Mega-Z' -> 'Absol-M-Z'; names without a Mega forme are unchanged."""
    return _MEGA_RE.sub("-M", name)

# Blocks are laid out in two stacked sets of nine columns. Within a set the
# Pokemon-name input columns are (left to right):
BLOCK_INPUT_COLS = ["O", "T", "Y", "AD", "AI", "AN", "AS", "AX", "BC"]
COLS_PER_SET = len(BLOCK_INPUT_COLS)
# Each set's roster starts at PICK_ROW_STARTS[set] (owner name at OWNER_ROWS[set]);
# the second set sits 16 rows below the first.
PICK_ROW_STARTS = [8, 24]
OWNER_ROWS = [5, 21]
PICK_ROWS = 11              # roster rows per block (e.g. 8..18)
BLOCK_COUNT = COLS_PER_SET * len(PICK_ROW_STARTS)   # 18 blocks total

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_client = None


# ---- pure cell math (no network; unit-tested) -------------------------------

def col_to_index(col: str) -> int:
    """'A' -> 1, 'O' -> 15, 'AA' -> 27."""
    idx = 0
    for ch in col.upper():
        idx = idx * 26 + (ord(ch) - 64)
    return idx


def index_to_col(idx: int) -> str:
    """1 -> 'A', 15 -> 'O', 27 -> 'AA'."""
    col = ""
    while idx:
        idx, rem = divmod(idx - 1, 26)
        col = chr(65 + rem) + col
    return col


def _block_loc(block_index: int):
    """Block index (0..BLOCK_COUNT-1) -> (input col, roster start row, owner row).
    Indices 0..8 are the top set, 9..17 the bottom set."""
    row_set, col_i = divmod(block_index, COLS_PER_SET)
    return BLOCK_INPUT_COLS[col_i], PICK_ROW_STARTS[row_set], OWNER_ROWS[row_set]


def block_range(block_index: int) -> str:
    """Roster range for a block, e.g. block 0 -> 'O8:O18', block 9 -> 'O24:O34'."""
    col, start, _ = _block_loc(block_index)
    return f"{col}{start}:{col}{start + PICK_ROWS - 1}"


def owner_cell(block_index: int) -> str:
    """Owner-name cell for a block (top-left of the merge, one column left of the
    input column), e.g. block 0 -> 'N5', block 9 -> 'N21'."""
    col, _, owner_row = _block_loc(block_index)
    return f"{index_to_col(col_to_index(col) - 1)}{owner_row}"


# ---- Google Sheets access (lazy) --------------------------------------------

def available() -> bool:
    """True if a service-account key is present (integration can be used)."""
    return os.path.exists(CREDS_FILE)


def _get_client():
    global _client
    if _client is None:
        import gspread
        from google.oauth2.service_account import Credentials
        creds = Credentials.from_service_account_file(CREDS_FILE, scopes=_SCOPES)
        _client = gspread.authorize(creds)
    return _client


def open_worksheet(sheet_id: str, tab=None):
    """Open a worksheet by spreadsheet id and tab (gid int, title str, or None
    for the first tab)."""
    spreadsheet = _get_client().open_by_key(sheet_id)
    if tab is None or tab == "":
        return spreadsheet.sheet1
    try:
        gid = int(tab)
    except (TypeError, ValueError):
        return spreadsheet.worksheet(str(tab))
    for ws in spreadsheet.worksheets():
        if ws.id == gid:
            return ws
    raise KeyError(f"No tab with gid {gid} in spreadsheet {sheet_id}")


def sync_block(ws, block_index: int, team_names) -> bool:
    """Rewrite a block's input column from a roster. Returns True if the roster
    overflowed the block (more mons than PICK_ROWS)."""
    names = [to_sheet_name(str(n)) for n in team_names]
    overflow = len(names) > PICK_ROWS
    names = names[:PICK_ROWS] + [""] * (PICK_ROWS - min(len(names), PICK_ROWS))
    ws.update(range_name=block_range(block_index),
              values=[[n] for n in names],
              value_input_option="USER_ENTERED")
    return overflow


def set_block_owner(ws, block_index: int, name: str):
    """Write the owner name into a block's owner cell."""
    ws.update(range_name=owner_cell(block_index),
              values=[[name]],
              value_input_option="USER_ENTERED")
