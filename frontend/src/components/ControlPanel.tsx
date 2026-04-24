import { lazy, Suspense } from "react";
import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { ChevronDown, Globe, Layers3, Sparkles, WandSparkles } from "lucide-react";
import { useLocale } from "../i18n";
import type { AnalysisDepth, AnalysisFormValues, AppStatus, SourceMode } from "../types/analysis";

const LazyDataImportPanel = lazy(async () => ({
  default: (await import("./data-import/DataImportPanel")).DataImportPanel,
}));

type ControlPanelProps = {
  values: AnalysisFormValues;
  status: AppStatus;
  onChange: <K extends keyof AnalysisFormValues>(field: K, value: AnalysisFormValues[K]) => void;
  onSubmit: () => void;
  onLoadDemo: () => void;
};

export function ControlPanel({ values, status, onChange, onSubmit, onLoadDemo }: ControlPanelProps) {
  const { copy } = useLocale();
  const isBusy = status === "loading";
  const sourceModes: Array<{ value: SourceMode; label: string; icon: typeof Globe; helper: string }> = [
    { value: "url", label: "URL", icon: Globe, helper: copy.controlPanel.sourceModes.url.helper },
    { value: "html", label: "HTML", icon: Layers3, helper: copy.controlPanel.sourceModes.html.helper },
    {
      value: "records",
      label: copy.controlPanel.sourceModes.records.label,
      icon: Sparkles,
      helper: copy.controlPanel.sourceModes.records.helper,
    },
  ];
  const depthModes: Array<{ value: AnalysisDepth; label: string; helper: string }> = [
    {
      value: "fast",
      label: copy.controlPanel.depthModes.fast.label,
      helper: copy.controlPanel.depthModes.fast.helper,
    },
    {
      value: "standard",
      label: copy.controlPanel.depthModes.standard.label,
      helper: copy.controlPanel.depthModes.standard.helper,
    },
    {
      value: "deep",
      label: copy.controlPanel.depthModes.deep.label,
      helper: copy.controlPanel.depthModes.deep.helper,
    },
  ];

  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.08 }}
      className="surface-card p-6 sm:p-7"
    >
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <p className="eyebrow">{copy.controlPanel.eyebrow}</p>
          <h2 className="mt-3 break-words font-display text-3xl text-ink">{copy.controlPanel.title}</h2>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-muted">{copy.controlPanel.description}</p>
        </div>
        <span className="badge-soft self-start border-accent/20 bg-accent-soft text-accent">
          {isBusy ? copy.common.running : copy.common.ready}
        </span>
      </div>

      <div className="mt-6 grid gap-5 xl:grid-cols-12">
        <SectionCard
          title={copy.controlPanel.sourceSectionTitle}
          helper={copy.controlPanel.sourceSectionHelper}
          className="xl:col-span-8"
        >
          <div className="grid gap-3 lg:grid-cols-3">
            {sourceModes.map((mode) => {
              const Icon = mode.icon;
              const active = values.sourceMode === mode.value;
              return (
                <button
                  key={mode.value}
                  type="button"
                  onClick={() => onChange("sourceMode", mode.value)}
                  className={`rounded-2xl border px-4 py-3 text-left transition ${
                    active
                      ? "border-accent/30 bg-accent-soft shadow-float"
                      : "border-slate-200/80 bg-white/80 hover:border-accent/20 hover:bg-white"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <span className={`mt-0.5 rounded-xl p-2 ${active ? "bg-white text-accent" : "bg-slate-100 text-ink"}`}>
                      <Icon className="h-4 w-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="break-words text-sm font-semibold text-ink">{mode.label}</p>
                      <p className="mt-1 text-xs leading-6 text-muted">{mode.helper}</p>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          {values.sourceMode === "url" && (
            <Field
              label={copy.controlPanel.fields.productPageUrl}
              helper={copy.controlPanel.fields.productPageUrlHelper}
            >
              <input
                value={values.url}
                onChange={(event) => onChange("url", event.target.value)}
                className={inputClass}
                placeholder={copy.controlPanel.placeholders.productUrl}
              />
            </Field>
          )}

          {values.sourceMode === "html" && (
            <>
              <Field
                label={copy.controlPanel.fields.sourceLabel}
                helper={copy.controlPanel.fields.sourceLabelHelper}
                className="lg:max-w-xl"
              >
                <input
                  value={values.sourceUrl}
                  onChange={(event) => onChange("sourceUrl", event.target.value)}
                  className={inputClass}
                  placeholder={copy.controlPanel.placeholders.sourceLabel}
                />
              </Field>
              <Field
                label={copy.controlPanel.fields.htmlSource}
                helper={copy.controlPanel.fields.htmlSourceHelper}
              >
                <textarea
                  value={values.html}
                  onChange={(event) => onChange("html", event.target.value)}
                  className={`${inputClass} min-h-[190px] resize-y`}
                  placeholder={copy.controlPanel.placeholders.html}
                />
              </Field>
            </>
          )}

          {values.sourceMode === "records" && (
            <Suspense fallback={<DataImportFallback />}>
              <LazyDataImportPanel
                recordsJson={values.recordsJson}
                recordsFileName={values.recordsFileName}
                disabled={isBusy}
                onRecordsChange={(value) => onChange("recordsJson", value)}
                onFileNameChange={(value) => onChange("recordsFileName", value)}
                onRunAnalysis={onSubmit}
              />
            </Suspense>
          )}
        </SectionCard>

        <SectionCard
          title={copy.controlPanel.fields.analysisModeTitle}
          helper={copy.controlPanel.fields.analysisModeHelper}
          className="xl:col-span-4"
        >
          <div className="grid gap-3 2xl:grid-cols-3">
            {depthModes.map((mode) => {
              const active = values.analysisDepth === mode.value;
              return (
                <button
                  key={mode.value}
                  type="button"
                  onClick={() => onChange("analysisDepth", mode.value)}
                  className={`rounded-2xl border px-4 py-3 text-left transition ${
                    active
                      ? "border-accent/30 bg-accent-soft shadow-float"
                      : "border-slate-200/80 bg-white/80 hover:border-accent/20 hover:bg-white"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <WandSparkles className="h-4 w-4 text-accent" />
                    <span className="break-words text-sm font-semibold text-ink">{mode.label}</span>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-muted">{mode.helper}</p>
                </button>
              );
            })}
          </div>
        </SectionCard>

        <details className="surface-card-soft group overflow-hidden p-5 xl:col-span-6">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-4">
            <div className="min-w-0">
              <p className="break-words text-sm font-semibold text-ink">{copy.controlPanel.fields.advancedTitle}</p>
              <p className="mt-1 text-xs leading-6 text-muted">
                {copy.controlPanel.fields.advancedHelper}
              </p>
            </div>
            <ChevronDown className="h-4 w-4 text-muted transition group-open:rotate-180" />
          </summary>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Field
              label={copy.controlPanel.fields.manualWait}
              helper={copy.controlPanel.fields.manualWaitHelper}
            >
              <input
                type="number"
                min={0}
                max={30000}
                step={500}
                inputMode="numeric"
                value={values.waitMs}
                onChange={(event) => onChange("waitMs", event.target.value)}
                className={inputClass}
                placeholder={copy.controlPanel.placeholders.waitMs}
              />
            </Field>
            <Field
              label={copy.controlPanel.fields.snapshotHelper}
              helper={copy.controlPanel.fields.snapshotHelperText}
            >
              <input
                value={values.sourceUrl}
                onChange={(event) => onChange("sourceUrl", event.target.value)}
                className={inputClass}
                placeholder={copy.controlPanel.placeholders.snapshotHelper}
              />
            </Field>
          </div>
        </details>

        <section className="surface-card-soft p-5 xl:col-span-6">
          <div className="mb-4">
            <p className="text-sm font-semibold text-ink">{copy.controlPanel.title}</p>
            <p className="mt-1 text-xs leading-6 text-muted">{copy.controlPanel.description}</p>
          </div>
          <div className="flex flex-col gap-3 lg:flex-row">
            <button
              type="button"
              onClick={onSubmit}
              disabled={isBusy}
              className="inline-flex flex-1 items-center justify-center gap-2 rounded-full bg-ink px-6 py-4 text-sm font-semibold text-white shadow-premium transition hover:-translate-y-0.5 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isBusy ? copy.controlPanel.actions.analyzing : copy.controlPanel.actions.analyze}
            </button>
            <button
              type="button"
              onClick={onLoadDemo}
              disabled={isBusy}
              className="inline-flex items-center justify-center gap-2 rounded-full border border-slate-200 bg-white/80 px-5 py-4 text-sm font-semibold text-ink transition hover:-translate-y-0.5 hover:border-accent/20 hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {copy.controlPanel.actions.demo}
            </button>
          </div>
        </section>
      </div>
    </motion.section>
  );
}

function SectionCard({
  title,
  helper,
  children,
  className = "",
}: {
  title: string;
  helper: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`surface-card-soft min-w-0 p-5 ${className}`}>
      <div className="mb-4">
        <p className="break-words text-sm font-semibold text-ink">{title}</p>
        <p className="mt-1 text-xs leading-6 text-muted">{helper}</p>
      </div>
      <div className="space-y-4">{children}</div>
    </section>
  );
}

function Field({
  label,
  helper,
  children,
  className = "",
}: {
  label: string;
  helper: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={`block min-w-0 ${className}`}>
      <span className="break-words text-sm font-semibold text-ink">{label}</span>
      <p className="mt-1 text-xs leading-6 text-muted">{helper}</p>
      <div className="mt-2">{children}</div>
    </label>
  );
}

const inputClass =
  "w-full rounded-2xl border border-slate-200/80 bg-white/90 px-4 py-3 text-sm text-ink outline-none transition placeholder:text-slate-400 focus:border-accent/40 focus:ring-4 focus:ring-accent/10";

function DataImportFallback() {
  return (
    <div className="rounded-[24px] border border-slate-200/80 bg-white/80 p-5">
      <div className="h-5 w-40 rounded-full bg-slate-200/80" />
      <div className="mt-4 h-4 w-full rounded-full bg-slate-200/60" />
      <div className="mt-2 h-4 w-5/6 rounded-full bg-slate-200/60" />
      <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-5">
        {Array.from({ length: 5 }).map((_, index) => (
          <div key={index} className="h-11 rounded-2xl bg-slate-100/90" />
        ))}
      </div>
      <div className="mt-5 h-44 rounded-[24px] border border-dashed border-slate-200/80 bg-slate-50/80" />
    </div>
  );
}
