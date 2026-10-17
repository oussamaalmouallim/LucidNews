import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, LoaderCircle, Sparkles } from 'lucide-react'
import { useId, useState, type FormEvent } from 'react'
import { ghostButton, hintClass, labelClass, primaryButton } from '../../design/Field'
import { Segmented } from '../../design/PageState'
import { Switch } from '../../design/Switch'
import { domainCategories, fetchReaderPreferences, saveReaderPreferences, type ReaderPreferences } from '../../lib/api'
import { categoryLabel, useLanguage } from '../../lib/i18n'
import { domainIcons } from '../edition/domains'
import { Card } from './Card'

const PREFS_KEY = ['reader-preferences']
const EVERYTHING: ReaderPreferences = { domains: [], min_importance: null, include_unconfirmed: true, detail_level: 'complete' }
type Threshold = 'any' | 'medium' | 'high' | 'critical'

/** "My watch": what the Edition's "My selection" keeps. Saved with the account; nothing is mailed. */
export function WatchCard() {
  const { t } = useLanguage()
  const stored = useQuery({ queryKey: PREFS_KEY, queryFn: ({ signal }) => fetchReaderPreferences(signal) })
  return (
    <Card icon={Sparkles} title={t('watch.title')} anchor="my-watch">
      <p className="-mt-2 mb-6 text-[13.5px] leading-relaxed text-muted">{t('watch.hint')}</p>
      {stored.data ? <WatchForm saved={stored.data.preferences} /> : <div className="h-40 animate-shimmer rounded-[18px] bg-canvas" aria-hidden />}
    </Card>
  )
}

function WatchForm({ saved }: { saved: ReaderPreferences }) {
  const { language, t } = useLanguage()
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<ReaderPreferences>(saved)
  const save = useMutation({ mutationFn: saveReaderPreferences, onSuccess: (state) => queryClient.setQueryData(PREFS_KEY, state) })
  const ids = { domains: useId(), unconfirmed: useId(), unconfirmedHint: useId() }

  const changed = JSON.stringify(draft) !== JSON.stringify(saved)
  const toggleDomain = (domain: string) =>
    setDraft((current) => ({
      ...current,
      // Kept in the taxonomy order, whatever the order of the clicks.
      domains: domainCategories.filter((entry) => (entry === domain ? !current.domains.includes(entry) : current.domains.includes(entry))),
    }))
  const submit = (event: FormEvent) => {
    event.preventDefault()
    save.mutate(draft)
  }

  return (
    <form onSubmit={submit} className="space-y-7">
      <fieldset aria-describedby={ids.domains}>
        <legend className={labelClass}>{t('watch.domains')}</legend>
        <p id={ids.domains} className={hintClass}>
          {t('watch.domainsHint')}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {domainCategories.map((domain) => {
            const Icon = domainIcons[domain]
            const on = draft.domains.includes(domain)
            return (
              <button
                key={domain}
                type="button"
                aria-pressed={on}
                onClick={() => toggleDomain(domain)}
                className={`flex items-center gap-2 rounded-full py-2 pr-3.5 pl-3 text-[13px] font-semibold ring-1 transition-all duration-150 ease-soft active:scale-[0.97] ${
                  on ? 'bg-accent text-on-fill shadow-accent ring-accent' : 'bg-canvas text-ink/75 ring-ink/[0.08] hover:text-ink hover:ring-ink/20'
                }`}
              >
                <Icon size={14} aria-hidden className={on ? '' : 'text-accent'} />
                {categoryLabel(language, domain)}
                {on && <Check size={13} aria-hidden />}
              </button>
            )
          })}
        </div>
      </fieldset>

      <div className="grid gap-6 sm:grid-cols-2">
        <div>
          <p className={labelClass}>{t('watch.importance')}</p>
          <div className="mt-2">
            <Segmented<Threshold>
              id="watch-importance"
              label={t('watch.importance')}
              value={!draft.min_importance || draft.min_importance === 'low' ? 'any' : draft.min_importance}
              onChange={(value) => setDraft((current) => ({ ...current, min_importance: value === 'any' ? null : value }))}
              options={[
                { value: 'any', label: t('watch.importance.any') },
                { value: 'medium', label: t('importance.medium') },
                { value: 'high', label: t('importance.high') },
                { value: 'critical', label: t('importance.critical') },
              ]}
            />
          </div>
        </div>
        <div>
          <p className={labelClass}>{t('watch.detail')}</p>
          <div className="mt-2">
            <Segmented<ReaderPreferences['detail_level']>
              id="watch-detail"
              label={t('watch.detail')}
              value={draft.detail_level}
              onChange={(value) => setDraft((current) => ({ ...current, detail_level: value }))}
              options={[
                { value: 'complete', label: t('watch.detail.complete') },
                { value: 'brief', label: t('watch.detail.brief') },
              ]}
            />
          </div>
          <p className={hintClass}>{t('watch.detailHint')}</p>
        </div>
      </div>

      <div className="flex items-start justify-between gap-4 rounded-[18px] bg-canvas/60 p-4 ring-1 ring-inset ring-ink/[0.05]">
        <div>
          <label htmlFor={ids.unconfirmed} className={labelClass}>
            {t('watch.unconfirmed')}
          </label>
          <p id={ids.unconfirmedHint} className={hintClass}>
            {t('watch.unconfirmedHint')}
          </p>
        </div>
        <Switch
          id={ids.unconfirmed}
          checked={draft.include_unconfirmed}
          describedBy={ids.unconfirmedHint}
          onCheckedChange={(checked) => setDraft((current) => ({ ...current, include_unconfirmed: checked }))}
        />
      </div>

      {save.isError && (
        <p role="alert" className="text-[13.5px] font-medium text-rumor">
          {t('auth.error.generic')}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={!changed || save.isPending} className={`${primaryButton} justify-center`}>
          {save.isPending ? (
            <LoaderCircle size={16} aria-hidden className="animate-spin" />
          ) : !changed && save.isSuccess ? (
            <Check size={16} aria-hidden />
          ) : null}
          {!changed && save.isSuccess ? t('watch.saved') : t('watch.save')}
        </button>
        <button type="button" className={ghostButton} disabled={JSON.stringify(draft) === JSON.stringify(EVERYTHING)} onClick={() => setDraft(EVERYTHING)}>
          {t('watch.reset')}
        </button>
      </div>
    </form>
  )
}
