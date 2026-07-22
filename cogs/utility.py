import discord
from discord import app_commands
from discord.ext import commands


class Utility(commands.Cog):
    """
    Általános és információs parancsok.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="ping",
        description="Megmutatja a bot válaszidejét.",
    )
    async def ping(
        self,
        interaction: discord.Interaction,
    ) -> None:
        latency_ms = round(self.bot.latency * 1000)

        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"A bot válaszideje: **{latency_ms} ms**",
            color=discord.Color.green(),
        )

        embed.set_footer(
            text=f"Kérte: {interaction.user}",
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    """
    Ezt futtatja le a main.py a modul betöltésekor.
    """

    await bot.add_cog(Utility(bot))