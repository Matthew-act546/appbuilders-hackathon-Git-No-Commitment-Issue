import { useEffect, useState } from 'react'
import { getAIStatus, getHealth } from '../lib/api'
import type { AIStatus } from '../lib/api'

export function useServiceStatus(online: boolean) {
  const [revision, setRevision] = useState(0)
  const [checking, setChecking] = useState(true)
  const [backend, setBackend] = useState<boolean | null>(null)
  const [backendMessage, setBackendMessage] = useState('Checking FastAPI…')
  const [ai, setAI] = useState<AIStatus | null>(null)
  const [aiError, setAIError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    let running = false
    async function check() {
      if (running) return
      running = true
      setChecking(true)
      const [health, status] = await Promise.allSettled([
        getHealth(controller.signal), getAIStatus(controller.signal),
      ])
      if (controller.signal.aborted) return
      const healthy = health.status === 'fulfilled' && health.value.status === 'ok'
      setBackend(healthy)
      setBackendMessage(healthy ? 'FastAPI is reachable.' : health.status === 'rejected' ? String(health.reason.message) : 'Unexpected health response.')
      setAI(status.status === 'fulfilled' ? status.value : null)
      setAIError(status.status === 'rejected' ? String(status.reason.message) : null)
      setChecking(false)
      running = false
    }
    void check()
    const interval = window.setInterval(() => void check(), 30_000)
    return () => {
      controller.abort()
      window.clearInterval(interval)
    }
  }, [online, revision])

  return { backend, backendMessage, ai, aiError, checking, refresh: () => setRevision(value => value + 1) }
}
