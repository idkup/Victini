from discord.ext import commands
with open('key.txt') as key_file:
    KEY = key_file.readline()
    key_file.close()
bot = commands.Bot(command_prefix='_')
bot.run(KEY)

