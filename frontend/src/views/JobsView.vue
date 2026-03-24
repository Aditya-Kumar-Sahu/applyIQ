<template>
  <main class="grid jobs-layout">
    <section class="panel">
      <p class="eyebrow">Match Engine</p>
      <h2>Ranked opportunities, filtered to fit how you actually want to work.</h2>
      <p class="lede">
        This view combines semantic similarity, skills overlap, seniority, location, and salary
        alignment into a single ranked shortlist.
      </p>

      <form class="search-bar" @submit.prevent="runSearch">
        <input v-model="searchQuery" type="text" placeholder="Search by natural language, skills, or role" />
        <button class="button-link auth-button" type="submit">Search</button>
      </form>

      <p v-if="jobsError" class="auth-error">{{ jobsError }}</p>
      <p v-if="jobsStatus === 'loading'" class="lede">Refreshing ranked jobs...</p>
      <p v-else class="lede">Showing {{ jobs.length }} ranked jobs.</p>
    </section>

    <section class="panel jobs-list-panel">
      <p class="eyebrow">Top Matches</p>
      <div v-if="jobs.length === 0" class="empty-state">
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
      <p v-else class="lede">Select a ranked job to inspect the match breakdown and description.</p>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import type { JobDetail, RankedJob } from "../services/jobs";
import { store } from "../store";

const jobs = computed(() => store.getters.jobs as RankedJob[]);
const jobsStatus = computed(() => store.getters.jobsStatus as string);
const jobsError = computed(() => store.getters.jobsError as string | null);
const selectedJob = computed(() => store.getters.selectedJob as JobDetail | null);

const searchQuery = ref("");

onMounted(async () => {
  await store.dispatch("fetchJobs");
});

async function runSearch() {
  if (!searchQuery.value.trim()) {
    await store.dispatch("fetchJobs");
    return;
  }
  await store.dispatch("searchJobs", searchQuery.value.trim());
}

async function selectJob(jobId: string) {
  await store.dispatch("fetchJobDetail", jobId);
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}
</script>
