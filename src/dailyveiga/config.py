from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppConfig:
    discord_token: str
    database_path: Path
    log_level: str = "INFO"
    test_guild_id: int | None = None

    @classmethod
    def from_env(cls) -> AppConfig:
        token = os.environ.get("DISCORD_TOKEN", "").strip()
        if not token or token == "cole_o_token_aqui":
            raise RuntimeError("Defina DISCORD_TOKEN com o token da aplicação Discord.")

        raw_guild_id = os.environ.get("DISCORD_TEST_GUILD_ID", "").strip()
        try:
            test_guild_id = int(raw_guild_id) if raw_guild_id else None
        except ValueError as exc:
            raise RuntimeError("DISCORD_TEST_GUILD_ID deve ser um número inteiro.") from exc

        database_path = Path(os.environ.get("DATABASE_PATH", "data/dailyveiga.db")).expanduser()
        log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
        if log_level not in logging.getLevelNamesMapping():
            raise RuntimeError(f"LOG_LEVEL inválido: {log_level}")

        return cls(
            discord_token=token,
            database_path=database_path,
            log_level=log_level,
            test_guild_id=test_guild_id,
        )
