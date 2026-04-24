import { motion } from "framer-motion";
import { LoaderCircle } from "lucide-react";
import { useLocale } from "../i18n";
import type { PipelineStage } from "../types/analysis";

type LoadingStateProps = {
  progress: number;
  stages: PipelineStage[];
};

export function LoadingState({ progress, stages }: LoadingStateProps) {
  const { copy } = useLocale();

  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="surface-card-soft p-6"
    >
      <div className="flex items-center gap-3">
        <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-accent-soft text-accent">
          <LoaderCircle className="h-6 w-6 animate-spin" />
        </span>
        <div>
          <p className="text-sm font-semibold text-ink">{copy.loadingState.title}</p>
          <p className="mt-1 text-sm text-muted">{copy.loadingState.description}</p>
        </div>
      </div>

      <div className="mt-6 overflow-hidden rounded-full bg-slate-200/70">
        <motion.div
          className="h-3 rounded-full bg-gradient-to-r from-accent to-emerald-400"
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.5 }}
        />
      </div>

      <div className="mt-2 flex items-center justify-between text-xs uppercase tracking-[0.22em] text-muted">
        <span>{copy.common.progress}</span>
        <span>{progress}%</span>
      </div>

      <div className="mt-6 grid gap-3 md:grid-cols-5">
        {stages.map((stage) => (
          <div
            key={stage.key}
            className={`rounded-2xl border p-4 ${
              stage.state === "active"
                ? "border-accent/30 bg-accent-soft"
                : stage.state === "complete"
                  ? "border-emerald-200 bg-emerald-50"
                  : stage.state === "error"
                    ? "border-danger/20 bg-danger/10"
                    : "border-slate-200/80 bg-white/80"
            }`}
          >
            <p className="text-sm font-semibold text-ink">{stage.label}</p>
            <p className="mt-1 text-xs leading-6 text-muted">{stage.description}</p>
          </div>
        ))}
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-3">
        {[1, 2, 3].map((item) => (
          <div key={item} className="rounded-3xl border border-slate-200/80 bg-white/80 p-5">
            <div className="h-4 w-28 animate-pulse rounded-full bg-slate-200" />
            <div className="mt-5 h-24 animate-pulse rounded-2xl bg-slate-100" />
          </div>
        ))}
      </div>
    </motion.div>
  );
}
