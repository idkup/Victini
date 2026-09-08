"""Test battery for the draft + matchup pipeline.

Builds a Champions draft league (equivalent to `!init <id> champs_ndex 540 180
110`), registers players (`!register`), makes arbitrary legal draft picks for
each, and asserts that the draft-legality rules reject illegal picks (over budget,
insufficient reserve to reach the 9-mon minimum, a second Mega, an already-drafted
mon, and the 12-mon cap). It then:
  * saves the league to files/leagues.txt so `python bot.py` loads it and the
    !mu command can be exercised from Discord;
  * populates the linked test Google Sheet with each player's block;
  * renders up to N_MATCHUPS matchup images to matchup_battery_out/.

Run:  python matchup_battery.py
Uses the real domain objects, sheet layer, and rendering pipeline. Writing to the
sheet needs files/service_account_key.json and the sheet shared with its email;
if that is missing, sheet population is skipped with a message and the rest runs.
"""
import asyncio
import itertools
import os
import pickle
import random

import matchup_image
import pokeapi
import sheet
from DraftLeague import DraftLeague
from DraftParticipant import DraftParticipant

RULESET = "champs_ndex"
POINTS = 110
OUT = "matchup_battery_out"
PLAYERS = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]
LEAGUE_ID = 1
LEAGUES_FILE = "files/leagues.txt"           # what bot.py loads on startup
N_MATCHUPS = 10                              # cap on rendered matchup images
# Test Google Sheet to populate (must be shared with the service account email).
SHEET_ID = "160fx8a8ljGVkeoS8rYqHEjLeQgt5TmG7wLxdP3TRCrk"
SHEET_TAB = 520719736


def new_league(lid):
    """Equivalent to `!init <lid> champs_ndex 540 180 110`."""
    return DraftLeague(lid, RULESET, 1000 + lid, 540, 180, POINTS)


def register(league, discord_id, name):
    """Equivalent to `!register` / `!forceregister`."""
    p = DraftParticipant(league, discord_id, name, league.get_start_timer(), league.get_start_points())
    league.add_participant(p)
    return p


def draft_team(league, participant, target):
    """Draft `target` arbitrary legal, affordable, non-duplicate mons."""
    pool = [m for m in league.get_all_pokemon() if m.get_owner() is None]
    random.shuffle(pool)
    for mon in pool:
        if len(participant.get_pokemon()) >= target:
            break
        participant.set_mon(mon)  # legal picks accepted; rejections ignored here
    return len(participant.get_pokemon())


def _check(results, label, ok, detail=""):
    results.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" -- {detail}" if detail else ""))


def test_illegal_picks():
    """Assert set_mon rejects each class of illegal pick."""
    print("Illegal-pick validation:")
    lg = new_league(99)
    by_name = {str(m): m for m in lg.get_all_pokemon()}
    by_cost = lambda c: [m for m in lg.get_all_pokemon() if m.get_cost() == c and m.get_owner() is None]
    megas = [m for m in lg.get_all_pokemon() if m.is_mega() and m.get_cost() <= 15]
    results = []

    # 1. already drafted
    a = register(lg, 1, "A")
    b = register(lg, 2, "B")
    shared = [m for m in by_cost(3) if not m.is_mega()][0]  # non-mega, so it won't collide with the Mega test
    _check(results, "first draft of a mon succeeds", a.set_mon(shared) is True)
    r = b.set_mon(shared)
    _check(results, "drafting an already-owned mon is rejected", r != True, repr(r))

    # 2. a second Mega
    c = register(lg, 3, "C")
    _check(results, "first Mega succeeds", c.set_mon(megas[0]) is True)
    r = c.set_mon(megas[1])
    _check(results, "second Mega is rejected", r != True, repr(r))

    # 3. reserve rule: too few points to still reach 9 mons
    d = register(lg, 4, "D")
    d.set_points(8)                      # 0 mons, needs points-cost >= 9-0 = 9
    r = d.set_mon(by_cost(1)[0])
    _check(results, "pick that breaks the 9-mon reserve is rejected", r != True, repr(r))

    # 4. over budget (would go negative)
    e = register(lg, 5, "E")
    e.set_points(3)
    r = e.set_mon(by_cost(10)[0])        # 3 - 10 < 0
    _check(results, "over-budget pick is rejected", r != True, repr(r))

    # 5. 12-mon cap
    f = register(lg, 6, "F")
    cheap = by_cost(1)
    for m in cheap[:12]:
        f.set_mon(m)
    _check(results, "roster filled to 12", len(f.get_pokemon()) == 12)
    r = f.set_mon(cheap[12])
    _check(results, "13th mon is rejected (12 cap)", r != True, repr(r))

    print(f"  => {sum(results)}/{len(results)} checks passed\n")
    return all(results)


async def rows_for(participant):
    rows = []
    for mon in participant.get_pokemon():
        species = str(mon)
        try:
            speed = await pokeapi.base_speed(species)
        except pokeapi.SpeedLookupError:
            speed = 0
        rows.append({"species": species, "speed": speed,
                     "sprite": await pokeapi.sprite_bytes(species)})
    return rows


def populate_sheet(league, players):
    """Write every player's block (owner + roster) to the linked test sheet."""
    print(f"Populating Google Sheet (tab {SHEET_TAB}) ...")
    try:
        ws = sheet.open_worksheet(league.get_sheet_id(), league.get_sheet_tab())
        for p in players:
            idx = p.get_block_index()
            sheet.set_block_owner(ws, idx, p.get_name())
            sheet.sync_block(ws, idx, [str(m) for m in p.get_pokemon()])
        print(f"  wrote {len(players)} blocks to '{ws.title}'.")
    except Exception as e:
        print(f"  sheet population skipped: {type(e).__name__}: {e}")


async def main():
    random.seed(7)
    os.makedirs(OUT, exist_ok=True)

    legal_ok = test_illegal_picks()

    # Build the league (equivalent to !init) and link the test sheet.
    league = new_league(LEAGUE_ID)
    league.set_sheet(SHEET_ID, SHEET_TAB)
    names = PLAYERS[:sheet.BLOCK_COUNT]                      # one block per player
    players = [register(league, 100 + i, n) for i, n in enumerate(names)]
    print("Drafting teams:")
    for i, p in enumerate(players):
        p.set_block_index(i)                                 # block assignment (as at !shuffle)
        n = draft_team(league, p, random.randint(9, 11))
        print(f"  {p.get_name()} (block {sheet.BLOCK_INPUT_COLS[i % sheet.COLS_PER_SET]}"
              f"{'/set2' if i >= sheet.COLS_PER_SET else ''}): {n} mons, {POINTS - p.get_points()} pts")
    print()

    # Save the league so `python bot.py` loads it and !mu works from Discord.
    with open(LEAGUES_FILE, "wb") as f:
        pickle.dump([league], f)
    print(f"Saved league {LEAGUE_ID} to {LEAGUES_FILE} "
          f"(run `python bot.py`, then in Discord: !mu {LEAGUE_ID} {players[0].get_name()} {players[1].get_name()})\n")

    populate_sheet(league, players)

    # Render up to N_MATCHUPS matchup images from random pairings.
    rows = {p.get_name(): await rows_for(p) for p in players}
    pairs = list(itertools.combinations([p.get_name() for p in players], 2))
    random.shuffle(pairs)
    pairs = pairs[:N_MATCHUPS]
    print(f"\nRendering {len(pairs)} matchups to {OUT}/ ...")
    for n, (a, b) in enumerate(pairs):
        png = matchup_image.render_matchup(a, rows[a], b, rows[b])   # default label: "Speed"
        with open(os.path.join(OUT, f"{n:02d}_{a}_vs_{b}.png"), "wb") as fh:
            fh.write(png.getvalue())
    print(f"  {len(pairs)} images written.")
    print(f"\nDone. illegal-pick checks {'PASSED' if legal_ok else 'FAILED'}.")


if __name__ == "__main__":
    asyncio.run(main())
