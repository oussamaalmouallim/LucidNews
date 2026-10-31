import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ArrowLeft, ArrowRight, Search, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'
import { ReliabilityBadge } from '../../design/ReliabilityBadge'
import { ApiError, fetchSearch, reliabilityLabels, SEARCH_MAX_QUERY, SEARCH_PAGE_SIZE, type SearchHit, type SearchResult } from '../../lib/api'
import { useDomainCategories } from '../../lib/sector'
import { formatEditionDate, formatItemTime, formatScore, itemPath, sourceName } from '../../lib/format'
import { highlight } from '../../lib/highlight'
import { categoryLabel, labelKey, translatePlural, useLanguage, type Language } from '../../lib/i18n'

/** What the address says about the search: `?q=`, `&category=`, `&label=`, `&source=`, `&offset=`. */
export function useSearchState() {
  const [params, setParams] = useSearchParams()
  const q = (params.get('q') ?? '').slice(0, SEARCH_MAX_QUERY)
  const state = {
    q,
    category: params.get('category') ?? undefined,
    label: params.get('label') ?? undefined,
    source: params.get('source') ?? undefined,
    offset: Math.max(0, Number.parseInt(params.get('offset') ?? '0', 10) || 0),
  }
  const update = (changes: Partial<Record<'q' | 'category' | 'label' | 'source' | 'offset', string | undefined>>) =>
    setParams(
      (current) => {
        for (const [key, value] of Object.entries(changes)) {
          if (value) current.set(key, value)
          else current.delete(key)
        }
        // A new search or filter starts again from the first results.
        if (!('offset' in changes)) current.delete('offset')
        return current
      },
      { replace: false },
    )
  return { ...state, update }
}

export type SearchState = ReturnType<typeof useSearchState>

/** The search field. Always shown at the top of the Archive page. */
export function SearchBar({ state }: { state: SearchState }) {
  const { t } = useLanguage()
  const [text, setText] = useState(state.q)
  const [problem, setProblem] = useState<string | null>(null)

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const value = text.trim()
    if (value === '') return clear()
    if (value.length > SEARCH_MAX_QUERY) return setProblem(t('search.tooLong'))
    if (!/[\p{L}\p{N}]{2}/u.test(value)) return setProblem(t('search.tooShort'))
    setProblem(null)
    state.update({ q: value })
  }
  const clear = () => {
    setText('')
    setProblem(null)
    state.update({ q: undefined, category: undefined, label: undefined, source: undefined })
  }

  return (
    <form role="search" aria-label={t('search.title')} onSubmit={submit} noValidate className="glass rounded-card p-4 sm:p-5">
      <div className="flex flex-wrap items-center gap-3">
        <label htmlFor="archive-search" className="sr-only">
          {t('search.title')}
        </label>
        <div className="relative min-w-[14rem] flex-1">
          <Search size={17} aria-hidden className="pointer-events-none absolute top-1/2 left-3.5 -translate-y-1/2 text-faint" />
          <input
            id="archive-search"
            type="search"
            value={text}
            maxLength={SEARCH_MAX_QUERY + 50}
            placeholder={t('search.placeholder')}
            aria-invalid={!!problem}
            aria-describedby={problem ? 'archive-search-problem' : 'archive-search-hint'}
            onChange={(event) => setText(event.target.value)}
            className="w-full rounded-control border border-ink/10 bg-surface py-3 pr-4 pl-10 text-[15px] outline-none transition-shadow duration-150 placeholder:text-faint focus:border-accent/50 focus:ring-3 focus:ring-accent/15 aria-invalid:border-rumor/50"
          />
        </div>
        <button
          type="submit"
          className="flex items-center gap-1.5 rounded-control bg-accent px-5 py-3 text-[14px] font-semibold text-on-fill shadow-accent transition-all duration-150 ease-soft hover:-translate-y-0.5 hover:bg-accent-deep active:translate-y-0"
        >
          {t('search.submit')}
        </button>
        {state.q && (
          <button
            type="button"
            onClick={clear}
            className="flex items-center gap-1.5 rounded-control px-3 py-3 text-[14px] font-semibold text-ink/70 transition-colors duration-150 hover:bg-surface"
          >
            <X size={15} aria-hidden />
            {t('search.clear')}
          </button>
        )}
      </div>
      {problem ? (
        <p id="archive-search-problem" role="alert" className="mt-2 px-1 text-[13px] text-rumor">
          {problem}
        </p>
      ) : (
        <p id="archive-search-hint" className="mt-2 px-1 text-[12.5px] text-muted">
          {t('search.hint')}
        </p>
      )}
    </form>
  )
}

/** Results of the current search, with filters. */
export function SearchResults({ state }: { state: SearchState }) {
  const { language, t } = useLanguage()
  const query = useQuery({
    queryKey: ['search', state.q, state.category, state.label, state.source, state.offset, language],
    queryFn: ({ signal }) => fetchSearch(state, language, signal),
    placeholderData: keepPreviousData,
  })

  if (query.isPending)
    return (
      <p role="status" className="px-1 text-muted">
        {t('state.loading')}
      </p>
    )
  if (query.isError) {
    const status = query.error instanceof ApiError ? query.error.status : 0
    return (
      <p role="alert" className="rounded-card bg-surface p-6 text-[14px] text-rumor shadow-card">
        {status === 503 ? t('search.unavailable') : status === 400 ? t('search.tooShort') : t('search.error')}
      </p>
    )
  }
  const data = query.data
  return (
    <div className="space-y-5" aria-busy={query.isFetching}>
      <Filters state={state} data={data} />
      <p role="status" aria-live="polite" className="px-1 text-[14px] font-semibold">
        {translatePlural(language, 'search.results', data.total, { count: data.total, query: data.query })}
      </p>
      {data.truncated && <p className="px-1 text-[13px] text-unverified">{t('search.truncated')}</p>}
      {data.total === 0 ? (
        <p className="rounded-card bg-surface p-6 text-[14.5px] text-muted shadow-card">{t('search.none', { query: data.query })}</p>
      ) : (
        <>
          <ul className="space-y-3">
            {data.results.map((hit) => (
              <li key={hit.id}>
                <Hit hit={hit} terms={data.terms} language={language} />
              </li>
            ))}
          </ul>
          <Pager data={data} onPage={(offset) => state.update({ offset: offset ? String(offset) : undefined })} />
        </>
      )}
    </div>
  )
}

function Filters({ state, data }: { state: SearchState; data: SearchResult }) {
  const { language, t } = useLanguage()
  const categories = useDomainCategories()
  const field =
    'rounded-control border border-ink/10 bg-surface px-3.5 py-2 text-[14px] font-semibold outline-none transition-shadow duration-150 hover:border-accent/40 focus-visible:ring-3 focus-visible:ring-accent/20'
  const sources = data.facets.sources.some((entry) => entry.source === state.source)
    ? data.facets.sources
    : state.source
      ? [...data.facets.sources, { source: state.source, count: 0 }]
      : data.facets.sources
  const sourceLabel = (key: string) => {
    const [type, ...rest] = key.split('/')
    return rest.length ? `${rest.join('/')} · ${sourceName(type)}` : sourceName(type)
  }
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
      <label className="flex items-center gap-2 text-[13.5px] font-semibold">
        {t('search.filter.domain')}
        <select value={state.category ?? ''} onChange={(event) => state.update({ category: event.target.value || undefined })} className={field}>
          <option value="">{t('search.filter.all')}</option>
          {categories.map((category) => (
            <option key={category} value={category} disabled={!data.facets.categories[category] && category !== state.category}>
              {categoryLabel(language, category)} ({data.facets.categories[category] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <label className="flex items-center gap-2 text-[13.5px] font-semibold">
        {t('search.filter.label')}
        <select value={state.label ?? ''} onChange={(event) => state.update({ label: event.target.value || undefined })} className={field}>
          <option value="">{t('search.filter.all')}</option>
          {reliabilityLabels.map((label) => (
            <option key={label} value={label} disabled={!data.facets.labels[label] && label !== state.label}>
              {t(labelKey(label))} ({data.facets.labels[label] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <label className="flex min-w-0 items-center gap-2 text-[13.5px] font-semibold">
        {t('search.filter.source')}
        <select
          value={state.source ?? ''}
          onChange={(event) => state.update({ source: event.target.value || undefined })}
          className={`${field} min-w-0 max-w-[16rem]`}
        >
          <option value="">{t('search.filter.allSources')}</option>
          {sources.map((entry) => (
            <option key={entry.source} value={entry.source}>
              {sourceLabel(entry.source)} ({entry.count})
            </option>
          ))}
        </select>
      </label>
    </div>
  )
}

function Hit({ hit, terms, language }: { hit: SearchHit; terms: string[]; language: Language }) {
  const { t } = useLanguage()
  return (
    <Link
      to={itemPath(hit.id, language, hit.edition ?? undefined)}
      className="group block rounded-card bg-surface p-5 shadow-card ring-1 ring-ink/[0.03] transition-[box-shadow,translate] duration-300 ease-soft hover:-translate-y-0.5 hover:shadow-card-hover sm:p-6"
    >
      <div className="flex flex-wrap items-center gap-2 text-[12.5px] text-muted">
        {hit.reliability && <ReliabilityBadge label={hit.reliability} />}
        {hit.score !== null && <span className="font-semibold tabular-nums text-ink/70">{formatScore(hit.score)}/10</span>}
        <span>{sourceName(hit.source_type)}</span>
        <span aria-hidden>·</span>
        <time dateTime={hit.published_at}>{formatItemTime(hit.published_at, language)}</time>
      </div>
      <h3 className="mt-2.5 font-serif text-[21px] leading-snug font-medium group-hover:text-accent">{highlight(hit.title, terms)}</h3>
      {hit.summary && <p className="mt-1.5 line-clamp-3 text-[14.5px] leading-relaxed text-ink/80">{highlight(hit.summary, terms)}</p>}
      <div className="mt-3 flex flex-wrap items-center gap-2 text-[12.5px]">
        {hit.categories.map((category) => (
          <span key={category} className="rounded-full bg-accent-soft px-2.5 py-0.5 font-semibold text-accent">
            {categoryLabel(language, category)}
          </span>
        ))}
        <span className="text-muted">
          {hit.unanalyzed
            ? t('search.unanalyzed')
            : hit.edition_at
              ? t('search.published', { date: formatEditionDate(hit.edition_at, language) })
              : t('search.notPublished')}
        </span>
      </div>
    </Link>
  )
}

function Pager({ data, onPage }: { data: SearchResult; onPage: (offset: number) => void }) {
  const { t } = useLanguage()
  if (data.total <= SEARCH_PAGE_SIZE) return null
  const from = data.offset + 1
  const to = Math.min(data.offset + data.results.length, data.total)
  const button = 'flex items-center gap-1.5 rounded-control px-4 py-2.5 text-[14px] font-semibold transition-colors duration-150 disabled:opacity-40'
  return (
    <nav aria-label={t('search.title')} className="flex items-center justify-between gap-3 pt-2">
      <button
        type="button"
        disabled={data.offset === 0}
        onClick={() => onPage(Math.max(0, data.offset - SEARCH_PAGE_SIZE))}
        className={`${button} bg-surface shadow-card hover:bg-accent-soft`}
      >
        <ArrowLeft size={15} aria-hidden />
        {t('search.prev')}
      </button>
      <span className="text-[13.5px] text-muted tabular-nums">{t('search.page', { from, to, total: data.total })}</span>
      <button
        type="button"
        disabled={to >= data.total}
        onClick={() => onPage(data.offset + SEARCH_PAGE_SIZE)}
        className={`${button} bg-surface shadow-card hover:bg-accent-soft`}
      >
        {t('search.next')}
        <ArrowRight size={15} aria-hidden />
      </button>
    </nav>
  )
}
