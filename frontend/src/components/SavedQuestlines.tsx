import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { asApiError, getQuestlines } from '../lib/api'
import type { ApiError } from '../lib/api'
import type { QuestlineList } from '../lib/questTypes'
import { Badge, Button, Card, EmptyState, ErrorNotice, LoadingIndicator } from './UI'

export function SavedQuestlines({ selectedId, revision = 0 }: { selectedId?: string; revision?: number }) {
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
        const value = await getQuestlines(offset, controller.signal)
        if (!controller.signal.aborted) setPage(value)
      } catch (cause) {
        if (!controller.signal.aborted) { setPage(null); setError(asApiError(cause)) }
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [offset, revision, refresh])
  return <Card className="saved-questlines">
    <div className="section-heading"><h2>Saved questlines</h2><Button variant="quiet" disabled={loading} onClick={() => setRefresh(v => v + 1)}>Refresh list</Button></div>
    <div className="saved-questlines-scroll" role="region" aria-label="Saved questlines list" tabIndex={0}>
      {loading && <LoadingIndicator>Reading saved questlines…</LoadingIndicator>}
      {error && <ErrorNotice action={<Button variant="secondary" onClick={() => setRefresh(v => v + 1)}>Retry saved list</Button>}>{error.message}</ErrorNotice>}
      {!loading && page && page.items.length === 0 && <EmptyState title={offset ? 'No more saved work' : 'A fresh starting point'} action={<Link className="text-link" to="/">Start a check-in →</Link>}>{offset ? 'Return to the previous page to choose a questline.' : 'Your saved questlines will appear here after successful local generation.'}</EmptyState>}
      {!loading && page && <ul className="questline-list">{page.items.map(line => <li key={line.id}><Link to={`/questlines/${line.id}`} aria-current={line.id === selectedId ? 'page' : undefined} className="questline-link"><strong>{line.goal}</strong><span className="summary-meta"><Badge tone={line.status === 'completed' ? 'sage' : 'neutral'}>{line.status}</Badge><span>{line.progress.completed_count} / {line.progress.total_count} completed</span></span></Link></li>)}</ul>}
    </div>
    {!loading && page && <div className="pagination"><Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(v => Math.max(0, v - 20))}>Previous</Button><Button variant="secondary" disabled={!page.has_more} onClick={() => setOffset(v => v + 20)}>Next</Button></div>}
  </Card>
}
