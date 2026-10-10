import { Link, useParams } from 'react-router'
import { CompletedStageTimeline } from '../components/CompletedStageTimeline'
import { JourneyQuestlinePicker } from '../components/JourneyQuestlinePicker'
import { Button, Card, EmptyState, ErrorNotice, LoadingIndicator, PageHeading } from '../components/UI'
import { useQuestline } from '../hooks/useQuestline'

export default function Journey() {
  const { id } = useParams<{ id: string }>()
  return <>
    <PageHeading eyebrow="One step leads to another" title="Your Journey">Revisit the small steps you have taken and the goals you have brought to life.</PageHeading>
    {id ? <JourneyHistory key={id} id={id} /> : <div className="journey-content stack">
      <JourneyQuestlinePicker />
      <Card tone="leaf"><EmptyState title="Every completed step has a place here">Choose a saved questline above to see its completed-stage timeline.</EmptyState></Card>
    </div>}
  </>
}

function JourneyHistory({ id }: { id: string }) {
  const { line, loading, error, reload } = useQuestline(id)
  return <div className="journey-content stack">
    <JourneyQuestlinePicker selectedId={id} selectedGoal={line?.goal} />
    <div className="section-heading"><p className="muted helper">Your saved history, at your own pace.</p><Button variant="quiet" disabled={loading} onClick={() => void reload()}>Refresh history</Button></div>
    {loading && <LoadingIndicator>Reading your completed stages…</LoadingIndicator>}
    {error && <ErrorNotice action={error.retryable ? <Button variant="secondary" onClick={() => void reload()}>Retry history</Button> : <Link className="text-link" to="/journey">Choose another questline →</Link>}>{error.message}</ErrorNotice>}
    {!loading && line && <CompletedStageTimeline line={line} />}
  </div>
}
