import { useState } from 'react'
import ChatWindow from './components/ChatWindow'
import ChatInput from './components/ChatInput'
import { sendMessage } from './api/chat'

function App() {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleSend(question) {
    setError(null)
    setMessages((prev) => [...prev, { role: 'user', text: question }])
    setLoading(true)

    try {
      const result = await sendMessage(question)
      setMessages((prev) => [
        ...prev,
        { role: 'ai', text: result.answer, sources: result.sources },
      ])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <header className="shrink-0 bg-white border-b border-gray-200 px-6 py-4 shadow-sm">
        <h1 className="text-lg font-semibold text-gray-800 tracking-tight">
          Personal Context Engine
        </h1>
        <p className="text-xs text-gray-400 mt-0.5">Your private AI assistant</p>
      </header>

      {/* Message list */}
      <ChatWindow messages={messages} loading={loading} />

      {/* Error banner */}
      {error && (
        <div className="mx-4 mb-2 rounded-lg bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700 flex items-center justify-between">
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="ml-4 text-red-400 hover:text-red-600 font-bold text-xs"
          >
            ✕
          </button>
        </div>
      )}

      {/* Input bar */}
      <ChatInput onSend={handleSend} disabled={loading} />
    </div>
  )
}

export default App
