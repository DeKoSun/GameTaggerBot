from __future__ import annotations
from typing import Optional, List

# Короткая справка для /start (без опасных <> — внутри <code> экранируем)
WELCOME = (
    "Привет! Я помогаю тегать участников на быстрые игры.\n"
    "• /games — список игр\n"
    "• /call &lt;игра&gt; — начать набор (пример: /call_codenames)\n"
    "• /optout — не упоминать меня\n"
    "• /optin — снова упоминать\n"
)

# Подсказки/ошибки, которые часто нужны хендлерам
IN_GROUP_ONLY = "Эта команда работает только в группах."
NO_RIGHTS = "Только админ или ведущий может это делать."
CALL_USAGE = "Укажи игру: /call codenames | bunker | alias | gartic | mafia | doors"
PRESET_NOT_FOUND = "Игра (пресет) не найдена. Посмотри список: /games."
SESSION_NOT_FOUND = "Сессия не найдена."

# Заголовок шапки набора в Markdown (**жирный**).
# sessions.py затем преобразует это в HTML, так что здесь оставляем markdown.
def header(game_title: str, emoji: Optional[str] = None) -> str:
    e = f"{emoji} " if emoji else ""
    return f"{e}**{game_title}** — набор открыт!"

# Сводка по RSVP (оставлено для совместимости; sessions.py формирует сводку сам)
SUMMARY_TITLE = "\n\n**Сводка:**"

def summary_lines(going: List[str], maybe: List[str], nope: List[str], target: int) -> str:
    parts: List[str] = [SUMMARY_TITLE]
    parts.append(f"Иду ({len(going)}/{target}): " + (", ".join(going) if going else "—"))
    parts.append(f"Может быть ({len(maybe)}): " + (", ".join(maybe) if maybe else "—"))
    parts.append(f"Не сегодня ({len(nope)}): " + (", ".join(nope) if nope else "—"))
    return "\n".join(parts)

# Плашка «укомплектовано» (без разметки — sessions.py экранирует)
FULLY_STAFFED = "✅ Набор укомплектован."

# Динамическая подпись кнопки «Позвать всех на …»
def button_call_all(game_title: str) -> str:
    return f"Позвать всех на {game_title}"

# Подписи кнопок RSVP
BTN_GO = "🧩 Иду"
BTN_MAYBE = "⏳ Через 10 мин"
BTN_NO = "🙅 Не сегодня"
