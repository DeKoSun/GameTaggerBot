from __future__ import annotations

import html
import re
from typing import List

from aiogram import Bot
from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from repo.supabase_repo import SupabaseRepo
from texts import (
    header,            # возвращает Markdown (**bold**)
    FULLY_STAFFED,
    BTN_GO,
    BTN_MAYBE,
    BTN_NO,
)


def _md_to_html(text: str) -> str:
    """
    Лёгкая конвертация markdown-**жирного** в HTML <b>…</b>, остальное экранируем.
    """
    placeholder_open = "\u0001"
    placeholder_close = "\u0002"

    def mark_bold(m: re.Match) -> str:
        inner = m.group(1)
        return f"{placeholder_open}{inner}{placeholder_close}"

    marked = re.sub(r"\*\*(.+?)\*\*", mark_bold, text)
    escaped = html.escape(marked)
    escaped = escaped.replace(placeholder_open, "<b>").replace(placeholder_close, "</b>")
    return escaped


class SessionService:
    def __init__(self, bot: Bot, repo: SupabaseRepo) -> None:
        self.bot = bot
        self.repo = repo

    def rsvp_keyboard(self, session_id: str) -> InlineKeyboardMarkup:
        kb = InlineKeyboardBuilder()
        kb.button(text=BTN_GO, callback_data=f"rsvp:going:{session_id}")
        kb.button(text=BTN_MAYBE, callback_data=f"rsvp:maybe:{session_id}")
        kb.button(text=BTN_NO, callback_data=f"rsvp:no:{session_id}")
        kb.adjust(3)
        return kb.as_markup()

    async def post_or_get_session_message(self, chat_id: int, preset, session: dict) -> Message:
        """
        Рисует/обновляет «шапку» сессии с HTML-упоминаниями и клавиатурой RSVP.
        """
        going_ids, maybe_ids, nope_ids = self.repo.get_rsvp_lists(session["session_id"])
        target = int(session.get("target_count", 10))

        def mention(uid: int) -> str:
            u = self.repo.get_user_public(uid)
            label = (
                f"@{u['username']}" if u and u.get("username")
                else (u["first_name"] if u and u.get("first_name") else "игрок")
            )
            return f'<a href="tg://user?id={uid}">{html.escape(label)}</a>'

        going = [mention(u) for u in going_ids]
        maybe = [mention(u) for u in maybe_ids]
        nope  = [mention(u) for u in nope_ids]

        # Заголовок из texts.header (он Markdown) → конвертируем в HTML
        head_html = _md_to_html(header(preset.title, preset.emoji))

        # Сводка (сразу делаем в HTML)
        lines: List[str] = [
            head_html,
            "",
            "<b>Сводка:</b>",
            f"Иду ({len(going)}/{target}): " + (", ".join(going) if going else "—"),
            f"Может быть ({len(maybe)}): " + (", ".join(maybe) if maybe else "—"),
            f"Не сегодня ({len(nope)}): " + (", ".join(nope) if nope else "—"),
        ]
        if len(going) >= target:
            lines.append("")
            lines.append(html.escape(FULLY_STAFFED))  # строка без разметки — просто экранируем

        text_html = "\n".join(lines)

        # Если сообщение уже есть — пробуем редактировать, иначе отправляем новое
        kb = None if len(going) >= target else self.rsvp_keyboard(session["session_id"])

        if session.get("message_id"):
            try:
                return await self.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=session["message_id"],
                    text=text_html,
                    parse_mode="HTML",
                    reply_markup=kb,
                    disable_web_page_preview=True,
                )
            except Exception:
                # если редактирование не удалось (удалили сообщение и т.п.) — отправим новое
                pass

        msg = await self.bot.send_message(
            chat_id=chat_id,
            text=text_html,
            parse_mode="HTML",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        self.repo.set_session_message(session["session_id"], msg.message_id)
        return msg
