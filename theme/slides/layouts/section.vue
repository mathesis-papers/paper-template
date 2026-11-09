<!--
  Chapter divider: the default frame with a large outlined numeral and the chapter title.
  Frontmatter: chapter: "01" (the numeral), section: "…" (header). Body: kicker, h2.t and a lead.
-->
<script setup lang="ts">
import Default from './default.vue'

defineOptions({ inheritAttrs: false })
const props = defineProps<{ chapter?: string | number, section?: string, class?: string }>()
</script>

<template>
  <Default :section="props.section" :class="['divider', props.class]">
    <div class="divider-n" aria-hidden="true">{{ props.chapter }}</div>
    <div class="body center divider-body"><slot /></div>
  </Default>
</template>
