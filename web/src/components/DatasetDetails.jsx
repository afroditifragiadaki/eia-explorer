import { csvUrl } from '../api'
import { eiaRequestLines, formatDateTime } from './format'

// Facts about one saved dataset, the EIA request behind it, and downloads.
// `dataset` is the JSON from GET /datasets/{id}.
export default function DatasetDetails({ dataset }) {
  const { query } = dataset
  const facts = [
    ['Frequency', query.frequency ?? '—'],
    ['Rows', dataset.rows.toLocaleString()],
    ['Metrics', dataset.metrics.join(', ')],
    ['Series', dataset.series.length],
    ...Object.entries(query.facets ?? {}).map(([facet, values]) => [facet, values.join(', ')]),
    ['Saved', formatDateTime(dataset.fetched_at)],
  ]

  return (
    <div className="details">
      <dl className="facts">
        {facts.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>

      <div className="details-block">
        <div className="label">EIA API request</div>
        <pre className="terminal">{eiaRequestLines(query)}</pre>
        <p className="muted small">The exact call that produced this data, so you can reuse it in your own code.</p>
      </div>

      <div className="details-actions">
        <a className="button-primary" href={csvUrl(dataset.id, 'wide')}>
          Download CSV
        </a>
        <a className="link-button" href={csvUrl(dataset.id, 'long')}>
          Long format (one row per value)
        </a>
      </div>
    </div>
  )
}
