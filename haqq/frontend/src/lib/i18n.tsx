import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Lang = "en" | "ar";

const D: Record<string, [string, string]> = {
  // brand & nav
  brand: ["HAQQ", "حقّك"],
  tagline: ["Don't lose what your contract entitles you to.", "اكتشف مستحقاتك التعاقدية قبل أن تضيع."],
  by_pais: ["by Paradise AI Solutions", "من Paradise AI Solutions"],
  nav_dashboard: ["Executive dashboard", "لوحة القيادة التنفيذية"],
  nav_projects: ["Projects", "المشروعات"],
  nav_deadlines: ["Deadline calendar", "تقويم المواعيد"],
  nav_reports: ["Reports & exports", "التقارير والتصدير"],
  nav_admin: ["Administration", "الإدارة"],
  nav_users: ["Users & roles", "المستخدمون والأدوار"],
  nav_settings: ["Organisation settings", "إعدادات المؤسسة"],
  nav_subscription: ["Subscription & usage", "الاشتراك والاستخدام"],
  nav_platform: ["PAIS commercial", "التقرير التجاري"],
  logout: ["Sign out", "تسجيل الخروج"],
  language: ["العربية", "English"],
  demo_banner: ["DEMONSTRATION DATA — fictional projects and documents. Figures are illustrative, not proven claims or guaranteed recoveries.",
    "بيانات عرض توضيحي — مشروعات ومستندات افتراضية. الأرقام توضيحية وليست مطالبات مثبتة أو مبالغ مضمونة التحصيل."],
  // auth
  sign_in: ["Sign in", "تسجيل الدخول"], email: ["E-mail", "البريد الإلكتروني"], password: ["Password", "كلمة المرور"],
  mfa_code: ["Authenticator code", "رمز المصادقة"], no_account: ["New company? Start a free trial", "شركة جديدة؟ ابدأ تجربة مجانية"],
  have_account: ["Already have an account? Sign in", "لديك حساب؟ سجّل الدخول"],
  demo_accounts: ["Demo accounts (password HaqqDemo!2026)", "حسابات العرض (كلمة المرور HaqqDemo!2026)"],
  // onboarding
  onboarding: ["Organisation onboarding", "تهيئة المؤسسة"], company_name: ["Company name", "اسم الشركة"],
  company_name_ar: ["Company name (Arabic)", "اسم الشركة بالعربية"], full_name: ["Your full name", "الاسم بالكامل"],
  plan: ["Plan", "الباقة"], create_account: ["Create organisation", "إنشاء المؤسسة"],
  onb_step_policy: ["Calendar & AI data policy", "التقويم وسياسة بيانات الذكاء الاصطناعي"],
  onb_step_project: ["Register your first project", "سجّل أول مشروع"], finish: ["Finish", "إنهاء"], next: ["Next", "التالي"],
  // common
  save: ["Save", "حفظ"], cancel: ["Cancel", "إلغاء"], create: ["Create", "إنشاء"], edit: ["Edit", "تعديل"], close: ["Close", "إغلاق"],
  loading: ["Loading…", "جارٍ التحميل…"], none: ["None", "لا يوجد"], search: ["Search", "بحث"], all: ["All", "الكل"],
  view: ["View", "عرض"], download: ["Download", "تنزيل"], open: ["Open", "فتح"], status: ["Status", "الحالة"], date: ["Date", "التاريخ"],
  type: ["Type", "النوع"], title: ["Title", "العنوان"], description: ["Description", "الوصف"], amount: ["Amount", "القيمة"],
  page: ["p.", "ص"], pages: ["pages", "صفحات"], confidence: ["Confidence", "درجة الثقة"], risk: ["Risk", "المخاطر"],
  high: ["High", "مرتفعة"], medium: ["Medium", "متوسطة"], low: ["Low", "منخفضة"], days: ["days", "يوم"],
  yes: ["Yes", "نعم"], no: ["No", "لا"], actions: ["Actions", "الإجراءات"], error: ["Something went wrong", "حدث خطأ"],
  not_quantified: ["Not quantified", "غير مُقدّر"], verify_required: ["Requires human verification", "يتطلب تحققًا بشريًا"],
  // dashboard
  exec_title: ["Executive intelligence", "الذكاء التنفيذي"],
  exec_sub: ["Contractual entitlements and revenue recovery across your portfolio — computed from stored records.",
    "المستحقات التعاقدية واسترداد الإيرادات عبر المحفظة — محسوبة من السجلات المخزنة."],
  k_total_contract_value: ["Total contract value", "إجمالي قيمة العقود"],
  k_potential_entitlements: ["Potential entitlements", "المستحقات المحتملة"],
  k_claims_in_preparation: ["Claims in preparation", "مطالبات قيد الإعداد"],
  k_claims_submitted: ["Claims submitted", "مطالبات مُقدّمة"], k_claims_approved: ["Claims approved", "مطالبات معتمدة"],
  k_claims_rejected: ["Claims rejected", "مطالبات مرفوضة"], k_outstanding_approved: ["Approved, not yet collected", "معتمد ولم يُحصّل"],
  k_cash_collected: ["Cash collected", "المبالغ المُحصّلة"], k_revenue_at_risk: ["Potential revenue at risk", "إيرادات محتملة معرضة للخطر"],
  k_critical_deadlines: ["Critical deadlines (30 days)", "مواعيد حرجة (30 يومًا)"], k_evidence_completeness: ["Evidence completeness", "اكتمال الأدلة"],
  k_claim_conversion_rate: ["Claim conversion rate", "معدل نجاح المطالبات"],
  overdue: ["overdue", "متأخر"], unquantified: ["unquantified", "غير مقدرة"], count: ["items", "بند"],
  ch_exposure: ["Financial exposure by project", "التعرض المالي حسب المشروع"], ch_by_type: ["Potential entitlements by category", "المستحقات المحتملة حسب الفئة"],
  ch_pipeline: ["Claims pipeline", "مسار المطالبات"], ch_sub_vs_app: ["Submitted vs approved vs collected", "المقدّم مقابل المعتمد مقابل المحصّل"],
  ch_trend: ["Monthly trend", "الاتجاه الشهري"], ch_heatmap: ["Project risk heatmap", "خريطة مخاطر المشروعات"],
  ch_deadlines: ["Upcoming contractual deadlines", "المواعيد التعاقدية القادمة"], ch_aging: ["Claims aging (since submission)", "أعمار المطالبات (منذ التقديم)"],
  ch_top: ["Top projects by potential recovery", "أعلى المشروعات من حيث الاسترداد المحتمل"],
  potential: ["Potential", "محتمل"], at_risk: ["At risk", "معرض للخطر"], submitted: ["Submitted", "مقدّم"], approved: ["Approved", "معتمد"],
  collected: ["Collected", "محصّل"], detected: ["Detected", "مرصود"], drilldown: ["Drill-down", "التفاصيل"],
  disclaimer: ["Potential entitlements are not substantiated claims. Amounts are not guaranteed recoveries.",
    "المستحقات المحتملة ليست مطالبات مُثبتة، والمبالغ ليست مضمونة التحصيل."],
  // projects
  portfolio: ["Project portfolio", "محفظة المشروعات"], new_project: ["New project", "مشروع جديد"], code: ["Code", "الكود"],
  name: ["Name", "الاسم"], name_ar: ["Name (Arabic)", "الاسم بالعربية"], employer: ["Employer", "صاحب العمل"],
  contractor: ["Contractor", "المقاول"], engineer: ["Engineer", "المهندس"], contract_value: ["Contract value", "قيمة العقد"],
  location: ["Location", "الموقع"], start_date: ["Start date", "تاريخ البدء"], completion: ["Completion date", "تاريخ الانتهاء"],
  contract_form: ["Contract form", "نوع العقد"],
  documents: ["Documents", "المستندات"], clause: ["Clause", "البند"], clauses: ["Clauses", "البنود"], events: ["Events", "الأحداث"],
  entitlements: ["Entitlements", "المستحقات"], claims: ["Claims", "المطالبات"], deadlines: ["Deadlines", "المواعيد"],
  overview: ["Overview", "نظرة عامة"], team: ["Team", "فريق العمل"],
  journey: ["Revenue protection journey", "رحلة حماية الإيرادات"],
  j1: ["Upload contract", "رفع العقد"], j2: ["Add project documents", "إضافة مستندات المشروع"], j3: ["Analyse", "التحليل"],
  j4: ["Discover entitlements", "اكتشاف المستحقات"], j5: ["Review evidence", "مراجعة الأدلة"], j6: ["Prepare claim", "إعداد المطالبة"],
  // documents
  upload: ["Upload documents", "رفع مستندات"], drop_here: ["Drop files here or click to choose (PDF, scanned images, Word, Excel, e-mail)",
    "اسحب الملفات هنا أو اضغط للاختيار (PDF، صور ممسوحة، Word، Excel، بريد)"],
  doc_type: ["Document type", "نوع المستند"], auto_detect: ["Auto-detect", "تحديد تلقائي"], author: ["Author party", "الطرف المُصدِر"],
  doc_date: ["Document date", "تاريخ المستند"], processing: ["Processing", "قيد المعالجة"], processed: ["Processed", "تمت المعالجة"],
  failed: ["Failed", "فشل"], uploaded: ["Queued", "في الانتظار"], ocr: ["OCR", "تعرف ضوئي"], version: ["Version", "الإصدار"],
  security_flag: ["Possible instruction-injection text detected — treated as data only", "تم رصد نص قد يحاول توجيه الذكاء الاصطناعي — يُعامل كبيانات فقط"],
  page_estimated: ["page numbers estimated (no fixed pagination)", "أرقام الصفحات تقديرية (لا ترقيم ثابت)"],
  reprocess: ["Re-analyse", "إعادة التحليل"], extracted_text: ["Extracted text", "النص المستخرج"], extracted_clauses: ["Extracted clauses", "البنود المستخرجة"],
  classification: ["Classification", "التصنيف"],
  // clauses
  clause_explorer: ["Contract clause explorer", "مستكشف بنود العقد"], category: ["Category", "الفئة"],
  time_limits: ["Time limits", "المهل الزمنية"], obligations: ["Obligations", "الالتزامات"], rights: ["Rights / entitlements", "الحقوق / الاستحقاقات"],
  conditions: ["Conditions", "الشروط"], exclusions: ["Exclusions / limitations", "الاستثناءات / القيود"], risk_flags: ["Risk flags", "مؤشرات المخاطر"],
  time_bar: ["time-bar", "سقوط حق"], verified: ["Verified", "تم التحقق"], unverified: ["Unverified", "غير مُتحقق"],
  rejected: ["Rejected", "مرفوض"], corrected: ["Corrected", "مُصحح"], mark_verified: ["Mark verified", "اعتماد البند"],
  mark_rejected: ["Reject extraction", "رفض الاستخراج"], ask_contract: ["Ask the contract", "اسأل العقد"],
  ask_placeholder: ["e.g. What is the notice period for claims?", "مثال: ما مهلة الإخطار بالمطالبات؟"],
  ask_extractive: ["No AI model is enabled — showing the most relevant clauses (extractive answer).", "لا يوجد نموذج ذكاء اصطناعي مفعّل — يتم عرض البنود الأكثر صلة."],
  with_time_limits: ["Only clauses with time limits", "البنود ذات المهل فقط"],
  // events
  event_register: ["Project event register", "سجل أحداث المشروع"], new_event: ["Record event", "تسجيل حدث"],
  event_date: ["Event date", "تاريخ الحدث"], awareness_date: ["Date contractor became aware", "تاريخ علم المقاول"],
  responsible: ["Responsible party", "الطرف المسؤول"], est_cost: ["Estimated cost impact (EGP)", "الأثر المالي المقدر (ج.م)"],
  est_time: ["Estimated time impact (days)", "الأثر الزمني المقدر (يوم)"], ai_suggest: ["AI suggestion", "اقتراح آلي"],
  linked_docs: ["Linked evidence", "الأدلة المرتبطة"], link: ["Link", "ربط"], unlink: ["Unlink", "فك الربط"],
  suggested_docs: ["Suggested related documents", "مستندات مقترحة ذات صلة"], related_clauses: ["Related contract clauses", "بنود العقد ذات الصلة"],
  run_discovery: ["Discover entitlements", "اكتشاف المستحقات"], run_all: ["Analyse all events", "تحليل جميع الأحداث"],
  // entitlements
  discovery: ["AI entitlement discovery", "الاكتشاف الذكي للمستحقات"], why: ["Why did HAQQ identify this potential entitlement?", "لماذا رصد حقّك هذا الاستحقاق المحتمل؟"],
  applicable_clause: ["Applicable contractual clause", "البند التعاقدي المنطبق"], evidence_available: ["Evidence available", "الأدلة المتوفرة"],
  evidence_missing: ["Missing evidence", "الأدلة الناقصة"], critical: ["critical", "جوهري"], financial_impact: ["Potential financial impact", "الأثر المالي المحتمل"],
  time_impact: ["Potential time impact", "الأثر الزمني المحتمل"], notice_req: ["Notice requirement & deadline", "متطلب الإخطار والموعد"],
  due: ["Due", "الاستحقاق"], certainty: ["Certainty", "درجة اليقين"], recommended: ["Recommended next actions", "الإجراءات الموصى بها"],
  assumptions: ["Assumptions & uncertainties", "الافتراضات وعدم اليقين"], facts: ["Facts (from documents)", "وقائع (من المستندات)"],
  contradictions: ["Possible contradictions", "تعارضات محتملة"], review: ["Human review", "المراجعة البشرية"],
  review_comment: ["Review comment", "ملاحظة المراجعة"], accept: ["Accept as potential", "قبول كاستحقاق محتمل"],
  reject: ["Reject / not applicable", "رفض / غير منطبق"], needs_info: ["Needs more information", "يحتاج معلومات إضافية"],
  substantiate: ["Mark substantiated", "اعتماد كمطالبة مُثبتة"], create_claim: ["Prepare claim", "إعداد مطالبة"],
  open_valuation: ["Valuation worksheet", "ورقة التقييم"], narrative: ["AI narrative (cited)", "سرد آلي موثّق"],
  generate_narrative: ["Generate AI narrative", "إنشاء سرد آلي"], basis: ["Basis", "الأساس"], score: ["Match score", "درجة المطابقة"],
  confidence_breakdown: ["How confidence is computed", "طريقة حساب درجة الثقة"],
  conf_clause_match: ["Clause match", "مطابقة البند"], conf_evidence_completeness: ["Evidence completeness", "اكتمال الأدلة"],
  conf_event_classification: ["Event classification", "تصنيف الحدث"], conf_notice_clarity: ["Notice clarity", "وضوح الإخطار"],
  conf_quantification: ["Quantification", "التقدير المالي"], conf_exclusion_penalty: ["Exclusion penalty", "خصم الاستثناء"],
  conf_contradiction_penalty: ["Contradiction penalty", "خصم التعارض"],
  calc: ["Calculation", "طريقة الحساب"],
  // valuation
  valuation: ["Claim valuation workspace", "مساحة تقييم المطالبة"], add_line: ["Add line", "إضافة بند"], from_boq: ["Add from BOQ", "إضافة من المقايسة"],
  qty: ["Qty", "الكمية"], unit: ["Unit", "الوحدة"], rate: ["Rate", "الفئة"], source: ["Source", "المصدر"],
  overhead: ["Overheads %", "مصروفات عمومية %"], profit: ["Profit %", "ربح %"], vat: ["Apply VAT", "تطبيق ضريبة القيمة المضافة"],
  save_calc: ["Calculate & save", "احسب واحفظ"], verify_val: ["Verify valuation", "اعتماد التقييم"], draft: ["Draft", "مسودة"],
  // claims
  claim_mgmt: ["Claims management", "إدارة المطالبات"], stage: ["Stage", "المرحلة"], claimed: ["Claimed", "المطالب به"],
  move_to: ["Move to", "نقل إلى"], history: ["Stage history", "سجل المراحل"], generate: ["Generate document", "إنشاء مستند"],
  generated_docs: ["Generated documents (drafts — never sent automatically)", "المستندات المُنشأة (مسودات — لا تُرسل آليًا)"],
  kind_notice: ["Notice letter", "خطاب إخطار"], kind_package: ["Full claim package", "ملف المطالبة الكامل"], kind_worksheet: ["Valuation worksheet", "ورقة التقييم"],
  approved_amount: ["Approved amount", "المبلغ المعتمد"], collected_amount: ["Collected amount", "المبلغ المحصّل"],
  comment: ["Comment", "ملاحظة"], not_allowed: ["Your role cannot perform this step", "دورك لا يسمح بهذه الخطوة"],
  // deadlines
  calendar: ["Deadline calendar", "تقويم المواعيد التعاقدية"], undetermined: ["Undetermined — verify manually", "غير محدد — يجب التحقق يدويًا"],
  complete: ["Mark complete", "تم الإنجاز"], scan_now: ["Run deadline scan & alerts", "فحص المواعيد وإرسال التنبيهات"],
  days_left: ["days left", "يوم متبقٍ"], notifications: ["Notifications", "الإشعارات"], mark_all_read: ["Mark all read", "تعليم الكل كمقروء"],
  // reports
  reports: ["Reports & exports", "التقارير والتصدير"], portfolio_xlsx: ["Portfolio report (Excel)", "تقرير المحفظة (Excel)"],
  // admin
  users: ["Users", "المستخدمون"], role: ["Role", "الدور"], add_user: ["Add user", "إضافة مستخدم"], active: ["Active", "نشط"],
  weekend: ["Weekend days", "أيام العطلة الأسبوعية"], holidays: ["Public holidays (one ISO date per line)", "العطلات الرسمية (تاريخ في كل سطر)"],
  vat_rate: ["VAT rate %", "نسبة ضريبة القيمة المضافة %"], ai_policy: ["Allow external AI model processing of document excerpts", "السماح بمعالجة مقتطفات المستندات بنماذج ذكاء اصطناعي خارجية"],
  ai_policy_help: ["When off, HAQQ uses only its deterministic engines; no document text leaves your environment.", "عند الإيقاف يستخدم حقّك محركاته الحتمية فقط ولا يغادر أي نص من بيئتك."],
  retention: ["Data retention (days)", "مدة الاحتفاظ بالبيانات (يوم)"], audit: ["Audit trail", "سجل التدقيق"], verify_chain: ["Verify integrity", "التحقق من السلامة"],
  security: ["Security", "الأمان"], enable_mfa: ["Enable two-factor authentication", "تفعيل المصادقة الثنائية"],
  usage: ["Usage this month", "الاستخدام هذا الشهر"], limits: ["Plan limits", "حدود الباقة"], billing: ["Billing records", "سجلات الفوترة"],
};

type Ctx = { lang: Lang; dir: "rtl" | "ltr"; setLang: (l: Lang) => void; t: (k: string, vars?: Record<string, string | number>) => string;
  pick: (o: { en?: string; ar?: string } | undefined | null) => string };
const I18n = createContext<Ctx>(null as unknown as Ctx);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    try { return (localStorage.getItem("haqq.lang") as Lang) || "ar"; } catch { return "ar"; }
  });
  const dir = lang === "ar" ? "rtl" : "ltr";
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = dir;
    document.body.classList.toggle("font-ar", lang === "ar");
  }, [lang, dir]);
  const setLang = (l: Lang) => { setLangState(l); try { localStorage.setItem("haqq.lang", l); } catch { /* ignore */ } };
  const t = (k: string, vars?: Record<string, string | number>) => {
    let s = D[k] ? D[k][lang === "ar" ? 1 : 0] : k;
    if (vars) for (const [a, b] of Object.entries(vars)) s = s.replace(`{${a}}`, String(b));
    return s;
  };
  const pick = (o: { en?: string; ar?: string } | undefined | null) => (o ? (lang === "ar" ? o.ar || o.en : o.en || o.ar) || "" : "");
  return <I18n.Provider value={{ lang, dir, setLang, t, pick }}>{children}</I18n.Provider>;
}

export const useI18n = () => useContext(I18n);

const loc = (l: Lang) => (l === "ar" ? "ar-EG" : "en-GB");

export function fmtMoney(v: string | number | null | undefined, lang: Lang, opts: { compact?: boolean; currency?: string } = {}) {
  if (v === null || v === undefined || v === "") return "—";
  const n = typeof v === "string" ? Number(v) : v;
  return new Intl.NumberFormat(loc(lang), { style: "currency", currency: opts.currency || "EGP",
    notation: opts.compact ? "compact" : "standard", maximumFractionDigits: opts.compact ? 1 : 0 }).format(n);
}
export const fmtNum = (v: number | string | null | undefined, lang: Lang, digits = 0) =>
  v === null || v === undefined ? "—" : new Intl.NumberFormat(loc(lang), { maximumFractionDigits: digits }).format(Number(v));
export const fmtPct = (v: number | null | undefined, lang: Lang) =>
  v === null || v === undefined ? "—" : new Intl.NumberFormat(loc(lang), { style: "percent", maximumFractionDigits: 0 }).format(v);
export function fmtDate(v: string | null | undefined, lang: Lang) {
  if (!v) return "—";
  const d = new Date(v.length === 10 ? v + "T00:00:00" : v);
  return new Intl.DateTimeFormat(loc(lang), { day: "numeric", month: "short", year: "numeric" }).format(d);
}
