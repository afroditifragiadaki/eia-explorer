// Small helpers shared by several screens.

const CATEGORY_NAMES = {
  petroleum: 'Petroleum',
  'natural-gas': 'Natural gas',
  electricity: 'Electricity',
  aeo: 'Annual Energy Outlook',
  coal: 'Coal',
  'densified-biomass': 'Densified biomass',
  ieo: 'International Energy Outlook',
  'nuclear-outages': 'Nuclear outages',
  'co2-emissions': 'CO₂ emissions',
  'crude-oil-imports': 'Crude oil imports',
  international: 'International',
  seds: 'State energy (SEDS)',
  steo: 'Short-term outlook (STEO)',
  'total-energy': 'Total energy',
}

// "electricity/retail-sales" → "electricity"
export const categoryOf = (route) => route.split('/')[0]

// "natural-gas" → "Natural gas"
export const categoryName = (id) => CATEGORY_NAMES[id] ?? id

// Group items by category: [{ id, name, count }], biggest first.
export function countByCategory(items, routeOf) {
  const counts = new Map()
  for (const item of items) {
    const id = categoryOf(routeOf(item))
    counts.set(id, (counts.get(id) ?? 0) + 1)
  }
  return [...counts.entries()]
    .map(([id, count]) => ({ id, name: categoryName(id), count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
}

// "2026-09-16T21:09:59+00:00" → "16 Sep 2026, 22:09" (in the viewer's time zone)
export function formatDateTime(iso) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

// The EIA API request a saved dataset came from, as readable lines.
export function eiaRequestLines(query) {
  const lines = [`GET /v2/${query.route}/data/`]
  const params = []
  if (query.frequency) params.push(`frequency=${query.frequency}`)
  query.data.forEach((column, i) => params.push(`data[${i}]=${column}`))
  for (const [facet, values] of Object.entries(query.facets ?? {})) {
    for (const value of values) params.push(`facets[${facet}][]=${value}`)
  }
  if (query.start) params.push(`start=${query.start}`)
  if (query.end) params.push(`end=${query.end}`)
  params.forEach((p, i) => lines.push(`  ${i === 0 ? '?' : '&'}${p}`))
  return lines.join('\n')
}
