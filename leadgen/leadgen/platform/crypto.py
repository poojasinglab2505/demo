"""Encrypts each company's API keys before storing them, since this is now
a multi-tenant system holding other people's credentials, not a single
user's own .env file."""
from __future__ import annotations

import base64
import hashlib
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

_fernet: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        secret = os.environ.get("APP_SECRET_KEY", "")
        if not secret:
            raise RuntimeError("APP_SECRET_KEY must be set to store/read encrypted credentials")
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
        _fernet = Fernet(key)
    return _fernet


def encrypt(value: str) -> str:
    if not value:
        return ""
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    if not value:
        return ""
    try:
        return _get_fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        return ""
