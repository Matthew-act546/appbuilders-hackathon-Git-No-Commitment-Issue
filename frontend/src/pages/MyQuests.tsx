import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'
import { useAppProfile } from '../components/AppShell'
import { SavedQuestlines } from '../components/SavedQuestlines'
import { ReplanForm } from '../components/ReplanForm'
import { GenerationLoading } from '../components/GenerationLoading'
import { Button, Card, EmptyState, ErrorNotice, LoadingIndicator, PageHeading } from '../components/UI'
import { useMutation } from '../hooks/useMutation'
import { useQuestline } from '../hooks/useQuestline'
import { completeQuest, replanQuestline, setQuestlinePaused } from '../lib/api'

import { CampaignMap, CampaignOverview } from '../components/CampaignMap'
import { CompletionCelebration } from '../components/CompletionCelebration'
import type { Completion, Energy, Quest, ReplanRequest } from '../lib/questTypes'

type Action = { kind: 'complete'; revision: number; questId: string }
  | { kind: 'pause' | 'resume'; revision: number }
  | { kind: 'replan'; request: ReplanRequest }

export default function MyQuests() {
  const { id } = useParams<{ id: string }>()
  const [listRevision, setListRevision] = useState(0)
  return <>
    <PageHeading eyebrow="Your workspace" title="My Quests">One current quest, with room to breathe. Your progress stays on this laptop.</PageHeading>
    {id ? <QuestDashboard key={id} id={id} listRevision={listRevision} onChanged={() => setListRevision(v => v + 1)} /> : <><Card tone="butter"><EmptyState title="Choose your next small step" action={<Link className="text-link" to="/">Start a new check-in →</Link>}>Open a saved questline below to continue its current quest.</EmptyState></Card><div className="history-foundation"><SavedQuestlines revision={listRevision} /></div></>}
  </>
}

function QuestDashboard({ id, listRevision, onChanged }: { id: string; listRevision: number; onChanged: () => void }) {
  const state = useQuestline(id)
  const profile = useAppProfile()
  const mutation = useMutation()
  const [failedAction, setFailedAction] = useState<Action | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [recovering, setRecovering] = useState(false)
  const [activity, setActivity] = useState<Action['kind'] | null>(null)
  const [replanEnergy, setReplanEnergy] = useState<Energy>('low')
  const [celebration, setCelebration] = useState<{ result: Completion; quest: Quest } | null>(null)
  const workspace = useRef<HTMLDivElement>(null)
  const overview = useRef<HTMLDivElement>(null)
  const dashboard = useRef<HTMLDivElement>(null)
  const replanFeedback = useRef<HTMLDivElement>(null)
  const [minimumHeight, setMinimumHeight] = useState(0)
  const { line, loading, error } = state
  const locked = loading || mutation.pending || recovering || Boolean(failedAction) || mutation.waitSeconds > 0

  useEffect(() => {
    if (activity === 'replan' && mutation.error && !mutation.pending) replanFeedback.current?.focus({ preventScroll: true })
  }, [activity, mutation.error, mutation.pending])

  useLayoutEffect(() => {
    const summary = overview.current
    const layout = workspace.current
    if (!summary || !layout) return
    const alignSidebar = () => {
      const settings = summary.querySelector('.campaign-settings')
      const progress = summary.querySelector('.campaign-progress')
      const firstStage = layout.querySelector('.campaign-stage')
      if (!settings || !progress) {
        for (const property of ['--saved-questlines-height', '--quest-sidebar-offset', '--quest-sidebar-gap']) layout.style.removeProperty(property)
        return
      }
      const settingsBounds = settings.getBoundingClientRect()
      const progressBounds = progress.getBoundingClientRect()
      layout.style.setProperty('--quest-sidebar-offset', `${settingsBounds.top - layout.getBoundingClientRect().top}px`)
      layout.style.setProperty('--saved-questlines-height', `${progressBounds.bottom - settingsBounds.top}px`)
      if (firstStage) layout.style.setProperty('--quest-sidebar-gap', `${firstStage.getBoundingClientRect().top - progressBounds.bottom}px`)
      for (const heading of layout.querySelectorAll('.campaign-map > .section-heading, .campaign-map > p')) observer.observe(heading)
    }
    const observer = new ResizeObserver(alignSidebar)
    alignSidebar()
    observer.observe(summary)
    return () => observer.disconnect()
  }, [])

  async function act(action: Action) {
    // Preserve the viewport even if the completed stage makes the page shorter.
    if (action.kind !== 'complete') setNotice(null)
    else setMinimumHeight(previous => Math.max(previous, dashboard.current?.getBoundingClientRect().height ?? 0))
    if (action.kind === 'replan') {
      setReplanEnergy(action.request.energy)
      setMinimumHeight(previous => Math.max(previous, workspace.current?.getBoundingClientRect().height ?? 0))
    }
    setActivity(action.kind)
    const fingerprint = `${id}:${JSON.stringify(action)}`
    if (action.kind === 'complete') {
      const result = await mutation.run(fingerprint, (_key, signal) => completeQuest(action.questId, action.revision, signal))
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
      const result = await mutation.run(fingerprint, (key, signal) => action.kind === 'replan'
        ? replanQuestline(id, action.request, key, signal)
        : setQuestlinePaused(id, action.revision, action.kind === 'pause', key, signal))
      if (!result) return
      if ('data' in result) {
        state.accept(result.data)
        setNotice(action.kind === 'replan' ? 'Your remaining stages have been replanned. Completed stages and earned XP are preserved.' : result.data.status === 'paused' ? 'Paused. Your current quest and earned XP are preserved.' : 'Saved state confirmed. Continue at your own pace.')
        setFailedAction(null)
        onChanged()
        if (action.kind === 'replan') requestAnimationFrame(() => document.getElementById(`campaign-map-${id}`)?.focus({ preventScroll: true }))
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
  const mutationFeedback = mutation.error && <ErrorNotice>
    {mutation.error.message}
    {mutation.waitSeconds > 0 && <p>Retry in {mutation.waitSeconds} seconds.</p>}
    {mutation.error.uncertain && <p>The previous action may have committed. Retry that same action to recover safely.</p>}
    {failedAction && <Button variant="secondary" onClick={() => void act(failedAction)} loading={mutation.pending} disabled={loading || recovering || mutation.waitSeconds > 0 || !mutation.error.retryable}>{failedAction.kind === 'replan' ? 'Retry replanning' : 'Retry previous action'}</Button>}
    {!failedAction && <Button variant="quiet" onClick={() => mutation.clear()} disabled={loading || recovering}>Continue with refreshed state</Button>}
    {failedAction?.kind === 'replan' && !mutation.error.uncertain && mutation.error.code !== 'REQUEST_IN_PROGRESS' && <Button variant="quiet" disabled={loading || recovering || mutation.waitSeconds > 0} onClick={() => { setFailedAction(null); mutation.clear(true) }}>Edit replanning details</Button>}
    {failedAction && !mutation.error.retryable && <Button variant="quiet" disabled={loading || recovering} onClick={async () => { await state.reload(); setFailedAction(null); mutation.clear(true) }}>Reload saved state</Button>}
  </ErrorNotice>
  return <div ref={workspace} className="workspace-grid">
    {mutation.pending && activity === 'replan' && <GenerationLoading energy={replanEnergy} purpose="replan" />}
    <div ref={dashboard} className="dashboard-stack stack" style={{ minHeight: minimumHeight || undefined }}>
      <div ref={overview} className="stack">
        <Link to="/questlines" className="text-link">← All saved questlines</Link>
        {loading && <LoadingIndicator>Reading your saved questline…</LoadingIndicator>}
        {error && <ErrorNotice action={<Link to="/questlines" className="text-link">Return to saved questlines</Link>}>{error.message}{error.retryable && <Button variant="secondary" onClick={() => void state.reload()}>Retry loading</Button>}</ErrorNotice>}
        {activity !== 'replan' && mutationFeedback}
        {mutation.pending && activity !== 'replan' && <LoadingIndicator>{activity === 'complete' ? 'Confirming quest completion…' : 'Saving your questline state…'}</LoadingIndicator>}
        {notice && <p role="status" className="success-notice">{notice}</p>}
        {celebration && <CompletionCelebration {...celebration} onContinue={() => { setCelebration(null); document.getElementById(`campaign-map-${id}`)?.focus({ preventScroll: true }) }} />}
        {line && <CampaignOverview line={line} profile={profile.profile} />}
      </div>
      {line && <>
        <CampaignMap line={line} disabled={locked} completionAction={<div className="quest-actions"><Button onClick={() => line.current_quest && void act({ kind: 'complete', questId: line.current_quest.id, revision: line.revision })} loading={mutation.pending && activity === 'complete'} disabled={locked || line.status !== 'active'}>Complete stage</Button>{line.status === 'paused' && <p className="helper muted">Resume this questline to complete its current stage.</p>}</div>} />
        {line.status === 'completed' && <Card tone="leaf"><EmptyState title="Campaign completed" action={<Link className="text-link" to="/">Start another check-in →</Link>}>Questline completed. Your earned XP and completed stage history remain available.</EmptyState></Card>}
        <p className="helper muted">Local AI suggestions may need your review. Hints and smaller starting actions are not connected in this phase.</p>
      </>}
    </div>
    <aside className="quest-sidebar" aria-label="Saved questlines and quest controls">
      <SavedQuestlines selectedId={id} revision={listRevision} />
      {line && line.status !== 'completed' && <Card tone="leaf" className="quest-pace"><h2>Adjust your pace</h2><p className="muted">Pausing keeps your current quest and completed progress. No XP is deducted.</p><div className="quest-actions"><Button variant="secondary" loading={mutation.pending && (activity === 'pause' || activity === 'resume')} disabled={locked} onClick={() => void act({ kind: line.status === 'paused' ? 'resume' : 'pause', revision: line.revision })}>{line.status === 'paused' ? 'Resume questline' : 'Pause questline'}</Button><Button variant="quiet" disabled={locked} onClick={() => void state.reload()}>Reload saved state</Button></div><ReplanForm key={line.revision} line={line} disabled={locked} onSubmit={request => void act({ kind: 'replan', request })} /></Card>}
      {activity === 'replan' && mutationFeedback && <div ref={replanFeedback} tabIndex={-1} className="replan-feedback">{mutationFeedback}</div>}
    </aside>
  </div>
}
