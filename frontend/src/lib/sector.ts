import { useQuery } from '@tanstack/react-query'
import { domainCategories, fetchSector, type SectorState } from './api'
import { registerCategoryLabels } from './i18n'

export const SECTOR_KEY = ['sector'] as const

async function loadSector(signal?: AbortSignal): Promise<SectorState> {
  const state = await fetchSector(signal)
  registerCategoryLabels(state.sector.categories) // before the first render that uses them
  return state
}

/** The installation's sector, as the server says (it changes only from Settings). */
export function useSector() {
  return useQuery({ queryKey: SECTOR_KEY, queryFn: ({ signal }) => loadSector(signal), staleTime: 5 * 60_000 })
}

/** The categories the edition, the filters and the reader's watch are built on. Until the server
 * has answered, the default sector's (tech), which is also what an older server serves. */
export function useDomainCategories(): readonly string[] {
  const { data } = useSector()
  return data ? data.sector.categories.map((category) => category.id) : domainCategories
}
