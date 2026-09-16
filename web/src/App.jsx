import { useCallback, useState } from 'react'
import Sidebar from './components/Sidebar'
import { useConversation } from './hooks/useConversation'
import AnswerScreen from './screens/AnswerScreen'
import CatalogueScreen from './screens/CatalogueScreen'
import HomeScreen from './screens/HomeScreen'
import LibraryScreen from './screens/LibraryScreen'

// The whole app: the sidebar on the left, one screen on the right.
// App holds the state several screens share, and passes it down as props.
export default function App() {
  const [screen, setScreen] = useState('ask') // 'ask' | 'library' | 'catalogue'
  const [openDatasetId, setOpenDatasetId] = useState(null) // dataset open in the Library
  const [libraryVersion, setLibraryVersion] = useState(0) // bumped when the agent saves data

  // When the agent saves a dataset, counts and lists should refetch.
  const onDataset = useCallback(() => setLibraryVersion((v) => v + 1), [])
  const conversation = useConversation({ onDataset })

  function askNew(question) {
    conversation.ask(question, { fresh: true })
    setScreen('ask')
  }

  function navigate(id) {
    if (id === 'new') {
      conversation.reset()
      id = 'ask'
    }
    if (id === 'library') setOpenDatasetId(null)
    setScreen(id)
  }

  function openDataset(datasetId) {
    setOpenDatasetId(datasetId)
    setScreen('library')
  }

  let content
  if (screen === 'library') {
    content = <LibraryScreen openId={openDatasetId} onOpen={setOpenDatasetId} refreshKey={libraryVersion} />
  } else if (screen === 'catalogue') {
    content = <CatalogueScreen onAsk={askNew} />
  } else if (conversation.turns.length === 0) {
    content = <HomeScreen onAsk={askNew} onNavigate={navigate} onOpenDataset={openDataset} refreshKey={libraryVersion} />
  } else {
    content = <AnswerScreen conversation={conversation} onOpenInLibrary={openDataset} />
  }

  return (
    <div className="app">
      <Sidebar
        screen={screen}
        onNavigate={navigate}
        refreshKey={libraryVersion}
        hasConversation={conversation.turns.length > 0}
        streaming={conversation.streaming}
      />
      {content}
    </div>
  )
}
