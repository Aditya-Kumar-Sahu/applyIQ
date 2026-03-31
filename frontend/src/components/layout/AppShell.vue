<template>
  <div class="app-shell">
    <AppSidebar />

    <div class="app-shell__workspace">
      <header class="app-topbar">
        <div class="app-topbar__search">
          <span class="material-symbols-outlined">search</span>
          <input type="search" placeholder="Search operations..." aria-label="Search operations" />
        </div>

        <nav class="app-topbar__links" aria-label="Top navigation">
          <a href="#" @click.prevent>Documentation</a>
          <a href="#" @click.prevent>Support</a>
        </nav>

        <div class="app-topbar__actions">
          <button type="button" class="app-topbar__icon-button" aria-label="Notifications">
            <span class="material-symbols-outlined">notifications</span>
          </button>
          <button type="button" class="app-topbar__icon-button" aria-label="Help">
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
import { computed } from 'vue';

import AppSidebar from '../AppSidebar.vue';
import { store } from '../../store';

const initials = computed(() => {
  const fullName = store.getters.authUser?.full_name ?? 'Alex Chen';
  return fullName
    .split(' ')
    .filter(Boolean)
    .map((part: string) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
});
</script>