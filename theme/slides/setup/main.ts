// Client setup of the trureturing slide theme.
//
// 1. No flash of fallback fonts (FOUT): when a slide is entered (also the first one) before the
//    fonts it uses have arrived, its content stays hidden — laid out normally, fonts loading — and
//    is shown once they are ready: at most 3 s for the first slide, 1 s on later navigation.
//    Mounted slides preload their font subsets in the background. Disabled in PDF export (?print),
//    which waits for fonts itself.
// 2. On the published site (the build passes VITE_SITE_*), small buttons at the top right: switch to
//    the other language edition on the same slide, download the PDF, back to the slides index.
//    They fade out while the pointer rests, so they never cover a presentation.
//
// Adapted from chrono-company-slides theme/setup/main.ts (Apache-2.0).
import { defineAppSetup } from '@slidev/types'
import { t } from '../i18n'

const PENDING = 'fonts-pending'
const FIRST_TIMEOUT = 3000
const NAV_TIMEOUT = 1000
const IDLE_MS = 2500

const nextFrame = () => new Promise<void>(resolve => requestAnimationFrame(() => resolve()))
const sleep = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms))

// Group the text of a slide (or the whole document) by font: CSS font shorthand → characters used.
function fontGroups(root: ParentNode): Map<string, string> {
  const groups = new Map<string, Set<string>>()
  const els = root instanceof Element && root.matches('.slide')
    ? [root, ...root.querySelectorAll<HTMLElement>('*')]
    : [...root.querySelectorAll<HTMLElement>('.slide, .slide *')]
  for (const el of els) {
    let text = ''
    for (const node of el.childNodes) {
      if (node.nodeType === Node.TEXT_NODE)
        text += node.textContent ?? ''
    }
    if (!text.trim())
      continue
    const cs = getComputedStyle(el)
    const font = `${cs.fontStyle} ${cs.fontWeight} 16px ${cs.fontFamily}`
    const chars = groups.get(font) ?? new Set<string>()
    for (const ch of text) chars.add(ch)
    groups.set(font, chars)
  }
  return new Map([...groups].map(([font, chars]) => [font, [...chars].join('')]))
}

const fontsReady = (groups: Map<string, string>) => [...groups].every(([font, text]) => document.fonts.check(font, text))
const loadFonts = (groups: Map<string, string>) => Promise.all([...groups].map(([font, text]) => document.fonts.load(font, text).catch(() => [])))
const slideOf = (no: string) => document.querySelector<HTMLElement>(`.slidev-page-${no} .slide`)

interface SiteLang { lang: string, name: string, href: string }

const ICON_INDEX = '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2" y="2" width="5" height="5"/><rect x="9" y="2" width="5" height="5"/><rect x="2" y="9" width="5" height="5"/><rect x="9" y="9" width="5" height="5"/></svg>'
const ICON_LANG = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.3"><circle cx="8" cy="8" r="6.2"/><ellipse cx="8" cy="8" rx="2.6" ry="6.2"/><path d="M2 8h12M3 4.8h10M3 11.2h10"/></svg>'
const ICON_PDF = '<svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M8 2v8M4.5 6.8 8 10.3l3.5-3.5M3 13.5h10"/></svg>'

function iconButton(href: string, label: string, icon: string) {
  const a = document.createElement('a')
  a.className = 'site-nav-btn'
  a.href = href
  a.title = label
  a.setAttribute('aria-label', label)
  a.innerHTML = icon
  return a
}

function mountSiteNav(index: string, langs: SiteLang[], current: string | undefined, pdf: string | undefined) {
  const nav = document.createElement('nav')
  nav.className = 'site-nav'
  // Switch to the next language edition, keeping #/<page> so the audience stays on the same slide.
  const i = langs.findIndex(l => l.lang === current)
  const next = i >= 0 && langs.length > 1 ? langs[(i + 1) % langs.length] : undefined
  if (next) {
    const a = iconButton(next.href, `${t('slides.switch_lang')} ${next.name}`, ICON_LANG)
    a.lang = next.lang
    a.addEventListener('click', () => { a.href = next.href + location.hash })
    nav.append(a)
  }
  if (pdf)
    nav.append(iconButton(pdf, t('slides.pdf'), ICON_PDF))
  nav.append(iconButton(index, t('slides.index'), ICON_INDEX))
  document.body.append(nav)
  let timer: ReturnType<typeof setTimeout> | undefined
  const wake = () => {
    nav.classList.remove('idle')
    clearTimeout(timer)
    timer = setTimeout(() => nav.classList.add('idle'), IDLE_MS)
  }
  for (const ev of ['mousemove', 'pointerdown', 'touchstart'])
    window.addEventListener(ev, wake, { passive: true })
  wake()
}

export default defineAppSetup(({ router }) => {
  if (typeof window === 'undefined' || new URLSearchParams(location.search).has('print'))
    return
  const root = document.documentElement

  const env = import.meta.env as Record<string, string | undefined>
  if (env.VITE_SITE_INDEX) {
    let langs: SiteLang[] = []
    try { langs = JSON.parse(env.VITE_SITE_LANGS ?? '[]') }
    catch {}
    mountSiteNav(env.VITE_SITE_INDEX, langs, env.VITE_SITE_LANG, env.VITE_SITE_PDF || undefined)
  }

  // Preload: after slides mount, load the font subsets they use (debounced).
  let timer: ReturnType<typeof setTimeout> | undefined
  new MutationObserver(() => {
    clearTimeout(timer)
    timer = setTimeout(() => loadFonts(fontGroups(document)), 300)
  }).observe(document.body, { childList: true, subtree: true })

  // Gate: hide the target slide until it is rendered and its fonts are ready.
  let first = true
  let seq = 0
  router.beforeEach((to) => {
    const no = to.params.no as string | undefined
    if (!no)
      return
    const el = slideOf(no)
    if (!el || !fontsReady(fontGroups(el)))
      root.classList.add(PENDING)
  })
  router.afterEach(async (to) => {
    const no = to.params.no as string | undefined
    const id = ++seq
    const limit = first ? FIRST_TIMEOUT : NAV_TIMEOUT
    first = false
    if (!no || !root.classList.contains(PENDING)) {
      root.classList.remove(PENDING)
      return
    }
    const deadline = performance.now() + limit
    let el = slideOf(no)
    while (!el && performance.now() < deadline) { // slide components load asynchronously
      await nextFrame()
      el = slideOf(no)
    }
    await nextFrame()
    await nextFrame()
    if (el)
      await Promise.race([loadFonts(fontGroups(el)), sleep(Math.max(0, deadline - performance.now()))])
    if (id === seq) // a later navigation took over
      root.classList.remove(PENDING)
  })
})
