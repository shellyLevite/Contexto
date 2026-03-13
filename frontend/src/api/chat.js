const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

/**
 * Send a question to the backend RAG endpoint.
 * @param {string} question
 * @returns {Promise<{ answer: string, sources: string[] }>}
 */
export async function sendMessage(question) {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(`Server error ${response.status}: ${text}`)
  }

  return response.json()
}
