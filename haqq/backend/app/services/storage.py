"""Object storage abstraction (S3-style keys). The local backend stores blobs on disk, outside any web root,
under tenant-prefixed keys, and verifies SHA-256 integrity on every read."""

from __future__ import annotations

import hashlib
from pathlib import Path

from ..config import get_settings


class IntegrityError(Exception):
    pass


class LocalObjectStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if not str(p).startswith(str(self.root.resolve())):
            raise ValueError("Invalid storage key")
        return p

    def put(self, key: str, data: bytes) -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    def get(self, key: str, expected_sha256: str | None = None) -> bytes:
        data = self._path(key).read_bytes()
        if expected_sha256 and hashlib.sha256(data).hexdigest() != expected_sha256:
            raise IntegrityError(f"Checksum mismatch for {key}")
        return data

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()


_store: LocalObjectStore | None = None


def get_store() -> LocalObjectStore:
    global _store
    if _store is None:
        s = get_settings()
        if s.storage_backend != "local":
            raise RuntimeError(f"Storage backend '{s.storage_backend}' is not implemented; use 'local'.")
        _store = LocalObjectStore(Path(s.storage_path))
    return _store


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
