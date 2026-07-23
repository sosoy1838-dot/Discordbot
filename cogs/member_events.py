import discord
from discord.ext import commands

from database.db import get_guild_setting
from utils.logging_utils import send_log


class MemberEvents(commands.Cog):
    """
    Belépési, kilépési és automatikus
    rangkiosztási események.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def get_text_channel(
        self,
        guild: discord.Guild,
        setting_key: str,
    ) -> discord.TextChannel | None:
        channel_id = await get_guild_setting(
            guild_id=guild.id,
            setting_key=setting_key,
        )

        if channel_id is None:
            return None

        try:
            channel = guild.get_channel(int(channel_id))
        except ValueError:
            return None

        if not isinstance(channel, discord.TextChannel):
            return None

        return channel

    # --------------------------------------------------
    # Tag belépése
    # --------------------------------------------------

    @commands.Cog.listener()
    async def on_member_join(
        self,
        member: discord.Member,
    ) -> None:
        guild = member.guild

        autorole_text = "Nincs beállítva"
        autorole_id = await get_guild_setting(
            guild_id=guild.id,
            setting_key="autorole_id",
        )

        if autorole_id is not None:
            try:
                role = guild.get_role(int(autorole_id))
            except ValueError:
                role = None

            if role is None:
                autorole_text = "A beállított rang nem található."

            elif role.managed:
                autorole_text = "A rangot egy integráció kezeli."

            elif guild.me is None:
                autorole_text = "A bot szervertagsága nem található."

            elif role >= guild.me.top_role:
                autorole_text = "A bot rangja túl alacsonyan van."

            else:
                try:
                    await member.add_roles(
                        role,
                        reason="Automatikus belépési rang",
                    )

                    autorole_text = role.mention

                except discord.Forbidden:
                    autorole_text = "A bot nem adhatta hozzá a rangot."

                except discord.HTTPException:
                    autorole_text = "Discord API-hiba történt."

        welcome_channel = await self.get_text_channel(
            guild,
            "welcome_channel_id",
        )

        if welcome_channel is not None:
            member_count = guild.member_count

            if member_count is None:
                member_count = len(guild.members)

            welcome_embed = discord.Embed(
                title="👋 Üdv a szerveren!",
                description=(
                    f"Szia {member.mention}!\n"
                    f"Üdv a **{guild.name}** szerveren.\n\n"
                    f"Te vagy a(z) **{member_count}. tag**."
                ),
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )

            welcome_embed.set_thumbnail(
                url=member.display_avatar.url
            )

            welcome_embed.set_footer(
                text=f"Felhasználóazonosító: {member.id}"
            )

            try:
                await welcome_channel.send(
                    embed=welcome_embed,
                    allowed_mentions=discord.AllowedMentions(
                        users=True,
                        roles=False,
                        everyone=False,
                    ),
                )

            except (discord.Forbidden, discord.HTTPException):
                pass

        log_embed = discord.Embed(
            title="📥 Tag csatlakozott",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )

        log_embed.add_field(
            name="Tag",
            value=(
                f"{member.mention}\n"
                f"`{member.id}`"
            ),
            inline=True,
        )

        log_embed.add_field(
            name="Fiók létrehozva",
            value=discord.utils.format_dt(
                member.created_at,
                style="R",
            ),
            inline=True,
        )

        log_embed.add_field(
            name="Automatikus rang",
            value=autorole_text,
            inline=False,
        )

        await send_log(
            guild=guild,
            embed=log_embed,
        )

    # --------------------------------------------------
    # Tag kilépése
    # --------------------------------------------------

    @commands.Cog.listener()
    async def on_member_remove(
        self,
        member: discord.Member,
    ) -> None:
        guild = member.guild

        goodbye_channel = await self.get_text_channel(
            guild,
            "goodbye_channel_id",
        )

        if goodbye_channel is not None:
            goodbye_embed = discord.Embed(
                title="👋 Viszlát!",
                description=(
                    f"**{member}** elhagyta a szervert.\n\n"
                    f"A szerveren jelenleg "
                    f"**{guild.member_count or len(guild.members)} tag** van."
                ),
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow(),
            )

            goodbye_embed.set_thumbnail(
                url=member.display_avatar.url
            )

            goodbye_embed.set_footer(
                text=f"Felhasználóazonosító: {member.id}"
            )

            try:
                await goodbye_channel.send(
                    embed=goodbye_embed,
                    allowed_mentions=discord.AllowedMentions.none(),
                )

            except (discord.Forbidden, discord.HTTPException):
                pass

        log_embed = discord.Embed(
            title="📤 Tag távozott",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )

        log_embed.add_field(
            name="Tag",
            value=f"{member}\n`{member.id}`",
            inline=True,
        )

        log_embed.add_field(
            name="Csatlakozott",
            value=(
                discord.utils.format_dt(
                    member.joined_at,
                    style="R",
                )
                if member.joined_at is not None
                else "Nem ismert"
            ),
            inline=True,
        )

        await send_log(
            guild=guild,
            embed=log_embed,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MemberEvents(bot))