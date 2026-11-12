<!--
  A large figure with a caption: <Stat value="5" label="条冻结的 Lean 声明" tone="ok" />.
  tone: cyan (default) | magenta | ok (Lean-verified only) | amber (current/now only) | warn | violet.
-->
<script setup lang="ts">
const props = withDefaults(defineProps<{ value: string | number, label?: string, unit?: string, tone?: string }>(), { tone: 'cyan' })
</script>

<template>
  <div class="tr-stat" :class="`tone-${props.tone}`">
    <div class="tr-stat-n">{{ props.value }}<small v-if="props.unit">{{ props.unit }}</small></div>
    <div v-if="props.label || $slots.default" class="tr-stat-l"><slot>{{ props.label }}</slot></div>
  </div>
</template>
