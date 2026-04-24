import { startTransition, useEffect, useReducer, useRef } from "react";
import { useLocale } from "../i18n";
import { AnalysisApiError, submitAnalysis } from "../lib/api";
import { PIPELINE_STAGE_COUNT, getBasePipelineStages, getDemoResult } from "../lib/mockData";
import { transformApiResponse } from "../lib/transformers";
import type {
  AnalysisErrorCode,
  AppStatus,
  DashboardResult,
  PipelineStage,
  ReviewApiResponse,
  SourceMode,
} from "../types/analysis";

type StoredRun = {
  payload: Record<string, unknown>;
  sourceMode: SourceMode;
  demo?: boolean;
};

type ResultPayload =
  | { kind: "demo"; sourceMode: SourceMode }
  | { kind: "api"; response: ReviewApiResponse; sourceMode: SourceMode };

type AnalysisState = {
  error: string | null;
  errorCode: AnalysisErrorCode | null;
  failedStageIndex: number | null;
  lastRun: StoredRun | null;
  progress: number;
  resultPayload: ResultPayload | null;
  stageIndex: number;
  status: AppStatus;
};

type AnalysisAction =
  | { type: "start"; run: StoredRun }
  | { type: "advance"; stageIndex: number; progress: number }
  | { type: "success"; resultPayload: ResultPayload }
  | { type: "failure"; error: string; errorCode: AnalysisErrorCode; failedStageIndex: number };

const initialState: AnalysisState = {
  error: null,
  errorCode: null,
  failedStageIndex: null,
  lastRun: null,
  progress: 0,
  resultPayload: null,
  stageIndex: 0,
  status: "idle",
};

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function analysisReducer(state: AnalysisState, action: AnalysisAction): AnalysisState {
  switch (action.type) {
    case "start":
      return {
        ...state,
        error: null,
        errorCode: null,
        failedStageIndex: null,
        lastRun: action.run,
        progress: 6,
        resultPayload: null,
        stageIndex: 0,
        status: "loading",
      };
    case "advance":
      return {
        ...state,
        progress: action.progress,
        stageIndex: action.stageIndex,
      };
    case "success":
      return {
        ...state,
        error: null,
        errorCode: null,
        failedStageIndex: null,
        progress: 100,
        resultPayload: action.resultPayload,
        status: "success",
      };
    case "failure":
      return {
        ...state,
        error: action.error,
        errorCode: action.errorCode,
        failedStageIndex: action.failedStageIndex,
        progress: 0,
        resultPayload: null,
        status: "error",
      };
    default:
      return state;
  }
}

function buildPipelineStages(state: AnalysisState, locale: "en" | "ru"): PipelineStage[] {
  const basePipelineStages = getBasePipelineStages(locale);

  if (state.status === "success") {
    return basePipelineStages.map((stage) => ({ ...stage, state: "complete" }));
  }

  return basePipelineStages.map((stage, index) => {
    if (state.status === "error" && state.failedStageIndex === index) {
      return { ...stage, state: "error" };
    }
    if (state.status === "error" && state.failedStageIndex !== null && index < state.failedStageIndex) {
      return { ...stage, state: "complete" };
    }
    if (state.status === "loading" && index < state.stageIndex) {
      return { ...stage, state: "complete" };
    }
    if (state.status === "loading" && index === state.stageIndex) {
      return { ...stage, state: "active" };
    }
    return { ...stage, state: "pending" };
  });
}

export function useAnalysis() {
  const { locale } = useLocale();
  const [state, dispatch] = useReducer(analysisReducer, initialState);
  const intervalRef = useRef<number | null>(null);
  const stageIndexRef = useRef(0);

  const clearTicker = () => {
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  useEffect(() => {
    return () => {
      clearTicker();
    };
  }, []);

  const runAnalysis = async (payload: Record<string, unknown>, sourceMode: SourceMode, demo = false) => {
    clearTicker();
    stageIndexRef.current = 0;
    dispatch({ type: "start", run: { payload, sourceMode, demo } });

    intervalRef.current = window.setInterval(() => {
      stageIndexRef.current = Math.min(stageIndexRef.current + 1, PIPELINE_STAGE_COUNT - 1);
      dispatch({
        type: "advance",
        progress: Math.min(6 + stageIndexRef.current * 17, 86),
        stageIndex: stageIndexRef.current,
      });
    }, 900);

    try {
      const resultPayload = demo
        ? (await sleep(2400), { kind: "demo", sourceMode } satisfies ResultPayload)
        : ({
            kind: "api",
            response: (await submitAnalysis(payload)) as ReviewApiResponse,
            sourceMode,
          } satisfies ResultPayload);

      clearTicker();
      await sleep(250);
      startTransition(() => {
        dispatch({ type: "success", resultPayload });
      });
    } catch (caughtError) {
      clearTicker();
      const errorCode: AnalysisErrorCode = caughtError instanceof AnalysisApiError ? caughtError.code : "UNKNOWN_ERROR";
      dispatch({
        type: "failure",
        error: caughtError instanceof Error ? caughtError.message : "Unexpected analysis error.",
        errorCode,
        failedStageIndex: stageIndexRef.current,
      });
    }
  };

  const retry = async () => {
    if (!state.lastRun) {
      return;
    }

    await runAnalysis(state.lastRun.payload, state.lastRun.sourceMode, Boolean(state.lastRun.demo));
  };

  const result: DashboardResult | null =
    state.resultPayload?.kind === "demo"
      ? getDemoResult(state.resultPayload.sourceMode, locale)
      : state.resultPayload?.kind === "api"
        ? transformApiResponse(state.resultPayload.response, state.resultPayload.sourceMode, locale)
        : null;

  return {
    status: state.status,
    result,
    error: state.error,
    errorCode: state.errorCode,
    progress: state.progress,
    pipelineStages: buildPipelineStages(state, locale),
    runAnalysis,
    retry,
  };
}
