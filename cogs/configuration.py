import discord
from discord import app_commands
from discord.ext import commands

from database.db import (
    add_staff_role,
    get_guild_settings,
    get_staff_roles,
    remove_staff_role,
    set_guild_setting,
)


@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
class Configuration(
    commands.GroupCog,
    group_name="config",
    group_description="A bot szerverenkénti beállításainak kezelése.",
):
    """
    Discordon belüli konfigurációs rendszer.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        """
        A /config parancsokat csak olyan tag használhatja,
        akinek van Szerver kezelése jogosultsága.
        """

        if not interaction.permissions.manage_guild:
            raise app_commands.MissingPermissions(
                ["manage_guild"]
            )

        return True

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

    # --------------------------------------------------
    # /config staff-add
    # --------------------------------------------------

    @app_commands.command(
        name="staff-add",
        description="Staffként kezelt rang hozzáadása.",
    )
    @app_commands.describe(
        role="A rang, amelyet staffrangként szeretnél kezelni.",
    )
    async def staff_add(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        if role.is_default():
            await interaction.response.send_message(
                "❌ Az @everyone rang nem állítható be staffrangként.",
                ephemeral=True,
            )
            return

        if role.managed:
            await interaction.response.send_message(
                "❌ Botokhoz vagy integrációkhoz tartozó "
                "kezelt rang nem állítható be.",
                ephemeral=True,
            )
            return

        added = await add_staff_role(
            guild_id=guild.id,
            role_id=role.id,
        )

        if not added:
            await interaction.response.send_message(
                f"ℹ️ A(z) {role.mention} rang már staffrangként van beállítva.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        await interaction.response.send_message(
            f"✅ A(z) {role.mention} rang hozzáadva a staffrangokhoz.",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # /config staff-remove
    # --------------------------------------------------

    @app_commands.command(
        name="staff-remove",
        description="Staffként kezelt rang eltávolítása.",
    )
    @app_commands.describe(
        role="Az eltávolítandó staffrang.",
    )
    async def staff_remove(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        removed = await remove_staff_role(
            guild_id=guild.id,
            role_id=role.id,
        )

        if not removed:
            await interaction.response.send_message(
                f"ℹ️ A(z) {role.mention} rang nincs staffrangként beállítva.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        await interaction.response.send_message(
            f"✅ A(z) {role.mention} rang eltávolítva a staffrangok közül.",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # /config staff-list
    # --------------------------------------------------

    @app_commands.command(
        name="staff-list",
        description="Megmutatja a beállított staffrangokat.",
    )
    async def staff_list(
        self,
        interaction: discord.Interaction,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        role_ids = await get_staff_roles(guild.id)

        if not role_ids:
            await interaction.response.send_message(
                "ℹ️ Jelenleg nincs staffrang beállítva.",
                ephemeral=True,
            )
            return

        role_lines: list[str] = []

        for role_id in role_ids:
            role = guild.get_role(role_id)

            if role is None:
                role_lines.append(
                    f"• Törölt vagy nem elérhető rang (`{role_id}`)"
                )
            else:
                role_lines.append(
                    f"• {role.mention}"
                )

        embed = discord.Embed(
            title="🛡️ Beállított staffrangok",
            description="\n".join(role_lines),
            color=discord.Color.blue(),
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # /config log-channel
    # --------------------------------------------------

    @app_commands.command(
        name="log-channel",
        description="Beállítja a bot naplózási csatornáját.",
    )
    @app_commands.describe(
        channel="A csatorna, ahová a bot naplózni fog.",
    )
    async def log_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        bot_member = guild.me

        if bot_member is None:
            await interaction.response.send_message(
                "❌ Nem sikerült lekérni a bot szervertagságát.",
                ephemeral=True,
            )
            return

        permissions = channel.permissions_for(bot_member)

        missing_permissions: list[str] = []

        if not permissions.view_channel:
            missing_permissions.append("Csatorna megtekintése")

        if not permissions.send_messages:
            missing_permissions.append("Üzenetek küldése")

        if not permissions.embed_links:
            missing_permissions.append("Hivatkozások beágyazása")

        if missing_permissions:
            formatted_permissions = "\n".join(
                f"• {permission}"
                for permission in missing_permissions
            )

            await interaction.response.send_message(
                "❌ A botnak nincs meg minden szükséges "
                f"jogosultsága a(z) {channel.mention} csatornában:\n"
                f"{formatted_permissions}",
                ephemeral=True,
            )
            return

        await set_guild_setting(
            guild_id=guild.id,
            setting_key="log_channel_id",
            setting_value=str(channel.id),
        )

        await interaction.response.send_message(
            f"✅ A naplózási csatorna beállítva: {channel.mention}",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # /config log-disable
    # --------------------------------------------------

    @app_commands.command(
        name="log-disable",
        description="Kikapcsolja a bot naplózási csatornáját.",
    )
    async def log_disable(
        self,
        interaction: discord.Interaction,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        await set_guild_setting(
            guild_id=guild.id,
            setting_key="log_channel_id",
            setting_value=None,
        )

        await interaction.response.send_message(
            "✅ A naplózási csatorna kikapcsolva.",
            ephemeral=True,
        )

    # --------------------------------------------------
    # /config show
    # --------------------------------------------------

    @app_commands.command(
        name="show",
        description="Megmutatja a bot jelenlegi szerverbeállításait.",
    )
    async def show(
        self,
        interaction: discord.Interaction,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        settings = await get_guild_settings(guild.id)
        staff_role_ids = await get_staff_roles(guild.id)

        log_channel_text = "Nincs beállítva"

        log_channel_id = settings.get("log_channel_id")

        if log_channel_id is not None:
            try:
                channel = guild.get_channel(
                    int(log_channel_id)
                )

                if channel is None:
                    log_channel_text = (
                        f"Törölt vagy nem elérhető csatorna "
                        f"(`{log_channel_id}`)"
                    )
                else:
                    log_channel_text = channel.mention

            except ValueError:
                log_channel_text = "Hibás csatornaazonosító"

        staff_role_lines: list[str] = []

        for role_id in staff_role_ids:
            role = guild.get_role(role_id)

            if role is None:
                staff_role_lines.append(
                    f"Törölt rang (`{role_id}`)"
                )
            else:
                staff_role_lines.append(
                    role.mention
                )

        if staff_role_lines:
            staff_roles_text = "\n".join(
                f"• {role_text}"
                for role_text in staff_role_lines
            )
        else:
            staff_roles_text = "Nincs beállítva"

        embed = discord.Embed(
            title="⚙️ Szerverbeállítások",
            description=(
                "Itt láthatók a bot jelenlegi "
                "szerverenkénti beállításai."
            ),
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="🛡️ Staffrangok",
            value=staff_roles_text,
            inline=False,
        )

        embed.add_field(
            name="📜 Naplózási csatorna",
            value=log_channel_text,
            inline=False,
        )

        embed.set_footer(
            text=f"Szerver: {guild.name}"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # Hibakezelés
    # --------------------------------------------------

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(
            error,
            app_commands.MissingPermissions,
        ):
            await self.send_error(
                interaction,
                "❌ A konfiguráció kezeléséhez "
                "Szerver kezelése jogosultság szükséges.",
            )
            return

        original_error = getattr(
            error,
            "original",
            error,
        )

        print(
            "Konfigurációs rendszer hibája:",
            repr(original_error),
        )

        await self.send_error(
            interaction,
            "❌ Hiba történt a beállítás mentése közben.",
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Configuration(bot))