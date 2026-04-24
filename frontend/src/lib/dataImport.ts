export type ImportSourceTab = "json" | "csv" | "excel" | "html" | "api";

export type NormalizedImportRecord = {
  item_id: string;
  user_id: string;
  rating: number | null;
  timestamp: string;
  review_text: string;
  ip_address: string;
  geo_country: string;
  geo: string;
};

export type PreviewRow = {
  item_id: string;
  user: string;
  rating: string;
  timestamp: string;
  text: string;
  ip: string;
  geo: string;
};

export type ParsedImportResult = {
  records: NormalizedImportRecord[];
  previewRows: PreviewRow[];
  normalizedJson: string;
  missingFields: string[];
  incompleteRows: number;
};

const REQUIRED_FIELDS: Array<keyof Pick<NormalizedImportRecord, "item_id" | "review_text" | "rating" | "timestamp">> = [
  "item_id",
  "review_text",
  "rating",
  "timestamp",
];

const REQUIRED_FIELD_LABELS: Record<(typeof REQUIRED_FIELDS)[number], string> = {
  item_id: "item_id",
  review_text: "text",
  rating: "rating",
  timestamp: "timestamp",
};

const EXPECTED_FIELDS = ["item_id", "user", "rating", "timestamp", "text", "ip", "geo"] as const;
const EMPTY_PREVIEW_VALUE = "-";

let xlsxModulePromise: Promise<typeof import("xlsx")> | null = null;

async function loadXlsxModule(): Promise<typeof import("xlsx")> {
  if (!xlsxModulePromise) {
    xlsxModulePromise = import("xlsx");
  }

  return xlsxModulePromise;
}

function stringifyValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "string") {
    return value.trim();
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return "";
}

function numberValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  const raw = stringifyValue(value);
  if (!raw) {
    return null;
  }

  const match = raw.replace(",", ".").match(/-?\d+(\.\d+)?/);
  if (!match) {
    return null;
  }

  const parsed = Number(match[0]);
  return Number.isFinite(parsed) ? parsed : null;
}

function hasMeaningfulValue(value: unknown): boolean {
  if (value === null || value === undefined) {
    return false;
  }
  if (typeof value === "number") {
    return Number.isFinite(value);
  }
  return stringifyValue(value).length > 0;
}

function extractCandidate(record: Record<string, unknown>, keys: string[]): unknown {
  for (const key of keys) {
    if (key in record && hasMeaningfulValue(record[key])) {
      return record[key];
    }
  }

  return undefined;
}

function normalizeRecord(raw: Record<string, unknown>, index: number, fallbackItemId = ""): NormalizedImportRecord {
  const itemId = stringifyValue(
    extractCandidate(raw, ["item_id", "itemId", "sku", "product_id", "productId", "item", "asin"])
  );
  const userId = stringifyValue(
    extractCandidate(raw, ["user_id", "user", "author", "reviewer", "username", "profile", "customer"])
  );
  const rating = numberValue(
    extractCandidate(raw, ["rating", "score", "stars", "value", "reviewRating", "ratingValue"])
  );
  const timestamp = stringifyValue(
    extractCandidate(raw, ["timestamp", "date", "created_at", "createdAt", "datePublished", "time"])
  );
  const reviewText = stringifyValue(
    extractCandidate(raw, ["review_text", "text", "review", "comment", "body", "content", "reviewBody", "message"])
  );
  const ipAddress = stringifyValue(extractCandidate(raw, ["ip_address", "ip", "ipAddress"]));
  const geo = stringifyValue(extractCandidate(raw, ["geo", "geo_country", "location", "country", "region"]));

  return {
    item_id: itemId || fallbackItemId || "",
    user_id: userId || `user-${index + 1}`,
    rating,
    timestamp,
    review_text: reviewText,
    ip_address: ipAddress,
    geo_country: geo,
    geo,
  };
}

function toPreviewRow(record: NormalizedImportRecord): PreviewRow {
  return {
    item_id: record.item_id || EMPTY_PREVIEW_VALUE,
    user: record.user_id || EMPTY_PREVIEW_VALUE,
    rating: record.rating === null ? EMPTY_PREVIEW_VALUE : record.rating.toFixed(1),
    timestamp: record.timestamp || EMPTY_PREVIEW_VALUE,
    text: record.review_text || EMPTY_PREVIEW_VALUE,
    ip: record.ip_address || EMPTY_PREVIEW_VALUE,
    geo: record.geo_country || record.geo || EMPTY_PREVIEW_VALUE,
  };
}

function validateRecords(records: NormalizedImportRecord[]): { missingFields: string[]; incompleteRows: number } {
  const missingFields = REQUIRED_FIELDS
    .filter((field) => !records.some((record) => hasMeaningfulValue(record[field])))
    .map((field) => REQUIRED_FIELD_LABELS[field]);

  const incompleteRows = records.filter(
    (record) =>
      !record.item_id || !record.review_text || !record.timestamp || record.rating === null || !Number.isFinite(record.rating)
  ).length;

  return { missingFields, incompleteRows };
}

function finalizeRecords(records: NormalizedImportRecord[]): ParsedImportResult {
  if (!records.length) {
    throw new Error("Could not extract any records. Check the source structure and try again.");
  }

  const { missingFields, incompleteRows } = validateRecords(records);

  return {
    records,
    previewRows: records.slice(0, 10).map(toPreviewRow),
    normalizedJson: JSON.stringify(records, null, 2),
    missingFields,
    incompleteRows,
  };
}

function extractRecordsPayload(payload: unknown): unknown[] {
  if (Array.isArray(payload)) {
    return payload;
  }

  if (payload && typeof payload === "object") {
    const typed = payload as Record<string, unknown>;

    if (Array.isArray(typed.records)) {
      return typed.records;
    }
    if (typed.data && typeof typed.data === "object") {
      const data = typed.data as Record<string, unknown>;
      if (Array.isArray(data.records)) {
        return data.records;
      }
      if (Array.isArray(data.items)) {
        return data.items;
      }
    }
    if (Array.isArray(typed.items)) {
      return typed.items;
    }
    if (Array.isArray(typed.results)) {
      return typed.results;
    }

    if (
      Object.keys(typed).some(
        (key) =>
          EXPECTED_FIELDS.includes(key as (typeof EXPECTED_FIELDS)[number]) || key === "user_id" || key === "review_text"
      )
    ) {
      return [typed];
    }
  }

  throw new Error("The source does not contain a record array. Expected a JSON array or an object with a `records` field.");
}

function parseCsvLine(line: string, delimiter: string): string[] {
  const values: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    const next = line[index + 1];

    if (char === '"') {
      if (inQuotes && next === '"') {
        current += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (char === delimiter && !inQuotes) {
      values.push(current.trim());
      current = "";
      continue;
    }

    current += char;
  }

  values.push(current.trim());
  return values;
}

function detectDelimiter(line: string): string {
  const candidates = [",", ";", "\t"];
  const scored = candidates.map((candidate) => ({
    candidate,
    count: parseCsvLine(line, candidate).length,
  }));
  return scored.sort((left, right) => right.count - left.count)[0]?.candidate || ",";
}

function parseCsvRecords(text: string): Record<string, unknown>[] {
  const sanitized = text.replace(/^\uFEFF/, "").trim();
  if (!sanitized) {
    throw new Error("The CSV file is empty.");
  }

  const lines = sanitized.split(/\r?\n/).filter((line) => line.trim().length > 0);
  const delimiter = detectDelimiter(lines[0]);
  const headers = parseCsvLine(lines[0], delimiter).map((header) => header.trim());
  const rows = lines.slice(1).map((line) => parseCsvLine(line, delimiter));

  return rows.map((row) => {
    const record: Record<string, unknown> = {};
    headers.forEach((header, index) => {
      record[header] = row[index] || "";
    });
    return record;
  });
}

function findReviewSchemaNodes(node: unknown): Record<string, unknown>[] {
  if (!node) {
    return [];
  }
  if (Array.isArray(node)) {
    return node.flatMap(findReviewSchemaNodes);
  }
  if (typeof node !== "object") {
    return [];
  }

  const record = node as Record<string, unknown>;
  const typeValue = stringifyValue(record["@type"]).toLowerCase();
  const current = typeValue.includes("review") ? [record] : [];

  return [
    ...current,
    ...findReviewSchemaNodes(record.review),
    ...findReviewSchemaNodes(record.reviews),
    ...findReviewSchemaNodes(record.itemReviewed),
    ...Object.values(record).flatMap(findReviewSchemaNodes),
  ];
}

function schemaToRawRecord(schema: Record<string, unknown>, fallbackItemId: string): Record<string, unknown> {
  const author =
    schema.author && typeof schema.author === "object"
      ? stringifyValue((schema.author as Record<string, unknown>).name)
      : stringifyValue(schema.author);
  const ratingObject =
    schema.reviewRating && typeof schema.reviewRating === "object" ? (schema.reviewRating as Record<string, unknown>) : {};
  const reviewedObject =
    schema.itemReviewed && typeof schema.itemReviewed === "object" ? (schema.itemReviewed as Record<string, unknown>) : {};

  return {
    item_id:
      stringifyValue(reviewedObject.sku) ||
      stringifyValue(reviewedObject.productID) ||
      stringifyValue(reviewedObject.name) ||
      fallbackItemId,
    user: author,
    rating: ratingObject.ratingValue || ratingObject.value || schema.ratingValue,
    timestamp: schema.datePublished || schema.timestamp || "",
    text: schema.reviewBody || schema.text || schema.description || "",
  };
}

function parseHtmlRecords(text: string, sourceLabel = "html-import"): Record<string, unknown>[] {
  const parser = new DOMParser();
  const document = parser.parseFromString(text, "text/html");
  const fallbackItemId = document.title?.trim() || sourceLabel;

  const schemaRecords = Array.from(document.querySelectorAll('script[type="application/ld+json"]'))
    .flatMap((script) => {
      try {
        return findReviewSchemaNodes(JSON.parse(script.textContent || ""));
      } catch {
        return [];
      }
    })
    .map((schema) => schemaToRawRecord(schema, fallbackItemId));

  if (schemaRecords.length) {
    return schemaRecords;
  }

  const table = document.querySelector("table");
  if (table) {
    const rows = Array.from(table.querySelectorAll("tr"));
    if (rows.length > 1) {
      const headers = Array.from(rows[0].querySelectorAll("th, td")).map((cell) => cell.textContent?.trim() || "");
      const records = rows.slice(1).map((row) => {
        const record: Record<string, unknown> = {};
        Array.from(row.querySelectorAll("td")).forEach((cell, index) => {
          record[headers[index] || `column_${index + 1}`] = cell.textContent?.trim() || "";
        });
        return record;
      });
      if (records.length) {
        return records;
      }
    }
  }

  return Array.from(
    document.querySelectorAll(
      '[itemprop="review"], .review, .review-item, [data-review], article, .review-card, li[class*="review"]'
    )
  )
    .slice(0, 50)
    .map((node, index) => {
      const root = node as HTMLElement;
      const author =
        root.querySelector('[itemprop="author"], .author, .user, .review-author, [data-author]')?.textContent?.trim() || "";
      const textValue =
        root.querySelector('[itemprop="reviewBody"], .review-text, .content, p, [data-text]')?.textContent?.trim() ||
        root.textContent?.trim() ||
        "";
      const ratingNode =
        root.querySelector('[itemprop="ratingValue"], [data-rating], .rating, .stars, [aria-label*="out of 5"]')
          ?.textContent?.trim() || "";
      const timeValue =
        root.querySelector("time")?.getAttribute("datetime") ||
        root.querySelector("time")?.textContent?.trim() ||
        root.querySelector(".date, [data-date]")?.textContent?.trim() ||
        "";

      return {
        item_id: fallbackItemId || `html-item-${index + 1}`,
        user: author || `html-user-${index + 1}`,
        rating: ratingNode,
        timestamp: timeValue,
        text: textValue,
      };
    })
    .filter((record) => stringifyValue(record.text).length > 0);
}

export function parseJsonInput(text: string): ParsedImportResult {
  const payload = JSON.parse(text);
  const records = extractRecordsPayload(payload).map((row, index) =>
    normalizeRecord((row || {}) as Record<string, unknown>, index)
  );
  return finalizeRecords(records);
}

export function parseCsvInput(text: string): ParsedImportResult {
  const records = parseCsvRecords(text).map((row, index) => normalizeRecord(row, index));
  return finalizeRecords(records);
}

export async function parseExcelInput(buffer: ArrayBuffer): Promise<ParsedImportResult> {
  const XLSX = await loadXlsxModule();
  const workbook = XLSX.read(buffer, { type: "array" });
  const firstSheet = workbook.SheetNames[0];
  if (!firstSheet) {
    throw new Error("No worksheet was found in the Excel file.");
  }

  const sheet = workbook.Sheets[firstSheet];
  const rows = XLSX.utils.sheet_to_json<Record<string, unknown>>(sheet, { defval: "" });
  const records = rows.map((row, index) => normalizeRecord(row, index));
  return finalizeRecords(records);
}

export function parseHtmlInput(text: string, sourceLabel?: string): ParsedImportResult {
  const records = parseHtmlRecords(text, sourceLabel).map((row, index) =>
    normalizeRecord(row, index, sourceLabel || "html-import")
  );
  return finalizeRecords(records);
}

export async function parseApiResponse(response: Response, sourceUrl: string): Promise<ParsedImportResult> {
  const contentType = response.headers.get("content-type")?.toLowerCase() || "";
  const urlLower = sourceUrl.toLowerCase();

  if (contentType.includes("application/json") || urlLower.endsWith(".json")) {
    return parseJsonInput(await response.text());
  }
  if (contentType.includes("text/csv") || urlLower.endsWith(".csv")) {
    return parseCsvInput(await response.text());
  }
  if (
    contentType.includes("spreadsheetml") ||
    contentType.includes("application/vnd.ms-excel") ||
    urlLower.endsWith(".xlsx") ||
    urlLower.endsWith(".xls")
  ) {
    return parseExcelInput(await response.arrayBuffer());
  }

  return parseHtmlInput(await response.text(), sourceUrl);
}

export function formatBytes(bytes: number): string {
  if (!bytes || bytes < 1024) {
    return `${bytes || 0} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function expectedStructureLabel(): string {
  return EXPECTED_FIELDS.join(", ");
}
