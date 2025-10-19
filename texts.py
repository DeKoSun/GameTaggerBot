from aiogram.utils.formatting import Bold


WELCOME = (
"Привет! Я помогаю тегать участников на быстрые игры.\n"
"• /optout — не упоминать меня\n"
"• /optin — снова упоминать\n"
"• /call_codenames — начать набор на Codenames (для ведущих/админов)\n"
)


def header(game_title: str, emoji: str | None = None) -> str:
e = f"{emoji} " if emoji else ""
return f"{e}**{game_title}** — набор открыт!"


SUMMARY_TITLE = "\n\n**Сводка:**"


def summary_lines(going: list[str], maybe: list[str], nope: list[str], target: int) -> str:
parts: list[str] = [SUMMARY_TITLE]
parts.append(f"Иду ({len(going)}/{target}): " + (", ".join(going) if going else "—"))
parts.append(f"Может быть ({len(maybe)}): " + (", ".join(maybe) if maybe else "—"))
parts.append(f"Не сегодня ({len(nope)}): " + (", ".join(nope) if nope else "—"))
return "\n".join(parts)


FULLY_STAFFED = "\n\n✅ Набор укомплектован." # показываем при достижении цели


BUTTON_CALL_ALL = "Позвать всех на Codenames"
BUTTON_CONTINUE = "Продолжить набор"
BUTTON_CLOSE = "Закрыть набор"
BUTTON_CLEAR = "Очистить RSVP"


BTN_GO = "🧩 Иду"
BTN_MAYBE = "⏳ Через 10 мин"
BTN_NO = "🙅 Не сегодня"


NO_RIGHTS = "Только админ или ведущий может это делать."