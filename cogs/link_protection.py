import re
from datetime import timedelta
from urllib.parse import urlparse

import discord
from discord import app_commands
from discord.ext import commands

from database.db import (
    add_link_protect_allowed_domain,
    add_link_protect_exempt_channel,
    add_link_protect_exempt_role,
    add_link_protect_restricted_role,
    get_bot_manager_roles,
    get_guild_setting,
    get_link_protect_allowed_domains,
    get_link_protect_exempt_channels,
    get_link_protect_exempt_roles,
    get_link_protect_restricted_roles,
    get_staff_roles,
    remove_link_protect_allowed_domain,
    remove_link_protect_exempt_channel,
    remove_link_protect_exempt_role,
    remove_link_protect_restricted_role,
    set_guild_setting,
)

from utils.bot_permissions import (
    is_bot_manager,
    send_manager_denied,
)

from utils.logging_utils import send_log


URL_PATTERN = re.compile(
    r"""
    (?<![@\w])
    (
        (?:https?://|www\.)[^\s<>()]+
        |
        (?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+
        [a-z]{2,}
        (?:/[^\s<>()]*)?
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def normalize_domain(domain: str) -> str | None:
    """
    A megadott domainből egységes formátumot készít.

    Példák:
    https://www.youtube.com/watch?v=123 -> youtube.com
    www.discord.com -> discord.com
    """

    cleaned = domain.strip().lower()

    if not cleaned:
        return None

    if "://" not in cleaned:
        cleaned = f"https://{cleaned}"

    try:
        parsed = urlparse(cleaned)
    except ValueError:
        return None

    hostname = parsed.hostname

    if hostname is None:
        return None

    hostname = hostname.lower().rstrip(".")

    if hostname.startswith("www."):
        hostname = hostname[4:]

    if not re.fullmatch(
        r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?",
        hostname,
    ):
        return None

    if "." not in hostname:
        return None

    return hostname


def extract_domains(content: str) -> list[str]:
    """
    Kikeresi az üzenetben található domaineket.
    """

    domains: list[str] = []

    for match in URL_PATTERN.finditer(content):
        raw_url = match.group(1).strip(
            ".,!?;:)]}>\"'"
        )

        domain = normalize_domain(raw_url)

        if domain is not None and domain not in domains:
            domains.append(domain)

    return domains


def domain_is_allowed(
    domain: str,
    allowed_domains: set[str],
) -> bool:
    """
    Az aldomain is engedélyezett, ha a fődomain szerepel
    az engedélyezett listában.

    Példa:
    youtube.com engedélyezi a www.youtube.com domaint is.
    """

    for allowed_domain in allowed_domains:
        if domain == allowed_domain:
            return True

        if domain.endswith(f".{allowed_domain}"):
            return True

    return False


@app_commands.guild_only()
class LinkProtection(
    commands.GroupCog,
    group_name="linkprotect",
    group_description="Linkküldés elleni védelem kezelése.",
):
    def __init__(
        self,
        bot: commands.Bot,
    ) -> None:
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
        A tulajdonos, adminok, staffok, botkezelők és
        külön kivételként megadott rangok nem büntethetők.
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
            await get_link_protect_exempt_roles(guild.id)
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
    # /linkprotect enable
    # --------------------------------------------------

    @app_commands.command(
        name="enable",
        description="Bekapcsolja a linkvédelmet.",
    )
    async def enable(
        self,
        interaction: discord.Interaction,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        restricted_roles = (
            await get_link_protect_restricted_roles(
                guild.id
            )
        )

        if not restricted_roles:
            await interaction.response.send_message(
                "❌ Először adj hozzá legalább egy korlátozott rangot:\n"
                "`/linkprotect restricted-role-add`",
                ephemeral=True,
            )
            return

        await set_guild_setting(
            guild_id=guild.id,
            setting_key="link_protect_enabled",
            setting_value="1",
        )

        current_timeout = await get_guild_setting(
            guild.id,
            "link_protect_timeout_minutes",
        )

        if current_timeout is None:
            await set_guild_setting(
                guild_id=guild.id,
                setting_key="link_protect_timeout_minutes",
                setting_value="5",
            )

        await interaction.response.send_message(
            "✅ A linkvédelem bekapcsolva.",
            ephemeral=True,
        )

    # --------------------------------------------------
    # /linkprotect disable
    # --------------------------------------------------

    @app_commands.command(
        name="disable",
        description="Kikapcsolja a linkvédelmet.",
    )
    async def disable(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if interaction.guild is None:
            return

        await set_guild_setting(
            guild_id=interaction.guild.id,
            setting_key="link_protect_enabled",
            setting_value="0",
        )

        await interaction.response.send_message(
            "✅ A linkvédelem kikapcsolva.",
            ephemeral=True,
        )

    # --------------------------------------------------
    # /linkprotect timeout
    # --------------------------------------------------

    @app_commands.command(
        name="timeout",
        description="Beállítja a linkküldésért járó timeoutot.",
    )
    @app_commands.describe(
        percek="A timeout időtartama percben.",
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
            setting_key="link_protect_timeout_minutes",
            setting_value=str(percek),
        )

        await interaction.response.send_message(
            f"✅ A linkküldésért járó büntetés **{percek} perc timeout**.",
            ephemeral=True,
        )

    # --------------------------------------------------
    # Korlátozott rang hozzáadása
    # --------------------------------------------------

    @app_commands.command(
        name="restricted-role-add",
        description="Rang hozzáadása a linkvédelemhez.",
    )
    @app_commands.describe(
        role="Az a rang, amely nem küldhet linkeket.",
    )
    async def restricted_role_add(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        if role.is_default() or role.managed:
            await interaction.response.send_message(
                "❌ Ez a rang nem használható korlátozott rangként.",
                ephemeral=True,
            )
            return

        added = await add_link_protect_restricted_role(
            guild.id,
            role.id,
        )

        message = (
            f"✅ A(z) {role.mention} rang mostantól nem küldhet linkeket."
            if added
            else f"ℹ️ A(z) {role.mention} rang már korlátozva van."
        )

        await interaction.response.send_message(
            message,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # Korlátozott rang eltávolítása
    # --------------------------------------------------

    @app_commands.command(
        name="restricted-role-remove",
        description="Rang eltávolítása a linkvédelemből.",
    )
    async def restricted_role_remove(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        if interaction.guild is None:
            return

        removed = await remove_link_protect_restricted_role(
            interaction.guild.id,
            role.id,
        )

        message = (
            f"✅ A(z) {role.mention} rang már küldhet linkeket."
            if removed
            else f"ℹ️ A(z) {role.mention} rang nem volt korlátozva."
        )

        await interaction.response.send_message(
            message,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # Kivételes rang hozzáadása
    # --------------------------------------------------

    @app_commands.command(
        name="exempt-role-add",
        description="Rang kivétele a linkvédelem alól.",
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

        added = await add_link_protect_exempt_role(
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
    # Kivételes rang eltávolítása
    # --------------------------------------------------

    @app_commands.command(
        name="exempt-role-remove",
        description="Rang eltávolítása a linkvédelmi kivételek közül.",
    )
    async def exempt_role_remove(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        if interaction.guild is None:
            return

        removed = await remove_link_protect_exempt_role(
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
    # Kivételes csatorna hozzáadása
    # --------------------------------------------------

    @app_commands.command(
        name="exempt-channel-add",
        description="Csatorna kivétele a linkvédelem alól.",
    )
    async def exempt_channel_add(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        if interaction.guild is None:
            return

        added = await add_link_protect_exempt_channel(
            interaction.guild.id,
            channel.id,
        )

        message = (
            f"✅ A(z) {channel.mention} csatornában engedélyezettek a linkek."
            if added
            else f"ℹ️ A(z) {channel.mention} csatorna már kivétel."
        )

        await interaction.response.send_message(
            message,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # Kivételes csatorna eltávolítása
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

        removed = await remove_link_protect_exempt_channel(
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
    # Engedélyezett domain hozzáadása
    # --------------------------------------------------

    @app_commands.command(
        name="allowed-domain-add",
        description="Engedélyezett weboldal hozzáadása.",
    )
    @app_commands.describe(
        domain="Például: youtube.com",
    )
    async def allowed_domain_add(
        self,
        interaction: discord.Interaction,
        domain: str,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        normalized_domain = normalize_domain(domain)

        if normalized_domain is None:
            await interaction.response.send_message(
                "❌ Hibás domain. Példa: `youtube.com`",
                ephemeral=True,
            )
            return

        added = await add_link_protect_allowed_domain(
            guild.id,
            normalized_domain,
        )

        message = (
            f"✅ Engedélyezett domain: `{normalized_domain}`"
            if added
            else f"ℹ️ A `{normalized_domain}` domain már engedélyezve van."
        )

        await interaction.response.send_message(
            message,
            ephemeral=True,
        )

    # --------------------------------------------------
    # Engedélyezett domain eltávolítása
    # --------------------------------------------------

    @app_commands.command(
        name="allowed-domain-remove",
        description="Engedélyezett weboldal eltávolítása.",
    )
    @app_commands.describe(
        domain="Például: youtube.com",
    )
    async def allowed_domain_remove(
        self,
        interaction: discord.Interaction,
        domain: str,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        normalized_domain = normalize_domain(domain)

        if normalized_domain is None:
            await interaction.response.send_message(
                "❌ Hibás domain. Példa: `youtube.com`",
                ephemeral=True,
            )
            return

        removed = await remove_link_protect_allowed_domain(
            guild.id,
            normalized_domain,
        )

        message = (
            f"✅ A `{normalized_domain}` domain eltávolítva."
            if removed
            else f"ℹ️ A `{normalized_domain}` domain nem volt engedélyezve."
        )

        await interaction.response.send_message(
            message,
            ephemeral=True,
        )

    # --------------------------------------------------
    # /linkprotect show
    # --------------------------------------------------

    @app_commands.command(
        name="show",
        description="Megmutatja a linkvédelem beállításait.",
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
            "link_protect_enabled",
        )

        timeout_text = await get_guild_setting(
            guild.id,
            "link_protect_timeout_minutes",
        )

        restricted_role_ids = (
            await get_link_protect_restricted_roles(
                guild.id
            )
        )

        exempt_role_ids = (
            await get_link_protect_exempt_roles(
                guild.id
            )
        )

        exempt_channel_ids = (
            await get_link_protect_exempt_channels(
                guild.id
            )
        )

        allowed_domains = (
            await get_link_protect_allowed_domains(
                guild.id
            )
        )

        restricted_roles = [
            guild.get_role(role_id).mention
            if guild.get_role(role_id) is not None
            else f"Törölt rang (`{role_id}`)"
            for role_id in restricted_role_ids
        ]

        exempt_roles = [
            guild.get_role(role_id).mention
            if guild.get_role(role_id) is not None
            else f"Törölt rang (`{role_id}`)"
            for role_id in exempt_role_ids
        ]

        exempt_channels = [
            guild.get_channel(channel_id).mention
            if guild.get_channel(channel_id) is not None
            else f"Törölt csatorna (`{channel_id}`)"
            for channel_id in exempt_channel_ids
        ]

        embed = discord.Embed(
            title="🔗 Linkvédelem",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )

        embed.add_field(
            name="Állapot",
            value=(
                "✅ Bekapcsolva"
                if enabled == "1"
                else "❌ Kikapcsolva"
            ),
            inline=True,
        )

        embed.add_field(
            name="Timeout",
            value=f"{timeout_text or '5'} perc",
            inline=True,
        )

        embed.add_field(
            name="Korlátozott rangok",
            value=(
                "\n".join(restricted_roles)[:1024]
                if restricted_roles
                else "Nincs beállítva"
            ),
            inline=False,
        )

        embed.add_field(
            name="Kivételes rangok",
            value=(
                "\n".join(exempt_roles)[:1024]
                if exempt_roles
                else "Nincs külön kivétel"
            ),
            inline=False,
        )

        embed.add_field(
            name="Kivételes csatornák",
            value=(
                "\n".join(exempt_channels)[:1024]
                if exempt_channels
                else "Nincs kivétel"
            ),
            inline=False,
        )

        embed.add_field(
            name="Engedélyezett domainek",
            value=(
                "\n".join(
                    f"`{domain}`"
                    for domain in allowed_domains
                )[:1024]
                if allowed_domains
                else "Nincs engedélyezett domain"
            ),
            inline=False,
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # Üzenetek ellenőrzése
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

        if not message.content:
            return

        enabled = await get_guild_setting(
            guild.id,
            "link_protect_enabled",
        )

        if enabled != "1":
            return

        exempt_channel_ids = set(
            await get_link_protect_exempt_channels(
                guild.id
            )
        )

        if message.channel.id in exempt_channel_ids:
            return

        if await self.member_is_exempt(author):
            return

        restricted_role_ids = set(
            await get_link_protect_restricted_roles(
                guild.id
            )
        )

        if not restricted_role_ids:
            return

        is_restricted = any(
            role.id in restricted_role_ids
            for role in author.roles
        )

        if not is_restricted:
            return

        detected_domains = extract_domains(
            message.content
        )

        if not detected_domains:
            return

        allowed_domains = set(
            await get_link_protect_allowed_domains(
                guild.id
            )
        )

        blocked_domains = [
            domain
            for domain in detected_domains
            if not domain_is_allowed(
                domain,
                allowed_domains,
            )
        ]

        if not blocked_domains:
            return

        timeout_text = await get_guild_setting(
            guild.id,
            "link_protect_timeout_minutes",
        )

        try:
            timeout_minutes = int(
                timeout_text or "5"
            )
        except ValueError:
            timeout_minutes = 5

        timeout_minutes = max(
            1,
            min(timeout_minutes, 40320),
        )

        deleted = False
        failure_reason: str | None = None

        try:
            await message.delete()
            deleted = True
        except (discord.Forbidden, discord.HTTPException):
            deleted = False

        bot_member = guild.me

        if bot_member is None:
            failure_reason = (
                "A bot szervertagja nem található."
            )

        elif not bot_member.guild_permissions.moderate_members:
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
                    timedelta(
                        minutes=timeout_minutes
                    ),
                    reason=(
                        "Tiltott link küldése: "
                        + ", ".join(blocked_domains)
                    )[:500],
                )

            except discord.Forbidden:
                failure_reason = (
                    "A Discord megtagadta a timeoutot."
                )

            except discord.HTTPException:
                failure_reason = (
                    "Discord API-hiba történt."
                )

        log_embed = discord.Embed(
            title="🚨 Tiltott link küldve",
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
            name="Tiltott domainek",
            value="\n".join(
                f"`{domain}`"
                for domain in blocked_domains
            )[:1024],
            inline=False,
        )

        log_embed.add_field(
            name="Üzenet törölve",
            value="Igen" if deleted else "Nem",
            inline=True,
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
            name="Eredeti üzenet",
            value=message.content[:1000],
            inline=False,
        )

        await send_log(
            guild=guild,
            embed=log_embed,
        )

        try:
            if failure_reason is None:
                warning_text = (
                    f"⏳ **{author.display_name}** "
                    f"{timeout_minutes} perc timeoutot kapott "
                    "tiltott link küldése miatt."
                )
            else:
                warning_text = (
                    "⚠️ Tiltott link észlelve, de a timeout "
                    "nem volt végrehajtható."
                )

            await message.channel.send(
                warning_text,
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
        if isinstance(
            error,
            app_commands.CheckFailure,
        ):
            return

        original_error = getattr(
            error,
            "original",
            error,
        )

        print(
            "Linkvédelmi rendszer hibája:",
            repr(original_error),
        )

        await self.send_error(
            interaction,
            "❌ Hiba történt a linkvédelem kezelése közben.",
        )


async def setup(
    bot: commands.Bot,
) -> None:
    await bot.add_cog(
        LinkProtection(bot)
    )