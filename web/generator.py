"""Content generator - creates XHS posts based on topic and user requirements."""
from __future__ import annotations

import re

from adapters.ai.base import BaseAIAdapter, GeneratedPost, ReviewResult


class DirectGenerator(BaseAIAdapter):
    """Generate XHS posts from topic + user requirements.

    Uses the user's own requirements text directly, expanding it into a
    structured post with proper formatting. No templates — content is
    derived entirely from user input.
    """

    async def generate_post(
        self, topic: str, tone: str = "casual",
        target_audience: str = "",
        keywords: list[str] | None = None,
        extra_context: str = "",
        max_length: int = 1000,
    ) -> GeneratedPost:
        title = topic.strip()
        if len(title) > 20:
            title = title[:20]

        body = self._build_body(title, extra_context, max_length)
        hashtags = self._extract_hashtags(title, extra_context)

        return GeneratedPost(
            title=title, body=body, hashtags=hashtags,
            seo_keywords=keywords or [],
        )

    async def review_content(
        self, title: str, body: str, hashtags: list[str]
    ) -> ReviewResult:
        issues = []
        if not title.strip():
            issues.append("title is empty")
        if len(title) > 20:
            issues.append(f"title exceeds 20 chars (currently {len(title)})")
        if not body.strip():
            issues.append("body is empty")
        if len(body) < 50:
            issues.append(f"body too short (currently {len(body)} chars)")
        passed = len(issues) == 0
        return ReviewResult(
            passed=passed,
            score=10.0 if passed else 3.0,
            issues=issues,
            suggestion="" if passed else "fix issues above",
        )

    # ── body building ──────────────────────────────────────────

    def _build_body(self, topic: str, requirements: str, max_len: int) -> str:
        """Build post body from user requirements, structured by parsed points."""
        reqs = requirements.strip()

        # Decide emoji based on topic category
        topic_emoji = self._pick_topic_emoji(topic, reqs)

        # Intro
        parts = [f"{topic_emoji} 今天来聊聊{topic}～"]

        if reqs:
            points = self._parse_points(reqs)
            if len(points) == 1 and len(points[0]) < 30:
                # Very short single input — just use it as a paragraph
                parts.append(points[0])
            else:
                for i, pt in enumerate(points):
                    parts.append(self._format_point(i + 1, pt))
        else:
            # No requirements — brief generic intro, not a template
            parts.append(f"{topic}这个话题值得深入了解，下面整理了一些核心要点分享给大家。")

        # Outro
        parts.append(self._build_outro(topic))

        body = "\n\n".join(parts)
        if len(body) > max_len:
            body = body[:max_len - 3] + "..."

        return body

    def _pick_topic_emoji(self, topic: str, reqs: str) -> str:
        combined = topic + reqs
        emoji_map = {
            "旅游": "✈️", "旅行": "🗺️", "景点": "🏞️", "周末": "🌿", "打卡": "📍",
            "美食": "🍜", "餐厅": "🍽️", "小吃": "🥟", "火锅": "🍲", "烧烤": "🍖",
            "健身": "💪", "运动": "🏃", "减肥": "⚖️", "瑜伽": "🧘",
            "穿搭": "👗", "护肤": "✨", "美妆": "💄", "发型": "💇",
            "家居": "🏠", "装修": "🔨", "收纳": "📦",
            "宠物": "🐱", "猫": "🐱", "狗": "🐶",
            "摄影": "📷", "手机": "📱", "数码": "💻",
            "读书": "📚", "学习": "📖", "考证": "📝", "职场": "💼",
            "理财": "💰", "省钱": "🤑", "副业": "💸",
            "母婴": "👶", "育儿": "🍼", "亲子": "👨‍👩‍👧",
            "徐州": "🏯", "南京": "🏛️", "北京": "🏙️", "上海": "🌃", "杭州": "🛶",
            "苏州": "🏡", "成都": "🐼", "重庆": "🌆", "西安": "🏮",
        }
        for key, emoji in emoji_map.items():
            if key in combined:
                return emoji
        return "📌"

    def _parse_points(self, reqs: str) -> list[str]:
        """Extract key points from user requirements."""
        lines = reqs.strip().split("\n")
        points = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            line = re.sub(r'^[\d]+[\.\、\)）]\s*', '', line)
            line = re.sub(r'^[-\*•▪▸►]\s*', '', line)
            line = re.sub(r'^[第][一二三四五六七八九十\d]+[点条步]', '', line)
            if line and len(line) >= 2:
                points.append(line)

        if len(points) >= 2:
            return points[:5]

        # Split by Chinese punctuation
        chunks = re.split(r'[。；;]', reqs)
        chunks = [c.strip() for c in chunks if len(c.strip()) >= 4]
        if len(chunks) >= 2:
            return chunks[:5]

        return [reqs] if reqs else []

    def _format_point(self, idx: int, point: str) -> str:
        """Format a user point into a readable section. The point text is the content."""
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        emoji = emojis[idx - 1] if idx <= 5 else "✅"

        # Use the point text directly — this is what the user wrote.
        # Add a short natural lead-in and keep the user's own words.
        return f"{emoji} {point.strip()}"

    def _build_outro(self, topic: str) -> str:
        """Build a simple outro that references the topic."""
        return (
            f"以上就是关于{topic}的分享啦～\n\n"
            f如果你觉得有帮助，记得点赞收藏！有什么想了解的评论区告诉我～"
        )

    # ── hashtags ───────────────────────────────────────────────

    def _extract_hashtags(self, topic: str, requirements: str) -> list[str]:
        tags = []

        # From topic words
        topic_words = re.findall(r'[一-鿿\w]{2,8}', topic)
        for w in topic_words:
            if w not in tags:
                tags.append(w)

        # From requirements
        words = re.findall(r'[一-鿿\w]{2,8}', requirements)
        for w in words:
            if w not in tags and len(w) <= 8:
                tags.append(w)
            if len(tags) >= 5:
                break

        defaults = ["干货分享", "推荐", "生活"]
        while len(tags) < 3:
            for d in defaults:
                if d not in tags:
                    tags.append(d)
                    break

        return tags[:5]
