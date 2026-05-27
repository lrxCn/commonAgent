import { createRouter, createWebHistory } from "vue-router";

import AppLayout from "@/components/layout/AppLayout.vue";
import { useAuthStore } from "@/stores/auth";
import HomeView from "@/views/HomeView.vue";
import LoginView from "@/views/LoginView.vue";
import KbDocumentsView from "@/views/admin/KbDocumentsView.vue";
import RolesView from "@/views/admin/RolesView.vue";
import CallsView from "@/views/CallsView.vue";
import StudentsView from "@/views/StudentsView.vue";
import UsersView from "@/views/admin/UsersView.vue";

declare module "vue-router" {
  interface RouteMeta {
    requiresAuth?: boolean;
    requiresAdmin?: boolean;
    guestOnly?: boolean;
  }
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: "/login",
      name: "login",
      component: LoginView,
      meta: { guestOnly: true },
    },
    {
      path: "/app",
      component: AppLayout,
      meta: { requiresAuth: true },
      children: [
        {
          path: "",
          redirect: { name: "app-home" },
        },
        {
          path: "home",
          name: "app-home",
          component: HomeView,
          meta: { requiresAuth: true },
        },
        {
          path: "students",
          name: "app-students",
          component: StudentsView,
          meta: { requiresAuth: true },
        },
        {
          path: "calls",
          name: "app-calls",
          component: CallsView,
          meta: { requiresAuth: true },
        },
        {
          path: "admin/roles",
          name: "app-admin-roles",
          component: RolesView,
          meta: { requiresAuth: true, requiresAdmin: true },
        },
        {
          path: "admin/users",
          name: "app-admin-users",
          component: UsersView,
          meta: { requiresAuth: true, requiresAdmin: true },
        },
        {
          path: "admin/kb",
          name: "app-admin-kb",
          component: KbDocumentsView,
          meta: { requiresAuth: true, requiresAdmin: true },
        },
      ],
    },
    {
      path: "/",
      redirect: "/app/home",
    },
    {
      path: "/:pathMatch(.*)*",
      redirect: "/app/home",
    },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();

  if (!auth.initialized) {
    await auth.initialize();
  }

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return {
      name: "login",
      query: { redirect: to.fullPath },
    };
  }

  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return { name: "app-home" };
  }

  if (to.meta.guestOnly && auth.isAuthenticated) {
    return { name: "app-home" };
  }

  return true;
});

export default router;
