import { motion } from "framer-motion";
import { DatabaseZap, LoaderCircle } from "lucide-react";
import { useLocale } from "../../i18n";

type LoadingStateProps = {
  progress: number;
};

export function LoadingState({ progress }: LoadingStateProps) {
  const { copy } = useLocale();

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="rounded-[22px] border border-slate-200/80 bg-white/85 p-5"
    >
      <div className="flex items-center gap-3">
        <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-accent-soft text-accent">
          <LoaderCircle className="h-5 w-5 animate-spin" />
        </span>
        <div>
          <p className="text-sm font-semibold text-ink">{copy.dataImport.importLoadingTitle}</p>
          <p className="mt-1 text-sm leading-7 text-muted">{copy.dataImport.importLoadingDescription}</p>
        </div>
      </div>

      <div className="mt-5 h-2.5 rounded-full bg-slate-200/80">
        <motion.div
          className="h-2.5 rounded-full bg-gradient-to-r from-accent to-emerald-400"
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.3 }}
        />
      </div>

      <div className="mt-4 inline-flex items-center gap-2 rounded-full border border-slate-200/70 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-muted">
        <DatabaseZap className="h-3.5 w-3.5 text-accent" />
        {progress}% {copy.common.complete}
      </div>
    </motion.div>
  );
}
