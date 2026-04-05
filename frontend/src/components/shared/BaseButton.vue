<template>
  <component
    :is="tag"
    class="base-button"
    :class="[`base-button--${variant}`, `base-button--${size}`]"
    v-bind="buttonAttributes"
  >
    <slot />
  </component>
</template>

<script setup lang="ts">
import { computed } from 'vue';

defineOptions({ inheritAttrs: false });

const props = withDefaults(
  defineProps<{
    as?: 'button' | 'a' | 'div';
    variant?: 'primary' | 'secondary' | 'ghost';
    size?: 'sm' | 'md' | 'lg';
    type?: 'button' | 'submit' | 'reset';
    href?: string;
  }>(),
  {
    as: 'button',
    variant: 'primary',
    size: 'md',
    type: 'button',
  },
);

const tag = computed(() => props.as);

const buttonAttributes = computed(() => {
  if (props.as !== 'button') {
    return props.as === 'a' && props.href ? { href: props.href } : {};
  }

  return {
    type: props.type,
  };
});
</script>