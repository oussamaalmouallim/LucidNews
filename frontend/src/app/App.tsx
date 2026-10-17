import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation, useSearchParams } from 'react-router'
import { Backdrop } from '../design/Backdrop'
import { ApiErrorCard, PageSkeleton } from '../design/PageState'
import { AuthProvider, safeNext, useAuth } from '../lib/auth'
import { useLanguage } from '../lib/i18n'
import { MotionProvider } from '../lib/motion'
import { ThemeProvider } from '../lib/theme'
import { AdminOnly } from './AdminOnly'
import { TopBar } from './TopBar'

// One chunk per screen: charts and the calendar load only where they are used.
const AuthPage = lazy(() => import('../features/auth/AuthPage').then((m) => ({ default: m.AuthPage })))
const EditionPage = lazy(() => import('../features/edition/EditionPage').then((m) => ({ default: m.EditionPage })))
const ArchivePage = lazy(() => import('../features/archive/ArchivePage').then((m) => ({ default: m.ArchivePage })))
const ItemPage = lazy(() => import('../features/item/ItemPage').then((m) => ({ default: m.ItemPage })))
const PreferencesPage = lazy(() => import('../features/preferences/PreferencesPage').then((m) => ({ default: m.PreferencesPage })))
const QualityPage = lazy(() => import('../features/quality/QualityPage').then((m) => ({ default: m.QualityPage })))
const SettingsPage = lazy(() => import('../features/settings/SettingsPage').then((m) => ({ default: m.SettingsPage })))
const SourcesPage = lazy(() => import('../features/sources/SourcesPage').then((m) => ({ default: m.SourcesPage })))

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { staleTime: 60_000, retry: 1, refetchOnWindowFocus: false } },
  })
}

const AUTH_PATHS = ['/sign-in', '/sign-up']

export function Shell() {
  const { language } = useLanguage()
  const auth = useAuth()
  const { pathname, search } = useLocation()
  const [params] = useSearchParams()
  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  if (auth.loading || auth.failed) {
    return (
      <>
        <Backdrop />
        <main className="mx-auto w-full max-w-6xl px-4 pt-24 sm:px-6">
          {auth.failed ? <ApiErrorCard error={new Error('session')} onRetry={auth.retry} /> : <PageSkeleton blocks={1} />}
        </main>
      </>
    )
  }

  // Accounts on: private routes never render for a signed-out reader (the API refuses them too).
  const onAuthPage = AUTH_PATHS.includes(pathname)
  if (auth.session?.enabled) {
    if (auth.locked && !onAuthPage) {
      const query = new URLSearchParams({ next: `${pathname}${search}`, lang: language })
      return <Navigate to={`/sign-in?${query.toString()}`} replace />
    }
    if (!auth.locked && onAuthPage) return <Navigate to={safeNext(params.get('next'))} replace />
  } else if (onAuthPage) {
    return <Navigate to="/" replace />
  }
  if (onAuthPage) {
    return (
      <>
        <Backdrop />
        <Suspense fallback={null}>
          <AuthPage mode={pathname === '/sign-up' ? 'up' : 'in'} />
        </Suspense>
      </>
    )
  }

  return (
    <>
      <Backdrop />
      <TopBar />
      <main className="mx-auto w-full max-w-6xl px-4 pb-32 pt-8 sm:px-6 sm:pt-10 lg:pb-24">
        <Suspense fallback={<PageSkeleton />}>
          <Routes>
            <Route path="/" element={<EditionPage />} />
            <Route path="/editions/:editionId" element={<EditionPage />} />
            <Route path="/items/:itemId" element={<ItemPage />} />
            <Route path="/archive" element={<ArchivePage />} />
            <Route element={<AdminOnly />}>
              <Route path="/sources" element={<SourcesPage />} />
              <Route path="/preferences" element={<PreferencesPage />} />
              <Route path="/preferences/:subscriberId" element={<PreferencesPage />} />
              <Route path="/quality" element={<QualityPage />} />
              <Route path="/quality/results" element={<QualityPage />} />
              <Route path="/quality/annotate" element={<QualityPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </main>
    </>
  )
}

export function App({ queryClient = createQueryClient() }: { queryClient?: QueryClient }) {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <MotionProvider>
          <BrowserRouter>
            <AuthProvider>
              <Shell />
            </AuthProvider>
          </BrowserRouter>
        </MotionProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}
