from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from database.db import (
    get_guild_setting,
    set_guild_setting,
)

from utils.bot_permissions import (
    is_bot_manager,
    send_manager_denied,
)

from utils.logging_utils import send_log


MAX_IMAGE_SIZE = 8 * 1024 * 1024

SUPPORTED_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
}


async def read_profile_image(
    attachment: discord.Attachment,
) -> bytes:
    """
    Ellenőrzi és beolvassa a profilképet vagy bannert.
    """

    extension = Path(
        attachment.filename
    ).suffix.lower()

    if extension not in SUPPORTED_IMAGE_EXTENSIONS:
        raise ValueError(
            "Csak PNG, JPG, JPEG, GIF vagy WEBP kép használható."
        )

    if attachment.size > MAX_IMAGE_SIZE:
        raise ValueError(
            "A kép legfeljebb 8 MB lehet."
        )

    image_bytes = await attachment.read()

    if not image_bytes:
        raise ValueError(
            "A feltöltött kép üres."
        )

    return image_bytes


@app_commands.guild_only()
class BotProfile(
    commands.GroupCog,
    group_name="botprofile",
    group_description=(
        "A bot szerverenkénti profiljának kezelése."
    ),
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

    async def get_bot_member(
        self,
        interaction: discord.Interaction,
    ) -> discord.Member | None:
        guild = interaction.guild

        if guild is None:
            return None

        bot_member = guild.me

        if bot_member is not None:
            return bot_member

        if self.bot.user is None:
            return None

        try:
            return await guild.fetch_member(
                self.bot.user.id
            )
        except (
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException,
        ):
            return None

    async def log_profile_change(
        self,
        guild: discord.Guild,
        member: discord.Member,
        action: str,
        value: str,
    ) -> None:
        embed = discord.Embed(
            title="🤖 Botprofil módosítva",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )

        embed.add_field(
            name="Módosította",
            value=(
                f"{member.mention}\n"
                f"`{member.id}`"
            ),
            inline=True,
        )

        embed.add_field(
            name="Módosítás",
            value=action,
            inline=True,
        )

        embed.add_field(
            name="Új érték",
            value=value[:1024],
            inline=False,
        )

        await send_log(
            guild=guild,
            embed=embed,
        )

    # --------------------------------------------------
    # /botprofile nickname
    # --------------------------------------------------

    @app_commands.command(
        name="nickname",
        description=(
            "Beállítja a bot nevét ezen a szerveren."
        ),
    )
    @app_commands.describe(
        nev="A bot új szerverneve.",
    )
    async def nickname(
        self,
        interaction: discord.Interaction,
        nev: str,
    ) -> None:
        guild = interaction.guild
        manager = interaction.user

        if guild is None or not isinstance(
            manager,
            discord.Member,
        ):
            return

        clean_name = nev.strip()

        if not 1 <= len(clean_name) <= 32:
            await interaction.response.send_message(
                (
                    "❌ A bot neve legalább 1, "
                    "legfeljebb 32 karakter lehet."
                ),
                ephemeral=True,
            )
            return

        bot_member = await self.get_bot_member(
            interaction
        )

        if bot_member is None:
            await interaction.response.send_message(
                "❌ Nem sikerült lekérni a bot szervertagját.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        try:
            await bot_member.edit(
                nick=clean_name,
                reason=(
                    f"Botprofil módosítva: "
                    f"{manager} ({manager.id})"
                ),
            )

        except discord.Forbidden:
            await interaction.followup.send(
                (
                    "❌ A bot nem módosíthatja a saját nevét.\n"
                    "Ellenőrizd a **Becenevek módosítása** "
                    "jogosultságot."
                ),
                ephemeral=True,
            )
            return

        except discord.HTTPException:
            await interaction.followup.send(
                "❌ Discord API-hiba történt.",
                ephemeral=True,
            )
            return

        await self.log_profile_change(
            guild=guild,
            member=manager,
            action="Szervernév",
            value=clean_name,
        )

        await interaction.followup.send(
            (
                "✅ A bot szerverneve módosítva:\n"
                f"**{clean_name}**"
            ),
            ephemeral=True,
        )

    # --------------------------------------------------
    # /botprofile avatar
    # --------------------------------------------------

    @app_commands.command(
        name="avatar",
        description=(
            "Beállítja a bot szerverenkénti profilképét."
        ),
    )
    @app_commands.describe(
        kep="PNG, JPG, GIF vagy WEBP kép.",
    )
    async def avatar(
        self,
        interaction: discord.Interaction,
        kep: discord.Attachment,
    ) -> None:
        guild = interaction.guild
        manager = interaction.user

        if guild is None or not isinstance(
            manager,
            discord.Member,
        ):
            return

        bot_member = await self.get_bot_member(
            interaction
        )

        if bot_member is None:
            await interaction.response.send_message(
                "❌ Nem sikerült lekérni a bot szervertagját.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        try:
            image_bytes = await read_profile_image(
                kep
            )

            await bot_member.edit(
                avatar=image_bytes,
                reason=(
                    f"Botprofilkép módosítva: "
                    f"{manager} ({manager.id})"
                ),
            )

        except ValueError as error:
            await interaction.followup.send(
                f"❌ {error}",
                ephemeral=True,
            )
            return

        except discord.Forbidden:
            await interaction.followup.send(
                (
                    "❌ A Discord megtagadta "
                    "a profilkép módosítását."
                ),
                ephemeral=True,
            )
            return

        except discord.HTTPException:
            await interaction.followup.send(
                (
                    "❌ Nem sikerült feltölteni a képet. "
                    "Ellenőrizd a kép formátumát."
                ),
                ephemeral=True,
            )
            return

        await self.log_profile_change(
            guild=guild,
            member=manager,
            action="Szerverprofilkép",
            value=kep.filename,
        )

        await interaction.followup.send(
            "✅ A bot szerverprofilképe módosítva.",
            ephemeral=True,
        )

    # --------------------------------------------------
    # /botprofile banner
    # --------------------------------------------------

    @app_commands.command(
        name="banner",
        description=(
            "Beállítja a bot szerverenkénti bannerét."
        ),
    )
    @app_commands.describe(
        kep="PNG, JPG, GIF vagy WEBP banner.",
    )
    async def banner(
        self,
        interaction: discord.Interaction,
        kep: discord.Attachment,
    ) -> None:
        guild = interaction.guild
        manager = interaction.user

        if guild is None or not isinstance(
            manager,
            discord.Member,
        ):
            return

        bot_member = await self.get_bot_member(
            interaction
        )

        if bot_member is None:
            await interaction.response.send_message(
                "❌ Nem sikerült lekérni a bot szervertagját.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        try:
            image_bytes = await read_profile_image(
                kep
            )

            await bot_member.edit(
                banner=image_bytes,
                reason=(
                    f"Botbanner módosítva: "
                    f"{manager} ({manager.id})"
                ),
            )

        except ValueError as error:
            await interaction.followup.send(
                f"❌ {error}",
                ephemeral=True,
            )
            return

        except discord.Forbidden:
            await interaction.followup.send(
                (
                    "❌ A Discord megtagadta "
                    "a banner módosítását."
                ),
                ephemeral=True,
            )
            return

        except discord.HTTPException:
            await interaction.followup.send(
                (
                    "❌ Nem sikerült feltölteni a bannert. "
                    "Ellenőrizd a kép formátumát."
                ),
                ephemeral=True,
            )
            return

        await self.log_profile_change(
            guild=guild,
            member=manager,
            action="Szerverbanner",
            value=kep.filename,
        )

        await interaction.followup.send(
            "✅ A bot szerverbannere módosítva.",
            ephemeral=True,
        )

    # --------------------------------------------------
    # /botprofile bio
    # --------------------------------------------------

    @app_commands.command(
        name="bio",
        description=(
            "Beállítja a bot szerverenkénti bemutatkozását."
        ),
    )
    @app_commands.describe(
        szoveg="A bot szerverenkénti bemutatkozása.",
    )
    async def bio(
        self,
        interaction: discord.Interaction,
        szoveg: str,
    ) -> None:
        guild = interaction.guild
        manager = interaction.user

        if guild is None or not isinstance(
            manager,
            discord.Member,
        ):
            return

        clean_bio = szoveg.strip()

        if not 1 <= len(clean_bio) <= 190:
            await interaction.response.send_message(
                (
                    "❌ A bemutatkozás legalább 1, "
                    "legfeljebb 190 karakter lehet."
                ),
                ephemeral=True,
            )
            return

        bot_member = await self.get_bot_member(
            interaction
        )

        if bot_member is None:
            await interaction.response.send_message(
                "❌ Nem sikerült lekérni a bot szervertagját.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        try:
            await bot_member.edit(
                bio=clean_bio,
                reason=(
                    f"Botbemutatkozás módosítva: "
                    f"{manager} ({manager.id})"
                ),
            )

        except discord.Forbidden:
            await interaction.followup.send(
                (
                    "❌ A Discord megtagadta "
                    "a bemutatkozás módosítását."
                ),
                ephemeral=True,
            )
            return

        except discord.HTTPException:
            await interaction.followup.send(
                "❌ Discord API-hiba történt.",
                ephemeral=True,
            )
            return

        await set_guild_setting(
            guild_id=guild.id,
            setting_key="bot_profile_bio",
            setting_value=clean_bio,
        )

        await self.log_profile_change(
            guild=guild,
            member=manager,
            action="Bemutatkozás",
            value=clean_bio,
        )

        await interaction.followup.send(
            "✅ A bot szerverenkénti bemutatkozása módosítva.",
            ephemeral=True,
        )

    # --------------------------------------------------
    # /botprofile reset
    # --------------------------------------------------

    @app_commands.command(
        name="reset",
        description=(
            "Visszaállítja a bot egyik profilbeállítását."
        ),
    )
    @app_commands.describe(
        resz="A visszaállítandó profilrész.",
    )
    @app_commands.choices(
        resz=[
            app_commands.Choice(
                name="Minden",
                value="all",
            ),
            app_commands.Choice(
                name="Szervernév",
                value="nickname",
            ),
            app_commands.Choice(
                name="Profilkép",
                value="avatar",
            ),
            app_commands.Choice(
                name="Banner",
                value="banner",
            ),
            app_commands.Choice(
                name="Bemutatkozás",
                value="bio",
            ),
        ]
    )
    async def reset(
        self,
        interaction: discord.Interaction,
        resz: app_commands.Choice[str],
    ) -> None:
        guild = interaction.guild
        manager = interaction.user

        if guild is None or not isinstance(
            manager,
            discord.Member,
        ):
            return

        bot_member = await self.get_bot_member(
            interaction
        )

        if bot_member is None:
            await interaction.response.send_message(
                "❌ Nem sikerült lekérni a bot szervertagját.",
                ephemeral=True,
            )
            return

        edit_values: dict = {}

        reset_names = {
            "all": "Minden profilbeállítás",
            "nickname": "Szervernév",
            "avatar": "Profilkép",
            "banner": "Banner",
            "bio": "Bemutatkozás",
        }

        if resz.value == "all":
            edit_values = {
                "nick": None,
                "avatar": None,
                "banner": None,
                "bio": None,
            }

        elif resz.value == "nickname":
            edit_values["nick"] = None

        elif resz.value == "avatar":
            edit_values["avatar"] = None

        elif resz.value == "banner":
            edit_values["banner"] = None

        elif resz.value == "bio":
            edit_values["bio"] = None

        await interaction.response.defer(
            ephemeral=True
        )

        try:
            await bot_member.edit(
                **edit_values,
                reason=(
                    f"Botprofil visszaállítva: "
                    f"{manager} ({manager.id})"
                ),
            )

        except discord.Forbidden:
            await interaction.followup.send(
                (
                    "❌ A Discord megtagadta "
                    "a profil visszaállítását."
                ),
                ephemeral=True,
            )
            return

        except (
            discord.HTTPException,
            ValueError,
        ):
            await interaction.followup.send(
                (
                    "❌ Hiba történt "
                    "a profil visszaállításakor."
                ),
                ephemeral=True,
            )
            return

        if resz.value in {
            "all",
            "bio",
        }:
            await set_guild_setting(
                guild_id=guild.id,
                setting_key="bot_profile_bio",
                setting_value=None,
            )

        reset_name = reset_names.get(
            resz.value,
            resz.value,
        )

        await self.log_profile_change(
            guild=guild,
            member=manager,
            action="Profil visszaállítása",
            value=reset_name,
        )

        await interaction.followup.send(
            f"✅ Visszaállítva: **{reset_name}**.",
            ephemeral=True,
        )

    # --------------------------------------------------
    # /botprofile show
    # --------------------------------------------------

    @app_commands.command(
        name="show",
        description=(
            "Megmutatja a bot jelenlegi szerverprofilját."
        ),
    )
    async def show(
        self,
        interaction: discord.Interaction,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        bot_member = await self.get_bot_member(
            interaction
        )

        if bot_member is None:
            await interaction.response.send_message(
                "❌ Nem sikerült lekérni a bot szervertagját.",
                ephemeral=True,
            )
            return

        bio_text = await get_guild_setting(
            guild_id=guild.id,
            setting_key="bot_profile_bio",
        )

        embed = discord.Embed(
            title="🤖 Bot szerverprofil",
            description=(
                f"A bot profilja a(z) **{guild.name}** szerveren."
            ),
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )

        embed.set_thumbnail(
            url=bot_member.display_avatar.url
        )

        embed.add_field(
            name="Szervernév",
            value=(
                bot_member.nick
                or "Nincs külön szervernév"
            ),
            inline=False,
        )

        embed.add_field(
            name="Külön profilkép",
            value=(
                "✅ Beállítva"
                if bot_member.guild_avatar is not None
                else "❌ Nincs beállítva"
            ),
            inline=True,
        )

        embed.add_field(
            name="Külön banner",
            value=(
                "✅ Beállítva"
                if bot_member.guild_banner is not None
                else "❌ Nincs beállítva"
            ),
            inline=True,
        )

        embed.add_field(
            name="Bemutatkozás",
            value=(
                bio_text
                or "Nincs külön bemutatkozás"
            ),
            inline=False,
        )

        if bot_member.guild_banner is not None:
            embed.set_image(
                url=bot_member.guild_banner.url
            )

        embed.set_footer(
            text=f"Szerverazonosító: {guild.id}"
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
            app_commands.CheckFailure,
        ):
            return

        original_error = getattr(
            error,
            "original",
            error,
        )

        print(
            "Botprofil rendszer hibája:",
            repr(original_error),
        )

        await self.send_error(
            interaction,
            "❌ Hiba történt a botprofil kezelése közben.",
        )


async def setup(
    bot: commands.Bot,
) -> None:
    await bot.add_cog(
        BotProfile(bot)
    )