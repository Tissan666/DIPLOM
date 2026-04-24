import { Suspense, lazy, useDeferredValue, useRef, useState } from "react";
import { ControlPanel } from "./components/ControlPanel";
import { HeroSection } from "./components/HeroSection";
import { PipelineStepper } from "./components/PipelineStepper";
import { ResultsPanel } from "./components/ResultsPanel";
import { useAnalysis } from "./hooks/useAnalysis";
import { useLocale } from "./i18n";
import { buildAnalysisPayload } from "./lib/analysisPayload";
import { defaultFormValues, getDemoResult } from "./lib/mockData";
import type { AnalysisFormValues } from "./types/analysis";

const LazyDetectorGrid = lazy(async () => ({
  default: (await import("./components/DetectorGrid")).DetectorGrid,
}));

const LazyExplainabilityPanel = lazy(async () => ({
  default: (await import("./components/ExplainabilityPanel")).ExplainabilityPanel,
}));

const LazySuspiciousReviewsTable = lazy(async () => ({
  default: (await import("./components/SuspiciousReviewsTable")).SuspiciousReviewsTable,
}));

export function App() {
  const { locale } = useLocale();
  const [formValues, setFormValues] = useState<AnalysisFormValues>(defaultFormValues);
  const workspaceRef = useRef<HTMLDivElement | null>(null);
  const { status, result, error, errorCode, progress, pipelineStages, runAnalysis, retry } = useAnalysis();
  const deferredResult = useDeferredValue(status === "success" ? result : null);
  const shouldRenderDeferredSections = Boolean(deferredResult);

  const updateField = <K extends keyof AnalysisFormValues>(field: K, value: AnalysisFormValues[K]) => {
    setFormValues((current) => ({
      ...current,
      [field]: value,
    }));
  };

  const scrollToWorkspace = () => {
    workspaceRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const handleAnalyze = async () => {
    scrollToWorkspace();
    await runAnalysis(buildAnalysisPayload(formValues), formValues.sourceMode);
  };

  const handleDemo = async () => {
    scrollToWorkspace();
    await runAnalysis(buildAnalysisPayload(formValues), formValues.sourceMode, true);
  };

  const preview = result || getDemoResult("url", locale);

  return (
    <div className="dashboard-shell">
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute left-[-10%] top-0 h-[360px] w-[360px] rounded-full bg-accent/10 blur-3xl" />
        <div className="absolute right-[-5%] top-[10%] h-[300px] w-[300px] rounded-full bg-slate-300/35 blur-3xl" />
        <div className="absolute bottom-[-8%] left-[18%] h-[280px] w-[280px] rounded-full bg-emerald-100 blur-3xl" />
      </div>

      <HeroSection preview={preview} onPrimaryAction={scrollToWorkspace} onSecondaryAction={handleDemo} />

      <main className="section-wrap pb-4" ref={workspaceRef}>
        <section className="space-y-5">
          <ControlPanel values={formValues} status={status} onChange={updateField} onSubmit={handleAnalyze} onLoadDemo={handleDemo} />
          <ResultsPanel
            status={status}
            result={result}
            error={error}
            errorCode={errorCode}
            progress={progress}
            pipelineStages={pipelineStages}
            onRetry={retry}
          />
        </section>
      </main>

      <PipelineStepper stages={pipelineStages} status={status} />

      {shouldRenderDeferredSections && (
        <Suspense fallback={<DeferredSectionFallback />}>
          <LazyDetectorGrid detectors={deferredResult?.detectorCards || []} status={status} />
          <LazyExplainabilityPanel factors={deferredResult?.explainability || []} status={status} />
          <LazySuspiciousReviewsTable reviews={deferredResult?.suspiciousReviews || []} status={status} />
        </Suspense>
      )}
    </div>
  );
}

function DeferredSectionFallback() {
  return (
    <section className="section-wrap space-y-5 pb-8">
      <div className="surface-card-soft h-56 animate-pulse bg-white/70" />
      <div className="surface-card-soft h-56 animate-pulse bg-white/70" />
      <div className="surface-card-soft h-72 animate-pulse bg-white/70" />
    </section>
  );
}
