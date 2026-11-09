<!-- "current / total" for slides that draw their own frame (bare: true). The current page is amber ("now"). -->
<script setup lang="ts">
import { useSlideContext } from '@slidev/client'

const { $page, $nav } = useSlideContext()
const pad = (n: number) => String(n).padStart(2, '0')
</script>

<template>
  <span class="pg"><b>{{ pad($page) }}</b><i>/</i>{{ pad($nav.total) }}</span>
</template>
