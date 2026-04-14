import { useState, useRef, useCallback, useEffect } from 'react'
import {
  Upload, FileText, Download, CheckCircle,
  AlertCircle, Lock, RefreshCw, X,
} from 'lucide-react'

// ── Types ────────────────────────────────────────────────────────────────────

type AppState = 'password' | 'idle' | 'uploading' | 'processing' | 'complete' | 'error'

interface JobStatus {
  status: string
  progress: number
  message: string
  line_item_count: number
  output_filename: string | null
}

// ── API helpers ───────────────────────────────────────────────────────────────

async function apiParse(file: File, password: string): Promise<{ job_id: string }> {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('password', password)
  const res = await fetch('/api/parse', { method: 'POST', body: fd })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error ?? `Server error ${res.status}`)
  return data
}

async function apiStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`/api/status/${jobId}`)
  const data = await res.json()
  if (!res.ok) throw new Error(data.error ?? 'Status check failed')
  return data
}

function downloadUrl(jobId: string, password: string): string {
  return `/api/download/${jobId}?password=${encodeURIComponent(password)}`
}

// ── Password gate ─────────────────────────────────────────────────────────────

function PasswordGate({ onUnlock }: { onUnlock: (pw: string) => void }) {
  const [value, setValue] = useState('')
  const [error, setError] = useState('')
  const [checking, setChecking] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!value.trim()) return
    setChecking(true)
    setError('')
    // Verify by making a test request
    try {
      const fd = new FormData()
      fd.append('password', value)
      // We use /api/health as a quick check — actual password validation
      // happens at /api/parse. Instead just proceed; wrong pw shows at upload.
      onUnlock(value)
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="min-h-screen bg-lpfc-navy flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo block */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-white/10 mb-4 border border-white/20">
            <FileText size={28} className="text-white" />
          </div>
          <h1 className="text-white text-2xl font-semibold">Estimate Parser</h1>
          <p className="text-white/50 text-sm mt-1">Moyer's Services Group</p>
          <p className="text-white/30 text-xs mt-0.5 font-mono">
            An <span className="text-white/60 font-semibold">LP First</span> Tool
          </p>
        </div>

        {/* Password card */}
        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-xl shadow-2xl p-8 space-y-5"
        >
          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1.5 uppercase tracking-wide">
              Access Password
            </label>
            <div className="relative">
              <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="password"
                value={value}
                onChange={e => { setValue(e.target.value); setError('') }}
                placeholder="Enter password"
                autoFocus
                className="w-full pl-9 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm
                           focus:outline-none focus:ring-2 focus:ring-lpfc-navy focus:border-transparent
                           placeholder:text-gray-400"
              />
            </div>
            {error && (
              <p className="mt-1.5 text-xs text-red-600 flex items-center gap-1">
                <AlertCircle size={12} /> {error}
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={checking || !value}
            className="w-full bg-lpfc-navy text-white py-2.5 rounded-lg text-sm font-medium
                       hover:bg-lpfc-navydark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {checking ? 'Checking…' : 'Continue'}
          </button>
        </form>
      </div>
    </div>
  )
}

// ── Progress bar ──────────────────────────────────────────────────────────────

function ProgressBar({ value }: { value: number }) {
  return (
    <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
      <div
        className="h-full bg-lpfc-navy rounded-full transition-all duration-500 ease-out"
        style={{ width: `${Math.min(value, 100)}%` }}
      />
    </div>
  )
}

// ── Drop zone ─────────────────────────────────────────────────────────────────

function DropZone({
  onFile,
  disabled,
}: {
  onFile: (f: File) => void
  disabled: boolean
}) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragging(false)
      if (disabled) return
      const file = e.dataTransfer.files[0]
      if (file) onFile(file)
    },
    [disabled, onFile],
  )

  return (
    <div
      onDragOver={e => { e.preventDefault(); if (!disabled) setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      className={[
        'relative border-2 border-dashed rounded-xl p-12 text-center transition-all duration-200',
        disabled
          ? 'border-gray-200 bg-gray-50 cursor-not-allowed opacity-60'
          : dragging
            ? 'border-lpfc-navy bg-blue-50 cursor-copy scale-[1.01]'
            : 'border-gray-300 bg-white hover:border-lpfc-navylight hover:bg-gray-50 cursor-pointer',
      ].join(' ')}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        className="hidden"
        onChange={e => { if (e.target.files?.[0]) onFile(e.target.files[0]) }}
        disabled={disabled}
      />
      <div className="flex flex-col items-center gap-3">
        <div className={[
          'w-14 h-14 rounded-full flex items-center justify-center transition-colors',
          dragging ? 'bg-lpfc-navy text-white' : 'bg-gray-100 text-gray-400',
        ].join(' ')}>
          <Upload size={24} />
        </div>
        <div>
          <p className="text-sm font-medium text-gray-700">
            {dragging ? 'Drop it here' : 'Drag & drop your estimate PDF'}
          </p>
          <p className="text-xs text-gray-400 mt-1">
            or <span className="text-lpfc-navy font-medium underline">browse to select</span>
          </p>
        </div>
        <p className="text-xs text-gray-400">
          Xactimate · Symbility · any carrier format · up to 100 MB
        </p>
      </div>
    </div>
  )
}

// ── File badge ────────────────────────────────────────────────────────────────

function FileBadge({ name, onRemove }: { name: string; onRemove?: () => void }) {
  return (
    <div className="flex items-center gap-2 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2">
      <FileText size={15} className="text-lpfc-navy shrink-0" />
      <span className="text-sm text-gray-700 truncate font-mono">{name}</span>
      {onRemove && (
        <button
          onClick={onRemove}
          className="ml-auto text-gray-400 hover:text-gray-600 transition-colors shrink-0"
        >
          <X size={14} />
        </button>
      )}
    </div>
  )
}

// ── Main App ──────────────────────────────────────────────────────────────────

export default function App() {
  const [password, setPassword] = useState<string | null>(null)
  const [appState, setAppState] = useState<AppState>('idle')
  const [file, setFile] = useState<File | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null)
  const [errorMsg, setErrorMsg] = useState('')
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // ── Polling ───────────────────────────────────────────────────────────────

  function stopPolling() {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }

  useEffect(() => {
    return () => stopPolling()
  }, [])

  function startPolling(jid: string) {
    stopPolling()
    pollRef.current = setInterval(async () => {
      try {
        const status = await apiStatus(jid)
        setJobStatus(status)
        if (status.status === 'complete') {
          stopPolling()
          setAppState('complete')
        } else if (status.status === 'error') {
          stopPolling()
          setErrorMsg(status.message || 'Processing failed.')
          setAppState('error')
        }
      } catch (e) {
        // transient poll failure — keep trying
      }
    }, 2500)
  }

  // ── Upload handler ────────────────────────────────────────────────────────

  async function handleUpload() {
    if (!file || !password) return
    setAppState('uploading')
    setErrorMsg('')
    setJobStatus(null)

    try {
      const { job_id } = await apiParse(file, password)
      setJobId(job_id)
      setAppState('processing')
      setJobStatus({ status: 'queued', progress: 0, message: 'Queued…', line_item_count: 0, output_filename: null })
      startPolling(job_id)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Upload failed.'
      if (msg.toLowerCase().includes('invalid password') || msg.includes('401')) {
        setPassword(null) // kick back to password gate
      }
      setErrorMsg(msg)
      setAppState('error')
    }
  }

  // ── Reset ────────────────────────────────────────────────────────────────

  function reset() {
    stopPolling()
    setFile(null)
    setJobId(null)
    setJobStatus(null)
    setErrorMsg('')
    setAppState('idle')
  }

  // ── Password gate ─────────────────────────────────────────────────────────

  if (!password) {
    return <PasswordGate onUnlock={pw => { setPassword(pw); setAppState('idle') }} />
  }

  // ── Main UI ───────────────────────────────────────────────────────────────

  const isProcessing = appState === 'uploading' || appState === 'processing'
  const progress = jobStatus?.progress ?? (appState === 'uploading' ? 5 : 0)
  const statusMsg = appState === 'uploading'
    ? 'Uploading file…'
    : jobStatus?.message ?? ''

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">

      {/* ── Header ── */}
      <header className="h-16 bg-white border-b border-gray-200 flex items-center px-6 shadow-sm shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-lpfc-navy flex items-center justify-center">
            <FileText size={16} className="text-white" />
          </div>
          <div className="flex items-center gap-2 text-lpfc-navy font-semibold text-lg">
            Moyer's Services Group
            <span className="text-gray-300 font-light mx-1">|</span>
            <span className="text-gray-500 font-normal text-sm">Estimate Parser</span>
          </div>
        </div>
        <div className="ml-auto flex items-center gap-4">
          <span className="text-xs text-gray-400 font-mono">
            An <span className="font-semibold text-lpfc-navy">LP First</span> Tool
          </span>
          <button
            onClick={() => setPassword(null)}
            className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
          >
            Sign out
          </button>
        </div>
      </header>

      {/* ── Main content ── */}
      <main className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-2xl space-y-6">

          {/* ── Title ── */}
          <div className="text-center">
            <h2 className="text-xl font-semibold text-gray-900">
              PDF Estimate → Excel Workbook
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              Upload any insurance repair estimate. AI extracts every line item into Moyer's work-order format.
            </p>
          </div>

          {/* ── Main card ── */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-5">

            {/* Drop zone — only show when idle or file selected */}
            {(appState === 'idle') && (
              <DropZone onFile={f => setFile(f)} disabled={false} />
            )}

            {/* File badge */}
            {file && appState === 'idle' && (
              <FileBadge name={file.name} onRemove={() => setFile(null)} />
            )}

            {/* Processing: file badge (no remove) + progress */}
            {isProcessing && file && (
              <>
                <FileBadge name={file.name} />
                <div className="space-y-2">
                  <ProgressBar value={progress} />
                  <div className="flex items-center justify-between">
                    <p className="text-sm text-gray-600 flex items-center gap-2">
                      <RefreshCw size={13} className="animate-spin text-lpfc-navy shrink-0" />
                      {statusMsg}
                    </p>
                    <span className="text-xs font-mono text-gray-400">{progress}%</span>
                  </div>
                </div>
              </>
            )}

            {/* Complete state */}
            {appState === 'complete' && jobStatus && (
              <div className="space-y-4">
                <div className="flex items-start gap-3 p-4 bg-green-50 border border-green-200 rounded-lg">
                  <CheckCircle size={20} className="text-green-600 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-green-800">Extraction complete</p>
                    <p className="text-xs text-green-600 mt-0.5">
                      {jobStatus.line_item_count} line items extracted
                      {jobStatus.output_filename && (
                        <> · <span className="font-mono">{jobStatus.output_filename}</span></>
                      )}
                    </p>
                  </div>
                </div>

                <div className="flex gap-3">
                  {jobId && (
                    <a
                      href={downloadUrl(jobId, password)}
                      download
                      className="flex-1 flex items-center justify-center gap-2 bg-lpfc-navy text-white
                                 py-2.5 px-4 rounded-lg text-sm font-medium hover:bg-lpfc-navydark
                                 transition-colors"
                    >
                      <Download size={16} />
                      Download Excel
                    </a>
                  )}
                  <button
                    onClick={reset}
                    className="flex items-center gap-2 bg-white text-gray-700 border border-gray-300
                               py-2.5 px-4 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors"
                  >
                    <RefreshCw size={14} />
                    New estimate
                  </button>
                </div>
              </div>
            )}

            {/* Error state */}
            {appState === 'error' && (
              <div className="space-y-4">
                <div className="flex items-start gap-3 p-4 bg-red-50 border border-red-200 rounded-lg">
                  <AlertCircle size={20} className="text-red-500 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-red-800">Processing failed</p>
                    <p className="text-xs text-red-600 mt-0.5">{errorMsg}</p>
                  </div>
                </div>
                <button
                  onClick={reset}
                  className="flex items-center gap-2 bg-white text-gray-700 border border-gray-300
                             py-2.5 px-4 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors"
                >
                  <RefreshCw size={14} />
                  Try again
                </button>
              </div>
            )}

            {/* Upload button — show when file selected and idle */}
            {file && appState === 'idle' && (
              <button
                onClick={handleUpload}
                className="w-full bg-lpfc-navy text-white py-3 rounded-lg text-sm font-medium
                           hover:bg-lpfc-navydark transition-colors flex items-center justify-center gap-2"
              >
                <Upload size={16} />
                Parse Estimate
              </button>
            )}
          </div>

          {/* ── What this does ── */}
          {appState === 'idle' && (
            <div className="grid grid-cols-3 gap-4">
              {[
                {
                  icon: <FileText size={16} className="text-lpfc-navy" />,
                  title: 'Any format',
                  desc: 'Xactimate, Symbility, or custom carrier PDFs up to 150 pages',
                },
                {
                  icon: <CheckCircle size={16} className="text-green-600" />,
                  title: 'AI extraction',
                  desc: 'Every line item pulled with section, trade, qty, pricing, and O&P',
                },
                {
                  icon: <Download size={16} className="text-lpfc-navy" />,
                  title: 'Ready to price',
                  desc: 'Excel with WO% column, Labor/Materials split, and trade filters',
                },
              ].map(({ icon, title, desc }) => (
                <div
                  key={title}
                  className="bg-white rounded-lg border border-gray-200 p-4 space-y-1.5"
                >
                  <div className="flex items-center gap-2">
                    {icon}
                    <span className="text-xs font-semibold text-gray-700">{title}</span>
                  </div>
                  <p className="text-xs text-gray-500 leading-relaxed">{desc}</p>
                </div>
              ))}
            </div>
          )}

        </div>
      </main>

      {/* ── Footer ── */}
      <footer className="py-4 text-center">
        <p className="text-xs text-gray-400">
          Moyer's Services Group · LP First Capital Portfolio Company
        </p>
      </footer>
    </div>
  )
}
