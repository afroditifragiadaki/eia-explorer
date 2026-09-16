import { useApi } from '../hooks/useApi'
import { AskIcon, CatalogueIcon, LibraryIcon, PlusIcon } from './Icons'

const NAV_ITEMS = [
  { id: 'ask', label: 'Ask', Icon: AskIcon, countKey: null },
  { id: 'library', label: 'Library', Icon: LibraryIcon, countKey: 'library_datasets' },
  { id: 'catalogue', label: 'Catalogue', Icon: CatalogueIcon, countKey: 'catalogue_datasets' },
]

// The left rail. `screen` is the screen being shown; `onNavigate(id)` asks
// App to show another one. Both come from App (they are "props").
export default function Sidebar({ screen, onNavigate }) {
  const stats = useApi('/stats') // → { catalogue_datasets, library_datasets }
  const health = useApi('/health') // → { status, storage }

  return (
    <nav className="rail" aria-label="Primary">
      <button type="button" className="wordmark" onClick={() => onNavigate('ask')}>
        <span>eia</span>
        <em>explorer</em>
      </button>

      <button type="button" className="new-question" onClick={() => onNavigate('ask')}>
        <PlusIcon size={16} />
        New question
      </button>

      <div className="nav-list">
        {NAV_ITEMS.map(({ id, label, Icon, countKey }) => (
          <button
            key={id}
            type="button"
            className={screen === id ? 'nav-item active' : 'nav-item'}
            aria-current={screen === id ? 'page' : undefined}
            onClick={() => onNavigate(id)}
          >
            <Icon />
            {label}
            {countKey && <span className="count">{stats.data ? stats.data[countKey] : '…'}</span>}
          </button>
        ))}
      </div>

      <div className="rail-status">
        <div>
          <span className={health.error ? 'dot dot-down' : health.loading ? 'dot dot-wait' : 'dot'} />
          {health.error
            ? 'API offline'
            : health.loading
              ? 'Connecting…'
              : `${health.data.storage === 'turso' ? 'Turso' : 'Local SQLite'} · connected`}
        </div>
        <div>Data: U.S. Energy Information Administration</div>
      </div>
    </nav>
  )
}
