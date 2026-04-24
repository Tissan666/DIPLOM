import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { useLocale } from "../i18n";

export function EmptyState() {
  const { copy } = useLocale();

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45 }}
      className="surface-card-soft p-8"
    >
      <div className="mx-auto max-w-xl text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-soft text-accent">
          <Sparkles className="h-6 w-6" />
        </div>
        <h3 className="mt-5 font-display text-3xl text-ink">{copy.emptyState.title}</h3>
        <p className="mt-3 text-sm leading-7 text-muted">{copy.emptyState.description}</p>

        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {copy.emptyState.cards.map((item) => (
            <div key={item} className="rounded-3xl border border-dashed border-slate-200/80 bg-white/70 p-4 text-sm text-muted">
              {item}
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}
