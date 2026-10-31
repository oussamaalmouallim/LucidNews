import { fireEvent, screen, within } from '@testing-library/react'
import { vi } from 'vitest'
import { renderAt } from '../../test/render'
import settingsFixture from '../../test/fixtures/settings.json'
import { categoryLabel } from '../../lib/i18n'

const tech = { id: 'tech', labels: { en: 'Technology & IT', fr: 'Tech et IT' }, descriptions: { en: 'IT.', fr: 'L’IT.' } }
const fake = { id: 'fake', labels: { en: 'Fake sector', fr: 'Secteur factice' }, descriptions: { en: 'Tests.', fr: 'Pour les tests.' } }
const state = (current: typeof tech, categories: { id: string; labels: Record<string, string> }[]) => ({
  sector: { ...current, categories },
  sectors: [tech, fake],
})

function mockApi() {
  const calls: { method: string; path: string; body: unknown }[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const path = new URL(String(input), 'http://localhost').pathname
    const method = init?.method ?? 'GET'
    const body = init?.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ method, path, body })
    const reply = (payload: unknown, status = 200) => new Response(JSON.stringify(payload), { status })
    if (path === '/api/sector') return reply(state(tech, [{ id: 'ai', labels: { en: 'AI', fr: 'IA' } }]))
    if (path === '/api/settings/sector') return reply(state(fake, [{ id: 'fake-markets', labels: { en: 'Markets', fr: 'Marchés' } }]))
    if (path === '/api/settings') return reply(settingsFixture)
    if (path === '/api/settings/backups') return reply({ backups: [] })
    if (path === '/api/secrets') return reply({ secrets: [] })
    return reply({ error: 'not found' }, 404)
  })
  return calls
}

test('the administrator sees the current sector and switches after confirming', async () => {
  const calls = mockApi()
  renderAt('/settings?lang=fr')
  const card = within(await screen.findByRole('region', { name: 'Ce que couvre la veille' }, { timeout: 5000 }))
  expect(await card.findByText('Actuel')).toBeInTheDocument()
  expect(card.getByText('Tech et IT')).toBeInTheDocument()

  fireEvent.click(card.getByRole('button', { name: 'Passer à ce secteur' }))
  const dialog = await screen.findByRole('alertdialog')
  expect(within(dialog).getByText('Passer la veille en « Secteur factice » ?')).toBeInTheDocument()
  fireEvent.click(within(dialog).getByRole('button', { name: 'Changer' }))

  expect(await card.findByText('La veille couvre maintenant « Secteur factice ».')).toBeInTheDocument()
  expect(calls.find((call) => call.method === 'PUT' && call.path === '/api/settings/sector')?.body).toEqual({ sector: 'fake' })
  expect(categoryLabel('fr', 'fake-markets')).toBe('Marchés') // the new sector's names are known at once
})

test('nothing is changed when the administrator keeps the current sector', async () => {
  const calls = mockApi()
  renderAt('/settings?lang=fr')
  const card = within(await screen.findByRole('region', { name: 'Ce que couvre la veille' }, { timeout: 5000 }))
  fireEvent.click(await card.findByRole('button', { name: 'Passer à ce secteur' }))
  fireEvent.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Garder le secteur actuel' }))
  expect(calls.some((call) => call.path === '/api/settings/sector')).toBe(false)
})
