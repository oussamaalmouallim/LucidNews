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

/** A domain section of an edition: ``other`` holds the news no domain could be given to. */
export type DomainKey = (typeof domainCategories)[number] | 'other'

export type DomainGroup = {
  key: DomainKey
  /** Analyzed news whose main domain (the first the AI gave) is this one, best score first. */
  items: EditionItem[]
  /** News the AI did not analyze, placed by the usual domain of their source. */
  unanalyzed: EditionItem[]
}

export const domainIcons: Record<DomainKey, LucideIcon> = {
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

export const domainTitle = (language: Language, key: DomainKey) => (key === 'other' ? translate(language, 'domain.other') : categoryLabel(language, key))

const isDomain = (value: string | null | undefined): value is DomainKey => !!value && (domainCategories as readonly string[]).includes(value)

const byScore = (a: EditionItem, b: EditionItem) => (b.score ?? 0) - (a.score ?? 0) || b.published_at.localeCompare(a.published_at)

/**
 * The edition by domain, in the taxonomy order, empty domains left out. Each news appears once.
 * With ``focus`` (the domain filter), every news shown belongs to that one section.
 */
export function groupByDomain(edition: Edition, focus: string | null = null): DomainGroup[] {
  const groups = new Map<DomainKey, DomainGroup>()
  const add = (key: DomainKey, kind: 'items' | 'unanalyzed', item: EditionItem) => {
    if (!groups.has(key)) groups.set(key, { key, items: [], unanalyzed: [] })
    groups.get(key)![kind].push(item)
  }
  for (const item of edition.sections.flatMap((section) => section.items)) {
    const main = isDomain(focus) ? focus : item.categories[0]
    add(isDomain(main) ? main : 'other', 'items', item)
  }
  for (const item of edition.unanalyzed) add(isDomain(item.source_domain) ? item.source_domain : 'other', 'unanalyzed', item)

  const order: DomainKey[] = [...domainCategories, 'other']
  return order.flatMap((key) => {
    const group = groups.get(key)
    return group ? [{ ...group, items: group.items.sort(byScore) }] : []
  })
}
