import asyncio
import io
import re
import unicodedata

import discord
from discord.ext import commands

from database.db import (
    claim_ticket,
    close_ticket,
    create_ticket,
    get_guild_setting,
    get_open_ticket_for_user,
    get_staff_roles,
    get_ticket_by_channel,
)


def create_safe_channel_name(
    member: discord.Member,
) -> str:
    """
    Biztonságos ticketcsatorna-nevet készít
    a felhasználó nevéből.
    """

    normalized_name = unicodedata.normalize(
        "NFKD",
        member.display_name,
    )

    ascii_name = normalized_name.encode(
        "ascii",
        "ignore",
    ).decode("ascii")

    cleaned_name = re.sub(
        r"[^a-zA-Z0-9]+",
        "-",
        ascii_name,
    ).strip("-").lower()

    if not cleaned_name:
        cleaned_name = "felhasznalo"

    return (
        f"ticket-{cleaned_name[:20]}-"
        f"{str(member.id)[-4:]}"
    )[:100]


async def get_ticket_staff_roles(
    guild: discord.Guild,
) -> list[discord.Role]:
    """
    Lekéri a Discordon beállított staffrangokat.
    """

    role_ids = await get_staff_roles(guild.id)
    roles: list[discord.Role] = []

    for role_id in role_ids:
        role = guild.get_role(role_id)

        if role is not None:
            roles.append(role)

    return roles


async def is_ticket_staff(
    member: discord.Member,
) -> bool:
    """
    Ellenőrzi, hogy a tag kezelhet-e ticketeket.
    """

    guild = member.guild

    if member.id == guild.owner_id:
        return True

    if member.guild_permissions.administrator:
        return True

    staff_role_ids = set(
        await get_staff_roles(guild.id)
    )

    return any(
        role.id in staff_role_ids
        for role in member.roles
    )


async def send_ticket_log(
    guild: discord.Guild,
    embed: discord.Embed,
    file: discord.File | None = None,
) -> bool:
    """
    Üzenetet küld a beállított ticket-log csatornába.
    """

    channel_id_text = await get_guild_setting(
        guild_id=guild.id,
        setting_key="ticket_log_channel_id",
    )

    if channel_id_text is None:
        return False

    try:
        channel_id = int(channel_id_text)
    except ValueError:
        return False

    channel = guild.get_channel(channel_id)

    if not isinstance(channel, discord.TextChannel):
        return False

    try:
        await channel.send(
            embed=embed,
            file=file,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    except (discord.Forbidden, discord.HTTPException):
        return False

    return True


async def create_ticket_transcript(
    channel: discord.TextChannel,
) -> discord.File:
    """
    TXT-átiratot készít a ticket üzeneteiből.
    """

    transcript_lines: list[str] = [
        f"Ticket: #{channel.name}",
        f"Szerver: {channel.guild.name}",
        f"Csatornaazonosító: {channel.id}",
        "-" * 70,
        "",
    ]

    async for message in channel.history(
        limit=5000,
        oldest_first=True,
    ):
        timestamp = message.created_at.strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )

        content = message.clean_content.strip()

        if not content:
            content = "[Nincs szöveges tartalom]"

        transcript_lines.append(
            f"[{timestamp}] "
            f"{message.author} ({message.author.id}):"
        )

        transcript_lines.append(content)

        for attachment in message.attachments:
            transcript_lines.append(
                f"Csatolmány: {attachment.url}"
            )

        transcript_lines.append("")

    transcript_text = "\n".join(transcript_lines)

    transcript_bytes = io.BytesIO(
        transcript_text.encode("utf-8")
    )

    return discord.File(
        transcript_bytes,
        filename=f"ticket-{channel.id}.txt",
    )


class TicketOpenView(discord.ui.View):
    """
    Állandó ticketnyitó gomb.
    """

    def __init__(
        self,
        bot: commands.Bot,
    ) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Ticket nyitása",
        emoji="🎫",
        style=discord.ButtonStyle.green,
        custom_id="ticket:open",
    )
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
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

        existing_ticket = await get_open_ticket_for_user(
            guild_id=guild.id,
            opener_id=member.id,
        )

        if existing_ticket is not None:
            existing_channel = guild.get_channel(
                int(existing_ticket["channel_id"])
            )

            if isinstance(
                existing_channel,
                discord.TextChannel,
            ):
                await interaction.response.send_message(
                    (
                        "ℹ️ Már van egy nyitott ticketed: "
                        f"{existing_channel.mention}"
                    ),
                    ephemeral=True,
                )
                return

            # Ha a csatornát kézzel törölték,
            # lezárjuk az elavult adatbázis-bejegyzést.
            await close_ticket(
                int(existing_ticket["channel_id"])
            )

        category_id_text = await get_guild_setting(
            guild_id=guild.id,
            setting_key="ticket_category_id",
        )

        if category_id_text is None:
            await interaction.response.send_message(
                "❌ A ticketkategória még nincs beállítva.",
                ephemeral=True,
            )
            return

        try:
            category_id = int(category_id_text)
        except ValueError:
            await interaction.response.send_message(
                "❌ Hibás ticketkategória-beállítás.",
                ephemeral=True,
            )
            return

        category = guild.get_channel(category_id)

        if not isinstance(
            category,
            discord.CategoryChannel,
        ):
            await interaction.response.send_message(
                "❌ A beállított ticketkategória nem található.",
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

        if not bot_member.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "❌ A botnak nincs Csatornák kezelése jogosultsága.",
                ephemeral=True,
            )
            return

        staff_roles = await get_ticket_staff_roles(guild)

        overwrites: dict[
            discord.Role | discord.Member,
            discord.PermissionOverwrite,
        ] = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False,
            ),
            member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            ),
            bot_member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
                manage_channels=True,
                manage_messages=True,
            ),
        }

        for staff_role in staff_roles:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            )

        await interaction.response.defer(
            ephemeral=True,
        )

        channel_name = create_safe_channel_name(member)

        try:
            ticket_channel = await category.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                topic=(
                    f"Ticket nyitója: {member} "
                    f"({member.id})"
                ),
                reason=(
                    f"Ticket nyitva: {member} "
                    f"({member.id})"
                ),
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ A bot nem hozhatott létre ticketcsatornát.",
                ephemeral=True,
            )
            return

        except discord.HTTPException:
            await interaction.followup.send(
                "❌ Discord API-hiba történt a ticket létrehozásakor.",
                ephemeral=True,
            )
            return

        try:
            ticket_id = await create_ticket(
                guild_id=guild.id,
                channel_id=ticket_channel.id,
                opener_id=member.id,
            )

        except Exception:
            try:
                await ticket_channel.delete(
                    reason="Az adatbázismentés sikertelen volt."
                )
            except discord.HTTPException:
                pass

            raise

        ticket_embed = discord.Embed(
            title=f"🎫 Ticket #{ticket_id}",
            description=(
                f"Szia {member.mention}!\n\n"
                "Írd le részletesen, miben kérsz segítséget.\n"
                "Egy stafftag hamarosan válaszolni fog."
            ),
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )

        ticket_embed.add_field(
            name="Ticket nyitója",
            value=member.mention,
            inline=True,
        )

        ticket_embed.add_field(
            name="Állapot",
            value="🟢 Nyitva",
            inline=True,
        )

        ticket_embed.set_footer(
            text=f"Ticket ID: {ticket_id}"
        )

        staff_mentions = " ".join(
            role.mention
            for role in staff_roles
        )

        notification_text = member.mention

        if staff_mentions:
            notification_text += f" | {staff_mentions}"

        await ticket_channel.send(
            content=notification_text,
            embed=ticket_embed,
            view=TicketControlView(self.bot),
            allowed_mentions=discord.AllowedMentions(
                users=True,
                roles=True,
                everyone=False,
            ),
        )

        log_embed = discord.Embed(
            title="🎫 Ticket megnyitva",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )

        log_embed.add_field(
            name="Ticket",
            value=(
                f"{ticket_channel.mention}\n"
                f"`{ticket_id}`"
            ),
            inline=True,
        )

        log_embed.add_field(
            name="Nyitotta",
            value=(
                f"{member.mention}\n"
                f"`{member.id}`"
            ),
            inline=True,
        )

        await send_ticket_log(
            guild=guild,
            embed=log_embed,
        )

        await interaction.followup.send(
            (
                "✅ A ticketed elkészült: "
                f"{ticket_channel.mention}"
            ),
            ephemeral=True,
        )


class TicketControlView(discord.ui.View):
    """
    A ticketcsatornák állandó kezelőgombjai.
    """

    def __init__(
        self,
        bot: commands.Bot,
    ) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Claim",
        emoji="🙋",
        style=discord.ButtonStyle.primary,
        custom_id="ticket:claim",
    )
    async def claim_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        channel = interaction.channel
        member = interaction.user

        if not isinstance(
            channel,
            discord.TextChannel,
        ) or not isinstance(
            member,
            discord.Member,
        ):
            await interaction.response.send_message(
                "❌ Ez nem egy megfelelő ticketcsatorna.",
                ephemeral=True,
            )
            return

        if not await is_ticket_staff(member):
            await interaction.response.send_message(
                "❌ Csak stafftag claimelhet ticketet.",
                ephemeral=True,
            )
            return

        ticket = await get_ticket_by_channel(channel.id)

        if ticket is None:
            await interaction.response.send_message(
                "❌ Ez a csatorna nincs ticketként nyilvántartva.",
                ephemeral=True,
            )
            return

        if ticket["status"] != "open":
            await interaction.response.send_message(
                "❌ Ez a ticket már le van zárva.",
                ephemeral=True,
            )
            return

        claimed_by = ticket["claimed_by"]

        if claimed_by is not None:
            if int(claimed_by) == member.id:
                message = "ℹ️ Ezt a ticketet már te claimelted."
            else:
                message = (
                    "ℹ️ Ezt a ticketet már claimelte: "
                    f"<@{claimed_by}>"
                )

            await interaction.response.send_message(
                message,
                ephemeral=True,
            )
            return

        claimed = await claim_ticket(
            channel_id=channel.id,
            staff_id=member.id,
        )

        if not claimed:
            await interaction.response.send_message(
                "❌ A ticketet közben egy másik stafftag claimelte.",
                ephemeral=True,
            )
            return

        claim_embed = discord.Embed(
            description=(
                f"🙋 {member.mention} átvette ezt a ticketet."
            ),
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )

        await interaction.response.send_message(
            embed=claim_embed,
        )

        log_embed = discord.Embed(
            title="🙋 Ticket claimelve",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )

        log_embed.add_field(
            name="Ticket",
            value=channel.mention,
            inline=True,
        )

        log_embed.add_field(
            name="Stafftag",
            value=member.mention,
            inline=True,
        )

        await send_ticket_log(
            guild=channel.guild,
            embed=log_embed,
        )

    @discord.ui.button(
        label="Lezárás",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="ticket:close",
    )
    async def close_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        channel = interaction.channel
        member = interaction.user

        if not isinstance(
            channel,
            discord.TextChannel,
        ) or not isinstance(
            member,
            discord.Member,
        ):
            return

        ticket = await get_ticket_by_channel(channel.id)

        if ticket is None:
            await interaction.response.send_message(
                "❌ Ez nem nyilvántartott ticket.",
                ephemeral=True,
            )
            return

        if ticket["status"] != "open":
            await interaction.response.send_message(
                "ℹ️ Ez a ticket már le van zárva.",
                ephemeral=True,
            )
            return

        is_opener = (
            int(ticket["opener_id"]) == member.id
        )

        staff = await is_ticket_staff(member)

        if not is_opener and not staff:
            await interaction.response.send_message(
                "❌ Ezt a ticketet csak a nyitója vagy egy stafftag zárhatja le.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        transcript_file = await create_ticket_transcript(
            channel
        )

        closed = await close_ticket(channel.id)

        if not closed:
            await interaction.followup.send(
                "❌ Nem sikerült lezárni a ticketet.",
                ephemeral=True,
            )
            return

        opener = channel.guild.get_member(
            int(ticket["opener_id"])
        )

        if opener is not None:
            try:
                await channel.set_permissions(
                    opener,
                    view_channel=True,
                    send_messages=False,
                    read_message_history=True,
                    reason="Ticket lezárva",
                )
            except discord.HTTPException:
                pass

        if not channel.name.startswith("closed-"):
            try:
                await channel.edit(
                    name=f"closed-{channel.name}"[:100],
                    reason="Ticket lezárva",
                )
            except discord.HTTPException:
                pass

        log_embed = discord.Embed(
            title="🔒 Ticket lezárva",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )

        log_embed.add_field(
            name="Ticket",
            value=f"#{channel.name}\n`{channel.id}`",
            inline=True,
        )

        log_embed.add_field(
            name="Lezárta",
            value=(
                f"{member.mention}\n"
                f"`{member.id}`"
            ),
            inline=True,
        )

        log_embed.add_field(
            name="Ticket nyitója",
            value=f"<@{ticket['opener_id']}>",
            inline=True,
        )

        await send_ticket_log(
            guild=channel.guild,
            embed=log_embed,
            file=transcript_file,
        )

        closed_embed = discord.Embed(
            title="🔒 Ticket lezárva",
            description=(
                f"A ticketet lezárta: {member.mention}\n"
                "A staff a **Törlés** gombbal törölheti a csatornát."
            ),
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )

        await channel.send(
            embed=closed_embed,
            view=TicketControlView(self.bot),
        )

        await interaction.followup.send(
            "✅ A ticket lezárva, az átirat elküldve.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Törlés",
        emoji="🗑️",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket:delete",
    )
    async def delete_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        channel = interaction.channel
        member = interaction.user

        if not isinstance(
            channel,
            discord.TextChannel,
        ) or not isinstance(
            member,
            discord.Member,
        ):
            return

        if not await is_ticket_staff(member):
            await interaction.response.send_message(
                "❌ Ticketcsatornát csak stafftag törölhet.",
                ephemeral=True,
            )
            return

        ticket = await get_ticket_by_channel(channel.id)

        if ticket is None:
            await interaction.response.send_message(
                "❌ Ez nem nyilvántartott ticket.",
                ephemeral=True,
            )
            return

        if ticket["status"] != "closed":
            await interaction.response.send_message(
                "❌ A ticketet először le kell zárni.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "🗑️ A ticketcsatorna 5 másodperc múlva törlődik.",
            ephemeral=True,
        )

        log_embed = discord.Embed(
            title="🗑️ Ticket törölve",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )

        log_embed.add_field(
            name="Csatorna",
            value=f"#{channel.name}\n`{channel.id}`",
            inline=True,
        )

        log_embed.add_field(
            name="Törölte",
            value=(
                f"{member.mention}\n"
                f"`{member.id}`"
            ),
            inline=True,
        )

        await send_ticket_log(
            guild=channel.guild,
            embed=log_embed,
        )

        await asyncio.sleep(5)

        try:
            await channel.delete(
                reason=(
                    f"Ticket törölve: {member} "
                    f"({member.id})"
                )
            )
        except discord.HTTPException:
            pass