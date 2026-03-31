import { createRouter, createWebHistory } from "vue-router";

import ApplicationsView  from "../views/ApplicationsView.vue";
import ApprovalGateView  from "../views/ApprovalGateView.vue";
import DashboardView     from "../views/DashboardView.vue";
import LoginView         from "../views/LoginView.vue";
import HomeView          from "../views/HomeView.vue";
import PipelineView      from "../views/PipelineView.vue";
import ProfileView       from "../views/ProfileView.vue";
import RegisterView      from "../views/RegisterView.vue";
import SettingsView      from "../views/SettingsView.vue";
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
      component: DashboardView,
      meta: { requiresAuth: true },
    },
    {
      path: "/pipeline",
      name: "pipeline",
      component: PipelineView,
      meta: { requiresAuth: true },
    },
    {
      path: "/applications",
      name: "applications",
      component: ApplicationsView,
      meta: { requiresAuth: true },
    },
    {
      path: "/approval",
      name: "approval",
      component: ApprovalGateView,
      meta: { requiresAuth: true },
    },
    {
      path: "/profile",
      name: "profile",
      component: ProfileView,
      meta: { requiresAuth: true },
    },
    {
      path: "/settings",
      name: "settings",
      component: SettingsView,
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
      component: RegisterView,
      meta: { guestOnly: true },
    },
    // Legacy redirects so old routes still work
    { path: "/resume", redirect: "/profile"   },
    { path: "/jobs",   redirect: "/pipeline"  },
    { path: "/vault",  redirect: "/dashboard" },
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
