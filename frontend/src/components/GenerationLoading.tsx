import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { Energy } from '../lib/questTypes'
import { Badge, Button, Card } from './UI'
import { Sprout } from './Sprout'

const encouragement: Record<Energy, readonly string[]> = {
  low: [
    'A small step still makes room for progress.',
    'You can begin gently and decide what comes next.',
    'Your pace is allowed to match your energy.',
    'You do not have to do it all in one sitting.',
    'Even a quiet beginning can grow into something useful.',
    'One manageable action is enough for a start.',
  ],
  medium: [
    'Steady steps can carry a meaningful goal forward.',
    'Choose one clear action, then give it your attention.',
    'Your next step can be small and purposeful.',
    'Progress has room for a comfortable rhythm.',
    'A little consistency can help a good idea take root.',
    'Give yourself room to learn as you move forward.',
  ],
  high: [
    'Let your energy support one clear next step.',
    'Focus on what matters, with room to rest along the way.',
    'A strong start can still leave room for breaks.',
    'Put your momentum into something meaningful to you.',
    'Bring your curiosity; the path can unfold one step at a time.',
    'Build on your momentum at a pace you can sustain.',
  ],
}
const energyLabel: Record<Energy, string> = {
  low: 'Low energy · A gentle start',
  medium: 'Medium energy · A steady pace',
  high: 'High energy · Room to focus',
}

function nextEncouragement(energy: Energy, previous?: string) {
  const choices = encouragement[energy].filter(quote => quote !== previous)
  return choices[Math.floor(Math.random() * choices.length)]
}

export function GenerationLoading({ energy, purpose = 'generate' }: { energy: Energy; purpose?: 'generate' | 'replan' }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const heading = useRef<HTMLHeadingElement>(null)
  const [quote, setQuote] = useState(() => nextEncouragement(energy))

  useLayoutEffect(() => {
    const popup = dialog.current
    if (!popup) return
    const previousFocus = document.activeElement
    const overflow = document.body.style.overflow
    const position = { left: window.scrollX, top: window.scrollY, behavior: 'instant' as const }
    document.body.style.overflow = 'hidden'
    popup.showModal()
    heading.current?.focus({ preventScroll: true })
    popup.scrollTop = 0
    window.scrollTo(position)
    return () => {
      popup.close()
      document.body.style.overflow = overflow
      window.scrollTo(position)
      queueMicrotask(() => {
        if (previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus({ preventScroll: true })
      })
    }
  }, [])

  useEffect(() => {
    const timer = window.setInterval(() => setQuote(previous => nextEncouragement(energy, previous)), 10000)
    return () => window.clearInterval(timer)
  }, [energy])

  return <dialog ref={dialog} className="completion-dialog generation-dialog" aria-labelledby="generation-heading" aria-describedby="generation-description" data-generation-loading data-energy={energy} onCancel={event => event.preventDefault()} onKeyDown={event => {
    if (event.key === 'Tab') { event.preventDefault(); dialog.current?.querySelector('button')?.focus() }
  }}>
    <Card tone="leaf" className="generation-loading">
      <div className="generation-seed" aria-hidden="true"><span className="generation-orbit" /><Sprout small /></div>
      <div className="generation-intro">
        <h2 id="generation-heading" ref={heading} tabIndex={-1}>{purpose === 'replan' ? 'Making room for your new pace' : 'Your next steps are growing'}</h2>
        <p id="generation-description" className="muted">{purpose === 'replan' ? 'Sibol is reshaping your unfinished stages. Your completed work stays saved.' : 'Sibol is creating a manageable path for your goal.'}</p>
        <div><Badge tone="sage">{energyLabel[energy]}</Badge></div>
      </div>
      <blockquote className="generation-quote" aria-live="polite" aria-atomic="true"><p data-generation-quote>“{quote}”</p></blockquote>
      <div className="generation-track" role="progressbar" aria-label={purpose === 'replan' ? 'Replanning your unfinished stages' : 'Creating your quests'}><span /></div>
      <Button variant="quiet" onClick={() => setQuote(previous => nextEncouragement(energy, previous))}>Another encouragement</Button>
      <p className="helper muted">This closes automatically when planning finishes.<br />{purpose === 'replan' ? 'Your saved questline is kept if a retry is needed.' : 'Your check-in stays saved if a retry is needed.'}</p>
    </Card>
  </dialog>
}
