import type { AnalysisErrorCode, ApiErrorResponse } from "../types/analysis";

export class AnalysisApiError extends Error {
  code: AnalysisErrorCode;
  status?: number;

  constructor(message: string, code: AnalysisErrorCode = "UNKNOWN_ERROR", status?: number) {
    super(message);
    this.name = "AnalysisApiError";
    this.code = code;
    this.status = status;
  }
}

async function readJsonResponse(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export async function submitAnalysis(payload: Record<string, unknown>) {
  let response: Response;
  try {
    response = await fetch("/api/predict", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new AnalysisApiError("Could not reach the analysis backend.", "NETWORK_ERROR");
  }

  const data = await readJsonResponse(response);
  if (!response.ok) {
    const errorData = (data && typeof data === "object" ? data : {}) as ApiErrorResponse;
    throw new AnalysisApiError(
      errorData.message || errorData.error || "Analysis request failed.",
      errorData.error_code || "UNKNOWN_ERROR",
      response.status
    );
  }
  if (!data || typeof data !== "object") {
    throw new AnalysisApiError("Backend returned an invalid response.", "INVALID_RESPONSE", response.status);
  }
  return data;
}
