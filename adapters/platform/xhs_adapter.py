from __future__ import annotations

import json
import os
import re
import tempfile
import time
import uuid
from pathlib import Path

_XHS_TITLE_MAX = 20

import httpx
from loguru import logger
from PIL import Image
from playwright.async_api import async_playwright
from xhshow import Xhshow

from adapters.platform.base import AuthResult, BasePlatformAdapter, PublishResult
from core.config import settings
from core.exceptions import PlatformAuthError, PublishError, PublishTimeoutError


def parse_cookies(credential: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for pair in credential.split(";"):
        pair = pair.strip()
        if "=" in pair:
            key, value = pair.split("=", 1)
            cookies[key.strip()] = value.strip()
    return cookies


class XHSAdapter(BasePlatformAdapter):
    """小红书平台适配器。

    认证走 HTTP API（xhshow 签名），发布走浏览器自动化（Playwright）。
    发布流程：导航到创作者页面 → 切换到图片上传标签 → 上传图片 →
    等待处理 → 填写标题和正文 → 添加话题 → 点击发布按钮。
    """

    def __init__(self) -> None:
        self._base_url = settings.xhs_api_base_url
        self._timeout = 60.0
        self._signer = Xhshow()

    def _parse_cookies(self, credential: str) -> dict[str, str]:
        return parse_cookies(credential)

    def _build_signed_headers(
        self, credential: str, method: str, url: str, payload: dict | None = None,
    ) -> dict[str, str]:
        cookies = self._parse_cookies(credential)
        sign_headers = self._signer.sign_headers(
            method=method.upper(), uri=url, cookies=cookies, payload=payload,
        )
        return {
            "Content-Type": "application/json",
            "Cookie": credential,
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Origin": "https://creator.xiaohongshu.com",
            "Referer": "https://creator.xiaohongshu.com/",
            **sign_headers,
        }

    def _make_placeholder_image(self, path: str, text: str = "") -> str:
        """Create a small placeholder image for testing or fallback."""
        img = Image.new("RGB", (800, 600), color=(73, 109, 137))
        img.save(path)
        return path

    async def _download_image(self, url: str, dest: str) -> str:
        """Download an image from URL to local path."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    with open(dest, "wb") as f:
                        f.write(resp.content)
                    return dest
        except Exception as e:
            logger.warning(f"Failed to download image {url}: {e}")
        return ""

    async def authenticate(self, credential: str) -> AuthResult:
        logger.info("Authenticating with XHS platform")
        url = f"{self._base_url}/api/sns/web/v1/user/me"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    url,
                    headers=self._build_signed_headers(credential, method="GET", url=url),
                )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    user = data.get("data", {}).get("user_info", {})
                    logger.info(f"XHS auth success")
                    return AuthResult(success=True, account_info=user)
            logger.warning(f"XHS auth failed: HTTP {resp.status_code}: {resp.text[:200]}")
            raise PlatformAuthError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        except httpx.TimeoutException:
            raise PlatformAuthError("authentication request timed out")
        except PlatformAuthError:
            raise
        except Exception as e:
            raise PlatformAuthError(str(e))

    async def publish(
        self,
        title: str,
        body: str,
        hashtags: list[str],
        image_urls: list[str],
        credential: str,
    ) -> PublishResult:
        logger.info(f"Publishing post via browser: {title}")
        # Truncate title to fit XHS 20-char limit
        if len(title) > _XHS_TITLE_MAX:
            logger.info(f"Title truncated from {len(title)} to {_XHS_TITLE_MAX} chars")
            title = title[:_XHS_TITLE_MAX]
        cookies_dict = self._parse_cookies(credential)

        # Prepare image files
        image_files: list[str] = []
        temp_dir = tempfile.mkdtemp(prefix="xhs_publish_")

        try:
            if image_urls:
                for i, url_or_path in enumerate(image_urls):
                    dest = os.path.join(temp_dir, f"image_{i}.png")
                    if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
                        result = await self._download_image(url_or_path, dest)
                    else:
                        # Local file path (from web upload)
                        if os.path.isfile(url_or_path):
                            import shutil
                            shutil.copy2(url_or_path, dest)
                            result = dest
                            logger.info(f"Copied local image: {url_or_path}")
                        else:
                            logger.warning(f"Local image not found: {url_or_path}")
                            result = ""
                    if result:
                        image_files.append(result)
            else:
                # Use a placeholder image
                placeholder = os.path.join(temp_dir, "placeholder.png")
                self._make_placeholder_image(placeholder)
                image_files.append(placeholder)
                logger.info("Using placeholder image (no image_urls provided)")

            if not image_files:
                raise PublishError("No image files available for upload")

            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 900},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                )

                cookie_list = [
                    {"name": k, "value": v, "domain": ".xiaohongshu.com", "path": "/"}
                    for k, v in cookies_dict.items()
                ]
                await context.add_cookies(cookie_list)
                page = await context.new_page()

                # Navigate to the publish page
                await page.goto(
                    "https://creator.xiaohongshu.com/publish/publish?from=menu",
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
                await page.wait_for_timeout(5000)

                current_url = page.url
                if "login" in current_url or "signup" in current_url:
                    await browser.close()
                    raise PlatformAuthError(
                        "Cookie expired, please re-login to creator.xiaohongshu.com"
                    )

                # Switch to image-text upload tab (上传图文)
                logger.info("Switching to image upload tab")
                # Wait for tabs to be rendered
                await page.wait_for_selector(
                    ".header-tabs .creator-tab[data-hp-bound]", timeout=15000
                )
                image_tab = page.locator(
                    '.header-tabs .creator-tab[data-hp-bound="1"]'
                ).filter(has_text="上传图文")
                await image_tab.wait_for(timeout=5000)
                await image_tab.click()
                await page.wait_for_timeout(3000)

                # Upload image(s)
                logger.info(f"Uploading {len(image_files)} image(s)")
                upload_input = page.locator("input.upload-input")
                await upload_input.wait_for(state="attached", timeout=10000)

                # Playwright accepts multiple files
                await upload_input.set_input_files(image_files)
                logger.info("Image upload triggered, waiting for processing...")
                await page.wait_for_timeout(12000)

                # Fill title
                logger.info("Filling title")
                title_input = page.locator('input[placeholder*="标题"]')
                await title_input.wait_for(timeout=15000)
                await title_input.fill(title)
                logger.info(f"Title filled: {title[:50]}")

                # Fill content body
                logger.info("Filling content body")
                tiptap = page.locator(".tiptap.ProseMirror")
                await tiptap.wait_for(timeout=10000)
                await tiptap.click()
                await page.keyboard.insert_text(body)
                logger.info(f"Content filled ({len(body)} chars)")

                # Add hashtags via topic panel (creates proper clickable topics)
                if hashtags:
                    logger.info(f"Adding {len(hashtags)} hashtag(s) via topic panel")
                    topic_btn = page.locator("#topicBtn")
                    if await topic_btn.is_visible(timeout=5000):
                        await topic_btn.click()
                        await page.wait_for_timeout(800)

                        topic_input = page.locator('input[placeholder*="搜索"]').last
                        if await topic_input.is_visible(timeout=3000):
                            for tag in hashtags:
                                # Clear and type tag name
                                await topic_input.click()
                                await page.keyboard.press("Control+a")
                                await page.keyboard.press("Backspace")
                                await page.keyboard.type(tag, delay=50)
                                await page.wait_for_timeout(1500)

                                # Try to click first suggestion
                                first = page.locator(".topic-suggestion-item, .topic-item").first
                                if await first.is_visible(timeout=3000):
                                    await first.click()
                                    await page.wait_for_timeout(500)

                        await page.keyboard.press("Escape")
                        await page.wait_for_timeout(500)
                    else:
                        logger.warning("Topic button not visible, skipping hashtags")
                else:
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(500)

                # Click publish button by calling Vue component's _onPublish
                logger.info("Calling publish handler")
                publish_btn = page.locator("xhs-publish-btn")
                await publish_btn.wait_for(timeout=10000)

                on_publish_result = await page.evaluate("""() => {
                    const btn = document.querySelector('xhs-publish-btn');
                    if (btn && typeof btn._onPublish === 'function') {
                        try {
                            const r = btn._onPublish();
                            return {called: true, result: r};
                        } catch(e) {
                            return {called: true, error: e.message || String(e)};
                        }
                    }
                    return {called: false};
                }""")
                logger.info(f"Publish handler result: {on_publish_result}")

                # Wait for publish confirmation - fast polling since XHS success page
                # auto-redirects after ~3 seconds
                success_signals = []
                note_id = ""
                for i in range(30):  # up to ~60s, poll every 2s
                    await page.wait_for_timeout(2000)

                    body_text = await page.evaluate("() => document.body.innerText || ''")
                    current_url = page.url

                    signals = []
                    if "发布成功" in body_text:
                        signals.append("success_text")
                    if "将返回发布页" in body_text:
                        signals.append("redirect_countdown")
                    if "发布中" in body_text:
                        signals.append("publishing_text")
                    if "success" in current_url and "/publish/" in current_url:
                        signals.append("redirect_success")

                    # Try to extract note ID from URL
                    note_match = re.search(r'note[/_]?([a-f0-9]{24})', current_url)
                    if note_match:
                        note_id = note_match.group(1)
                        logger.info(f"Note ID extracted from URL: {note_id}")
                        signals.append("note_id_found")
                    if not note_id:
                        param_match = re.search(r'[?&](?:note_id|id)=([a-f0-9]+)', current_url)
                        if param_match:
                            note_id = param_match.group(1)
                            logger.info(f"Note ID extracted from URL params: {note_id}")
                            signals.append("note_id_found")

                    if signals:
                        success_signals.extend(signals)
                        logger.info(f"Publish signals detected after {i*2+2}s: {signals}")

                    # Success page detected — post was published
                    if "success_text" in signals or "redirect_countdown" in signals:
                        break

                    # If we already saw success_text but the page redirected back,
                    # that's still success (XHS auto-returns after 3s)
                    if i >= 2 and "success_text" in success_signals:
                        break

                await browser.close()

                if note_id:
                    logger.info(f"Publish confirmed, note ID: {note_id}")
                    return PublishResult(success=True, platform_post_id=note_id)
                elif success_signals:
                    logger.info(f"Publish confirmed with signals: {success_signals}")
                    return PublishResult(
                        success=True,
                        platform_post_id="published_via_browser",
                    )
                else:
                    logger.error("Publish may have failed - no success signals detected")
                    raise PublishError("publish failed - no success signals detected after clicking publish")

        except PlatformAuthError:
            raise
        except Exception as e:
            logger.error(f"Browser publish failed: {e}")
            raise PublishError(str(e))
        finally:
            # Cleanup temp files
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

    async def get_publish_status(self, platform_post_id: str, credential: str) -> str:
        logger.info(f"Checking publish status: {platform_post_id}")
        url = f"{self._base_url}/api/sns/web/v1/note/{platform_post_id}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    url,
                    headers=self._build_signed_headers(credential, method="GET", url=url),
                )
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("data", {}).get("note", {}).get("status", "unknown")
                return status
            return "unknown"
        except Exception as e:
            logger.error(f"Failed to check publish status: {e}")
            return "error"
