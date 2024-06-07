import discord
from discord.ext import tasks

from datetime import datetime, timedelta
import os, json

DEBUG = True
VERSION = -1
config = None

WAITTIME = 1440 # 1 day = 1440 mins

intents = discord.Intents.default()
intents.reactions = True # We want to listen for reactions
intents.members = True


class ErasureClient(discord.Client):
    async def debug_message(self, message):
        channel = self.get_channel(config['debug_channel'])
        await channel.send(message)
    
    # We can't be guaranteed that the message we want to listen on will be in the cache, so we need to use the raw reaction add here.
    async def on_raw_reaction_add(self, event): 
        if event.message_id != config['watched_message']: 
            return # The reaction is on a different message
        member = event.member

        if member.get_role(config['given_role_t1']) == None and member.get_role(config['given_role_t2']) == None: # If they don't already have the role, or the t2 version...
            role = self.guild.get_role(config['given_role_t1'])
            # await self.debug_message("added role to " + member.display_name)
            await member.add_roles(role) # ...give it to them

    async def on_ready(self):
        self.guild = self.get_guild(config['guild_id'])
        channel = self.get_channel(config['debug_channel'])
        await channel.send("Booting ErasureOS...")
        
    @discord.ext.tasks.loop(minutes=1)
    async def check_tier2(self):
        # Get all the users with the tier1 role...
        t1_members = self.guild.get_role(config['given_role_t1']).members
        for member in t1_members:
            # await self.debug_message("for user " + member.display_name + "   " + str(member.joined_at))
            if datetime.now(member.joined_at.tzinfo) - timedelta(minutes=config['automatic_role_t2_waittime']) > member.joined_at:
                await member.add_roles(self.guild.get_role(config['given_role_t2']))
                await member.remove_roles(self.guild.get_role(config['given_role_t1']))
                # await self.debug_message("updated role for " + member.display_name)

    @check_tier2.before_loop
    async def before_check_tier2(self):
        await self.wait_until_ready()
        

    async def setup_hook(self) -> None:
        if config['automatic_role_t2']:
            self.check_tier2.start()


client = ErasureClient(intents=intents)

def main():
    global config

    with open('secret.token', 'r') as file:
        token = file.read().rstrip()
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
    
    VERSION = config['version']
    
    if DEBUG:
        config = config["debug"]
    else:
        config = config["live"]

    print(config)
    client.run(token)


if __name__=="__main__":
    main()
