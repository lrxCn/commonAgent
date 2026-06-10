import { defineStore } from "pinia";
import { ref } from "vue";

import * as studentsApi from "@/api/students";
import type { Student } from "@/types";

/** Bumped when employee data changes outside this page (e.g. chat createStudent). */
export const useStudentsStore = defineStore("students", () => {
  const students = ref<Student[]>([]);
  const total = ref(0);
  const loading = ref(false);
  const page = ref(1);
  const pageSize = ref(10);
  const search = ref("");
  const statusFilter = ref<string | null>(null);
  const classFilter = ref<string | null>(null);
  const classOptions = ref<{ label: string; value: string }[]>([]);
  const listRevision = ref(0);

  async function loadClassNames(): Promise<void> {
    try {
      const names = await studentsApi.fetchClassNames();
      classOptions.value = names.map((name) => ({ label: name, value: name }));
    } catch {
      classOptions.value = [];
    }
  }

  async function loadStudents(): Promise<void> {
    loading.value = true;
    try {
      const data = await studentsApi.fetchStudents({
        offset: (page.value - 1) * pageSize.value,
        limit: pageSize.value,
        search: search.value.trim() || undefined,
        status: statusFilter.value || undefined,
        class_name: classFilter.value || undefined,
      });
      students.value = data.items;
      total.value = data.total;
    } finally {
      loading.value = false;
    }
  }

  /** Chat / other surfaces created or mutated employees; StudentsView watches and reloads. */
  function markListChanged(): void {
    listRevision.value += 1;
  }

  async function refreshAfterExternalChange(): Promise<void> {
    await loadClassNames();
    await loadStudents();
  }

  function resetListState(): void {
    students.value = [];
    total.value = 0;
    page.value = 1;
    search.value = "";
    statusFilter.value = null;
    classFilter.value = null;
    classOptions.value = [];
    listRevision.value = 0;
  }

  return {
    students,
    total,
    loading,
    page,
    pageSize,
    search,
    statusFilter,
    classFilter,
    classOptions,
    listRevision,
    loadClassNames,
    loadStudents,
    markListChanged,
    refreshAfterExternalChange,
    resetListState,
  };
});
