from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time


@dataclass(frozen=True, slots=True)
class GuildSettings:
    guild_id: int
    reminder_channel_id: int
    report_channel_id: int
    participant_role_id: int
    timezone: str
    opening_time: time
    closing_time: time
    weekdays: tuple[int, ...]
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class Participant:
    user_id: int
    display_name: str


@dataclass(frozen=True, slots=True)
class DailyRound:
    id: int
    guild_id: int
    scheduled_date: date
    opened_at: datetime
    closes_at: datetime
    status: str
    discord_message_id: int | None = None


@dataclass(frozen=True, slots=True)
class DailyResponse:
    round_id: int
    user_id: int
    completed: str
    doing: str
    blockers: str
    submitted_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ParticipantStatus:
    participant: Participant
    response: DailyResponse | None
