from __future__ import annotations

from aiogram import Router, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- устойчивые импорты: корень проекта или подпапки repo/ и services/ ---
try:
    from supabase_repo import SupabaseRepo, Preset
except ModuleNotFoundError:
    from repo.supabase_repo import SupabaseRepo, Preset

try:
    from sessions import SessionService
except ModuleNotFoundError:
    from services.sessions import SessionService
# -------------------------------------------------------------------------

router = Router()

# ===== Локальная проверка прав (без внешнего permissions.py) =====
async def is_admin_or_leader(bot: Bot, repo: SupabaseRepo, chat_id: int, user_id: int) -> bool:
    # «Ведущий» из базы
    try:
        if repo.is_leader(chat_id, user_id):
            return True
    except Exception:
        pass
    # Создатель/админ чата
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return getattr(member, "status", None) in {"creator", "administrator"}
    except Exception:
        return False
# ==================================================================

# ====== Цели по умолчанию ======
DEFAULT_TARGET = 10
TARGET_BY_GAME = {"doors": 6}  # Doors хотим 6 человек

def target_for(game_key: str) -> int:
    return TARGET_BY_GAME.get(game_key, DEFAULT_TARGET)


# =========================
# БАЗОВЫЕ КОМАНДЫ
# =========================
@router.message(Command("start"))
async def cmd_start(message: Message, repo: SupabaseRepo):
    u = message.from_user
    if not u:
        return
    repo.upsert_user(u.id, u.username, u.first_name, u.last_name)
    await message.reply(
        "Привет! Я помогаю тегать участников на быстрые игры.\n\n"
        "• /games — список игр\n"
        "• /call &lt;игра&gt; — начать набор (пример: /call codenames)\n"
        "• /optout — не упоминать меня\n"
        "• /optin — снова упоминать\n\n"
        "Также доступны команды: /call_codenames, /call_bunker, /call_alias, "
        "/call_gartic, /call_mafia, /call_doors."
    )


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
    await message.reply("\n".join(lines), parse_mode="HTML")


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
    if not message.chat or message.chat.type not in {"group", "supergroup"}:
        await message.reply("Эта команда работает только в группах.")
        return

    chat_id = message.chat.id
    u = message.from_user
    if not u:
        return

    bot: Bot = message.bot
    if not await is_admin_or_leader(bot, repo, chat_id, u.id):
        await message.reply("⛔ Эту команду могут использовать только админы или ведущие.")
        return

    query = (command.args or "").strip()
    if not query:
        await message.reply("Укажи игру: /call codenames | bunker | alias | gartic | mafia | doors")
        return

    preset = _find_preset(repo, query)
    if not preset:
        await message.reply("Игра не найдена. Смотри список: /games")
        return

    # закрываем старую активную сессию, чтобы не копилось
    old = repo.get_active_session(chat_id, preset.game_key)
    if old:
        try:
            repo.close_session(old["session_id"])
        except Exception:
            pass

    # создаём новую
    session = repo.create_session(
        chat_id, preset.game_key, u.id, target_count=target_for(preset.game_key)
    )

    # публикуем шапку RSVP и кнопку "Позвать всех"
    await session_service.post_or_get_session_message(chat_id, preset, session)

    kb = InlineKeyboardBuilder()
    kb.button(
        text=f"Позвать всех на {preset.title}",
        callback_data=f"callall:{session['session_id']}:{preset.game_key}",
    )
    await message.answer("Управление набором:", reply_markup=kb.as_markup())


# =========================
# Алиасы /call_<game>
# =========================
@router.message(Command("call_codenames"))
async def call_codenames(message: Message, repo: SupabaseRepo, session_service: SessionService):
    await _call_by_key("codenames", message, repo, session_service)

@router.message(Command("call_bunker"))
async def call_bunker(message: Message, repo: SupabaseRepo, session_service: SessionService):
    await _call_by_key("bunker", message, repo, session_service)

@router.message(Command("call_alias"))
async def call_alias(message: Message, repo: SupabaseRepo, session_service: SessionService):
    await _call_by_key("alias", message, repo, session_service)

@router.message(Command("call_gartic"))
async def call_gartic(message: Message, repo: SupabaseRepo, session_service: SessionService):
    await _call_by_key("gartic", message, repo, session_service)

@router.message(Command("call_mafia"))
async def call_mafia(message: Message, repo: SupabaseRepo, session_service: SessionService):
    await _call_by_key("mafia", message, repo, session_service)

@router.message(Command("call_doors"))
async def call_doors(message: Message, repo: SupabaseRepo, session_service: SessionService):
    await _call_by_key("doors", message, repo, session_service)


# =========================
# ВЕДУЩИЕ (leaders)
# =========================
async def _resolve_target_user_id(message: Message, repo: SupabaseRepo) -> int | None:
    """
    Ищем целевого пользователя:
    1) если команда отправлена в ответ на сообщение — берём автора реплая
    2) если есть @username вторым словом — пытаемся найти в БД (gt_users)
    """
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id

    if message.text:
        parts = message.text.strip().split(maxsplit=1)
        if len(parts) == 2:
            raw = parts[1].strip()
            if raw.startswith("@"):
                uname = raw[1:]
                try:
                    return repo.get_user_id_by_username(uname)
                except Exception:
                    return None
    return None


@router.message(Command("leaders"))
async def cmd_leaders(message: Message, repo: SupabaseRepo):
    if not message.chat or message.chat.type not in {"group", "supergroup"}:
        await message.reply("Эта команда работает только в группах.")
        return

    leaders = repo.list_leaders(message.chat.id)
    if not leaders:
        await message.reply("В этом чате пока нет ведущих.")
        return

    lines = ["<b>Ведущие чата:</b>"]
    for u in leaders:
        label = f"@{u['username']}" if u.get("username") else (u.get("first_name") or str(u["user_id"]))
        lines.append(f"• {label}")
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("lead"))
async def cmd_lead(message: Message, repo: SupabaseRepo):
    if not message.chat or message.chat.type not in {"group", "supergroup"}:
        await message.reply("Эта команда работает только в группах.")
        return

    bot: Bot = message.bot
    # Назначать может только админ Телеграма (или владелец)
    is_admin = False
    try:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        is_admin = getattr(member, "status", None) in {"creator", "administrator"}
    except Exception:
        pass

    if not is_admin:
        await message.reply("⛔ Назначать ведущих может только админ чата.")
        return

    target_id = await _resolve_target_user_id(message, repo)
    if not target_id:
        await message.reply("Укажи пользователя: ответь на его сообщение командой /lead или напиши /lead @username")
        return

    # проверим, что пользователь в чате
    try:
        await bot.get_chat_member(message.chat.id, target_id)
    except Exception:
        await message.reply("Пользователь не найден в этом чате.")
        return

    repo.add_leader(message.chat.id, target_id, message.from_user.id)
    await message.reply("Готово. Пользователь назначен ведущим.")


@router.message(Command("unlead"))
async def cmd_unlead(message: Message, repo: SupabaseRepo):
    if not message.chat or message.chat.type not in {"group", "supergroup"}:
        await message.reply("Эта команда работает только в группах.")
        return

    bot: Bot = message.bot
    # Снимать может только админ Телеграма (или владелец)
    is_admin = False
    try:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        is_admin = getattr(member, "status", None) in {"creator", "administrator"}
    except Exception:
        pass

    if not is_admin:
        await message.reply("⛔ Снимать ведущих может только админ чата.")
        return

    target_id = await _resolve_target_user_id(message, repo)
    if not target_id:
        await message.reply("Укажи пользователя: ответь на его сообщение командой /unlead или напиши /unlead @username")
        return

    repo.remove_leader(message.chat.id, target_id)
    await message.reply("Готово. Пользователь снят с роли ведущего.")


# =========================
# ВСПОМОГАТЕЛЬНЫЕ
# =========================
def _find_preset(repo: SupabaseRepo, query: str) -> Preset | None:
    q = query.lower().strip()
    p = repo.get_preset(q)
    if p:
        return p
    for item in repo.list_active_presets():
        title = (item.title or "").lower()
        if title == q or q in title:
            return item
    return None


async def _call_by_key(
    game_key: str, message: Message, repo: SupabaseRepo, session_service: SessionService
):
    if not message.chat or message.chat.type not in {"group", "supergroup"}:
        await message.reply("Эта команда работает только в группах.")
        return

    bot: Bot = message.bot
    if not await is_admin_or_leader(bot, repo, message.chat.id, message.from_user.id):
        await message.reply("⛔ Эту команду могут использовать только админы или ведущие.")
        return

    preset = repo.get_preset(game_key)
    if not preset:
        await message.reply("Пресет не найден или отключён.")
        return

    # закрываем старую активную сессию
    old = repo.get_active_session(message.chat.id, game_key)
    if old:
        try:
            repo.close_session(old["session_id"])
        except Exception:
            pass

    # создаём новую
    session = repo.create_session(
        message.chat.id, game_key, message.from_user.id, target_count=target_for(game_key)
    )

    # публикуем шапку RSVP
    await session_service.post_or_get_session_message(message.chat.id, preset, session)

    kb = InlineKeyboardBuilder()
    kb.button(
        text=f"Позвать всех на {preset.title}",
        callback_data=f"callall:{session['session_id']}:{game_key}",
    )
    await message.answer("Управление набором:", reply_markup=kb.as_markup())
