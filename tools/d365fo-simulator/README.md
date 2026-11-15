# Dynamics 365 F&O simulator (Arabic test data)

A local test double for Future Mirror's Dynamics 365 Finance & Operations connector. It answers the
Entra ID client-credentials sign-in and the read-only OData data entities over HTTPS, with
synthetic Arabic data for two fictitious Egyptian companies. It is not a Microsoft product.

Start it with `ops/d365-sim.sh` (Windows: `ops\d365-sim.bat`) and read
[docs/D365_FO_TESTING.md](../../docs/D365_FO_TESTING.md).

| File | Purpose |
|---|---|
| `d365fo_sim/arabic_data.py` | Deterministic data: legal entities, chart of accounts, customers, vendors, ledger entries |
| `d365fo_sim/server.py` | Token endpoint, `/data/<EntitySet>`, `/data/$metadata`, browser pages at `/` |
| `d365fo_sim/odata.py` | The OData subset: `$filter` (comparisons joined by `and`), `$select`, `$orderby`, `$top`, `$skip`, `$count`, paging |
| `d365fo_sim/run.py` | Creates a local CA and server certificate in `/certs`, then serves on port 8443 |
| `d365fo_sim/configure_fm.py` | Points Future Mirror's connection at the simulator and tests it |
| `d365fo_sim/package.py` | Writes `arabic-data-package/*.xlsx` for Data management import into a real F&O environment |

Settings (environment variables): `SIM_TENANT_ID`, `SIM_CLIENT_ID`, `SIM_CLIENT_SECRET`,
`SIM_DEFAULT_COMPANY` (EGMF), `SIM_PAGE_SIZE` (1000), `SIM_PUBLIC_URLS`.

Tests: `backend/tests/test_d365fo_simulator.py` runs the real connector against it, including a
real HTTPS handshake with the local CA.
