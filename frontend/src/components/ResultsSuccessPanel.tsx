import { motion } from "framer-motion";
import { BarChart3, ShieldAlert, ShieldCheck, Sparkles, Target } from "lucide-react";
import {
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useLocale } from "../i18n";
import type { DashboardResult } from "../types/analysis";

type ResultsSuccessPanelProps = {
  result: DashboardResult;
};

export function ResultsSuccessPanel({ result }: ResultsSuccessPanelProps) {
  const { copy } = useLocale();

  return (
    <div className="space-y-6">
      <motion.div layout className="surface-card-soft p-6 sm:p-7">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <p className="text-sm font-semibold uppercase tracking-[0.28em] text-muted">{copy.resultsSuccess.riskProfile}</p>
            <h3 className="mt-3 max-w-5xl break-words font-display text-4xl leading-[0.98] text-ink lg:text-[3.3rem]">
              {result.overview.productName}
            </h3>
          </div>
          <span className="badge-soft self-start border-danger/20 bg-danger/10 text-danger">
            {result.overview.statusLabel}
          </span>
        </div>
        <p className="mt-5 max-w-4xl break-words text-sm leading-7 text-muted sm:text-[15px]">{result.overview.verdict}</p>

        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
          <MetricTile icon={ShieldAlert} label={copy.resultsSuccess.riskScore} value={String(result.overview.riskScore)} accent="danger" />
          <MetricTile
            icon={Target}
            label={copy.resultsSuccess.manipulationProbability}
            value={`${result.overview.manipulationProbability}%`}
            accent="warning"
          />
          <MetricTile icon={Sparkles} label={copy.resultsSuccess.confidence} value={`${result.overview.confidence}%`} accent="success" />
          <MetricTile icon={BarChart3} label={copy.resultsSuccess.collectedReviews} value={String(result.overview.reviewCount)} accent="neutral" />
          <MetricTile icon={ShieldCheck} label={copy.resultsSuccess.flaggedReviews} value={String(result.overview.suspiciousCount)} accent="danger" />
          <MetricTile
            icon={ShieldAlert}
            label={copy.resultsSuccess.manualReview}
            value={String(result.overview.manualReviewCount)}
            accent={result.overview.manualReviewCount > 0 ? "warning" : "neutral"}
          />
        </div>
      </motion.div>

      <motion.div layout className="surface-card-soft p-6">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.28em] text-muted">{copy.resultsSuccess.explainabilityEyebrow}</p>
            <h4 className="mt-3 break-words text-2xl font-semibold text-ink">{copy.resultsSuccess.explainabilityTitle}</h4>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-muted">{copy.resultsSuccess.explainabilityDescription}</p>
          </div>
          <span className="badge-soft">{copy.resultsSuccess.decisionDigest}</span>
        </div>

        <div className="mt-6 grid gap-3 lg:grid-cols-3">
          {result.keyInsights.map((insight) => (
            <div key={insight} className="rounded-2xl border border-slate-200/70 bg-white/85 px-4 py-4 text-sm leading-7 text-muted">
              {insight}
            </div>
          ))}
        </div>
      </motion.div>

      <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
        <motion.div layout className="chart-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-muted">{copy.resultsSuccess.trustSplitEyebrow}</p>
              <h4 className="mt-1 text-xl font-semibold text-ink">{copy.resultsSuccess.trustSplitTitle}</h4>
            </div>
            <span className="badge-soft">{result.overview.sourceLabel}</span>
          </div>
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={result.trustBreakdown}
                  dataKey="value"
                  innerRadius={72}
                  outerRadius={100}
                  paddingAngle={4}
                  stroke="none"
                >
                  {result.trustBreakdown.map((entry) => (
                    <Cell key={entry.name} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend verticalAlign="bottom" />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        <motion.div layout className="chart-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-muted">{copy.resultsSuccess.temporalEyebrow}</p>
              <h4 className="mt-1 text-xl font-semibold text-ink">{copy.resultsSuccess.temporalTitle}</h4>
            </div>
            <span className="badge-soft">{copy.resultsSuccess.timeAware}</span>
          </div>
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={result.activitySeries}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="label" stroke="#61758a" />
                <YAxis stroke="#61758a" />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="reviews"
                  name={copy.resultsSuccess.reviewSeries}
                  stroke="#0f766e"
                  strokeWidth={3}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="suspicious"
                  name={copy.resultsSuccess.suspiciousSeries}
                  stroke="#c35e43"
                  strokeWidth={3}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </motion.div>
      </div>

      <motion.div layout className="chart-card">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-muted">{copy.resultsSuccess.anomalyEyebrow}</p>
            <h4 className="mt-1 text-xl font-semibold text-ink">{copy.resultsSuccess.anomalyTitle}</h4>
          </div>
          <span className="badge-soft">{result.anomalyTypes.length} {copy.common.signalGroups}</span>
        </div>
        <AnomalySignalProfile items={result.anomalyTypes} countLabel={copy.resultsSuccess.countSeries} />
      </motion.div>
    </div>
  );
}

function AnomalySignalProfile({
  items,
  countLabel,
}: {
  items: DashboardResult["anomalyTypes"];
  countLabel: string;
}) {
  const maxCount = Math.max(...items.map((item) => item.count), 1);

  return (
    <div className="mt-5 space-y-3">
      {items.map((item, index) => {
        const width = Math.max(8, Math.round((item.count / maxCount) * 100));
        return (
          <div
            key={item.type}
            className="rounded-[22px] border border-slate-200/70 bg-white/82 p-4 shadow-[0_14px_30px_rgba(15,23,42,0.05)]"
          >
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <p className="min-w-0 text-sm font-semibold leading-6 text-ink">{item.type}</p>
              <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-bold ${anomalyCountClass(index)}`}>
                {countLabel}: {item.count}
              </span>
            </div>
            <div className="mt-3 h-3 overflow-hidden rounded-full bg-slate-200/75">
              <div
                className={`h-full rounded-full ${anomalyBarClass(index)}`}
                style={{ width: `${width}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function MetricTile({
  icon: Icon,
  label,
  value,
  accent,
}: {
  icon: typeof ShieldAlert;
  label: string;
  value: string;
  accent: "danger" | "warning" | "success" | "neutral";
}) {
  const accentClass =
    accent === "danger"
      ? "bg-danger/10 text-danger"
      : accent === "warning"
        ? "bg-warning/10 text-warning"
        : accent === "success"
          ? "bg-accent-soft text-accent"
          : "bg-slate-100 text-ink";

  return (
    <div className="flex h-full min-h-[136px] flex-col rounded-3xl border border-slate-200/80 bg-white/90 p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <span className={`shrink-0 rounded-2xl p-2.5 ${accentClass}`}>
          <Icon className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] leading-4 text-muted">{label}</p>
        </div>
      </div>
      <div className="mt-auto pt-5">
        <p className="mt-2 text-3xl font-semibold leading-none text-ink sm:text-[2rem]">{value}</p>
      </div>
    </div>
  );
}

function anomalyBarClass(index: number) {
  return index % 3 === 0
    ? "bg-accent"
    : index % 3 === 1
      ? "bg-danger"
      : "bg-warning";
}

function anomalyCountClass(index: number) {
  return index % 3 === 0
    ? "bg-accent-soft text-accent"
    : index % 3 === 1
      ? "bg-danger/10 text-danger"
      : "bg-warning/10 text-warning";
}
