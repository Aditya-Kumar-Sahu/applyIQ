<template>
  <main class="grid">
    <section class="panel">
      <p class="eyebrow">Credential Vault</p>
      <h2>Store site credentials securely so supported ATS flows can auto-apply when approval is granted.</h2>
      <p class="lede">
        Credentials are encrypted before they are stored. This screen only shows masked usernames and usage timestamps.
      </p>

      <form class="pipeline-form" @submit.prevent="saveCredential">
        <label>
          Site name
          <select v-model="form.siteName">
            <option value="linkedin">linkedin</option>
            <option value="indeed">indeed</option>
            <option value="workday">workday</option>
            <option value="greenhouse">greenhouse</option>
          </select>
        </label>
        <label>
          Site URL
          <input v-model="form.siteUrl" type="url" required />
        </label>
        <label>
          Username
          <input v-model="form.username" type="text" required />
        </label>
        <label>
          Password
          <input v-model="form.password" type="password" required />
        </label>
        <div class="action-row">
          <button class="button-link auth-button" type="submit">{{ saving ? "Saving..." : "Save credential" }}</button>
          <button class="button-link secondary-button" type="button" @click="loadCredentials">Refresh</button>
        </div>
      </form>

      <p v-if="error" class="auth-error">{{ error }}</p>
    </section>

    <section class="panel">
      <p class="eyebrow">Stored Sites</p>
      <div v-if="credentials.length === 0" class="empty-state">
        <p class="lede">No credentials saved yet.</p>
      </div>

      <article v-for="credential in credentials" :key="credential.id" class="approval-card">
        <div class="approval-card-head">
          <div>
            <h3>{{ credential.site_name }}</h3>
            <p class="job-meta">{{ credential.masked_username }}</p>
            <p class="job-meta">{{ credential.site_url }}</p>
          </div>
          <button class="button-link danger-button" type="button" @click="removeCredential(credential.id)">
            Delete
          </button>
        </div>
        <p class="job-meta">
          Last used:
          {{ credential.last_used_at ? formatDate(credential.last_used_at) : "Not used yet" }}
        </p>
      </article>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";

import type { VaultCredential } from "../services/vault";
import { deleteCredential, listCredentials, storeCredential } from "../services/vault";

const credentials = ref<VaultCredential[]>([]);
const saving = ref(false);
const error = ref<string | null>(null);
const form = reactive({
  siteName: "linkedin",
  siteUrl: "https://www.linkedin.com/jobs",
  username: "",
  password: "",
});

onMounted(async () => {
  await loadCredentials();
});

async function loadCredentials() {
  try {
    error.value = null;
    const response = await listCredentials();
    credentials.value = response.items;
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : "Unable to load credentials";
  }
}

async function saveCredential() {
  try {
    saving.value = true;
    error.value = null;
    await storeCredential({
      site_name: form.siteName,
      site_url: form.siteUrl,
      username: form.username,
      password: form.password,
    });
    form.username = "";
    form.password = "";
    await loadCredentials();
  } catch (saveError) {
    error.value = saveError instanceof Error ? saveError.message : "Unable to save credential";
  } finally {
    saving.value = false;
  }
}

async function removeCredential(credentialId: string) {
  try {
    error.value = null;
    await deleteCredential(credentialId);
    await loadCredentials();
  } catch (deleteError) {
    error.value = deleteError instanceof Error ? deleteError.message : "Unable to delete credential";
  }
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString();
}
</script>
