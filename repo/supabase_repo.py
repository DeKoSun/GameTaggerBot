from __future__ import annotations
self.client.table("gt_exclusions").delete().match({"chat_id": chat_id, "user_id": user_id}).execute()


# Presets
def get_preset(self, game_key: str) -> Optional[Preset]:
res = self.client.table("gt_game_presets").select("game_key,title,invite_lines,emoji,is_active").eq("game_key", game_key).maybe_single().execute()
if not res.data:
return None
if not res.data.get("is_active", True):
return None
return Preset(
game_key=res.data["game_key"],
title=res.data["title"],
invite_lines=res.data["invite_lines"] or [],
emoji=res.data.get("emoji"),
)

# Sessions
def get_active_session(self, chat_id: int, game_key: str) -> Optional[dict]:
res = self.client.table("gt_sessions").select("*").match({"chat_id": chat_id, "game_key": game_key, "is_closed": False}).order("created_at", desc=True).limit(1).execute()
rows = res.data or []
return rows[0] if rows else None


def create_session(self, chat_id: int, game_key: str, started_by: int, target_count: int = 10) -> dict:
res = self.client.table("gt_sessions").insert({
"chat_id": chat_id,
"game_key": game_key,
"started_by": started_by,
"target_count": target_count,
}).execute()
return (res.data or [])[0]


def set_session_message(self, session_id: str, message_id: int) -> None:
self.client.table("gt_sessions").update({"message_id": message_id}).eq("session_id", session_id).execute()


def close_session(self, session_id: str) -> None:
self.client.table("gt_sessions").update({"is_closed": True}).eq("session_id", session_id).execute()


# RSVP
def upsert_rsvp(self, session_id: str, user_id: int, status: str) -> None:
self.client.table("gt_session_rsvp").upsert({
"session_id": session_id,
"user_id": user_id,
"status": status
}).execute()


def get_rsvp_lists(self, session_id: str) -> tuple[list[int], list[int], list[int]]:
res = self.client.table("gt_session_rsvp").select("user_id,status").eq("session_id", session_id).execute()
going, maybe, nope = [], [], []
for r in (res.data or []):
if r["status"] == "going":
going.append(r["user_id"])
elif r["status"] == "maybe":
maybe.append(r["user_id"])
else:
nope.append(r["user_id"])
return going, maybe, nope