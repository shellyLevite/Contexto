import { useState } from 'react'
import ChatWindow from './components/ChatWindow'
import ChatInput from './components/ChatInput'
import UploadPage from './components/UploadPage'
import { sendMessage } from './api/chat'

function App() {
  const [tab, setTab] = useState('chat')          // 'chat' | 'upload'
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
    <div className="flex flex-col h-screen bg-zinc-950 text-zinc-100">

      {/* ── Title block ── */}
      <div className="shrink-0 pt-10 pb-4 text-center px-4">
        <h1 className="text-5xl md:text-6xl font-extrabold tracking-tighter text-center bg-gradient-to-r from-blue-500 to-cyan-400 bg-clip-text text-transparent">
          CONTEXTO
        </h1>
        <p className="text-lg md:text-xl text-zinc-400 text-center mt-3">
          Your private AI assistant — ask anything about your personal data
        </p>
      </div>

      {/* ── Tab bar ── */}
      <div className="shrink-0 flex justify-center gap-1 pb-4 px-4">
        {[{ id: 'chat', label: 'Chat' }, { id: 'upload', label: 'Upload Data' }].map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`px-5 py-1.5 rounded-full text-sm font-medium transition-colors duration-150
              ${tab === id
                ? 'bg-blue-600 text-white'
                : 'text-zinc-500 hover:text-zinc-300'
              }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ── Main content ── */}
      {tab === 'chat' ? (
        <>
          <ChatWindow messages={messages} loading={loading} />

          {error && (
            <div className="mx-4 mb-2 rounded-xl bg-red-950/60 border border-red-800/60 px-4 py-2.5 text-sm text-red-400 flex items-center justify-between">
              <span>{error}</span>
              <button
                onClick={() => setError(null)}
                className="ml-4 text-red-600 hover:text-red-400 font-bold text-xs transition"
              >
                ✕
              </button>
            </div>
          )}

          <ChatInput onSend={handleSend} disabled={loading} />
        </>
      ) : (
        <UploadPage />
      )}
    </div>
  )
}

export default App
