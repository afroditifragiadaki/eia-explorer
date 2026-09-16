import { lazy, Suspense } from 'react'

// Plotly is big (~1.5 MB compressed). `lazy` + `import()` put the chart code
// in a separate file that the browser downloads only when the first chart is
// shown, so the home screen loads fast. <Suspense> shows the fallback while
// that file downloads.
const Chart = lazy(() => import('./Chart'))

export default function LazyChart(props) {
  return (
    <Suspense fallback={<p className="muted chart-empty">Loading chart…</p>}>
      <Chart {...props} />
    </Suspense>
  )
}
