<template>
  <div class="shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">ApplyIQ</p>
        <h1>Autonomous job hunting, with a human approval gate.</h1>
      </div>
      <nav class="nav">
        <RouterLink to="/">Overview</RouterLink>
        <RouterLink v-if="!isAuthenticated" to="/login">Login</RouterLink>
        <RouterLink v-if="!isAuthenticated" to="/register">Register</RouterLink>
        <RouterLink to="/dashboard">Dashboard</RouterLink>
        <RouterLink v-if="isAuthenticated" to="/resume">Resume</RouterLink>
        <RouterLink v-if="isAuthenticated" to="/jobs">Jobs</RouterLink>
        <RouterLink v-if="isAuthenticated" to="/pipeline">Pipeline</RouterLink>
      </nav>
    </header>

    <RouterView />
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, RouterView } from "vue-router";

import { store } from "./store";

const isAuthenticated = computed(() => store.getters.isAuthenticated as boolean);
</script>
