from __future__ import annotations

import re

from core.exceptions import ValidationError

SENSITIVE_PATTERNS = [
    (re.compile(r"(政治敏感|反动|颠覆)"), "POLITICAL"),
    (re.compile(r"(色情|淫秽|成人|裸)"), "ADULT"),
    (re.compile(r"(赌博|赌场|博彩|彩票预测)"), "GAMBLING"),
    (re.compile(r"(毒品|吸毒|大麻|海洛因)"), "DRUG"),
    (re.compile(r"(枪支|弹药|爆炸物)"), "WEAPON"),
]

AD_VIOLATION_PATTERNS = [
    re.compile(r"(国家级|世界级|顶级|极品|最优秀|第一品牌|唯一指定|绝对有效)"),
    re.compile(r"(根治|治愈率|永不复发|100%有效|百分百有效)"),
    re.compile(r"(保证疗效|确保治愈|无效退款|包治百病)"),
]

MAX_TITLE_LENGTH = 20
MAX_BODY_LENGTH = 2000
MIN_BODY_LENGTH = 100
MAX_EMOJI_RATIO = 0.15


def validate_content_direction(
    topic: str,
    tone: str | None = None,
    keywords: list[str] | None = None,
    max_length: int = 1000,
    image_count: int = 1,
) -> None:
    if not topic or not topic.strip():
        raise ValidationError("content topic cannot be empty")
    if len(topic) > 200:
        raise ValidationError("topic exceeds 200 characters")
    valid_tones = {"casual", "professional", "storytelling", "tutorial"}
    if tone and tone not in valid_tones:
        raise ValidationError(
            f"invalid tone: {tone}. Must be one of {valid_tones}"
        )
    if max_length < 50 or max_length > 2000:
        raise ValidationError("max_length must be between 50 and 2000")
    if image_count < 1 or image_count > 9:
        raise ValidationError("image_count must be between 1 and 9")


def check_sensitive_content(text: str) -> list[str]:
    violations: list[str] = []
    for pattern, category in SENSITIVE_PATTERNS:
        if pattern.search(text):
            violations.append(category)
    return violations


def check_ad_violations(text: str) -> list[str]:
    violations: list[str] = []
    for pattern in AD_VIOLATION_PATTERNS:
        for match in pattern.finditer(text):
            violations.append(match.group())
    return violations


def validate_post_content(title: str, body: str) -> list[str]:
    issues: list[str] = []
    if not title.strip():
        issues.append("title is empty")
    if len(title) > MAX_TITLE_LENGTH:
        issues.append(f"title exceeds {MAX_TITLE_LENGTH} characters (current: {len(title)})")
    if not body.strip():
        issues.append("body is empty")
    if len(body) < MIN_BODY_LENGTH:
        issues.append(f"body is too short (min {MIN_BODY_LENGTH}, current: {len(body)})")
    if len(body) > MAX_BODY_LENGTH:
        issues.append(f"body exceeds {MAX_BODY_LENGTH} characters (current: {len(body)})")
    emoji_count = len(re.findall(r"[\U0001F300-\U0001FAFF]|[\u2600-\u27BF]|[\uFE00-\uFEFF]", body))
    if body and emoji_count / len(body) > MAX_EMOJI_RATIO:
        issues.append(f"emoji density too high (max {MAX_EMOJI_RATIO:.0%})")
    sensitive = check_sensitive_content(title + body)
    if sensitive:
        issues.append(f"sensitive content detected: {', '.join(sensitive)}")
    ad_violations = check_ad_violations(body)
    if ad_violations:
        issues.append(f"ad compliance issues: {', '.join(ad_violations)}")
    return issues
