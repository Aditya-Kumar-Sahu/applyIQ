import { createRouter, createWebHistory } from "vue-router";

import HomeView          from "../views/HomeView.vue";
import LoginView         from "../views/LoginView.vue";
import { store }         from "../store";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "home",
      component: HomeView,
      meta: { guestOnly: true },
    },
    {
      path: "/dashboard",
      name: "dashboard",
      component: () => import("../views/DashboardView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/pipeline",
      name: "pipeline",
      component: () => import("../views/PipelineView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/jobs",
      name: "jobs",
      component: () => import("../views/JobsView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/applications",
      name: "applications",
      component: () => import("../views/ApplicationsView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/approval",
      name: "approval",
      component: () => import("../views/ApprovalGateView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/profile",
      name: "profile",
      component: () => import("../views/ProfileView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/settings",
      name: "settings",
      component: () => import("../views/SettingsView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/login",
      name: "login",
      component: LoginView,
      meta: { guestOnly: true },
    },
    {
      path: "/register",
      name: "register",
      component: () => import("../views/RegisterView.vue"),
      meta: { guestOnly: true },
    },
    // Legacy redirects so old routes still work
    { path: "/resume", redirect: "/profile"   },
    { path: "/home",   redirect: "/"          },
  ],
});

router.beforeEach(async (to) => {
  if (store.getters.authStatus === "idle") {
    await store.dispatch("hydrateSession");
  }

  const isAuthenticated = store.getters.isAuthenticated as boolean;

  if (to.meta.requiresAuth && !isAuthenticated) {
    return { name: "login" };
  }

  if (to.meta.guestOnly && isAuthenticated) {
    return { name: "dashboard" };
  }

  return true;
});
