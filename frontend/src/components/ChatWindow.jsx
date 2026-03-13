import { useEffect, useRef } from 'react'

/**
 * ChatWindow — scrollable list of message bubbles.
 *
 * Props:
 *   messages: Array<{ role: 'user' | 'ai', text: string, sources?: string[] }>
 *   loading:  boolean — shows a typing indicator when the AI is thinking
 */
export default function ChatWindow({ messages, loading }) {
  const bottomRef = useRef(null)

  // Auto-scroll to the newest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
      {messages.length === 0 && !loading && (
        <p className="text-center text-gray-400 text-sm mt-16 select-none">
          Ask anything about your personal data.
        </p>
      )}

      {messages.map((msg, i) => (
        <div
          key={i}
          className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
        >
          <div
            className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap shadow-sm ${
              msg.role === 'user'
                ? 'bg-indigo-600 text-white rounded-br-sm'
                : 'bg-white text-gray-800 border border-gray-200 rounded-bl-sm'
            }`}
          >
            <p>{msg.text}</p>

            {/* Source citations under AI messages */}
            {msg.role === 'ai' && msg.sources && msg.sources.length > 0 && (
              <div className="mt-2 pt-2 border-t border-gray-200">
                <p className="text-xs text-gray-400 font-medium mb-1">Sources</p>
                <ul className="space-y-0.5">
                  {msg.sources.map((src, j) => (
                    <li key={j} className="text-xs text-gray-400 truncate" title={src}>
                      {src.split(/[\\/]/).pop()}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      ))}

      {/* Typing indicator */}
      {loading && (
        <div className="flex justify-start">
          <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
            <div className="flex space-x-1 items-center h-4">
              <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce [animation-delay:-0.3s]" />
              <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce [animation-delay:-0.15s]" />
              <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" />
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}
