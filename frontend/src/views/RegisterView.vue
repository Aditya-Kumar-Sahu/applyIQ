<template>
  <div class="app-shell--auth">
    <div class="auth-card">
      <p class="auth-card__brand">ApplyIQ</p>
      <p class="auth-card__tagline">The Digital Curator</p>
      <h1 class="auth-card__title">Create your workspace</h1>
      <p class="auth-card__sub">Start automating your job search in minutes.</p>

      <form class="auth-form" @submit.prevent="submit" id="register-form">
        <div class="field-group">
          <label class="field-label" for="reg-name">Full name</label>
          <input
            id="reg-name"
            v-model="fullName"
            type="text"
            class="field-input"
            autocomplete="name"
            placeholder="Full name"
            required
          />
        </div>

        <div class="field-group">
          <label class="field-label" for="reg-email">Email</label>
          <input
            id="reg-email"
            v-model="email"
            type="email"
            class="field-input"
            autocomplete="email"
            placeholder="Email address"
            required
          />
        </div>

        <div class="field-group">
          <label class="field-label" for="reg-password">Password</label>
          <input
            id="reg-password"
            v-model="password"
            type="password"
            class="field-input"
            autocomplete="new-password"
            placeholder="Create a password"
            required
          />
        </div>

        <div v-if="errorMessage" class="auth-error">{{ errorMessage }}</div>

        <button id="register-submit" class="btn btn-primary w-full" type="submit" style="margin-top:0.5rem;">
          Create account
        </button>
      </form>

      <p class="auth-form__footer">
        Already have an account?
        <RouterLink to="/login">Sign in</RouterLink>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { store } from "../store";

const router       = useRouter();
const fullName     = ref("");
const email        = ref("");
const password     = ref("");
const errorMessage = computed(() => store.getters.authError as string | null);

async function submit() {
  await store.dispatch("register", {
    full_name: fullName.value,
    email:     email.value,
    password:  password.value,
  });
  if (!store.getters.authError) {
    await router.push({ name: "dashboard" });
  }
}
</script>
