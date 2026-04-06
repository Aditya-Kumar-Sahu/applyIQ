<template>
  <div class="dashboard-view">
    <div class="page-header">
      <p class="page-header__eyebrow">Command Center</p>
      <h1 class="page-header__title">Dashboard</h1>
      <p class="page-header__sub">
        A live view of active sourcing, approval flow, and recruiter response.
      </p>
    </div>

    <div v-if="errorMessage" style="padding: 0 2.5rem 1rem;">
      <div class="auth-error">{{ errorMessage }}</div>
    </div>

    <div class="dashboard-grid">
      <div class="dashboard-grid__hero">
        <DashboardHero :stats="heroStats" />
      </div>

      <div class="dashboard-grid__aside">
        <TopMatchesCard :matches="topMatches" @review="openApprovalQueue" />
      </div>

      <div class="dashboard-grid__feed">
        <SystemFeedLog :entries="feedEntries" />
      </div>

      <AppCard class="dashboard-insight app-card--interactive" tone="soft">
        <div class="dashboard-insight__header">
          <div>
            <p class="label-md dashboard-insight__eyebrow">Portfolio Health</p>
            <h2 class="dashboard-insight__title">Active profile snapshot</h2>
          </div>
          <StatusChip tone="neutral">{{ profileStateLabel }}</StatusChip>
        </div>

        <div class="dashboard-insight__metrics">
          <div class="dashboard-insight__metric">
            <span class="dashboard-insight__metric-label">Resume</span>
            <strong class="dashboard-insight__metric-value">{{ resumeSummary }}</strong>
          </div>
          <div class="dashboard-insight__metric">
            <span class="dashboard-insight__metric-label">Sources</span>
            <strong class="dashboard-insight__metric-value">{{ sourceSummary }}</strong>
          </div>
          <div class="dashboard-insight__metric">
            <span class="dashboard-insight__metric-label">Pipeline</span>
            <strong class="dashboard-insight__metric-value">{{ pipelineSummary }}</strong>
          </div>
        </div>

        <div class="dashboard-insight__actions">
          <BaseButton as="a" href="/pipeline" variant="primary" size="sm">
            Start pipeline
            <span class="material-symbols-outlined">play_arrow</span>
          </BaseButton>
          <BaseButton as="a" href="/profile" variant="secondary" size="sm">
            Review profile
            <span class="material-symbols-outlined">person</span>
          </BaseButton>
        </div>
      </AppCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import AppCard from '../components/shared/AppCard.vue';
import BaseButton from '../components/shared/BaseButton.vue';
import StatusChip from '../components/shared/StatusChip.vue';
import DashboardHero from '../components/pages/dashboard/DashboardHero.vue';
import TopMatchesCard from '../components/pages/dashboard/TopMatchesCard.vue';
import SystemFeedLog from '../components/pages/dashboard/SystemFeedLog.vue';
import type { ApplicationsStats, NotificationItem } from '../services/applications';
import { getApplicationsStats, getNotifications } from '../services/applications';
import type { PipelineResults } from '../services/pipeline';
import type { RankedJob } from '../services/jobs';
import { store } from '../store';

type DashboardFeedEntry = {
  id: string | number;
  title: string;
  detail: string;
  time: string;
  tone: 'amber' | 'emerald' | 'neutral';
};

type DashboardMatch = {
  title: string;
  company: string;
  source: string;
  location: string;
  salary: string;
  score?: number | null;
};

const router = useRouter();
const applicationsStats = ref<ApplicationsStats | null>(null);
const notifications = ref<NotificationItem[]>([]);
const loadError = ref<string | null>(null);
const errorMessage = computed(() => loadError.value);

const jobs = computed(() => store.getters.jobs as RankedJob[]);
const pipelineRun = computed(() => store.getters.pipelineRun as PipelineResults | null);
const pipelineResults = computed(() => store.getters.pipelineResults as PipelineResults | null);
const resumeProfile = computed(() => store.getters.resumeProfile as { current_title?: string; years_of_experience?: number } | null);
const profileCompleteness = computed(() => store.getters.profileCompleteness as { score: number } | null);

const heroStats = computed(() => {
  const results = pipelineResults.value;
  const stats = applicationsStats.value;
  const pendingApprovalCount =
    pipelineRun.value?.pending_approvals_count ??
    results?.applications.filter((application) => application.status === 'pending_approval').length ??
    0;

  return [
    {
      label: 'Jobs Found',
      value: pipelineRun.value?.jobs_found ?? results?.jobs_found ?? jobs.value.length,
      subtext: 'Across all active sources',
    },
    {
      label: 'Pending Approval',
      value: pendingApprovalCount,
      subtext: 'Ready for review',
      toneClass: 'dashboard-stat__value--amber',
    },
    {
      label: 'Replies',
      value: stats?.total_replied ?? 0,
      subtext: `${Math.round((stats?.response_rate ?? 0) * 100)}% response rate`,
      toneClass: 'dashboard-stat__value--emerald',
    },
  ];
});

const topMatches = computed<DashboardMatch[]>(() =>
  pipelineResults.value ?
  [...jobs.value]
    .sort((left, right) => right.match_score - left.match_score)
    .slice(0, 4)
    .map((job) => ({
      title: job.title,
      company: job.company_name,
      source: job.source,
      location: job.is_remote ? 'Remote' : job.location,
      salary: formatSalary(job.salary_min, job.salary_max),
      score: Math.round(job.match_score),
    })) : []
);

const feedEntries = computed<DashboardFeedEntry[]>(() => {
  if (notifications.value.length > 0) {
    return notifications.value.slice(0, 5).map((item) => ({
      id: item.application_id,
      title: item.company_name,
      detail: `${item.title} · ${formatClassification(item.classification)}`,
      time: formatRelativeTime(item.created_at),
      tone: toneFromClassification(item.classification),
    }));
  }

  if (pipelineResults.value) {
    return [
      {
        id: 'pipeline-status',
        title: 'Pipeline status',
        detail: `${pipelineResults.value.jobs_found} jobs found · ${pipelineResults.value.jobs_matched} matched`,
        time: pipelineResults.value.completed_at ? 'Complete' : 'Live',
        tone: pipelineResults.value.status === 'complete' ? 'emerald' : 'amber',
      },
      {
        id: 'pipeline-submitted',
        title: 'Applications submitted',
        detail: `${pipelineResults.value.applications_submitted} applications pushed to employers`,
        time: 'Current run',
        tone: 'neutral',
      },
    ];
  }

  return [
    {
      id: 'dashboard-empty',
      title: 'No live events yet',
      detail: 'Run the pipeline to populate the system feed.',
      time: 'Ready',
      tone: 'neutral',
    },
  ];
});

const profileStateLabel = computed(() => {
  if (profileCompleteness.value) {
    return `${profileCompleteness.value.score}% complete`;
  }

  return resumeProfile.value ? 'Profile loaded' : 'No resume yet';
});

const resumeSummary = computed(() => {
  const title = resumeProfile.value?.current_title;
  const experience = resumeProfile.value?.years_of_experience;

  if (!title && experience == null) {
    return 'Upload your resume';
  }

  if (title && experience != null) {
    return `${title} · ${experience}y exp`;
  }

  return title ?? `${experience}y exp`;
});

const sourceSummary = computed(() => `${jobs.value.length} jobs tracked`);
const pipelineSummary = computed(() => {
  if (!pipelineResults.value) {
    return 'Idle';
  }

  return pipelineResults.value.status === 'complete' ? 'Complete' : 'Live';
});

function formatSalary(min: number | null, max: number | null): string {
  if (min == null && max == null) {
    return 'Salary undisclosed';
  }

  const formatValue = (value: number) => `$${Math.round(value / 1000)}k`;

  if (min != null && max != null) {
    return `${formatValue(min)}-${formatValue(max)}`;
  }

  if (min != null) {
    return `From ${formatValue(min)}`;
  }

  return `Up to ${formatValue(max ?? 0)}`;
}

function formatClassification(classification: string): string {
  return classification.replaceAll('_', ' ');
}

function toneFromClassification(classification: string): 'amber' | 'emerald' | 'neutral' {
  if (classification.includes('interview') || classification.includes('reply') || classification.includes('positive')) {
    return 'emerald';
  }

  if (classification.includes('rejection') || classification.includes('negative')) {
    return 'amber';
  }

  return 'neutral';
}

function formatRelativeTime(value: string): string {
  const timestamp = new Date(value).getTime();

  if (Number.isNaN(timestamp)) {
    return 'Just now';
  }

  const diffMinutes = Math.max(1, Math.round((Date.now() - timestamp) / 60000));

  if (diffMinutes < 60) {
    return `${diffMinutes}m ago`;
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours}h ago`;
  }

  const diffDays = Math.round(diffHours / 24);
  return `${diffDays}d ago`;
}

function openApprovalQueue() {
  router.push({ name: 'approval' });
}

onMounted(async () => {
  const tasks: Promise<unknown>[] = [];

  if (jobs.value.length === 0) {
    tasks.push(store.dispatch('fetchJobs'));
  }

  tasks.push(getApplicationsStats().then((value) => {
    applicationsStats.value = value;
  }).catch(() => {
    applicationsStats.value = null;
  }));

  tasks.push(getNotifications().then((value) => {
    notifications.value = value.items;
  }).catch((error) => {
    notifications.value = [];
    loadError.value = error instanceof Error ? error.message : 'Unable to load dashboard data';
  }));

  await Promise.allSettled(tasks);
});
</script>

<style scoped>
.dashboard-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(22rem, 0.95fr);
  gap: 1.25rem;
  align-items: start;
}

.dashboard-grid__hero,
.dashboard-grid__aside,
.dashboard-grid__feed,
.dashboard-insight {
  min-width: 0;
}

.dashboard-grid__hero {
  grid-column: 1 / -1;
}

.dashboard-grid__feed {
  grid-column: 1;
}

.dashboard-grid__aside {
  grid-column: 2;
  grid-row: 2 / span 2;
}

.dashboard-insight {
  grid-column: 1;
  padding: 1.5rem;
}

.dashboard-insight__header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  margin-bottom: 1.25rem;
}

.dashboard-insight__eyebrow,
.dashboard-insight__title,
.dashboard-insight__metric-label,
.dashboard-insight__metric-value {
  margin: 0;
}

.dashboard-insight__title {
  font-family: 'Manrope', sans-serif;
  font-size: 1.25rem;
  font-weight: 700;
  letter-spacing: -0.03em;
}

.dashboard-insight__metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}

.dashboard-insight__metric {
  padding: 1rem;
  border-radius: var(--radius-lg);
  background: var(--surface-low);
  min-width: 0;
}

.dashboard-insight__metric-label {
  display: block;
  color: var(--on-surface-variant);
  margin-bottom: 0.35rem;
}

.dashboard-insight__metric-value {
  display: block;
  color: var(--on-surface);
  font-family: 'Manrope', sans-serif;
  font-size: 1rem;
  font-weight: 700;
  line-height: 1.35;
}

.dashboard-insight__actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-top: 1.25rem;
}

@media (max-width: 1100px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }

  .dashboard-grid__hero,
  .dashboard-grid__feed,
  .dashboard-grid__aside,
  .dashboard-insight {
    grid-column: auto;
    grid-row: auto;
  }

  .dashboard-insight__metrics {
    grid-template-columns: 1fr;
  }
}
</style>