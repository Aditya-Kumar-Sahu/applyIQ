<template>
  <main class="grid">
    <section class="panel">
      <p class="eyebrow">Dashboard</p>
      <h2>{{ headline }}</h2>
      <p class="lede">
        This is the Vue/Vuex starter surface for the real-time command centre we will expand in the
        next phases.
      </p>
      <p v-if="currentUser" class="lede">Signed in as {{ currentUser.full_name }} ({{ currentUser.email }})</p>
    </section>

    <section class="stats-grid">
      <article v-for="stat in stats" :key="stat.label" class="stat-card">
        <p class="stat-label">{{ stat.label }}</p>
        <p class="stat-value">{{ stat.value }}</p>
      </article>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed } from "vue";

import { store } from "../store";

const headline = computed(() => store.getters.headline as string);
const stats = computed(() => store.getters.dashboardStats as { label: string; value: string }[]);
const currentUser = computed(
  () => store.getters.authUser as { full_name: string; email: string } | null,
);
</script>
