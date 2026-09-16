import { useState } from 'react'
import { SearchIcon } from '../components/Icons'
import { categoryOf, countByCategory } from '../components/format'
import { useApi, useDebounced } from '../hooks/useApi'

// Details of one EIA dataset, loaded when its row is opened.
function CatalogueEntry({ route, onAsk }) {
  const entry = useApi(`/catalogue/${route}`)
  if (entry.loading) return <p className="muted small">Loading details…</p>
  if (entry.error) return <p className="error small">{entry.error.message}</p>
  const e = entry.data

  return (
    <div className="entry">
      <p className="entry-description">{e.description}</p>
      <div className="entry-grid">
        <div>
          <div className="label">Metrics</div>
          <ul className="plain-list">
            {e.metrics.map((m) => (
              <li key={m.id}>
                <span className="mono accent">{m.id}</span>
                {m.units && <span className="muted"> · {m.units}</span>}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <div className="label">Filters</div>
          <ul className="plain-list">
            {e.facets.map((f) => (
              <li key={f.id}>
                <span className="mono">{f.id}</span>
                {f.description && <span className="muted"> · {f.description}</span>}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <div className="label">Frequency</div>
          <div>{e.frequencies.join(' · ')}</div>
          <div className="label spaced">Coverage</div>
          <div className="mono">
            {e.start_period} → {e.end_period}
          </div>
        </div>
      </div>
      <button
        type="button"
        className="button-primary"
        onClick={() => onAsk(`Show me an overview chart from the EIA dataset ${e.route} (${e.name}).`)}
      >
        Ask about this dataset
      </button>
    </div>
  )
}

// The Catalogue: every dataset the EIA API serves, searchable.
export default function CatalogueScreen({ onAsk }) {
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState(null)
  const [openRoute, setOpenRoute] = useState(null)
  const query = useDebounced(search.trim())
  const catalogue = useApi(`/catalogue?limit=250${query ? `&q=${encodeURIComponent(query)}` : ''}`)

  const items = catalogue.data ?? []
  const categories = countByCategory(items, (item) => item.route)
  const shown = category ? items.filter((item) => categoryOf(item.route) === category) : items
  const categoryStillPresent = !category || categories.some((c) => c.id === category)

  return (
    <main className="screen">
      <header className="screen-head">
        <div>
          <h1>Catalogue</h1>
          <p className="lede">Every dataset the EIA API serves, indexed so you and the agent can find them.</p>
        </div>
        <label className="search wide">
          <SearchIcon size={16} />
          <span className="visually-hidden">Search catalogue</span>
          <input
            type="search"
            placeholder="nuclear outages, crude imports, state CO2…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
      </header>

      <div className="catalogue-layout">
        <nav className="category-list" aria-label="Categories">
          <button
            type="button"
            className={category === null ? 'category active' : 'category'}
            onClick={() => setCategory(null)}
          >
            <span>All</span>
            <span className="mono muted">{items.length}</span>
          </button>
          {categories.map((c) => (
            <button
              key={c.id}
              type="button"
              className={category === c.id ? 'category active' : 'category'}
              onClick={() => setCategory(c.id)}
            >
              <span>{c.name}</span>
              <span className="mono muted">{c.count}</span>
            </button>
          ))}
        </nav>

        <div className="route-list">
          {catalogue.loading && <p className="muted">Loading…</p>}
          {catalogue.error && <p className="error">Couldn't load the catalogue: {catalogue.error.message}</p>}
          {catalogue.data && items.length === 0 && (
            <p className="muted">No datasets match “{query}”. Try EIA's words: “retail sales”, “rto”, “seds”.</p>
          )}
          {!categoryStillPresent && (
            <p className="muted">
              No matches in this category.{' '}
              <button type="button" className="link-button inline" onClick={() => setCategory(null)}>
                Show all
              </button>
            </p>
          )}

          {shown.map((item) => {
            const open = openRoute === item.route
            return (
              <div key={item.route} className={open ? 'route open' : 'route'}>
                <button
                  type="button"
                  className="route-row"
                  aria-expanded={open}
                  onClick={() => setOpenRoute(open ? null : item.route)}
                >
                  <span className="route-name">
                    <span>{item.name}</span>
                    <span className="mono accent">{item.route}</span>
                  </span>
                  <span className="mono muted route-metrics">{item.metrics.slice(0, 3).join(' · ')}</span>
                  <span className="small muted route-freq">{item.frequencies.join(' · ')}</span>
                  <span className="small muted route-coverage">{item.coverage}</span>
                </button>
                {open && <CatalogueEntry route={item.route} onAsk={onAsk} />}
              </div>
            )
          })}
        </div>
      </div>
    </main>
  )
}
