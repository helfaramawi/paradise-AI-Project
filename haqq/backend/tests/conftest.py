"""Test configuration: a dedicated PostgreSQL database built with the real Alembic migrations,
synchronous job processing, and an isolated storage directory."""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("HAQQ_DATABASE_URL", "postgresql+psycopg2://haqq:haqq@localhost:5432/haqq_test")
os.environ["HAQQ_WORKER_MODE"] = "inline"
os.environ["HAQQ_STORAGE_PATH"] = tempfile.mkdtemp(prefix="haqq-test-")
os.environ["HAQQ_LLM_PROVIDER"] = "none"
os.environ["HAQQ_RATE_LIMIT_LOGIN_PER_MINUTE"] = "1000"

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from app.core.ratelimit import limiter  # noqa: E402
from app.db import engine  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = "Str0ngPassw0rd!"


@pytest.fixture(scope="session", autouse=True)
def database():
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    cfg = Config(os.path.join(HERE, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(HERE, "alembic"))
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(scope="session")
def client(database):
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_limits():
    limiter.reset()
    yield


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register(client, company: str, email: str) -> dict:
    r = client.post("/api/v1/auth/register", json={"company_name": company, "full_name": "Admin " + company,
                                                    "email": email, "password": PASSWORD, "language": "en"})
    assert r.status_code == 201, r.text
    return r.json()


def add_user(client, admin_token: str, email: str, role: str) -> str:
    r = client.post("/api/v1/users", headers=auth(admin_token), json={"email": email, "full_name": role.title(),
                                                                       "role": role, "password": PASSWORD})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]
