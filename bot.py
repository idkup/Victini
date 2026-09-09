import json
import re
import time

from DraftLeague import DraftLeague
from DraftParticipant import DraftParticipant
from ParseReplay import parse_replay
import sheet
import pokeapi
import matchup_image
import asyncio
import discord
from discord import Embed
from discord.ext import commands
import pickle
import requests

admin_ids = [590336288935378950, 167690209821982721, 173733502041325569, 263127883973787648, 194925053463363585,
             175763247176220672, 142796252243951616, 974026524003024917]

# discord.py 2.x requires intents to be declared explicitly. Prefix commands
# read message text, which is a privileged intent: message_content must be
# enabled here AND toggled on for the bot in the Discord Developer Portal.
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)


# ---- shared helpers ---------------------------------------------------------

def league_by_id(l_id):
    """Return the league with the given ID, or None."""
    for l in leagues:
        if l.get_id() == int(l_id):
            return l
    return None


def league_by_channel(channel_id):
    """Return the league whose drafting channel is channel_id, or None."""
    for l in leagues:
        if l.get_channel() == channel_id:
            return l
    return None


async def require_admin(ctx):
    """Warn and return True if the caller is not an admin (so callers can
    `if await require_admin(ctx): return`)."""
    if ctx.author.id not in admin_ids:
        await ctx.send("This is an admin-only command.")
        return True
    return False


# Base Speed lookups and sprites for matchups live in pokeapi.py (cached on disk).


# ---- Google Sheet sync (optional per league) --------------------------------

# Sheet writes are coalesced and throttled to at most one flush per league every
# SYNC_COOLDOWN seconds: a burst of picks marks blocks dirty and a single delayed
# flush writes the latest state (sync_block is idempotent), keeping well under
# Google's write quota and letting rapid test/draft activity run smoothly.
SYNC_COOLDOWN = 30
_sync_state = {}   # league id -> {"last": float, "task": Task|None, "dirty": {pid:(participant,owner)}, "dest": messageable}

# Serializes draft-progression sends between the manual !draft/!forcedraft handlers
# and the timer loop (which auto-resolves predrafts and missed picks). Without it a
# predraft the timer executes for the *next* picker can race ahead of the manual
# pick that advanced the turn to them, printing out of order.
draft_lock = asyncio.Lock()


async def push_block(dest, league, participant, owner=False):
    """Queue a best-effort sheet sync of a participant's block. No-op if the league
    has no linked sheet or the player has no assigned block. Coalesced/throttled to
    one flush per league per SYNC_COOLDOWN; failures report to `dest` but never
    affect the draft."""
    if league.get_sheet_id() is None:
        return
    idx = participant.get_block_index()
    if idx is None or idx >= sheet.BLOCK_COUNT:
        return
    st = _sync_state.setdefault(league.get_id(), {"last": 0.0, "task": None, "dirty": {}, "dest": dest})
    st["dest"] = dest
    pid = participant.get_discord()
    st["dirty"][pid] = (participant, owner or st["dirty"].get(pid, (None, False))[1])
    if st["task"] is None or st["task"].done():
        st["task"] = asyncio.create_task(_flush_league_blocks(league))


async def _flush_league_blocks(league):
    """After the cooldown, write every block dirtied since the last flush."""
    st = _sync_state[league.get_id()]
    delay = SYNC_COOLDOWN - (time.monotonic() - st["last"])
    if delay > 0:
        await asyncio.sleep(delay)
    st["last"] = time.monotonic()
    st["task"] = None
    dest = st["dest"]
    jobs = []
    for participant, owner in st["dirty"].values():
        idx = participant.get_block_index()
        if idx is None or idx >= sheet.BLOCK_COUNT:
            continue
        jobs.append((idx,
                     [str(m) for m in participant.get_pokemon()],
                     participant.get_name() if owner else None,
                     participant.get_name()))
    st["dirty"] = {}
    if not jobs:
        return

    def work():
        ws = sheet.open_worksheet(league.get_sheet_id(), league.get_sheet_tab())
        overflowed = []
        for block_idx, names, owner_name, pname in jobs:
            if owner_name is not None:
                sheet.set_block_owner(ws, block_idx, owner_name)
            if sheet.sync_block(ws, block_idx, names):
                overflowed.append(pname)
        return overflowed

    loop = asyncio.get_running_loop()
    try:
        overflowed = await loop.run_in_executor(None, work)
    except Exception as e:
        if dest is not None:
            await dest.send(f":warning: Sheet sync failed: {e}")
        return
    for pname in overflowed:
        if dest is not None:
            await dest.send(f":warning: {pname}'s roster exceeds the "
                            f"{sheet.PICK_ROWS}-slot block; extra Pokemon were not written to the sheet.")


async def resync_all(dest, league):
    """Rewrite every assigned block (owners + rosters) from current state, opening
    the worksheet once. Used by !shuffle and !resync_sheet. Any participant without
    a block yet is assigned a free one first, so a sheet linked after the draft has
    finished (when !shuffle is no longer allowed) can still be populated."""
    if league.get_sheet_id() is None:
        return await dest.send("No sheet is linked to this league. Use !set_sheet first.")

    participants = league.get_participants()
    unassigned = [p for p in participants if p.get_block_index() is None]
    if unassigned:
        used = {p.get_block_index() for p in participants if p.get_block_index() is not None}
        free = [i for i in range(sheet.BLOCK_COUNT) if i not in used]
        if len(free) < len(unassigned):
            return await dest.send(
                f"Too many participants ({len(participants)}) for the {sheet.BLOCK_COUNT} "
                f"blocks on the linked sheet; cannot assign blocks.")
        for p, idx in zip(unassigned, free):
            p.set_block_index(idx)
        with open('files/leagues.txt', 'wb+') as f:
            pickle.dump(leagues, f)

    def work():
        ws = sheet.open_worksheet(league.get_sheet_id(), league.get_sheet_tab())
        done = []
        for p in league.get_participants():
            idx = p.get_block_index()
            if idx is None or idx >= sheet.BLOCK_COUNT:
                continue
            sheet.set_block_owner(ws, idx, p.get_name())
            sheet.sync_block(ws, idx, [str(m) for m in p.get_pokemon()])
            done.append(p.get_name())
        return done

    loop = asyncio.get_running_loop()
    try:
        done = await loop.run_in_executor(None, work)
    except Exception as e:
        return await dest.send(f":warning: Sheet resync failed: {e}")
    # count this manual full sync against the throttle window
    _sync_state.setdefault(league.get_id(), {"last": 0.0, "task": None, "dirty": {}, "dest": dest})["last"] = time.monotonic()
    if done:
        await dest.send("Sheet blocks synced for: " + ", ".join(done))
    else:
        await dest.send("No participants to sync yet.")


@bot.command()
async def available(ctx, l_id, cost):
    """Wrapper for DraftLeague.available_pokemon()"""
    league = league_by_id(l_id)
    if league is None:
        return await ctx.send("Invalid league ID.")
    av = league.available_pokemon(int(cost))
    if len(av) <= 100:
        return await ctx.send("Available Pokemon with cost {}: {}".format(cost, ", ".join(av)))
    await ctx.send("Available Pokemon with cost {}:".format(cost))
    for i in range(0, len(av), 100):
        await ctx.send(", ".join(av[i:i+100]))


@bot.command()
async def close_trades(ctx):
    """Ends free agency in the identified league."""
    if await require_admin(ctx):
        return
    league = league_by_channel(ctx.channel.id)
    if league is None:
        return await ctx.send("This is not a drafting channel.")
    if league.get_phase() != 2:
        return await ctx.send("Free agency is not currently open.")
    league.next_phase()
    return await ctx.send("Trades are now closed in this league.")


@bot.command()
async def debug_add_pokemon(ctx, name, cost):
    """Adds a Pokemon to a DraftLeague already in progress. Formerly debug_aggs(). Admin command."""
    if await require_admin(ctx):
        return
    league = league_by_channel(ctx.channel.id)
    if league is None:
        return await ctx.send("This is not a drafting channel!")
    try:
        cost = int(cost)
    except ValueError:
        return await ctx.send("Cost must be an integer.")
    league.add_pokemon(name, cost)
    return await ctx.send("{} added to this league at cost {}.".format(name, cost))


@bot.command()
async def debug_cost(ctx, mon, cost):
    """Changes the cost of a specific Pokemon in that DraftLeague. Admin command."""
    if await require_admin(ctx):
        return
    league = league_by_channel(ctx.channel.id)
    if league is None:
        return await ctx.send("This is not a drafting channel!")
    try:
        cost = int(cost)
    except ValueError:
        return await ctx.send("Cost must be an integer.")
    for p in league.get_all_pokemon():
        if str(p).lower() == mon.lower():
            p.set_cost(cost)
            return await ctx.send("{} now costs {}.".format(mon, cost))
    return await ctx.send("Could not find {}".format(mon))


@bot.command()
async def debug_rename(ctx, mon, name):
    """Changes the name of a specific Pokemon in that DraftLeague. Admin command."""
    if await require_admin(ctx):
        return
    league = league_by_channel(ctx.channel.id)
    if league is None:
        return await ctx.send("This is not a drafting channel!")
    for p in league.get_all_pokemon():
        if str(p).lower() == mon.lower():
            p.set_name(name)
            return await ctx.send("{} is now {}.".format(mon, name))
    return await ctx.send("Could not find {}".format(mon))


@bot.command()
async def debug_draft(ctx, l_id, d_id, *args):
    """Adds a Pokemon to a player's team. Admin command."""

    league = league_by_id(l_id)
    if league is None:
        return await ctx.send("Invalid league ID.")
    for p in league.get_participants():
        if p.get_discord() == int(d_id):
            picker = p
            break
    else:
        return await ctx.send("The specified ID is not in this draft!")
    name = " ".join(args)
    for mon in league.get_all_pokemon():
        if str(mon).lower() == name.strip().lower():
            to_draft = mon
            break
    else:
        return await ctx.send("The Pokemon you are attempting to draft is not recognized!")
    picker.set_mon(to_draft)
    await ctx.send("Attempted to add {} to <@{}>'s team.".format(to_draft, picker.get_discord()))
    await push_block(ctx, league, picker)


@bot.command()
async def debug_increment(ctx, l_id, s):
    """Changes the increment of the pick timer. Admin command."""
    if await require_admin(ctx):
        return
    league = league_by_id(l_id)
    if league is None:
        return await ctx.send("Invalid league ID.")
    league.set_increment(int(s))
    return await ctx.send("Draft timer increment for league {} is now {} seconds.".format(l_id, s))


@bot.command()
async def debug_phase(ctx, l_id, phase="0"):
    """Sets the phase in a league. Admin command."""
    if await require_admin(ctx):
        return
    league = league_by_id(l_id)
    if league is None:
        return await ctx.send("Invalid league ID.")
    league.set_phase(int(phase))
    return await ctx.send("Phase of league {} set to {}".format(league.get_id(), league.get_phase()))


@bot.command()
async def debug_leagues(ctx):
    """Prints all leagues with their current phase. Admin command."""
    if await require_admin(ctx):
        return
    await ctx.send("Current leagues: \n{}".format("\n".join(["ID: {} Phase: {}".format(
        l.get_id(), l.get_phase()) for l in leagues])))


@bot.command()
async def debug_participants(ctx, l_id):
    """Rebuilds all participant objects in the league. Admin command."""
    if await require_admin(ctx):
        return
    league = league_by_id(l_id)
    if league is None:
        return await ctx.send("Invalid league ID.")
    lp = []
    for p in league.get_participants():
        lp.append([league, p.get_discord(), p.get_name()])
    league.clear_participants()
    for p in lp:
        league.add_participant(DraftParticipant(p[0], int(p[1]), p[2], league.get_start_timer()))
    for pk in league.get_all_pokemon():
        o = pk.get_owner()
        if o is not None:
            for p in league.get_participants():
                if o.get_discord() == p.get_discord():
                    pk.set_owner(None)
                    p.set_mon(pk)
                    continue

    await ctx.send("Participant objects rebuilt in league {}".format(l_id))


@bot.command()
async def debug_pickorder(ctx, l_id):
    """Debugs pick order. Admin command."""
    if await require_admin(ctx):
        return
    league = league_by_id(l_id)
    if league is None:
        return await ctx.send("Invalid league ID.")
    league.set_pick_order()
    return await ctx.send("Pick order debugged.")


@bot.command()
async def debug_predraft(ctx, l_id):
    """Wipes all predrafts. Admin command."""
    if await require_admin(ctx):
        return
    league = league_by_id(l_id)
    if league is None:
        return await ctx.send("Invalid league ID.")
    for p in league.get_participants():
        p.set_next_pick([])
    return await ctx.send(f"All predrafts wiped in league {l_id}.")


@bot.command()
async def debug_points(ctx, l_id, pts):
    """Debugs starting points. Admin command."""
    if await require_admin(ctx):
        return
    league = league_by_id(l_id)
    if league is None:
        return await ctx.send("Invalid league ID.")
    for p in league.get_participants():
        new_pts = int(pts)
        for m in p.get_pokemon():
            new_pts -= m.get_cost()
        p.set_points(new_pts)
        await ctx.send(f"{p.get_name()} now has {p.get_points()} points remaining.")
    return await ctx.send(f"League {l_id} points per participant set to {pts}.")


@bot.command()
async def debug_add_after_draft(ctx, l_id, d_id, *args):
    """Adds a Pokemon to a player's team. Admin command."""
    if await require_admin(ctx):
        return
    league = league_by_id(l_id)
    if league is None:
        return await ctx.send("Invalid league ID.")
    for p in league.get_participants():
        if p.get_discord() == int(d_id):
            player = p
            break
    else:
        return await ctx.send("The specified ID is not in this draft!")
    name = " ".join(args)
    for mon in league.get_all_pokemon():
        if str(mon).lower() == name.strip().lower():
            to_add = mon
            break
    else:
        return await ctx.send("The Pokemon you are attempting to draft is not recognized!")
    player.set_mon(to_add)
    await ctx.send("Attempted to add {} to <@{}>'s team.".format(to_add, player.get_discord()))
    await push_block(ctx, league, player)


@bot.command()
async def debug_release(ctx, l_id, d_id, *args):
    """Removes a Pokemon from a player's team. Admin command."""
    if await require_admin(ctx):
        return
    league = league_by_id(l_id)
    if league is None:
        return await ctx.send("Invalid league ID.")
    for p in league.get_participants():
        if p.get_discord() == int(d_id):
            player = p
            break
    else:
        return await ctx.send("The specified ID is not in this draft!")
    name = " ".join(args)
    for mon in league.get_all_pokemon():
        if str(mon).lower() == name.strip().lower():
            to_release = mon
            break
    else:
        return await ctx.send("The Pokemon you are attempting to remove is not recognized!")
    player.remove_mon(to_release)
    await ctx.send("Attempted to remove {} from <@{}>'s team.".format(to_release, player.get_discord()))
    await push_block(ctx, league, player)


@bot.command()
async def debug_kills(ctx, l_id, number, *args):
    """Adjusts kill count of a Pokemon in a league. Admin command."""
    if await require_admin(ctx):
        return
    league = league_by_id(l_id)
    if league is None:
        return await ctx.send("Invalid league ID.")
    name = " ".join(args)
    for mon in league.get_all_pokemon():
        if str(mon).lower() == name.strip().lower():
            to_adjust = mon
            break
    else:
        return await ctx.send("The Pokemon you are attempting to find is not recognized!")
    to_adjust.add_kills(int(number))
    return await ctx.send("Attempted to add {} kills to {}.".format(number, to_adjust))


@bot.command()
async def debug_deaths(ctx, l_id, number, *args):
    """Adjusts death count of a Pokemon in a league. Admin command."""
    if await require_admin(ctx):
        return
    league = league_by_id(l_id)
    if league is None:
        return await ctx.send("Invalid league ID.")
    name = " ".join(args)
    for mon in league.get_all_pokemon():
        if str(mon).lower() == name.strip().lower():
            to_adjust = mon
            break
    else:
        return await ctx.send("The Pokemon you are attempting to find is not recognized!")
    to_adjust.add_deaths(int(number))
    return await ctx.send("Attempted to add {} deaths to {}.".format(number, to_adjust))


@bot.command()
async def debug_reset(ctx, l_id):
    """Wipes the league. Admin command."""
    if await require_admin(ctx):
        return
    league = league_by_id(l_id)
    if league is None:
        return await ctx.send("Invalid league ID.")
    leagues.remove(league)
    return await ctx.send("League removed from database.")


@bot.command()
async def draft(ctx, *args):
    """Wrapper for DraftLeague.draft()."""
    league = league_by_channel(ctx.channel.id)
    if league is None:
        return await ctx.send("This is not a drafting channel.")

    name = " ".join(args)
    for p in league.get_participants():
        if p.get_discord() == ctx.author.id:
            picker = p
            break
    else:
        return await ctx.send("You are not in this draft!")
    for mon in league.get_all_pokemon():
        if str(mon).lower() == name.strip().lower():
            to_draft = mon
            break
    else:
        return await ctx.send("The Pokemon you are attempting to draft is not recognized!")
    async with draft_lock:
        await ctx.send(league.draft(picker, to_draft))
        with open('files/leagues.txt', 'wb+') as f:
            pickle.dump(leagues, f)
            f.close()
        await push_block(ctx, league, picker)


@bot.command()
async def find(ctx, l_id, *args):
    """Wrapper for DraftLeague.find_mon()"""
    league = league_by_id(l_id)
    if league is None:
        return await ctx.send("Invalid league ID.")
    name = " ".join(args)
    for mon in league.get_all_pokemon():
        if str(mon).lower() == name.strip().lower():
            target = mon
            break
    else:
        return await ctx.send("The Pokemon you are attempting to find is not recognized!")
    return await ctx.send("{}".format(league.find_mon(target)))


@bot.command()
async def forcedraft(ctx, *args):
    """Admin command to draft for an AFK player."""
    if await require_admin(ctx):
        return
    league = league_by_channel(ctx.channel.id)
    if league is None:
        return await ctx.send("This is not a drafting channel.")
    if league.get_phase() != 1:
        return await ctx.send("It is not the drafting phase!")
    name = " ".join(args)
    picker = league.get_pickorder()[league.get_picking()[0]]
    if name == "SKIP":
        async with draft_lock:
            league.add_missed_pick(picker)
            return await ctx.send(league.next_pick())
    for mon in league.get_all_pokemon():
        if str(mon).lower() == name.strip().lower():
            to_draft = mon
            break
    else:
        return await ctx.send("The Pokemon you are attempting to draft is not recognized!")
    async with draft_lock:
        await ctx.send(league.draft(picker, to_draft))
        with open('files/leagues.txt', 'wb+') as f:
            pickle.dump(leagues, f)
            f.close()
        await push_block(ctx, league, picker)


@bot.command()
async def forceregister(ctx, d_id, name):
    """Allows an admin to register participants to a DraftLeague."""
    if await require_admin(ctx):
        return
    league = league_by_channel(ctx.channel.id)
    if league is None:
        return await ctx.send("This is not a drafting channel.")
    if league.get_phase() != 0:
        return await ctx.send("It is too late to register!")
    for x in league.get_participants():
        if x.get_discord() == int(d_id):
            return await ctx.send("{} is already registered!".format(name))
    league.add_participant(DraftParticipant(league, int(d_id), name,
                                            league.get_start_timer(), league.get_start_points()))
    await ctx.send("{} is now registered in league {}!".format(name, league.get_id()))


# matchup speed modes: trailing flag on !mu selects base (default), Lv50 or Lv100.
_SPEED_MODES = {
    "50": ("Lv 50", pokeapi.speed_at_50), "l50": ("Lv 50", pokeapi.speed_at_50),
    "100": ("Lv 100", pokeapi.speed_at_100), "l100": ("Lv 100", pokeapi.speed_at_100),
}


async def _speed_rows(species_iter, speed_fn):
    """Build matchup rows from an iterable of species/slug strings."""
    rows = []
    for species in species_iter:
        base = await pokeapi.base_speed(species)
        rows.append({"species": species,
                     "speed": speed_fn(base) if speed_fn else base,
                     "sprite": await pokeapi.sprite_bytes(species)})
    return rows


@bot.command(aliases=["mu", "gm"])
async def generate_matchup(ctx, *args):
    """Render a team-vs-team matchup image (sprites + per-side Speed ladders).
    League mode:  !mu <league_id> <player1> <player2> [l50|l100]
    Ad-hoc mode:  !mu "mon1 mon2 ..." "monA monB ..." [l50|l100]
      names are space-delimited; hyphens are optional (samurotthisui ==
      samurott-hisui), -m == -mega (raichu-m-y == raichu-mega-y), and multi-word
      species are written as one word (e.g. tapukoko). Trailing l50/l100 shows
      max Level-50 / Level-100 Speed instead of base Speed."""
    args = list(args)
    label, speed_fn = "Speed", None
    if args and args[-1].lower().lstrip("-+") in _SPEED_MODES:
        label, speed_fn = _SPEED_MODES[args.pop().lower().lstrip("-+")]

    if len(args) == 2:
        # ad-hoc mode: two space-delimited lists of Pokemon
        p1, p2 = "Team 1", "Team 2"
        toks1, toks2 = args[0].split(), args[1].split()
        if not toks1 or not toks2:
            return await ctx.send("Give two space-separated lists of Pokemon.")
        slugs1 = [pokeapi.resolve_fuzzy(t) for t in toks1]
        slugs2 = [pokeapi.resolve_fuzzy(t) for t in toks2]
        bad = [t for t, s in zip(toks1 + toks2, slugs1 + slugs2) if s is None]
        if bad:
            return await ctx.send("Unrecognized Pokemon: " + ", ".join(bad))
        try:
            p1_rows = await _speed_rows(slugs1, speed_fn)
            p2_rows = await _speed_rows(slugs2, speed_fn)
        except pokeapi.SpeedLookupError as e:
            return await ctx.send(f"failed api call: {e}")
    elif len(args) >= 3:
        # league mode: league_id, player1, player2
        league = league_by_id(args[0])
        if league is None:
            return await ctx.send("Invalid league ID.")
        p1, p2 = args[1], args[2]
        p1_user = league.get_user(p1)
        if p1_user is False:
            return await ctx.send("{} is not participating in the draft.".format(p1))
        p2_user = league.get_user(p2)
        if p2_user is False:
            return await ctx.send("{} is not participating in the draft.".format(p2))
        p1 = f"{p1_user.get_name()} ({p1_user.get_record()})"   # header shows record
        p2 = f"{p2_user.get_name()} ({p2_user.get_record()})"
        try:
            p1_rows = await _speed_rows([str(m) for m in p1_user.get_pokemon()], speed_fn)
            p2_rows = await _speed_rows([str(m) for m in p2_user.get_pokemon()], speed_fn)
        except pokeapi.SpeedLookupError as e:
            return await ctx.send(f"failed api call: {e}")
    else:
        return await ctx.send('Usage: !mu <league_id> <p1> <p2>  —or—  '
                              '!mu "mon1 mon2 ..." "monA monB ..."')

    try:
        png = matchup_image.render_matchup(p1, p1_rows, p2, p2_rows, speed_label=label)
        return await ctx.send(file=discord.File(png, filename="matchup.png"))
    except Exception as err:  # fall back to a text embed if rendering is unavailable
        def line(r):
            return f"{r['species']}: {r['speed']}"
        e = Embed(title=f"{p1} vs {p2}")
        e.add_field(name=p1, value="\n".join(line(r) for r in sorted(p1_rows, key=lambda r: -r["speed"])) or "\u200B", inline=True)
        e.add_field(name="\u200B", value="\u200B", inline=True)
        e.add_field(name=p2, value="\n".join(line(r) for r in sorted(p2_rows, key=lambda r: -r["speed"])) or "\u200B", inline=True)
        return await ctx.send(content=f"(matchup image unavailable: {err})", embed=e)


@bot.command()
async def info(ctx, l_id, *args):
    """Prints str(DraftParticipant) to Discord if possible."""
    league = league_by_id(l_id)
    if league is None:
        return await ctx.send("Invalid league ID.")
    name = " ".join([*args])
    if name.lower() == "all":
        for p in league.get_participants():
            await ctx.author.send(str(p))
        return
    n = league.get_user(name)
    if n is False:
        return await ctx.send("{} is not participating in the draft.".format(name))
    else:
        return await ctx.send(str(league.get_user(name)))


@bot.command()
async def init(ctx, l_id, tierlist, init_time=540, increment=180, points=120,
               min_mons=9, max_mons=11):
    """Starts a new DraftLeague(). Roster size defaults to 9-11 Pokemon."""
    if await require_admin(ctx):
        return
    try:
        l_id = int(l_id)
    except ValueError:
        return await ctx.send("Please enter a valid ID.")
    try:
        min_mons, max_mons = int(min_mons), int(max_mons)
    except ValueError:
        return await ctx.send("Roster minimum and maximum must be integers.")
    if min_mons > max_mons:
        return await ctx.send("Roster minimum cannot exceed the maximum.")
    for league in leagues:
        if league.get_id() == l_id:
            return await ctx.send("League already exists with this ID.")
        if league.get_channel() == ctx.channel.id:
            return await ctx.send("Another league is using this channel as its drafting channel.")
    leagues.append(DraftLeague(l_id, tierlist, ctx.channel.id, init_time, increment, points,
                               min_mons, max_mons))
    return await ctx.send("New league initialized with ID {} ({}-{} Pokemon).".format(
        l_id, min_mons, max_mons))


@bot.command()
async def kills(ctx, l_id):
    """Displays the kill leaderboard for the league."""
    league = league_by_id(l_id)
    if league is None:
        return await ctx.send("Invalid league ID.")
    msg = f"**Kill Leaderboard (League {l_id}):**\n"
    league.get_all_pokemon().sort(key=lambda x: x.get_kills(), reverse=True)
    top_20 = league.get_all_pokemon()[:20]
    i = 1
    for p in top_20:
        if p.get_owner():
            name = p.get_owner().get_name()
        else:
            name = "Free Agent"
        msg += f"{i}. {str(p)} ({name}): {p.get_kills()} kill(s) | {p.get_deaths()} death(s)\n"
        i += 1
    return await ctx.send(msg)


@bot.command()
async def participants(ctx, l_id):
    """Wrapper for DraftLeague.get_participants()."""
    league = league_by_id(l_id)
    if league is None:
        return await ctx.send("Invalid league ID.")
    pl = [x.get_name() for x in league.get_participants()]
    if len(pl) == 0:
        return await ctx.send("No participants yet!")
    else:
        return await ctx.send("Participants ({}): {}".format(len(pl), ", ".join(pl)))


@bot.command()
async def predraft(ctx, l_id, key, rd=0, *args):
    """Alters the list of premade picks of a DraftParticipant. If rd is not 0, the predrafted Pokemon will only be
    drafted in the specified round. Keys: ADD, CLEAR, REMOVE"""
    league = league_by_id(l_id)
    if league is None:
        return await ctx.send("Invalid league ID.")
    for p in league.get_participants():
        if p.get_discord() == ctx.author.id:
            picker = p
            break
    else:
        return await ctx.send("You are not in this draft!")
    if league.get_phase() != 1:
        return await ctx.send("It is not the drafting phase!")
    np = picker.get_next_pick()
    if key.lower() == "clear":
        picker.set_next_pick([])
        return await ctx.send("Priority for automatic drafting cleared.")
    if key.lower() == "add":
        try:
            rd = int(rd)  # discord passes args as strings; the round must be int
        except (ValueError, TypeError):
            return await ctx.send("Round must be an integer. Usage: !predraft <id> add <round> <mon> (round 0 = any round).")
        pick = " ".join(args)
        for mon in league.get_all_pokemon():
            if str(mon).lower() == pick.strip().lower():
                break
        else:
            return await ctx.send("The Pokemon you are attempting to predraft is not recognized!")
        np.append((pick, rd))
        picker.set_next_pick(np)
    if key.lower() == "remove":
        target = " ".join(args).strip().lower()
        picker.set_next_pick([x for x in np if x[0].strip().lower() != target])
    return await ctx.send("Priority for automatic drafting: {}".format(
        "; ".join([f"{x[0]}, round: {x[1]}" for x in picker.get_next_pick()])))


@bot.command()
async def register(ctx):
    """Registers the user to a DraftLeague as a DraftParticipant."""
    league = league_by_channel(ctx.channel.id)
    if league is None:
        return await ctx.send("This is not a drafting channel.")
    if league.get_phase() != 0:
        return await ctx.send("It is too late to register!")
    for x in league.get_participants():
        if x.get_discord() == ctx.author.id:
            return await ctx.send("You are already registered!")
    league.add_participant(
        DraftParticipant(league, ctx.author.id, ctx.author.name, league.get_start_timer(), league.get_start_points()))
    await ctx.send("{}, you are now registered in league {}!".format(ctx.author.mention, league.get_id()))
    with open('files/leagues.txt', 'wb+') as f:
        pickle.dump(leagues, f)
        f.close()


@bot.command()
async def release(ctx, *args):
    """Wrapper for DraftParticipant.release()"""
    league = league_by_channel(ctx.channel.id)
    if league is None:
        return await ctx.send("This is not a drafting channel.")
    if league.get_phase() != 2:
        return await ctx.send("You cannot release Pokemon right now.")
    name = " ".join(args)
    for p in league.get_participants():
        if p.get_discord() == ctx.author.id:
            player = p
            break
    else:
        return await ctx.send("You are not in this draft!")
    for mon in player.get_pokemon():
        if str(mon).lower() == name.strip().lower():
            to_release = mon
            break
    else:
        return await ctx.send("You do not own {}!".format(name))
    player.remove_mon(to_release)
    await ctx.send("<@{}> has released {}!".format(player.get_discord(), name.title()))
    with open('files/leagues.txt', 'wb+') as f:
        pickle.dump(leagues, f)
        f.close()
    await push_block(ctx, league, player)


@bot.command()
async def replay(ctx, replay_url):
    """Uploads a replay to be parsed."""
    for l in leagues:
        try:
            if ctx.channel.id == l.get_replay_channel():
                league = l
                break
        except AttributeError:
            pass
    else:
        return await ctx.send("This is not a replay channel.")
    if league.get_phase() < 2:
        return await ctx.send("This league is still in the drafting phase!")
    parsed_battle = parse_replay(replay_url)
    if parsed_battle.winner is None:
        return await ctx.send("Could not determine a winner from that replay.")
    check_alive = lambda x: not x.ko
    winner_id = None
    loser_id = None
    for participant in l.get_participants():
        matches = 0
        match_list = []
        for p in participant.get_pokemon():
            for q in parsed_battle.winner.team:
                if (str(p) in q.species or q.species in str(p)) and not(str(p) != q.species == "Porygon") or (str(p) == q.species == "Porygon"):
                    matches += 1
                    match_list.append((p, q))
                    break
            if matches == 6:
                for m in match_list:
                    m[0].add_kills(m[1].direct_kills + m[1].indirect_kills)
                    m[0].add_deaths(m[1].ko)
                winner_id = participant.get_discord()
                break
            for q in parsed_battle.loser.team:
                if (str(p) in q.species or q.species in str(p)) and not(str(p) != q.species == "Porygon") or (str(p) == q.species == "Porygon"):
                    matches += 1
                    match_list.append((p, q))
                    break
            if matches == 6:
                for m in match_list:
                    m[0].add_kills(m[1].direct_kills + m[1].indirect_kills)
                    m[0].add_deaths(m[1].ko)
                loser_id = participant.get_discord()
                break

    # Record the result into standings (schedule-unchecked, deduped by URL).
    scored = ""
    if winner_id is not None and loser_id is not None:
        if league.record_result(winner_id, loser_id, replay_url):
            with open('files/leagues.txt', 'wb+') as f:
                pickle.dump(leagues, f)
                f.close()
            w = league._participant_by_id(winner_id)
            lo = league._participant_by_id(loser_id)
            scored = f"\n\n**Records:** {w.get_name()} ({w.get_record()}), {lo.get_name()} ({lo.get_record()})"
        else:
            scored = "\n\n*(Result already recorded — not counted again.)*"
    else:
        scored = "\n\n*(Could not score: a team did not match a league participant.)*"

    winner_team_stats = "\n".join(f"`{p}`" for p in parsed_battle.winner.team)
    loser_team_stats = "\n".join(f"`{p}`" for p in parsed_battle.loser.team)
    return await ctx.send(f"""Result: ||**<@{winner_id}>** won against **<@{loser_id}>** {
    sum(map(check_alive, parsed_battle.winner.team))} - {sum(map(check_alive, parsed_battle.loser.team))}||

||**{parsed_battle.winner.psname}**:
{winner_team_stats}||

||**{parsed_battle.loser.psname}**:
{loser_team_stats}||{scored}""")


@bot.command()
async def replay_channel(ctx, l_id):
    """Sets the replay channel of a league."""
    if await require_admin(ctx):
        return
    for l in leagues:
        try:
            if l.get_channel() == ctx.channel.id:
                return await ctx.send("Cannot set a drafting channel as a replay channel.")
            elif l.get_replay_channel() == ctx.channel.id:
                return await ctx.send("This channel is already being used as a replay channel.")
        except AttributeError:
            pass
    for l in leagues:
        if l.get_id() == int(l_id):
            l.set_replay_channel(ctx.channel.id)
            return await ctx.send(f"Current channel set as the replay channel for league {l_id}.")
    else:
        return await ctx.send("There is no league with this id.")


@bot.command()
async def save(ctx):
    """Backs up all leagues."""
    if await require_admin(ctx):
        return
    with open('files/leagues.txt', 'wb+') as f:
        pickle.dump(leagues, f)
        f.close()
    await ctx.send("All leagues backed up.")


@bot.command()
async def shuffle(ctx):
    """Wrapper for DraftLeague.shuffle()"""
    if await require_admin(ctx):
        return
    league = league_by_channel(ctx.channel.id)
    if league is None:
        return await ctx.send("This is not a drafting channel.")
    if league.get_phase() != 0:
        return await ctx.send("Cannot shuffle participants in a league that has already started.")
    participants = league.get_participants()
    if league.get_sheet_id() is not None and len(participants) > sheet.BLOCK_COUNT:
        return await ctx.send(
            f"Too many participants ({len(participants)}) for the {sheet.BLOCK_COUNT} "
            f"blocks on the linked sheet; cannot assign blocks.")
    league.shuffle()
    for i, p in enumerate(league.get_participants()):
        p.set_block_index(i)
    with open('files/leagues.txt', 'wb+') as f:
        pickle.dump(leagues, f)
    await ctx.send("Participants of league {} shuffled. Pick order: {}".format(
        league.get_id(), ", ".join([p.get_name() for p in league.get_participants()])))
    if league.get_sheet_id() is not None:
        await resync_all(ctx, league)


@bot.command()
async def set_sheet(ctx, url):
    """Links a Google Sheet to this league so picks auto-populate it. Admin command.
    Accepts a full sheet URL (tab gid honored) or a bare spreadsheet id."""
    if await require_admin(ctx):
        return
    league = league_by_channel(ctx.channel.id)
    if league is None:
        return await ctx.send("This is not a drafting channel.")
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    sheet_id = m.group(1) if m else url.strip()
    g = re.search(r"[#?&]gid=(\d+)", url)
    tab = int(g.group(1)) if g else None
    league.set_sheet(sheet_id, tab)
    with open('files/leagues.txt', 'wb+') as f:
        pickle.dump(leagues, f)
    where = f"id `{sheet_id}`" + (f", tab {tab}" if tab is not None else "")
    if not sheet.available():
        return await ctx.send(
            f"Sheet linked to league {league.get_id()} ({where}), but no service-account "
            f"key is installed yet — syncing will start once `{sheet.CREDS_FILE}` is added "
            f"and the sheet is shared with the service account's email.")
    await ctx.send(f"Sheet linked to league {league.get_id()} ({where}). "
                   f"Run !shuffle to assign blocks, then picks will sync automatically.")


@bot.command()
async def resync_sheet(ctx):
    """Rewrites every assigned block on the linked sheet from current state. Admin command."""
    if await require_admin(ctx):
        return
    league = league_by_channel(ctx.channel.id)
    if league is None:
        return await ctx.send("This is not a drafting channel.")
    await resync_all(ctx, league)


@bot.command()
async def start_draft(ctx):
    """Starts the draft phase of the identified league."""
    if await require_admin(ctx):
        return
    league = league_by_channel(ctx.channel.id)
    if league is None:
        return await ctx.send("This is not a drafting channel.")
    if league.get_phase() != 0:
        return await ctx.send("The draft has already been started.")
    if len(league.get_participants()) == 0:
        return await ctx.send("There are no participants.")
    league.set_pick_order()
    league.next_phase()
    await ctx.send("The draft has been started! Pick order: {}".format(
        ", ".join([p.get_name() for p in league.get_participants()])))

    first_participant = league._pickorder[league._picking[0]]
    first_participant.add_time_to_timer(league._increment)

    return await ctx.send("Now picking: <@{}>. Deadline: {} ({} minutes)".format(
            first_participant.get_discord(), (league._picking[1] + first_participant.get_timer()).replace(microsecond=0),
            round(first_participant.get_timer().total_seconds()/60)))


@bot.command()
async def substitute(ctx, old_id, new_id, new_name):
    """Wrapper for DraftParticipant.substitute()."""
    if await require_admin(ctx):
        return
    league = league_by_channel(ctx.channel.id)
    if league is None:
        return await ctx.send("This is not a drafting channel.")
    for p in league.get_participants():
        if int(p.get_discord()) == int(old_id):
            p.substitute(new_name, int(new_id))
            break
    else:
        return await ctx.send("The player you are attempting to substitute is not in the league.")
    await ctx.send("<@{}> has been substituted for <@{}>!".format(old_id, new_id))
    await push_block(ctx, league, p, owner=True)


def _save_leagues():
    with open('files/leagues.txt', 'wb+') as f:
        pickle.dump(leagues, f)
        f.close()


def _pname(x):
    return "TBD" if x is None else x.get_name()


@bot.command()
async def generate_schedule(ctx, weeks="8"):
    """Generates the round-robin regular-season schedule. Admin command."""
    if await require_admin(ctx):
        return
    league = league_by_channel(ctx.channel.id)
    if league is None:
        return await ctx.send("This is not a drafting channel.")
    if league.get_phase() < 2:
        return await ctx.send("Finish the draft before generating a schedule.")
    if len(league.get_participants()) < 2:
        return await ctx.send("Need at least two participants.")
    try:
        weeks = int(weeks)
    except ValueError:
        return await ctx.send("Weeks must be an integer.")
    league.generate_schedule(weeks)
    _save_leagues()
    return await ctx.send(f"Generated a {weeks}-week schedule for league {league.get_id()}. "
                          f"View it with !schedule {league.get_id()} or !fullschedule {league.get_id()}.")


@bot.command()
async def schedule(ctx, l_id, week=None):
    """!schedule <league_id> shows your own schedule; add a week number to see that
    week's pairings (with results/links for completed games)."""
    league = league_by_id(l_id)
    if league is None:
        return await ctx.send("Invalid league ID.")
    sched = league.get_schedule()
    if not sched:
        return await ctx.send("No schedule yet — an admin can run !generate_schedule.")

    if week is None:
        me = league._participant_by_id(ctx.author.id)
        if me is None:
            return await ctx.send(f"You are not in league {l_id}. Try !fullschedule {l_id}.")
        lines = []
        for wk, pairings in enumerate(sched, 1):
            opp = next((b if a is me else a for a, b in pairings if me in (a, b)), None)
            if opp is None:
                lines.append(f"Week {wk}: *BYE*")
                continue
            res = league.result_for(me, opp)
            tag = ""
            if res:
                tag = f" — {'W' if res[0] is me else 'L'}" + (f" <{res[2]}>" if res[2] else "")
            lines.append(f"Week {wk}: vs {opp.get_name()}{tag}")
        e = Embed(title=f"{me.get_name()}'s schedule — league {league.get_id()} ({me.get_record()})")
        e.description = "\n".join(lines)
        return await ctx.send(embed=e)

    try:
        week = int(week)
    except ValueError:
        return await ctx.send("Week must be an integer.")
    if not 1 <= week <= len(sched):
        return await ctx.send(f"Week must be between 1 and {len(sched)}.")
    lines = []
    for a, b in sched[week - 1]:
        if a is None or b is None:
            lines.append(f"{_pname(a or b)} — *BYE*")
            continue
        res = league.result_for(a, b)
        if res:
            w, lo = res[0], res[1]
            link = f"  <{res[2]}>" if res[2] else ""
            lines.append(f"**{w.get_name()}** def. {lo.get_name()}{link}")
        else:
            lines.append(f"{a.get_name()} vs {b.get_name()}")
    e = Embed(title=f"League {league.get_id()} — Week {week}")
    e.description = "\n".join(lines) or "No pairings."
    return await ctx.send(embed=e)


@bot.command()
async def fullschedule(ctx, l_id):
    """Shows the whole league schedule as a table (one column per week)."""
    league = league_by_id(l_id)
    if league is None:
        return await ctx.send("Invalid league ID.")
    sched = league.get_schedule()
    if not sched:
        return await ctx.send("No schedule yet — an admin can run !generate_schedule.")
    e = Embed(title=f"League {league.get_id()} — Full schedule")
    for wk, pairings in enumerate(sched, 1):
        rows = []
        for a, b in pairings:
            if a is None or b is None:
                rows.append(f"{_pname(a or b)}: BYE")
                continue
            res = league.result_for(a, b)
            if res:
                rows.append(f"{a.get_name()} v {b.get_name()} → {res[0].get_name()}")
            else:
                rows.append(f"{a.get_name()} v {b.get_name()}")
        e.add_field(name=f"Week {wk}", value="\n".join(rows) or "—", inline=True)
    return await ctx.send(embed=e)


@bot.command()
async def standings(ctx, l_id):
    """Shows the standings (wins, then kill differential, then head-to-head)."""
    league = league_by_id(l_id)
    if league is None:
        return await ctx.send("Invalid league ID.")
    ranked = league.standings()
    if not ranked:
        return await ctx.send("No participants yet.")
    lines = [f"{i}. {p.get_name()} ({p.get_record()}) — kill diff {p.get_kill_diff():+d}"
             for i, p in enumerate(ranked, 1)]
    e = Embed(title=f"League {league.get_id()} — Standings")
    e.description = "\n".join(lines)
    return await ctx.send(embed=e)


@bot.command()
async def playoffs(ctx, size="8"):
    """Seeds a single-elimination playoff bracket from current standings. Admin command."""
    if await require_admin(ctx):
        return
    league = league_by_channel(ctx.channel.id)
    if league is None:
        return await ctx.send("This is not a drafting channel.")
    if len(league.get_participants()) < 2:
        return await ctx.send("Need at least two participants.")
    try:
        size = int(size)
    except ValueError:
        return await ctx.send("Size must be an integer.")
    league.generate_bracket(size)
    _save_leagues()
    return await ctx.send(f"Seeded a top-{size} single-elimination bracket for league "
                          f"{league.get_id()}. View it with !bracket {league.get_id()}.")


@bot.command()
async def bracket(ctx, l_id):
    """Displays the playoff bracket and recorded results."""
    league = league_by_id(l_id)
    if league is None:
        return await ctx.send("Invalid league ID.")
    br = league.get_bracket()
    if not br:
        return await ctx.send("No playoff bracket yet — an admin can run !playoffs.")
    round_names = {1: "Final", 2: "Semifinals", 4: "Quarterfinals"}
    e = Embed(title=f"League {league.get_id()} — Playoff bracket")
    for rnd in br:
        rows = []
        for a, b, w in rnd:
            if (a is None) ^ (b is None) and w is not None:
                rows.append(f"{w.get_name()} — bye")
            else:
                line = f"{_pname(a)} vs {_pname(b)}"
                if w is not None:
                    line += f" → **{w.get_name()}**"
                rows.append(line)
        e.add_field(name=round_names.get(len(rnd), f"Round of {len(rnd) * 2}"),
                    value="\n".join(rows) or "—", inline=False)
    return await ctx.send(embed=e)


@bot.event
async def setup_hook():
    """Runs once during login (discord.py 2.x). Starts the draft-phase timer
    here rather than in on_ready, which can fire multiple times on reconnect
    and would spawn duplicate timer loops."""
    bot.loop.create_task(timer())


@bot.event
async def on_ready():
    """Prints readiness when the bot is online."""
    print(f'ready — logged in as {bot.user}')


async def timer():
    """Timer for draft phase."""
    await bot.wait_until_ready()
    while True:
        for l in leagues:
            if l.get_phase() == 1:
                async with draft_lock:
                    msg = l.check_pick_deadline()
                    picker = l.take_pending_sync()
                    if msg:
                        channel = bot.get_channel(l.get_channel())
                        if channel is not None:
                            await channel.send(msg)
                            if picker is not None:
                                await push_block(channel, l, picker)
        await asyncio.sleep(1)


with open('files/key.txt') as key_file:
    bot_key = key_file.readline()
    key_file.close()
try:
    with open('files/leagues.txt', 'rb') as backup:
        leagues = pickle.load(backup)
        backup.close()
except FileNotFoundError:
    leagues = []
bot.run(bot_key.strip())
