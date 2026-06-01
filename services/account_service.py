from __future__ import annotations

import asyncio

from loguru import logger
from sqlalchemy.orm import Session

from core.exceptions import NotFoundError, PlatformAuthError
from core.security import encrypt_credential, decrypt_credential
from models.user import Account
from adapters.platform.base import AuthResult


class AccountService:

    def create_account(
        self,
        db: Session,
        credential: str,
        platform: str = "xhs",
        nickname: str = "",
    ) -> Account:
        encrypted = encrypt_credential(credential)
        account = Account(
            platform=platform,
            nickname=nickname,
            credential=encrypted,
            status="active",
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        logger.info(f"Created account: {account.id} ({nickname})")
        return account

    def get_account(self, db: Session, account_id: str) -> Account:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise NotFoundError("Account", account_id)
        return account

    def list_accounts(
        self, db: Session, platform: str | None = None
    ) -> list[Account]:
        query = db.query(Account)
        if platform:
            query = query.filter(Account.platform == platform)
        return query.order_by(Account.created_at.desc()).all()

    def update_credential(
        self, db: Session, account_id: str, new_credential: str
    ) -> Account:
        account = self.get_account(db, account_id)
        account.credential = encrypt_credential(new_credential)
        db.commit()
        db.refresh(account)
        logger.info(f"Updated credential for account: {account_id}")
        return account

    def delete_account(self, db: Session, account_id: str) -> None:
        account = self.get_account(db, account_id)
        db.delete(account)
        db.commit()
        logger.info(f"Deleted account: {account_id}")

    def verify_account(self, db: Session, account_id: str) -> bool:
        account = self.get_account(db, account_id)
        try:
            credential = decrypt_credential(account.credential)
            if not credential:
                raise PlatformAuthError("empty credential")
            from adapters.platform.xhs_adapter import XHSAdapter
            adapter = XHSAdapter()

            async def _auth() -> AuthResult:
                return await adapter.authenticate(credential)

            result = asyncio.run(_auth())
            if result.success:
                logger.info(f"Account {account_id} verified successfully via platform API")
                return True
            logger.warning(f"Account {account_id} platform auth returned failure")
            return False
        except Exception as e:
            logger.warning(f"Account {account_id} verification failed: {e}")
            return False


account_service = AccountService()
