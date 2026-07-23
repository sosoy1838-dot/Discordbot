import discord

from database.db import get_bot_manager_roles


async def is_owner_or_administrator(
    interaction: discord.Interaction,
) -> bool:
    """
    Ellenőrzi, hogy a felhasználó a szerver tulajdonosa
    vagy rendszergazda-e.
    """

    guild = interaction.guild
    member = interaction.user

    if guild is None:
        return False

    if not isinstance(member, discord.Member):
        return False

    if member.id == guild.owner_id:
        return True

    return member.guild_permissions.administrator


async def is_bot_manager(
    interaction: discord.Interaction,
) -> bool:
    """
    Igaz, ha a felhasználó:

    - szervertulajdonos;
    - rendszergazda;
    - vagy rendelkezik egy beállított botkezelő ranggal.
    """

    guild = interaction.guild
    member = interaction.user

    if guild is None:
        return False

    if not isinstance(member, discord.Member):
        return False

    if await is_owner_or_administrator(interaction):
        return True

    manager_role_ids = set(
        await get_bot_manager_roles(guild.id)
    )

    return any(
        role.id in manager_role_ids
        for role in member.roles
    )


async def send_manager_denied(
    interaction: discord.Interaction,
) -> None:
    """
    Egységes hozzáférés-megtagadási üzenet.
    """

    message = (
        "❌ Nincs jogosultságod a bot kezeléséhez.\n"
        "Ezt csak a szervertulajdonos, egy rendszergazda "
        "vagy egy beállított botkezelő rang használhatja."
    )

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