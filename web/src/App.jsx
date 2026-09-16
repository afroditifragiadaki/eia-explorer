import { useState } from 'react'
import Sidebar from './components/Sidebar'
import HomeScreen from './screens/HomeScreen'
import Placeholder from './screens/Placeholder'

// The whole app: the sidebar on the left, one screen on the right.
// `screen` remembers which screen is showing; changing it redraws the app.
export default function App() {
  const [screen, setScreen] = useState('ask')
  const [question, setQuestion] = useState(null) // the question being answered, if any

  function ask(text) {
    setQuestion(text)
    setScreen('ask')
  }

  function navigate(id) {
    if (id === 'ask') setQuestion(null) // "Ask" / "New question" → back to the empty home screen
    setScreen(id)
  }

  let content
  if (screen === 'ask' && question === null) {
    content = <HomeScreen onAsk={ask} onNavigate={navigate} />
  } else if (screen === 'ask') {
    content = (
      <Placeholder title="Answer">
        You asked: “{question}”. The live answer screen is the next frontend step.
      </Placeholder>
    )
  } else if (screen === 'library') {
    content = <Placeholder title="Library">Coming next: every saved dataset, with charts and CSV downloads.</Placeholder>
  } else {
    content = <Placeholder title="Catalogue">Coming next: search all EIA datasets.</Placeholder>
  }

  return (
    <div className="app">
      <Sidebar screen={screen} onNavigate={navigate} />
      {content}
    </div>
  )
}
