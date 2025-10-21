from __future__ import annotations

import html
import re
from typing import Optional, List

from aiogram import Bot
from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Устойчивые импорты (корень или подпапки)
try:
    from supabase_repo import SupabaseRepo, Preset
except ModuleNotFoundError:
    from repo.supabase_repo import SupabaseRepo, Preset

try:
    import texts
except ModuleNotFoundError:
    from handlers import texts


# ---------- Markdown -> HTML (жирный) ----------
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
    return escaped.replace(placeholder_open, "<b>").replace(placeholder_close, "</b>")


class SessionService:
    def __init__(self, bot: Bot, repo: SupabaseRepo) -> None:
        self.bot = bot
        self.repo = repo

    # ---------- Публичный метод: создать/обновить «шапку» ----------
    async def post_or_get_session_message(
        self,
        chat_id: int,
        preset: Preset,
        session: dict,
        show_target_picker: bool = False,
    ) -> int:
        """
        Создаёт/обновляет «шапку» набора для сессии.
        Возвращает message_id.
        """
        text_html = self._build_header_text(preset, session)
        kb = self._build_keyboard(session["session_id"], session["target_count"], show_target_picker)

        msg_id = session.get("message_id")
        if msg_id:
            try:
                await self.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=text_html,
                    parse_mode="HTML",
                    reply_markup=kb,
                    disable_web_page_preview=True,
                )
                return msg_id
            except Exception:
                # если редактирование не удалось (удалили/нет прав) — отправим новое
                pass

        sent = await self.bot.send_message(
            chat_id,
            text_html,
            parse_mode="HTML",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        self.repo.set_session_message(session["session_id"], sent.message_id)
        return sent.message_id

    # ---------- Построение UI ----------
    def _build_header_text(self, preset: Preset, session: dict) -> str:
        """
        **Название** (Markdown -> HTML) +
        строка «👥 Количество участников — N» +
        сводка RSVP (HTML).
        """
        title_html = _md_to_html(texts.header(preset.title, preset.emoji))
        target = int(session.get("target_count", 10))

        going_ids, maybe_ids, nope_ids = self.repo.get_rsvp_lists(session["session_id"])
        going = [self._mention(uid) for uid in going_ids]
        maybe = [self._mention(uid) for uid in maybe_ids]
        nope = [self._mention(uid) for uid in nope_ids]

        lines: List[str] = [
            title_html,
            f"\n👥 Количество участников — <b>{target}</b>",
            "",
            "<b>Сводка:</b>",
            f"Иду ({len(going)}/{target}): " + (", ".join(going) if going else "—"),
            f"Может быть ({len(maybe)}): " + (", ".join(maybe) if maybe else "—"),
            f"Не сегодня ({len(nope)}): " + (", ".join(nope) if nope else "—"),
        ]
        if len(going) >= target:
            lines.append("")
            lines.append(html.escape(texts.FULLY_STAFFED))

        return "\n".join(lines)

    def _build_keyboard(self, session_id: str, target: int, show_picker: bool) -> InlineKeyboardMarkup:
        """
        Основная клавиатура:
        - ряд RSVP-кнопок;
        - кнопка «Изменить количество (N)» ИЛИ быстрый выбор [3,4,5,6,8,10,12] + «Назад».
        """
        kb = InlineKeyboardBuilder()
        # RSVP
        kb.button(text=texts.BTN_GO, callback_data=f"rsvp:going:{session_id}")
        kb.button(text=texts.BTN_MAYBE, callback_data=f"rsvp:maybe:{session_id}")
        kb.button(text=texts.BTN_NO, callback_data=f"rsvp:no:{session_id}")
        kb.row()

        if show_picker:
            # Быстрые варианты
            for n in (3, 4, 5, 6, 8, 10, 12):
                kb.button(text=str(n), callback_data=f"set_target:{session_id}:{n}")
            kb.row()
            kb.button(text="⬅️ Назад", callback_data=f"target_back:{session_id}")
        else:
            kb.button(text=f"Изменить количество ({int(target)})", callback_data=f"change_target:{session_id}")

        return kb.as_markup()

    # ---------- Хелперы ----------
    def _mention(self, uid: int) -> str:
        """
        Возвращает HTML-упоминание: <a href="tg://user?id=...">label</a>
        label = @username | Имя | "игрок"
        """
        try:
            u = self.repo.get_user_public(uid)
        except Exception:
            u = None

        if u and u.get("username"):
            label = f"@{u['username']}"
        elif u and u.get("first_name"):
            label = u["first_name"]
        else:
            label = "игрок"

        return f'<a href="tg://user?id={uid}">{html.escape(label)}</a>'
