import inspect
import traceback

from fastapi import APIRouter, HTTPException, Request

# from app.agent.agent import agent_executor
from app.core.memory import append_messages, clear_history, get_history
from app.integrations.evolution import send_text
from app.modules.devices_control import (
    get_windows_status,
    restart_windows,
    shutdown_windows,
    wake_windows,
)

router = APIRouter()

commands = {
    "/help": "Exibe os comandos disponíveis.",
    "/ligar-win": "Liga o PC com Windows via Wake-on-LAN.",
    "/desligar-win": "Desliga o PC com Windows via SSH.",
    "/reiniciar-win": "Reinicia o PC com Windows via SSH.",
    "/status-win": "Verifica se o PC com Windows está online via SSH (atalho: /status).",
}


@router.post("/webhook")
async def evolution_webhook(request: Request):
    """Recebe eventos do Evolution API via webhook.
    Extrai a mensagem de texto e a envia ao agente LangChain para processamento.
    """
    try:
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

        if not message_text:
            raise HTTPException(status_code=400, detail={"status": "ignored", "reason": "empty_message"})

        cmd = message_text.strip().lower()

        if cmd == "/help":
            res = send_text(
                to=remote_jid,
                text="💻 Comandos disponíveis:\n" + "\n".join([f"{c} - {desc}" for c, desc in commands.items()]),
            )
            if inspect.isawaitable(res):
                await res
            raise HTTPException(status_code=200, detail={"status": "success", "reply": "help_command_received"})

        if cmd == "/ligar-win":
            result = await wake_windows()
            res = send_text(to=remote_jid, text=result["message"])
            if inspect.isawaitable(res):
                await res
            raise HTTPException(
                status_code=200,
                detail={
                    "status": "success" if result.get("success") else "error",
                    "reply": "pc_ligar_command_received",
                    "result": result,
                },
            )

        if cmd == "/desligar-win":
            result = await shutdown_windows()
            res = send_text(to=remote_jid, text=result["message"])
            if inspect.isawaitable(res):
                await res
            raise HTTPException(
                status_code=200,
                detail={
                    "status": "success" if result.get("success") else "error",
                    "reply": "pc_desligar_command_received",
                    "result": result,
                },
            )

        if cmd in ("/reiniciar-win", "/reniciar-win"):
            result = await restart_windows()
            res = send_text(to=remote_jid, text=result["message"])
            if inspect.isawaitable(res):
                await res
            raise HTTPException(
                status_code=200,
                detail={
                    "status": "success" if result.get("success") else "error",
                    "reply": "pc_reiniciar_command_received",
                    "result": result,
                },
            )

        if cmd in ("/status-win", "/status"):
            result = await get_windows_status()
            res = send_text(to=remote_jid, text=result["message"])
            if inspect.isawaitable(res):
                await res
            raise HTTPException(
                status_code=200,
                detail={
                    "status": "success",
                    "reply": "pc_status_command_received",
                    "online": result.get("online", False),
                    "hostname": result.get("hostname"),
                    "reason": result.get("reason"),
                },
            )

        current_msg = f"{remote_jid} | {push_name} : {message_text}"

        response = {
            "messages": [
                {"role": "assistant", "content": "Desculpe, o agente não está implementado no momento."}
            ]
        }
        reply = response["messages"][0].get("content", "Desculpe, não consegui gerar uma resposta.")

        # Persiste o turno no Redis
        append_messages(remote_jid, current_msg, reply)

        await send_text(to=remote_jid, text=reply)
        print(f" Resposta enviada para {remote_jid}")

        return {"status": "success", "reply": reply}

    except HTTPException:
        # Repassa exceções HTTP de controle de fluxo (ex: 400 para eventos ignorados)
        raise
    except Exception as exc:
        traceback.print_exc()
        return {"status": "error", "message": "Internal server error"}
