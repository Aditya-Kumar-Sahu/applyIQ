<template>
  <div class="app-shell--auth">
    <div class="auth-card">
      <p class="auth-card__brand">ApplyIQ</p>
      <p class="auth-card__tagline">The Digital Curator</p>
      <h1 class="auth-card__title">Welcome back</h1>
      <p class="auth-card__sub">Sign in to your workspace to continue.</p>

      <form class="auth-form" @submit.prevent="submit" id="login-form">
        <div class="field-group">
          <label class="field-label" for="login-email">Email</label>
          <input
            id="login-email"
            v-model="email"
            type="email"
            class="field-input"
            autocomplete="email"
            placeholder="Email address"
            required
          />
        </div>

        <div class="field-group">
          <label class="field-label" for="login-password">Password</label>
          <input
            id="login-password"
            v-model="password"
            type="password"
            class="field-input"
            autocomplete="current-password"
            placeholder="Password"
            required
          />
        </div>

        <div v-if="errorMessage" class="auth-error">{{ errorMessage }}</div>

        <button id="login-submit" class="btn btn-primary w-full" type="submit" style="margin-top:0.5rem;">
          Sign in
        </button>
      </form>

      <p class="auth-form__footer">
        Don't have an account?
        <RouterLink to="/register">Create one</RouterLink>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { store } from "../store";

const router       = useRouter();
const email        = ref("");
const password     = ref("");
const errorMessage = computed(() => store.getters.authError as string | null);

async function submit() {
  await store.dispatch("login", { email: email.value, password: password.value });
  if (!store.getters.authError) {
    await router.push({ name: "dashboard" });
  }
}
</script>
