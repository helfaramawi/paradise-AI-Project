import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { Check, PlusCircle, Rocket, Wand2 } from "lucide-react";
import { api } from "@/lib/api";
import { useActiveDecision, useI18n } from "@/lib/app";
import { ControlsForm, DEFAULT_CONTROLS, pickControls, type Controls } from "@/components/Controls";
import { Badge, Button, Card, ErrorBox, Input, PageHeader, Select, Textarea, cn } from "@/components/ui";

export default function IntakeWizard() {
  const { t, lang, pick, egp, setDomain } = useI18n();
  const nav = useNavigate();
  const qc = useQueryClient();
  const { setActive } = useActiveDecision();
  const [step, setStep] = useState(0);
  const [question, setQuestion] = useState("");
  const [title, setTitle] = useState("");
  const [controls, setControls] = useState<Controls>(DEFAULT_CONTROLS);
  const [parsed, setParsed] = useState<any>(null);
  const [datasetVersion, setDatasetVersion] = useState<string>("");
  const demo = useQuery({ queryKey: ["demoq"], queryFn: () => api("/decisions/demo-question") });
  const datasets = useQuery({ queryKey: ["datasets"], queryFn: () => api<any[]>("/datasets") });
  const parse = useMutation({
    mutationFn: () => api("/decisions/parse", { method: "POST", json: { question } }),
    onSuccess: (r: any) => {
      setParsed(r);
      setControls(pickControls(r.suggested_controls));
      const collections = r.suggested_controls.domain === "collections";
      setDomain(collections ? "collections" : "opex");
      if (!title) {
        setTitle(collections
          ? lang === "ar" ? "زيادة المتحصلات عبر شركة تحصيل" : "Higher collections through a collection agency"
          : lang === "ar" ? "خفض التكاليف التشغيلية دون إنهاء خدمة" : "Operating cost reduction without terminations");
      }
      setStep(1);
    },
  });
  const create = useMutation({
    mutationFn: () => api("/decisions", {
      method: "POST",
      json: { title, question, language: lang, controls, auto_run: true, dataset_version_id: datasetVersion || undefined },
    }),
    onSuccess: (d: any) => {
      setActive(d.id);
      qc.invalidateQueries({ queryKey: ["decisions"] });
      nav(`/execution/${d.run_id}`);
    },
  });
  const steps = [t("in.step1"), t("in.step2"), t("in.step3"), t("in.step4")];
  const versions = datasets.data?.flatMap((d) => d.versions.map((v: any) => ({ ...v, dsName: d.name }))) || [];
  const dv = versions.find((v: any) => v.id === datasetVersion) || versions[0];
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader icon={PlusCircle} title={t("in.title")} />
      <ol className="mb-6 grid grid-cols-4 gap-2">
        {steps.map((s, i) => (
          <li key={s} className={cn("rounded-xl border px-3 py-2 text-xs transition",
            i === step ? "border-accent bg-accent/10 text-ink" : i < step ? "border-good/40 text-good" : "border-line text-muted")}>
            <span className="me-1 font-semibold">{i < step ? <Check className="inline h-3 w-3" /> : i + 1}</span> {s}
          </li>
        ))}
      </ol>
      <AnimatePresence mode="wait">
        <motion.div key={step} initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }}>
          {step === 0 && (
            <Card title={t("in.question")}>
              <Textarea rows={6} value={question} onChange={(e) => setQuestion(e.target.value)} data-testid="question-input"
                placeholder={pick(demo.data?.question_en, demo.data?.question_ar)} />
              <div className="mt-4 flex flex-wrap justify-between gap-2">
                <Button variant="outline" icon={Wand2} data-testid="use-demo"
                  onClick={() => setQuestion(pick(demo.data?.question_en, demo.data?.question_ar))}>{t("in.useDemo")}</Button>
                <Button onClick={() => parse.mutate()} loading={parse.isPending} disabled={question.length < 10} data-testid="parse-btn">
                  {t("in.parse")}
                </Button>
              </div>
              <ErrorBox error={parse.error} />
            </Card>
          )}
          {step === 1 && parsed && (
            <Card title={t("in.step2")} subtitle={t("in.parsed")}>
              {!parsed.supported && <ErrorBox error={new Error(t("in.unsupported"))} />}
              <div className="flex flex-wrap gap-2">
                {parsed.parsed.detected.map((d: string) => <Badge key={d} tone="accent" icon={Check}>{d.replace(/_/g, " ")}</Badge>)}
              </div>
              <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
                {[["lab.domain", parsed.parsed.domain ? t(`dom.${parsed.parsed.domain}` as any) : "—"],
                  ["in.target", parsed.parsed.cost_reduction_target_pct != null ? `${parsed.parsed.cost_reduction_target_pct}%` : "—"],
                  ["in.duration", parsed.parsed.implementation_months != null ? `${parsed.parsed.implementation_months} ${t("months")}` : "—"],
                  parsed.parsed.domain === "collections"
                    ? ["lever.agency_placement", parsed.parsed.mentions_agency ? "✓" : "—"]
                    : ["cc.kpi.opex", parsed.parsed.annual_opex != null ? egp(parsed.parsed.annual_opex, 0) : "—"],
                  ["in.noTerm", parsed.parsed.no_terminations ? "✓" : "—"]].map(([k, v]) => (
                  <div key={k} className="rounded-xl border border-line p-3">
                    <dt className="text-xs text-muted">{t(k as any)}</dt>
                    <dd className="mt-1 font-semibold">{v}</dd>
                  </div>
                ))}
              </dl>
              <label className="mt-5 block text-xs text-ink2">{t("in.titleField")}
                <Input className="mt-1" value={title} onChange={(e) => setTitle(e.target.value)} />
              </label>
              <div className="mt-5 flex justify-between">
                <Button variant="ghost" onClick={() => setStep(0)}>{t("back")}</Button>
                <Button onClick={() => setStep(2)} disabled={!parsed.supported || title.length < 3} data-testid="next-2">{t("next")}</Button>
              </div>
            </Card>
          )}
          {step === 2 && (
            <Card title={t("in.step3")}>
              <ControlsForm value={controls} onChange={setControls} />
              <div className="mt-6 flex justify-between">
                <Button variant="ghost" onClick={() => setStep(1)}>{t("back")}</Button>
                <Button onClick={() => setStep(3)} data-testid="next-3">{t("next")}</Button>
              </div>
            </Card>
          )}
          {step === 3 && (
            <Card title={t("in.step4")}>
              <label className="block text-xs text-ink2">{t("in.dataset")}
                <Select className="mt-1 w-full" value={datasetVersion} onChange={(e) => setDatasetVersion(e.target.value)}>
                  {versions.map((v: any) => <option key={v.id} value={v.id}>{v.dsName} · v{v.version} · {v.note}</option>)}
                </Select>
              </label>
              {dv && (
                <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
                  <Badge tone="warn">{t("chip.synthetic")}</Badge>
                  <Badge tone={dv.validation.has_errors ? "critical" : "good"}>
                    {t("dc.quality")}: {Math.round(dv.validation.quality_score * 100)}%
                  </Badge>
                  {dv.validation.checks.filter((c: any) => c.severity === "error").map((c: any) => (
                    <span key={c.code} className="text-critical dark:text-red-300">{c.code}: {pick(c.title_en, c.title_ar)}</span>
                  ))}
                </div>
              )}
              <ErrorBox error={create.error} />
              <div className="mt-6 flex justify-between">
                <Button variant="ghost" onClick={() => setStep(2)}>{t("back")}</Button>
                <Button size="lg" icon={Rocket} loading={create.isPending} onClick={() => create.mutate()} data-testid="launch-btn">{t("in.launch")}</Button>
              </div>
            </Card>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
