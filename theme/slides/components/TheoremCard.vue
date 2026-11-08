<!--
  A numbered statement with its verification state, mirroring the book's theorem environment:
    <TheoremCard label="定理 1.2" title="亏量只取三个值" gid="D5/S1/Deficit/DeficitThreeValued.deficit_three_valued">

    $$c(v_1, v_2) \in \{-1, 0, 1\}$$

    </TheoremCard>
  Props: label (kind and number, as the book prints it), title, gid (Lean GID; must be in
  trureturing.lock.json), status ('open' for an open problem, 'argued' for an unverified argument),
  kind ('definition' for a definition card: cyan rule, the GID may name a Lean def), cite (the id of
  the matching environment in the book, e.g. thm-deficit; ./tbook check then verifies that label and
  GID agree with the book). The statement goes in the default slot (Markdown and KaTeX work when it is
  separated by blank lines; keep it unindented).
-->
<script setup lang="ts">
import { computed } from 'vue'
import LeanBadge from './LeanBadge.vue'
import { leanInfo } from '../lean'
import { t } from '../i18n'

const props = defineProps<{ label?: string, title?: string, gid?: string, status?: 'open' | 'argued', kind?: string, cite?: string }>()
const info = computed(() => leanInfo(props.gid))
const state = computed(() => props.status ?? (info.value.locked ? 'lean' : 'unverified'))
const kindClass = computed(() => props.kind === 'definition' ? 'tr-thm-def' : '')
</script>

<template>
  <section class="tr-thm" :class="[`tr-thm-${state}`, kindClass]" :data-cite="props.cite">
    <header class="tr-thm-head">
      <span class="tr-thm-label">{{ props.label }}</span>
      <span v-if="props.title" class="tr-thm-title">{{ props.title }}</span>
      <LeanBadge :gid="props.gid" :status="props.status" />
    </header>
    <div class="tr-thm-body"><slot /></div>
    <footer class="tr-thm-decl">
      <template v-if="props.gid">
        <span class="tr-thm-glyph" aria-hidden="true">λ</span>
        <a v-if="info.url" :href="info.url" target="_blank" rel="noopener"><code>{{ info.name }}</code></a>
        <code v-else>{{ info.name }}</code>
      </template>
      <span v-else class="tr-thm-none">{{ props.status === 'argued' ? t('slides.badge_argued_title') : t('slides.no_lean') }}</span>
    </footer>
  </section>
</template>
