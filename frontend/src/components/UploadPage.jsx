import { useCallback, useEffect, useRef, useState } from 'react'
import { deleteFile, listFiles, uploadFiles } from '../api/ingest'

const ACCEPTED = '.txt,.json,.csv,.pdf'
const MAX_MB = 10

function fmt(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export default function UploadPage() {
  const [existing, setExisting] = useState([])
  const [loadingList, setLoadingList] = useState(true)
  const [dragging, setDragging] = useState(false)
  const [queue, setQueue] = useState([])        // files staged for upload
  const [uploading, setUploading] = useState(false)
  const [deleting, setDeleting] = useState(null) // filename being deleted
  const [result, setResult] = useState(null)    // { ingested, skipped }
  const [error, setError] = useState(null)
  const inputRef = useRef(null)

  // Load the existing file list on mount
  useEffect(() => {
    listFiles()
      .then((data) => setExisting(data.files))
      .catch(() => setExisting([]))
      .finally(() => setLoadingList(false))
  }, [])

  function addFiles(fileList) {
    const incoming = Array.from(fileList).filter((f) => {
      const ext = f.name.split('.').pop().toLowerCase()
      return ['txt', 'json', 'csv', 'pdf'].includes(ext) && f.size <= MAX_MB * 1024 * 1024
    })
    setQueue((prev) => {
      const names = new Set(prev.map((f) => f.name))
      return [...prev, ...incoming.filter((f) => !names.has(f.name))]
    })
  }

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    addFiles(e.dataTransfer.files)
  }, [])

  const onDragOver = (e) => { e.preventDefault(); setDragging(true) }
  const onDragLeave = () => setDragging(false)

  async function handleUpload() {
    if (!queue.length || uploading) return
    setError(null)
    setResult(null)
    setUploading(true)
    try {
      const data = await uploadFiles(queue)
      setResult(data)
      setQueue([])
      // Refresh the file list
      const updated = await listFiles()
      setExisting(updated.files)
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  async function handleDelete(filename) {
    if (deleting) return
    setDeleting(filename)
    setError(null)
    try {
      await deleteFile(filename)
      const updated = await listFiles()
      setExisting(updated.files)
    } catch (err) {
      setError(err.message)
    } finally {
      setDeleting(null)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto chat-scroll px-4 py-8 max-w-2xl w-full mx-auto space-y-8">

      {/* ── Drop zone ── */}
      <div
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onClick={() => inputRef.current?.click()}
        className={`flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed cursor-pointer transition-all duration-200 px-8 py-12
          ${dragging
            ? 'border-blue-500 bg-blue-500/10'
            : 'border-zinc-700 hover:border-zinc-500 bg-zinc-900/60'
          }`}
      >
        <svg className="w-10 h-10 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" />
        </svg>
        <p className="text-zinc-300 font-medium">Drop files here or click to browse</p>
        <p className="text-zinc-600 text-sm">.txt · .json · .csv · .pdf · max {MAX_MB} MB each</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED}
          className="hidden"
          onChange={(e) => addFiles(e.target.files)}
        />
      </div>

      {/* ── Staged queue ── */}
      {queue.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs text-zinc-500 uppercase tracking-widest font-semibold">Ready to upload</p>
          <ul className="space-y-2">
            {queue.map((f, i) => (
              <li key={i} className="flex items-center justify-between bg-zinc-900 rounded-xl px-4 py-2.5">
                <span className="text-sm text-zinc-200 truncate">{f.name}</span>
                <div className="flex items-center gap-3 shrink-0 ml-4">
                  <span className="text-xs text-zinc-500">{fmt(f.size)}</span>
                  <button
                    onClick={() => setQueue((prev) => prev.filter((_, j) => j !== i))}
                    className="text-zinc-600 hover:text-red-400 transition text-sm font-bold"
                  >
                    ✕
                  </button>
                </div>
              </li>
            ))}
          </ul>

          <button
            onClick={handleUpload}
            disabled={uploading}
            className="w-full rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-semibold py-3 transition-colors duration-150"
          >
            {uploading ? 'Ingesting…' : `Ingest ${queue.length} file${queue.length !== 1 ? 's' : ''}`}
          </button>
        </div>
      )}

      {/* ── Result banner ── */}
      {result && (
        <div className="rounded-xl bg-zinc-900 border border-zinc-800 px-5 py-4 space-y-2">
          {result.ingested.length > 0 && (
            <div>
              <p className="text-xs text-zinc-500 uppercase tracking-widest font-semibold mb-1">Ingested</p>
              <ul className="space-y-0.5">
                {result.ingested.map((name, i) => (
                  <li key={i} className="text-sm text-green-400 flex items-center gap-2">
                    <span className="text-green-500">✓</span> {name}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {result.skipped.length > 0 && (
            <div>
              <p className="text-xs text-zinc-500 uppercase tracking-widest font-semibold mb-1 mt-2">Skipped</p>
              <ul className="space-y-0.5">
                {result.skipped.map((msg, i) => (
                  <li key={i} className="text-sm text-yellow-500 flex items-center gap-2">
                    <span>⚠</span> {msg}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* ── Error ── */}
      {error && (
        <div className="rounded-xl bg-red-950/60 border border-red-800/60 px-4 py-3 text-sm text-red-400 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-4 text-red-600 hover:text-red-400 font-bold">✕</button>
        </div>
      )}

      {/* ── Existing files ── */}
      <div className="space-y-3">
        <p className="text-xs text-zinc-500 uppercase tracking-widest font-semibold">
          Files in data_export/
        </p>
        {loadingList ? (
          <p className="text-zinc-600 text-sm">Loading…</p>
        ) : existing.length === 0 ? (
          <p className="text-zinc-600 text-sm">No files yet. Upload something above.</p>
        ) : (
          <ul className="space-y-2">
            {existing.map((f, i) => (
              <li key={i} className="flex items-center justify-between bg-zinc-900 rounded-xl px-4 py-2.5">
                <span className="text-sm text-zinc-300 truncate">{f.name}</span>
                <div className="flex items-center gap-3 shrink-0 ml-4">
                  <span className="text-xs text-zinc-600 uppercase">{f.type}</span>
                  <span className="text-xs text-zinc-500">{fmt(f.size)}</span>
                  <button
                    onClick={() => handleDelete(f.name)}
                    disabled={deleting === f.name}
                    className="text-zinc-600 hover:text-red-400 disabled:opacity-40 disabled:cursor-not-allowed transition text-sm font-bold"
                    title="Delete file and clear vectors"
                  >
                    {deleting === f.name ? '…' : '✕'}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

    </div>
  )
}
