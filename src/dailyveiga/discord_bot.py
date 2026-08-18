from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from dailyveiga.database import Database
from dailyveiga.formatting import format_response, pending_names
from dailyveiga.models import GuildSettings, Participant, ParticipantStatus
from dailyveiga.scheduling import should_close, should_open
from dailyveiga.service import DailyService, split_statuses
from dailyveiga.validation import (
    parse_time,
    parse_weekdays,
    validate_schedule,
    validate_timezone,
)

LOGGER = logging.getLogger(__name__)


class DailyModal(discord.ui.Modal, title="Responder daily"):
    completed = discord.ui.TextInput(
        label="O que você concluiu?",
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )
    doing = discord.ui.TextInput(
        label="Em que trabalhará agora?",
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )
    blockers = discord.ui.TextInput(
        label="Existe algum impedimento?",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        default="Nenhum",
    )

    def __init__(self, service: DailyService, guild_id: int) -> None:
        super().__init__()
        self.service = service
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            updated = await self.service.answer(
                self.guild_id,
                interaction.user.id,
                str(self.completed),
                str(self.doing),
                str(self.blockers),
            )
        except (ValueError, PermissionError) as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        verb = "atualizada" if updated else "registrada"
        await interaction.response.send_message(
            f"✅ Sua resposta foi {verb} com sucesso.", ephemeral=True
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        LOGGER.exception("Falha ao enviar resposta da daily", exc_info=error)
        message = "Não consegui salvar a resposta. Tente novamente em instantes."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


class ResponseView(discord.ui.View):
    def __init__(self, service: DailyService) -> None:
        super().__init__(timeout=None)
        self.service = service

    @discord.ui.button(
        label="Responder daily",
        style=discord.ButtonStyle.primary,
        emoji="📝",
        custom_id="dailyveiga:respond",
    )
    async def respond(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "Use este botão dentro do servidor.", ephemeral=True
            )
            return
        await interaction.response.send_modal(DailyModal(self.service, interaction.guild_id))


class DailyCog(commands.Cog):
    daily = app_commands.Group(name="daily", description="Organize as dailys da equipe")

    def __init__(self, bot: commands.Bot, database: Database) -> None:
        self.bot = bot
        self.database = database
        self.service = DailyService(database)
        self.scheduler.start()

    async def cog_unload(self) -> None:
        self.scheduler.cancel()

    @daily.command(name="ping", description="Verifica se o DailyVeiga está online")
    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            f"✅ DailyVeiga online — {round(self.bot.latency * 1000)} ms", ephemeral=True
        )

    @daily.command(name="configurar", description="Configura a rotina de dailys")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        canal_lembrete="Canal onde a daily será aberta",
        canal_relatorio="Canal que receberá o relatório final",
        cargo_participantes="Cargo que identifica os participantes",
        abertura="Horário HH:MM",
        fechamento="Horário HH:MM",
        dias="Dias ISO separados por vírgula: 1=segunda, 7=domingo",
        fuso="Fuso IANA, por exemplo America/Belem",
    )
    async def configure(
        self,
        interaction: discord.Interaction,
        canal_lembrete: discord.TextChannel,
        canal_relatorio: discord.TextChannel,
        cargo_participantes: discord.Role,
        abertura: str = "09:00",
        fechamento: str = "10:00",
        dias: str = "1,2,3,4,5",
        fuso: str = "America/Belem",
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "Este comando só funciona dentro de um servidor.", ephemeral=True
            )
            return
        try:
            opening_time = parse_time(abertura)
            closing_time = parse_time(fechamento)
            weekdays = parse_weekdays(dias)
            timezone = validate_timezone(fuso)
            validate_schedule(opening_time, closing_time)
        except (ValueError, TypeError) as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        settings = GuildSettings(
            guild_id=interaction.guild_id,
            reminder_channel_id=canal_lembrete.id,
            report_channel_id=canal_relatorio.id,
            participant_role_id=cargo_participantes.id,
            timezone=timezone,
            opening_time=opening_time,
            closing_time=closing_time,
            weekdays=weekdays,
        )
        await self.database.upsert_settings(settings)
        await interaction.response.send_message(
            "✅ Daily configurada.\n"
            f"Abertura: **{abertura}** · Fechamento: **{fechamento}**\n"
            f"Dias: **{dias}** · Fuso: **{fuso}**\n"
            f"Participantes: {cargo_participantes.mention}",
            ephemeral=True,
        )

    @daily.command(name="abrir", description="Abre a daily de hoje manualmente")
    @app_commands.checks.has_permissions(administrator=True)
    async def open(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "Este comando só funciona dentro de um servidor.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            daily_round, created = await self._open_for_guild(interaction.guild)
        except (ValueError, TypeError) as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        if not created:
            await interaction.followup.send("A daily de hoje já foi criada.", ephemeral=True)
            return
        await interaction.followup.send(
            f"✅ Daily aberta. Rodada #{daily_round.id}.", ephemeral=True
        )

    @daily.command(name="responder", description="Responde ou edita a daily aberta")
    async def answer(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "Este comando só funciona dentro de um servidor.", ephemeral=True
            )
            return
        await interaction.response.send_modal(DailyModal(self.service, interaction.guild_id))

    @daily.command(name="status", description="Mostra quem respondeu e quem está pendente")
    async def status(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "Este comando só funciona dentro de um servidor.", ephemeral=True
            )
            return
        try:
            daily_round, statuses = await self.service.status(interaction.guild_id)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        answered, _pending = split_statuses(statuses)
        await interaction.response.send_message(
            f"📊 **Daily de {daily_round.scheduled_date.strftime('%d/%m/%Y')}**\n"
            f"Responderam: **{len(answered)}/{len(statuses)}**\n"
            f"Pendentes: {pending_names(statuses)}",
            ephemeral=True,
        )

    @daily.command(name="fechar", description="Fecha a daily e publica o relatório")
    @app_commands.checks.has_permissions(administrator=True)
    async def close(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "Este comando só funciona dentro de um servidor.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await self._close_for_guild(interaction.guild)
        except (ValueError, TypeError) as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        await interaction.followup.send("✅ Daily fechada e relatório publicado.", ephemeral=True)

    async def _open_for_guild(self, guild: discord.Guild):
        settings = await self.database.get_settings(guild.id)
        if not settings:
            raise ValueError("Configure o bot primeiro com `/daily configurar`.")
        channel = guild.get_channel(settings.reminder_channel_id)
        if not isinstance(channel, discord.TextChannel):
            raise TypeError("O canal de lembrete configurado não está disponível.")
        role = guild.get_role(settings.participant_role_id)
        if not role:
            raise ValueError("O cargo configurado não existe mais.")
        participants = [
            Participant(member.id, member.display_name) for member in role.members if not member.bot
        ]
        if not participants:
            raise ValueError("O cargo configurado não possui participantes humanos.")

        daily_round, created = await self.service.open_round(settings, participants)
        if not created and daily_round.discord_message_id is not None:
            return daily_round, False

        embed = discord.Embed(
            title=f"☀️ Daily — {daily_round.scheduled_date.strftime('%d/%m/%Y')}",
            description=(
                f"Responda até **{settings.closing_time.strftime('%H:%M')}** ({settings.timezone})."
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"{len(participants)} participante(s)")
        message = await channel.send(embed=embed, view=ResponseView(self.service))
        await self.database.set_round_message(daily_round.id, message.id)
        return daily_round, True

    async def _close_for_guild(self, guild: discord.Guild) -> None:
        settings = await self.database.get_settings(guild.id)
        if not settings:
            raise ValueError("O servidor ainda não foi configurado.")
        daily_round, statuses = await self.service.close(guild.id)
        channel = guild.get_channel(settings.report_channel_id)
        if not isinstance(channel, discord.TextChannel):
            raise TypeError("O canal de relatório configurado não está disponível.")
        for embed in build_report_embeds(daily_round.scheduled_date.strftime("%d/%m/%Y"), statuses):
            await channel.send(embed=embed)

    @tasks.loop(seconds=30)
    async def scheduler(self) -> None:
        settings_list = await self.database.list_enabled_settings()
        for settings in settings_list:
            guild = self.bot.get_guild(settings.guild_id)
            if guild is None:
                continue
            try:
                current = datetime.now(ZoneInfo(settings.timezone))
                today_round = await self.database.get_round_by_date(guild.id, current.date())
                open_round = await self.database.get_open_round(guild.id)
                if should_close(settings, open_round, current):
                    await self._close_for_guild(guild)
                    open_round = None
                if should_open(settings, today_round, current) and open_round is None:
                    await self._open_for_guild(guild)
            except Exception:
                LOGGER.exception("Falha no agendador do servidor %s", guild.id)

    @scheduler.before_loop
    async def before_scheduler(self) -> None:
        await self.bot.wait_until_ready()

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            message = "Somente administradores podem usar este comando."
        else:
            LOGGER.exception("Erro em comando Discord", exc_info=error)
            message = "O comando falhou. Consulte os logs do bot."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


def build_report_embeds(
    formatted_date: str, statuses: list[ParticipantStatus]
) -> list[discord.Embed]:
    answered, _pending = split_statuses(statuses)
    chunks = [answered[index : index + 10] for index in range(0, len(answered), 10)] or [[]]
    embeds: list[discord.Embed] = []
    for index, chunk in enumerate(chunks, start=1):
        title = f"📋 Daily — {formatted_date}"
        if len(chunks) > 1:
            title += f" ({index}/{len(chunks)})"
        embed = discord.Embed(title=title, color=discord.Color.green())
        for status in chunk:
            embed.add_field(
                name=f"👤 {status.participant.display_name}",
                value=format_response(status),
                inline=False,
            )
        if index == len(chunks):
            embed.add_field(
                name="⏳ Não responderam",
                value=pending_names(statuses),
                inline=False,
            )
        embeds.append(embed)
    return embeds
