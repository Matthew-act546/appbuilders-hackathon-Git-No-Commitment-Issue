import { parseCheckIn, parseCompletion, parseProfile, parseQuestline, parseQuestlineList } from './validate'
import type { CheckInAnswer, CheckInStart, GenerateQuestlineRequest } from './questTypes'
export type { Profile } from './questTypes'

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '')
export interface AIStatus { available: boolean; server_available: boolean; model_available: boolean; model: string; message: string }
export interface Generation { model: string; response: string }

const messages: Record<string, string> = {
  VALIDATION_ERROR: 'Check the entered fields and try again.',
  UNSUPPORTED_REQUEST: 'This companion cannot provide medical diagnosis, therapy or treatment.',
  CLARIFICATION_INSUFFICIENT: 'Please add a little more specific detail to answer the same question.',
  STALE_REVISION: 'This saved state changed. It will be reloaded before another action.',
  INVALID_STATE: 'That action is not available in the current state. Reload the saved state.',
  QUESTLINE_PAUSED: 'Resume this questline before completing a quest.',
  CHECK_IN_NOT_READY: 'Answer the saved clarification before generating quests.',
  CHECK_IN_ALREADY_USED: 'This check-in already has a saved questline. Reload it to continue.',
  IDEMPOTENCY_CONFLICT: 'This request key belongs to a different action. Reload the saved state before continuing.',
  REQUEST_IN_PROGRESS: 'A local request is still running. Wait, then retry the same action.',
  REQUEST_INTERRUPTED: 'The previous request was interrupted. Retry the same action to recover.',
  OLLAMA_UNAVAILABLE: 'Ollama is unavailable. Start the local runtime, then retry. Saved quests still work.',
  MODEL_UNAVAILABLE: 'The configured model is unavailable. Check your installed Ollama models, then retry.',
  STORAGE_BUSY: 'Local storage is busy. Wait briefly, then retry the same action.',
  STORAGE_UNAVAILABLE: 'Local storage is unavailable. Check FastAPI and the database path, then retry.',
  AI_TIMEOUT: 'Local generation timed out. Your check-in is preserved; retry the same action.',
  AI_INVALID_OUTPUT: 'The local model returned an invalid plan. No quests were saved. Your check-in is saved; retry generation.',
  AI_SEMANTIC_REJECTED: 'The local model could not produce a plan that passed the quality checks. No quests were saved. Your check-in is saved; retry generation.',
  AI_REVIEW_UNCERTAIN: 'The local model could not confidently verify its plan. No quests were saved. Your check-in is saved; retry generation.',
  AI_UPSTREAM_ERROR: 'The local model request failed. Check Ollama, then retry.',
  CHECK_IN_NOT_FOUND: 'This check-in is no longer available. Start a new check-in.',
  QUESTLINE_NOT_FOUND: 'This saved questline is no longer available. Return to My Quests.',
  QUEST_NOT_FOUND: 'This quest is no longer actionable. Reload the questline.',
  INTERNAL_ERROR: 'The operation could not be completed. Reload the saved state and try again.',
}
export class ApiError extends Error {
  constructor(public code: string, message: string, public status = 0, public retryable = true, public retryAfter = 0, public uncertain = false) { super(message); this.name = 'ApiError' }
}
export const asApiError = (error: unknown) => error instanceof ApiError ? error : new ApiError('REQUEST_FAILED', 'The request could not be completed. Retry or reload saved state.')

async function request<T>(path: string, options: RequestInit = {}, timeout = 10_000, parse?: (value: unknown) => T): Promise<T> {
  const timeoutSignal = AbortSignal.timeout(timeout)
  const signal = options.signal ? AbortSignal.any([options.signal, timeoutSignal]) : timeoutSignal
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...options, signal, cache: 'no-store' })
  } catch (error) {
    if (options.signal?.aborted) throw error
    throw new ApiError(timeoutSignal.aborted ? 'RESPONSE_TIMEOUT' : 'NETWORK_ERROR', timeoutSignal.aborted
      ? 'The response was not confirmed before the timeout. Retry the unchanged action or reload saved state.'
      : 'Cannot reach FastAPI. Check the local backend, then retry the unchanged action.', 0, true, 0, options.method === 'POST')
  }
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const envelope = body && typeof body === 'object' && 'error' in body ? body.error : null
    const details = envelope && typeof envelope === 'object' ? envelope as Record<string, unknown> : null
    const code = typeof details?.code === 'string' && Object.hasOwn(messages, details.code) ? details.code : 'REQUEST_FAILED'
    const retryAfter = Number(response.headers.get('Retry-After'))
    throw new ApiError(code, messages[code] ?? `The local service could not complete this request (${response.status}).`, response.status,
      typeof details?.retryable === 'boolean' ? details.retryable : response.status >= 500 || response.status === 429,
      Number.isFinite(retryAfter) && retryAfter > 0 ? Math.ceil(retryAfter) : 0)
  }
  try {
    if (body === null) throw new Error('Missing JSON')
    return parse ? parse(body) : body as T
  } catch {
    throw new ApiError('INVALID_RESPONSE', 'The backend returned an invalid response. Reload saved state or retry the unchanged action.', response.status, true, 0, options.method === 'POST')
  }
}
function post<T>(path: string, body: object, signal: AbortSignal, parse: (value: unknown) => T, key?: string, timeout = 15_000) {
  return request(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(key ? { 'Idempotency-Key': key } : {}) }, body: JSON.stringify(body), signal }, timeout, parse)
}
export const getHealth = (signal: AbortSignal) => request<{ status: string }>('/api/health', { signal })
export const getAIStatus = (signal: AbortSignal) => request<AIStatus>('/api/ai/status', { signal })
export const getProfile = (signal: AbortSignal) => request('/api/profile', { signal }, 10_000, parseProfile)
export const getCheckIn = (id: string, signal: AbortSignal) => request(`/api/check-in/${encodeURIComponent(id)}`, { signal }, 10_000, parseCheckIn)
export const submitCheckIn = (body: CheckInStart | CheckInAnswer, key: string, signal: AbortSignal) => post('/api/check-in', body, signal, parseCheckIn, key)
export const generateQuestline = (body: GenerateQuestlineRequest, key: string, signal: AbortSignal) => post('/api/questlines', body, signal, parseQuestline, key, 150_000)
export const getQuestlines = (offset: number, signal: AbortSignal) => request(`/api/questlines?limit=20&offset=${offset}`, { signal }, 10_000, parseQuestlineList)
export const getQuestline = (id: string, signal: AbortSignal) => request(`/api/questlines/${encodeURIComponent(id)}`, { signal }, 10_000, parseQuestline)
export const completeQuest = (id: string, revision: number, signal: AbortSignal) => post(`/api/quests/${encodeURIComponent(id)}/complete`, { expected_revision: revision }, signal, parseCompletion)
export const setQuestlinePaused = (id: string, revision: number, paused: boolean, key: string, signal: AbortSignal) => post(`/api/questlines/${encodeURIComponent(id)}/${paused ? 'pause' : 'resume'}`, { expected_revision: revision }, signal, parseQuestline, key)
export const generate = (prompt: string, signal: AbortSignal) => request<Generation>('/api/ai/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt }), signal }, 130_000)
