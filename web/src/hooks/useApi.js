import { useEffect, useState } from 'react'
import { getJSON } from '../api'

// A "custom hook": reusable logic for "fetch this path when the component
// appears, and remember the result". Any component can call it:
//
//   const { data, error, loading } = useApi('/stats')
//
// - Pass `null` as the path to fetch nothing (yet).
// - Change `refreshKey` (any value) to fetch the same path again.
// - While a new path loads, the previous data stays visible.
export function useApi(path, refreshKey = 0) {
  const [state, setState] = useState({ data: null, error: null, loading: path !== null })

  useEffect(() => {
    if (path === null) return undefined
    // If the component disappears (or the path changes) before the reply
    // arrives, ignore that reply.
    let cancelled = false

    getJSON(path)
      .then((data) => {
        if (!cancelled) setState({ data, error: null, loading: false })
      })
      .catch((error) => {
        if (!cancelled) setState((prev) => ({ data: prev.data, error, loading: false }))
      })

    return () => {
      cancelled = true
    }
  }, [path, refreshKey]) // run again when either changes

  return state
}

// Returns `value`, but only after it has stopped changing for `delay` ms.
// Used for search boxes: ask the backend once the user pauses typing,
// not on every keystroke.
export function useDebounced(value, delay = 250) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debounced
}
