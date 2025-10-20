from __future__ import annotations

import asyncio
import html
import random
import re
from typing import Optional, List

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from repo.supabase_repo import SupabaseRepo, Preset


BATCH_DEFAULT = 15
PAUSE_DEFAULT = 1.5
TG_MAX_MESSAGE_LEN = 4096


class TaggingService:
    """
    Отвечает за отправку персональных упоминаний батчами:
      - Формирует HTML-упоминания (<a href="tg://user?id=...">label</a>)
      - Конвертирует **bold** из шаблонов в <b>bold</b>
      - Отправляет партиями с паузами
      - Может остановиться, если по сессии набралось target_count 'going'
      - Анти-повтор: не повторяет одну и ту же invite-фразу подряд для одной игры
      - Фильтрует тех, кто реально состоит в чате (creator/administrator/member)
    """

    def __init__(self, bot: Bot, repo: SupabaseRepo) -> None:
        self.bot = bot
        self.repo = repo

    # -------------------------- public API --------------------------

    async def batch_tag(
        self,
        chat_id: int,
        preset: Preset,
        invitees: List[int],
        per_batch: int = BATCH_DEFAULT,
        pause: float = PAUSE_DEFAULT,
        session_id: Optional[str] = None,
    ) -> None:
        """
        Отправляет теги батчами. Если передан session_id — между батчами проверяем,
        достигнута ли цель по RSVP 'going' и останавливаемся.
        """

        per_batch = max(1, int(per_batch))
        invitees = list(dict.fromkeys(invitees))  # unique, сохраняем порядок

        # NEW: фильтруем только тех, кто реально состоит в чате сейчас
        invitees = await self.filter_present_members(chat_id, invitees)
        if not invitees:
            await self._safe_send_message(chat_id, "Некого звать: в чате нет подходящих участников.")
            return

        for start in range(0, len(invitees), per_batch):
            batch = invitees[start : start + per_batch]
            text = self._build_batch_text(preset, batch)

            # Страхуемся от лимита 4096 символов
            if len(text) > TG_MAX_MESSAGE_LEN:
                # грубый фоллбек: режем по строкам
                for chunk in self._split_by_lines(text):
                    await self._safe_send_message(chat_id, chunk)
            else:
                await self._safe_send_message(chat_id, text)

            # Авто-стоп при достижении цели
            if session_id and await self._reached_target(session_id):
                break

            await asyncio.sleep(pause)

    # -------------------------- presence filter --------------------------

    async def filter_present_members(self, chat_id: int, user_ids: List[int]) -> List[int]:
        """
        Возвращает только тех user_id, кто реально состоит в чате:
        статусы creator/administrator/member. Остальные (left/kicked/restricted) отбрасываются.
        """
        ok_status = {"creator", "administrator", "member"}
        sem = asyncio.Semaphore(20)  # ограничим параллелизм, чтобы не словить FLOOD

        async def check(uid: int) -> tuple[int, bool]:
            async with sem:
                try:
                    m = await self.bot.get_chat_member(chat_id, uid)
                    return uid, (getattr(m, "status", None) in ok_status)
                except TelegramBadRequest:
                    # пользователя нельзя проверить или его нет в чате
                    return uid, False
                except Exception:
                    # сетевые/прочие — тихо отбрасываем
                    return uid, False

        results = await asyncio.gather(*(check(uid) for uid in user_ids))
        return [uid for uid, ok in results if ok]

    # -------------------------- helpers --------------------------

    def _build_batch_text(self, preset: Preset, user_ids: List[int]) -> str:
        """
        Строит текст батча построчно:
          <a href="tg://user?id=...">label</a> — <invite_line>
        """
        # анти-повтор: берём новую фразу с учётом последней
        invite_html = self._pick_invite_line_html(preset)

        lines: List[str] = []
        for uid in user_ids:
            label = self._label_for_user(uid)
            mention = f'<a href="tg://user?id={uid}">{label}</a>'
            lines.append(f"{mention} — {invite_html}")
        # Сообщение отправляется с parse_mode=HTML
        return "\n".join(lines)

    def _pick_invite_line_html(self, preset: Preset) -> str:
        """
        Выбираем invite-фразу с анти-повтором:
        - читаем из gt_app_settings последнюю фразу для игры
        - выбираем новую, отличную от последней (если это возможно)
        - сохраняем как последнюю
        - конвертируем **жирный** в <b>…</b> и экранируем остальное
        """
        lines = preset.invite_lines or []
        if not lines:
            return ""

        last_key = f"last_invite_{preset.game_key}"
        try:
            last_line = self.repo.get_app_setting(last_key)
        except Exception:
            last_line = None

        # Если только одна строка в пуле — берём её
        if len(lines) == 1:
            chosen = lines[0]
        else:
            chosen = random.choice(lines)
            if last_line and chosen == last_line:
                # выбрать альтернативу
                alts = [x for x in lines if x != last_line]
                if alts:
                    chosen = random.choice(alts)

        # сохраняем выбранную строку как последнюю
        try:
            self.repo.set_app_setting(last_key, chosen)
        except Exception:
            # не критично, продолжаем без сохранения
            pass

        return self._md_to_html(chosen)

    def _label_for_user(self, user_id: int) -> str:
        """
        Собираем красивую подпись: @username -> иначе Имя -> иначе 'игрок'
        Все части экранируем.
        """
        try:
            u = self.repo.get_user_public(user_id)  # ожидается метод в репозитории
        except Exception:
            u = None

        if u and u.get("username"):
            return html.escape(f"@{u['username']}")
        if u and u.get("first_name"):
            # Можно добавить last_name при желании
            return html.escape(u["first_name"])
        return html.escape("игрок")

    @staticmethod
    def _md_to_html(text: str) -> str:
        """
        Лёгкая конвертация markdown-**жирного** в HTML <b>…</b>,
        остальное экранируем.
        """
        # Сохраняем жирные участки, остальное экранируем
        # Шаг 1: временно пометим жирные фрагменты
        placeholder_open = "\u0001"
        placeholder_close = "\u0002"

        def mark_bold(m: re.Match) -> str:
            inner = m.group(1)
            return f"{placeholder_open}{inner}{placeholder_close}"

        marked = re.sub(r"\*\*(.+?)\*\*", mark_bold, text)

        # Шаг 2: экранируем весь текст как HTML
        escaped = html.escape(marked)

        # Шаг 3: заменяем плейсхолдеры на <b>…</b>
        escaped = escaped.replace(placeholder_open, "<b>").replace(placeholder_close, "</b>")

        return escaped

    async def _reached_target(self, session_id: str) -> bool:
        """
        Проверяем, достигнут ли target_count по going для сессии.
        """
        try:
            sess = (
                self.repo.client.table("gt_sessions")
                .select("session_id,target_count")
                .eq("session_id", session_id)
                .maybe_single()
                .execute()
                .data
            )
            if not sess:
                return False
            going, _, _ = self.repo.get_rsvp_lists(session_id)
            return len(going) >= int(sess.get("target_count", 10))
        except Exception:
            return False

    async def _safe_send_message(self, chat_id: int, text: str) -> None:
        try:
            await self.bot.send_message(
                chat_id,
                text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception:
            # краткая задержка и одна повторная попытка
            await asyncio.sleep(0.5)
            try:
                await self.bot.send_message(
                    chat_id,
                    text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            except Exception:
                # гасим окончательно — не валим цикл батчей
                pass

    @staticmethod
    def _split_by_lines(text: str) -> List[str]:
        """
        Режем большое сообщение на части по строкам, чтобы укладываться в лимит Telegram.
        """
        parts: List[str] = []
        current: List[str] = []
        current_len = 0

        for line in text.splitlines():
            add = len(line) + 1  # +\n
            if current_len + add > TG_MAX_MESSAGE_LEN and current:
                parts.append("\n".join(current))
                current = [line]
                current_len = len(line) + 1
            else:
                current.append(line)
                current_len += add

        if current:
            parts.append("\n".join(current))
        return parts
