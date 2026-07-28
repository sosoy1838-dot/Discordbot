import platform
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands


def format_yes_no(value: bool) -> str:
    return "✅ Igen" if value else "❌ Nem"


def format_uptime(duration: timedelta) -> str:
    """
    Olvasható működési időt készít.
    """

    total_seconds = max(
        0,
        int(duration.total_seconds()),
    )

    days, remainder = divmod(
        total_seconds,
        86400,
    )

    hours, remainder = divmod(
        remainder,
        3600,
    )

    minutes, seconds = divmod(
        remainder,
        60,
    )

    parts: list[str] = []

    if days:
        parts.append(f"{days} nap")

    if hours:
        parts.append(f"{hours} óra")

    if minutes:
        parts.append(f"{minutes} perc")

    if seconds or not parts:
        parts.append(f"{seconds} másodperc")

    return ", ".join(parts)


def split_help_lines(
    lines: list[str],
    maximum_length: int = 1000,
) -> list[str]:
    """
    A parancslistát több embedmezőre bontja,
    hogy ne lépje túl a Discord korlátját.
    """

    chunks: list[str] = []
    current_lines: list[str] = []
    current_length = 0

    for line in lines:
        added_length = len(line) + 1

        if (
            current_lines
            and current_length + added_length
            > maximum_length
        ):
            chunks.append(
                "\n".join(current_lines)
            )

            current_lines = []
            current_length = 0

        current_lines.append(line)
        current_length += added_length

    if current_lines:
        chunks.append(
            "\n".join(current_lines)
        )

    return chunks


def collect_command_lines(
    command: app_commands.Command
    | app_commands.Group,
) -> list[str]:
    """
    Egy parancsból vagy parancscsoportból
    összegyűjti az összes végrehajtható parancsot.
    """

    if isinstance(
        command,
        app_commands.Group,
    ):
        lines: list[str] = []

        for child_command in sorted(
            command.commands,
            key=lambda item: item.name,
        ):
            lines.extend(
                collect_command_lines(
                    child_command
                )
            )

        return lines

    description = (
        command.description
        or "Nincs leírás."
    )

    return [
        (
            f"`/{command.qualified_name}`\n"
            f"↳ {description}"
        )
    ]


def count_commands(
    commands_list: list[
        app_commands.Command
        | app_commands.Group
    ],
) -> int:
    """
    Megszámolja a tényleges slash parancsokat.
    """

    total = 0

    for command in commands_list:
        if isinstance(
            command,
            app_commands.Group,
        ):
            total += count_commands(
                list(command.commands)
            )
        else:
            total += 1

    return total


class InformationCommands(
    commands.Cog,
):
    def __init__(
        self,
        bot: commands.Bot,
    ) -> None:
        self.bot = bot
        self.started_at = discord.utils.utcnow()

    # --------------------------------------------------
    # /help
    # --------------------------------------------------

    @app_commands.command(
        name="help",
        description="Megmutatja a bot parancsait.",
    )
    @app_commands.guild_only()
    async def help_command(
        self,
        interaction: discord.Interaction,
    ) -> None:
        top_level_commands = sorted(
            self.bot.tree.get_commands(),
            key=lambda command: command.name,
        )

        embed = discord.Embed(
            title="📘 Bot parancsok",
            description=(
                "Az alábbi parancsok érhetők el ezen a boton.\n"
                "A kezelőparancsok csak megfelelő "
                "jogosultsággal használhatók."
            ),
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )

        standalone_lines: list[str] = []
        fields_added = 0

        for command in top_level_commands:
            if isinstance(
                command,
                app_commands.Group,
            ):
                command_lines = collect_command_lines(
                    command
                )

                chunks = split_help_lines(
                    command_lines
                )

                for chunk_index, chunk in enumerate(
                    chunks,
                    start=1,
                ):
                    if fields_added >= 24:
                        break

                    field_name = (
                        f"📂 /{command.name}"
                        if chunk_index == 1
                        else (
                            f"📂 /{command.name} "
                            f"– folytatás"
                        )
                    )

                    embed.add_field(
                        name=field_name,
                        value=chunk,
                        inline=False,
                    )

                    fields_added += 1

            else:
                standalone_lines.extend(
                    collect_command_lines(
                        command
                    )
                )

        if standalone_lines and fields_added < 25:
            standalone_chunks = split_help_lines(
                standalone_lines
            )

            for chunk_index, chunk in enumerate(
                standalone_chunks,
                start=1,
            ):
                if fields_added >= 25:
                    break

                field_name = (
                    "⚙️ Általános parancsok"
                    if chunk_index == 1
                    else "⚙️ Általános – folytatás"
                )

                embed.add_field(
                    name=field_name,
                    value=chunk,
                    inline=False,
                )

                fields_added += 1

        total_commands = count_commands(
            list(top_level_commands)
        )

        embed.set_footer(
            text=(
                f"Összesen {total_commands} slash parancs"
            )
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # /userinfo
    # --------------------------------------------------

    @app_commands.command(
        name="userinfo",
        description="Információkat mutat egy szervertagról.",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        member=(
            "A megtekintendő tag. "
            "Üresen hagyva saját magadat mutatja."
        ),
    )
    async def userinfo(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        target = member

        if target is None:
            if not isinstance(
                interaction.user,
                discord.Member,
            ):
                return

            target = interaction.user

        roles = [
            role
            for role in reversed(target.roles)
            if not role.is_default()
        ]

        role_mentions = [
            role.mention
            for role in roles[:15]
        ]

        if len(roles) > 15:
            role_mentions.append(
                f"… és még {len(roles) - 15} rang"
            )

        embed = discord.Embed(
            title=f"👤 {target.display_name}",
            description=target.mention,
            color=(
                target.color
                if target.color.value != 0
                else discord.Color.blurple()
            ),
            timestamp=discord.utils.utcnow(),
        )

        embed.set_thumbnail(
            url=target.display_avatar.url
        )

        embed.add_field(
            name="Felhasználónév",
            value=f"`{target}`",
            inline=True,
        )

        embed.add_field(
            name="Azonosító",
            value=f"`{target.id}`",
            inline=True,
        )

        embed.add_field(
            name="Botfiók",
            value=format_yes_no(target.bot),
            inline=True,
        )

        embed.add_field(
            name="Fiók létrehozva",
            value=(
                f"{discord.utils.format_dt(target.created_at, 'F')}\n"
                f"({discord.utils.format_dt(target.created_at, 'R')})"
            ),
            inline=False,
        )

        if target.joined_at is not None:
            embed.add_field(
                name="Csatlakozott a szerverhez",
                value=(
                    f"{discord.utils.format_dt(target.joined_at, 'F')}\n"
                    f"({discord.utils.format_dt(target.joined_at, 'R')})"
                ),
                inline=False,
            )

        embed.add_field(
            name="Legmagasabb rang",
            value=target.top_role.mention,
            inline=True,
        )

        embed.add_field(
            name="Rangok száma",
            value=str(len(roles)),
            inline=True,
        )

        if target.premium_since is not None:
            embed.add_field(
                name="Szerverkiemelés kezdete",
                value=discord.utils.format_dt(
                    target.premium_since,
                    "R",
                ),
                inline=True,
            )

        embed.add_field(
            name="Rangok",
            value=(
                " ".join(role_mentions)[:1024]
                if role_mentions
                else "Nincs külön rangja"
            ),
            inline=False,
        )

        embed.set_footer(
            text=(
                f"Lekérte: {interaction.user}"
            )
        )

        await interaction.response.send_message(
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # /serverinfo
    # --------------------------------------------------

    @app_commands.command(
        name="serverinfo",
        description="Információkat mutat a szerverről.",
    )
    @app_commands.guild_only()
    async def serverinfo(
        self,
        interaction: discord.Interaction,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        owner_text = (
            guild.owner.mention
            if guild.owner is not None
            else f"<@{guild.owner_id}>"
        )

        member_count = (
            guild.member_count
            if guild.member_count is not None
            else len(guild.members)
        )

        verification_names = {
            "none": "Nincs",
            "low": "Alacsony",
            "medium": "Közepes",
            "high": "Magas",
            "highest": "Legmagasabb",
        }

        verification_level = (
            verification_names.get(
                guild.verification_level.name,
                guild.verification_level.name,
            )
        )

        premium_tier = int(guild.premium_tier)

        embed = discord.Embed(
            title=f"🏠 {guild.name}",
            description=(
                guild.description
                or "Nincs szerverleírás."
            ),
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )

        if guild.icon is not None:
            embed.set_thumbnail(
                url=guild.icon.url
            )

        if guild.banner is not None:
            embed.set_image(
                url=guild.banner.url
            )

        embed.add_field(
            name="Tulajdonos",
            value=owner_text,
            inline=True,
        )

        embed.add_field(
            name="Szerverazonosító",
            value=f"`{guild.id}`",
            inline=True,
        )

        embed.add_field(
            name="Tagok",
            value=str(member_count),
            inline=True,
        )

        embed.add_field(
            name="Szöveges csatornák",
            value=str(
                len(guild.text_channels)
            ),
            inline=True,
        )

        embed.add_field(
            name="Hangcsatornák",
            value=str(
                len(guild.voice_channels)
            ),
            inline=True,
        )

        embed.add_field(
            name="Kategóriák",
            value=str(
                len(guild.categories)
            ),
            inline=True,
        )

        embed.add_field(
            name="Rangok",
            value=str(
                len(guild.roles)
            ),
            inline=True,
        )

        embed.add_field(
            name="Emojik",
            value=str(
                len(guild.emojis)
            ),
            inline=True,
        )

        embed.add_field(
            name="Matricák",
            value=str(
                len(guild.stickers)
            ),
            inline=True,
        )

        embed.add_field(
            name="Boostszint",
            value=f"{premium_tier}. szint",
            inline=True,
        )

        embed.add_field(
            name="Boostok",
            value=str(
                guild.premium_subscription_count
            ),
            inline=True,
        )

        embed.add_field(
            name="Ellenőrzési szint",
            value=verification_level,
            inline=True,
        )

        embed.add_field(
            name="Szerver létrehozva",
            value=(
                f"{discord.utils.format_dt(guild.created_at, 'F')}\n"
                f"({discord.utils.format_dt(guild.created_at, 'R')})"
            ),
            inline=False,
        )

        if guild.system_channel is not None:
            embed.add_field(
                name="Rendszercsatorna",
                value=guild.system_channel.mention,
                inline=False,
            )

        await interaction.response.send_message(
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # /avatar
    # --------------------------------------------------

    @app_commands.command(
        name="avatar",
        description="Megmutatja egy tag profilképét.",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        member=(
            "A megtekintendő tag. "
            "Üresen hagyva saját magadat mutatja."
        ),
    )
    async def avatar(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        target = member

        if target is None:
            if not isinstance(
                interaction.user,
                discord.Member,
            ):
                return

            target = interaction.user

        avatar_url = (
            target.display_avatar
            .with_size(1024)
            .url
        )

        embed = discord.Embed(
            title=(
                f"🖼️ {target.display_name} profilképe"
            ),
            color=(
                target.color
                if target.color.value != 0
                else discord.Color.blurple()
            ),
            timestamp=discord.utils.utcnow(),
        )

        embed.set_image(
            url=avatar_url
        )

        embed.set_footer(
            text=f"Felhasználóazonosító: {target.id}"
        )

        view = discord.ui.View()

        view.add_item(
            discord.ui.Button(
                label="Profilkép megnyitása",
                emoji="🔗",
                url=avatar_url,
            )
        )

        await interaction.response.send_message(
            embed=embed,
            view=view,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # /roleinfo
    # --------------------------------------------------

    @app_commands.command(
        name="roleinfo",
        description="Információkat mutat egy rangról.",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        role="A megtekintendő rang.",
    )
    async def roleinfo(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        enabled_permissions = sum(
            1
            for _, enabled in role.permissions
            if enabled
        )

        member_mentions = [
            member.mention
            for member in role.members[:15]
        ]

        if len(role.members) > 15:
            member_mentions.append(
                (
                    f"… és még "
                    f"{len(role.members) - 15} tag"
                )
            )

        embed = discord.Embed(
            title=f"🏷️ {role.name}",
            description=role.mention,
            color=(
                role.color
                if role.color.value != 0
                else discord.Color.blurple()
            ),
            timestamp=discord.utils.utcnow(),
        )

        role_icon = role.display_icon

        if isinstance(
            role_icon,
            discord.Asset,
        ):
            embed.set_thumbnail(
                url=role_icon.url
            )

        embed.add_field(
            name="Azonosító",
            value=f"`{role.id}`",
            inline=True,
        )

        embed.add_field(
            name="Szín",
            value=f"`{str(role.color)}`",
            inline=True,
        )

        embed.add_field(
            name="Pozíció",
            value=str(role.position),
            inline=True,
        )

        embed.add_field(
            name="Tagok száma",
            value=str(len(role.members)),
            inline=True,
        )

        embed.add_field(
            name="Engedélyek száma",
            value=str(enabled_permissions),
            inline=True,
        )

        embed.add_field(
            name="Külön megjelenítve",
            value=format_yes_no(role.hoist),
            inline=True,
        )

        embed.add_field(
            name="Megemlíthető",
            value=format_yes_no(
                role.mentionable
            ),
            inline=True,
        )

        embed.add_field(
            name="Discord által kezelt",
            value=format_yes_no(role.managed),
            inline=True,
        )

        embed.add_field(
            name="@everyone rang",
            value=format_yes_no(
                role.is_default()
            ),
            inline=True,
        )

        embed.add_field(
            name="Létrehozva",
            value=(
                f"{discord.utils.format_dt(role.created_at, 'F')}\n"
                f"({discord.utils.format_dt(role.created_at, 'R')})"
            ),
            inline=False,
        )

        embed.add_field(
            name="Ranggal rendelkező tagok",
            value=(
                " ".join(member_mentions)[:1024]
                if member_mentions
                else "Jelenleg senki"
            ),
            inline=False,
        )

        await interaction.response.send_message(
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # /botinfo
    # --------------------------------------------------

    @app_commands.command(
        name="botinfo",
        description="Információkat mutat a botról.",
    )
    @app_commands.guild_only()
    async def botinfo(
        self,
        interaction: discord.Interaction,
    ) -> None:
        bot_user = self.bot.user

        if bot_user is None:
            await interaction.response.send_message(
                "❌ A bot adatai még nem érhetők el.",
                ephemeral=True,
            )
            return

        uptime = (
            discord.utils.utcnow()
            - self.started_at
        )

        guild_count = len(
            self.bot.guilds
        )

        total_members = sum(
            (
                guild.member_count
                if guild.member_count is not None
                else len(guild.members)
            )
            for guild in self.bot.guilds
        )

        application_commands = (
            self.bot.tree.get_commands()
        )

        command_count = count_commands(
            list(application_commands)
        )

        latency_ms = round(
            self.bot.latency * 1000
        )

        embed = discord.Embed(
            title=f"🤖 {bot_user.display_name}",
            description=(
                "Moduláris Discord szerverkezelő bot."
            ),
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )

        embed.set_thumbnail(
            url=bot_user.display_avatar.url
        )

        embed.add_field(
            name="Botazonosító",
            value=f"`{bot_user.id}`",
            inline=True,
        )

        embed.add_field(
            name="Késleltetés",
            value=f"`{latency_ms} ms`",
            inline=True,
        )

        embed.add_field(
            name="Működési idő",
            value=format_uptime(uptime),
            inline=False,
        )

        embed.add_field(
            name="Szerverek",
            value=str(guild_count),
            inline=True,
        )

        embed.add_field(
            name="Összes tag",
            value=str(total_members),
            inline=True,
        )

        embed.add_field(
            name="Betöltött modulok",
            value=str(len(self.bot.cogs)),
            inline=True,
        )

        embed.add_field(
            name="Slash parancsok",
            value=str(command_count),
            inline=True,
        )

        embed.add_field(
            name="Python",
            value=f"`{platform.python_version()}`",
            inline=True,
        )

        embed.add_field(
            name="discord.py",
            value=f"`{discord.__version__}`",
            inline=True,
        )

        embed.add_field(
            name="Botfiók létrehozva",
            value=(
                f"{discord.utils.format_dt(bot_user.created_at, 'F')}\n"
                f"({discord.utils.format_dt(bot_user.created_at, 'R')})"
            ),
            inline=False,
        )

        await interaction.response.send_message(
            embed=embed,
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
        original_error = getattr(
            error,
            "original",
            error,
        )

        print(
            "Információs parancs hiba:",
            repr(original_error),
        )

        error_message = (
            "❌ Hiba történt az adatok lekérése közben."
        )

        if interaction.response.is_done():
            await interaction.followup.send(
                error_message,
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                error_message,
                ephemeral=True,
            )


async def setup(
    bot: commands.Bot,
) -> None:
    await bot.add_cog(
        InformationCommands(bot)
    )