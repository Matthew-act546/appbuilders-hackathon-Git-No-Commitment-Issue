import { useEffect, useRef } from 'react'
import type { Completion, Quest } from '../lib/questTypes'
import { completionMessage } from '../lib/campaign'
import { Badge, Button, Card } from './UI'
import { Sprout } from './Sprout'

export function CompletionCelebration({ result, quest, onContinue }: { result: Completion; quest: Quest; onContinue: () => void }) {
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { heading.current?.focus() }, [quest.id])
  const next = result.questline.current_quest
  return <Card tone="leaf" elevated className="completion-celebration" aria-labelledby="completion-heading" data-completion-celebration>
    <Sprout small />
    <div className="stack">
      <h2 id="completion-heading" ref={heading} tabIndex={-1}>Quest Complete!</h2>
      <p data-completion-message>{completionMessage(quest)}</p>
      <div><Badge>{result.awarded_xp > 0 ? `+${result.awarded_xp} XP awarded` : '0 additional XP · already rewarded'}</Badge></div>
      {result.questline.status === 'completed' ? <p>Campaign completed. Your progress is saved.</p> : next && <p>{result.outcome === 'completed' ? `Stage ${next.order} unlocked.` : `Current stage: ${next.order}.`} {result.questline.status === 'paused' ? 'Resume when you’re ready.' : 'Continue at your own pace.'}</p>}
      <div><Button onClick={onContinue}>Continue Journey</Button></div>
    </div>
  </Card>
}
