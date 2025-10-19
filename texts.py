from __future__ import annotations
from typing import Optional

# Короткая справка для /start
WELCOME = (
    "Привет! Я помогаю тегать участников на быстрые игры.\n"
    "• /optout — не упоминать меня\n"
    "• /optin — снова упоминать\n"
    "• /call_codenames — начать набор на Codenames (для ведущих/админов)\n"
)

def header(game_title: str, emoji: Optional[str] = None) -> str:
    """
    Заголовок шапки набора в Markdown (**жирный**).
    В sessions.py он будет преобразован в HTML.
    """
    e = f"{emoji} " if emoji else ""
    return f"{e}**{game_title}** — набор открыт!"

# Резюме (оставляем для совместимости, но sessions.py формирует собственную сводку)
SUMMARY_TITLE = "\n\n**Сводка:**"
def summary_lines(going: list[str], maybe: list[str], nope: list[str], target: int) -> str:
    parts: list[str] = [SUMMARY_TITLE]
    parts.append(f"Иду ({len(going)}/{target}): " + (", ".join(going) if going else "—"))
    parts.append(f"Может быть ({len(maybe)}): " + (", ".join(maybe) if maybe else "—"))
    parts.append(f"Не сегодня ({len(nope)}): " + (", ".join(nope) if nope else "—"))
    return "\n".join(parts)

# Плашка «укомплектовано» (без разметки — sessions.py экранирует)
FULLY_STAFFED = "✅ Набор укомплектован."

# Текст кнопок
BUTTON_CALL_ALL = "Позвать всех на Codenames"
BUTTON_CONTINUE = "Продолжить набор"
BUTTON_CLOSE = "Закрыть набор"
BUTTON_CLEAR = "Очистить RSVP"

BTN_GO = "🧩 Иду"
BTN_MAYBE = "⏳ Через 10 мин"
BTN_NO = "🙅 Не сегодня"

# Общие сообщения
NO_RIGHTS = "Только админ или ведущий может это делать."
