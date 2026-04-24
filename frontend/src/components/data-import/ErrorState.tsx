import { motion } from "framer-motion";
import { RefreshCcw, TriangleAlert } from "lucide-react";
import { useLocale } from "../../i18n";

type ErrorStateProps = {
  message: string;
  onRetry: () => void;
};

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  const { copy } = useLocale();

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28 }}
      className="rounded-[22px] border border-danger/20 bg-danger/10 p-5"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-11 w-11 items-center justify-center rounded-2xl bg-white/80 text-danger">
            <TriangleAlert className="h-5 w-5" />
          </span>
          <div>
            <p className="text-sm font-semibold text-ink">{copy.dataImport.importFailedTitle}</p>
            <p className="mt-1 text-sm leading-7 text-muted">{message}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center justify-center gap-2 rounded-full bg-ink px-4 py-2.5 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-slate-800"
        >
          <RefreshCcw className="h-4 w-4" />
          {copy.common.tryAgain}
        </button>
      </div>
    </motion.div>
  );
}
