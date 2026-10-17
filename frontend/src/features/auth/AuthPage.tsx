import { useMutation } from '@tanstack/react-query'
import { ArrowRight, Check, Eye, EyeOff, LoaderCircle, Lock, Mail, Moon, ShieldCheck, Sun, TriangleAlert, User } from 'lucide-react'
import { AnimatePresence, m } from 'motion/react'
import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router'
import { ReliabilityBadge } from '../../design/ReliabilityBadge'
import { ApiError, signIn, signUp, type Session } from '../../lib/api'
import { safeNext, useAuth } from '../../lib/auth'
import { languages, useLanguage, type MessageKey } from '../../lib/i18n'
import { easeSoft, useMotionPreference } from '../../lib/motion'
import { useTheme } from '../../lib/theme'
import { MAX_PASSWORD, MIN_PASSWORD, StrengthMeter } from './strength'

const EMAIL = /^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$/
const SUCCESS_PAUSE_MS = 700

type Mode = 'in' | 'up'

export function AuthPage({ mode }: { mode: Mode }) {
  const { t, language } = useLanguage()
  const { enabled: motionOn } = useMotionPreference()
  const auth = useAuth()
  const [params] = useSearchParams()
  const next = safeNext(params.get('next'))
  const callbackError = params.get('error')

  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [reveal, setReveal] = useState(false)
  const [attempted, setAttempted] = useState(false)
  const [googleBusy, setGoogleBusy] = useState(false)
  const [done, setDone] = useState(false)
  const [serverError, setServerError] = useState<string | null>(callbackError)
  const pending = useRef<number | null>(null)

  const signUpMode = mode === 'up'
  const session = auth.session
  const googleOn = session?.providers.google ?? false
  const signupOpen = session?.signup_enabled ?? true

  useEffect(() => () => void (pending.current && window.clearTimeout(pending.current)), [])
  // Switching tabs keeps what was typed but not the previous attempt's error.
  useEffect(() => {
    setServerError(null)
    setAttempted(false)
  }, [mode])

  const submit = useMutation({
    mutationFn: () => (signUpMode ? signUp(email.trim(), password, name.trim()) : signIn(email.trim(), password)),
    onSuccess: (result: Session) => {
      setServerError(null)
      setDone(true)
      // A short success beat, then the session is accepted and the guard moves the reader on.
      pending.current = window.setTimeout(() => auth.accept(result), motionOn ? SUCCESS_PAUSE_MS : 0)
    },
    onError: (error) => setServerError(error instanceof ApiError && error.code ? error.code : 'generic'),
  })

  const emailProblem = !EMAIL.test(email.trim()) ? 'auth.error.invalid_email' : null
  const passwordProblem =
    signUpMode && (password.length < MIN_PASSWORD || password.length > MAX_PASSWORD)
      ? 'auth.error.weak_password'
      : !password
        ? 'auth.error.invalid_credentials'
        : null

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    setAttempted(true)
    if (submit.isPending || done) return
    if (emailProblem || passwordProblem) return
    setServerError(null)
    submit.mutate()
  }

  const goGoogle = () => {
    setGoogleBusy(true)
    window.location.assign(`/api/auth/google/start?next=${encodeURIComponent(next)}`)
  }

  const switchTo = signUpMode ? '/sign-in' : '/sign-up'
  const switchSearch = `?${new URLSearchParams({ lang: language, ...(next !== '/' ? { next } : {}) }).toString()}`
  const busy = submit.isPending || done
  const errorKey = serverError ? (`auth.error.${serverError}` as MessageKey) : null
  const errorText = errorKey ? (t(errorKey) === errorKey ? t('auth.error.generic') : t(errorKey)) : null
  const closed = signUpMode && !signupOpen
  const notice = errorText ?? (closed ? t('auth.error.signup_disabled') : null)

  return (
    <div className="relative mx-auto grid min-h-dvh w-full max-w-[1280px] items-stretch gap-6 px-4 py-4 sm:px-6 sm:py-6 lg:grid-cols-[1.05fr_1fr] lg:gap-8 lg:py-8">
      <Controls />
      <BrandPanel />

      <main className="flex items-center justify-center py-6 lg:pt-16 lg:pb-0">
        <m.div
          initial={motionOn ? { opacity: 0, y: 24 } : false}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: easeSoft }}
          className="w-full max-w-[460px]"
        >
          <div className="mb-7 flex items-center gap-3 lg:hidden">
            <Logo />
            <span className="text-[19px] font-bold tracking-tight">LucidNews</span>
          </div>

          <div className="rounded-[28px] bg-surface p-6 shadow-card ring-1 ring-ink/[0.05] sm:p-9">
            <Tabs mode={mode} switchSearch={switchSearch} />

            <AnimatePresence mode="wait" initial={false}>
              <m.div
                key={mode}
                initial={motionOn ? { opacity: 0, y: 8 } : false}
                animate={{ opacity: 1, y: 0 }}
                exit={motionOn ? { opacity: 0, y: -6 } : undefined}
                transition={{ duration: 0.2, ease: easeSoft }}
                className="mt-7"
              >
                <h1 className="font-serif text-[32px] leading-[1.1] font-medium tracking-[-0.01em] sm:text-[36px]">
                  {t(signUpMode ? 'auth.signUpTitle' : 'auth.signInTitle')}
                </h1>
                <p className="mt-2 text-[15px] leading-relaxed text-muted">{t(signUpMode ? 'auth.signUpSubtitle' : 'auth.signInSubtitle')}</p>
              </m.div>
            </AnimatePresence>

            <AnimatePresence initial={false}>
              {notice && (
                <m.div
                  key={serverError ?? 'closed'}
                  role="alert"
                  initial={motionOn ? { opacity: 0, height: 0 } : false}
                  animate={{ opacity: 1, height: 'auto', x: motionOn ? [0, -6, 6, -4, 4, 0] : 0 }}
                  exit={motionOn ? { opacity: 0, height: 0 } : undefined}
                  transition={{ duration: 0.4, ease: easeSoft }}
                  className="mt-5 overflow-hidden"
                >
                  <p className="flex items-start gap-2.5 rounded-control bg-rumor/10 px-3.5 py-3 text-[13.5px] leading-snug font-medium text-rumor ring-1 ring-rumor/20">
                    <TriangleAlert size={16} aria-hidden className="mt-0.5 shrink-0" />
                    {notice}
                  </p>
                </m.div>
              )}
            </AnimatePresence>

            {googleOn && !closed && (
              <>
                <button
                  type="button"
                  onClick={goGoogle}
                  disabled={googleBusy || busy}
                  aria-busy={googleBusy}
                  className="mt-6 flex h-12 w-full items-center justify-center gap-3 rounded-[14px] bg-canvas text-[14.5px] font-semibold ring-1 ring-ink/10 transition-all duration-150 ease-soft hover:-translate-y-px hover:ring-accent/40 hover:shadow-card focus-visible:ring-2 focus-visible:ring-accent/50 active:translate-y-0 disabled:opacity-60"
                >
                  {googleBusy ? <LoaderCircle size={18} aria-hidden className="animate-spin" /> : <GoogleMark />}
                  {t(googleBusy ? 'auth.googleRedirect' : 'auth.google')}
                </button>
                <div className="my-6 flex items-center gap-4 text-[12px] font-semibold tracking-wider text-faint uppercase" aria-hidden>
                  <span className="h-px flex-1 bg-line" />
                  {t('auth.or')}
                  <span className="h-px flex-1 bg-line" />
                </div>
              </>
            )}

            <form onSubmit={onSubmit} noValidate className={`space-y-4 ${googleOn && !closed ? '' : 'mt-6'}`} aria-busy={busy}>
              <AnimatePresence initial={false}>
                {signUpMode && (
                  <m.div
                    key="name"
                    initial={motionOn ? { opacity: 0, height: 0 } : false}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={motionOn ? { opacity: 0, height: 0 } : undefined}
                    transition={{ duration: 0.28, ease: easeSoft }}
                    className="-mx-1 overflow-hidden px-1 pt-1 pb-1"
                  >
                    <TextField
                      icon={<User size={17} aria-hidden />}
                      label={t('auth.name')}
                      value={name}
                      onChange={setName}
                      autoComplete="name"
                      disabled={busy || closed}
                      maxLength={80}
                    />
                  </m.div>
                )}
              </AnimatePresence>

              <TextField
                icon={<Mail size={17} aria-hidden />}
                label={t('auth.email')}
                type="email"
                inputMode="email"
                value={email}
                onChange={setEmail}
                autoComplete="email"
                disabled={busy || closed}
                error={attempted && emailProblem ? t(emailProblem as MessageKey) : undefined}
                maxLength={254}
              />

              <TextField
                icon={<Lock size={17} aria-hidden />}
                label={t('auth.password')}
                type={reveal ? 'text' : 'password'}
                value={password}
                onChange={setPassword}
                autoComplete={signUpMode ? 'new-password' : 'current-password'}
                disabled={busy || closed}
                error={attempted && passwordProblem ? t(passwordProblem as MessageKey) : undefined}
                hint={signUpMode ? t('auth.passwordHint') : undefined}
                maxLength={MAX_PASSWORD + 1}
                trailing={
                  <button
                    type="button"
                    onClick={() => setReveal((value) => !value)}
                    aria-label={t(reveal ? 'auth.hidePassword' : 'auth.showPassword')}
                    aria-pressed={reveal}
                    className="grid h-9 w-9 place-items-center rounded-full text-muted transition-colors duration-150 hover:bg-ink/[0.05] hover:text-ink"
                  >
                    {reveal ? <EyeOff size={17} aria-hidden /> : <Eye size={17} aria-hidden />}
                  </button>
                }
              />

              <AnimatePresence initial={false}>
                {signUpMode && password.length > 0 && (
                  <m.div
                    key="strength"
                    initial={motionOn ? { opacity: 0, height: 0 } : false}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={motionOn ? { opacity: 0, height: 0 } : undefined}
                    transition={{ duration: 0.22, ease: easeSoft }}
                    className="overflow-hidden"
                  >
                    <StrengthMeter password={password} />
                  </m.div>
                )}
              </AnimatePresence>

              {/* The label is inside the animated span below. */}
              {/* oxlint-disable-next-line jsx-a11y/control-has-associated-label */}
              <button
                type="submit"
                disabled={busy || closed}
                className={`group relative flex h-12 w-full items-center justify-center gap-2 overflow-hidden rounded-[14px] px-5 text-[15px] font-semibold text-on-fill shadow-accent transition-all duration-200 ease-soft focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-surface enabled:hover:-translate-y-0.5 enabled:active:translate-y-0 enabled:active:scale-[0.99] disabled:cursor-not-allowed ${
                  done ? 'bg-confirmed' : 'bg-gradient-to-r from-accent to-accent-deep'
                } ${busy && !done ? 'opacity-90' : ''} ${closed ? 'opacity-50' : ''}`}
              >
                <AnimatePresence mode="wait" initial={false}>
                  <m.span
                    key={done ? 'done' : submit.isPending ? 'busy' : 'idle'}
                    initial={motionOn ? { opacity: 0, y: 8 } : false}
                    animate={{ opacity: 1, y: 0 }}
                    exit={motionOn ? { opacity: 0, y: -8 } : undefined}
                    transition={{ duration: 0.16 }}
                    className="flex items-center gap-2"
                  >
                    {done ? (
                      <>
                        <Check size={18} aria-hidden />
                        {t('auth.done')}
                      </>
                    ) : submit.isPending ? (
                      <>
                        <LoaderCircle size={18} aria-hidden className="animate-spin" />
                        {t(signUpMode ? 'auth.submittingSignUp' : 'auth.submittingSignIn')}
                      </>
                    ) : (
                      <>
                        {t(signUpMode ? 'auth.submitSignUp' : 'auth.submitSignIn')}
                        <ArrowRight size={17} aria-hidden className="transition-transform duration-200 ease-soft group-hover:translate-x-0.5" />
                      </>
                    )}
                  </m.span>
                </AnimatePresence>
              </button>
            </form>

            <p className="mt-6 text-center text-[14px] text-muted">
              {t(signUpMode ? 'auth.switchToSignIn' : 'auth.switchToSignUp')}{' '}
              <Link to={{ pathname: switchTo, search: switchSearch }} className="font-semibold text-accent underline-offset-4 hover:underline">
                {t(signUpMode ? 'auth.signInTab' : 'auth.signUpTab')}
              </Link>
            </p>
          </div>

          <p className="mt-5 flex items-center justify-center gap-2 px-4 text-center text-[12.5px] leading-snug text-muted">
            <ShieldCheck size={14} aria-hidden className="shrink-0 text-confirmed" />
            {t('auth.passwordsStored')}
          </p>
        </m.div>
      </main>
      <span className="sr-only" role="status" aria-live="polite">
        {submit.isPending ? t(signUpMode ? 'auth.submittingSignUp' : 'auth.submittingSignIn') : ''}
      </span>
    </div>
  )
}

function Logo() {
  return (
    <span className="grid h-9 w-9 place-items-center rounded-[11px] bg-accent text-on-fill shadow-accent">
      <svg viewBox="0 0 20 20" className="h-[18px] w-[18px]" aria-hidden>
        <circle cx="10" cy="10" r="6" fill="none" stroke="currentColor" strokeWidth="2.2" />
        <circle cx="10" cy="10" r="2.2" fill="currentColor" />
      </svg>
    </span>
  )
}

function Controls() {
  const { language, setLanguage, t } = useLanguage()
  const theme = useTheme()
  return (
    <div className="absolute top-5 right-5 z-10 flex items-center gap-2 sm:top-8 sm:right-8 lg:top-9 lg:right-10">
      <div role="group" aria-label={t('language.switch')} className="flex rounded-full bg-surface/80 p-1 shadow-card ring-1 ring-ink/[0.04] backdrop-blur">
        {languages.map((code) => (
          <button
            key={code}
            type="button"
            aria-pressed={code === language}
            onClick={() => setLanguage(code)}
            className="rounded-full px-3 py-1.5 text-xs font-bold tracking-wide text-muted uppercase transition-colors duration-150 hover:text-ink aria-pressed:bg-accent-soft aria-pressed:text-accent"
          >
            {code}
          </button>
        ))}
      </div>
      <button
        type="button"
        onClick={theme.toggle}
        aria-label={t(theme.dark ? 'theme.toLight' : 'theme.toDark')}
        title={t(theme.dark ? 'theme.toLight' : 'theme.toDark')}
        className="grid h-10 w-10 place-items-center rounded-full bg-surface/80 text-muted shadow-card ring-1 ring-ink/[0.04] backdrop-blur transition-all duration-150 ease-soft hover:text-ink active:scale-95"
      >
        {theme.dark ? <Sun size={17} aria-hidden /> : <Moon size={17} aria-hidden />}
      </button>
    </div>
  )
}

function Tabs({ mode, switchSearch }: { mode: Mode; switchSearch: string }) {
  const { t } = useLanguage()
  const { enabled } = useMotionPreference()
  const id = useId()
  const items: { to: string; mode: Mode; label: MessageKey }[] = [
    { to: '/sign-in', mode: 'in', label: 'auth.signInTab' },
    { to: '/sign-up', mode: 'up', label: 'auth.signUpTab' },
  ]
  return (
    <div role="tablist" aria-label={`${t('auth.signInTab')} / ${t('auth.signUpTab')}`} className="grid grid-cols-2 rounded-full bg-ink/[0.045] p-1">
      {items.map((item) => {
        const active = item.mode === mode
        return (
          <Link
            key={item.mode}
            role="tab"
            aria-selected={active}
            replace
            to={{ pathname: item.to, search: switchSearch }}
            className={`relative rounded-full px-2 py-2.5 text-center text-[13.5px] font-semibold whitespace-nowrap sm:px-4 sm:text-[14px] transition-colors duration-150 ${active ? 'text-ink' : 'text-muted hover:text-ink'}`}
          >
            {active && (
              <m.span
                layoutId={`${id}-auth-pill`}
                transition={enabled ? { type: 'spring', stiffness: 420, damping: 34 } : { duration: 0 }}
                className="absolute inset-0 rounded-full bg-surface shadow-card ring-1 ring-ink/[0.05]"
              />
            )}
            <span className="relative">{t(item.label)}</span>
          </Link>
        )
      })}
    </div>
  )
}

function TextField({
  label,
  value,
  onChange,
  icon,
  trailing,
  error,
  hint,
  type = 'text',
  ...rest
}: {
  label: string
  value: string
  onChange: (value: string) => void
  icon: ReactNode
  trailing?: ReactNode
  error?: string
  hint?: string
  type?: string
  autoComplete?: string
  inputMode?: 'email'
  disabled?: boolean
  maxLength?: number
}) {
  const id = useId()
  const describedBy = [hint ? `${id}-hint` : '', error ? `${id}-error` : ''].filter(Boolean).join(' ') || undefined
  return (
    <div>
      <label htmlFor={id} className="text-[13.5px] font-semibold text-ink/85">
        {label}
      </label>
      <div className="relative mt-1.5">
        <span aria-hidden className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-faint">
          {icon}
        </span>
        <input
          id={id}
          type={type}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          spellCheck={false}
          {...rest}
          className={`h-12 w-full rounded-[14px] bg-canvas pl-11 text-[15px] outline-none ring-1 transition-shadow duration-150 placeholder:text-faint focus:ring-2 disabled:cursor-not-allowed disabled:opacity-60 ${
            trailing ? 'pr-12' : 'pr-4'
          } ${error ? 'ring-rumor/50 focus:ring-rumor/60' : 'ring-ink/10 focus:ring-accent/60'}`}
        />
        {trailing && <span className="absolute top-1/2 right-1.5 -translate-y-1/2">{trailing}</span>}
      </div>
      {hint && !error && (
        <p id={`${id}-hint`} className="mt-1.5 text-[12.5px] text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="mt-1.5 text-[12.5px] font-medium text-rumor">
          {error}
        </p>
      )}
    </div>
  )
}

function BrandPanel() {
  const { t } = useLanguage()
  const { enabled } = useMotionPreference()
  const points: MessageKey[] = ['auth.brand.point1', 'auth.brand.point2', 'auth.brand.point3']
  const float = (delay: number) =>
    enabled ? { animate: { y: [0, -8, 0] }, transition: { duration: 6, ease: 'easeInOut' as const, repeat: Infinity, delay } } : {}
  return (
    <aside className="relative isolate hidden overflow-hidden rounded-[32px] bg-gradient-to-br from-accent to-accent-deep p-12 text-on-fill shadow-[0_30px_70px_-30px_rgb(76_63_216/0.55)] lg:flex lg:flex-col">
      <span aria-hidden className="absolute -top-28 -right-24 -z-10 h-96 w-96 animate-drift rounded-full bg-on-fill/[0.08] blur-sm" />
      <span aria-hidden className="absolute -bottom-40 -left-24 -z-10 h-[26rem] w-[26rem] animate-drift-slow rounded-full bg-on-fill/[0.06] blur-sm" />
      <svg aria-hidden className="absolute inset-0 -z-10 h-full w-full text-on-fill/[0.07]" preserveAspectRatio="none">
        <defs>
          <pattern id="auth-lines" width="260" height="220" patternUnits="userSpaceOnUse">
            <rect x="16" y="16" width="170" height="140" rx="40" fill="none" stroke="currentColor" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#auth-lines)" />
      </svg>

      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-[12px] bg-on-fill/15 ring-1 ring-on-fill/25">
          <svg viewBox="0 0 20 20" className="h-5 w-5" aria-hidden>
            <circle cx="10" cy="10" r="6" fill="none" stroke="currentColor" strokeWidth="2.2" />
            <circle cx="10" cy="10" r="2.2" fill="currentColor" />
          </svg>
        </span>
        <span className="text-[20px] font-bold tracking-tight">LucidNews</span>
      </div>

      <div className="mt-16 max-w-[30rem]">
        <h2 className="font-serif text-[52px] leading-[1.03] font-medium tracking-[-0.02em]">{t('auth.brand.title')}</h2>
        <p className="mt-5 text-[17px] leading-relaxed text-on-fill/80">{t('auth.brand.subtitle')}</p>
        <ul className="mt-9 space-y-3.5">
          {points.map((point) => (
            <li key={point} className="flex items-center gap-3 text-[15px] font-medium">
              <span className="grid h-6 w-6 place-items-center rounded-full bg-on-fill/15 ring-1 ring-on-fill/25">
                <Check size={14} aria-hidden strokeWidth={3} />
              </span>
              {t(point)}
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-auto grid gap-4 pt-12 xl:max-w-[30rem]" aria-hidden>
        <m.div {...float(0)} className="rounded-[20px] bg-surface p-4 text-ink shadow-float">
          <ReliabilityBadge label="confirmed" />
          <p className="mt-2.5 text-[14px] leading-snug font-semibold">{t('auth.brand.sample1')}</p>
        </m.div>
        <m.div {...float(1.4)} className="rounded-[20px] bg-surface p-4 text-ink shadow-float xl:ml-10">
          <ReliabilityBadge label="rumor" />
          <p className="mt-2.5 text-[14px] leading-snug font-semibold">{t('auth.brand.sample2')}</p>
        </m.div>
      </div>
    </aside>
  )
}

function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" className="h-[18px] w-[18px]" aria-hidden>
      <path
        fill="#EA4335"
        d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
      />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path
        fill="#FBBC05"
        d="M10.53 28.59A14.5 14.5 0 0 1 9.5 24c0-1.59.28-3.14.76-4.59l-7.98-6.19A23.99 23.99 0 0 0 0 24c0 3.77.9 7.35 2.56 10.78l7.97-6.19z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
      />
    </svg>
  )
}
