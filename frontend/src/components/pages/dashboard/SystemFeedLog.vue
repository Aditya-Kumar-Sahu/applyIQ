<template>
  <AppCard class="system-feed app-card--interactive">
    <div class="system-feed__header">
      <div>
        <p class="label-md system-feed__eyebrow">System Feed</p>
        <h2 class="system-feed__title">Live pipeline events</h2>
      </div>
      <StatusChip tone="emerald">Live</StatusChip>
    </div>

    <div class="system-feed__list">
      <article v-for="entry in entries" :key="entry.id" class="system-feed__entry">
        <div class="system-feed__dot" :class="`system-feed__dot--${entry.tone}`"></div>
        <div class="system-feed__body">
          <div class="system-feed__copy">
            <h3 class="system-feed__entry-title">{{ entry.title }}</h3>
            <p class="system-feed__entry-detail body-sm">{{ entry.detail }}</p>
          </div>
          <span class="system-feed__time label-md">{{ entry.time }}</span>
        </div>
      </article>
    </div>
  </AppCard>
</template>

<script setup lang="ts">
import AppCard from '../../shared/AppCard.vue';
import StatusChip from '../../shared/StatusChip.vue';

defineProps<{
  entries: Array<{
    id: string | number;
    title: string;
    detail: string;
    time: string;
    tone: 'amber' | 'emerald' | 'neutral';
  }>;
}>();
</script>

<style scoped>
.system-feed {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.5rem;
}

.system-feed__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.system-feed__eyebrow {
  margin-bottom: 0.35rem;
}

.system-feed__title {
  margin: 0;
  font-family: 'Manrope', sans-serif;
  font-size: 1.25rem;
  font-weight: 700;
  letter-spacing: -0.03em;
}

.system-feed__list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  position: relative;
  padding-left: 0.8rem;
}

.system-feed__list::before {
  content: '';
  position: absolute;
  left: 0.45rem;
  top: 0.4rem;
  bottom: 0.4rem;
  width: 1px;
  background: color-mix(in srgb, var(--outline-variant) 50%, transparent);
}

.system-feed__entry {
  display: flex;
  align-items: flex-start;
  gap: 0.9rem;
}

.system-feed__dot {
  width: 0.75rem;
  height: 0.75rem;
  margin-top: 0.3rem;
  border-radius: 50%;
  flex-shrink: 0;
}

.system-feed__dot--amber {
  background: var(--secondary-container);
}

.system-feed__dot--emerald {
  background: var(--tertiary-fixed);
}

.system-feed__dot--neutral {
  background: var(--outline-variant);
}

.system-feed__body {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  width: 100%;
}

.system-feed__copy {
  min-width: 0;
}

.system-feed__entry-title {
  margin: 0;
  font-family: 'Manrope', sans-serif;
  font-size: 1rem;
  font-weight: 700;
}

.system-feed__entry-detail {
  margin: 0.25rem 0 0;
  color: var(--on-surface-variant);
}

.system-feed__time {
  white-space: nowrap;
  color: var(--on-surface-variant);
}
</style>