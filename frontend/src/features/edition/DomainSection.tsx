import { m } from 'motion/react'
import { translatePlural, useLanguage } from '../../lib/i18n'
import { listStagger, riseIn } from '../../lib/motion'
import { domainIcons, domainTitle, type DomainGroup } from './domains'
import { ItemCard } from './ItemCard'
import { UnanalyzedList } from './Unanalyzed'

/** One domain of the edition: its analyzed news as cards, then the unanalyzed ones, plain. */
export function DomainSection({ group, editionId, brief = false }: { group: DomainGroup; editionId?: string; brief?: boolean }) {
  const { language } = useLanguage()
  const Icon = domainIcons[group.key]
  const total = group.items.length + group.unanalyzed.length
  const confirmed = group.items.filter((item) => item.reliability?.label === 'confirmed').length
  return (
    <m.section variants={listStagger} id={`domain-${group.key}`} aria-labelledby={`domain-heading-${group.key}`} className="scroll-mt-28 space-y-4 pt-4">
      <m.header variants={riseIn} className="flex items-center gap-3.5 px-1">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-[14px] bg-accent-soft text-accent ring-1 ring-inset ring-accent/10">
          <Icon size={20} strokeWidth={2} aria-hidden />
        </span>
        <div className="min-w-0">
          <h2 id={`domain-heading-${group.key}`} className="truncate text-[20px] leading-tight font-bold tracking-[-0.015em] text-ink">
            {domainTitle(language, group.key)}
          </h2>
          <p className="mt-0.5 text-[13px] text-muted">
            <span className="tabular-nums">{translatePlural(language, 'domain.count', total, { count: total })}</span>
            {confirmed > 0 && <span className="text-confirmed"> · {translatePlural(language, 'domain.confirmed', confirmed, { count: confirmed })}</span>}
          </p>
        </div>
        <span aria-hidden className="ml-2 hidden h-px flex-1 bg-gradient-to-r from-ink/15 to-ink/0 sm:block" />
      </m.header>
      {group.items.map((item) => (
        <ItemCard key={item.id} item={item} editionId={editionId} brief={brief} />
      ))}
      {group.unanalyzed.length > 0 && <UnanalyzedList items={group.unanalyzed} editionId={editionId} id={`domain-unanalyzed-${group.key}`} />}
    </m.section>
  )
}

/** Phones and tablets (the side index sits at the end there): one tap to each domain. */
export function DomainJumpBar({ groups }: { groups: DomainGroup[] }) {
  const { language, t } = useLanguage()
  if (groups.length < 2) return null
  return (
    <m.nav variants={riseIn} aria-label={t('domain.jump')} className="-mx-1 overflow-x-auto px-1 pb-1 [scrollbar-width:none] xl:hidden">
      <ul className="flex w-max gap-2">
        {groups.map((group) => {
          const Icon = domainIcons[group.key]
          return (
            <li key={group.key}>
              <a
                href={`#domain-${group.key}`}
                className="flex items-center gap-2 rounded-full bg-surface py-1.5 pr-1.5 pl-3 text-[13px] font-semibold text-ink/80 shadow-card ring-1 ring-ink/[0.04] transition-colors duration-150 hover:text-accent"
              >
                <Icon size={14} aria-hidden className="text-accent" />
                {domainTitle(language, group.key)}
                <span className="grid h-5 min-w-5 place-items-center rounded-full bg-accent-soft px-1.5 text-[11.5px] font-bold text-accent tabular-nums">
                  {group.items.length + group.unanalyzed.length}
                </span>
              </a>
            </li>
          )
        })}
      </ul>
    </m.nav>
  )
}
