from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from app.api.v1.applications import router as applications_router
from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.profile import router as profile_router
from app.api.v1.resumes import router as resumes_router
from app.api.v1.system import router as system_router
from app.api.webhook import router as webhook_router
from app.api.ws.chat import router as ws_chat_router
from app.db.seed import init_db
from app.modules.scheduler import CronScheduler, load_scheduler_config

load_dotenv()

PORT = int(os.environ.get("PORT", 5000))

logger = logging.getLogger(__name__)

_DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
]


def _get_cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "").strip()
    if not raw:
        return _DEFAULT_CORS_ORIGINS
    origins = [o.strip() for o in raw.split(",") if o.strip() and o.strip() != "*"]
    return origins or _DEFAULT_CORS_ORIGINS


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida da aplicação FastAPI: inicializa banco/RBAC e gerencia o CronScheduler."""
    logger.info("Inicializando banco de dados e RBAC no lifespan do FastAPI...")
    try:
        init_db()
        logger.info("Banco de dados e seed RBAC inicializados com sucesso.")
    except Exception as exc:
        logger.error("Erro ao inicializar banco de dados no lifespan: %s", exc)

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


app = FastAPI(title="C3PO – Career & Automation Platform", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(webhook_router)
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(resumes_router)
app.include_router(jobs_router)
app.include_router(applications_router)
app.include_router(chat_router)
app.include_router(system_router)
app.include_router(ws_chat_router)


@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok"}


_FRONTEND_DIST = (Path(__file__).resolve().parent.parent / "frontend" / "dist").resolve()
if _FRONTEND_DIST.is_dir():
    _assets_dir = _FRONTEND_DIST / "assets"
    if _assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="frontend_assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        if full_path.startswith(("api/", "ws/", "webhook", "docs", "redoc", "openapi.json")):
            raise HTTPException(status_code=404, detail="Not Found")
        if full_path:
            candidate = (_FRONTEND_DIST / full_path).resolve()
            if candidate.is_relative_to(_FRONTEND_DIST) and candidate.is_file():
                return FileResponse(str(candidate))
        index_file = _FRONTEND_DIST / "index.html"
        if index_file.is_file():
            return FileResponse(str(index_file))
        raise HTTPException(status_code=404, detail="SPA index.html não encontrado")


if __name__ == "__main__":
    print("C3PO rodando na porta 5000...")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
