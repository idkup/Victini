"""Test battery for the draft + matchup pipeline.

Builds a Champions draft league (equivalent to `!init <id> champs_ndex 540 180
110`), registers players (`!register`), makes arbitrary legal draft picks for
each, asserts that the draft-legality rules reject illegal picks (over budget,
insufficient reserve to reach the 9-mon minimum, a second Mega, an already-drafted
mon, and the 12-mon cap), then renders ~10 matchup images.

Run:  python matchup_battery.py   (writes PNGs to matchup_battery_out/)
Uses the real domain objects and the same rendering pipeline as the !mu command;
no Discord connection or Google Sheet is involved.
"""
import asyncio
import os
import random

import matchup_image
import pokeapi
from DraftLeague import DraftLeague
from DraftParticipant import DraftParticipant

RULESET = "champs_ndex"
POINTS = 110
OUT = "matchup_battery_out"
PLAYERS = ["Patrick", "Harbar", "Firling", "Kboww", "Raikaa"]  # 5 -> 10 pairings


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


async def main():
    random.seed(7)
    os.makedirs(OUT, exist_ok=True)

    legal_ok = test_illegal_picks()

    # A fresh league with legal teams for the matchup images.
    league = new_league(1)
    players = [register(league, 100 + i, name) for i, name in enumerate(PLAYERS)]
    print("Drafting teams:")
    for p in players:
        n = draft_team(league, p, random.randint(9, 11))
        spent = POINTS - p.get_points()
        print(f"  {p.get_name():9} {n} mons, {spent} pts: "
              + ", ".join(str(m) for m in p.get_pokemon()))
    print()

    rows = {p.get_name(): await rows_for(p) for p in players}
    print(f"Rendering matchups to {OUT}/ ...")
    n = 0
    for i in range(len(players)):
        for j in range(i + 1, len(players)):
            a, b = players[i].get_name(), players[j].get_name()
            png = matchup_image.render_matchup(a, rows[a], b, rows[b], speed_label="Base Spe")
            path = os.path.join(OUT, f"{n:02d}_{a}_vs_{b}.png")
            with open(path, "wb") as fh:
                fh.write(png.getvalue())
            print(f"  {path}")
            n += 1
    print(f"\n{n} matchup images rendered; illegal-pick checks {'PASSED' if legal_ok else 'FAILED'}.")


if __name__ == "__main__":
    asyncio.run(main())
