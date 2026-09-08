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

CREDS_FILE = "files/service_account.json"

# The dex sheet abbreviates Mega formes as "-M" (e.g. "Absol-M-Z"), while the
# ruleset JSON / bot use the full "-Mega" spelling. Convert on the way to the
# sheet so written names match its input validation.
_MEGA_RE = re.compile(r"-Mega(?=-|$)")


def to_sheet_name(name: str) -> str:
    """'Absol-Mega-Z' -> 'Absol-M-Z'; names without a Mega forme are unchanged."""
    return _MEGA_RE.sub("-M", name)

# Input columns where each block's Pokemon names are typed, left to right.
BLOCK_INPUT_COLS = ["O", "T", "Y", "AD", "AI", "AN", "AS", "AX", "BC"]
BLOCK_COUNT = len(BLOCK_INPUT_COLS)
PICK_ROW_START = 8          # first roster row in a block's input column
PICK_ROWS = 11              # rows 8..18 inclusive
OWNER_ROW = 5               # owner name row (merged region <col-1>5:<col+2>7)

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


def block_range(input_col: str) -> str:
    """Input column letter -> the roster range, e.g. 'O' -> 'O8:O18'."""
    end = PICK_ROW_START + PICK_ROWS - 1
    return f"{input_col}{PICK_ROW_START}:{input_col}{end}"


def owner_cell(input_col: str) -> str:
    """Input column letter -> the owner-name cell (top-left of the merge),
    one column to the left at OWNER_ROW, e.g. 'O' -> 'N5'."""
    return f"{index_to_col(col_to_index(input_col) - 1)}{OWNER_ROW}"


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


def sync_block(ws, input_col: str, team_names) -> bool:
    """Rewrite a block's input column from a roster. Returns True if the roster
    overflowed the block (more mons than PICK_ROWS)."""
    names = [to_sheet_name(str(n)) for n in team_names]
    overflow = len(names) > PICK_ROWS
    names = names[:PICK_ROWS] + [""] * (PICK_ROWS - min(len(names), PICK_ROWS))
    ws.update(range_name=block_range(input_col),
              values=[[n] for n in names],
              value_input_option="USER_ENTERED")
    return overflow


def set_block_owner(ws, input_col: str, name: str):
    """Write the owner name into a block's owner cell."""
    ws.update(range_name=owner_cell(input_col),
              values=[[name]],
              value_input_option="USER_ENTERED")
