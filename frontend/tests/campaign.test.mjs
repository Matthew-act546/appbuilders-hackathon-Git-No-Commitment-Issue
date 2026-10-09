import test from 'node:test'
import assert from 'node:assert/strict'
import { campaignEarnedXP, campaignStages, completionMessage, stageObjectives } from '../src/lib/campaign.ts'
const quest = { id: 'current', order: 1, plan_version: 1, status: 'active', title: 'Fictional local test', action: 'Read the local task and list its requirements.', completion_criteria: 'A written list contains the requirements.', estimated_minutes: 5, difficulty: 'easy', xp_reward: 10, hint: null, starting_action: null, completed_at: null }
const line = { current_quest: quest, completed_quests: [], progress: { completed_count: 0, remaining_count: 3, total_count: 3 } }

test('two through six stage counts come from safe backend totals without padding or hidden content', () => {
  for (const count of [2, 3, 4, 5, 6]) {
    const sized = { ...line, progress: { completed_count: 0, remaining_count: count, total_count: count } }
    const stages = campaignStages(sized)
    assert.equal(stages.length, count)
    assert.deepEqual(stages.slice(1), Array.from({ length: count - 1 }, (_, index) => ({ kind: 'locked', number: index + 2 })))
    assert.equal(stageObjectives(quest).length, 2)
  }
})

test('two checkpoints preserve the complete permitted action and criteria', () => {
  const objectives = stageObjectives(quest)
  assert.equal(objectives.length, 2)
  assert.equal(objectives[0].text, quest.action)
  assert.equal(objectives[1].text, quest.completion_criteria)
})
test('two action sentences produce three checkpoints without invented content', () => {
  const action = 'Gather the supplied bread and cheese. Assemble the sandwich on a plate.'
  const objectives = stageObjectives({ ...quest, action })
  assert.equal(objectives.length, 3)
  assert.equal(objectives.slice(0, 2).map(o => o.text).join(' '), action)
})
test('long actions retain all sentences instead of dropping extra requirements', () => {
  const action = 'Read the brief. Write the test. Run it locally.'
  assert.equal(stageObjectives({ ...quest, action })[0].text, action)
})
test('future stages contain only a locked state and number, without invented IDs/content/XP', () => {
  const stages = campaignStages(line)
  assert.equal(stages.length, 3)
  assert.deepEqual(stages.slice(1), [{ kind: 'locked', number: 2 }, { kind: 'locked', number: 3 }])
  assert.equal(JSON.stringify(stages.slice(1)).includes('title'), false)
})
test('backend-confirmed history supplies campaign XP, not current/future rewards or profile XP', () => {
  const completed = { ...quest, id: 'completed', status: 'completed', xp_reward: 20 }
  assert.equal(campaignEarnedXP(line), 0)
  assert.equal(campaignEarnedXP({ ...line, completed_quests: [completed] }), 20)
})
test('replanned ordering preserves history and uses current counts without padding to six', () => {
  const completed = { ...quest, status: 'completed' }
  const current = { ...quest, id: 'new-current', order: 2, plan_version: 2 }
  const replanned = { current_quest: current, completed_quests: [completed], progress: { completed_count: 1, remaining_count: 2, total_count: 3 } }
  const stages = campaignStages(replanned)
  assert.deepEqual(stages.map(s => s.number), [1, 2, 3])
  assert.equal(stages[1].quest.id, current.id)
  assert.deepEqual(stages[2], { kind: 'locked', number: 3 })
  const finished = { ...replanned, current_quest: null, completed_quests: [completed, { ...current, status: 'completed' }], progress: { completed_count: 2, remaining_count: 0, total_count: 2 } }
  assert.equal(campaignStages(finished).length, 2)
  assert.equal(campaignStages(finished).some(s => s.kind === 'locked'), false)
})
test('legacy completion messages remain quest-specific and do not award XP', () => {
  const first = { title: 'Gather the ingredients', action: 'Gather bread, tomato and cheese.' }
  const second = { title: 'Assemble the snack', action: 'Layer the ingredients on bread.' }
  assert.ok(completionMessage(first).includes(first.title))
  assert.notEqual(completionMessage(first), completionMessage(second))
  assert.equal(completionMessage({ ...first, completion_encouragement: 'Backend-validated copy' }), 'Backend-validated copy')
})
