from pydantic import BaseModel
import os

class Settings(BaseModel):
    bot_token: str
    supabase_url: str
    supabase_service_key: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            bot_token=os.getenv("BOT_TOKEN", ""),
            supabase_url=os.getenv("SUPABASE_URL", ""),
            supabase_service_key=os.getenv("SUPABASE_SERVICE_KEY", ""),
        )

settings = Settings.from_env()