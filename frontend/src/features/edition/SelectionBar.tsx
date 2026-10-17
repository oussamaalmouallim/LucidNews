import { ArrowRight, SlidersHorizontal, Sparkles } from 'lucide-react'
import { m } from 'motion/react'
import { Link } from 'react-router'
import { Segmented } from '../../design/PageState'
import type { PreferencesState } from '../../lib/api'
import { categoryLabel, useLanguage, type Language, type MessageKey } from '../../lib/i18n'
import { riseIn } from '../../lib/motion'

const SHOWN_DOMAINS = 3

/** What "My selection" keeps, in a few words: the domains, the threshold, the trust level. */
export function selectionSummary(
  state: PreferencesState,
  language: Language,
  t: (key: MessageKey, params?: Record<string, string | number>) => string,
): string[] {
  const { domains, min_importance, include_unconfirmed } = state.preferences
  const parts: string[] = []
  if (domains.length) {
    const names = domains.slice(0, SHOWN_DOMAINS).map((domain) => categoryLabel(language, domain))
    parts.push(domains.length > SHOWN_DOMAINS ? `${names.join(', ')} +${domains.length - SHOWN_DOMAINS}` : names.join(', '))
  }
  if (min_importance) parts.push(t(`selection.importance.${min_importance}` as MessageKey))
  if (!include_unconfirmed) parts.push(t('selection.trustedOnly'))
  return parts
}

/**
 * Above the edition, for a signed-in reader: their selection and the switch to the whole edition,
 * or, before they set anything, an invitation to choose their domains.
 */
export function SelectionBar({ state, mine, onChange }: { state: PreferencesState; mine: boolean; onChange: (view: 'mine' | 'all') => void }) {
  const { language, t } = useLanguage()
  const settings = { pathname: '/account', search: `?lang=${language}`, hash: '#my-watch' }

  if (!state.filters) {
    return (
      <m.aside
        variants={riseIn}
        initial="hidden"
        animate="visible"
        aria-label={t('selection.title')}
        className="glass flex flex-wrap items-center gap-4 rounded-card px-5 py-4 sm:px-6"
      >
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-[13px] bg-accent-soft text-accent ring-1 ring-inset ring-accent/10">
          <Sparkles size={18} aria-hidden />
        </span>
        <p className="min-w-0 flex-1 text-[14px] leading-snug text-muted">
          <span className="font-semibold text-ink">{t('selection.inviteTitle')}</span> {t('selection.inviteBody')}
        </p>
        <Link
          to={settings}
          className="flex items-center gap-1.5 rounded-full bg-accent px-4 py-2 text-[13.5px] font-semibold text-on-fill shadow-accent transition-all duration-150 ease-soft hover:-translate-y-px hover:bg-accent-deep"
        >
          {t('selection.invite')}
          <ArrowRight size={15} aria-hidden />
        </Link>
      </m.aside>
    )
  }

  const summary = selectionSummary(state, language, t)
  return (
    <m.aside
      variants={riseIn}
      initial="hidden"
      animate="visible"
      aria-label={t('selection.title')}
      className="glass flex flex-col gap-3 rounded-card px-5 py-4 sm:flex-row sm:items-center sm:gap-5 sm:px-6"
    >
      <div className="flex min-w-0 items-center gap-3.5 sm:flex-1">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-[13px] bg-accent text-on-fill shadow-accent">
          <Sparkles size={18} aria-hidden />
        </span>
        <div className="min-w-0">
          <p className="text-[15px] font-bold tracking-[-0.01em]">{t(mine ? 'selection.title' : 'selection.all')}</p>
          <ul className="mt-1 flex flex-wrap gap-1.5" aria-label={t('selection.keeps')}>
            {summary.map((part) => (
              <li
                key={part}
                className={`rounded-full px-2.5 py-0.5 text-[12px] font-medium ring-1 ring-inset ${
                  mine ? 'bg-accent-soft text-accent ring-accent/10' : 'bg-canvas text-muted ring-ink/[0.06] line-through decoration-ink/25'
                }`}
              >
                {part}
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="flex items-center justify-between gap-2 sm:justify-end">
        <Segmented
          id="selection"
          label={t('selection.view')}
          value={mine ? 'mine' : 'all'}
          onChange={onChange}
          options={[
            { value: 'mine', label: t('selection.mine') },
            { value: 'all', label: t('selection.everything') },
          ]}
        />
        <Link
          to={settings}
          aria-label={t('selection.adjust')}
          title={t('selection.adjust')}
          className="grid h-9 w-9 place-items-center rounded-full text-muted ring-1 ring-ink/10 transition-colors duration-150 hover:bg-surface hover:text-accent"
        >
          <SlidersHorizontal size={16} aria-hidden />
        </Link>
      </div>
    </m.aside>
  )
}

/** Nothing in the reader's selection today, while the edition has news: say so, offer the rest. */
export function SelectionEmpty({ onShowAll }: { onShowAll: () => void }) {
  const { t } = useLanguage()
  return (
    <div role="status" className="mx-auto mt-6 max-w-lg rounded-card bg-surface p-8 text-center shadow-card">
      <span className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-accent-soft text-accent">
        <Sparkles size={22} aria-hidden />
      </span>
      <h2 className="mt-4 text-lg font-bold">{t('selection.emptyTitle')}</h2>
      <p className="mt-2 text-sm text-muted">{t('selection.emptyBody')}</p>
      <button type="button" onClick={onShowAll} className="mt-6 rounded-control bg-accent px-5 py-2.5 text-sm font-semibold text-on-fill shadow-accent">
        {t('selection.showAll')}
      </button>
    </div>
  )
}
