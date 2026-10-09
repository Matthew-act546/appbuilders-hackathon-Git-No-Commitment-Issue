import { useEffect, useRef, useState } from 'react'
import { asApiError } from '../lib/api'
import type { ApiError } from '../lib/api'

// Keys stay in memory for explicit retries, never in private browser storage.
export function useMutation(scope = '') {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [retryAt, setRetryAt] = useState(0)
  const [now, setNow] = useState(Date.now())
  const busy = useRef(false)
  const controller = useRef<AbortController | null>(null)
  const intent = useRef<{ fingerprint: string; key: string } | null>(null)
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    busy.current = false
    intent.current = null
    setPending(false)
    setError(null)
    setRetryAt(0)
    return () => { mounted.current = false; controller.current?.abort() }
  }, [scope])
  useEffect(() => {
    if (!retryAt) return
    const timer = window.setInterval(() => setNow(Date.now()), 500)
    return () => window.clearInterval(timer)
  }, [retryAt])
  const waitSeconds = Math.max(0, Math.ceil((retryAt - now) / 1000))

  async function run<T>(fingerprint: string, send: (key: string, signal: AbortSignal) => Promise<T>): Promise<{ data: T } | { error: ApiError } | null> {
    if (busy.current || Date.now() < retryAt) return null
    if (intent.current?.fingerprint !== fingerprint) intent.current = { fingerprint, key: crypto.randomUUID() }
    const key = intent.current.key
    const abort = new AbortController()
    controller.current = abort
    busy.current = true
    setPending(true)
    setError(null)
    setRetryAt(0)
    try {
      const data = await send(key, abort.signal)
      return abort.signal.aborted ? null : { data }
    } catch (cause) {
      if (abort.signal.aborted) return null
      const failure = asApiError(cause)
      setError(failure)
      const time = Date.now()
      setNow(time)
      setRetryAt(time + failure.retryAfter * 1000)
      return { error: failure }
    } finally {
      if (mounted.current && controller.current === abort) { setPending(false); busy.current = false }
    }
  }
  function clear(newIntent = false) {
    if (busy.current) return
    setError(null)
    setRetryAt(0)
    if (newIntent) intent.current = null
  }
  return { pending, error, waitSeconds, run, clear }
}
