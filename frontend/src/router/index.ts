import { createRouter, createWebHistory } from "vue-router";

import DashboardView from "../views/DashboardView.vue";
import HomeView from "../views/HomeView.vue";
import JobsView from "../views/JobsView.vue";
import LoginView from "../views/LoginView.vue";
import PipelineView from "../views/PipelineView.vue";
import RegisterView from "../views/RegisterView.vue";
import ResumeView from "../views/ResumeView.vue";
import { store } from "../store";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "home",
      component: HomeView,
    },
    {
      path: "/dashboard",
      name: "dashboard",
      component: DashboardView,
      meta: { requiresAuth: true },
    },
    {
      path: "/resume",
      name: "resume",
      component: ResumeView,
      meta: { requiresAuth: true },
    },
    {
      path: "/jobs",
      name: "jobs",
      component: JobsView,
      meta: { requiresAuth: true },
    },
    {
      path: "/pipeline",
      name: "pipeline",
      component: PipelineView,
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
