from DraftLeague import DraftLeague
from DraftParticipant import DraftParticipant
import asyncio
from discord.ext import commands
import discord
import pickle

admin_ids = [590336288935378950]
bot = commands.Bot(command_prefix='_')


@bot.command()
async def debug_phase(ctx, phase="0"):
    """Sets the phase to whatever I want."""
    if ctx.author.id not in admin_ids:
        return await ctx.send("This is an admin-only command.")
    league.set_phase(int(phase))
    return await ctx.send("Phase set to {}".format(league.get_phase()))


@bot.command()
async def debug_reset(ctx):
    """Wipes the league."""
    if ctx.author.id not in admin_ids:
        return await ctx.send("This is an admin-only command.")
    league = DraftLeague()
    return await ctx.send("League reset. Completely.")


@bot.command()
async def draft(ctx, *args):
    """Wrapper for DraftLeague.draft()."""
    name = " ".join(args)
    for p in league.get_participants():
        if p.get_discord() == ctx.author.id:
            picker = p
            break
    else:
        return await ctx.send("You are not in the draft!")
    for mon in league.get_all_pokemon():
        if str(mon).lower() == name.strip().lower():
            to_draft = mon
            break
    else:
        return await ctx.send("The Pokemon you are attempting to draft is not recognized!")
    if league.draft(picker, to_draft) is True:
        return await ctx.send("{} has drafted {}!".format(ctx.author.mention, name.title()))
    else:
        return await ctx.send("Could not draft {}.".format(name.title()))


@bot.command()
async def info(ctx, *args):
    """Prints str(DraftParticipant) to Discord if possible."""
    name = " ".join([*args])
    n = league.get_user(name)
    if n is False:
        return await ctx.send("{} is not participating in the draft.".format(name))
    else:
        return await ctx.send(str(league.get_user(name)))


@bot.command()
async def participants(ctx):
    """Wrapper for DraftLeague.get_participants()."""
    pl = [x.get_name() for x in league.get_participants()]
    if len(pl) == 0:
        return await ctx.send("No participants yet!")
    else:
        return await ctx.send("Participants ({}): {}".format(len(pl), ", ".join(pl)))


@bot.command()
async def register(ctx):
    """Registers the user to the DraftLeague as a DraftParticipant."""
    if league.get_phase() != 0:
        return await ctx.send("It is too late to register!")
    for x in league.get_participants():
        if x.get_discord() == ctx.author.id:
            return await ctx.send("You are already registered!")
    league.add_participant(DraftParticipant(ctx.author.id, ctx.author.name))
    return await ctx.send("{}, you are now registered!".format(ctx.author.mention))


@bot.event
async def on_ready():
    """Prints 'ready' when bot is online."""
    print('ready')


with open('files/key.txt') as key_file:
    bot_key = key_file.readline()
    key_file.close()
try:
    with open('files/league.txt', 'rb') as backup:
        league = pickle.load(backup)
        backup.close()
except FileNotFoundError:
    league = DraftLeague()
bot.run(bot_key)
