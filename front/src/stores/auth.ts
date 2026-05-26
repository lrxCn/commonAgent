import { defineStore } from "pinia";
import { computed, ref } from "vue";

import * as authApi from "@/api/auth";
import { useChatStore } from "@/stores/chat";
import type { MeResponse } from "@/types";

export const useAuthStore = defineStore("auth", () => {
  const user = ref<MeResponse | null>(null);
  const initialized = ref(false);

  const isAuthenticated = computed(() => user.value !== null);
  const isAdmin = computed(() => user.value?.is_admin ?? false);

  async function initialize(): Promise<void> {
    try {
      user.value = await authApi.fetchMe();
      if (user.value) {
        useChatStore().ensureThreadForUser(user.value.user_id);
      }
    } catch {
      user.value = null;
    } finally {
      initialized.value = true;
    }
  }

  async function login(username: string, password: string): Promise<void> {
    user.value = await authApi.login({ username, password });
    useChatStore().ensureThreadForUser(user.value.user_id);
  }

  async function logout(): Promise<void> {
    try {
      await authApi.logout();
    } finally {
      useChatStore().resetOnLogout();
      user.value = null;
    }
  }

  function clearSession(): void {
    useChatStore().resetOnLogout();
    user.value = null;
  }

  return {
    user,
    initialized,
    isAuthenticated,
    isAdmin,
    initialize,
    login,
    logout,
    clearSession,
  };
});
