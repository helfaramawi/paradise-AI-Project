"""Write the Arabic test data as Excel files for Data management import into a real F&O environment.

    python -m d365fo_sim.package [output folder]     (default: ../arabic-data-package)

One workbook per data entity and legal entity, in import order. Column names follow the standard
entity field names (Main accounts, Customers V3, Vendors V2, General journal). If an environment
names a field differently, F&O shows it in "View map" and you map it there. General journal lines
use the main account only (no financial dimensions), so they import without a dimension setup.
"""

from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from .arabic_data import LEGAL_ENTITIES, MAIN_ACCOUNTS, Dataset, generate

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "arabic-data-package"


def _write(path: Path, sheet: str, header: list[str], rows: list[list]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet[:31]
    ws.append(header)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="E5E7EB")
    for r in rows:
        ws.append(r)
    for i, h in enumerate(header, 1):
        width = max([len(str(h))] + [len(str(r[i - 1])) for r in rows[:200]]) + 2
        ws.column_dimensions[get_column_letter(i)].width = min(width, 60)
        if h in ("TRANSDATE",):
            for cell in ws[get_column_letter(i)][1:]:
                cell.number_format = "yyyy-mm-dd"
    ws.freeze_panes = "A2"
    wb.save(path)


def write_package(out: Path = DEFAULT_OUT, ds: Dataset | None = None) -> list[Path]:
    ds = ds or generate()
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    p = out / "01_MainAccounts.xlsx"
    _write(p, "Main accounts", ["MAINACCOUNTID", "NAME", "MAINACCOUNTTYPE", "CHARTOFACCOUNTS"],
           [[a["MainAccountId"], a["Name"], a["MainAccountType"], a["ChartOfAccounts"]] for a in ds.main_accounts])
    written.append(p)
    p = out / "01_MainAccounts_English_names.xlsx"
    _write(p, "Main account translations", ["MAINACCOUNTID", "NAME_AR", "NAME_EN"],
           [[a, ar, en] for a, ar, en, _ in MAIN_ACCOUNTS])
    written.append(p)

    for le in LEGAL_ENTITIES:
        co = le["LegalEntityId"]
        cust = [c for c in ds.customers if c["dataAreaId"] == co.lower()]
        p = out / f"02_Customers_{co}.xlsx"
        _write(p, "Customers V3", ["CUSTOMERACCOUNT", "ORGANIZATIONNAME", "PARTYTYPE", "CUSTOMERGROUPID",
                                   "SALESCURRENCYCODE", "LANGUAGEID", "ADDRESSCOUNTRYREGIONID", "ADDRESSCITY",
                                   "ADDRESSSTREET", "PRIMARYCONTACTPHONE", "CREDITLIMIT", "PAYMENTTERMS"],
               [[c["CustomerAccount"], c["OrganizationName"], c["PartyType"], c["CustomerGroupId"],
                 c["SalesCurrencyCode"], c["LanguageId"], c["AddressCountryRegionId"], c["AddressCity"],
                 c["AddressStreet"], c["PrimaryContactPhone"], c["CreditLimit"], c["PaymentTerms"]] for c in cust])
        written.append(p)
        vend = [v for v in ds.vendors if v["dataAreaId"] == co.lower()]
        p = out / f"03_Vendors_{co}.xlsx"
        _write(p, "Vendors V2", ["VENDORACCOUNTNUMBER", "VENDORORGANIZATIONNAME", "VENDORGROUPID", "CURRENCYCODE",
                                 "LANGUAGEID", "ADDRESSCOUNTRYREGIONID", "ADDRESSCITY", "ADDRESSSTREET",
                                 "PRIMARYCONTACTPHONE", "PAYMENTTERMSNAME"],
               [[v["VendorAccountNumber"], v["VendorOrganizationName"], v["VendorGroupId"], v["CurrencyCode"],
                 v["LanguageId"], v["AddressCountryRegionId"], v["AddressCity"], v["AddressStreet"],
                 v["PrimaryContactPhone"], v["PaymentTermsName"]] for v in vend])
        written.append(p)
        lines = []
        for j in (j for j in ds.journals if j["company"] == co):
            batch = f"{co}-GJ-{j['date']:%y%m}"
            for acct, amount in j["lines"]:
                lines.append([batch, "GenJrn", f"قيود شهر {j['date']:%Y-%m}", 0, j["voucher"], j["date"], "Ledger", acct,
                              round(amount, 2) if amount > 0 else None, round(-amount, 2) if amount < 0 else None,
                              "EGP", j["text"]])
        counters: dict[str, int] = {}
        for row in lines:  # line numbers restart in every monthly journal
            counters[row[0]] = counters.get(row[0], 0) + 1
            row[3] = counters[row[0]]
        p = out / f"04_GeneralJournal_{co}.xlsx"
        _write(p, "General journal", ["JOURNALBATCHNUMBER", "JOURNALNAME", "DESCRIPTION", "LINENUMBER", "VOUCHER",
                                      "TRANSDATE", "ACCOUNTTYPE", "ACCOUNTDISPLAYVALUE", "DEBITAMOUNT", "CREDITAMOUNT",
                                      "CURRENCYCODE", "TEXT"], lines)
        written.append(p)
    return written


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    for f in write_package(target):
        print(f)
