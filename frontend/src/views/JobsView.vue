<template>
  <main class="jobs-layout">
    <div class="page-header jobs-header">
      <p class="page-header__eyebrow">Match Engine</p>
      <h1 class="page-header__title">Jobs</h1>
      <p class="page-header__sub">
        Ranked results from the latest scrape. Use the top bar to search by role, skill, or natural language.
      </p>
      <p v-if="jobsError" class="auth-error" style="margin-top:1rem;">{{ jobsError }}</p>
      <p v-else-if="jobsStatus === 'loading'" class="page-header__sub" style="margin-top:1rem;">Refreshing ranked jobs...</p>
      <p v-else class="page-header__sub" style="margin-top:1rem;">Showing {{ jobs.length }} ranked jobs.</p>
    </div>

    <section class="panel jobs-list-panel">
      <p class="eyebrow">Top Matches</p>
      <div v-if="jobsStatus === 'loading' && jobs.length === 0" class="empty-state">
        <p class="lede">Ranking jobs now. This usually takes a moment.</p>
      </div>
      <div v-else-if="jobs.length === 0" class="empty-state">
        <p class="lede">No ranked jobs yet. Run a scrape first, then return here for matching.</p>
      </div>
      <article
        v-for="job in jobs"
        :key="job.job_id"
        class="job-card"
        :class="{ active: selectedJob?.job_id === job.job_id }"
        @click="selectJob(job.job_id)"
      >
        <div class="job-card-head">
          <div>
            <h3>{{ job.title }}</h3>
            <p class="job-meta">{{ job.company_name }} · {{ job.location }}</p>
            <div style="margin-top:0.35rem;">
              <span class="chip">{{ job.source }}</span>
            </div>
          </div>
          <div class="score-pill">{{ percent(job.match_score) }}</div>
        </div>
        <p class="lede compact">{{ job.one_line_reason }}</p>
        <div class="chip-row">
          <span v-for="skill in job.matched_skills.slice(0, 3)" :key="skill" class="chip">{{ skill }}</span>
        </div>
      </article>
    </section>

    <section class="panel job-detail-panel">
      <p class="eyebrow">Job Detail</p>
      <template v-if="selectedJob">
        <h3>{{ selectedJob.title }}</h3>
        <p class="lede">{{ selectedJob.company_name }} · {{ selectedJob.location }}</p>
        <p class="lede compact">Source: {{ selectedJob.source }}</p>
        <div class="metrics-grid">
          <article class="metric-card">
            <span>Semantic</span>
            <strong>{{ percent(selectedJob.score_breakdown.semantic_similarity) }}</strong>
          </article>
          <article class="metric-card">
            <span>Skills</span>
            <strong>{{ percent(selectedJob.score_breakdown.skills_coverage) }}</strong>
          </article>
          <article class="metric-card">
            <span>Seniority</span>
            <strong>{{ percent(selectedJob.score_breakdown.seniority_alignment) }}</strong>
          </article>
          <article class="metric-card">
            <span>Location</span>
            <strong>{{ percent(selectedJob.score_breakdown.location_match) }}</strong>
          </article>
          <article class="metric-card">
            <span>Salary</span>
            <strong>{{ percent(selectedJob.score_breakdown.salary_alignment) }}</strong>
          </article>
        </div>

        <div class="detail-block">
          <p class="eyebrow muted">Description</p>
          <p class="lede compact">{{ selectedJob.description_text }}</p>
        </div>

        <div class="detail-block">
          <p class="eyebrow muted">Matched Skills</p>
          <div class="chip-row">
            <span v-for="skill in selectedJob.matched_skills" :key="skill" class="chip">{{ skill }}</span>
          </div>
        </div>

        <div class="detail-block" v-if="selectedJob.missing_skills.length > 0">
          <p class="eyebrow muted">Potential Gaps</p>
          <div class="chip-row">
            <span v-for="skill in selectedJob.missing_skills" :key="skill" class="chip muted-chip">{{ skill }}</span>
          </div>
        </div>

        <a class="button-link" :href="selectedJob.apply_url" target="_blank" rel="noreferrer">Open apply page</a>
      </template>
      <p v-else-if="jobsStatus === 'loading'" class="lede">Loading ranked jobs...</p>
      <p v-else class="lede">Select a ranked job to inspect the match breakdown and description.</p>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, watch } from "vue";
import { useRoute } from "vue-router";

import type { JobDetail, RankedJob } from "../services/jobs";
import { store } from "../store";

const route = useRoute();
const jobs = computed(() => store.getters.jobs as RankedJob[]);
const jobsStatus = computed(() => store.getters.jobsStatus as string);
const jobsError = computed(() => store.getters.jobsError as string | null);
const selectedJob = computed(() => store.getters.selectedJob as JobDetail | null);

watch(
  () => route.query.q,
  async (query) => {
    const normalizedQuery = typeof query === "string" ? query.trim() : "";

    if (!normalizedQuery) {
      await store.dispatch("fetchJobs");
      return;
    }

    await store.dispatch("searchJobs", normalizedQuery);
  },
  { immediate: true },
);

async function selectJob(jobId: string) {
  await store.dispatch("fetchJobDetail", jobId);
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}
</script>

<style scoped>
.jobs-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr);
  gap: 1.25rem;
  align-items: start;
}

.jobs-header {
  grid-column: 1 / -1;
}

.panel {
  background: var(--surface-lowest);
  border-radius: var(--radius-xl);
  border: var(--border-ghost);
  box-shadow: var(--shadow-whisper);
  padding: 1.5rem;
}

.eyebrow {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--on-surface-var);
}

.lede {
  max-width: 68ch;
  color: var(--on-surface-var);
  font-size: 0.95rem;
  line-height: 1.65;
}

.compact {
  max-width: 56ch;
}

.jobs-list-panel,
.job-detail-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-width: 0;
}

.job-detail-panel {
  position: sticky;
  top: 6.5rem;
}

.empty-state {
  align-items: flex-start;
  justify-content: flex-start;
  text-align: left;
  padding: 2rem 1.25rem;
  border-radius: var(--radius-lg);
  background: var(--surface-low);
  border: 1px dashed rgba(199, 198, 202, 0.7);
}

.job-card {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  padding: 1rem 1.05rem;
  border-radius: var(--radius-lg);
  border: 1px solid rgba(199, 198, 202, 0.45);
  background: var(--surface-lowest);
  cursor: pointer;
  transition: transform var(--ease-ui), box-shadow var(--ease-ui), border-color var(--ease-ui), background var(--ease-ui);
}

.job-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-float);
  border-color: rgba(144, 77, 0, 0.24);
}

.job-card.active {
  border-color: rgba(144, 77, 0, 0.4);
  background: rgba(254, 147, 44, 0.06);
  box-shadow: 0 0 0 1px rgba(144, 77, 0, 0.08), var(--shadow-whisper);
}

.job-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.job-card h3 {
  font-size: 1.05rem;
  letter-spacing: -0.02em;
}

.job-meta {
  margin-top: 0.15rem;
  font-size: 0.875rem;
  color: var(--on-surface-var);
}

.score-pill {
  width: 4rem;
  height: 4rem;
  flex-shrink: 0;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: linear-gradient(180deg, rgba(144, 77, 0, 0.12) 0%, rgba(254, 147, 44, 0.18) 100%);
  color: var(--secondary);
  font-family: 'Manrope', sans-serif;
  font-size: 1.05rem;
  font-weight: 800;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.chip {
  background: rgba(233, 232, 231, 0.92);
  color: var(--on-surface);
}

.muted-chip {
  background: rgba(144, 77, 0, 0.08);
  color: var(--secondary);
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.metric-card {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 0.95rem 1rem;
  border-radius: var(--radius-md);
  background: var(--surface-low);
}

.metric-card span {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--on-surface-var);
}

.metric-card strong {
  font-family: 'Manrope', sans-serif;
  font-size: 1.35rem;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.detail-block {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

@media (max-width: 1280px) {
  .jobs-layout {
    grid-template-columns: 1fr;
  }

  .job-detail-panel {
    position: static;
  }
}

@media (max-width: 900px) {
  .panel {
    padding: 1.25rem;
  }

  .job-card-head {
    flex-direction: column;
  }

  .metrics-grid {
    grid-template-columns: 1fr;
  }

  .score-pill {
    width: 3.5rem;
    height: 3.5rem;
    font-size: 1rem;
  }
}
</style>
