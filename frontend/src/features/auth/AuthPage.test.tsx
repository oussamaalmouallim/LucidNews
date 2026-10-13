import { fireEvent, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import { fixtures, renderAt } from '../../test/render'

type Session = { enabled: boolean; authenticated: boolean; user: unknown; signup_enabled: boolean; providers: { google: boolean } }
type Call = { method: string; path: string; body: unknown }

const user = { id: 'u1', email: 'ada@example.com', name: 'Ada Reader', picture: null, has_password: true, has_google: false }
const signedOut = (overrides: Partial<Session> = {}): Session => ({
  enabled: true,
  authenticated: false,
  user: null,
  signup_enabled: true,
  providers: { google: false },
  ...overrides,
})
const signedIn: Session = { ...signedOut(), authenticated: true, user }

/** An API with accounts on: the session starts as given and follows sign-in, sign-up and sign-out. */
function mockAuthApi(start: Session, replies: Partial<Record<'sign-in' | 'sign-up', [number, unknown]>> = {}) {
  let session = start
  const calls: Call[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const path = new URL(String(input), 'http://localhost').pathname
    const method = init?.method ?? 'GET'
    calls.push({ method, path, body: init?.body ? JSON.parse(String(init.body)) : undefined })
    const reply = (status: number, body: unknown) => new Response(JSON.stringify(body), { status })
    if (path === '/api/auth/session') return reply(200, session)
    if (path === '/api/auth/sign-in' || path === '/api/auth/sign-up') {
      const key = path.endsWith('in') ? 'sign-in' : 'sign-up'
      const [status, body] = replies[key] ?? [200, undefined]
      if (status < 400) session = (body as Session | undefined) ?? signedIn
      return reply(status, status < 400 ? session : body)
    }
    if (path === '/api/auth/sign-out') {
      session = signedOut()
      return reply(200, session)
    }
    if (path.startsWith('/api/editions/')) return reply(200, fixtures.editionFr)
    if (path === '/api/editions') return reply(200, fixtures.editions)
    return reply(404, { error: 'not found' })
  })
  return calls
}

const waitForSignIn = () => screen.findByRole('heading', { level: 1, name: 'Bon retour' }, { timeout: 5000 })
const fill = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } })

test('a signed-out reader never sees a private page: they land on the sign-in page and come back after', async () => {
  const calls = mockAuthApi(signedOut())
  renderAt('/archive?lang=fr', null)
  await waitForSignIn()

  expect(window.location.pathname).toBe('/sign-in')
  expect(new URLSearchParams(window.location.search).get('next')).toBe('/archive?lang=fr')
  expect(calls.some((call) => call.path.startsWith('/api/editions'))).toBe(false) // nothing private was even requested
  expect(screen.queryByRole('navigation', { name: 'Navigation principale' })).toBeNull()

  fill('Adresse e-mail', 'ada@example.com')
  fill('Mot de passe', 'a long enough password')
  fireEvent.click(screen.getByRole('button', { name: /^Se connecter$/ }))

  await waitFor(() => expect(window.location.pathname).toBe('/archive'), { timeout: 5000 })
  expect(calls.find((call) => call.path === '/api/auth/sign-in')?.body).toEqual({ email: 'ada@example.com', password: 'a long enough password' })
})

test('a wrong password is explained and the form stays usable', async () => {
  mockAuthApi(signedOut(), { 'sign-in': [401, { error: 'incorrect', code: 'invalid_credentials' }] })
  renderAt('/sign-in?lang=fr', null)
  await waitForSignIn()

  fill('Adresse e-mail', 'ada@example.com')
  fill('Mot de passe', 'not the password')
  fireEvent.click(screen.getByRole('button', { name: /^Se connecter$/ }))

  expect(await screen.findByRole('alert')).toHaveTextContent('Adresse e-mail ou mot de passe incorrect.')
  expect(screen.getByRole('button', { name: /^Se connecter$/ })).toBeEnabled()
  expect(window.location.pathname).toBe('/sign-in')
})

test('sign-up checks the form before sending anything, then creates the account without any e-mail step', async () => {
  const calls = mockAuthApi(signedOut({ providers: { google: false } }))
  renderAt('/sign-up?lang=fr', null)
  await screen.findByRole('heading', { level: 1, name: 'Créez votre compte' }, { timeout: 5000 })

  expect(screen.getByText('Quelques secondes. Aucun e-mail à confirmer.')).toBeInTheDocument()
  fill('Adresse e-mail', 'not an address')
  fill('Mot de passe', 'short')
  fireEvent.click(screen.getByRole('button', { name: 'Créer mon compte' }))
  expect(await screen.findByText('Saisissez une adresse e-mail valide.')).toBeInTheDocument()
  expect(screen.getByText('Le mot de passe doit faire de 8 à 128 caractères.')).toBeInTheDocument()
  expect(calls.some((call) => call.path === '/api/auth/sign-up')).toBe(false)

  fill('Nom (facultatif)', 'Ada')
  fill('Adresse e-mail', 'ada@example.com')
  fill('Mot de passe', 'a long enough password')
  expect(screen.getByRole('status', { name: 'Solidité du mot de passe' })).toHaveTextContent('Correct')
  fill('Mot de passe', 'a Much-longer passphrase, 2026!')
  expect(screen.getByRole('status', { name: 'Solidité du mot de passe' })).toHaveTextContent('Solide')
  fireEvent.click(screen.getByRole('button', { name: 'Créer mon compte' }))

  await waitFor(() => expect(window.location.pathname).toBe('/'), { timeout: 5000 })
  expect(calls.find((call) => call.path === '/api/auth/sign-up')?.body).toEqual({
    email: 'ada@example.com',
    password: 'a Much-longer passphrase, 2026!',
    name: 'Ada',
  })
})

test('an address already used is reported on sign-up', async () => {
  mockAuthApi(signedOut(), { 'sign-up': [409, { error: 'taken', code: 'email_taken' }] })
  renderAt('/sign-up?lang=fr', null)
  await screen.findByRole('heading', { level: 1, name: 'Créez votre compte' }, { timeout: 5000 })

  fill('Adresse e-mail', 'ada@example.com')
  fill('Mot de passe', 'a long enough password')
  fireEvent.click(screen.getByRole('button', { name: 'Créer mon compte' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('Un compte utilise déjà cette adresse.')
})

test('the Google button exists only when the server has Google configured, and starts the real redirect', async () => {
  mockAuthApi(signedOut())
  renderAt('/sign-in?lang=fr&next=%2Fsources', null)
  await waitForSignIn()
  expect(screen.queryByRole('button', { name: /Continuer avec Google/ })).toBeNull()

  vi.restoreAllMocks()
  mockAuthApi(signedOut({ providers: { google: true } }))
  const assign = vi.fn()
  const original = window.location
  Object.defineProperty(window, 'location', { configurable: true, value: { ...original, assign, pathname: original.pathname, search: original.search } })
  try {
    renderAt('/sign-in?lang=fr&next=%2Fsources', null)
    fireEvent.click(await screen.findByRole('button', { name: /Continuer avec Google/ }, { timeout: 5000 }))
    expect(assign).toHaveBeenCalledWith('/api/auth/google/start?next=%2Fsources')
  } finally {
    Object.defineProperty(window, 'location', { configurable: true, value: original })
  }
})

test('the reason a Google sign-in failed is shown on return', async () => {
  mockAuthApi(signedOut({ providers: { google: true } }))
  renderAt('/sign-in?lang=fr&error=google_cancelled', null)

  expect(await screen.findByRole('alert', {}, { timeout: 5000 })).toHaveTextContent('La connexion Google a été annulée.')
})

test('a closed sign-up says so and cannot be submitted', async () => {
  mockAuthApi(signedOut({ signup_enabled: false }))
  renderAt('/sign-up?lang=fr', null)
  await screen.findByRole('heading', { level: 1, name: 'Créez votre compte' }, { timeout: 5000 })

  expect(screen.getByRole('button', { name: 'Créer mon compte' })).toBeDisabled()
  expect(screen.getByRole('alert')).toHaveTextContent('Les inscriptions sont fermées sur ce serveur.')
})

test('signed in, the sign-in page is skipped and the reader can sign out from the account menu', async () => {
  const calls = mockAuthApi(signedIn)
  renderAt('/sign-in?lang=fr&next=%2Farchive%3Flang%3Dfr', null)

  await waitFor(() => expect(window.location.pathname).toBe('/archive'), { timeout: 5000 })
  fireEvent.click(await screen.findByRole('button', { name: 'Menu du compte' }))
  expect(await screen.findByText('ada@example.com')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Se déconnecter' }))

  await waitForSignIn()
  expect(calls.some((call) => call.path === '/api/auth/sign-out' && call.method === 'POST')).toBe(true)
  expect(window.location.pathname).toBe('/sign-in')
})

test('a session that ends while the app is open sends the reader back to sign in', async () => {
  mockAuthApi(signedIn)
  renderAt('/?lang=fr', null)
  await screen.findByRole('heading', { level: 1, name: /6 octobre 2026/i }, { timeout: 5000 })

  vi.restoreAllMocks()
  mockAuthApi(signedOut())
  window.dispatchEvent(new Event('lucidnews:unauthorized'))

  await waitForSignIn()
})

test('without accounts the sign-in page does not exist: the app stays open', async () => {
  renderAt('/sign-in?lang=fr')
  await waitFor(() => expect(window.location.pathname).toBe('/'), { timeout: 5000 })
})
