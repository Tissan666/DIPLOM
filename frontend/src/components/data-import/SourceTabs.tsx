import { motion } from "framer-motion";
import { FileUp, Link2 } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useLocale } from "../../i18n";
import type { ImportSourceTab } from "../../lib/dataImport";

type SourceTabsProps = {
  activeTab: ImportSourceTab;
  onChange: (tab: ImportSourceTab) => void;
};

export function SourceTabs({ activeTab, onChange }: SourceTabsProps) {
  const { copy } = useLocale();
  const tabs: Array<{
    value: ImportSourceTab;
    label: string;
    icon: LucideIcon;
  }> = [
    { value: "file", label: copy.dataImport.sources.file, icon: FileUp },
    { value: "api", label: copy.dataImport.sources.api, icon: Link2 },
  ];

  return (
    <div className="grid grid-cols-2 gap-2 rounded-[24px] border border-slate-200/80 bg-white/76 p-2 shadow-soft">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const active = tab.value === activeTab;

        return (
          <button
            key={tab.value}
            type="button"
            onClick={() => onChange(tab.value)}
            className={`relative inline-flex items-center justify-center gap-2 rounded-[18px] px-3 py-3 text-sm font-bold transition ${
              active ? "text-ink" : "text-muted hover:text-ink"
            }`}
          >
            {active && (
              <motion.span
                layoutId="import-source-tab"
                className="absolute inset-0 rounded-[18px] border border-accent/15 bg-accent-soft/85 shadow-float"
                transition={{ type: "spring", stiffness: 340, damping: 28 }}
              />
            )}
            <span className="relative z-10 inline-flex items-center gap-2">
              <Icon className={`h-5 w-5 ${active ? "text-accent" : "text-muted"}`} />
              {tab.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}
