import { Icon } from '../components/Icon'
import { Badge, Card, EmptyState, PageHeading } from '../components/UI'

export default function Journey() {
  return <>
    <PageHeading eyebrow="One step leads to another" title="Your Journey">A quiet view of where you’ve been and the step you’re on.</PageHeading>
    <Card className="journey-foundation">
      <div className="section-heading"><h2>Your path</h2><Badge tone="neutral">Journey preview</Badge></div>
      <EmptyState title="Your path will take shape here">Select a saved questline once connected. This preview does not display a generated plan or assume any progress.</EmptyState>
      <div className="journey-key" aria-label="Journey symbol key, not user progress"><h3>Journey key</h3><ul><li><span className="journey-node node-completed"><Icon name="check" /></span>Completed</li><li><span className="journey-node node-current"><Icon name="sprout" /></span>Current step</li><li><span className="journey-node node-locked"><Icon name="lock" /></span>Locked milestone</li></ul></div>
    </Card>
    <p className="muted page-note">Only completed work and the current quest’s details will be shown. Locked milestones will remain anonymous.</p>
  </>
}
