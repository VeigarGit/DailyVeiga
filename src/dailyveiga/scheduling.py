from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from dailyveiga.models import DailyRound, GuildSettings


def local_now(settings: GuildSettings, now: datetime | None = None) -> datetime:
    zone = ZoneInfo(settings.timezone)
    if now is None:
        return datetime.now(zone)
    if now.tzinfo is None:
        raise ValueError("O horário informado precisa conter fuso horário.")
    return now.astimezone(zone)


def should_open(
    settings: GuildSettings,
    existing_round: DailyRound | None,
    now: datetime | None = None,
) -> bool:
    current = local_now(settings, now)
    return (
        settings.enabled
        and current.isoweekday() in settings.weekdays
        and settings.opening_time <= current.time().replace(tzinfo=None) < settings.closing_time
        and existing_round is None
    )


def should_close(
    settings: GuildSettings,
    existing_round: DailyRound | None,
    now: datetime | None = None,
) -> bool:
    if not existing_round or existing_round.status != "open":
        return False
    current = local_now(settings, now)
    return current.date() >= existing_round.scheduled_date and current >= existing_round.closes_at
