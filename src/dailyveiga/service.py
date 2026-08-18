from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from dailyveiga.database import Database
from dailyveiga.models import DailyRound, GuildSettings, Participant, ParticipantStatus


class DailyService:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def open_round(
        self,
        settings: GuildSettings,
        participants: list[Participant],
        scheduled_date: date | None = None,
    ) -> tuple[DailyRound, bool]:
        zone = ZoneInfo(settings.timezone)
        now = datetime.now(zone)
        target_date = scheduled_date or now.date()
        opened_at = datetime.combine(target_date, settings.opening_time, tzinfo=zone)
        closes_at = datetime.combine(target_date, settings.closing_time, tzinfo=zone)
        return await self.database.create_round(
            guild_id=settings.guild_id,
            scheduled_date=target_date,
            opened_at=opened_at,
            closes_at=closes_at,
            participants=participants,
        )

    async def answer(
        self,
        guild_id: int,
        user_id: int,
        completed: str,
        doing: str,
        blockers: str,
    ) -> bool:
        daily_round = await self.database.get_open_round(guild_id)
        if not daily_round:
            raise ValueError("Não existe uma daily aberta neste servidor.")
        values = (completed.strip(), doing.strip(), blockers.strip())
        if any(not value for value in values):
            raise ValueError("Preencha todas as perguntas antes de enviar.")
        return await self.database.submit_response(
            daily_round.id,
            user_id,
            completed=values[0],
            doing=values[1],
            blockers=values[2],
        )

    async def status(self, guild_id: int) -> tuple[DailyRound, list[ParticipantStatus]]:
        daily_round = await self.database.get_open_round(guild_id)
        if not daily_round:
            raise ValueError("Não existe uma daily aberta neste servidor.")
        return daily_round, await self.database.get_participant_statuses(daily_round.id)

    async def close(self, guild_id: int) -> tuple[DailyRound, list[ParticipantStatus]]:
        daily_round = await self.database.get_open_round(guild_id)
        if not daily_round:
            raise ValueError("Não existe uma daily aberta neste servidor.")
        statuses = await self.database.get_participant_statuses(daily_round.id)
        await self.database.close_round(daily_round.id)
        return daily_round, statuses


def split_statuses(
    statuses: list[ParticipantStatus],
) -> tuple[list[ParticipantStatus], list[ParticipantStatus]]:
    answered = [status for status in statuses if status.response is not None]
    pending = [status for status in statuses if status.response is None]
    return answered, pending
