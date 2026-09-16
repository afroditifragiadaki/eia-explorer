import { useEffect, useState } from 'react'
import { getJSON } from '../api'

// A "custom hook": reusable logic for "fetch this path when the component
// appears, and remember the result". Any component can call it:
//
//   const { data, error, loading } = useApi('/stats')
//
// It starts with loading = true, then React redraws the component once the
// data (or an error) arrives.
export function useApi(path) {
  const [state, setState] = useState({ data: null, error: null, loading: true })

  useEffect(() => {
    // If the component disappears before the reply arrives, ignore the reply.
    let cancelled = false

    getJSON(path)
      .then((data) => {
        if (!cancelled) setState({ data, error: null, loading: false })
      })
      .catch((error) => {
        if (!cancelled) setState({ data: null, error, loading: false })
      })

    return () => {
      cancelled = true
    }
  }, [path]) // run again only if `path` changes

  return state
}
