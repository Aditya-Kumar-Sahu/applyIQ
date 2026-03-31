<template>
  <div>
    <div class="page-header">
      <p class="page-header__eyebrow">Orchestration</p>
      <h1 class="page-header__title">Main Orchestration Graph</h1>
      <p class="page-header__sub" style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap;margin-top:0.5rem;">
        <span class="chip chip-neutral">v2.0.4-production</span>
        <span class="chip chip-neutral">Cluster: US-EAST-1</span>
        <span v-if="pipelineRun" class="chip" :class="pipelineRun.status === 'complete' ? 'chip-emerald' : 'chip-amber'">
          {{ statusLabel }}
        </span>
      </p>
    </div>

    <div class="pipeline-layout">
      <!-- Main: Graph + Control Form -->
      <div class="pipeline-main">

        <!-- Control form -->
        <div class="pipeline-section">
          <div class="section-header" style="margin-bottom:1.25rem;">
            <div>
              <div class="section-header__title">Start a Run</div>
              <div class="section-header__sub">Configure sources and target role, then launch the pipeline.</div>
            </div>
          </div>
          <form @submit.prevent="handleStart" style="display:flex;flex-direction:column;gap:1rem;">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
              <div class="field-group">
                <label class="field-label" for="pipe-role">Target role</label>
                <input id="pipe-role" v-model="form.targetRole" type="text" class="field-input" required placeholder="ML Engineer" />
              </div>
              <div class="field-group">
                <label class="field-label" for="pipe-loc">Location</label>
                <input id="pipe-loc" v-model="form.location" type="text" class="field-input" placeholder="Remote or a city" />
              </div>
            </div>
            <div class="field-group">
              <label class="field-label" for="pipe-limit">Jobs per source</label>
              <input id="pipe-limit" v-model.number="form.limitPerSource" type="number" min="1" max="25" class="field-input" style="max-width:120px;" />
            </div>
            <div>
              <p class="field-label" style="margin-bottom:0.5rem;">Sources</p>
              <div style="display:flex;flex-wrap:wrap;gap:0.5rem;">
                <label
                  v-for="source in availableSources"
                  :key="source"
                  style="display:inline-flex;align-items:center;gap:0.5rem;padding:0.5rem 0.875rem;background:var(--surface-low);border-radius:var(--radius-full);font-size:0.8125rem;cursor:pointer;user-select:none;"
                  :style="form.sources.includes(source) ? 'background:rgba(144,77,0,0.12);color:var(--secondary);font-weight:600;' : ''"
                >
                  <input v-model="form.sources" type="checkbox" :value="source" style="display:none;" />
                  {{ source }}
                </label>
              </div>
            </div>
            <div style="display:flex;gap:0.75rem;align-items:center;flex-wrap:wrap;">
              <button class="btn btn-primary" type="submit" :disabled="pipelineStatus === 'loading'">
                <span class="material-symbols-outlined icon-sm">play_arrow</span>
                {{ pipelineStatus === 'loading' ? 'Running…' : 'Start pipeline run' }}
              </button>
              <button v-if="pipelineRun" class="btn btn-secondary" type="button" :disabled="pipelineStatus === 'loading'" @click="refreshPipeline">
                <span class="material-symbols-outlined icon-sm">refresh</span>
                Refresh
              </button>
            </div>
            <div v-if="pipelineError" class="auth-error">{{ pipelineError }}</div>
          </form>
        </div>

        <!-- Execution Graph -->
        <div class="pipeline-section">
          <div class="section-header" style="margin-bottom:1.25rem;">
            <div>
              <div class="section-header__title">{{ statusLabel }}</div>
              <div class="section-header__sub" v-if="pipelineRun">Run ID: {{ pipelineRun.run_id?.slice(0,8) }}…</div>
            </div>
            <div v-if="pipelineRun" style="display:flex;gap:0.5rem;flex-wrap:wrap;">
              <span class="chip chip-neutral">Jobs: {{ pipelineRun.jobs_found }}</span>
              <span class="chip chip-amber">Matched: {{ pipelineRun.jobs_matched }}</span>
              <span class="chip chip-neutral">Pending: {{ pendingApplications.length }}</span>
            </div>
          </div>

          <div class="pipeline-graph">
            <svg class="pipeline-graph__svg" viewBox="0 0 1000 220" preserveAspectRatio="none" aria-hidden="true">
              <defs>
                <marker id="pipelineArrow" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto" markerUnits="strokeWidth">
                  <path d="M 0 0 L 10 5 L 0 10 z"></path>
                </marker>
              </defs>
              <path d="M 130 112 L 290 112" :class="{ 'is-active': nodeStatus('rank_jobs_node') !== 'pending' }" marker-end="url(#pipelineArrow)" />
              <path d="M 330 112 L 490 112" :class="{ 'is-active': nodeStatus('approval_gate_node') !== 'pending' }" marker-end="url(#pipelineArrow)" />
              <path d="M 530 112 L 690 112" :class="{ 'is-active': nodeStatus('auto_apply_node') !== 'pending' }" marker-end="url(#pipelineArrow)" />
              <path d="M 730 112 L 890 112" :class="{ 'is-active': nodeStatus('track_applications_node') !== 'pending' }" marker-end="url(#pipelineArrow)" />
            </svg>
            <template v-for="(node, idx) in nodes" :key="node.id">
              <div
                class="pipeline-node"
                :class="{
                  'is-active':   nodeStatus(node.id) === 'active',
                  'is-complete': nodeStatus(node.id) === 'complete',
                  'is-selected': selectedNode === node.id,
                }"
                @click="selectedNode = node.id"
              >
                <span class="pipeline-node__step">{{ node.step }}</span>
                <span
                  class="pipeline-node__badge"
                  :class="{
                    'pipeline-node__badge--active': nodeStatus(node.id) === 'active',
                    'pipeline-node__badge--complete': nodeStatus(node.id) === 'complete',
                  }"
                >
                  {{ nodeStatusLabel(node.id) }}
                </span>
                <div class="pipeline-node__icon">{{ node.icon }}</div>
                <p class="pipeline-node__title">{{ node.label }}</p>
                <p class="pipeline-node__sub">{{ node.description }}</p>
                <p class="pipeline-node__state"
                  :class="{
                    'pipeline-node__state--active':   nodeStatus(node.id) === 'active',
                    'pipeline-node__state--complete': nodeStatus(node.id) === 'complete',
                  }"
                >
                  {{ nodeStatusLabel(node.id) }}
                </p>
                <div style="margin-top:0.5rem;padding-top:0.5rem;border-top:1px solid rgba(199,198,202,0.2);">
                  <span style="font-family:'Manrope',sans-serif;font-size:1.25rem;font-weight:800;letter-spacing:-0.03em;">{{ nodeMetric(node.id).value }}</span>
                  <span style="font-size:0.68rem;color:var(--on-surface-var);margin-left:0.3rem;text-transform:uppercase;letter-spacing:0.05em;">{{ nodeMetric(node.id).label }}</span>
                </div>
              </div>
              <div v-if="idx < nodes.length - 1" class="pipeline-arrow">
                <span class="material-symbols-outlined">arrow_forward</span>
              </div>
            </template>
          </div>

          <!-- Telemetry row -->
          <div v-if="pipelineRun" style="display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin-top:1.5rem;">
            <div style="padding:1rem;background:var(--surface-low);border-radius:var(--radius-md);">
              <p class="font-label" style="margin-bottom:0.35rem;">Run State</p>
              <p style="font-size:0.9rem;font-weight:600;color:var(--on-surface);">{{ statusLabel }}</p>
              <p style="font-size:0.78rem;color:var(--on-surface-var);margin-top:0.2rem;">{{ pipelineRun.current_node?.replaceAll('_',' ') ?? '—' }}</p>
            </div>
            <div style="padding:1rem;background:var(--surface-low);border-radius:var(--radius-md);">
              <p class="font-label" style="margin-bottom:0.35rem;">Review Queue</p>
              <p style="font-size:0.9rem;font-weight:600;color:var(--on-surface);">{{ pendingApplications.length }}</p>
              <p style="font-size:0.78rem;color:var(--on-surface-var);margin-top:0.2rem;">Awaiting approval</p>
            </div>
            <div style="padding:1rem;background:var(--surface-low);border-radius:var(--radius-md);">
              <p class="font-label" style="margin-bottom:0.35rem;">Submitted</p>
              <p style="font-size:0.9rem;font-weight:600;color:var(--on-surface);">{{ appliedCount }}</p>
              <p style="font-size:0.78rem;color:var(--on-surface-var);margin-top:0.2rem;">Applied or tracked</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Aside: Execution Details + Approval Gate -->
      <div class="pipeline-aside">

        <!-- Execution log for selected node -->
        <div class="pipeline-section" v-if="pipelineRun">
          <div class="section-header" style="margin-bottom:1rem;">
            <div class="section-header__title">Execution Details</div>
          </div>
          <div class="execution-panel__metrics">
            <div class="execution-metric">
              <span class="execution-metric__label">Selected Node</span>
              <strong class="execution-metric__value">{{ selectedNodeLabel }}</strong>
            </div>
            <div class="execution-metric">
              <span class="execution-metric__label">Connection</span>
              <strong class="execution-metric__value">{{ connectionStateLabel }}</strong>
            </div>
            <div class="execution-metric">
              <span class="execution-metric__label">Task ID</span>
              <strong class="execution-metric__value">{{ pipelineRun.run_id?.slice(0, 8) ?? '—' }}</strong>
            </div>
          </div>

          <div class="execution-memory">
            <div class="execution-memory__label">
              <span>Memory utilization</span>
              <span>{{ memoryUtilization }}%</span>
            </div>
            <div class="execution-memory__bar">
              <div class="execution-memory__fill" :style="{ width: `${memoryUtilization}%` }"></div>
            </div>
          </div>
          <div class="exec-log">
            <div v-for="entry in execLog" :key="entry.time" class="exec-log__entry">
              <div class="exec-log__dot" :class="entry.active ? 'exec-log__dot--active' : ''"></div>
              <span class="exec-log__time">{{ entry.time }}</span>
              <span class="exec-log__msg">{{ entry.msg }}</span>
            </div>
          </div>
        </div>

        <div v-if="!pipelineRun" class="pipeline-section">
          <div class="empty-state">
            <div class="empty-state__icon"><span class="material-symbols-outlined">account_tree</span></div>
            <p class="empty-state__title">No active run</p>
            <p class="empty-state__body">Launch the pipeline on the left to see the execution graph come alive.</p>
          </div>
        </div>

        <!-- Approval Gate mini -->
        <div class="pipeline-section">
          <div class="section-header" style="margin-bottom:1rem;">
            <div>
              <div class="section-header__title">Approval Gate</div>
              <div class="section-header__sub">{{ approvalHeading }}</div>
            </div>
          </div>

          <div v-if="!pipelineResults || sortedApplications.length === 0" class="empty-state" style="padding:1.5rem 0;">
            <div class="empty-state__icon"><span class="material-symbols-outlined">inbox</span></div>
            <p class="empty-state__body">Applications will appear here once the pipeline reaches the gate.</p>
          </div>

          <div v-else style="display:flex;flex-direction:column;gap:0.5rem;max-height:340px;overflow-y:auto;">
            <div
              v-for="app in sortedApplications.slice(0, 8)"
              :key="app.id"
              style="display:flex;align-items:center;gap:0.75rem;padding:0.75rem;background:var(--surface-low);border-radius:var(--radius-md);"
            >
              <div style="flex:1;min-width:0;">
                <p style="font-size:0.8125rem;font-weight:600;color:var(--on-surface);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{{ app.title }}</p>
                <p style="font-size:0.75rem;color:var(--on-surface-var);">{{ app.company_name }}</p>
              </div>
              <span class="chip chip-neutral" style="font-size:0.7rem;flex-shrink:0;">{{ Math.round(app.match_score * 100) }}%</span>
              <label v-if="app.status === 'pending_approval'" style="display:inline-flex;align-items:center;">
                <input v-model="selectedIds" type="checkbox" :value="app.id" style="accent-color:var(--secondary);width:16px;height:16px;" />
              </label>
              <span v-else class="chip" :class="app.status === 'approved' || app.status === 'applied' ? 'chip-emerald' : 'chip-error'" style="font-size:0.68rem;">
                {{ app.status === 'approved' || app.status === 'applied' ? '✓' : '✕' }}
              </span>
            </div>
          </div>

          <div v-if="sortedApplications.length > 0" style="display:flex;gap:0.5rem;margin-top:1rem;flex-wrap:wrap;">
            <button class="btn btn-secondary btn-sm" :disabled="highScorePendingIds.length === 0 || pipelineStatus === 'loading'" @click="approveHighScore">
              Approve ≥80%
            </button>
            <button class="btn btn-primary btn-sm" :disabled="selectedIds.length === 0 || pipelineStatus === 'loading'" @click="approveSelected">
              Approve selected
            </button>
            <RouterLink to="/approval" class="btn btn-ghost btn-sm">Full review →</RouterLink>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from "vue";
import { RouterLink } from "vue-router";

import {
  isDemoApplication,
  subscribePipelineStatus,
  type CoverLetterVariant,
  type PipelineApplication,
  type PipelineResults,
  type PipelineRunSummary,
} from "../services/pipeline";
import { store } from "../store";

type PipelineNode = { id: string; step: string; label: string; description: string; icon: string; emphasis?: boolean; };
type StageStatus  = "pending" | "active" | "complete";

const availableSources = ["linkedin", "indeed", "remotive", "wellfound"];
const nodes: PipelineNode[] = [
  { id: "fetch_jobs_node",        step: "01", label: "Job Scout",     description: "Scrapes selected sources in parallel.",         icon: "01" },
  { id: "rank_jobs_node",         step: "02", label: "Match & Rank",  description: "Scores jobs against the resume profile.",       icon: "02" },
  { id: "approval_gate_node",     step: "03", label: "Approval Gate", description: "Waits for explicit user approval.",             icon: "03", emphasis: true },
  { id: "auto_apply_node",        step: "04", label: "Auto Apply",    description: "Submits approved applications only.",           icon: "04" },
  { id: "track_applications_node",step: "05", label: "Tracker",       description: "Persists outcomes and status updates.",        icon: "05" },
];

const form = reactive({ targetRole: "ML Engineer", location: "Remote", limitPerSource: 10, sources: ["linkedin", "indeed", "remotive"] });
const selectedIds  = ref<string[]>([]);
const selectedNode = ref<string>(nodes[0].id);
const abVariants   = reactive<Record<string, CoverLetterVariant[]>>({});

const pipelineRun     = computed(() => store.getters.pipelineRun     as PipelineRunSummary | null);
const pipelineResults = computed(() => store.getters.pipelineResults as PipelineResults    | null);
const pipelineStatus  = computed(() => store.getters.pipelineStatus  as string);
const pipelineError   = computed(() => store.getters.pipelineError   as string | null);

const sortedApplications = computed(() => {
  const apps = [...(pipelineResults.value?.applications ?? [])];
  apps.sort((a, b) => b.match_score - a.match_score);
  return apps;
});
const pendingApplications = computed(() =>
  (pipelineResults.value?.applications ?? []).filter(a => a.status === "pending_approval")
);
const appliedCount = computed(() =>
  (pipelineResults.value?.applications ?? []).filter(a => ["applied","manual_required","failed"].includes(a.status)).length
);
const highScorePendingIds = computed(() =>
  pendingApplications.value.filter(a => a.match_score >= 0.8).map(a => a.id)
);
const approvalHeading = computed(() => {
  if (!pipelineResults.value)              return "No applications waiting yet";
  if (pipelineRun.value?.status === "complete") return "Pipeline completed after approval";
  return `${pendingApplications.value.length} application(s) waiting for review`;
});
const statusLabel = computed(() => {
  if (!pipelineRun.value) return "Idle";
  if (pipelineRun.value.status === "paused_at_gate") return "Waiting for Approval";
  return pipelineRun.value.status.replaceAll("_", " ");
});

// Simulated exec log from pipeline state
const execLog = computed(() => {
  if (!pipelineRun.value) return [];
  const entries: { time: string; msg: string; active: boolean }[] = [];
  if (pipelineRun.value.jobs_found)    entries.push({ time: "14:22:01", msg: `Scraped ${pipelineRun.value.jobs_found} job listings`, active: false });
  if (pipelineRun.value.jobs_matched)  entries.push({ time: "14:22:05", msg: `Ranked ${pipelineRun.value.jobs_matched} matches`, active: false });
  if (pendingApplications.value.length > 0) entries.push({ time: "14:22:12", msg: `${pendingApplications.value.length} pending approval`, active: true });
  return entries;
});

const selectedNodeLabel = computed(() => nodes.find((node) => node.id === selectedNode.value)?.label ?? "Select a node");
const connectionStateLabel = computed(() => {
  if (!pipelineRun.value) return "Idle";
  return pipelineRun.value.status === "paused_at_gate" ? "Awaiting review" : pipelineRun.value.status.replaceAll("_", " ");
});
const memoryUtilization = computed(() => (pipelineRun.value ? 38 : 0));

let stopPipelineStatusStream: (() => void) | null = null;

watch(() => pipelineRun.value?.current_node, (nodeId) => {
  if (nodeId) {
    selectedNode.value = nodeId;
  }
}, { immediate: true });

watch(() => pipelineRun.value?.run_id, (runId, prevId) => {
  if (prevId && prevId !== runId) { stopPipelineStatusStream?.(); stopPipelineStatusStream = null; }
  if (!runId) { stopPipelineStatusStream?.(); stopPipelineStatusStream = null; return; }
  stopPipelineStatusStream?.();
  stopPipelineStatusStream = subscribePipelineStatus(
    runId,
    (update) => {
      store.commit("setPipelineRun", {
        run_id: update.run_id, status: update.status, current_node: update.current_node,
        jobs_found: update.jobs_found, jobs_matched: update.jobs_matched,
        applications_submitted: update.applications_submitted,
        pending_approvals_count: update.applications.filter(a => a.status === "pending_approval").length,
      });
      store.commit("setPipelineResults", update);
    },
    (err) => store.commit("setPipelineError", err.message),
  );
}, { immediate: true });

onBeforeUnmount(() => { stopPipelineStatusStream?.(); stopPipelineStatusStream = null; });

async function handleStart() {
  if (form.sources.length === 0) return;
  await store.dispatch("startPipeline", {
    target_role: form.targetRole, location: form.location,
    limit_per_source: form.limitPerSource, sources: form.sources,
  });
}
async function refreshPipeline() { await store.dispatch("loadPipeline"); }

async function approveSelected() {
  if (selectedIds.value.length === 0) return;
  const ids = [...selectedIds.value]; selectedIds.value = [];
  await store.dispatch("approvePipelineApplications", { applicationIds: ids });
}
async function approveHighScore() {
  if (highScorePendingIds.value.length === 0) return;
  selectedIds.value = [...highScorePendingIds.value];
  await approveSelected();
}

function nodeStatus(nodeId: string): StageStatus {
  const cur = pipelineRun.value?.current_node;
  if (!cur) return "pending";
  const ni = nodes.findIndex(n => n.id === nodeId);
  const ci = nodes.findIndex(n => n.id === cur);
  if (pipelineRun.value?.status === "complete") return "complete";
  if (ni < ci)  return "complete";
  if (ni === ci) return "active";
  return "pending";
}
function nodeStatusLabel(nodeId: string): string {
  const s = nodeStatus(nodeId);
  if (s === "complete") return "Complete";
  if (s === "active") return pipelineRun.value?.status === "paused_at_gate" && nodeId === "approval_gate_node" ? "Awaiting review" : "Running";
  return "Queued";
}
function nodeMetric(nodeId: string): { label: string; value: string } {
  switch (nodeId) {
    case "fetch_jobs_node":        return { label: "jobs found",     value: String(pipelineRun.value?.jobs_found           ?? 0) };
    case "rank_jobs_node":         return { label: "ranked",         value: String(pipelineRun.value?.jobs_matched          ?? 0) };
    case "approval_gate_node":     return { label: "waiting",        value: String(pendingApplications.value.length)            };
    case "auto_apply_node":        return { label: "submitted",      value: String(pipelineRun.value?.applications_submitted ?? 0) };
    case "track_applications_node":return { label: "tracked",        value: String(appliedCount.value)                          };
    default:                       return { label: "events",         value: "0"                                                  };
  }
}
</script>
