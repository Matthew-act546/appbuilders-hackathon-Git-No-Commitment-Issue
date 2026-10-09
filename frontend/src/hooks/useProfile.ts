import { useEffect, useRef, useState } from 'react'
import { getProfile } from '../lib/api'
import type { Profile } from '../lib/api'

export function useProfile(online: boolean) {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)
  const currentController = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    currentController.current = controller
    let running = false
    async function read() {
      if (running) return
      running = true
      setLoading(true)
      try {
        const result = await getProfile(controller.signal)
        if (!controller.signal.aborted) {
          setProfile(result)
          setError(null)
        }
      } catch (cause) {
        if (!controller.signal.aborted) {
          setProfile(null)
          setError(cause instanceof Error ? cause.message : 'Progress is unavailable. Try again.')
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false)
        running = false
      }
    }
    void read()
    const interval = window.setInterval(() => void read(), 30_000)
    return () => {
      controller.abort()
      window.clearInterval(interval)
    }
  }, [online, revision])

  function accept(value: Profile) {
    currentController.current?.abort()
    setProfile(value)
    setError(null)
    setLoading(false)
    setRevision(revision => revision + 1)
  }
  return { profile, loading, error, accept, refresh: () => setRevision(value => value + 1) }
}
