export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '')

export interface AIStatus {
  available: boolean
  server_available: boolean
  model_available: boolean
  model: string
  message: string
}

export interface Generation {
  model: string
  response: string
}

async function request<T>(path: string, options: RequestInit = {}, timeout = 8_000): Promise<T> {
  const timeoutSignal = AbortSignal.timeout(timeout)
  const signal = options.signal ? AbortSignal.any([options.signal, timeoutSignal]) : timeoutSignal
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...options, signal, cache: 'no-store' })
  } catch (error) {
    if (options.signal?.aborted) throw error
    if (timeoutSignal.aborted) throw new Error('The request timed out. Check FastAPI and Ollama, then retry.')
    throw new Error('Cannot reach FastAPI. Check that the backend is running and its URL and CORS settings are correct.')
  }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : null
    throw new Error(typeof detail === 'string' ? detail : `Request failed (${response.status}).`)
  }
  return response.json() as Promise<T>
}

export const getHealth = (signal: AbortSignal) => request<{ status: string }>('/api/health', { signal })
export const getAIStatus = (signal: AbortSignal) => request<AIStatus>('/api/ai/status', { signal })
export const generate = (prompt: string, signal: AbortSignal) => request<Generation>('/api/ai/generate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ prompt }),
  signal,
}, 130_000)
