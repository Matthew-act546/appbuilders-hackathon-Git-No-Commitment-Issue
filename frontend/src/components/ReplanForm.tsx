import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import type { Energy, Questline, ReplanRequest } from '../lib/questTypes'
import { Button, ErrorNotice, Input, Select, Textarea } from './UI'

export function ReplanForm({ line, disabled, onSubmit }: { line: Questline; disabled: boolean; onSubmit: (request: ReplanRequest) => void }) {
  const [open, setOpen] = useState(false)
  const [minutes, setMinutes] = useState(String(line.available_minutes))
  const [energy, setEnergy] = useState<Energy>(line.energy)
  const [reason, setReason] = useState('')
  const [validation, setValidation] = useState<string | null>(null)
  const form = useRef<HTMLFormElement>(null)
  const canReplan = line.status === 'active' && line.progress.completed_count < 6

  useEffect(() => {
    if (open) form.current?.querySelector('input')?.focus({ preventScroll: true })
  }, [open])

  function close() {
    setOpen(false)
    setMinutes(String(line.available_minutes))
    setEnergy(line.energy)
    setReason('')
    setValidation(null)
    document.getElementById(`replan-toggle-${line.id}`)?.focus({ preventScroll: true })
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (disabled || !canReplan) return
    const available = Number(minutes)
    if (!Number.isInteger(available) || available < 1 || available > 1440 || reason.length > 1000) {
      setValidation('Enter 1–1440 whole minutes and keep your explanation within 1,000 characters.')
      return
    }
    setValidation(null)
    // Omit deadline and contextual_notes so the server preserves saved values.
    onSubmit({ expected_revision: line.revision, available_minutes: available, energy, reason: reason.trim() || null })
  }

  return <div className="replan-panel">
    <Button id={`replan-toggle-${line.id}`} variant="secondary" className="full-width" disabled={disabled || !canReplan} aria-expanded={open} aria-controls={`replan-form-${line.id}`} onClick={() => open ? close() : setOpen(true)}>Replan remaining stages</Button>
    {!canReplan && <p className="helper muted">{line.status === 'paused' ? 'Resume this questline before replanning.' : 'This questline has reached the six-stage replan limit. You can still complete its saved stages.'}</p>}
    {open && canReplan && <form ref={form} id={`replan-form-${line.id}`} className="stack" onSubmit={submit} noValidate aria-label="Replan remaining stages">
      <p className="helper muted">Make room for a different pace. Only unfinished stages change; completed work and earned XP stay saved.</p>
      {validation && <ErrorNotice>{validation}</ErrorNotice>}
      <fieldset disabled={disabled} className="form-fields stack">
        <div><label htmlFor="replan-minutes">Time available now <span className="muted">(minutes)</span></label><Input id="replan-minutes" type="number" min={1} max={1440} step={1} required value={minutes} onChange={event => setMinutes(event.target.value)} /><p className="helper muted">For your next session, rather than the whole goal.</p></div>
        <div><label htmlFor="replan-energy">Your energy</label><Select id="replan-energy" value={energy} onChange={event => setEnergy(event.target.value as Energy)}><option value="low">Low — a gentle start</option><option value="medium">Medium — a steady pace</option><option value="high">High — ready to focus</option></Select></div>
        <div><label htmlFor="replan-reason">What changed? <span className="muted">(optional)</span></label><Textarea id="replan-reason" rows={3} maxLength={1000} value={reason} onChange={event => setReason(event.target.value)} placeholder="e.g. I have less time today and need a smaller next step." /></div>
      </fieldset>
      <p className="helper muted">Your goal, saved deadline and original notes stay the same.</p>
      <div className="quest-actions"><Button type="submit" disabled={disabled}>Generate revised stages</Button><Button variant="quiet" disabled={disabled} onClick={close}>Cancel replanning</Button></div>
    </form>}
  </div>
}
