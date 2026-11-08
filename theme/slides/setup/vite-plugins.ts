// Build-time data for the trureturing Slidev theme, exposed as the virtual module
// `virtual:trureturing` (typed in ../env.d.ts):
//
//   lang      edition language derived from the entry file name (slides.md → zh, slides.<lang>.md → lang)
//   book/deck from the entry path books/<slug>/slides/<deck>/
//   lock      {repo, commit, decls: {gid: {name, kind, line}}} read from trureturing.lock.json — the
//             only source that decides whether <LeanBadge> shows the green LEAN ✓
//   text      the merged i18n table for `lang` (theme/i18n/<lang>.toml overridden by i18n/<lang>.toml)
//
// It also drops the legacy `.woff`/`.ttf` fallbacks from the @fontsource and KaTeX stylesheets, so
// a build ships each self-hosted font face once (woff2 only; every browser Slidev supports reads
// woff2), and keeps Vite's dependency cache out of the deck directory.
import { basename, dirname, join, relative, sep } from 'node:path'
import { ROOT, i18n, langOfFile, loadLock } from '../../../tools/node/slides-lib.mjs'

const ID = 'virtual:trureturing'
const RESOLVED = `\0${ID}`
const FONT_CSS = /[\\/](?:@fontsource[\\/][^?]+|katex[\\/]dist[\\/]katex(?:\.min)?)\.css(?:\?.*)?$/
const LEGACY_FONT = /,\s*url\([^)]*\.(?:woff|ttf)\)\s*format\(['"](?:woff|truetype)['"]\)/g

interface Options { entry: string, userRoot: string }

function data(entry: string) {
  const lang = langOfFile(basename(entry)) ?? 'zh'
  const parts = relative(join(ROOT, 'books'), dirname(entry)).split(sep)
  const inBook = parts.length === 3 && parts[1] === 'slides'
  const book = inBook ? parts[0] : ''
  const deck = inBook ? parts[2] : ''
  const lock = loadLock()
  const decls: Record<string, { name: string, kind: string, line: number }> = {}
  for (const [gid, d] of Object.entries<any>(lock?.declarations ?? {}))
    decls[gid] = { name: String(d.name ?? ''), kind: String(d.kind ?? ''), line: Number(d.line ?? 0) }
  return {
    lang,
    book,
    deck,
    lock: lock ? { repo: String(lock.repo), commit: String(lock.commit), decls } : null,
    text: i18n(lang),
  }
}

export default function setupVitePlugins(options: Options) {
  const watched = [join(ROOT, 'trureturing.lock.json'), join(ROOT, 'theme', 'i18n'), join(ROOT, 'i18n')]
  return [
    {
      name: 'trureturing:data',
      config() {
        const parts = relative(ROOT, options.userRoot).split(sep).filter(p => p && p !== '..')
        return { cacheDir: join(ROOT, 'node_modules', '.vite', `slidev-${parts.join('-') || 'deck'}`) }
      },
      resolveId(id: string) {
        return id === ID ? RESOLVED : undefined
      },
      load(id: string) {
        if (id !== RESOLVED)
          return undefined
        return `export default ${JSON.stringify(data(options.entry))}`
      },
      configureServer(server: any) {
        server.watcher.add(watched)
        server.watcher.on('change', (file: string) => {
          if (!watched.some(w => file === w || file.startsWith(w + sep)))
            return
          const mod = server.moduleGraph.getModuleById(RESOLVED)
          if (mod) {
            server.moduleGraph.invalidateModule(mod)
            server.ws.send({ type: 'full-reload' })
          }
        })
      },
    },
    {
      name: 'trureturing:woff2-only-fonts',
      enforce: 'pre' as const,
      transform(code: string, id: string) {
        if (!FONT_CSS.test(id))
          return undefined
        return { code: code.replace(LEGACY_FONT, ''), map: null }
      },
    },
  ]
}
