import { FileSpreadsheet } from "lucide-react";
import { useState } from "react";
import { Alert, Button, Card, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { useI18n } from "../lib/i18n";

export default function Reports() {
  const { t, lang } = useI18n();
  const [err, setErr] = useState<string | null>(null);
  const dl = (l: string) => api.download(`/reports/portfolio.xlsx?lang=${l}`, "HAQQ_portfolio.xlsx").catch((e) => setErr(e.message));
  return (
    <div>
      <PageHeader title={t("reports")} />
      <div className="grid gap-5 md:grid-cols-2">
        <Card title={<span className="flex items-center gap-2"><FileSpreadsheet className="h-4 w-4" />{t("portfolio_xlsx")}</span>}>
          <p className="text-sm text-slate-600">{lang === "ar" ? "مؤشرات الأداء، جميع المستحقات (بحالتها وأساسها المالي ومواعيدها)، وجميع المطالبات. البيانات التوضيحية مُعلّمة." :
            "KPIs, every entitlement (status, financial basis, notice dates) and every claim. Demonstration data is labelled."}</p>
          <div className="mt-4 flex gap-2"><Button onClick={() => dl("en")}>English</Button><Button variant="secondary" onClick={() => dl("ar")}>العربية</Button></div>
          {err && <Alert tone="error">{err}</Alert>}
        </Card>
        <Card title={lang === "ar" ? "ملفات المطالبات" : "Claim documents"}>
          <p className="text-sm text-slate-600">{lang === "ar" ? "خطابات الإخطار وملفات المطالبات (Word/PDF) وأوراق التقييم (Excel) تُنشأ من صفحة كل مطالبة، بالعربية أو الإنجليزية، مع مراجع المصادر وعلامات التحقق." :
            "Notice letters, claim packages (Word/PDF) and valuation worksheets (Excel) are generated from each claim page, in Arabic or English, with source references and verification markers."}</p>
        </Card>
      </div>
    </div>
  );
}
