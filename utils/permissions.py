# utils/permissions.py
from __future__ import annotations

from aiogram import Bot
from aiogram.types import ChatMemberAdministrator, ChatMemberOwner

from repo.supabase_repo import SupabaseRepo


async def is_admin_or_leader(bot: Bot, repo: SupabaseRepo, chat_id: int, user_id: int) -> bool:
    """
    Возвращает True, если пользователь — админ/владелец чата
    или занесён в таблицу gt_leaders как «ведущий».
    """
    # 1) проверяем права в самом Telegram-чате
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        if isinstance(member, (ChatMemberAdministrator, ChatMemberOwner)):
            return True
    except Exception:
        # например, бот не видит участника — просто продолжаем
        pass

    # 2) проверяем роль «ведущий» в нашей БД
    return repo.is_leader(chat_id, user_id)
