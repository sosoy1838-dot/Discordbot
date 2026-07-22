import discord

from database.db import get_guild_setting


async def send_log(
    guild: discord.Guild,
    embed: discord.Embed,
) -> bool:
    """
    Embed üzenetet küld a szerver beállított
    logcsatornájába.

    True: sikerült elküldeni.
    False: nincs csatorna vagy nem sikerült küldeni.
    """

    log_channel_id = await get_guild_setting(
        guild_id=guild.id,
        setting_key="log_channel_id",
    )

    if log_channel_id is None:
        return False

    try:
        channel_id = int(log_channel_id)
    except ValueError:
        return False

    channel = guild.get_channel(channel_id)

    if not isinstance(channel, discord.TextChannel):
        return False

    bot_member = guild.me

    if bot_member is None:
        return False

    permissions = channel.permissions_for(bot_member)

    if not (
        permissions.view_channel
        and permissions.send_messages
        and permissions.embed_links
    ):
        return False

    try:
        await channel.send(
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    except (discord.Forbidden, discord.HTTPException):
        return False

    return True