import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  BarChart3,
  Camera,
  Clock3,
  Copy,
  FileText,
  Fingerprint,
  Flame,
  Gauge,
  Image,
  Languages,
  Maximize2,
  Minimize2,
  Radar,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Star,
  Target,
  Users,
} from "lucide-react";
import {
  Area,
  Brush,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useLocale } from "../i18n";
import type { ActivityPoint, DashboardResult } from "../types/analysis";

type ResultsSuccessPanelProps = {
  result: DashboardResult;
};

export function ResultsSuccessPanel({ result }: ResultsSuccessPanelProps) {
  const { copy, locale } = useLocale();

  return (
    <div className="space-y-6">
      <motion.div layout className="surface-card-soft p-6 sm:p-7">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <p className="text-sm font-semibold uppercase tracking-[0.28em] text-muted">{copy.resultsSuccess.riskProfile}</p>
            <h3 className="mt-3 max-w-5xl break-words font-display text-4xl font-bold leading-[0.98] text-ink lg:text-[3.3rem]">
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
            <div key={insight} className="product-card rounded-[22px] px-4 py-4 text-sm leading-7 text-muted">
              {insight}
            </div>
          ))}
        </div>
      </motion.div>

      <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
        <motion.div layout className="chart-card">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-muted">{copy.resultsSuccess.trustSplitEyebrow}</p>
              <h4 className="mt-1 text-xl font-bold text-ink">{copy.resultsSuccess.trustSplitTitle}</h4>
            </div>
            <span className="badge-soft">{result.overview.sourceLabel}</span>
          </div>
          <TrustBreakdownCard items={result.trustBreakdown} totalReviews={result.overview.reviewCount} />
        </motion.div>

        <ActivityTimelineCard
          series={result.activitySeries}
          locale={locale}
          eyebrow={copy.resultsSuccess.temporalEyebrow}
          title={copy.resultsSuccess.temporalTitle}
          reviewLabel={copy.resultsSuccess.reviewSeries}
          suspiciousLabel={copy.resultsSuccess.suspiciousSeries}
        />
      </div>

      <motion.div layout className="chart-card">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-muted">{copy.resultsSuccess.anomalyEyebrow}</p>
            <h4 className="mt-1 text-xl font-semibold text-ink">{copy.resultsSuccess.anomalyTitle}</h4>
          </div>
          <span className="badge-soft">{result.anomalyTypes.length} {copy.common.signalGroups}</span>
        </div>
        <AnomalySignalProfile items={result.anomalyTypes} countLabel={copy.resultsSuccess.countSeries} locale={locale} />
      </motion.div>
    </div>
  );
}

type ActivityTimelineCardProps = {
  series: ActivityPoint[];
  locale: "en" | "ru";
  eyebrow: string;
  title: string;
  reviewLabel: string;
  suspiciousLabel: string;
};

type TimelineChartPoint = ActivityPoint & {
  suspiciousRate: number;
};

function ActivityTimelineCard({
  series,
  locale,
  eyebrow,
  title,
  reviewLabel,
  suspiciousLabel,
}: ActivityTimelineCardProps) {
  const [expanded, setExpanded] = useState(false);
  const points = useMemo(() => buildTimelineChartPoints(series), [series]);
  const summary = useMemo(() => buildTimelineSummary(points, locale), [points, locale]);
  const rateLabel = locale === "ru" ? "Доля риска" : "Risk share";

  useEffect(() => {
    if (!expanded) {
      return;
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setExpanded(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [expanded]);

  return (
    <>
      <motion.div layout className="chart-card">
        <TimelineHeader
          eyebrow={eyebrow}
          title={title}
          expanded={false}
          locale={locale}
          onToggle={() => setExpanded(true)}
        />
        <TimelineSummary summary={summary} locale={locale} />
        <div className="mt-4 h-80">
          <TimelineChart
            points={points}
            locale={locale}
            reviewLabel={reviewLabel}
            suspiciousLabel={suspiciousLabel}
            rateLabel={rateLabel}
            expanded={false}
          />
        </div>
      </motion.div>

      {expanded && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/95 p-3 backdrop-blur-md sm:p-4">
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={title}
            initial={{ opacity: 0, scale: 0.985 }}
            animate={{ opacity: 1, scale: 1 }}
            className="mx-auto flex min-h-0 w-full max-w-[1500px] flex-col overflow-hidden rounded-[22px] border border-slate-700 bg-slate-950 shadow-2xl"
          >
            <div className="border-b border-slate-800 px-4 py-3 sm:px-5">
              <TimelineHeader
                eyebrow={eyebrow}
                title={title}
                expanded
                locale={locale}
                onToggle={() => setExpanded(false)}
              />
            </div>
            <div className="min-h-0 px-4 pb-4 pt-3 sm:px-5 sm:pb-5">
              <TimelineSummary summary={summary} locale={locale} compact />
              <div className="mt-3 h-[min(68dvh,720px)] min-h-[360px] rounded-[18px] border border-slate-800 bg-slate-950/70 p-2 sm:h-[min(70dvh,760px)] sm:p-3">
                <TimelineChart
                  points={points}
                  locale={locale}
                  reviewLabel={reviewLabel}
                  suspiciousLabel={suspiciousLabel}
                  rateLabel={rateLabel}
                  expanded
                />
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </>
  );
}

function TimelineHeader({
  eyebrow,
  title,
  expanded,
  locale,
  onToggle,
}: {
  eyebrow: string;
  title: string;
  expanded: boolean;
  locale: "en" | "ru";
  onToggle: () => void;
}) {
  const label = expanded
    ? locale === "ru"
      ? "Свернуть график"
      : "Exit fullscreen"
    : locale === "ru"
      ? "На весь экран"
      : "Open fullscreen";
  const Icon = expanded ? Minimize2 : Maximize2;

  return (
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <p className="text-sm font-semibold text-muted">{eyebrow}</p>
        <h4 className={`${expanded ? "text-xl sm:text-2xl" : "text-xl"} mt-1 break-words font-semibold text-ink`}>{title}</h4>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <button
          type="button"
          className="icon-shell h-10 w-10 border-slate-200 bg-slate-100 text-ink transition hover:border-accent/30 hover:bg-accent-soft hover:text-accent"
          aria-label={label}
          title={label}
          onClick={onToggle}
        >
          <Icon className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}

function TimelineSummary({
  summary,
  locale,
  compact = false,
}: {
  summary: TimelineSummaryData;
  locale: "en" | "ru";
  compact?: boolean;
}) {
  if (!summary.hasData) {
    return null;
  }
  const labels =
    locale === "ru"
      ? { period: "Период", total: "Всего", peak: "Пик", risk: "Доля риска", points: "Точек" }
      : { period: "Period", total: "Total", peak: "Peak", risk: "Risk share", points: "Points" };

  return (
    <div className={`${compact ? "mt-0" : "mt-4"} flex flex-wrap gap-2`}>
      <span className="badge-soft">{labels.period}: {summary.periodLabel}</span>
      <span className="badge-soft">{labels.total}: {summary.totalReviews}</span>
      <span className="badge-soft">{labels.peak}: {summary.peakLabel}</span>
      <span className="badge-soft">{labels.risk}: {summary.riskShare}%</span>
      <span className="badge-soft">{labels.points}: {summary.pointCount}</span>
    </div>
  );
}

function TimelineChart({
  points,
  locale,
  reviewLabel,
  suspiciousLabel,
  rateLabel,
  expanded,
}: {
  points: TimelineChartPoint[];
  locale: "en" | "ru";
  reviewLabel: string;
  suspiciousLabel: string;
  rateLabel: string;
  expanded: boolean;
}) {
  if (!points.length) {
    return (
      <div className="flex h-full items-center justify-center rounded-[18px] border border-dashed border-slate-300 text-sm text-muted">
        {locale === "ru" ? "Нет временных данных" : "No timeline data"}
      </div>
    );
  }

  const gradientId = expanded ? "timeline-review-area-expanded" : "timeline-review-area-inline";
  const xInterval = points.length > (expanded ? 18 : 9) ? Math.ceil(points.length / (expanded ? 14 : 6)) : 0;
  const showBrush = points.length > 8;

  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={points} margin={{ top: 12, right: expanded ? 24 : 8, left: 0, bottom: showBrush ? 10 : 0 }}>
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0f766e" stopOpacity={0.42} />
            <stop offset="100%" stopColor="#0f766e" stopOpacity={0.03} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#8fa1b5" opacity={0.7} />
        <XAxis dataKey="label" stroke="#7f92a8" interval={xInterval} minTickGap={expanded ? 12 : 18} tickLine={false} />
        <YAxis yAxisId="count" stroke="#7f92a8" allowDecimals={false} domain={[0, "dataMax"]} tickLine={false} />
        <YAxis
          yAxisId="rate"
          orientation="right"
          stroke="#b7791f"
          width={expanded ? 44 : 34}
          allowDecimals={false}
          domain={[0, 100]}
          tickFormatter={(value) => `${value}%`}
          tickLine={false}
        />
        <Tooltip
          cursor={{ stroke: "#94a3b8", strokeDasharray: "4 4" }}
          content={(props) => (
            <TimelineTooltip
              active={Boolean(props.active)}
              payload={props.payload as Array<{ payload?: TimelineChartPoint }> | undefined}
              label={String(props.label || "")}
              locale={locale}
              reviewLabel={reviewLabel}
              suspiciousLabel={suspiciousLabel}
              rateLabel={rateLabel}
            />
          )}
        />
        <Legend wrapperStyle={{ paddingTop: 8 }} />
        <Area
          yAxisId="count"
          type="monotone"
          dataKey="reviews"
          name={reviewLabel}
          stroke="#0f766e"
          strokeWidth={expanded ? 3 : 2.5}
          fill={`url(#${gradientId})`}
          dot={false}
          activeDot={{ r: 5 }}
          isAnimationActive={points.length <= 80}
        />
        <Line
          yAxisId="count"
          type="monotone"
          dataKey="suspicious"
          name={suspiciousLabel}
          stroke="#c35e43"
          strokeWidth={expanded ? 3 : 2.5}
          dot={false}
          activeDot={{ r: 5 }}
          isAnimationActive={points.length <= 80}
        />
        <Line
          yAxisId="rate"
          type="monotone"
          dataKey="suspiciousRate"
          name={rateLabel}
          stroke="#d97706"
          strokeWidth={expanded ? 2.5 : 2}
          strokeDasharray="6 4"
          dot={false}
          activeDot={{ r: 4 }}
          isAnimationActive={points.length <= 80}
        />
        {showBrush && (
          <Brush
            dataKey="label"
            height={expanded ? 34 : 28}
            stroke="#0f766e"
            fill="#f8fafc"
            travellerWidth={12}
            tickFormatter={(value) => String(value)}
          />
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

function TimelineTooltip({
  active,
  payload,
  label,
  locale,
  reviewLabel,
  suspiciousLabel,
  rateLabel,
}: {
  active: boolean;
  payload?: Array<{ payload?: TimelineChartPoint }>;
  label: string;
  locale: "en" | "ru";
  reviewLabel: string;
  suspiciousLabel: string;
  rateLabel: string;
}) {
  const point = payload?.find((item) => item.payload)?.payload;
  if (!active || !point) {
    return null;
  }
  const rangeLabel = formatTimelinePointRange(point, locale);

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-xl">
      <p className="font-semibold text-ink">{label}</p>
      {rangeLabel && <p className="mt-1 text-xs text-muted">{rangeLabel}</p>}
      <div className="mt-3 space-y-1.5">
        <p className="font-medium text-accent">{reviewLabel}: {point.reviews}</p>
        <p className="font-medium text-danger">{suspiciousLabel}: {point.suspicious}</p>
        <p className="font-medium text-warning">{rateLabel}: {point.suspiciousRate}%</p>
      </div>
    </div>
  );
}

type TimelineSummaryData = {
  hasData: boolean;
  periodLabel: string;
  totalReviews: string;
  peakLabel: string;
  riskShare: number;
  pointCount: number;
};

function buildTimelineChartPoints(series: ActivityPoint[]): TimelineChartPoint[] {
  return series.map((point) => {
    const reviews = Number(point.reviews || 0);
    const suspicious = Number(point.suspicious || 0);
    return {
      ...point,
      reviews,
      suspicious,
      suspiciousRate: reviews > 0 ? Math.round((suspicious / reviews) * 100) : 0,
    };
  });
}

function buildTimelineSummary(points: TimelineChartPoint[], locale: "en" | "ru"): TimelineSummaryData {
  if (!points.length) {
    return {
      hasData: false,
      periodLabel: "",
      totalReviews: "0",
      peakLabel: "0",
      riskShare: 0,
      pointCount: 0,
    };
  }

  const formatter = new Intl.NumberFormat(locale === "ru" ? "ru-RU" : "en-US");
  const totalReviews = points.reduce((sum, point) => sum + point.reviews, 0);
  const totalSuspicious = points.reduce((sum, point) => sum + point.suspicious, 0);
  const peak = points.reduce((best, point) => (point.reviews > best.reviews ? point : best), points[0]);
  return {
    hasData: true,
    periodLabel: formatTimelinePeriod(points, locale),
    totalReviews: formatter.format(totalReviews),
    peakLabel: `${peak.label}: ${formatter.format(peak.reviews)}`,
    riskShare: totalReviews > 0 ? Math.round((totalSuspicious / totalReviews) * 100) : 0,
    pointCount: points.length,
  };
}

function formatTimelinePeriod(points: TimelineChartPoint[], locale: "en" | "ru") {
  const first = points[0];
  const last = points[points.length - 1];
  const firstDate = parseTimelineDate(first.bucketStart);
  const lastDate = parseTimelineDate(last.bucketEnd || last.bucketStart);
  if (!firstDate || !lastDate) {
    return first.label === last.label ? first.label : `${first.label} - ${last.label}`;
  }
  const formatter = new Intl.DateTimeFormat(locale === "ru" ? "ru-RU" : "en-US", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
  return `${formatter.format(firstDate)} - ${formatter.format(lastDate)}`;
}

function formatTimelinePointRange(point: TimelineChartPoint, locale: "en" | "ru") {
  const start = parseTimelineDate(point.bucketStart);
  const end = parseTimelineDate(point.bucketEnd);
  if (!start || !end) {
    return "";
  }
  const sameDay =
    start.getFullYear() === end.getFullYear() && start.getMonth() === end.getMonth() && start.getDate() === end.getDate();
  const formatter = new Intl.DateTimeFormat(locale === "ru" ? "ru-RU" : "en-US", {
    day: "numeric",
    month: "short",
    year: "numeric",
    ...(sameDay ? { hour: "2-digit", minute: "2-digit" } : {}),
  });
  return sameDay ? formatter.format(start) : `${formatter.format(start)} - ${formatter.format(end)}`;
}

function parseTimelineDate(value: string | undefined) {
  if (!value) {
    return null;
  }
  const parsed = new Date(value);
  return Number.isFinite(parsed.getTime()) ? parsed : null;
}

function AnomalySignalProfile({
  items,
  countLabel,
  locale,
}: {
  items: DashboardResult["anomalyTypes"];
  countLabel: string;
  locale: "en" | "ru";
}) {
  const sortedItems = [...items].sort((left, right) => right.count - left.count);
  const maxCount = Math.max(...sortedItems.map((item) => item.count), 1);
  const totalCount = sortedItems.reduce((sum, item) => sum + item.count, 0);
  const topItems = sortedItems.slice(0, 3);
  const dominant = topItems[0];
  const dominantShare = dominant ? Math.round((dominant.count / Math.max(totalCount, 1)) * 100) : 0;
  const signalDensity = Math.round(totalCount / Math.max(sortedItems.length, 1));
  const hotGroups = sortedItems.filter((item) => item.count >= maxCount * 0.55).length;
  const averageIntensity = Math.round(
    (sortedItems.reduce((sum, item) => sum + item.count / maxCount, 0) / Math.max(sortedItems.length, 1)) * 100
  );
  const labels =
    locale === "ru"
      ? {
          total: "Всего сигналов",
          totalHint: "суммарная нагрузка",
          dominant: "Главный драйвер",
          dominantHint: `${dominantShare}% от профиля`,
          density: "Плотность",
          densityHint: "в среднем на группу",
          hot: "Горячие зоны",
          hotHint: "группы выше порога",
          topTitle: "Топ-сигналы",
          mapTitle: "Карта интенсивности",
          share: "Доля",
          intensity: "Интенсивность",
          critical: "Критично",
          high: "Высоко",
          watch: "Наблюдать",
          categories: "категорий",
        }
      : {
          total: "Total signals",
          totalHint: "combined load",
          dominant: "Main driver",
          dominantHint: `${dominantShare}% of profile`,
          density: "Density",
          densityHint: "average per group",
          hot: "Hot zones",
          hotHint: "groups above threshold",
          topTitle: "Top signals",
          mapTitle: "Intensity map",
          share: "Share",
          intensity: "Intensity",
          critical: "Critical",
          high: "High",
          watch: "Watch",
          categories: "categories",
        };
  const numberFormatter = new Intl.NumberFormat(locale === "ru" ? "ru-RU" : "en-US");

  return (
    <div className="mt-5 space-y-5">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <AnomalyKpiTile icon={Radar} label={labels.total} value={numberFormatter.format(totalCount)} hint={labels.totalHint} tone="accent" />
        <AnomalyKpiTile
          icon={Flame}
          label={labels.dominant}
          value={dominant ? dominant.type : "-"}
          hint={labels.dominantHint}
          tone="danger"
          compactValue
        />
        <AnomalyKpiTile icon={Gauge} label={labels.density} value={numberFormatter.format(signalDensity)} hint={labels.densityHint} tone="warning" />
        <AnomalyKpiTile icon={Fingerprint} label={labels.hot} value={String(hotGroups)} hint={labels.hotHint} tone="neutral" />
      </div>

      <AnomalySignalRibbon items={topItems} totalCount={totalCount} labels={labels} numberFormatter={numberFormatter} />

      <div className="grid gap-3 lg:grid-cols-3">
        {topItems.map((item, index) => {
          const share = Math.round((item.count / Math.max(totalCount, 1)) * 100);
          const width = Math.max(8, Math.round((item.count / maxCount) * 100));
          const Icon = anomalyIconForType(item.type);
          return (
            <div key={item.type} className={`rounded-[22px] border p-4 shadow-soft ${anomalyHeroClass(index)}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-start gap-3">
                  <span className={`icon-shell h-11 w-11 ${anomalyCountClass(index)}`}>
                    <Icon className="h-5 w-5" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-[11px] font-black uppercase tracking-[0.16em] text-muted">#{index + 1} {labels.topTitle}</p>
                    <h5 className="mt-2 break-words text-base font-black leading-6 text-ink">{item.type}</h5>
                  </div>
                </div>
                <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-black ${anomalyCountClass(index)}`}>
                  {numberFormatter.format(item.count)}
                </span>
              </div>
              <div className="mt-4 flex items-end justify-between gap-3">
                <div>
                  <p className="text-3xl font-black leading-none text-ink">{share}%</p>
                  <p className="mt-1 text-xs font-semibold text-muted">{labels.share}</p>
                </div>
                <div className="min-w-[120px] flex-1">
                  <div className="h-2.5 overflow-hidden rounded-full bg-slate-200/70">
                    <div className={`h-full rounded-full ${anomalyBarClass(index)}`} style={{ width: `${width}%` }} />
                  </div>
                  <p className="mt-2 text-right text-[11px] font-bold text-muted">{labels.intensity}: {width}%</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-bold text-ink">{labels.mapTitle}</p>
            <p className="mt-1 text-xs leading-5 text-muted">
              {labels.intensity}: {averageIntensity}% · {sortedItems.length} {labels.categories}
            </p>
          </div>
          <span className="badge-soft">{countLabel}: {numberFormatter.format(totalCount)}</span>
        </div>

        <div className="mt-3 grid gap-3">
          {sortedItems.map((item, index) => {
            const width = Math.max(8, Math.round((item.count / maxCount) * 100));
            const share = Math.round((item.count / Math.max(totalCount, 1)) * 100);
            const level = anomalyLevelLabel(width, labels);
            const Icon = anomalyIconForType(item.type);
            return (
              <div
                key={item.type}
                className="rounded-[22px] border border-slate-200/75 bg-white/78 p-4 shadow-soft transition duration-300 hover:-translate-y-0.5 hover:border-accent/25 hover:bg-white/90 hover:shadow-lift"
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex min-w-0 items-start gap-3">
                    <span className={`icon-shell mt-0.5 h-10 w-10 ${anomalyCountClass(index)}`}>
                      <Icon className="h-5 w-5" />
                    </span>
                    <div className="min-w-0">
                      <p className="break-words text-sm font-black leading-6 text-ink">{item.type}</p>
                      <p className="mt-0.5 text-xs font-semibold text-muted">{level} · {labels.share}: {share}%</p>
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className={`rounded-full px-3 py-1 text-xs font-black ${anomalyCountClass(index)}`}>
                      {countLabel}: {numberFormatter.format(item.count)}
                    </span>
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-black text-ink">{width}%</span>
                  </div>
                </div>
                <div className="mt-3 h-3 overflow-hidden rounded-full bg-slate-200/75">
                  <div className={`h-full rounded-full ${anomalyBarClass(index)}`} style={{ width: `${width}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function AnomalyKpiTile({
  icon: Icon,
  label,
  value,
  hint,
  tone,
  compactValue = false,
}: {
  icon: typeof ShieldAlert;
  label: string;
  value: string;
  hint: string;
  tone: "accent" | "danger" | "warning" | "neutral";
  compactValue?: boolean;
}) {
  const toneClass =
    tone === "accent"
      ? "border-accent/20 bg-accent-soft text-accent"
      : tone === "danger"
        ? "border-danger/20 bg-danger/10 text-danger"
        : tone === "warning"
          ? "border-warning/20 bg-warning/10 text-warning"
          : "border-slate-200 bg-slate-100 text-ink";

  return (
    <div className="rounded-[22px] border border-slate-200/75 bg-white/78 p-4 shadow-soft">
      <div className="flex items-start gap-3">
        <span className={`icon-shell h-10 w-10 ${toneClass}`}>
          <Icon className="h-5 w-5" />
        </span>
        <div className="min-w-0">
          <p className="text-[11px] font-black uppercase tracking-[0.14em] text-muted">{label}</p>
          <p className={`${compactValue ? "text-base leading-6" : "text-3xl leading-none"} mt-2 break-words font-black text-ink`}>
            {value}
          </p>
          <p className="mt-1 text-xs font-semibold text-muted">{hint}</p>
        </div>
      </div>
    </div>
  );
}

function AnomalySignalRibbon({
  items,
  totalCount,
  labels,
  numberFormatter,
}: {
  items: DashboardResult["anomalyTypes"];
  totalCount: number;
  labels: { topTitle: string; share: string; intensity: string };
  numberFormatter: Intl.NumberFormat;
}) {
  if (!items.length) {
    return null;
  }

  return (
    <div className="rounded-[24px] border border-slate-200/75 bg-white/70 p-4 shadow-soft">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-black text-ink">{labels.topTitle}</p>
          <p className="mt-1 text-xs font-semibold text-muted">{labels.share} / {labels.intensity}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {items.map((item, index) => (
            <span key={item.type} className={`rounded-full px-3 py-1 text-xs font-black ${anomalyCountClass(index)}`}>
              #{index + 1} · {numberFormatter.format(item.count)}
            </span>
          ))}
        </div>
      </div>
      <div className="mt-4 flex h-4 overflow-hidden rounded-full bg-slate-200/75">
        {items.map((item, index) => {
          const width = Math.max(8, Math.round((item.count / Math.max(totalCount, 1)) * 100));
          return (
            <div
              key={item.type}
              className={`${anomalyBarClass(index)} transition-all`}
              style={{ width: `${width}%` }}
              title={`${item.type}: ${numberFormatter.format(item.count)}`}
            />
          );
        })}
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        {items.map((item, index) => {
          const share = Math.round((item.count / Math.max(totalCount, 1)) * 100);
          return (
            <div key={item.type} className="flex min-w-0 items-center gap-2 text-xs font-bold text-muted">
              <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${anomalyBarClass(index)}`} />
              <span className="truncate">{item.type}</span>
              <span className="ml-auto text-ink">{share}%</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function anomalyIconForType(type: string): typeof ShieldAlert {
  const normalized = type.toLowerCase();
  if (normalized.includes("фото") || normalized.includes("photo") || normalized.includes("image")) {
    return Camera;
  }
  if (normalized.includes("ocr") || normalized.includes("маркетинг") || normalized.includes("synthetic") || normalized.includes("stock")) {
    return Image;
  }
  if (normalized.includes("ru/en") || normalized.includes("язык") || normalized.includes("language") || normalized.includes("slang")) {
    return Languages;
  }
  if (normalized.includes("рейтинг") || normalized.includes("rating")) {
    return Star;
  }
  if (normalized.includes("автор") || normalized.includes("author") || normalized.includes("cluster")) {
    return Users;
  }
  if (normalized.includes("всплеск") || normalized.includes("burst") || normalized.includes("temporal")) {
    return Clock3;
  }
  if (normalized.includes("схож") || normalized.includes("similarity") || normalized.includes("повтор") || normalized.includes("repeat")) {
    return Copy;
  }
  if (normalized.includes("текст") || normalized.includes("text")) {
    return FileText;
  }
  return Fingerprint;
}

function anomalyHeroClass(index: number) {
  return index === 0
    ? "border-accent/25 bg-accent-soft/70"
    : index === 1
      ? "border-danger/20 bg-danger/10"
      : "border-warning/25 bg-warning/10";
}

function anomalyLevelLabel(width: number, labels: { critical: string; high: string; watch: string }) {
  if (width >= 78) {
    return labels.critical;
  }
  if (width >= 45) {
    return labels.high;
  }
  return labels.watch;
}

function TrustBreakdownCard({
  items,
  totalReviews,
}: {
  items: DashboardResult["trustBreakdown"];
  totalReviews: number;
}) {
  const total = items.reduce((sum, item) => sum + item.value, 0) || totalReviews || 1;
  const primary = items[0];
  const primaryPercent = Math.round((primary.value / total) * 100);

  return (
    <div className="mt-5 grid gap-5 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
      <div className="relative min-h-[250px] rounded-[26px] border border-slate-200/75 bg-white/76 p-4 shadow-soft">
        <ResponsiveContainer width="100%" height={230}>
          <PieChart>
            <Pie
              data={items}
              dataKey="value"
              innerRadius={70}
              outerRadius={102}
              paddingAngle={5}
              cornerRadius={8}
              stroke="rgba(255,255,255,0.92)"
              strokeWidth={5}
            >
              {items.map((entry) => (
                <Cell key={entry.name} fill={entry.fill} />
              ))}
            </Pie>
            <Tooltip
              allowEscapeViewBox={{ x: true, y: true }}
              content={(props) => <TrustBreakdownTooltip {...props} total={total} />}
              cursor={false}
              offset={18}
              position={{ x: 12, y: 12 }}
              wrapperStyle={{ outline: "none", pointerEvents: "none", zIndex: 30 }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="text-center">
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted">{primary.name}</p>
            <p className="mt-1 text-4xl font-bold leading-none text-ink">{primaryPercent}%</p>
            <p className="mt-1 text-xs font-semibold text-muted">{primary.value} / {total}</p>
          </div>
        </div>
      </div>

      <div className="grid gap-3">
        {items.map((item) => {
          const percent = Math.round((item.value / total) * 100);

          return (
            <div key={item.name} className="rounded-[22px] border border-slate-200/75 bg-white/82 p-4 shadow-soft">
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="h-3 w-3 shrink-0 rounded-full" style={{ backgroundColor: item.fill }} />
                  <p className="truncate text-sm font-bold text-ink">{item.name}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-bold text-ink">{percent}%</p>
                  <p className="text-[11px] font-semibold text-muted">{item.value}</p>
                </div>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200/70">
                <div className="h-full rounded-full" style={{ width: `${Math.max(4, percent)}%`, backgroundColor: item.fill }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

type TrustBreakdownTooltipPayload = {
  color?: string;
  name?: unknown;
  value?: unknown;
  payload?: {
    fill?: string;
    name?: unknown;
    value?: unknown;
  };
};

function TrustBreakdownTooltip({
  active,
  payload,
  total,
}: {
  active?: boolean;
  payload?: TrustBreakdownTooltipPayload[];
  total: number;
}) {
  if (!active || !payload?.length) {
    return null;
  }

  const item = payload[0];
  const value = numberFromTooltipValue(item.value ?? item.payload?.value);
  const name = String(item.name ?? item.payload?.name ?? "");
  const color = item.payload?.fill || item.color || "#0f766e";
  const percent = Math.round((value / Math.max(total, 1)) * 100);

  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white/90 px-3 py-2 shadow-lift backdrop-blur-xl">
      <div className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
        <p className="text-xs font-bold text-ink">{name}</p>
      </div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="text-lg font-bold leading-none text-ink">{percent}%</span>
        <span className="text-xs font-semibold text-muted">{value} / {total}</span>
      </div>
    </div>
  );
}

function numberFromTooltipValue(value: unknown) {
  if (typeof value === "number") {
    return value;
  }
  if (typeof value === "string") {
    return Number(value) || 0;
  }
  if (Array.isArray(value)) {
    return numberFromTooltipValue(value[0]);
  }
  return 0;
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
      ? "border-danger/20 bg-danger/10 text-danger"
      : accent === "warning"
        ? "border-warning/20 bg-warning/10 text-warning"
        : accent === "success"
          ? "border-success/20 bg-success/10 text-success"
          : "border-slate-200 bg-slate-100 text-ink";

  return (
    <div className="product-card product-card-hover flex h-full min-h-[136px] flex-col p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <span className={`icon-shell h-11 w-11 ${accentClass}`}>
          <Icon className="h-6 w-6" />
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
