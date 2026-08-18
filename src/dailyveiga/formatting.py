from __future__ import annotations

from dailyveiga.models import ParticipantStatus
from dailyveiga.service import split_statuses


def truncate(value: str, limit: int = 1000) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def format_response(status: ParticipantStatus) -> str:
    if status.response is None:
        raise ValueError("Não é possível formatar uma resposta ausente.")
    response = status.response
    return truncate(
        f"**✅ Concluído:** {response.completed}\n"
        f"**🎯 Próximo:** {response.doing}\n"
        f"**🚧 Impedimentos:** {response.blockers}"
    )


def pending_names(statuses: list[ParticipantStatus]) -> str:
    _, pending = split_statuses(statuses)
    if not pending:
        return "Ninguém — todos responderam."
    return truncate(", ".join(item.participant.display_name for item in pending), 1000)
