from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class GeneratedPost:
    title: str = ""
    body: str = ""
    hashtags: list[str] = field(default_factory=list)
    image_prompts: list[str] = field(default_factory=list)
    seo_keywords: list[str] = field(default_factory=list)


@dataclass
class ReviewResult:
    passed: bool
    score: float
    issues: list[str] = field(default_factory=list)
    suggestion: str = ""


class BaseAIAdapter(ABC):

    @abstractmethod
    async def generate_post(
        self,
        topic: str,
        tone: str = "casual",
        target_audience: str = "",
        keywords: list[str] | None = None,
        extra_context: str = "",
        max_length: int = 1000,
    ) -> GeneratedPost:
        raise NotImplementedError

    @abstractmethod
    async def review_content(self, title: str, body: str, hashtags: list[str]) -> ReviewResult:
        raise NotImplementedError
