from __future__ import annotations
from aiogram import Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from repo.supabase_repo import SupabaseRepo
from texts import header, summary_lines, FULLY_STAFFED, BTN_GO, BTN_MAYBE, BTN_NO


from aiogram.utils.keyboard import InlineKeyboardBuilder


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
going, maybe, nope = self.repo.get_rsvp_lists(session["session_id"])
text = header(preset.title, preset.emoji) + summary_lines(
going=[f"@{await self._username(u)}" if await self._username(u) else f"tg://user?id={u}" for u in going],
maybe=[f"@{await self._username(u)}" if await self._username(u) else f"tg://user?id={u}" for u in maybe],
nope=[f"@{await self._username(u)}" if await self._username(u) else f"tg://user?id={u}" for u in nope],
target=session.get("target_count", 10)
)
if len(going) >= session.get("target_count", 10):
text += FULLY_STAFFED
if session.get("message_id"):
try:
return await self.bot.edit_message_text(
chat_id=chat_id,
message_id=session["message_id"],
text=text,
parse_mode="Markdown",
reply_markup=self.rsvp_keyboard(session["session_id"]) if len(going) < session.get("target_count", 10) else None
)
except Exception:
pass
msg = await self.bot.send_message(
chat_id=chat_id,
text=text,
parse_mode="Markdown",
reply_markup=self.rsvp_keyboard(session["session_id"]) if len(going) < session.get("target_count", 10) else None
)
self.repo.set_session_message(session["session_id"], msg.message_id)
return msg


async def _username(self, user_id: int) -> str | None:
try:
m = await self.bot.get_chat_member(chat_id=user_id, user_id=user_id) # not reliable in groups; fallback handled
except Exception:
return None
return m.user.username if m and m.user and m.user.username else None