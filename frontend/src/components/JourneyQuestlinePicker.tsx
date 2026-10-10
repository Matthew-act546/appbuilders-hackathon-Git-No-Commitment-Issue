import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { asApiError, getQuestlines } from '../lib/api'
import type { ApiError } from '../lib/api'
import type { QuestlineList } from '../lib/questTypes'
import { Button, Card, EmptyState, ErrorNotice, LoadingIndicator, Select } from './UI'

export function JourneyQuestlinePicker({ selectedId, selectedGoal }: { selectedId?: string; selectedGoal?: string }) {
  const navigate = useNavigate()
  const [offset, setOffset] = useState(0)
  const [page, setPage] = useState<QuestlineList | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)
  const [refresh, setRefresh] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    async function load() {
      try {
        const result = await getQuestlines(offset, controller.signal)
        if (!controller.signal.aborted) setPage(result)
      } catch (cause) {
        if (!controller.signal.aborted) { setPage(null); setError(asApiError(cause)) }
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [offset, refresh])

  const selectedOnPage = page?.items.some(line => line.id === selectedId)
  return <Card className="journey-picker" aria-label="Choose a questline">
    <div className="journey-picker-controls">
      <div>
        <label htmlFor="journey-questline">Revisit a questline</label>
        <Select id="journey-questline" value={selectedId ?? ''} disabled={loading || !page || page.items.length === 0} aria-describedby="journey-picker-help" onChange={event => navigate(`/journey/${event.target.value}`)}>
          <option value="" disabled>Choose a saved questline</option>
          {selectedId && !selectedOnPage && <option value={selectedId}>{selectedGoal ?? 'Selected questline — history below'}</option>}
          {page?.items.map(line => <option key={line.id} value={line.id}>{line.goal} · {line.status} · {line.progress.completed_count}/{line.progress.total_count} completed</option>)}
        </Select>
      </div>
      <Button variant="quiet" disabled={loading} onClick={() => setRefresh(value => value + 1)}>Refresh list</Button>
    </div>
    <p id="journey-picker-help" className="muted helper">Choose a goal to revisit its completed stages. Active, paused and finished questlines stay here.</p>
    {loading && <LoadingIndicator>Reading saved questlines…</LoadingIndicator>}
    {error && <ErrorNotice action={<Button variant="secondary" onClick={() => setRefresh(value => value + 1)}>Retry saved list</Button>}>{error.message}</ErrorNotice>}
    {!loading && page && page.items.length === 0 && <EmptyState title={offset ? 'No more saved questlines' : 'A fresh starting point'} action={!offset && <Link className="text-link" to="/">Start a check-in →</Link>}>{offset ? 'Return to the previous page to choose a goal.' : 'Your saved goals will appear here after you generate a questline.'}</EmptyState>}
    {!loading && page && (offset > 0 || page.has_more) && <div className="journey-picker-pages">
      <Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - 20))}>Previous goals</Button>
      <span className="muted helper" role="status">{page.items.length ? `Goals ${offset + 1}–${offset + page.items.length}` : 'End of saved goals'}</span>
      <Button variant="secondary" disabled={!page.has_more} onClick={() => setOffset(value => value + 20)}>Next goals</Button>
    </div>}
  </Card>
}
