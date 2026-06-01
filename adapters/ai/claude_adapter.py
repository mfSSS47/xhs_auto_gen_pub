from __future__ import annotations

import json
import time
from pathlib import Path

from loguru import logger

from adapters.ai.base import BaseAIAdapter, GeneratedPost, ReviewResult

REQUEST_FILE = Path(__file__).parent.parent.parent / "_claude_request.json"
RESPONSE_FILE = Path(__file__).parent.parent.parent / "_claude_response.json"


class ClaudeAdapter(BaseAIAdapter):
    """与当前对话的 Claude 助手通过文件通信生成内容。

    工作流程：
    1. 将请求参数写入 _claude_request.json
    2. 打印提示，等待 Claude 读取并生成内容
    3. Claude 写入 _claude_response.json
    4. 适配器读取响应并返回
    """

    def __init__(self) -> None:
        pass

    async def generate_post(
        self,
        topic: str,
        tone: str = "casual",
        target_audience: str = "",
        keywords: list[str] | None = None,
        extra_context: str = "",
        max_length: int = 1000,
    ) -> GeneratedPost:
        request = {
            "action": "generate_post",
            "topic": topic,
            "tone": tone,
            "target_audience": target_audience,
            "keywords": keywords or [],
            "extra_context": extra_context,
            "max_length": max_length,
        }
        self._write_request(request)
        _print_prompt("generate")

        data = await self._wait_for_response(timeout=300)
        return GeneratedPost(
            title=data.get("title", ""),
            body=data.get("body", ""),
            hashtags=data.get("hashtags", []),
            image_prompts=data.get("image_prompts", []),
            seo_keywords=data.get("seo_keywords", []),
        )

    async def review_content(
        self, title: str, body: str, hashtags: list[str]
    ) -> ReviewResult:
        request = {
            "action": "review_content",
            "title": title,
            "body": body,
            "hashtags": hashtags,
        }
        self._write_request(request)
        _print_prompt("review")

        result = await self._wait_for_response(timeout=300)
        return ReviewResult(
            passed=result.get("review_passed", True),
            score=float(result.get("review_score", 7.0)),
            issues=result.get("review_issues", []),
            suggestion=result.get("review_suggestion", ""),
        )

    def _write_request(self, data: dict) -> None:
        REQUEST_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(f"Request written to {REQUEST_FILE}")

        if RESPONSE_FILE.exists():
            RESPONSE_FILE.unlink()

    async def _wait_for_response(self, timeout: int) -> dict:
        start = time.time()
        while time.time() - start < timeout:
            if RESPONSE_FILE.exists():
                try:
                    data = json.loads(RESPONSE_FILE.read_text(encoding="utf-8"))
                    RESPONSE_FILE.unlink()
                    return data
                except json.JSONDecodeError:
                    pass
            time.sleep(1)
        raise TimeoutError(
            f"等待 Claude 响应超时（{timeout}秒），请确认已请 Claude 生成内容"
        )


def cleanup_claude_files() -> None:
    """删除残留的请求/响应文件，防止下次管道误读。"""
    for f in (REQUEST_FILE, RESPONSE_FILE):
        if f.exists():
            f.unlink()
            logger.info(f"Cleaned up stale file: {f.name}")


def _print_prompt(action: str) -> None:
    if action == "generate":
        msg = "go-gen"
    else:
        msg = "go-review"
    print()
    print("=" * 60)
    print(f"  >>> 请在 Claude 对话中发送: {msg}")
    print("=" * 60)
    print()
