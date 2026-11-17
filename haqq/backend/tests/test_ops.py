"""Backup / recovery integrity checks: document-archive verification and the database helper script."""

import os
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

from app.config import get_settings
from app.demo import documents as D
from app.ops_tools import check_storage, verify_archive

from .conftest import auth, register

OPS_DB = Path(__file__).resolve().parents[2] / "ops" / "db" / "haqq_db.sh"


@pytest.fixture(scope="module")
def stored(client):
    tok = register(client, "Backup Co", "admin@backup.haqq.dev")["access_token"]
    pid = client.post("/api/v1/projects", headers=auth(tok), json={"code": "BK", "name": "Backup project"}).json()["id"]
    for name, data in (("c.pdf", D.contract_pdf()), ("boq.xlsx", D.boq_xlsx())):
        assert client.post(f"/api/v1/projects/{pid}/documents", headers=auth(tok), files={"file": (name, data)}).status_code == 201
    return Path(get_settings().storage_path)


def _archive(src_root: Path, out: Path, mutate=None) -> Path:
    work = out.parent / "work"
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(src_root, work / "storage")
    if mutate:
        mutate(work / "storage")
    with tarfile.open(out, "w:gz") as t:
        t.add(work / "storage", arcname="storage")
    return out


def test_archive_verification_passes_for_intact_backup(stored, tmp_path):
    ok, verdict, problems = verify_archive(str(_archive(stored, tmp_path / "ok.tgz")))
    assert ok and verdict.startswith("VERIFIED") and not problems
    assert check_storage()[0]


def test_archive_verification_detects_damaged_and_missing_files(stored, tmp_path):
    files = sorted(p for p in stored.rglob("*") if p.is_file())

    def damage(root: Path):
        rel = [f.relative_to(stored) for f in files]
        (root / rel[0]).write_bytes(b"tampered")
        (root / rel[1]).unlink()

    ok, verdict, problems = verify_archive(str(_archive(stored, tmp_path / "bad.tgz", damage)))
    assert not ok and verdict.startswith("VERIFY FAILED")
    assert any(p.startswith("checksum mismatch") for p in problems) and any(p.startswith("missing") for p in problems)


def _pg_env() -> dict:
    url = get_settings().database_url  # postgresql+psycopg2://user:pw@host:port/db
    creds, rest = url.split("://", 1)[1].split("@", 1)
    user, pw = creds.split(":", 1)
    host, db = rest.split("/", 1)
    return {**os.environ, "POSTGRES_USER": user, "POSTGRES_PASSWORD": pw, "POSTGRES_DB": db,
            "PGPASSWORD": pw, "PGHOST": host.split(":")[0], "PGPORT": host.split(":")[1] if ":" in host else "5432"}


def _require_matching_pg_tools(env: dict) -> None:
    """In production haqq_db.sh runs inside the PostgreSQL container, so client and server versions always match.
    Here the host's tools are used: they must match the server, or newer pg_dump output cannot be restored.
    CI sets HAQQ_REQUIRE_PG_TOOLS=1 so a mismatch fails instead of silently skipping."""
    strict = os.environ.get("HAQQ_REQUIRE_PG_TOOLS") == "1"
    reason = None
    if not shutil.which("pg_dump"):
        reason = "PostgreSQL client tools not installed"
    else:
        client = subprocess.run(["pg_dump", "--version"], capture_output=True, text=True).stdout.split()[-1].split(".")[0]
        server = subprocess.run(["psql", "-Atc", "show server_version_num"], env={**env, "PGDATABASE": env["POSTGRES_DB"],
                                "PGUSER": env["POSTGRES_USER"]}, capture_output=True, text=True).stdout.strip()[:2]
        if client != server:
            reason = f"pg_dump {client} does not match PostgreSQL server {server}"
    if reason:
        if strict:
            pytest.fail(reason)
        pytest.skip(reason)


def test_database_backup_verify_and_corruption_detection(stored, tmp_path):
    env = _pg_env()
    _require_matching_pg_tools(env)
    dump = tmp_path / "db.dump"
    subprocess.run(["sh", str(OPS_DB), "backup", str(dump)], env=env, check=True)
    r = subprocess.run(["sh", str(OPS_DB), "verify", str(dump)], env=env, capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.startswith("VERIFIED"), r.stdout + r.stderr
    bad = tmp_path / "bad.dump"
    bad.write_bytes(dump.read_bytes()[:20000])
    r = subprocess.run(["sh", str(OPS_DB), "verify", str(bad)], env=env, capture_output=True, text=True)
    assert r.returncode == 1 and "VERIFY FAILED" in r.stdout
