<template>
  <template v-if="isAuthRoute">
    <div class="app-shell--auth">
      <RouterView />
    </div>
  </template>

  <template v-else>
    <AppShell>
      <RouterView v-slot="{ Component, route }">
        <Transition name="fade-slide" mode="out-in">
          <component :is="Component" :key="route.fullPath" />
        </Transition>
      </RouterView>
    </AppShell>
  </template>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { RouterView, useRoute } from "vue-router";
import AppShell from "./components/layout/AppShell.vue";

const route = useRoute();

const isAuthRoute = computed(() => route.meta.guestOnly === true || route.name === "login" || route.name === "register");
</script>
