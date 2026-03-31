<template>
  <div>
    <div class="page-header">
      <p class="page-header__eyebrow">Applications</p>
      <h1 class="page-header__title">Application Pipeline</h1>
      <p class="page-header__sub">
        Tracking {{ applications.length }} active opportunit{{ applications.length === 1 ? 'y' : 'ies' }} across recruitment stages.
      </p>
    </div>

    <div v-if="error" style="padding:0 2.5rem 1rem;">
      <div class="auth-error">{{ error }}</div>
    </div>

    <div class="apps-layout">
      <!-- Left sidebar: priority + stats -->
      <div class="apps-sidebar">

        <!-- Velocity Stats -->
        <div class="pipeline-section" v-if="stats">
          <div class="section-header" style="margin-bottom:1rem;">
            <div class="section-header__title">Velocity</div>
          </div>
            <div style="display:flex;flex-direction:column;gap:0.75rem;">
            <div class="stat-card" style="padding:1rem 1.25rem;">
              <div class="stat-card__label">Applied</div>
              <div class="stat-card__value" style="font-size:1.5rem;">{{ stats.total_applied }}<span style="font-size:1rem;color:var(--on-surface-var);font-weight:500;">/{{ stats.total_applications }}</span></div>
            </div>
            <div class="stat-card" style="padding:1rem 1.25rem;">
              <div class="stat-card__label">Response Rate</div>
              <div class="stat-card__value stat-card__value--amber" style="font-size:1.5rem;">{{ percent(stats.response_rate) }}</div>
            </div>
            <div class="stat-card" style="padding:1rem 1.25rem;">
              <div class="stat-card__label">Avg. Time to Reply</div>
              <div class="stat-card__value" style="font-size:1.1rem;font-weight:700;">
                {{ stats.avg_hours_to_first_reply === null ? 'n/a' : `${stats.avg_hours_to_first_reply.toFixed(1)}h` }}
              </div>
            </div>
          </div>
        </div>

        <!-- Priority: Interviewing -->
        <div class="pipeline-section" v-if="priorityApps.length > 0">
          <div class="section-header" style="margin-bottom:1rem;">
            <div>
              <div class="section-header__title">Priority: Interviewing</div>
              <div class="section-header__sub">Active interview stages</div>
            </div>
            <span class="chip chip-emerald">{{ priorityApps.length }}</span>
          </div>

          <div style="display:flex;flex-direction:column;gap:0.75rem;">
            <div
              v-for="app in priorityApps"
              :key="app.id"
              class="priority-card"
              :class="{ 'is-selected': selectedApplication?.id === app.id }"
              style="border: var(--border-ghost);"
              @click="selectApplication(app.id)"
            >
              <div style="display:flex;align-items:center;gap:0.75rem;">
                <div class="list-row__logo">{{ app.company_name.slice(0,2).toUpperCase() }}</div>
                <div style="flex:1;min-width:0;">
                  <div class="priority-card__company">{{ app.company_name }}</div>
                  <div class="priority-card__role">{{ app.title }}</div>
                </div>
              </div>
              <div style="display:flex;align-items:center;justify-content:space-between;gap:0.75rem;flex-wrap:wrap;">
                <span class="chip chip-emerald" style="align-self:flex-start;">
                  {{ app.status.replaceAll('_', ' ') }}
                </span>
                <button class="btn btn-primary btn-sm" type="button" @click.stop="selectApplication(app.id)">Prepare</button>
              </div>
              <div class="priority-card__datetime">
                <span class="material-symbols-outlined icon-sm">schedule</span>
                Match: {{ percent(app.match_score) }}
              </div>
            </div>
          </div>
        </div>

        <!-- Notifications -->
        <div class="pipeline-section" v-if="notifications.length > 0">
          <div class="section-header" style="margin-bottom:1rem;">
            <div class="section-header__title">Recruiter Notifications</div>
            <span class="chip chip-amber">{{ notifications.length }}</span>
          </div>
          <div style="display:flex;flex-direction:column;gap:0.5rem;">
            <div v-for="n in notifications" :key="n.application_id" style="padding:0.75rem;background:var(--surface-low);border-radius:var(--radius-md);">
              <div style="font-size:0.875rem;font-weight:600;color:var(--on-surface);">{{ n.company_name }}</div>
              <div style="font-size:0.78rem;color:var(--on-surface-var);margin-top:0.15rem;">{{ n.title }}</div>
              <div style="font-size:0.78rem;color:var(--secondary);margin-top:0.25rem;font-weight:500;">{{ n.classification.replaceAll('_', ' ') }}</div>
              <div style="font-size:0.75rem;color:var(--on-surface-var);margin-top:0.25rem;line-height:1.4;">{{ n.snippet }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right: Application list + detail -->
      <div class="apps-main">
        <!-- Filter bar -->
        <div class="pipeline-section" style="padding:1rem 1.5rem;">
          <div class="apps-filter-bar">
            <div class="apps-filter-bar__group">
              <div style="position:relative;flex:1;min-width:240px;">
                <span class="material-symbols-outlined" style="position:absolute;left:0.75rem;top:50%;transform:translateY(-50%);color:var(--on-surface-var);font-size:18px;">search</span>
                <input
                  v-model="searchQuery"
                  type="text"
                  class="field-input"
                  placeholder="Search applications..."
                  style="padding-left:2.5rem;"
                />
              </div>
              <select v-model="statusFilter" class="field-input" style="width:180px;">
                <option value="">All statuses</option>
                <option v-for="s in allStatuses" :key="s" :value="s">{{ s.replaceAll('_', ' ') }}</option>
              </select>
              <select v-model="companyFilter" class="field-input" style="width:180px;">
                <option value="">All companies</option>
                <option v-for="company in companyOptions" :key="company" :value="company">{{ company }}</option>
              </select>
              <select v-model="dateFilter" class="field-input" style="width:180px;">
                <option v-for="option in dateOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Application table / list -->
        <div class="pipeline-section" style="padding:0;overflow:hidden;">
          <div v-if="filteredApplications.length === 0" class="empty-state" style="padding:3rem;">
            <div class="empty-state__icon"><span class="material-symbols-outlined">inbox</span></div>
            <p class="empty-state__title">No applications yet</p>
            <p class="empty-state__body">Approve and auto-apply to at least one job from the Pipeline first.</p>
          </div>

          <div v-else class="applications-list">
            <div
              v-for="app in filteredApplications"
              :key="app.id"
              class="list-row"
              :style="selectedApplication?.id === app.id ? 'background:var(--surface-low);' : ''"
              style="border-radius:0;padding:1rem 1.5rem;border-bottom:1px solid rgba(199,198,202,0.15);"
              @click="selectApplication(app.id)"
            >
              <div class="list-row__logo">{{ app.company_name.slice(0,2).toUpperCase() }}</div>
              <div class="list-row__main">
                <div class="list-row__title">{{ app.title }}</div>
                <div class="list-row__sub">{{ app.company_name }}</div>
              </div>
              <div class="application-row__actions">
                <StatusChip :tone="statusTone(app.status)">
                  {{ app.status.replaceAll('_', ' ') }}
                </StatusChip>
                <span class="chip chip-neutral" v-if="isDemoApplication(app)">Demo</span>
                <span class="list-row__meta">{{ percent(app.match_score) }}</span>
                <span v-if="app.latest_email_classification" class="list-row__meta">
                  <span class="material-symbols-outlined icon-sm">mail</span>
                </span>
                <span class="application-row__timestamp">{{ formatAppliedAt(app.applied_at) }}</span>
                <button class="application-row__menu" type="button" aria-label="More actions">
                  <span class="material-symbols-outlined icon-sm">more_horiz</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Detail panel -->
        <div class="pipeline-section" v-if="selectedApplication">
          <div class="section-header" style="margin-bottom:1.25rem;">
            <div>
              <div class="section-header__title">{{ selectedApplication.title }}</div>
              <div class="section-header__sub">{{ selectedApplication.company_name }} · ATS: {{ selectedApplication.ats_provider ?? 'n/a' }}</div>
            </div>
            <div style="display:flex;gap:0.5rem;align-items:center;">
              <span class="chip" :class="statusChipClass(selectedApplication.status)">
                {{ selectedApplication.status.replaceAll('_', ' ') }}
              </span>
              <span class="chip chip-neutral" v-if="isDemoApplication(selectedApplication)">Demo</span>
            </div>
          </div>

          <!-- Update status -->
          <div v-if="availableStatusOptions.length > 0" style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1.25rem;">
            <select v-model="selectedStatus" class="field-input" style="flex:1;max-width:220px;" :disabled="statusUpdating">
              <option :value="selectedApplication.status">Current: {{ selectedApplication.status.replaceAll('_', ' ') }}</option>
              <option v-for="opt in availableStatusOptions" :key="opt" :value="opt">{{ opt.replaceAll('_', ' ') }}</option>
            </select>
            <button
              class="btn btn-secondary btn-sm"
              :disabled="statusUpdating || selectedStatus === selectedApplication.status"
              @click="applyStatusUpdate"
            >
              {{ statusUpdating ? 'Updating…' : 'Update Status' }}
            </button>
          </div>
          <p v-if="statusMessage" style="font-size:0.8125rem;color:var(--on-tertiary-c);margin-bottom:1rem;">✓ {{ statusMessage }}</p>

          <!-- Cover Letter -->
          <div style="background:var(--surface-low);border-radius:var(--radius-md);padding:1.25rem;margin-bottom:1rem;">
            <p class="font-label mb-1">Cover Letter</p>
            <p style="font-size:0.8125rem;line-height:1.75;color:var(--on-surface);white-space:pre-wrap;">{{ selectedApplication.cover_letter_text }}</p>
          </div>

          <!-- Email monitor -->
          <div v-if="selectedApplication.email_monitor" style="background:var(--surface-low);border-radius:var(--radius-md);padding:1.25rem;margin-bottom:1rem;">
            <p class="font-label mb-1">Latest Recruiter Reply</p>
            <p style="font-size:0.875rem;font-weight:600;color:var(--on-surface);">{{ selectedApplication.email_monitor.subject }}</p>
            <p style="font-size:0.8125rem;color:var(--on-surface-var);margin-top:0.4rem;line-height:1.5;">{{ selectedApplication.email_monitor.snippet }}</p>
            <span class="chip chip-emerald" style="margin-top:0.75rem;">{{ selectedApplication.email_monitor.latest_classification.replaceAll('_', ' ') }}</span>
          </div>

          <a
            v-if="selectedApplication.confirmation_url"
            class="btn btn-ghost btn-sm"
            :href="selectedApplication.confirmation_url"
            target="_blank"
            rel="noreferrer"
          >
            <span class="material-symbols-outlined icon-sm">open_in_new</span>
            Open confirmation
          </a>
        </div>

        <!-- Performance Breakdown -->
        <div class="pipeline-section" v-if="stats">
          <div class="section-header" style="margin-bottom:1rem;">
            <div class="section-header__title">Performance Breakdown</div>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
            <div v-if="stats.source_breakdown.length > 0">
              <p class="font-label mb-1">By Source</p>
              <div style="display:flex;flex-direction:column;gap:0.5rem;">
                <div v-for="item in stats.source_breakdown" :key="item.source" style="padding:0.75rem;background:var(--surface-low);border-radius:var(--radius-md);">
                  <p style="font-size:0.875rem;font-weight:600;color:var(--on-surface);">{{ item.source }}</p>
                  <p style="font-size:0.78rem;color:var(--on-surface-var);margin-top:0.15rem;">{{ item.total_applications }} apps · {{ percent(item.response_rate) }} reply rate</p>
                </div>
              </div>
            </div>
            <div v-if="stats.top_titles.length > 0">
              <p class="font-label mb-1">Top Titles</p>
              <div style="display:flex;flex-direction:column;gap:0.5rem;">
                <div v-for="item in stats.top_titles" :key="item.title" style="padding:0.75rem;background:var(--surface-low);border-radius:var(--radius-md);">
                  <p style="font-size:0.875rem;font-weight:600;color:var(--on-surface);">{{ item.title }}</p>
                  <p style="font-size:0.78rem;color:var(--on-surface-var);margin-top:0.15rem;">{{ item.total_applications }} apps · {{ percent(item.response_rate) }} reply rate</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import StatusChip from "../components/shared/StatusChip.vue";

import type {
  ApplicationDetail,
  ApplicationListItem,
  ApplicationsStats,
  ApplicationStatus,
  NotificationItem,
} from "../services/applications";
import {
  getApplicationDetail,
  getApplications,
  getApplicationsStats,
  getNotifications,
  isDemoApplication,
  subscribeNotifications,
  updateApplicationStatus,
} from "../services/applications";

const applications        = ref<ApplicationListItem[]>([]);
const selectedApplication = ref<ApplicationDetail | null>(null);
const notifications       = ref<NotificationItem[]>([]);
const stats               = ref<ApplicationsStats | null>(null);
const error               = ref<string | null>(null);
const statusMessage       = ref<string | null>(null);
const statusUpdating      = ref(false);
const selectedStatus      = ref<string>("");
const searchQuery         = ref("");
const statusFilter        = ref("");
const companyFilter       = ref("");
const dateFilter          = ref("all");
let stopNotificationsStream: (() => void) | null = null;

const forwardTransitions: Record<string, ApplicationStatus[]> = {
  pending_approval:    ["rejected", "withdrawn"],
  approved:            ["rejected", "withdrawn"],
  applied:             ["interview_requested", "rejected", "offer", "withdrawn"],
  manual_required:     ["interview_requested", "rejected", "offer", "withdrawn"],
  interview_requested: ["offer", "rejected", "withdrawn"],
  failed:              ["rejected", "withdrawn"],
};

const allStatuses = ["applied", "pending_approval", "approved", "rejected", "interview_requested", "offer", "withdrawn", "failed", "manual_required"];

const priorityApps = computed(() =>
  applications.value.filter(a => a.status === "interview_requested").slice(0, 3)
);

const filteredApplications = computed(() => {
  return applications.value.filter(a => {
    const q = searchQuery.value.toLowerCase();
    const matchesQ = !q || a.title.toLowerCase().includes(q) || a.company_name.toLowerCase().includes(q);
    const matchesS = !statusFilter.value || a.status === statusFilter.value;
    const matchesCompany = !companyFilter.value || a.company_name === companyFilter.value;
    const matchesDate = matchesDateFilter(a.applied_at);
    return matchesQ && matchesS && matchesCompany && matchesDate;
  });
});

const companyOptions = computed(() => {
  return [...new Set(applications.value.map((application) => application.company_name))].sort((left, right) => left.localeCompare(right));
});

const dateOptions = [
  { value: "all", label: "All dates" },
  { value: "7d", label: "Past 7 days" },
  { value: "30d", label: "Past 30 days" },
  { value: "90d", label: "Past 90 days" },
];

const availableStatusOptions = computed(() =>
  selectedApplication.value ? (forwardTransitions[selectedApplication.value.status] ?? []) : []
);

watch(selectedApplication, (app) => {
  selectedStatus.value = app?.status ?? "";
  statusMessage.value  = null;
}, { immediate: true });

onMounted(async () => {
  await loadApplications();
  await loadStats();
  await loadNotifications();
  stopNotificationsStream = subscribeNotifications(
    (payload) => { notifications.value = payload.items; },
    (err)     => { error.value = err.message; },
  );
});

onBeforeUnmount(() => {
  stopNotificationsStream?.();
  stopNotificationsStream = null;
});

async function loadApplications() {
  try {
    error.value = null;
    const response = await getApplications();
    applications.value = response.items;
    if (response.items.length > 0) await selectApplication(response.items[0].id);
  } catch (e) { error.value = e instanceof Error ? e.message : "Unable to load applications"; }
}

async function loadNotifications() {
  try { const r = await getNotifications(); notifications.value = r.items; } catch {}
}

async function loadStats() {
  try { stats.value = await getApplicationsStats(); } catch {}
}

async function selectApplication(id: string) {
  try { selectedApplication.value = await getApplicationDetail(id); }
  catch (e) { error.value = e instanceof Error ? e.message : "Unable to load application detail"; }
}

async function applyStatusUpdate() {
  if (!selectedApplication.value) return;
  if (selectedStatus.value === selectedApplication.value.status) return;
  statusUpdating.value = true;
  statusMessage.value  = null;
  error.value          = null;
  try {
    await updateApplicationStatus(selectedApplication.value.id, selectedStatus.value as ApplicationStatus);
    selectedApplication.value.status = selectedStatus.value;
    const idx = applications.value.findIndex(a => a.id === selectedApplication.value?.id);
    if (idx >= 0) applications.value[idx] = { ...applications.value[idx], status: selectedStatus.value };
    await loadStats();
    statusMessage.value = "Status updated.";
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Unable to update status";
    selectedStatus.value = selectedApplication.value.status;
  } finally { statusUpdating.value = false; }
}

function percent(value: number): string { return `${Math.round(value * 100)}%`; }

function formatAppliedAt(value: string | null): string {
  if (!value) return "Queued";
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function matchesDateFilter(value: string | null): boolean {
  if (dateFilter.value === "all" || !value) return true;

  const appliedAt = new Date(value).getTime();
  const now = Date.now();
  const days = dateFilter.value === "7d" ? 7 : dateFilter.value === "30d" ? 30 : 90;
  return now - appliedAt <= days * 24 * 60 * 60 * 1000;
}

function statusTone(status: string): "neutral" | "amber" | "emerald" | "error" {
  if (status === "interview_requested" || status === "offer") return "emerald";
  if (status === "applied" || status === "approved") return "amber";
  if (status === "rejected" || status === "failed") return "error";
  return "neutral";
}

function statusChipClass(status: string): string {
  if (status === "applied" || status === "approved")           return "chip chip-amber";
  if (status === "interview_requested" || status === "offer")  return "chip chip-emerald";
  if (status === "rejected" || status === "failed")            return "chip chip-error";
  if (status === "withdrawn")                                  return "chip chip-neutral";
  return "chip chip-neutral";
}
</script>
