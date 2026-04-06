<template>
  <div class="app-shell">
    <AppSidebar />

    <div class="app-shell__workspace">
      <header class="app-topbar">
        <form class="app-topbar__search" @submit.prevent="runSearch">
          <span class="material-symbols-outlined">search</span>
          <input v-model="searchQuery" type="search" placeholder="Search jobs, skills, or role" aria-label="Search jobs, skills, or role" />
        </form>

        <div class="app-topbar__actions">
          <button type="button" class="app-topbar__icon-button" aria-label="Notifications" disabled title="Coming soon">
            <span class="material-symbols-outlined">notifications</span>
          </button>
          <button type="button" class="app-topbar__icon-button" aria-label="Help" disabled title="Coming soon">
            <span class="material-symbols-outlined">help_outline</span>
          </button>
          <div class="app-topbar__avatar">{{ initials }}</div>
        </div>
      </header>

      <main class="app-shell__main">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import AppSidebar from '../AppSidebar.vue';
import { store } from '../../store';

const route = useRoute();
const router = useRouter();
const searchQuery = ref('');

const currentUser = computed(() => store.getters.authUser as { full_name: string } | null);

const initials = computed(() => {
  const fullName = currentUser.value?.full_name;
  if (!fullName) {
    return '?';
  }

  return fullName
    .split(' ')
    .filter(Boolean)
    .map((part: string) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
});

watch(
  () => [route.name, route.query.q],
  ([routeName, query]) => {
    const normalizedQuery = typeof query === 'string' ? query.trim() : '';

    if (routeName === 'jobs' || normalizedQuery) {
      searchQuery.value = normalizedQuery;
    }
  },
  { immediate: true },
);

async function runSearch() {
  const query = searchQuery.value.trim();
  await router.replace({ path: '/jobs', query: query ? { q: query } : {} });
}
</script>