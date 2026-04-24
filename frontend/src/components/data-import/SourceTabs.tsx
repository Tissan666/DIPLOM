import { motion } from "framer-motion";
import { FileCode2, FileJson2, FileSpreadsheet, Link2 } from "lucide-react";
import type { ImportSourceTab } from "../../lib/dataImport";

type SourceTabsProps = {
  activeTab: ImportSourceTab;
  onChange: (tab: ImportSourceTab) => void;
};

const tabs: Array<{
  value: ImportSourceTab;
  label: string;
  icon: typeof FileJson2;
}> = [
  { value: "json", label: "JSON", icon: FileJson2 },
  { value: "csv", label: "CSV", icon: FileSpreadsheet },
  { value: "excel", label: "Excel", icon: FileSpreadsheet },
  { value: "html", label: "HTML", icon: FileCode2 },
  { value: "api", label: "API", icon: Link2 },
];

export function SourceTabs({ activeTab, onChange }: SourceTabsProps) {
  return (
    <div className="grid grid-cols-2 gap-2 rounded-[22px] border border-slate-200/80 bg-white/75 p-2 sm:grid-cols-5">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const active = tab.value === activeTab;

        return (
          <button
            key={tab.value}
            type="button"
            onClick={() => onChange(tab.value)}
            className={`relative inline-flex items-center justify-center gap-2 rounded-2xl px-3 py-3 text-sm font-semibold transition ${
              active ? "text-ink" : "text-muted hover:text-ink"
            }`}
          >
            {active && (
              <motion.span
                layoutId="import-source-tab"
                className="absolute inset-0 rounded-2xl border border-accent/15 bg-accent-soft/80 shadow-float"
                transition={{ type: "spring", stiffness: 340, damping: 28 }}
              />
            )}
            <span className="relative z-10 inline-flex items-center gap-2">
              <Icon className={`h-4 w-4 ${active ? "text-accent" : "text-muted"}`} />
              {tab.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}
