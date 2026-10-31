import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { History } from 'lucide-react'
import { m } from 'motion/react'
import { useState } from 'react'
import { ConfirmDialog } from '../../design/ConfirmDialog'
import { ApiErrorCard, PageHeader, PageSkeleton } from '../../design/PageState'
import { fetchBackups, fetchSecrets, fetchSettings, restoreBackup, type Backup } from '../../lib/api'
import { capitalize, formatEditionDate, formatTime } from '../../lib/format'
import { useLanguage } from '../../lib/i18n'
import { listStagger, riseIn, useMotionPreference } from '../../lib/motion'
import { RunsSection } from './RunsSection'
import { SectorCard } from './SectorCard'
import { SettingsForm } from './SettingsForm'

export function SettingsPage() {
  const { t } = useLanguage()
  const { enabled } = useMotionPreference()
  const settings = useQuery({ queryKey: ['settings'], queryFn: ({ signal }) => fetchSettings(signal) })
  const secrets = useQuery({ queryKey: ['secrets'], queryFn: ({ signal }) => fetchSecrets(signal) })

  return (
    <m.div variants={listStagger} initial={enabled ? 'hidden' : false} animate="visible" className="space-y-8">
      <PageHeader title={t('settings.title')} subtitle={t('settings.subtitle')} />
      {settings.isPending ? (
        <PageSkeleton blocks={3} />
      ) : settings.isError ? (
        <ApiErrorCard error={settings.error} onRetry={() => settings.refetch()} />
      ) : (
        <>
          <m.div variants={riseIn}>
            <SectorCard />
          </m.div>
          <m.div variants={riseIn}>
            <RunsSection />
          </m.div>
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px] xl:gap-8">
            <m.div variants={riseIn} className="min-w-0">
              <SettingsForm settings={settings.data} secrets={secrets.data} onConflict={() => settings.refetch()} />
            </m.div>
            <m.aside variants={riseIn} className="space-y-6 self-start xl:sticky xl:top-28">
              <BackupsCard />
            </m.aside>
          </div>
        </>
      )}
    </m.div>
  )
}

function BackupsCard() {
  const { language, t } = useLanguage()
  const queryClient = useQueryClient()
  const [restored, setRestored] = useState(false)
  const backups = useQuery({ queryKey: ['settings-backups'], queryFn: ({ signal }) => fetchBackups(signal) })
  const restore = useMutation({
    mutationFn: (backup: Backup) => restoreBackup(backup.name),
    onSuccess: async (settings) => {
      queryClient.setQueryData(['settings'], settings)
      setRestored(true)
      await queryClient.invalidateQueries({ queryKey: ['settings-backups'] })
      await queryClient.invalidateQueries({ queryKey: ['secrets'] })
    },
  })

  return (
    <section aria-labelledby="backups-title" className="glass rounded-card p-6">
      <h2 id="backups-title" className="flex items-center gap-2 text-[15px] font-bold">
        <History size={16} aria-hidden className="text-accent" />
        {t('settings.backups')}
      </h2>
      <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{t('settings.backupsHint')}</p>
      {backups.data && backups.data.length > 0 ? (
        <ul className="mt-4 space-y-1">
          {backups.data.map((backup) => (
            <li key={backup.name} className="flex items-center justify-between gap-3 rounded-control px-3 py-2 text-[14px] hover:bg-surface/70">
              <span>
                <span className="font-medium">{capitalize(formatEditionDate(backup.saved_at, language))}</span>
                <span className="ml-2 text-muted tabular-nums">{formatTime(backup.saved_at, language)}</span>
              </span>
              <ConfirmDialog
                trigger={
                  <button
                    type="button"
                    className="rounded-full px-3 py-1 text-[13px] font-semibold text-accent transition-colors duration-150 hover:bg-accent-soft"
                  >
                    {t('settings.restore')}
                  </button>
                }
                title={t('settings.restoreTitle')}
                description={t('settings.restoreBody')}
                cancel={t('settings.discard')}
                confirm={t('settings.restore')}
                onConfirm={() => restore.mutate(backup)}
              />
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-[13.5px] text-muted">{t('settings.noBackup')}</p>
      )}
      <p role="status" aria-live="polite" className="mt-2 text-[12.5px] text-confirmed">
        {restored ? t('settings.restored') : ''}
      </p>
    </section>
  )
}
