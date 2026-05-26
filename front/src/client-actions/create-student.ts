import type { ClientAction, CreateStudentArgs, StudentCreateRequest } from "@/types";

const CREATE_STUDENT_STATUSES = new Set(["active", "inactive"]);

export type CreateStudentValidation =
  | { ok: true; args: Partial<StudentCreateRequest> }
  | { ok: false; detail: string };

function readOptionalString(raw: Record<string, unknown>, key: keyof CreateStudentArgs): string | undefined {
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

export function sanitizeCreateStudentArgs(raw: Record<string, unknown>): Partial<StudentCreateRequest> {
  const result: Partial<StudentCreateRequest> = {};

  const studentNo = readOptionalString(raw, "student_no");
  if (studentNo !== undefined) {
    result.student_no = studentNo;
  }

  const name = readOptionalString(raw, "name");
  if (name !== undefined) {
    result.name = name;
  }

  const className = readOptionalString(raw, "class_name");
  if (className !== undefined) {
    result.class_name = className;
  }

  const status = readOptionalString(raw, "status");
  if (status !== undefined && CREATE_STUDENT_STATUSES.has(status)) {
    result.status = status;
  }

  return result;
}

export function validateCreateStudentAction(action: ClientAction): CreateStudentValidation {
  const raw = action.args ?? {};
  if (typeof raw !== "object" || Array.isArray(raw)) {
    return { ok: false, detail: "参数格式无效" };
  }

  const record = raw as Record<string, unknown>;
  const status = record.status;
  if (status !== undefined && status !== null) {
    if (typeof status !== "string" || !CREATE_STUDENT_STATUSES.has(status.trim())) {
      return { ok: false, detail: "状态只能是 active（在读）或 inactive（休学）" };
    }
  }

  for (const key of ["student_no", "name", "class_name", "status"] as const) {
    const value = record[key];
    if (value !== undefined && value !== null && typeof value !== "string") {
      return { ok: false, detail: `字段 ${key} 必须是字符串` };
    }
  }

  return { ok: true, args: sanitizeCreateStudentArgs(record) };
}

export const CREATE_STUDENT_STATUS_LABELS: Record<string, string> = {
  active: "在读",
  inactive: "休学",
};

export function formatCreateStudentPrefill(args: Partial<StudentCreateRequest>): string[] {
  const lines: string[] = [];
  if (args.student_no) {
    lines.push(`学号：${args.student_no}`);
  }
  if (args.name) {
    lines.push(`姓名：${args.name}`);
  }
  if (args.class_name) {
    lines.push(`班级：${args.class_name}`);
  }
  if (args.status) {
    lines.push(`状态：${CREATE_STUDENT_STATUS_LABELS[args.status] ?? args.status}`);
  }
  return lines;
}
