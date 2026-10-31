import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, Compass } from 'lucide-react'
import { useState } from 'react'
import { ConfirmDialog } from '../../design/ConfirmDialog'
import { ApiError, changeSector, type SectorState } from '../../lib/api'
import { registerCategoryLabels, useLanguage, type Language } from '../../lib/i18n'
import { SECTOR_KEY, useSector } from '../../lib/sector'

const name = (labels: Record<string, string>, language: Language) => labels[language] ?? labels.en ?? ''

/** Settings: the sector this installation watches. Changing it rewrites the configuration
 * (a backup is kept) and every screen then shows the new sector's domains. */
export function SectorCard() {
  const { language, t } = useLanguage()
  const queryClient = useQueryClient()
  const sector = useSector()
  const [done, setDone] = useState<string | null>(null)
  const change = useMutation({
    mutationFn: changeSector,
    onSuccess: async (state: SectorState) => {
      registerCategoryLabels(state.sector.categories)
      queryClient.setQueryData(SECTOR_KEY, state)
      setDone(name(state.sector.labels, language))
      // Settings, coverage, sources and editions all depend on the sector.
      await queryClient.invalidateQueries({ predicate: (query) => query.queryKey[0] !== SECTOR_KEY[0] })
    },
  })
  const error = change.error instanceof ApiError ? change.error.message : change.error ? String(change.error) : null

  return (
    <section aria-labelledby="sector-title" className="glass rounded-card p-6">
      <h2 id="sector-title" className="flex items-center gap-2 text-[15px] font-bold">
        <Compass size={16} aria-hidden className="text-accent" />
        {t('sector.title')}
      </h2>
      <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{t('sector.hint')}</p>
      {sector.data ? (
        <ul className="mt-4 grid gap-3 sm:grid-cols-2">
          {sector.data.sectors.map((entry) => {
            const current = entry.id === sector.data.sector.id
            return (
              <li
                key={entry.id}
                className={`rounded-[18px] p-4 ring-1 ring-inset ${current ? 'bg-accent-soft ring-accent/25' : 'bg-surface/70 ring-ink/[0.06]'}`}
              >
                <p className="flex items-center justify-between gap-3 text-[14.5px] font-semibold">
                  {name(entry.labels, language)}
                  {current && (
                    <span className="flex items-center gap-1 rounded-full bg-accent px-2.5 py-0.5 text-[11.5px] font-semibold text-on-fill">
                      <Check size={12} aria-hidden />
                      {t('sector.current')}
                    </span>
                  )}
                </p>
                <p className="mt-1 text-[13px] leading-relaxed text-muted">{name(entry.descriptions, language)}</p>
                {!current && (
                  <ConfirmDialog
                    trigger={
                      <button
                        type="button"
                        disabled={change.isPending}
                        className="mt-3 rounded-full px-3 py-1 text-[13px] font-semibold text-accent transition-colors duration-150 hover:bg-accent-soft disabled:opacity-50"
                      >
                        {t('sector.choose')}
                      </button>
                    }
                    title={t('sector.confirmTitle', { name: name(entry.labels, language) })}
                    description={t('sector.confirmBody')}
                    cancel={t('sector.cancel')}
                    confirm={t('sector.confirm')}
                    onConfirm={() => change.mutate(entry.id)}
                  />
                )}
              </li>
            )
          })}
        </ul>
      ) : (
        <div className="mt-4 h-20 animate-shimmer rounded-[18px] bg-canvas" aria-hidden />
      )}
      {sector.data && sector.data.sectors.length === 1 && <p className="mt-3 text-[12.5px] text-muted">{t('sector.only')}</p>}
      <p role="status" aria-live="polite" className="mt-2 text-[12.5px]">
        {error ? (
          <span className="text-rumor">{t('sector.failed', { detail: error })}</span>
        ) : done ? (
          <span className="text-confirmed">{t('sector.changed', { name: done })}</span>
        ) : (
          ''
        )}
      </p>
    </section>
  )
}
