import json

from DraftLeague import DraftLeague
from DraftParticipant import DraftParticipant
from ParseReplay import parse_replay
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


# Base Speed lookups for matchup tables are cached (in memory and on disk) so a
# given species is fetched from PokeAPI at most once, and the blocking HTTP call
# is run off the event loop.
SPEED_CACHE_FILE = 'files/speeds.json'
try:
    with open(SPEED_CACHE_FILE) as _f:
        _speed_cache = json.load(_f)
except (FileNotFoundError, json.JSONDecodeError):
    _speed_cache = {}


class SpeedLookupError(Exception):
    """Raised when PokeAPI has no usable entry for a species."""


def _pokeapi_name(species):
    """Map a drafted Pokemon's display name to the species slug PokeAPI expects."""
    name = species.replace(" ", "-")
    name += "-Single-Strike" if name == "Urshifu" else ""
    name += "-Pom-Pom" if name == "Oricorio" else ""
    name += "-Terastal" if name == "Terapagos" else ""
    name += "-Female" if name in ("Basculegion", "Indeedee") else ""
    name += "-Mask" if name in ("Ogerpon-Hearthflame", "Ogerpon-Wellspring", "Ogerpon-Cornerstone") else ""
    name += "-Ordinary" if name == "Keldeo" else ""
    name += "-Incarnate" if name in ("Tornadus", "Thundurus", "Landorus", "Enamorus") else ""
    name += "-Hero" if name == "Palafin" else ""
    return name.lower()


async def base_speed(species):
    """Base Speed stat for a species, cached across calls and persisted to disk."""
    if species in _speed_cache:
        return _speed_cache[species]
    api_name = _pokeapi_name(species)
    url = f"https://pokeapi.co/api/v2/pokemon/{api_name}"
    loop = asyncio.get_running_loop()
    resp = await loop.run_in_executor(None, requests.get, url)
    try:
        spe = resp.json()["stats"][5]["base_stat"]
    except (json.JSONDecodeError, KeyError, IndexError):
        raise SpeedLookupError(api_name)
    _speed_cache[species] = spe
    with open(SPEED_CACHE_FILE, "w") as f:
        json.dump(_speed_cache, f)
    return spe


async def team_base_speeds(mons):
    """{species: base speed} for a participant's team, sorted fastest first."""
    speeds = {str(p): await base_speed(str(p)) for p in mons}
    return dict(sorted(speeds.items(), key=lambda item: item[1], reverse=True))


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
    return await ctx.send("Attempted to add {} to <@{}>'s team.".format(to_draft, picker.get_discord()))


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
    return await ctx.send("Attempted to add {} to <@{}>'s team.".format(to_add, player.get_discord()))


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
    return await ctx.send("Attempted to remove {} from <@{}>'s team.".format(to_release, player.get_discord()))


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
    await ctx.send(league.draft(picker, to_draft))
    with open('files/leagues.txt', 'wb+') as f:
        pickle.dump(leagues, f)
        f.close()


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
        league.add_missed_pick(picker)
        return await ctx.send(league.next_pick())
    for mon in league.get_all_pokemon():
        if str(mon).lower() == name.strip().lower():
            to_draft = mon
            break
    else:
        return await ctx.send("The Pokemon you are attempting to draft is not recognized!")
    await ctx.send(league.draft(picker, to_draft))
    with open('files/leagues.txt', 'wb+') as f:
        pickle.dump(leagues, f)
        f.close()


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


@bot.command(aliases=["mu", "gm"])
async def generate_matchup(ctx, l_id, *args):
    """Generates a matchup embed if possible."""
    league = league_by_id(l_id)
    if league is None:
        return await ctx.send("Invalid league ID.")
    p1 = args[0]
    p2 = args[1]
    p1_user = league.get_user(p1)
    if p1_user is False:
        return await ctx.send("{} is not participating in the draft.".format(p1))
    p2_user = league.get_user(p2)
    if p2_user is False:
        return await ctx.send("{} is not participating in the draft.".format(p2))
    try:
        p1_speeds = await team_base_speeds(p1_user.get_pokemon())
        p2_speeds = await team_base_speeds(p2_user.get_pokemon())
    except SpeedLookupError as e:
        return await ctx.send(f"failed api call: {e}")
    p1_speedstrings = [f"{k}: {int((5+v*2+31+63)*1.1)}" for k, v in p1_speeds.items()]
    p2_speedstrings = [f"{k}: {int((5+v*2+31+63)*1.1)}" for k, v in p2_speeds.items()]
    e = Embed(title=f"{p1} vs {p2}")
    e.add_field(name=p1, value="\n".join(p1_speedstrings), inline=True)
    e.add_field(name="\u200B", value="\u200B", inline=True)
    e.add_field(name=p2, value="\n".join(p2_speedstrings), inline=True)
    await ctx.send(embed=e)


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
async def init(ctx, l_id, tierlist, init_time=540, increment=180, points=120):
    """Starts a new DraftLeague()."""
    if await require_admin(ctx):
        return
    try:
        l_id = int(l_id)
    except ValueError:
        return await ctx.send("Please enter a valid ID.")
    for league in leagues:
        if league.get_id() == l_id:
            return await ctx.send("League already exists with this ID.")
        if league.get_channel() == ctx.channel.id:
            return await ctx.send("Another league is using this channel as its drafting channel.")
    leagues.append(DraftLeague(l_id, tierlist, ctx.channel.id, init_time, increment, points))
    return await ctx.send("New league initialized with ID {}.".format(l_id))


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
        pick = " ".join(args)
        for mon in league.get_all_pokemon():
            if str(mon).lower() == pick.strip().lower():
                break
        else:
            return await ctx.send("The Pokemon you are attempting to predraft is not recognized!")
        np.append((pick, rd))
        picker.set_next_pick(np)
    if key.lower() == "remove":
        for p in np:
            if p[0] == " ".join(args):
                np.remove(p)
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

    winner_team_stats = "\n".join(f"`{p}`" for p in parsed_battle.winner.team)
    loser_team_stats = "\n".join(f"`{p}`" for p in parsed_battle.loser.team)
    return await ctx.send(f"""Result: ||**<@{winner_id}>** won against **<@{loser_id}>** {
    sum(map(check_alive, parsed_battle.winner.team))} - {sum(map(check_alive, parsed_battle.loser.team))}||

||**{parsed_battle.winner.psname}**: 
{winner_team_stats}||

||**{parsed_battle.loser.psname}**:
{loser_team_stats}||""")


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
    league.shuffle()
    return await ctx.send("Participants of league {} shuffled. Pick order: {}".format(
        league.get_id(), ", ".join([p.get_name() for p in league.get_participants()])))


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
    return await ctx.send("<@{}> has been substituted for <@{}>!".format(old_id, new_id))


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
                msg = l.check_pick_deadline()
                if msg:
                    channel = bot.get_channel(l.get_channel())
                    if channel is not None:
                        await channel.send(msg)
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
