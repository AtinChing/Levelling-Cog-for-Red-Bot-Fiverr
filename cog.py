from asyncio import windows_events
import asyncio
from time import time
import discord
from discord import user
from discord.ext import commands
from discord.ext.commands.errors import CommandInvokeError, MemberNotFound
from discord.utils import get
import datetime
import pymongo
from pymongo import MongoClient
import json
import calendar # calendar libraray is used for quick conversion from int (returned by weekday()) to weekday str.

class Levelcog(commands.Cog):   

    def __init__(self, bot):
        self.bot : commands.Bot = bot
        self.db = None
        self.client = None
        self.collection = None
        self.connected = False # Whether the bot is connected to the db.
        json_dict = json.load(open('data.json', 'r'))
        self.xp_per_message = json_dict['levelfactor']
        self.voice_xp_rate = json_dict['voice_xp_rate']
        self.bonus_xp_rate = json_dict['bonus_xp_rate']
        self.bonus_xp_days = json_dict['bonus_days']
        self.valid_days = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
        self.connect_to_db()
        asyncio.create_task(self.give_voice_xp(60))

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
                    'normal_xp' : 0,
                    'bonus_xp' : 0,
                    'total_xp' : 0,
                    'voice_xp' : 0, 
                    'background' : None 
        })
        return True # Could register user into the db    
    
    def update_user_in_db(self, user): # Updates the level field of a user, in the db, accordingly with the users total xp. Called whenever the normal_xp or bonus_xp of a user is changed.
        cloned_dict = dict(self.collection.find_one({'_id' : user.id}))
        self.collection.update_one({'_id' : user.id}, {'$set' : {'total_xp' : cloned_dict['normal_xp'] + cloned_dict['bonus_xp']}}) # Updates the users total_xp field, within the db, which is calculated by adding normal_xp and bonus_xp.
        cloned_dict = dict(self.collection.find_one({'_id' : user.id})) # Refreshing the the dict to have the newly updated xp value
        self.collection.update_one({'_id' : user.id}, {'$set' : {'level' : self.determine_level(cloned_dict['total_xp'])}}) # Then it updates the users level field, in the db, accordingly with the users total_xp.

    async def give_voice_xp(self, delay): # Voice xp is given per minute, so this function is called every minute to check every single voice channel in the server and give users voice xp accordingly.
        if self.connected:
            for channel in self.bot.guilds[0].voice_channels: # We can just use bot.guilds[0] because the bot is only in 1 server.
                json_dict = json.load(open('data.json', 'r'))
                non_bot_members = [] # Non-bot users connected to the voice channel.
                for m in channel.members: 
                    if not m.bot: non_bot_members.append(m)
                if len(non_bot_members) >= 2 and channel.id not in json_dict['blacklisted']['channels'] and channel.category.id not in json_dict['blacklisted']['channels']:
                    for member in non_bot_members:
                        if not member.bot and not member.voice.self_mute and not member.voice.self_deaf and self.collection.find_one({'_id' : member.id}) != None:
                            self.collection.update_one({'_id' : member.id}, {'$inc' : {'voice_xp' : self.voice_xp_rate}})
            time.sleep(delay)
            asyncio.create_task(self.give_voice_xp(60)) # Check and give voice xp again in 1 minute/60 seconds.

    @commands.Cog.listener()
    async def on_message(self, message : discord.Message):
        author = message.author
        if author.bot: return
        if self.connected: 
            entry = self.collection.find_one({'_id' : author.id}) 
            json_dict = json.load(open('data.json', 'r'))
            time_diff = datetime.datetime.now() - datetime.datetime.fromisoformat(json_dict['last_messages'][str(author.id)]) # The difference in time/time passed between the last message the user sent and the message they just sent.
            json_dict['last_messages'][str(author.id)] =  str(datetime.datetime.now()) # Updating the last_message entry in the json.
            if entry != None and message.channel.id not in json_dict['blacklisted']['channels'] and message.channel.category_id not in json_dict['blacklisted']['categories'] and time_diff >= datetime.timedelta(seconds=10): # If the entry could be extracted from the database and if the channel or category the message was sent isn't blacklisted.
                self.collection.update_one({'_id' : author.id}, {'$inc' : {'normal_xp' : self.xp_per_message}, '$set' : {'level' : self.determine_level(entry['normal_xp'] + self.xp_per_message)}})
                self.update_user_in_db(author)
                if calendar.day_name[datetime.datetime.now().weekday()].lower in json_dict['bonus_days']: # If today is one of the bonus xp days:
                    self.collection.update_one({'_id' : author.id}, {'$inc' : {'bonus_xp' : self.xp_per_message * self.bonus_xp_rate}})
                    self.update_user_in_db(author)
            elif entry == None: self.register_user(author)
            with open('data.json', 'w') as file:
                json.dump(json_dict, file, indent=4)
   
    @commands.command()
    async def status(self, ctx, *args): # Returns embed containing the bot's status, like its connection to the database, latency etc.
        embed = discord.Embed(title='Bot Status')
        embed.set_footer(text=str(datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
        embed.add_field(name='Connection to database', value=self.connected, inline=True)
        embed.add_field(name='Latency', value=self.bot.latency, inline=True)
        embed.set_thumbnail(url=self.bot.user.avatar_url)
        await ctx.send(embed=embed)

    @commands.command()
    async def initialise(self, ctx, *args):
        embed : discord.Embed = discord.Embed(title="Members added to the database", description='') # Embed that stores all the members added to the database.
        for m in self.bot.guilds[0].members: # Bot is only in 1 server/guild thats why we can use self.bot.guilds[0]
            if self.collection.find_one({'_id' : m.id}) == None: # If the member could not be found in the db, then find_one() returns NoneType, so that's how we know the member doesn't exist in the db.
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
                current = dict(self.collection.find_one({'_id' : user.id})) # The current bonus xp the user has, according to the db.
                current_bonus_xp = current['bonus_xp']
                new_level = current['level'] + level
                self.collection.update_one({'_id' : user.id}, {'$inc' : {'level' : level}, '$set' : {'normal_xp' : self.determine_xp(new_level) - current_bonus_xp, 'total_xp' : self.determine_xp(level)}}) # Updating the member entry in the database according to their level.
                await ctx.send('Gave ' + str(level) + ' levels to ' + user.mention + "!")
            elif level <= 0: raise TypeError # Raising typeerror here so that it passes on to the except statement and sends the "invalid levels" message. 
            else: await ctx.send("Connection to database could not be made!") # Otherwise, the only scenario is that the bot is not connected to the database.
        except(TypeError):
            await ctx.send("Invalid amount of levels was passed in!")
        except(AttributeError): # AttributeError is thrown if the user value could not be found or initialized.
            await ctx.send('Invalid username was passed in!')

    @commands.command()
    async def subtract_level(self, ctx, user : discord.Member, level_arg : int):
        try:
            level = int(level_arg)
            if level >= 1 and self.connected:
                current = dict(self.collection.find_one({'_id' : user.id})) # The current bonus xp the user has, according to the db.
                current_bonus_xp = current['bonus_xp']
                new_level = current['level'] - level
                if new_level <= 0: raise TypeError # We can't minus the level all the way to to 0 or negative.
                self.collection.update_one({'_id' : user.id}, {'$inc' : {'level' : -level}, '$set' : {'normal_xp' : self.determine_xp(new_level) - current_bonus_xp, 'total_xp' : self.determine_xp(level)}})
                await ctx.send('Took away ' + str(level) + ' levels from ' + user.mention + "!")
            elif level <= 0: raise TypeError # Raising typeerror here so that it sends the invalid amount of levels message
            else: await ctx.send("Connection to database could not be made!")    
        except(TypeError):
            await ctx.send("Invalid amount of levels was passed in!")
        except(AttributeError):
            await ctx.send("Invalid username was passed in!")

    @commands.command()
    async def set_level(self, ctx, user : discord.Member, level_arg : int, *args):
        try:
            level = int(level_arg)
            if level >= 1 and self.connected:
                current_bonus_xp = dict(self.collection.find_one({'_id' : user.id}))['bonus_xp'] # The current bonus xp the user has, according to the db.
                self.collection.update_one({'_id': user.id}, {'$set' : {'level' : level, 'normal_xp' : self.determine_xp(level) - current_bonus_xp, 'total_xp' : self.determine_xp(level)}})
                await ctx.send('Set ' + user.mention + "'s level to " + str(level))
            elif level <= 0: 
                raise TypeError
            else: await ctx.send("Connection to database could not be made!") 
        except(TypeError):
            await ctx.send("Invalid amount of levels was passed in!")
        except(AttributeError):
            await ctx.send("Invalid username was passed in!")

    @commands.command()
    async def reset_level(self, ctx, user : discord.Member, *args):
        try:
            if self.connected:
                self.collection.update_one({'_id' : user.id}, {'$set' : {'level' : 1, 'normal_xp' : 0, 'bonus_xp' : 0, 'total_xp' : 0}})
                await ctx.send('Reset ' + user.mention + "'s level to 1!")
            else:
                await ctx.send("Connections to database could not be made!")
        except(AttributeError):
            await ctx.send("Invalid username was passed in!")    

    @commands.command()
    async def add_xp(self, ctx, user : discord.Member, xp_arg : int, *args):
        try:
            xp = int(xp_arg)
            if xp >= 1 and self.connected:
                self.collection.update_one({'_id' : user.id}, {'$inc' : {'normal_xp' : xp}}) # We increase the normal_xp field of the user, within the database, by the amount of xp passed in.
                self.update_user_in_db(user) # Then we call update_user_in_db() to update the total_xp and level fields of the user within the database.
            elif xp < 1: 
                raise TypeError
            else: await ctx.send("Connection to database could not be made!") 
        except(TypeError):
            await ctx.send("Invalid amount of xp was passed in!")
            
    @commands.command()
    async def subtract_xp(self, ctx, user : discord.Member, xp_arg : int, *args):
        try:
            xp = int(xp_arg)
            if xp >= 1 and self.connected:
                self.collection.update_one({'_id' : user.id}, {'$inc' : {'normal_xp' : -xp}}) # We decrease the normal_xp field of the user, within the database, by the amount of xp passed in (by using the negation of the number of xp passed in).
                self.update_user_in_db(user) # Then we call update_user_in_db() to update the total_xp and level fields of the user within the database.
            elif xp < 1: 
                raise TypeError
            else: await ctx.send("Connection to database could not be made!") 
        except(TypeError):
            await ctx.send("Invalid amount of xp was passed in!")

    @commands.command()
    async def leaderboard(self, ctx):
        if self.connected:
            leaderboard = list(self.collection.find({}).sort('total_xp', pymongo.DESCENDING).limit(10))
            total_count = len(leaderboard)
            embed_list = []
            i = 0
            while total_count >= 1: # Keep making pages as long as there are user entries left.
                if total_count > 0 and total_count < 10:
                    embed = discord.Embed(title='Leaderboard ' + "(Showing " + str(i + 1) + " - " + str(len(leaderboard)) + ")", description='')
                    while i <= total_count - 1 and (i == 0 or i % 10 != 0):
                        user_dict = self.collection.find_one({'_id' : leaderboard[i]['_id']})
                        embed.description += str(i + 1) + '. ' + self.bot.get_user(leaderboard[i]['_id']).mention + '\n' +  str(user_dict['total_xp']) + " XP  :microphone2: " + str(user_dict['voice_xp']) + "  :trophy: " + str(user_dict['bonus_xp'])  
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

    @commands.command()
    async def set_bonus_xp_days(self, ctx, *args):
        for arg in args:
            if self.connected and arg.lower() in self.valid_days: 
                arg_lower = arg.lower()
                if arg_lower not in self.bonus_xp_days: # If the current day entered IS NOT in the already active bonus days
                    self.bonus_xp_days.append(arg_lower) # We add it
                    temp_dict = dict(json.load(open('data.json', 'r')))
                    temp_dict['bonus_days'] = self.bonus_xp_days
                    with open('data.json', 'w') as file:
                        json.dump(temp_dict, file, indent=4)
                    await ctx.send(arg + " has been set as a bonus xp day!")
                else: await ctx.send(arg + ' is already a bonus xp day!') # Otherwise it's already one of the active bonus xp days. 
            elif not self.connected: await ctx.send("The bot could not connect to the database.")
            else: await ctx.send('You sent in an invalid day!')
    
    @commands.command()
    async def unset_bonus_xp_days(self, ctx, *args):
        for arg in args:
            if self.connected and arg.lower() in self.valid_days:
                arg_lower = arg.lower()
                if arg_lower in self.bonus_xp_days: # If the current day entered IS in the already active bonus days
                    self.bonus_xp_days.remove(arg_lower) # We remove it.
                    temp_dict = dict(json.load(open('data.json', 'r')))
                    temp_dict['bonus_days'] = self.bonus_xp_days
                    with open('data.json', 'w') as file:
                        json.dump(temp_dict, file, indent=4)
                    await ctx.send(arg + ' is no longer a bonus xp day!')
                else: await ctx.send(arg + ' is not a bonus xp day!')
            elif not self.connected: await ctx.send("The bot could not connect to the database.")
            else: await ctx.send('You sent in an invalid day!')
        
    @commands.command()
    async def set_xp_per_message(self, ctx, xp, *args):
        try:
            xp = int(xp) # Trying to convert the xp arg to a number
            if xp < 0: raise ValueError # We can't have negative xp for a number
        except(ValueError): # ValueError is thrown if xp couldn't be converted to int.
            await ctx.send('You sent in an invalid number!')
            return
        self.xp_per_message = xp
        # Updates the levelfactor field in data.json, so that it's value is used as the xp/levelfactor when the bot is started up next time. 
        with open('data.json', 'r') as file: # Creates temp dict object to hold all the values
            temp_dict = json.load(file) 
        temp_dict['levelfactor'] = xp # Updates levelfactor value in cloned dict object
        with open('data.json', 'w') as file: # Sets data.json to the newly updated cloned dict
            json.dump(temp_dict, file, indent=4)
        await ctx.send('The amount of xp given per message has been set to ' + str(xp))

    @commands.command()
    async def set_bonus_xp_rate(self, ctx, rate, *args):
        try:
            rate = int(rate)
            if rate < 0: raise ValueError # Rates below 0 are invalid.
        except(ValueError):
            await ctx.send('The rate you sent in is an invalid number!')
            return
        self.bonus_xp_rate = rate
        # Updates the levelfactor field in data.json, so that it's value is used as the xp/levelfactor when the bot is started up next time. 
        temp_dict = json.load('data.json', 'r') # Creates temp dict object to hold all the values
        temp_dict['bonus_xp_rate'] = rate # Updates levelfactor value in cloned dict object
        with open('data.json', 'w') as file: # Sets data.json to the newly updated cloned dict
            json.dump(temp_dict, file, indent=4)
        await ctx.send('The rate of bonus xp has been set to ' + str(rate))    

    @commands.command()
    async def set_voice_xp_rate(self, ctx, rate, *args):
        try:
            rate = int(rate)
            if rate < 0: raise ValueError
        except(ValueError):
            await ctx.send('The rate you sent in is an invalid number!')
            return
        self.voice_xp_rate = rate
        temp_dict = json.load(open('data.json', 'r'))
        temp_dict['voice_xp_rate'] = rate
        with open('data.json', 'w') as file:
            json.dump(temp_dict, file, indent=4)
        await ctx.send('The amount of voice xp given per minute has been set ' + str(rate))

    @commands.command()
    async def blacklist_channel(self, ctx, channel, *args):
        try:
            channel = self.bot.get_channel(int(channel.replace('<', '').replace('>', '').replace('#', '')))
        except(Exception): # if there was an error while trying to get the channel
            await ctx.send('The channel you sent in could not be found!')
            return
        temp_dict = json.load(open('data.json', 'r'))
        if channel.id not in temp_dict['blacklisted']['channels']:
            temp_dict['blacklisted']['channels'].append(channel.id)
        else:
            await ctx.send('The channel you sent in is already blacklisted!')
            return
        with open('data.json', 'w') as file:
            json.dump(temp_dict, file, indent=4)
        await ctx.send(channel.mention + ' is now blacklisted. None of the messages sent in it will gain xp for their sender!')

    @commands.command()
    async def unblacklist_channel(self, ctx, channel, *args):
        try:
            channel = self.bot.get_channel(int(channel.replace('<', '').replace('>', '').replace('#', '')))
        except(Exception): # if there was an error while trying to get the channel
            await ctx.send('The channel you sent in could not be found!')
            return
        temp_dict = json.load(open('data.json', 'r'))
        if channel.id in temp_dict['blacklisted']['channels']: # Only remove it if it is in the blacklisted channels list
            temp_dict['blacklisted']['channels'].remove(channel.id)
        else:
            await ctx.send('The channel you sent in is already not blacklisted!')
            return 
        with open('data.json', 'w') as file:
            json.dump(temp_dict, file, indent=4)
        await ctx.send(channel.mention + ' is no longer blacklisted. Messages sent in it will now gain xp for their sender!')

    @commands.command()
    async def blacklist_category(self, ctx, *args):
        try:
            category_id = int(args[0]) # Trying to convert arg into int by default, presuming its an int for ID
            category = get(ctx.guild.categories, id=category_id)
        except(ValueError): # if there was an error in trying to convert it, then it must be the category name that is being passed in=
            category_name = ''
            for arg in args:
                category_name += arg + ' '
            category = get(ctx.guild.categories, name=category_name[:-1]) # :-1 to remove the last extra space
        if category == None: # If category couldn't be found
            await ctx.send('The category you sent in could not be found!')
        else:
            temp_dict = json.load(open('data.json', 'r'))
            if category.id not in temp_dict['blacklisted']['categories']:
                temp_dict['blacklisted']['categories'].append(category.id)
            else: 
                await ctx.send('The category you sent in is already blacklisted!')
                return
            with open('data.json', 'w') as file:
                json.dump(temp_dict, file, indent=4)
            await ctx.send(category.mention + ' is now blacklisted. None of the messages sent in it will gain xp for their sender!')

    @commands.command()
    async def unblacklist_category(self, ctx, *args):
        try:
            category_id = int(args[0]) # Trying to convert arg into int by default, presuming its an int for ID
            category = get(ctx.guild.categories, id=category_id)
        except(ValueError): # if there was an error in trying to convert it, then it must be the category name that is being passed in=
            category_name = ''
            for arg in args:
                category_name += arg + ' '
            category = get(ctx.guild.categories, name=category_name[:-1]) # :-1 to remove the last extra space
        if category == None: # If category couldn't be found
            await ctx.send('The category you sent in could not be found!')
        else:
            temp_dict = json.load(open('data.json', 'r'))
            if category.id in temp_dict['blacklisted']['categories']: # Only remove it if it is in the blacklisted categories list
                temp_dict['blacklisted']['categories'].remove(category.id)
            else:
                await ctx.send('The category you sent in is already not blacklisted!')
                return
            with open('data.json', 'w') as file:
                json.dump(temp_dict, file, indent=4)
            await ctx.send(category.mention + ' is no longer blacklisted. Messages sent in it will now gain xp for their sender!')
        
def setup(client):
    client.add_cog(Levelcog(client)) 