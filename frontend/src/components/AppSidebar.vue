<template>
  <aside class="sidebar">
    <!-- Wordmark -->
    <div class="sidebar__wordmark">
      <div class="sidebar__brand-mark">
        <span class="material-symbols-outlined" aria-hidden="true">smart_toy</span>
      </div>
      <div>
        <span class="sidebar__brand">ApplyIQ</span>
        <span class="sidebar__subtitle">The Digital Curator</span>
      </div>
    </div>

    <!-- Nav -->
    <nav class="sidebar__nav" aria-label="Main navigation">
      <RouterLink
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="nav-item"
        :class="{ active: isActive(item.to) }"
        :title="item.label"
      >
        <span class="material-symbols-outlined">{{ item.icon }}</span>
        {{ item.label }}
      </RouterLink>
    </nav>

    <!-- Footer / User -->
    <div class="sidebar__footer">
      <div class="sidebar__user" @click="goToProfile">
        <div class="sidebar__avatar">{{ initials }}</div>
        <div class="sidebar__user-info">
          <div class="sidebar__user-name">{{ userName }}</div>
          <div class="sidebar__user-plan">{{ userPlan }}</div>
        </div>
      </div>
      <div class="sidebar__footer-links">
        <a href="#" style="color:var(--error)" @click.prevent="handleLogout">Logout</a>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { store } from "../store";

const route = useRoute();
const router = useRouter();

const navItems = [
  { to: "/dashboard",    icon: "dashboard",    label: "Dashboard"    },
  { to: "/pipeline",     icon: "account_tree", label: "Pipeline"     },
  { to: "/jobs",         icon: "search",       label: "Jobs"         },
  { to: "/applications", icon: "description",  label: "Applications" },
  { to: "/approval",     icon: "approval",     label: "Approval Gate"},
  { to: "/profile",      icon: "person",       label: "Profile"      },
  { to: "/settings",     icon: "settings",     label: "Settings"     },
];

const currentUser = computed(() => store.getters.authUser as { full_name: string; email: string; subscription_tier?: string } | null);
const userName = computed(() => currentUser.value?.full_name ?? "Loading profile");
const userPlan = computed(() => currentUser.value?.subscription_tier ?? "Plan unavailable");
const initials = computed(() => {
  if (!currentUser.value?.full_name) {
    return "?";
  }

  const parts = currentUser.value.full_name.split(" ");
  return parts.map((p: string) => p[0]).slice(0, 2).join("").toUpperCase();
});

function isActive(to: string) {
  return route.path.startsWith(to);
}

function goToProfile() {
  router.push("/profile");
}

async function handleLogout() {
  await store.dispatch("logout");
  await router.replace({ name: "login" });
}
</script>
