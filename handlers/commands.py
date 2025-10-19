from __future__ import annotations

from aiogram import Router, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from repo.supabase_repo import SupabaseRepo, Preset
from services.sessions import SessionService
from utils.permissions import is_admin_or_leader
from texts import (
    WELCOME,
    NO_RIGHTS,
    button_call_all,  # динамическая подпись кнопки
)

router = Router()

DEFAULT_TARGET = 10


# =========================
# БАЗОВЫЕ КОМАНДЫ
# =========================
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


# =========================
# СПИСОК ИГР
# =========================
@router.message(Command("games"))
async def cmd_games(message: Message, repo: SupabaseRepo):
    presets = repo.list_active_presets()
    if not presets:
        await message.reply("Список игр пуст.")
        return

    lines = ["Доступные игры:"]
    for p in presets:
        lines.append(f"• <b>{p.title}</b>  (<code>{p.game_key}</code>)")
    lines.append("")
    lines.append("Запуск набора: <code>/call &lt;игра&gt;</code>")
    lines.append("Примеры: <code>/call codenames</code>, <code>/call bunker</code>")
    await message.reply("\n".join(lines))


# =========================
# /call <игра> — универсальный запуск набора
# =========================
@router.message(Command("call"))
async def cmd_call(
    message: Message,
    repo: SupabaseRepo,
    session_service: SessionService,
    command: CommandObject,
):
    chat_id = message.chat.id
    u = message.from_user
    if not u:
        return

    bot: Bot = message.bot
    if not await is_admin_or_leader(bot, repo, chat_id, u.id):
        await message.reply(NO_RIGHTS)
        return

    query = (command.args or "").strip()
    if not query:
        await message.reply("Укажи игру: <code>/call codenames</code>\nСмотри /games")
        return

    preset = _find_preset(repo, query)
    if not preset:
        await message.reply("Игра не найдена. Смотри список: /games")
        return

    await _ensure_session_and_controls(message, repo, session_service, preset)


# =========================
# Алиасы /call_<game>
# =========================
@router.message(Command("call_codenames"))
async def cmd_call_codenames(message: Message, repo: SupabaseRepo, session_service: SessionService):
    await _call_by_key("codenames", message, repo, session_service)

@router.message(Command("call_bunker"))
async def cmd_call_bunker(message: Message, repo: SupabaseRepo, session_service: SessionService):
    await _call_by_key("bunker", message, repo, session_service)

@router.message(Command("call_alias"))
async def cmd_call_alias(message: Message, repo: SupabaseRepo, session_service: SessionService):
    await _call_by_key("alias", message, repo, session_service)

@router.message(Command("call_gartic"))
async def cmd_call_gartic(message: Message, repo: SupabaseRepo, session_service: SessionService):
    await _call_by_key("gartic", message, repo, session_service)

@router.message(Command("call_mafia"))
async def cmd_call_mafia(message: Message, repo: SupabaseRepo, session_service: SessionService):
    await _call_by_key("mafia", message, repo, session_service)

@router.message(Command("call_doors"))
async def cmd_call_doors(message: Message, repo: SupabaseRepo, session_service: SessionService):
    await _call_by_key("doors", message, repo, session_service)


# =========================
# РОЛИ И ИСКЛЮЧЕНИЯ
# =========================
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


# =========================
# ВСПОМОГАТЕЛЬНЫЕ
# =========================
def _find_preset(repo: SupabaseRepo, query: str) -> Preset | None:
    """
    Ищем пресет по ключу или названию (без регистра; допускаем часть названия).
    """
    q = query.lower().strip()
    # точное совпадение по ключу
    p = repo.get_preset(q)
    if p:
        return p
    # поиск по названию среди активных
    for item in repo.list_active_presets():
        title = (item.title or "").lower()
        if title == q or q in title:
            return item
    return None


async def _call_by_key(game_key: str, message: Message, repo: SupabaseRepo, session_service: SessionService):
    preset = repo.get_preset(game_key)
    if not preset:
        await message.reply("Пресет не найден или отключён.")
        return
    await _ensure_session_and_controls(message, repo, session_service, preset)


async def _ensure_session_and_controls(
    message: Message,
    repo: SupabaseRepo,
    session_service: SessionService,
    preset: Preset,
):
    chat_id = message.chat.id
    u = message.from_user
    bot: Bot = message.bot

    if not await is_admin_or_leader(bot, repo, chat_id, u.id):
        await message.reply(NO_RIGHTS)
        return

    session = repo.get_active_session(chat_id, preset.game_key)
    if not session:
        session = repo.create_session(chat_id, preset.game_key, u.id, target_count=DEFAULT_TARGET)

    # публикуем/обновляем «шапку» сессии и даём кнопку «Позвать всех на {title}»
    await session_service.post_or_get_session_message(chat_id, preset, session)

    kb = InlineKeyboardBuilder()
    kb.button(
        text=button_call_all(preset.title),
        callback_data=f"callall:{session['session_id']}:{preset.game_key}",
    )
    await message.answer("Управление набором:", reply_markup=kb.as_markup())
