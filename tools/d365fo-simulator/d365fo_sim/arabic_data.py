"""Deterministic Arabic test data for the Dynamics 365 F&O simulator and the import package.

Two fictitious Egyptian legal entities share one chart of accounts with Arabic names. Each month
from January 2025 to October 2026 produces balanced vouchers (payroll, contractors, software,
hosting, rent, utilities, services, travel, sales, collections) as general-ledger lines. All names
are invented; amounts are in EGP. The same seed always gives the same data.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date

SEED = 2026
FIRST_MONTH = (2025, 1)
LAST_MONTH = (2026, 10)
CHART_OF_ACCOUNTS = "EGCOA"
VAT_RATE = 0.14

MONTHS_AR = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر",
             "نوفمبر", "ديسمبر"]

LEGAL_ENTITIES = [
    {"LegalEntityId": "EGMF", "Name": "شركة المستقبل للصناعات الغذائية", "NameAlias": "Future Foods Industries (test)",
     "AddressCity": "بورسعيد", "AddressCountryRegionId": "EGY", "AccountingCurrency": "EGP", "LanguageId": "ar",
     "scale": 1.0},
    {"LegalEntityId": "EGHS", "Name": "شركة القناة للخدمات الفندقية", "NameAlias": "Canal Hospitality Services (test)",
     "AddressCity": "الإسماعيلية", "AddressCountryRegionId": "EGY", "AccountingCurrency": "EGP", "LanguageId": "ar",
     "scale": 0.4},
]

# (main account, Arabic name, English name, type)
MAIN_ACCOUNTS = [
    ("110100", "النقدية بالبنوك", "Cash at bank", "Asset"),
    ("110200", "الخزينة", "Cash on hand", "Asset"),
    ("120100", "العملاء", "Accounts receivable", "Asset"),
    ("130100", "المخزون", "Inventory", "Asset"),
    ("210100", "الموردون", "Accounts payable", "Liability"),
    ("220100", "رواتب مستحقة", "Accrued salaries", "Liability"),
    ("230100", "ضريبة القيمة المضافة المستحقة", "VAT payable", "Liability"),
    ("240100", "تأمينات اجتماعية مستحقة", "Social insurance payable", "Liability"),
    ("310100", "رأس المال", "Share capital", "Equity"),
    ("410100", "إيرادات المبيعات", "Sales revenue", "Revenue"),
    ("420100", "إيرادات الخدمات", "Service revenue", "Revenue"),
    ("510100", "تكلفة المبيعات - مواد خام", "Cost of sales - raw materials", "Expense"),
    ("610100", "الرواتب والأجور الأساسية", "Basic salaries and wages", "Expense"),
    ("610200", "الحوافز والمكافآت", "Incentives and bonuses", "Expense"),
    ("610300", "حصة الشركة في التأمينات الاجتماعية", "Employer social insurance", "Expense"),
    ("610400", "التأمين الطبي للعاملين", "Employee medical insurance", "Expense"),
    ("620100", "مقاولون واستشاريون خارجيون", "External contractors and consultants", "Expense"),
    ("620200", "عمالة مؤقتة", "Temporary staff", "Expense"),
    ("630100", "تراخيص البرمجيات", "Software licences", "Expense"),
    ("630200", "اشتراكات البرمجيات السحابية", "Cloud software subscriptions", "Expense"),
    ("631100", "استضافة الخوادم ومراكز البيانات", "Server hosting and data centres", "Expense"),
    ("631200", "الاتصالات والإنترنت", "Telecoms and internet", "Expense"),
    ("640100", "إيجار المقر الإداري", "Office rent", "Expense"),
    ("640200", "الكهرباء والمياه", "Electricity and water", "Expense"),
    ("640300", "صيانة المباني", "Building maintenance", "Expense"),
    ("650100", "خدمات الأمن والحراسة", "Security services", "Expense"),
    ("650200", "خدمات النظافة", "Cleaning services", "Expense"),
    ("650300", "خدمات النقل والشحن", "Transport and freight services", "Expense"),
    ("660100", "السفر والانتقالات", "Travel", "Expense"),
    ("660200", "التدريب", "Training", "Expense"),
    ("660300", "مصروفات إدارية عامة", "General administrative expenses", "Expense"),
    ("660400", "أدوات مكتبية ومطبوعات", "Stationery and printing", "Expense"),
]
ACCOUNT_NAME = {a: ar for a, ar, _, _ in MAIN_ACCOUNTS}

# Future Mirror connector mapping: main account prefix -> cost category (longest prefix wins).
FM_ACCOUNT_MAPPING = {"61": "personnel", "62": "contractors", "630": "software", "631": "infrastructure",
                      "64": "facilities", "65": "vendor services", "66": "other g&a"}

DEPARTMENTS = [("ADM", "الإدارة العامة", 0.18), ("PRD", "الإنتاج", 0.42), ("SAL", "المبيعات", 0.16),
               ("FIN", "الشؤون المالية", 0.10), ("IT", "تكنولوجيا المعلومات", 0.14)]
COST_CENTRES = {"EGMF": "PSD", "EGHS": "ISM"}  # بورسعيد / الإسماعيلية

CITIES = ["بورسعيد", "الإسماعيلية", "السويس", "القاهرة", "الإسكندرية", "دمياط", "المنصورة", "طنطا"]
STREETS = ["شارع الجمهورية", "شارع 23 يوليو", "شارع محمد علي", "شارع فلسطين", "شارع الثلاثيني",
           "شارع النصر", "شارع سعد زغلول", "كورنيش النيل"]
NAME_CORES = ["النيل", "الدلتا", "القناة", "الفيروز", "الصفا", "المروة", "الأمل", "الرواد", "السلام", "النور",
              "الهدى", "الوادي", "سيناء", "المنارة", "الأهرام", "المتوسط", "الريادة", "التقدم", "الفجر", "الشروق",
              "الزهراء", "الإيمان", "البركة", "الخليج", "الأندلس"]
CUSTOMER_KINDS = [("شركة", "للتجارة والتوزيع", "CORP"), ("سلسلة", "للأسواق التجارية", "RETAIL"),
                  ("مجموعة", "للفنادق والسياحة", "CORP"), ("مؤسسة", "للتوريدات العمومية", "CORP"),
                  ("شركة", "للاستيراد والتصدير", "EXPORT"), ("مصنع", "للمنتجات الغذائية", "CORP")]
VENDOR_KINDS = {
    "CONT": [("مكتب", "للاستشارات الهندسية"), ("شركة", "للمقاولات العامة"), ("مكتب", "للاستشارات المالية")],
    "IT": [("شركة", "لنظم المعلومات"), ("شركة", "للحلول الرقمية")],
    "UTIL": [("شركة", "لخدمات المرافق")],
    "SERV": [("شركة", "للأمن والحراسة"), ("شركة", "لخدمات النظافة"), ("شركة", "للنقل والشحن")],
    "SUPP": [("شركة", "للمواد الخام"), ("مؤسسة", "للأدوات المكتبية")],
}


@dataclass
class Dataset:
    legal_entities: list[dict] = field(default_factory=list)
    main_accounts: list[dict] = field(default_factory=list)
    customers: list[dict] = field(default_factory=list)
    vendors: list[dict] = field(default_factory=list)
    gl_entries: list[dict] = field(default_factory=list)
    journals: list[dict] = field(default_factory=list)  # balanced vouchers, for the import package

    def entity_sets(self) -> dict[str, list[dict]]:
        return {"LegalEntities": self.legal_entities, "MainAccounts": self.main_accounts,
                "CustomersV3": self.customers, "VendorsV2": self.vendors,
                "GeneralJournalAccountEntries": self.gl_entries}


def _months():
    y, m = FIRST_MONTH
    while (y, m) <= LAST_MONTH:
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def _unique_names(rng: random.Random, kinds: list[tuple[str, str]], n: int, used: set[str]) -> list[tuple[str, int]]:
    out = []
    while len(out) < n:
        k = rng.randrange(len(kinds))
        prefix, suffix = kinds[k][0], kinds[k][1]
        name = f"{prefix} {rng.choice(NAME_CORES)} {suffix}"
        if name not in used:
            used.add(name)
            out.append((name, k))
    return out


def _phone(rng: random.Random, city: str) -> str:
    code = {"بورسعيد": "66", "الإسماعيلية": "64", "السويس": "62", "القاهرة": "2", "الإسكندرية": "3",
            "دمياط": "57", "المنصورة": "50", "طنطا": "40"}[city]
    return f"+20 {code} {rng.randint(2000000, 3999999)}"


def generate(seed: int = SEED) -> Dataset:
    rng = random.Random(seed)
    ds = Dataset()
    ds.legal_entities = [{k: v for k, v in le.items() if k != "scale"} for le in LEGAL_ENTITIES]
    ds.main_accounts = [{"ChartOfAccounts": CHART_OF_ACCOUNTS, "MainAccountId": a, "Name": ar, "MainAccountType": t}
                        for a, ar, _, t in MAIN_ACCOUNTS]
    used: set[str] = set()
    for le in LEGAL_ENTITIES:
        co = le["LegalEntityId"]
        for i, (name, k) in enumerate(_unique_names(rng, [(p, s) for p, s, _ in CUSTOMER_KINDS], 30, used), 1):
            city = rng.choice(CITIES)
            ds.customers.append({
                "dataAreaId": co.lower(), "CustomerAccount": f"C-{i:04d}", "OrganizationName": name,
                "PartyType": "Organization", "CustomerGroupId": CUSTOMER_KINDS[k][2], "SalesCurrencyCode": "EGP",
                "LanguageId": "ar", "AddressCity": city, "AddressStreet": f"{rng.randint(1, 120)} {rng.choice(STREETS)}",
                "AddressCountryRegionId": "EGY", "PrimaryContactPhone": _phone(rng, city),
                "CreditLimit": float(rng.choice([250, 500, 750, 1000, 1500, 2500]) * 1000),
                "PaymentTerms": rng.choice(["Net30", "Net45", "Net60"])})
        vid = 0
        for group, kinds in VENDOR_KINDS.items():
            for name, _ in _unique_names(rng, kinds, 2 if group != "SERV" else 3, used):
                vid += 1
                city = rng.choice(CITIES)
                ds.vendors.append({
                    "dataAreaId": co.lower(), "VendorAccountNumber": f"V-{vid:04d}", "VendorOrganizationName": name,
                    "VendorGroupId": group, "CurrencyCode": "EGP", "LanguageId": "ar", "AddressCity": city,
                    "AddressStreet": f"{rng.randint(1, 120)} {rng.choice(STREETS)}", "AddressCountryRegionId": "EGY",
                    "PrimaryContactPhone": _phone(rng, city), "PaymentTermsName": rng.choice(["Net30", "Net45"])})
    for le in LEGAL_ENTITIES:
        _ledger(rng, ds, le)
    return ds


def _ledger(rng: random.Random, ds: Dataset, le: dict) -> None:
    co, scale = le["LegalEntityId"], le["scale"]
    cc = COST_CENTRES[co]
    customers = [c for c in ds.customers if c["dataAreaId"] == co.lower()]
    vendors = {g: [v for v in ds.vendors if v["dataAreaId"] == co.lower() and v["VendorGroupId"] == g]
               for g in VENDOR_KINDS}
    seq = {"n": 0}
    receivable_open: list[float] = []

    def voucher(d: date, category: str, text: str, lines: list[tuple[str, float, str]]) -> None:
        """lines = (ledger account display value, signed amount, posting type); must balance."""
        assert abs(sum(a for _, a, _ in lines)) < 0.005, text
        seq["n"] += 1
        jnum = f"GJ-{co}-{seq['n']:06d}"
        vnum = f"{co}-{d:%y%m}-{seq['n']:05d}"
        ds.journals.append({"company": co, "journal": jnum, "voucher": vnum, "date": d, "category": category,
                            "text": text, "lines": [(acct.split("-")[0], amt) for acct, amt, _ in lines]})
        for acct, amt, ptype in lines:
            main = acct.split("-")[0]
            ds.gl_entries.append({
                "dataAreaId": co.lower(), "JournalNumber": jnum, "Voucher": vnum,
                "AccountingDate": f"{d.isoformat()}T12:00:00Z", "LedgerAccount": acct, "MainAccount": main,
                "MainAccountName": ACCOUNT_NAME[main], "Text": text, "JournalCategory": category,
                "PostingType": ptype, "IsCredit": amt < 0, "AccountingCurrencyAmount": round(amt, 2),
                "TransactionCurrencyAmount": round(amt, 2), "TransactionCurrencyCode": "EGP"})

    def amt(base: float, noise: float = 0.08) -> float:
        return round(base * scale * rng.uniform(1 - noise, 1 + noise), 2)

    def day(y: int, m: int, lo: int = 1, hi: int = 28) -> date:
        return date(y, m, rng.randint(lo, hi))

    def dim(main: str, dept: str = "ADM") -> str:
        return f"{main}-{cc}-{dept}"

    def vend_invoice(d: date, main: str, group: str, base: float, what: str, dept: str = "ADM") -> None:
        v = rng.choice(vendors[group])
        a = amt(base)
        voucher(d, "Vendor invoice", f"{what} - {v['VendorOrganizationName']} - فاتورة {rng.randint(1000, 9999)}",
                [(dim(main, dept), a, "LedgerJournal"), ("210100", -a, "VendBalance")])

    for i, (y, m) in enumerate(_months()):
        month = f"{MONTHS_AR[m - 1]} {y}"
        growth = 1 + 0.006 * i  # about 7% a year
        # Payroll by department (personnel, about 66m a year at full scale)
        for code, name_ar, share in DEPARTMENTS:
            gross = amt(4_150_000 * share * growth, 0.02)
            voucher(date(y, m, 25), "Payroll", f"رواتب شهر {month} - {name_ar}",
                    [(dim("610100", code), gross, "LedgerJournal"), ("220100", -gross, "LedgerJournal")])
        si = amt(520_000 * growth, 0.02)
        voucher(date(y, m, 25), "Payroll", f"حصة الشركة في التأمينات الاجتماعية - {month}",
                [(dim("610300", "ADM"), si, "LedgerJournal"), ("240100", -si, "LedgerJournal")])
        vend_invoice(day(y, m), "610400", "SERV", 260_000 * growth, f"التأمين الطبي - {month}")
        if m in (3, 6, 9, 12):
            bonus = amt(1_900_000 * growth, 0.15)
            voucher(date(y, m, 28), "Payroll", f"حوافز الربع - {month}",
                    [(dim("610200", "PRD"), bonus, "LedgerJournal"), ("220100", -bonus, "LedgerJournal")])
        net = round(4_150_000 * scale * growth * 0.97, 2)
        voucher(date(y, m, 27), "Payment", f"صرف رواتب شهر {month}",
                [("220100", net, "LedgerJournal"), ("110100", -net, "Bank")])
        # Contractors (about 18m)
        for _ in range(rng.randint(3, 5)):
            vend_invoice(day(y, m), rng.choice(["620100", "620100", "620200"]), "CONT", 370_000,
                         "أعمال استشارية وتنفيذية", rng.choice(["PRD", "IT", "ADM"]))
        # Software (about 12m): annual licences in January, subscriptions monthly
        if m == 1:
            vend_invoice(date(y, 1, 15), "630100", "IT", 6_000_000, f"تجديد تراخيص البرمجيات لعام {y}", "IT")
        vend_invoice(day(y, m), "630200", "IT", 500_000, f"اشتراكات البرمجيات السحابية - {month}", "IT")
        # Infrastructure (about 9m)
        vend_invoice(day(y, m), "631100", "IT", 560_000, f"استضافة الخوادم - {month}", "IT")
        vend_invoice(day(y, m), "631200", "UTIL", 190_000, f"الاتصالات والإنترنت - {month}", "IT")
        # Facilities (about 6m)
        vend_invoice(date(y, m, 1), "640100", "SUPP", 330_000, f"إيجار المقر الإداري - {month}")
        vend_invoice(day(y, m), "640200", "UTIL", 120_000, f"فاتورة الكهرباء والمياه - {month}")
        if rng.random() < 0.4:
            vend_invoice(day(y, m), "640300", "CONT", 180_000, "أعمال صيانة المباني")
        # Vendor services (about 5m)
        vend_invoice(day(y, m), "650100", "SERV", 170_000, f"خدمات الأمن والحراسة - {month}")
        vend_invoice(day(y, m), "650200", "SERV", 110_000, f"خدمات النظافة - {month}")
        vend_invoice(day(y, m), "650300", "SERV", 140_000, "نقل وشحن البضائع", "SAL")
        # Other G&A (about 4m)
        for main, base, what in (("660100", 120_000, "مصروفات سفر وانتقالات"), ("660300", 110_000, "مصروفات إدارية"),
                                 ("660400", 40_000, "أدوات مكتبية ومطبوعات")):
            a = amt(base, 0.3)
            voucher(day(y, m), "Daily", f"{what} - {month}",
                    [(dim(main, rng.choice(["ADM", "SAL", "FIN"])), a, "LedgerJournal"), ("110200", -a, "LedgerJournal")])
        if m in (2, 5, 10):
            vend_invoice(day(y, m), "660200", "CONT", 420_000, "برنامج تدريبي للعاملين", "ADM")
        # Vendor payments: settle most payables monthly
        pay = amt(9_200_000 * growth, 0.05)
        voucher(day(y, m, 20, 28), "Payment", f"سداد مستحقات الموردين - {month}",
                [("210100", pay, "VendBalance"), ("110100", -pay, "Bank")])
        # Sales with VAT, cost of sales, and collections with a lag
        for _ in range(rng.randint(8, 12)):
            c = rng.choice(customers)
            net_sale = amt(1_650_000 * growth, 0.35)
            vat = round(net_sale * VAT_RATE, 2)
            rev = "420100" if le["LegalEntityId"] == "EGHS" else "410100"
            voucher(day(y, m), "Customer invoice", f"فاتورة مبيعات - {c['OrganizationName']}",
                    [("120100", net_sale + vat, "CustBalance"), (rev, -net_sale, "LedgerJournal"),
                     ("230100", -vat, "LedgerJournal")])
            receivable_open.append(net_sale + vat)
            cogs = round(net_sale * rng.uniform(0.52, 0.6), 2)
            voucher(day(y, m), "Daily", f"تكلفة المبيعات - {c['OrganizationName']}",
                    [(dim("510100", "PRD"), cogs, "LedgerJournal"), ("130100", -cogs, "LedgerJournal")])
        due = receivable_open[: max(0, len(receivable_open) - 12)]
        receivable_open = receivable_open[len(due):]
        collected = round(sum(due) * rng.uniform(0.78, 0.9), 2)
        if collected:
            voucher(day(y, m, 15, 28), "Payment", f"تحصيلات من العملاء - {month}",
                    [("110100", collected, "Bank"), ("120100", -collected, "CustBalance")])


if __name__ == "__main__":  # quick summary
    d = generate()
    print({k: len(v) for k, v in d.entity_sets().items()}, "vouchers:", len(d.journals))
