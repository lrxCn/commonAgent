import http from "@/api/http";
import type {
  Student,
  StudentCreateRequest,
  StudentListParams,
  StudentListResponse,
  StudentUpdateRequest,
} from "@/types";

export async function fetchStudents(
  params: StudentListParams = {},
): Promise<StudentListResponse> {
  const { data } = await http.get<StudentListResponse>("/api/students", {
    params,
  });
  return data;
}

export async function fetchClassNames(): Promise<string[]> {
  const { data } = await http.get<string[]>("/api/students/meta/class-names");
  return data;
}

export async function createStudent(
  body: StudentCreateRequest,
): Promise<Student> {
  const { data } = await http.post<Student>("/api/students", body);
  return data;
}

export async function updateStudent(
  studentId: string,
  body: StudentUpdateRequest,
): Promise<Student> {
  const { data } = await http.patch<Student>(
    `/api/students/${studentId}`,
    body,
  );
  return data;
}

export async function deleteStudent(studentId: string): Promise<void> {
  await http.delete(`/api/students/${studentId}`);
}

export async function batchDeleteStudents(
  studentIds: string[],
): Promise<number> {
  const { data } = await http.post<{ deleted: number }>(
    "/api/students/batch-delete",
    { student_ids: studentIds },
  );
  return data.deleted;
}
