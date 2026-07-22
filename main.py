import os

import discord
from discord.ext import commands
from dotenv import load_dotenv


# Beolvassa a .env fájl tartalmát.
load_dotenv()

# Kiveszi belőle a bot tokenjét.
TOKEN = os.getenv("DISCORD_TOKEN")

# Ha nem talál tokent, érthető hibával leáll.
if not TOKEN:
    raise RuntimeError(
        "Nem található a DISCORD_TOKEN!\n"
        "Ellenőrizd a .env fájlt."
    )


# Meghatározzuk, milyen Discord-eseményeket figyelhet a bot.
intents = discord.Intents.default()

# Belépés, kilépés és tagkezelés miatt kell.
intents.members = True

# Üzenetfigyelés és a későbbi automoderáció miatt kell.
intents.message_content = True


class ServerBot(commands.Bot):
    async def setup_hook(self) -> None:
        """
        A bot indulásakor szinkronizálja
        a Discord slash parancsait.
        """

        parancsok = await self.tree.sync()

        print(
            f"{len(parancsok)} slash parancs szinkronizálva."
        )


bot = ServerBot(
    command_prefix="!",
    intents=intents,
    help_command=None,
)


@bot.event
async def on_ready() -> None:
    """
    Akkor fut le, amikor a bot sikeresen
    csatlakozott a Discordhoz.
    """

    if bot.user is None:
        return

    print("-----------------------------------")
    print("A bot sikeresen elindult!")
    print(f"Bot neve: {bot.user}")
    print(f"Bot azonosítója: {bot.user.id}")
    print(f"Szerverek száma: {len(bot.guilds)}")
    print("-----------------------------------")

    await bot.change_presence(
        activity=discord.Game(name="/ping | Fejlesztés alatt")
    )


@bot.tree.command(
    name="ping",
    description="Megmutatja a bot válaszidejét.",
)
async def slash_ping(
    interaction: discord.Interaction,
) -> None:
    válaszidő = round(bot.latency * 1000)

    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Válaszidő: **{válaszidő} ms**",
        color=discord.Color.green(),
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True,
    )


@bot.command(name="ping")
async def szöveges_ping(ctx: commands.Context) -> None:
    """
    Ideiglenes !ping parancs arra az esetre,
    ha a /ping még nem jelent meg.
    """

    válaszidő = round(bot.latency * 1000)

    await ctx.send(
        f"🏓 Pong! Válaszidő: **{válaszidő} ms**"
    )


bot.run(TOKEN)