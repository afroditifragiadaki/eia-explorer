import { useCallback, useRef, useState } from 'react'
import { askStream } from '../api'

// Everything about the current conversation with the agent.
//
// It lives in App (not in the Answer screen), so an answer keeps streaming
// and stays on screen when you switch to the Library and back.
//
// turns: [{ id, question, events: [{type, data}], status: 'streaming' | 'done' | 'error', stopped? }]
export function useConversation({ onDataset } = {}) {
  const [turns, setTurns] = useState([])
  const [conversationId, setConversationId] = useState(null)
  const abortRef = useRef(null) // the running request, so Stop can cancel it
  const nextId = useRef(1)

  // Change one turn, found by its id. If it's gone (the conversation was
  // reset meanwhile), do nothing.
  const updateTurn = useCallback((id, change) => {
    setTurns((prev) => prev.map((turn) => (turn.id === id ? change(turn) : turn)))
  }, [])

  const ask = useCallback(
    async (question, { fresh = false } = {}) => {
      abortRef.current?.abort() // only one answer streams at a time
      const controller = new AbortController()
      abortRef.current = controller

      const id = nextId.current++
      const turn = { id, question, events: [], status: 'streaming' }
      setTurns((prev) => (fresh ? [turn] : [...prev, turn]))
      if (fresh) setConversationId(null)

      try {
        await askStream({
          question,
          conversationId: fresh ? null : conversationId,
          signal: controller.signal,
          onEvent: (event) => {
            if (event.type === 'start') {
              setConversationId(event.data.conversation_id)
              return
            }
            if (event.type === 'dataset') onDataset?.(event.data)
            updateTurn(id, (t) => ({
              ...t,
              events: [...t.events, event],
              status: event.type === 'error' ? 'error' : t.status,
            }))
          },
        })
        updateTurn(id, (t) => ({ ...t, status: t.status === 'streaming' ? 'done' : t.status }))
      } catch (error) {
        if (error.name === 'AbortError') {
          updateTurn(id, (t) => ({ ...t, status: 'done', stopped: true }))
        } else {
          updateTurn(id, (t) => ({
            ...t,
            status: 'error',
            events: [...t.events, { type: 'error', data: { text: error.message } }],
          }))
        }
      } finally {
        if (abortRef.current === controller) abortRef.current = null
      }
    },
    [conversationId, onDataset, updateTurn],
  )

  const stop = useCallback(() => abortRef.current?.abort(), [])

  const reset = useCallback(() => {
    abortRef.current?.abort()
    setTurns([])
    setConversationId(null)
  }, [])

  const streaming = turns.some((turn) => turn.status === 'streaming')
  return { turns, streaming, ask, stop, reset }
}
