import type { Edition, EditionItem, ReaderPreferences } from '../../lib/api'

const RANK = { critical: 3, high: 2, medium: 1, low: 0 } as const
const TRUSTED = new Set(['confirmed', 'reliable'])

/** An analyzed news the reader's preferences keep: one of their domains, important enough, trusted if asked. */
export function keepsAnalyzed(item: EditionItem, prefs: ReaderPreferences): boolean {
  if (prefs.domains.length && !item.categories.some((category) => prefs.domains.includes(category))) return false
  if (prefs.min_importance && (!item.importance || RANK[item.importance] < RANK[prefs.min_importance])) return false
  return prefs.include_unconfirmed || TRUSTED.has(item.reliability?.label ?? '')
}

/**
 * A news the AI did not analyze has no importance and nothing verified: kept only when the reader
 * set no importance threshold, accepts unconfirmed news, and its source covers one of their domains.
 */
export function keepsUnanalyzed(item: EditionItem, prefs: ReaderPreferences): boolean {
  if (prefs.min_importance || !prefs.include_unconfirmed) return false
  return !prefs.domains.length || (!!item.source_domain && prefs.domains.includes(item.source_domain))
}

/** "My selection": the edition as the reader's preferences filter it. */
export function applySelection<T extends Edition>(edition: T, prefs: ReaderPreferences): T {
  const sections = edition.sections
    .map((section) => ({ ...section, items: section.items.filter((item) => keepsAnalyzed(item, prefs)) }))
    .filter((section) => section.items.length > 0)
  const unanalyzed = edition.unanalyzed.filter((item) => keepsUnanalyzed(item, prefs))
  const count = sections.reduce((total, section) => total + section.items.length, 0) + unanalyzed.length
  return { ...edition, sections, unanalyzed, selected_count: count }
}
