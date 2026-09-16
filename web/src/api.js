// Everything that talks to the FastAPI backend goes through this file,
// so the backend's address is written in exactly one place.

// Vite reads VITE_API_URL from web/.env; without it, use the local backend.
export const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

// Build "/path?a=1&b=x&b=y" from an object, skipping empty values.
// Arrays become repeated parameters, which is how FastAPI reads lists.
export function withQuery(path, params = {}) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === '') continue
    for (const item of Array.isArray(value) ? value : [value]) query.append(key, item)
  }
  const text = query.toString()
  return text ? `${path}?${text}` : path
}

// Turn an error reply into an Error with the backend's message.
async function errorFrom(response) {
  const body = await response.json().catch(() => ({}))
  const message = typeof body.detail === 'string' ? body.detail : `HTTP ${response.status}`
  return new Error(message)
}

// GET a path from the backend and return the JSON it sends back.
export async function getJSON(path) {
  const response = await fetch(`${API_URL}${path}`)
  if (!response.ok) throw await errorFrom(response)
  return response.json()
}

// The link that downloads a dataset as CSV (the backend marks it as a file).
export function csvUrl(datasetId, layout = 'wide') {
  return `${API_URL}${withQuery(`/datasets/${datasetId}/csv`, { layout })}`
}

// POST a question to /ask and call onEvent({type, data}) for every
// Server-Sent Event as it arrives. Resolves when the stream ends.
//
// The browser's built-in EventSource only supports GET, so we read the
// stream ourselves: the body arrives in chunks of bytes, we decode them to
// text, and every blank line ("\n\n") marks the end of one event.
export async function askStream({ question, conversationId, signal, onEvent }) {
  const response = await fetch(`${API_URL}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, conversation_id: conversationId ?? null }),
    signal, // lets the caller cancel (the Stop button)
  })
  if (!response.ok) throw await errorFrom(response)

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let end
    while ((end = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, end)
      buffer = buffer.slice(end + 2)
      const event = parseEvent(block)
      if (event) onEvent(event)
    }
  }
}

// "event: text\ndata: {...}"  →  { type: 'text', data: {...} }
function parseEvent(block) {
  let type = 'message'
  let data = ''
  for (const line of block.split('\n')) {
    if (line.startsWith('event: ')) type = line.slice(7)
    else if (line.startsWith('data: ')) data += line.slice(6)
  }
  if (!data) return null
  return { type, data: JSON.parse(data) }
}
