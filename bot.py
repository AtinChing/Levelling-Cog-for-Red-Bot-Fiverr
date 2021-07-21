import discord
from discord.ext import commands
from discord.ext.commands.core import command 
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

bot.load_extension('cog') # Loading cog by default without need of commands.

bot.run('ODQwOTc1NTk0OTUwMzYxMDg4.YJgBjg.AbNi7Lgz3przn5O1TmoI5why53w')