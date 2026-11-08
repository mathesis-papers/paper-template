<!--
  The source line at the bottom of a slide, above the footer: <Source>D5/S1/Deficit/DeficitInteger.lean</Source>.
  Facts on a slide name where they come from (a Lean module, a chapter of the book, a paper).
-->
<script setup lang="ts">
import { t } from '../i18n'
</script>

<template>
  <p class="src"><span class="src-k">{{ t('slides.source') }}</span><slot /></p>
</template>
