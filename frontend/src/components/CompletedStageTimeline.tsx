import { Link } from 'react-router'
import { campaignEarnedXP, completionMessage } from '../lib/campaign'
import type { Questline } from '../lib/questTypes'
import { Icon } from './Icon'
import { Badge, Card, EmptyState } from './UI'

const completionDate = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })

export function CompletedStageTimeline({ line }: { line: Questline }) {
  const stages = [...line.completed_quests].sort((a, b) => Date.parse(a.completed_at!) - Date.parse(b.completed_at!) || a.order - b.order)
  const earnedXP = campaignEarnedXP(line)
  return <div className="journey-history stack">
    <Card tone="leaf" className="journey-summary">
      <div className="section-heading"><p className="eyebrow">A record of your effort</p><Badge tone={line.status === 'completed' ? 'sage' : 'neutral'}>{line.status}</Badge></div>
      <h2 className="goal-heading">{line.goal}</h2>
      <dl className="journey-stats">
        <div><dt>Stages completed</dt><dd>{line.progress.completed_count} <span>/ {line.progress.total_count}</span></dd></div>
        <div><dt>Questline XP earned</dt><dd data-journey-xp>{earnedXP.toLocaleString()} XP</dd></div>
      </dl>
      {line.status !== 'completed' && <Link className="button button-secondary" to={`/questlines/${line.id}`}>{line.status === 'paused' ? 'Return to paused questline' : 'Continue this questline'} <span aria-hidden="true">→</span></Link>}
      {line.status === 'paused' && <p className="helper muted">Taking a pause keeps every completed step. Resume in My Quests when you are ready.</p>}
    </Card>
    <section aria-labelledby="journey-timeline-title">
      <div className="section-heading"><h2 id="journey-timeline-title">Completed stages</h2><span className="muted helper">{stages.length ? 'In completion order' : 'One step at a time'}</span></div>
      {stages.length === 0 ? <Card className="journey-empty"><EmptyState title="Your first small step belongs here">Your journey starts with one small step. Completed stages will appear here.</EmptyState></Card> : <ol className="stage-timeline" aria-label="Completed-stage timeline">
        {stages.map(quest => <li key={quest.id} className="stage-timeline-item" data-completed-stage={quest.id}>
          <span className="journey-node node-completed" aria-hidden="true"><Icon name="check" /></span>
          <Card className="stage-memory">
            <div className="section-heading"><span className="stage-number">Stage {quest.order}</span><Badge tone="sage">{quest.xp_reward} XP earned</Badge></div>
            <h3>{quest.title}</h3>
            <p className="helper muted">Completed <time dateTime={quest.completed_at!}>{completionDate.format(new Date(quest.completed_at!))}</time></p>
            <p className="stage-memory-encouragement" data-journey-encouragement><Icon name="sprout" /><span>{completionMessage(quest)}</span></p>
            <details className="stage-memory-details">
              <summary>Revisit this stage<span className="helper">View saved details</span></summary>
              <div><h4>What you worked on</h4><p>{quest.action}</p></div>
              <div><h4>How you checked it was done</h4><p>{quest.completion_criteria}</p></div>
              {quest.starting_action && <div><h4>Your starting action</h4><p>{quest.starting_action}</p></div>}
              {quest.hint && <div><h4>Saved hint</h4><p>{quest.hint}</p></div>}
            </details>
          </Card>
        </li>)}
        {line.status === 'completed' && <li className="stage-timeline-item">
          <span className="journey-node node-current" aria-hidden="true"><Icon name="sprout" /></span>
          <Card tone="butter" className="journey-finished" data-journey-finished>
            <Badge>A goal brought to life</Badge>
            <h3>Look how far you have grown.</h3>
            <p>You completed all {stages.length} stages and earned {earnedXP.toLocaleString()} XP along the way. Every small step helped you get here.</p>
            <Link className="text-link" to="/">Start another check-in →</Link>
          </Card>
        </li>}
      </ol>}
    </section>
    <p className="muted helper">Completion times use your local time zone. Your completed work stays saved on this laptop.</p>
  </div>
}
