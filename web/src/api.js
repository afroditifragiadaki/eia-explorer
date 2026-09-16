// Everything that talks to the FastAPI backend goes through this file,
// so the backend's address is written in exactly one place.

// Vite reads VITE_API_URL from web/.env; without it, use the local backend.
export const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

// GET a path from the backend and return the JSON it sends back.
// On an error status (404, 422, 500...) throw an Error with the backend's
// message, so screens can show it.
export async function getJSON(path) {
  const response = await fetch(`${API_URL}${path}`)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const message = typeof body.detail === 'string' ? body.detail : `HTTP ${response.status}`
    throw new Error(message)
  }
  return response.json()
}
