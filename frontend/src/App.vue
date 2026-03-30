<template>
  <div class="shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">ApplyIQ</p>
      </div>
      <nav class="nav">
        <RouterLink to="/">Overview</RouterLink>
        <RouterLink v-if="!isAuthenticated" to="/login">Login</RouterLink>
        <RouterLink v-if="!isAuthenticated" to="/register">Register</RouterLink>
        <RouterLink to="/dashboard">Dashboard</RouterLink>
        <RouterLink v-if="isAuthenticated" to="/resume">Resume</RouterLink>
        <RouterLink v-if="isAuthenticated" to="/jobs">Jobs</RouterLink>
        <RouterLink v-if="isAuthenticated" to="/applications">Applications</RouterLink>
        <RouterLink v-if="isAuthenticated" to="/pipeline">Pipeline</RouterLink>
        <RouterLink v-if="isAuthenticated" to="/vault">Vault</RouterLink>
        <RouterLink v-if="isAuthenticated" to="/settings">Settings</RouterLink>
        <button v-if="isAuthenticated" class="nav-action" type="button" @click="handleLogout">Logout</button>
      </nav>
    </header>

    <RouterView />
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, RouterView } from "vue-router";

import { useRouter } from "vue-router";
import { store } from "./store";

const isAuthenticated = computed(() => store.getters.isAuthenticated as boolean);

const router = useRouter();

async function handleLogout() {
  await store.dispatch("logout");
  if (router.currentRoute.value.name !== "login") {
    await router.replace({ name: "login" });
  }
}
</script>
