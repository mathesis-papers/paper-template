// Interface strings of the slide theme (badges, footer labels, site buttons).
//
// Lookup order: the shared i18n table that setup/vite-plugins.ts injects for the deck's language
// (theme/i18n/<lang>.toml, overridden by i18n/<lang>.toml in the books repository), then the
// component-local defaults below. The `slides.*` keys are not yet in theme/i18n/*.toml; once they
// are merged there (see LOCAL), the shared values win automatically.
import tr from 'virtual:trureturing'

const LOCAL: Record<string, Record<string, string>> = {
  zh: {
    'slides.badge_unverified': 'UNVERIFIED',
    'slides.badge_unverified_title': '该声明不在 trureturing.lock.json 中：未经 Lean 内核验证',
    'slides.badge_argued': 'ARGUED',
    'slides.badge_argued_title': '有论证，但未经 Lean 内核验证',
    'slides.no_lean': '尚无 Lean 证明',
    'slides.book': '书',
    'slides.version': '版本',
    'slides.commit': 'trureturing 提交',
    'slides.source': '出处',
    'slides.index': '回到幻灯片目录',
    'slides.switch_lang': '切换到',
    'slides.pdf': '下载 PDF',
  },
  en: {
    'slides.badge_unverified': 'UNVERIFIED',
    'slides.badge_unverified_title': 'Not in trureturing.lock.json: not kernel-verified in Lean',
    'slides.badge_argued': 'ARGUED',
    'slides.badge_argued_title': 'Argued, but not kernel-verified in Lean',
    'slides.no_lean': 'No Lean proof yet',
    'slides.book': 'Book',
    'slides.version': 'Version',
    'slides.commit': 'trureturing commit',
    'slides.source': 'Source',
    'slides.index': 'Back to all slides',
    'slides.switch_lang': 'Switch to',
    'slides.pdf': 'Download PDF',
  },
}

function lookup(table: any, dotted: string): string | undefined {
  let node = table
  for (const part of dotted.split('.')) {
    if (!node || typeof node !== 'object' || !(part in node))
      return undefined
    node = node[part]
  }
  return node == null ? undefined : String(node)
}

/** The deck's edition language (zh for slides.md, <lang> for slides.<lang>.md). */
export const lang: string = tr.lang

/** Look up an interface string such as t('badge.lean') or t('slides.source'). */
export function t(key: string): string {
  return lookup(tr.text, key) ?? LOCAL[lang]?.[key] ?? LOCAL.en[key] ?? key
}
