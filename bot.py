import discord
from discord.ext import tasks
from discord import app_commands

from datetime import datetime, timedelta
import os, json, copy

DEBUG = False
VERSION = -1
config = None

WAITTIME = 1440 # 1 day = 1440 mins

intents = discord.Intents.default()
intents.reactions = True # We want to listen for reactions
intents.members = True
intents.messages = True # Not message_content

initial_count = {'positive': 0, 'negative': 0, 'exceptions': {}}
count = copy.deepcopy(initial_count)
try:
    with open('grube.json', 'r') as f:
        count = json.load(f)
except:
    pass # ignored: file not found or could not be read

class ErasureClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super(ErasureClient, self).__init__(*args, **kwargs)
        self.tree = discord.app_commands.CommandTree(self)
        self.automute = False
        self.automute_channel = None

    def save_count(self):
        try:
            with open('grube.json', 'w') as f:
                json.dump(count, f)
        except:
            pass

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

    async def on_message(self, event):
        if event.author == client.user:
            return
        if event.channel.id == self.automute_channel:
            if not self.automute:
                return
            try:
                await event.author.timeout(timedelta(hours=1))
                await event.add_reaction('🌩')
            except discord.errors.Forbidden as e:
                print(e)
        if event.channel.id == config['grube_channel']:
            if len(event.stickers) == 1:
                sticker = event.stickers[0]
                if sticker.name == config['sticker_names']['positive']:
                    count['positive'] += 1
                elif sticker.name == config['sticker_names']['negative']:
                    count['negative'] += 1
                else:
                    new_val = count['exceptions'].get(sticker.url, 0) + 1
                    count['exceptions'][sticker.url] = new_val
            self.save_count()
    
    async def on_ready(self):
        self.guild = self.get_guild(config['guild_id'])

        verify_command = app_commands.ContextMenu(name='Verify User', callback=self.verify)
        self.tree.add_command(verify_command, guild=self.guild)

        automute_command = app_commands.Command(name='enable_automute', description="Enables automute in this channel", callback=self.enable_automute)
        self.tree.add_command(automute_command, guild=self.guild)

        remove_automute_command = app_commands.Command(name='disable_automute', description="Disables automute in this channel", callback=self.disable_automute)
        self.tree.add_command(remove_automute_command, guild=self.guild)

        grube_command = app_commands.Command(name='grube_stats', description="THE TOWER STANDS TALL", callback=self.grube_stats)
        self.tree.add_command(grube_command, guild=self.guild)

        reset_grube_command = app_commands.Command(name='reset_stats', description="THE TOWER SHALL FALL", callback=self.reset_stats)
        self.tree.add_command(reset_grube_command, guild=self.guild)

        self.tree.copy_global_to(guild=self.guild)
        await self.tree.sync(guild=self.guild)
        channel = self.get_channel(config['debug_channel'])
        version_str = 'v'+VERSION
        if DEBUG:
            version_str += ' [DEBUG]'
        await channel.send(f"Booting ErasureOS {version_str}...\n\nConfig:```json\n{json.dumps(config, indent=2)}```")
        
    async def enable_automute(self, interaction: discord.Interaction):
        if not interaction.permissions.manage_roles:
            await interaction.response.send_message(f"<:disgrayced:1150932813978280057> Permission denied.", ephemeral=True)
            return
        self.automute = True
        self.automute_channel = interaction.channel_id
        await interaction.response.send_message(":cloud_lightning:")

    async def disable_automute(self, interaction: discord.Interaction):
        if not interaction.permissions.manage_roles:
            await interaction.response.send_message(f"<:disgrayced:1150932813978280057> Permission denied.", ephemeral=True)
            return
        self.automute = False
        self.automute_channel = None
        await interaction.response.send_message(":sun:")
    
    async def grube_stats(self, interaction: discord.Interaction, flavour: str="THE TOWER STANDS TALL"):
        if not interaction.permissions.manage_roles:
            await interaction.response.send_message(f"<:disgrayced:1150932813978280057> Permission denied.", ephemeral=True)
            return
        log = f"""```
DIS OS REPORT {datetime.now().day:02}/{datetime.now().month:02}/10{datetime.now().year}
RECIEVING GRUBE DATA...

{flavour}
POSITIVE: {count['positive']}
NEGATIVE: {count['negative']}
EXCEPTIONS: {sum(count['exceptions'].values())}```"""
        await interaction.channel.send(log)
        await interaction.response.send_message("Done.", ephemeral=True)
        return
    
    async def reset_stats(self, interaction: discord.Interaction):
        if not interaction.permissions.manage_roles:
            await interaction.response.send_message(f"<:disgrayced:1150932813978280057> Permission denied.", ephemeral=True)
            return
        global count
        count = copy.deepcopy(initial_count)
        self.save_count()
        await interaction.response.send_message("Done.", ephemeral=True)

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
