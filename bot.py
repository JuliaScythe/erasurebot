import discord
from discord.ext import tasks
from discord import app_commands

from datetime import datetime, timedelta
import os, json

DEBUG = False
VERSION = -1
config = None

WAITTIME = 1440 # 1 day = 1440 mins

intents = discord.Intents.default()
intents.reactions = True # We want to listen for reactions
intents.members = True


class ErasureClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super(ErasureClient, self).__init__(*args, **kwargs)
        self.tree = discord.app_commands.CommandTree(self)

    async def debug_message(self, message):
        channel = self.get_channel(config['debug_channel'])
        await channel.send(message)
    
    # We can't be guaranteed that the message we want to listen on will be in the cache, so we need to use the raw reaction add here.
    async def on_raw_reaction_add(self, event): 
        if event.message_id != config['watched_message']: 
            return # The reaction is on a different message
        member = event.member

        if member.get_role(config['given_role_t1']) == None and member.get_role(config['given_role_t2']) == None: # If they don't already have the role, or the t2 version...
            #role = self.guild.get_role(config['given_role_t1'])
            # await self.debug_message("added role to " + member.display_name)
            #await member.add_roles(role) # ...give it to them
            await self.grant_role(member, config['given_role_t1'])

    async def on_ready(self):
        self.guild = self.get_guild(config['guild_id'])
        verify_command = app_commands.ContextMenu(name='Verify User', callback=self.verify)
        self.tree.add_command(verify_command, guild=self.guild)
        self.tree.copy_global_to(guild=self.guild)
        await self.tree.sync(guild=self.guild)
        channel = self.get_channel(config['debug_channel'])
        version_str = 'v'+VERSION
        if DEBUG:
            version_str += ' [DEBUG]'
        await channel.send(f"Booting ErasureOS {version_str}...\n\nConfig:```json\n{json.dumps(config, indent=2)}```")
        
    @discord.ext.tasks.loop(minutes=1)
    async def check_tier2(self):
        # Get all the users with the tier1 role...
        t1_members = self.guild.get_role(config['given_role_t1']).members
        for member in t1_members:
            if datetime.now(member.joined_at.tzinfo) - timedelta(minutes=config['automatic_role_t2_waittime']) > member.joined_at:
                self.verify_user(self, member)

    @check_tier2.before_loop
    async def before_check_tier2(self):
        await self.wait_until_ready()

    async def verify_user(self, member):
        if (await self.grant_role(member, config['given_role_t2'])):
            return await self.remove_role(member, config['given_role_t1'])
        else:
            return False
        
    async def grant_role(self, member, role_id):
        try:
            await member.add_roles(self.guild.get_role(role_id))
        except Exception as ex:
            await self.debug_message(f"<@409758119145635851> failed to grant role {role_id} to {member.display_name}:\n {ex}")
            return False
        return True
    
    async def remove_role(self, member, role_id):
        try:
            await member.remove_roles(self.guild.get_role(role_id))
        except Exception as ex:
            await self.debug_message(f"<@409758119145635851> failed to remove role {role_id} from {member.display_name}:\n {ex}")
            return False
        return True

    async def setup_hook(self) -> None:
        if config['automatic_role_t2']:
            self.check_tier2.start()

    async def verify(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.permissions.manage_roles:
            await interaction.response.send_message(f"<:disgrayced:1150932813978280057> Permission denied.", ephemeral=True)
            return
        if member.get_role(config['given_role_t2']) != None:
            await interaction.response.send_message(f"<:i_know_what_you_are:1150490164909592587> {member.display_name} is already verified!", ephemeral=True)
            return
        else:
            if await self.verify_user(member):
                await interaction.response.send_message(f"<:yeslord:1172009353981734962> Verified {member.display_name} successfully.", ephemeral=True)
            else:
                await interaction.response.send_message(f"<:salamislices:1150434195538182285> Failed to verify {member.display_name}, see log for details.", ephemeral=True)

client = ErasureClient(intents=intents)

def main():
    global config, VERSION

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
