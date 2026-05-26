import { defineStore } from "pinia";
import { ref } from "vue";

import type { StudentCreateRequest } from "@/types";

export const useStudentUiStore = defineStore("studentUi", () => {
  const pendingCreate = ref<Partial<StudentCreateRequest> | null>(null);

  function setPendingCreate(args: Partial<StudentCreateRequest>): void {
    pendingCreate.value = { ...args };
  }

  function consumePendingCreate(): Partial<StudentCreateRequest> | null {
    const current = pendingCreate.value;
    pendingCreate.value = null;
    return current;
  }

  function clearPendingCreate(): void {
    pendingCreate.value = null;
  }

  return {
    pendingCreate,
    setPendingCreate,
    consumePendingCreate,
    clearPendingCreate,
  };
});
