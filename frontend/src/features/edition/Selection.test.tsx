import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { vi } from 'vitest'
import { fixtures, mockApi, renderAt } from '../../test/render'

const user = { id: 'u1', email: 'ada@example.com', name: 'Ada', picture: null, has_password: true, has_google: false, role: 'reader' }
const session = { enabled: true, authenticated: true, user, signup_enabled: false, providers: { google: false } }
const everything = { domains: [], min_importance: null, include_unconfirmed: true, detail_level: 'complete' }

/** A signed-in reader whose saved preferences are ``preferences``. */
function mockReader(preferences: Record<string, unknown>) {
  const state = { preferences: { ...everything, ...preferences }, filters: false, updated_at: '2026-10-17T10:00:00Z' }
  const p = state.preferences
  state.filters = p.domains.length > 0 || p.min_importance !== null || !p.include_unconfirmed
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const path = new URL(String(input), 'http://localhost').pathname
    const reply = (body: unknown) => new Response(JSON.stringify(body), { status: 200 })
    if (path === '/api/auth/session') return reply(session)
    if (path === '/api/auth/account/preferences') return reply(state)
    if (path === '/api/editions') return reply(fixtures.editions)
    if (path.startsWith('/api/editions/')) return reply(fixtures.editionFr)
    return new Response(JSON.stringify({ error: 'not found' }), { status: 404 })
  })
}

const bar = () => screen.findByRole('complementary', { name: 'Ma sélection' }, { timeout: 5000 })

test('a reader with preferences sees their selection first, and can switch to everything', async () => {
  mockReader({ domains: ['ai'], include_unconfirmed: false })
  renderAt('/?lang=fr', null)

  const selection = await bar()
  expect(within(selection).getByRole('list', { name: 'Ce que garde votre sélection' })).toHaveTextContent('IA / LLM / Agents')
  expect(within(selection).getByText('Confirmées et fiables seulement')).toBeInTheDocument()
  await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(4))
  expect(within(selection).getByRole('link', { name: 'Régler ma veille' })).toHaveAttribute('href', '/account?lang=fr#my-watch')

  fireEvent.click(within(selection).getByRole('button', { name: 'Tout' }))
  await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(13))
  expect(window.location.search).toContain('view=all')
})

test('an empty selection says so and offers the whole edition', async () => {
  mockReader({ domains: ['databases'] })
  renderAt('/?lang=fr', null)

  expect(await screen.findByText('Rien dans votre sélection aujourd’hui', {}, { timeout: 5000 })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Voir toute l’édition' }))
  await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(13))
})

test('before any preference, an invitation; brief cards do not unfold', async () => {
  mockReader({ detail_level: 'brief' })
  renderAt('/?lang=fr', null)

  const invite = await bar()
  expect(within(invite).getByRole('link', { name: /Choisir mes domaines/ })).toHaveAttribute('href', '/account?lang=fr#my-watch')
  await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(13))
  const first = screen.getAllByRole('article')[0]!
  expect(within(first).queryByRole('button', { name: /Détails/ })).toBeNull()
  expect(within(first).getByRole('link', { name: /Fiche complète/ })).toBeInTheDocument()
})

test('without accounts there is no selection bar', async () => {
  mockApi()
  renderAt('/?lang=fr')
  await screen.findAllByRole('article', {}, { timeout: 5000 })
  expect(screen.queryByRole('complementary', { name: 'Ma sélection' })).toBeNull()
})
