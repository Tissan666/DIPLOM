import { lazy, Suspense } from "react";
import { motion } from "framer-motion";
import { BarChart3, ShieldCheck } from "lucide-react";
import { useLocale } from "../i18n";
import type { AnalysisErrorCode, AppStatus, DashboardResult, PipelineStage } from "../types/analysis";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { LoadingState } from "./LoadingState";

const LazyResultsSuccessPanel = lazy(async () => ({
  default: (await import("./ResultsSuccessPanel")).ResultsSuccessPanel,
}));

type ResultsPanelProps = {
  status: AppStatus;
  result: DashboardResult | null;
  error: string | null;
  errorCode: AnalysisErrorCode | null;
  progress: number;
  pipelineStages: PipelineStage[];
  onRetry: () => void;
  onSetup: () => void;
  onLoadDemo: () => void;
  onUseFastRetry: () => void;
  onUseHtmlSnapshot: () => void;
};

export function ResultsPanel({
  status,
  result,
  error,
  errorCode,
  progress,
  pipelineStages,
  onRetry,
  onSetup,
  onLoadDemo,
  onUseFastRetry,
  onUseHtmlSnapshot,
}: ResultsPanelProps) {
  const { copy } = useLocale();
  const showReportBadges = status === "success";

  return (
    <div className="space-y-5">
      <motion.section
        initial={{ opacity: 0, y: 22 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.12 }}
        className="surface-card p-6 sm:p-8"
      >
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0">
            <p className="eyebrow">{copy.resultsPanel.eyebrow}</p>
            <h2 className="mt-3 break-words font-display text-3xl font-bold text-ink sm:text-4xl">{copy.resultsPanel.title}</h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-muted">{copy.resultsPanel.description}</p>
          </div>
          <div className="flex flex-wrap gap-2 xl:max-w-[360px] xl:justify-end">
            {showReportBadges ? (
              <>
                <span className="badge-soft">
                  <ShieldCheck className="mr-2 h-4 w-4 text-accent" />
                  {copy.resultsPanel.trustworthySplit}
                </span>
                <span className="badge-soft">
                  <BarChart3 className="mr-2 h-4 w-4 text-accent" />
                  {copy.resultsPanel.trendCharts}
                </span>
              </>
            ) : (
              <span className="badge-soft">
                <ShieldCheck className="mr-2 h-4 w-4 text-accent" />
                {copy.resultsPanel.waitingBadge}
              </span>
            )}
          </div>
        </div>

        <div className="mt-6">
          {status === "idle" && <EmptyState onSetup={onSetup} onLoadDemo={onLoadDemo} />}
          {status === "loading" && <LoadingState progress={progress} stages={pipelineStages} />}
          {status === "error" && (
            <ErrorState
              errorCode={errorCode}
              message={error || copy.resultsPanel.unexpectedFailure}
              onLoadDemo={onLoadDemo}
              onRetry={onRetry}
              onUseFastRetry={onUseFastRetry}
              onUseHtmlSnapshot={onUseHtmlSnapshot}
            />
          )}
          {status === "success" && result && (
            <Suspense fallback={<SuccessPanelFallback />}>
              <LazyResultsSuccessPanel result={result} />
            </Suspense>
          )}
        </div>
      </motion.section>
    </div>
  );
}

function SuccessPanelFallback() {
  return (
    <div className="space-y-4">
      <div className="surface-card-soft p-6">
        <div className="h-5 w-32 rounded-full bg-slate-200/80" />
        <div className="mt-4 h-12 w-3/4 rounded-3xl bg-slate-200/70" />
        <div className="mt-4 h-5 w-full rounded-full bg-slate-200/60" />
        <div className="mt-2 h-5 w-5/6 rounded-full bg-slate-200/60" />
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <div className="chart-card h-72 animate-pulse bg-slate-100/80" />
        <div className="chart-card h-72 animate-pulse bg-slate-100/80" />
      </div>
    </div>
  );
}
