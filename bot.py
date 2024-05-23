import discord
from discord.ext import tasks

from datetime import datetime, timedelta
import os

# The message to watch for reactions
WATCHED_MESSAGE_ID = 1243160802014269461

# The first role to be given, upon reacting to the message
GIVEN_ROLE_TIER1_ID = 1243160838593056808

# The second role to be given, upon having the first role and being in the server for WAITTIME mins
GIVEN_ROLE_TIER2_ID = 1243211172011049020

# Channel to print messages to, and guild to join for role data
DEBUG_CHANNEL = 1243218823059083286
GUILD_ID = 1243159672362631200

WAITTIME = 1440 # 1 day = 1440 mins

intents = discord.Intents.default()
intents.reactions = True # We want to listen for reactions
intents.members = True


class ErasureClient(discord.Client):
    async def debug_message(self, message):
        channel = self.get_channel(DEBUG_CHANNEL)
        await channel.send(message)
    
    # We can't be guaranteed that the message we want to listen on will be in the cache, so we need to use the raw reaction add here.
    async def on_raw_reaction_add(self, event): 
        if event.message_id != WATCHED_MESSAGE_ID: 
            return # The reaction is on a different message
        member = event.member

        if member.get_role(GIVEN_ROLE_TIER1_ID) == None and member.get_role(GIVEN_ROLE_TIER2_ID) == None: # If they don't already have the role, or the t2 version...
            role = self.guild.get_role(GIVEN_ROLE_TIER1_ID)
            await self.debug_message("added role to " + member.display_name)
            await member.add_roles(role) # ...give it to them

    async def on_ready(self):
        self.guild = self.get_guild(GUILD_ID)
        channel = self.get_channel(DEBUG_CHANNEL)
        await channel.send("Started ErasureBot, listening for reactions on message " + str(WATCHED_MESSAGE_ID) + " giving role " + str(GIVEN_ROLE_TIER1_ID))
        
    @discord.ext.tasks.loop(minutes=1)
    async def check_tier2(self):
        await self.debug_message("running job!!")
        # Get all the users with the tier1 role...
        t1_members = self.guild.get_role(GIVEN_ROLE_TIER1_ID).members
        print(str(t1_members))
        for member in t1_members:
            await self.debug_message("for user " + member.display_name + "   " + str(member.joined_at))
            if datetime.now(member.joined_at.tzinfo) - timedelta(minutes=WAITTIME) > member.joined_at:
                await member.add_roles(self.guild.get_role(GIVEN_ROLE_TIER2_ID))
                await member.remove_roles(self.guild.get_role(GIVEN_ROLE_TIER1_ID))
                await self.debug_message("updated role for " + member.display_name)

    @check_tier2.before_loop
    async def before_check_tier2(self):
        await self.wait_until_ready()
        

    async def setup_hook(self) -> None:
        self.check_tier2.start()


client = ErasureClient(intents=intents)

def main():
    with open('secret.token', 'r') as file:
        token = file.read().rstrip()
    client.run(token)


if __name__=="__main__":
    main()