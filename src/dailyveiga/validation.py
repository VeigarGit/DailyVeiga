from __future__ import annotations

from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def parse_time(value: str) -> time:
    try:
        hour_text, minute_text = value.strip().split(":", maxsplit=1)
        parsed = time(hour=int(hour_text), minute=int(minute_text))
    except (TypeError, ValueError) as exc:
        raise ValueError("Use o formato HH:MM, por exemplo 09:00.") from exc
    return parsed


def parse_weekdays(value: str) -> tuple[int, ...]:
    try:
        days = tuple(sorted({int(item.strip()) for item in value.split(",") if item.strip()}))
    except ValueError as exc:
        raise ValueError("Informe os dias como números separados por vírgula.") from exc
    if not days or any(day < 1 or day > 7 for day in days):
        raise ValueError("Os dias devem estar entre 1 (segunda) e 7 (domingo).")
    return days


def validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Fuso horário desconhecido: {value}") from exc
    return value


def validate_schedule(opening_time: time, closing_time: time) -> None:
    if opening_time >= closing_time:
        raise ValueError("O horário de fechamento deve ser posterior ao de abertura.")
