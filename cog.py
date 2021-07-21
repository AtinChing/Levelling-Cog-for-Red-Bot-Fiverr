import discord
from discord.ext import commands
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
        level = 0
        totalpointreq = 255
        totalpointreqchange = 155
        totalpointreqchangechange = 65
        if xp > 100:
            level += 1
            while xp >= totalpointreq:
                level += 1
                totalpointreqchange += totalpointreqchangechange
                totalpointreqchangechange += 10
                totalpointreq += totalpointreqchange
        return level

    def determine_xp(self, level): # Formula to get the amount of xp a user should have according to the level they have.
        l = 0
        totalpointreq = 0
        totalpointreqchange = 100
        totalpointreqchangechange = 55
        while l < level:
            l += 1
            totalpointreq += totalpointreqchange
            totalpointreqchange += totalpointreqchangechange
            totalpointreqchangechange += 10
        return totalpointreq

    def register_user(self, user): # Register user into the database
        if not self.connected: # If a connection to database hasn't been established 
            if not self.connect_to_db(): # Trying to make connection here. If we can't then we return false and exit the function
                return False    
        self.collection.insert_one({
                    'name' : user.name,
                    '_id' : user.id, # _id (which is the primary key/identifier/unique field among all member entries in the database) is the discord user's id.
                    'level' : 0,
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
            else: raise TypeError
        except(TypeError):
            await ctx.send("Invalid amount of levels was passed in!")


def setup(client):
    client.add_cog(Levelcog(client))