from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from database.db import (
    add_warning,
    count_warnings,
    delete_warning,
    get_warnings,
)


class WarningSystem(commands.Cog):
    """
    A tagok figyelmeztetéseinek kezelése.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def hierarchy_problem(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ) -> str | None:
        """
        Ellenőrzi, hogy a moderátor figyelmeztetheti-e
        a kiválasztott tagot.
        """

        guild = interaction.guild
        moderator = interaction.user

        if guild is None:
            return "❌ Ez a parancs csak szerveren használható."

        if not isinstance(moderator, discord.Member):
            return "❌ Nem sikerült lekérni a moderátor adatait."

        if member.id == moderator.id:
            return "❌ Saját magadat nem figyelmeztetheted."

        if member.id == guild.owner_id:
            return "❌ A szerver tulajdonosát nem figyelmeztetheted."

        if member.bot:
            return "❌ Botot nem figyelmeztethetsz."

        if (
            moderator.id != guild.owner_id
            and member.top_role >= moderator.top_role
        ):
            return (
                "❌ Nem figyelmeztetheted ezt a tagot, mert "
                "a rangja azonos vagy magasabb a te rangodnál."
            )

        return None

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

    @staticmethod
    def format_created_at(created_at: str) -> str:
        """
        Az SQLite időpontját Discord-időbélyeggé alakítja.
        """

        try:
            parsed_time = datetime.strptime(
                created_at,
                "%Y-%m-%d %H:%M:%S",
            ).replace(tzinfo=timezone.utc)

            timestamp = int(parsed_time.timestamp())

            return f"<t:{timestamp}:R>"

        except ValueError:
            return created_at

    # --------------------------------------------------
    # /warn
    # --------------------------------------------------

    @app_commands.command(
        name="warn",
        description="Figyelmeztetést ad egy tagnak.",
    )
    @app_commands.describe(
        member="A figyelmeztetendő tag.",
        ok="A figyelmeztetés indoka.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(
        moderate_members=True,
    )
    async def warn(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        ok: str,
    ) -> None:
        problem = self.hierarchy_problem(
            interaction,
            member,
        )

        if problem:
            await interaction.response.send_message(
                problem,
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            return

        reason = ok.strip()

        if not reason:
            await interaction.response.send_message(
                "❌ Az indok nem lehet üres.",
                ephemeral=True,
            )
            return

        if len(reason) > 500:
            reason = reason[:500]

        warning_id = await add_warning(
            guild_id=interaction.guild.id,
            user_id=member.id,
            moderator_id=interaction.user.id,
            reason=reason,
        )

        total = await count_warnings(
            interaction.guild.id,
            member.id,
        )

        embed = discord.Embed(
            title="⚠️ Figyelmeztetés rögzítve",
            color=discord.Color.orange(),
        )

        embed.add_field(
            name="Tag",
            value=member.mention,
            inline=True,
        )

        embed.add_field(
            name="Moderátor",
            value=interaction.user.mention,
            inline=True,
        )

        embed.add_field(
            name="Figyelmeztetés azonosítója",
            value=f"`{warning_id}`",
            inline=True,
        )

        embed.add_field(
            name="Indok",
            value=reason,
            inline=False,
        )

        embed.set_footer(
            text=f"Összes figyelmeztetés: {total}"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    # --------------------------------------------------
    # /warnings
    # --------------------------------------------------

    @app_commands.command(
        name="warnings",
        description="Megmutatja egy tag figyelmeztetéseit.",
    )
    @app_commands.describe(
        member="A tag, akinek meg szeretnéd nézni a figyelmeztetéseit.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(
        moderate_members=True,
    )
    async def warnings(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ) -> None:
        if interaction.guild is None:
            return

        records = await get_warnings(
            guild_id=interaction.guild.id,
            user_id=member.id,
            limit=10,
        )

        total = await count_warnings(
            interaction.guild.id,
            member.id,
        )

        if not records:
            await interaction.response.send_message(
                f"✅ {member.mention} tagnak nincs figyelmeztetése.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"⚠️ {member} figyelmeztetései",
            description=(
                f"Összes figyelmeztetés: **{total}**\n"
                "Az utolsó 10 bejegyzés látható."
            ),
            color=discord.Color.orange(),
        )

        for record in records:
            reason = str(record["reason"])

            if len(reason) > 180:
                reason = reason[:177] + "..."

            created_at = self.format_created_at(
                str(record["created_at"])
            )

            embed.add_field(
                name=f"Figyelmeztetés #{record['id']}",
                value=(
                    f"**Indok:** {reason}\n"
                    f"**Moderátor:** <@{record['moderator_id']}>\n"
                    f"**Időpont:** {created_at}"
                ),
                inline=False,
            )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    # --------------------------------------------------
    # /delwarn
    # --------------------------------------------------

    @app_commands.command(
        name="delwarn",
        description="Töröl egy figyelmeztetést.",
    )
    @app_commands.describe(
        warning_id="A törlendő figyelmeztetés azonosítója.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(
        moderate_members=True,
    )
    async def delwarn(
        self,
        interaction: discord.Interaction,
        warning_id: int,
    ) -> None:
        if interaction.guild is None:
            return

        if warning_id < 1:
            await interaction.response.send_message(
                "❌ Érvénytelen figyelmeztetés-azonosító.",
                ephemeral=True,
            )
            return

        deleted_record = await delete_warning(
            guild_id=interaction.guild.id,
            warning_id=warning_id,
        )

        if deleted_record is None:
            await interaction.response.send_message(
                "❌ Ezen a szerveren nem található ilyen figyelmeztetés.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            (
                f"✅ A(z) **#{warning_id}** figyelmeztetés törölve.\n"
                f"**Tag:** <@{deleted_record['user_id']}>\n"
                f"**Korábbi indok:** {deleted_record['reason']}"
            ),
            ephemeral=True,
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
                "❌ Nincs jogosultságod ehhez a parancshoz.",
            )
            return

        original_error = getattr(
            error,
            "original",
            error,
        )

        print(
            "Figyelmeztetési rendszer hibája:",
            repr(original_error),
        )

        await self.send_error(
            interaction,
            "❌ Hiba történt a figyelmeztetés kezelése közben.",
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WarningSystem(bot))