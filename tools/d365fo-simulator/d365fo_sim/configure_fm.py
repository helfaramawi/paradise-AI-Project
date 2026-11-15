"""Point Future Mirror's "Dynamics 365 F&O" connection at the simulator and test it.

Runs inside the simulator image on the Compose network (see ops/d365-sim.*):
    docker compose --profile d365sim run --rm d365fo-sim python -m d365fo_sim.configure_fm

It signs in as the platform administrator, saves the connection settings (URL, tenant, client id,
legal entity, the last 12 months and the account mapping) and runs "Test connection". It does not
sync, so your current dataset stays as it is until you press Sync in Data Connections.
"""

from __future__ import annotations

import os
import sys

import httpx

from .arabic_data import FM_ACCOUNT_MAPPING, LAST_MONTH
from .server import Settings

API = os.environ.get("FM_API_URL", "http://backend:8000/api/v1").rstrip("/")
SIM_URL = os.environ.get("SIM_INTERNAL_URL", "https://d365fo-sim:8443")


def last_twelve_months() -> tuple[str, str]:
    y, m = LAST_MONTH
    start_y, start_m = (y, m - 11) if m == 12 else (y - 1, m + 1)
    end_day = 31 if m in (1, 3, 5, 7, 8, 10, 12) else (30 if m != 2 else 28)
    return f"{start_y}-{start_m:02d}-01", f"{y}-{m:02d}-{end_day}"


def main() -> int:
    s = Settings.from_env()
    date_from, date_to = last_twelve_months()
    with httpx.Client(timeout=60) as c:
        r = c.post(f"{API}/auth/login", json={"email": os.environ.get("FM_ADMIN_EMAIL", "admin@futuremirror.demo"),
                                              "password": os.environ.get("FM_ADMIN_PASSWORD", "FutureMirror!2026"),
                                              "tenant": os.environ.get("FM_TENANT", "nile-engineering")})
        if r.status_code != 200:
            print(f"[FAILED] Sign-in to Future Mirror failed ({r.status_code}): {r.text[:200]}")
            print("Set FM_ADMIN_EMAIL / FM_ADMIN_PASSWORD if you changed the administrator account.")
            return 1
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        conns = c.get(f"{API}/connectors", headers=h).json()
        conn = next((x for x in conns if x.get("kind") == "d365_fo"), None)
        if not conn:
            print("[FAILED] No 'Dynamics 365 Finance & Operations' connection found in Future Mirror.")
            return 1
        config = {"environment_url": SIM_URL, "authority": SIM_URL, "tenant_id": s.tenant_id, "client_id": s.client_id,
                  "legal_entity": s.default_company, "date_from": date_from, "date_to": date_to,
                  "account_mapping": FM_ACCOUNT_MAPPING}
        r = c.patch(f"{API}/connectors/{conn['id']}", headers=h, json={"config": config})
        if r.status_code != 200:
            print(f"[FAILED] Saving the connection settings failed ({r.status_code}): {r.text[:300]}")
            return 1
        print(f"Saved the Dynamics 365 F&O connection: {SIM_URL}, legal entity {s.default_company}, "
              f"{date_from} to {date_to}.")
        if not r.json().get("secret_configured"):
            print("[FAILED] FM_D365_FO_CLIENT_SECRET is not set for the backend. Run ops/d365-sim again.")
            return 1
        t = c.post(f"{API}/connectors/{conn['id']}/test", headers=h).json()
        print(("Test connection: OK - " if t.get("ok") else "[FAILED] Test connection: ") + str(t.get("message")))
        return 0 if t.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
