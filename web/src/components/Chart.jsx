import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'

// Plotly draws into a real page element, outside React's control. So React
// renders an empty <div>, and after each render we hand that div to Plotly.
// `useRef` is how a component keeps hold of its own page element.

const COLORS = ['#3ddc97', '#58a6ff', '#e3b341', '#f778ba', '#a371f7', '#56d4dd', '#ff9b5e', '#8ddb8c']
const GRID = '#1e2228'
const AXIS_LINE = '#2e333b'

// The backend's figure uses Plotly's default light style. Restyle it to match
// the app: transparent background, our fonts, our colour order.
function themed(figure, height) {
  const data = figure.data.map((trace) => ({
    ...trace,
    // Drop the colours Plotly picked, so our `colorway` applies instead.
    line: trace.line ? { ...trace.line, color: undefined, width: 2.2 } : trace.line,
    marker: trace.marker ? { ...trace.marker, color: undefined } : trace.marker,
  }))

  const layout = {
    ...figure.layout,
    template: {},
    title: { text: '' }, // the title is shown above the chart instead
    height,
    autosize: true,
    margin: { l: 64, r: 16, t: 12, b: 48 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    colorway: COLORS,
    font: { family: 'Geist, system-ui, sans-serif', size: 12, color: '#a9afb8' },
    hoverlabel: { bgcolor: '#15181d', bordercolor: AXIS_LINE, font: { color: '#e8eaed', family: 'Geist Mono, monospace' } },
    legend: { ...figure.layout.legend, font: { color: '#a9afb8' }, bgcolor: 'rgba(0,0,0,0)' },
  }
  // Style every axis (faceted charts have xaxis2, yaxis3, …).
  for (const key of Object.keys(figure.layout)) {
    if (/^[xy]axis\d*$/.test(key)) {
      layout[key] = {
        ...figure.layout[key],
        gridcolor: GRID,
        linecolor: AXIS_LINE,
        zerolinecolor: AXIS_LINE,
        tickfont: { family: 'Geist Mono, monospace', size: 11 },
      }
    }
  }
  return { data, layout }
}

export default function Chart({ figure, height = 380 }) {
  const ref = useRef(null)

  // Draw (or redraw) whenever the figure changes.
  useEffect(() => {
    if (!figure || !ref.current) return
    const { data, layout } = themed(figure, height)
    Plotly.react(ref.current, data, layout, {
      displaylogo: false,
      responsive: true,
      modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'],
    })
  }, [figure, height])

  // When the component disappears, let Plotly clean up.
  useEffect(() => {
    const element = ref.current
    return () => {
      if (element) Plotly.purge(element)
    }
  }, [])

  return <div ref={ref} className="chart" style={{ minHeight: height }} />
}
