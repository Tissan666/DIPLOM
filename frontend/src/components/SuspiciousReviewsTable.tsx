import { useState } from "react";
import type { ReactNode } from "react";
import { ArrowUpDown, Camera, Filter, Languages, Search, ShieldAlert, Tags } from "lucide-react";
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

  return (
    <section className="section-wrap py-5 pb-12">
      <div className="surface-card p-6 sm:p-7">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="eyebrow">{copy.suspiciousTable.eyebrow}</p>
            <h2 className="mt-3 font-display text-3xl text-ink">{copy.suspiciousTable.title}</h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-muted">{copy.suspiciousTable.description}</p>
          </div>
          <span className="badge-soft">
            {status === "success" ? `${reviews.length} ${copy.common.rowsAvailable}` : copy.common.tablePreview}
          </span>
        </div>

        <div className="mt-8 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-1 items-center gap-3 rounded-2xl border border-slate-200/80 bg-white/85 px-4 py-3">
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
          <div className="mt-8 overflow-hidden rounded-[28px] border border-slate-200/80 bg-white/85">
            <div className="hidden grid-cols-[2.5fr_0.7fr_0.9fr_1.4fr_1.1fr_0.9fr] gap-4 border-b border-slate-200/80 px-5 py-4 text-xs font-semibold uppercase tracking-[0.2em] text-muted xl:grid">
              <span>{copy.suspiciousTable.columns.reviewText}</span>
              <span>{copy.suspiciousTable.columns.rating}</span>
              <span>{copy.suspiciousTable.columns.suspiciousness}</span>
              <span>{copy.suspiciousTable.columns.reason}</span>
              <span>{copy.suspiciousTable.columns.author}</span>
              <span>{copy.suspiciousTable.columns.date}</span>
            </div>

            <div className="divide-y divide-slate-200/80">
              {filtered.map((review, index) => (
                <motion.article
                  key={review.id}
                  initial={{ opacity: 0, y: 10 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.1 }}
                  transition={{ duration: 0.24, delay: index * 0.03 }}
                  className="grid gap-4 px-5 py-5 xl:grid-cols-[2.5fr_0.7fr_0.9fr_1.4fr_1.1fr_0.9fr] xl:items-start"
                >
                  <div>
                    <p className="text-sm font-semibold text-ink">{review.title}</p>
                    <p className="mt-2 text-sm leading-7 text-muted">{review.text}</p>
                    <LanguageEvidence review={review} locale={locale} />
                  </div>
                  <CellLabel title={copy.suspiciousTable.labels.rating} value={`${review.rating.toFixed(1)} / 5`} />
                  <CellLabel
                    title={copy.suspiciousTable.labels.suspiciousness}
                    value={`${Math.round(review.suspiciousness * 100)}%`}
                    severity={review.severity}
                  />
                  <CellLabel title={copy.suspiciousTable.labels.reason} value={review.reason} wrap />
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted xl:hidden">
                      {copy.suspiciousTable.labels.author}
                    </p>
                    <p className="text-sm font-semibold text-ink">{review.author}</p>
                    <span className={`mt-2 inline-flex rounded-full px-3 py-1 text-xs font-semibold ${authorTrustClass(review.authorTrust)}`}>
                      {authorTrustLabel(review.authorTrust, locale)}
                    </span>
                  </div>
                  <CellLabel title={copy.suspiciousTable.labels.date} value={review.date} />
                </motion.article>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function SelectFilter({
  icon: Icon,
  value,
  options,
  onChange,
}: {
  icon: typeof Filter;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex items-center gap-2 rounded-2xl border border-slate-200/80 bg-white/85 px-3 py-2.5">
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
        {review.detectedTerms.map((term) => (
          <EvidenceChip key={`${review.id}-${term}`} className="border-slate-200/70 bg-slate-50 text-muted">
            <Tags className="h-3.5 w-3.5" />
            {term}
          </EvidenceChip>
        ))}
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <SignalMeter
          label={copy.suspiciousTable.labels.slangRisk}
          value={review.languageSignalScore}
          tone={review.languageSignalScore >= 0.55 ? "danger" : review.languageSignalScore >= 0.35 ? "warning" : "accent"}
        />
        <SignalMeter
          label={copy.suspiciousTable.labels.grounding}
          value={review.languageAuthenticityScore}
          tone={review.languageAuthenticityScore >= 0.55 ? "accent" : review.languageAuthenticityScore >= 0.35 ? "warning" : "danger"}
        />
        <SignalMeter
          label={copy.suspiciousTable.labels.uncertainty}
          value={review.uncertaintyScore}
          tone={review.uncertaintyScore >= 0.55 ? "danger" : review.uncertaintyScore >= 0.35 ? "warning" : "accent"}
        />
        <SignalMeter
          label={copy.suspiciousTable.labels.oodDrift}
          value={review.oodScore}
          tone={review.oodScore >= 0.45 ? "danger" : review.oodScore >= 0.25 ? "warning" : "accent"}
        />
        {review.imageCount > 0 && (
          <SignalMeter
            label={copy.suspiciousTable.labels.photoReuse}
            value={review.duplicateImageScore}
            tone={review.duplicateImageScore >= 0.55 ? "danger" : review.duplicateImageScore >= 0.25 ? "warning" : "accent"}
          />
        )}
        {review.imageTemporalClusterScore !== undefined && review.imageTemporalClusterScore > 0 && (
          <SignalMeter
            label={copy.suspiciousTable.labels.photoTemporalClusterScore}
            value={review.imageTemporalClusterScore}
            tone={review.imageTemporalClusterScore >= 0.55 ? "danger" : review.imageTemporalClusterScore >= 0.35 ? "warning" : "accent"}
          />
        )}
        {review.imageTextMismatchScore !== undefined && review.imageTextMismatchScore > 0 && (
          <SignalMeter
            label={copy.suspiciousTable.labels.photoTextMismatch}
            value={review.imageTextMismatchScore}
            tone={review.imageTextMismatchScore >= 0.58 ? "danger" : review.imageTextMismatchScore >= 0.35 ? "warning" : "accent"}
          />
        )}
        {review.imageStockMarketingScore !== undefined && review.imageStockMarketingScore > 0 && (
          <SignalMeter
            label={copy.suspiciousTable.labels.stockMarketingScore}
            value={review.imageStockMarketingScore}
            tone={review.imageStockMarketingScore >= 0.58 ? "danger" : review.imageStockMarketingScore >= 0.35 ? "warning" : "accent"}
          />
        )}
        {review.imageOcrScore !== undefined && review.imageOcrScore > 0 && (
          <SignalMeter
            label={copy.suspiciousTable.labels.photoOcrScore}
            value={review.imageOcrScore}
            tone={review.imageOcrScore >= 0.46 ? "danger" : review.imageOcrScore >= 0.25 ? "warning" : "accent"}
          />
        )}
        {review.imageSyntheticScore !== undefined && review.imageSyntheticScore > 0 && (
          <SignalMeter
            label={copy.suspiciousTable.labels.syntheticImageScore}
            value={review.imageSyntheticScore}
            tone={review.imageSyntheticScore >= 0.66 ? "warning" : "accent"}
          />
        )}
      </div>
    </div>
  );
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
    <div className="rounded-2xl border border-slate-200/80 bg-slate-50/70 px-3 py-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted">{label}</p>
        <span className="text-sm font-semibold text-ink">{Math.round(value * 100)}%</span>
      </div>
      <div className="mt-2 h-2 rounded-full bg-slate-200/80">
        <div className={`h-2 rounded-full ${signalMeterClass(tone)}`} style={{ width: `${Math.max(6, value * 100)}%` }} />
      </div>
    </div>
  );
}

function CellLabel({
  title,
  value,
  severity,
  wrap = false,
}: {
  title: string;
  value: string;
  severity?: "high" | "medium" | "low";
  wrap?: boolean;
}) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted xl:hidden">{title}</p>
      <span
        className={`inline-flex ${
          wrap ? "whitespace-normal text-left leading-7" : ""
        } rounded-full ${severity ? `${severityBadge(severity)} px-3 py-1` : ""} text-sm font-medium text-ink`}
      >
        {value}
      </span>
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

function authorTrustClass(level: "trusted" | "neutral" | "low") {
  if (level === "trusted") {
    return "bg-accent-soft text-accent";
  }
  if (level === "neutral") {
    return "bg-warning/10 text-warning";
  }
  return "bg-danger/10 text-danger";
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
