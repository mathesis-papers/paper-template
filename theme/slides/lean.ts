// Lean verification state of a declaration, as recorded in trureturing.lock.json at build time.
// A GID is verified for the slides exactly when the lock resolves it; the build never guesses.
import tr from 'virtual:trureturing'

export interface LeanInfo {
  gid: string
  locked: boolean
  name: string
  kind: string
  url: string
}

const GID_RE = /^(D[0-9]+\/S[0-9]+\/(?:[A-Za-z_][A-Za-z0-9_]*\/)*[A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][\w']*(?:\.[A-Za-z_][\w']*)*)$/

export function leanInfo(gid: string | undefined): LeanInfo {
  const id = (gid ?? '').trim()
  const decl = tr.lock?.decls[id]
  const m = GID_RE.exec(id)
  const module = m?.[1] ?? ''
  const fallback = m ? `${module.replaceAll('/', '.')}.${m[2]}` : id
  const url = decl && tr.lock
    ? `https://github.com/${tr.lock.repo}/blob/${tr.lock.commit}/${module}.lean${decl.line ? `#L${decl.line}` : ''}`
    : ''
  return { gid: id, locked: !!decl, name: decl?.name || fallback, kind: decl?.kind ?? '', url }
}

/** The pinned trureturing commit (short) and its tree URL, or empty strings without a lock. */
export const pinned = tr.lock
  ? { short: tr.lock.commit.slice(0, 8), url: `https://github.com/${tr.lock.repo}/tree/${tr.lock.commit}`, repo: tr.lock.repo }
  : { short: '', url: '', repo: '' }
