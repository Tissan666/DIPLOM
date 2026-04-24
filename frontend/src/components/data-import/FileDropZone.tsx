import { useId, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { FileUp, UploadCloud } from "lucide-react";
import { useLocale } from "../../i18n";
import type { ImportSourceTab } from "../../lib/dataImport";

type FileDropZoneProps = {
  activeTab: ImportSourceTab;
  isDragging: boolean;
  disabled?: boolean;
  onDragStateChange: (dragging: boolean) => void;
  onFileSelect: (file: File) => void;
};

const tabCopy: Record<Exclude<ImportSourceTab, "api">, { title: string; accept: string }> = {
  json: { title: "Drop a JSON file here or click to upload", accept: ".json,application/json" },
  csv: { title: "Drop a CSV file here or click to upload", accept: ".csv,text/csv" },
  excel: {
    title: "Drop an Excel file here or click to upload",
    accept: ".xlsx,.xls,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel",
  },
  html: { title: "Drop an HTML file here or click to upload", accept: ".html,.htm,text/html" },
};

export function FileDropZone({
  activeTab,
  isDragging,
  disabled,
  onDragStateChange,
  onFileSelect,
}: FileDropZoneProps) {
  const { copy } = useLocale();
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement | null>(null);

  if (activeTab === "api") {
    return null;
  }

  const tabMeta = tabCopy[activeTab];
  const helperId = `${inputId}-helper`;

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      aria-describedby={helperId}
      onDragOver={(event) => {
        event.preventDefault();
        onDragStateChange(true);
      }}
      onDragEnter={(event) => {
        event.preventDefault();
        onDragStateChange(true);
      }}
      onDragLeave={(event) => {
        event.preventDefault();
        onDragStateChange(false);
      }}
      onDrop={(event) => {
        event.preventDefault();
        onDragStateChange(false);
        const file = event.dataTransfer.files?.[0];
        if (file) {
          onFileSelect(file);
        }
      }}
      onClick={() => {
        if (!disabled) {
          inputRef.current?.click();
        }
      }}
      onKeyDown={(event) => {
        if (disabled) {
          return;
        }

        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          inputRef.current?.click();
        }
      }}
      className={`group relative block cursor-pointer overflow-hidden rounded-[24px] border border-dashed px-6 py-8 transition ${
        isDragging
          ? "border-accent/35 bg-accent-soft/60 shadow-float"
          : "border-slate-200/80 bg-white/75 hover:border-accent/25 hover:bg-white"
      } ${disabled ? "cursor-not-allowed opacity-70" : ""}`}
    >
      <AnimatePresence>
        {isDragging && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-gradient-to-br from-accent/10 via-white/0 to-accent/5"
          />
        )}
      </AnimatePresence>

      <div className="relative z-10 mx-auto flex max-w-xl flex-col items-center text-center">
        <span className="flex h-16 w-16 items-center justify-center rounded-3xl bg-white/90 text-accent shadow-float">
          {isDragging ? <FileUp className="h-7 w-7" /> : <UploadCloud className="h-7 w-7" />}
        </span>
        <h4 className="mt-5 text-lg font-semibold text-ink">
          {activeTab === "json"
            ? copy.dataImport.fileDrop.json
            : activeTab === "csv"
              ? copy.dataImport.fileDrop.csv
              : activeTab === "excel"
                ? copy.dataImport.fileDrop.excel
                : copy.dataImport.fileDrop.html}
        </h4>
        <p id={helperId} className="mt-2 max-w-md text-sm leading-7 text-muted">
          {activeTab.toUpperCase()} {copy.dataImport.fileDrop.helper}
        </p>
        <button
          type="button"
          disabled={disabled}
          onClick={(event) => {
            event.stopPropagation();
            inputRef.current?.click();
          }}
          className="mt-5 inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-ink transition group-hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {copy.dataImport.chooseFile}
        </button>
      </div>

      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept={tabMeta.accept}
        className="sr-only"
        disabled={disabled}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) {
            onFileSelect(file);
          }
          event.target.value = "";
        }}
      />
    </div>
  );
}
