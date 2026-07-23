import discord
from discord import app_commands
from discord.ext import commands

from database.db import (
    get_guild_setting,
    get_staff_roles,
    set_guild_setting,
)

from utils.bot_permissions import (
    is_bot_manager,
    send_manager_denied,
)

from views.tickets import (
    TicketControlView,
    TicketOpenView,
)


@app_commands.guild_only()
class TicketPanel(
    commands.GroupCog,
    group_name="ticketpanel",
    group_description="A ticketnyitó panel kezelése.",
):
    """
    Ticketpanel létrehozása és törlése.
    """

    def __init__(
        self,
        bot: commands.Bot,
    ) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        """
        Újraindítás után visszaregisztrálja
        az állandó ticketgombokat.
        """

        self.bot.add_view(
            TicketOpenView(self.bot)
        )

        self.bot.add_view(
            TicketControlView(self.bot)
        )

        print("Ticket gombok visszatöltve.")

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

    # --------------------------------------------------
    # /ticketpanel create
    # --------------------------------------------------

    @app_commands.command(
        name="create",
        description="Ticketnyitó panel létrehozása.",
    )
    @app_commands.describe(
        channel="A csatorna, ahová a ticketpanel kerüljön.",
        cim="A ticketpanel címe.",
        leiras="A ticketpanel leírása.",
    )
    async def create(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        cim: str = "Ügyfélszolgálat",
        leiras: str = (
            "Segítségre van szükséged?\n"
            "Nyomd meg az alábbi gombot egy privát ticket nyitásához."
        ),
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        category_id = await get_guild_setting(
            guild.id,
            "ticket_category_id",
        )

        if category_id is None:
            await interaction.response.send_message(
                "❌ Először állítsd be a ticketkategóriát:\n"
                "`/config ticket-category`",
                ephemeral=True,
            )
            return

        staff_roles = await get_staff_roles(guild.id)

        if not staff_roles:
            await interaction.response.send_message(
                "❌ Nincs staffrang beállítva.\n"
                "Használd: `/config staff-add`",
                ephemeral=True,
            )
            return

        bot_member = guild.me

        if bot_member is None:
            return

        permissions = channel.permissions_for(bot_member)

        if not (
            permissions.view_channel
            and permissions.send_messages
            and permissions.embed_links
        ):
            await interaction.response.send_message(
                "❌ A bot nem tud üzenetet küldeni ebbe a csatornába.",
                ephemeral=True,
            )
            return

        title = cim.strip()[:256]
        description = leiras.strip()[:3500]

        if not title or not description:
            await interaction.response.send_message(
                "❌ A cím és a leírás nem lehet üres.",
                ephemeral=True,
            )
            return

        old_channel_id = await get_guild_setting(
            guild.id,
            "ticket_panel_channel_id",
        )

        old_message_id = await get_guild_setting(
            guild.id,
            "ticket_panel_message_id",
        )

        if (
            old_channel_id is not None
            and old_message_id is not None
        ):
            try:
                old_channel = guild.get_channel(
                    int(old_channel_id)
                )

                if isinstance(
                    old_channel,
                    discord.TextChannel,
                ):
                    old_message = await old_channel.fetch_message(
                        int(old_message_id)
                    )

                    await old_message.delete()

            except (
                ValueError,
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException,
            ):
                pass

        panel_embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )

        panel_embed.add_field(
            name="🎫 Ticket nyitása",
            value=(
                "A ticketet csak te és a staff fogja látni.\n"
                "Egyszerre csak egy nyitott ticketed lehet."
            ),
            inline=False,
        )

        panel_embed.set_footer(
            text=f"Szerver: {guild.name}"
        )

        panel_message = await channel.send(
            embed=panel_embed,
            view=TicketOpenView(self.bot),
            allowed_mentions=discord.AllowedMentions.none(),
        )

        await set_guild_setting(
            guild.id,
            "ticket_panel_channel_id",
            str(channel.id),
        )

        await set_guild_setting(
            guild.id,
            "ticket_panel_message_id",
            str(panel_message.id),
        )

        await interaction.response.send_message(
            (
                "✅ Ticketpanel létrehozva.\n"
                f"[Ugrás a panelhez]({panel_message.jump_url})"
            ),
            ephemeral=True,
        )

    # --------------------------------------------------
    # /ticketpanel delete
    # --------------------------------------------------

    @app_commands.command(
        name="delete",
        description="Törli a beállított ticketpanelt.",
    )
    async def delete(
        self,
        interaction: discord.Interaction,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        channel_id = await get_guild_setting(
            guild.id,
            "ticket_panel_channel_id",
        )

        message_id = await get_guild_setting(
            guild.id,
            "ticket_panel_message_id",
        )

        if channel_id is None or message_id is None:
            await interaction.response.send_message(
                "ℹ️ Jelenleg nincs ticketpanel beállítva.",
                ephemeral=True,
            )
            return

        try:
            channel = guild.get_channel(
                int(channel_id)
            )

            if isinstance(
                channel,
                discord.TextChannel,
            ):
                message = await channel.fetch_message(
                    int(message_id)
                )

                await message.delete()

        except (
            ValueError,
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException,
        ):
            pass

        await set_guild_setting(
            guild.id,
            "ticket_panel_channel_id",
            None,
        )

        await set_guild_setting(
            guild.id,
            "ticket_panel_message_id",
            None,
        )

        await interaction.response.send_message(
            "✅ A ticketpanel törölve.",
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
        if isinstance(error, app_commands.CheckFailure):
            return

        original_error = getattr(
            error,
            "original",
            error,
        )

        print(
            "Ticketpanel rendszer hibája:",
            repr(original_error),
        )

        await self.send_error(
            interaction,
            "❌ Hiba történt a ticketpanel kezelése közben.",
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TicketPanel(bot))