import { CalendarDays, Hourglass } from 'lucide-react'
import { m } from 'motion/react'
import { CountUp } from '../../design/CountUp'
import type { Edition } from '../../lib/api'
import { capitalize, formatEditionDate } from '../../lib/format'
import { isLanguage, translatePlural, useLanguage } from '../../lib/i18n'
import { riseIn } from '../../lib/motion'

/** The edition banner: accent card with soft circles, date and run figures. */
export function EditionHero({
  edition,
  archived = false,
  kicker,
  title,
  domains,
}: {
  edition: Edition
  archived?: boolean
  /** Replaces the "Daily edition" label (a period shows its own). */
  kicker?: string
  /** Replaces the date of the edition (a period shows its range). */
  title?: string
  /** Number of domain sections on screen. */
  domains: number
}) {
  const { language, t } = useLanguage()
  const unanalyzed = edition.unanalyzed.length
  const stats = [
    // When the AI stopped early, not every collected item was analyzed. Not shown for a
    // period: the same item is collected by several editions, so the sum would overcount.
    ...(title === undefined ? [{ value: edition.fetched_count, label: t(edition.ai_limit ? 'edition.collected' : 'edition.analyzed') }] : []),
    { value: edition.selected_count - unanalyzed, label: t('edition.selected') },
    { value: domains, label: t('edition.domains') },
    ...(unanalyzed > 0 ? [{ value: unanalyzed, label: t('edition.unanalyzed') }] : []),
  ]

  return (
    <m.section
      variants={riseIn}
      className="relative isolate overflow-hidden rounded-card bg-gradient-to-br from-accent to-accent-deep px-6 py-8 text-on-fill shadow-[0_30px_70px_-30px_rgb(76_63_216/0.6)] sm:px-10 sm:py-10"
    >
      <span aria-hidden className="absolute -right-24 -top-28 -z-10 h-80 w-80 rounded-full bg-on-fill/[0.07]" />
      <span aria-hidden className="absolute -bottom-36 right-40 -z-10 h-72 w-72 rounded-full bg-on-fill/[0.05]" />
      <span aria-hidden className="absolute -left-20 bottom-[-9rem] -z-10 h-64 w-64 rounded-full bg-on-fill/[0.04]" />

      <p className="flex items-center gap-2 text-sm font-semibold text-on-fill/75">
        <CalendarDays size={16} aria-hidden />
        {kicker ?? t(archived ? 'edition.archived' : 'edition.kicker')}
      </p>
      <h1 className="mt-3 font-serif text-[34px] leading-[1.1] font-medium tracking-[-0.01em] sm:text-[44px]">
        {title ?? capitalize(formatEditionDate(edition.started_at, isLanguage(edition.language) ? edition.language : language))}
      </h1>

      {edition.ai_limit && (
        <p className="mt-5 flex max-w-2xl items-start gap-2.5 rounded-2xl border border-on-fill/20 bg-on-fill/10 px-4 py-3 text-[14px] leading-relaxed backdrop-blur-sm">
          <Hourglass size={16} className="mt-0.5 shrink-0" aria-hidden />
          <span>
            {t(`quota.${edition.ai_limit}`)}
            {unanalyzed > 0 && <> {translatePlural(language, 'quota.hero', unanalyzed, { count: unanalyzed })}</>}
          </span>
        </p>
      )}

      <dl className="mt-8 flex flex-wrap gap-3">
        {stats.map(({ value, label }) => (
          <div key={label} className="flex items-baseline gap-2 rounded-2xl border border-on-fill/15 bg-on-fill/10 px-4 py-2.5 backdrop-blur-sm">
            <dt className="sr-only">{label}</dt>
            <dd className="text-2xl font-bold">
              <CountUp value={value} />
            </dd>
            <span aria-hidden className="text-sm text-on-fill/75">
              {label}
            </span>
          </div>
        ))}
      </dl>
    </m.section>
  )
}
