export type ImportSourceTab = "file" | "api";

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

const FIELD_ALIASES = {
  item_id: [
    "item_id",
    "itemId",
    "sku",
    "product_id",
    "productId",
    "productName",
    "asin",
    "article",
    "vendorCode",
    "артикул",
    "название товара",
    "id товара",
    "код товара",
  ],
  user_id: [
    "user_id",
    "user",
    "author",
    "reviewer",
    "username",
    "profile",
    "customer",
    "client",
    "buyer",
    "пользователь",
    "автор",
    "клиент",
    "покупатель",
    "имя",
    "ник",
  ],
  rating: [
    "rating",
    "score",
    "stars",
    "value",
    "reviewRating",
    "ratingValue",
    "оценка",
    "рейтинг",
    "звезды",
    "звёзды",
    "балл",
    "баллы",
  ],
  timestamp: [
    "timestamp",
    "date",
    "created_at",
    "createdAt",
    "datePublished",
    "time",
    "published",
    "дата",
    "время",
    "дата отзыва",
    "дата публикации",
    "опубликовано",
  ],
  review_text: [
    "review_text",
    "text",
    "review",
    "comment",
    "body",
    "content",
    "reviewBody",
    "message",
    "feedback",
    "отзыв",
    "текст",
    "текст отзыва",
    "комментарий",
    "сообщение",
    "описание",
    "мнение",
  ],
  ip_address: ["ip_address", "ip", "ipAddress", "ip адрес", "ip-адрес", "адрес ip"],
  geo: ["geo", "geo_country", "location", "country", "region", "city", "страна", "регион", "город", "локация", "гео"],
} satisfies Record<"item_id" | "user_id" | "rating" | "timestamp" | "review_text" | "ip_address" | "geo", string[]>;

type AutoFieldKey = keyof typeof FIELD_ALIASES;

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

function wordCount(value: string): number {
  return value.split(/\s+/).filter(Boolean).length;
}

function normalizeKeyName(key: string): string {
  return key
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/ё/g, "е")
    .replace(/[^a-zа-я0-9]+/g, "");
}

function isRatingLike(value: unknown): boolean {
  const rating = numberValue(value);
  return rating !== null && rating >= 1 && rating <= 5;
}

function isDateLike(value: unknown): boolean {
  const raw = stringifyValue(value);
  if (raw.length < 6) {
    return false;
  }

  if (/\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b/.test(raw) || /\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b/.test(raw)) {
    return true;
  }

  if (/\b\d{1,2}\s+(январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)/i.test(raw)) {
    return true;
  }

  if (/^\d{10,13}$/.test(raw)) {
    return true;
  }

  const parsed = Date.parse(raw);
  return Number.isFinite(parsed) && /[-/.:, ]/.test(raw);
}

function keyHasAny(key: string, fragments: string[]): boolean {
  const normalizedKey = normalizeKeyName(key);
  return fragments.some((fragment) => normalizedKey.includes(normalizeKeyName(fragment)));
}

function scoreCandidate(field: AutoFieldKey, key: string, value: unknown): number {
  const raw = stringifyValue(value);
  if (!raw) {
    return Number.NEGATIVE_INFINITY;
  }

  switch (field) {
    case "rating": {
      const rating = numberValue(raw);
      if (rating === null) {
        return Number.NEGATIVE_INFINITY;
      }
      let score = rating >= 1 && rating <= 5 ? 60 : rating >= 0 && rating <= 10 ? 20 : -40;
      if (keyHasAny(key, FIELD_ALIASES.rating)) score += 35;
      if (/(зв[её]зд|star|rating|оцен|score|балл|\/\s*5|из\s*5|out\s+of\s+5)/i.test(raw)) score += 20;
      if (keyHasAny(key, ["id", "код", "артикул", "date", "дата", "time", "время"])) score -= 45;
      if (raw.length > 24 && wordCount(raw) > 4 && !keyHasAny(key, FIELD_ALIASES.rating)) score -= 55;
      return score;
    }
    case "timestamp": {
      if (!isDateLike(raw)) {
        return Number.NEGATIVE_INFINITY;
      }
      let score = 55;
      if (keyHasAny(key, FIELD_ALIASES.timestamp)) score += 35;
      if (keyHasAny(key, ["rating", "оцен", "score", "text", "отзыв", "comment"])) score -= 35;
      return score;
    }
    case "review_text": {
      if (isDateLike(raw) || isRatingLike(raw)) {
        return Number.NEGATIVE_INFINITY;
      }
      const words = wordCount(raw);
      if (raw.length < 18 && words < 4) {
        return Number.NEGATIVE_INFINITY;
      }
      let score = Math.min(raw.length, 500) / 6 + words * 4;
      if (keyHasAny(key, FIELD_ALIASES.review_text)) score += 45;
      if (keyHasAny(key, ["id", "код", "артикул", "user", "author", "автор", "покупатель"])) score -= 40;
      return score;
    }
    case "user_id": {
      if (isDateLike(raw) || isRatingLike(raw) || raw.length > 90 || wordCount(raw) > 8) {
        return Number.NEGATIVE_INFINITY;
      }
      let score = 20;
      if (/[a-zа-я]/i.test(raw)) score += 20;
      if (keyHasAny(key, FIELD_ALIASES.user_id)) score += 45;
      if (keyHasAny(key, ["text", "отзыв", "comment", "review", "rating", "оцен"])) score -= 35;
      return score;
    }
    case "item_id": {
      if (raw.length > 120 || wordCount(raw) > 10) {
        return Number.NEGATIVE_INFINITY;
      }
      let score = 12;
      if (keyHasAny(key, FIELD_ALIASES.item_id)) score += 45;
      if (/[A-ZА-Я0-9-]{3,}/.test(raw)) score += 8;
      if (keyHasAny(key, ["text", "отзыв", "comment", "review", "rating", "оцен", "date", "дата"])) score -= 35;
      return score;
    }
    case "ip_address": {
      if (!/\b(?:\d{1,3}\.){3}\d{1,3}\b/.test(raw)) {
        return Number.NEGATIVE_INFINITY;
      }
      return keyHasAny(key, FIELD_ALIASES.ip_address) ? 85 : 55;
    }
    case "geo": {
      if (isDateLike(raw) || isRatingLike(raw) || raw.length > 80 || wordCount(raw) > 6) {
        return Number.NEGATIVE_INFINITY;
      }
      let score = 10;
      if (keyHasAny(key, FIELD_ALIASES.geo)) score += 45;
      if (keyHasAny(key, ["text", "отзыв", "comment", "review"])) score -= 35;
      return score;
    }
    default:
      return Number.NEGATIVE_INFINITY;
  }
}

function inferCandidate(record: Record<string, unknown>, field: AutoFieldKey, usedKeys = new Set<string>()): unknown {
  const ranked = Object.entries(record)
    .filter(([key, value]) => !usedKeys.has(key) && hasMeaningfulValue(value))
    .map(([key, value]) => ({ key, value, score: scoreCandidate(field, key, value) }))
    .filter((candidate) => candidate.score > 0)
    .sort((left, right) => right.score - left.score);

  return ranked[0]?.value;
}

function extractCandidate(record: Record<string, unknown>, keys: string[]): unknown {
  const entries = Object.entries(record).map(([key, value]) => ({
    key,
    normalizedKey: normalizeKeyName(key),
    value,
  }));
  const normalizedKeys = keys.map(normalizeKeyName).filter(Boolean);

  for (const key of keys) {
    if (key in record && hasMeaningfulValue(record[key])) {
      return record[key];
    }
  }

  for (const alias of normalizedKeys) {
    const match = entries.find((entry) => entry.normalizedKey === alias && hasMeaningfulValue(entry.value));
    if (match) {
      return match.value;
    }
  }

  for (const alias of normalizedKeys) {
    if (alias.length < 3) {
      continue;
    }
    const match = entries.find(
      (entry) =>
        entry.normalizedKey.length >= 3 &&
        (entry.normalizedKey.includes(alias) || alias.includes(entry.normalizedKey)) &&
        hasMeaningfulValue(entry.value)
    );
    if (match) {
      return match.value;
    }
  }

  return undefined;
}

function normalizeRecord(raw: Record<string, unknown>, index: number, fallbackItemId = ""): NormalizedImportRecord {
  const itemId = stringifyValue(extractCandidate(raw, FIELD_ALIASES.item_id) ?? inferCandidate(raw, "item_id"));
  const userId = stringifyValue(extractCandidate(raw, FIELD_ALIASES.user_id) ?? inferCandidate(raw, "user_id"));
  const rating = numberValue(extractCandidate(raw, FIELD_ALIASES.rating) ?? inferCandidate(raw, "rating"));
  const timestamp = stringifyValue(extractCandidate(raw, FIELD_ALIASES.timestamp) ?? inferCandidate(raw, "timestamp"));
  const reviewText = stringifyValue(extractCandidate(raw, FIELD_ALIASES.review_text) ?? inferCandidate(raw, "review_text"));
  const ipAddress = stringifyValue(extractCandidate(raw, FIELD_ALIASES.ip_address) ?? inferCandidate(raw, "ip_address"));
  const geo = stringifyValue(extractCandidate(raw, FIELD_ALIASES.geo) ?? inferCandidate(raw, "geo"));

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

function parseJsonlRecords(text: string): Record<string, unknown>[] {
  const sanitized = text.replace(/^\uFEFF/, "").trim();
  if (!sanitized) {
    throw new Error("The JSONL file is empty.");
  }

  return sanitized
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      try {
        const parsed = JSON.parse(line);
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
          throw new Error("not_object");
        }
        return parsed as Record<string, unknown>;
      } catch (error) {
        throw new Error(`Invalid JSONL record on line ${index + 1}.`);
      }
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

function firstText(root: ParentNode, selectors: string[]): string {
  for (const selector of selectors) {
    const value = root.querySelector(selector)?.textContent?.trim();
    if (value) {
      return value;
    }
  }
  return "";
}

function elementCandidateValues(element: Element): string[] {
  const attrs = ["data-rating", "aria-label", "title", "content", "value", "datetime", "data-date", "alt"];
  return [
    ...attrs.map((attr) => element.getAttribute(attr) || ""),
    element.textContent?.trim() || "",
  ].filter(Boolean);
}

function ratingFromText(value: string): string {
  const raw = value.trim();
  if (!raw) {
    return "";
  }

  const filledStars = (raw.match(/★/g) || []).length;
  if (filledStars >= 1 && filledStars <= 5) {
    return String(filledStars);
  }

  const patterns = [
    /(\d+(?:[.,]\d+)?)\s*(?:\/|из|out\s+of)\s*5/i,
    /(?:rating|score|оценка|рейтинг)\D{0,16}(\d+(?:[.,]\d+)?)/i,
    /(\d+(?:[.,]\d+)?)\s*(?:зв[её]зд|stars?)/i,
  ];

  for (const pattern of patterns) {
    const match = raw.match(pattern);
    if (match?.[1]) {
      return match[1];
    }
  }

  if (/^\d+(?:[.,]\d+)?$/.test(raw) && isRatingLike(raw)) {
    return raw;
  }

  return "";
}

function extractHtmlRating(root: HTMLElement): string {
  const nodes = [
    root,
    ...Array.from(
      root.querySelectorAll(
        '[itemprop="ratingValue"], [data-rating], [aria-label*="star"], [aria-label*="зв"], .rating, .stars, [class*="rating"], [class*="star"]'
      )
    ),
  ];

  for (const node of nodes) {
    for (const value of elementCandidateValues(node)) {
      const rating = ratingFromText(value);
      if (rating) {
        return rating;
      }
    }
  }

  return "";
}

function extractHtmlDate(root: HTMLElement): string {
  const nodes = [
    ...Array.from(root.querySelectorAll("time, [datetime], [data-date], [itemprop='datePublished'], .date, [class*='date']")),
    root,
  ];

  for (const node of nodes) {
    for (const value of elementCandidateValues(node)) {
      if (isDateLike(value)) {
        return value;
      }
    }
  }

  return "";
}

function extractHtmlReviewText(root: HTMLElement): string {
  const direct = firstText(root, [
    '[itemprop="reviewBody"]',
    '[data-review-text]',
    '[data-text]',
    ".review-text",
    ".review-body",
    ".comment",
    ".content",
  ]);

  if (direct) {
    return direct;
  }

  const candidates = Array.from(root.querySelectorAll("p, span, div"))
    .map((node) => node.textContent?.trim() || "")
    .filter((value) => value.length >= 24 && !isDateLike(value) && !isRatingLike(value))
    .sort((left, right) => right.length - left.length);

  return candidates[0] || root.textContent?.trim() || "";
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
        firstText(root, [
          '[itemprop="author"]',
          '[data-author]',
          '[data-user]',
          ".author",
          ".user",
          ".review-author",
          '[class*="author"]',
          '[class*="user"]',
        ]) || "";
      const textValue = extractHtmlReviewText(root);
      const ratingNode = extractHtmlRating(root);
      const timeValue = extractHtmlDate(root);

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

export function parseJsonlInput(text: string): ParsedImportResult {
  const records = parseJsonlRecords(text).map((row, index) => normalizeRecord(row, index));
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

function looksLikeCsv(text: string): boolean {
  const firstLine = text.replace(/^\uFEFF/, "").trim().split(/\r?\n/)[0] || "";
  if (!firstLine) {
    return false;
  }

  return [",", ";", "\t"].some((delimiter) => parseCsvLine(firstLine, delimiter).length > 1);
}

export async function parseFileInput(file: File): Promise<ParsedImportResult> {
  const fileName = file.name.toLowerCase();
  const fileType = file.type.toLowerCase();

  if (
    fileName.endsWith(".xlsx") ||
    fileName.endsWith(".xls") ||
    fileType.includes("spreadsheetml") ||
    fileType.includes("application/vnd.ms-excel")
  ) {
    return parseExcelInput(await file.arrayBuffer());
  }

  const text = await file.text();
  const trimmed = text.trim();

  if (fileName.endsWith(".json") || fileType.includes("application/json") || trimmed.startsWith("{") || trimmed.startsWith("[")) {
    return parseJsonInput(text);
  }

  if (
    fileName.endsWith(".jsonl") ||
    fileName.endsWith(".ndjson") ||
    fileType.includes("application/x-ndjson") ||
    fileType.includes("application/jsonlines")
  ) {
    return parseJsonlInput(text);
  }

  if (
    fileName.endsWith(".csv") ||
    fileName.endsWith(".tsv") ||
    fileType.includes("text/csv") ||
    fileType.includes("text/tab-separated-values") ||
    looksLikeCsv(text)
  ) {
    return parseCsvInput(text);
  }

  if (fileName.endsWith(".html") || fileName.endsWith(".htm") || fileType.includes("text/html") || trimmed.startsWith("<")) {
    return parseHtmlInput(text, file.name);
  }

  throw new Error("Unsupported file format. Upload JSON, JSONL, CSV, TSV, Excel, or HTML.");
}

export async function parseApiResponse(response: Response, sourceUrl: string): Promise<ParsedImportResult> {
  const contentType = response.headers.get("content-type")?.toLowerCase() || "";
  const urlLower = sourceUrl.toLowerCase();

  if (contentType.includes("application/json") || urlLower.endsWith(".json")) {
    return parseJsonInput(await response.text());
  }
  if (
    contentType.includes("application/x-ndjson") ||
    contentType.includes("application/jsonlines") ||
    urlLower.endsWith(".jsonl") ||
    urlLower.endsWith(".ndjson")
  ) {
    return parseJsonlInput(await response.text());
  }
  if (
    contentType.includes("text/csv") ||
    contentType.includes("text/tab-separated-values") ||
    urlLower.endsWith(".csv") ||
    urlLower.endsWith(".tsv")
  ) {
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
