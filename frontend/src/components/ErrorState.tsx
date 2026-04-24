import { motion } from "framer-motion";
import { RefreshCcw, TriangleAlert } from "lucide-react";
import { useLocale } from "../i18n";
import type { AnalysisErrorCode } from "../types/analysis";

type ErrorStateProps = {
  errorCode: AnalysisErrorCode | null;
  message: string;
  onRetry: () => void;
};

export function ErrorState({ errorCode, message, onRetry }: ErrorStateProps) {
  const { copy } = useLocale();
  const typedError = errorCode ? copy.errorState.errors[errorCode] : null;
  const displayMessage = typedError?.message || message;
  const helperMessage = typedError?.helper || copy.errorState.helper;

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
    </motion.div>
  );
}
