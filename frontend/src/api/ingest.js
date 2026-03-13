const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

/**
 * Upload files to the backend for ingestion.
 * @param {File[]} files
 * @returns {Promise<{ ingested: string[], skipped: string[] }>}
 */
export async function uploadFiles(files) {
  const form = new FormData()
  for (const file of files) {
    form.append('files', file)
  }

  const response = await fetch(`${API_BASE}/api/ingest`, {
    method: 'POST',
    body: form,
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(`Server error ${response.status}: ${text}`)
  }

  return response.json()
}

/**
 * List files already in data_export/.
 * @returns {Promise<{ files: Array<{ name: string, size: number, type: string }> }>}
 */
export async function listFiles() {
  const response = await fetch(`${API_BASE}/api/files`)
  if (!response.ok) throw new Error(`Server error ${response.status}`)
  return response.json()
}
