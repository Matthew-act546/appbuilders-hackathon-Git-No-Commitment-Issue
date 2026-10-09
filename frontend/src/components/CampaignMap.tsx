import { useId, useState } from 'react'
import type { ReactNode } from 'react'
import type { Profile, Quest, Questline } from '../lib/questTypes'
import { campaignEarnedXP, campaignStages, completionMessage, stageObjectives } from '../lib/campaign'
import { Badge, Card } from './UI'
import { Icon } from './Icon'

export function CampaignOverview({ line, profile }: { line: Questline; profile: Profile | null }) {
  return <>
    <Card tone="leaf" className="campaign-settings">
      <h2 className="eyebrow">YOUR ADAPTIVE QUEST SETTINGS</h2>
      <div className="section-heading"><h3 className="goal-heading">{line.goal}</h3><Badge tone={line.status === 'completed' ? 'sage' : 'butter'}>{line.status}</Badge></div>
      <div className="quest-meta"><Badge tone="neutral">{line.available_minutes} minutes available</Badge><Badge tone="neutral">{line.energy} energy</Badge></div>
      <p>These saved settings guide the request for a manageable starting action. The session time is not the whole campaign’s budget; estimates are suggestions to review.</p>
      {line.energy === 'low' && <p className="helper muted">Low energy asks for a small first step. It does not guarantee every suggestion will suit you.</p>}
      {line.deadline && <p className="helper muted">Deadline: <time dateTime={line.deadline}>{new Date(line.deadline).toLocaleString()}</time>. Passing a deadline does not remove earned XP.</p>}
    </Card>
    <Card className="campaign-progress">
      <h2 className="eyebrow">CAMPAIGN PROGRESS</h2>
      <div className="campaign-stats"><div><span>Campaign XP earned</span><strong data-campaign-xp>{campaignEarnedXP(line).toLocaleString()} XP</strong><small>From completed stages in this campaign</small></div><div><span>Lifetime profile XP</span><strong>{profile ? `${profile.total_xp.toLocaleString()} XP` : 'Unavailable'}</strong><small>{profile ? `Level ${profile.level} · across all campaigns` : 'Check the local backend status'}</small></div></div>
      <label className="campaign-progress-label" htmlFor={`campaign-progress-${line.id}`}>{line.progress.completed_count} of {line.progress.total_count} stages completed</label>
      <progress id={`campaign-progress-${line.id}`} max={line.progress.total_count} value={line.progress.completed_count} />
      <p className="helper muted">Completion and rewards update only after the backend confirms them.</p>
    </Card>
  </>
}

function StageContent({ quest, number, disabled, action }: { quest: Quest; number: number; disabled: boolean; action?: ReactNode }) {
  const [checked, setChecked] = useState<number[]>([])
  const uid = useId()
  const completed = quest.status === 'completed'
  const objectives = stageObjectives(quest)
  const shortDescription = quest.action.split(/(?<=[.!?])\s+(?=[A-Z])/u)[0]
  return <Card tone={completed ? 'leaf' : 'butter'} elevated={!completed} className={`campaign-stage ${completed ? 'stage-completed' : 'current-quest'}`}>
    <div className="section-heading"><span className="stage-number">Stage {number}</span><Badge tone={completed ? 'sage' : 'butter'}>{completed ? 'Completed' : quest.status === 'paused' ? 'Paused stage' : 'Current stage'}</Badge></div>
    <h3 className={completed ? 'campaign-stage-title' : 'quest-title'}>{quest.title}</h3>
    <p className="quest-content">{shortDescription}</p>
    <div className="quest-meta"><Badge tone="neutral">{quest.estimated_minutes} min estimated</Badge><Badge tone="neutral">{quest.difficulty}</Badge><Badge>{completed ? `${quest.xp_reward} XP earned` : `+${quest.xp_reward} XP reward`}</Badge></div>
    {completed && <p className="completed-encouragement" data-history-encouragement>{completionMessage(quest)}</p>}
    {completed ? <><h4>Stage objectives</h4><ul className="stage-objective-reference">{objectives.map((objective, index) => <li key={index}><strong>{objective.label}:</strong> {objective.text}</li>)}</ul><p className="helper muted">Whole-stage completion saved <time dateTime={quest.completed_at!}>{new Date(quest.completed_at!).toLocaleString()}</time>. Individual checklist marks are not stored.</p></> : <>
      <fieldset className="stage-objectives" disabled={disabled}><legend>Stage objectives</legend>{objectives.map((objective, index) => <label key={index} htmlFor={`${uid}-${index}`}><input id={`${uid}-${index}`} type="checkbox" checked={checked.includes(index)} onChange={event => setChecked(previous => event.target.checked ? [...previous, index] : previous.filter(value => value !== index))} /><span><strong>{objective.label}</strong><span>{objective.text}</span></span></label>)}</fieldset>
      <p className="helper muted">Optional checklist for this open stage; marks reset after refresh. Only whole-stage completion is saved. Checking a box does not award XP.</p>
      {action}
    </>}
  </Card>
}

export function CampaignMap({ line, disabled, completionAction }: { line: Questline; disabled: boolean; completionAction: ReactNode }) {
  return <section aria-labelledby={`campaign-map-${line.id}`} className="campaign-map">
    <div className="section-heading"><h2 id={`campaign-map-${line.id}`} tabIndex={-1}>CAMPAIGN MAP</h2><Badge tone="neutral">{line.progress.total_count} stages</Badge></div>
    <p className="muted helper">Follow the revealed actions toward your goal, one stage at a time. Future details appear only after completion.</p>
    <ol className="campaign-path">{campaignStages(line).map(stage => <li key={stage.kind === 'locked' ? `locked-${stage.number}` : stage.quest.id} className={`campaign-node ${stage.kind === 'locked' ? 'stage-locked' : ''}`}>
      <span className={`journey-node ${stage.kind === 'locked' ? 'node-locked' : stage.quest.status === 'completed' ? 'node-completed' : 'node-current'}`}><Icon name={stage.kind === 'locked' ? 'lock' : stage.quest.status === 'completed' ? 'check' : 'sprout'} /></span>
      {stage.kind === 'locked' ? <Card className="locked-stage"><h3>Stage {stage.number} — Locked</h3><p>Complete Stage {stage.number - 1} to reveal this stage.</p></Card> : <div><StageContent key={stage.quest.id} quest={stage.quest} number={stage.number} disabled={disabled || line.status !== 'active'} action={stage.quest.status === 'completed' ? undefined : completionAction} />{stage.quest.status !== 'completed' && line.progress.remaining_count > 1 && <p className="stage-unlock-note helper">Complete Stage {stage.number} to unlock Stage {stage.number + 1}.</p>}</div>}
    </li>)}</ol>
  </section>
}
