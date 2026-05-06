import { motion } from "framer-motion";
import { BarChart3, Brain, FileText, Globe, ShieldAlert } from "lucide-react";
import { useLocale } from "../i18n";
import type { AppStatus, PipelineStage } from "../types/analysis";

type PipelineStepperProps = {
  stages: PipelineStage[];
  status: AppStatus;
};

const stepIcons = [Globe, FileText, BarChart3, Brain, ShieldAlert];

export function PipelineStepper({ stages, status }: PipelineStepperProps) {
  const { copy } = useLocale();

  return (
    <section className="section-wrap py-6">
      <div className="surface-card p-6 sm:p-8">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="eyebrow">{copy.pipeline.eyebrow}</p>
            <h2 className="mt-3 font-display text-3xl font-bold text-ink sm:text-4xl">{copy.pipeline.title}</h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-muted">{copy.pipeline.description}</p>
          </div>
          <span className="badge-soft">
            {status === "loading" ? copy.pipeline.active : status === "success" ? copy.pipeline.complete : copy.pipeline.waiting}
          </span>
        </div>

        <div className="mt-8 grid gap-4 lg:grid-cols-5">
          {stages.map((stage, index) => {
            const Icon = stepIcons[index] || Globe;
            const stateClass =
              stage.state === "complete"
                ? "border-emerald-200 bg-emerald-50"
                : stage.state === "active"
                  ? "border-accent/30 bg-accent-soft"
                  : stage.state === "error"
                    ? "border-danger/20 bg-danger/10"
                    : "border-slate-200/80 bg-white/80";

            return (
              <motion.article
                key={stage.key}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.25 }}
                transition={{ duration: 0.35, delay: index * 0.05 }}
                className={`rounded-[26px] border p-5 shadow-soft transition duration-300 hover:-translate-y-1 hover:shadow-lift ${stateClass}`}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="icon-shell border-slate-200 bg-white/90 text-ink">
                    <Icon className="h-6 w-6" />
                  </span>
                  <span className="text-xs font-semibold uppercase tracking-[0.22em] text-muted">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                </div>
                <h3 className="mt-4 text-base font-semibold text-ink">{stage.label}</h3>
                <p className="mt-2 text-sm leading-7 text-muted">{stage.description}</p>
              </motion.article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
