from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PublishResult:
    success: bool
    platform_post_id: str = ""
    error_msg: str = ""
    published_at: datetime | None = None


@dataclass
class AuthResult:
    success: bool
    message: str = ""
    account_info: dict | None = None


class BasePlatformAdapter(ABC):

    @abstractmethod
    async def authenticate(self, credential: str) -> AuthResult:
        raise NotImplementedError

    @abstractmethod
    async def publish(
        self,
        title: str,
        body: str,
        hashtags: list[str],
        image_urls: list[str],
        credential: str,
    ) -> PublishResult:
        raise NotImplementedError

    @abstractmethod
    async def get_publish_status(self, platform_post_id: str, credential: str) -> str:
        raise NotImplementedError
