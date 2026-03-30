<template>
  <main class="grid applications-layout">
    <section class="panel">
      <p class="eyebrow">Application Tracker</p>
      <h2>Track submitted applications, recruiter replies, and status changes from one place.</h2>
      <p class="lede">
        This view combines application outcomes with the response-tracking layer so interview requests and rejections are visible immediately.
      </p>

      <p v-if="error" class="auth-error">{{ error }}</p>

      <div v-if="stats" class="detail-block">
        <p class="eyebrow muted">Velocity Snapshot</p>
        <p class="job-meta">Applied: {{ stats.total_applied }} / {{ stats.total_applications }}</p>
        <p class="job-meta">Replies: {{ stats.total_replied }} ({{ percent(stats.response_rate) }})</p>
        <p class="job-meta">
          Avg. time to first reply:
          {{ stats.avg_hours_to_first_reply === null ? "n/a" : `${stats.avg_hours_to_first_reply.toFixed(1)} hours` }}
        </p>
      </div>

      <div v-if="applications.length === 0" class="empty-state">
        <p class="lede">No applications yet. Approve and auto-apply to at least one job first.</p>
      </div>

      <article
        v-for="application in applications"
        :key="application.id"
        class="job-card"
        :class="{ active: selectedApplication?.id === application.id }"
        @click="selectApplication(application.id)"
      >
        <div class="job-card-head">
          <div>
            <h3>{{ application.title }}</h3>
            <p class="job-meta">{{ application.company_name }}</p>
          </div>
          <span class="status-pill">{{ application.status.replaceAll("_", " ") }}</span>
        </div>
        <p class="job-meta">Match score: {{ percent(application.match_score) }}</p>
        <p v-if="application.latest_email_classification" class="job-meta">
          Latest reply: {{ application.latest_email_classification.replaceAll("_", " ") }}
        </p>
      </article>
    </section>

    <section class="panel">
      <p class="eyebrow">Application Detail</p>
      <template v-if="selectedApplication">
        <h3>{{ selectedApplication.title }}</h3>
        <p class="job-meta">{{ selectedApplication.company_name }}</p>
        <p class="job-meta">ATS: {{ selectedApplication.ats_provider ?? "n/a" }}</p>

        <div class="detail-block">
          <p class="eyebrow muted">Cover Letter</p>
          <p class="lede compact">{{ selectedApplication.cover_letter_text }}</p>
        </div>

        <div class="detail-block" v-if="selectedApplication.email_monitor">
          <p class="eyebrow muted">Latest Recruiter Reply</p>
          <p class="job-meta">{{ selectedApplication.email_monitor.subject }}</p>
          <p class="lede compact">{{ selectedApplication.email_monitor.snippet }}</p>
          <p class="job-meta">
            Classification: {{ selectedApplication.email_monitor.latest_classification.replaceAll("_", " ") }}
          </p>
        </div>

        <a
          v-if="selectedApplication.confirmation_url"
          class="button-link secondary-button"
          :href="selectedApplication.confirmation_url"
          target="_blank"
          rel="noreferrer"
        >
          Open confirmation
        </a>
      </template>
      <p v-else class="lede">Select an application to inspect its latest status and recruiter response.</p>
    </section>

    <section class="panel">
      <p class="eyebrow">Performance Breakdown</p>
      <div v-if="stats === null" class="empty-state">
        <p class="lede">No stats yet.</p>
      </div>
      <template v-else>
        <div class="detail-block">
          <p class="eyebrow muted">By Source</p>
          <article v-for="item in stats.source_breakdown" :key="item.source" class="approval-card">
            <h3>{{ item.source }}</h3>
            <p class="job-meta">Applications: {{ item.total_applications }}</p>
            <p class="job-meta">Replies: {{ item.replied_count }} ({{ percent(item.response_rate) }})</p>
          </article>
        </div>

        <div class="detail-block">
          <p class="eyebrow muted">Top Titles</p>
          <article v-for="item in stats.top_titles" :key="item.title" class="approval-card">
            <h3>{{ item.title }}</h3>
            <p class="job-meta">Applications: {{ item.total_applications }}</p>
            <p class="job-meta">Replies: {{ item.replied_count }} ({{ percent(item.response_rate) }})</p>
          </article>
        </div>
      </template>
    </section>

    <section class="panel">
      <p class="eyebrow">Notifications</p>
      <div v-if="notifications.length === 0" class="empty-state">
        <p class="lede">No recruiter notifications yet.</p>
      </div>
      <article v-for="notification in notifications" :key="notification.application_id" class="approval-card">
        <h3>{{ notification.company_name }}</h3>
        <p class="job-meta">{{ notification.title }}</p>
        <p class="job-meta">{{ notification.classification.replaceAll("_", " ") }}</p>
        <p class="lede compact">{{ notification.snippet }}</p>
      </article>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";

import type {
  ApplicationDetail,
  ApplicationListItem,
  ApplicationsStats,
  NotificationItem,
} from "../services/applications";
import {
  getApplicationDetail,
  getApplications,
  getApplicationsStats,
  getNotifications,
  subscribeNotifications,
} from "../services/applications";

const applications = ref<ApplicationListItem[]>([]);
const selectedApplication = ref<ApplicationDetail | null>(null);
const notifications = ref<NotificationItem[]>([]);
const stats = ref<ApplicationsStats | null>(null);
const error = ref<string | null>(null);
let stopNotificationsStream: (() => void) | null = null;

onMounted(async () => {
  await loadApplications();
  await loadStats();
  await loadNotifications();

  stopNotificationsStream = subscribeNotifications(
    (notificationPayload) => {
      notifications.value = notificationPayload.items;
    },
    (streamError) => {
      error.value = streamError.message;
    },
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
    if (response.items.length > 0) {
      await selectApplication(response.items[0].id);
    }
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : "Unable to load applications";
  }
}

async function loadNotifications() {
  try {
    const response = await getNotifications();
    notifications.value = response.items;
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : "Unable to load notifications";
  }
}

async function loadStats() {
  try {
    stats.value = await getApplicationsStats();
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : "Unable to load application stats";
  }
}

async function selectApplication(applicationId: string) {
  try {
    selectedApplication.value = await getApplicationDetail(applicationId);
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : "Unable to load application detail";
  }
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}
</script>
