import { motion } from "framer-motion";
import { FileText, Gauge, PlayCircle, RefreshCcw, TriangleAlert } from "lucide-react";
import { useLocale } from "../i18n";
import type { AnalysisErrorCode } from "../types/analysis";

type ErrorStateProps = {
  errorCode: AnalysisErrorCode | null;
  message: string;
  onLoadDemo: () => void;
  onRetry: () => void;
  onUseFastRetry: () => void;
  onUseHtmlSnapshot: () => void;
};

const SCRAPING_RECOVERY_CODES: Array<AnalysisErrorCode> = [
  "SCRAPING_BLOCKED",
  "SCRAPINGBEE_NOT_CONFIGURED",
  "SCRAPEDO_NOT_CONFIGURED",
  "SCRAPING_FETCH_FAILED",
  "SCRAPING_RATE_LIMITED",
  "SCRAPING_SERVICE_NOT_CONFIGURED",
  "SCRAPING_TIMEOUT",
];

export function ErrorState({
  errorCode,
  message,
  onLoadDemo,
  onRetry,
  onUseFastRetry,
  onUseHtmlSnapshot,
}: ErrorStateProps) {
  const { copy, locale } = useLocale();
  const typedError = errorCode ? copy.errorState.errors[errorCode] : null;
  const displayMessage = typedError?.message || message;
  const helperMessage = typedError?.helper || copy.errorState.helper;
  const isScrapingRecovery = Boolean(errorCode && SCRAPING_RECOVERY_CODES.includes(errorCode));
  const recoveryCopy =
    locale === "ru"
      ? {
          title: "Как продолжить без тупика",
          htmlTitle: "HTML-снимок",
          htmlText: "Сохрани страницу в браузере или вставь HTML вручную. Анализ пройдет без внешнего сборщика.",
          fastTitle: "Быстрый повтор",
          fastText: "Снизит ожидание и глубину сбора, если маркетплейс отвечает нестабильно.",
          demoTitle: "Демо-отчет",
          demoText: "Покажет полный сценарий защиты, даже если внешний сайт сейчас не отдает страницу.",
        }
      : {
          title: "Continue without a dead end",
          htmlTitle: "HTML snapshot",
          htmlText: "Save the page in the browser or paste HTML manually. Analysis will run without the external collector.",
          fastTitle: "Fast retry",
          fastText: "Reduces wait time and collection depth when the marketplace responds unstably.",
          demoTitle: "Demo report",
          demoText: "Shows the full protection workflow even when the external site is unavailable.",
        };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45 }}
      className="rounded-[28px] border border-danger/20 bg-danger/10 p-8"
    >
      <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
        <div className="flex items-start gap-4">
          <span className="mt-0.5 flex h-12 w-12 items-center justify-center rounded-2xl bg-white/70 text-danger">
            <TriangleAlert className="h-6 w-6" />
          </span>
          <div>
            <h3 className="font-display text-3xl text-ink">{copy.errorState.title}</h3>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-muted">{displayMessage}</p>
            <p className="mt-2 text-sm leading-7 text-muted">{helperMessage}</p>
          </div>
        </div>

        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center justify-center gap-2 rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-slate-800"
        >
          <RefreshCcw className="h-4 w-4" />
          {copy.common.retry}
        </button>
      </div>

      {isScrapingRecovery && (
        <div className="mt-6 rounded-[24px] border border-white/70 bg-white/72 p-4 shadow-soft">
          <p className="text-sm font-bold text-ink">{recoveryCopy.title}</p>
          <div className="mt-3 grid gap-3 lg:grid-cols-3">
            <RecoveryButton icon={FileText} title={recoveryCopy.htmlTitle} text={recoveryCopy.htmlText} onClick={onUseHtmlSnapshot} />
            <RecoveryButton icon={Gauge} title={recoveryCopy.fastTitle} text={recoveryCopy.fastText} onClick={onUseFastRetry} />
            <RecoveryButton icon={PlayCircle} title={recoveryCopy.demoTitle} text={recoveryCopy.demoText} onClick={onLoadDemo} />
          </div>
        </div>
      )}
    </motion.div>
  );
}

function RecoveryButton({
  icon: Icon,
  title,
  text,
  onClick,
}: {
  icon: typeof FileText;
  title: string;
  text: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group rounded-[20px] border border-slate-200/80 bg-white/88 p-4 text-left transition hover:-translate-y-0.5 hover:border-accent/25 hover:bg-white hover:shadow-soft"
    >
      <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-accent-soft text-accent transition group-hover:bg-accent group-hover:text-white">
        <Icon className="h-5 w-5" />
      </span>
      <span className="mt-3 block text-sm font-bold text-ink">{title}</span>
      <span className="mt-1 block text-xs leading-6 text-muted">{text}</span>
    </button>
  );
}
