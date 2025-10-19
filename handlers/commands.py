from __future__ import annotations

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from repo.supabase_repo import SupabaseRepo
from services.sessions import SessionService
from services.tagging import TaggingService
from utils.permissions import is_admin_or_leader
from texts import (
    WELCOME,
    BUTTON_CALL_ALL,
    NO_RIGHTS,
)

router = Router()

GAME_KEY_DEFAULT = "codenames"


@router.message(Command("start"))
async def cmd_start(message: Message, repo: SupabaseRepo):
    u = message.from_user
    if not u:
        return
    # фиксируем пользователя в БД, чтобы потом его можно было тегать
    repo.upsert_user(u.id, u.username, u.first_name, u.last_name)
    await message.reply(WELCOME)


@router.message(Command("optout"))
async def cmd_optout(message: Message, repo: SupabaseRepo):
    u = message.from_user
    if not u:
        return
    repo.set_optout(u.id, True)
    await message.reply("Готово. Больше не буду вас упоминать в наборах.")


@router.message(Command("optin"))
async def cmd_optin(message: Message, repo: SupabaseRepo):
    u = message.from_user
    if not u:
        return
    repo.set_optout(u.id, False)
    await message.reply("Вернул вас в список для упоминаний.")


@router.message(Command("call_codenames"))
async def cmd_call_codenames(
    message: Message,
    repo: SupabaseRepo,
    session_service: SessionService,
):
    chat_id = message.chat.id
    u = message.from_user
    if not u:
        return

    bot: Bot = message.bot
    if not await is_admin_or_leader(bot, repo, chat_id, u.id):
        await message.reply(NO_RIGHTS)
        return

    preset = repo.get_preset(GAME_KEY_DEFAULT)
    if not preset:
        await message.reply("Пресет Codenames не найден.")
        return

    session = repo.get_active_session(chat_id, GAME_KEY_DEFAULT)
    if not session:
        session = repo.create_session(chat_id, GAME_KEY_DEFAULT, u.id, target_count=10)

    # публикуем/обновляем «шапку» сессии и даём кнопку «Позвать всех»
    await session_service.post_or_get_session_message(chat_id, preset, session)

    kb = InlineKeyboardBuilder()
    kb.button(
        text=BUTTON_CALL_ALL,
        callback_data=f"callall:{session['session_id']}:{preset.game_key}",
    )
    await message.answer("Управление набором:", reply_markup=kb.as_markup())


@router.message(Command("lead"))
async def cmd_lead(message: Message, repo: SupabaseRepo):
    """
    Выдать/снять права ведущего. Делается ответом на сообщение нужного пользователя.
    """
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply(
            "Сделайте команду ответом на сообщение пользователя, чтобы выдать/снять права ведущего."
        )
        return

    chat_id = message.chat.id
    admin_id = message.from_user.id if message.from_user else None
    user_id = message.reply_to_message.from_user.id

    bot: Bot = message.bot
    if not await is_admin_or_leader(bot, repo, chat_id, admin_id):
        await message.reply(NO_RIGHTS)
        return

    if repo.is_leader(chat_id, user_id):
        repo.remove_leader(chat_id, user_id)
        await message.reply("Права ведущего сняты.")
    else:
        repo.add_leader(chat_id, user_id, admin_id)
        await message.reply("Права ведущего выданы.")


@router.message(Command("leaders"))
async def cmd_leaders(message: Message, repo: SupabaseRepo):
    leaders = repo.list_leaders(message.chat.id)
    if not leaders:
        await message.reply("В этом чате пока нет ведущих.")
        return

    # Отдаём кликабельные ссылки (работают с parse_mode=HTML в боте)
    txt = "Ведущие: " + ", ".join(
        [f'<a href="tg://user?id={uid}">{uid}</a>' for uid in leaders]
    )
    await message.reply(txt, disable_web_page_preview=True)


@router.message(Command("exclude"))
async def cmd_exclude(message: Message, repo: SupabaseRepo):
    """
    Исключить пользователя из упоминаний в этом чате (админ/ведущий).
    Делайте команду ответом на сообщение нужного пользователя.
    """
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply(
            "Сделайте команду ответом на сообщение пользователя для исключения."
        )
        return

    chat_id = message.chat.id
    admin_id = message.from_user.id if message.from_user else None
    user_id = message.reply_to_message.from_user.id

    bot: Bot = message.bot
    if not await is_admin_or_leader(bot, repo, chat_id, admin_id):
        await message.reply(NO_RIGHTS)
        return

    repo.exclude(chat_id, user_id, admin_id)
    await message.reply("Пользователь исключён из упоминаний в этом чате.")


@router.message(Command("include"))
async def cmd_include(message: Message, repo: SupabaseRepo):
    """
    Вернуть пользователя в упоминания в этом чате (админ/ведущий).
    Делайте команду ответом на сообщение нужного пользователя.
    """
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply(
            "Сделайте команду ответом на сообщение пользователя для включения."
        )
        return

    chat_id = message.chat.id
    admin_id = message.from_user.id if message.from_user else None
    user_id = message.reply_to_message.from_user.id

    bot: Bot = message.bot
    if not await is_admin_or_leader(bot, repo, chat_id, admin_id):
        await message.reply(NO_RIGHTS)
        return

    repo.include(chat_id, user_id)
    await message.reply("Пользователь возвращён в упоминания в этом чате.")
