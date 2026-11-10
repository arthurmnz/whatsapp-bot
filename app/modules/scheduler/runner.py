import asyncio
import logging
from pathlib import Path
import signal
import sys

from dotenv import load_dotenv

from app.modules.scheduler.config import load_scheduler_config
from app.modules.scheduler.service import CronScheduler

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scheduler_runner")

DEFAULT_CONFIG_PATH = Path("config/scheduled_messages.json")


async def run_scheduler(config_path: Path = DEFAULT_CONFIG_PATH) -> None:
    """Executa o CronScheduler em loop de eventos carregando a configuração especificada."""
    logger.info("Carregando configuração do agendador em '%s'...", config_path)
    config = load_scheduler_config(config_path)

    scheduler = CronScheduler()
    scheduler.start()
    scheduler.register_jobs(config)

    logger.info(
        "Agendador iniciado com fuso horário '%s' e %d jobs.",
        config.timezone,
        len(config.jobs),
    )

    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # Compatibilidade em plataformas onde add_signal_handler não é suportado
            pass

    try:
        await stop_event.wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Interrupção detectada.")
    finally:
        logger.info("Encerrando agendador...")
        scheduler.shutdown()
        logger.info("Agendador finalizado com sucesso.")


def main() -> None:
    config_file = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CONFIG_PATH
    try:
        asyncio.run(run_scheduler(config_file))
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
