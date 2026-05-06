import { motion } from "framer-motion";
import { CheckCircle2, Database, Link2, Play, Upload } from "lucide-react";
import { useDataImport } from "../../hooks/useDataImport";
import { useLocale } from "../../i18n";
import { DataPreviewTable } from "./DataPreviewTable";
import { ErrorState } from "./ErrorState";
import { FileDropZone } from "./FileDropZone";
import { LoadingState } from "./LoadingState";
import { SourceTabs } from "./SourceTabs";
import { ValidationAlert } from "./ValidationAlert";

type DataImportPanelProps = {
  recordsJson: string;
  recordsFileName: string;
  disabled?: boolean;
  onRecordsChange: (value: string) => void;
  onFileNameChange: (value: string) => void;
  onRunAnalysis: () => void;
};

export function DataImportPanel({
  recordsJson,
  recordsFileName,
  disabled,
  onRecordsChange,
  onFileNameChange,
  onRunAnalysis,
}: DataImportPanelProps) {
  const { copy, locale } = useLocale();
  const {
    activeTab,
    apiUrl,
    effectiveMeta,
    errorMessage,
    isDragging,
    progress,
    status,
    validationState,
    setActiveTab,
    setApiUrl,
    setIsDragging,
    clearImport,
    handleApiImport,
    handleFile,
  } = useDataImport({
    recordsJson,
    recordsFileName,
    onRecordsChange,
    onFileNameChange,
  });

  return (
    <div className="space-y-4">
      <div className="product-card p-5 shadow-soft">
        <div className="flex items-start gap-4">
          <span className="icon-shell border-accent/20 bg-accent-soft text-accent">
            <Database className="h-6 w-6" />
          </span>
          <div className="min-w-0">
            <p className="text-base font-bold text-ink">{copy.dataImport.title}</p>
            <p className="mt-1 text-sm leading-7 text-muted">{copy.dataImport.description}</p>
          </div>
        </div>

        <div className="mt-5">
          <SourceTabs activeTab={activeTab} onChange={setActiveTab} />
        </div>

        <div className="mt-5">
          {activeTab === "api" ? (
            <div className="product-card p-5">
              <div className="flex items-start gap-3">
                <span className="icon-shell h-11 w-11 border-accent/20 bg-accent-soft text-accent">
                  <Link2 className="h-5 w-5" />
                </span>
                <div>
                  <p className="text-sm font-bold text-ink">{copy.dataImport.fetchTitle}</p>
                  <p className="mt-1 text-sm leading-7 text-muted">{copy.dataImport.fetchDescription}</p>
                </div>
              </div>

              <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                <input
                  value={apiUrl}
                  onChange={(event) => setApiUrl(event.target.value)}
                  disabled={disabled}
                  className="w-full rounded-2xl border border-slate-200/80 bg-white/90 px-4 py-3 text-sm text-ink outline-none transition placeholder:text-slate-400 focus:border-accent/40 focus:ring-4 focus:ring-accent/10"
                  placeholder={copy.dataImport.apiPlaceholder}
                />
                <button
                  type="button"
                  disabled={disabled || status === "loading"}
                  onClick={handleApiImport}
                  className="primary-button justify-center px-5 py-3"
                >
                  <Upload className="h-4 w-4" />
                  {copy.dataImport.fetchAction}
                </button>
              </div>
            </div>
          ) : (
            <FileDropZone
              isDragging={isDragging}
              disabled={disabled || status === "loading"}
              onDragStateChange={setIsDragging}
              onFileSelect={handleFile}
            />
          )}
        </div>
      </div>

      {status === "loading" && <LoadingState progress={progress} />}

      {status === "error" && errorMessage && !effectiveMeta && <ErrorState message={errorMessage} onRetry={clearImport} />}

      {status === "error" && errorMessage && effectiveMeta && validationState !== "error" && (
        <ErrorState message={errorMessage} onRetry={clearImport} />
      )}

      {effectiveMeta && (
        <div className="space-y-4">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.32 }}
            className="product-card p-5"
          >
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <div className="inline-flex items-center gap-2 rounded-full border border-success/20 bg-success/10 px-3 py-1 text-xs font-semibold text-success">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    {copy.common.sourceLoaded}
                  </div>
                  <p className="mt-3 text-base font-bold text-ink">{effectiveMeta.sourceName}</p>
                  <p className="mt-1 text-sm leading-7 text-muted">
                    {effectiveMeta.result.records.length} {copy.common.rows}, {effectiveMeta.sizeLabel}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={clearImport}
                  className="secondary-button justify-center px-4 py-2.5 hover:border-danger/20 hover:text-danger"
                  >
                  {copy.common.clear}
                </button>
                <button
                  type="button"
                  disabled={disabled || validationState === "error"}
                  onClick={onRunAnalysis}
                  className="primary-button justify-center px-5 py-2.5"
                >
                  <Play className="h-4 w-4" />
                  {copy.dataImport.runAnalysis}
                </button>
              </div>
            </div>
          </motion.div>

          {validationState === "success" && (
            <ValidationAlert
              status="success"
              title={copy.dataImport.readyTitle}
              description={copy.dataImport.readyDescription}
            />
          )}

          {validationState === "warning" && (
            <ValidationAlert
              status="warning"
              title={copy.dataImport.warningTitle}
              description={
                locale === "ru"
                  ? `Часть строк неполная: в ${effectiveMeta.result.incompleteRows} записях отсутствует как минимум одно обязательное значение.`
                  : `Some rows are incomplete: ${effectiveMeta.result.incompleteRows} record(s) are missing at least one required value.`
              }
            />
          )}

          {validationState === "error" && (
            <>
              <ValidationAlert
                status="error"
                title={copy.dataImport.errorTitle}
                description={copy.dataImport.errorDescription}
                missingFields={effectiveMeta.result.missingFields}
              />
              {errorMessage && <ErrorState message={errorMessage} onRetry={clearImport} />}
            </>
          )}

          <DataPreviewTable rows={effectiveMeta.result.previewRows.slice(0, 8)} />
        </div>
      )}
    </div>
  );
}
