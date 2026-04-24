import { motion } from "framer-motion";
import { useLocale } from "../../i18n";
import type { PreviewRow } from "../../lib/dataImport";

type DataPreviewTableProps = {
  rows: PreviewRow[];
};

const columns: Array<keyof PreviewRow> = ["item_id", "user", "rating", "timestamp", "text", "ip", "geo"];

export function DataPreviewTable({ rows }: DataPreviewTableProps) {
  const { copy } = useLocale();

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32 }}
      className="overflow-hidden rounded-[22px] border border-slate-200/80 bg-white/85"
    >
      <div className="flex items-center justify-between border-b border-slate-200/80 px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-ink">{copy.dataImport.previewTitle}</p>
          <p className="mt-1 text-xs leading-6 text-muted">{copy.dataImport.previewDescription}</p>
        </div>
        <span className="badge-soft">{rows.length} {copy.common.rows}</span>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-left">
          <thead className="border-b border-slate-200/70 bg-slate-50/80">
            <tr>
              {columns.map((column) => (
                <th key={column} className="px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">
                  {copy.dataImport.previewHeaders[column]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200/70">
            {rows.map((row) => (
              <tr key={`${row.item_id}-${row.user}-${row.timestamp}`} className="align-top">
                {columns.map((column) => (
                  <td key={column} className="max-w-[220px] px-4 py-3 text-sm leading-7 text-ink">
                    <div className={column === "text" ? "line-clamp-3 min-w-[220px]" : "whitespace-nowrap"}>{row[column]}</div>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.div>
  );
}
