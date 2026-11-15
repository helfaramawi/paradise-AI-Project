# Testing Future Mirror with Dynamics 365 Finance & Operations (Arabic test data)

There are two ways to test the Dynamics 365 F&O connector:

| | Local F&O simulator | Real F&O environment |
|---|---|---|
| What it is | A Docker service on your PC that answers like F&O: the Entra ID sign-in and the OData data entities, over HTTPS | A Microsoft F&O sandbox or developer environment in your Microsoft tenant |
| What you need | Docker Desktop, nothing else | F&O licences or partner access, a Power Platform / Entra ID administrator |
| Arabic data | Built in: two Egyptian companies, 22 months of ledger entries | Imported from the Excel package in `tools/d365fo-simulator/arabic-data-package` |
| Use it to | Test and demo the connector today | Prove the integration against the real product |

The simulator is a test double written for Future Mirror. It is not a Microsoft product and it does not reproduce F&O: it implements only the sign-in and the read-only OData calls the connector makes. A real environment remains the final check.

## 1. Local F&O simulator (start here)

### Start it

Windows: double-click `ops\d365-sim.bat`. macOS / Linux: run `ops/d365-sim.sh`.

The script:

1. adds two lines to `.env` if they are not there (`FM_D365_FO_CLIENT_SECRET` and `FM_D365_CA_BUNDLE`);
2. starts Future Mirror together with the simulator (`docker compose --profile d365sim up -d --build`);
3. connects Future Mirror's "Dynamics 365 Finance & Operations" connection to the simulator and runs **Test connection**.

It does not sync, so your current dataset stays as it is until you press **Sync** yourself.

To stop only the simulator: `ops\d365-sim.bat stop` (or `ops/d365-sim.sh stop`). `ops\stop.bat` stops everything.

### Look at the test data

Open https://localhost:8443 and accept the browser's certificate warning (the simulator uses its own local certificate). The page lists the companies, the record counts and the connection details. Every table opens in the browser.

| Data | EGMF · شركة المستقبل للصناعات الغذائية | EGHS · شركة القناة للخدمات الفندقية |
|---|---|---|
| Customers (`CustomersV3`) | 30 | 30 |
| Vendors (`VendorsV2`) | 11 | 11 |
| Ledger lines (`GeneralJournalAccountEntries`) | about 2,200 | about 2,250 |

Shared: 32 main accounts with Arabic names (`MainAccounts`), and 2 legal entities (`LegalEntities`). Ledger entries run from January 2025 to October 2026, in EGP: payroll by department, social and medical insurance, contractors, software licences and subscriptions, hosting, telecoms, rent, utilities, security and cleaning services, freight, travel and training, sales with 14% VAT, cost of sales, customer collections and vendor payments. EGHS is about 40% the size of EGMF. All names are invented.

### Sync in Future Mirror

1. Sign in as `admin@futuremirror.demo` (or CFO).
2. Open **Data Connections** → **Dynamics 365 Finance & Operations**. The status shows **connected**.
3. Press **Sync**. Future Mirror reads about 1,230 ledger lines for the last 12 months (November 2025 to October 2026), in pages of 1,000, and updates the cost profile.

What to expect for EGMF, in EGP millions (the account mapping is set by the script):

| Category | Main accounts | About |
|---|---|---|
| Personnel | 61xxxx | 73 |
| Contractors | 62xxxx | 17.5 |
| Software | 630xxx | 11.7 |
| Infrastructure | 631xxx | 9.1 |
| Facilities | 64xxxx | 6.5 |
| Vendor services | 65xxxx | 5.0 |
| Other G&A | 66xxxx | 4.5 |

Balance-sheet, revenue and cost-of-sales accounts are counted as "ignored" in the reconciliation, as they should be.

To try the second company, change **Legal entity** to `EGHS` in the connection settings and sync again. To try failures, change the client ID, the environment URL or a field name under **Advanced**: the simulator answers with the same kind of error a real tenant gives (see Troubleshooting).

### Connection details (already filled in by the script)

| Setting | Value |
|---|---|
| Environment URL | `https://d365fo-sim:8443` (the simulator's name inside Docker) |
| Sign-in authority (Advanced) | `https://d365fo-sim:8443` |
| Tenant ID | `7d3c1f2a-5b6e-4c8d-9a01-2b3c4d5e6f70` |
| Client ID | `c9e5b8d4-1a2b-4c3d-8e9f-0a1b2c3d4e5f` |
| Client secret | `FM_D365_FO_CLIENT_SECRET` in `.env` (default `fm-sim-secret-2026`) |
| Legal entity | `EGMF` (the simulator's default company) or `EGHS` |
| Period | 2025-11-01 to 2026-10-31 |

`FM_D365_CA_BUNDLE=/certs/d365sim/ca.pem` makes Future Mirror trust the simulator's local certificate. Certificate checking stays on.

## 2. A real Dynamics 365 F&O environment

Microsoft provides F&O environments only inside your own Microsoft tenant, so this part needs someone with the right Microsoft licences or partner access. The usual routes are:

- **Customers with F&O licences:** create a sandbox, or a developer environment in the **Power Platform admin center**. For a new unified environment, install the **Finance and Operations Platform Tools** app first and then the **Dynamics 365 Finance and Operations Provisioning App**, which has an option to deploy the Contoso demo data. Microsoft's tutorial: [Install the finance and operations provisioning app](https://learn.microsoft.com/en-us/power-platform/admin/unified-experience/tutorial-install-finance-operations-provisioning-app).
- **Microsoft partners:** use your partner entitlements, or ask your Microsoft partner for a sandbox.
- **Trials:** Microsoft offers Dynamics 365 Finance trials on its website. Before you rely on one, check that you can register an Entra ID app in the trial tenant and add it in F&O (step 2.3); without that the connector cannot sign in.

Contoso's demo data is in English and in other currencies. To get the Arabic data used in the simulator, import the package in step 2.2.

### 2.1 Arabic interface

Each user picks the language under **Settings (gear) → User options → Language → Arabic (ar)**. The interface switches to right-to-left. Data you enter stays as entered.

### 2.2 Import the Arabic test data

The Excel files in `tools/d365fo-simulator/arabic-data-package` hold the same data as the simulator (regenerate them with `python -m d365fo_sim.package` from `tools/d365fo-simulator`).

**Set up first (by hand, once):**

1. **Legal entities:** Organization administration → Organizations → Legal entities → New: `EGMF` (شركة المستقبل للصناعات الغذائية) and `EGHS` (شركة القناة للخدمات الفندقية), country/region EGY.
2. **Chart of accounts:** General ledger → Chart of accounts → Accounts → Chart of accounts → New: `EGCOA`.
3. **Ledger:** in each new company, General ledger → Ledger setup → Ledger: chart of accounts `EGCOA`, accounting currency `EGP`, a fiscal calendar that covers 2025–2026, and an account structure that uses the main account only (or add the dimensions you need).
4. **Groups and terms:** in each company, customer groups `CORP`, `RETAIL`, `EXPORT`; vendor groups `CONT`, `IT`, `UTIL`, `SERV`, `SUPP`; payment terms `Net30`, `Net45`, `Net60`.
5. **Journal name:** General ledger → Journal setup → Journal names: `GenJrn`, type Daily. If the import later rejects the voucher numbers, set the journal name's voucher allocation to manual.

**Import (Data management workspace → Import), in this order:**

| Order | File | Data entity | Company |
|---|---|---|---|
| 1 | `01_MainAccounts.xlsx` | Main accounts | any (shared) |
| 2 | `02_Customers_EGMF.xlsx`, `02_Customers_EGHS.xlsx` | Customers V3 | EGMF, EGHS |
| 3 | `03_Vendors_EGMF.xlsx`, `03_Vendors_EGHS.xlsx` | Vendors V2 | EGMF, EGHS |
| 4 | `04_GeneralJournal_EGMF.xlsx`, `04_GeneralJournal_EGHS.xlsx` | General journal | EGMF, EGHS |

For each file:

1. Switch to the target company (top right).
2. **Import** → enter a name, **Source data format** = EXCEL, choose the entity, then upload the file.
3. Open **View map**. F&O matches the columns by name. If your version names a field differently, map it here.
4. Press **Import**, then fix any rows listed under **View staging data** / **Execution log**.

After step 4 the journals exist but are not posted. Open General ledger → Journal entries → General journals, select the journals, **Validate** and then **Post**. Only posted lines appear in `GeneralJournalAccountEntries`, which is what Future Mirror reads.

The journal files hold one journal per month (about 2,200 lines per company) and use the main account only, with no financial dimensions, so they import without a dimension setup. `01_MainAccounts_English_names.xlsx` lists the English name of every account, if you want to add translations.

### 2.3 Let Future Mirror sign in

**In Microsoft Entra ID (Azure portal), as an administrator:**

1. **App registrations → New registration**: name `Future Mirror AI`, single tenant. Note the **Application (client) ID** and the **Directory (tenant) ID**.
2. **Certificates & secrets → New client secret**. Copy the secret value now; it is shown once.

**In F&O, as a system administrator:**

3. **System administration → Setup → Microsoft Entra applications → New**: client ID = the application ID above, name `Future Mirror AI`, user ID = a user with read access to the general ledger in EGMF and EGHS (a dedicated integration user is best). The app reads data with that user's security roles.

**In Future Mirror:**

4. In `.env` on the Future Mirror server, set `FM_D365_FO_CLIENT_SECRET=<the secret>`. If you used the simulator before, delete the `FM_D365_CA_BUNDLE` line (Microsoft's certificates are trusted already). Restart with `ops\restart.bat`.
5. **Data Connections → Dynamics 365 Finance & Operations → Settings:**

| Setting | Value |
|---|---|
| Environment URL | `https://<your-environment>.operations.dynamics.com` (no trailing `/`) |
| Tenant ID, Client ID | from step 1 |
| Legal entity | `EGMF` |
| Date from / to | the period to read, e.g. 2025-11-01 to 2026-10-31 |
| Sign-in authority (Advanced) | leave empty (Microsoft's sign-in, `https://login.microsoftonline.com`) |
| Account mapping | `61` personnel, `62` contractors, `630` software, `631` infrastructure, `64` facilities, `65` vendor services, `66` other g&a |

6. Press **Test connection**, then **Sync**.

If **Test connection** says a field does not exist, open `https://<your-environment>.operations.dynamics.com/data/GeneralJournalAccountEntries?$top=1&cross-company=true` in a browser where you are signed in to F&O. Compare the field names with the connector's defaults (`LedgerAccount`, `AccountingCurrencyAmount`, `AccountingDate`, `dataAreaId`) and set the right names under **Advanced**.

## 3. Troubleshooting

| Message | Meaning | Fix |
|---|---|---|
| `AADSTS7000215: Invalid client secret` | Wrong or expired secret | Set `FM_D365_FO_CLIENT_SECRET` in `.env` again and restart |
| `AADSTS700016: Application ... was not found` | Wrong client ID, or the app is in another tenant | Check the client ID and tenant ID |
| `AADSTS500011: The resource principal ... was not found` | The environment URL is wrong (the token is requested for that URL) | Use the exact environment URL, with no path and no trailing `/` |
| `AADSTS90002: Tenant ... not found` | Wrong tenant ID | Copy the Directory (tenant) ID again |
| `OData request failed (401)` | Signed in, but F&O does not know the app | Add it under Microsoft Entra applications (step 2.3, item 3) |
| `Could not find a property named ...` | The entity's field names differ | Set the field names under **Advanced** |
| `CERTIFICATE_VERIFY_FAILED` | The server certificate is not trusted | Simulator: run `ops/d365-sim` again so `FM_D365_CA_BUNDLE` is set. Behind a TLS-inspecting proxy: point `FM_D365_CA_BUNDLE` to the proxy's CA file (mounted into the backend) |
| `FM_D365_CA_BUNDLE points to a file that does not exist` | The simulator has never started, so its certificate was not created | Run `ops/d365-sim` |
| `More than 500000 ledger lines` | The period is too large | Narrow the dates or set a legal entity |
| Sync works, but categories are 0 | The account mapping does not match your chart of accounts | Change the prefixes in the mapping |
