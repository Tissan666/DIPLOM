import type { AnalysisFormValues } from "../types/analysis";

export function depthWaitMs(depth: AnalysisFormValues["analysisDepth"]): number {
  if (depth === "fast") {
    return 2500;
  }
  if (depth === "deep") {
    return 12000;
  }
  return 6000;
}

export function depthScrollRounds(depth: AnalysisFormValues["analysisDepth"]): number {
  if (depth === "fast") {
    return 1;
  }
  if (depth === "deep") {
    return 48;
  }
  return 16;
}

export function buildAnalysisPayload(values: AnalysisFormValues): Record<string, unknown> {
  if (values.sourceMode === "url") {
    return {
      url: values.url.trim(),
      analysis_depth: values.analysisDepth,
      wait_ms: values.waitMs.trim() ? Number(values.waitMs.trim()) : depthWaitMs(values.analysisDepth),
      scroll_rounds: depthScrollRounds(values.analysisDepth),
      scroll_delay_ms: values.analysisDepth === "deep" ? 1200 : 900,
    };
  }

  if (values.sourceMode === "html") {
    return {
      html: values.html.trim(),
      source_url: values.sourceUrl.trim() || "inline-html",
    };
  }

  let parsedRecords: unknown = [];
  try {
    parsedRecords = JSON.parse(values.recordsJson || "[]");
  } catch {
    parsedRecords = [];
  }

  return {
    records: Array.isArray(parsedRecords) ? parsedRecords : (parsedRecords as { records?: unknown[] }).records || [],
  };
}
