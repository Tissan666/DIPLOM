import { useEffect, useState } from "react";
import { Archive, Clock3, ExternalLink, RotateCw, ShieldAlert } from "lucide-react";
import { useLocale } from "../i18n";
import type { AppStatus } from "../types/analysis";

type HistoryReport = {
  id: string;
  created_at: string;
  source_type: string;
  source_label: string;
  risk_level: string;
  total_count: number;
  suspicious_count: number;
  manual_review_count: number;
  history_url: string;
};

type HistoryResponse = {
  reports?: HistoryReport[];
};

type HistoryPanelProps = {
  status: AppStatus;
};

export function HistoryPanel({ status }: HistoryPanelProps) {
  const { locale } = useLocale();
  const [reports, setReports] = useState<HistoryReport[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const copy =
    locale === "ru"
      ? {
          eyebrow: "История проверок",
          title: "Последние сохраненные отчеты",
          description: "Backend сохраняет результаты в SQLite, чтобы можно было вернуться к проверке и подтвердить воспроизводимость.",
          refresh: "Обновить",
          empty: "История появится после первого успешного анализа.",
          open: "JSON",
          suspicious: "подозрительных",
          manual: "ручная проверка",
          rows: "строк",
          failed: "Не удалось загрузить историю.",
        }
      : {
          eyebrow: "Analysis history",
          title: "Recent saved reports",
          description: "The backend saves completed reports in SQLite so checks can be revisited and reproduced.",
          refresh: "Refresh",
          empty: "History appears after the first successful analysis.",
          open: "JSON",
          suspicious: "suspicious",
          manual: "manual review",
          rows: "rows",
          failed: "Could not load history.",
        };

  const loadHistory = async () => {
    setIsLoading(true);
    setError("");
    try {
      const response = await fetch("/api/history?limit=5");
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = (await response.json()) as HistoryResponse;
      setReports(Array.isArray(payload.reports) ? payload.reports : []);
    } catch {
      setError(copy.failed);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadHistory();
  }, []);

  useEffect(() => {
    if (status === "success") {
      const timer = window.setTimeout(() => void loadHistory(), 350);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [status]);

  return (
    <section className="section-wrap pb-6">
      <div className="surface-card-soft p-6 sm:p-7">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <p className="eyebrow">{copy.eyebrow}</p>
            <h2 className="mt-3 break-words font-display text-3xl font-bold text-ink">{copy.title}</h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-muted">{copy.description}</p>
          </div>
          <button type="button" onClick={loadHistory} className="secondary-button self-start px-4 py-2.5" disabled={isLoading}>
            <RotateCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            {copy.refresh}
          </button>
        </div>

        {error && (
          <div className="mt-5 rounded-[22px] border border-danger/20 bg-danger/10 px-4 py-3 text-sm font-semibold text-danger">
            {error}
          </div>
        )}

        {!error && reports.length === 0 && (
          <div className="mt-5 flex items-center gap-3 rounded-[22px] border border-dashed border-slate-200 bg-white/70 p-4 text-sm text-muted">
            <Archive className="h-5 w-5 text-accent" />
            {copy.empty}
          </div>
        )}

        {reports.length > 0 && (
          <div className="mt-6 grid gap-3 xl:grid-cols-5">
            {reports.map((report) => (
              <article key={report.id} className="product-card product-card-hover rounded-[22px] p-4">
                <div className="flex items-start justify-between gap-3">
                  <span className="icon-shell h-10 w-10 border-accent/20 bg-accent-soft text-accent">
                    <Clock3 className="h-5 w-5" />
                  </span>
                  <a href={report.history_url} target="_blank" rel="noreferrer" className="badge-soft hover:border-accent/30 hover:text-accent">
                    <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
                    {copy.open}
                  </a>
                </div>
                <p className="mt-4 line-clamp-2 text-sm font-bold leading-6 text-ink">{report.source_label}</p>
                <p className="mt-2 text-xs font-semibold uppercase tracking-[0.12em] text-muted">{formatReportDate(report.created_at)}</p>
                <div className="mt-4 space-y-2 text-xs font-semibold text-muted">
                  <div className="flex items-center justify-between gap-3">
                    <span>{copy.rows}</span>
                    <span className="text-ink">{report.total_count}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span>{copy.suspicious}</span>
                    <span className="text-danger">{report.suspicious_count}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span>{copy.manual}</span>
                    <span className="text-warning">{report.manual_review_count}</span>
                  </div>
                </div>
                <div className="mt-4 inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-ink">
                  <ShieldAlert className="h-3.5 w-3.5 text-accent" />
                  {report.risk_level}
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function formatReportDate(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}
