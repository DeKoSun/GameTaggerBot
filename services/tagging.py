from __future__ import annotations

import asyncio
import html
import random
import re
from typing import Optional, List, Dict

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

# если у тебя импорт из корня — оставь этот
from repo.supabase_repo import SupabaseRepo, Preset
# если проект лежит иначе, можно переключить на:
# try:
#     from supabase_repo import SupabaseRepo, Preset
# except ModuleNotFoundError:
#     from repo.supabase_repo import SupabaseRepo, Preset


BATCH_DEFAULT = 15
PAUSE_DEFAULT = 1.5
TG_MAX_MESSAGE_LEN = 4096


class TaggingService:
    """
    Батчевый тегинг с персональными фразами-приглашениями.

    Теперь:
    - В ОДНОМ СОЗЫВЕ фразы не повторяются между пользователями,
      пока хватает вариантов в пресете (у тебя по 100 на игру — отлично).
    - «Анти-повтор для пользователя»: если выбранная фраза совпадает с его
      прошлой по ЭТОЙ игре — сдвигаем на следующую.
    - Фразы для каждого пользователя сохраняются в gt_app_settings под ключом:
        last_invite:<game_key>:<user_id>
    - Фильтруем присутствующих в чате (creator/administrator/member).
    - Паузируем между батчами и останавливаемся, если достигнут target.
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
        Отправляет теги батчами. При session_id между батчами проверяем достижение цели.
        """

        per_batch = max(1, int(per_batch))
        # unique + сохранение порядка
        invitees = list(dict.fromkeys(invitees))

        # Оставляем только реально присутствующих в чате
        invitees = await self.filter_present_members(chat_id, invitees)
        if not invitees:
            await self._safe_send_message(chat_id, "Некого звать: в чате нет подходящих участников.")
            return

        # Подбираем приглашение ДЛЯ КАЖДОГО пользователя сразу —
        # чтобы в одном созыве не было повторов между людьми.
        picks = self._pick_lines_for_users(preset, invitees)
        # превратим в список строк для отправки (упоминание + фраза)
        mentions: List[str] = [
            f'<a href="tg://user?id={uid}">{self._label_for_user(uid)}</a> — {picks[uid]}'
            for uid in invitees
        ]

        # Рассылаем батчами
        for start in range(0, len(mentions), per_batch):
            batch_lines = mentions[start : start + per_batch]
            text = "\n".join(batch_lines)

            if len(text) > TG_MAX_MESSAGE_LEN:
                for chunk in self._split_by_lines(text):
                    await self._safe_send_message(chat_id, chunk)
            else:
                await self._safe_send_message(chat_id, text)

            if session_id and await self._reached_target(session_id):
                break

            await asyncio.sleep(pause)

    # -------------------------- presence filter --------------------------

    async def filter_present_members(self, chat_id: int, user_ids: List[int]) -> List[int]:
        """
        Возвращает только тех user_id, кто реально состоит в чате:
        creator/administrator/member. Остальные (left/kicked/restricted) отбрасываются.
        """
        ok_status = {"creator", "administrator", "member"}
        sem = asyncio.Semaphore(20)  # ограничим параллелизм

        async def check(uid: int) -> tuple[int, bool]:
            async with sem:
                try:
                    m = await self.bot.get_chat_member(chat_id, uid)
                    return uid, (getattr(m, "status", None) in ok_status)
                except TelegramBadRequest:
                    return uid, False
                except Exception:
                    return uid, False

        results = await asyncio.gather(*(check(uid) for uid in user_ids))
        return [uid for uid, ok in results if ok]

    # -------------------------- picking logic --------------------------

    def _pick_lines_for_users(self, preset: Preset, user_ids: List[int]) -> Dict[int, str]:
        """
        Раздаёт фразы пользователям так, чтобы:
        - внутри ЭТОГО созыва повторы между людьми не встречались, пока хватает вариантов,
        - если людей больше, чем фраз — фразы идут по циклу (в случайном порядке),
        - «анти-повтор для пользователя»: если выданная фраза совпадает с его последней,
          сдвигаем на следующую в цикле,
        - результат: {user_id: invite_html}.
        """
        lines_raw = (preset.invite_lines or [])[:]
        if not lines_raw:
            lines_raw = ["заглядывай!"]  # страховка

        # Для справедливости перетасуем «колоду» фраз
        random.shuffle(lines_raw)
        n = len(lines_raw)

        # Случайный стартовый сдвиг, чтобы разные созывы начинались с разных мест
        start = random.randrange(n)

        picked: Dict[int, str] = {}
        for idx, uid in enumerate(user_ids):
            base_idx = (start + idx) % n
            phrase = lines_raw[base_idx]

            # анти-повтор для КОНКРЕТНОГО пользователя
            last_key = f"last_invite:{preset.game_key}:{uid}"
            last_line = None
            try:
                last_line = self.repo.get_app_setting(last_key)
            except Exception:
                pass

            if n > 1 and last_line == phrase:
                phrase = lines_raw[(base_idx + 1) % n]

            # сохраняем пользователю и фиксируем «последнюю»
            picked[uid] = self._md_to_html(phrase)
            try:
                self.repo.set_app_setting(last_key, phrase)
            except Exception:
                pass

        return picked

    # -------------------------- helpers --------------------------

    def _label_for_user(self, user_id: int) -> str:
        """
        Красивый лейбл: @username -> Имя -> 'игрок'. Всё экранируем.
        """
        try:
            u = self.repo.get_user_public(user_id)
        except Exception:
            u = None

        if u and u.get("username"):
            return html.escape(f"@{u['username']}")
        if u and u.get("first_name"):
            return html.escape(u["first_name"])
        return html.escape("игрок")

    @staticmethod
    def _md_to_html(text: str) -> str:
        """
        Лёгкая конвертация markdown-**жирного** в HTML <b>…</b>,
        остальное экранируем.
        """
        placeholder_open = "\u0001"
        placeholder_close = "\u0002"

        def mark_bold(m: re.Match) -> str:
            return f"{placeholder_open}{m.group(1)}{placeholder_close}"

        marked = re.sub(r"\*\*(.+?)\*\*", mark_bold, text)
        escaped = html.escape(marked)
        return escaped.replace(placeholder_open, "<b>").replace(placeholder_close, "</b>")

    async def _reached_target(self, session_id: str) -> bool:
        """
        Проверяем, достигнут ли target_count по 'going' для сессии.
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
            await asyncio.sleep(0.5)
            try:
                await self.bot.send_message(
                    chat_id,
                    text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            except Exception:
                pass

    @staticmethod
    def _split_by_lines(text: str) -> List[str]:
        """
        Режем длинное сообщение по строкам, чтобы уложиться в 4096 символов.
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
