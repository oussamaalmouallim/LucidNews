import { useQuery } from '@tanstack/react-query'
import { m } from 'motion/react'
import { useMemo, type ReactNode } from 'react'
import { useParams, useSearchParams } from 'react-router'
import { ApiErrorCard } from '../../design/PageState'
import { domainCategories, fetchAllEditions, fetchEdition, fetchPeriod, type Edition, type Period } from '../../lib/api'
import { capitalize, formatPeriod, periodBounds, type PeriodKind } from '../../lib/format'
import { translatePlural, useLanguage } from '../../lib/i18n'
import { listStagger, useMotionPreference } from '../../lib/motion'
import { EditionHero } from './EditionHero'
import { EditionSidebar } from './EditionSidebar'
import { PeriodFilter, type DomainOption, type PeriodChoice } from './PeriodFilter'
import { DomainJumpBar, DomainSection } from './DomainSection'
import { groupByDomain } from './domains'
import { UnanalyzedNote } from './Unanalyzed'

const PERIOD_PARAMS: PeriodKind[] = ['day', 'month', 'year']

/** The period in the address (`?month=2026-10`), if valid. Shareable, and Back works. */
function periodFromParams(params: URLSearchParams): PeriodChoice {
  for (const kind of PERIOD_PARAMS) {
    const value = params.get(kind)
    if (value && periodBounds(kind, value)) return { kind, value }
  }
  return null
}

/** The domain in the address (`?domain=ai`), if it is one of the 12. */
function domainFromParams(params: URLSearchParams): string | null {
  const value = params.get('domain')
  return value && (domainCategories as readonly string[]).includes(value) ? value : null
}

const itemsOf = (edition: Edition) => edition.sections.flatMap((section) => section.items)

/**
 * Only the news of ``domain``: the analyzed ones the AI placed in it (main domain or not), and
 * the unanalyzed ones whose source usually covers it. Sections left empty disappear.
 */
function applyDomain<T extends Edition>(edition: T, domain: string | null): T {
  if (!domain) return edition
  const sections = edition.sections
    .map((section) => ({ ...section, items: section.items.filter((item) => item.categories.includes(domain)) }))
    .filter((section) => section.items.length > 0)
  const unanalyzed = edition.unanalyzed.filter((item) => item.source_domain === domain)
  const count = sections.reduce((total, section) => total + section.items.length, 0) + unanalyzed.length
  return { ...edition, sections, unanalyzed, selected_count: count }
}

export function EditionPage() {
  const { editionId = 'latest' } = useParams()
  const [params, setParams] = useSearchParams()
  const { language } = useLanguage()
  const choice = editionId === 'latest' ? periodFromParams(params) : null
  const domain = editionId === 'latest' ? domainFromParams(params) : null
  const editions = useQuery({ queryKey: ['editions', 'all'], queryFn: ({ signal }) => fetchAllEditions(signal), enabled: editionId === 'latest' })

  const setChoice = (next: PeriodChoice) =>
    setParams(
      (current) => {
        for (const kind of PERIOD_PARAMS) current.delete(kind)
        if (next) current.set(next.kind, next.value)
        return current
      },
      { replace: false },
    )

  const query = useQuery({
    queryKey: ['edition', editionId, language],
    queryFn: ({ signal }) => fetchEdition(editionId, language, signal),
    placeholderData: (previous) => previous, // keep the page while switching language
    enabled: !choice,
  })
  const bounds = choice ? periodBounds(choice.kind, choice.value) : null
  const period = useQuery({
    queryKey: ['period', choice?.kind, choice?.value, language],
    queryFn: ({ signal }) => fetchPeriod(bounds!.since, bounds!.until, language, signal),
    placeholderData: (previous) => previous,
    enabled: !!bounds,
  })
  const active = choice ? period : query
  const data = active.data

  const setDomain = (next: string | null) =>
    setParams(
      (current) => {
        if (next) current.set('domain', next)
        else current.delete('domain')
        return current
      },
      { replace: false },
    )

  // Domains with their number of news in what is on screen (before the domain filter).
  const domainOptions: DomainOption[] = useMemo(() => {
    const items = data ? itemsOf(data) : []
    const unanalyzed = data?.unanalyzed ?? []
    return domainCategories.map((category) => ({
      category,
      count: items.filter((item) => item.categories.includes(category)).length + unanalyzed.filter((item) => item.source_domain === category).length,
    }))
  }, [data])

  const filter =
    editionId === 'latest' && editions.data && editions.data.length > 0 ? (
      <PeriodFilter runs={editions.data} choice={choice} onChange={setChoice} domain={domain} domainOptions={domainOptions} onDomainChange={setDomain} />
    ) : null

  // The filter stays mounted while the news load, so the open calendar and focus survive.
  let content
  if (active.isError) content = <ApiErrorCard error={active.error} onRetry={() => active.refetch()} />
  else if (!data) content = <EditionSkeleton />
  else if (choice)
    content = <PeriodView key={`${choice.kind}-${choice.value}`} period={data as Period} kind={choice.kind} value={choice.value} domain={domain} />
  else
    content = (
      <DomainNote edition={data} domain={domain}>
        <EditionView key={data.id} edition={applyDomain(data, domain)} archived={editionId !== 'latest'} domain={domain} />
      </DomainNote>
    )

  return (
    <div className="space-y-6">
      {filter}
      {content}
    </div>
  )
}

/** Explains what a selected domain hides, and what is left. */
function DomainNote({ edition, domain, children }: { edition: Edition; domain: string | null; children: ReactNode }) {
  const { t } = useLanguage()
  if (!domain) return <>{children}</>
  const empty = itemsOf(edition).every((item) => !item.categories.includes(domain)) && edition.unanalyzed.every((item) => item.source_domain !== domain)
  return (
    <>
      {edition.unanalyzed.length > 0 && <p className="px-1 text-[13.5px] text-muted">{t('filter.domainNote')}</p>}
      {empty ? <p className="px-1 text-muted">{t('filter.domainEmpty')}</p> : children}
    </>
  )
}

function PeriodView({ period, kind, value, domain }: { period: Period; kind: PeriodKind; value: string; domain: string | null }) {
  const { language, t } = useLanguage()
  if (period.edition_count === 0) return <p className="px-1 text-muted">{t('filter.empty')}</p>
  const shown = applyDomain(period, domain)
  return (
    <DomainNote edition={period} domain={domain}>
      <EditionView
        edition={shown}
        archived={false}
        domain={domain}
        period={{
          title: capitalize(formatPeriod(kind, value, language)),
          kicker: t('filter.kicker'),
          summary: translatePlural(language, 'filter.summary', period.edition_count, {
            editions: period.edition_count,
            items: itemsOf(shown).length + shown.unanalyzed.length,
          }),
        }}
      />
    </DomainNote>
  )
}

type PeriodInfo = { title: string; kicker: string; summary: string }

function EditionView({ edition, archived, period, domain }: { edition: Edition; archived: boolean; period?: PeriodInfo; domain: string | null }) {
  const { enabled } = useMotionPreference()
  const groups = useMemo(() => groupByDomain(edition, domain), [edition, domain])
  const editionId = period ? undefined : edition.id
  return (
    <m.div
      variants={listStagger}
      // Animations off: render the final state directly (children inherit it).
      initial={enabled ? 'hidden' : false}
      animate="visible"
      className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px] xl:gap-8"
    >
      <div className="min-w-0 space-y-6">
        <EditionHero edition={edition} archived={archived} title={period?.title} kicker={period?.kicker} domains={groups.length} />
        {period && <p className="px-1 text-[14px] text-muted">{period.summary}</p>}
        <DomainJumpBar groups={groups} />
        {edition.unanalyzed.length > 0 && <UnanalyzedNote />}
        {groups.map((group) => (
          <DomainSection key={group.key} group={group} editionId={editionId} />
        ))}
      </div>
      <EditionSidebar edition={edition} groups={groups} />
    </m.div>
  )
}

function EditionSkeleton() {
  const { t } = useLanguage()
  return (
    <div role="status" aria-live="polite" className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px] xl:gap-8">
      <span className="sr-only">{t('state.loading')}</span>
      <div className="space-y-6">
        <div className="h-52 animate-shimmer rounded-card bg-accent/15" />
        {[0, 1, 2].map((index) => (
          <div key={index} className="h-60 animate-shimmer rounded-card bg-surface/80 shadow-card" />
        ))}
      </div>
      <div className="hidden h-96 animate-shimmer rounded-card bg-surface/50 xl:block" />
    </div>
  )
}
