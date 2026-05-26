import { defineStore } from "pinia";
import { ref } from "vue";

/** Placeholder store; auth/chat stores arrive in task 84/91. */
export const useAppStore = defineStore("app", () => {
  const initialized = ref(true);

  return { initialized };
});
