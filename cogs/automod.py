import asyncio
import re
import time
from collections import deque
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from database.db import (
    add_automod_blocked_word,
    add_automod_exempt_channel,
    add_automod_exempt_role,
    get_automod_blocked_words,
    get_automod_exempt_channels,
    get_automod_exempt_roles,
    get_bot_manager_roles,
    get_guild_setting,
    get_staff_roles,
    remove_automod_blocked_word,
    remove_automod_exempt_channel,
    remove_automod_exempt_role,
    set_guild_setting,
)

from utils.bot_permissions import (
    is_bot_manager,
    send_manager_denied,
)

from utils.logging_utils import send_log


def normalize_content(content: str) -> str:
    """
    Egységes formátum az ismételt üzenetek
    és tiltott szavak ellenőrzéséhez.
    """

    return " ".join(
        content.casefold().split()
    )


def safe_int(
    value: str | None,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    try:
        number = int(value or str(default))
    except ValueError:
        number = default

    return max(
        minimum,
        min(number, maximum),
    )


def find_blocked_word(
    content: str,
    blocked_words: list[str],
) -> str | None:
    """
    Megkeresi az első tiltott szót vagy kifejezést.
    """

    normalized_content = normalize_content(
        content
    )

    for blocked_word in sorted(
        blocked_words,
        key=len,
        reverse=True,
    ):
        normalized_word = normalize_content(
            blocked_word
        )

        if not normalized_word:
            continue

        pattern = (
            rf"(?<!\w)"
            rf"{re.escape(normalized_word)}"
            rf"(?!\w)"
        )

        if re.search(
            pattern,
            normalized_content,
            flags=re.IGNORECASE,
        ):
            return blocked_word

    return None


@app_commands.guild_only()
class AutoModeration(
    commands.GroupCog,
    group_name="automod",
    group_description=(
        "Spam, tömeges ping és tiltott szavak elleni védelem."
    ),
):
    def __init__(
        self,
        bot: commands.Bot,
    ) -> None:
        self.bot = bot

        self.message_times: dict[
            tuple[int, int],
            deque[float],
        ] = {}

        self.recent_messages: dict[
            tuple[int, int],
            deque[tuple[float, str]],
        ] = {}

        self.user_locks: dict[
            tuple[int, int],
            asyncio.Lock,
        ] = {}

        self.last_punishments: dict[
            tuple[int, int],
            float,
        ] = {}

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

    def get_user_lock(
        self,
        guild_id: int,
        user_id: int,
    ) -> asyncio.Lock:
        key = (
            guild_id,
            user_id,
        )

        if key not in self.user_locks:
            self.user_locks[key] = asyncio.Lock()

        return self.user_locks[key]

    async def member_is_exempt(
        self,
        member: discord.Member,
    ) -> bool:
        """
        Tulajdonos, admin, staff, botkezelő és
        kivételes rang nem kap automatikus büntetést.
        """

        guild = member.guild

        if member.id == guild.owner_id:
            return True

        if member.guild_permissions.administrator:
            return True

        staff_roles = set(
            await get_staff_roles(guild.id)
        )

        manager_roles = set(
            await get_bot_manager_roles(guild.id)
        )

        exempt_roles = set(
            await get_automod_exempt_roles(guild.id)
        )

        protected_roles = (
            staff_roles
            | manager_roles
            | exempt_roles
        )

        return any(
            role.id in protected_roles
            for role in member.roles
        )

    # --------------------------------------------------
    # /automod enable
    # --------------------------------------------------

    @app_commands.command(
        name="enable",
        description="Bekapcsolja az automoderációt.",
    )
    async def enable(
        self,
        interaction: discord.Interaction,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        defaults = {
            "automod_timeout_minutes": "5",
            "automod_spam_limit": "5",
            "automod_spam_window_seconds": "5",
            "automod_repeat_limit": "3",
            "automod_repeat_window_seconds": "30",
            "automod_mention_limit": "5",
        }

        for setting_key, default_value in defaults.items():
            current_value = await get_guild_setting(
                guild.id,
                setting_key,
            )

            if current_value is None:
                await set_guild_setting(
                    guild_id=guild.id,
                    setting_key=setting_key,
                    setting_value=default_value,
                )

        await set_guild_setting(
            guild_id=guild.id,
            setting_key="automod_enabled",
            setting_value="1",
        )

        await interaction.response.send_message(
            "✅ Az automoderáció bekapcsolva.",
            ephemeral=True,
        )

    # --------------------------------------------------
    # /automod disable
    # --------------------------------------------------

    @app_commands.command(
        name="disable",
        description="Kikapcsolja az automoderációt.",
    )
    async def disable(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if interaction.guild is None:
            return

        await set_guild_setting(
            guild_id=interaction.guild.id,
            setting_key="automod_enabled",
            setting_value="0",
        )

        await interaction.response.send_message(
            "✅ Az automoderáció kikapcsolva.",
            ephemeral=True,
        )

    # --------------------------------------------------
    # /automod timeout
    # --------------------------------------------------

    @app_commands.command(
        name="timeout",
        description="Beállítja az automod miatti timeoutot.",
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
            interaction.guild.id,
            "automod_timeout_minutes",
            str(percek),
        )

        await interaction.response.send_message(
            (
                "✅ Az automod büntetése "
                f"**{percek} perc timeout**."
            ),
            ephemeral=True,
        )

    # --------------------------------------------------
    # /automod spam
    # --------------------------------------------------

    @app_commands.command(
        name="spam",
        description="Beállítja a gyors üzenetküldés határát.",
    )
    @app_commands.describe(
        uzenetek="Ennyi üzenet már spamnek számít.",
        masodperc="Ezen időn belül számolja az üzeneteket.",
    )
    async def spam_setting(
        self,
        interaction: discord.Interaction,
        uzenetek: app_commands.Range[int, 2, 20],
        masodperc: app_commands.Range[int, 1, 60],
    ) -> None:
        if interaction.guild is None:
            return

        await set_guild_setting(
            interaction.guild.id,
            "automod_spam_limit",
            str(uzenetek),
        )

        await set_guild_setting(
            interaction.guild.id,
            "automod_spam_window_seconds",
            str(masodperc),
        )

        await interaction.response.send_message(
            (
                "✅ Spamhatár: "
                f"**{uzenetek} üzenet / "
                f"{masodperc} másodperc**."
            ),
            ephemeral=True,
        )

    # --------------------------------------------------
    # /automod repeat
    # --------------------------------------------------

    @app_commands.command(
        name="repeat",
        description="Beállítja az ismételt üzenetek határát.",
    )
    @app_commands.describe(
        ismetlesek="Ennyi azonos üzenet már szabálysértés.",
        masodperc="Ezen időn belül számolja az ismétléseket.",
    )
    async def repeat_setting(
        self,
        interaction: discord.Interaction,
        ismetlesek: app_commands.Range[int, 2, 10],
        masodperc: app_commands.Range[int, 2, 120],
    ) -> None:
        if interaction.guild is None:
            return

        await set_guild_setting(
            interaction.guild.id,
            "automod_repeat_limit",
            str(ismetlesek),
        )

        await set_guild_setting(
            interaction.guild.id,
            "automod_repeat_window_seconds",
            str(masodperc),
        )

        await interaction.response.send_message(
            (
                "✅ Ismétlésvédelem: "
                f"**{ismetlesek} azonos üzenet / "
                f"{masodperc} másodperc**."
            ),
            ephemeral=True,
        )

    # --------------------------------------------------
    # /automod mentions
    # --------------------------------------------------

    @app_commands.command(
        name="mentions",
        description="Beállítja a tömeges ping határát.",
    )
    @app_commands.describe(
        emlitesek="Ennyi említés már büntetést okoz.",
    )
    async def mentions_setting(
        self,
        interaction: discord.Interaction,
        emlitesek: app_commands.Range[int, 2, 50],
    ) -> None:
        if interaction.guild is None:
            return

        await set_guild_setting(
            interaction.guild.id,
            "automod_mention_limit",
            str(emlitesek),
        )

        await interaction.response.send_message(
            (
                "✅ Tömeges ping határa: "
                f"**{emlitesek} említés**."
            ),
            ephemeral=True,
        )

    # --------------------------------------------------
    # Tiltott szó hozzáadása
    # --------------------------------------------------

    @app_commands.command(
        name="blocked-word-add",
        description="Tiltott szót vagy kifejezést ad hozzá.",
    )
    @app_commands.describe(
        szo="A tiltandó szó vagy kifejezés.",
    )
    async def blocked_word_add(
        self,
        interaction: discord.Interaction,
        szo: str,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        word = normalize_content(szo)

        if not word:
            await interaction.response.send_message(
                "❌ A tiltott szó nem lehet üres.",
                ephemeral=True,
            )
            return

        if len(word) > 100:
            await interaction.response.send_message(
                (
                    "❌ A tiltott kifejezés legfeljebb "
                    "100 karakter lehet."
                ),
                ephemeral=True,
            )
            return

        added = await add_automod_blocked_word(
            guild.id,
            word,
        )

        message = (
            f"✅ Tiltott kifejezés hozzáadva: `{word}`"
            if added
            else f"ℹ️ A `{word}` már szerepel a listában."
        )

        await interaction.response.send_message(
            message,
            ephemeral=True,
        )

    # --------------------------------------------------
    # Tiltott szó eltávolítása
    # --------------------------------------------------

    @app_commands.command(
        name="blocked-word-remove",
        description="Tiltott szót vagy kifejezést távolít el.",
    )
    @app_commands.describe(
        szo="Az eltávolítandó szó vagy kifejezés.",
    )
    async def blocked_word_remove(
        self,
        interaction: discord.Interaction,
        szo: str,
    ) -> None:
        if interaction.guild is None:
            return

        word = normalize_content(szo)

        removed = await remove_automod_blocked_word(
            interaction.guild.id,
            word,
        )

        message = (
            f"✅ A `{word}` eltávolítva."
            if removed
            else f"ℹ️ A `{word}` nem volt tiltva."
        )

        await interaction.response.send_message(
            message,
            ephemeral=True,
        )

    # --------------------------------------------------
    # Tiltott szavak listázása
    # --------------------------------------------------

    @app_commands.command(
        name="blocked-word-list",
        description="Megmutatja a tiltott szavakat.",
    )
    async def blocked_word_list(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if interaction.guild is None:
            return

        words = await get_automod_blocked_words(
            interaction.guild.id
        )

        if not words:
            await interaction.response.send_message(
                "ℹ️ Nincs tiltott szó beállítva.",
                ephemeral=True,
            )
            return

        lines = [
            f"`{index}.` {word}"
            for index, word in enumerate(
                words,
                start=1,
            )
        ]

        description = "\n".join(lines)

        if len(description) > 3900:
            description = (
                description[:3900]
                + "\n… A lista további elemeket is tartalmaz."
            )

        embed = discord.Embed(
            title="🚫 Tiltott szavak",
            description=description,
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )

        embed.set_footer(
            text=f"Összesen: {len(words)}"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    # --------------------------------------------------
    # Kivételes rang hozzáadása
    # --------------------------------------------------

    @app_commands.command(
        name="exempt-role-add",
        description="Rang kivétele az automoderáció alól.",
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
                "❌ Ez a rang nem használható kivételként.",
                ephemeral=True,
            )
            return

        added = await add_automod_exempt_role(
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
        description="Rang eltávolítása az automod kivételei közül.",
    )
    async def exempt_role_remove(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        if interaction.guild is None:
            return

        removed = await remove_automod_exempt_role(
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
        description="Csatorna kivétele az automoderáció alól.",
    )
    async def exempt_channel_add(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        if interaction.guild is None:
            return

        added = await add_automod_exempt_channel(
            interaction.guild.id,
            channel.id,
        )

        message = (
            (
                f"✅ A(z) {channel.mention} csatorna "
                "kivételként hozzáadva."
            )
            if added
            else (
                f"ℹ️ A(z) {channel.mention} csatorna "
                "már kivétel."
            )
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
        description="Csatorna eltávolítása az automod kivételei közül.",
    )
    async def exempt_channel_remove(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        if interaction.guild is None:
            return

        removed = await remove_automod_exempt_channel(
            interaction.guild.id,
            channel.id,
        )

        message = (
            (
                f"✅ A(z) {channel.mention} csatorna "
                "már nem kivétel."
            )
            if removed
            else (
                f"ℹ️ A(z) {channel.mention} csatorna "
                "nem volt kivétel."
            )
        )

        await interaction.response.send_message(
            message,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # /automod show
    # --------------------------------------------------

    @app_commands.command(
        name="show",
        description="Megmutatja az automoderáció beállításait.",
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
            "automod_enabled",
        )

        timeout_minutes = await get_guild_setting(
            guild.id,
            "automod_timeout_minutes",
        )

        spam_limit = await get_guild_setting(
            guild.id,
            "automod_spam_limit",
        )

        spam_window = await get_guild_setting(
            guild.id,
            "automod_spam_window_seconds",
        )

        repeat_limit = await get_guild_setting(
            guild.id,
            "automod_repeat_limit",
        )

        repeat_window = await get_guild_setting(
            guild.id,
            "automod_repeat_window_seconds",
        )

        mention_limit = await get_guild_setting(
            guild.id,
            "automod_mention_limit",
        )

        exempt_role_ids = await get_automod_exempt_roles(
            guild.id
        )

        exempt_channel_ids = await get_automod_exempt_channels(
            guild.id
        )

        blocked_words = await get_automod_blocked_words(
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
            title="🛡️ Automoderáció",
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
            value=f"{timeout_minutes or '5'} perc",
            inline=True,
        )

        embed.add_field(
            name="Spam",
            value=(
                f"{spam_limit or '5'} üzenet / "
                f"{spam_window or '5'} másodperc"
            ),
            inline=False,
        )

        embed.add_field(
            name="Ismételt üzenetek",
            value=(
                f"{repeat_limit or '3'} ismétlés / "
                f"{repeat_window or '30'} másodperc"
            ),
            inline=False,
        )

        embed.add_field(
            name="Tömeges ping",
            value=f"{mention_limit or '5'} említéstől",
            inline=False,
        )

        embed.add_field(
            name="Tiltott szavak",
            value=str(len(blocked_words)),
            inline=True,
        )

        embed.add_field(
            name="Kivételes rangok",
            value=(
                "\n".join(role_lines)[:1024]
                if role_lines
                else "Nincs külön kivétel"
            ),
            inline=False,
        )

        embed.add_field(
            name="Kivételes csatornák",
            value=(
                "\n".join(channel_lines)[:1024]
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
    # Automatikus büntetés
    # --------------------------------------------------

    async def punish_member(
        self,
        message: discord.Message,
        reason: str,
        details: str,
        timeout_minutes: int,
    ) -> None:
        guild = message.guild
        author = message.author

        if guild is None:
            return

        if not isinstance(
            author,
            discord.Member,
        ):
            return

        key = (
            guild.id,
            author.id,
        )

        lock = self.get_user_lock(
            guild.id,
            author.id,
        )

        async with lock:
            now = time.monotonic()

            previous_punishment = self.last_punishments.get(
                key,
                0.0,
            )

            if now - previous_punishment < 10:
                return

            self.last_punishments[key] = now

            deleted = False
            failure_reason: str | None = None

            try:
                await message.delete()
                deleted = True

            except (
                discord.Forbidden,
                discord.NotFound,
                discord.HTTPException,
            ):
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
                        reason=f"Automod: {reason}"[:450],
                    )

                except discord.Forbidden:
                    failure_reason = (
                        "A Discord megtagadta a timeoutot."
                    )

                except discord.HTTPException:
                    failure_reason = (
                        "Discord API-hiba történt."
                    )

            self.message_times.pop(
                key,
                None,
            )

            self.recent_messages.pop(
                key,
                None,
            )

            log_embed = discord.Embed(
                title="🤖 Automoderációs intézkedés",
                color=(
                    discord.Color.red()
                    if failure_reason is None
                    else discord.Color.orange()
                ),
                timestamp=discord.utils.utcnow(),
            )

            log_embed.add_field(
                name="Felhasználó",
                value=(
                    f"{author.mention}\n"
                    f"`{author.id}`"
                ),
                inline=True,
            )

            log_embed.add_field(
                name="Csatorna",
                value=message.channel.mention,
                inline=True,
            )

            log_embed.add_field(
                name="Ok",
                value=reason[:1024],
                inline=False,
            )

            log_embed.add_field(
                name="Részletek",
                value=details[:1024],
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

            try:
                warning = (
                    (
                        f"⏳ **{author.display_name}** "
                        f"{timeout_minutes} perc timeoutot kapott.\n"
                        f"Ok: **{reason}**"
                    )
                    if failure_reason is None
                    else (
                        "⚠️ Szabálysértés történt, de a timeout "
                        "nem volt végrehajtható."
                    )
                )

                await message.channel.send(
                    warning,
                    delete_after=10,
                    allowed_mentions=discord.AllowedMentions.none(),
                )

            except (
                discord.Forbidden,
                discord.HTTPException,
            ):
                pass

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

        if not isinstance(
            author,
            discord.Member,
        ):
            return

        if author.bot or message.webhook_id is not None:
            return

        enabled = await get_guild_setting(
            guild.id,
            "automod_enabled",
        )

        if enabled != "1":
            return

        exempt_channels = set(
            await get_automod_exempt_channels(
                guild.id
            )
        )

        if message.channel.id in exempt_channels:
            return

        if await self.member_is_exempt(author):
            return

        key = (
            guild.id,
            author.id,
        )

        now = time.monotonic()

        if (
            now
            - self.last_punishments.get(
                key,
                0.0,
            )
            < 10
        ):
            return

        timeout_minutes = safe_int(
            await get_guild_setting(
                guild.id,
                "automod_timeout_minutes",
            ),
            default=5,
            minimum=1,
            maximum=40320,
        )

        spam_limit = safe_int(
            await get_guild_setting(
                guild.id,
                "automod_spam_limit",
            ),
            default=5,
            minimum=2,
            maximum=20,
        )

        spam_window = safe_int(
            await get_guild_setting(
                guild.id,
                "automod_spam_window_seconds",
            ),
            default=5,
            minimum=1,
            maximum=60,
        )

        repeat_limit = safe_int(
            await get_guild_setting(
                guild.id,
                "automod_repeat_limit",
            ),
            default=3,
            minimum=2,
            maximum=10,
        )

        repeat_window = safe_int(
            await get_guild_setting(
                guild.id,
                "automod_repeat_window_seconds",
            ),
            default=30,
            minimum=2,
            maximum=120,
        )

        mention_limit = safe_int(
            await get_guild_setting(
                guild.id,
                "automod_mention_limit",
            ),
            default=5,
            minimum=2,
            maximum=50,
        )

        # Tiltott szavak

        blocked_words = await get_automod_blocked_words(
            guild.id
        )

        detected_word = find_blocked_word(
            message.content,
            blocked_words,
        )

        if detected_word is not None:
            await self.punish_member(
                message=message,
                reason="Tiltott szó vagy kifejezés",
                details=f"Találat: `{detected_word}`",
                timeout_minutes=timeout_minutes,
            )
            return

        # Tömeges ping

        mention_count = (
            len(set(message.raw_mentions))
            + len(set(message.raw_role_mentions))
            + (
                1
                if message.mention_everyone
                else 0
            )
        )

        if mention_count >= mention_limit:
            await self.punish_member(
                message=message,
                reason="Tömeges ping",
                details=(
                    f"Említések: "
                    f"{mention_count}/{mention_limit}"
                ),
                timeout_minutes=timeout_minutes,
            )
            return

        # Spam időpontok

        message_queue = self.message_times.setdefault(
            key,
            deque(),
        )

        message_queue.append(
            now
        )

        while (
            message_queue
            and now - message_queue[0] > spam_window
        ):
            message_queue.popleft()

        # Ismételt üzenetek

        normalized_message = normalize_content(
            message.content
        )

        repeat_queue = self.recent_messages.setdefault(
            key,
            deque(),
        )

        if normalized_message:
            repeat_queue.append(
                (
                    now,
                    normalized_message,
                )
            )

        while (
            repeat_queue
            and now - repeat_queue[0][0] > repeat_window
        ):
            repeat_queue.popleft()

        if normalized_message:
            repeated_count = sum(
                1
                for _, old_message in repeat_queue
                if old_message == normalized_message
            )

            if repeated_count >= repeat_limit:
                await self.punish_member(
                    message=message,
                    reason="Ismételt üzenetek",
                    details=(
                        f"Azonos üzenetek: "
                        f"{repeated_count}/{repeat_limit} "
                        f"{repeat_window} másodpercen belül"
                    ),
                    timeout_minutes=timeout_minutes,
                )
                return

        # Gyors üzenetküldés

        if len(message_queue) >= spam_limit:
            await self.punish_member(
                message=message,
                reason="Gyors üzenetküldés / spam",
                details=(
                    f"Üzenetek: "
                    f"{len(message_queue)}/{spam_limit} "
                    f"{spam_window} másodpercen belül"
                ),
                timeout_minutes=timeout_minutes,
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
            app_commands.CheckFailure,
        ):
            return

        original_error = getattr(
            error,
            "original",
            error,
        )

        print(
            "Automoderációs rendszer hibája:",
            repr(original_error),
        )

        await self.send_error(
            interaction,
            "❌ Hiba történt az automoderáció kezelése közben.",
        )


async def setup(
    bot: commands.Bot,
) -> None:
    await bot.add_cog(
        AutoModeration(bot)
    )