import { Lock } from 'lucide-react'
import { useId, type ReactNode } from 'react'
import { useLanguage } from '../lib/i18n'

/** Form styles and the labelled field shared by the Settings and Sources forms. */
export const inputClass =
  'w-full rounded-control bg-canvas px-3.5 py-2.5 text-[14px] ring-1 ring-ink/10 outline-none transition-shadow duration-150 focus:ring-2 focus:ring-accent/50 disabled:cursor-not-allowed disabled:opacity-60'
export const labelClass = 'text-[13.5px] font-semibold text-ink/85'
export const hintClass = 'mt-0.5 text-[12.5px] leading-snug text-muted'
export const errorClass = 'mt-1.5 text-[12.5px] font-medium text-rumor'
export const primaryButton =
  'flex items-center gap-1.5 rounded-control bg-accent px-4 py-2.5 text-[14px] font-semibold text-on-fill shadow-accent transition-all duration-150 ease-soft hover:-translate-y-px hover:bg-accent-deep disabled:opacity-60'
export const ghostButton =
  'rounded-control px-4 py-2.5 text-[14px] font-semibold text-ink/70 transition-colors duration-150 hover:bg-surface disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent'

export function Field({
  label,
  hint,
  error,
  locked = false,
  children,
}: {
  label: string
  hint?: string
  error?: string
  locked?: boolean
  children: (id: string, describedBy: string | undefined) => ReactNode
}) {
  const { t } = useLanguage()
  const id = useId()
  const hintId = `${id}-hint`
  const errorId = `${id}-error`
  const describedBy = [hint || locked ? hintId : '', error ? errorId : ''].filter(Boolean).join(' ') || undefined
  return (
    <div>
      <label htmlFor={id} className={`${labelClass} flex items-center gap-1.5`}>
        {label}
        {locked && <Lock size={12} aria-hidden className="text-faint" />}
      </label>
      <div className="mt-1.5">{children(id, describedBy)}</div>
      {(hint || locked) && (
        <p id={hintId} className={hintClass}>
          {locked ? t('settings.locked') : hint}
        </p>
      )}
      {error && (
        <p id={errorId} className={errorClass}>
          {error}
        </p>
      )}
    </div>
  )
}
