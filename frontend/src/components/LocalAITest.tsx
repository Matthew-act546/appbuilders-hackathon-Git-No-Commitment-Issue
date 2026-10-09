import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { generate } from '../lib/api'
import type { Generation } from '../lib/api'
import { Button, ErrorNotice, LoadingIndicator, Textarea } from './UI'

export function LocalAITest({ onComplete }: { onComplete: () => void }) {
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
        onComplete()
      }
    }
  }

  return <details className="diagnostic">
    <summary>Try a local AI connection test</summary>
    <p className="muted helper">This diagnostic sends a prompt to FastAPI and Ollama on this laptop. It does not create or save quests.</p>
    <form onSubmit={submit} className="stack">
      <div><label htmlFor="prompt">Your test prompt</label><Textarea id="prompt" value={prompt} onChange={event => setPrompt(event.target.value)} required maxLength={8000} rows={3} placeholder="Describe what a local language model does." /></div>
      <p className="muted helper">Up to 8,000 characters. Generation may take up to two minutes.</p>
      <Button type="submit" loading={loading} disabled={!prompt.trim()}>{loading ? 'Generating…' : 'Generate response'}</Button>
    </form>
    <div aria-live="polite" aria-busy={loading}>
      {loading && <LoadingIndicator>Waiting for your local model…</LoadingIndicator>}
      {error && <ErrorNotice>{error}</ErrorNotice>}
      {result && <div className="diagnostic-result"><h3>Response · {result.model}</h3><p>{result.response || 'The model returned an empty response. Try another prompt.'}</p></div>}
    </div>
  </details>
}
