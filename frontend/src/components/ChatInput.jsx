import { useState, useRef, useEffect } from 'react'

/**
 * ChatInput — text field + send button.
 *
 * Props:
 *   onSend:  (question: string) => void
 *   disabled: boolean — true while the AI is responding
 */
export default function ChatInput({ onSend, disabled }) {
  const [value, setValue] = useState('')
  const textareaRef = useRef(null)

  // Auto-grow textarea up to ~5 lines
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 140) + 'px'
  }, [value])

  function handleSend() {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const canSend = !disabled && value.trim().length > 0

  return (
    <div className="shrink-0 px-4 pb-6 pt-3 max-w-3xl w-full mx-auto">
      {/* Input box */}
      <div className="flex items-end gap-3 bg-zinc-900 rounded-2xl px-4 py-3 shadow-lg focus-within:shadow-[0_0_0_2px_rgba(59,130,246,0.4)] transition-all duration-200">
        <textarea
          ref={textareaRef}
          className="flex-1 resize-none bg-transparent text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none leading-relaxed disabled:opacity-40 min-h-[24px] max-h-[140px] overflow-y-auto"
          rows={1}
          placeholder="Ask something about your data…"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
        />
        <button
          onClick={handleSend}
          disabled={!canSend}
          aria-label="Send message"
          className="shrink-0 w-9 h-9 rounded-xl flex items-center justify-center bg-blue-600 hover:bg-blue-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors duration-150"
        >
          <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" />
          </svg>
        </button>
      </div>

      {/* Footer labels */}
      <div className="flex flex-col items-center gap-1 mt-4 text-sm text-zinc-500">
        <span>Personal Context Engine</span>
        <span>Enter to send · Shift+Enter for new line</span>
      </div>
    </div>
  )
}
