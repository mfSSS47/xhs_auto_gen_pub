from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy.orm import Session

from adapters.platform.base import BasePlatformAdapter
from adapters.platform.xhs_adapter import XHSAdapter
from core.config import settings
from core.exceptions import PlatformAuthError, PublishError, PublishTimeoutError
from core.security import decrypt_credential
from models.post import Post, PublishRecord
from models.user import Account


class PublishService:

    def __init__(self, platform_adapter: BasePlatformAdapter | None = None) -> None:
        self._platform = platform_adapter or XHSAdapter()
        self._max_retries = settings.publish_retry_max
        self._retry_delay = settings.publish_retry_delay
        self._rate_limiter = _RateLimiter(settings.publish_rate_limit_per_minute)

    async def publish_post(
        self,
        db: Session,
        post: Post,
        account_id: str | None = None,
    ) -> PublishRecord:
        logger.info(f"Publishing post: {post.id}")

        if post.status != "approved":
            raise PublishError(f"post {post.id} is not approved (current: {post.status})")

        account = self._resolve_account(db, account_id)
        credential = decrypt_credential(account.credential)

        try:
            await self._platform.authenticate(credential)
        except PlatformAuthError:
            account.status = "auth_failed"
            db.commit()
            raise

        await self._rate_limiter.wait()

        record = PublishRecord(
            post_id=post.id,
            account_id=account.id,
            status="publishing",
        )
        db.add(record)
        post.status = "publishing"
        db.commit()
        db.refresh(record)

        for attempt in range(self._max_retries + 1):
            try:
                result = await self._platform.publish(
                    title=post.title or "",
                    body=post.body or "",
                    hashtags=post.hashtags or [],
                    image_urls=post.image_urls or [],
                    credential=credential,
                )
                if result.success:
                    record.status = "published"
                    record.platform_post_id = result.platform_post_id
                    record.completed_at = datetime.now(timezone.utc)
                    post.status = "published"
                    db.commit()
                    db.refresh(record)
                    logger.info(
                        f"Post {post.id} published successfully, platform_id={result.platform_post_id}"
                    )
                    return record

                raise PublishError(result.error_msg or "unknown error")

            except (PublishError, PublishTimeoutError) as e:
                record.retry_count = attempt + 1
                record.error_msg = str(e)
                db.commit()

                if attempt < self._max_retries:
                    wait = self._retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Publish attempt {attempt + 1} failed for post {post.id}, "
                        f"retrying in {wait}s: {e}"
                    )
                    await asyncio.sleep(wait)
                    await self._rate_limiter.wait()
                else:
                    record.status = "failed"
                    post.status = "failed"
                    db.commit()
                    logger.error(
                        f"Publish failed after {self._max_retries + 1} attempts for post {post.id}"
                    )
                    raise PublishError(
                        f"all {self._max_retries + 1} publish attempts failed: {e}"
                    )

        raise PublishError("unreachable")

    def _resolve_account(self, db: Session, account_id: str | None) -> Account:
        if account_id:
            account = db.query(Account).filter(Account.id == account_id).first()
            if not account:
                raise PublishError(f"account {account_id} not found")
        else:
            account = (
                db.query(Account)
                .filter(Account.platform == "xhs", Account.status == "active")
                .first()
            )
            if not account:
                raise PublishError("no active XHS account found")
        return account


class _RateLimiter:
    def __init__(self, max_per_minute: int):
        self._interval = 60.0 / max_per_minute
        self._last_time = 0.0

    async def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_time
        if elapsed < self._interval:
            await asyncio.sleep(self._interval - elapsed)
        self._last_time = time.monotonic()


publish_service = PublishService()
