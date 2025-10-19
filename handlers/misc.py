from __future__ import annotations
from aiogram import Router, F
from aiogram.types import Message, ChatMemberUpdated
from repo.supabase_repo import SupabaseRepo

router = Router()

# Любое сообщение в группе — фиксируем пользователя в БД
@router.message(F.chat.type.in_({"group", "supergroup"}))
async def seen_user_in_group(message: Message, repo: SupabaseRepo):
    u = message.from_user
    if not u:
        return
    repo.upsert_user(u.id, u.username, u.first_name, u.last_name)

# Вступление/изменение статуса участника
@router.chat_member()
async def on_member_update(event: ChatMemberUpdated, repo: SupabaseRepo):
    u = event.new_chat_member.user if event.new_chat_member else None
    if not u:
        return
    repo.upsert_user(u.id, u.username, u.first_name, u.last_name)
