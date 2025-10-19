import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv


from config import settings
from repo.supabase_repo import SupabaseRepo
from services.sessions import SessionService
from services.tagging import TaggingService


from handlers import commands as commands_handler
from handlers import callbacks as callbacks_handler


def setup_logging():
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


async def main():
    load_dotenv()
    setup_logging()

    settings = Settings.from_env()  # ← теперь .env точно загружен
    bot = Bot(settings.bot_token, parse_mode="HTML")  # см. ниже про HTML
    dp = Dispatcher(storage=MemoryStorage())

    # DI
    repo = SupabaseRepo()
    session_service = SessionService(bot, repo)
    tagging = TaggingService(bot, repo)

    # Регистрация роутеров
    dp.include_router(commands_handler.router)
    dp.include_router(callbacks_handler.router)

    # Регистрация мидлвари (в aiogram 3 — экземпляром)
    class InjectMiddleware:
        async def __call__(self, handler, event, data):
            data.setdefault("repo", repo)
            data.setdefault("session_service", session_service)
            data.setdefault("tagging", tagging)
            return await handler(event, data)

    dp.update.outer_middleware(InjectMiddleware())

    await dp.start_polling(bot)


if __name__ == "__main__":
try:
asyncio.run(main())
except (KeyboardInterrupt, SystemExit):
pass