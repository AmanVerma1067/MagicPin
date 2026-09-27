from __future__ import annotations

import json
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    LLM_TIMEOUT_S: float = 7.0
    TICK_DEADLINE_S: float = 22.0
    REPLY_DEADLINE_S: float = 18.0
    COMPOSE_CONCURRENCY: int = 8
    MAX_CONTEXT_BYTES: int = 512000
    TEAM_NAME: str = "Team Vera"
    TEAM_MEMBERS: Any = ["Aman Verma"]
    APP_VERSION: str = "1.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    @field_validator("TEAM_MEMBERS", mode="after")
    @classmethod
    def parse_team_members(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except Exception:
                pass
            return [m.strip() for m in v.split(",") if m.strip()]
        elif isinstance(v, (list, tuple)):
            return [str(item) for item in v]
        return ["Aman Verma"]


settings = Settings()
