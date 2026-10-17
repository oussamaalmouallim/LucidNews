import { useLanguage, type MessageKey } from '../../lib/i18n'

export const MIN_PASSWORD = 8
export const MAX_PASSWORD = 128

/** 0 (too short) to 3 (strong): a hint for the reader, never a rule the server relies on. */
export function strengthOf(password: string): number {
  if (password.length < MIN_PASSWORD) return 0
  let score = 1
  if (password.length >= 12) score += 1
  if (/[a-z]/.test(password) && /[A-Z0-9]/.test(password) && /[^A-Za-z0-9]|\d/.test(password)) score += 1
  return Math.min(3, score)
}

const STRENGTH_LABELS: MessageKey[] = ['auth.strength.short', 'auth.strength.weak', 'auth.strength.good', 'auth.strength.strong']
const STRENGTH_TONES = ['bg-rumor', 'bg-unverified', 'bg-reliable', 'bg-confirmed']

/** Three bars and a word: shared by sign-up and the account page. */
export function StrengthMeter({ password }: { password: string }) {
  const { t } = useLanguage()
  const strength = strengthOf(password)
  return (
    <div role="status" aria-label={t('auth.strength')} className="flex items-center gap-3 pt-0.5">
      <div className="flex flex-1 gap-1.5" aria-hidden>
        {[0, 1, 2].map((bar) => (
          <span key={bar} className={`h-1.5 flex-1 rounded-full transition-colors duration-300 ${bar < strength ? STRENGTH_TONES[strength] : 'bg-ink/10'}`} />
        ))}
      </div>
      <span className="w-16 text-right text-[12.5px] font-semibold text-muted">{t(STRENGTH_LABELS[strength]!)}</span>
    </div>
  )
}
