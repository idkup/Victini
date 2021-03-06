from DraftLeague import DraftLeague
from DraftParticipant import DraftParticipant
import asyncio
from discord import Embed
from discord.ext import commands
import pickle

admin_ids = [590336288935378950, 167690209821982721]
bot = commands.Bot(command_prefix='!')


@bot.command()
async def available(ctx, l_id, cost):
    """Wrapper for DraftLeague.available_pokemon()"""
    for l in leagues:
        if l.get_id() == int(l_id):
            league = l
            break
    else:
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
    if ctx.author.id not in admin_ids:
        return await ctx.send("This is an admin-only command.")
    for l in leagues:
        if l.get_channel() == ctx.channel.id:
            league = l
            break
    else:
        return await ctx.send("Invalid league ID.")
    if league.get_phase() != 2:
        return await ctx.send("Free agency is not currently open.")
    league.next_phase()
    return await ctx.send("Trades are now closed in this league.")


@bot.command()
async def debug_cost(ctx, mon, cost):
    """Changes the cost of a specific Pokemon in that DraftLeague. Admin command."""
    if ctx.author.id not in admin_ids:
        return await ctx.send("This is an admin-only command.")
    for l in leagues:
        if l.get_channel() == ctx.channel.id:
            league = l
            break
    else:
        return await ctx.send("Invalid league ID.")
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
async def debug_draft(ctx, l_id, d_id, *args):
    """Adds a Pokemon to a player's team. Admin command."""

    for l in leagues:
        if l.get_id() == int(l_id):
            league = l
            break
    else:
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
async def debug_phase(ctx, l_id, phase="0"):
    """Sets the phase in a league. Admin command."""
    if ctx.author.id not in admin_ids:
        return await ctx.send("This is an admin-only command.")
    for l in leagues:
        if l.get_id() == int(l_id):
            league = l
            break
    else:
        return await ctx.send("Invalid league ID.")
    league.set_phase(int(phase))
    return await ctx.send("Phase of league {} set to {}".format(league.get_id(), league.get_phase()))


@bot.command()
async def debug_leagues(ctx):
    """Prints all leagues with their current phase. Admin command."""
    if ctx.author.id not in admin_ids:
        return await ctx.send("This is an admin-only command.")
    await ctx.send("Current leagues: \n{}".format("\n".join(["ID: {} Phase: {}".format(
        l.get_id(), l.get_phase()) for l in leagues])))


@bot.command()
async def debug_participants(ctx, l_id):
    """Rebuilds all participant objects in the league. Admin command."""
    if ctx.author.id not in admin_ids:
        return await ctx.send("This is an admin-only command.")
    for l in leagues:
        if l.get_id() == int(l_id):
            league = l
            break
    else:
        return await ctx.send("Invalid league ID.")
    lp = []
    for p in league.get_participants():
        lp.append([league, p.get_discord(), p.get_name()])
    league.clear_participants()
    for p in lp:
        league.add_participant(DraftParticipant(p[0], int(p[1]), p[2]))
    await ctx.send("Participant objects rebuilt in league {}".format(l_id))


@bot.command()
async def debug_pickorder(ctx, l_id):
    """Debugs pick order. Admin command."""
    if ctx.author.id not in admin_ids:
        return await ctx.send("This is an admin-only command.")
    for l in leagues:
        if l.get_id() == int(l_id):
            league = l
            break
    else:
        return await ctx.send("Invalid league ID.")
    league.set_pick_order()
    return await ctx.send("Pick order debugged.")


@bot.command()
async def debug_release(ctx, l_id, d_id, *args):
    """Removes a Pokemon from a player's team. Admin command."""
    if ctx.author.id not in admin_ids:
        return await ctx.send("This is an admin-only command.")
    for l in leagues:
        if l.get_id() == int(l_id):
            league = l
            break
    else:
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
        return await ctx.send("The Pokemon you are attempting to draft is not recognized!")
    player.remove_mon(to_release)
    return await ctx.send("Attempted to remove {} from <@{}>'s team.".format(to_release, player.get_discord()))


@bot.command()
async def debug_reset(ctx, l_id):
    """Wipes the league. Admin command."""
    if ctx.author.id not in admin_ids:
        return await ctx.send("This is an admin-only command.")
    for l in leagues:
        if l.get_id() == int(l_id):
            league = l
            break
    else:
        return await ctx.send("Invalid league ID.")
    leagues.remove(league)
    return await ctx.send("League removed from database.")


@bot.command()
async def debug_timer(ctx, l_id, s):
    """Changes the timer for picks. Admin command."""
    if ctx.author.id not in admin_ids:
        return await ctx.send("This is an admin-only command.")
    for l in leagues:
        if l.get_id() == int(l_id):
            league = l
            break
    else:
        return await ctx.send("Invalid league ID.")
    league.set_timer(int(s))
    return await ctx.send("Draft timer for league {} is now {} seconds.".format(l_id, s))


@bot.command()
async def draft(ctx, *args):
    """Wrapper for DraftLeague.draft()."""
    for l in leagues:
        if l.get_channel() == ctx.channel.id:
            league = l
            break
    else:
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
    for l in leagues:
        if l.get_id() == int(l_id):
            league = l
            break
    else:
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
    if ctx.author.id not in admin_ids:
        return await ctx.send("This is an admin-only command.")
    for l in leagues:
        if l.get_channel() == ctx.channel.id:
            league = l
            break
    else:
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
    if ctx.author.id not in admin_ids:
        return await ctx.send("This is an admin-only command.")
    for l in leagues:
        if l.get_channel() == ctx.channel.id:
            league = l
            break
    else:
        return await ctx.send("This is not a drafting channel.")
    if league.get_phase() != 0:
        return await ctx.send("It is too late to register!")
    for x in league.get_participants():
        if x.get_discord() == int(d_id):
            return await ctx.send("{} is already registered!".format(name))
    league.add_participant(DraftParticipant(league, int(d_id), name))
    await ctx.send("{} is now registered in league {}!".format(name, league.get_id()))


@bot.command()
async def info(ctx, l_id, *args):
    """Prints str(DraftParticipant) to Discord if possible."""
    for l in leagues:
        if l.get_id() == int(l_id):
            league = l
            break
    else:
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
async def init(ctx, l_id, tierlist):
    """Starts a new DraftLeague()."""
    if ctx.author.id not in admin_ids:
        return await ctx.send("This is an admin-only command.")
    try:
        l_id = int(l_id)
    except ValueError:
        return await ctx.send("Please enter a valid ID.")
    for league in leagues:
        if league.get_id() == l_id:
            return await ctx.send("League already exists with this ID.")
        if league.get_channel() == ctx.channel.id:
            return await ctx.send("Another league is using this channel as its drafting channel.")
    leagues.append(DraftLeague(l_id, tierlist, ctx.channel.id))
    return await ctx.send("New league initialized with ID {}.".format(l_id))


@bot.command()
async def participants(ctx, l_id):
    """Wrapper for DraftLeague.get_participants()."""
    for l in leagues:
        if l.get_id() == int(l_id):
            league = l
            break
    else:
        return await ctx.send("Invalid league ID.")
    pl = [x.get_name() for x in league.get_participants()]
    if len(pl) == 0:
        return await ctx.send("No participants yet!")
    else:
        return await ctx.send("Participants ({}): {}".format(len(pl), ", ".join(pl)))


@bot.command()
async def predraft(ctx, l_id, key, *args):
    """Alters the list of premade picks of a DraftParticipant. Keys: CLEAR, ADD, REPLACE, REMOVE"""
    for l in leagues:
        if l.get_id() == int(l_id):
            league = l
            break
    else:
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
        np.append(" ".join(args))
        picker.set_next_pick(np)
    elif key.lower() == "replace":
        picker.set_next_pick([" ".join(args)])
    elif key.lower() == "remove":
        np.remove(" ".join(args))
    return await ctx.send("Priority for automatic drafting: {}".format(" ".join(picker.get_next_pick())))


@bot.command()
async def register(ctx):
    """Registers the user to a DraftLeague as a DraftParticipant."""
    for l in leagues:
        if l.get_channel() == ctx.channel.id:
            league = l
            break
    else:
        return await ctx.send("This is not a drafting channel.")
    if league.get_phase() != 0:
        return await ctx.send("It is too late to register!")
    for x in league.get_participants():
        if x.get_discord() == ctx.author.id:
            return await ctx.send("You are already registered!")
    league.add_participant(DraftParticipant(league, ctx.author.id, ctx.author.name))
    await ctx.send("{}, you are now registered in league {}!".format(ctx.author.mention, league.get_id()))
    with open('files/leagues.txt', 'wb+') as f:
        pickle.dump(leagues, f)
        f.close()


@bot.command()
async def release(ctx, *args):
    """Wrapper for DraftParticipant.release()"""
    for l in leagues:
        if l.get_channel() == ctx.channel.id:
            league = l
            break
    else:
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
async def save(ctx):
    """Backs up all leagues."""
    if ctx.author.id not in admin_ids:
        return await ctx.send("This is an admin-only command.")
    with open('files/leagues.txt', 'wb+') as f:
        pickle.dump(leagues, f)
        f.close()
    await ctx.send("All leagues backed up.")


@bot.command()
async def shuffle(ctx):
    """Wrapper for DraftLeague.shuffle()"""
    if ctx.author.id not in admin_ids:
        return await ctx.send("This is an admin-only command.")
    for l in leagues:
        if l.get_channel() == ctx.channel.id:
            league = l
            break
    else:
        return await ctx.send("This is not a drafting channel.")
    if league.get_phase() != 0:
        return await ctx.send("Cannot shuffle participants in a league that has already started.")
    league.shuffle()
    return await ctx.send("Participants of league {} shuffled. Pick order: {}".format(
        league.get_id(), ", ".join([p.get_name() for p in league.get_participants()])))


@bot.command()
async def start_draft(ctx):
    """Starts the draft phase of the identified league."""
    if ctx.author.id not in admin_ids:
        return await ctx.send("This is an admin-only command.")
    for l in leagues:
        if l.get_channel() == ctx.channel.id:
            league = l
            break
    else:
        return await ctx.send("Invalid league ID.")
    if league.get_phase() != 0:
        return await ctx.send("The draft has already been started.")
    if len(league.get_participants()) == 0:
        return await ctx.send("There are no participants.")
    league.set_pick_order()
    league.next_phase()
    return await ctx.send("The draft has been started! Pick order: {}".format(
        ", ".join([p.get_name() for p in league.get_participants()])))


@bot.command()
async def substitute(ctx, old_id, new_id, new):
    """Wrapper for DraftParticipant.substitute()."""
    if ctx.author.id not in admin_ids:
        return await ctx.send("This is an admin-only command.")
    for l in leagues:
        if l.get_channel() == ctx.channel.id:
            league = l
            break
    else:
        return await ctx.send("This is not a drafting channel.")
    for p in league.get_participants():
        if int(p.get_discord()) == int(old_id):
            p.substitute(new, int(new_id))
            break
    else:
        return await ctx.send("The player you are attempting to substitute is not in the league.")
    return await ctx.send("<@{}> has been substituted for <@{}>!".format(old_id, new_id))


@bot.event
async def on_ready():
    """Prints 'ready' when bot is online. Starts timer for draft phase."""
    bot.loop.create_task(timer())
    print('ready')


async def timer():
    """Timer for draft phase."""
    while True:
        for l in leagues:
            if l.get_phase() == 1:
                msg = l.check_pick_deadline()
                if msg:
                    await bot.get_channel(l.get_channel()).send(msg)
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
