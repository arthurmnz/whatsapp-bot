# 💡 Sugestões de Segurança, Arquitetura e Qualidade (`SUGGESTIONS.md`)

Este documento centraliza recomendações técnicas, melhorias de segurança e pontos de atenção identificados durante ciclos de revisão (Security Analyst, Tester e Code Reviewer). Sempre que novas oportunidades forem levantadas, elas serão registradas aqui de forma priorizada.

---

## 🔒 1. Segurança (Security Analyst)

### 1.1. Controle de Acesso (`ADMIN_JIDS`) para Comandos Críticos
- **Contexto:** Os comandos `/ligar-win`, `/desligar-win`, `/reiniciar-win` e `/status-win` em [`app/api/webhook/handlers/command_handler.py`](file:///home/arthurmnz/code/whatsApp-bot/app/api/webhook/handlers/command_handler.py) executam ações de infraestrutura no PC Windows via SSH e Wake-on-LAN.
- **Risco:** Caso qualquer contato envie um desses comandos para o número conectado à Evolution API, a ação será executada se não houver restrição de remetente (`remote_jid`).
- **Recomendação:**
  - Adicionar a variável de ambiente opcional `WEBHOOK_ADMIN_JIDS` (ex: `5511999999999@s.whatsapp.net,5574999999999@s.whatsapp.net`).
  - Validar em `CommandHandler.handle()` se `event.remote_jid` pertence à whitelist antes de invocar funções de `app.modules.devices_control`.
  - Retornar mensagem de acesso negado (`⛔ Acesso negado: remetente não autorizado.`) quando um remetente não listado tentar acionar comandos administrativos.

### 1.2. Validação de `remote_jid` Ausente na Triagem
- **Contexto:** Em [`app/api/webhook/triage.py`](file:///home/arthurmnz/code/whatsApp-bot/app/api/webhook/triage.py), `WebhookTriageEngine.evaluate()` filtra eventos diferentes de `messages.upsert`, `fromMe=True` e `empty_message`.
- **Risco:** Se um payload malformado contiver texto válido mas `remote_jid` vazio (`""`), o fluxo prosseguirá até o Redis (`append_messages("", ...)`) e até a chamada HTTP da Evolution API (`send_text(to="", ...)`).
- **Recomendação:**
  - Adicionar verificação em `WebhookTriageEngine.evaluate()`:
    ```python
    if not event.remote_jid or not event.remote_jid.strip():
        return TriageDecision(action=ActionType.IGNORE, reason="missing_remote_jid")
    ```

### 1.3. Mitigação de Log Injection no Webhook
- **Contexto:** Em [`app/api/webhook/router.py`](file:///home/arthurmnz/code/whatsApp-bot/app/api/webhook/router.py), os campos `event.remote_jid`, `event.push_name` e `event.message_text` vêm de payload externo e são interpolados em `logger.info`.
- **Risco:** Caracteres de controle como `\r` e `\n` no `push_name` ou `message_text` permitem forjar linhas falsas nos logs do container.
- **Recomendação:**
  - Sanitizar quebras de linha (`value.replace("\r", " ").replace("\n", " ")`) antes de registrar entradas no logger.

### 1.4. Autenticação do Endpoint `POST /webhook`
- **Contexto:** A rota `/webhook` aceita requisições POST sem verificação de token/header na aplicação FastAPI.
- **Recomendação:**
  - Validar um header compartilhado (ex: `X-Webhook-Token` ou `apikey`) configurado na Evolution API para garantir que apenas a instância autorizada da Evolution API consiga postar eventos no bot.

---

## 🧪 2. Testes e Qualidade (Tester)

### 2.1. Alinhamento dos Testes de `devices_control` (`tests/test_devices_control.py`)
- **Contexto:** A implementação em [`app/modules/devices_control/config.py`](file:///home/arthurmnz/code/whatsApp-bot/app/modules/devices_control/config.py) e [`app/modules/devices_control/service.py`](file:///home/arthurmnz/code/whatsApp-bot/app/modules/devices_control/service.py) foi atualizada para formatar o MAC address com hífens (`10-FF-E0-01-AA-D1`) e utilizar a biblioteca `wakeonlan.wake()`.
- **Impacto atual:** 7 testes unitários em [`tests/test_devices_control.py`](file:///home/arthurmnz/code/whatsApp-bot/tests/test_devices_control.py) ainda aguardam o formato antigo com dois-pontos (`10:FF:E0:01:AA:D1`) e mock direto de `socket.socket`.
- **Recomendação:**
  - Atualizar as asserções de `tests/test_devices_control.py` para refletir o formato canônico `XX-XX-XX-XX-XX-XX` e realizar o mock de `wakeonlan.wake` nos testes de Wake-on-LAN.

---

## 🐳 3. Infraestrutura e Rede (Homelab / Docker)

### 3.1. Rede `bridge` vs Wake-on-LAN Broadcast no Docker
- **Contexto:** O `docker-compose.yml` utiliza a rede `whatsapp-net` com `driver: bridge` para permitir resolução de DNS interna entre os containers `agent` e `redis` (`redis://redis:6379/6`) e mapeamento de portas (`5050:5050`).
- **Ponto de atenção para Wake-on-LAN (`/ligar-win`):**
  - Em redes Docker do tipo `bridge` (NAT), pacotes UDP broadcast enviados para `255.255.255.255` ficam restritos à sub-rede virtual do Docker e podem não alcançar a placa de rede física da LAN (`192.168.0.x`).
  - **Alternativas caso o WOL não atravesse a bridge no homelab:**
    1. Definir `WIN_MNZ_BROADCAST=192.168.0.255` (directed broadcast da sub-rede local) e passar `ip_address=config.broadcast, port=config.port` na chamada `wakeonlan.wake(config.mac, ip_address=config.broadcast, port=config.port)`.
    2. Ou, caso o roteador/kernel bloqueie broadcast vindo da bridge Docker, usar `network_mode: host` diretamente no serviço `agent` (sem declarar `driver: host` na seção `networks:`) e apontar `CACHE_REDIS_URI=redis://127.0.0.1:6379/6` expondo a porta `127.0.0.1:6379:6379` no serviço `redis`.
