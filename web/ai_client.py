"""Direct Anthropic API client for content generation and review."""
from __future__ import annotations

import json

from anthropic import Anthropic

from adapters.ai.base import BaseAIAdapter, GeneratedPost, ReviewResult

GENERATE_SYSTEM = """You are a Xiaohongshu (小红书) content creator. Generate a Chinese post based on the user's topic and requirements.

Output as JSON:
{
  "body": "帖子正文（300-500字，有emoji，分段清晰，结尾引导互动。正文中不要包含#话题标签。）",
  "hashtags": ["标签1", "标签2", "标签3"],
  "seo_keywords": ["关键词1", "关键词2", "关键词3"]
}

Rules:
- The title is already decided by the user, do NOT generate one
- Body 300-500 characters, well-structured with emoji
- 3-5 hashtags relevant to the topic
- End with a call to action (question or invitation to comment)
- Casual, friendly tone like sharing with a friend
- NO hashtags (#) inside the body text
- NO markdown code fences in output, just raw JSON"""

REVIEW_SYSTEM = """You are a Xiaohongshu (小红书) content reviewer. Review the given post for quality and compliance.

Output as JSON:
{
  "review_passed": true/false,
  "review_score": 0-10,
  "review_issues": ["issue1", "issue2"],
  "review_suggestion": "brief feedback"
}

Checks:
- Title ≤20 Chinese characters
- Body has substance (not generic filler)
- No sensitive/political/advertising-violation content
- Content is relevant to the topic
- Score ≥6 passes"""


class APIGenerator(BaseAIAdapter):
    """Uses Anthropic API directly — no file protocol, no manual intervention."""

    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-6") -> None:
        self._client = Anthropic(api_key=api_key)
        self._model = model

    @staticmethod
    def _extract_text(content) -> str:
        """Extract text from response, handling thinking blocks."""
        for block in content:
            if hasattr(block, "text") and getattr(block, "text", None):
                return block.text
        raise ValueError("No text block found in response")

    async def generate_post(
        self, topic: str, tone: str = "casual",
        target_audience: str = "",
        keywords: list[str] | None = None,
        extra_context: str = "",
        max_length: int = 1000,
    ) -> GeneratedPost:
        user_prompt = f"Topic: {topic}\nTone: {tone}\nRequirements: {extra_context or 'Create an engaging Xiaohongshu post about this topic.'}"
        if keywords:
            user_prompt += f"\nKeywords: {', '.join(keywords)}"

        resp = self._client.messages.create(
            model=self._model,
            max_tokens=2000,
            system=GENERATE_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
        data = json.loads(self._extract_text(resp.content))
        title = topic[:20]
        return GeneratedPost(
            title=title,
            body=data.get("body", ""),
            hashtags=data.get("hashtags", []),
            seo_keywords=data.get("seo_keywords", keywords or []),
        )

    async def review_content(
        self, title: str, body: str, hashtags: list[str]
    ) -> ReviewResult:
        user_prompt = f"Title: {title}\nBody: {body}\nHashtags: {hashtags}"

        resp = self._client.messages.create(
            model=self._model,
            max_tokens=1000,
            system=REVIEW_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
        data = json.loads(self._extract_text(resp.content))
        return ReviewResult(
            passed=data.get("review_passed", True),
            score=float(data.get("review_score", 7.0)),
            issues=data.get("review_issues", []),
            suggestion=data.get("review_suggestion", ""),
        )
