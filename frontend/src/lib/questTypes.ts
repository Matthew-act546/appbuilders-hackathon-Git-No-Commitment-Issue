export type Energy = 'low' | 'medium' | 'high'
export type Difficulty = 'easy' | 'medium' | 'hard'
export type QuestlineStatus = 'active' | 'paused' | 'completed'
export interface Profile { id: 1; total_xp: number; level: number }
export interface CheckInContext {
  goal: string
  available_minutes: number
  energy: Energy
  deadline: string | null
  contextual_notes: string | null
}
export interface CheckIn {
  id: string
  status: 'needs_follow_up' | 'ready' | 'consumed'
  revision: number
  context: CheckInContext
  question: string | null
  summary: string | null
  questline_id: string | null
  clarification_answer: string | null
  created_at: string
  updated_at: string
}
export interface CheckInStart extends CheckInContext { mode: 'start' }
export interface CheckInAnswer { mode: 'answer'; check_in_id: string; expected_revision: number; answer: string }
export interface GenerateQuestlineRequest { check_in_id: string; expected_check_in_revision: number }
export interface ReplanRequest {
  expected_revision: number
  available_minutes: number
  energy: Energy
  deadline?: string | null
  contextual_notes?: string | null
  reason?: string | null
}
export interface QuestProgress { completed_count: number; remaining_count: number; total_count: number }
export interface Quest {
  id: string
  order: number
  plan_version: number
  status: 'active' | 'paused' | 'completed'
  title: string
  action: string
  completion_criteria: string
  estimated_minutes: number
  difficulty: Difficulty
  xp_reward: 10 | 20 | 30
  hint: string | null
  starting_action: string | null
  completed_at: string | null
  completion_encouragement?: string | null
}
export interface QuestlineSummary {
  id: string
  goal: string
  status: QuestlineStatus
  deadline: string | null
  plan_version: number
  revision: number
  progress: QuestProgress
  created_at: string
  updated_at: string
}
export interface Questline extends QuestlineSummary {
  available_minutes: number
  energy: Energy
  current_quest: Quest | null
  completed_quests: Quest[]
}
export interface QuestlineList { items: QuestlineSummary[]; limit: number; offset: number; has_more: boolean }
export interface Completion {
  outcome: 'completed' | 'already_completed'
  awarded_xp: 0 | 10 | 20 | 30
  profile: Profile
  questline: Questline
}
