from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands


class Moderation(commands.Cog):
    """
    Alapvető szervermoderációs parancsok.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def send_error(
        self,
        interaction: discord.Interaction,
        message: str,
    ) -> None:
        """
        Akkor is tud hibaüzenetet küldeni,
        ha a parancs már elkezdett válaszolni.
        """

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

    def hierarchy_problem(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ) -> str | None:
        """
        Ellenőrzi a moderátor és a bot szerepkörének
        helyét a célpont szerepköréhez képest.
        """

        guild = interaction.guild
        moderator = interaction.user

        if guild is None:
            return "❌ Ez a parancs csak szerveren használható."

        if not isinstance(moderator, discord.Member):
            return "❌ Nem sikerült lekérni a moderátor adatait."

        bot_member = guild.me

        if bot_member is None:
            return "❌ Nem sikerült lekérni a bot szervertagságát."

        if member.id == moderator.id:
            return "❌ Saját magadon nem használhatod ezt a parancsot."

        if member.id == bot_member.id:
            return "❌ A bot saját magát nem moderálhatja."

        if member.id == guild.owner_id:
            return "❌ A szerver tulajdonosát nem lehet moderálni."

        if (
            moderator.id != guild.owner_id
            and member.top_role >= moderator.top_role
        ):
            return (
                "❌ Nem moderálhatod ezt a tagot, mert a legmagasabb "
                "rangja azonos vagy magasabb a te rangodnál."
            )

        if member.top_role >= bot_member.top_role:
            return (
                "❌ A bot rangja nincs a célpont legmagasabb rangja fölött.\n"
                "Mozgasd a bot rangját feljebb a szerver ranglistájában."
            )

        return None

    # --------------------------------------------------
    # /clear
    # --------------------------------------------------

    @app_commands.command(
        name="clear",
        description="Üzenetek törlése az aktuális csatornából.",
    )
    @app_commands.describe(
        mennyiseg="A törlendő üzenetek száma, 1 és 100 között.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.checks.bot_has_permissions(
        manage_messages=True,
        read_message_history=True,
    )
    async def clear(
        self,
        interaction: discord.Interaction,
        mennyiseg: app_commands.Range[int, 1, 100],
    ) -> None:
        channel = interaction.channel

        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "❌ Ez a parancs csak normál szöveges csatornában használható.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        torolt_uzenetek = await channel.purge(
            limit=mennyiseg,
            reason=(
                f"Üzenettörlés: {interaction.user} "
                f"({interaction.user.id})"
            ),
        )

        await interaction.followup.send(
            f"✅ **{len(torolt_uzenetek)}** üzenet törölve.",
            ephemeral=True,
        )

    # --------------------------------------------------
    # /kick
    # --------------------------------------------------

    @app_commands.command(
        name="kick",
        description="Kirúg egy tagot a szerverről.",
    )
    @app_commands.describe(
        member="A kirúgandó tag.",
        ok="A kirúgás indoka.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(kick_members=True)
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    async def kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        ok: str | None = None,
    ) -> None:
        problem = self.hierarchy_problem(interaction, member)

        if problem:
            await interaction.response.send_message(
                problem,
                ephemeral=True,
            )
            return

        indok = (ok or "Nincs megadva.")[:400]

        await interaction.response.defer(ephemeral=True)

        await member.kick(
            reason=(
                f"{indok} | Moderátor: {interaction.user} "
                f"({interaction.user.id})"
            )
        )

        await interaction.followup.send(
            f"✅ {member.mention} kirúgva.\n"
            f"**Indok:** {indok}",
            ephemeral=True,
        )

    # --------------------------------------------------
    # /ban
    # --------------------------------------------------

    @app_commands.command(
        name="ban",
        description="Kitilt egy tagot a szerverről.",
    )
    @app_commands.describe(
        member="A kitiltandó tag.",
        ok="A kitiltás indoka.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(ban_members=True)
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        ok: str | None = None,
    ) -> None:
        problem = self.hierarchy_problem(interaction, member)

        if problem:
            await interaction.response.send_message(
                problem,
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            return

        indok = (ok or "Nincs megadva.")[:400]

        await interaction.response.defer(ephemeral=True)

        await interaction.guild.ban(
            member,
            reason=(
                f"{indok} | Moderátor: {interaction.user} "
                f"({interaction.user.id})"
            ),
            delete_message_seconds=0,
        )

        await interaction.followup.send(
            f"✅ **{member}** kitiltva.\n"
            f"**Indok:** {indok}",
            ephemeral=True,
        )

    # --------------------------------------------------
    # /timeout
    # --------------------------------------------------

    @app_commands.command(
        name="timeout",
        description="Ideiglenesen felfüggeszt egy tagot.",
    )
    @app_commands.describe(
        member="A felfüggesztendő tag.",
        percek="A felfüggesztés hossza percben.",
        ok="A felfüggesztés indoka.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    async def timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        percek: app_commands.Range[int, 1, 40320],
        ok: str | None = None,
    ) -> None:
        problem = self.hierarchy_problem(interaction, member)

        if problem:
            await interaction.response.send_message(
                problem,
                ephemeral=True,
            )
            return

        indok = (ok or "Nincs megadva.")[:400]

        await interaction.response.defer(ephemeral=True)

        await member.timeout(
            timedelta(minutes=percek),
            reason=(
                f"{indok} | Moderátor: {interaction.user} "
                f"({interaction.user.id})"
            ),
        )

        await interaction.followup.send(
            f"✅ {member.mention} felfüggesztve "
            f"**{percek} percre**.\n"
            f"**Indok:** {indok}",
            ephemeral=True,
        )

    # --------------------------------------------------
    # /untimeout
    # --------------------------------------------------

    @app_commands.command(
        name="untimeout",
        description="Megszünteti egy tag felfüggesztését.",
    )
    @app_commands.describe(
        member="A tag, akinek megszünteted a felfüggesztését.",
        ok="A megszüntetés indoka.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    async def untimeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        ok: str | None = None,
    ) -> None:
        problem = self.hierarchy_problem(interaction, member)

        if problem:
            await interaction.response.send_message(
                problem,
                ephemeral=True,
            )
            return

        indok = (ok or "Nincs megadva.")[:400]

        await interaction.response.defer(ephemeral=True)

        await member.timeout(
            None,
            reason=(
                f"{indok} | Moderátor: {interaction.user} "
                f"({interaction.user.id})"
            ),
        )

        await interaction.followup.send(
            f"✅ {member.mention} felfüggesztése megszüntetve.",
            ephemeral=True,
        )

    # --------------------------------------------------
    # Moderációs hibakezelés
    # --------------------------------------------------

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await self.send_error(
                interaction,
                "❌ Nincs jogosultságod ehhez a parancshoz.",
            )
            return

        if isinstance(error, app_commands.BotMissingPermissions):
            await self.send_error(
                interaction,
                "❌ A botnak nincs meg a szükséges jogosultsága.",
            )
            return

        eredeti_hiba = getattr(error, "original", error)

        if isinstance(eredeti_hiba, discord.Forbidden):
            await self.send_error(
                interaction,
                "❌ A Discord megtagadta a műveletet. "
                "Ellenőrizd a bot rangját és jogosultságait.",
            )
            return

        if isinstance(eredeti_hiba, discord.HTTPException):
            await self.send_error(
                interaction,
                "❌ Discord API-hiba történt. Próbáld újra később.",
            )
            return

        print(
            "Ismeretlen moderációs hiba:",
            repr(eredeti_hiba),
        )

        await self.send_error(
            interaction,
            "❌ Ismeretlen hiba történt a parancs futtatásakor.",
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))