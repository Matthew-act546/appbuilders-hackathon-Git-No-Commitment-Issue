import { useEffect, useRef, useState } from 'react'
import { ApiError, asApiError, getQuestline } from '../lib/api'
import type { Questline } from '../lib/questTypes'
import { isUUID } from '../lib/validate'

export function useQuestline(id: string) {
  const [line, setLine] = useState<Questline | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)
  const controller = useRef<AbortController | null>(null)
  const sequence = useRef(0)
  const mounted = useRef(true)
  async function reload(): Promise<void> {
    controller.current?.abort()
    const abort = new AbortController()
    controller.current = abort
    const request = ++sequence.current
    setLoading(true)
    setError(null)
    try {
      if (!isUUID(id)) throw new ApiError('QUESTLINE_NOT_FOUND', 'This questline address is invalid. Return to My Quests.', 404, false)
      const data = await getQuestline(id, abort.signal)
      if (!abort.signal.aborted && mounted.current && request === sequence.current) setLine(previous => !previous || data.revision >= previous.revision ? data : previous)
    } catch (cause) {
      if (!abort.signal.aborted && mounted.current && request === sequence.current) {
        setLine(null)
        setError(asApiError(cause))
      }
    } finally {
      if (!abort.signal.aborted && mounted.current && request === sequence.current) setLoading(false)
    }
  }
  useEffect(() => {
    mounted.current = true
    void reload()
    return () => { mounted.current = false; controller.current?.abort(); sequence.current++ }
    // Dashboard is keyed by route ID, so its state cannot cross selected lines.
  }, [id])
  function accept(data: Questline) {
    if (!mounted.current || data.id !== id) return
    controller.current?.abort()
    sequence.current++
    setLine(previous => !previous || data.revision >= previous.revision ? data : previous)
    setError(null)
    setLoading(false)
  }
  return { line, loading, error, reload, accept }
}
