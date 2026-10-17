import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { vi } from 'vitest'
import { renderAt } from '../../test/render'

const user = { id: 'u1', email: 'ada@example.com', name: 'Ada', picture: null, has_password: true, has_google: false, role: 'reader' }
const session = { enabled: true, authenticated: true, user, signup_enabled: false, providers: { google: false } }
const sessions = [
  {
    id: 'aaaaaaaaaaaaaaaa',
    created_at: '2026-10-01T08:00:00Z',
    last_seen_at: '2026-10-17T08:00:00Z',
    expires_at: '2026-11-16T08:00:00Z',
    device: 'Firefox · macOS',
    current: true,
  },
  {
    id: 'bbbbbbbbbbbbbbbb',
    created_at: '2026-10-05T08:00:00Z',
    last_seen_at: '2026-10-16T08:00:00Z',
    expires_at: '2026-11-15T08:00:00Z',
    device: 'Chrome · Android',
    current: false,
  },
]
type Call = { method: string; path: string; body: unknown }

/** The account API with its real shapes; replies can be forced per route. */
function mockAccountApi(replies: Record<string, [number, unknown]> = {}, account: Record<string, unknown> = {}) {
  let state = { user, sessions, can_delete: true, session_days: 30, ...account }
  let current: unknown = session
  const calls: Call[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const path = new URL(String(input), 'http://localhost').pathname
    const method = init?.method ?? 'GET'
    const body = init?.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ method, path, body })
    const reply = (status: number, value: unknown) => new Response(JSON.stringify(value), { status })
    const forced = replies[`${method} ${path}`]
    if (forced) return reply(...forced)
    if (path === '/api/auth/session') return reply(200, current)
    if (path === '/api/auth/account' && method === 'PUT') state = { ...state, user: { ...state.user, name: body.name } }
    if (path === '/api/auth/account/sessions/bbbbbbbbbbbbbbbb') state = { ...state, sessions: sessions.slice(0, 1) }
    if (path === '/api/auth/account/delete') {
      current = { ...session, authenticated: false, user: null }
      return reply(200, current)
    }
    if (path.startsWith('/api/auth/account')) return reply(200, state)
    if (path.startsWith('/api/editions')) return reply(200, { editions: [] })
    return reply(404, { error: 'not found' })
  })
  return calls
}

const open = async () => screen.findByRole('heading', { level: 1, name: 'Mon compte' }, { timeout: 5000 })
const fill = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } })

test('shows the profile, the role and the open sessions', async () => {
  mockAccountApi()
  renderAt('/account?lang=fr', null)
  await open()

  expect(screen.getAllByText('ada@example.com').length).toBeGreaterThan(0)
  expect(screen.getByText('Lecteur')).toBeInTheDocument()
  const devices = within(screen.getByRole('region', { name: 'Appareils connectés' }))
  expect(devices.getByText('Firefox · macOS')).toBeInTheDocument()
  expect(devices.getByText('Cet appareil')).toBeInTheDocument()
  expect(devices.getByText(/30 jours/)).toBeInTheDocument()
})

test('renames the account', async () => {
  const calls = mockAccountApi()
  renderAt('/account?lang=fr', null)
  await open()

  fill('Nom', 'Ada Lovelace')
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
  await screen.findByRole('button', { name: 'Enregistré' })
  expect(calls.find((call) => call.method === 'PUT')?.body).toEqual({ name: 'Ada Lovelace' })
})

test('changes the password with the current one, and explains a wrong one', async () => {
  const calls = mockAccountApi({ 'POST /api/auth/account/password': [401, { error: 'x', code: 'wrong_password' }] })
  renderAt('/account?lang=fr', null)
  await open()
  const submit = screen.getByRole('button', { name: 'Changer le mot de passe' })
  expect(submit).toBeDisabled()

  fill('Mot de passe actuel', 'old password')
  fill('Nouveau mot de passe', 'a new long password')
  fill('Répétez le nouveau mot de passe', 'a different one')
  expect(screen.getByText('Les deux mots de passe sont différents.')).toBeInTheDocument()
  expect(submit).toBeDisabled()

  fill('Répétez le nouveau mot de passe', 'a new long password')
  fireEvent.click(submit)
  expect(await screen.findByText('Le mot de passe actuel est incorrect.')).toBeInTheDocument()
  expect(calls.find((call) => call.path.endsWith('/password'))?.body).toEqual({ current: 'old password', password: 'a new long password' })
})

test('signs out another device', async () => {
  const calls = mockAccountApi()
  renderAt('/account?lang=fr', null)
  await open()

  const devices = within(screen.getByRole('region', { name: 'Appareils connectés' }))
  fireEvent.click(devices.getByRole('button', { name: 'Déconnecter' }))
  await waitFor(() => expect(devices.queryByText('Chrome · Android')).toBeNull())
  expect(calls.some((call) => call.method === 'DELETE' && call.path.endsWith('/bbbbbbbbbbbbbbbb'))).toBe(true)
})

test('deletes the account after the password, then leaves for the sign-in page', async () => {
  const calls = mockAccountApi()
  renderAt('/account?lang=fr', null)
  await open()

  fireEvent.click(screen.getByRole('button', { name: 'Supprimer mon compte' }))
  const dialog = await screen.findByRole('alertdialog')
  fireEvent.change(within(dialog).getByLabelText('Votre mot de passe, pour confirmer'), { target: { value: 'my password' } })
  fireEvent.click(within(dialog).getByRole('button', { name: 'Supprimer définitivement' }))

  await waitFor(() => expect(window.location.pathname).toBe('/sign-in'), { timeout: 5000 })
  expect(calls.find((call) => call.path.endsWith('/delete'))?.body).toEqual({ current: 'my password' })
})

test('the last administrator is told why they cannot delete their account', async () => {
  mockAccountApi({}, { user: { ...user, role: 'admin' }, can_delete: false })
  renderAt('/account?lang=fr', null)
  await open()

  expect(screen.getByText(/Vous êtes le dernier administrateur/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Supprimer mon compte' })).toBeNull()
})

test('without accounts the page does not exist', async () => {
  renderAt('/account?lang=fr')
  await waitFor(() => expect(window.location.pathname).toBe('/'))
})
