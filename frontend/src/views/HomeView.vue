<template>
  <main class="home-view">
    <section class="home-hero">
      <div class="home-copy">
        <StatusChip tone="amber">Curated workflow</StatusChip>
        <p class="home-kicker">Human-in-the-loop job search</p>
        <h1>ApplyIQ: from search to submission.</h1>
        <p class="home-lede">
          ApplyIQ helps organize roles, surface strong matches, and keep approval where it belongs:
          with you. The page is intentionally illustrative, not a disguised live dashboard.
        </p>

        <div class="home-actions">
          <BaseButton as="a" href="/dashboard" variant="primary" size="lg">
            Open command centre
            <span class="material-symbols-outlined">arrow_forward</span>
          </BaseButton>
          <RouterLink class="home-link" to="/login">Sign in</RouterLink>
        </div>

        <div class="home-metrics">
          <AppCard class="home-metric" tone="soft">
            <span class="home-metric__label">Signal</span>
            <strong class="home-metric__value">Source inputs</strong>
          </AppCard>
          <AppCard class="home-metric" tone="soft">
            <span class="home-metric__label">Review</span>
            <strong class="home-metric__value home-metric__value--amber">Approval gate</strong>
          </AppCard>
          <AppCard class="home-metric" tone="soft">
            <span class="home-metric__label">Output</span>
            <strong class="home-metric__value home-metric__value--emerald">Submission path</strong>
          </AppCard>
        </div>
      </div>

      <AppCard class="home-preview" tone="glass">
        <div class="home-preview__header">
          <div>
            <p class="home-preview__eyebrow">Interface study</p>
            <h2 class="home-preview__title">Designed to feel composed under pressure</h2>
          </div>
          <StatusChip tone="neutral">Visual concept</StatusChip>
        </div>

        <div class="home-preview__panel">
          <div class="home-preview__ring">
            <div class="home-preview__ring-inner">
              <span>Focus</span>
              <small>Review</small>
            </div>
          </div>

          <div class="home-preview__copy">
            <p class="home-preview__role">A visual system, not a scoreboard</p>
            <p class="home-preview__company">Warm surfaces, clear hierarchy, and deliberate state changes</p>
            <div class="home-preview__chips">
              <StatusChip tone="emerald">Focus states</StatusChip>
              <StatusChip tone="neutral">Clear boundaries</StatusChip>
            </div>
          </div>
        </div>

        <div class="home-preview__feed">
          <article class="home-preview__item">
            <span class="home-preview__dot home-preview__dot--amber"></span>
            <div>
              <p>Layered decisions</p>
              <span>Each stage has its own visual rhythm and stopping point.</span>
            </div>
          </article>
          <article class="home-preview__item">
            <span class="home-preview__dot home-preview__dot--emerald"></span>
            <div>
              <p>Motion language</p>
              <span>Soft reveals and layered cards keep the interface calm.</span>
            </div>
          </article>
        </div>
      </AppCard>
    </section>

    <section class="home-grid">
      <AppCard class="home-card" tone="default">
        <p class="home-card__eyebrow">Why this build matters</p>
        <h3>Built to move quickly without blurring the line of approval.</h3>
        <ul class="home-list">
          <li>LangGraph orchestration with pause and resume.</li>
          <li>ToS-aware, multi-source job discovery.</li>
          <li>Human-in-the-loop approval before every submission.</li>
          <li>Encrypted credentials and resumable automation.</li>
        </ul>
      </AppCard>

      <AppCard class="home-card" tone="soft">
        <p class="home-card__eyebrow">Interface flow</p>
        <h3>From profile to a deliberate decision.</h3>
        <div class="home-steps">
          <div class="home-step">
            <span class="home-step__index">01</span>
            <div>
              <p>Parse profile</p>
              <span>Extract experience, skills, and preferences.</span>
            </div>
          </div>
          <div class="home-step">
            <span class="home-step__index">02</span>
            <div>
              <p>Rank matches</p>
              <span>Score jobs and surface the strongest opportunities.</span>
            </div>
          </div>
          <div class="home-step">
            <span class="home-step__index">03</span>
            <div>
              <p>Request approval</p>
              <span>Stop before submission until you confirm.</span>
            </div>
          </div>
        </div>
      </AppCard>
    </section>

    <section class="home-outro">
      <AppCard class="home-outro__panel" tone="glass">
        <div class="home-outro__header">
          <p class="home-card__eyebrow">Design notes</p>
          <h3>Clear states, softer motion, fewer surprises.</h3>
        </div>

        <p class="home-outro__lede">
          The home page is meant to feel composed and editorial, not transactional. Each card,
          glow, and label is there to guide attention without pretending to be live telemetry.
        </p>

        <div class="home-outro__grid">
          <div class="home-outro__item">
            <span class="home-outro__index">01</span>
            <div>
              <p>Anchored hierarchy</p>
              <span>Large type, warm surfaces, and a restrained palette keep the page grounded.</span>
            </div>
          </div>
          <div class="home-outro__item">
            <span class="home-outro__index">02</span>
            <div>
              <p>Distinct states</p>
              <span>Signals, review, and output are visually separated so nothing feels implied.</span>
            </div>
          </div>
          <div class="home-outro__item">
            <span class="home-outro__index">03</span>
            <div>
              <p>Controlled motion</p>
              <span>Soft offsets and layered cards add movement without simulating activity.</span>
            </div>
          </div>
        </div>
      </AppCard>
    </section>

    <section class="home-cta">
      <AppCard class="home-cta__panel" tone="default">
        <div class="home-cta__copy">
          <p class="home-card__eyebrow">Ready when you are</p>
          <h3>One clear place for jobs, review, and next steps.</h3>
          <p>
            Use the dashboard when you want live data. Use this page as the calm front door:
            a visual introduction that points to the workflow without pretending to be it.
          </p>
        </div>

        <div class="home-cta__rail">
          <div class="home-cta__tile">
            <span>Dashboard</span>
            <p>Operational views and current status.</p>
          </div>
          <div class="home-cta__tile">
            <span>Pipeline</span>
            <p>Structured stages with visible approvals.</p>
          </div>
          <div class="home-cta__tile">
            <span>Profile</span>
            <p>Inputs that shape the matching flow.</p>
          </div>
        </div>
      </AppCard>
    </section>
  </main>
</template>

<script setup lang="ts">
import { RouterLink } from "vue-router";

import AppCard from "../components/shared/AppCard.vue";
import BaseButton from "../components/shared/BaseButton.vue";
import StatusChip from "../components/shared/StatusChip.vue";
</script>

<style scoped>
.home-view {
  width: min(1180px, calc(100vw - 2rem));
  margin: 0 auto;
  padding: 2rem 1rem;
  display: grid;
  gap: 1.25rem;
  position: relative;
  padding-bottom: 4rem;
}

:global(body) {
  overflow-x: hidden;
}

.home-view::before,
.home-view::after {
  content: '';
  position: absolute;
  inset: auto;
  border-radius: 9999px;
  filter: blur(24px);
  pointer-events: none;
  opacity: 0.55;
}

.home-view::before {
  width: 16rem;
  height: 16rem;
  background: rgba(254, 147, 44, 0.12);
  top: -5rem;
  right: -2rem;
}

.home-view::after {
  width: 20rem;
  height: 20rem;
  background: rgba(133, 248, 196, 0.12);
  left: -5rem;
  bottom: -7rem;
}

.home-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.9fr);
  gap: 1.25rem;
  align-items: stretch;
  position: relative;
  z-index: 1;
}

.home-copy,
.home-preview,
.home-card {
  position: relative;
  z-index: 1;
}

.home-copy {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 1rem;
  padding: 1rem 0.25rem;
}

.home-kicker,
.home-preview__eyebrow,
.home-card__eyebrow {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--on-surface-var);
}

.home-copy h1 {
  font-family: 'Manrope', sans-serif;
  font-size: clamp(2.6rem, 6vw, 4.5rem);
  font-weight: 800;
  line-height: 0.98;
  letter-spacing: -0.05em;
  max-width: 11ch;
}

.home-lede {
  max-width: 54ch;
  color: var(--on-surface-var);
  font-size: 1rem;
  line-height: 1.7;
}

.home-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.home-link {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--on-surface-var);
  transition: color var(--ease-ui), transform var(--ease-ui);
}

.home-link:hover {
  color: var(--on-surface);
  transform: translateY(-1px);
}

.home-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.875rem;
  margin-top: 0.5rem;
}

.home-metric {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.home-metric__label {
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--on-surface-var);
}

.home-metric__value {
  font-family: 'Manrope', sans-serif;
  font-size: 2rem;
  font-weight: 800;
  letter-spacing: -0.04em;
  color: var(--on-surface);
}

.home-metric__value--amber {
  color: var(--secondary);
}

.home-metric__value--emerald {
  color: var(--on-tertiary-c);
}

.home-preview {
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  min-height: 100%;
}

.home-preview__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.home-preview__title {
  font-family: 'Manrope', sans-serif;
  font-size: 1.35rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  margin-top: 0.35rem;
}

.home-preview__panel {
  background: var(--surface-low);
  border-radius: var(--radius-lg);
  padding: 1.25rem;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 1rem;
  align-items: center;
}

.home-preview__ring {
  width: 6.5rem;
  height: 6.5rem;
  border-radius: 50%;
  background: conic-gradient(var(--secondary-container) 0 84%, rgba(199, 198, 202, 0.45) 84% 100%);
  display: grid;
  place-items: center;
}

.home-preview__ring-inner {
  width: 4.7rem;
  height: 4.7rem;
  border-radius: 50%;
  background: var(--surface-lowest);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-whisper);
}

.home-preview__ring-inner span {
  font-family: 'Manrope', sans-serif;
  font-size: 1.35rem;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.home-preview__ring-inner small {
  font-size: 0.7rem;
  color: var(--on-surface-var);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.home-preview__copy {
  min-width: 0;
}

.home-preview__role {
  font-family: 'Manrope', sans-serif;
  font-size: 1.1rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.home-preview__company {
  margin-top: 0.25rem;
  color: var(--on-surface-var);
  font-size: 0.875rem;
}

.home-preview__chips {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-top: 0.85rem;
}

.home-preview__feed {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.home-preview__item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.9rem 1rem;
  background: var(--surface-low);
  border-radius: var(--radius-lg);
}

.home-preview__item p {
  font-weight: 600;
  margin-bottom: 0.15rem;
}

.home-preview__item span {
  font-size: 0.8125rem;
  color: var(--on-surface-var);
}

.home-preview__dot {
  width: 0.7rem;
  height: 0.7rem;
  border-radius: 50%;
  margin-top: 0.3rem;
  flex-shrink: 0;
}

.home-preview__dot--amber {
  background: var(--secondary-container);
}

.home-preview__dot--emerald {
  background: var(--tertiary-fixed);
}

.home-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1.25rem;
  position: relative;
  z-index: 1;
}

.home-outro {
  position: relative;
  z-index: 1;
}

.home-outro__panel {
  padding: 1.5rem;
  display: grid;
  gap: 1rem;
}

.home-outro__header h3 {
  font-family: 'Manrope', sans-serif;
  font-size: 1.2rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  margin-top: 0.35rem;
}

.home-outro__lede {
  max-width: 70ch;
  color: var(--on-surface-var);
  line-height: 1.7;
}

.home-outro__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.85rem;
}

.home-outro__item {
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
  padding: 1rem;
  border-radius: var(--radius-lg);
  background: var(--surface-low);
}

.home-outro__index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  background: rgba(254, 147, 44, 0.16);
  color: var(--secondary);
  font-size: 0.75rem;
  font-weight: 700;
  flex-shrink: 0;
}

.home-outro__item p {
  font-weight: 700;
  margin-bottom: 0.15rem;
}

.home-outro__item span {
  font-size: 0.8125rem;
  color: var(--on-surface-var);
}

.home-cta {
  position: relative;
  z-index: 1;
}

.home-cta__panel {
  padding: 1.5rem;
  display: grid;
  gap: 1rem;
}

.home-cta__copy {
  display: grid;
  gap: 0.5rem;
  max-width: 68ch;
}

.home-cta__copy h3 {
  font-family: 'Manrope', sans-serif;
  font-size: 1.2rem;
  font-weight: 700;
  letter-spacing: -0.03em;
}

.home-cta__copy p:last-child {
  color: var(--on-surface-var);
  line-height: 1.7;
}

.home-cta__rail {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.85rem;
}

.home-cta__tile {
  padding: 1rem;
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, rgba(254, 147, 44, 0.08), rgba(133, 248, 196, 0.05));
  min-height: 7rem;
}

.home-cta__tile span {
  display: block;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--on-surface-var);
  margin-bottom: 0.45rem;
}

.home-cta__tile p {
  font-weight: 600;
  line-height: 1.6;
}

.home-card {
  padding: 1.5rem;
}

.home-card h3 {
  font-family: 'Manrope', sans-serif;
  font-size: 1.2rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  margin-top: 0.35rem;
}

.home-list {
  margin-top: 1rem;
  padding-left: 1rem;
  display: grid;
  gap: 0.65rem;
  color: var(--on-surface-var);
  line-height: 1.6;
}

.home-steps {
  display: grid;
  gap: 0.85rem;
  margin-top: 1rem;
}

.home-step {
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
  padding: 0.95rem 1rem;
  border-radius: var(--radius-lg);
  background: var(--surface-low);
}

.home-step__index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  background: var(--secondary);
  color: #fff;
  font-size: 0.75rem;
  font-weight: 700;
  flex-shrink: 0;
}

.home-step p {
  font-weight: 700;
  margin-bottom: 0.15rem;
}

.home-step span {
  font-size: 0.8125rem;
  color: var(--on-surface-var);
}

@media (max-width: 980px) {
  .home-hero,
  .home-grid {
    grid-template-columns: 1fr;
  }

  .home-outro__grid {
    grid-template-columns: 1fr;
  }

  .home-cta__rail {
    grid-template-columns: 1fr;
  }

  .home-copy h1 {
    max-width: none;
  }

  .home-metrics {
    grid-template-columns: 1fr;
  }
}
</style>
