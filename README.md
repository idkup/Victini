# Victini
Automated Draft League Bot

## Setup

- Requires Python 3.8+. Install dependencies: `pip install -r requirements.txt`
- Put the bot token in `files/key.txt`.
- Run: `python bot.py`
- The **Message Content Intent** must be enabled for the bot in the Discord
  Developer Portal (prefix commands read message text).

## Google Sheet integration (optional, per league)

When a league is linked to a sheet, picks auto-populate that player's block
(names go down the input column, rows 8–18; the sheet's own formulas fill the
rest). It is entirely opt-in — leagues with no linked sheet behave as before.

One-time setup:
1. Create a Google Cloud project and enable the **Google Sheets API**.
2. Create a **service account**, download its JSON key to
   `files/service_account.json` (gitignored).
3. Share each league's sheet with the service account's email as **Editor**.

Usage:
- `!set_sheet <sheet-url-or-id>` — link the current channel's league to a sheet
  (a full URL's `gid` selects the tab).
- `!shuffle` — assigns each player a block (left to right) and writes owner names.
- Picks (`!draft`, auto-drafts, `!release`, etc.) then sync automatically.
- `!resync_sheet` — rewrite every block from current state (backfill / repair).

## Matchup image (`!mu`)

`!mu <league_id> <player1> <player2> [l50|l100]` renders a comparison image:
large sprite grids per side and two independent Speed ladders down the middle.
Speed defaults to base stat; add a trailing `l50` or `l100` for max Level-50 /
Level-100 Speed (31 IV, 252 EV, positive nature). Base Speeds come from PokeAPI
(cached in `files/speeds.json`); sprites are cached under `files/sprites/`. To use
a different sprite host, set `pokeapi.SPRITE_URL_TEMPLATE` to a URL with `{slug}`.

Credits:

harbar20 for sending me down this rabbit hole

Firling

more TBA
