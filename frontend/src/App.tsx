import { Suspense, lazy, useDeferredValue, useRef, useState } from "react";
import { BusinessValueSection } from "./components/BusinessValueSection";
import { ControlPanel } from "./components/ControlPanel";
import { HeroSection } from "./components/HeroSection";
import { HistoryPanel } from "./components/HistoryPanel";
import { PipelineStepper } from "./components/PipelineStepper";
import { ResultsPanel } from "./components/ResultsPanel";
import { useAnalysis } from "./hooks/useAnalysis";
import { buildAnalysisPayload } from "./lib/analysisPayload";
import { defaultFormValues } from "./lib/mockData";
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

  const handleUseHtmlSnapshot = () => {
    setFormValues((current) => ({
      ...current,
      html: current.html,
      sourceMode: "html",
      sourceUrl: current.sourceUrl || current.url || "manual-html-snapshot",
    }));
    scrollToWorkspace();
  };

  const handleFastRetry = async () => {
    const fastValues: AnalysisFormValues = {
      ...formValues,
      analysisDepth: "fast",
      waitMs: "",
    };
    setFormValues(fastValues);
    scrollToWorkspace();
    await runAnalysis(buildAnalysisPayload(fastValues), fastValues.sourceMode);
  };

  return (
    <div className="dashboard-shell">
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute inset-x-0 top-0 h-[560px] bg-[radial-gradient(ellipse_at_top,rgba(15,118,110,0.12),transparent_62%)]" />
        <div className="absolute inset-0 bg-[linear-gradient(135deg,rgba(255,255,255,0.56),transparent_46%)]" />
      </div>

      <HeroSection onPrimaryAction={scrollToWorkspace} onSecondaryAction={handleDemo} />
      <BusinessValueSection />

      <main className="section-wrap pb-6" ref={workspaceRef}>
        <section className="space-y-6">
          <ControlPanel values={formValues} status={status} onChange={updateField} onSubmit={handleAnalyze} onLoadDemo={handleDemo} />
          <ResultsPanel
            status={status}
            result={result}
            error={error}
            errorCode={errorCode}
            progress={progress}
            pipelineStages={pipelineStages}
            onRetry={retry}
            onSetup={scrollToWorkspace}
            onLoadDemo={handleDemo}
            onUseFastRetry={handleFastRetry}
            onUseHtmlSnapshot={handleUseHtmlSnapshot}
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

      <HistoryPanel status={status} />
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
