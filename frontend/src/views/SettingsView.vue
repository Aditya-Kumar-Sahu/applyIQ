<template>
  <div>
    <div class="page-header">
      <p class="page-header__eyebrow">Settings & Integrations</p>
      <h1 class="page-header__title">Workspace Settings</h1>
      <p class="page-header__sub">Configure automation preferences, security protocols, and external service integrations.</p>
    </div>

    <div class="settings-layout">
      <!-- Category Nav -->
      <nav class="settings-nav" aria-label="Settings categories">
        <button
          v-for="cat in categories"
          :key="cat.id"
          class="nav-item"
          :class="{ active: selectedCategory === cat.id }"
          style="width:100%;justify-content:flex-start;border-radius:var(--radius-md);"
          @click="selectedCategory = cat.id"
        >
          <span class="material-symbols-outlined">{{ cat.icon }}</span>
          {{ cat.label }}
        </button>
      </nav>

      <!-- Panel content -->
      <div class="settings-panel">

        <!-- === Gmail Integration === -->
        <template v-if="selectedCategory === 'gmail'">
          <div class="settings-section">
            <div class="section-header" style="margin-bottom:1.25rem;">
              <div>
                <div class="section-header__title">Gmail Connection</div>
                <div class="section-header__sub">Sync your inbox for real-time response tracking.</div>
              </div>
              <span class="chip" :class="gmailStatus.connected ? 'chip-emerald' : 'chip-neutral'">
                <span class="material-symbols-outlined icon-sm">{{ gmailStatus.connected ? 'wifi' : 'wifi_off' }}</span>
                {{ gmailStatus.connected ? 'Connected' : 'Not connected' }}
              </span>
            </div>

            <div v-if="gmailStatus.gmail_account_hint" style="font-size:0.8125rem;color:var(--on-surface-var);margin-bottom:0.75rem;">
              Account: <strong style="color:var(--on-surface);">{{ gmailStatus.gmail_account_hint }}</strong>
            </div>
            <div style="font-size:0.8125rem;color:var(--on-surface-var);margin-bottom:1.25rem;">
              Last checked: {{ gmailStatus.last_checked_at ? formatDate(gmailStatus.last_checked_at) : 'Never' }}
            </div>

            <div style="display:flex;gap:0.75rem;flex-wrap:wrap;">
              <button class="btn btn-primary" :disabled="loading" @click="connectGmail">
                <span class="material-symbols-outlined icon-sm">mail</span>
                {{ loading ? 'Opening…' : 'Connect Gmail' }}
              </button>
              <button class="btn btn-secondary" :disabled="loading" @click="pollNow">Poll now</button>
              <button class="btn btn-ghost" :disabled="loading" @click="refreshStatus">Refresh</button>
            </div>

            <p v-if="pollMessage" style="margin-top:0.75rem;font-size:0.8125rem;color:var(--on-tertiary-c);">✓ {{ pollMessage }}</p>
            <div v-if="error" class="auth-error" style="margin-top:0.75rem;">{{ error }}</div>
          </div>

          <div class="settings-section">
            <div class="section-header" style="margin-bottom:0.5rem;"><div class="section-header__title">Automation Rules</div></div>
            <div class="toggle-row">
              <div class="toggle-row__info">
                <p class="toggle-row__label">Automatic Follow-up</p>
                <p class="toggle-row__desc">Preview only. Automatic follow-up drafting is not enabled in this build.</p>
              </div>
              <label class="toggle-switch">
                <input type="checkbox" v-model="autoFollowup" disabled title="Coming soon" />
                <span class="toggle-track"></span>
              </label>
            </div>
            <div class="toggle-row">
              <div class="toggle-row__info">
                <p class="toggle-row__label">Ghost Mode</p>
                <p class="toggle-row__desc">Preview only. Ghost mode is not configurable in this build.</p>
              </div>
              <label class="toggle-switch">
                <input type="checkbox" v-model="ghostMode" disabled title="Coming soon" />
                <span class="toggle-track"></span>
              </label>
            </div>
          </div>
        </template>

        <!-- === General Profile === -->
        <template v-if="selectedCategory === 'general'">
          <div class="settings-section">
            <div class="section-header" style="margin-bottom:1.25rem;"><div class="section-header__title">General Profile</div></div>
            <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem;">
              <div class="sidebar__avatar" style="width:3.5rem;height:3.5rem;font-size:1.1rem;">{{ initials }}</div>
              <div>
                <p style="font-size:1rem;font-weight:700;color:var(--on-surface);">{{ currentUser?.full_name ?? '—' }}</p>
                <p style="font-size:0.8125rem;color:var(--on-surface-var);">{{ currentUser?.email ?? '—' }}</p>
                <span class="chip chip-amber" style="margin-top:0.35rem;">{{ planLabel }}</span>
              </div>
            </div>
            <div class="advisory">
              <span class="material-symbols-outlined">info</span>
              <p class="advisory__text">To update your name or email, please contact support. Account details are managed through secure channels.</p>
            </div>
          </div>
        </template>

        <!-- === Security === -->
        <template v-if="selectedCategory === 'security'">
          <div class="settings-section">
            <div class="section-header" style="margin-bottom:1.25rem;"><div class="section-header__title">Security & Privacy</div></div>
            <div class="advisory" style="margin-bottom:1.5rem;">
              <span class="material-symbols-outlined">lock</span>
              <p class="advisory__text">Your data is encrypted server-side and private mailbox content is not shared with third-party training models.</p>
            </div>
            <div style="display:flex;gap:0.75rem;flex-wrap:wrap;">
              <button class="btn btn-secondary" type="button" disabled title="Coming soon">Change Password</button>
              <button class="btn btn-ghost" type="button" style="color:var(--error);" disabled title="Coming soon">Delete Account</button>
              <button class="btn btn-danger" @click="handleLogout">
                <span class="material-symbols-outlined icon-sm">logout</span>
                Sign out
              </button>
            </div>
          </div>
        </template>

        <!-- === Integrations === -->
        <template v-if="selectedCategory === 'integrations'">
          <div class="settings-section">
            <div class="section-header" style="margin-bottom:1.25rem;"><div class="section-header__title">External Integrations</div></div>
            <div class="advisory" style="margin-bottom:1rem;">
              <span class="material-symbols-outlined">info</span>
              <p class="advisory__text">These connectors are shown for reference only and are not active in this build.</p>
            </div>
            <div style="display:flex;flex-direction:column;gap:1rem;">
              <div v-for="intg in integrations" :key="intg.name" style="display:flex;align-items:center;justify-content:space-between;padding:1rem 1.25rem;background:var(--surface-low);border-radius:var(--radius-md);">
                <div>
                  <p style="font-size:0.9rem;font-weight:600;color:var(--on-surface);">{{ intg.name }}</p>
                  <p style="font-size:0.78rem;color:var(--on-surface-var);margin-top:0.15rem;">{{ intg.desc }}</p>
                </div>
                <button class="btn btn-secondary btn-sm" type="button" disabled title="Coming soon">Coming soon</button>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import type { GmailStatusData } from "../services/gmail";
import { getGmailAuthUrl, getGmailStatus, pollGmailNow } from "../services/gmail";
import { store } from "../store";

const router          = useRouter();
const selectedCategory= ref("gmail");
const loading         = ref(false);
const error           = ref<string | null>(null);
const pollMessage     = ref("");
const autoFollowup    = ref(false);
const ghostMode       = ref(false);

const gmailStatus = reactive<GmailStatusData>({
  connected: false,
  gmail_account_hint: null,
  last_checked_at: null,
});

const categories = [
  { id: "gmail",        icon: "mail",        label: "Gmail"        },
  { id: "general",      icon: "person",      label: "General"      },
  { id: "security",     icon: "lock",        label: "Security"     },
  { id: "integrations", icon: "link",        label: "Integrations" },
];

const integrations = [
  { name: "LinkedIn",   desc: "Connect for job scraping and network insights."    },
  { name: "Greenhouse", desc: "Auto-populate ATS applications."                   },
  { name: "Lever",      desc: "Track Lever-hosted job applications automatically." },
];

const currentUser = computed(() => store.getters.authUser as { full_name: string; email: string; subscription_tier?: string } | null);
const planLabel = computed(() => currentUser.value?.subscription_tier ?? "Plan unavailable");
const initials    = computed(() => {
  const parts = (currentUser.value?.full_name ?? "?").split(" ");
  return parts.map((p: string) => p[0]).slice(0, 2).join("").toUpperCase();
});

onMounted(async () => { await refreshStatus(); });

async function refreshStatus() {
  loading.value = true; error.value = null;
  try {
    const s = await getGmailStatus();
    gmailStatus.connected = s.connected;
    gmailStatus.gmail_account_hint = s.gmail_account_hint;
    gmailStatus.last_checked_at = s.last_checked_at;
  } catch (e) { error.value = e instanceof Error ? e.message : "Unable to load Gmail status"; }
  finally { loading.value = false; }
}

async function connectGmail() {
  loading.value = true; error.value = null;
  try { const d = await getGmailAuthUrl(); window.location.assign(d.auth_url); }
  catch (e) { error.value = e instanceof Error ? e.message : "Unable to start Gmail OAuth"; }
  finally { loading.value = false; }
}

async function pollNow() {
  loading.value = true; error.value = null; pollMessage.value = "";
  try {
    const r = await pollGmailNow();
    pollMessage.value = (r.polled ?? true)
      ? `Polling complete. Processed ${r.processed_messages} message(s).`
      : "Polling is not configured for this account.";
    await refreshStatus();
  } catch (e) { error.value = e instanceof Error ? e.message : "Unable to poll Gmail"; }
  finally { loading.value = false; }
}

function formatDate(v: string): string { return new Date(v).toLocaleString(); }

async function handleLogout() {
  await store.dispatch("logout");
  await router.replace({ name: "login" });
}
</script>
