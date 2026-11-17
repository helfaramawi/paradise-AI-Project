"""Operational integrity checks used by the backup / restore scripts.

    python -m app.ops_tools verify-archive <documents.tar.gz>   # every stored file in the archive matches its DB SHA-256
    python -m app.ops_tools check-storage                       # every stored file on disk matches its DB SHA-256
    python -m app.ops_tools counts                              # row counts of the main tables

Exit code 0 = verified, 1 = problem found. The first output line is a one-line verdict for the manifest.
"""

from __future__ import annotations

import hashlib
import sys
import tarfile
from pathlib import Path

from sqlalchemy import func, select

from .config import get_settings
from .db import SessionLocal
from .models import Claim, ClaimDocument, Document, Entitlement, Organization, Project, ProjectEvent, User


def _expected(db) -> dict[str, str]:
    """storage_key -> sha256 for every stored blob the database refers to."""
    rows = db.execute(select(Document.storage_key, Document.sha256)).all()
    rows += db.execute(select(ClaimDocument.storage_key, ClaimDocument.sha256)).all()
    return {k: h for k, h in rows if k}


def verify_archive(path: str) -> tuple[bool, str, list[str]]:
    with SessionLocal() as db:
        expected = _expected(db)
    problems: list[str] = []
    found: dict[str, str] = {}
    with tarfile.open(path, "r:gz") as tar:
        for m in tar.getmembers():
            if not m.isfile():
                continue
            name = m.name.lstrip("./")
            key = name.split("storage/", 1)[1] if name.startswith("storage/") else name
            if key in expected:
                found[key] = hashlib.sha256(tar.extractfile(m).read()).hexdigest()
    for key, sha in expected.items():
        if key not in found:
            problems.append(f"missing: {key}")
        elif found[key] != sha:
            problems.append(f"checksum mismatch: {key}")
    if problems:
        return False, f"VERIFY FAILED: {len(problems)} of {len(expected)} stored files missing or damaged", problems
    return True, f"VERIFIED: all {len(expected)} stored files present and every SHA-256 matches the database", []


def check_storage() -> tuple[bool, str, list[str]]:
    root = Path(get_settings().storage_path)
    with SessionLocal() as db:
        expected = _expected(db)
    problems = []
    for key, sha in expected.items():
        p = root / key
        if not p.is_file():
            problems.append(f"missing: {key}")
        elif hashlib.sha256(p.read_bytes()).hexdigest() != sha:
            problems.append(f"checksum mismatch: {key}")
    orphans = [f for f in root.rglob("*") if f.is_file() and str(f.relative_to(root)) not in expected] if root.exists() else []
    if orphans:
        problems.append(f"note: {len(orphans)} file(s) on disk are not referenced by the database (e.g. from deleted organisations)")
    if any(not p.startswith("note:") for p in problems):
        return False, f"STORAGE CHECK FAILED: {len([p for p in problems if not p.startswith('note:')])} of {len(expected)} stored files missing or damaged", problems
    return True, f"STORAGE OK: all {len(expected)} stored files present and every SHA-256 matches the database", problems


def counts() -> str:
    with SessionLocal() as db:
        parts = []
        for label, model in (("organisations", Organization), ("users", User), ("projects", Project),
                             ("documents", Document), ("events", ProjectEvent), ("entitlements", Entitlement),
                             ("claims", Claim), ("claim documents", ClaimDocument)):
            parts.append(f"{label} {db.scalar(select(func.count()).select_from(model))}")
    return ", ".join(parts)


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "verify-archive":
        ok, verdict, problems = verify_archive(argv[1])
    elif argv[:1] == ["check-storage"]:
        ok, verdict, problems = check_storage()
    elif argv[:1] == ["counts"]:
        print(counts())
        return 0
    else:
        print(__doc__)
        return 2
    print(verdict)
    for p in problems[:20]:
        print("  " + p)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
