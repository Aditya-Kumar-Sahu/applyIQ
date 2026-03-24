<template>
  <main class="grid resume-grid">
    <section class="panel">
      <p class="eyebrow">Resume Hub</p>
      <h2>Upload once, then tune how ApplyIQ represents you.</h2>
      <p class="lede">
        This phase turns an uploaded resume into a structured profile, stores an embedding, and lets
        you refine the search preferences that future job matching will use.
      </p>

      <label class="upload-box">
        <span>Upload PDF or DOCX</span>
        <input type="file" accept=".pdf,.docx" @change="handleUpload" />
      </label>

      <p v-if="resumeError" class="auth-error">{{ resumeError }}</p>
      <p v-if="resumeStatus === 'loading'" class="lede">Working through your resume now...</p>
    </section>

    <section class="panel">
      <p class="eyebrow">Profile</p>
      <template v-if="resumeProfile">
        <h3>{{ resumeProfile.current_title }}</h3>
        <p class="lede">{{ resumeProfile.summary_for_matching }}</p>
        <div class="chip-row">
          <span v-for="skill in resumeProfile.skills.technical" :key="skill" class="chip">{{ skill }}</span>
        </div>
        <p class="lede">{{ resumeProfile.years_of_experience }} years of experience | {{ resumeProfile.seniority_level }}</p>
      </template>
      <p v-else class="lede">No resume uploaded yet. Upload one above to generate your structured profile.</p>
    </section>

    <section class="panel">
      <p class="eyebrow">Completeness</p>
      <template v-if="profileCompleteness">
        <p class="score-number">{{ profileCompleteness.score }}%</p>
        <p class="lede" v-if="profileCompleteness.missing_fields.length === 0">
          Your profile has the key fields needed for matching.
        </p>
        <ul v-else class="feature-list">
          <li v-for="item in profileCompleteness.recommendations" :key="item">{{ item }}</li>
        </ul>
      </template>
      <p v-else class="lede">Completeness will appear after your first upload.</p>
    </section>

    <section class="panel">
      <p class="eyebrow">Search Preferences</p>
      <form class="auth-form" @submit.prevent="savePreferences">
        <label>
          <span>Target roles</span>
          <input v-model="targetRoles" type="text" placeholder="ML Engineer, AI Engineer" />
        </label>

        <label>
          <span>Preferred locations</span>
          <input v-model="preferredLocations" type="text" placeholder="Remote, Bengaluru" />
        </label>

        <label>
          <span>Remote preference</span>
          <select v-model="remotePreference">
            <option value="any">Any</option>
            <option value="remote">Remote</option>
            <option value="hybrid">Hybrid</option>
            <option value="onsite">Onsite</option>
          </select>
        </label>

        <label>
          <span>Salary min</span>
          <input v-model.number="salaryMin" type="number" min="0" />
        </label>

        <label>
          <span>Salary max</span>
          <input v-model.number="salaryMax" type="number" min="0" />
        </label>

        <label>
          <span>Currency</span>
          <input v-model="currency" type="text" />
        </label>

        <label>
          <span>Excluded companies</span>
          <input v-model="excludedCompanies" type="text" placeholder="Example Corp" />
        </label>

        <label>
          <span>Seniority level</span>
          <input v-model="seniorityLevel" type="text" placeholder="senior" />
        </label>

        <button class="button-link auth-button" type="submit">Save preferences</button>
      </form>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import type { SearchPreferences } from "../store";
import { store } from "../store";

const resumeProfile = computed(() => store.getters.resumeProfile);
const profileCompleteness = computed(() => store.getters.profileCompleteness);
const resumeStatus = computed(() => store.getters.resumeStatus as string);
const resumeError = computed(() => store.getters.resumeError as string | null);
const storedPreferences = computed(() => store.getters.resumePreferences as SearchPreferences | null);

const targetRoles = ref("");
const preferredLocations = ref("");
const remotePreference = ref("any");
const salaryMin = ref<number | null>(null);
const salaryMax = ref<number | null>(null);
const currency = ref("INR");
const excludedCompanies = ref("");
const seniorityLevel = ref("");

watch(
  storedPreferences,
  (preferences) => {
    if (!preferences) {
      return;
    }

    targetRoles.value = preferences.target_roles.join(", ");
    preferredLocations.value = preferences.preferred_locations.join(", ");
    remotePreference.value = preferences.remote_preference;
    salaryMin.value = preferences.salary_min;
    salaryMax.value = preferences.salary_max;
    currency.value = preferences.currency;
    excludedCompanies.value = preferences.excluded_companies.join(", ");
    seniorityLevel.value = preferences.seniority_level ?? "";
  },
  { immediate: true },
);

onMounted(async () => {
  await store.dispatch("fetchResume");
});

async function handleUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];

  if (!file) {
    return;
  }

  await store.dispatch("uploadResume", file);
}

async function savePreferences() {
  await store.dispatch("savePreferences", {
    target_roles: splitList(targetRoles.value),
    preferred_locations: splitList(preferredLocations.value),
    remote_preference: remotePreference.value,
    salary_min: salaryMin.value,
    salary_max: salaryMax.value,
    currency: currency.value || "INR",
    excluded_companies: splitList(excludedCompanies.value),
    seniority_level: seniorityLevel.value || null,
    is_active: true,
  });
}

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}
</script>
