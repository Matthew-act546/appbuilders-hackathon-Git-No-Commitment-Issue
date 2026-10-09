import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { StatusCard } from '../components/StatusCard'
import { useConnectivity } from '../hooks/useConnectivity'
import { useServiceStatus } from '../hooks/useServiceStatus'
import { generate } from '../lib/api'
import type { Generation } from '../lib/api'

export default function Home() {
  const online = useConnectivity()
  const status = useServiceStatus(online)
  const [prompt, setPrompt] = useState('')
  const [result, setResult] = useState<Generation | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const generationController = useRef<AbortController | null>(null)
  useEffect(() => () => generationController.current?.abort(), [])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!prompt.trim() || loading) return
    const controller = new AbortController()
    generationController.current = controller
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      setResult(await generate(prompt.trim(), controller.signal))
    } catch (cause) {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Generation failed.')
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false)
        status.refresh()
      }
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-5 py-8 sm:px-8 sm:py-14">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <a className="flex items-center gap-3 font-semibold" href="/">
          <img src="/icons/favicon.svg" alt="" width="40" height="40" />
          AppBuildersPH <span className="font-normal text-slate-500">2026</span>
        </a>
        <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600">Local-first starter</span>
      </header>

      <div className="my-12 max-w-2xl">
        <p className="text-sm font-semibold uppercase tracking-widest text-teal-700">AppBuildersPH Hackathon 2026</p>
        <h1 className="mt-4 text-4xl font-semibold tracking-tight sm:text-5xl">Build something that works closer to home.</h1>
        <p className="mt-5 text-lg leading-8 text-slate-600">A minimal desktop workspace, powered by services on this laptop. Start with a prompt to test your local AI.</p>
      </div>

      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="font-semibold">Your connections</h2>
        <button type="button" onClick={status.refresh} disabled={status.checking} className="text-sm font-medium text-teal-700 disabled:opacity-50">{status.checking ? 'Checking…' : 'Refresh status'}</button>
      </div>
      <div className="grid gap-4 sm:grid-cols-3" aria-live="polite">
        <StatusCard title="Browser connectivity" label={online ? 'Online signal' : 'Offline signal'} available={online} description="Reported by your browser. This does not confirm internet access or local service availability." />
        <StatusCard title="Backend" label={status.backend === null ? 'Checking…' : status.backend ? 'Connected' : 'Unavailable'} available={status.backend} description={status.backendMessage} />
        <StatusCard title="Local AI" label={status.ai ? status.ai.available ? 'Model ready' : status.ai.server_available ? 'Model unavailable' : 'Ollama unavailable' : status.aiError ? 'Status unavailable' : 'Checking…'} available={status.ai?.available ?? (status.aiError ? false : null)} description={status.ai ? `${status.ai.model} · ${status.ai.message}` : status.aiError ?? 'Checking Ollama and the configured model…'} />
      </div>

      <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-5 sm:p-8">
        <h2 className="text-xl font-semibold">Try your local AI</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">Prompts go to FastAPI and Ollama on this laptop. Generation needs both services running.</p>
        <form className="mt-6" onSubmit={submit}>
          <label htmlFor="prompt" className="text-sm font-medium">Your prompt</label>
          <textarea id="prompt" value={prompt} onChange={event => setPrompt(event.target.value)} required maxLength={8000} rows={4} placeholder="Suggest a small hackathon project for a local community…" className="mt-2 w-full resize-y rounded-xl border border-slate-300 bg-slate-50 p-4 text-base" />
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-slate-500">Up to 8,000 characters. Requests may take up to two minutes.</p>
            <button disabled={loading || !prompt.trim()} className="rounded-xl bg-teal-700 px-5 py-3 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-50">{loading ? 'Generating…' : 'Generate response'}</button>
          </div>
        </form>
        <div aria-live="polite" aria-busy={loading}>
          {loading && <p className="mt-6 text-sm text-slate-600">Waiting for your local model…</p>}
          {error && <p role="alert" className="mt-6 rounded-xl bg-red-50 p-4 text-sm text-red-800">{error}</p>}
          {result && <div className="mt-6 border-t border-slate-200 pt-6"><h3 className="text-sm font-semibold text-teal-700">Response · {result.model}</h3><p className="mt-3 whitespace-pre-wrap break-words leading-7">{result.response || 'The model returned an empty response. Try another prompt.'}</p></div>}
        </div>
      </section>

      <footer className="mt-6 text-sm leading-6 text-slate-500">
        <p>Keep the local frontend server, FastAPI and Ollama running. After initial setup, internet access is not required for the local app; reloading still needs the frontend server.</p>
      </footer>
    </main>
  )
}
