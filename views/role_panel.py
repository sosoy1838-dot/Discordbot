import discord

from database.db import (
    get_role_panel,
    get_role_panel_buttons,
)


def role_has_dangerous_permissions(
    role: discord.Role,
) -> bool:
    """
    Megakadályozza, hogy veszélyes jogosultságú rangot
    lehessen saját magunknak kiosztani.
    """

    permissions = role.permissions

    return any(
        (
            permissions.administrator,
            permissions.manage_guild,
            permissions.manage_roles,
            permissions.manage_channels,
            permissions.kick_members,
            permissions.ban_members,
            permissions.moderate_members,
            permissions.manage_messages,
            permissions.manage_webhooks,
            permissions.mention_everyone,
        )
    )


def parse_emoji(
    emoji: str | None,
) -> discord.PartialEmoji | None:
    """
    Unicode vagy Discord-emojit alakít át
    a gomb által használható formára.
    """

    if emoji is None:
        return None

    cleaned_emoji = emoji.strip()

    if not cleaned_emoji:
        return None

    return discord.PartialEmoji.from_str(cleaned_emoji)


class RoleToggleButton(discord.ui.Button):
    """
    Egyetlen rangot hozzáadó vagy elvevő gomb.
    """

    def __init__(
        self,
        panel_id: int,
        role_id: int,
        label: str,
        emoji: str | None,
        style: int,
        position: int,
    ) -> None:
        self.panel_id = panel_id
        self.role_id = role_id

        super().__init__(
            label=label[:80],
            emoji=parse_emoji(emoji),
            style=discord.ButtonStyle(style),
            custom_id=f"rolepanel:{panel_id}:{role_id}",
            row=position // 5,
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ) -> None:
        guild = interaction.guild
        member = interaction.user

        if guild is None or not isinstance(
            member,
            discord.Member,
        ):
            await interaction.response.send_message(
                "❌ Ez a gomb csak szerveren használható.",
                ephemeral=True,
            )
            return

        panel = await get_role_panel(
            guild_id=guild.id,
            panel_id=self.panel_id,
        )

        if panel is None:
            await interaction.response.send_message(
                "❌ Ez a rangpanel már nem létezik.",
                ephemeral=True,
            )
            return

        panel_buttons = await get_role_panel_buttons(
            self.panel_id
        )

        button_exists = any(
            int(button["role_id"]) == self.role_id
            for button in panel_buttons
        )

        if not button_exists:
            await interaction.response.send_message(
                "❌ Ez a rang már nincs a panelhez rendelve.",
                ephemeral=True,
            )
            return

        role = guild.get_role(self.role_id)

        if role is None:
            await interaction.response.send_message(
                "❌ A rangot időközben törölték.",
                ephemeral=True,
            )
            return

        if role.is_default() or role.managed:
            await interaction.response.send_message(
                "❌ Ez a rang nem osztható ki.",
                ephemeral=True,
            )
            return

        if role_has_dangerous_permissions(role):
            await interaction.response.send_message(
                "❌ Ez a rang veszélyes moderátori vagy "
                "rendszergazdai jogosultságokat tartalmaz.",
                ephemeral=True,
            )
            return

        bot_member = guild.me

        if bot_member is None:
            await interaction.response.send_message(
                "❌ Nem sikerült lekérni a bot rangját.",
                ephemeral=True,
            )
            return

        if not bot_member.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "❌ A botnak nincs Rangok kezelése jogosultsága.",
                ephemeral=True,
            )
            return

        if role >= bot_member.top_role:
            await interaction.response.send_message(
                "❌ A bot rangja nincs a kiosztandó rang fölött.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        try:
            if role in member.roles:
                await member.remove_roles(
                    role,
                    reason=(
                        "Rangpanel: a felhasználó "
                        "eltávolította saját rangját"
                    ),
                )

                await interaction.followup.send(
                    f"➖ Eltávolítottam a(z) "
                    f"**{role.name}** rangot.",
                    ephemeral=True,
                )

            else:
                await member.add_roles(
                    role,
                    reason=(
                        "Rangpanel: a felhasználó "
                        "kiválasztotta saját rangját"
                    ),
                )

                await interaction.followup.send(
                    f"✅ Megkaptad a(z) "
                    f"**{role.name}** rangot.",
                    ephemeral=True,
                )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ A Discord megtagadta a rang módosítását. "
                "Ellenőrizd a bot rangját és jogosultságait.",
                ephemeral=True,
            )

        except discord.HTTPException:
            await interaction.followup.send(
                "❌ Discord API-hiba történt. Próbáld újra.",
                ephemeral=True,
            )


class RolePanelView(discord.ui.View):
    """
    Egy teljes rangpanel összes gombja.
    """

    def __init__(
        self,
        panel_id: int,
        buttons: list[dict],
    ) -> None:
        super().__init__(timeout=None)

        for button in buttons:
            self.add_item(
                RoleToggleButton(
                    panel_id=panel_id,
                    role_id=int(button["role_id"]),
                    label=str(button["label"]),
                    emoji=(
                        str(button["emoji"])
                        if button["emoji"] is not None
                        else None
                    ),
                    style=int(button["style"]),
                    position=int(button["position"]),
                )
            )