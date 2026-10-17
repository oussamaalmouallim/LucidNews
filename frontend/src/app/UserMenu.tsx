import { LoaderCircle, LogOut, UserRound } from 'lucide-react'
import { Popover } from 'radix-ui'
import { useState } from 'react'
import { Link } from 'react-router'
import type { AuthUser } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useLanguage } from '../lib/i18n'

function initials(user: AuthUser): string {
  const source = user.name.trim() || user.email
  const parts = source.split(/[\s@._-]+/).filter(Boolean)
  return ((parts[0]?.[0] ?? '?') + (parts.length > 1 ? (parts[1]?.[0] ?? '') : '')).toUpperCase()
}

export function Avatar({ user, size = 'h-9 w-9 text-[13px]' }: { user: AuthUser; size?: string }) {
  return user.picture ? (
    <img src={user.picture} alt="" referrerPolicy="no-referrer" className={`${size} rounded-full object-cover ring-2 ring-surface`} />
  ) : (
    <span aria-hidden className={`${size} grid place-items-center rounded-full bg-accent-soft font-bold text-accent ring-2 ring-surface`}>
      {initials(user)}
    </span>
  )
}

/** The signed-in reader and the way out. Rendered only when accounts are on. */
export function UserMenu() {
  const { language, t } = useLanguage()
  const auth = useAuth()
  const [open, setOpen] = useState(false)
  const [leaving, setLeaving] = useState(false)
  const user = auth.session?.user
  if (!user) return null

  const leave = async () => {
    setLeaving(true)
    try {
      await auth.logOut()
    } finally {
      setLeaving(false)
      setOpen(false)
    }
  }

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          type="button"
          aria-label={t('auth.userMenu')}
          title={user.email}
          className="grid h-10 w-10 shrink-0 place-items-center rounded-full transition-transform duration-150 ease-soft hover:scale-105 active:scale-95"
        >
          <Avatar user={user} />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          sideOffset={10}
          align="end"
          className="z-50 w-[min(18rem,calc(100vw-2rem))] rounded-card bg-surface p-4 shadow-card-hover ring-1 ring-ink/[0.06]"
        >
          <div className="flex items-center gap-3">
            <Avatar user={user} size="h-11 w-11 text-[15px]" />
            <div className="min-w-0">
              <p className="text-[11.5px] font-semibold tracking-wide text-faint uppercase">{t('auth.signedInAs')}</p>
              <p className="truncate text-[14.5px] font-bold">{user.name}</p>
              <p className="truncate text-[13px] text-muted">{user.email}</p>
              <p className="mt-1 inline-flex rounded-full bg-accent-soft px-2 py-0.5 text-[11.5px] font-semibold text-accent">
                {t(user.role === 'admin' ? 'auth.role.admin' : 'auth.role.reader')}
              </p>
            </div>
          </div>
          <Link
            to={{ pathname: '/account', search: `?lang=${language}` }}
            onClick={() => setOpen(false)}
            className="mt-4 flex w-full items-center justify-center gap-2 rounded-control bg-accent-soft px-4 py-2.5 text-[14px] font-semibold text-accent transition-all duration-150 ease-soft hover:bg-accent hover:text-on-fill"
          >
            <UserRound size={16} aria-hidden />
            {t('auth.myAccount')}
          </Link>
          <button
            type="button"
            onClick={leave}
            disabled={leaving}
            className="mt-2 flex w-full items-center justify-center gap-2 rounded-control bg-canvas px-4 py-2.5 text-[14px] font-semibold ring-1 ring-ink/10 transition-all duration-150 ease-soft hover:text-rumor hover:ring-rumor/30 disabled:opacity-60"
          >
            {leaving ? <LoaderCircle size={16} aria-hidden className="animate-spin" /> : <LogOut size={16} aria-hidden />}
            {t('auth.signOut')}
          </button>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
