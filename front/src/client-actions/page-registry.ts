import type { RouteLocationRaw } from "vue-router";

export type PageSlug =
  | "home"
  | "students"
  | "admin-roles"
  | "admin-users"
  | "admin-kb";

export const PAGE_SLUGS: readonly PageSlug[] = [
  "home",
  "students",
  "admin-roles",
  "admin-users",
  "admin-kb",
];

const ADMIN_ONLY_SLUGS = new Set<PageSlug>([
  "admin-roles",
  "admin-users",
  "admin-kb",
]);

const SLUG_TO_ROUTE: Record<PageSlug, RouteLocationRaw> = {
  home: { name: "app-home" },
  students: { name: "app-students" },
  "admin-roles": { name: "app-admin-roles" },
  "admin-users": { name: "app-admin-users" },
  "admin-kb": { name: "app-admin-kb" },
};

/** User-facing labels for jumpPage confirmation UI. */
export const PAGE_SLUG_LABELS: Record<PageSlug, string> = {
  home: "首页",
  students: "员工管理",
  "admin-roles": "角色管理",
  "admin-users": "用户管理",
  "admin-kb": "RAG 知识库",
};

export function parsePageSlug(page: string): PageSlug | null {
  const normalized = page.trim().toLowerCase();
  for (const slug of PAGE_SLUGS) {
    if (slug.toLowerCase() === normalized) {
      return slug;
    }
  }
  return null;
}

export function resolveJumpPageTarget(page: string): RouteLocationRaw | null {
  const slug = parsePageSlug(page);
  if (!slug) {
    return null;
  }
  return SLUG_TO_ROUTE[slug];
}

export function isPageAllowedForUser(page: PageSlug, isAdmin: boolean): boolean {
  if (ADMIN_ONLY_SLUGS.has(page)) {
    return isAdmin;
  }
  return true;
}
