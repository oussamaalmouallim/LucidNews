import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, type ReactNode } from 'react'
import { fetchSession, signOut, UNAUTHORIZED_EVENT, type Session } from './api'

const SESSION_KEY = ['auth-session']

type AuthState = {
  /** The first answer has not arrived yet. */
  loading: boolean
  /** The session endpoint could not be reached (not the same as "signed out"). */
  failed: boolean
  session: Session | undefined
  /** Accounts are on and nobody is signed in: private routes must not render. */
  locked: boolean
  /** May open the administration screens. Accounts off: the API alone decides (localhost). */
  isAdmin: boolean
  accept: (session: Session) => void
  logOut: () => Promise<void>
  /** The account is gone (deleted): drop everything loaded for it and keep the signed-out session. */
  forget: (session: Session) => void
  retry: () => void
}

const AuthContext = createContext<AuthState | null>(null)

/** Asks the server who the reader is, once, and again whenever a request comes back 401. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: SESSION_KEY, queryFn: ({ signal }) => fetchSession(signal), staleTime: 5 * 60_000 })

  useEffect(() => {
    const onUnauthorized = () => void queryClient.invalidateQueries({ queryKey: SESSION_KEY })
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
  }, [queryClient])

  const accept = useCallback((session: Session) => queryClient.setQueryData(SESSION_KEY, session), [queryClient])
  const forget = useCallback(
    (session: Session) => {
      // Whatever was loaded for the previous reader must not outlive the session.
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== SESSION_KEY[0] })
      queryClient.setQueryData(SESSION_KEY, session)
    },
    [queryClient],
  )
  const logOut = useCallback(async () => forget(await signOut()), [forget])

  const value = useMemo<AuthState>(
    () => ({
      loading: query.isPending,
      failed: query.isError,
      session: query.data,
      locked: Boolean(query.data?.enabled && !query.data.authenticated),
      isAdmin: !query.data?.enabled || query.data.user?.role === 'admin',
      accept,
      logOut,
      forget,
      retry: () => void query.refetch(),
    }),
    [query, accept, logOut, forget],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}

/** A path of this app only (what the server also enforces for the Google return). */
export function safeNext(value: string | null): string {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.includes('\\')) return '/'
  return value.startsWith('/sign-in') ? '/' : value
}

/** The same path in the reader's language, unless it already names one: signing in keeps French in French. */
export function withLanguage(path: string, language: string): string {
  const url = new URL(path, 'http://app.invalid')
  if (!url.searchParams.has('lang')) url.searchParams.set('lang', language)
  return `${url.pathname}${url.search}${url.hash}`
}
