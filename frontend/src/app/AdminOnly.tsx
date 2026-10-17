import { ArrowLeft, ShieldCheck } from 'lucide-react'
import { Link, Outlet } from 'react-router'
import { useAuth } from '../lib/auth'
import { useLanguage } from '../lib/i18n'

/** The administration screens: a reader gets an explanation instead (the API refuses the data too). */
export function AdminOnly() {
  const { language, t } = useLanguage()
  if (useAuth().isAdmin) return <Outlet />
  return (
    <div role="alert" className="mx-auto mt-10 max-w-lg rounded-card bg-surface p-8 text-center shadow-card">
      <span className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-accent-soft text-accent">
        <ShieldCheck size={22} aria-hidden />
      </span>
      <h1 className="mt-4 text-lg font-bold">{t('admin.only.title')}</h1>
      <p className="mt-2 text-sm text-muted">{t('admin.only.body')}</p>
      <Link
        to={{ pathname: '/', search: `?lang=${language}` }}
        className="mt-6 inline-flex items-center gap-2 rounded-control bg-accent px-5 py-2.5 text-sm font-semibold text-on-fill shadow-accent transition-all duration-150 ease-soft hover:-translate-y-0.5 hover:bg-accent-deep active:translate-y-0 active:scale-[0.98]"
      >
        <ArrowLeft size={15} aria-hidden />
        {t('admin.only.back')}
      </Link>
    </div>
  )
}
