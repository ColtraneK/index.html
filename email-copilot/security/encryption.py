"""Fernet encryption with PBKDF2 key derivation for secure token storage."""

import base64
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_SALT_SIZE = 16
_ITERATIONS = 600_000


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))


def encrypt(data: str, passphrase: str) -> bytes:
    """Encrypt string data using a passphrase. Returns salt + ciphertext."""
    salt = os.urandom(_SALT_SIZE)
    key = _derive_key(passphrase, salt)
    f = Fernet(key)
    ciphertext = f.encrypt(data.encode())
    return salt + ciphertext


def decrypt(encrypted: bytes, passphrase: str) -> str:
    """Decrypt data that was encrypted with encrypt(). Expects salt + ciphertext."""
    salt = encrypted[:_SALT_SIZE]
    ciphertext = encrypted[_SALT_SIZE:]
    key = _derive_key(passphrase, salt)
    f = Fernet(key)
    return f.decrypt(ciphertext).decode()


def encrypt_to_file(data: str, passphrase: str, filepath) -> None:
    """Encrypt and write to file with restricted permissions."""
    encrypted = encrypt(data, passphrase)
    fd = os.open(str(filepath), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, encrypted)
    finally:
        os.close(fd)


def decrypt_from_file(filepath, passphrase: str) -> str:
    """Read and decrypt a file."""
    with open(filepath, "rb") as f:
        return decrypt(f.read(), passphrase)
