# seed_invites.py
from __future__ import annotations
import os
import random
from supabase import create_client
from itertools import product

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise SystemExit("Set SUPABASE_URL and SUPABASE_SERVICE_KEY env vars.")

sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ---------- БАЗА: игры, названия и эмодзи заголовка ----------
GAMES = {
    "codenames": {"title": "Codenames", "emoji": "🧠"},
    "bunker":    {"title": "Бункер",    "emoji": "🏚️"},
    "alias":     {"title": "Alias",     "emoji": "🗣️"},
    "gartic":    {"title": "Gartic",    "emoji": "🎨"},
    "mafia":     {"title": "Mafia",     "emoji": "🕵️"},
    "doors":     {"title": "Doors (захваты и защита)", "emoji": "🚪"},
}

# ---------- ГЕНЕРАЦИЯ ФРАЗ: 100 уникальных на игру ----------
# Правила:
# - коротко, дружелюбно, без упоминаний (упоминание добавляет bot)
# - в конце иногда добавляем мини-иконки темпа/времени
TAILS = ["", " — поехали!", " — 10 минут и старт!", " — залетаем!", " — без разогрева!", " — быстро-быстро!"]
CLOCKS = ["⏱️", "⏳", "🕒", "⚡", "🔥", "🎯", "⭐", "✅"]

def mix(patterns, emojis, extras=None, need=100):
    extras = extras or [""]
    pool = []
    for p, e, t in product(patterns, emojis, extras):
        s = p.replace("{e}", e)
        if t:
            s = f"{s} {t}"
        pool.append(s.strip())
    random.shuffle(pool)
    # уникализуем и нарежем до need
    uniq = []
    seen = set()
    for s in pool:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
        if len(uniq) >= need:
            break
    # если всё же < need — добьём вариациями с хвостами/часиками
    i = 0
    while len(uniq) < need:
        base = patterns[i % len(patterns)].replace("{e}", emojis[i % len(emojis)])
        tail = random.choice(TAILS)
        clock = random.choice(CLOCKS)
        candidate = f"{base} {clock} {tail}".strip()
        if candidate not in seen:
            seen.add(candidate)
            uniq.append(candidate)
        i += 1
    return uniq[:need]

# --- Наборы фраз по играм (шаблоны и эмодзи) ---
PATTERNS = {
    "codenames": {
        "patterns": [
            "{e} Готов сыграть в Codenames?",
            "{e} Погнали в Codenames!",
            "{e} Командам нужны бойцы!",
            "{e} Codenames прямо сейчас!",
            "{e} Коды ждут — присоединишься?",
            "{e} Быстрый раунд в Codenames!",
            "{e} Синие или красные — куда ты?",
            "{e} Заглядывай в комнату — идём!",
        ],
        "emojis": ["🧠","🟥","🟦","🗝️","🗺️","🕵️","🎯","⚡"],
    },
    "bunker": {
        "patterns": [
            "{e} Срочный сбор в Бункер!",
            "{e} В Бункер — выживать будем?",
            "{e} Собираем команду в Бункер!",
            "{e} К двери Бункера — выходи!",
            "{e} Без тебя люк не закроется!",
            "{e} Брифинг у входа — подойдёшь?",
            "{e} Переждём вместе? В Бункер!",
            "{e} Экспресс-раунд в Бункер!",
        ],
        "emojis": ["🏚️","🛡️","🔦","🧭","🧰","🪖","🚨","🥫"],
    },
    "alias": {
        "patterns": [
            "{e} Поясни-ка! Идём в Alias?",
            "{e} Alias сейчас — подключайся!",
            "{e} Отгадываем слова — в дело!",
            "{e} Погнали разговаривать намёками!",
            "{e} Раунд Alias на скорость!",
            "{e} Готов(а) объяснять без слов?",
            "{e} Потреним находчивость?",
            "{e} Присоединяйся к Alias!",
        ],
        "emojis": ["🗣️","💬","🧩","🎉","⚡","🎯","📣","🤹"],
    },
    "gartic": {
        "patterns": [
            "{e} В Gartic! Рисуем и угадываем!",
            "{e} Быстрый скетч-баттл?",
            "{e} Кисти заряжены — заходи!",
            "{e} Нарисуешь нам победу?",
            "{e} Время каракуль! В Gartic!",
            "{e} Пиксели ждут — присоединяйся!",
            "{e} Угадаешь по трём линиям?",
            "{e} Рисуем мгновенно — летс гоу!",
        ],
        "emojis": ["🎨","✏️","🖌️","🧠","⚡","🖼️","✨","🏆"],
    },
    "mafia": {
        "patterns": [
            "{e} Ночь близко — в Mafia!",
            "{e} Город уснул, играем?",
            "{e} Круглый стол ждёт — присаживайся!",
            "{e} Мирные/мафия — проверим удачу?",
            "{e} Срочный созыв на Mafia!",
            "{e} Детективы в деле, зайдёшь?",
            "{e} Улика найдена — идём играть!",
            "{e} Быстрый сет в Mafia!",
        ],
        "emojis": ["🕵️","🌙","🧩","🔍","🗳️","💼","🎯","🫢"],
    },
    "doors": {
        "patterns": [
            "{e} Doors: захваты и защита — в бой?",
            "{e} На рубеж! Doors ждёт!",
            "{e} Собираем штурм — присоединишься?",
            "{e} Держим оборону? Залетай!",
            "{e} Быстрый матч Doors!",
            "{e} Штурм начался — ты с нами?",
            "{e} Нужна твоя реакция — Doors!",
            "{e} Защита готовы? Погнали!",
        ],
        "emojis": ["🚪","🛡️","⚔️","🏁","⚡","🎯","🔥","🏆"],
    },
}

def build_invites_for(game_key: str) -> list[str]:
    pack = PATTERNS[game_key]
    return mix(pack["patterns"], pack["emojis"], extras=[*TAILS, *CLOCKS], need=100)

def upsert_preset(game_key: str, title: str, emoji: str, invite_lines: list[str]):
    sb.table("gt_game_presets").upsert({
        "game_key": game_key,
        "title": title,
        "emoji": emoji,
        "invite_lines": invite_lines,
        "is_active": True,
    }).execute()

def main():
    for key, meta in GAMES.items():
        invites = build_invites_for(key)
        upsert_preset(key, meta["title"], meta["emoji"], invites)
        print(f"Upserted {key}: {len(invites)} lines")

if __name__ == "__main__":
    main()
