import { Badge, Card } from './UI'

interface Props {
  title: string
  label: string
  available: boolean | null
  description: string
}

export function StatusCard({ title, label, available, description }: Props) {
  return <Card className="status-card">
    <h3>{title}</h3>
    <Badge tone={available === null ? 'neutral' : available ? 'sage' : 'butter'}>{label}</Badge>
    <p className="muted helper">{description}</p>
  </Card>
}
