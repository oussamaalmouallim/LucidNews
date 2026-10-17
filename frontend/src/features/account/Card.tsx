import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

/** A section of the account page: icon tile, title, optional action, body. */
export function Card({
  icon: Icon,
  title,
  aside,
  tone = 'accent',
  anchor,
  children,
}: {
  icon: LucideIcon
  title: string
  aside?: ReactNode
  tone?: 'accent' | 'danger'
  /** An id other pages link to (``/account#my-watch``). */
  anchor?: string
  children: ReactNode
}) {
  const headingId = `account-${title.toLowerCase().replace(/\W+/g, '-')}`
  return (
    <section id={anchor} aria-labelledby={headingId} className="scroll-mt-28 rounded-card bg-surface p-6 shadow-card ring-1 ring-ink/[0.03] sm:p-8">
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
