import { motion } from "framer-motion";
import { ArrowRight, CircleGauge, ClipboardCheck, FileSearch, ListChecks, ScanSearch } from "lucide-react";
import { useLocale } from "../i18n";

type EmptyStateProps = {
  onSetup: () => void;
  onLoadDemo: () => void;
};

const reportCardVisuals = [
  {
    Icon: CircleGauge,
    tone: "icon-risk",
  },
  {
    Icon: ScanSearch,
    tone: "icon-analysis",
  },
  {
    Icon: ListChecks,
    tone: "icon-suspicious",
  },
  {
    Icon: ClipboardCheck,
    tone: "icon-decision",
  },
] as const;

export function EmptyState({ onSetup, onLoadDemo }: EmptyStateProps) {
  const { copy } = useLocale();

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45 }}
      className="rounded-[30px] border border-slate-200/80 bg-white/72 p-5 shadow-soft sm:p-6"
    >
      <div className="grid gap-6 lg:grid-cols-[0.92fr_1.08fr] lg:items-center">
        <div className="rounded-[26px] border border-accent/20 bg-accent-soft/74 p-5 sm:p-6">
          <div className="icon-shell border-accent/15 bg-white text-accent">
            <FileSearch className="h-6 w-6" />
          </div>
          <p className="mt-5 text-[0.68rem] font-bold uppercase tracking-[0.28em] text-accent">
            {copy.emptyState.eyebrow}
          </p>
          <h3 className="mt-3 max-w-xl font-display text-2xl leading-tight text-ink sm:text-3xl">
            {copy.emptyState.title}
          </h3>
          <p className="mt-3 max-w-xl text-sm leading-7 text-muted">{copy.emptyState.description}</p>

          <div className="mt-6 flex flex-col gap-3 sm:flex-row">
            <button className="primary-button justify-center" type="button" onClick={onSetup}>
              {copy.emptyState.setupAction}
              <ArrowRight className="h-4 w-4" />
            </button>
            <button className="secondary-button justify-center" type="button" onClick={onLoadDemo}>
              {copy.emptyState.demoAction}
            </button>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {copy.emptyState.cards.map((item, index) => {
            const visual = reportCardVisuals[index] ?? reportCardVisuals[0];
            const Icon = visual.Icon;

            return (
              <div key={item.title} className="product-card product-card-hover p-4">
                <div className={`icon-shell ${visual.tone}`}>
                  <Icon className="h-6 w-6" aria-hidden="true" />
                </div>
                <h4 className="mt-4 text-sm font-bold text-ink">{item.title}</h4>
                <p className="mt-2 text-xs leading-6 text-muted">{item.description}</p>
              </div>
            );
          })}
        </div>
      </div>
    </motion.div>
  );
}
