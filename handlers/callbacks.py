from __future__ import annotations

from aiogram import Router
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest

# Импортируем по абсолютным именам из корня проекта
from supabase_repo import SupabaseRepo
from sessions import SessionService
from tagging import TaggingService

router = Router()


# ===== Локальная проверка прав (чтобы не зависеть от permissions.py) =====
async def is_admin_or_leader(bot, repo: SupabaseRepo, chat_id: int, user_id: int) -> bool:
    # Сначала — «ведущий» из базы
    try:
        if repo.is_leader(chat_id, user_id):
            return True
    except Exception:
        pass

    # Затем — админ/создатель чата
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return getattr(member, "status", None) in {"creator", "administrator"}
    except TelegramBadRequest:
        return False
    except Exception:
        return False
# ========================================================================


@router.callback_query(lambda c: c.data and c.data.startswith("rsvp:"))
async def cb_rsvp(
    call: CallbackQuery,
    repo: SupabaseRepo,
    session_service: SessionService,
):
    """
    Формат callback_data: rsvp:<status>:<session_id>
    status ∈ {going, maybe, no}
    """
    # ---- разбор данных
    try:
        _, status, session_id = call.data.split(":", 2)
    except Exception:
        await call.answer("Некорректные данные.", show_alert=True)
        return

    if status not in {"going", "maybe", "no"}:
        await call.answer("Неизвестный статус.", show_alert=True)
        return

    user = call.from_user
    if not user:
        await call.answer()
        return

    # ---- пишем RSVP
    try:
        repo.upsert_rsvp(session_id, user.id, status)
    except Exception:
        await call.answer("Не удалось сохранить ответ, попробуйте ещё раз.", show_alert=True)
        return

    # ---- если "Не сегодня" — ставим кулдаун на 6 часов в этом чате
    if status == "no" and call.message and call.message.chat:
        try:
            repo.set_no_cooldown(
                chat_id=call.message.chat.id,
                user_id=user.id,
                hours=6,
                reason="no",
            )
        except Exception:
            pass  # не критично

    # ---- обновляем сводку под шапкой сессии
    if not call.message:
        await call.answer("Принято")
        return

    session = repo.get_session(session_id)
    if not session:
        await call.answer("Сессия не найдена.", show_alert=True)
        return

    preset = repo.get_preset(session["game_key"])
    if not preset:
        await call.answer("Пресет не найден.", show_alert=True)
        return

    await session_service.post_or_get_session_message(
        call.message.chat.id, preset, session
    )
    await call.answer("Принято")


@router.callback_query(lambda c: c.data and c.data.startswith("callall:"))
async def cb_call_all(
    call: CallbackQuery,
    repo: SupabaseRepo,
    tagging: TaggingService,
):
    """
    Формат callback_data: callall:<session_id>:<game_key>
    """
    # ---- разбор данных
    try:
        _, session_id, game_key = call.data.split(":", 2)
    except Exception:
        await call.answer("Некорректные данные.", show_alert=True)
        return

    chat_id = call.message.chat.id if call.message else None
    if not chat_id:
        await call.answer()
        return

    # ---- проверка прав по нажимающему
    try:
        allowed = await is_admin_or_leader(call.message.bot, repo, chat_id, call.from_user.id)
    except Exception:
        allowed = False
    if not allowed:
        await call.answer("Нет прав.", show_alert=True)
        return

    # ---- проверяем пресет и актуальную сессию
    preset = repo.get_preset(game_key)
    if not preset:
        await call.answer("Пресет не найден.", show_alert=True)
        return

    session = repo.get_active_session(chat_id, game_key)
    if not session:
        await call.answer("Сессия закрыта или отсутствует.", show_alert=True)
        return

    # Жёсткая защита от старых сообщений набора
    if session_id != session.get("session_id"):
        await call.answer("Это устаревшее сообщение набора. Откройте актуальное.", show_alert=True)
        return

    # ---- список кандидатов к упоминанию (учитывает optout, исключения и кулдаун)
    try:
        invitees = repo.list_invitees(chat_id)
    except Exception:
        await call.answer("Ошибка загрузки списка участников.", show_alert=True)
        return

    if not invitees:
        await call.answer("Нет подходящих участников.", show_alert=True)
        return

    await call.answer("Зову всех…")
    try:
        await tagging.batch_tag(
            chat_id, preset, invitees, per_batch=15, pause=1.5, session_id=session_id
        )
    except Exception:
        # не роняем колбэк при сетевых/лимитных ошибках
        pass
