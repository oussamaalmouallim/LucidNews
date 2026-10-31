import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Ban, CircleDashed, Eye, Layers, PauseCircle, Plus, Settings2, type LucideIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Segmented } from '../../design/PageState'
import { Switch } from '../../design/Switch'
import {
  ApiError,
  fetchSourceDomains,
  updateSource,
  type SourceDomain,
  type HealthStatus,
  type SourceConfig,
  type SourceEntry,
  type SourceHealth,
} from '../../lib/api'
import { useDomainCategories } from '../../lib/sector'
import { formatItemTime } from '../../lib/format'
import { categoryLabel, translatePlural, useLanguage, type MessageKey } from '../../lib/i18n'
import { HealthBadge, QualityScore, SourceDetail } from './SourceBits'
import { SourcePanel, type PanelTarget } from './SourcePanel'
import { kindKey } from './sourceFields'

type State = HealthStatus | 'off' | 'paused' | 'new' | 'untracked' | 'readonly'
type Filter = 'all' | 'active' | 'off' | 'attention'
type GroupBy = 'domain' | 'type'

/** One block of the list: a domain or a source type, with its sources (and Reddit/Telegram switches). */
type Section = { id: string; title: string; entries: SourceEntry[]; switchEntry?: SourceEntry; switches?: SourceEntry[] }

const GROUPS: { id: string; title: MessageKey; kinds: string[]; switchKey?: string }[] = [
  { id: 'rss', title: 'sources.group.rss', kinds: ['rss'] },
  { id: 'github', title: 'sources.group.github', kinds: ['github_repo', 'github_user'] },
  { id: 'reddit', title: 'sources.group.reddit', kinds: ['reddit_subreddit', 'reddit_user'], switchKey: 'reddit' },
  { id: 'telegram', title: 'sources.group.telegram', kinds: ['telegram_channel'], switchKey: 'telegram' },
  { id: 'builtin', title: 'sources.group.builtin', kinds: ['hackernews', 'ossinsight', 'gdelt', 'google_news'] },
  { id: 'x', title: 'sources.group.x', kinds: ['twitter'] },
]

// States without a health report: icon + label, never colour alone.
const STATE_STYLES: Record<Exclude<State, HealthStatus>, { icon: LucideIcon; label: MessageKey; tone: string }> = {
  off: { icon: Ban, label: 'sources.state.off', tone: 'bg-ink/[0.06] text-ink/60 ring-ink/10' },
  paused: { icon: PauseCircle, label: 'sources.state.paused', tone: 'bg-ink/[0.06] text-ink/60 ring-ink/10' },
  new: { icon: CircleDashed, label: 'sources.state.new', tone: 'bg-reliable/10 text-reliable ring-reliable/20' },
  untracked: { icon: Layers, label: 'sources.state.untracked', tone: 'bg-ink/[0.06] text-ink/60 ring-ink/10' },
  readonly: { icon: Eye, label: 'sources.state.readonly', tone: 'bg-ink/[0.06] text-ink/60 ring-ink/10' },
}
const ATTENTION: State[] = ['dead', 'failing', 'silent', 'noisy']

/** The state shown for a source: only what the configuration and past runs say. */
export function sourceState(entry: SourceEntry, health?: SourceHealth): State {
  if (entry.readonly) return 'readonly'
  if (!entry.enabled) return 'off'
  if (entry.group_enabled === false) return 'paused'
  if (!entry.tracked) return 'untracked'
  return health?.status ?? 'new'
}

function matches(filter: Filter, state: State) {
  if (filter === 'all') return true
  if (filter === 'off') return state === 'off' || state === 'paused'
  if (filter === 'attention') return ATTENTION.includes(state)
  return !['off', 'paused', 'readonly'].includes(state)
}

export function SourceManager({ config, health, onReload }: { config: SourceConfig; health: SourceHealth[]; onReload: () => void }) {
  const { language, t } = useLanguage()
  const categories = useDomainCategories()
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState<Filter>('all')
  const [groupBy, setGroupBy] = useState<GroupBy>('domain')
  // The domain of each source: from the archive, else the catalog. Absent when it cannot be read.
  const domainsQuery = useQuery({ queryKey: ['source-domains'], queryFn: ({ signal }) => fetchSourceDomains(signal), retry: false })
  const domains = domainsQuery.data
  const [panel, setPanel] = useState<PanelTarget | null>(null)
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null)
  const byKey = new Map(health.map((entry) => [entry.source, entry]))

  useEffect(() => {
    if (!notice || notice.error) return
    const timer = window.setTimeout(() => setNotice(null), 4000)
    return () => window.clearTimeout(timer)
  }, [notice])

  const applied = async (next: SourceConfig, message: string) => {
    queryClient.setQueryData(['source-config'], next)
    setPanel(null)
    setNotice({ text: message })
    await queryClient.invalidateQueries({ queryKey: ['sources'] })
  }

  const toggle = useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) => updateSource(config.version, key, { enabled }),
    onSuccess: (next) => applied(next, t('sources.saved')),
    onError: (error) => {
      const conflict = error instanceof ApiError && error.status === 409
      setNotice({ text: conflict ? t('sources.conflict') : t('error.save'), error: true })
      if (conflict) onReload()
    },
  })

  const entries = config.sources.filter((entry) => !entry.group)
  const states = new Map(entries.map((entry) => [entry.key, sourceState(entry, byKey.get(entry.key))]))
  const count = (value: Filter) => entries.filter((entry) => matches(value, states.get(entry.key)!)).length
  const filters: { value: Filter; label: string }[] = [
    { value: 'all', label: `${t('sources.filterAll')} · ${count('all')}` },
    { value: 'active', label: `${t('sources.filter.active')} · ${count('active')}` },
    { value: 'off', label: `${t('sources.filter.off')} · ${count('off')}` },
    { value: 'attention', label: `${t('sources.filter.attention')} · ${count('attention')}` },
  ]

  const switchEntries = config.sources.filter((entry) => entry.group)
  const typeSections: Section[] = GROUPS.map((group) => ({
    id: group.id,
    title: t(group.title),
    entries: entries.filter((entry) => group.kinds.includes(entry.kind)),
    switchEntry: group.switchKey ? config.sources.find((entry) => entry.key === group.switchKey) : undefined,
  }))
  // A domain outside the sector (news collected under a former sector) counts as unknown here.
  const domainOf = (entry: SourceEntry) => {
    const category = domains?.[entry.key]?.category ?? null
    return category !== null && categories.includes(category) ? category : null
  }
  const domainSections: Section[] = [
    ...categories.map((category) => ({
      id: `domain-${category}`,
      title: categoryLabel(language, category),
      entries: entries.filter((entry) => domainOf(entry) === category),
    })),
    { id: 'domain-unknown', title: t('sources.domain.unknown'), entries: entries.filter((entry) => domainOf(entry) === null) },
    ...(switchEntries.length > 0 ? [{ id: 'domain-switches', title: t('sources.domainSwitches'), entries: [], switches: switchEntries }] : []),
  ]
  // Without domain data (API unreadable) the type view is the only honest grouping.
  const sections = groupBy === 'domain' && domains ? domainSections : typeSections

  return (
    <section aria-labelledby="sources-manage" className="rounded-card bg-surface p-5 shadow-card sm:p-7">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 id="sources-manage" className="text-[17px] font-bold">
            {t('sources.manage.title')}
          </h2>
          <p className="mt-1 text-[13.5px] text-muted">{t('sources.manage.hint')}</p>
        </div>
        <button
          type="button"
          onClick={() => setPanel({ mode: 'add' })}
          className="flex items-center gap-1.5 rounded-control bg-accent px-4 py-2.5 text-[14px] font-semibold text-on-fill shadow-accent transition-all duration-150 ease-soft hover:-translate-y-px hover:bg-accent-deep"
        >
          <Plus size={16} aria-hidden />
          {t('sources.add')}
        </button>
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Segmented id="manage-filter" label={t('sources.col.status')} value={filter} onChange={setFilter} options={filters} />
        {domains && (
          <span className="flex items-center gap-2">
            <span className="text-[13px] font-semibold text-muted">{t('sources.groupBy')}</span>
            <Segmented<GroupBy>
              id="manage-group-by"
              label={t('sources.groupBy')}
              value={groupBy}
              onChange={setGroupBy}
              options={[
                { value: 'domain', label: t('sources.groupBy.domain') },
                { value: 'type', label: t('sources.groupBy.type') },
              ]}
            />
          </span>
        )}
        <p role="status" aria-live="polite" className={`text-[13px] font-medium ${notice?.error ? 'text-rumor' : 'text-confirmed'}`}>
          {notice?.text ?? ''}
        </p>
      </div>

      <div className="mt-6 space-y-8">
        {sections.map((section) => {
          const shown = section.entries.filter((entry) => matches(filter, states.get(entry.key)!))
          const total = section.entries.length
          const hasSwitches = !!section.switchEntry || !!section.switches?.length
          if (shown.length === 0 && (filter !== 'all' || (total === 0 && !hasSwitches))) return null
          return (
            <section key={section.id} aria-labelledby={`group-${section.id}`}>
              <div className="flex flex-wrap items-center gap-3 border-b border-line pb-2.5">
                <h3 id={`group-${section.id}`} className="text-[14px] font-bold">
                  {section.title}
                  {!section.switches && <span className="ml-2 font-medium text-faint tabular-nums">{total}</span>}
                </h3>
                {section.switchEntry && (
                  <GroupSwitch
                    entry={section.switchEntry}
                    busy={toggle.isPending}
                    onToggle={(enabled) => toggle.mutate({ key: section.switchEntry!.key, enabled })}
                    onManage={() => setPanel({ mode: 'edit', entry: section.switchEntry! })}
                  />
                )}
              </div>
              {section.switches?.map((entry) => (
                <div key={entry.key} className="flex flex-wrap items-center gap-3 border-b border-line/70 py-3">
                  <span className="font-semibold">{entry.label}</span>
                  <GroupSwitch
                    entry={entry}
                    busy={toggle.isPending}
                    onToggle={(enabled) => toggle.mutate({ key: entry.key, enabled })}
                    onManage={() => setPanel({ mode: 'edit', entry })}
                  />
                </div>
              ))}
              {shown.length === 0 && !hasSwitches ? (
                <p className="py-3 text-[13.5px] text-muted">{t('sources.group.empty')}</p>
              ) : (
                <ul className="divide-y divide-line/70">
                  {shown.map((entry) => (
                    <SourceRow
                      key={entry.key}
                      entry={entry}
                      state={states.get(entry.key)!}
                      health={byKey.get(entry.key)}
                      domain={domains?.[entry.key]}
                      domainsKnown={!!domains}
                      busy={toggle.isPending}
                      onToggle={(enabled) => toggle.mutate({ key: entry.key, enabled })}
                      onManage={() => setPanel({ mode: 'edit', entry })}
                    />
                  ))}
                </ul>
              )}
            </section>
          )
        })}
      </div>

      {panel && (
        <SourcePanel
          target={panel}
          config={config}
          health={panel.mode === 'edit' ? byKey.get(panel.entry.key) : undefined}
          onClose={() => setPanel(null)}
          onSaved={applied}
          onConflict={() => {
            setPanel(null)
            onReload()
          }}
        />
      )}
    </section>
  )
}

function SourceRow({
  entry,
  state,
  health,
  domain,
  domainsKnown,
  busy,
  onToggle,
  onManage,
}: {
  entry: SourceEntry
  state: State
  health?: SourceHealth
  domain?: SourceDomain
  domainsKnown: boolean
  busy: boolean
  onToggle: (enabled: boolean) => void
  onManage: () => void
}) {
  const { language, t } = useLanguage()
  const group = entry.kind.startsWith('reddit') ? 'Reddit' : 'Telegram'
  const detail = entry.readonly
    ? entry.summary
      ? t('sources.x.summary', { mode: entry.summary.mode, users: entry.summary.users, keywords: entry.summary.keywords })
      : t('sources.x.none')
    : null

  return (
    <li className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 py-3.5 md:grid-cols-[3rem_minmax(0,1.5fr)_10.5rem_minmax(0,2fr)_6rem]">
      {entry.readonly ? (
        <span className="w-12" aria-hidden />
      ) : (
        <Switch checked={entry.enabled} disabled={busy} label={t('sources.toggle', { name: entry.label })} onCheckedChange={onToggle} />
      )}

      <div className="min-w-0">
        <p className="truncate font-semibold" title={entry.label}>
          {entry.label}
        </p>
        <p className="truncate text-[12px] text-faint">{t(kindKey(entry.kind))}</p>
        {domainsKnown && !entry.readonly && <DomainLine domain={domain} />}
      </div>

      <div className="col-start-3 row-start-1 md:col-start-auto md:row-start-auto">
        {entry.readonly ? null : (
          <button
            type="button"
            onClick={onManage}
            aria-label={`${t('sources.manage')} · ${entry.label}`}
            className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] font-semibold text-accent transition-colors duration-150 hover:bg-accent-soft md:hidden"
          >
            <Settings2 size={14} aria-hidden />
            {t('sources.manage')}
          </button>
        )}
        <span className="hidden md:inline-flex">
          <StateBadge state={state} />
        </span>
      </div>

      <div className="col-span-2 col-start-2 min-w-0 text-[13px] text-muted md:col-span-1 md:col-start-auto">
        <span className="md:hidden">
          <StateBadge state={state} />
        </span>
        {state === 'paused' && <p className="mt-1 md:mt-0">{t('sources.state.pausedHint', { group })}</p>}
        {detail && <p className="mt-1 md:mt-0">{detail}</p>}
        {entry.readonly && <p className="mt-0.5 text-[12.5px] text-faint">{t('sources.x.hint')}</p>}
        {health && state !== 'off' && state !== 'paused' && (
          <>
            <p className="mt-1 tabular-nums md:mt-0">
              {t('sources.col.runs')} {health.runs} · {t('sources.col.failures')} {health.failures} · {t('sources.col.selected')} {health.selected}
              {health.quality && (
                <>
                  {' '}
                  · {t('sources.col.quality')} <QualityScore source={health} />
                </>
              )}
            </p>
            <p className="text-[12.5px]">
              {t('sources.col.lastSuccess')} : {health.last_success_at ? formatItemTime(health.last_success_at, language) : t('sources.never')}
            </p>
            <p className="text-[12.5px]">
              <SourceDetail source={health} />
            </p>
          </>
        )}
      </div>

      <div className="hidden justify-end md:flex">{!entry.readonly && <ManageButton label={entry.label} onClick={onManage} />}</div>
    </li>
  )
}

/** The domain of a source, and where that comes from. Never shown as certain when it is not. */
function DomainLine({ domain }: { domain?: SourceDomain }) {
  const { language, t } = useLanguage()
  if (!domain || domain.category === null) {
    return (
      <p className="mt-1 text-[12px] text-faint">
        {t('sources.domain')} : {t('sources.domain.unknownShort')}
      </p>
    )
  }
  const total = domain.categories.reduce((sum, entry) => sum + entry.items, 0)
  const others = domain.categories.slice(1).map((entry) => categoryLabel(language, entry.category))
  return (
    <p className="mt-1 text-[12px] text-muted">
      {t('sources.domain')} :{' '}
      <span className="rounded-full bg-accent-soft px-2 py-0.5 font-semibold text-accent">{categoryLabel(language, domain.category)}</span>{' '}
      <span className="text-faint">
        {domain.origin === 'archive' ? translatePlural(language, 'sources.domain.archive', total, { count: total }) : t('sources.domain.catalog')}
        {others.length > 0 && ` · ${t('sources.domain.others', { list: others.join(', ') })}`}
      </span>
    </p>
  )
}

function GroupSwitch({ entry, busy, onToggle, onManage }: { entry: SourceEntry; busy: boolean; onToggle: (enabled: boolean) => void; onManage: () => void }) {
  const { t } = useLanguage()
  return (
    <div className="ml-auto flex items-center gap-2">
      <span className="text-[13px] text-muted">{t('sources.groupSwitch', { group: entry.label })}</span>
      <Switch checked={entry.enabled} disabled={busy} label={t('sources.groupSwitch', { group: entry.label })} onCheckedChange={onToggle} />
      {Object.keys(entry.values).length > 0 && <ManageButton label={entry.label} onClick={onManage} />}
    </div>
  )
}

function ManageButton({ label, onClick }: { label: string; onClick: () => void }) {
  const { t } = useLanguage()
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`${t('sources.manage')} · ${label}`}
      className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] font-semibold text-accent transition-colors duration-150 hover:bg-accent-soft"
    >
      <Settings2 size={14} aria-hidden />
      {t('sources.manage')}
    </button>
  )
}

function StateBadge({ state }: { state: State }) {
  const { t } = useLanguage()
  if (!(state in STATE_STYLES)) return <HealthBadge status={state as HealthStatus} />
  const { icon: Icon, label, tone } = STATE_STYLES[state as keyof typeof STATE_STYLES]
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12.5px] font-semibold whitespace-nowrap ring-1 ring-inset ${tone}`}>
      <Icon size={14} strokeWidth={2.25} aria-hidden />
      {t(label)}
    </span>
  )
}
