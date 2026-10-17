import { screen, within } from '@testing-library/react'
import { mockApi, noAccounts, renderAt } from '../test/render'

const account = (role: 'admin' | 'reader') => ({
  enabled: true,
  authenticated: true,
  user: { id: 'u1', email: 'ada@example.com', name: 'Ada', picture: null, has_password: true, has_google: false, role },
  signup_enabled: false,
  providers: { google: false },
})

const navLinks = async () => {
  const [nav] = await screen.findAllByRole('navigation', { name: 'Navigation principale' }, { timeout: 5000 })
  return within(nav!)
    .getAllByRole('link')
    .map((link) => link.textContent)
}

test('a reader sees only the news in the navigation', async () => {
  mockApi()
  renderAt('/archive?lang=fr', account('reader'))

  expect(await navLinks()).toEqual(['Édition', 'Archives'])
})

test('a reader who opens an administration screen gets an explanation, and no admin data is requested', async () => {
  const fetch = mockApi()
  renderAt('/settings?lang=fr', account('reader'))

  expect(await screen.findByRole('heading', { name: 'Réservé à l’administration' }, { timeout: 5000 })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Revenir à l’édition/ })).toHaveAttribute('href', '/?lang=fr')
  const paths = fetch.mock.calls.map(([input]) => new URL(String(input), 'http://localhost').pathname)
  expect(paths.some((path) => path.startsWith('/api/settings'))).toBe(false)
})

test('an administrator, or the operator without accounts, sees every screen', async () => {
  mockApi()
  const all = ['Édition', 'Archives', 'Sources', 'Préférences', 'Qualité', 'Réglages']
  const { unmount } = renderAt('/archive?lang=fr', account('admin'))
  expect(await navLinks()).toEqual(all)
  unmount()

  renderAt('/archive?lang=fr', noAccounts)
  expect(await navLinks()).toEqual(all)
})
