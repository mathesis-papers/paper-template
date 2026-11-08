// Merged with Slidev's own UnoCSS configuration. Theme class names that collide with UnoCSS
// utilities are blocked here so the utility does not override the theme rule;
// tools/node/slides-check.mjs reports new collisions in decks (keep both lists in sync).
import { defineConfig } from 'unocss'

export default defineConfig({
  blocklist: ['mt', 'mb-0', 'grow'],
})
