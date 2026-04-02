<template>
  <div>
    <div class="page-header">
      <p class="page-header__eyebrow">Profile & Resume</p>
      <h1 class="page-header__title">{{ resumeProfile ? resumeProfile.current_title : 'Your Profile' }}</h1>
      <p class="page-header__sub">Upload your resume to generate a structured intelligence map and tune your search preferences.</p>
    </div>

    <div class="profile-layout">
      <!-- Left -->
      <div class="profile-aside">
        <!-- Strength -->
        <div class="pipeline-section">
          <div class="section-header" style="margin-bottom:0.75rem;">
            <div class="section-header__title">Profile Strength</div>
            <span class="chip" :class="strengthChip.cls">{{ strengthChip.label }}</span>
          </div>
          <div class="strength-bar"><div class="strength-bar__fill" :style="{ width: strengthPct + '%' }"></div></div>
          <p style="font-size:0.78rem;color:var(--on-surface-var);margin-top:0.5rem;">{{ strengthPct }}% complete</p>
        </div>

        <!-- Upload -->
        <div class="pipeline-section">
          <div class="section-header" style="margin-bottom:1rem;"><div class="section-header__title">Resume</div></div>
          <label class="resume-upload-zone" for="resume-upload" style="display:block;text-align:center;">
            <span class="material-symbols-outlined" style="font-size:2rem;color:var(--outline-var);">upload_file</span>
            <p style="font-size:0.875rem;font-weight:600;color:var(--on-surface);margin-top:0.5rem;">Upload PDF or DOCX</p>
            <p style="font-size:0.78rem;color:var(--on-surface-var);margin-top:0.2rem;">Up to 10MB</p>
            <input id="resume-upload" type="file" accept=".pdf,.docx" style="display:none;" @change="handleUpload" />
          </label>
          <div v-if="resumeStatus === 'loading'" style="margin-top:0.75rem;font-size:0.8125rem;color:var(--on-surface-var);display:flex;gap:0.5rem;align-items:center;">
            <span class="material-symbols-outlined icon-sm">sync</span> Parsing resume…
          </div>
          <div v-if="resumeProfile" style="margin-top:0.75rem;display:flex;gap:0.75rem;align-items:center;padding:0.875rem;background:var(--surface-low);border-radius:var(--radius-md);">
            <span class="material-symbols-outlined" style="color:var(--secondary);">description</span>
            <div style="flex:1;min-width:0;">
              <p style="font-size:0.8125rem;font-weight:600;">Resume on file</p>
              <p style="font-size:0.75rem;color:var(--on-surface-var);">{{ resumeProfile.current_title }}</p>
            </div>
            <span class="chip chip-emerald">✓</span>
          </div>
          <div v-if="resumeError" class="auth-error" style="margin-top:0.75rem;">{{ resumeError }}</div>
        </div>

        <!-- Target Filters -->
        <div class="pipeline-section">
          <div class="section-header" style="margin-bottom:1rem;"><div class="section-header__title">Target Filters</div></div>
          <form @submit.prevent="savePreferences" style="display:flex;flex-direction:column;gap:0.875rem;">
            <div class="field-group">
              <label class="field-label">Target roles</label>
              <input v-model="targetRoles" type="text" class="field-input" placeholder="Target roles" />
            </div>
            <div class="field-group">
              <label class="field-label">Locations</label>
              <input v-model="preferredLocations" type="text" class="field-input" placeholder="Preferred locations" />
            </div>
            <div class="field-group">
              <label class="field-label">Remote preference</label>
              <select v-model="remotePreference" class="field-input">
                <option value="any">Any</option>
                <option value="remote">Remote</option>
                <option value="hybrid">Hybrid</option>
                <option value="onsite">Onsite</option>
              </select>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem;">
              <div class="field-group"><label class="field-label">Salary min</label><input v-model.number="salaryMin" type="number" min="0" class="field-input" /></div>
              <div class="field-group"><label class="field-label">Salary max</label><input v-model.number="salaryMax" type="number" min="0" class="field-input" /></div>
            </div>
            <div class="field-group"><label class="field-label">Currency</label><input v-model="currency" type="text" class="field-input" /></div>
            <div class="field-group"><label class="field-label">Excluded companies</label><input v-model="excludedCompanies" type="text" class="field-input" placeholder="Companies to exclude" /></div>
            <div class="field-group"><label class="field-label">Seniority level</label><input v-model="seniorityLevel" type="text" class="field-input" placeholder="Seniority level" /></div>
            <button class="btn btn-primary w-full" type="submit">Save preferences</button>
          </form>
        </div>
      </div>

      <!-- Right -->
      <div class="profile-main">
        <div class="pipeline-section" v-if="resumeProfile">
          <div class="section-header" style="margin-bottom:1rem;">
            <div>
              <p class="font-label" style="margin-bottom:0.25rem;">Extracted Expertise</p>
              <div class="section-header__title">Intelligence Map</div>
            </div>
            <div style="display:flex;gap:0.5rem;">
              <span class="chip chip-neutral">{{ resumeProfile.years_of_experience }}y exp</span>
              <span class="chip chip-amber">{{ resumeProfile.seniority_level }}</span>
            </div>
          </div>
          <div class="skill-tags" style="margin-bottom:1.25rem;">
            <span v-for="skill in resumeProfile.skills.technical" :key="skill" class="intel-tag intel-tag--strong">{{ skill }}</span>
          </div>
          <p style="font-size:0.875rem;color:var(--on-surface);line-height:1.7;">{{ resumeProfile.summary_for_matching }}</p>
        </div>

        <div v-if="!resumeProfile" class="pipeline-section">
          <div class="empty-state">
            <div class="empty-state__icon"><span class="material-symbols-outlined">account_circle</span></div>
            <p class="empty-state__title">No resume uploaded yet</p>
            <p class="empty-state__body">Upload your PDF or DOCX to generate your intelligence map.</p>
          </div>
        </div>

        <div class="pipeline-section" v-if="profileCompleteness">
          <div class="section-header" style="margin-bottom:1rem;">
            <div class="section-header__title">Profile Completeness</div>
            <span style="font-family:'Manrope',sans-serif;font-size:1.75rem;font-weight:800;letter-spacing:-0.03em;">{{ profileCompleteness.score }}%</span>
          </div>
          <div v-if="profileCompleteness.missing_fields.length === 0" style="display:flex;align-items:center;gap:0.5rem;color:var(--on-tertiary-c);font-size:0.875rem;">
            <span class="material-symbols-outlined">check_circle</span> All key fields complete.
          </div>
          <ul v-else style="margin:0;padding-left:1.1rem;display:flex;flex-direction:column;gap:0.35rem;">
            <li v-for="rec in profileCompleteness.recommendations" :key="rec" style="font-size:0.8125rem;color:var(--on-surface-var);">{{ rec }}</li>
          </ul>
        </div>

        <div class="pipeline-section">
          <div class="section-header" style="margin-bottom:1rem;">
            <div class="section-header__title">Work Experience</div>
          </div>
          <div v-if="resumeProfile?.experience?.length > 0" class="profile-list">
            <div v-for="experience in resumeProfile.experience" :key="`${experience.company}-${experience.title}`" class="profile-list__item">
              <div class="profile-list__title">{{ experience.title }} · {{ experience.company }}</div>
              <div class="profile-list__meta">{{ experience.duration_months }} months</div>
              <p v-if="experience.highlights.length > 0" style="margin-top:0.65rem;font-size:0.8125rem;color:var(--on-surface-var);line-height:1.6;">
                {{ experience.highlights.slice(0, 2).join(' · ') }}
              </p>
            </div>
          </div>
          <div v-else class="empty-state" style="padding:1.5rem 1rem;">
            <div class="empty-state__icon"><span class="material-symbols-outlined">work</span></div>
            <p class="empty-state__body">No experience entries extracted yet.</p>
          </div>
        </div>

        <div class="pipeline-section">
          <div class="section-header" style="margin-bottom:1rem;">
            <div class="section-header__title">Education</div>
          </div>
          <div v-if="resumeProfile?.education?.length > 0" class="profile-list">
            <div v-for="education in resumeProfile.education" :key="`${education.institution}-${education.degree}`" class="profile-list__item">
              <div class="profile-list__title">{{ education.degree }} · {{ education.institution }}</div>
              <div class="profile-list__meta">{{ education.field }}{{ education.year ? ` · ${education.year}` : '' }}</div>
            </div>
          </div>
          <div v-else class="empty-state" style="padding:1.5rem 1rem;">
            <div class="empty-state__icon"><span class="material-symbols-outlined">school</span></div>
            <p class="empty-state__body">No education entries extracted yet.</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import type { SearchPreferences } from "../store";
import { store } from "../store";

const resumeProfile       = computed(() => store.getters.resumeProfile);
const profileCompleteness = computed(() => store.getters.profileCompleteness);
const resumeStatus        = computed(() => store.getters.resumeStatus as string);
const resumeError         = computed(() => store.getters.resumeError as string | null);
const storedPreferences   = computed(() => store.getters.resumePreferences as SearchPreferences | null);

const targetRoles         = ref("");
const preferredLocations  = ref("");
const remotePreference    = ref("any");
const salaryMin           = ref<number | null>(null);
const salaryMax           = ref<number | null>(null);
const currency            = ref("INR");
const excludedCompanies   = ref("");
const seniorityLevel      = ref("");

watch(storedPreferences, (p) => {
  if (!p) return;
  targetRoles.value        = p.target_roles.join(", ");
  preferredLocations.value = p.preferred_locations.join(", ");
  remotePreference.value   = p.remote_preference;
  salaryMin.value          = p.salary_min;
  salaryMax.value          = p.salary_max;
  currency.value           = p.currency;
  excludedCompanies.value  = p.excluded_companies.join(", ");
  seniorityLevel.value     = p.seniority_level ?? "";
}, { immediate: true });

onMounted(async () => { await store.dispatch("fetchResume"); });

const strengthPct  = computed(() => profileCompleteness.value?.score ?? 0);
const strengthChip = computed(() => {
  const s = strengthPct.value;
  if (s >= 90) return { label: "Expert",        cls: "chip chip-emerald" };
  if (s >= 70) return { label: "Strong",         cls: "chip chip-amber"  };
  return              { label: "Getting started", cls: "chip chip-neutral"};
});

async function handleUpload(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0];
  if (!file) return;
  await store.dispatch("uploadResume", file);
}

async function savePreferences() {
  await store.dispatch("savePreferences", {
    target_roles:        splitList(targetRoles.value),
    preferred_locations: splitList(preferredLocations.value),
    remote_preference:   remotePreference.value,
    salary_min:          salaryMin.value,
    salary_max:          salaryMax.value,
    currency:            currency.value || "INR",
    excluded_companies:  splitList(excludedCompanies.value),
    seniority_level:     seniorityLevel.value || null,
    is_active:           true,
  });
}

function splitList(v: string): string[] {
  return v.split(",").map(i => i.trim()).filter(Boolean);
}
</script>
