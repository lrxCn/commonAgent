import { createApp } from "vue";
import { createPinia } from "pinia";

import { setUnauthorizedHandler } from "@/api/http";
import App from "./App.vue";
import router from "./router";
import { useAuthStore } from "./stores/auth";

const app = createApp(App);
const pinia = createPinia();

app.use(pinia);
app.use(router);

setUnauthorizedHandler(() => {
  const auth = useAuthStore();
  auth.clearSession();
  if (router.currentRoute.value.name !== "login") {
    void router.push({
      name: "login",
      query: { redirect: router.currentRoute.value.fullPath },
    });
  }
});

app.mount("#app");
