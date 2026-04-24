export type SourceMode = "url" | "html" | "records";
export type AnalysisDepth = "fast" | "standard" | "deep";
export type AppStatus = "idle" | "loading" | "success" | "error";
export type PipelineStageState = "pending" | "active" | "complete" | "error";
export type DetectorSeverity = "low" | "medium" | "high";
export type DetectorStatus = "stable" | "watch" | "critical";
export type ReviewTriageStatus = "confident_suspicious" | "confident_clean" | "needs_manual_review";
export type AnalysisErrorCode =
  | "ANALYSIS_FAILED"
  | "INPUT_SOURCE_MISSING"
  | "INVALID_INPUT"
  | "INVALID_RESPONSE"
  | "INVALID_URL"
  | "INVALID_SCRAPING_WAIT"
  | "NETWORK_ERROR"
  | "RATING_ARTIFACTS_MISSING"
  | "REQUEST_BODY_INVALID"
  | "REVIEW_ARTIFACTS_MISSING"
  | "SCRAPINGBEE_NOT_CONFIGURED"
  | "SCRAPING_FETCH_FAILED"
  | "SCRAPING_TIMEOUT"
  | "UNKNOWN_ERROR";

export interface AnalysisFormValues {
  sourceMode: SourceMode;
  url: string;
  html: string;
  recordsJson: string;
  recordsFileName: string;
  sourceUrl: string;
  analysisDepth: AnalysisDepth;
  waitMs: string;
}

export interface PipelineStage {
  key: string;
  label: string;
  description: string;
  state: PipelineStageState;
}

export interface DonutSlice {
  name: string;
  value: number;
  fill: string;
}

export interface ActivityPoint {
  label: string;
  reviews: number;
  suspicious: number;
}

export interface AnomalyTypePoint {
  type: string;
  count: number;
}

export interface DetectorCardData {
  id: string;
  name: string;
  description: string;
  severity: DetectorSeverity;
  score: number;
  status: DetectorStatus;
}

export interface ExplainabilityFactor {
  label: string;
  weight: number;
  narrative: string;
}

export interface SuspiciousReviewRow {
  id: string;
  title: string;
  text: string;
  rating: number;
  suspiciousness: number;
  reason: string;
  author: string;
  authorTrust: "trusted" | "neutral" | "low";
  date: string;
  severity: DetectorSeverity;
  triageStatus: ReviewTriageStatus;
  languageProfile: "neutral" | "organic" | "mixed" | "suspicious";
  detectedTerms: string[];
  languageSignalScore: number;
  languageAuthenticityScore: number;
  languageDomain: string;
  templateClustered: boolean;
  uncertaintyScore: number;
  oodScore: number;
  imageUrls: string[];
  imageCount: number;
  duplicateImageCount: number;
  duplicateImageClusterSize: number;
  duplicateImageScore: number;
  duplicateImageFlag: boolean;
  imageTemporalClusterScore?: number;
  imageTemporalClusterFlag?: boolean;
  imageTemporalClusterSize?: number;
  imageTemporalClusterAuthorCount?: number;
  imageTemporalClusterWindowHours?: number;
  imageTextAlignmentScore?: number;
  imageTextMismatchScore?: number;
  imageTextMismatchFlag?: boolean;
  imageTextAlignmentLabel?: string;
  imageStockMarketingScore?: number;
  imageStockMarketingFlag?: boolean;
  imageStockMarketingLabel?: string;
  imageSyntheticScore?: number;
  imageSyntheticFlag?: boolean;
  imageSyntheticLabel?: string;
  imageOcrScore?: number;
  imageOcrFlag?: boolean;
  imageOcrText?: string;
  imageOcrLabels?: string[];
}

export interface DashboardOverview {
  productName: string;
  sourceLabel: string;
  statusLabel: string;
  riskScore: number;
  manipulationProbability: number;
  confidence: number;
  reviewCount: number;
  suspiciousCount: number;
  manualReviewCount: number;
  verdict: string;
}

export interface DashboardResult {
  sourceMode: SourceMode;
  overview: DashboardOverview;
  trustBreakdown: DonutSlice[];
  activitySeries: ActivityPoint[];
  anomalyTypes: AnomalyTypePoint[];
  detectorCards: DetectorCardData[];
  explainability: ExplainabilityFactor[];
  suspiciousReviews: SuspiciousReviewRow[];
  keyInsights: string[];
}

export interface ReviewApiResponse {
  request?: Record<string, unknown>;
  summary?: Record<string, unknown>;
  highlights?: Record<string, unknown>;
  reviews?: Array<Record<string, unknown>>;
  predictions?: Array<Record<string, unknown>>;
  suspicious_users?: Array<Record<string, unknown>>;
}

export interface ApiErrorResponse {
  error?: string;
  error_code?: AnalysisErrorCode;
  message?: string;
}
