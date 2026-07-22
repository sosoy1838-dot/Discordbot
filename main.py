import os
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

from database.db import init_database


# --------------------------------------------------
# Token betöltése
# --------------------------------------------------

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "Nem található a DISCORD_TOKEN!\n"
        "Ellenőrizd a .env fájlt."
    )


# --------------------------------------------------
# Discord intentek
# --------------------------------------------------

intents = discord.Intents.default()
intents.members = True
intents.message_content = True


# --------------------------------------------------
# Saját bot osztály
# --------------------------------------------------

class ServerBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )

    async def setup_hook(self) -> None:
        """
        Inicializálja az adatbázist, betölti a modulokat,
        majd szinkronizálja a slash parancsokat.
        """

        await init_database()
        print("Adatbázis inicializálva.")

        cogs_mappa = Path(__file__).parent / "cogs"

        for fajl in sorted(cogs_mappa.glob("*.py")):
            if fajl.name.startswith("_"):
                continue

            modul_neve = f"cogs.{fajl.stem}"

            await self.load_extension(modul_neve)
            print(f"Modul betöltve: {modul_neve}")

        parancsok = await self.tree.sync()

        print(
            f"{len(parancsok)} slash parancs szinkronizálva."
        )


bot = ServerBot()


# --------------------------------------------------
# Bot elindulási eseménye
# --------------------------------------------------

@bot.event
async def on_ready() -> None:
    if bot.user is None:
        return

    print("-----------------------------------")
    print("A bot sikeresen elindult!")
    print(f"Bot neve: {bot.user}")
    print(f"Bot azonosítója: {bot.user.id}")
    print(f"Szerverek száma: {len(bot.guilds)}")
    print("-----------------------------------")

    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(
            name="/ping | Fejlesztés alatt"
        ),
    )


# --------------------------------------------------
# Bot indítása
# --------------------------------------------------

bot.run(TOKEN)