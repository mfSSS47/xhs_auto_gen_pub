from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    xhs_api_base_url: str = Field(
        default="https://edith.xiaohongshu.com", alias="XHS_API_BASE_URL"
    )
    xhs_cookie: str = Field(default="", alias="XHS_COOKIE")

    database_url: str = Field(default="sqlite:///xhs_demo.db", alias="DATABASE_URL")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file: str = Field(default="logs/app.log", alias="LOG_FILE")
    log_retention: str = Field(default="30 days", alias="LOG_RETENTION")

    publish_retry_max: int = Field(default=3, alias="PUBLISH_RETRY_MAX")
    publish_retry_delay: int = Field(default=2, alias="PUBLISH_RETRY_DELAY")
    publish_rate_limit_per_minute: int = Field(
        default=5, alias="PUBLISH_RATE_LIMIT_PER_MINUTE"
    )

    upload_folder: str = Field(
        default="web/uploads", alias="UPLOAD_FOLDER"
    )

    @property
    def log_file_path(self) -> Path:
        return Path(self.log_file)


settings = Settings()
