import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { fixtures, mockApi, renderAt } from '../../test/render'

test('renders the edition by domain, with figures and reliability labels', async () => {
  const fetchMock = mockApi()
  renderAt('/?lang=fr')

  expect(await screen.findByRole('heading', { level: 1, name: /6 octobre 2026/i }, { timeout: 5000 })).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith('/api/editions/latest?lang=fr', expect.anything())

  const index = screen.getByRole('navigation', { name: 'Dans cette édition' })
  expect(
    within(index)
      .getAllByRole('link')
      .map((link) => link.textContent),
  ).toEqual(['IA / LLM / Agents5', 'Développement logiciel2', 'Cloud1', 'Data1', 'Cybersécurité3', 'Technologies émergentes1'])
  // Phones and tablets get the same index as one-tap chips.
  const jump = screen.getByRole('navigation', { name: 'Aller à un domaine' })
  expect(within(jump).getByRole('link', { name: /Cybersécurité/ })).toHaveAttribute('href', '#domain-cybersecurity')
  // One section per domain, in the taxonomy order; each news once, in its main domain, best score first.
  const ai = screen.getByRole('region', { name: 'IA / LLM / Agents' })
  expect(within(ai).getAllByRole('article')).toHaveLength(5)
  expect(within(ai).getByText('5 news')).toBeInTheDocument()
  expect(screen.getAllByRole('heading', { level: 2 }).map((heading) => heading.textContent)).toEqual(
    expect.arrayContaining(['IA / LLM / Agents', 'Développement logiciel', 'Cybersécurité', 'Technologies émergentes']),
  )
  expect(screen.getAllByRole('article')).toHaveLength(13)
  expect(screen.getByRole('link', { name: 'Sortie officielle de Polars 2.0' })).toHaveAttribute('href', 'https://pola.rs/posts/release-polars-2/')
  // Unconfirmed items carry an explicit warning, never a bare fact.
  expect(screen.getAllByText('Pas confirmé par une source officielle ou reconnue.').length).toBeGreaterThanOrEqual(2)
})

test('switches language and expands an item', async () => {
  mockApi()
  renderAt('/?lang=fr')
  await screen.findByRole('heading', { level: 1 })

  fireEvent.click(screen.getByRole('button', { name: 'en' }))
  expect(await screen.findByRole('heading', { level: 1, name: /6 October 2026/i })).toBeInTheDocument()
  expect(document.documentElement.lang).toBe('en')
  await screen.findByRole('link', { name: /Polars 2.0 Released/ })

  const first = screen.getAllByRole('article')[0]
  fireEvent.click(within(first).getByRole('button', { name: /details/i }))
  expect(within(first).getByRole('button', { name: /show less/i })).toHaveAttribute('aria-expanded', 'true')
  expect(within(first).getByRole('heading', { level: 4, name: 'Why now' })).toBeInTheDocument()
})

test('explains how to start the API when it is down', async () => {
  mockApi({}, 502)
  renderAt('/?lang=en')

  expect(await screen.findByRole('alert')).toHaveTextContent('uv run lucidnews-api')
})

test('files items the AI could not analyze under their source’s domain, plainly, only when the quota ran out', async () => {
  const base = fixtures.editionFr
  const raw = {
    ...base.sections[0].items[0],
    id: 'rss:test:raw',
    title: 'Titre brut non analysé',
    score: null,
    importance: null,
    summary: '',
    sections: [],
    categories: [],
    translated: false,
    ai_skipped: true,
    source_domain: 'ai',
    reliability: { ...base.sections[0].items[0].reliability, label: 'unverified' },
  }
  mockApi({
    edition: { ...base, selected_count: base.selected_count + 1, ai_limit: 'provider_quota', unanalyzed: [raw] },
  })
  renderAt('/?lang=fr')

  expect(await screen.findByText(/Le quota IA a été épuisé pendant ce run\./)).toHaveTextContent(
    '1 news est listée sans analyse, rangée d’après le domaine habituel de sa source.',
  )
  // Explained once, then listed plainly inside the domain its source usually covers.
  expect(screen.getByText(/ni résumé, ni score, ni vérification/)).toBeInTheDocument()
  const ai = screen.getByRole('region', { name: 'IA / LLM / Agents' })
  const section = within(ai).getByRole('region', { name: /Sans analyse IA · classées d’après leur source/ })
  expect(within(section).getByRole('link', { name: 'Titre brut non analysé' })).toBeInTheDocument()
  expect(within(section).queryByText('/10')).toBeNull()
  expect(within(ai).getByText('6 news')).toBeInTheDocument()
  // The 13 analyzed items stay in their sections; the raw one is not an article card.
  expect(screen.getAllByRole('article')).toHaveLength(13)
  expect(screen.getAllByText('contenus collectés').length).toBeGreaterThan(0)
  const index = screen.getByRole('navigation', { name: 'Dans cette édition' })
  expect(within(index).getByRole('link', { name: 'IA / LLM / Agents6' })).toHaveAttribute('href', '#domain-ai')
})

test('shows no quota notice on a normal edition', async () => {
  mockApi()
  renderAt('/?lang=fr')
  await screen.findByRole('heading', { level: 1 })

  expect(screen.queryByText(/quota IA/)).toBeNull()
  expect(screen.queryByRole('region', { name: /Sans analyse IA/ })).toBeNull()
})

test('an unanalyzed item whose source has no known domain goes under Other topics', async () => {
  const base = fixtures.editionFr
  const raw = { ...base.sections[0].items[0], id: 'raw', title: 'Titre sans domaine', score: null, categories: [], ai_skipped: true, source_domain: null }
  mockApi({ edition: { ...base, ai_limit: 'disabled', sections: [], unanalyzed: [raw] } })
  renderAt('/?lang=fr')

  const other = await screen.findByRole('region', { name: 'Autres sujets' }, { timeout: 5000 })
  expect(within(other).getByRole('link', { name: 'Titre sans domaine' })).toBeInTheDocument()
  expect(screen.queryAllByRole('article')).toHaveLength(0)
})

// --- Date filter ---------------------------------------------------------------------------

function mockPeriodApi(period: Record<string, unknown> = {}) {
  const spy = mockApi()
  const inner = spy.getMockImplementation()!
  spy.mockImplementation(async (input, init) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/editions/period') {
      return new Response(JSON.stringify({ ...fixtures.editionFr, id: 'period', edition_count: 8, analyzed_total: 13, ...period }))
    }
    return inner(input, init)
  })
  return spy
}

const periodCalls = (spy: ReturnType<typeof mockApi>) =>
  spy.mock.calls.map((call) => new URL(String(call[0]), 'http://localhost')).filter((url) => url.pathname === '/api/editions/period')

test('filters the news by month: all editions of the month, in one page', async () => {
  const spy = mockPeriodApi()
  renderAt('/?lang=fr')
  const filter = await screen.findByRole('region', { name: 'Filtrer par date' })
  expect(periodCalls(spy)).toHaveLength(0) // nothing is requested until a period is chosen

  fireEvent.click(within(filter).getByRole('button', { name: 'Mois' }))

  expect(await screen.findByRole('heading', { level: 1, name: 'Octobre 2026' })).toBeInTheDocument()
  expect(window.location.search).toContain('month=2026-10')
  expect(screen.getByText('8 éditions · 13 news')).toBeInTheDocument()
  const [call] = periodCalls(spy)
  // Local month boundaries, sent as instants.
  expect(new Date(call.searchParams.get('since')!).getTime()).toBe(new Date(2026, 9, 1).getTime())
  expect(new Date(call.searchParams.get('until')!).getTime()).toBe(new Date(2026, 10, 1).getTime())
  expect(screen.getAllByRole('article')).toHaveLength(13)
  // Items of a period do not link to a single edition.
  expect(screen.getAllByRole('link', { name: /Détails|Ouvrir/i }).every((link) => !link.getAttribute('href')?.includes('edition='))).toBe(true)
})

test('filters by year and by day, and goes back to the latest edition', async () => {
  const spy = mockPeriodApi()
  renderAt('/?lang=fr')
  const filter = await screen.findByRole('region', { name: 'Filtrer par date' })

  fireEvent.click(within(filter).getByRole('button', { name: 'Année' }))
  expect(await screen.findByRole('heading', { level: 1, name: '2026' })).toBeInTheDocument()
  expect(within(filter).getByRole('combobox', { name: 'Année' })).toHaveValue('2026')

  fireEvent.click(within(filter).getByRole('button', { name: 'Jour' }))
  expect(await screen.findByRole('heading', { level: 1, name: /Mardi 6 octobre 2026/i })).toBeInTheDocument()
  expect(window.location.search).toContain('day=2026-10-06')
  expect(window.location.search).not.toContain('year=')
  const last = periodCalls(spy).at(-1)!
  expect(new Date(last.searchParams.get('until')!).getTime() - new Date(last.searchParams.get('since')!).getTime()).toBeGreaterThan(0)

  fireEvent.click(within(filter).getByRole('button', { name: 'Dernière édition' }))
  expect(await screen.findByText(/Édition du jour/)).toBeInTheDocument()
  expect(window.location.search).not.toMatch(/day=|month=|year=/)
})

test('a period without any edition says so', async () => {
  mockPeriodApi({ edition_count: 0, selected_count: 0, sections: [], unanalyzed: [], analyzed_total: 0 })
  renderAt('/?lang=fr&month=2020-01')
  expect(await screen.findByText('Aucune édition n’a été publiée sur cette période.')).toBeInTheDocument()
})

test('a malformed period in the address is ignored', async () => {
  const spy = mockPeriodApi()
  renderAt('/?lang=fr&month=2026-13')
  expect(await screen.findByRole('heading', { level: 1, name: /6 octobre 2026/i })).toBeInTheDocument()
  expect(periodCalls(spy)).toHaveLength(0)
})

test('shows every news of a long period, with no limit', async () => {
  const base = fixtures.editionFr
  const items = Array.from({ length: 120 }, (_, index) => ({ ...base.sections[0].items[0], id: `bulk-${index}` }))
  mockPeriodApi({ sections: [{ ...base.sections[0], items }] })
  renderAt('/?lang=fr&year=2026')

  expect(await screen.findByText('8 éditions · 120 news', {}, { timeout: 8000 })).toBeInTheDocument()
  expect(screen.getAllByRole('article')).toHaveLength(120)
  expect(screen.queryByText(/mieux notées/)).not.toBeInTheDocument()
}, 15000)

// --- Domain filter ---------------------------------------------------------------------------

test('filters the news by domain, next to the date filter', async () => {
  mockApi()
  renderAt('/?lang=fr')
  const filter = await screen.findByRole('region', { name: 'Filtrer par date' }, { timeout: 5000 })
  await screen.findAllByRole('article')
  const select = within(filter).getByRole('combobox', { name: 'Domaine' })

  // The counts come from the news on screen (5 of the 13 are about AI).
  expect(within(select).getByRole('option', { name: 'IA / LLM / Agents (5)' })).toBeInTheDocument()
  expect(within(select).getByRole('option', { name: 'Bases de données (0)' })).toBeDisabled()

  fireEvent.change(select, { target: { value: 'ai' } })

  await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(5))
  expect(window.location.search).toContain('domain=ai')
  const index = screen.getByRole('navigation', { name: 'Dans cette édition' })
  expect(
    within(index)
      .getAllByRole('link')
      .every((link) => /\d+$/.test(link.textContent ?? '')),
  ).toBe(true)

  fireEvent.change(select, { target: { value: '' } })
  await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(13))
  expect(window.location.search).not.toContain('domain')
})

test('the domain filter works inside a period and ignores an unknown domain', async () => {
  mockPeriodApi()
  renderAt('/?lang=fr&month=2026-10&domain=cybersecurity')
  expect(await screen.findByText('8 éditions · 3 news', {}, { timeout: 5000 })).toBeInTheDocument()
  expect(screen.getAllByRole('article')).toHaveLength(3)

  mockApi()
  renderAt('/?lang=fr&domain=not-a-domain')
  await waitFor(() => expect(screen.getAllByRole('article').length).toBeGreaterThanOrEqual(13))
})

test('says when a domain has no news, and how unanalyzed news are filed', async () => {
  const base = fixtures.editionFr
  mockApi({ edition: { ...base, unanalyzed: [{ ...base.sections[0].items[0], id: 'u1', categories: [] }] } })
  renderAt('/?lang=fr&domain=databases')

  expect(await screen.findByText('Aucune news dans ce domaine sur cette période.', {}, { timeout: 5000 })).toBeInTheDocument()
  expect(screen.getByText(/rangées d’après le domaine habituel de leur source/)).toBeInTheDocument()
})
