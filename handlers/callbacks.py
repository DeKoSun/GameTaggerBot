from __future__ import annotations

from aiogram import Router
from aiogram.types import CallbackQuery

from repo.supabase_repo import SupabaseRepo
from services.sessions import SessionService
from services.tagging import TaggingService

router = Router()


@router.callback_query(lambda c: c.data and c.data.startswith("rsvp:"))
async def cb_rsvp(
    call: CallbackQuery,
    repo: SupabaseRepo,
    session_service: SessionService,
):
    # формат: rsvp:<status>:<session_id>
    try:
        _, status, session_id = call.data.split(":", 2)
    except Exception:
        await call.answer("Ошибка формата.", show_alert=True)
        return

    user = call.from_user
    if not user:
        await call.answer()
        return

    # записываем RSVP
    repo.upsert_rsvp(session_id, user.id, status)

    # обновляем сводку под шапкой сессии
    if not call.message:
        await call.answer("OK")
        return

    session = (
        repo.client.table("gt_sessions")
        .select("*")
        .eq("session_id", session_id)
        .maybe_single()
        .execute()
        .data
    )
    if not session:
        await call.answer("Сессия не найдена.")
        return

    preset = repo.get_preset(session["game_key"])
    if not preset:
        await call.answer("Пресет не найден.")
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
    # формат: callall:<session_id>:<game_key>
    try:
        _, session_id, game_key = call.data.split(":", 2)
    except Exception:
        await call.answer("Ошибка формата.", show_alert=True)
        return

    chat_id = call.message.chat.id if call.message else None
    if not chat_id:
        await call.answer()
        return

    # проверка прав по нажимающему
    from utils.permissions import is_admin_or_leader

    if not await is_admin_or_leader(call.message.bot, repo, chat_id, call.from_user.id):
        await call.answer("Нет прав.", show_alert=True)
        return

    preset = repo.get_preset(game_key)
    if not preset:
        await call.answer("Пресет не найден.", show_alert=True)
        return

    session = repo.get_active_session(chat_id, game_key)
    if not session:
        await call.answer("Сессия закрыта или отсутствует.", show_alert=True)
        return

    # Берём известных боту пользователей (не opted_out) и не исключённых в этом чате
    users = (
        repo.client.table("gt_users")
        .select("user_id,username")
        .eq("is_opted_out", False)
        .execute()
        .data
        or []
    )
    excluded = set(
        r["user_id"]
        for r in (
            repo.client.table("gt_exclusions")
            .select("user_id")
            .eq("chat_id", chat_id)
            .execute()
            .data
            or []
        )
    )

    invitees = [u["user_id"] for u in users if u["user_id"] not in excluded]
    if not invitees:
        await call.answer("Нет подходящих участников.", show_alert=True)
        return

    await call.answer("Зову всех…")
    await tagging.batch_tag(
        chat_id, preset, invitees, per_batch=15, pause=1.5, session_id=session_id
    )
