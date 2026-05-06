import { useState } from "react";
import type { ReactNode } from "react";
import {
  AlertTriangle,
  ArrowUpDown,
  Bot,
  CalendarDays,
  Camera,
  Filter,
  Languages,
  Search,
  ShieldAlert,
  Star,
  Tags,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import { motion } from "framer-motion";
import { getCopy, useLocale, type Locale } from "../i18n";
import type { AppStatus, SuspiciousReviewRow } from "../types/analysis";

type SuspiciousReviewsTableProps = {
  reviews: SuspiciousReviewRow[];
  status: AppStatus;
};

type SortMode = "suspiciousness" | "date" | "rating";
type SeverityFilter = "all" | "high" | "medium" | "low";
type LanguageFilter = "all" | "suspicious" | "mixed" | "organic" | "neutral";
type TriageFilter = "all" | "confident_suspicious" | "needs_manual_review" | "confident_clean";
type SuspiciousTableLabels = ReturnType<typeof getCopy>["suspiciousTable"]["labels"];

export function SuspiciousReviewsTable({ reviews, status }: SuspiciousReviewsTableProps) {
  const { copy, locale } = useLocale();
  const [query, setQuery] = useState("");
  const [sortMode, setSortMode] = useState<SortMode>("suspiciousness");
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>("all");
  const [languageFilter, setLanguageFilter] = useState<LanguageFilter>("all");
  const [triageFilter, setTriageFilter] = useState<TriageFilter>("all");

  const filtered = reviews
    .filter((review) => {
      if (severityFilter !== "all" && review.severity !== severityFilter) {
        return false;
      }
      if (languageFilter !== "all" && review.languageProfile !== languageFilter) {
        return false;
      }
      if (triageFilter !== "all" && review.triageStatus !== triageFilter) {
        return false;
      }
      const haystack = [
        review.title,
        review.text,
        review.reason,
        review.author,
        review.languageDomain,
        review.triageStatus,
        ...review.detectedTerms,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(query.trim().toLowerCase());
    })
    .sort((left, right) => {
      if (sortMode === "date") {
        return right.date.localeCompare(left.date);
      }
      if (sortMode === "rating") {
        return right.rating - left.rating;
      }
      return right.suspiciousness - left.suspiciousness;
    });
  const highRiskCount = filtered.filter((review) => review.severity === "high").length;
  const manualReviewCount = filtered.filter((review) => review.triageStatus !== "confident_clean").length;
  const averageSuspiciousness = filtered.length
    ? Math.round((filtered.reduce((sum, review) => sum + review.suspiciousness, 0) / filtered.length) * 100)
    : 0;

  return (
    <section className="section-wrap py-6 pb-12">
      <div className="surface-card p-6 sm:p-8">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="eyebrow">{copy.suspiciousTable.eyebrow}</p>
            <h2 className="mt-3 font-display text-3xl font-bold text-ink sm:text-4xl">{copy.suspiciousTable.title}</h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-muted">{copy.suspiciousTable.description}</p>
          </div>
          <span className="badge-soft">
            {status === "success" ? `${reviews.length} ${copy.common.rowsAvailable}` : copy.common.tablePreview}
          </span>
        </div>

        {status === "success" && (
          <div className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <SummaryTile
              icon={Search}
              label={copy.suspiciousTable.summary.visible}
              value={`${filtered.length}/${reviews.length}`}
              tone="neutral"
            />
            <SummaryTile
              icon={AlertTriangle}
              label={copy.suspiciousTable.summary.highRisk}
              value={String(highRiskCount)}
              tone="danger"
            />
            <SummaryTile
              icon={ShieldAlert}
              label={copy.suspiciousTable.summary.manualReview}
              value={String(manualReviewCount)}
              tone="warning"
            />
            <SummaryTile
              icon={ArrowUpDown}
              label={copy.suspiciousTable.summary.avgRisk}
              value={`${averageSuspiciousness}%`}
              tone="accent"
            />
          </div>
        )}

        <div className="mt-7 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-1 items-center gap-3 rounded-2xl border border-slate-200/80 bg-white/85 px-4 py-3 shadow-soft">
            <Search className="h-4 w-4 text-muted" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={copy.suspiciousTable.filterPlaceholder}
              className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-slate-400"
            />
          </div>

          <div className="flex flex-wrap gap-3">
            <SelectFilter
              icon={Filter}
              value={severityFilter}
              onChange={(value) => setSeverityFilter(value as SeverityFilter)}
              options={[
                { value: "all", label: copy.suspiciousTable.severity.all },
                { value: "high", label: copy.suspiciousTable.severity.high },
                { value: "medium", label: copy.suspiciousTable.severity.medium },
                { value: "low", label: copy.suspiciousTable.severity.low },
              ]}
            />
            <SelectFilter
              icon={Languages}
              value={languageFilter}
              onChange={(value) => setLanguageFilter(value as LanguageFilter)}
              options={[
                { value: "all", label: copy.suspiciousTable.language.all },
                { value: "suspicious", label: copy.suspiciousTable.language.suspicious },
                { value: "mixed", label: copy.suspiciousTable.language.mixed },
                { value: "organic", label: copy.suspiciousTable.language.organic },
                { value: "neutral", label: copy.suspiciousTable.language.neutral },
              ]}
            />
            <SelectFilter
              icon={ArrowUpDown}
              value={sortMode}
              onChange={(value) => setSortMode(value as SortMode)}
              options={[
                { value: "suspiciousness", label: copy.suspiciousTable.sort.suspiciousness },
                { value: "date", label: copy.suspiciousTable.sort.date },
                { value: "rating", label: copy.suspiciousTable.sort.rating },
              ]}
            />
            <SelectFilter
              icon={ShieldAlert}
              value={triageFilter}
              onChange={(value) => setTriageFilter(value as TriageFilter)}
              options={[
                { value: "all", label: copy.suspiciousTable.triage.all },
                { value: "confident_suspicious", label: copy.suspiciousTable.triage.confidentSuspicious },
                { value: "needs_manual_review", label: copy.suspiciousTable.triage.needsManualReview },
                { value: "confident_clean", label: copy.suspiciousTable.triage.confidentClean },
              ]}
            />
          </div>
        </div>

        {status !== "success" ? (
          <EmptyTableState
            title={copy.suspiciousTable.waitingTitle}
            description={copy.suspiciousTable.waitingDescription}
          />
        ) : filtered.length === 0 ? (
          <EmptyTableState
            title={copy.suspiciousTable.emptyTitle}
            description={copy.suspiciousTable.emptyDescription}
          />
        ) : (
          <div className="mt-8 grid gap-4">
            {filtered.map((review, index) => (
              <ReviewCard
                key={review.id}
                review={review}
                index={index}
                locale={locale}
                labels={copy.suspiciousTable.labels}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function SummaryTile({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  tone: "danger" | "warning" | "accent" | "neutral";
}) {
  const toneClass =
    tone === "danger"
      ? "icon-risk"
      : tone === "warning"
        ? "icon-analysis"
        : tone === "accent"
          ? "border-accent/20 bg-accent-soft text-accent"
          : "border-slate-200 bg-white text-ink";

  return (
    <div className="product-card p-4">
      <div className="flex items-center gap-3">
        <span className={`icon-shell h-11 w-11 ${toneClass}`}>
          <Icon className="h-5 w-5" />
        </span>
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted">{label}</p>
          <p className="mt-1 text-2xl font-bold leading-none text-ink">{value}</p>
        </div>
      </div>
    </div>
  );
}

function ReviewCard({
  review,
  index,
  locale,
  labels,
}: {
  review: SuspiciousReviewRow;
  index: number;
  locale: Locale;
  labels: SuspiciousTableLabels;
}) {
  const suspiciousness = Math.round(review.suspiciousness * 100);

  return (
    <motion.article
      initial={{ opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.1 }}
      transition={{ duration: 0.28, delay: index * 0.03 }}
      className={`product-card product-card-hover overflow-hidden border-l-4 ${reviewAccentBorder(review.severity)}`}
    >
      <div className="grid gap-5 p-5 xl:grid-cols-[minmax(0,1fr)_260px] xl:p-6">
        <div className="min-w-0">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded-full px-3 py-1 text-xs font-bold ${severityBadge(review.severity)}`}>
                  {suspiciousness}%
                </span>
                <span className="rounded-full border border-slate-200/80 bg-white/80 px-3 py-1 text-xs font-bold text-muted">
                  {labels.reason}: {review.reason}
                </span>
              </div>
              <h3 className="mt-3 text-base font-bold leading-6 text-ink">{review.title}</h3>
            </div>
          </div>

          <p className="mt-3 max-w-4xl text-sm leading-7 text-muted">{review.text}</p>
          <LanguageEvidence review={review} locale={locale} />
        </div>

        <aside className="grid gap-3 rounded-[24px] border border-slate-200/75 bg-white/70 p-4 shadow-soft">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-muted">{labels.suspiciousness}</p>
            <div className="mt-3 flex items-end justify-between gap-3">
              <p className="text-4xl font-bold leading-none text-ink">{suspiciousness}%</p>
              <span className={`rounded-full px-3 py-1 text-xs font-bold ${severityBadge(review.severity)}`}>
                {severityLabel(review.severity, locale)}
              </span>
            </div>
            <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-slate-200/70">
              <div className={`h-full rounded-full ${riskBarClass(review.severity)}`} style={{ width: `${suspiciousness}%` }} />
            </div>
          </div>

          <div className="grid gap-2">
            <MetaPill icon={Star} label={labels.rating} value={`${review.rating.toFixed(1)} / 5`} />
            <MetaPill icon={UserRound} label={labels.author} value={review.author} helper={authorTrustLabel(review.authorTrust, locale)} />
            <MetaPill icon={CalendarDays} label={labels.date} value={review.date} />
          </div>
        </aside>
      </div>
    </motion.article>
  );
}

function MetaPill({
  icon: Icon,
  label,
  value,
  helper,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  helper?: string;
}) {
  return (
    <div className="flex items-start gap-3 rounded-2xl border border-slate-200/70 bg-white/78 px-3 py-3">
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-ink">
        <Icon className="h-4 w-4" />
      </span>
      <div className="min-w-0">
        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-muted">{label}</p>
        <p className="mt-1 break-words text-sm font-bold text-ink">{value}</p>
        {helper && <p className="mt-1 text-xs font-semibold text-muted">{helper}</p>}
      </div>
    </div>
  );
}

function SelectFilter({
  icon: Icon,
  value,
  options,
  onChange,
}: {
  icon: LucideIcon;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex items-center gap-2 rounded-2xl border border-slate-200/80 bg-white/85 px-3 py-2.5 shadow-soft transition hover:border-accent/25 hover:bg-white">
      <Icon className="h-4 w-4 text-muted" />
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="bg-transparent text-sm font-medium text-ink outline-none"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function EmptyTableState({ title, description }: { title: string; description: string }) {
  return (
    <div className="mt-8 rounded-[28px] border border-dashed border-slate-200/80 bg-white/75 p-10 text-center">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-soft text-accent">
        <ShieldAlert className="h-6 w-6" />
      </div>
      <h3 className="mt-5 font-display text-3xl text-ink">{title}</h3>
      <p className="mt-3 text-sm leading-7 text-muted">{description}</p>
    </div>
  );
}

function LanguageEvidence({ review, locale }: { review: SuspiciousReviewRow; locale: Locale }) {
  const copy = getCopy(locale);
  const visibleTerms = review.detectedTerms.slice(0, 4);
  const hiddenTermsCount = Math.max(0, review.detectedTerms.length - visibleTerms.length);
  const signalMeters = buildSignalMeters(review, copy.suspiciousTable.labels);

  return (
    <div className="mt-4 space-y-3">
      <div className="flex flex-wrap gap-2">
        <EvidenceChip className={languageProfileClass(review.languageProfile)}>
          {languageProfileLabel(review.languageProfile, locale)}
        </EvidenceChip>
        <EvidenceChip className={triageChipClass(review.triageStatus)}>
          {triageStatusLabel(review.triageStatus, locale)}
        </EvidenceChip>
        {review.languageDomain !== "general" && review.languageDomain !== "общий" && (
          <EvidenceChip className="border-slate-200/80 bg-white text-ink">
            <Languages className="h-3.5 w-3.5" />
            {review.languageDomain}
          </EvidenceChip>
        )}
        {review.templateClustered && (
          <EvidenceChip className="border-danger/15 bg-danger/10 text-danger">
            {copy.suspiciousTable.labels.templateCluster}
          </EvidenceChip>
        )}
        {review.aiTextScore !== undefined && review.aiTextScore > 0 && (
          <EvidenceChip
            className={
              review.aiTextFlag
                ? "border-danger/15 bg-danger/10 text-danger"
                : review.aiTextScore >= 0.52
                  ? "border-warning/15 bg-warning/10 text-warning"
                  : "border-accent/15 bg-accent-soft text-accent"
            }
          >
            <Bot className="h-3.5 w-3.5" />
            {`${copy.suspiciousTable.labels.aiTextScore}: ${Math.round(review.aiTextScore * 100)}%`}
          </EvidenceChip>
        )}
        {review.imageCount > 0 && (
          <EvidenceChip
            className={
              review.duplicateImageFlag ||
              review.imageTemporalClusterFlag ||
              review.imageTextMismatchFlag ||
              review.imageStockMarketingFlag ||
              review.imageOcrFlag
                ? "border-danger/15 bg-danger/10 text-danger"
                : review.imageSyntheticFlag
                  ? "border-warning/15 bg-warning/10 text-warning"
                : "border-accent/15 bg-accent-soft text-accent"
            }
          >
            <Camera className="h-3.5 w-3.5" />
            {review.imageOcrFlag
              ? `${copy.suspiciousTable.labels.photoOcrText}: ${Math.round((review.imageOcrScore || 0) * 100)}%`
              : review.imageTemporalClusterFlag
              ? `${copy.suspiciousTable.labels.photoTemporalCluster}: ${review.imageTemporalClusterAuthorCount || 0} ${
                  locale === "ru" ? "авт." : "authors"
                }`
              : review.imageStockMarketingFlag
              ? `${copy.suspiciousTable.labels.stockMarketingPhoto}: ${Math.round((review.imageStockMarketingScore || 0) * 100)}%`
              : review.imageTextMismatchFlag
              ? `${copy.suspiciousTable.labels.photoMismatch}: ${Math.round((review.imageTextMismatchScore || 0) * 100)}%`
              : review.duplicateImageFlag
              ? `${copy.suspiciousTable.labels.duplicatePhotoCluster}: ${review.duplicateImageClusterSize}`
              : review.imageSyntheticFlag
              ? `${copy.suspiciousTable.labels.syntheticImageHint}: ${Math.round((review.imageSyntheticScore || 0) * 100)}%`
              : `${copy.suspiciousTable.labels.photoEvidence}: ${review.imageCount}`}
          </EvidenceChip>
        )}
        {visibleTerms.map((term) => (
          <EvidenceChip key={`${review.id}-${term}`} className="border-slate-200/70 bg-slate-50 text-muted">
            <Tags className="h-3.5 w-3.5" />
            {term}
          </EvidenceChip>
        ))}
        {hiddenTermsCount > 0 && (
          <EvidenceChip className="border-slate-200/70 bg-white text-muted">
            +{hiddenTermsCount}
          </EvidenceChip>
        )}
      </div>

      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {signalMeters.map((signal) => (
          <SignalMeter key={signal.label} label={signal.label} value={signal.value} tone={signal.tone} />
        ))}
      </div>
    </div>
  );
}

function buildSignalMeters(review: SuspiciousReviewRow, labels: SuspiciousTableLabels) {
  const signals: Array<{
    label: string;
    value: number;
    tone: "accent" | "warning" | "danger";
    visible?: boolean;
  }> = [
    {
      label: labels.slangRisk,
      value: review.languageSignalScore,
      tone: review.languageSignalScore >= 0.55 ? "danger" : review.languageSignalScore >= 0.35 ? "warning" : "accent",
      visible: true,
    },
    {
      label: labels.grounding,
      value: review.languageAuthenticityScore,
      tone: review.languageAuthenticityScore >= 0.55 ? "accent" : review.languageAuthenticityScore >= 0.35 ? "warning" : "danger",
      visible: true,
    },
    {
      label: labels.uncertainty,
      value: review.uncertaintyScore,
      tone: review.uncertaintyScore >= 0.55 ? "danger" : review.uncertaintyScore >= 0.35 ? "warning" : "accent",
      visible: true,
    },
    {
      label: labels.oodDrift,
      value: review.oodScore,
      tone: review.oodScore >= 0.45 ? "danger" : review.oodScore >= 0.25 ? "warning" : "accent",
      visible: true,
    },
    {
      label: labels.aiTextScore,
      value: review.aiTextScore || 0,
      tone: (review.aiTextScore || 0) >= 0.66 ? "danger" : (review.aiTextScore || 0) >= 0.52 ? "warning" : "accent",
    },
    {
      label: labels.photoReuse,
      value: review.duplicateImageScore,
      tone: review.duplicateImageScore >= 0.55 ? "danger" : review.duplicateImageScore >= 0.25 ? "warning" : "accent",
      visible: review.imageCount > 0,
    },
    {
      label: labels.photoTemporalClusterScore,
      value: review.imageTemporalClusterScore || 0,
      tone:
        (review.imageTemporalClusterScore || 0) >= 0.55
          ? "danger"
          : (review.imageTemporalClusterScore || 0) >= 0.35
            ? "warning"
            : "accent",
    },
    {
      label: labels.photoTextMismatch,
      value: review.imageTextMismatchScore || 0,
      tone:
        (review.imageTextMismatchScore || 0) >= 0.58
          ? "danger"
          : (review.imageTextMismatchScore || 0) >= 0.35
            ? "warning"
            : "accent",
    },
    {
      label: labels.stockMarketingScore,
      value: review.imageStockMarketingScore || 0,
      tone:
        (review.imageStockMarketingScore || 0) >= 0.58
          ? "danger"
          : (review.imageStockMarketingScore || 0) >= 0.35
            ? "warning"
            : "accent",
    },
    {
      label: labels.photoOcrScore,
      value: review.imageOcrScore || 0,
      tone:
        (review.imageOcrScore || 0) >= 0.46
          ? "danger"
          : (review.imageOcrScore || 0) >= 0.25
            ? "warning"
            : "accent",
    },
    {
      label: labels.syntheticImageScore,
      value: review.imageSyntheticScore || 0,
      tone: (review.imageSyntheticScore || 0) >= 0.66 ? "warning" : "accent",
    },
  ];

  return signals
    .filter((signal) => signal.visible || signal.value > 0)
    .sort((left, right) => right.value - left.value)
    .slice(0, 6);
}

function EvidenceChip({
  className,
  children,
}: {
  className: string;
  children: ReactNode;
}) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold ${className}`}>
      {children}
    </span>
  );
}

function SignalMeter({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "accent" | "warning" | "danger";
}) {
  return (
    <div className="rounded-2xl border border-slate-200/80 bg-slate-50/70 px-3 py-2.5">
      <div className="flex items-center justify-between gap-3">
        <p className="line-clamp-2 text-[10px] font-bold uppercase tracking-[0.14em] text-muted">{label}</p>
        <span className="text-sm font-semibold text-ink">{Math.round(value * 100)}%</span>
      </div>
      <div className="mt-2 h-1.5 rounded-full bg-slate-200/80">
        <div className={`h-1.5 rounded-full ${signalMeterClass(tone)}`} style={{ width: `${Math.max(6, value * 100)}%` }} />
      </div>
    </div>
  );
}

function severityBadge(severity: "high" | "medium" | "low") {
  if (severity === "high") {
    return "bg-danger/10 text-danger";
  }
  if (severity === "medium") {
    return "bg-warning/10 text-warning";
  }
  return "bg-accent-soft text-accent";
}

function reviewAccentBorder(severity: "high" | "medium" | "low") {
  if (severity === "high") {
    return "border-l-danger";
  }
  if (severity === "medium") {
    return "border-l-warning";
  }
  return "border-l-accent";
}

function riskBarClass(severity: "high" | "medium" | "low") {
  if (severity === "high") {
    return "bg-danger";
  }
  if (severity === "medium") {
    return "bg-warning";
  }
  return "bg-accent";
}

function severityLabel(severity: "high" | "medium" | "low", locale: Locale) {
  if (locale === "ru") {
    if (severity === "high") {
      return "Высокий";
    }
    if (severity === "medium") {
      return "Средний";
    }
    return "Низкий";
  }

  return severity;
}

function languageProfileClass(profile: SuspiciousReviewRow["languageProfile"]) {
  if (profile === "suspicious") {
    return "border-danger/15 bg-danger/10 text-danger";
  }
  if (profile === "mixed") {
    return "border-warning/15 bg-warning/10 text-warning";
  }
  if (profile === "organic") {
    return "border-accent/15 bg-accent-soft text-accent";
  }
  return "border-slate-200/80 bg-white text-muted";
}

function languageProfileLabel(profile: SuspiciousReviewRow["languageProfile"], locale: Locale) {
  if (locale === "ru") {
    if (profile === "suspicious") {
      return "Язык: подозрительный";
    }
    if (profile === "mixed") {
      return "Язык: смешанный";
    }
    if (profile === "organic") {
      return "Язык: органичный";
    }
    return "Язык: нейтральный";
  }

  if (profile === "suspicious") {
    return "Language: suspicious";
  }
  if (profile === "mixed") {
    return "Language: mixed";
  }
  if (profile === "organic") {
    return "Language: organic";
  }
  return "Language: neutral";
}

function triageChipClass(status: SuspiciousReviewRow["triageStatus"]) {
  if (status === "confident_suspicious") {
    return "border-danger/15 bg-danger/10 text-danger";
  }
  if (status === "needs_manual_review") {
    return "border-warning/15 bg-warning/10 text-warning";
  }
  return "border-accent/15 bg-accent-soft text-accent";
}

function triageStatusLabel(status: SuspiciousReviewRow["triageStatus"], locale: Locale) {
  if (locale === "ru") {
    if (status === "confident_suspicious") {
      return "Проверка: уверенно подозрительный";
    }
    if (status === "needs_manual_review") {
      return "Проверка: ручная проверка";
    }
    return "Проверка: уверенно чистый";
  }

  if (status === "confident_suspicious") {
    return "Triage: confident suspicious";
  }
  if (status === "needs_manual_review") {
    return "Triage: manual review";
  }
  return "Triage: confident clean";
}

function authorTrustLabel(level: SuspiciousReviewRow["authorTrust"], locale: Locale) {
  if (locale === "ru") {
    if (level === "trusted") {
      return "надежный";
    }
    if (level === "neutral") {
      return "нейтральный";
    }
    return "низкое доверие";
  }

  return level;
}

function signalMeterClass(tone: "accent" | "warning" | "danger") {
  if (tone === "danger") {
    return "bg-danger";
  }
  if (tone === "warning") {
    return "bg-warning";
  }
  return "bg-accent";
}
