import asyncio
from datetime import datetime, timezone
import discord
from discord.ext import commands

from database.db import (
    add_giveaway_entry,
    count_giveaway_entries,
    get_giveaway_by_message,
    remove_giveaway_entry,
)


class GiveawayEntryView(discord.ui.View):
    """
    Állandó giveaway jelentkezési gomb.

    Első kattintás:
    - jelentkezés

    Második kattintás:
    - jelentkezés visszavonása
    """

    def __init__(
        self,
        bot: commands.Bot,
    ) -> None:
        super().__init__(timeout=None)

        self.bot = bot
        self.giveaway_locks: dict[int, asyncio.Lock] = {}

    def get_lock(
        self,
        giveaway_id: int,
    ) -> asyncio.Lock:
        """
        Megakadályozza, hogy egyszerre több kattintás
        összekeverje a jelentkezők számát.
        """

        if giveaway_id not in self.giveaway_locks:
            self.giveaway_locks[giveaway_id] = asyncio.Lock()

        return self.giveaway_locks[giveaway_id]

    @discord.ui.button(
        label="Jelentkezés / kilépés",
        emoji="🎉",
        style=discord.ButtonStyle.green,
        custom_id="giveaway:toggle-entry",
    )
    async def toggle_entry(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        guild = interaction.guild
        member = interaction.user
        message = interaction.message

        if guild is None:
            await interaction.response.send_message(
                "❌ Ez a gomb csak szerveren használható.",
                ephemeral=True,
            )
            return

        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "❌ Nem sikerült lekérni a felhasználót.",
                ephemeral=True,
            )
            return

        if message is None:
            await interaction.response.send_message(
                "❌ Nem található a giveaway üzenete.",
                ephemeral=True,
            )
            return

        giveaway = await get_giveaway_by_message(
            message.id
        )

        if giveaway is None:
            await interaction.response.send_message(
                "❌ Ez a giveaway nincs az adatbázisban.",
                ephemeral=True,
            )
            return

        if giveaway["status"] != "active":
            await interaction.response.send_message(
                "ℹ️ Ez a giveaway már véget ért.",
                ephemeral=True,
            )
            return
        try:
            end_time = datetime.fromisoformat(
                str(giveaway["end_time"]).replace(
                    "Z",
                    "+00:00",
                )
            )

            if end_time.tzinfo is None:
                end_time = end_time.replace(
                    tzinfo=timezone.utc
                )

        except ValueError:
            await interaction.response.send_message(
                "❌ Hibás giveaway időpont.",
                ephemeral=True,
            )
            return

        if discord.utils.utcnow() >= end_time:
            await interaction.response.send_message(
                "ℹ️ Ez a giveaway már véget ért.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        giveaway_id = int(giveaway["id"])
        lock = self.get_lock(giveaway_id)

        async with lock:
            added = await add_giveaway_entry(
                giveaway_id=giveaway_id,
                user_id=member.id,
            )

            if added:
                joined = True
            else:
                removed = await remove_giveaway_entry(
                    giveaway_id=giveaway_id,
                    user_id=member.id,
                )

                joined = not removed

            entry_count = await count_giveaway_entries(
                giveaway_id
            )

        if message.embeds:
            embed = discord.Embed.from_dict(
                message.embeds[0].to_dict()
            )
        else:
            embed = discord.Embed(
                title="🎉 Giveaway",
                color=discord.Color.blurple(),
            )

        participants_field_index: int | None = None

        for index, field in enumerate(embed.fields):
            if field.name == "👥 Résztvevők":
                participants_field_index = index
                break

        if participants_field_index is None:
            embed.add_field(
                name="👥 Résztvevők",
                value=str(entry_count),
                inline=True,
            )
        else:
            embed.set_field_at(
                participants_field_index,
                name="👥 Résztvevők",
                value=str(entry_count),
                inline=True,
            )

        try:
            await message.edit(
                embed=embed,
                view=self,
            )
        except discord.HTTPException:
            pass

        if joined:
            response_text = (
                "✅ Sikeresen jelentkeztél a giveawayre!"
            )
        else:
            response_text = (
                "✅ Visszavontad a jelentkezésedet."
            )

        await interaction.followup.send(
            response_text,
            ephemeral=True,
        )