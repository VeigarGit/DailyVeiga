from __future__ import annotations

import asyncio
import tempfile
import unittest
from datetime import date, time
from pathlib import Path

from dailyveiga.database import Database
from dailyveiga.models import GuildSettings, Participant
from dailyveiga.service import DailyService, split_statuses


class DatabaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp_directory.name) / "test.db")
        self.service = DailyService(self.database)
        asyncio.run(self.database.initialize())
        self.settings = GuildSettings(
            guild_id=123,
            reminder_channel_id=10,
            report_channel_id=11,
            participant_role_id=12,
            timezone="America/Belem",
            opening_time=time(9, 0),
            closing_time=time(10, 0),
            weekdays=(1, 2, 3, 4, 5),
        )
        asyncio.run(self.database.upsert_settings(self.settings))

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def test_settings_are_persisted(self) -> None:
        stored = asyncio.run(self.database.get_settings(123))
        self.assertEqual(stored, self.settings)

    def test_round_response_edit_status_and_close(self) -> None:
        participants = [Participant(1, "Ana"), Participant(2, "Bruno")]
        daily_round, created = asyncio.run(
            self.service.open_round(self.settings, participants, date(2026, 8, 18))
        )
        self.assertTrue(created)

        duplicate, duplicate_created = asyncio.run(
            self.service.open_round(self.settings, participants, date(2026, 8, 18))
        )
        self.assertFalse(duplicate_created)
        self.assertEqual(duplicate.id, daily_round.id)

        updated = asyncio.run(self.service.answer(123, 1, "Login", "Testes", "Nenhum"))
        self.assertFalse(updated)
        updated = asyncio.run(self.service.answer(123, 1, "Login pronto", "Testes", "Acesso"))
        self.assertTrue(updated)

        _, statuses = asyncio.run(self.service.status(123))
        answered, pending = split_statuses(statuses)
        self.assertEqual([item.participant.display_name for item in answered], ["Ana"])
        self.assertEqual([item.participant.display_name for item in pending], ["Bruno"])
        self.assertEqual(answered[0].response.completed, "Login pronto")

        _, report_statuses = asyncio.run(self.service.close(123))
        self.assertEqual(len(report_statuses), 2)
        with self.assertRaisesRegex(ValueError, "Não existe uma daily aberta"):
            asyncio.run(self.service.status(123))

    def test_outsider_cannot_answer(self) -> None:
        asyncio.run(
            self.service.open_round(self.settings, [Participant(1, "Ana")], date(2026, 8, 19))
        )
        with self.assertRaisesRegex(PermissionError, "não faz parte"):
            asyncio.run(self.service.answer(123, 99, "A", "B", "C"))
