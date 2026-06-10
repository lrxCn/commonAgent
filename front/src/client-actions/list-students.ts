import type { ClientAction, StudentListParams } from "@/types";

const LIST_STUDENT_STATUSES = new Set(["active", "inactive"]);
const DEFAULT_LIMIT = 10;
const MAX_LIMIT = 100;

export const DEFAULT_LIST_AFTER_CREATE: StudentListParams = {
  offset: 0,
  limit: DEFAULT_LIMIT,
};

export type ListStudentsValidation =
  | { ok: true; query: StudentListParams }
  | { ok: false; detail: string };

function readOptionalString(raw: Record<string, unknown>, key: "search" | "class_name"): string | undefined {
  const value = raw[key];
  if (value === undefined || value === null) {
    return undefined;
  }
  if (typeof value !== "string") {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function readNonNegativeInt(value: unknown, fallback: number): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.max(0, Math.floor(value));
  }
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number.parseInt(value, 10);
    if (Number.isFinite(parsed)) {
      return Math.max(0, parsed);
    }
  }
  return fallback;
}

function readLimit(value: unknown): number {
  const parsed = readNonNegativeInt(value, DEFAULT_LIMIT);
  const normalized = parsed > 0 ? parsed : DEFAULT_LIMIT;
  return Math.min(normalized, MAX_LIMIT);
}

export function sanitizeListStudentsArgs(raw: Record<string, unknown>): StudentListParams {
  const query: StudentListParams = {
    offset: readNonNegativeInt(raw.offset, 0),
    limit: readLimit(raw.limit),
  };

  const search = readOptionalString(raw, "search");
  if (search !== undefined) {
    query.search = search;
  }

  const className = readOptionalString(raw, "class_name");
  if (className !== undefined) {
    query.class_name = className;
  }

  const status = readOptionalString(raw, "status");
  if (status !== undefined && LIST_STUDENT_STATUSES.has(status)) {
    query.status = status;
  }

  return query;
}

export function validateListStudentsAction(action: ClientAction): ListStudentsValidation {
  const raw = action.args ?? {};
  if (typeof raw !== "object" || Array.isArray(raw)) {
    return { ok: false, detail: "参数格式无效" };
  }

  const record = raw as Record<string, unknown>;

  for (const key of ["search", "class_name", "status"] as const) {
    const value = record[key];
    if (value !== undefined && value !== null && typeof value !== "string") {
      return { ok: false, detail: `字段 ${key} 必须是字符串` };
    }
  }

  const status = record.status;
  if (status !== undefined && status !== null) {
    if (typeof status !== "string" || !LIST_STUDENT_STATUSES.has(status.trim())) {
      return { ok: false, detail: "状态只能是 active（在职）或 inactive（离职）" };
    }
  }

  if (record.offset !== undefined && record.offset !== null) {
    if (
      typeof record.offset !== "number" &&
      (typeof record.offset !== "string" || Number.isNaN(Number.parseInt(String(record.offset), 10)))
    ) {
      return { ok: false, detail: "offset 必须是非负整数" };
    }
  }

  if (record.limit !== undefined && record.limit !== null) {
    if (
      typeof record.limit !== "number" &&
      (typeof record.limit !== "string" || Number.isNaN(Number.parseInt(String(record.limit), 10)))
    ) {
      return { ok: false, detail: "limit 必须是正整数" };
    }
    const limit = readLimit(record.limit);
    if (limit < 1) {
      return { ok: false, detail: "limit 至少为 1" };
    }
  }

  return { ok: true, query: sanitizeListStudentsArgs(record) };
}

const STATUS_LABELS: Record<string, string> = {
  active: "在职",
  inactive: "离职",
};

/** Human-readable query summary for historical list cards without row data. */
export function formatListStudentsQuerySummary(query: StudentListParams): string {
  const parts: string[] = [];
  if (query.search) {
    parts.push(`搜索「${query.search}」`);
  }
  if (query.status) {
    parts.push(`状态：${STATUS_LABELS[query.status] ?? query.status}`);
  }
  if (query.class_name) {
    parts.push(`部门：${query.class_name}`);
  }
  const limit = query.limit ?? DEFAULT_LIMIT;
  const offset = query.offset ?? 0;
  const page = Math.floor(offset / limit) + 1;
  parts.push(`第 ${page} 页（每页 ${limit} 条）`);
  return parts.length > 0 ? parts.join("，") : "全部员工";
}
