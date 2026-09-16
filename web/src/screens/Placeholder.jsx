// A stand-in for screens we haven't built yet.
export default function Placeholder({ title, children }) {
  return (
    <main className="placeholder">
      <h1>{title}</h1>
      <p className="muted">{children}</p>
    </main>
  )
}
