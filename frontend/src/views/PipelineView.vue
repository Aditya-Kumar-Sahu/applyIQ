<template>
  <main class="grid pipeline-layout polished-pipeline">
    <section class="panel pipeline-control-panel">
      <p class="eyebrow">Pipeline Control</p>
      <h2>Run, inspect, and approve with a single workflow.</h2>
      <p class="lede">
        The graph pauses at the approval gate. You can edit letters, reject low-fit jobs, or bulk approve high-score matches.
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

    <section class="panel graph-panel">
      <div class="approval-head">
        <div>
          <p class="eyebrow">Execution Graph</p>
          <h3>{{ statusLabel }}</h3>
        </div>
        <div class="pipeline-summary-inline" v-if="pipelineRun">
          <span class="status-pill">Jobs: {{ pipelineRun.jobs_found }}</span>
          <span class="status-pill">Matched: {{ pipelineRun.jobs_matched }}</span>
          <span class="status-pill">Pending: {{ pendingApplications.length }}</span>
        </div>
      </div>

      <section class="graph-stage-board" aria-label="Pipeline execution graph">
        <div class="graph-stage-lines" aria-hidden="true">
          <span class="graph-line graph-line-one"></span>
          <span class="graph-line graph-line-two"></span>
          <span class="graph-line graph-line-three"></span>
          <span class="graph-line graph-line-four"></span>
        </div>

        <article
          v-for="node in nodes"
          :key="node.id"
          class="graph-stage-card"
          :class="[`stage-${nodeStatus(node.id)}`, node.emphasis ? 'stage-gate' : '']"
        >
          <div class="graph-stage-topline">
            <span class="graph-stage-step">{{ node.step }}</span>
            <span class="graph-stage-state">{{ nodeStatusLabel(node.id) }}</span>
          </div>
          <div class="graph-stage-icon" aria-hidden="true">{{ node.icon }}</div>
          <h4>{{ node.label }}</h4>
          <p class="job-meta">{{ node.description }}</p>
          <div class="graph-stage-metric">
            <strong>{{ nodeMetric(node.id).value }}</strong>
            <span>{{ nodeMetric(node.id).label }}</span>
          </div>
        </article>
      </section>

      <div class="graph-telemetry" v-if="pipelineRun">
        <article class="telemetry-card">
          <p class="eyebrow muted">Run State</p>
          <h4>{{ statusLabel }}</h4>
          <p class="job-meta">Current node: {{ readableNodeName(pipelineRun.current_node) }}</p>
        </article>
        <article class="telemetry-card">
          <p class="eyebrow muted">Review Queue</p>
          <h4>{{ pendingApplications.length }}</h4>
          <p class="job-meta">Applications waiting at the gate</p>
        </article>
        <article class="telemetry-card">
          <p class="eyebrow muted">Submission Flow</p>
          <h4>{{ appliedCount }}</h4>
          <p class="job-meta">Applied or handed off to the tracker</p>
        </article>
      </div>
    </section>

    <section class="panel pipeline-approval-panel">
      <div class="approval-head">
        <div>
          <p class="eyebrow">Approval Gate</p>
          <h3>{{ approvalHeading }}</h3>
        </div>
        <div class="approval-actions">
          <button
            class="button-link secondary-button"
            type="button"
            :disabled="highScorePendingIds.length === 0 || pipelineStatus === 'loading'"
            @click="approveHighScore"
          >
            Approve score >= 80%
          </button>
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
        v-for="application in sortedApplications"
        :key="application.id"
        class="approval-card approval-workspace"
        :class="{ approved: application.status === 'approved', rejected: application.status === 'rejected' }"
      >
        <div class="approval-card-head">
          <label v-if="application.status === 'pending_approval'" class="select-pill">
            <input v-model="selectedIds" type="checkbox" :value="application.id" />
            <span>Select</span>
          </label>
          <div>
            <h3>{{ application.title }}</h3>
            <p class="job-meta">{{ application.company_name }}</p>
          </div>
          <div class="status-stack">
            <span class="status-pill">{{ application.status.replaceAll("_", " ") }}</span>
            <span v-if="isDemoApplication(application)" class="status-pill demo-pill">Demo application</span>
          </div>
        </div>

        <div class="approval-split approval-split-rich">
          <section class="approval-job-pane">
            <div class="score-ring-wrap">
              <svg viewBox="0 0 120 120" class="score-ring" role="img" aria-label="Match score">
                <circle cx="60" cy="60" r="48" class="score-ring-track" />
                <circle
                  cx="60"
                  cy="60"
                  r="48"
                  class="score-ring-progress"
                  :stroke-dasharray="scoreRingDash(application.match_score)"
                />
              </svg>
              <div class="score-ring-label">{{ scorePercent(application.match_score) }}%</div>
            </div>

            <div class="detail-block">
              <p class="eyebrow muted">Score Breakdown</p>
              <div v-for="metric in scoreBreakdown(application)" :key="`${application.id}-${metric.label}`" class="score-row">
                <span>{{ metric.label }}</span>
                <div class="score-bar">
                  <div class="score-fill" :style="{ width: `${metric.value}%` }"></div>
                </div>
                <strong>{{ metric.value }}%</strong>
              </div>
            </div>

            <div class="detail-block job-signal-grid">
              <article class="job-signal-card">
                <span>Tone</span>
                <strong>{{ application.tone }}</strong>
              </article>
              <article class="job-signal-card">
                <span>Words</span>
                <strong>{{ application.word_count }}</strong>
              </article>
              <article v-if="application.selected_variant_id" class="job-signal-card">
                <span>Variant</span>
                <strong>{{ application.selected_variant_id }}</strong>
              </article>
              <article class="job-signal-card">
                <span>ATS</span>
                <strong>{{ application.ats_provider ?? "pending" }}</strong>
              </article>
            </div>

            <div v-if="application.status !== 'pending_approval'" class="apply-outcome">
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
              <p class="job-meta">Screenshots: {{ application.screenshot_urls.length }}</p>
            </div>
          </section>

          <section class="approval-letter-pane approval-editor-pane">
            <div class="editor-shell" :class="{ disabled: application.status !== 'pending_approval' || pipelineStatus === 'loading' }">
              <div class="editor-header">
                <div>
                  <p class="eyebrow muted">Cover Letter Studio</p>
                  <h4>{{ application.company_name }} draft</h4>
                </div>
                <div class="editor-meta-row">
                  <span class="status-pill muted-chip">{{ editorWordCount(application.id) }} words</span>
                  <span class="status-pill muted-chip">Version {{ application.cover_letter_version }}</span>
                </div>
              </div>

              <div class="editor-toolbar">
                <button
                  v-for="tool in editorTools"
                  :key="`${application.id}-${tool.command}`"
                  class="editor-tool"
                  type="button"
                  :disabled="application.status !== 'pending_approval' || pipelineStatus === 'loading'"
                  @click="formatEditor(application.id, tool.command)"
                >
                  {{ tool.label }}
                </button>
                <button
                  class="editor-tool editor-tool-ghost"
                  type="button"
                  :disabled="application.status !== 'pending_approval' || pipelineStatus === 'loading'"
                  @click="insertBridge(application.id)"
                >
                  Add bridge sentence
                </button>
              </div>

              <div
                :ref="(element) => setEditorRef(application.id, element)"
                class="rich-editor"
                :contenteditable="application.status === 'pending_approval' && pipelineStatus !== 'loading'"
                spellcheck="true"
                @input="syncDraftFromEditor(application.id)"
                @blur="syncDraftFromEditor(application.id)"
              ></div>
            </div>

            <div v-if="abVariants[application.id]?.length" class="detail-block">
              <p class="eyebrow muted">A/B Variants</p>
              <article
                v-for="variant in abVariants[application.id]"
                :key="`${application.id}-${variant.variant_id}`"
                class="approval-card variant-card"
              >
                <h3>Variant {{ variant.variant_id }} / {{ variant.tone }}</h3>
                <p class="job-meta">{{ variant.word_count }} words</p>
                <p class="lede compact">{{ variant.cover_letter_text }}</p>
                <button
                  class="button-link secondary-button"
                  type="button"
                  :disabled="application.status !== 'pending_approval' || pipelineStatus === 'loading'"
                  @click="selectVariant(application.id, variant.variant_id)"
                >
                  Use Variant {{ variant.variant_id }}
                </button>
              </article>
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
                @click="generateAB(application.id)"
              >
                Generate A/B
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
                Skip
              </button>
            </div>
          </section>
        </div>
      </article>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from "vue";

import {
  isDemoApplication,
  subscribePipelineStatus,
  type CoverLetterVariant,
  type PipelineApplication,
  type PipelineResults,
  type PipelineRunSummary,
} from "../services/pipeline";
import { store } from "../store";

type PipelineNode = {
  id: string;
  step: string;
  label: string;
  description: string;
  icon: string;
  emphasis?: boolean;
};

type ScoreMetric = {
  label: string;
  value: number;
};

type EditorTool = {
  label: string;
  command: "bold" | "italic" | "insertUnorderedList" | "formatBlock";
};

type StageStatus = "pending" | "active" | "complete";

const availableSources = ["linkedin", "indeed", "remotive", "wellfound"];
const nodes: PipelineNode[] = [
  { id: "fetch_jobs_node", step: "01", label: "Job Scout", description: "Scrapes selected sources in parallel.", icon: "01" },
  { id: "rank_jobs_node", step: "02", label: "Match and Rank", description: "Scores jobs against the resume profile.", icon: "02" },
  { id: "approval_gate_node", step: "03", label: "Approval Gate", description: "Waits for explicit user approval.", icon: "03", emphasis: true },
  { id: "auto_apply_node", step: "04", label: "Auto Apply", description: "Submits approved applications only.", icon: "04" },
  { id: "track_applications_node", step: "05", label: "Tracker", description: "Persists outcomes and status updates.", icon: "05" },
];
const editorTools: EditorTool[] = [
  { label: "Bold", command: "bold" },
  { label: "Italic", command: "italic" },
  { label: "Bullets", command: "insertUnorderedList" },
  { label: "Focus line", command: "formatBlock" },
];

const form = reactive({
  targetRole: "ML Engineer",
  location: "Remote",
  limitPerSource: 10,
  sources: ["linkedin", "indeed", "remotive"],
});

const selectedIds = ref<string[]>([]);
const drafts = reactive<Record<string, string>>({});
const editorRefs = new Map<string, HTMLDivElement>();
const abVariants = reactive<Record<string, CoverLetterVariant[]>>({});

const pipelineRun = computed(() => store.getters.pipelineRun as PipelineRunSummary | null);
const pipelineResults = computed(() => store.getters.pipelineResults as PipelineResults | null);
const pipelineStatus = computed(() => store.getters.pipelineStatus as string);
const pipelineError = computed(() => store.getters.pipelineError as string | null);
const sortedApplications = computed(() => {
  const applications = [...(pipelineResults.value?.applications ?? [])];
  applications.sort((left, right) => right.match_score - left.match_score);
  return applications;
});
const pendingApplications = computed(() =>
  (pipelineResults.value?.applications ?? []).filter((application) => application.status === "pending_approval"),
);
const appliedCount = computed(
  () =>
    (pipelineResults.value?.applications ?? []).filter((application) =>
      ["applied", "manual_required", "failed"].includes(application.status),
    ).length,
);
const highScorePendingIds = computed(() =>
  pendingApplications.value.filter((application) => application.match_score >= 0.8).map((application) => application.id),
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
const statusLabel = computed(() => {
  if (!pipelineRun.value) {
    return "Idle";
  }
  if (pipelineRun.value.status === "paused_at_gate") {
    return "Waiting for Approval";
  }
  return pipelineRun.value.status.replaceAll("_", " ");
});

let stopPipelineStatusStream: (() => void) | null = null;

watch(
  pipelineResults,
  async (results) => {
    selectedIds.value = selectedIds.value.filter((id) =>
      results?.applications.some((application) => application.id === id && application.status === "pending_approval"),
    );

    for (const application of results?.applications ?? []) {
      drafts[application.id] = application.cover_letter_text;
    }

    await nextTick();

    for (const application of results?.applications ?? []) {
      syncEditorFromDraft(application.id);
    }
  },
  { immediate: true },
);

watch(
  () => pipelineRun.value?.run_id,
  (runId, previousRunId) => {
    if (previousRunId && previousRunId !== runId) {
      stopPipelineStatusStream?.();
      stopPipelineStatusStream = null;
    }

    if (!runId) {
      stopPipelineStatusStream?.();
      stopPipelineStatusStream = null;
      return;
    }

    stopPipelineStatusStream?.();
    stopPipelineStatusStream = subscribePipelineStatus(
      runId,
      (pipelineResultsUpdate) => {
        store.commit("setPipelineRun", {
          run_id: pipelineResultsUpdate.run_id,
          status: pipelineResultsUpdate.status,
          current_node: pipelineResultsUpdate.current_node,
          jobs_found: pipelineResultsUpdate.jobs_found,
          jobs_matched: pipelineResultsUpdate.jobs_matched,
          applications_submitted: pipelineResultsUpdate.applications_submitted,
          pending_approvals_count: pipelineResultsUpdate.applications.filter(
            (application) => application.status === "pending_approval",
          ).length,
        });
        store.commit("setPipelineResults", pipelineResultsUpdate);
      },
      (streamError) => {
        store.commit("setPipelineError", streamError.message);
      },
    );
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  stopPipelineStatusStream?.();
  stopPipelineStatusStream = null;
});

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
  syncDraftFromEditor(applicationId);
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

async function generateAB(applicationId: string) {
  const result = await store.dispatch("generatePipelineCoverLetterAB", { applicationId });
  abVariants[applicationId] = result.variants;
}

async function selectVariant(applicationId: string, variantId: string) {
  await store.dispatch("selectPipelineCoverLetterVariant", { applicationId, variantId });
  delete abVariants[applicationId];
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

async function approveHighScore() {
  if (highScorePendingIds.value.length === 0) {
    return;
  }
  selectedIds.value = [...highScorePendingIds.value];
  await approveSelected();
}

function setEditorRef(applicationId: string, element: unknown) {
  if (element instanceof HTMLDivElement) {
    editorRefs.set(applicationId, element);
    syncEditorFromDraft(applicationId);
    return;
  }
  editorRefs.delete(applicationId);
}

function syncEditorFromDraft(applicationId: string) {
  const editor = editorRefs.get(applicationId);
  const draft = drafts[applicationId] ?? "";
  if (!editor) {
    return;
  }
  if (editor.innerText.trim() === draft.trim()) {
    return;
  }
  editor.innerText = draft;
}

function syncDraftFromEditor(applicationId: string) {
  const editor = editorRefs.get(applicationId);
  if (!editor) {
    return;
  }
  drafts[applicationId] = normalizeEditorText(editor.innerText);
}

function formatEditor(applicationId: string, command: EditorTool["command"]) {
  const editor = editorRefs.get(applicationId);
  if (!editor) {
    return;
  }
  editor.focus();
  if (command === "formatBlock") {
    document.execCommand(command, false, "blockquote");
  } else {
    document.execCommand(command, false);
  }
  syncDraftFromEditor(applicationId);
}

function insertBridge(applicationId: string) {
  const editor = editorRefs.get(applicationId);
  if (!editor) {
    return;
  }
  editor.focus();
  document.execCommand(
    "insertText",
    false,
    "\nThis role lines up with the systems work and measurable outcomes already delivered across prior projects.",
  );
  syncDraftFromEditor(applicationId);
}

function editorWordCount(applicationId: string): number {
  const text = drafts[applicationId] ?? "";
  return text.split(/\s+/).filter(Boolean).length;
}

function normalizeEditorText(value: string): string {
  return value.replace(/\r/g, "").replace(/\n{3,}/g, "\n\n").trim();
}

function scorePercent(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value * 100)));
}

function scoreRingDash(value: number): string {
  const circumference = 2 * Math.PI * 48;
  const filled = (scorePercent(value) / 100) * circumference;
  return `${filled} ${circumference - filled}`;
}

function scoreBreakdown(application: PipelineApplication): ScoreMetric[] {
  const semantic = application.semantic_similarity ?? application.match_score;
  const skills = application.skills_coverage ?? Math.max(0, application.match_score - 0.05);
  const seniority = application.seniority_alignment ?? Math.max(0, application.match_score - 0.12);
  const location = application.location_match ?? Math.max(0, application.match_score - 0.2);
  const salary = application.salary_alignment ?? Math.max(0, application.match_score - 0.16);

  return [
    { label: "Semantic", value: scorePercent(semantic) },
    { label: "Skills", value: scorePercent(skills) },
    { label: "Seniority", value: scorePercent(seniority) },
    { label: "Location", value: scorePercent(location) },
    { label: "Salary", value: scorePercent(salary) },
  ];
}

function nodeStatus(nodeId: string): StageStatus {
  const currentNode = pipelineRun.value?.current_node;
  if (!currentNode) {
    return "pending";
  }

  const nodeIndex = nodes.findIndex((node) => node.id === nodeId);
  const currentIndex = nodes.findIndex((node) => node.id === currentNode);

  if (pipelineRun.value?.status === "complete") {
    return "complete";
  }
  if (nodeIndex < currentIndex) {
    return "complete";
  }
  if (nodeIndex === currentIndex) {
    return "active";
  }
  return "pending";
}

function nodeStatusLabel(nodeId: string): string {
  const status = nodeStatus(nodeId);
  if (status === "complete") {
    return "Complete";
  }
  if (status === "active") {
    return pipelineRun.value?.status === "paused_at_gate" && nodeId === "approval_gate_node" ? "Awaiting review" : "Running";
  }
  return "Queued";
}

function nodeMetric(nodeId: string): { label: string; value: string } {
  switch (nodeId) {
    case "fetch_jobs_node":
      return { label: "jobs found", value: String(pipelineRun.value?.jobs_found ?? 0) };
    case "rank_jobs_node":
      return { label: "matches ranked", value: String(pipelineRun.value?.jobs_matched ?? 0) };
    case "approval_gate_node":
      return { label: "waiting review", value: String(pendingApplications.value.length) };
    case "auto_apply_node":
      return { label: "submitted", value: String(pipelineRun.value?.applications_submitted ?? 0) };
    case "track_applications_node":
      return { label: "tracked", value: String(appliedCount.value) };
    default:
      return { label: "events", value: "0" };
  }
}

function readableNodeName(nodeId: string): string {
  return nodes.find((node) => node.id === nodeId)?.label ?? nodeId.replaceAll("_", " ");
}
</script>
