import discord
from discord import app_commands
from discord.ext import commands

from database.db import (
    add_bot_manager_role,
    add_staff_role,
    get_bot_manager_roles,
    get_guild_settings,
    get_staff_roles,
    remove_bot_manager_role,
    remove_staff_role,
    set_guild_setting,
)
from utils.bot_permissions import (
    is_bot_manager,
    is_owner_or_administrator,
    send_manager_denied,
)


@app_commands.guild_only()
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
        Minden /config alparancs előtt lefut.
        """

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
    # /config welcome-channel
    # --------------------------------------------------

    @app_commands.command(
        name="welcome-channel",
        description="Beállítja az üdvözlőüzenetek csatornáját.",
    )
    @app_commands.describe(
        channel="A csatorna, ahová az üdvözlőüzenetek kerülnek.",
    )
    async def welcome_channel(
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
                "❌ Nem sikerült lekérni a botot.",
                ephemeral=True,
            )
            return

        permissions = channel.permissions_for(bot_member)

        if not (
            permissions.view_channel
            and permissions.send_messages
            and permissions.embed_links
        ):
            await interaction.response.send_message(
                "❌ A botnak nincs jogosultsága üzenetet "
                f"küldeni a(z) {channel.mention} csatornába.",
                ephemeral=True,
            )
            return

        await set_guild_setting(
            guild_id=guild.id,
            setting_key="welcome_channel_id",
            setting_value=str(channel.id),
        )

        await interaction.response.send_message(
            f"✅ Üdvözlőcsatorna beállítva: {channel.mention}",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # /config welcome-disable
    # --------------------------------------------------

    @app_commands.command(
        name="welcome-disable",
        description="Kikapcsolja az üdvözlőüzeneteket.",
    )
    async def welcome_disable(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if interaction.guild is None:
            return

        await set_guild_setting(
            guild_id=interaction.guild.id,
            setting_key="welcome_channel_id",
            setting_value=None,
        )

        await interaction.response.send_message(
            "✅ Az üdvözlőüzenetek kikapcsolva.",
            ephemeral=True,
        )

    # --------------------------------------------------
    # /config goodbye-channel
    # --------------------------------------------------

    @app_commands.command(
        name="goodbye-channel",
        description="Beállítja a búcsúüzenetek csatornáját.",
    )
    @app_commands.describe(
        channel="A csatorna, ahová a búcsúüzenetek kerülnek.",
    )
    async def goodbye_channel(
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
                "❌ Nem sikerült lekérni a botot.",
                ephemeral=True,
            )
            return

        permissions = channel.permissions_for(bot_member)

        if not (
            permissions.view_channel
            and permissions.send_messages
            and permissions.embed_links
        ):
            await interaction.response.send_message(
                "❌ A botnak nincs jogosultsága üzenetet "
                f"küldeni a(z) {channel.mention} csatornába.",
                ephemeral=True,
            )
            return

        await set_guild_setting(
            guild_id=guild.id,
            setting_key="goodbye_channel_id",
            setting_value=str(channel.id),
        )

        await interaction.response.send_message(
            f"✅ Búcsúcsatorna beállítva: {channel.mention}",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # /config goodbye-disable
    # --------------------------------------------------

    @app_commands.command(
        name="goodbye-disable",
        description="Kikapcsolja a búcsúüzeneteket.",
    )
    async def goodbye_disable(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if interaction.guild is None:
            return

        await set_guild_setting(
            guild_id=interaction.guild.id,
            setting_key="goodbye_channel_id",
            setting_value=None,
        )

        await interaction.response.send_message(
            "✅ A búcsúüzenetek kikapcsolva.",
            ephemeral=True,
        )

    # --------------------------------------------------
    # /config autorole
    # --------------------------------------------------

    @app_commands.command(
        name="autorole",
        description="Beállítja a belépéskor automatikusan kiosztott rangot.",
    )
    @app_commands.describe(
        role="A belépő tagoknak automatikusan kiosztott rang.",
    )
    async def autorole(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        if role.is_default():
            await interaction.response.send_message(
                "❌ Az @everyone rang nem választható.",
                ephemeral=True,
            )
            return

        if role.managed:
            await interaction.response.send_message(
                "❌ Bothoz vagy integrációhoz tartozó rang "
                "nem választható.",
                ephemeral=True,
            )
            return

        if role.permissions.administrator:
            await interaction.response.send_message(
                "❌ Biztonsági okból rendszergazda-jogosultságú "
                "rang nem állítható be automatikus rangként.",
                ephemeral=True,
            )
            return

        bot_member = guild.me

        if bot_member is None:
            await interaction.response.send_message(
                "❌ Nem sikerült lekérni a botot.",
                ephemeral=True,
            )
            return

        if role >= bot_member.top_role:
            await interaction.response.send_message(
                "❌ A kiválasztott rang a bot rangjával azonos "
                "szinten vagy afölött van.\n"
                "Húzd a bot rangját a kiosztandó rang fölé.",
                ephemeral=True,
            )
            return

        await set_guild_setting(
            guild_id=guild.id,
            setting_key="autorole_id",
            setting_value=str(role.id),
        )

        await interaction.response.send_message(
            f"✅ Automatikus alaprang beállítva: {role.mention}",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # /config autorole-disable
    # --------------------------------------------------

    @app_commands.command(
        name="autorole-disable",
        description="Kikapcsolja az automatikus rangkiosztást.",
    )
    async def autorole_disable(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if interaction.guild is None:
            return

        await set_guild_setting(
            guild_id=interaction.guild.id,
            setting_key="autorole_id",
            setting_value=None,
        )

        await interaction.response.send_message(
            "✅ Az automatikus rangkiosztás kikapcsolva.",
            ephemeral=True,
        )
        
   
        # --------------------------------------------------
    # /config manager-add
    # --------------------------------------------------

    @app_commands.command(
        name="manager-add",
        description="Botkezelő rang hozzáadása.",
    )
    @app_commands.describe(
        role="A rang, amely kezelheti a bot beállításait.",
    )
    async def manager_add(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        # Botkezelő rangokat csak tulajdonos vagy admin módosíthat.
        if not await is_owner_or_administrator(interaction):
            await interaction.response.send_message(
                "❌ Botkezelő rangot csak a szervertulajdonos "
                "vagy egy rendszergazda adhat hozzá.",
                ephemeral=True,
            )
            return

        if role.is_default():
            await interaction.response.send_message(
                "❌ Az @everyone rang nem lehet botkezelő.",
                ephemeral=True,
            )
            return

        if role.managed:
            await interaction.response.send_message(
                "❌ Bothoz vagy integrációhoz tartozó rang "
                "nem választható.",
                ephemeral=True,
            )
            return

        added = await add_bot_manager_role(
            guild_id=guild.id,
            role_id=role.id,
        )

        if not added:
            await interaction.response.send_message(
                f"ℹ️ A(z) {role.mention} rang már botkezelő.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        await interaction.response.send_message(
            f"✅ A(z) {role.mention} rang hozzáadva "
            "a botkezelő rangokhoz.",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # /config manager-remove
    # --------------------------------------------------

    @app_commands.command(
        name="manager-remove",
        description="Botkezelő rang eltávolítása.",
    )
    @app_commands.describe(
        role="Az eltávolítandó botkezelő rang.",
    )
    async def manager_remove(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        if not await is_owner_or_administrator(interaction):
            await interaction.response.send_message(
                "❌ Botkezelő rangot csak a szervertulajdonos "
                "vagy egy rendszergazda távolíthat el.",
                ephemeral=True,
            )
            return

        removed = await remove_bot_manager_role(
            guild_id=guild.id,
            role_id=role.id,
        )

        if not removed:
            await interaction.response.send_message(
                f"ℹ️ A(z) {role.mention} rang nincs "
                "botkezelőként beállítva.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        await interaction.response.send_message(
            f"✅ A(z) {role.mention} rang eltávolítva "
            "a botkezelők közül.",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # /config manager-list
    # --------------------------------------------------

    @app_commands.command(
        name="manager-list",
        description="Megmutatja a beállított botkezelő rangokat.",
    )
    async def manager_list(
        self,
        interaction: discord.Interaction,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        role_ids = await get_bot_manager_roles(guild.id)

        if not role_ids:
            await interaction.response.send_message(
                "ℹ️ Nincs külön botkezelő rang beállítva.\n"
                "A szervertulajdonos és a rendszergazdák "
                "ettől függetlenül használhatják a botot.",
                ephemeral=True,
            )
            return

        role_lines: list[str] = []

        for role_id in role_ids:
            role = guild.get_role(role_id)

            if role is None:
                role_lines.append(
                    f"• Törölt rang (`{role_id}`)"
                )
            else:
                role_lines.append(
                    f"• {role.mention}"
                )

        embed = discord.Embed(
            title="🔐 Botkezelő rangok",
            description="\n".join(role_lines),
            color=discord.Color.blue(),
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
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

        def get_channel_text(setting_key: str) -> str:
            channel_id = settings.get(setting_key)

            if channel_id is None:
                return "Nincs beállítva"

            try:
                channel = guild.get_channel(int(channel_id))
            except ValueError:
                return "Hibás csatornaazonosító"

            if channel is None:
                return f"Törölt csatorna (`{channel_id}`)"

            return channel.mention

        def get_role_text(setting_key: str) -> str:
            role_id = settings.get(setting_key)

            if role_id is None:
                return "Nincs beállítva"

            try:
                role = guild.get_role(int(role_id))
            except ValueError:
                return "Hibás rangazonosító"

            if role is None:
                return f"Törölt rang (`{role_id}`)"

            return role.mention

        staff_role_lines: list[str] = []

        for role_id in staff_role_ids:
            role = guild.get_role(role_id)

            if role is None:
                staff_role_lines.append(
                    f"• Törölt rang (`{role_id}`)"
                )
            else:
                staff_role_lines.append(
                    f"• {role.mention}"
                )

        if staff_role_lines:
            staff_roles_text = "\n".join(staff_role_lines)
        else:
            staff_roles_text = "Nincs beállítva"

        embed = discord.Embed(
            title="⚙️ Szerverbeállítások",
            description=(
                "A bot jelenlegi Discordon beállított értékei."
            ),
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="🛡️ Staffrangok",
            value=staff_roles_text,
            inline=False,
        )

        embed.add_field(
            name="📜 Logcsatorna",
            value=get_channel_text("log_channel_id"),
            inline=False,
        )

        embed.add_field(
            name="👋 Üdvözlőcsatorna",
            value=get_channel_text("welcome_channel_id"),
            inline=False,
        )

        embed.add_field(
            name="🚪 Búcsúcsatorna",
            value=get_channel_text("goodbye_channel_id"),
            inline=False,
        )

        embed.add_field(
            name="🎭 Automatikus alaprang",
            value=get_role_text("autorole_id"),
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
    