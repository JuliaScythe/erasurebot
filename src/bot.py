import copy
import json
import time
from datetime import datetime, timedelta
from io import BufferedReader
from itertools import count
from typing import Literal, Optional

import discord
from discord import (
    Client,
    Interaction,
    Member,
    Message,
    RawReactionActionEvent,
    TextChannel,
    Thread,
    app_commands,
)
from discord.abc import Messageable
from discord.ext import tasks

from src import parse_ansi, roomfetch
from src.config import EnvironmentConfig
from src.count import Count


def disos_header():
    return f"DIS OS REPORT {datetime.now().day:02}/{datetime.now().month:02}/11{datetime.now().year}"


class ErasureClient(Client):
    def __init__(
        self,
        config: EnvironmentConfig,
        count: Count,
        version: str,
        debug=False,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.tree = discord.app_commands.CommandTree(self)
        self.automute = False
        self.automute_channel = None
        self.config = config
        self.count = count
        self.version = version
        self.debug = debug

    def save_count(self):
        try:
            with open("grube.json", "w") as f:
                json.dump(count, f)
        except Exception:
            pass

    async def debug_message(self, message):
        channel = self.get_channel(self.config.debug_channel)
        if not isinstance(channel, Messageable):
            return

        await channel.send(message)

    # We can't be guaranteed that the message we want to listen on will be in the cache, so we need to use the raw reaction add here.
    async def on_raw_reaction_add(self, event: RawReactionActionEvent):
        if event.message_id not in {
            self.config.watched_message,
            self.config.event_role_message,
            self.config.afd_react_message,
        }:
            return  # The reaction is on a different message

        member = event.member

        if member is None:
            return

        if event.message_id == self.config.watched_message:
            if (
                member.get_role(self.config.given_role_t1) is None
                and member.get_role(self.config.given_role_t2) is None
            ):  # If they don't already have the role, or the t2 version...
                # role = self.guild.get_role(config['given_role_t1'])
                # await self.debug_message("added role to " + member.display_name)
                # await member.add_roles(role) # ...give it to them
                await self.grant_role(member, self.config.given_role_t1)
        elif event.message_id == self.config.event_role_message:
            if member.get_role(self.config.event_role) is None:
                await self.grant_role(member, self.config.event_role)
        elif event.message_id == self.config.afd_react_message:
            emoji = event.emoji
            if emoji.name == "🟢":
                if member.get_role(self.config.afd_green_role) is None:
                    await self.grant_role(member, self.config.afd_green_role)
            elif emoji.name == "🟠":
                if member.get_role(self.config.afd_orange_role) is None:
                    await self.grant_role(member, self.config.afd_orange_role)

    async def on_raw_reaction_remove(self, event):
        if event.message_id not in {
            self.config.event_role_message,
            self.config.afd_react_message,
        }:
            return

        guild = self.guild

        if guild is None:
            return

        member = await guild.fetch_member(event.user_id)

        if event.message_id == self.config.event_role_message:
            if member.get_role(self.config.event_role) is not None:
                await self.remove_role(member, self.config.event_role)
        elif event.message_id == self.config.afd_react_message:
            emoji = event.emoji
            if emoji.name == "🟢":
                if member.get_role(self.config.afd_green_role) is not None:
                    await self.remove_role(member, self.config.afd_green_role)
            elif emoji.name == "🟠":
                if member.get_role(self.config.afd_orange_role) is not None:
                    await self.remove_role(member, self.config.afd_orange_role)

    async def on_message(self, event: Message):
        if event.author == self.user:
            return
        if event.channel.id == self.automute_channel:
            if not self.automute:
                return
            try:
                if isinstance(event, Member):
                    await event.author.timeout(timedelta(hours=1))
                await event.add_reaction("🌩")
            except discord.errors.Forbidden as e:
                print(e)
        if event.channel.id == self.config.grube_channel:
            if len(event.stickers) == 1:
                sticker = event.stickers[0]
                if sticker.name == self.config.sticker_names["positive"]:
                    self.count.positive += 1
                elif sticker.name == self.config.sticker_names["negative"]:
                    self.count.negative += 1
                else:
                    self.count.exceptions += 1
            self.save_count()

    async def on_ready(self):
        self.guild = self.get_guild(self.config.guild_id)

        verify_command = app_commands.ContextMenu(
            name="Verify User", callback=self.verify
        )
        self.tree.add_command(verify_command, guild=self.guild)

        automute_command = app_commands.Command(
            name="enable_automute",
            description="Enables automute in this channel",
            callback=self.enable_automute,
        )
        self.tree.add_command(automute_command, guild=self.guild)

        remove_automute_command = app_commands.Command(
            name="disable_automute",
            description="Disables automute in this channel",
            callback=self.disable_automute,
        )
        self.tree.add_command(remove_automute_command, guild=self.guild)

        grube_command = app_commands.Command(
            name="grube_stats",
            description="THE TOWER STANDS TALL",
            callback=self.grube_stats,
        )
        self.tree.add_command(grube_command, guild=self.guild)

        reset_grube_command = app_commands.Command(
            name="reset_stats",
            description="THE TOWER SHALL FALL",
            callback=self.reset_stats,
        )
        self.tree.add_command(reset_grube_command, guild=self.guild)

        stats_override_command = app_commands.Command(
            name="override_stats",
            description="THE TOWER SHALL Change?",
            callback=self.stats_override,
        )
        self.tree.add_command(stats_override_command, guild=self.guild)

        echo_command = app_commands.Command(
            name="echo",
            description="Interpret the markup in this message as colours and relay it back, for testing purposes",
            callback=self.echo,
        )
        self.tree.add_command(echo_command, guild=self.guild)

        dump_command = app_commands.Command(
            name="dump",
            description="Dump all messages between two message IDs, to a file on the server (ask juli to retrieve the file)",
            callback=self.dump_command,
        )
        self.tree.add_command(dump_command, guild=self.guild)

        proxy_command = app_commands.Command(
            name="proxy",
            description="proxy a message through erasurebot",
            callback=self.proxy,
        )
        self.tree.add_command(proxy_command, guild=self.guild)

        pluralfreeze_command = app_commands.Command(
            name="pk_freeze",
            description="Prevent PluralKit from viewing channels.",
            callback=self.pk_freeze,
        )
        self.tree.add_command(pluralfreeze_command, guild=self.guild)

        pluralunfreeze_command = app_commands.Command(
            name="pk_unfreeze",
            description="Grant PluralKit channel viewing perms.",
            callback=self.pk_unfreeze,
        )
        self.tree.add_command(pluralunfreeze_command, guild=self.guild)

        floor_command = app_commands.Command(
            name="floor",
            description="fetch an image of a void stranger floor",
            callback=self.floor,
        )
        self.tree.add_command(floor_command, guild=self.guild)

        slowmode_command = app_commands.Command(
            name="slowmode",
            description="set slowmode in the current channel/thread",
            callback=self.slowmode,
        )
        self.tree.add_command(slowmode_command, guild=self.guild)

        if self.guild is not None:
            self.tree.copy_global_to(guild=self.guild)

        await self.tree.sync(guild=self.guild)
        channel = self.get_channel(self.config.debug_channel)
        if not isinstance(channel, Messageable):
            return

        version_str = "v" + self.version
        if self.debug:
            version_str += " [DEBUG]"

        await channel.send(
            f"Booting ErasureOS {version_str}...\n\nConfig:```json\n{json.dumps(self.config, indent=2)}```"
        )

    async def slowmode(self, interaction: Interaction, amount: int):
        channel = interaction.channel
        if not isinstance(channel, TextChannel):
            return

        if not interaction.permissions.manage_roles:
            await interaction.response.send_message(
                "<:disgrayced:1408465331382652959> Permission denied.", ephemeral=True
            )
            return

        await channel.edit(slowmode_delay=amount)
        await interaction.response.send_message("Done.", ephemeral=True)

    async def enable_automute(self, interaction: Interaction):
        if not interaction.permissions.manage_roles:
            await interaction.response.send_message(
                "<:disgrayced:1408465331382652959> Permission denied.", ephemeral=True
            )
            return
        self.automute = True
        self.automute_channel = interaction.channel_id
        await interaction.response.send_message(":cloud_lightning:")

    async def proxy(self, interaction: Interaction, payload: str):
        channel = interaction.channel
        if not isinstance(channel, Messageable):
            return

        if not (
            interaction.permissions.manage_roles
            or interaction.user.id == self.config.gooey_id
        ):
            await interaction.response.send_message(
                "<:disgrayced:1408465331382652959> Permission denied.", ephemeral=True
            )
            return
        if len(payload) > 4000:
            await interaction.response.send_message(
                f"Message too long, I can't break discord's 4K character limit. (Your message was {len(payload)} characters)",
                ephemeral=True,
            )
            return

        await channel.send(payload.replace("\\n", "\n"))
        await interaction.response.send_message(
            "<:fire2:1341871545517084803>", ephemeral=True
        )

    async def disable_automute(self, interaction: Interaction):
        if not interaction.permissions.manage_roles:
            await interaction.response.send_message(
                "<:disgrayced:1408465331382652959> Permission denied.", ephemeral=True
            )
            return
        self.automute = False
        self.automute_channel = None
        await interaction.response.send_message(":sun:")

    async def grube_stats(
        self, interaction: Interaction, flavour: str = "THE TOWER STANDS TALL"
    ):
        channel = interaction.channel
        if not isinstance(channel, Messageable):
            return

        if not interaction.permissions.manage_roles:
            await interaction.response.send_message(
                "<:disgrayced:1408465331382652959> Permission denied.", ephemeral=True
            )
            return

        log = f"""```ansi
{disos_header()}
RECEIVING GRUBE[{parse_ansi.COLOR_YELLOW}{self.count.resets}{parse_ansi.COLOR_RESET}] DATA...

{parse_ansi.parse_ansi(flavour)}
POSITIVE: {self.count.positive}
NEGATIVE: {self.count.negative}
EXCEPTIONS: {parse_ansi.COLOR_RED}{self.count.exceptions}{parse_ansi.COLOR_RESET}```"""
        await channel.send(log)
        await interaction.response.send_message("Done.", ephemeral=True)
        return

    async def reset_stats(self, interaction: Interaction):
        if not interaction.permissions.manage_roles:
            await interaction.response.send_message(
                "<:disgrayced:1408465331382652959> Permission denied.", ephemeral=True
            )
            return
        emergency_log = f"""```ansi
{disos_header()}
{parse_ansi.COLOR_RED}RESET TRIGGERED{parse_ansi.COLOR_RESET}
COMMENCING EMERGENCY GRUBE BACKUP

POSITIVE: {self.count.positive}
NEGATIVE: {self.count.negative}
EXCEPTIONS: {self.count.exceptions}```"""

        old_resets = self.count.resets
        initial_count = Count()
        self.count = copy.deepcopy(initial_count)
        self.count.resets = old_resets + 1  # another one lost...

        self.save_count()
        await self.debug_message(emergency_log)
        await interaction.response.send_message("Done.", ephemeral=True)

    async def stats_override(
        self,
        interaction: Interaction,
        field: Literal["positive", "negative", "exceptions", "resets"],
        value: int,
    ):
        if not interaction.permissions.manage_roles:
            await interaction.response.send_message(
                "<:disgrayced:1408465331382652959> Permission denied.", ephemeral=True
            )
            return

        self.count = self.count.model_copy(update={field: value})
        self.save_count()

        await interaction.response.send_message("Done.", ephemeral=True)

    async def echo(self, interaction: Interaction, message: str):
        await interaction.response.send_message(
            f"```ansi\n{parse_ansi.parse_ansi(message)}\n```", ephemeral=True
        )

    @tasks.loop(minutes=1)
    async def check_tier2(self):
        # Get all the users with the tier1 role...
        guild = self.guild
        if guild is None:
            return

        role = guild.get_role(self.config.given_role_t1)
        if role is None:
            return

        t1_members = role.members
        for member in t1_members:
            joined_at = member.joined_at
            if joined_at is None:
                return

            if (
                datetime.now(joined_at.tzinfo)
                - timedelta(minutes=self.config.automatic_role_t2_waittime)
                > joined_at
            ):
                await self.verify_user(member)

    @check_tier2.before_loop
    async def before_check_tier2(self):
        await self.wait_until_ready()

    async def verify_user(self, member):
        if await self.grant_role(member, self.config.given_role_t2):
            return await self.remove_role(member, self.config.given_role_t1)
        else:
            return False

    async def grant_role(self, member, role_id):
        guild = self.guild
        if guild is None:
            return

        try:
            await member.add_roles(guild.get_role(role_id))
        except Exception as ex:
            await self.debug_message(
                f"<@409758119145635851> failed to grant role {role_id} to {member.display_name}:\n {ex}"
            )
            return False
        return True

    async def remove_role(self, member, role_id):
        guild = self.guild
        if guild is None:
            return

        try:
            await member.remove_roles(guild.get_role(role_id))
        except Exception as ex:
            await self.debug_message(
                f"<@409758119145635851> failed to remove role {role_id} from {member.display_name}:\n {ex}"
            )
            return False
        return True

    async def setup_hook(self) -> None:
        if self.config.automatic_role_t2:
            self.check_tier2.start()

    async def verify(self, interaction: Interaction, member: Member):
        if not interaction.permissions.manage_roles:
            await interaction.response.send_message(
                "<:disgrayced:1408465331382652959> Permission denied.", ephemeral=True
            )
            return
        if member.get_role(self.config.given_role_t2) is not None:
            await interaction.response.send_message(
                f"<:i_know_what_you_are:1150490164909592587> {member.display_name} is already verified!",
                ephemeral=True,
            )
            return
        else:
            if await self.verify_user(member):
                await interaction.response.send_message(
                    f"<:yeslord:1172009353981734962> Verified {member.display_name} successfully.",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"<:salamislices:1150434195538182285> Failed to verify {member.display_name}, see log for details.",
                    ephemeral=True,
                )

    async def dump_command(self, interaction: Interaction, start: str, end: str):
        if not interaction.permissions.manage_roles:
            await interaction.response.send_message(
                "<:disgrayced:1408465331382652959> Permission denied.", ephemeral=True
            )
            return

        # first, get the channel the messages are in (i.e. the channel the command was sent from)
        channel = interaction.channel
        if not isinstance(channel, Messageable):
            return

        start_msg = await channel.fetch_message(int(start))
        end_msg = await channel.fetch_message(int(end))

        await interaction.response.send_message(
            f"Recording history... (from {start_msg.jump_url} to {end_msg.jump_url}). This may take some time."
        )
        filename = str(int(time.time()))
        counter = 0
        last_msg = start_msg
        with open(filename, mode="w") as f:
            done = False
            while not done:
                done = True
                async for msg in channel.history(after=last_msg, before=end_msg):
                    done = False
                    counter += 1
                    if counter % 500 == 0:
                        await channel.send(f"{counter}. {msg.jump_url}")
                    json.dump(
                        {
                            "content": msg.content,
                            "author": msg.author.display_name,
                            "author_username": msg.author.name,
                            "author_colour": msg.author.colour.to_rgb(),
                            "time": time.mktime(msg.created_at.timetuple()),
                            "attachments": str(msg.attachments),
                        },
                        f,
                    )
                    f.write("\n")
                    last_msg = msg
        await channel.send("Done.")

    async def pk_freeze(self, interaction: Interaction):
        guild = self.guild
        channel = interaction.channel

        if not isinstance(channel, Messageable):
            return

        if guild is None:
            return

        pluralkit = await guild.fetch_member(self.config.pluralkit_member or 0)
        await self.remove_role(pluralkit, self.config.given_role_t2)  # remove Verified

        role = guild.get_role(self.config.pluralkit_role or 0)

        if role is None:
            return

        perms = role.permissions
        perms.view_channel = False
        await role.edit(permissions=perms)

        await channel.send("❄️ PluralKit frozen.")

    async def pk_unfreeze(self, interaction: Interaction):
        guild = self.guild
        channel = interaction.channel

        if not isinstance(channel, Messageable):
            return

        if guild is None:
            return

        pluralkit = await guild.fetch_member(self.config.pluralkit_member or 0)
        await self.grant_role(pluralkit, self.config.given_role_t2)  # add Verified

        role = guild.get_role(self.config.pluralkit_role or 0)

        if role is None:
            return

        perms = role.permissions
        perms.view_channel = True
        await role.edit(permissions=perms)

        await channel.send("🔥 PluralKit revived.")

    async def floor(self, interaction: Interaction, floor: str, whisper: bool = False):
        # WARNING: THIS COMMAND IS USABLE BY ANYONE
        channel = interaction.channel
        if not isinstance(channel, TextChannel):
            return

        if isinstance(channel, Thread):
            channel = channel.parent  # threads inherit spoiler tiers of their parents
        img: Optional[BufferedReader] = None
        spoiler_tier: int = 0
        if channel.name in self.config.spoiler_tiers_map:
            spoiler_tier = self.config.spoiler_tiers_map[channel.name]
            img = roomfetch.get_floor_image(floor, spoiler_tier)
        if img is None:
            await interaction.response.send_message(
                "<:vsNo:1277638286336200788> floor not found or permitted in this channel / spoiler level",
                ephemeral=True,
            )
        else:
            # 's' check for SX levels which are always spoilered
            prefix = (
                "SPOILER_" if floor[0].lower() == "s" or spoiler_tier != 5 else ""
            )  # for some reason this is how discord decides if an image has a spoiler tag or not
            await interaction.response.send_message(
                roomfetch.normalise_room_name(floor),
                file=discord.File(img, prefix + floor + ".png"),
                ephemeral=whisper,
            )
