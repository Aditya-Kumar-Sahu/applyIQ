<template>
  <main class="grid settings-layout">
    <section class="panel settings-hero">
      <p class="eyebrow">Settings</p>
      <h2>Connect Gmail for automatic response tracking.</h2>
      <p class="lede">
        Once connected, ApplyIQ can classify replies and update application statuses without manual polling.
      </p>
    </section>

    <section class="panel">
      <p class="eyebrow">Gmail Integration</p>
      <h3>Connection Status</h3>
      <div class="connection-row">
        <span class="status-pill" :class="gmailStatus.connected ? 'status-good' : 'status-pending'">
          {{ gmailStatus.connected ? "Connected" : "Not connected" }}
        </span>
        <p class="job-meta" v-if="gmailStatus.gmail_account_hint">
          Account: {{ gmailStatus.gmail_account_hint }}
        </p>
      </div>
      <p class="job-meta">
        Last checked:
        {{ gmailStatus.last_checked_at ? formatDate(gmailStatus.last_checked_at) : "Never" }}
      </p>

      <div class="action-row">
        <button class="button-link auth-button" type="button" :disabled="loading" @click="connectGmail">
          {{ loading ? "Opening..." : "Connect Gmail" }}
        </button>
        <button class="button-link secondary-button" type="button" :disabled="loading" @click="pollNow">
          Poll now
        </button>
        <button class="button-link secondary-button" type="button" :disabled="loading" @click="refreshStatus">
          Refresh status
        </button>
      </div>

      <p v-if="pollMessage" class="job-meta">{{ pollMessage }}</p>
      <p v-if="error" class="auth-error">{{ error }}</p>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";

import type { GmailStatusData } from "../services/gmail";
import { getGmailAuthUrl, getGmailStatus, pollGmailNow } from "../services/gmail";

const loading = ref(false);
const error = ref<string | null>(null);
const pollMessage = ref<string>("");
const gmailStatus = reactive<GmailStatusData>({
  connected: false,
  gmail_account_hint: null,
  last_checked_at: null,
});

onMounted(async () => {
  await refreshStatus();
});

async function refreshStatus() {
  loading.value = true;
  error.value = null;
  try {
    const status = await getGmailStatus();
    gmailStatus.connected = status.connected;
    gmailStatus.gmail_account_hint = status.gmail_account_hint;
    gmailStatus.last_checked_at = status.last_checked_at;
  } catch (statusError) {
    error.value = statusError instanceof Error ? statusError.message : "Unable to load Gmail status";
  } finally {
    loading.value = false;
  }
}

async function connectGmail() {
  loading.value = true;
  error.value = null;
  try {
    const data = await getGmailAuthUrl();
    window.location.assign(data.auth_url);
  } catch (connectError) {
    error.value = connectError instanceof Error ? connectError.message : "Unable to start Gmail OAuth";
  } finally {
    loading.value = false;
  }
}

async function pollNow() {
  loading.value = true;
  error.value = null;
  pollMessage.value = "";
  try {
    const result = await pollGmailNow();
    const polled = result.polled ?? true;
    pollMessage.value = polled
      ? `Polling complete. Processed ${result.processed_messages} message(s).`
      : "Polling is not configured for this account.";
    await refreshStatus();
  } catch (pollError) {
    error.value = pollError instanceof Error ? pollError.message : "Unable to poll Gmail";
  } finally {
    loading.value = false;
  }
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString();
}
</script>
