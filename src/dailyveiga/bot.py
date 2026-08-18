from __future__ import annotations

import logging

import discord
from discord.ext import commands

from dailyveiga.config import AppConfig
from dailyveiga.database import Database
from dailyveiga.discord_bot import DailyCog, ResponseView
from dailyveiga.service import DailyService


class DailyVeigaBot(commands.Bot):
    def __init__(self, config: AppConfig, database: Database) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        intents.members = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.config = config
        self.database = database

    async def setup_hook(self) -> None:
        await self.database.initialize()
        await self.add_cog(DailyCog(self, self.database))
        self.add_view(ResponseView(DailyService(self.database)))

        if self.config.test_guild_id:
            guild = discord.Object(id=self.config.test_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logging.getLogger(__name__).info(
                "Comandos sincronizados no servidor de teste %s", self.config.test_guild_id
            )
        else:
            await self.tree.sync()
            logging.getLogger(__name__).info("Comandos globais sincronizados")

    async def on_ready(self) -> None:
        if self.user:
            logging.getLogger(__name__).info(
                "DailyVeiga conectado como %s (%s)", self.user, self.user.id
            )


def run() -> None:
    config = AppConfig.from_env()
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    bot = DailyVeigaBot(config, Database(config.database_path))
    bot.run(config.discord_token, log_handler=None)
