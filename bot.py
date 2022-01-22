import discord
from discord.ext import commands
bot = commands.Bot(command_prefix='.', intents= discord.Intents.all())

@bot.event
async def on_ready():
    print('Bot is ready.')
@bot.command()
async def load(ctx, extension):
    bot.load_extension(extension)
    print('Loaded ' + extension)
@bot.command()
async def unload(ctx, extension):
    bot.unload_extension(extension)
    print('Unloaded ' + extension)

bot.load_extension('levelling') # Loading cog by default without need of commands.

bot.run('ODQwOTc1NTk0OTUwMzYxMDg4.YJgBjg.26luccinvUzAVKSeE2gXY3Zyopk')
