import { useEffect, useMemo, useRef, useState } from "react";
import { useLocale } from "../i18n";
import {
  formatBytes,
  parseApiResponse,
  parseFileInput,
  parseJsonInput,
  type ImportSourceTab,
  type ParsedImportResult,
} from "../lib/dataImport";

type ImportStatus = "idle" | "loading" | "success" | "error";
type ValidationState = "success" | "warning" | "error" | null;

type ImportMeta = {
  sourceName: string;
  sizeBytes: number;
  sizeLabel: string;
  result: ParsedImportResult;
};

type DataImportJobResult = {
  result: ParsedImportResult;
  sourceName: string;
  sizeBytes: number;
};

type UseDataImportOptions = {
  recordsJson: string;
  recordsFileName: string;
  onRecordsChange: (value: string) => void;
  onFileNameChange: (value: string) => void;
};

type UseDataImportResult = {
  activeTab: ImportSourceTab;
  apiUrl: string;
  effectiveMeta: ImportMeta | null;
  errorMessage: string;
  isDragging: boolean;
  progress: number;
  status: ImportStatus;
  validationState: ValidationState;
  setActiveTab: (tab: ImportSourceTab) => void;
  setApiUrl: (value: string) => void;
  setIsDragging: (dragging: boolean) => void;
  clearImport: () => void;
  handleApiImport: () => Promise<void>;
  handleFile: (file: File) => Promise<void>;
};

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export function useDataImport({
  recordsJson,
  recordsFileName,
  onRecordsChange,
  onFileNameChange,
}: UseDataImportOptions): UseDataImportResult {
  const { locale } = useLocale();
  const [activeTab, setActiveTab] = useState<ImportSourceTab>("file");
  const [apiUrl, setApiUrl] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [status, setStatus] = useState<ImportStatus>("idle");
  const [progress, setProgress] = useState(0);
  const [errorMessage, setErrorMessage] = useState("");
  const [meta, setMeta] = useState<ImportMeta | null>(null);
  const intervalRef = useRef<number | null>(null);

  const resetTicker = () => {
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  useEffect(() => {
    return () => {
      resetTicker();
    };
  }, []);

  const normalizedPreview = useMemo(() => {
    if (!recordsJson || meta) {
      return null;
    }

    try {
      return parseJsonInput(recordsJson);
    } catch {
      return null;
    }
  }, [meta, recordsJson]);

  const effectiveMeta = meta
    ? meta
    : normalizedPreview
      ? {
          sourceName: recordsFileName || "manual-structured-data.json",
          sizeBytes: recordsJson.length,
          sizeLabel: formatBytes(recordsJson.length),
          result: normalizedPreview,
        }
      : null;

  const validationState: ValidationState =
    effectiveMeta?.result.missingFields.length && effectiveMeta.result.missingFields.length > 0
      ? "error"
      : effectiveMeta?.result.incompleteRows && effectiveMeta.result.incompleteRows > 0
        ? "warning"
        : effectiveMeta
          ? "success"
          : null;

  const runImport = async (job: () => Promise<DataImportJobResult>) => {
    resetTicker();
    setStatus("loading");
    setProgress(14);
    setErrorMessage("");

    intervalRef.current = window.setInterval(() => {
      setProgress((current) => Math.min(current + 11, 86));
    }, 180);

    try {
      const payload = await job();
      resetTicker();
      setProgress(100);
      await sleep(180);

      onRecordsChange(payload.result.normalizedJson);
      onFileNameChange(payload.sourceName);
      setMeta({
        sourceName: payload.sourceName,
        sizeBytes: payload.sizeBytes,
        sizeLabel: formatBytes(payload.sizeBytes),
        result: payload.result,
      });
      setStatus(payload.result.missingFields.length > 0 ? "error" : "success");
      setErrorMessage(
        payload.result.missingFields.length > 0
          ? locale === "ru"
            ? `Не хватает обязательных полей: ${payload.result.missingFields.join(", ")}.`
            : `Missing required fields: ${payload.result.missingFields.join(", ")}.`
          : ""
      );
    } catch (error) {
      resetTicker();
      setStatus("error");
      setProgress(0);
      setMeta(null);
      setErrorMessage(
        error instanceof Error
          ? localizeImportError(error.message, locale)
          : locale === "ru"
            ? "Не удалось импортировать выбранный источник данных."
            : "Could not import the selected data source."
      );
    }
  };

  const handleFile = async (file: File) => {
    await runImport(async () => {
      const sourceName = file.name;
      const sizeBytes = file.size;
      return { result: await parseFileInput(file), sourceName, sizeBytes };
    });
  };

  const handleApiImport = async () => {
    const sourceUrl = apiUrl.trim();
    if (!sourceUrl) {
      setStatus("error");
      setErrorMessage(locale === "ru" ? "Укажи API URL перед запуском импорта." : "Enter an API URL before starting the import.");
      return;
    }

    await runImport(async () => {
      const response = await fetch("/api/import-source", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ url: sourceUrl }),
      });
      if (!response.ok) {
        const errorPayload = await response.json().catch(() => null);
        const backendMessage =
          errorPayload && typeof errorPayload === "object" && "message" in errorPayload
            ? String((errorPayload as { message?: unknown }).message || "")
            : "";
        throw new Error(
          backendMessage ||
            (locale === "ru"
            ? `Не удалось получить API-источник: HTTP ${response.status}.`
            : `Could not fetch the API source: HTTP ${response.status}.`)
        );
      }
      const result = await parseApiResponse(response, sourceUrl);
      return {
        result,
        sourceName: sourceUrl,
        sizeBytes: result.normalizedJson.length,
      };
    });
  };

  const clearImport = () => {
    resetTicker();
    setStatus("idle");
    setProgress(0);
    setErrorMessage("");
    setMeta(null);
    onRecordsChange("");
    onFileNameChange("");
  };

  return {
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
  };
}

function localizeImportError(message: string, locale: "en" | "ru") {
  if (locale === "en") {
    return message;
  }

  const exactMap: Record<string, string> = {
    "Could not import the selected data source.": "Не удалось импортировать выбранный источник данных.",
    "The CSV file is empty.": "CSV-файл пуст.",
    "The JSONL file is empty.": "JSONL-файл пуст.",
    "No worksheet was found in the Excel file.": "В Excel-файле не найден ни один лист.",
    "Could not extract any records. Check the source structure and try again.":
      "Не удалось извлечь ни одной записи. Проверь структуру источника и попробуй снова.",
    "The source does not contain a record array. Expected a JSON array or an object with a `records` field.":
      "Источник не содержит массива записей. Ожидается JSON-массив или объект с полем `records`.",
    "Unsupported file format. Upload JSON, JSONL, CSV, TSV, Excel, or HTML.":
      "Неподдерживаемый формат файла. Загрузите JSON, JSONL, CSV, TSV, Excel или HTML.",
  };

  if (message.startsWith("Invalid JSONL record on line ")) {
    return message.replace("Invalid JSONL record on line ", "Некорректная JSONL-запись в строке ");
  }

  return exactMap[message] || message;
}
