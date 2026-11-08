<!--
  Verification badge. Colour carries meaning (theme/tokens.json semantics):
    gid="<GID>"        green LEAN ✓ (links to the Lean source at the pinned commit) only when
                       trureturing.lock.json resolves the GID; otherwise a red UNVERIFIED warning
    status="open"      red OPEN: an open problem, no Lean proof
    status="argued"    violet ARGUED: argued, but not kernel-verified
  ./tbook check and tools/node/slides-check.mjs reject unlocked GIDs, so UNVERIFIED should never ship.
-->
<script setup lang="ts">
import { computed } from 'vue'
import { leanInfo } from '../lean'
import { t } from '../i18n'

const props = defineProps<{ gid?: string, status?: 'open' | 'argued' }>()
const info = computed(() => leanInfo(props.gid))
const state = computed(() => {
  if (props.status === 'open' || props.status === 'argued')
    return props.status
  return info.value.locked ? 'lean' : 'unverified'
})
const label = computed(() => ({
  lean: t('badge.lean'),
  open: t('badge.open'),
  argued: t('slides.badge_argued'),
  unverified: t('slides.badge_unverified'),
})[state.value])
const title = computed(() => ({
  lean: `${t('badge.lean_title')} · ${info.value.name}`,
  open: t('badge.open_title'),
  argued: t('slides.badge_argued_title'),
  unverified: `${t('slides.badge_unverified_title')} · ${info.value.gid || '—'}`,
})[state.value])
</script>

<template>
  <a v-if="state === 'lean' && info.url" class="tr-badge tr-badge-lean" :href="info.url" target="_blank" rel="noopener" :title="title">{{ label }}</a>
  <span v-else class="tr-badge" :class="`tr-badge-${state}`" :title="title">{{ label }}</span>
</template>
