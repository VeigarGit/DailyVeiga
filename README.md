# DailyVeiga

Bot auto-hospedado para organizar dailys diretamente no Discord, sem depender
do serviço DailyBot.

## O que já funciona

- Configuração por servidor com `/daily configurar`.
- Participantes selecionados por cargo do Discord.
- Abertura manual com `/daily abrir`.
- Abertura e fechamento automáticos nos dias e horários configurados.
- Resposta por modal usando `/daily responder` ou o botão da mensagem.
- Edição da resposta enquanto a rodada estiver aberta.
- Consulta de pendentes com `/daily status`.
- Fechamento manual com `/daily fechar`.
- Relatório em embeds, com destaque para impedimentos e ausentes.
- Persistência em SQLite e recuperação segura após reinicialização.

## Requisitos

- Python 3.11 ou superior; ou Docker.
- Uma aplicação criada no Discord Developer Portal.
- O **Server Members Intent** habilitado na página `Bot` da aplicação, pois o
  DailyVeiga precisa descobrir os integrantes do cargo configurado.

O bot não usa o Message Content Intent e não lê as conversas do servidor.

## Configuração da aplicação no Discord

1. Crie uma aplicação em <https://discord.com/developers/applications>.
2. Na seção `Bot`, crie ou redefina o token e habilite `Server Members Intent`.
3. Em `OAuth2 > URL Generator`, selecione os escopos `bot` e
   `applications.commands`.
4. Dê ao bot as permissões `View Channels`, `Send Messages`, `Embed Links`,
   `Read Message History` e `Use Application Commands`.
5. Use a URL gerada para adicionar o bot ao servidor.

## Execução local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Edite `.env`, carregue as variáveis e execute:

```bash
set -a
source .env
set +a
dailyveiga
```

Durante o desenvolvimento, informe `DISCORD_TEST_GUILD_ID` para registrar os
comandos imediatamente apenas no servidor de teste. Sem essa variável, os
comandos são registrados globalmente e podem levar algum tempo para aparecer.

## Execução com Docker

```bash
cp .env.example .env
docker compose up -d --build
docker compose logs -f
```

O banco fica no volume `./data`. Faça backup desse diretório regularmente.

## Primeiro uso

Um administrador configura a rotina:

```text
/daily configurar
```

Parâmetros de exemplo:

```text
canal_lembrete: #daily
canal_relatorio: #daily-relatorios
cargo_participantes: @Equipe
abertura: 09:00
fechamento: 10:00
dias: 1,2,3,4,5
fuso: America/Belem
```

Os dias seguem ISO: `1` é segunda-feira e `7` é domingo.

Para testar sem esperar o horário:

```text
/daily abrir
/daily responder
/daily status
/daily fechar
```

## Desenvolvimento

```bash
python -m unittest discover -s tests -v
```

## Limitações atuais

- As três perguntas são fixas: concluído, próximo trabalho e impedimentos.
- Ainda não há lembretes adicionais antes do fechamento.
- O SQLite é adequado para equipes pequenas; suporte a PostgreSQL pode ser
  adicionado posteriormente.
