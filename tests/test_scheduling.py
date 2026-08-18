from __future__ import annotations

import unittest
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from dailyveiga.models import DailyRound, GuildSettings
from dailyveiga.scheduling import should_close, should_open


class SchedulingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = GuildSettings(
            guild_id=1,
            reminder_channel_id=2,
            report_channel_id=3,
            participant_role_id=4,
            timezone="America/Belem",
            opening_time=time(9),
            closing_time=time(10),
            weekdays=(1, 2, 3, 4, 5),
        )
        self.zone = ZoneInfo("America/Belem")

    def test_opens_during_window_on_workday(self) -> None:
        monday = datetime(2026, 8, 17, 9, 15, tzinfo=self.zone)
        self.assertTrue(should_open(self.settings, None, monday))

    def test_does_not_open_after_deadline_or_weekend(self) -> None:
        monday_late = datetime(2026, 8, 17, 10, 1, tzinfo=self.zone)
        sunday = datetime(2026, 8, 16, 9, 15, tzinfo=self.zone)
        self.assertFalse(should_open(self.settings, None, monday_late))
        self.assertFalse(should_open(self.settings, None, sunday))

    def test_closes_open_round_at_deadline(self) -> None:
        daily_round = DailyRound(
            id=1,
            guild_id=1,
            scheduled_date=date(2026, 8, 17),
            opened_at=datetime(2026, 8, 17, 9, tzinfo=self.zone),
            closes_at=datetime(2026, 8, 17, 10, tzinfo=self.zone),
            status="open",
        )
        deadline = datetime(2026, 8, 17, 10, tzinfo=self.zone)
        self.assertTrue(should_close(self.settings, daily_round, deadline))

    def test_closes_old_round_after_restart(self) -> None:
        daily_round = DailyRound(
            id=1,
            guild_id=1,
            scheduled_date=date(2026, 8, 17),
            opened_at=datetime(2026, 8, 17, 9, tzinfo=self.zone),
            closes_at=datetime(2026, 8, 17, 10, tzinfo=self.zone),
            status="open",
        )
        next_day = datetime(2026, 8, 18, 8, tzinfo=self.zone)
        self.assertTrue(should_close(self.settings, daily_round, next_day))
