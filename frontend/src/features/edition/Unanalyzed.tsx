import { ArrowUpRight, Clock, FileText, Hourglass } from 'lucide-react'
import { m } from 'motion/react'
import { Link } from 'react-router'
import type { EditionItem } from '../../lib/api'
import { formatItemTime, hostOf, itemPath, sourceName } from '../../lib/format'
import { tierKey, useLanguage } from '../../lib/i18n'
import { listStagger, riseIn } from '../../lib/motion'

/** Said once per edition: what "without AI analysis" means. */
export function UnanalyzedNote() {
  const { t } = useLanguage()
  return (
    <m.p variants={riseIn} className="flex items-start gap-2.5 rounded-control bg-unverified/[0.07] px-4 py-3 text-[13.5px] leading-relaxed text-unverified">
      <Hourglass size={16} className="mt-0.5 shrink-0" aria-hidden />
      {t('unanalyzed.body')}
    </m.p>
  )
}

/**
 * Items the AI did not analyze (AI off or quota gone), inside their domain section. Deliberately
 * plain: original headline, source and link only, no score, summary or reliability badge.
 */
export function UnanalyzedList({ items, editionId, id }: { items: EditionItem[]; editionId?: string; id: string }) {
  const { language, t } = useLanguage()
  return (
    <m.div variants={listStagger} role="region" aria-labelledby={id} className="space-y-3">
      <m.h3 variants={riseIn} id={id} className="flex items-center gap-2 px-1 pt-1 text-[12.5px] font-semibold text-muted">
        <Hourglass size={13} aria-hidden />
        {t('domain.unanalyzed')}
        <span className="tabular-nums text-faint">· {items.length}</span>
      </m.h3>

      <m.ul variants={riseIn} className="divide-y divide-line overflow-hidden rounded-card bg-surface shadow-card ring-1 ring-ink/[0.03]">
        {items.map((item) => (
          <li key={item.id} id={`item-${item.id}`} className="scroll-mt-28 p-5 sm:px-7">
            <p className="flex flex-wrap items-center gap-2 text-[12.5px] text-muted">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-ink/5 px-2.5 py-1 font-semibold text-ink/65 ring-1 ring-inset ring-ink/10">
                <Hourglass size={12} aria-hidden />
                {t('unanalyzed.badge')}
              </span>
              {item.reliability && <span>{t(tierKey(item.reliability.source_tier))}</span>}
            </p>
            <h3 className="mt-2.5 font-serif text-[19px] leading-[1.3] font-medium text-ink sm:text-[20px]">
              <a
                href={item.url}
                target="_blank"
                rel="noreferrer noopener"
                className="decoration-accent/30 decoration-2 underline-offset-4 transition-colors duration-150 hover:text-accent hover:underline"
              >
                {item.title}
              </a>
            </h3>
            <p className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[13px] text-muted">
              <span className="font-semibold text-ink/70">{sourceName(item.source_type)}</span>
              <span className="flex items-center gap-1.5">
                <Clock size={13} aria-hidden />
                <time dateTime={item.published_at}>{formatItemTime(item.published_at, language)}</time>
              </span>
              <a
                href={item.url}
                target="_blank"
                rel="noreferrer noopener"
                aria-label={`${t('item.open')} (${hostOf(item.url)})`}
                className="flex items-center gap-1 transition-colors duration-150 hover:text-accent"
              >
                {hostOf(item.url)}
                <ArrowUpRight size={13} aria-hidden />
              </a>
              <Link
                to={itemPath(item.id, language, editionId)}
                className="ml-auto flex items-center gap-1.5 font-semibold text-ink/70 transition-colors duration-150 hover:text-ink"
              >
                <FileText size={14} aria-hidden />
                {t('item.details')}
              </Link>
            </p>
          </li>
        ))}
      </m.ul>
    </m.div>
  )
}
