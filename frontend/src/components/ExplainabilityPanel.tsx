import { motion } from "framer-motion";
import { Info, ScanSearch } from "lucide-react";
import { useLocale } from "../i18n";
import type { AppStatus, ExplainabilityFactor } from "../types/analysis";

type ExplainabilityPanelProps = {
  factors: ExplainabilityFactor[];
  status: AppStatus;
};

export function ExplainabilityPanel({ factors, status }: ExplainabilityPanelProps) {
  const { copy } = useLocale();
  const showPlaceholder = status !== "success" || factors.length === 0;

  return (
    <section className="section-wrap py-5">
      <div className="surface-card p-6 sm:p-7">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="eyebrow">{copy.explainability.eyebrow}</p>
            <h2 className="mt-3 font-display text-3xl text-ink">{copy.explainability.title}</h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-muted">{copy.explainability.description}</p>
          </div>
          <span className="badge-soft">
            {status === "success" ? copy.explainability.liveWeights : copy.common.explainabilityPreview}
          </span>
        </div>

        {showPlaceholder ? (
          <div className="mt-8 grid gap-4 xl:grid-cols-[0.82fr_1.18fr]">
            {Array.from({ length: 2 }).map((_, cardIndex) => (
              <div key={cardIndex} className="surface-card-soft p-5">
                <div className="h-5 w-40 animate-pulse rounded-full bg-slate-200" />
                <div className="mt-5 space-y-4">
                  {Array.from({ length: 4 }).map((__, rowIndex) => (
                    <div key={rowIndex}>
                      <div className="h-4 w-48 animate-pulse rounded-full bg-slate-200" />
                      <div className="mt-3 h-2.5 animate-pulse rounded-full bg-slate-200" />
                      <div className="mt-3 h-10 animate-pulse rounded-2xl bg-slate-100" />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="mt-8 grid gap-4 xl:grid-cols-[0.82fr_1.18fr]">
            <div className="surface-card-soft p-5">
              <div className="flex items-center gap-3">
                <span className="rounded-2xl bg-accent-soft p-2.5 text-accent">
                  <ScanSearch className="h-5 w-5" />
                </span>
                <div>
                  <p className="text-sm font-semibold text-ink">{copy.explainability.decisionNarrative}</p>
                  <p className="mt-1 text-sm leading-7 text-muted">{copy.explainability.decisionNarrativeDescription}</p>
                </div>
              </div>

              <div className="mt-6 space-y-3">
                {factors.slice(0, 3).map((factor) => (
                  <div key={factor.label} className="rounded-2xl border border-slate-200/80 bg-white/80 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-ink">{factor.label}</p>
                      <span className="text-sm font-semibold text-accent">{Math.round(factor.weight * 100)}%</span>
                    </div>
                    <p className="mt-2 text-sm leading-7 text-muted">{factor.narrative}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="surface-card-soft p-5">
              <div className="flex items-center gap-3">
                <span className="rounded-2xl bg-white/90 p-2.5 text-ink shadow-sm">
                  <Info className="h-5 w-5" />
                </span>
                <div>
                  <p className="text-sm font-semibold text-ink">{copy.explainability.topFactors}</p>
                  <p className="mt-1 text-sm leading-7 text-muted">{copy.explainability.topFactorsDescription}</p>
                </div>
              </div>

              <div className="mt-6 space-y-4">
                {factors.map((factor, index) => (
                  <motion.div
                    key={factor.label}
                    initial={{ opacity: 0, x: -14 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true, amount: 0.2 }}
                    transition={{ duration: 0.28, delay: index * 0.04 }}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-ink">{factor.label}</p>
                      <span className="text-sm font-semibold text-muted">{Math.round(factor.weight * 100)}%</span>
                    </div>
                    <div className="mt-2 h-2.5 rounded-full bg-slate-200/80">
                      <div
                        className="h-2.5 rounded-full bg-gradient-to-r from-accent to-emerald-400"
                        style={{ width: `${Math.max(10, factor.weight * 100)}%` }}
                      />
                    </div>
                    <p className="mt-2 text-sm leading-7 text-muted">{factor.narrative}</p>
                  </motion.div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
