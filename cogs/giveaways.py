import re
import secrets
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from database.db import (
    count_giveaway_entries,
    create_giveaway,
    end_giveaway,
    get_active_giveaways,
    get_giveaway_by_id,
    get_giveaway_entries,
    set_giveaway_message_id,
)

from utils.bot_permissions import (
    is_bot_manager,
    send_manager_denied,
)

from utils.logging_utils import send_log

from views.giveaway import GiveawayEntryView


DURATION_PATTERN = re.compile(
    r"(\d+)([smhdw])",
    re.IGNORECASE,
)


def parse_duration(
    duration_text: str,
) -> timedelta | None:
    """
    Időtartam feldolgozása.

    Használható példák:
    30s
    10m
    2h
    1d
    1d12h
    1w
    """

    normalized = (
        duration_text
        .strip()
        .lower()
        .replace(" ", "")
    )

    if not normalized:
        return None

    matches = list(
        DURATION_PATTERN.finditer(normalized)
    )

    if not matches:
        return None

    reconstructed = "".join(
        match.group(0)
        for match in matches
    )

    if reconstructed != normalized:
        return None

    total_seconds = 0

    unit_seconds = {
        "s": 1,
        "m": 60,
        "h": 60 * 60,
        "d": 60 * 60 * 24,
        "w": 60 * 60 * 24 * 7,
    }

    for match in matches:
        amount = int(match.group(1))
        unit = match.group(2).lower()

        total_seconds += (
            amount * unit_seconds[unit]
        )

    minimum_seconds = 10
    maximum_seconds = 60 * 60 * 24 * 365

    if not (
        minimum_seconds
        <= total_seconds
        <= maximum_seconds
    ):
        return None

    return timedelta(
        seconds=total_seconds
    )


def parse_database_datetime(
    value: str,
) -> datetime:
    """
    Az adatbázisban tárolt ISO időpont feldolgozása.
    """

    cleaned = value.replace(
        "Z",
        "+00:00",
    )

    result = datetime.fromisoformat(
        cleaned
    )

    if result.tzinfo is None:
        result = result.replace(
            tzinfo=timezone.utc
        )

    return result.astimezone(
        timezone.utc
    )


def build_active_embed(
    giveaway_id: int,
    prize: str,
    host_id: int,
    winner_count: int,
    end_time: datetime,
    participant_count: int = 0,
) -> discord.Embed:
    """
    Aktív giveaway embed elkészítése.
    """

    embed = discord.Embed(
        title="🎉 GIVEAWAY",
        description=(
            f"## {prize}\n\n"
            "A jelentkezéshez nyomd meg az alábbi gombot!"
        ),
        color=discord.Color.blurple(),
        timestamp=discord.utils.utcnow(),
    )

    embed.add_field(
        name="🏆 Nyeremény",
        value=prize,
        inline=False,
    )

    embed.add_field(
        name="👑 Rendező",
        value=f"<@{host_id}>",
        inline=True,
    )

    embed.add_field(
        name="🎯 Nyertesek",
        value=str(winner_count),
        inline=True,
    )

    embed.add_field(
        name="👥 Résztvevők",
        value=str(participant_count),
        inline=True,
    )

    embed.add_field(
        name="⏰ Befejezés",
        value=(
            f"{discord.utils.format_dt(end_time, style='F')}\n"
            f"({discord.utils.format_dt(end_time, style='R')})"
        ),
        inline=False,
    )

    embed.set_footer(
        text=f"Giveaway ID: {giveaway_id}"
    )

    return embed


def build_ended_embed(
    giveaway: dict,
    participant_count: int,
    winners: list[discord.Member],
) -> discord.Embed:
    """
    Lezárt giveaway embed elkészítése.
    """

    prize = str(giveaway["prize"])
    giveaway_id = int(giveaway["id"])
    host_id = int(giveaway["host_id"])

    if winners:
        winner_text = "\n".join(
            winner.mention
            for winner in winners
        )
    else:
        winner_text = (
            "Nem volt elegendő érvényes jelentkező."
        )

    embed = discord.Embed(
        title="🎉 GIVEAWAY VÉGET ÉRT",
        description=f"## {prize}",
        color=discord.Color.gold(),
        timestamp=discord.utils.utcnow(),
    )

    embed.add_field(
        name="🏆 Nyertesek",
        value=winner_text,
        inline=False,
    )

    embed.add_field(
        name="👑 Rendező",
        value=f"<@{host_id}>",
        inline=True,
    )

    embed.add_field(
        name="👥 Résztvevők",
        value=str(participant_count),
        inline=True,
    )

    embed.set_footer(
        text=(
            f"Giveaway ID: {giveaway_id} • Lezárva"
        )
    )

    return embed


@app_commands.guild_only()
class Giveaways(
    commands.GroupCog,
    group_name="giveaway",
    group_description="Giveawayek létrehozása és kezelése.",
):
    def __init__(
        self,
        bot: commands.Bot,
    ) -> None:
        self.bot = bot

        self.entry_view = GiveawayEntryView(
            bot
        )

        self.random = secrets.SystemRandom()

    async def cog_load(self) -> None:
        """
        A jelentkezési gomb és az automatikus
        giveaway-ellenőrzés elindítása.
        """

        self.bot.add_view(
            self.entry_view
        )

        if not self.giveaway_watcher.is_running():
            self.giveaway_watcher.start()

        print(
            "Giveaway gombok és időzítő betöltve."
        )

    def cog_unload(self) -> None:
        """
        Modul leállításakor az ellenőrző feladat leállítása.
        """

        self.giveaway_watcher.cancel()

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

    async def finish_giveaway(
        self,
        giveaway_id: int,
        ended_by: discord.Member | None = None,
    ) -> tuple[bool, str]:
        """
        Giveaway lezárása, nyertesek kiválasztása,
        az eredeti üzenet frissítése és eredményhirdetés.
        """

        giveaway = await get_giveaway_by_id(
            giveaway_id
        )

        if giveaway is None:
            return (
                False,
                "❌ Nem található ilyen giveaway.",
            )

        if giveaway["status"] != "active":
            return (
                False,
                "ℹ️ Ez a giveaway már véget ért.",
            )

        successfully_ended = await end_giveaway(
            giveaway_id
        )

        if not successfully_ended:
            return (
                False,
                "ℹ️ Ezt a giveawayt közben már lezárták.",
            )

        guild_id = int(
            giveaway["guild_id"]
        )

        channel_id = int(
            giveaway["channel_id"]
        )

        message_id_value = giveaway[
            "message_id"
        ]

        guild = self.bot.get_guild(
            guild_id
        )

        entry_ids = await get_giveaway_entries(
            giveaway_id
        )

        participant_count = len(entry_ids)

        if guild is None:
            return (
                True,
                (
                    "✅ A giveaway lezárva, de a szerver "
                    "nem található a bot gyorsítótárában."
                ),
            )

        eligible_members: list[
            discord.Member
        ] = []

        for user_id in entry_ids:
            member = guild.get_member(
                user_id
            )

            if (
                member is not None
                and not member.bot
            ):
                eligible_members.append(
                    member
                )

        requested_winners = int(
            giveaway["winner_count"]
        )

        actual_winner_count = min(
            requested_winners,
            len(eligible_members),
        )

        if actual_winner_count > 0:
            winners = self.random.sample(
                eligible_members,
                actual_winner_count,
            )
        else:
            winners = []

        channel = guild.get_channel(
            channel_id
        )

        ended_embed = build_ended_embed(
            giveaway=giveaway,
            participant_count=participant_count,
            winners=winners,
        )

        if isinstance(
            channel,
            discord.TextChannel,
        ):
            if message_id_value is not None:
                try:
                    giveaway_message = (
                        await channel.fetch_message(
                            int(message_id_value)
                        )
                    )

                    await giveaway_message.edit(
                        embed=ended_embed,
                        view=None,
                    )

                except (
                    discord.NotFound,
                    discord.Forbidden,
                    discord.HTTPException,
                ):
                    pass

            if winners:
                winner_mentions = " ".join(
                    winner.mention
                    for winner in winners
                )

                result_text = (
                    f"🎉 Gratulálunk {winner_mentions}!\n"
                    f"Megnyertétek: **{giveaway['prize']}**"
                )
            else:
                result_text = (
                    "😕 A giveaway véget ért, de nem volt "
                    "elegendő érvényes jelentkező."
                )

            try:
                await channel.send(
                    result_text,
                    allowed_mentions=discord.AllowedMentions(
                        users=True,
                        roles=False,
                        everyone=False,
                    ),
                )

            except discord.HTTPException:
                pass

        log_embed = discord.Embed(
            title="🎉 Giveaway lezárva",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow(),
        )

        log_embed.add_field(
            name="Giveaway ID",
            value=f"`{giveaway_id}`",
            inline=True,
        )

        log_embed.add_field(
            name="Nyeremény",
            value=str(giveaway["prize"])[:1024],
            inline=True,
        )

        log_embed.add_field(
            name="Résztvevők",
            value=str(participant_count),
            inline=True,
        )

        if winners:
            log_embed.add_field(
                name="Nyertesek",
                value="\n".join(
                    (
                        f"{winner.mention} "
                        f"(`{winner.id}`)"
                    )
                    for winner in winners
                )[:1024],
                inline=False,
            )
        else:
            log_embed.add_field(
                name="Nyertesek",
                value="Nem volt érvényes nyertes.",
                inline=False,
            )

        if ended_by is not None:
            log_embed.add_field(
                name="Manuálisan lezárta",
                value=(
                    f"{ended_by.mention}\n"
                    f"`{ended_by.id}`"
                ),
                inline=False,
            )

        await send_log(
            guild=guild,
            embed=log_embed,
        )

        if winners:
            winner_text = ", ".join(
                winner.display_name
                for winner in winners
            )

            return (
                True,
                (
                    "✅ A giveaway lezárva.\n"
                    f"Nyertesek: **{winner_text}**"
                ),
            )

        return (
            True,
            (
                "✅ A giveaway lezárva, de nem volt "
                "elegendő érvényes jelentkező."
            ),
        )

    # --------------------------------------------------
    # /giveaway create
    # --------------------------------------------------

    @app_commands.command(
        name="create",
        description="Új giveaway létrehozása.",
    )
    @app_commands.describe(
        channel="A csatorna, ahová a giveaway kerüljön.",
        nyeremeny="A kisorsolandó nyeremény.",
        idotartam=(
            "Például: 30s, 10m, 2h, 1d vagy 1d12h."
        ),
        nyertesek="A kisorsolandó nyertesek száma.",
    )
    async def create(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        nyeremeny: str,
        idotartam: str,
        nyertesek: app_commands.Range[int, 1, 20] = 1,
    ) -> None:
        guild = interaction.guild
        host = interaction.user

        if guild is None:
            return

        if not isinstance(
            host,
            discord.Member,
        ):
            return

        prize = nyeremeny.strip()

        if not prize:
            await interaction.response.send_message(
                "❌ A nyeremény nem lehet üres.",
                ephemeral=True,
            )
            return

        if len(prize) > 200:
            await interaction.response.send_message(
                "❌ A nyeremény legfeljebb 200 karakter lehet.",
                ephemeral=True,
            )
            return

        duration = parse_duration(
            idotartam
        )

        if duration is None:
            await interaction.response.send_message(
                (
                    "❌ Hibás időtartam.\n"
                    "Példák: `30s`, `10m`, `2h`, "
                    "`1d`, `1d12h` vagy `1w`.\n"
                    "A minimum 10 másodperc, "
                    "a maximum 365 nap."
                ),
                ephemeral=True,
            )
            return

        bot_member = guild.me

        if bot_member is None:
            await interaction.response.send_message(
                "❌ Nem sikerült lekérni a bot szervertagját.",
                ephemeral=True,
            )
            return

        permissions = channel.permissions_for(
            bot_member
        )

        if not (
            permissions.view_channel
            and permissions.send_messages
            and permissions.embed_links
            and permissions.read_message_history
        ):
            await interaction.response.send_message(
                (
                    "❌ A botnak nincs megfelelő jogosultsága "
                    "a kiválasztott csatornában."
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        end_time = (
            discord.utils.utcnow()
            + duration
        )

        giveaway_id = await create_giveaway(
            guild_id=guild.id,
            channel_id=channel.id,
            host_id=host.id,
            prize=prize,
            winner_count=int(nyertesek),
            end_time=end_time.isoformat(),
        )

        giveaway_embed = build_active_embed(
            giveaway_id=giveaway_id,
            prize=prize,
            host_id=host.id,
            winner_count=int(nyertesek),
            end_time=end_time,
            participant_count=0,
        )

        try:
            giveaway_message = await channel.send(
                embed=giveaway_embed,
                view=self.entry_view,
                allowed_mentions=discord.AllowedMentions.none(),
            )

        except (
            discord.Forbidden,
            discord.HTTPException,
        ):
            await end_giveaway(
                giveaway_id
            )

            await interaction.followup.send(
                "❌ Nem sikerült elküldeni a giveaway üzenetét.",
                ephemeral=True,
            )
            return

        message_saved = await set_giveaway_message_id(
            giveaway_id=giveaway_id,
            message_id=giveaway_message.id,
        )

        if not message_saved:
            try:
                await giveaway_message.delete()
            except discord.HTTPException:
                pass

            await end_giveaway(
                giveaway_id
            )

            await interaction.followup.send(
                "❌ Nem sikerült elmenteni a giveawayt.",
                ephemeral=True,
            )
            return

        log_embed = discord.Embed(
            title="🎉 Giveaway létrehozva",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )

        log_embed.add_field(
            name="Giveaway ID",
            value=f"`{giveaway_id}`",
            inline=True,
        )

        log_embed.add_field(
            name="Nyeremény",
            value=prize,
            inline=True,
        )

        log_embed.add_field(
            name="Rendező",
            value=(
                f"{host.mention}\n"
                f"`{host.id}`"
            ),
            inline=True,
        )

        log_embed.add_field(
            name="Csatorna",
            value=channel.mention,
            inline=True,
        )

        log_embed.add_field(
            name="Befejezés",
            value=discord.utils.format_dt(
                end_time,
                style="F",
            ),
            inline=False,
        )

        await send_log(
            guild=guild,
            embed=log_embed,
        )

        await interaction.followup.send(
            (
                "✅ A giveaway létrehozva.\n"
                f"Giveaway ID: `{giveaway_id}`\n"
                f"[Ugrás az üzenethez]"
                f"({giveaway_message.jump_url})"
            ),
            ephemeral=True,
        )

    # --------------------------------------------------
    # /giveaway end
    # --------------------------------------------------

    @app_commands.command(
        name="end",
        description="Egy aktív giveaway azonnali lezárása.",
    )
    @app_commands.describe(
        giveaway_id="A giveaway belső azonosítója.",
    )
    async def end_command(
        self,
        interaction: discord.Interaction,
        giveaway_id: app_commands.Range[int, 1],
    ) -> None:
        guild = interaction.guild
        member = interaction.user

        if guild is None:
            return

        if not isinstance(
            member,
            discord.Member,
        ):
            return

        giveaway = await get_giveaway_by_id(
            int(giveaway_id)
        )

        if giveaway is None:
            await interaction.response.send_message(
                "❌ Nem található ilyen giveaway.",
                ephemeral=True,
            )
            return

        if int(giveaway["guild_id"]) != guild.id:
            await interaction.response.send_message(
                "❌ Ez a giveaway nem ezen a szerveren található.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        success, message = await self.finish_giveaway(
            giveaway_id=int(giveaway_id),
            ended_by=member,
        )

        await interaction.followup.send(
            message,
            ephemeral=True,
        )

    # --------------------------------------------------
    # /giveaway reroll
    # --------------------------------------------------

    @app_commands.command(
        name="reroll",
        description="Új nyertest sorsol egy lezárt giveawayből.",
    )
    @app_commands.describe(
        giveaway_id="A lezárt giveaway azonosítója.",
        nyertesek="Az újonnan kisorsolandó nyertesek száma.",
    )
    async def reroll(
        self,
        interaction: discord.Interaction,
        giveaway_id: app_commands.Range[int, 1],
        nyertesek: app_commands.Range[int, 1, 20] = 1,
    ) -> None:
        guild = interaction.guild
        member = interaction.user

        if guild is None:
            return

        if not isinstance(
            member,
            discord.Member,
        ):
            return

        giveaway = await get_giveaway_by_id(
            int(giveaway_id)
        )

        if giveaway is None:
            await interaction.response.send_message(
                "❌ Nem található ilyen giveaway.",
                ephemeral=True,
            )
            return

        if int(giveaway["guild_id"]) != guild.id:
            await interaction.response.send_message(
                "❌ Ez a giveaway nem ezen a szerveren található.",
                ephemeral=True,
            )
            return

        if giveaway["status"] != "ended":
            await interaction.response.send_message(
                "❌ Először le kell zárni a giveawayt.",
                ephemeral=True,
            )
            return

        entry_ids = await get_giveaway_entries(
            int(giveaway_id)
        )

        eligible_members: list[
            discord.Member
        ] = []

        for user_id in entry_ids:
            entry_member = guild.get_member(
                user_id
            )

            if (
                entry_member is not None
                and not entry_member.bot
            ):
                eligible_members.append(
                    entry_member
                )

        if not eligible_members:
            await interaction.response.send_message(
                "❌ Nincs érvényes résztvevő az újrasorsoláshoz.",
                ephemeral=True,
            )
            return

        winner_count = min(
            int(nyertesek),
            len(eligible_members),
        )

        winners = self.random.sample(
            eligible_members,
            winner_count,
        )

        channel = guild.get_channel(
            int(giveaway["channel_id"])
        )

        if not isinstance(
            channel,
            discord.TextChannel,
        ):
            await interaction.response.send_message(
                "❌ A giveaway eredeti csatornája nem található.",
                ephemeral=True,
            )
            return

        winner_mentions = " ".join(
            winner.mention
            for winner in winners
        )

        try:
            await channel.send(
                (
                    f"🔄 **Újrasorsolás – Giveaway "
                    f"#{giveaway_id}**\n"
                    f"Gratulálunk {winner_mentions}!\n"
                    f"Nyeremény: **{giveaway['prize']}**"
                ),
                allowed_mentions=discord.AllowedMentions(
                    users=True,
                    roles=False,
                    everyone=False,
                ),
            )

        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ Nem sikerült elküldeni az újrasorsolás eredményét.",
                ephemeral=True,
            )
            return

        log_embed = discord.Embed(
            title="🔄 Giveaway újrasorsolva",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )

        log_embed.add_field(
            name="Giveaway ID",
            value=f"`{giveaway_id}`",
            inline=True,
        )

        log_embed.add_field(
            name="Újrasorsolta",
            value=(
                f"{member.mention}\n"
                f"`{member.id}`"
            ),
            inline=True,
        )

        log_embed.add_field(
            name="Új nyertesek",
            value="\n".join(
                (
                    f"{winner.mention} "
                    f"(`{winner.id}`)"
                )
                for winner in winners
            )[:1024],
            inline=False,
        )

        await send_log(
            guild=guild,
            embed=log_embed,
        )

        await interaction.response.send_message(
            (
                "✅ Az újrasorsolás megtörtént.\n"
                "Nyertesek: "
                + ", ".join(
                    winner.display_name
                    for winner in winners
                )
            ),
            ephemeral=True,
        )

    # --------------------------------------------------
    # Aktív giveawayek automatikus ellenőrzése
    # --------------------------------------------------

    @tasks.loop(seconds=5)
    async def giveaway_watcher(
        self,
    ) -> None:
        try:
            active_giveaways = (
                await get_active_giveaways()
            )
        except Exception as error:
            print(
                "Giveaway adatbázis-ellenőrzési hiba:",
                repr(error),
            )
            return

        current_time = discord.utils.utcnow()

        for giveaway in active_giveaways:
            try:
                end_time = parse_database_datetime(
                    str(giveaway["end_time"])
                )

                if end_time <= current_time:
                    await self.finish_giveaway(
                        giveaway_id=int(
                            giveaway["id"]
                        )
                    )

            except Exception as error:
                print(
                    (
                        "Giveaway automatikus "
                        "lezárási hiba:"
                    ),
                    repr(error),
                )

    @giveaway_watcher.before_loop
    async def before_giveaway_watcher(
        self,
    ) -> None:
        await self.bot.wait_until_ready()

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
            "Giveaway rendszer hibája:",
            repr(original_error),
        )

        await self.send_error(
            interaction,
            "❌ Hiba történt a giveaway kezelése közben.",
        )


async def setup(
    bot: commands.Bot,
) -> None:
    await bot.add_cog(
        Giveaways(bot)
    )