<template>
  <main class="grid">
    <section class="panel auth-panel">
      <p class="eyebrow">Login</p>
      <h2>Continue your ApplyIQ session</h2>
      <form class="auth-form" @submit.prevent="submit">
        <label>
          <span>Email</span>
          <input v-model="email" type="email" autocomplete="email" required />
        </label>

        <label>
          <span>Password</span>
          <input v-model="password" type="password" autocomplete="current-password" required />
        </label>

        <p v-if="errorMessage" class="auth-error">{{ errorMessage }}</p>

        <button class="button-link auth-button" type="submit">Sign in</button>
      </form>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import { store } from "../store";

const router = useRouter();
const email = ref("");
const password = ref("");
const errorMessage = computed(() => store.getters.authError as string | null);

async function submit() {
  await store.dispatch("login", { email: email.value, password: password.value });
  await router.push({ name: "dashboard" });
}
</script>
