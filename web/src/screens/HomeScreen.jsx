import { useState } from 'react'
import { ArrowUpIcon } from '../components/Icons'
import { useApi } from '../hooks/useApi'

const EXAMPLES = [
  'Residential electricity prices, New York vs Florida since 2015',
  'Henry Hub natural gas spot price, last two years',
  'ERCOT hourly demand last week',
  'Weekly US gasoline prices since 2020',
]

// The landing screen: a big ask box, example questions, recent datasets.
export default function HomeScreen({ onAsk, onNavigate, onOpenDataset, refreshKey }) {
  const [question, setQuestion] = useState('')
  const library = useApi('/library', refreshKey)
  const stats = useApi('/stats')

  function handleSubmit(event) {
    event.preventDefault() // stop the browser from reloading the page
    const text = question.trim()
    if (text) onAsk(text)
  }

  return (
    <main className="home">
      <div className="home-inner">
        <header className="home-header">
          <div className="mission">
            <span className="dot" aria-hidden="true" />
            Easily accessible energy data for all
          </div>
          <h1>
            Ask for energy data.
            <br />
            <span className="accent">Get the chart.</span>
          </h1>
          <p className="lede">
            Describe what you want to see. The agent finds the right EIA dataset, downloads it, saves it to your
            library and plots it.
          </p>
          <div className="eyebrow">
            {stats.data ? stats.data.catalogue_datasets : '…'} EIA datasets · electricity · gas · petroleum · coal
          </div>
        </header>

        <form className="ask-box" onSubmit={handleSubmit}>
          <label htmlFor="question" className="visually-hidden">
            Your question
          </label>
          <textarea
            id="question"
            rows={2}
            placeholder="e.g. How has coal production in Wyoming changed since 2010?"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              // Enter sends; Shift+Enter makes a new line.
              if (event.key === 'Enter' && !event.shiftKey) handleSubmit(event)
            }}
          />
          <div className="ask-box-footer">
            <span className="hint">Saved datasets are reused instantly</span>
            <button type="submit" className="send-button" aria-label="Ask" disabled={!question.trim()}>
              <ArrowUpIcon />
            </button>
          </div>
        </form>

        <div className="chips">
          {EXAMPLES.map((example) => (
            <button key={example} type="button" className="chip" onClick={() => onAsk(example)}>
              {example}
            </button>
          ))}
        </div>

        <section className="recent-section">
          <div className="section-head">
            <h2>Recently saved</h2>
            <button type="button" className="link-button" onClick={() => onNavigate('library')}>
              Open library
            </button>
          </div>

          {library.loading && <p className="muted">Loading…</p>}
          {library.error && <p className="error">Couldn't load the library: {library.error.message}</p>}
          {library.data && library.data.length === 0 && <p className="muted">Nothing saved yet. Ask a question!</p>}

          {library.data && library.data.length > 0 && (
            <div className="card-grid">
              {library.data.slice(0, 3).map((item) => (
                <button key={item.id} type="button" className="card" onClick={() => onOpenDataset(item.id)}>
                  <span className="card-title">{item.title}</span>
                  <span className="mono accent">{item.route}</span>
                  <span className="muted small">
                    {item.rows.toLocaleString()} rows · saved {new Date(item.fetched_at).toLocaleDateString()}
                  </span>
                </button>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  )
}
