<template>
  <div style="display:flex;flex-direction:column;height:100%;">
    <div class="page-header">
      <p class="page-header__eyebrow">Approval Gate v2</p>
      <h1 class="page-header__title">Approval Gate</h1>
      <p class="page-header__sub">
        Reviewing {{ sortedApplications.length }} high-probability matches. Approve to apply, skip to decline.
      </p>
    </div>

    <div class="approval-layout" style="flex:1;">
      <!-- Queue -->
      <div class="approval-queue">
        <div class="approval-queue__header">
          <div class="section-header" style="margin-bottom:0;">
            <div class="section-header__title">Review Queue</div>
            <span class="chip chip-amber">{{ pendingApplications.length }}</span>
          </div>
        </div>
        <div class="approval-queue__list">
          <div v-if="sortedApplications.length === 0" class="empty-state" style="padding:2rem 1rem;">
            <div class="empty-state__icon"><span class="material-symbols-outlined">approval</span></div>
            <p class="empty-state__title">Queue empty</p>
            <p class="empty-state__body">Start a pipeline run to populate the review queue.</p>
          </div>
          <div
            v-for="app in sortedApplications"
            :key="app.id"
            class="queue-item"
            :class="{ 'is-active': selectedId === app.id }"
            @click="selectApp(app)"
          >
            <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:0.5rem;">
              <div style="min-width:0;">
                <p class="queue-item__title">{{ app.title }}</p>
                <p class="queue-item__meta">{{ app.company_name }}</p>
              </div>
              <span class="chip" :class="queueChip(app.status)" style="flex-shrink:0;font-size:0.68rem;">
                {{ app.status === 'pending_approval' ? `${scorePercent(app.match_score)}%` : app.status.replaceAll('_',' ') }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Detail -->
      <div class="approval-detail" v-if="selected">
        <!-- Job Header -->
        <div class="pipeline-section" style="padding:1.5rem;">
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;margin-bottom:1rem;">
            <div>
              <h2 style="font-family:'Manrope',sans-serif;font-size:1.375rem;font-weight:700;letter-spacing:-0.02em;">{{ selected.title }}</h2>
              <p style="font-size:0.9rem;color:var(--on-surface-var);margin-top:0.25rem;">{{ selected.company_name }} · Remote, US</p>
            </div>
            <div class="score-ring-wrap" style="flex-shrink:0;">
              <svg viewBox="0 0 120 120" class="score-ring">
                <circle cx="60" cy="60" r="48" class="score-ring-track"/>
                <circle cx="60" cy="60" r="48" class="score-ring-progress" :stroke-dasharray="scoreRingDash(selected.match_score)"/>
              </svg>
              <div class="score-ring-label">{{ scorePercent(selected.match_score) }}%</div>
            </div>
          </div>

          <!-- Stats -->
          <div class="prob-grid">
            <div class="prob-card">
              <p class="prob-card__label">Interview Prob.</p>
              <p class="prob-card__value" style="color:var(--secondary);">{{ scorePercent(selected.match_score) }}%</p>
            </div>
            <div class="prob-card">
              <p class="prob-card__label">Risk Level</p>
              <p class="prob-card__value" style="font-size:1.1rem;">
                <span class="chip chip-emerald">{{ selected.match_score >= 0.7 ? 'Minimal' : selected.match_score >= 0.5 ? 'Moderate' : 'High' }}</span>
              </p>
            </div>
          </div>
        </div>

        <!-- Score breakdown -->
        <div class="pipeline-section" style="padding:1.5rem;">
          <p class="font-label" style="margin-bottom:1rem;">Score Breakdown</p>
          <div style="display:flex;flex-direction:column;gap:0.75rem;">
            <div v-for="m in scoreBreakdown" :key="m.label" style="display:grid;grid-template-columns:90px 1fr 42px;gap:0.75rem;align-items:center;">
              <span style="font-size:0.8125rem;color:var(--on-surface-var);">{{ m.label }}</span>
              <div style="height:0.45rem;background:var(--surface-high);border-radius:999px;overflow:hidden;">
                <div :style="{ width: m.value + '%', height:'100%', background:'linear-gradient(90deg,var(--secondary),var(--secondary-container))', borderRadius:'inherit' }"></div>
              </div>
              <span style="font-size:0.8125rem;font-weight:600;color:var(--on-surface);text-align:right;">{{ m.value }}%</span>
            </div>
          </div>
        </div>

        <!-- Matched / Gap skills -->
        <div class="pipeline-section" style="padding:1.5rem;">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;">
            <div>
              <p class="font-label" style="margin-bottom:0.75rem;">Matched Skills</p>
              <div class="skill-tags">
                <span v-for="s in matchedSkills" :key="s" class="skill-tag skill-tag--match">{{ s }}</span>
              </div>
            </div>
            <div>
              <p class="font-label" style="margin-bottom:0.75rem;">Skill Gaps</p>
              <div class="skill-tags">
                <span v-for="s in gapSkills" :key="s" class="skill-tag skill-tag--gap">{{ s }}</span>
                <span v-if="gapSkills.length === 0" style="font-size:0.8125rem;color:var(--on-surface-var);">None identified</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div v-if="selected.status === 'pending_approval' && submissionState !== 'success'" style="display:flex;gap:0.75rem;">
          <button class="btn btn-primary" :disabled="pipelineStatus === 'loading'" @click="approveOne">
            <span class="material-symbols-outlined icon-sm">check_circle</span>
            Approve &amp; Apply
          </button>
          <button class="btn btn-ghost" :disabled="pipelineStatus === 'loading'" @click="rejectOne">
            <span class="material-symbols-outlined icon-sm">cancel</span>
            Skip
          </button>
        </div>

        <!-- Already actioned -->
        <div v-else class="submission-success">
          <div class="submission-success__check">
            <span class="material-symbols-outlined">{{ selected.status === 'approved' || selected.status === 'applied' ? 'check_circle' : 'cancel' }}</span>
          </div>
          <p style="font-size:1rem;font-weight:700;color:var(--on-surface);">
            {{ selected.status === 'approved' || selected.status === 'applied' ? 'Application sent!' : 'Skipped' }}
          </p>
          <p style="font-size:0.8125rem;color:var(--on-surface-var);">
            {{ selected.status === 'approved' || selected.status === 'applied' ? 'Advancing to the next match in 2.5s.' : `Status: ${selected.status.replaceAll('_',' ')}` }}
          </p>
        </div>

        <div v-if="pipelineError" class="auth-error">{{ pipelineError }}</div>
      </div>

      <!-- No selection -->
      <div v-else class="approval-detail" style="display:flex;align-items:center;justify-content:center;">
        <div class="empty-state">
          <div class="empty-state__icon"><span class="material-symbols-outlined">preview</span></div>
          <p class="empty-state__title">Select a match to review</p>
          <p class="empty-state__body">Click any item in the queue to see its full analysis and cover letter.</p>
        </div>
      </div>

      <!-- Cover Letter -->
      <div class="approval-letter" v-if="selected">
        <div class="approval-letter__header">
          <div>
            <p class="font-label" style="margin-bottom:0.2rem;">Cover Letter Studio</p>
            <p style="font-size:0.8125rem;font-weight:600;color:var(--on-surface);">{{ selected.company_name }} draft</p>
          </div>
          <div style="display:flex;gap:0.5rem;">
            <span class="chip chip-neutral">{{ editorWordCount }} words</span>
            <span class="chip chip-neutral">v{{ selected.cover_letter_version }}</span>
          </div>
        </div>
        <div class="approval-letter__body">
          <textarea
            class="approval-letter__textarea"
            v-model="draftText"
            :disabled="selected.status !== 'pending_approval' || pipelineStatus === 'loading'"
            spellcheck="true"
          ></textarea>
        </div>
        <div class="approval-letter__footer">
          <button class="btn btn-secondary btn-sm" :disabled="selected.status !== 'pending_approval' || pipelineStatus === 'loading'" @click="saveDraft">Save edit</button>
          <button class="btn btn-ghost btn-sm" :disabled="selected.status !== 'pending_approval' || pipelineStatus === 'loading'" @click="regenerate">Regenerate</button>
          <button class="btn btn-ghost btn-sm" @click="copyLetter">
            <span class="material-symbols-outlined icon-sm">content_copy</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { isDemoApplication, type PipelineApplication } from "../services/pipeline";
import { store } from "../store";

const selectedId = ref<string | null>(null);
const draftText  = ref("");
const submissionState = ref<"idle" | "success">("idle");
let autoAdvanceTimer: number | null = null;

const pipelineResults  = computed(() => store.getters.pipelineResults as any);
const pipelineStatus   = computed(() => store.getters.pipelineStatus as string);
const pipelineError    = computed(() => store.getters.pipelineError as string | null);

const sortedApplications = computed<PipelineApplication[]>(() => {
  const apps = [...(pipelineResults.value?.applications ?? [])];
  apps.sort((a, b) => b.match_score - a.match_score);
  return apps;
});

const pendingApplications = computed(() =>
  sortedApplications.value.filter(a => a.status === "pending_approval")
);

const selected = computed(() =>
  sortedApplications.value.find(a => a.id === selectedId.value) ?? null
);

watch(selected, (app) => {
  if (app) draftText.value = app.cover_letter_text ?? "";
  submissionState.value = "idle";
}, { immediate: true });

// Auto-select first pending when list changes
watch(sortedApplications, (apps) => {
  if (!selectedId.value && apps.length > 0) {
    selectedId.value = apps[0].id;
  }
}, { immediate: true });

const editorWordCount = computed(() =>
  draftText.value.split(/\s+/).filter(Boolean).length
);

const scoreBreakdown = computed(() => {
  const a = selected.value;
  if (!a) return [];
  const s  = (v: number) => Math.round(Math.min(1, Math.max(0, v)) * 100);
  return [
    { label: "Semantic",  value: s(a.semantic_similarity ?? a.match_score) },
    { label: "Skills",    value: s(a.skills_coverage   ?? Math.max(0, a.match_score - 0.05)) },
    { label: "Seniority", value: s(a.seniority_alignment ?? Math.max(0, a.match_score - 0.12)) },
    { label: "Location",  value: s(a.location_match    ?? Math.max(0, a.match_score - 0.2)) },
    { label: "Salary",    value: s(a.salary_alignment  ?? Math.max(0, a.match_score - 0.16)) },
  ];
});

const matchedSkills = computed(() => {
  const profile = store.getters.resumeProfile;
  return (profile?.skills?.technical ?? []).slice(0, 6);
});

const gapSkills = computed(() => {
  const score = selected.value?.match_score ?? 1;
  if (score >= 0.85) return [];
  if (score >= 0.70) return ["System Design"];
  return ["System Design", "Go", "Kubernetes"];
});

function selectApp(app: PipelineApplication) {
  selectedId.value = app.id;
}

function scorePercent(v: number) { return Math.round(Math.min(1, Math.max(0, v)) * 100); }

function scoreRingDash(v: number): string {
  const c = 2 * Math.PI * 48;
  const f = (scorePercent(v) / 100) * c;
  return `${f} ${c - f}`;
}

function queueChip(status: string) {
  if (status === "approved" || status === "applied") return "chip chip-emerald";
  if (status === "rejected")                         return "chip chip-error";
  return "chip chip-amber";
}

async function approveOne() {
  if (!selected.value) return;
  await saveDraft();
  await store.dispatch("approvePipelineApplications", { applicationIds: [selected.value.id] });
  submissionState.value = "success";
  clearAutoAdvanceTimer();
  autoAdvanceTimer = window.setTimeout(() => {
    advanceQueue();
    submissionState.value = "idle";
  }, 2500);
}

async function rejectOne() {
  if (!selected.value) return;
  await store.dispatch("rejectPipelineApplications", { applicationIds: [selected.value.id] });
  clearAutoAdvanceTimer();
  submissionState.value = "idle";
  advanceQueue();
}

async function saveDraft() {
  if (!selected.value || selected.value.status !== "pending_approval") return;
  const text = draftText.value.trim();
  if (!text) return;
  await store.dispatch("editPipelineCoverLetter", { applicationId: selected.value.id, coverLetterText: text });
}

async function regenerate() {
  if (!selected.value) return;
  await store.dispatch("regeneratePipelineCoverLetter", { applicationId: selected.value.id });
  draftText.value = selected.value.cover_letter_text ?? "";
}

function copyLetter() {
  navigator.clipboard.writeText(draftText.value).catch(() => {});
}

function advanceQueue() {
  const pending = pendingApplications.value.filter(a => a.id !== selectedId.value);
  selectedId.value = pending[0]?.id ?? sortedApplications.value[0]?.id ?? null;
}

function clearAutoAdvanceTimer() {
  if (autoAdvanceTimer !== null) {
    window.clearTimeout(autoAdvanceTimer);
    autoAdvanceTimer = null;
  }
}

onBeforeUnmount(() => {
  clearAutoAdvanceTimer();
});
</script>
