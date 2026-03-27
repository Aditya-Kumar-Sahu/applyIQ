<template>
  <main class="grid">
    <h1 class="page-hero">Autonomous job hunting, with a human approval gate.</h1>
    <section class="hero-card">
      <p class="eyebrow">Portfolio flagship</p>
      <h2>Your job search, on autopilot.</h2>
      <p class="lede">
        ApplyIQ scouts jobs, ranks them semantically, drafts tailored applications, pauses for your
        approval, and only then automates the safe parts.
      </p>
      <RouterLink class="button-link" to="/dashboard">Open command centre</RouterLink>
    </section>

    <section class="panel">
      <h3>Why this build matters</h3>
      <ul class="feature-list">
        <li>LangGraph orchestration with pause and resume.</li>
        <li>ToS-aware, multi-source job discovery.</li>
        <li>Human-in-the-loop approval before every submission.</li>
        <li>Encrypted credentials and resumable automation.</li>
      </ul>
    </section>
  </main>
</template>

<script setup lang="ts">
import { RouterLink } from "vue-router";
</script>
