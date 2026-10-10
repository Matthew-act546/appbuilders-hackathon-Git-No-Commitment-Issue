import { useLayoutEffect, useRef } from 'react'
import type { KeyboardEvent } from 'react'
import type { Completion, Quest } from '../lib/questTypes'
import { completionMessage } from '../lib/campaign'
import { Badge, Button, Card } from './UI'
import { Sprout } from './Sprout'

export function CompletionCelebration({ result, quest, onContinue }: { result: Completion; quest: Quest; onContinue: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const heading = useRef<HTMLHeadingElement>(null)
  useLayoutEffect(() => {
    const popup = dialog.current
    if (!popup) return
    const overflow = document.body.style.overflow
    const position = { left: window.scrollX, top: window.scrollY, behavior: 'instant' as const }
    document.body.style.overflow = 'hidden'
    popup.showModal()
    heading.current?.focus({ preventScroll: true })
    window.scrollTo(position)
    return () => {
      popup.close()
      document.body.style.overflow = overflow
      window.scrollTo(position)
    }
  }, [quest.id])
  function dismiss() {
    dialog.current?.close()
    onContinue()
  }
  function keepFocusInPopup(event: KeyboardEvent<HTMLDialogElement>) {
    if (event.key !== 'Tab') return
    const buttons = event.currentTarget.querySelectorAll<HTMLButtonElement>('button')
    const first = buttons[0]
    const last = buttons[buttons.length - 1]
    if (event.shiftKey && (document.activeElement === first || document.activeElement === heading.current)) {
      event.preventDefault()
      last?.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first?.focus()
    }
  }
  const next = result.questline.current_quest
  return <dialog ref={dialog} className="completion-dialog" aria-labelledby="completion-heading" aria-describedby="completion-message" data-completion-celebration onKeyDown={keepFocusInPopup} onCancel={event => { event.preventDefault(); dismiss() }}>
    <Card tone="leaf" className="completion-celebration">
      <Button variant="quiet" className="icon-button completion-close" aria-label="Close completion popup" onClick={dismiss}><span aria-hidden="true">×</span></Button>
      <Sprout small />
      <div className="stack">
        <h2 id="completion-heading" ref={heading} tabIndex={-1}>Quest Complete!</h2>
        <p id="completion-message" data-completion-message>{completionMessage(quest)}</p>
        <div><Badge>{result.awarded_xp > 0 ? `+${result.awarded_xp} XP awarded` : '0 additional XP · already rewarded'}</Badge></div>
        {result.questline.status === 'completed' ? <p>Campaign completed. Your progress is saved.</p> : next && <p>{result.outcome === 'completed' ? `Stage ${next.order} unlocked.` : `Current stage: ${next.order}.`} {result.questline.status === 'paused' ? 'Resume when you’re ready.' : 'Continue at your own pace.'}</p>}
        <div><Button onClick={dismiss}>Continue Journey</Button></div>
      </div>
    </Card>
  </dialog>
}
