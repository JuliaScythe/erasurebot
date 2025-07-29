import time
import discord
from discord.ext import tasks
from discord import app_commands

from datetime import datetime, timedelta
import os, json, copy, socket
from typing import Literal, Optional, BinaryIO

import parse_ansi
import roomfetch


if socket.gethostname() == "erasurebot":
    DEBUG = False
else:
    DEBUG = True

VERSION = -1
config = None

WAITTIME = 1440 # 1 day = 1440 mins

intents = discord.Intents.default()
intents.reactions = True # We want to listen for reactions
intents.members = True
intents.messages = True # Not message_content

initial_count = {'positive': 0, 'negative': 0, 'exceptions': 0, 'resets': 0}
count = copy.deepcopy(initial_count)

PASSWORDS = {1234} # TODO change me to the real password :3


try:
    with open('grube.json', 'r') as f:
        count = json.load(f)
except:
    pass # ignored: file not found or could not be read

def disos_header():
    return f"DIS OS REPORT {datetime.now().day:02}/{datetime.now().month:02}/11{datetime.now().year}"

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
        if event.message_id not in {config['watched_message'], config['event_role_message'], config['afd_react_message']}: 
            return # The reaction is on a different message
        member = event.member

        if event.message_id == config['watched_message']:
            if member.get_role(config['given_role_t1']) == None and member.get_role(config['given_role_t2']) == None: # If they don't already have the role, or the t2 version...
                #role = self.guild.get_role(config['given_role_t1'])
                # await self.debug_message("added role to " + member.display_name)
                #await member.add_roles(role) # ...give it to them
                await self.grant_role(member, config['given_role_t1'])
        elif event.message_id == config['event_role_message']:
            if member.get_role(config['event_role']) == None:
                await self.grant_role(member, config['event_role'])
        elif event.message_id == config['afd_react_message']:
            emoji = event.emoji
            if emoji.name == '🟢':
                if member.get_role(config['afd_green_role']) == None:
                    await self.grant_role(member, config['afd_green_role'])
            elif emoji.name == '🟠':
                if member.get_role(config['afd_orange_role']) == None:
                    await self.grant_role(member, config['afd_orange_role'])


    async def on_raw_reaction_remove(self, event):
        if event.message_id not in {config['event_role_message'], config['afd_react_message']}: 
            return
        member = await self.guild.fetch_member(event.user_id)

        if event.message_id == config['event_role_message']:
            if member.get_role(config['event_role']) != None:
                await self.remove_role(member, config['event_role'])
        elif event.message_id == config['afd_react_message']:
            emoji = event.emoji
            if emoji.name == '🟢':
                if member.get_role(config['afd_green_role']) != None:
                    await self.remove_role(member, config['afd_green_role'])
            elif emoji.name == '🟠':
                if member.get_role(config['afd_orange_role']) != None:
                    await self.remove_role(member, config['afd_orange_role'])


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
                    count['exceptions'] += 1
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

        stats_override_command = app_commands.Command(name='override_stats', description="THE TOWER SHALL Change?", callback=self.stats_override)
        self.tree.add_command(stats_override_command, guild=self.guild)

        echo_command = app_commands.Command(name='echo', description='Interpret the markup in this message as colours and relay it back, for testing purposes', callback=self.echo)
        self.tree.add_command(echo_command, guild=self.guild)

        dump_command = app_commands.Command(name='dump', description='Dump all messages between two message IDs, to a file on the server (ask juli to retrieve the file)', callback=self.dump_command)
        self.tree.add_command(dump_command, guild=self.guild)

        proxy_command = app_commands.Command(name='proxy', description="proxy a message through erasurebot", callback=self.proxy)
        self.tree.add_command(proxy_command, guild=self.guild)


        pluralfreeze_command = app_commands.Command(name='pk_freeze', description="Prevent PluralKit from viewing channels.", callback=self.pk_freeze)
        self.tree.add_command(pluralfreeze_command, guild=self.guild)

        pluralunfreeze_command = app_commands.Command(name='pk_unfreeze', description="Grant PluralKit channel viewing perms.", callback=self.pk_unfreeze)
        self.tree.add_command(pluralunfreeze_command, guild=self.guild)

        floor_command = app_commands.Command(name="floor", description="fetch an image of a void stranger floor", callback=self.floor)
        self.tree.add_command(floor_command, guild=self.guild)


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
    
    async def proxy(self, interaction: discord.Interaction, payload: str):
        if not interaction.permissions.manage_roles:
            await interaction.response.send_message(f"<:disgrayced:1150932813978280057> Permission denied.", ephemeral=True)
            return
        if len(payload) > 4000:
            await interaction.response.send_message(f"Message too long, I can't break discord's 4K character limit. (Your message was {len(payload)} characters)", ephemeral=True)
            return

        await interaction.channel.send(payload.replace("\\n","\n"))
        await interaction.response.send_message("<:fire2:1341871545517084803>", ephemeral=True)

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
        log = f"""```ansi
{disos_header()}
RECEIVING GRUBE[{parse_ansi.COLOR_YELLOW}{count['resets']}{parse_ansi.COLOR_RESET}] DATA...

{parse_ansi.parse_ansi(flavour)}
POSITIVE: {count['positive']}
NEGATIVE: {count['negative']}
EXCEPTIONS: {parse_ansi.COLOR_RED}{count['exceptions']}{parse_ansi.COLOR_RESET}```"""
        await interaction.channel.send(log)
        await interaction.response.send_message("Done.", ephemeral=True)
        return
    
    async def reset_stats(self, interaction: discord.Interaction):
        if not interaction.permissions.manage_roles:
            await interaction.response.send_message(f"<:disgrayced:1150932813978280057> Permission denied.", ephemeral=True)
            return
        global count
        emergency_log = f"""```ansi
{disos_header()}
{parse_ansi.COLOR_RED}RESET TRIGGERED{parse_ansi.COLOR_RESET}
COMMENCING EMERGENCY GRUBE BACKUP

POSITIVE: {count['positive']}
NEGATIVE: {count['negative']}
EXCEPTIONS: {count['exceptions']}```"""
        
        old_resets = count['resets']
        count = copy.deepcopy(initial_count)
        count['resets'] = old_resets + 1  # another one lost...

        self.save_count()
        await self.debug_message(emergency_log)
        await interaction.response.send_message("Done.", ephemeral=True)

    async def stats_override(self, interaction: discord.Interaction, field: Literal["positive", "negative", "exceptions", "resets"], value: int):
        if not interaction.permissions.manage_roles:
            await interaction.response.send_message(f"<:disgrayced:1150932813978280057> Permission denied.", ephemeral=True)
            return
        count[field] = value
        self.save_count()
        await interaction.response.send_message("Done.", ephemeral=True)

    async def echo(self, interaction: discord.Integration, message: str):
        await interaction.response.send_message(f"```ansi\n{parse_ansi.parse_ansi(message)}\n```", ephemeral=True)

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
    
    async def dump_command(self, interaction: discord.Interaction, start: str, end: str):
        if not interaction.permissions.manage_roles:
            await interaction.response.send_message(f"<:disgrayced:1150932813978280057> Permission denied.", ephemeral=True)
            return

        # first, get the channel the messages are in (i.e. the channel the command was sent from)
        channel = interaction.channel
        start_msg = await channel.fetch_message(int(start))
        end_msg = await channel.fetch_message(int(end))
        end_stamp = end_msg.created_at

        await interaction.response.send_message(f"Recording history... (from {start_msg.jump_url} to {end_msg.jump_url}). This may take some time.")
        filename = str(int(time.time()))
        counter = 0
        last_msg = start_msg
        with open(filename, mode='w') as f:
            done = False
            while( not done):
                done = True
                async for msg in channel.history(after=last_msg, before=end_msg):
                    done = False
                    counter += 1
                    if counter % 500 == 0:
                        await channel.send(f"{counter}. {msg.jump_url}")
                    json.dump({
                        "content": msg.content,
                        "author": msg.author.display_name,
                        "author_username": msg.author.name,
                        "author_colour": msg.author.colour.to_rgb(),
                        "time": time.mktime(msg.created_at.timetuple()),
                        "attachments": str(msg.attachments)
                    }, f)
                    f.write("\n")
                    last_msg = msg
        await channel.send("Done.")

    async def pk_freeze(self, interaction: discord.Interaction):
        pluralkit = await self.guild.fetch_member(config['pluralkit_member'])  
        await self.remove_role(pluralkit, config['given_role_t2']) # remove Verified

        perms = self.guild.get_role(config['pluralkit_role']).permissions 
        perms.view_channel = False
        await self.guild.get_role(config['pluralkit_role']).edit(permissions=perms)

        await interaction.channel.send("❄️ PluralKit frozen.")

    async def pk_unfreeze(self, interaction: discord.Interaction):
        pluralkit = await self.guild.fetch_member(config['pluralkit_member'])  
        await self.grant_role(pluralkit, config['given_role_t2']) # add Verified
        
        perms = self.guild.get_role(config['pluralkit_role']).permissions
        perms.view_channel = True
        await self.guild.get_role(config['pluralkit_role']).edit(permissions=perms)

        await interaction.channel.send("🔥 PluralKit revived.")

    async def floor(self, interaction: discord.Interaction, floor: str):
        # WARNING: THIS COMMAND IS USABLE BY ANYONE
        channel = interaction.channel
        if isinstance(channel, discord.Thread):
            channel = channel.parent # threads inherit spoiler tiers of their parents
        img: Optional[BytesIO] = None
        spoiler_tier : int = 0
        if channel.name in config["spoiler_tiers_map"]:
            spoiler_tier = config["spoiler_tiers_map"][channel.name]
            img = roomfetch.get_floor_image(floor, spoiler_tier)
        if img is None:
            await interaction.response.send_message("<:vsNo:1277638286336200788> floor not found or permitted in this channel / spoiler level", ephemeral=True)
        else:
            prefix = "SPOILER_" if spoiler_tier != 5 else "" # for some reason this is how discord decides if an image has a spoiler tag or not
            await interaction.response.send_message(roomfetch.normalise_room_name(floor), file=discord.File(img, prefix + floor + ".png"))
            


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
