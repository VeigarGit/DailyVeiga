from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path

from dailyveiga.models import (
    DailyResponse,
    DailyRound,
    GuildSettings,
    Participant,
    ParticipantStatus,
)


class Database:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._initialize_sync)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _initialize_sync(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    reminder_channel_id INTEGER NOT NULL,
                    report_channel_id INTEGER NOT NULL,
                    participant_role_id INTEGER NOT NULL,
                    timezone TEXT NOT NULL,
                    opening_time TEXT NOT NULL,
                    closing_time TEXT NOT NULL,
                    weekdays TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS daily_rounds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    scheduled_date TEXT NOT NULL,
                    opened_at TEXT NOT NULL,
                    closes_at TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('open', 'closed', 'cancelled')),
                    discord_message_id INTEGER,
                    UNIQUE(guild_id, scheduled_date)
                );

                CREATE TABLE IF NOT EXISTS round_participants (
                    round_id INTEGER NOT NULL REFERENCES daily_rounds(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL,
                    display_name TEXT NOT NULL,
                    PRIMARY KEY(round_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS responses (
                    round_id INTEGER NOT NULL REFERENCES daily_rounds(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL,
                    completed TEXT NOT NULL,
                    doing TEXT NOT NULL,
                    blockers TEXT NOT NULL,
                    submitted_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(round_id, user_id),
                    FOREIGN KEY(round_id, user_id)
                        REFERENCES round_participants(round_id, user_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_rounds_status
                    ON daily_rounds(guild_id, status, scheduled_date);
                """
            )

    async def upsert_settings(self, settings: GuildSettings) -> None:
        await asyncio.to_thread(self._upsert_settings_sync, settings)

    def _upsert_settings_sync(self, settings: GuildSettings) -> None:
        now = datetime.now().astimezone().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO guild_settings (
                    guild_id, reminder_channel_id, report_channel_id,
                    participant_role_id, timezone, opening_time, closing_time,
                    weekdays, enabled, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    reminder_channel_id = excluded.reminder_channel_id,
                    report_channel_id = excluded.report_channel_id,
                    participant_role_id = excluded.participant_role_id,
                    timezone = excluded.timezone,
                    opening_time = excluded.opening_time,
                    closing_time = excluded.closing_time,
                    weekdays = excluded.weekdays,
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
                """,
                (
                    settings.guild_id,
                    settings.reminder_channel_id,
                    settings.report_channel_id,
                    settings.participant_role_id,
                    settings.timezone,
                    settings.opening_time.strftime("%H:%M"),
                    settings.closing_time.strftime("%H:%M"),
                    ",".join(str(day) for day in settings.weekdays),
                    int(settings.enabled),
                    now,
                    now,
                ),
            )

    async def get_settings(self, guild_id: int) -> GuildSettings | None:
        return await asyncio.to_thread(self._get_settings_sync, guild_id)

    def _get_settings_sync(self, guild_id: int) -> GuildSettings | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,)
            ).fetchone()
        return self._settings_from_row(row) if row else None

    async def list_enabled_settings(self) -> list[GuildSettings]:
        return await asyncio.to_thread(self._list_enabled_settings_sync)

    def _list_enabled_settings_sync(self) -> list[GuildSettings]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM guild_settings WHERE enabled = 1").fetchall()
        return [self._settings_from_row(row) for row in rows]

    @staticmethod
    def _settings_from_row(row: sqlite3.Row) -> GuildSettings:
        from datetime import time

        return GuildSettings(
            guild_id=row["guild_id"],
            reminder_channel_id=row["reminder_channel_id"],
            report_channel_id=row["report_channel_id"],
            participant_role_id=row["participant_role_id"],
            timezone=row["timezone"],
            opening_time=time.fromisoformat(row["opening_time"]),
            closing_time=time.fromisoformat(row["closing_time"]),
            weekdays=tuple(int(day) for day in row["weekdays"].split(",")),
            enabled=bool(row["enabled"]),
        )

    async def create_round(
        self,
        guild_id: int,
        scheduled_date: date,
        opened_at: datetime,
        closes_at: datetime,
        participants: Iterable[Participant],
    ) -> tuple[DailyRound, bool]:
        participant_list = list(participants)
        return await asyncio.to_thread(
            self._create_round_sync,
            guild_id,
            scheduled_date,
            opened_at,
            closes_at,
            participant_list,
        )

    def _create_round_sync(
        self,
        guild_id: int,
        scheduled_date: date,
        opened_at: datetime,
        closes_at: datetime,
        participants: list[Participant],
    ) -> tuple[DailyRound, bool]:
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM daily_rounds WHERE guild_id = ? AND scheduled_date = ?",
                (guild_id, scheduled_date.isoformat()),
            ).fetchone()
            if existing:
                return self._round_from_row(existing), False

            cursor = connection.execute(
                """
                INSERT INTO daily_rounds (
                    guild_id, scheduled_date, opened_at, closes_at, status
                ) VALUES (?, ?, ?, ?, 'open')
                """,
                (
                    guild_id,
                    scheduled_date.isoformat(),
                    opened_at.isoformat(),
                    closes_at.isoformat(),
                ),
            )
            round_id = int(cursor.lastrowid)
            connection.executemany(
                """
                INSERT INTO round_participants (round_id, user_id, display_name)
                VALUES (?, ?, ?)
                """,
                [(round_id, item.user_id, item.display_name) for item in participants],
            )
            row = connection.execute(
                "SELECT * FROM daily_rounds WHERE id = ?", (round_id,)
            ).fetchone()
        return self._round_from_row(row), True

    async def get_round_by_date(self, guild_id: int, scheduled_date: date) -> DailyRound | None:
        return await asyncio.to_thread(self._get_round_by_date_sync, guild_id, scheduled_date)

    def _get_round_by_date_sync(self, guild_id: int, scheduled_date: date) -> DailyRound | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM daily_rounds WHERE guild_id = ? AND scheduled_date = ?",
                (guild_id, scheduled_date.isoformat()),
            ).fetchone()
        return self._round_from_row(row) if row else None

    async def get_open_round(self, guild_id: int) -> DailyRound | None:
        return await asyncio.to_thread(self._get_open_round_sync, guild_id)

    def _get_open_round_sync(self, guild_id: int) -> DailyRound | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM daily_rounds
                WHERE guild_id = ? AND status = 'open'
                ORDER BY scheduled_date DESC LIMIT 1
                """,
                (guild_id,),
            ).fetchone()
        return self._round_from_row(row) if row else None

    async def set_round_message(self, round_id: int, message_id: int) -> None:
        await asyncio.to_thread(self._set_round_message_sync, round_id, message_id)

    def _set_round_message_sync(self, round_id: int, message_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE daily_rounds SET discord_message_id = ? WHERE id = ?",
                (message_id, round_id),
            )

    async def submit_response(
        self,
        round_id: int,
        user_id: int,
        completed: str,
        doing: str,
        blockers: str,
    ) -> bool:
        return await asyncio.to_thread(
            self._submit_response_sync,
            round_id,
            user_id,
            completed,
            doing,
            blockers,
        )

    def _submit_response_sync(
        self,
        round_id: int,
        user_id: int,
        completed: str,
        doing: str,
        blockers: str,
    ) -> bool:
        now = datetime.now().astimezone().isoformat()
        with self._connect() as connection:
            round_row = connection.execute(
                "SELECT status FROM daily_rounds WHERE id = ?", (round_id,)
            ).fetchone()
            if not round_row or round_row["status"] != "open":
                raise ValueError("Esta daily não está aberta.")

            participant = connection.execute(
                """
                SELECT 1 FROM round_participants
                WHERE round_id = ? AND user_id = ?
                """,
                (round_id, user_id),
            ).fetchone()
            if not participant:
                raise PermissionError("Você não faz parte desta rodada.")

            existing = connection.execute(
                "SELECT 1 FROM responses WHERE round_id = ? AND user_id = ?",
                (round_id, user_id),
            ).fetchone()
            connection.execute(
                """
                INSERT INTO responses (
                    round_id, user_id, completed, doing, blockers,
                    submitted_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(round_id, user_id) DO UPDATE SET
                    completed = excluded.completed,
                    doing = excluded.doing,
                    blockers = excluded.blockers,
                    updated_at = excluded.updated_at
                """,
                (round_id, user_id, completed, doing, blockers, now, now),
            )
        return existing is not None

    async def get_participant_statuses(self, round_id: int) -> list[ParticipantStatus]:
        return await asyncio.to_thread(self._get_participant_statuses_sync, round_id)

    def _get_participant_statuses_sync(self, round_id: int) -> list[ParticipantStatus]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    p.user_id, p.display_name,
                    r.completed, r.doing, r.blockers,
                    r.submitted_at, r.updated_at
                FROM round_participants AS p
                LEFT JOIN responses AS r
                    ON r.round_id = p.round_id AND r.user_id = p.user_id
                WHERE p.round_id = ?
                ORDER BY p.display_name COLLATE NOCASE
                """,
                (round_id,),
            ).fetchall()

        statuses: list[ParticipantStatus] = []
        for row in rows:
            response = None
            if row["submitted_at"]:
                response = DailyResponse(
                    round_id=round_id,
                    user_id=row["user_id"],
                    completed=row["completed"],
                    doing=row["doing"],
                    blockers=row["blockers"],
                    submitted_at=datetime.fromisoformat(row["submitted_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
            statuses.append(
                ParticipantStatus(
                    participant=Participant(row["user_id"], row["display_name"]),
                    response=response,
                )
            )
        return statuses

    async def close_round(self, round_id: int) -> bool:
        return await asyncio.to_thread(self._close_round_sync, round_id)

    def _close_round_sync(self, round_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE daily_rounds SET status = 'closed'
                WHERE id = ? AND status = 'open'
                """,
                (round_id,),
            )
        return cursor.rowcount == 1

    @staticmethod
    def _round_from_row(row: sqlite3.Row) -> DailyRound:
        return DailyRound(
            id=row["id"],
            guild_id=row["guild_id"],
            scheduled_date=date.fromisoformat(row["scheduled_date"]),
            opened_at=datetime.fromisoformat(row["opened_at"]),
            closes_at=datetime.fromisoformat(row["closes_at"]),
            status=row["status"],
            discord_message_id=row["discord_message_id"],
        )
