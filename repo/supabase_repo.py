from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict, Any

from supabase import create_client, Client

from config import Settings

# Мы читаем env в main.py -> Settings.from_env()
# Здесь создаём клиент уже на готовых переменных
_settings = Settings.from_env()


@dataclass
class Preset:
    game_key: str
    title: str
    invite_lines: List[str]
    emoji: Optional[str] = None


class SupabaseRepo:
    def __init__(self) -> None:
        self.client: Client = create_client(
            _settings.supabase_url,
            _settings.supabase_service_key,
        )

    # ---------------------------
    # Users
    # ---------------------------

    def upsert_user(
        self,
        user_id: int,
        username: Optional[str],
        first_name: Optional[str],
        last_name: Optional[str],
    ) -> None:
        self.client.table("gt_users").upsert(
            {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
            }
        ).execute()

    def set_optout(self, user_id: int, value: bool) -> None:
        self.client.table("gt_users").upsert(
            {"user_id": user_id, "is_opted_out": value}
        ).execute()

    def is_opted_out(self, user_id: int) -> bool:
        res = (
            self.client.table("gt_users")
            .select("is_opted_out")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        data = res.data or {}
        return bool(data.get("is_opted_out", False))

    def get_user_public(self, user_id: int) -> Optional[Dict[str, Any]]:
        res = (
            self.client.table("gt_users")
            .select("user_id,username,first_name,last_name")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        return res.data or None

    # ---------------------------
    # Leaders
    # ---------------------------

    def is_leader(self, chat_id: int, user_id: int) -> bool:
        res = (
            self.client.table("gt_leaders")
            .select("user_id")
            .match({"chat_id": chat_id, "user_id": user_id})
            .execute()
        )
        return len(res.data or []) > 0

    def add_leader(
        self, chat_id: int, user_id: int, granted_by: Optional[int]
    ) -> None:
        self.client.table("gt_leaders").upsert(
            {"chat_id": chat_id, "user_id": user_id, "granted_by": granted_by}
        ).execute()

    def remove_leader(self, chat_id: int, user_id: int) -> None:
        self.client.table("gt_leaders").delete().match(
            {"chat_id": chat_id, "user_id": user_id}
        ).execute()

    def list_leaders(self, chat_id: int) -> List[int]:
        res = (
            self.client.table("gt_leaders")
            .select("user_id")
            .eq("chat_id", chat_id)
            .execute()
        )
        return [row["user_id"] for row in (res.data or [])]

    # ---------------------------
    # Exclusions
    # ---------------------------

    def is_excluded(self, chat_id: int, user_id: int) -> bool:
        res = (
            self.client.table("gt_exclusions")
            .select("user_id")
            .match({"chat_id": chat_id, "user_id": user_id})
            .execute()
        )
        return len(res.data or []) > 0

    def exclude(
        self,
        chat_id: int,
        user_id: int,
        created_by: Optional[int],
        reason: Optional[str] = None,
    ) -> None:
        self.client.table("gt_exclusions").upsert(
            {
                "chat_id": chat_id,
                "user_id": user_id,
                "created_by": created_by,
                "reason": reason,
            }
        ).execute()

    def include(self, chat_id: int, user_id: int) -> None:
        self.client.table("gt_exclusions").delete().match(
            {"chat_id": chat_id, "user_id": user_id}
        ).execute()

    # ---------------------------
    # Presets
    # ---------------------------

    def get_preset(self, game_key: str) -> Optional[Preset]:
        res = (
            self.client.table("gt_game_presets")
            .select("game_key,title,invite_lines,emoji,is_active")
            .eq("game_key", game_key)
            .maybe_single()
            .execute()
        )
        data = res.data
        if not data:
            return None
        if not data.get("is_active", True):
            return None
        return Preset(
            game_key=data["game_key"],
            title=data["title"],
            invite_lines=data.get("invite_lines") or [],
            emoji=data.get("emoji"),
        )

    def list_active_presets(self) -> list[Preset]:
        """Список активных игр для /games и /call <игра>."""
        res = (
            self.client.table("gt_game_presets")
            .select("game_key,title,invite_lines,emoji,is_active")
            .eq("is_active", True)
            .order("title", desc=False)
            .execute()
        )
        items: list[Preset] = []
        for row in (res.data or []):
            items.append(
                Preset(
                    game_key=row["game_key"],
                    title=row["title"],
                    invite_lines=row.get("invite_lines") or [],
                    emoji=row.get("emoji"),
                )
            )
        return items

    # ---------------------------
    # Sessions
    # ---------------------------

    def get_active_session(self, chat_id: int, game_key: str) -> Optional[Dict[str, Any]]:
        res = (
            self.client.table("gt_sessions")
            .select("*")
            .match({"chat_id": chat_id, "game_key": game_key, "is_closed": False})
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None

    def create_session(
        self, chat_id: int, game_key: str, started_by: int, target_count: int = 10
    ) -> Dict[str, Any]:
        res = (
            self.client.table("gt_sessions")
            .insert(
                {
                    "chat_id": chat_id,
                    "game_key": game_key,
                    "started_by": started_by,
                    "target_count": target_count,
                }
            )
            .execute()
        )
        return (res.data or [])[0]

    def set_session_message(self, session_id: str, message_id: int) -> None:
        self.client.table("gt_sessions").update(
            {"message_id": message_id}
        ).eq("session_id", session_id).execute()

    def set_session_target(self, session_id: str, target_count: int) -> None:
        """Обновить целевое количество игроков для сессии."""
        self.client.table("gt_sessions").update(
            {"target_count": target_count}
        ).eq("session_id", session_id).execute()

    def close_session(self, session_id: str) -> None:
        self.client.table("gt_sessions").update(
            {"is_closed": True}
        ).eq("session_id", session_id).execute()

    # ---------------------------
    # RSVP
    # ---------------------------

    def upsert_rsvp(self, session_id: str, user_id: int, status: str) -> None:
        self.client.table("gt_session_rsvp").upsert(
            {"session_id": session_id, "user_id": user_id, "status": status}
        ).execute()

    def get_rsvp_lists(self, session_id: str) -> Tuple[List[int], List[int], List[int]]:
        res = (
            self.client.table("gt_session_rsvp")
            .select("user_id,status")
            .eq("session_id", session_id)
            .execute()
        )
        going: List[int] = []
        maybe: List[int] = []
        nope: List[int] = []
        for r in (res.data or []):
            st = r["status"]
            uid = r["user_id"]
            if st == "going":
                going.append(uid)
            elif st == "maybe":
                maybe.append(uid)
            else:
                nope.append(uid)
        return going, maybe, nope
