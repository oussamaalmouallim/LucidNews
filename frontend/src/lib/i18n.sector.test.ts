import { en, fr } from './i18n'

// Chantier « Nouveaux secteurs », lot 1.7: outside the names of the sectors and of the categories,
// no interface text says the watch is about tech or IT.
const SECTOR_WORDS = /\b(IT|tech|Tech)\b/

test('no interface text names the tech sector, in any language', () => {
  for (const dictionary of [en, fr] as Record<string, string>[]) {
    const offenders = Object.entries(dictionary).filter(([key, text]) => !key.startsWith('category.') && !key.startsWith('sector.') && SECTOR_WORDS.test(text))
    expect(offenders).toEqual([])
  }
})
