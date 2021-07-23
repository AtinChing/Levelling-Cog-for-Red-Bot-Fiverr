import discord
from discord import user
from discord.ext import commands
from discord.ext.commands.errors import CommandInvokeError, MemberNotFound
from discord.utils import get
import datetime
import pymongo
from pymongo import MongoClient

class Levelcog(commands.Cog):   

    def __init__(self, bot):
        self.bot : commands.Bot = bot
        self.db = None
        self.client = None
        self.collection = None
        self.connected = False # Whether the bot is connected to the db.
        self.connect_to_db()

    def connect_to_db(self):
        try:
            self.client = MongoClient('mongodb://localhost:27017/?readPreference=primary&appname=MongoDB%20Compass&directConnection=true&ssl=false')
            self.db = self.client.discord_members
            self.collection = self.db.members
            self.connected = True
            return True # Connection successfully made, return true
        except(Exception):
            print("Connection to db failed.")
            self.connected = False
            return False # Connection could not be made, return false

    def determine_level(self, xp): # Formula to get the level a user should have according to the amount of xp they have.
        level = 1
        totalpointreq = 250
        currentpointreq = 250
        pointreqchange = 150
        if xp > 100:
            level += 1
            while xp >= totalpointreq:
                level += 1
                currentpointreq += pointreqchange
                totalpointreq += currentpointreq
        return level

    def determine_xp(self, level): # Formula to get the amount of xp a user should have according to the level they have.
        lev = 1
        totalpointreq = 0
        currentpointreq = 100
        pointreqchange = 150
        if level > 1:
            lev += 1
            while level > lev:
                currentpointreq += pointreqchange
                totalpointreq += currentpointreq
                lev += 1
        return totalpointreq

    def register_user(self, user): # Register user into the database
        if not self.connected: # If a connection to database hasn't been established 
            if not self.connect_to_db(): # Trying to make connection here. If we can't then we return false and exit the function
                return False    
        self.collection.insert_one({
                    'name' : user.name,
                    '_id' : user.id, # _id (which is the primary key/identifier/unique field among all member entries in the database) is the discord user's id.
                    'level' : 1,
                    'xp' : 0,
                    'background' : None 
        })
        return True # Could register user into the db        
            
    
    @commands.command()
    async def initialise(self, ctx, *args):
        embed : discord.Embed = discord.Embed(title="Members added to the database", description='') # Embed that stores all the members added to the database.
        for m in self.bot.guilds[0].members: # Bot is only in 1 server/guild thats why we can use self.bot.guilds[0]
            if self.collection.find_one({'_id' : m.id}) == None and not m.bot: # If the member could not be found in the db, then find_one() returns NoneType, so that's how we know the member doesn't exist in the db.
                if self.connected: # Registering user into db. If they can't then that means a connection to the db couldn't be established
                    self.register_user(m)
                    embed.description += "\n " + m.mention
                else: 
                    await ctx.send('A connection to the database could not be made, as a result, members of the server, who are not in the database, could not be initialised into the database.')
                    return
        await ctx.send(embed=embed)
    
    @commands.command()
    async def add_level(self, ctx, user : discord.Member,  level_arg : int) :
        try:
            level = int(level_arg)
            if level >= 1 and self.connected: # If connection to database is alive and level being added is more than 0
                self.collection.update_one({'_id' : user.id}, {"$inc" : {'level' : level}, '$set' : {'xp' : self.determine_xp(level)}}) # Updating the member entry in the database according to their level.
            elif level <= 0: raise TypeError # Raising typeerror here so that it passes on to the except statement and sends the "invalid levels" message. 
            else: await ctx.send("Connection to database could not be made!") # Otherwise, the only scenario is that the bot is not connected to the database.
        except(TypeError):
            await ctx.send("Invalid amount of levels was passed in!")
        except(AttributeError) as e: # CommandInvokeError is thrown if the user value could not be found or initialized.
            await ctx.send(e)

    @commands.command()
    async def subtract_level(self, ctx, user : discord.Member, level_arg : int):
        try:
            level = int(level_arg)
            if level >= 1 and self.connected:
                self.connection.update_one({'_id' : user.id}, {'$inc' : {'level' : -level}, '$set' : {'xp' : self.determine_xp(-level)}})
            elif level <= 0: raise TypeError # Raising typeerror here so that
            else: await ctx.send("Connection to database could not be made!")    
        except(TypeError):
            await ctx.send("Invalid amount of levels was passed in!")
        except(AttributeError):
            await ctx.send("Invalid username was passed in!")

    @commands.command()
    async def set_level(self, ctx, user : discord.Member, level_arg : int):
        try:
            level = int(level_arg)
            if level >= 1 and self.connected:
                self.collection.update_one({'_id': user.id}, {'$set', {'level' : level, 'xp' : self.determine_xp(level)}})
            elif level <= 0: raise TypeError
            else: await ctx.send("Connection to database could not be made!") 
        except(TypeError):
            await ctx.send("Invalid amount of levels was passed in!")
        except(AttributeError):
            await ctx.send("Invalid username was passed in!")

    @commands.command()
    async def reset_level(self, ctx, user : discord.Member):
        try:
            if self.connected:
                self.collection.update_one({'_id' : user.id}, {'$set' : {'level' : 1, 'xp' : 0}})
            else:
                await ctx.send("Connections to database could not be made!")
        except(AttributeError):
            await ctx.send("Invalid username was passed in!")    

    @commands.command()
    async def leaderboard(self, ctx):
        if self.connected:
            leaderboard = list(self.collection.find({}).sort('xp', pymongo.DESCENDING).limit(10))
            total_count = len(leaderboard)
            embed = discord.Embed()
            embed_list = []
            i = 0
            while total_count >= 1: # Keep making pages as long as there are user entries left.
                if total_count > 0 and total_count < 10:
                    embed = discord.Embed(title='Leaderboard ' + "(Showing " + str(i + 1) + " - " + str(len(leaderboard)) + ")", description='')
                    while i <= total_count - 1 and (i == 0 or i % 10 != 0):
                        user_dict = self.collection.find_one({'_id' : leaderboard[i]['_id']})
                        embed.description += str(i + 1) + '. ' + self.bot.get_user(leaderboard[i]['_id']).mention + ' | Level ' + str(user_dict['level']) +' | ' + str(user_dict['xp'] - self.determine_xp(user_dict['level'])) + '/' + str(self.determine_xp(user_dict['level'] + 1) - self.determine_xp(user_dict['level'])) + '\n\n'
                        i += 1
                    embed_list.append(embed)
                total_count -= 10
            if len(embed_list) > 0:
                for e in embed_list:
                    e.set_footer(text = str(datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
                    e.set_thumbnail(url=ctx.guild.icon_url)
                    msg_send : discord.Message = await ctx.send(embed=e)
                    #await msg_send.add_reaction(":▶:")
                    #await msg_send.add_reaction(":arrow_left:")
                    #await msg_send.add_reaction(":x:")



def setup(client):
    client.add_cog(Levelcog(client))