<template>
  <main class="grid pipeline-layout">
    <section class="panel">
      <p class="eyebrow">Pipeline Control</p>
      <h2>Run the LangGraph pipeline, review matched jobs, and resume only after approval.</h2>
      <p class="lede">
        This workspace reflects the core orchestration pattern: scrape, rank, pause at the human gate, then continue.
      </p>

      <form class="pipeline-form" @submit.prevent="handleStart">
        <label>
          Target role
          <input v-model="form.targetRole" type="text" required />
        </label>
        <label>
          Location
          <input v-model="form.location" type="text" placeholder="Remote or a city" />
        </label>
        <label>
          Jobs per source
          <input v-model.number="form.limitPerSource" type="number" min="1" max="25" />
        </label>
        <label>
          Sources
          <div class="source-grid">
            <label v-for="source in availableSources" :key="source" class="source-option">
              <input v-model="form.sources" type="checkbox" :value="source" />
              <span>{{ source }}</span>
            </label>
          </div>
        </label>
        <div class="action-row">
          <button class="button-link auth-button" type="submit" :disabled="pipelineStatus === 'loading'">
            {{ pipelineStatus === "loading" ? "Running..." : "Start pipeline run" }}
          </button>
          <button
            v-if="pipelineRun"
            class="button-link secondary-button"
            type="button"
            :disabled="pipelineStatus === 'loading'"
            @click="refreshPipeline"
          >
            Refresh status
          </button>
        </div>
      </form>

      <p v-if="pipelineError" class="auth-error">{{ pipelineError }}</p>
    </section>

    <section class="panel">
      <p class="eyebrow">Live Graph</p>
      <div class="node-grid">
        <article v-for="node in nodes" :key="node.id" class="node-card" :class="nodeClass(node.id)">
          <span class="node-step">{{ node.step }}</span>
          <h3>{{ node.label }}</h3>
          <p class="lede compact">{{ node.description }}</p>
        </article>
      </div>

      <div v-if="pipelineRun" class="pipeline-summary">
        <article class="metric-card">
          <span>Status</span>
          <strong>{{ pipelineRun.status }}</strong>
        </article>
        <article class="metric-card">
          <span>Current Node</span>
          <strong>{{ pipelineRun.current_node }}</strong>
        </article>
        <article class="metric-card">
          <span>Jobs Found</span>
          <strong>{{ pipelineRun.jobs_found }}</strong>
        </article>
        <article class="metric-card">
          <span>Jobs Matched</span>
          <strong>{{ pipelineRun.jobs_matched }}</strong>
        </article>
        <article class="metric-card">
          <span>Pending</span>
          <strong>{{ pendingApplications.length }}</strong>
        </article>
      </div>
      <p v-else class="lede">No pipeline run yet. Start one to populate the live graph and approval queue.</p>
    </section>

    <section class="panel pipeline-approval-panel">
      <div class="approval-head">
        <div>
          <p class="eyebrow">Approval Gate</p>
          <h3>{{ approvalHeading }}</h3>
        </div>
        <div class="approval-actions">
          <button
            class="button-link auth-button"
            type="button"
            :disabled="selectedIds.length === 0 || pipelineStatus === 'loading'"
            @click="approveSelected"
          >
            Approve selected
          </button>
        </div>
      </div>

      <div v-if="pipelineResults && pipelineResults.applications.length === 0" class="empty-state">
        <p class="lede">Applications will appear here once the pipeline reaches the approval gate.</p>
      </div>

      <article
        v-for="application in pipelineResults?.applications ?? []"
        :key="application.id"
        class="approval-card"
        :class="{ approved: application.status === 'approved', rejected: application.status === 'rejected' }"
      >
        <div class="approval-card-head">
          <label v-if="application.status === 'pending_approval'" class="select-pill">
            <input v-model="selectedIds" type="checkbox" :value="application.id" />
            <span>Select</span>
          </label>
          <div>
            <h3>{{ application.title }}</h3>
            <p class="job-meta">{{ application.company_name }} / {{ percent(application.match_score) }} match</p>
            <p class="job-meta">{{ application.tone }} tone / {{ application.word_count }} words</p>
          </div>
          <span class="status-pill">{{ application.status.replaceAll("_", " ") }}</span>
        </div>

        <label class="cover-letter-field">
          Cover letter
          <textarea
            v-model="drafts[application.id]"
            rows="5"
            :disabled="application.status !== 'pending_approval' || pipelineStatus === 'loading'"
          />
        </label>

        <div v-if="application.status !== 'pending_approval'" class="apply-outcome">
          <p class="job-meta">ATS: {{ application.ats_provider ?? "pending" }}</p>
          <p v-if="application.confirmation_number" class="job-meta">
            Confirmation: {{ application.confirmation_number }}
          </p>
          <p v-if="application.manual_required_reason" class="auth-error">{{ application.manual_required_reason }}</p>
          <p v-if="application.failure_reason" class="auth-error">{{ application.failure_reason }}</p>
          <a
            v-if="application.confirmation_url"
            class="button-link secondary-button"
            :href="application.confirmation_url"
            target="_blank"
            rel="noreferrer"
          >
            Open confirmation
          </a>
          <p class="job-meta">Screenshots captured: {{ application.screenshot_urls.length }}</p>
        </div>

        <div class="action-row compact-actions">
          <button
            class="button-link secondary-button"
            type="button"
            :disabled="application.status !== 'pending_approval' || pipelineStatus === 'loading'"
            @click="regenerate(application.id)"
          >
            Regenerate
          </button>
          <button
            class="button-link secondary-button"
            type="button"
            :disabled="application.status !== 'pending_approval' || pipelineStatus === 'loading'"
            @click="saveDraft(application.id)"
          >
            Save edit
          </button>
          <button
            class="button-link danger-button"
            type="button"
            :disabled="application.status !== 'pending_approval' || pipelineStatus === 'loading'"
            @click="rejectOne(application.id)"
          >
            Reject
          </button>
          <span class="version-note">Version {{ application.cover_letter_version }}</span>
        </div>
      </article>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";

import type { PipelineResults, PipelineRunSummary } from "../services/pipeline";
import { store } from "../store";

type PipelineNode = {
  id: string;
  step: string;
  label: string;
  description: string;
};

const availableSources = ["linkedin", "indeed", "remotive", "wellfound"];
const nodes: PipelineNode[] = [
  { id: "fetch_jobs_node", step: "01", label: "Job Scout", description: "Scrapes all selected sources in parallel." },
  { id: "rank_jobs_node", step: "02", label: "Match and Rank", description: "Scores jobs against the resume profile." },
  { id: "approval_gate_node", step: "03", label: "Approval Gate", description: "Pauses until the user reviews each application." },
  { id: "auto_apply_node", step: "04", label: "Auto Apply", description: "Resumes only after explicit approval." },
  { id: "track_applications_node", step: "05", label: "Tracker", description: "Finalizes the run and records application outcomes." },
];

const form = reactive({
  targetRole: "ML Engineer",
  location: "Remote",
  limitPerSource: 10,
  sources: ["linkedin", "indeed", "remotive"],
});

const selectedIds = ref<string[]>([]);
const drafts = reactive<Record<string, string>>({});

const pipelineRun = computed(() => store.getters.pipelineRun as PipelineRunSummary | null);
const pipelineResults = computed(() => store.getters.pipelineResults as PipelineResults | null);
const pipelineStatus = computed(() => store.getters.pipelineStatus as string);
const pipelineError = computed(() => store.getters.pipelineError as string | null);

const pendingApplications = computed(() =>
  (pipelineResults.value?.applications ?? []).filter((application) => application.status === "pending_approval"),
);

const approvalHeading = computed(() => {
  if (!pipelineResults.value) {
    return "No applications waiting yet";
  }

  if (pipelineRun.value?.status === "complete") {
    return "Pipeline completed after approval";
  }

  return `${pendingApplications.value.length} applications waiting for review`;
});

watch(
  pipelineResults,
  (results) => {
    selectedIds.value = selectedIds.value.filter((id) =>
      results?.applications.some((application) => application.id === id && application.status === "pending_approval"),
    );

    for (const application of results?.applications ?? []) {
      drafts[application.id] = application.cover_letter_text;
    }
  },
  { immediate: true },
);

async function handleStart() {
  if (form.sources.length === 0) {
    return;
  }

  await store.dispatch("startPipeline", {
    target_role: form.targetRole,
    location: form.location,
    limit_per_source: form.limitPerSource,
    sources: form.sources,
  });
}

async function refreshPipeline() {
  await store.dispatch("loadPipeline");
}

async function saveDraft(applicationId: string) {
  const coverLetterText = drafts[applicationId]?.trim();
  if (!coverLetterText) {
    return;
  }

  await store.dispatch("editPipelineCoverLetter", {
    applicationId,
    coverLetterText,
  });
}

async function regenerate(applicationId: string) {
  await store.dispatch("regeneratePipelineCoverLetter", { applicationId });
}

async function rejectOne(applicationId: string) {
  await store.dispatch("rejectPipelineApplications", { applicationIds: [applicationId] });
}

async function approveSelected() {
  if (selectedIds.value.length === 0) {
    return;
  }

  const approvedIds = [...selectedIds.value];
  selectedIds.value = [];
  await store.dispatch("approvePipelineApplications", { applicationIds: approvedIds });
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function nodeClass(nodeId: string): string {
  const currentNode = pipelineRun.value?.current_node;
  if (!currentNode) {
    return "pending";
  }

  const nodeIndex = nodes.findIndex((node) => node.id === nodeId);
  const currentIndex = nodes.findIndex((node) => node.id === currentNode);

  if (nodeIndex < currentIndex) {
    return "complete";
  }

  if (nodeIndex === currentIndex) {
    return pipelineRun.value?.status === "complete" ? "complete" : "active";
  }

  if (pipelineRun.value?.status === "complete") {
    return "complete";
  }

  return "pending";
}
</script>
