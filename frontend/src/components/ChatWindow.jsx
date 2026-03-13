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

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  return (
    <div className="chat-scroll flex-1 overflow-y-auto px-4 py-6 space-y-5 max-w-3xl w-full mx-auto">
      {messages.length === 0 && !loading && (
        <p className="text-center text-zinc-600 text-sm select-none mt-8">
          No messages yet. Start a conversation below.
        </p>
      )}

      {messages.map((msg, i) => (
        <div
          key={i}
          className={`flex ${
            msg.role === 'user' ? 'justify-end' : 'justify-start'
          }`}
        >
          <div
            className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
              msg.role === 'user'
                ? 'bg-blue-600 text-white rounded-br-sm shadow-md'
                : 'bg-zinc-800 text-zinc-100 rounded-bl-sm shadow-md'
            }`}
          >
            <p>{msg.text}</p>

            {/* Source citations */}
            {msg.role === 'ai' && msg.sources && msg.sources.length > 0 && (
              <div className="mt-3 pt-2 border-t border-zinc-700/50">
                <p className="text-[10px] text-zinc-500 uppercase tracking-widest font-semibold mb-1">Sources</p>
                <ul className="space-y-0.5">
                  {msg.sources.map((src, j) => (
                    <li key={j} className="text-[11px] text-zinc-500 truncate" title={src}>
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
          <div className="bg-zinc-800 rounded-2xl rounded-bl-sm px-4 py-3 shadow-md">
            <div className="flex space-x-1.5 items-center h-4">
              <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-bounce [animation-delay:-0.3s]" />
              <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-bounce [animation-delay:-0.15s]" />
              <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-bounce" />
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}
