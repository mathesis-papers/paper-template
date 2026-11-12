<!--
  KaTeX inside HTML blocks, where Slidev's Markdown `$…$` is not processed:
    <Tex t="c(v_1, v_2) \in \{-1, 0, 1\}" />          inline
    <Tex display t="\exists\, r,\ t = r \circ p" />      display
  Rendered at build time by the same KaTeX that Slidev bundles (fonts self-hosted, works offline).
-->
<script setup lang="ts">
import { computed } from 'vue'
import katex from 'katex'

const props = defineProps<{ t: string, display?: boolean }>()
const html = computed(() => katex.renderToString(props.t, { displayMode: !!props.display, throwOnError: false, output: 'htmlAndMathml' }))
</script>

<template>
  <div v-if="props.display" class="tex-display" v-html="html" />
  <span v-else class="tex" v-html="html" />
</template>
