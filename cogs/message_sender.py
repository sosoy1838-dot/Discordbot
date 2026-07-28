import importlib

import discord
from discord import app_commands
from discord.ext import commands

from data import message_templates

from utils.bot_permissions import (
    is_bot_manager,
    send_manager_denied,
)

from utils.logging_utils import send_log


def load_templates() -> dict:
    """
    Minden /send használatkor újra beolvassa
    a Python-fájlban tárolt sablonokat.
    """

    reloaded_module = importlib.reload(
        message_templates
    )

    templates = getattr(
        reloaded_module,
        "MESSAGE_TEMPLATES",
        {},
    )

    if not isinstance(templates, dict):
        raise ValueError(
            "A MESSAGE_TEMPLATES értékének szótárnak kell lennie."
        )

    return templates


def replace_placeholders(
    text: str,
    guild: discord.Guild,
    channel: discord.TextChannel,
    sender: discord.Member,
) -> str:
    """
    Egyszerű helyettesítések az üzenetsablonokban.
    """

    return (
        text
        .replace("{server}", guild.name)
        .replace("{channel}", channel.name)
        .replace("{sender}", sender.display_name)
    )


async def template_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """
    A /send sablonmezőjében megmutatja
    az elérhető sablonokat.
    """

    try:
        templates = load_templates()
    except Exception:
        return []

    current_lower = current.lower()

    matching_names = [
        str(template_name)
        for template_name in templates
        if current_lower in str(template_name).lower()
    ]

    return [
        app_commands.Choice(
            name=template_name,
            value=template_name,
        )
        for template_name in matching_names[:25]
    ]


class MessageSender(
    commands.Cog,
):
    def __init__(
        self,
        bot: commands.Bot,
    ) -> None:
        self.bot = bot

    async def manager_check(
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

    async def check_channel_permissions(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        embeds_required: bool,
    ) -> bool:
        guild = interaction.guild

        if guild is None:
            return False

        bot_member = guild.me

        if bot_member is None:
            await self.send_error(
                interaction,
                "❌ Nem sikerült lekérni a botot.",
            )
            return False

        permissions = channel.permissions_for(
            bot_member
        )

        required_permissions = (
            permissions.view_channel
            and permissions.send_messages
        )

        if embeds_required:
            required_permissions = (
                required_permissions
                and permissions.embed_links
            )

        if not required_permissions:
            await self.send_error(
                interaction,
                (
                    "❌ A botnak nincs megfelelő jogosultsága "
                    "a kiválasztott csatornában."
                ),
            )
            return False

        return True

    async def log_sent_message(
        self,
        guild: discord.Guild,
        sender: discord.Member,
        channel: discord.TextChannel,
        sent_message: discord.Message,
        message_type: str,
        content_preview: str,
    ) -> None:
        embed = discord.Embed(
            title="📤 Botüzenet elküldve",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )

        embed.add_field(
            name="Küldő",
            value=(
                f"{sender.mention}\n"
                f"`{sender.id}`"
            ),
            inline=True,
        )

        embed.add_field(
            name="Célcsatorna",
            value=channel.mention,
            inline=True,
        )

        embed.add_field(
            name="Típus",
            value=message_type,
            inline=True,
        )

        embed.add_field(
            name="Üzenetazonosító",
            value=f"`{sent_message.id}`",
            inline=False,
        )

        embed.add_field(
            name="Tartalom",
            value=content_preview[:1000] or "[Nincs tartalom]",
            inline=False,
        )

        embed.add_field(
            name="Ugrás az üzenethez",
            value=f"[Üzenet megnyitása]({sent_message.jump_url})",
            inline=False,
        )

        await send_log(
            guild=guild,
            embed=embed,
        )

    # --------------------------------------------------
    # /say
    # --------------------------------------------------

    @app_commands.command(
        name="say",
        description="Sima üzenetet küld a bot nevében.",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        channel="A csatorna, ahová az üzenet kerüljön.",
        message="A bot által elküldendő üzenet.",
    )
    async def say(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message: str,
    ) -> None:
        if not await self.manager_check(interaction):
            return

        guild = interaction.guild
        sender = interaction.user

        if guild is None or not isinstance(
            sender,
            discord.Member,
        ):
            return

        content = message.strip()

        if not content:
            await interaction.response.send_message(
                "❌ Az üzenet nem lehet üres.",
                ephemeral=True,
            )
            return

        if len(content) > 2000:
            await interaction.response.send_message(
                "❌ A sima üzenet legfeljebb 2000 karakter lehet.",
                ephemeral=True,
            )
            return

        if not await self.check_channel_permissions(
            interaction,
            channel,
            embeds_required=False,
        ):
            return

        await interaction.response.defer(
            ephemeral=True
        )

        try:
            sent_message = await channel.send(
                content,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            await interaction.followup.send(
                "❌ Nem sikerült elküldeni az üzenetet.",
                ephemeral=True,
            )
            return

        await self.log_sent_message(
            guild=guild,
            sender=sender,
            channel=channel,
            sent_message=sent_message,
            message_type="Sima üzenet",
            content_preview=content,
        )

        await interaction.followup.send(
            (
                "✅ Az üzenet elküldve.\n"
                f"[Ugrás az üzenethez]({sent_message.jump_url})"
            ),
            ephemeral=True,
        )

    # --------------------------------------------------
    # /announce
    # --------------------------------------------------

    @app_commands.command(
        name="announce",
        description="Embed bejelentést küld a bot nevében.",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        channel="A csatorna, ahová a bejelentés kerüljön.",
        title="A bejelentés címe.",
        message="A bejelentés szövege.",
    )
    async def announce(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str,
        message: str,
    ) -> None:
        if not await self.manager_check(interaction):
            return

        guild = interaction.guild
        sender = interaction.user

        if guild is None or not isinstance(
            sender,
            discord.Member,
        ):
            return

        clean_title = title.strip()
        clean_message = message.strip()

        if not clean_title or not clean_message:
            await interaction.response.send_message(
                "❌ A cím és az üzenet nem lehet üres.",
                ephemeral=True,
            )
            return

        if len(clean_title) > 256:
            await interaction.response.send_message(
                "❌ A cím legfeljebb 256 karakter lehet.",
                ephemeral=True,
            )
            return

        if len(clean_message) > 4096:
            await interaction.response.send_message(
                "❌ A bejelentés legfeljebb 4096 karakter lehet.",
                ephemeral=True,
            )
            return

        if not await self.check_channel_permissions(
            interaction,
            channel,
            embeds_required=True,
        ):
            return

        embed = discord.Embed(
            title=clean_title,
            description=clean_message,
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )

        embed.set_footer(
            text=guild.name
        )

        await interaction.response.defer(
            ephemeral=True
        )

        try:
            sent_message = await channel.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException:
            await interaction.followup.send(
                "❌ Nem sikerült elküldeni a bejelentést.",
                ephemeral=True,
            )
            return

        await self.log_sent_message(
            guild=guild,
            sender=sender,
            channel=channel,
            sent_message=sent_message,
            message_type="Embed bejelentés",
            content_preview=(
                f"{clean_title}\n{clean_message}"
            ),
        )

        await interaction.followup.send(
            (
                "✅ A bejelentés elküldve.\n"
                f"[Ugrás az üzenethez]({sent_message.jump_url})"
            ),
            ephemeral=True,
        )

    # --------------------------------------------------
    # /send
    # --------------------------------------------------

    @app_commands.command(
        name="send",
        description="Python-fájlban megírt sablont küld el.",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        channel="A csatorna, ahová a sablon kerüljön.",
        template="A message_templates.py fájlban lévő sablon neve.",
    )
    @app_commands.autocomplete(
        template=template_autocomplete
    )
    async def send_template(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        template: str = "alap",
    ) -> None:
        if not await self.manager_check(interaction):
            return

        guild = interaction.guild
        sender = interaction.user

        if guild is None or not isinstance(
            sender,
            discord.Member,
        ):
            return

        try:
            templates = load_templates()
        except Exception as error:
            print(
                "Üzenetsablon betöltési hiba:",
                repr(error),
            )

            await interaction.response.send_message(
                (
                    "❌ Nem sikerült beolvasni a "
                    "`data/message_templates.py` fájlt.\n"
                    "Ellenőrizd, hogy nincs-e benne Python-hiba."
                ),
                ephemeral=True,
            )
            return

        selected_template = templates.get(
            template
        )

        if not isinstance(
            selected_template,
            dict,
        ):
            await interaction.response.send_message(
                (
                    f"❌ Nem található ilyen sablon: `{template}`\n"
                    "Ellenőrizd a `MESSAGE_TEMPLATES` tartalmát."
                ),
                ephemeral=True,
            )
            return

        kind = str(
            selected_template.get(
                "kind",
                "embed",
            )
        ).lower()

        raw_message = str(
            selected_template.get(
                "message",
                "",
            )
        )

        rendered_message = replace_placeholders(
            raw_message,
            guild,
            channel,
            sender,
        ).strip()

        if not rendered_message:
            await interaction.response.send_message(
                "❌ A kiválasztott sablon üzenete üres.",
                ephemeral=True,
            )
            return

        if kind == "text":
            if len(rendered_message) > 2000:
                await interaction.response.send_message(
                    "❌ A sablon szövege hosszabb 2000 karakternél.",
                    ephemeral=True,
                )
                return

            if not await self.check_channel_permissions(
                interaction,
                channel,
                embeds_required=False,
            ):
                return

            await interaction.response.defer(
                ephemeral=True
            )

            try:
                sent_message = await channel.send(
                    rendered_message,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException:
                await interaction.followup.send(
                    "❌ Nem sikerült elküldeni a sablont.",
                    ephemeral=True,
                )
                return

        elif kind == "embed":
            raw_title = str(
                selected_template.get(
                    "title",
                    "📢 Bejelentés",
                )
            )

            raw_footer = str(
                selected_template.get(
                    "footer",
                    "",
                )
            )

            rendered_title = replace_placeholders(
                raw_title,
                guild,
                channel,
                sender,
            ).strip()[:256]

            rendered_footer = replace_placeholders(
                raw_footer,
                guild,
                channel,
                sender,
            ).strip()[:2048]

            if len(rendered_message) > 4096:
                await interaction.response.send_message(
                    "❌ A sablon leírása hosszabb 4096 karakternél.",
                    ephemeral=True,
                )
                return

            try:
                color_value = int(
                    selected_template.get(
                        "color",
                        0x5865F2,
                    )
                )
            except (TypeError, ValueError):
                color_value = 0x5865F2

            if not await self.check_channel_permissions(
                interaction,
                channel,
                embeds_required=True,
            ):
                return

            embed = discord.Embed(
                title=rendered_title,
                description=rendered_message,
                color=color_value,
                timestamp=discord.utils.utcnow(),
            )

            if rendered_footer:
                embed.set_footer(
                    text=rendered_footer
                )

            await interaction.response.defer(
                ephemeral=True
            )

            try:
                sent_message = await channel.send(
                    embed=embed,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException:
                await interaction.followup.send(
                    "❌ Nem sikerült elküldeni a sablont.",
                    ephemeral=True,
                )
                return

        else:
            await interaction.response.send_message(
                (
                    "❌ A sablon `kind` értéke csak "
                    "`text` vagy `embed` lehet."
                ),
                ephemeral=True,
            )
            return

        await self.log_sent_message(
            guild=guild,
            sender=sender,
            channel=channel,
            sent_message=sent_message,
            message_type=f"Python-sablon: {template}",
            content_preview=rendered_message,
        )

        await interaction.followup.send(
            (
                f"✅ A `{template}` sablon elküldve.\n"
                f"[Ugrás az üzenethez]({sent_message.jump_url})"
            ),
            ephemeral=True,
        )

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
            "Botüzenet rendszer hibája:",
            repr(original_error),
        )

        await self.send_error(
            interaction,
            "❌ Hiba történt az üzenet küldése közben.",
        )


async def setup(
    bot: commands.Bot,
) -> None:
    await bot.add_cog(
        MessageSender(bot)
    )