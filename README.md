# WhatsApp Bot (Evolution API & Cron Scheduler)

Bot inteligente para WhatsApp integrado à **Evolution API**, desenvolvido em Python com arquitetura assíncrona. O projeto combina recepção e envio de mensagens via Webhook (FastAPI), agente de inteligência artificial com memória em Redis e um módulo autônomo de agendamento de mensagens (Cron Jobs) via APScheduler.

---

## 🚀 Funcionalidades Principais

### 1. Client Evolution API (`src/evolution_client.py`)
- **Envio Assíncrono e Síncrono:** Funções `send_text` (usando `httpx.AsyncClient`) e `send_text_sync` (usando `httpx.Client`).
- **Fallback Automático de Payload:** Tenta primeiro a estrutura v2 (`{"number": to, "text": text}`); caso receba status 400 por incompatibilidade de schema, realiza fallback transparente para o formato v1 (`{"textMessage": {"text": text}, "options": {...}}`).
- **Resolução Automática do 9º Dígito (Brasil):** Fallback automático entre 8 e 9 dígitos para destinatários brasileiros (DDI 55), convertendo números conforme a disponibilidade na operadora/WhatsApp.
- **Segurança e Redação de Segredos:** Mascaramento de chaves de API (`***REDACTED***`) em mensagens de log, headers e exceções `httpx.HTTPStatusError`.
- **Validação Estrita:** Proteção contra injeção de caracteres de controle (`\r`, `\n`, `\0`) nos destinatários e timeout configurado para evitar bloqueios de rede.

### 2. Agendador de Mensagens / Cron Jobs (`src/scheduler/`)
- **Modelagem e Validação Pydantic v2:**
  - Validação estrita de expressões Cron Unix de 5 campos via APScheduler `CronTrigger`.
  - Sanitização de destinatários (contatos `@s.whatsapp.net` e grupos `@g.us`, rejeitando caracteres inválidos e garantindo contatos numéricos válidos).
  - Validação de fusos horários IANA (padrão: `America/Sao_Paulo`).
- **Templates Dinâmicos:** Interpolação automática de variáveis no texto da mensagem:
  - `{dia_semana}`: dia da semana por extenso em português (ex: *segunda-feira*).
  - `{data}`: data formatada em `DD/MM/AAAA`.
  - `{hora}`: hora formatada em `HH:MM`.
  - Preservação segura de chaves arbitrárias sem quebras por `KeyError`.
- **APScheduler Integrado:** Gerenciamento de tarefas em background (`CronScheduler`) com disparo sequencial e intervalo configurável (`delay_seconds`).
- **Runner Independente:** CLI autônoma com controle de ciclo de vida e encerramento gracioso via sinais `SIGINT`/`SIGTERM`.

### 3. Webhook & Agente Conversacional (`src/webhook.py`, `src/memory.py`, `src/agent/`)
- **Servidor FastAPI:** Endpoint `/webhook` para receber eventos `messages.upsert` da Evolution API.
- **Gerenciamento de Histórico:** Armazenamento de turnos no Redis com expiração automática (TTL) e comandos de reset (`/limpar`, `/clear`, `/reset`).
- **Agente LangChain / OpenRouter:** Estrutura para processamento de linguagem natural e chamada de ferramentas (Tool Calling).

---

## 📁 Estrutura do Projeto

```text
whatsApp-bot/
├── config/
│   └── scheduled_messages.json     # Configuração dos jobs agendados
├── src/
│   ├── evolution_client.py         # Client HTTP (síncrono/assíncrono) para Evolution API
│   ├── memory.py                   # Gerenciamento de memória e histórico no Redis
│   ├── webhook.py                  # Servidor FastAPI para recepção de webhooks
│   ├── agent/
│   │   ├── __init__.py
│   │   └── agent.py                # Agente LangChain/OpenRouter e ferramentas
│   └── scheduler/
│       ├── __init__.py             # Exportações públicas do módulo
│       ├── config.py               # Modelos Pydantic v2 e parser de configuração
│       ├── runner.py               # Processo de execução independente do agendador
│       └── service.py              # CronScheduler, renderizador e despachador
├── tests/
│   ├── test_evolution_client.py    # Testes unitários do client da Evolution API
│   └── test_scheduler.py           # Testes unitários do scheduler e Pydantic
├── docker-compose.yml              # Orquestração do agente e serviço Redis
├── Dockerfile                      # Imagem do container da aplicação
├── requirements.txt                # Dependências Python do projeto
└── README.md                       # Documentação do projeto
```

---

## ⚙️ Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto baseado no `.env.example`:

```bash
# Evolution API
EVOLUTION_API_URL=http://localhost:8080
EVOLUTION_API_KEY=sua-chave-api-evolution
EVOLUTION_INSTANCE=sua_instancia

# LLM / OpenRouter
OPENROUTER_API_KEY=sua-chave-openrouter

# Redis / Cache
CACHE_REDIS_URI=redis://localhost:6379/0
CACHE_REDIS_ENABLED=true
```

---

## 🛠️ Como Executar

### 1. Preparação do Ambiente

Ative o ambiente virtual e instale as dependências:

```bash
# Ativação do virtualenv
source venv/bin/activate

# Instalação de dependências (se necessário)
pip install -r requirements.txt
```

---

### 2. Usando o Client da Evolution API

Você pode importar e utilizar o client diretamente em seus scripts ou módulos:

#### Envio Assíncrono (`send_text`):
```python
import asyncio
from src.evolution_client import send_text

async def main():
    resposta = await send_text(
        to="5511999999999",
        text="Olá! Mensagem enviada via Evolution Client assíncrono."
    )
    print(resposta)

asyncio.run(main())
```

#### Envio Síncrono (`send_text_sync`):
```python
from src.evolution_client import send_text_sync

resposta = send_text_sync(
    to="5511999999999",
    text="Olá! Mensagem enviada via Evolution Client síncrono."
)
print(resposta)
```

---

### 3. Configurando e Rodando o Agendador (Cron Scheduler)

Edite o arquivo `config/scheduled_messages.json` para definir as mensagens e horários:

```json
{
  "timezone": "America/Sao_Paulo",
  "jobs": [
    {
      "id": "lembrete_manha",
      "name": "Lembrete Diário da Manhã",
      "enabled": true,
      "cron": "0 9 * * 1-5",
      "recipients": [
        "5511999999999"
      ],
      "message": "Bom dia! Hoje é {dia_semana}, {data} e agora são {hora}. Tenha um excelente dia!",
      "delay_seconds": 0.5
    }
  ]
}
```

Para iniciar o processo do agendador:

```bash
python -m src.scheduler.runner
```

*(Opcional) Passe o caminho de um arquivo de configuração alternativo:*
```bash
python -m src.scheduler.runner caminho/para/outro_config.json
```

---

### 4. Rodando o Webhook FastAPI

Para iniciar o servidor FastAPI e receber eventos de mensagens do WhatsApp:

```bash
# Execução direta com uvicorn
uvicorn src.webhook:app --host 0.0.0.0 --port 5000 --reload
```

Ou através do **Docker Compose** (inicia a aplicação e o Redis):

```bash
docker compose up -d
```

---

### 5. Executando a Suíte de Testes

Os testes unitários validam toda a lógica de sanitização de destinatários, fallback de formato e dígitos, proteção de segredos, modelos Pydantic e agendamentos:

```bash
./venv/bin/pytest -v
```
