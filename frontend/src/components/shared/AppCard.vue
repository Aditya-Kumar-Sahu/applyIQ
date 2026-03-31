<template>
  <component :is="as" class="app-card" :class="[`app-card--${tone}`, { 'app-card--interactive': interactive }]">
    <slot />
  </component>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    as?: string;
    tone?: 'default' | 'soft' | 'glass';
    interactive?: boolean;
  }>(),
  {
    as: 'div',
    tone: 'default',
    interactive: false,
  },
);
</script>