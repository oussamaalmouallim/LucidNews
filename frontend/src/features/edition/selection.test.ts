import type { Edition, ReaderPreferences } from '../../lib/api'
import { fixtures } from '../../test/render'
import { groupByDomain } from './domains'
import { applySelection, keepsUnanalyzed } from './selection'

const edition = { unanalyzed: [], ...fixtures.editionFr } as unknown as Edition
const prefs = (overrides: Partial<ReaderPreferences> = {}): ReaderPreferences => ({
  domains: [],
  min_importance: null,
  include_unconfirmed: true,
  detail_level: 'complete',
  ...overrides,
})
const ids = (e: Edition) => e.sections.flatMap((section) => section.items.map((item) => item.id))

test('no preference keeps the whole edition', () => {
  expect(ids(applySelection(edition, prefs()))).toEqual(ids(edition))
})

test('domains, importance and trust narrow the selection', () => {
  expect(ids(applySelection(edition, prefs({ domains: ['ai'] })))).toHaveLength(5)
  expect(ids(applySelection(edition, prefs({ domains: ['ai'], include_unconfirmed: false })))).toHaveLength(4)
  expect(ids(applySelection(edition, prefs({ domains: ['ai'], min_importance: 'high' })))).toHaveLength(4)
  expect(ids(applySelection(edition, prefs({ domains: ['ai'], min_importance: 'critical' })))).toHaveLength(1)
  expect(applySelection(edition, prefs({ domains: ['databases'] })).selected_count).toBe(0)
})

test('a news goes under the first of its domains the reader follows', () => {
  const mine = applySelection(edition, prefs({ domains: ['open-source'] }))
  const groups = groupByDomain(mine, null, ['open-source'])
  expect(groups.map((group) => [group.key, group.items.length])).toEqual([['open-source', 5]])
})

test('a news the AI did not analyze is kept only when nothing asks for importance or trust', () => {
  const raw = { ...edition.sections[0]!.items[0]!, categories: [], importance: null, source_domain: 'ai' }
  expect(keepsUnanalyzed(raw, prefs({ domains: ['ai'] }))).toBe(true)
  expect(keepsUnanalyzed(raw, prefs({ domains: ['cloud'] }))).toBe(false)
  expect(keepsUnanalyzed(raw, prefs({ include_unconfirmed: false }))).toBe(false)
  expect(keepsUnanalyzed(raw, prefs({ min_importance: 'low' }))).toBe(false)
})
