from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from database.db import (
    add_staff_ping_exempt_channel,
    add_staff_ping_exempt_role,
    get_bot_manager_roles,
    get_guild_setting,
    get_staff_ping_exempt_channels,
    get_staff_ping_exempt_roles,
    get_staff_roles,
    remove_staff_ping_exempt_channel,
    remove_staff_ping_exempt_role,
    set_guild_setting,
)

from utils.bot_permissions import (
    is_bot_manager,
    send_manager_denied,
)

from utils.logging_utils import send_log


@app_commands.guild_only()
class StaffPingProtection(
    commands.GroupCog,
    group_name="staffping",
    group_description="A staff megpingelése elleni védelem beállításai.",
):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if await is_bot_manager(interaction):
            return True

        await send_manager_denied(interaction)
        return False

    async def send_error(
        self,
        interaction: discord.Interaction,
        message: str,
    ) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(
                message,
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                message,
                ephemeral=True,
            )

    async def member_is_exempt(
        self,
        member: discord.Member,
    ) -> bool:
        """
        A szervertulajdonos, rendszergazdák, staffok,
        botkezelők és kivételes rangok nem kapnak timeoutot.
        """

        guild = member.guild

        if member.id == guild.owner_id:
            return True

        if member.guild_permissions.administrator:
            return True

        staff_role_ids = set(
            await get_staff_roles(guild.id)
        )

        manager_role_ids = set(
            await get_bot_manager_roles(guild.id)
        )

        exempt_role_ids = set(
            await get_staff_ping_exempt_roles(guild.id)
        )

        protected_role_ids = (
            staff_role_ids
            | manager_role_ids
            | exempt_role_ids
        )

        return any(
            role.id in protected_role_ids
            for role in member.roles
        )

    # --------------------------------------------------
    # /staffping enable
    # --------------------------------------------------

    @app_commands.command(
        name="enable",
        description="Bekapcsolja a staff-ping védelmet.",
    )
    async def enable(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if interaction.guild is None:
            return

        await set_guild_setting(
            guild_id=interaction.guild.id,
            setting_key="staff_ping_enabled",
            setting_value="1",
        )

        current_timeout = await get_guild_setting(
            interaction.guild.id,
            "staff_ping_timeout_minutes",
        )

        if current_timeout is None:
            await set_guild_setting(
                guild_id=interaction.guild.id,
                setting_key="staff_ping_timeout_minutes",
                setting_value="5",
            )

        await interaction.response.send_message(
            "✅ A staff-ping védelem bekapcsolva.",
            ephemeral=True,
        )

    # --------------------------------------------------
    # /staffping disable
    # --------------------------------------------------

    @app_commands.command(
        name="disable",
        description="Kikapcsolja a staff-ping védelmet.",
    )
    async def disable(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if interaction.guild is None:
            return

        await set_guild_setting(
            guild_id=interaction.guild.id,
            setting_key="staff_ping_enabled",
            setting_value="0",
        )

        await interaction.response.send_message(
            "✅ A staff-ping védelem kikapcsolva.",
            ephemeral=True,
        )

    # --------------------------------------------------
    # /staffping timeout
    # --------------------------------------------------

    @app_commands.command(
        name="timeout",
        description="Beállítja a staff-ping miatti timeout hosszát.",
    )
    @app_commands.describe(
        percek="A timeout hossza percben.",
    )
    async def timeout_setting(
        self,
        interaction: discord.Interaction,
        percek: app_commands.Range[int, 1, 40320],
    ) -> None:
        if interaction.guild is None:
            return

        await set_guild_setting(
            guild_id=interaction.guild.id,
            setting_key="staff_ping_timeout_minutes",
            setting_value=str(percek),
        )

        await interaction.response.send_message(
            f"✅ A staff-ping büntetése **{percek} perc** timeout.",
            ephemeral=True,
        )

    # --------------------------------------------------
    # /staffping exempt-role-add
    # --------------------------------------------------

    @app_commands.command(
        name="exempt-role-add",
        description="Rang kivétele a staff-ping büntetés alól.",
    )
    @app_commands.describe(
        role="A kivételes rang.",
    )
    async def exempt_role_add(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        if role.is_default() or role.managed:
            await interaction.response.send_message(
                "❌ Ez a rang nem állítható be kivételként.",
                ephemeral=True,
            )
            return

        added = await add_staff_ping_exempt_role(
            guild.id,
            role.id,
        )

        message = (
            f"✅ A(z) {role.mention} rang kivételként hozzáadva."
            if added
            else f"ℹ️ A(z) {role.mention} rang már kivétel."
        )

        await interaction.response.send_message(
            message,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # /staffping exempt-role-remove
    # --------------------------------------------------

    @app_commands.command(
        name="exempt-role-remove",
        description="Rang eltávolítása a staff-ping kivételek közül.",
    )
    async def exempt_role_remove(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        if interaction.guild is None:
            return

        removed = await remove_staff_ping_exempt_role(
            interaction.guild.id,
            role.id,
        )

        message = (
            f"✅ A(z) {role.mention} rang már nem kivétel."
            if removed
            else f"ℹ️ A(z) {role.mention} rang nem volt kivétel."
        )

        await interaction.response.send_message(
            message,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # /staffping exempt-channel-add
    # --------------------------------------------------

    @app_commands.command(
        name="exempt-channel-add",
        description="Csatorna kivétele a staff-ping védelem alól.",
    )
    async def exempt_channel_add(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        if interaction.guild is None:
            return

        added = await add_staff_ping_exempt_channel(
            interaction.guild.id,
            channel.id,
        )

        message = (
            f"✅ A(z) {channel.mention} csatorna kivételként hozzáadva."
            if added
            else f"ℹ️ A(z) {channel.mention} csatorna már kivétel."
        )

        await interaction.response.send_message(
            message,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # /staffping exempt-channel-remove
    # --------------------------------------------------

    @app_commands.command(
        name="exempt-channel-remove",
        description="Csatorna eltávolítása a kivételek közül.",
    )
    async def exempt_channel_remove(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        if interaction.guild is None:
            return

        removed = await remove_staff_ping_exempt_channel(
            interaction.guild.id,
            channel.id,
        )

        message = (
            f"✅ A(z) {channel.mention} csatorna már nem kivétel."
            if removed
            else f"ℹ️ A(z) {channel.mention} csatorna nem volt kivétel."
        )

        await interaction.response.send_message(
            message,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # /staffping show
    # --------------------------------------------------

    @app_commands.command(
        name="show",
        description="Megmutatja a staff-ping védelem beállításait.",
    )
    async def show(
        self,
        interaction: discord.Interaction,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        enabled = await get_guild_setting(
            guild.id,
            "staff_ping_enabled",
        )

        timeout_text = await get_guild_setting(
            guild.id,
            "staff_ping_timeout_minutes",
        )

        exempt_role_ids = await get_staff_ping_exempt_roles(
            guild.id
        )

        exempt_channel_ids = await get_staff_ping_exempt_channels(
            guild.id
        )

        role_lines: list[str] = []

        for role_id in exempt_role_ids:
            role = guild.get_role(role_id)

            role_lines.append(
                role.mention
                if role is not None
                else f"Törölt rang (`{role_id}`)"
            )

        channel_lines: list[str] = []

        for channel_id in exempt_channel_ids:
            channel = guild.get_channel(channel_id)

            channel_lines.append(
                channel.mention
                if channel is not None
                else f"Törölt csatorna (`{channel_id}`)"
            )

        embed = discord.Embed(
            title="🛡️ Staff-ping védelem",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="Állapot",
            value="Bekapcsolva" if enabled == "1" else "Kikapcsolva",
            inline=True,
        )

        embed.add_field(
            name="Timeout",
            value=f"{timeout_text or '5'} perc",
            inline=True,
        )

        embed.add_field(
            name="Kivételes rangok",
            value=(
                "\n".join(role_lines)
                if role_lines
                else "Nincs külön kivétel"
            ),
            inline=False,
        )

        embed.add_field(
            name="Kivételes csatornák",
            value=(
                "\n".join(channel_lines)
                if channel_lines
                else "Nincs kivétel"
            ),
            inline=False,
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # Üzenetek figyelése
    # --------------------------------------------------

    @commands.Cog.listener()
    async def on_message(
        self,
        message: discord.Message,
    ) -> None:
        guild = message.guild
        author = message.author

        if guild is None:
            return

        if not isinstance(author, discord.Member):
            return

        if author.bot or message.webhook_id is not None:
            return

        enabled = await get_guild_setting(
            guild.id,
            "staff_ping_enabled",
        )

        if enabled != "1":
            return

        exempt_channel_ids = set(
            await get_staff_ping_exempt_channels(guild.id)
        )

        if message.channel.id in exempt_channel_ids:
            return

        if await self.member_is_exempt(author):
            return

        staff_role_ids = set(
            await get_staff_roles(guild.id)
        )

        if not staff_role_ids:
            return

        pinged_staff_members = [
            member
            for member in message.mentions
            if any(
                role.id in staff_role_ids
                for role in member.roles
            )
        ]

        pinged_staff_roles = [
            role
            for role in message.role_mentions
            if role.id in staff_role_ids
        ]

        if not pinged_staff_members and not pinged_staff_roles:
            return

        timeout_text = await get_guild_setting(
            guild.id,
            "staff_ping_timeout_minutes",
        )

        try:
            timeout_minutes = int(timeout_text or "5")
        except ValueError:
            timeout_minutes = 5

        timeout_minutes = max(
            1,
            min(timeout_minutes, 40320),
        )

        bot_member = guild.me

        if bot_member is None:
            return

        failure_reason: str | None = None

        if not bot_member.guild_permissions.moderate_members:
            failure_reason = (
                "A botnak nincs Tagok moderálása jogosultsága."
            )

        elif author.top_role >= bot_member.top_role:
            failure_reason = (
                "A bot rangja nincs a felhasználó rangja fölött."
            )

        if failure_reason is None:
            try:
                await author.timeout(
                    timedelta(minutes=timeout_minutes),
                    reason="Staff indokolatlan megpingelése",
                )

            except discord.Forbidden:
                failure_reason = (
                    "A Discord megtagadta a timeoutot."
                )

            except discord.HTTPException:
                failure_reason = (
                    "Discord API-hiba történt."
                )

        pinged_names = [
            f"{member} (`{member.id}`)"
            for member in pinged_staff_members
        ]

        pinged_names.extend(
            f"@{role.name} (`{role.id}`)"
            for role in pinged_staff_roles
        )

        log_embed = discord.Embed(
            title="🚨 Staff megpingelve",
            color=(
                discord.Color.red()
                if failure_reason is None
                else discord.Color.orange()
            ),
            timestamp=discord.utils.utcnow(),
        )

        log_embed.add_field(
            name="Felhasználó",
            value=f"{author}\n`{author.id}`",
            inline=True,
        )

        log_embed.add_field(
            name="Csatorna",
            value=message.channel.mention,
            inline=True,
        )

        log_embed.add_field(
            name="Megpingelt staff",
            value="\n".join(pinged_names)[:1024],
            inline=False,
        )

        log_embed.add_field(
            name="Eredmény",
            value=(
                f"{timeout_minutes} perc timeout"
                if failure_reason is None
                else failure_reason
            ),
            inline=False,
        )

        log_embed.add_field(
            name="Üzenet",
            value=(
                message.content[:1000]
                if message.content
                else "[Nincs szöveges tartalom]"
            ),
            inline=False,
        )

        await send_log(
            guild=guild,
            embed=log_embed,
        )

        if failure_reason is None:
            try:
                await message.channel.send(
                    (
                        f"⏳ **{author.display_name}** "
                        f"{timeout_minutes} perc timeoutot kapott "
                        "staff indokolatlan megpingelése miatt."
                    ),
                    delete_after=10,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException:
                pass

    # --------------------------------------------------
    # Hibakezelés
    # --------------------------------------------------

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            return

        original_error = getattr(
            error,
            "original",
            error,
        )

        print(
            "Staff-ping rendszer hibája:",
            repr(original_error),
        )

        await self.send_error(
            interaction,
            "❌ Hiba történt a staff-ping beállítása közben.",
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StaffPingProtection(bot))