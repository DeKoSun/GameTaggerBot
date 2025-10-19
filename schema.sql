-- =========================================================
-- GameTagger schema (public) — idempotent, safe to rerun
-- =========================================================

-- UUID generator for gen_random_uuid()
DO $$ BEGIN
  CREATE EXTENSION IF NOT EXISTS pgcrypto;
END $$;

-- RSVP enum
DO $$
BEGIN
  CREATE TYPE gt_rsvp AS ENUM ('going','maybe','no');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

-- -----------------------------------------
-- Пользователи, известные боту
-- -----------------------------------------
CREATE TABLE IF NOT EXISTS public.gt_users (
  user_id      bigint PRIMARY KEY,             -- Telegram user id
  username     text,                           -- @username (может быть null/меняется)
  first_name   text,
  last_name    text,
  is_opted_out boolean NOT NULL DEFAULT false,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);

-- -----------------------------------------
-- Права "ведущий" по чатам
-- -----------------------------------------
CREATE TABLE IF NOT EXISTS public.gt_leaders (
  chat_id    bigint NOT NULL,
  user_id    bigint NOT NULL,
  granted_by bigint,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (chat_id, user_id)
);

-- -----------------------------------------
-- Пресеты игр (редактируемые)
-- -----------------------------------------
CREATE TABLE IF NOT EXISTS public.gt_game_presets (
  game_key     text PRIMARY KEY,               -- 'codenames', 'bunker', ...
  title        text NOT NULL,                  -- отображаемое имя
  invite_lines text[] NOT NULL,                -- варианты мини-приглашений
  emoji        text,                           -- эмодзи заголовка
  is_active    boolean NOT NULL DEFAULT true,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);

-- -----------------------------------------
-- Сессия набора по игре в конкретном чате
-- -----------------------------------------
CREATE TABLE IF NOT EXISTS public.gt_sessions (
  session_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id      bigint NOT NULL,
  game_key     text NOT NULL REFERENCES public.gt_game_presets(game_key),
  started_by   bigint NOT NULL,                -- user_id инициатора
  is_closed    boolean NOT NULL DEFAULT false,
  target_count int NOT NULL DEFAULT 10,        -- цель авто-остановки
  message_id   bigint,                         -- id сообщения с кнопками/сводкой
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);

-- -----------------------------------------
-- RSVP по сессии: going / maybe / no
-- -----------------------------------------
CREATE TABLE IF NOT EXISTS public.gt_session_rsvp (
  session_id uuid   NOT NULL REFERENCES public.gt_sessions(session_id) ON DELETE CASCADE,
  user_id    bigint NOT NULL,
  status     gt_rsvp NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (session_id, user_id)
);

-- -----------------------------------------
-- Исключения админом по чатам (доп. к /optout)
-- -----------------------------------------
CREATE TABLE IF NOT EXISTS public.gt_exclusions (
  chat_id    bigint NOT NULL,
  user_id    bigint NOT NULL,
  reason     text,
  created_by bigint,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (chat_id, user_id)
);

-- -----------------------------------------
-- Индексы
-- -----------------------------------------
CREATE INDEX IF NOT EXISTS idx_gt_users_username   ON public.gt_users (username);
CREATE INDEX IF NOT EXISTS idx_gt_leaders_chat     ON public.gt_leaders (chat_id);
CREATE INDEX IF NOT EXISTS idx_gt_sessions_chat    ON public.gt_sessions (chat_id, is_closed);
CREATE INDEX IF NOT EXISTS idx_gt_rsvp_session     ON public.gt_session_rsvp (session_id, status);
CREATE INDEX IF NOT EXISTS idx_gt_exclusions_chat  ON public.gt_exclusions (chat_id);

-- -----------------------------------------
-- Стартовые пресеты игр (idempotent)
-- -----------------------------------------
INSERT INTO public.gt_game_presets (game_key, title, invite_lines, emoji)
VALUES
 ('codenames','Codenames', ARRAY[
   '🚕 быстрый рейс в **Codenames**! Жми кнопку ниже!',
   '🧩 **Codenames** через пару минут. В деле?',
   '🎯 экспресс-зах
