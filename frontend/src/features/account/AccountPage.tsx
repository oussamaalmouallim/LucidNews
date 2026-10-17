import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Download, KeyRound, LoaderCircle, LogOut, Monitor, ShieldAlert, Smartphone, Trash2, UserRound, type LucideIcon } from 'lucide-react'
import { AlertDialog } from 'radix-ui'
import { useState, type FormEvent, type ReactNode } from 'react'
import { Navigate } from 'react-router'
import { Avatar } from '../../app/UserMenu'
import { Field, ghostButton, inputClass, primaryButton } from '../../design/Field'
import { ApiErrorCard, PageHeader, PageSkeleton } from '../../design/PageState'
import {
  ApiError,
  changePassword,
  closeOtherSessions,
  closeSession,
  deleteAccount,
  exportAccount,
  fetchAccount,
  renameAccount,
  type Account,
  type AccountSession,
} from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { formatItemTime, formatShortDate } from '../../lib/format'
import { useLanguage, type MessageKey } from '../../lib/i18n'
import { MAX_PASSWORD, MIN_PASSWORD, StrengthMeter } from '../auth/strength'

const ACCOUNT_KEY = ['account']

/** The message for an API refusal: its stable code when the app knows it, else a generic one. */
function useErrorText() {
  const { t } = useLanguage()
  return (error: unknown) => {
    const key = `auth.error.${error instanceof ApiError && error.code ? error.code : 'generic'}` as MessageKey
    return t(key) === key ? t('auth.error.generic') : t(key)
  }
}

/** The signed-in person's own account: profile, password, sessions, data. No e-mail involved. */
export function AccountPage() {
  const { t } = useLanguage()
  const auth = useAuth()
  const account = useQuery({ queryKey: ACCOUNT_KEY, queryFn: ({ signal }) => fetchAccount(signal), enabled: Boolean(auth.session?.user) })

  if (!auth.session?.enabled) return <Navigate to="/" replace />
  if (account.isError) return <ApiErrorCard error={account.error} onRetry={() => account.refetch()} />
  if (!account.data) return <PageSkeleton blocks={3} />

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader title={t('account.title')} subtitle={t('account.subtitle')} />
      <ProfileCard account={account.data} />
      <PasswordCard account={account.data} />
      <SessionsCard account={account.data} />
      <DataCard account={account.data} />
    </div>
  )
}

function Card({
  icon: Icon,
  title,
  aside,
  tone = 'accent',
  children,
}: {
  icon: LucideIcon
  title: string
  aside?: ReactNode
  tone?: 'accent' | 'danger'
  children: ReactNode
}) {
  const headingId = `account-${title.toLowerCase().replace(/\W+/g, '-')}`
  return (
    <section aria-labelledby={headingId} className="rounded-card bg-surface p-6 shadow-card ring-1 ring-ink/[0.03] sm:p-8">
      <header className="mb-5 flex flex-wrap items-center gap-3">
        <span
          className={`grid h-10 w-10 shrink-0 place-items-center rounded-[13px] ring-1 ring-inset ${
            tone === 'danger' ? 'bg-rumor/10 text-rumor ring-rumor/15' : 'bg-accent-soft text-accent ring-accent/10'
          }`}
        >
          <Icon size={19} aria-hidden />
        </span>
        <h2 id={headingId} className="flex-1 text-[18px] font-bold tracking-[-0.01em]">
          {title}
        </h2>
        {aside}
      </header>
      {children}
    </section>
  )
}

function useAccountMutation<A>(fn: (args: A) => Promise<Account>) {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: fn, onSuccess: (account) => queryClient.setQueryData(ACCOUNT_KEY, account) })
}

function ProfileCard({ account }: { account: Account }) {
  const { t } = useLanguage()
  const errorText = useErrorText()
  const auth = useAuth()
  const { user } = account
  const [name, setName] = useState(user.name)
  const save = useAccountMutation(renameAccount)

  const submit = (event: FormEvent) => {
    event.preventDefault()
    save.mutate(name, {
      // The menu shows the name too.
      onSuccess: (next) => auth.session && auth.accept({ ...auth.session, user: next.user }),
    })
  }
  const methods = [user.has_password && 'password', user.has_google && 'google'].filter(Boolean) as ('password' | 'google')[]

  return (
    <Card icon={UserRound} title={t('account.profile')}>
      <div className="flex items-center gap-4">
        <Avatar user={user} size="h-16 w-16 text-[20px]" />
        <div className="min-w-0">
          <p className="truncate text-[17px] font-bold">{user.name}</p>
          <p className="truncate text-[14px] text-muted">{user.email}</p>
          <p className="mt-2 flex flex-wrap gap-1.5">
            <span className="rounded-full bg-accent-soft px-2.5 py-0.5 text-[12px] font-semibold text-accent">
              {t(user.role === 'admin' ? 'auth.role.admin' : 'auth.role.reader')}
            </span>
            {methods.map((method) => (
              <span key={method} className="rounded-full bg-canvas px-2.5 py-0.5 text-[12px] font-medium text-muted ring-1 ring-inset ring-ink/[0.06]">
                {t(`account.method.${method}`)}
              </span>
            ))}
          </p>
        </div>
      </div>

      <form onSubmit={submit} className="mt-6 grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
        <Field label={t('account.name')} error={save.isError ? errorText(save.error) : undefined}>
          {(id, describedBy) => (
            <input id={id} aria-describedby={describedBy} className={inputClass} value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
          )}
        </Field>
        <SubmitButton pending={save.isPending} done={save.isSuccess && name === save.data?.user.name} disabled={!name.trim() || name.trim() === user.name}>
          {t('account.save')}
        </SubmitButton>
      </form>
    </Card>
  )
}

function SubmitButton({ pending, done, disabled, children }: { pending: boolean; done?: boolean; disabled?: boolean; children: ReactNode }) {
  const { t } = useLanguage()
  return (
    <button type="submit" disabled={pending || disabled} className={`${primaryButton} justify-center`}>
      {pending ? <LoaderCircle size={16} aria-hidden className="animate-spin" /> : done ? <Check size={16} aria-hidden /> : null}
      {done ? t('account.saved') : children}
    </button>
  )
}

function PasswordCard({ account }: { account: Account }) {
  const { t } = useLanguage()
  const errorText = useErrorText()
  const hasPassword = account.user.has_password
  const [current, setCurrent] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const change = useAccountMutation(({ current, password }: { current: string; password: string }) => changePassword(current, password))
  const mismatch = confirm.length > 0 && confirm !== password
  const ready = password.length >= MIN_PASSWORD && password === confirm && (!hasPassword || current.length > 0)

  const submit = (event: FormEvent) => {
    event.preventDefault()
    change.mutate(
      { current, password },
      {
        onSuccess: () => {
          setCurrent('')
          setPassword('')
          setConfirm('')
        },
      },
    )
  }

  return (
    <Card icon={KeyRound} title={t('account.password')}>
      {!hasPassword && <p className="mb-4 text-[14px] leading-relaxed text-muted">{t('account.password.googleOnly')}</p>}
      <form onSubmit={submit} className="grid gap-4">
        {hasPassword && (
          <Field label={t('account.password.current')} hint={t('account.password.forgot')}>
            {(id, describedBy) => (
              <input
                id={id}
                aria-describedby={describedBy}
                type="password"
                autoComplete="current-password"
                className={inputClass}
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
              />
            )}
          </Field>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t('account.password.new')}>
            {(id, describedBy) => (
              <input
                id={id}
                aria-describedby={describedBy}
                type="password"
                autoComplete="new-password"
                maxLength={MAX_PASSWORD}
                className={inputClass}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            )}
          </Field>
          <Field label={t('account.password.confirm')} error={mismatch ? t('account.password.mismatch') : undefined}>
            {(id, describedBy) => (
              <input
                id={id}
                aria-describedby={describedBy}
                type="password"
                autoComplete="new-password"
                maxLength={MAX_PASSWORD}
                className={inputClass}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
              />
            )}
          </Field>
        </div>
        {password.length > 0 && <StrengthMeter password={password} />}
        {change.isError && (
          <p role="alert" className="text-[13.5px] font-medium text-rumor">
            {errorText(change.error)}
          </p>
        )}
        {change.isSuccess && (
          <p role="status" className="flex items-center gap-2 text-[13.5px] font-medium text-confirmed">
            <Check size={15} aria-hidden />
            {t('account.password.done')}
          </p>
        )}
        <div>
          <SubmitButton pending={change.isPending} disabled={!ready}>
            {t(hasPassword ? 'account.password.submit' : 'account.password.add')}
          </SubmitButton>
        </div>
      </form>
    </Card>
  )
}

const isPhone = (device: string | null) => /iOS|iPadOS|Android/.test(device ?? '')

function SessionsCard({ account }: { account: Account }) {
  const { t } = useLanguage()
  const errorText = useErrorText()
  const close = useAccountMutation(closeSession)
  const closeOthers = useAccountMutation(() => closeOtherSessions())
  const others = account.sessions.filter((session) => !session.current).length

  return (
    <Card
      icon={Monitor}
      title={t('account.sessions')}
      aside={
        others > 0 && (
          <button
            type="button"
            onClick={() => closeOthers.mutate(undefined)}
            disabled={closeOthers.isPending}
            className={`${ghostButton} flex items-center gap-1.5 text-[13px] ring-1 ring-ink/10`}
          >
            {closeOthers.isPending ? <LoaderCircle size={14} aria-hidden className="animate-spin" /> : <LogOut size={14} aria-hidden />}
            {t('account.sessions.closeOthers')}
          </button>
        )
      }
    >
      <p className="-mt-2 mb-4 text-[13px] text-muted">{t('account.sessions.hint', { days: account.session_days })}</p>
      <ul className="divide-y divide-line overflow-hidden rounded-[18px] ring-1 ring-ink/[0.06]">
        {account.sessions.map((session) => (
          <SessionRow key={session.id} session={session} onClose={() => close.mutate(session.id)} closing={close.isPending && close.variables === session.id} />
        ))}
      </ul>
      {(close.isError || closeOthers.isError) && (
        <p role="alert" className="mt-3 text-[13.5px] font-medium text-rumor">
          {errorText(close.error ?? closeOthers.error)}
        </p>
      )}
    </Card>
  )
}

function SessionRow({ session, onClose, closing }: { session: AccountSession; onClose: () => void; closing: boolean }) {
  const { language, t } = useLanguage()
  const Icon = isPhone(session.device) ? Smartphone : Monitor
  return (
    <li className="flex items-center gap-3.5 bg-canvas/40 px-4 py-3.5">
      <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-full ${session.current ? 'bg-accent-soft text-accent' : 'bg-ink/[0.05] text-muted'}`}>
        <Icon size={17} aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[14.5px] font-semibold">{session.device ?? t('account.sessions.unknown')}</p>
        <p className="truncate text-[12.5px] text-muted">
          {t('account.sessions.seen', { date: formatItemTime(session.last_seen_at, language), since: formatShortDate(session.created_at, language) })}
        </p>
      </div>
      {session.current ? (
        <span className="rounded-full bg-confirmed/10 px-2.5 py-1 text-[12px] font-semibold text-confirmed">{t('account.sessions.current')}</span>
      ) : (
        <button
          type="button"
          onClick={onClose}
          disabled={closing}
          className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] font-semibold text-muted ring-1 ring-ink/10 transition-colors duration-150 hover:text-rumor hover:ring-rumor/30 disabled:opacity-60"
        >
          {closing && <LoaderCircle size={13} aria-hidden className="animate-spin" />}
          {t('account.sessions.close')}
        </button>
      )}
    </li>
  )
}

function DataCard({ account }: { account: Account }) {
  const { t } = useLanguage()
  const errorText = useErrorText()
  const download = useMutation({
    mutationFn: exportAccount,
    onSuccess: (data) => {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `lucidnews-account-${new Date().toISOString().slice(0, 10)}.json`
      link.click()
      URL.revokeObjectURL(url)
    },
  })

  return (
    <Card icon={ShieldAlert} title={t('account.data')}>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <p className="max-w-md text-[14px] leading-relaxed text-muted">{t('account.export.hint')}</p>
        <button
          type="button"
          onClick={() => download.mutate()}
          disabled={download.isPending}
          className={`${ghostButton} flex items-center gap-1.5 ring-1 ring-ink/10`}
        >
          {download.isPending ? <LoaderCircle size={15} aria-hidden className="animate-spin" /> : <Download size={15} aria-hidden />}
          {t('account.export')}
        </button>
      </div>
      {download.isError && (
        <p role="alert" className="mt-3 text-[13.5px] font-medium text-rumor">
          {errorText(download.error)}
        </p>
      )}

      <div className="mt-6 rounded-[18px] bg-rumor/[0.05] p-5 ring-1 ring-inset ring-rumor/15">
        <p className="text-[15px] font-bold text-rumor">{t('account.delete')}</p>
        <p className="mt-1 text-[13.5px] leading-relaxed text-muted">{t(account.can_delete ? 'account.delete.hint' : 'account.delete.lastAdmin')}</p>
        {account.can_delete && <DeleteAccount account={account} />}
      </div>
    </Card>
  )
}

function DeleteAccount({ account }: { account: Account }) {
  const { t } = useLanguage()
  const errorText = useErrorText()
  const auth = useAuth()
  const [value, setValue] = useState('')
  const withPassword = account.user.has_password
  const remove = useMutation({
    mutationFn: () => deleteAccount(withPassword ? { current: value } : { email: value }),
    onSuccess: (session) => auth.forget(session),
  })
  const label = withPassword ? t('account.delete.withPassword') : t('account.delete.withEmail', { email: account.user.email })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    remove.mutate()
  }

  return (
    <AlertDialog.Root onOpenChange={() => (setValue(''), remove.reset())}>
      <AlertDialog.Trigger asChild>
        <button
          type="button"
          className="mt-4 flex items-center gap-1.5 rounded-control bg-rumor px-4 py-2.5 text-[14px] font-semibold text-on-fill transition-all duration-150 ease-soft hover:-translate-y-px hover:brightness-110"
        >
          <Trash2 size={15} aria-hidden />
          {t('account.delete')}
        </button>
      </AlertDialog.Trigger>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="fixed inset-0 z-[60] bg-ink/25 backdrop-blur-sm data-[state=open]:animate-[fade-in_200ms_ease-out]" />
        <AlertDialog.Content className="glass fixed top-1/2 left-1/2 z-[70] w-[min(92vw,440px)] -translate-x-1/2 -translate-y-1/2 rounded-card p-7 data-[state=open]:animate-[pop-in_220ms_var(--ease-soft)]">
          <AlertDialog.Title className="text-[18px] font-bold">{t('account.delete.title')}</AlertDialog.Title>
          <AlertDialog.Description className="mt-2 text-[14px] leading-relaxed text-muted">{t('account.delete.body')}</AlertDialog.Description>
          <form onSubmit={submit} className="mt-5 space-y-4">
            <Field label={label} error={remove.isError ? errorText(remove.error) : undefined}>
              {(id, describedBy) => (
                <input
                  id={id}
                  aria-describedby={describedBy}
                  type={withPassword ? 'password' : 'email'}
                  autoComplete={withPassword ? 'current-password' : 'off'}
                  className={inputClass}
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                />
              )}
            </Field>
            <div className="flex justify-end gap-3">
              <AlertDialog.Cancel className={ghostButton}>{t('account.delete.cancel')}</AlertDialog.Cancel>
              <button
                type="submit"
                disabled={!value || remove.isPending}
                className="flex items-center gap-1.5 rounded-control bg-rumor px-4 py-2.5 text-[14px] font-semibold text-on-fill transition-all duration-150 ease-soft hover:brightness-110 disabled:opacity-60"
              >
                {remove.isPending && <LoaderCircle size={15} aria-hidden className="animate-spin" />}
                {t('account.delete.confirm')}
              </button>
            </div>
          </form>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  )
}
