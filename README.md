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

- Docker Engine com o plugin Docker Compose.
- Uma aplicação criada no Discord Developer Portal.
- O **Server Members Intent** habilitado na página `Bot` da aplicação, pois o
  DailyVeiga precisa descobrir os integrantes do cargo configurado.

O bot não usa o Message Content Intent e não lê as conversas do servidor.
Python, `pip`, `venv` e SQLite não precisam estar instalados na VM.

## Configuração da aplicação no Discord

1. Crie uma aplicação em <https://discord.com/developers/applications>.
2. Na seção `Bot`, crie ou redefina o token e habilite `Server Members Intent`.
3. Em `OAuth2 > URL Generator`, selecione os escopos `bot` e
   `applications.commands`.
4. Dê ao bot as permissões `View Channels`, `Send Messages`, `Embed Links`,
   `Read Message History` e `Use Application Commands`.
5. Use a URL gerada para adicionar o bot ao servidor.

## Implantação na VM

Na primeira implantação, crie o arquivo de configuração a partir do exemplo:

```bash
cp .env.example .env
```

Edite `.env` e preencha `DISCORD_TOKEN` com o token da aplicação. Essa é a única
preparação exigida pelo bot. O arquivo é ignorado pelo Git e pelo contexto de
build, portanto o token não é incorporado à imagem.

Depois, construa e inicie todo o projeto com um único comando:

```bash
docker compose up --build -d
```

Durante o desenvolvimento, informe `DISCORD_TEST_GUILD_ID` para registrar os
comandos imediatamente apenas no servidor de teste. Sem essa variável, os
comandos são registrados globalmente e podem levar algum tempo para aparecer.

O build instala todas as dependências e executa a suíte de testes antes de criar
a imagem final. Se um teste falhar, o serviço não é atualizado.

## Operação

Consulte o estado e acompanhe os logs com:

```bash
docker compose ps
docker compose logs -f bot
```

Depois de atualizar o código, o mesmo comando reconstrói e recria apenas o que
for necessário:

```bash
docker compose up --build -d
```

Para parar e remover o contêiner sem apagar os dados:

```bash
docker compose down
```

## Persistência e backup

O banco SQLite fica em um volume criado e nomeado automaticamente pelo Docker
Compose conforme o nome do projeto. Reiniciar, reconstruir ou executar
`docker compose down` não remove esse volume. Não use `docker compose down -v`
a menos que queira apagar definitivamente as configurações, rodadas e respostas.

Para gerar um backup consistente do banco no diretório atual da VM:

```bash
docker compose stop bot
docker compose cp bot:/app/data/dailyveiga.db ./dailyveiga-backup.db
docker compose start bot
```

A antiga pasta local `./data` não é montada nem enviada à imagem. Uma implantação
nova na VM começa com um banco vazio no volume Docker.

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

## Limitações atuais

- As três perguntas são fixas: concluído, próximo trabalho e impedimentos.
- Ainda não há lembretes adicionais antes do fechamento.
- O SQLite é adequado para equipes pequenas; suporte a PostgreSQL pode ser
  adicionado posteriormente.
