import { useAppProfile } from '../components/AppShell'
import { Button, Card, EmptyState, ErrorNotice, LoadingIndicator, PageHeading } from '../components/UI'

export default function Progress() {
  const { profile, loading, error, refresh } = useAppProfile()
  return <>
    <PageHeading eyebrow="Small steps add up" title="Your Progress">A record of effort, without streaks or penalties.</PageHeading>
    {loading && !profile && <LoadingIndicator>Reading your local progress…</LoadingIndicator>}
    {error && <ErrorNotice action={<Button variant="secondary" onClick={refresh} loading={loading}>Retry progress</Button>}>{error}</ErrorNotice>}
    <div className="progress-grid" aria-live="polite">
      <Card><h2>Total XP</h2><p className="stat-number">{profile ? profile.total_xp.toLocaleString() : '—'}</p><p className="muted helper">{profile ? 'From your local profile.' : 'Waiting for backend profile data.'}</p></Card>
      <Card tone="butter"><h2>Current Level</h2><p className="stat-number">{profile ? profile.level : '—'}</p><p className="muted helper">{profile ? 'Confirmed by the backend.' : 'No level assumed before loading.'}</p></Card>
      <Card tone="leaf"><h2>Completed Quests</h2><p className="stat-number">—</p><p className="muted helper">Completed-work totals are not connected yet.</p></Card>
    </div>
    <Card className="history-foundation"><h2>Your completed work</h2><EmptyState title="History has a place here">Saved questline history will be connected in the next integration phase. No completed quests are assumed in this preview.</EmptyState></Card>
  </>
}
