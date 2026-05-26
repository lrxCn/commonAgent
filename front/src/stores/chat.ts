import { defineStore } from "pinia";
import { ref } from "vue";

/** Chat drawer shell state; SSE and thread handling arrive in task 91. */
export const useChatStore = defineStore("chat", () => {
  const drawerOpen = ref(false);

  function openDrawer(): void {
    drawerOpen.value = true;
  }

  function closeDrawer(): void {
    drawerOpen.value = false;
  }

  function toggleDrawer(): void {
    drawerOpen.value = !drawerOpen.value;
  }

  return {
    drawerOpen,
    openDrawer,
    closeDrawer,
    toggleDrawer,
  };
});
