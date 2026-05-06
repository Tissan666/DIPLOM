import { lazy, Suspense } from "react";
import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { Globe, Layers3, Sparkles, WandSparkles } from "lucide-react";
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
      className="surface-card p-6 sm:p-8"
    >
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <p className="eyebrow">{copy.controlPanel.eyebrow}</p>
          <h2 className="mt-3 break-words font-display text-3xl font-bold text-ink sm:text-4xl">{copy.controlPanel.title}</h2>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-muted">{copy.controlPanel.description}</p>
        </div>
        <span className="badge-soft self-start border-accent/20 bg-accent-soft text-accent">
          {isBusy ? copy.common.running : copy.common.ready}
        </span>
      </div>

      <div className="mt-7 grid gap-5 xl:grid-cols-12">
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
                  className={`rounded-[22px] border px-4 py-4 text-left shadow-soft transition duration-300 hover:-translate-y-0.5 ${
                    active
                      ? "border-accent/30 bg-accent-soft shadow-float ring-4 ring-accent/10"
                      : "border-slate-200/80 bg-white/82 hover:border-accent/20 hover:bg-white hover:shadow-float"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <span className={`mt-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${active ? "bg-white text-accent shadow-sm" : "bg-slate-100 text-ink"}`}>
                      <Icon className="h-6 w-6" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="break-words text-sm font-bold text-ink">{mode.label}</p>
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
          <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1 2xl:grid-cols-3">
            {depthModes.map((mode) => {
              const active = values.analysisDepth === mode.value;
              return (
                <button
                  key={mode.value}
                  type="button"
                  onClick={() => onChange("analysisDepth", mode.value)}
                  className={`rounded-[22px] border px-4 py-4 text-left shadow-soft transition duration-300 hover:-translate-y-0.5 ${
                    active
                      ? "border-accent/30 bg-accent-soft shadow-float ring-4 ring-accent/10"
                      : "border-slate-200/80 bg-white/82 hover:border-accent/20 hover:bg-white hover:shadow-float"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="flex h-9 w-9 items-center justify-center rounded-2xl bg-warning/10 text-warning">
                      <WandSparkles className="h-5 w-5" />
                    </span>
                    <span className="break-words text-sm font-bold text-ink">{mode.label}</span>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-muted">{mode.helper}</p>
                </button>
              );
            })}
          </div>
        </SectionCard>

        <section className="surface-card-soft bg-gradient-to-r from-white/86 via-accent-soft/40 to-white/78 p-5 xl:col-span-12">
          <div className="mb-4">
            <p className="text-sm font-bold text-ink">{copy.controlPanel.submitTitle}</p>
            <p className="mt-1 text-xs leading-6 text-muted">{copy.controlPanel.submitDescription}</p>
          </div>
          <div className="flex flex-col gap-3 lg:flex-row">
            <button
              type="button"
              onClick={onSubmit}
              disabled={isBusy}
              className="primary-button flex-1 justify-center px-6 py-4 shadow-premium"
            >
              {isBusy ? copy.controlPanel.actions.analyzing : copy.controlPanel.actions.analyze}
            </button>
            <button
              type="button"
              onClick={onLoadDemo}
              disabled={isBusy}
              className="secondary-button justify-center px-5 py-4"
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
    <section className={`surface-card-soft min-w-0 p-5 sm:p-6 ${className}`}>
      <div className="mb-4">
        <p className="break-words text-sm font-bold text-ink">{title}</p>
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
