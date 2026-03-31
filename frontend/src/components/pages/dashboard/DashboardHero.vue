<template>
  <section class="dashboard-hero app-card app-card--glass">
    <div class="dashboard-hero__copy">
      <span class="dashboard-hero__badge label-md">System Status: Active</span>
      <h1 class="dashboard-hero__title">Your pipeline is actively hunting</h1>
      <p class="dashboard-hero__subtitle body-md">
        We're currently scanning multiple platforms to find roles that match your career trajectory.
        Sit back while ApplyIQ handles the heavy lifting.
      </p>
      <BaseButton as="a" href="/pipeline" variant="primary" size="lg" class="dashboard-hero__cta">
        Run New Pipeline
        <span class="material-symbols-outlined">arrow_forward</span>
      </BaseButton>
    </div>

    <div class="dashboard-hero__art" aria-hidden="true">
      <div class="dashboard-hero__orb"></div>
      <span class="material-symbols-outlined">radar</span>
    </div>
  </section>

  <section class="dashboard-stats">
    <article v-for="stat in animatedStats" :key="stat.label" class="dashboard-stat app-card">
      <p class="dashboard-stat__label label-md">{{ stat.label }}</p>
      <h2 class="dashboard-stat__value" :class="stat.toneClass">{{ stat.displayValue }}</h2>
      <p class="dashboard-stat__sub body-sm">{{ stat.subtext }}</p>
    </article>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import BaseButton from '../../shared/BaseButton.vue';

type DashboardStat = {
  label: string;
  value: number;
  subtext: string;
  toneClass?: string;
  padStart?: number;
};

const props = withDefaults(
  defineProps<{
    stats: DashboardStat[];
  }>(),
  {
    stats: () => [],
  },
);

const values = ref<number[]>(props.stats.map(() => 0));
let animationFrame = 0;

function animate() {
  const duration = 800;
  const startedAt = performance.now();
  const targets = props.stats.map((item) => item.value);

  const tick = (now: number) => {
    const progress = Math.min(1, (now - startedAt) / duration);
    values.value = targets.map((target) => Math.round(target * easeOutCubic(progress)));

    if (progress < 1) {
      animationFrame = window.requestAnimationFrame(tick);
    }
  };

  animationFrame = window.requestAnimationFrame(tick);
}

function easeOutCubic(value: number) {
  return 1 - Math.pow(1 - value, 3);
}

onMounted(() => {
  animate();
});

watch(
  () => props.stats,
  () => {
    values.value = props.stats.map(() => 0);
    animate();
  },
  { deep: true },
);

onBeforeUnmount(() => {
  window.cancelAnimationFrame(animationFrame);
});

const animatedStats = computed(() =>
  props.stats.map((stat, index) => {
    const value = values.value[index] ?? 0;
    const displayValue = stat.padStart
      ? String(value).padStart(stat.padStart, '0')
      : new Intl.NumberFormat('en-US').format(value);

    return {
      ...stat,
      displayValue,
    };
  }),
);
</script>

<style scoped>
.dashboard-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 2rem;
  padding: 3rem;
  min-height: 20rem;
  position: relative;
  overflow: hidden;
}

.dashboard-hero__copy {
  position: relative;
  z-index: 1;
  max-width: 36rem;
}

.dashboard-hero__badge {
  display: inline-flex;
  padding: 0.35rem 0.75rem;
  margin-bottom: 1rem;
  border-radius: 9999px;
  background: var(--tertiary-fixed);
  color: var(--on-tertiary-fixed);
}

.dashboard-hero__title {
  font-family: 'Manrope', sans-serif;
  font-size: clamp(2.2rem, 3vw, 3.25rem);
  font-weight: 800;
  line-height: 1.08;
  letter-spacing: -0.04em;
  margin: 0 0 1rem;
}

.dashboard-hero__subtitle {
  max-width: 33rem;
  margin: 0 0 1.5rem;
  color: var(--on-surface-variant);
}

.dashboard-hero__cta {
  box-shadow: 0 18px 34px rgba(144, 77, 0, 0.18);
}

.dashboard-hero__art {
  width: 13rem;
  height: 13rem;
  border-radius: 50%;
  display: grid;
  place-items: center;
  position: relative;
  flex-shrink: 0;
  color: rgba(144, 77, 0, 0.24);
}

.dashboard-hero__art .material-symbols-outlined {
  font-size: 6rem;
  position: relative;
  z-index: 1;
}

.dashboard-hero__orb {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(254, 147, 44, 0.2), rgba(254, 147, 44, 0));
}

.dashboard-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1.25rem;
  margin-top: 1.25rem;
}

.dashboard-stat {
  padding: 1.5rem;
  min-height: 11.5rem;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.dashboard-stat__label {
  color: var(--on-surface-variant);
}

.dashboard-stat__value {
  font-family: 'Manrope', sans-serif;
  font-size: clamp(2.25rem, 4vw, 3.5rem);
  font-weight: 800;
  letter-spacing: -0.04em;
  margin: 0.35rem 0 0.5rem;
  color: var(--on-surface);
}

.dashboard-stat__value--amber {
  color: var(--secondary);
}

.dashboard-stat__value--emerald {
  color: var(--on-tertiary-container);
}

.dashboard-stat__sub {
  color: var(--on-surface-variant);
}

@media (max-width: 1200px) {
  .dashboard-hero {
    flex-direction: column;
    align-items: flex-start;
  }

  .dashboard-hero__art {
    width: 10rem;
    height: 10rem;
  }

  .dashboard-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .dashboard-stats {
    grid-template-columns: 1fr;
  }
}
</style>