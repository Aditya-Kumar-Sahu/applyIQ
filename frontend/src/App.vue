<template>
  <div class="shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">ApplyIQ</p>
        <h1>Autonomous job hunting, with a human approval gate.</h1>
      </div>
      <nav class="nav">
        <RouterLink to="/">Overview</RouterLink>
        <RouterLink to="/dashboard">Dashboard</RouterLink>
      </nav>
    </header>

    <RouterView />
  </div>
</template>

<script setup lang="ts">
import { RouterLink, RouterView } from "vue-router";
</script>
