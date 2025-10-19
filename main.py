import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from config import Settings
from repo.supabase_repo import SupabaseRepo
from services.sessions import SessionService
from services.tagging import TaggingService
from handlers import commands as commands_handler
from handlers import callbacks as callbacks_handler


def setup_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )


async def main() -> None:
    # Загружаем .env (на Railway переменные берутся из UI переменных окружения)
    load_dotenv()
    setup_logging()

    # ВАЖНО: читаем .env после load_dotenv()
    settings = Settings.from_env()

    # Явные проверки, чтобы в логах была понятная ошибка если что-то не задано
    missing = []
    if not settings.bot_token:
        missing.append("BOT_TOKEN")
    if not settings.supabase_url:
        missing.append("SUPABASE_URL")
    if not settings.supabase_service_key:
        missing.append("SUPABASE_SERVICE_KEY")
    if missing:
        raise RuntimeError(f"Missing env vars: {', '.join(missing)}")

    # HTML для корректных упоминаний <a href="tg://user?id=...">...</a>
    bot = Bot(settings.bot_token, parse_mode="HTML")
    dp = Dispatcher(storage=MemoryStorage())

    # DI
    repo = SupabaseRepo()
    session_service = SessionService(bot, repo)
    tagging = TaggingService(bot, repo)

    # Роутеры
    dp.include_router(commands_handler.router)
    dp.include_router(callbacks_handler.router)

    # Простейший middleware для передачи зависимостей в handlers
    class InjectMiddleware:
        async def __call__(self, handler, event, data):
            data.setdefault("repo", repo)
            data.setdefault("session_service", session_service)
            data.setdefault("tagging", tagging)
            return await handler(event, data)

    dp.update.outer_middleware(InjectMiddleware())

    # Запускаем polling (для Railway этого достаточно)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
