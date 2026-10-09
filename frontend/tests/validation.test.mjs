import test from 'node:test'
import assert from 'node:assert/strict'
import { parseCheckIn, parseCompletion, parseProfile, parseQuestline } from '../src/lib/validate.ts'
const id = '10000000-0000-4000-8000-000000000001'
const time = '2026-10-10T00:00:00Z'
const quest = { id, order: 1, plan_version: 1, status: 'active', title: 'Fictional test quest', action: 'Read the fictional local test file.', completion_criteria: 'The fictional test file has been read.', estimated_minutes: 5, difficulty: 'easy', xp_reward: 10, hint: null, starting_action: null, completed_at: null }
const line = { id, goal: 'Fictional fixture goal', status: 'active', deadline: null, plan_version: 1, revision: 1, progress: { completed_count: 0, remaining_count: 3, total_count: 3 }, created_at: time, updated_at: time, available_minutes: 20, energy: 'low', current_quest: quest, completed_quests: [] }
const checkIn = { id, status: 'ready', revision: 1, context: { goal: 'Fictional test goal', available_minutes: 20, energy: 'low', deadline: null, contextual_notes: null }, question: null, summary: 'Fictional summary', questline_id: null, clarification_answer: null, created_at: time, updated_at: time }

test('accepts actual current/completed public shapes without inventing state', () => {
  assert.deepEqual(parseQuestline(line), line)
  const completed = { ...quest, status: 'completed', completed_at: time }
  const finished = { ...line, status: 'completed', current_quest: null, completed_quests: [completed], progress: { completed_count: 1, remaining_count: 0, total_count: 1 } }
  assert.deepEqual(parseQuestline(finished), finished)
  assert.deepEqual(parseCompletion({ outcome: 'already_completed', awarded_xp: 0, profile: { id: 1, total_xp: 10, level: 1 }, questline: finished }).awarded_xp, 0)
})
test('rejects extra locked/superseded content at the API boundary', () => {
  assert.throws(() => parseQuestline({ ...line, locked_quests: [{ action: 'SECRET_FUTURE' }] }))
  assert.throws(() => parseQuestline({ ...line, current_quest: { ...quest, status: 'locked' } }))
  assert.throws(() => parseQuestline({ ...line, completed_quests: [{ ...quest, status: 'superseded' }] }))
})
test('rejects malformed XP, enums, timestamps, IDs and missing fields', () => {
  assert.throws(() => parseProfile({ id: 1, total_xp: -1, level: 1 }))
  assert.throws(() => parseProfile({ id: 1, total_xp: '10', level: 1 }))
  assert.throws(() => parseQuestline({ ...line, energy: 'steady' }))
  assert.throws(() => parseQuestline({ ...line, created_at: '2026-10-10T00:00' }))
  assert.throws(() => parseQuestline({ ...line, id: '../../secret' }))
  const { current_quest: omitted, ...missing } = line
  assert.throws(() => parseQuestline(missing))
})
test('rejects inconsistent current state and fabricated duplicate rewards', () => {
  assert.throws(() => parseQuestline({ ...line, status: 'paused' }))
  assert.throws(() => parseQuestline({ ...line, progress: { completed_count: 1, remaining_count: 3, total_count: 3 } }))
  assert.throws(() => parseCompletion({ outcome: 'already_completed', awarded_xp: 10, profile: { id: 1, total_xp: 10, level: 1 }, questline: line }))
})
test('requires actual clarification and consumed-resource links', () => {
  assert.deepEqual(parseCheckIn(checkIn), checkIn)
  assert.throws(() => parseCheckIn({ ...checkIn, status: 'needs_follow_up' }))
  assert.throws(() => parseCheckIn({ ...checkIn, status: 'consumed' }))
  assert.throws(() => parseCheckIn({ ...checkIn, context: { ...checkIn.context, available_minutes: 0 } }))
})

test('completion-only copy is optional but never accepted for active quests', () => {
  assert.throws(() => parseQuestline({ ...line, current_quest: { ...quest, completion_encouragement: 'SECRET_BEFORE_COMPLETION' } }))
  assert.equal(parseQuestline({ ...line, current_quest: { ...quest, completion_encouragement: null } }).current_quest.completion_encouragement, null)
  const completed = { ...quest, status: 'completed', completed_at: time, completion_encouragement: 'A quest-specific message.' }
  const finished = { ...line, status: 'completed', current_quest: null, completed_quests: [completed], progress: { completed_count: 1, remaining_count: 0, total_count: 1 } }
  assert.equal(parseQuestline(finished).completed_quests[0].completion_encouragement, completed.completion_encouragement)
  assert.equal(parseQuestline({ ...finished, completed_quests: [{ ...completed, completion_encouragement: {} }] }).completed_quests[0].completion_encouragement, null)
})
