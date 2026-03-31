<template>
  <span class="status-chip" :class="`status-chip--${tone}`">
    <slot>{{ label }}</slot>
  </span>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    label?: string;
    tone?: 'neutral' | 'amber' | 'emerald' | 'error';
  }>(),
  {
    tone: 'neutral',
  },
);
</script>