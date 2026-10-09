import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { useAppProfile } from '../components/AppShell'
import { SavedQuestlines } from '../components/SavedQuestlines'
import { Button, Card, EmptyState, ErrorNotice, LoadingIndicator, PageHeading } from '../components/UI'
import { useMutation } from '../hooks/useMutation'
import { useQuestline } from '../hooks/useQuestline'
import { completeQuest, setQuestlinePaused } from '../lib/api'

import { CampaignMap, CampaignOverview } from '../components/CampaignMap'
import { CompletionCelebration } from '../components/CompletionCelebration'
import type { Completion, Quest } from '../lib/questTypes'

interface Action { kind: 'complete' | 'pause' | 'resume'; revision: number; questId?: string }

export default function MyQuests() {
  const { id } = useParams<{ id: string }>()
  const [listRevision, setListRevision] = useState(0)
  return <>
    <PageHeading eyebrow="Your workspace" title="My Quests">One current quest, with room to breathe. Your progress stays on this laptop.</PageHeading>
    {id ? <div className="workspace-grid"><QuestDashboard key={id} id={id} onChanged={() => setListRevision(v => v + 1)} /><SavedQuestlines selectedId={id} revision={listRevision} /></div> : <><Card tone="butter"><EmptyState title="Choose your next small step" action={<Link className="text-link" to="/">Start a new check-in →</Link>}>Open a saved questline below to continue its current quest.</EmptyState></Card><div className="history-foundation"><SavedQuestlines revision={listRevision} /></div></>}
  </>
}

function QuestDashboard({ id, onChanged }: { id: string; onChanged: () => void }) {
  const state = useQuestline(id)
  const profile = useAppProfile()
  const mutation = useMutation()
  const [failedAction, setFailedAction] = useState<Action | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [recovering, setRecovering] = useState(false)
  const [activity, setActivity] = useState<Action['kind'] | null>(null)
  const [celebration, setCelebration] = useState<{ result: Completion; quest: Quest } | null>(null)
  const { line, loading, error } = state
  const locked = loading || mutation.pending || recovering || Boolean(failedAction) || mutation.waitSeconds > 0

  async function act(action: Action) {
    setNotice(null)
    setActivity(action.kind)
    const fingerprint = `${id}:${JSON.stringify(action)}`
    if (action.kind === 'complete' && action.questId) {
      setCelebration(null)
      const result = await mutation.run(fingerprint, (_key, signal) => completeQuest(action.questId!, action.revision, signal))
      if (!result) return
      if ('data' in result) {
        state.accept(result.data.questline)
        profile.accept(result.data.profile)
        const completed = result.data.questline.completed_quests.find(quest => quest.id === action.questId)
        if (completed) setCelebration({ result: result.data, quest: completed })
        setNotice(result.data.outcome === 'already_completed' ? 'Already completed. No additional XP awarded.' : `Quest completed. ${result.data.awarded_xp} XP confirmed by the backend.`)
        setFailedAction(null)
        onChanged()
        return
      }
      setFailedAction(action)
      if (result.error.status === 409 || result.error.status === 404 || result.error.uncertain) {
        setRecovering(true)
        await state.reload()
        profile.refresh()
        if ((result.error.status === 409 || result.error.status === 404) && result.error.code !== 'REQUEST_IN_PROGRESS') setFailedAction(null)
        setRecovering(false)
      }
    } else {
      const result = await mutation.run(fingerprint, (key, signal) => setQuestlinePaused(id, action.revision, action.kind === 'pause', key, signal))
      if (!result) return
      if ('data' in result) {
        state.accept(result.data)
        setNotice(result.data.status === 'paused' ? 'Paused. Your current quest and earned XP are preserved.' : 'Saved state confirmed. Continue at your own pace.')
        setFailedAction(null)
        onChanged()
        return
      }
      setFailedAction(action)
      if (result.error.status === 409 || result.error.status === 404 || result.error.uncertain) {
        setRecovering(true)
        await state.reload()
        profile.refresh()
        if ((result.error.status === 409 || result.error.status === 404) && result.error.code !== 'REQUEST_IN_PROGRESS') setFailedAction(null)
        setRecovering(false)
      }
    }
  }
  return <div className="dashboard-stack stack">
    <Link to="/questlines" className="text-link">← All saved questlines</Link>
    {loading && <LoadingIndicator>Reading your saved questline…</LoadingIndicator>}
    {error && <ErrorNotice action={<Link to="/questlines" className="text-link">Return to saved questlines</Link>}>{error.message}{error.retryable && <Button variant="secondary" onClick={() => void state.reload()}>Retry loading</Button>}</ErrorNotice>}
    {mutation.error && <ErrorNotice>{mutation.error.message}{mutation.waitSeconds > 0 && <p>Retry in {mutation.waitSeconds} seconds.</p>}{mutation.error.uncertain && <p>The previous action may have committed. Retry that same action to recover safely.</p>}{failedAction && <Button variant="secondary" onClick={() => void act(failedAction)} loading={mutation.pending} disabled={loading || recovering || mutation.waitSeconds > 0 || !mutation.error.retryable}>Retry previous action</Button>}{!failedAction && <Button variant="quiet" onClick={() => mutation.clear()} disabled={loading || recovering}>Continue with refreshed state</Button>}{failedAction && !mutation.error?.retryable && <Button variant="quiet" disabled={loading || recovering} onClick={async () => { await state.reload(); setFailedAction(null); mutation.clear(true) }}>Reload saved state</Button>}</ErrorNotice>}
    {mutation.pending && <LoadingIndicator>{activity === 'complete' ? 'Confirming quest completion…' : 'Saving your questline state…'}</LoadingIndicator>}
    {notice && <p role="status" className="success-notice">{notice}</p>}
    {celebration && <CompletionCelebration {...celebration} onContinue={() => { setCelebration(null); document.getElementById(`campaign-map-${id}`)?.focus() }} />}
    {line && <>
      <CampaignOverview line={line} profile={profile.profile} />
      <CampaignMap line={line} disabled={locked} completionAction={<div className="quest-actions"><Button onClick={() => line.current_quest && void act({ kind: 'complete', questId: line.current_quest.id, revision: line.revision })} loading={mutation.pending && activity === 'complete'} disabled={locked || line.status !== 'active'}>Complete stage</Button>{line.status === 'paused' && <p className="helper muted">Resume this questline to complete its current stage.</p>}</div>} />
      {line.status === 'completed' && <Card tone="leaf"><EmptyState title="Campaign completed" action={<Link className="text-link" to="/">Start another check-in →</Link>}>Questline completed. Your earned XP and completed stage history remain available.</EmptyState></Card>}
      {line.status !== 'completed' && <Card tone="leaf"><h2>Adjust your pace</h2><p className="muted">Pausing keeps your current quest and completed progress. No XP is deducted.</p><div className="quest-actions"><Button variant="secondary" loading={mutation.pending && activity !== 'complete'} disabled={locked} onClick={() => void act({ kind: line.status === 'paused' ? 'resume' : 'pause', revision: line.revision })}>{line.status === 'paused' ? 'Resume questline' : 'Pause questline'}</Button><Button variant="quiet" disabled={locked} onClick={() => void state.reload()}>Reload saved state</Button></div></Card>}
      <p className="helper muted">Local AI suggestions may need your review. Hints, smaller starting actions and replanning are not connected in this phase.</p>
    </>}
  </div>
}
