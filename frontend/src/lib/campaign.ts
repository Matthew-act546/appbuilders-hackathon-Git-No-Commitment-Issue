import type { Quest, Questline } from './questTypes'

export interface StageObjective { label: string; text: string }
export type CampaignStage = { kind: 'locked'; number: number } | { kind: 'revealed'; number: number; quest: Quest }

// Reference checkpoints only: no new AI content or independently saved state.
export function stageObjectives(quest: Pick<Quest, 'action' | 'completion_criteria'>): StageObjective[] {
  const sentences = quest.action.trim().split(/(?<=[.!?])\s+(?=[A-Z])/u)
  const actions = sentences.length === 2 ? sentences : [quest.action]
  return [...actions.map((text, index) => ({ label: actions.length === 1 ? 'Take the action' : `Action ${index + 1}`, text })),
    { label: 'Verify the result', text: quest.completion_criteria }]
}

export function campaignStages(line: Questline): CampaignStage[] {
  const revealed: CampaignStage[] = [...line.completed_quests, ...(line.current_quest ? [line.current_quest] : [])]
    .sort((a, b) => a.order - b.order)
    .map(quest => ({ kind: 'revealed', number: quest.order, quest }))
  const lockedCount = line.progress.remaining_count - (line.current_quest ? 1 : 0)
  const nextNumber = (line.current_quest?.order ?? line.progress.completed_count) + 1
  return [...revealed, ...Array.from({ length: lockedCount }, (_, index): CampaignStage => ({ kind: 'locked', number: nextNumber + index }))]
}

// Display aggregate of already completed, backend-rewarded records. Never awards XP.
export function campaignEarnedXP(line: Pick<Questline, 'completed_quests'>): number {
  return line.completed_quests.reduce((sum, quest) => sum + quest.xp_reward, 0)
}
export function completionMessage(quest: Quest): string {
  if (quest.completion_encouragement) return quest.completion_encouragement
  const excerpt = (value: string, count: number) => {
    const words = value.trim().split(/[.!?]\s+/u)[0].replace(/[.!?]+$/u, '').split(/\s+/u)
    const label = words.slice(0, count).join(' ')
    return label.slice(0, 80).replace(/[ ,;:.!?]+$/u, '') + (words.length > count || label.length > 80 ? '…' : '')
  }
  return `“${excerpt(quest.title, 6)}” is complete—your step: “${excerpt(quest.action, 8)}”. Let this small step be a quiet win along your path.`
}

