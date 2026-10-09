import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { Sprout } from '../components/Sprout'
import { Badge, Button, Card, ErrorNotice, Input, LoadingIndicator, Select, Textarea } from '../components/UI'
import { useAppProfile } from '../components/AppShell'
import { useMutation } from '../hooks/useMutation'
import { ApiError, asApiError, generateQuestline, getCheckIn, submitCheckIn } from '../lib/api'
import type { CheckIn, CheckInAnswer, CheckInContext, CheckInStart, Energy } from '../lib/questTypes'
import { isUUID } from '../lib/validate'

interface Draft { goal: string; minutes: string; energy: Energy | ''; deadline: string; notes: string }
const emptyDraft: Draft = { goal: '', minutes: '', energy: '', deadline: '', notes: '' }
function localDeadline(value: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}
function draftFrom(context: CheckInContext): Draft {
  return { goal: context.goal, minutes: String(context.available_minutes), energy: context.energy, deadline: localDeadline(context.deadline), notes: context.contextual_notes ?? '' }
}

export default function Home() {
  const [params, setParams] = useSearchParams()
  const savedId = params.get('check_in')
  const navigate = useNavigate()
  const profile = useAppProfile()
  const [draft, setDraft] = useState<Draft>(emptyDraft)
  const [checkIn, setCheckIn] = useState<CheckIn | null>(null)
  const [answer, setAnswer] = useState('')
  const [restoring, setRestoring] = useState(Boolean(savedId))
  const [readError, setReadError] = useState<ApiError | null>(null)
  const [validation, setValidation] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)
  const mutation = useMutation(savedId ?? 'new')
  const alive = useRef(true)
  const recoveryController = useRef<AbortController | null>(null)
  useEffect(() => { alive.current = true; return () => { alive.current = false; recoveryController.current?.abort() } }, [])

  useEffect(() => {
    recoveryController.current?.abort()
    if (!savedId) { setRestoring(false); setCheckIn(null); setReadError(null); setAnswer(''); return }
    // A successful submit already supplied this exact committed view.
    if (checkIn?.id === savedId && revision === 0) return
    const controller = new AbortController()
    setRestoring(true)
    setReadError(null)
    setCheckIn(null)
    async function restore() {
      try {
        if (!isUUID(savedId!)) throw new ApiError('CHECK_IN_NOT_FOUND', 'This check-in address is invalid. Start a new check-in.', 404, false)
        const result = await getCheckIn(savedId!, controller.signal)
        if (!controller.signal.aborted) { setCheckIn(result); setDraft(draftFrom(result.context)); setAnswer(result.clarification_answer ?? '') }
      } catch (cause) {
        if (!controller.signal.aborted) setReadError(asApiError(cause))
      } finally {
        if (!controller.signal.aborted) setRestoring(false)
      }
    }
    void restore()
    return () => controller.abort()
  }, [savedId, revision])

  function applyCheckIn(value: CheckIn) {
    setCheckIn(value)
    setDraft(draftFrom(value.context))
    setReadError(null)
    setParams({ check_in: value.id }, { replace: true })
  }
  function revise() {
    mutation.clear(true)
    setCheckIn(null)
    setAnswer('')
    setReadError(null)
    setValidation(null)
    setRevision(0)
    setParams({}, { replace: true })
  }
  async function recoverState() {
    if (!checkIn) return
    const controller = new AbortController()
    recoveryController.current = controller
    setRestoring(true)
    try {
      const value = await getCheckIn(checkIn.id, controller.signal)
      if (!alive.current || controller.signal.aborted) return
      applyCheckIn(value)
      if (value.status === 'consumed' && value.questline_id) { profile.refresh(); navigate(`/questlines/${value.questline_id}`) }
    } catch (cause) {
      if (alive.current && !controller.signal.aborted) setReadError(asApiError(cause))
    } finally {
      if (alive.current && !controller.signal.aborted) setRestoring(false)
    }
  }
  async function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setValidation(null)
    const minutes = Number(draft.minutes)
    if (!draft.goal.trim() || draft.goal.length > 4000 || !Number.isInteger(minutes) || minutes < 1 || minutes > 1440 || !draft.energy || draft.notes.length > 2000) {
      setValidation('Enter a goal, 1–1440 whole minutes, and an energy level. Notes may contain up to 2,000 characters.')
      return
    }
    const parsedDeadline = draft.deadline ? new Date(draft.deadline) : null
    if (parsedDeadline && !Number.isFinite(parsedDeadline.getTime())) { setValidation('Choose a valid local deadline, or leave it blank.'); return }
    const body: CheckInStart = { mode: 'start', goal: draft.goal.trim(), available_minutes: minutes, energy: draft.energy, deadline: parsedDeadline?.toISOString() ?? null, contextual_notes: draft.notes.trim() || null }
    const result = await mutation.run(`check-in:${JSON.stringify(body)}`, (key, signal) => submitCheckIn(body, key, signal))
    if (result && 'data' in result) applyCheckIn(result.data)
  }
  async function clarify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!checkIn || !answer.trim()) return
    const body: CheckInAnswer = { mode: 'answer', check_in_id: checkIn.id, expected_revision: checkIn.revision, answer: answer.trim() }
    const result = await mutation.run(`answer:${JSON.stringify(body)}`, (key, signal) => submitCheckIn(body, key, signal))
    if (result && 'data' in result) applyCheckIn(result.data)
    else if (result && (result.error.status === 409 || result.error.uncertain)) await recoverState()
  }
  async function generate() {
    if (!checkIn || checkIn.status !== 'ready') return
    const body = { check_in_id: checkIn.id, expected_check_in_revision: checkIn.revision }
    const result = await mutation.run(`generate:${JSON.stringify(body)}`, (key, signal) => generateQuestline(body, key, signal))
    if (result && 'data' in result) { profile.refresh(); navigate(`/questlines/${result.data.id}`) }
    else if (result && (result.error.status === 409 || result.error.uncertain)) await recoverState()
  }
  const blocked = mutation.pending || mutation.waitSeconds > 0 || restoring || Boolean(readError)
  const error = validation ?? readError?.message ?? mutation.error?.message

  return <div className="home-page">
    <section className="welcome-hero"><Badge>A little direction, at your pace</Badge><div className="hero-title"><h1>One small step<br />at a time.</h1><Sprout /></div><p>Bring a goal. Make room for a manageable start.<br className="desktop-break" /> Your quest companion is right here on this laptop.</p></section>
    <Card elevated className="check-in-card">
      <div className="section-heading"><h2>A place to begin</h2>{checkIn && <Badge tone="sage">{checkIn.status === 'needs_follow_up' ? 'One detail needed' : checkIn.status === 'ready' ? 'Ready to plan' : 'Saved questline'}</Badge>}</div>
      <p className="muted">What would you like to move forward?</p>
      {restoring && <LoadingIndicator>Restoring your saved check-in…</LoadingIndicator>}
      {error && <ErrorNotice>{error}{mutation.waitSeconds > 0 && <p>Retry in {mutation.waitSeconds} seconds.</p>}{mutation.error?.uncertain && <p>The previous action may have succeeded. Retry unchanged to recover it safely.</p>}</ErrorNotice>}
      <form className="stack" onSubmit={start}>
        <fieldset disabled={blocked || Boolean(checkIn) || Boolean(savedId && readError)} className="stack form-fields">
          <div><label htmlFor="goal">Your goal or deliverable</label><Textarea id="goal" value={draft.goal} onChange={e => setDraft({ ...draft, goal: e.target.value })} required rows={3} maxLength={4000} placeholder="e.g. Write three unit tests for my FastAPI login endpoint" /></div>
          <div className="form-row"><div><label htmlFor="minutes">Time available now <span className="muted">(minutes)</span></label><Input id="minutes" value={draft.minutes} onChange={e => setDraft({ ...draft, minutes: e.target.value })} required type="number" min={1} max={1440} step={1} placeholder="e.g. 20" /><p className="helper muted">For this session, not the entire goal.</p></div><div><label htmlFor="energy">Your energy</label><Select id="energy" value={draft.energy} onChange={e => setDraft({ ...draft, energy: e.target.value as Energy })} required><option value="" disabled>Choose your energy</option><option value="low">Low — a gentle start</option><option value="medium">Medium — a steady pace</option><option value="high">High — ready to focus</option></Select></div></div>
          <div><label htmlFor="deadline">Deadline <span className="muted">(optional, local time)</span></label><Input id="deadline" value={draft.deadline} onChange={e => setDraft({ ...draft, deadline: e.target.value })} type="datetime-local" /></div>
          <div><label htmlFor="notes">Context or notes <span className="muted">(optional)</span></label><Textarea id="notes" value={draft.notes} onChange={e => setDraft({ ...draft, notes: e.target.value })} rows={2} maxLength={2000} placeholder="Requirements, materials or constraints that matter…" /></div>
        </fieldset>
        {!checkIn && !savedId && <Button type="submit" loading={mutation.pending} disabled={blocked} className="full-width">{mutation.pending ? 'Saving your check-in…' : mutation.error ? 'Retry check-in' : 'Start my journey'}</Button>}
      </form>
      {checkIn?.status === 'needs_follow_up' && <form onSubmit={clarify} className="clarification-panel stack"><h3>One helpful detail</h3><p>{checkIn.question}</p><div><label htmlFor="clarification">Your answer</label><Textarea id="clarification" value={answer} onChange={e => setAnswer(e.target.value)} required rows={3} maxLength={2000} disabled={blocked} /></div><Button type="submit" loading={mutation.pending} disabled={blocked || !answer.trim()}>Continue</Button></form>}
      {checkIn?.status === 'ready' && <div className="ready-panel stack">{checkIn.clarification_answer && <p><strong>Your detail:</strong> {checkIn.clarification_answer}</p>}<p>Your local model will choose 2–6 meaningful stages for your whole goal, which may span several sessions. Only the first stage is revealed.</p><Button onClick={() => void generate()} loading={mutation.pending} disabled={blocked}>{mutation.pending ? 'Generating quests locally…' : mutation.error ? 'Retry Generate My Quests' : 'Generate My Quests'}</Button>{mutation.pending && <p role="status" className="helper muted">Local inference can take up to two minutes. Your check-in stays saved if generation fails.</p>}</div>}
      {checkIn?.status === 'consumed' && <div className="ready-panel"><Link className="text-link" to={`/questlines/${checkIn.questline_id}`}>Continue your saved questline →</Link></div>}
      {(checkIn || readError) && <div className="quest-actions"><Button variant="quiet" onClick={revise} disabled={restoring || mutation.pending || mutation.waitSeconds > 0 || Boolean(mutation.error?.uncertain) || mutation.error?.code === 'REQUEST_IN_PROGRESS'}>{readError ? 'Start a new check-in' : 'Revise check-in'}</Button>{readError && readError.retryable && <Button variant="secondary" onClick={() => setRevision(value => value + 1)} disabled={restoring || mutation.pending}>Retry loading</Button>}</div>}
    </Card>
    <p className="home-disclosure">Quest suggestions come from a local AI model and may need your review.<br />No cloud inference. No account required. <Link className="text-link" to="/questlines">Open saved quests</Link></p>
  </div>
}
