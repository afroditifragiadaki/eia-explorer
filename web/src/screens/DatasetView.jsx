import { useMemo, useState } from 'react'
import { withQuery } from '../api'
import Chart from '../components/LazyChart'
import DatasetDetails from '../components/DatasetDetails'
import { useApi } from '../hooks/useApi'

const KINDS = [
  { id: 'line', label: 'Line' },
  { id: 'area', label: 'Area' },
  { id: 'bar', label: 'Bar' },
  { id: 'seasonal', label: 'Seasonal' },
  { id: 'latest_bar', label: 'Latest' },
]

// One saved dataset: chart with controls, details, downloads.
export default function DatasetView({ id, onBack }) {
  const dataset = useApi(`/datasets/${id}`)
  const [kind, setKind] = useState('line')
  const [metric, setMetric] = useState(null) // null = the first metric
  const [hidden, setHidden] = useState([]) // series the user switched off

  const d = dataset.data
  const activeMetric = metric ?? d?.metrics[0] ?? null

  // Series that exist for the chosen metric. useMemo: only recompute when
  // the data or metric changes, not on every redraw.
  const seriesNames = useMemo(() => {
    if (!d) return []
    const names = new Set(d.observations.filter((o) => o.metric === activeMetric).map((o) => o.series))
    return [...names].sort()
  }, [d, activeMetric])

  const visible = seriesNames.filter((name) => !hidden.includes(name))
  const chartPath = d
    ? withQuery(`/datasets/${id}/chart`, {
        kind,
        metric: activeMetric,
        // Only send a series filter when some are switched off.
        series: hidden.length ? visible : null,
      })
    : null
  const chart = useApi(visible.length ? chartPath : null)

  function toggleSeries(name) {
    setHidden((prev) => (prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]))
  }

  if (dataset.loading) return <p className="muted">Loading dataset…</p>
  if (dataset.error) return <p className="error">Couldn't load this dataset: {dataset.error.message}</p>

  const units = d.observations.find((o) => o.metric === activeMetric)?.units

  return (
    <div className="dataset-view">
      <button type="button" className="link-button back" onClick={onBack}>
        ← All datasets
      </button>

      <header className="dataset-head">
        <h1>{d.title}</h1>
        <span className="mono accent">{d.route}</span>
      </header>

      <div className="dataset-layout">
        <section className="panel chart-panel">
          <div className="chart-toolbar">
            {d.metrics.length > 1 && (
              <label className="select">
                <span className="visually-hidden">Metric</span>
                <select
                  value={activeMetric}
                  onChange={(e) => {
                    setMetric(e.target.value)
                    setHidden([])
                  }}
                >
                  {d.metrics.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {units && <span className="muted small">{units}</span>}
            <div className="segmented" role="group" aria-label="Chart type">
              {KINDS.map((k) => (
                <button
                  key={k.id}
                  type="button"
                  aria-pressed={kind === k.id}
                  className={kind === k.id ? 'active' : ''}
                  onClick={() => setKind(k.id)}
                >
                  {k.label}
                </button>
              ))}
            </div>
          </div>

          {seriesNames.length > 1 && (
            <div className="series-toggles" role="group" aria-label="Series">
              {seriesNames.map((name) => (
                <button
                  key={name}
                  type="button"
                  aria-pressed={!hidden.includes(name)}
                  className={hidden.includes(name) ? 'toggle off' : 'toggle'}
                  onClick={() => toggleSeries(name)}
                >
                  {name}
                </button>
              ))}
            </div>
          )}

          {!visible.length && <p className="muted chart-empty">Switch on at least one series.</p>}
          {visible.length > 0 && chart.error && <p className="error chart-empty">{chart.error.message}</p>}
          {visible.length > 0 && !chart.data && !chart.error && <p className="muted chart-empty">Drawing chart…</p>}
          {visible.length > 0 && chart.data && <Chart figure={chart.data} height={420} />}
        </section>

        <aside className="panel">
          <DatasetDetails dataset={d} />
        </aside>
      </div>
    </div>
  )
}
