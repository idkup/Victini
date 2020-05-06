

from ChallongeApi import ChallongeApi
import re
from discord.ext import commands

bot = commands.Bot(command_prefix="_")

with open('challonge.txt') as challonge_key_file:
    CHALLONGE_KEY = challonge_key_file.readline()
    USERNAME = "Firling"

    challonge_key_file.close()

tournament = ChallongeApi(USERNAME, CHALLONGE_KEY)

ERROR_MESSAGE = "An error occurred or the tournament has not been created yet."

ADMIN_IDS = [590336288935378950, 173733502041325569]

@bot.command()
async def set_id(ctx, id=0):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    tournament.setId(int(id))
    await ctx.send("The tournament's ID has been set to {}".format(id))

@bot.command()
async def get_id(ctx):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    await ctx.send("The tournament current ID is {}".format(tournament.getId()))

@bot.command()
async def set_url(ctx, url=""):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    if not tournament.update_url(url):
        return await ctx.send(ERROR_MESSAGE)
    await ctx.send("The tournament's URL has been set to {}".format(tournament.getUrl()))

@bot.command()
async def get_url(ctx):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    await ctx.send("The tournament current URL is {}".format(tournament.getUrl()))

@bot.command()
async def set_name(ctx, name=""):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    if not tournament.update_name(name):
        return await ctx.send(ERROR_MESSAGE)
    await ctx.send("The tournament's Name has been set to {}".format(name))

@bot.command()
async def get_name(ctx):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    await ctx.send("The tournament current name is {}".format(tournament.getName()))

@bot.command()
async def set_type(ctx, type=""):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    if type.lower().replace("_", " ") not in ["single elimination", "double elimination", "round robin", "swiss", "free for all"]:
        msg = "The type you submitted is wrong, please chose between these types:\n"
        msg += "- Single_Elimination\n"
        msg += "- Double_Elimination\n"
        msg += "- Round_Robin\n"
        msg += "- Swiss\n"
        msg += "- Free_for_All"
        return await ctx.send(msg)
    if not tournament.update_type(type.lower().replace("_", " ")):
        return await ctx.send(ERROR_MESSAGE)
    await ctx.send("The tournament's Type has been set to {}".format(type))

@bot.command()
async def get_type(ctx):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    await ctx.send("The tournament current type is {}".format(tournament.getType()))

@bot.command()
async def create(ctx, name, url, type="single elimination"):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    if not tournament.create(name, url, type):
        return await ctx.send("An error occurred, or the tournament is already created.")
    await ctx.send("A new tournament as been created, id: {}".format(tournament.getId()))

@bot.command()
async def delete(ctx):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    id = tournament.getId()
    if not tournament.delete():
        return await ctx.send(ERROR_MESSAGE)
    await ctx.send("The tournament with the id {} has been deleted".format(id))

@bot.command()
async def process_check_in(ctx):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    if not tournament.process_check_in():
        return await ctx.send("An error occurred, or the tournament is not created yet, or the check_in has already started.")
    await ctx.send("The Check-In started.")

@bot.command()
async def abort_check_in(ctx):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    if not tournament.abort_check_in():
        return await ctx.send("An error occurred, or the tournament is not created yet, or the check_in has not started.")
    await ctx.send("The Check-In started.")

@bot.command()
async def get_check_in(ctx):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    return await ctx.send("The check-in status is {}".format("on" if tournament.getCheckIn() else "off"))

@bot.command()
async def start_tournament(ctx):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    if not tournament.start():
        return await ctx.send("An error occurred, or the tournament is not created yet, or the tournament has already started.")
    return await ctx.send("The tournament Started.")

@bot.command()
async def finalize_tournament(ctx):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    if not tournament.finalize():
        return await ctx.send(
            "An error occurred, or the tournament is not created yet, or the tournament has not started.")
    return await ctx.send("The tournament is now FINISHED.")

@bot.command()
async def reset_tournament(ctx):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    if not tournament.reset():
        return await ctx.send(ERROR_MESSAGE)
    return await ctx.send("The tournament has been reseted.")

@bot.command()
async def participants(ctx):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    participants = tournament.get_participants()
    if not participants:
        return await ctx.send(ERROR_MESSAGE)
    return await ctx.send("List of every participants: {}.".format(", ".join(participants.keys())))

@bot.command()
async def add_participant(ctx, name, challonge_name=""):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    if not tournament.add_participant(name, challonge_name):
        return await ctx.send(ERROR_MESSAGE)
    return await ctx.send("{} has been added to the participants list.".format(name))

@bot.command()
async def change_name(ctx, oldName, newName):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    if not tournament.update_participant_name(oldName, newName):
        return await ctx.send(ERROR_MESSAGE)
    return await ctx.send("{} has been updated to {}.".format(oldName, newName))

@bot.command()
async def change_challonge_name(ctx, currentName, newChallongeName):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    if not tournament.update_participant_challonge_name(currentName, newChallongeName):
        return await ctx.send(ERROR_MESSAGE)
    return await ctx.send("{} has been updated to {}.".format(currentName, newChallongeName))

@bot.command()
async def check_in_participant(ctx, name):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    if not tournament.check_in_participant(name):
        return await ctx.send(ERROR_MESSAGE)
    return await ctx.send("{} has been checked-in.".format(name))

@bot.command()
async def undo_check_in_participant(ctx, name):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    if not tournament.undo_check_in_participant(name):
        return await ctx.send(ERROR_MESSAGE)
    return await ctx.send("{} has been unchecked-in.".format(name))

@bot.command()
async def delete_participant(ctx, name):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    if not tournament.delete_participant(name):
        return await ctx.send(ERROR_MESSAGE)
    return await ctx.send("{} has been unchecked-in.".format(name))

@bot.command()
async def delete_everyone(ctx):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    if not tournament.delete_participants():
        return await ctx.send(ERROR_MESSAGE)
    return await ctx.send("Every participant has been unchecked-in.")

@bot.command()
async def randomize(ctx):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    if not tournament.randomize_participants():
        return await ctx.send(ERROR_MESSAGE)
    return await ctx.send("Every participant has been randomized in the tree.")

@bot.command()
async def randomize(ctx):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    if not tournament.randomize_participants():
        return await ctx.send(ERROR_MESSAGE)
    return await ctx.send("Every participant has been randomized in the tree.")

@bot.command()
async def result(ctx, scores, winner):
    if ctx.author.id not in ADMIN_IDS:
        return await ctx.send("You do not have the permission to run this command.")
    if not re.match("([0-9]-[0-9],?)+^$", scores):
        return await ctx.send("The scores must be under this forms \"1-3\" or \"1-3,2-3\"")
    if not tournament.update_match(winner, scores):
        return await ctx.send("An error occurred, or the tournament has not started or the winner has already been set.")
    return await ctx.send("The winner has been set for the match!")


bot.run("NjE1MjM2NjQ1NjkxNTg4NjI4.XWLF2A.QkzeLRmBHIic6BaSLgvFXWRnMi0")
