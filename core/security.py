from __future__ import annotations

import base64
import os
from pathlib import Path

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

KEY_FILE = Path(__file__).parent.parent / ".encryption_key"


def _load_or_create_key() -> bytes:
    env_key = os.environ.get("ENCRYPTION_KEY", "")
    if env_key:
        try:
            key = base64.b64decode(env_key)
            if len(key) >= 32:
                return key[:32]
        except Exception:
            pass

    if KEY_FILE.exists():
        key_data = KEY_FILE.read_bytes()
        if len(key_data) >= 32:
            return key_data[:32]

    key = os.urandom(32)
    KEY_FILE.write_bytes(key)
    return key


class CredentialEncryptor:
    def __init__(self, key: bytes | None = None):
        if key is None:
            key = _load_or_create_key()
        self._key = key[:32]

    def encrypt(self, plaintext: str) -> str:
        iv = os.urandom(12)
        cipher = Cipher(
            algorithms.AES(self._key), modes.GCM(iv), backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext.encode("utf-8")) + encryptor.finalize()
        result = iv + encryptor.tag + ciphertext
        return base64.b64encode(result).decode("utf-8")

    def decrypt(self, token: str) -> str:
        data = base64.b64decode(token)
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        cipher = Cipher(
            algorithms.AES(self._key), modes.GCM(iv, tag), backend=default_backend()
        )
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        return plaintext.decode("utf-8")


_encryptor = CredentialEncryptor()


def encrypt_credential(plaintext: str) -> str:
    return _encryptor.encrypt(plaintext)


def decrypt_credential(token: str) -> str:
    return _encryptor.decrypt(token)
