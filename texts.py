from __future__ import annotations
from typing import Optional, List

# Короткая справка для /start
WELCOME = (
    "Привет! Я помогаю тегать участников на быстрые игры.\n"
    "• /games — список игр\n"
    "• <code>/call &lt;игра&gt;</code> — начать набор (пример: <code>/call codenames</code>)\n"
    "• /optout — не упоминать меня\n"
    "• /optin — снова упоминать\n"
)

def header(game_title: str, emoji: Optional[str] = None) -> str:
    """
    Заголовок шапки набора в Markdown (**жирный**).
    В sessions.py он будет преобразован в HTML.
    """
    e = f"{emoji} " if emoji else ""
    return f"{e}**{game_title}** — набор открыт!"

# Резюме (оставлено для совместимости; sessions.py формирует сводку самостоятельно)
SUMMARY_TITLE = "\n\n**Сводка:**"
def summary_lines(going: List[str], maybe: List[str], nope: List[str], target: int) -> str:
    parts: List[str] = [SUMMARY_TITLE]
    parts.append(f"Иду ({len(going)}/{target}): " + (", ".join(going) if going else "—"))
    parts.append(f"Может быть ({len(maybe)}): " + (", ".join(maybe) if maybe else "—"))
    parts.append(f"Не сегодня ({len(nope)}): " + (", ".join(nope) if nope else "—"))
    return "\n".join(parts)

# Плашка «укомплектовано» (без разметки — sessions.py экранирует)
FULLY_STAFFED = "✅ Набор укомплектован."

# Динамическая подпись кнопки «Позвать всех на <игра>»
def button_call_all(game_title: str) -> str:
    return f"Позвать всех на {game_title}"

# Резервные подписи (используются в SessionService)
BTN_GO = "🧩 Иду"
BTN_MAYBE = "⏳ Через 10 мин"
BTN_NO = "🙅 Не сегодня"

# Общие сообщения
NO_RIGHTS = "Только админ или ведущий может это делать."
