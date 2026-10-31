import {
  ChartColumn,
  Cloud,
  CodeXml,
  Database,
  GitFork,
  Globe,
  Infinity as Loop,
  Layers,
  Rocket,
  Server,
  ShieldHalf,
  Sparkles,
  Wrench,
  type LucideIcon,
} from 'lucide-react'
import { domainCategories, type Edition, type EditionItem } from '../../lib/api'
import { categoryLabel, translate, type Language } from '../../lib/i18n'

/** A domain section of an edition: a category of the installation's sector, or ``other`` for the
 * news no domain could be given to. The categories come from the server (``useDomainCategories``). */
export type DomainKey = string

export type DomainGroup = {
  key: DomainKey
  /** Analyzed news whose main domain (the first the AI gave) is this one, best score first. */
  items: EditionItem[]
  /** News the AI did not analyze, placed by the usual domain of their source. */
  unanalyzed: EditionItem[]
}

const icons: Record<string, LucideIcon> = {
  ai: Sparkles,
  'software-development': CodeXml,
  cloud: Cloud,
  devops: Loop,
  data: ChartColumn,
  cybersecurity: ShieldHalf,
  web: Globe,
  'open-source': GitFork,
  'developer-tools': Wrench,
  databases: Database,
  infrastructure: Server,
  'emerging-tech': Rocket,
  other: Layers,
}

/** The icon of a domain; a category without its own icon (another sector) gets the generic one. */
export const domainIcon = (key: DomainKey): LucideIcon => icons[key] ?? Layers

export const domainTitle = (language: Language, key: DomainKey) => (key === 'other' ? translate(language, 'domain.other') : categoryLabel(language, key))

const byScore = (a: EditionItem, b: EditionItem) => (b.score ?? 0) - (a.score ?? 0) || b.published_at.localeCompare(a.published_at)

/**
 * The edition by domain, in the taxonomy order, empty domains left out. Each news appears once.
 * With ``focus`` (the domain filter), every news shown belongs to that one section; with
 * ``followed`` (the reader's domains), a news goes under the first of them it belongs to.
 */
export function groupByDomain(
  edition: Edition,
  focus: string | null = null,
  followed: readonly string[] = [],
  categories: readonly string[] = domainCategories,
): DomainGroup[] {
  const isDomain = (value: string | null | undefined): value is DomainKey => !!value && categories.includes(value)
  const groups = new Map<DomainKey, DomainGroup>()
  const add = (key: DomainKey, kind: 'items' | 'unanalyzed', item: EditionItem) => {
    if (!groups.has(key)) groups.set(key, { key, items: [], unanalyzed: [] })
    groups.get(key)![kind].push(item)
  }
  for (const item of edition.sections.flatMap((section) => section.items)) {
    // In "My selection", a news goes under the first of its domains the reader follows.
    const main = isDomain(focus) ? focus : (item.categories.find((category) => followed.includes(category)) ?? item.categories[0])
    add(isDomain(main) ? main : 'other', 'items', item)
  }
  for (const item of edition.unanalyzed) add(isDomain(item.source_domain) ? item.source_domain : 'other', 'unanalyzed', item)

  const order: DomainKey[] = [...categories, 'other']
  return order.flatMap((key) => {
    const group = groups.get(key)
    return group ? [{ ...group, items: group.items.sort(byScore) }] : []
  })
}
