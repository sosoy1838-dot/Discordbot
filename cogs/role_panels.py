import discord
from discord import app_commands
from discord.ext import commands

from database.db import (
    add_role_panel_button,
    create_role_panel,
    delete_role_panel,
    get_all_role_panels,
    get_guild_role_panels,
    get_role_panel,
    get_role_panel_buttons,
    remove_role_panel_button,
)

from views.role_panel import (
    RolePanelView,
    RoleToggleButton,
    role_has_dangerous_permissions,
)
from utils.bot_permissions import (
    is_bot_manager,
    send_manager_denied,
)


def build_panel_embed(
    guild: discord.Guild,
    panel: dict,
    buttons: list[dict],
) -> discord.Embed:
    """
    Elkészíti a rangpanel megjelenését.
    """

    embed = discord.Embed(
        title=str(panel["title"]),
        description=str(panel["description"]),
        color=discord.Color.blurple(),
    )

    if not buttons:
        roles_text = (
            "Ehhez a panelhez még nincs rang hozzáadva."
        )

    else:
        role_lines: list[str] = []

        for button in buttons:
            role_id = int(button["role_id"])
            role = guild.get_role(role_id)

            emoji = button["emoji"]
            emoji_text = (
                f"{emoji} "
                if emoji is not None
                else ""
            )

            if role is None:
                role_text = (
                    f"Törölt rang (`{role_id}`)"
                )
            else:
                role_text = role.mention

            role_lines.append(
                f"{emoji_text}**{button['label']}** → "
                f"{role_text}"
            )

        roles_text = "\n".join(role_lines)

    embed.add_field(
        name="🎭 Választható rangok",
        value=roles_text,
        inline=False,
    )

    embed.set_footer(
        text=(
            f"Panel ID: {panel['id']} • "
            "Nyomd meg újra a gombot a rang levételéhez."
        )
    )

    return embed


async def refresh_panel_message(
    guild: discord.Guild,
    panel: dict,
) -> tuple[bool, str]:
    """
    Frissíti a panel üzenetét és a rajta lévő gombokat.
    """

    channel = guild.get_channel(
        int(panel["channel_id"])
    )

    if not isinstance(
        channel,
        discord.TextChannel,
    ):
        return False, "A panel csatornája nem található."

    try:
        message = await channel.fetch_message(
            int(panel["message_id"])
        )

    except discord.NotFound:
        return False, "A panel üzenetét törölték."

    except discord.Forbidden:
        return False, (
            "A bot nem fér hozzá a panel üzenetéhez."
        )

    except discord.HTTPException:
        return False, (
            "Discord API-hiba történt az üzenet lekérésekor."
        )

    buttons = await get_role_panel_buttons(
        int(panel["id"])
    )

    embed = build_panel_embed(
        guild=guild,
        panel=panel,
        buttons=buttons,
    )

    view: RolePanelView | None

    if buttons:
        view = RolePanelView(
            panel_id=int(panel["id"]),
            buttons=buttons,
        )
    else:
        view = None

    try:
        await message.edit(
            embed=embed,
            view=view,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    except discord.Forbidden:
        return False, (
            "A bot nem szerkesztheti a panel üzenetét."
        )

    except discord.HTTPException:
        return False, (
            "Discord API-hiba történt a panel frissítésekor."
        )

    return True, "A panel frissítve."


@app_commands.guild_only()
class RolePanels(
    commands.GroupCog,
    group_name="rolepanel",
    group_description="Gombos rangválasztó panelek kezelése.",
):
    """
    Gombos rangpanel létrehozása és kezelése.
    """

    def __init__(
        self,
        bot: commands.Bot,
    ) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        """
        A bot indulásakor visszatölti az összes
        tartós rangpanel gombjait.
        """

        panels = await get_all_role_panels()
        restored_panels = 0

        for panel in panels:
            buttons = await get_role_panel_buttons(
                int(panel["id"])
            )

            if not buttons:
                continue

            view = RolePanelView(
                panel_id=int(panel["id"]),
                buttons=buttons,
            )

            try:
                self.bot.add_view(
                    view,
                    message_id=int(panel["message_id"]),
                )

                restored_panels += 1

            except ValueError:
                continue

        print(
            f"{restored_panels} rangpanel visszatöltve."
        )

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
            """
            A rangpanelek kezelése csak botkezelőknek engedélyezett.
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
    # /rolepanel create
    # --------------------------------------------------

    @app_commands.command(
        name="create",
        description="Új gombos rangpanel létrehozása.",
    )
    @app_commands.describe(
        channel="A csatorna, ahová a panel kerüljön.",
        cim="A rangpanel címe.",
        leiras="A panel rövid leírása.",
    )
    async def create(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        cim: str,
        leiras: str,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        title = cim.strip()
        description = leiras.strip()

        if not title or len(title) > 256:
            await interaction.response.send_message(
                "❌ A cím 1–256 karakter hosszú lehet.",
                ephemeral=True,
            )
            return

        if not description or len(description) > 3500:
            await interaction.response.send_message(
                "❌ A leírás 1–3500 karakter hosszú lehet.",
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

        permissions = channel.permissions_for(
            bot_member
        )

        required_permissions = (
            permissions.view_channel
            and permissions.send_messages
            and permissions.embed_links
            and permissions.read_message_history
        )

        if not required_permissions:
            await interaction.response.send_message(
                "❌ A botnak a kiválasztott csatornában "
                "szüksége van ezekre:\n"
                "• Csatorna megtekintése\n"
                "• Üzenetek küldése\n"
                "• Hivatkozások beágyazása\n"
                "• Üzenetelőzmények visszaolvasása",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        placeholder_embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blurple(),
        )

        placeholder_embed.add_field(
            name="🎭 Választható rangok",
            value=(
                "Ehhez a panelhez még nincs rang hozzáadva."
            ),
            inline=False,
        )

        try:
            message = await channel.send(
                embed=placeholder_embed,
                allowed_mentions=discord.AllowedMentions.none(),
            )

        except (discord.Forbidden, discord.HTTPException):
            await interaction.followup.send(
                "❌ Nem sikerült elküldeni a panel üzenetét.",
                ephemeral=True,
            )
            return

        try:
            panel_id = await create_role_panel(
                guild_id=guild.id,
                channel_id=channel.id,
                message_id=message.id,
                title=title,
                description=description,
                created_by=interaction.user.id,
            )

        except Exception:
            try:
                await message.delete()
            except discord.HTTPException:
                pass

            raise

        panel = await get_role_panel(
            guild_id=guild.id,
            panel_id=panel_id,
        )

        if panel is not None:
            await message.edit(
                embed=build_panel_embed(
                    guild=guild,
                    panel=panel,
                    buttons=[],
                )
            )

        await interaction.followup.send(
            (
                f"✅ Rangpanel létrehozva.\n"
                f"**Panel ID:** `{panel_id}`\n"
                f"**Csatorna:** {channel.mention}\n"
                f"[Ugrás a panelhez]({message.jump_url})"
            ),
            ephemeral=True,
        )

    # --------------------------------------------------
    # /rolepanel add
    # --------------------------------------------------

    @app_commands.command(
        name="add",
        description="Ranggomb hozzáadása egy panelhez.",
    )
    @app_commands.describe(
        panel_id="A panel azonosítója.",
        role="A gombbal kiosztható rang.",
        label="A gomb felirata. Üresen a rang neve.",
        emoji="Egy emoji, például 🎮.",
        stilus="A gomb színe.",
    )
    @app_commands.choices(
        stilus=[
            app_commands.Choice(
                name="Szürke",
                value=2,
            ),
            app_commands.Choice(
                name="Kék",
                value=1,
            ),
            app_commands.Choice(
                name="Zöld",
                value=3,
            ),
            app_commands.Choice(
                name="Piros",
                value=4,
            ),
        ]
    )
    async def add(
        self,
        interaction: discord.Interaction,
        panel_id: int,
        role: discord.Role,
        label: str | None = None,
        emoji: str | None = None,
        stilus: app_commands.Choice[int] | None = None,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        panel = await get_role_panel(
            guild_id=guild.id,
            panel_id=panel_id,
        )

        if panel is None:
            await interaction.response.send_message(
                "❌ Ezen a szerveren nincs ilyen panel.",
                ephemeral=True,
            )
            return

        if role.is_default():
            await interaction.response.send_message(
                "❌ Az @everyone rang nem adható a panelhez.",
                ephemeral=True,
            )
            return

        if role.managed:
            await interaction.response.send_message(
                "❌ Bothoz vagy integrációhoz tartozó "
                "rang nem választható.",
                ephemeral=True,
            )
            return

        if role_has_dangerous_permissions(role):
            await interaction.response.send_message(
                "❌ Biztonsági okból moderátori vagy "
                "rendszergazdai jogosultságú rang "
                "nem adható rangpanelhez.",
                ephemeral=True,
            )
            return

        bot_member = guild.me

        if bot_member is None:
            return

        if role >= bot_member.top_role:
            await interaction.response.send_message(
                "❌ Húzd a bot rangját a kiválasztott "
                "rang fölé.",
                ephemeral=True,
            )
            return

        button_label = (
            label.strip()
            if label is not None
            else role.name
        )

        if not button_label or len(button_label) > 80:
            await interaction.response.send_message(
                "❌ A gomb felirata 1–80 karakter lehet.",
                ephemeral=True,
            )
            return

        cleaned_emoji = (
            emoji.strip()
            if emoji is not None and emoji.strip()
            else None
        )

        style_value = (
            stilus.value
            if stilus is not None
            else 2
        )

        try:
            RoleToggleButton(
                panel_id=panel_id,
                role_id=role.id,
                label=button_label,
                emoji=cleaned_emoji,
                style=style_value,
                position=0,
            )

        except (TypeError, ValueError):
            await interaction.response.send_message(
                "❌ Az emoji vagy a gomb beállítása érvénytelen.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        try:
            added = await add_role_panel_button(
                panel_id=panel_id,
                role_id=role.id,
                label=button_label,
                emoji=cleaned_emoji,
                style=style_value,
            )

        except ValueError as error:
            await interaction.followup.send(
                f"❌ {error}",
                ephemeral=True,
            )
            return

        if not added:
            await interaction.followup.send(
                "ℹ️ Ez a rang már szerepel a panelen.",
                ephemeral=True,
            )
            return

        success, message = await refresh_panel_message(
            guild=guild,
            panel=panel,
        )

        if not success:
            await remove_role_panel_button(
                panel_id=panel_id,
                role_id=role.id,
            )

            await interaction.followup.send(
                f"❌ {message}",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            (
                f"✅ A(z) **{role.name}** rang "
                f"hozzáadva a(z) `{panel_id}` panelhez."
            ),
            ephemeral=True,
        )

    # --------------------------------------------------
    # /rolepanel remove
    # --------------------------------------------------

    @app_commands.command(
        name="remove",
        description="Ranggomb eltávolítása egy panelről.",
    )
    @app_commands.describe(
        panel_id="A panel azonosítója.",
        role="Az eltávolítandó rang.",
    )
    async def remove(
        self,
        interaction: discord.Interaction,
        panel_id: int,
        role: discord.Role,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        panel = await get_role_panel(
            guild_id=guild.id,
            panel_id=panel_id,
        )

        if panel is None:
            await interaction.response.send_message(
                "❌ Ezen a szerveren nincs ilyen panel.",
                ephemeral=True,
            )
            return

        current_buttons = await get_role_panel_buttons(
            panel_id
        )

        previous_button = next(
            (
                button
                for button in current_buttons
                if int(button["role_id"]) == role.id
            ),
            None,
        )

        if previous_button is None:
            await interaction.response.send_message(
                "ℹ️ Ez a rang nincs a panelhez adva.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        await remove_role_panel_button(
            panel_id=panel_id,
            role_id=role.id,
        )

        success, message = await refresh_panel_message(
            guild=guild,
            panel=panel,
        )

        if not success:
            await add_role_panel_button(
                panel_id=panel_id,
                role_id=role.id,
                label=str(previous_button["label"]),
                emoji=(
                    str(previous_button["emoji"])
                    if previous_button["emoji"] is not None
                    else None
                ),
                style=int(previous_button["style"]),
            )

            await interaction.followup.send(
                f"❌ {message}",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            (
                f"✅ A(z) **{role.name}** rang "
                "eltávolítva a panelről."
            ),
            ephemeral=True,
        )

    # --------------------------------------------------
    # /rolepanel list
    # --------------------------------------------------

    @app_commands.command(
        name="list",
        description="Megmutatja a szerver rangpaneljeit.",
    )
    async def list_panels(
        self,
        interaction: discord.Interaction,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        panels = await get_guild_role_panels(
            guild.id
        )

        if not panels:
            await interaction.response.send_message(
                "ℹ️ Ezen a szerveren még nincs rangpanel.",
                ephemeral=True,
            )
            return

        panel_lines: list[str] = []

        for panel in panels[:20]:
            channel = guild.get_channel(
                int(panel["channel_id"])
            )

            channel_text = (
                channel.mention
                if channel is not None
                else "Törölt csatorna"
            )

            panel_lines.append(
                f"• `{panel['id']}` — "
                f"**{panel['title']}** — "
                f"{channel_text}"
            )

        embed = discord.Embed(
            title="🎭 Rangpanelek",
            description="\n".join(panel_lines),
            color=discord.Color.blurple(),
        )

        if len(panels) > 20:
            embed.set_footer(
                text=(
                    f"Összesen {len(panels)} panel van. "
                    "Az első 20 látható."
                )
            )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    # --------------------------------------------------
    # /rolepanel delete
    # --------------------------------------------------

    @app_commands.command(
        name="delete",
        description="Töröl egy teljes rangpanelt.",
    )
    @app_commands.describe(
        panel_id="A törlendő panel azonosítója.",
    )
    async def delete(
        self,
        interaction: discord.Interaction,
        panel_id: int,
    ) -> None:
        guild = interaction.guild

        if guild is None:
            return

        panel = await get_role_panel(
            guild_id=guild.id,
            panel_id=panel_id,
        )

        if panel is None:
            await interaction.response.send_message(
                "❌ Ezen a szerveren nincs ilyen panel.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        channel = guild.get_channel(
            int(panel["channel_id"])
        )

        if isinstance(channel, discord.TextChannel):
            try:
                message = await channel.fetch_message(
                    int(panel["message_id"])
                )

                await message.delete()

            except discord.NotFound:
                pass

            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ A bot nem törölheti a panel üzenetét.",
                    ephemeral=True,
                )
                return

            except discord.HTTPException:
                await interaction.followup.send(
                    "❌ Discord API-hiba történt.",
                    ephemeral=True,
                )
                return

        deleted = await delete_role_panel(
            guild_id=guild.id,
            panel_id=panel_id,
        )

        if not deleted:
            await interaction.followup.send(
                "❌ Nem sikerült törölni a panelt.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            f"✅ A(z) `{panel_id}` rangpanel törölve.",
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
                "❌ A rangpanelek kezeléséhez "
                "Rangok kezelése jogosultság szükséges.",
            )
            return

        original_error = getattr(
            error,
            "original",
            error,
        )

        print(
            "Rangpanel rendszer hibája:",
            repr(original_error),
        )

        await self.send_error(
            interaction,
            "❌ Hiba történt a rangpanel kezelése közben.",
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RolePanels(bot))