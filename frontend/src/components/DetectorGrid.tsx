import { motion } from "framer-motion";
import {
  AlertTriangle,
  BarChart3,
  Bot,
  Clock3,
  FileSearch,
  Fingerprint,
  Gauge,
  ImageOff,
  Languages,
  MessageSquareText,
  ScanSearch,
  ShieldQuestion,
  UsersRound,
  type LucideIcon,
} from "lucide-react";
import { useLocale } from "../i18n";
import type { AppStatus, DetectorCardData } from "../types/analysis";

type DetectorGridProps = {
  detectors: DetectorCardData[];
  status: AppStatus;
};

export function DetectorGrid({ detectors, status }: DetectorGridProps) {
  const { copy, locale } = useLocale();
  const showPlaceholder = status !== "success" || detectors.length === 0;

  return (
    <section className="section-wrap py-6">
      <div className="surface-card p-6 sm:p-8">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="eyebrow">{copy.detectorGrid.eyebrow}</p>
            <h2 className="mt-3 font-display text-3xl font-bold text-ink sm:text-4xl">{copy.detectorGrid.title}</h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-muted">{copy.detectorGrid.description}</p>
          </div>
          <span className="badge-soft">
            {status === "success" ? `${detectors.length} ${copy.common.detectorsActive}` : copy.common.detectorPreview}
          </span>
        </div>

        {showPlaceholder ? (
          <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="surface-card-soft p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="h-10 w-10 animate-pulse rounded-2xl bg-slate-200" />
                  <div className="h-6 w-20 animate-pulse rounded-full bg-slate-200" />
                </div>
                <div className="mt-5 h-5 w-40 animate-pulse rounded-full bg-slate-200" />
                <div className="mt-3 h-16 animate-pulse rounded-2xl bg-slate-100" />
                <div className="mt-5 h-2 animate-pulse rounded-full bg-slate-200" />
              </div>
            ))}
          </div>
        ) : (
          <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {detectors.map((detector, index) => (
              <motion.article
                key={detector.id}
                initial={{ opacity: 0, y: 22 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.2 }}
                transition={{ duration: 0.35, delay: index * 0.05 }}
                whileHover={{ y: -4 }}
                className="product-card product-card-hover group p-5"
              >
                <div className="flex items-start justify-between gap-3">
                  <span className="icon-shell bg-white/90 text-ink">
                    {renderDetectorIcon(detector)}
                  </span>
                  <span className={`badge-soft ${severityClass(detector.severity)}`}>
                    {localizeSeverity(detector.severity, locale)}
                  </span>
                </div>

                <h3 className="mt-5 text-lg font-semibold text-ink">{detector.name}</h3>
                <p className="mt-2 text-sm leading-7 text-muted">{detector.description}</p>

                <div className="mt-5 flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted">{copy.detectorGrid.detectorScore}</p>
                    <p className="mt-2 text-3xl font-semibold text-ink">{detector.score}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted">{copy.detectorGrid.status}</p>
                    <p className="mt-2 inline-flex items-center gap-2 text-sm font-semibold text-ink">
                      <ShieldQuestion className="h-4 w-4 text-accent" />
                      {localizeDetectorStatus(detector.status, locale)}
                    </p>
                  </div>
                </div>

                <div className="mt-5 h-2 rounded-full bg-slate-200/70">
                  <div
                    className={`h-2 rounded-full transition-all duration-500 ${
                      detector.severity === "high"
                        ? "bg-danger"
                        : detector.severity === "medium"
                          ? "bg-warning"
                          : "bg-accent"
                    }`}
                    style={{ width: `${detector.score}%` }}
                  />
                </div>
              </motion.article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function localizeDetectorStatus(status: DetectorCardData["status"], locale: "en" | "ru") {
  if (locale === "ru") {
    if (status === "critical") {
      return "Критический";
    }
    if (status === "watch") {
      return "Под наблюдением";
    }
    return "Стабильный";
  }

  return status;
}

function renderDetectorIcon(detector: DetectorCardData) {
  const Icon = detectorIcon(detector);
  return <Icon className={`h-6 w-6 ${detectorIconClass(detector)}`} />;
}

function detectorIcon(detector: DetectorCardData): LucideIcon {
  const id = detector.id.toLowerCase();
  if (id.includes("ai-text")) {
    return Bot;
  }
  if (id.includes("text-similarity")) {
    return Fingerprint;
  }
  if (id.includes("burst") || id.includes("temporal")) {
    return Clock3;
  }
  if (id.includes("reviewer") || id.includes("user") || id.includes("author")) {
    return UsersRound;
  }
  if (id.includes("rating")) {
    return BarChart3;
  }
  if (id.includes("sentiment")) {
    return MessageSquareText;
  }
  if (id.includes("slang") || id.includes("bilingual")) {
    return Languages;
  }
  if (id.includes("ocr") || id.includes("alignment")) {
    return ScanSearch;
  }
  if (id.includes("synthetic") || id.includes("stock") || id.includes("photo")) {
    return ImageOff;
  }
  if (id.includes("uncertainty")) {
    return Gauge;
  }
  if (detector.status === "critical") {
    return AlertTriangle;
  }
  return FileSearch;
}

function detectorIconClass(detector: DetectorCardData) {
  if (detector.status === "critical") {
    return "text-danger";
  }
  if (detector.status === "watch") {
    return "text-warning";
  }
  return "text-accent";
}

function localizeSeverity(severity: DetectorCardData["severity"], locale: "en" | "ru") {
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

function severityClass(severity: "low" | "medium" | "high") {
  if (severity === "high") {
    return "severity-high";
  }
  if (severity === "medium") {
    return "severity-medium";
  }
  return "severity-low";
}
