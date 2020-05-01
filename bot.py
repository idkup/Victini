from discord.ext import commands
with open('files/key.txt') as key_file:
    KEY = key_file.readline()
    key_file.close()
bot = commands.Bot(command_prefix='_')
bot.run(KEY)

