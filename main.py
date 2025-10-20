import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

# === Добавляем системные пути, чтобы импорты работали и при repo/, и при services/ ===
BASE_DIR = os.getcwd()
for path in [
    BASE_DIR,
    os.path.join(BASE_DIR, "repo"),
    os.path.join(BASE_DIR, "services"),
    os.path.join(BASE_DIR, "handlers"),
]:
    if path not in sys.path:
        sys.path.insert(0, path)
# ================================================================================

from config import Settings

# Устойчивые импорты — и корень, и подпапки
try:
    from supabase_repo import SupabaseRepo
except ModuleNotFoundError:
    from repo.supabase_repo import SupabaseRepo

try:
    from sessions import SessionService
except ModuleNotFoundError:
    from services.sessions import SessionService

try:
    from tagging import TaggingService
except ModuleNotFoundError:
    from services.tagging import TaggingService

from handlers import commands as commands_handler
from handlers import callbacks as callbacks_handler
from handlers import misc as misc_handler


def setup_logging() -> None:
    """Простая настройка логирования с читаемым форматом."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


async def main() -> None:
    # Загружаем .env (на Railway переменные задаются в UI)
    load_dotenv()
    setup_logging()

    # Проверяем настройки окружения
    settings = Settings.from_env()
    missing = []
    if not settings.bot_token:
        missing.append("BOT_TOKEN")
    if not settings.supabase_url:
        missing.append("SUPABASE_URL")
    if not settings.supabase_service_key:
        missing.append("SUPABASE_SERVICE_KEY")
    if missing:
        raise RuntimeError(f"❌ Missing env vars: {', '.join(missing)}")

    # Создаём бота и диспетчер
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())

    # Зависимости (DI)
    repo = SupabaseRepo()
    session_service = SessionService(bot, repo)
    tagging = TaggingService(bot, repo)

    # Подключаем роутеры
    dp.include_router(commands_handler.router)
    dp.include_router(callbacks_handler.router)
    dp.include_router(misc_handler.router)

    # Middleware для передачи зависимостей
    class InjectMiddleware:
        async def __call__(self, handler, event, data):
            data.setdefault("repo", repo)
            data.setdefault("session_service", session_service)
            data.setdefault("tagging", tagging)
            return await handler(event, data)

    dp.update.outer_middleware(InjectMiddleware())

    logging.info("🚀 Bot is starting polling...")
    print("🔥 Bot started and polling...")

    # Стартуем
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.warning("🛑 Bot stopped manually.")
        pass
