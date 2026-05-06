import { useId, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { FileUp, UploadCloud } from "lucide-react";
import { useLocale } from "../../i18n";

type FileDropZoneProps = {
  isDragging: boolean;
  disabled?: boolean;
  onDragStateChange: (dragging: boolean) => void;
  onFileSelect: (file: File) => void;
};

const supportedFileTypes =
  ".json,.jsonl,.ndjson,.csv,.tsv,.xlsx,.xls,.html,.htm,application/json,application/x-ndjson,text/csv,text/tab-separated-values,text/html,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel";

export function FileDropZone({
  isDragging,
  disabled,
  onDragStateChange,
  onFileSelect,
}: FileDropZoneProps) {
  const { copy } = useLocale();
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement | null>(null);

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
      className={`group relative block cursor-pointer overflow-hidden rounded-[26px] border border-dashed px-6 py-9 transition duration-300 ${
        isDragging
          ? "border-accent/35 bg-accent-soft/60 shadow-float"
          : "border-slate-200/80 bg-white/76 hover:-translate-y-0.5 hover:border-accent/25 hover:bg-white hover:shadow-float"
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
        <span className="icon-shell h-16 w-16 rounded-3xl border-accent/20 bg-white/90 text-accent shadow-float">
          {isDragging ? <FileUp className="h-8 w-8" /> : <UploadCloud className="h-8 w-8" />}
        </span>
        <h4 className="mt-5 text-lg font-bold text-ink">
          {copy.dataImport.fileDrop.file}
        </h4>
        <p id={helperId} className="mt-2 max-w-md text-sm leading-7 text-muted">
          {copy.dataImport.fileDrop.helper}
        </p>
        <button
          type="button"
          disabled={disabled}
          onClick={(event) => {
            event.stopPropagation();
            inputRef.current?.click();
          }}
          className="secondary-button mt-5 px-4 py-2"
        >
          {copy.dataImport.chooseFile}
        </button>
      </div>

      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept={supportedFileTypes}
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
