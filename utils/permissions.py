from aiogram import Bot
from aiogram.types import ChatMemberAdministrator, ChatMemberOwner
from repo.supabase_repo import SupabaseRepo


async def is_admin_or_leader(bot: Bot, repo: SupabaseRepo, chat_id: int, user_id: int) -> bool:
try:
member = await bot.get_chat_member(chat_id, user_id)
if isinstance(member, (ChatMemberAdministrator, ChatMemberOwner)):
return True
except Exception:
pass
return repo.is_leader(chat_id, user_id)