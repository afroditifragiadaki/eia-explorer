import { useEffect, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import Chart from '../components/LazyChart'
import DatasetDetails from '../components/DatasetDetails'
import { ArrowUpIcon, StopIcon } from '../components/Icons'
import { useApi } from '../hooks/useApi'

// "fetch_data", {route: "...", facets: {...}} → 'route="…" facets={…}'
function formatArgs(args) {
  return Object.entries(args)
    .map(([key, value]) => `${key}=${JSON.stringify(value)}`)
    .join(' ')
}

// The agent's steps, shown like terminal output.
function StepsLog({ events, status, stopped }) {
  const lines = events.filter((e) => ['tool_call', 'dataset', 'thinking'].includes(e.type))
  const toolCalls = events.filter((e) => e.type === 'tool_call').length
  const summary =
    status === 'streaming'
      ? 'agent · working…'
      : `agent · ${toolCalls} tool call${toolCalls === 1 ? '' : 's'}${stopped ? ' · stopped' : ''}`

  return (
    <details className="steps" open>
      <summary>
        <span className={status === 'streaming' ? 'dot dot-wait pulse' : status === 'error' ? 'dot dot-down' : 'dot'} />
        <span className="mono">{summary}</span>
      </summary>
      <div className="terminal log">
        {lines.length === 0 && <div className="muted">starting…</div>}
        {lines.map((event, i) => {
          if (event.type === 'tool_call') {
            return (
              <div key={i} className="log-line">
                <span className="accent">›</span> {event.data.name}{' '}
                <span className="muted">{formatArgs(event.data.args)}</span>
              </div>
            )
          }
          if (event.type === 'dataset') {
            const d = event.data
            return (
              <div key={i} className="log-line blue">
                {'  '}↳ {d.rows.toLocaleString()} rows · {d.from_cache ? 'from library' : 'downloaded from EIA · saved'}
              </div>
            )
          }
          return (
            <div key={i} className="log-line muted thinking">
              {'  '}
              {event.data.text}
            </div>
          )
        })}
      </div>
    </details>
  )
}

// One question and everything the agent sent back for it.
function Turn({ turn, onShowDataset, onOpenInLibrary }) {
  // Answer text, charts and errors appear in the order they arrived.
  const blocks = turn.events.filter((e) => ['text', 'chart', 'error'].includes(e.type))

  return (
    <div className="turn">
      <div className="user-bubble">{turn.question}</div>
      <StepsLog events={turn.events} status={turn.status} stopped={turn.stopped} />
      {blocks.map((event, i) => {
        if (event.type === 'text') {
          return (
            <div key={i} className="prose">
              <Markdown>{event.data.text}</Markdown>
            </div>
          )
        }
        if (event.type === 'chart') {
          const { figure, dataset_id: datasetId } = event.data
          return (
            <figure key={i} className="panel chart-card">
              <figcaption>{figure.layout?.title?.text}</figcaption>
              <Chart figure={figure} />
              <div className="chart-card-foot">
                <button type="button" className="link-button" onClick={() => onShowDataset(datasetId)}>
                  Show details
                </button>
                <button type="button" className="link-button" onClick={() => onOpenInLibrary(datasetId)}>
                  Open in library
                </button>
              </div>
            </figure>
          )
        }
        return (
          <div key={i} className="error-box">
            {event.data.text}
          </div>
        )
      })}
    </div>
  )
}

// The right-hand panel: the dataset the answer is about.
function SidePanel({ datasetId }) {
  const dataset = useApi(datasetId ? `/datasets/${datasetId}` : null)
  if (!datasetId) {
    return <p className="muted small">The dataset behind the answer will appear here.</p>
  }
  if (!dataset.data) {
    return dataset.error ? <p className="error small">{dataset.error.message}</p> : <p className="muted small">Loading…</p>
  }
  return (
    <>
      <div className="side-head">
        <span className="label">Dataset</span>
        <h2>{dataset.data.title}</h2>
        <span className="mono accent">{dataset.data.route}</span>
      </div>
      <DatasetDetails dataset={dataset.data} />
    </>
  )
}

export default function AnswerScreen({ conversation, onOpenInLibrary }) {
  const { turns, streaming, ask, stop } = conversation
  const [followUp, setFollowUp] = useState('')
  const [pinnedId, setPinnedId] = useState(null) // chosen with "Show details"
  const endRef = useRef(null)

  // The newest dataset any turn mentioned (from a chart or a download).
  let latestId = null
  for (const turn of turns) {
    for (const event of turn.events) {
      if (event.type === 'chart') latestId = event.data.dataset_id
      if (event.type === 'dataset') latestId = event.data.id
    }
  }
  const panelId = pinnedId ?? latestId

  // Keep the newest output in view while the answer streams in.
  const eventCount = turns.reduce((n, t) => n + t.events.length, 0)
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [turns.length, eventCount])

  function send(event) {
    event.preventDefault()
    const text = followUp.trim()
    if (!text || streaming) return
    setPinnedId(null)
    ask(text)
    setFollowUp('')
  }

  return (
    <div className="answer">
      <main className="conversation">
        <header className="conversation-head">
          <h1>{turns[0]?.question}</h1>
          <span className="muted small">
            {turns.length} question{turns.length === 1 ? '' : 's'}
          </span>
        </header>

        <div className="turns">
          {turns.map((turn) => (
            <Turn key={turn.id} turn={turn} onShowDataset={setPinnedId} onOpenInLibrary={onOpenInLibrary} />
          ))}
          <div ref={endRef} />
        </div>

        <form className="composer" onSubmit={send}>
          <label htmlFor="follow-up" className="visually-hidden">
            Follow-up question
          </label>
          <input
            id="follow-up"
            type="text"
            placeholder={streaming ? 'The agent is working…' : 'Ask a follow-up…'}
            value={followUp}
            onChange={(e) => setFollowUp(e.target.value)}
            disabled={streaming}
          />
          {streaming ? (
            <button type="button" className="send-button stop" aria-label="Stop" onClick={stop}>
              <StopIcon />
            </button>
          ) : (
            <button type="submit" className="send-button" aria-label="Send" disabled={!followUp.trim()}>
              <ArrowUpIcon />
            </button>
          )}
        </form>
      </main>

      <aside className="side-panel" aria-label="Dataset details">
        <SidePanel datasetId={panelId} />
      </aside>
    </div>
  )
}
