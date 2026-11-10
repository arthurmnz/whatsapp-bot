from contextlib import asynccontextmanager
import inspect
import logging
import os
import traceback

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
import uvicorn

# from src.agent.agent import agent_executor
from src.evolution_client import send_text
from src.memory import append_messages, clear_history, get_history
from src.scheduler import CronScheduler, load_scheduler_config

load_dotenv()

PORT = int(os.environ.get("PORT", 5000))

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida da aplicação FastAPI: inicia e encerra o CronScheduler."""
    logger.info("Iniciando CronScheduler no lifespan do FastAPI...")
    scheduler = CronScheduler()
    try:
        config = load_scheduler_config("config/scheduled_messages.json")
        scheduler.start()
        scheduler.register_jobs(config)
        logger.info("CronScheduler iniciado com sucesso.")
    except Exception as exc:
        logger.error("Erro ao iniciar CronScheduler: %s", exc)

    yield

    logger.info("Encerrando CronScheduler...")
    scheduler.shutdown()


app = FastAPI(title="C3PO – Webhook", lifespan=lifespan)


async def handle_message(request: Request):
    data = await request.json()
    event_type = data.get("event")

    if event_type != "messages.upsert":
        raise HTTPException(status_code=400, detail={"status": "ignored", "reason": "event_not_handled"})

    message_info = data.get("data", {})
    from_me = message_info.get("key", {}).get("fromMe", False)

    if from_me:
        raise HTTPException(status_code=400, detail={"status": "ignored", "reason": "fromMe"})

    message_obj = message_info.get("message", {})
    message_text = (
        message_obj.get("conversation")
        or message_obj.get("extendedTextMessage", {}).get("text")
        or ""
    )

    remote_jid = message_info.get("key", {}).get("remoteJid", "")
    push_name = message_info.get("pushName", "")
    print(f"\n[{remote_jid}] {message_text}")

    if not message_text:
        raise HTTPException(status_code=400, detail={"status": "ignored", "reason": "empty_message"})

    # Comando para limpar histórico
    if message_text.strip().lower() in ("/limpar", "/clear", "/reset"):
        clear_history(remote_jid)
        res = send_text(to=remote_jid, text="🧹 Histórico apagado! Começando uma nova conversa.")
        if inspect.isawaitable(res):
            await res
        raise HTTPException(status_code=200, detail={"status": "success", "reply": "history_cleared"})

    return f"{remote_jid} | {push_name} : {message_text}", remote_jid


@app.post("/webhook")
async def evolution_webhook(request: Request):
    """Recebe eventos do Evolution API via webhook.
    Extrai a mensagem de texto e a envia ao agente LangChain para processamento.
    """
    try:
        current_msg, remote_jid = await handle_message(request)
        history = get_history(remote_jid)
        messages = history + [("user", current_msg)]

        print("🧠 Processando com o agente...")
        # response = agent_executor.invoke({"messages": messages})
        response = {
            "messages": [
                {"role": "assistant", "content": "Desculpe, o agente não está implementado no momento."}
            ]
        }
        reply = response["messages"][0].get("content", "Desculpe, não consegui gerar uma resposta.")
        print(f"🤖 Resposta: {reply}")

        # Persiste o turno no Redis
        append_messages(remote_jid, current_msg, reply)

        # send_text(to=remote_jid, text=reply)
        print(f" Resposta enviada para {remote_jid}")

        return {"status": "success", "reply": reply}

    except HTTPException:
        # Repassa exceções HTTP de controle de fluxo (ex: 400 para eventos ignorados)
        raise
    except Exception as exc:
        traceback.print_exc()
        return {"status": "error", "message": "Internal server error"}


if __name__ == "__main__":
    print("C3PO rodando na porta 5000...")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
