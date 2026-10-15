import os
import tempfile
import time

_tmp = tempfile.mkdtemp(prefix="fm-test-")
os.environ.setdefault("FM_DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ["FM_PRESENTATION_PACING_MS"] = "0"
os.environ["FM_ENVIRONMENT"] = "test"
os.environ["FM_LLM_PROVIDER"] = "none"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

PASSWORD = "FutureMirror!2026"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def login(client, email: str, tenant: str = "nile-engineering") -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD, "tenant": tenant})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def ceo(client):
    return login(client, "ceo@futuremirror.demo")


@pytest.fixture(scope="session")
def analyst(client):
    return login(client, "analyst@futuremirror.demo")


def wait_run(client, headers, run_id: str, timeout: float = 60) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = client.get(f"/api/v1/runs/{run_id}", headers=headers).json()
        if r["status"] in ("completed", "failed", "cancelled"):
            return r
        time.sleep(0.2)
    raise AssertionError("run did not finish")


@pytest.fixture(scope="session")
def analyzed_decision(client, analyst):
    q = client.get("/api/v1/decisions/demo-question", headers=analyst).json()["question_en"]
    d = client.post("/api/v1/decisions", json={"title": "Demo opex reduction", "question": q}, headers=analyst).json()
    run = client.post(f"/api/v1/decisions/{d['id']}/runs", json={"pacing_ms": 0}, headers=analyst).json()
    res = wait_run(client, analyst, run["run_id"])
    assert res["status"] == "completed", res.get("error")
    return {"decision": d, "run_id": run["run_id"]}
