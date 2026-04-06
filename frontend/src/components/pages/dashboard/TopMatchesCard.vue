<template>
  <AppCard class="top-matches-card" interactive>
    <div class="top-matches-card__header">
      <div>
        <p class="label-md top-matches-card__eyebrow">Review Top Matches</p>
        <h2 class="top-matches-card__title">Live roles from active sources</h2>
      </div>
      <StatusChip tone="amber">{{ matches.length }} Active</StatusChip>
    </div>

    <p class="top-matches-card__sub body-sm">
      High-fit jobs surfaced from the live job feed with salary, source, and location context.
    </p>

    <div v-if="matches.length > 0" class="top-matches-card__list">
      <article v-for="match in matches" :key="match.title + match.company" class="top-match">
        <div class="top-match__content">
          <div>
            <h3 class="top-match__title">{{ match.title }}</h3>
            <p class="top-match__meta">{{ match.company }} · {{ match.location }}</p>
            <div style="margin-top:0.4rem;">
              <span class="chip chip-neutral">{{ match.source }}</span>
            </div>
          </div>
          <div class="top-match__details">
            <span class="top-match__salary status-chip status-chip--neutral">{{ match.salary }}</span>
            <span v-if="match.score" class="top-match__score status-chip status-chip--emerald">{{ match.score }}% match</span>
          </div>
        </div>
        <BaseButton as="button" variant="primary" size="sm" class="top-match__action" @click="$emit('review', match)">
          Review
          <span class="material-symbols-outlined">arrow_forward</span>
        </BaseButton>
      </article>
    </div>

    <div v-else class="top-matches-card__empty">
      <p class="top-matches-card__empty-title">No live matches right now</p>
      <p class="top-matches-card__empty-body">Run a pipeline to populate this section with current job matches.</p>
    </div>

    <BaseButton as="a" href="/approval" variant="secondary" size="sm" class="top-matches-card__footer">
      Review queue
      <span class="material-symbols-outlined">visibility</span>
    </BaseButton>
  </AppCard>
</template>

<script setup lang="ts">
import AppCard from '../../shared/AppCard.vue';
import BaseButton from '../../shared/BaseButton.vue';
import StatusChip from '../../shared/StatusChip.vue';

defineProps<{
  matches: Array<{
    title: string;
    company: string;
    source: string;
    location: string;
    salary: string;
    score?: number | null;
  }>;
}>();

defineEmits<{
  review: [match: { title: string; company: string; source: string; location: string; salary: string; score?: number | null }];
}>();
</script>

<style scoped>
.top-matches-card {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.5rem;
  min-height: 100%;
}

.top-matches-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.top-matches-card__eyebrow {
  margin-bottom: 0.35rem;
}

.top-matches-card__title {
  font-family: 'Manrope', sans-serif;
  font-size: 1.25rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  margin: 0;
}

.top-matches-card__sub {
  color: var(--on-surface-variant);
  margin: 0;
}

.top-matches-card__list {
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
}

.top-matches-card__empty {
  padding: 1rem;
  border-radius: var(--radius-lg);
  background: var(--surface-low);
}

.top-matches-card__empty-title,
.top-matches-card__empty-body {
  margin: 0;
}

.top-matches-card__empty-title {
  font-weight: 700;
  color: var(--on-surface);
  margin-bottom: 0.35rem;
}

.top-matches-card__empty-body {
  color: var(--on-surface-variant);
  font-size: 0.875rem;
}

.top-match {
  background: var(--surface-low);
  border-radius: var(--radius-lg);
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
}

.top-match__content {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.top-match__title {
  margin: 0;
  font-family: 'Manrope', sans-serif;
  font-size: 1rem;
  font-weight: 700;
}

.top-match__meta {
  margin: 0.25rem 0 0;
  color: var(--on-surface-variant);
  font-size: 0.875rem;
}

.top-match__details {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.top-match__action {
  align-self: flex-start;
}

.top-matches-card__footer {
  width: 100%;
}
</style>