import type { CheckIn, CheckInContext, Completion, Profile, Quest, Questline, QuestlineList, QuestlineSummary, QuestProgress } from './questTypes'

export const isUUID = (value: string) => /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)
const invalid = (): never => { throw new Error('Invalid backend response') }
function object(value: unknown, keys: string[]): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return invalid()
  const obj = value as Record<string, unknown>
  if (Object.keys(obj).some(key => !keys.includes(key)) || keys.some(key => !(key in obj))) return invalid()
  return obj
}
function text(value: unknown, min = 1, max = 4000): string {
  return typeof value === 'string' && value.trim().length >= min && value.length <= max ? value : invalid()
}
function integer(value: unknown, min = 0, max = Number.MAX_SAFE_INTEGER): number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= min && value <= max ? value : invalid()
}
function choice<T extends string | number>(value: unknown, choices: readonly T[]): T {
  return choices.includes(value as T) ? value as T : invalid()
}
function uuid(value: unknown): string { return typeof value === 'string' && isUUID(value) ? value : invalid() }
function date(value: unknown): string {
  return typeof value === 'string' && /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) && Number.isFinite(Date.parse(value)) ? value : invalid()
}
function nullable<T>(value: unknown, parse: (value: unknown) => T): T | null { return value === null ? null : parse(value) }
function array<T>(value: unknown, parse: (value: unknown) => T): T[] { return Array.isArray(value) ? value.map(parse) : invalid() }
const energy = (value: unknown) => choice(value, ['low', 'medium', 'high'] as const)
export function parseProfile(value: unknown): Profile {
  const v = object(value, ['id', 'total_xp', 'level'])
  if (v.id !== 1) return invalid()
  return { id: 1, total_xp: integer(v.total_xp), level: integer(v.level, 1) }
}
function context(value: unknown): CheckInContext {
  const v = object(value, ['goal', 'available_minutes', 'energy', 'deadline', 'contextual_notes'])
  return { goal: text(v.goal), available_minutes: integer(v.available_minutes, 1, 1440), energy: energy(v.energy), deadline: nullable(v.deadline, date), contextual_notes: nullable(v.contextual_notes, x => text(x, 0, 2000)) }
}
export function parseCheckIn(value: unknown): CheckIn {
  const v = object(value, ['id', 'status', 'revision', 'context', 'question', 'summary', 'questline_id', 'clarification_answer', 'created_at', 'updated_at'])
  const result: CheckIn = { id: uuid(v.id), status: choice(v.status, ['needs_follow_up', 'ready', 'consumed']), revision: integer(v.revision, 1), context: context(v.context), question: nullable(v.question, x => text(x, 1, 300)), summary: nullable(v.summary, x => text(x, 1, 2000)), questline_id: nullable(v.questline_id, uuid), clarification_answer: nullable(v.clarification_answer, x => text(x, 1, 2000)), created_at: date(v.created_at), updated_at: date(v.updated_at) }
  if ((result.status === 'needs_follow_up') !== (result.question !== null) || (result.status === 'consumed') !== (result.questline_id !== null)) return invalid()
  return result
}
function progress(value: unknown): QuestProgress {
  const v = object(value, ['completed_count', 'remaining_count', 'total_count'])
  const result = { completed_count: integer(v.completed_count), remaining_count: integer(v.remaining_count), total_count: integer(v.total_count, 1) }
  return result.completed_count + result.remaining_count === result.total_count ? result : invalid()
}
const summaryKeys = ['id', 'goal', 'status', 'deadline', 'plan_version', 'revision', 'progress', 'created_at', 'updated_at']
function summary(v: Record<string, unknown>): QuestlineSummary {
  return { id: uuid(v.id), goal: text(v.goal), status: choice(v.status, ['active', 'paused', 'completed']), deadline: nullable(v.deadline, date), plan_version: integer(v.plan_version, 1), revision: integer(v.revision, 1), progress: progress(v.progress), created_at: date(v.created_at), updated_at: date(v.updated_at) }
}
function quest(value: unknown): Quest {
  // Accept pre-enhancement DTOs, but reject any message before completion.
  const candidate = value && typeof value === 'object' ? value as Record<string, unknown> : null
  const optionalKeys = candidate && 'completion_encouragement' in candidate ? ['completion_encouragement'] : []
  const v = object(value, ['id', 'order', 'plan_version', 'status', 'title', 'action', 'completion_criteria', 'estimated_minutes', 'difficulty', 'xp_reward', 'hint', 'starting_action', 'completed_at', ...optionalKeys])
  const result: Quest = { id: uuid(v.id), order: integer(v.order, 1), plan_version: integer(v.plan_version, 1), status: choice(v.status, ['active', 'paused', 'completed']), title: text(v.title, 1, 100), action: text(v.action, 1, 2000), completion_criteria: text(v.completion_criteria, 1, 1000), estimated_minutes: integer(v.estimated_minutes, 1, 1440), difficulty: choice(v.difficulty, ['easy', 'medium', 'hard']), xp_reward: choice(v.xp_reward, [10, 20, 30]), hint: nullable(v.hint, x => text(x, 1, 1000)), starting_action: nullable(v.starting_action, x => text(x, 1, 1000)), completed_at: nullable(v.completed_at, date) }
  if (optionalKeys.length) {
    // Optional copy must not turn a confirmed completion into a failed request.
    if (result.status !== 'completed' && v.completion_encouragement !== null) return invalid()
    result.completion_encouragement = typeof v.completion_encouragement === 'string' && v.completion_encouragement.trim() && v.completion_encouragement.length <= 500 ? v.completion_encouragement : null
  }
  return (result.status === 'completed') === (result.completed_at !== null) ? result : invalid()
}
export function parseQuestline(value: unknown): Questline {
  const v = object(value, [...summaryKeys, 'available_minutes', 'energy', 'current_quest', 'completed_quests'])
  const result: Questline = { ...summary(v), available_minutes: integer(v.available_minutes, 1, 1440), energy: energy(v.energy), current_quest: nullable(v.current_quest, quest), completed_quests: array(v.completed_quests, quest) }
  if (result.completed_quests.some(q => q.status !== 'completed') || result.completed_quests.length !== result.progress.completed_count) return invalid()
  if (result.status === 'completed' ? result.current_quest !== null || result.progress.remaining_count !== 0 : result.current_quest?.status !== result.status || result.progress.remaining_count < 1) return invalid()
  return result
}
export function parseQuestlineList(value: unknown): QuestlineList {
  const v = object(value, ['items', 'limit', 'offset', 'has_more'])
  if (typeof v.has_more !== 'boolean') return invalid()
  return { items: array(v.items, x => summary(object(x, summaryKeys))), limit: integer(v.limit, 1, 100), offset: integer(v.offset), has_more: v.has_more }
}
export function parseCompletion(value: unknown): Completion {
  const v = object(value, ['outcome', 'awarded_xp', 'profile', 'questline'])
  const result: Completion = { outcome: choice(v.outcome, ['completed', 'already_completed']), awarded_xp: choice(v.awarded_xp, [0, 10, 20, 30]), profile: parseProfile(v.profile), questline: parseQuestline(v.questline) }
  return result.outcome === 'already_completed' && result.awarded_xp !== 0 ? invalid() : result
}
