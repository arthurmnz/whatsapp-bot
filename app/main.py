from contextlib import asynccontextmanager
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
import uvicorn

from app.api.webhook import router as webhook_router
from app.modules.scheduler import CronScheduler, load_scheduler_config

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
app.include_router(webhook_router)

if __name__ == "__main__":
    print("C3PO rodando na porta 5000...")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
