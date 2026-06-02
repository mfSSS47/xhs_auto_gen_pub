"""Persistent Playwright browser pool — keeps one browser alive across requests."""
from __future__ import annotations

import asyncio
import atexit
import threading
from contextlib import asynccontextmanager

from loguru import logger
from playwright.async_api import async_playwright, Browser, BrowserContext

from models.database import SessionLocal
from models.user import Account
from core.security import decrypt_credential


class BrowserPool:
    """Lazy singleton: one browser, reused across requests."""

    def __init__(self):
        self._pw = None
        self._browser: Browser | None = None
        self._lock = threading.Lock()
        self._started = False

    def _ensure_started(self):
        if self._started:
            return
        with self._lock:
            if self._started:
                return
            self._started = True
            atexit.register(self.stop)

    def stop(self):
        if self._browser:
            try:
                asyncio.run(self._browser.close())
            except Exception:
                pass
            self._browser = None
        self._started = False

    @asynccontextmanager
    async def context(self):
        """Yield a BrowserContext with XHS cookies set."""
        self._ensure_started()

        if self._pw is None:
            self._pw = await async_playwright().__aenter__()

        if self._browser is None or not self._browser.is_connected():
            self._browser = await self._pw.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )

        ctx = await self._browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
        )

        # Inject XHS cookies
        cookies = _get_xhs_cookies()
        if cookies:
            await ctx.add_cookies([
                {"name": k, "value": v, "domain": ".xiaohongshu.com", "path": "/"}
                for k, v in cookies.items()
            ])

        try:
            yield ctx
        finally:
            await ctx.close()


_browser_pool = BrowserPool()


def _get_xhs_cookies() -> dict[str, str]:
    try:
        db = SessionLocal()
        acct = db.query(Account).filter(
            Account.platform == "xhs", Account.status == "active"
        ).first()
        if not acct:
            db.close()
            return {}
        cred = decrypt_credential(acct.credential)
        db.close()
        cookies = {}
        for p in cred.split(";"):
            p = p.strip()
            if "=" in p:
                k, v = p.split("=", 1)
                cookies[k.strip()] = v.strip()
        return cookies
    except Exception:
        return {}


def get_browser_pool() -> BrowserPool:
    return _browser_pool
