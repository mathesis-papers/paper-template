// Slidev's shortcuts plus F for full screen (as in chrono-company-slides theme/setup/shortcuts.ts).
import type { NavOperations, ShortcutOptions } from '@slidev/types'
import { defineShortcutsSetup } from '@slidev/types'

export default defineShortcutsSetup((_nav: NavOperations, base: ShortcutOptions[]) => [
  ...base,
  {
    name: 'toggle_fullscreen',
    key: 'f',
    fn: () => document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen(),
  },
])
