import { safeNext, withLanguage } from './auth'

test('the page reached after signing in keeps the language of the sign-in page', () => {
  expect(withLanguage('/', 'fr')).toBe('/?lang=fr')
  expect(withLanguage('/archive?q=rust#top', 'fr')).toBe('/archive?q=rust&lang=fr#top')
  expect(withLanguage('/settings?lang=en', 'fr')).toBe('/settings?lang=en') // an explicit choice wins
  expect(withLanguage(safeNext('//evil.example'), 'fr')).toBe('/?lang=fr')
})
