<template>
  <main class="grid">
    <section class="panel auth-panel">
      <p class="eyebrow">Register</p>
      <h2>Create your ApplyIQ account</h2>
      <form class="auth-form" @submit.prevent="submit">
        <label>
          <span>Full name</span>
          <input v-model="fullName" type="text" autocomplete="name" required />
        </label>

        <label>
          <span>Email</span>
          <input v-model="email" type="email" autocomplete="email" required />
        </label>

        <label>
          <span>Password</span>
          <input v-model="password" type="password" autocomplete="new-password" required />
        </label>

        <p v-if="errorMessage" class="auth-error">{{ errorMessage }}</p>

        <button class="button-link auth-button" type="submit">Create account</button>
      </form>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import { store } from "../store";

const router = useRouter();
const fullName = ref("");
const email = ref("");
const password = ref("");
const errorMessage = computed(() => store.getters.authError as string | null);

async function submit() {
  await store.dispatch("register", {
    email: email.value,
    password: password.value,
    full_name: fullName.value,
  });
  await router.push({ name: "dashboard" });
}
</script>
