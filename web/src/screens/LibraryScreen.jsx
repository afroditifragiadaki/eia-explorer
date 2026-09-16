import { useState } from 'react'
import { SearchIcon } from '../components/Icons'
import { categoryName, categoryOf, countByCategory, formatDateTime } from '../components/format'
import { useApi, useDebounced } from '../hooks/useApi'
import DatasetView from './DatasetView'

// The Library: every dataset the agent has saved. Click one to open it.
// `openId` / `onOpen` come from App, so other screens can open a dataset too.
export default function LibraryScreen({ openId, onOpen, refreshKey }) {
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState(null) // null = all
  const query = useDebounced(search.trim())
  const library = useApi(`/library${query ? `?contains=${encodeURIComponent(query)}` : ''}`, refreshKey)

  if (openId) {
    return (
      <main className="screen">
        {/* `key` makes React start a fresh DatasetView for each dataset. */}
        <DatasetView key={openId} id={openId} onBack={() => onOpen(null)} />
      </main>
    )
  }

  const items = library.data ?? []
  const categories = countByCategory(items, (item) => item.route)
  const shown = category ? items.filter((item) => categoryOf(item.route) === category) : items

  return (
    <main className="screen">
      <header className="screen-head">
        <div>
          <h1>Library</h1>
          <p className="lede">Every dataset the agent has downloaded, stored in Turso and ready to reuse.</p>
        </div>
        <label className="search">
          <SearchIcon size={16} />
          <span className="visually-hidden">Search library</span>
          <input
            type="search"
            placeholder="Search by title"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
      </header>

      <div className="filter-row" role="group" aria-label="Category">
        <button
          type="button"
          className={category === null ? 'pill active' : 'pill'}
          aria-pressed={category === null}
          onClick={() => setCategory(null)}
        >
          All · {items.length}
        </button>
        {categories.map((c) => (
          <button
            key={c.id}
            type="button"
            className={category === c.id ? 'pill active' : 'pill'}
            aria-pressed={category === c.id}
            onClick={() => setCategory(c.id)}
          >
            {c.name} · {c.count}
          </button>
        ))}
      </div>

      {library.loading && <p className="muted">Loading…</p>}
      {library.error && <p className="error">Couldn't load the library: {library.error.message}</p>}
      {library.data && shown.length === 0 && (
        <p className="muted">{query ? `Nothing saved matches “${query}”.` : 'Nothing saved yet. Ask a question!'}</p>
      )}

      <div className="card-grid">
        {shown.map((item) => (
          <button key={item.id} type="button" className="card" onClick={() => onOpen(item.id)}>
            <span className="tag">{categoryName(categoryOf(item.route))}</span>
            <span className="card-title">{item.title}</span>
            <span className="mono accent">{item.route}</span>
            <span className="card-foot">
              <span className="mono">{item.rows.toLocaleString()} rows</span>
              <span className="muted small">{formatDateTime(item.fetched_at)}</span>
            </span>
          </button>
        ))}
      </div>
    </main>
  )
}
