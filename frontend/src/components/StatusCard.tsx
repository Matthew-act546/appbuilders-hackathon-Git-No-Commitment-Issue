interface Props {
  title: string
  label: string
  available: boolean | null
  description: string
}

export function StatusCard({ title, label, available, description }: Props) {
  const color = available === null ? 'bg-slate-100 text-slate-600' : available ? 'bg-teal-50 text-teal-800' : 'bg-amber-50 text-amber-800'
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-500">{title}</h2>
      <span className={`mt-3 inline-block rounded-full px-3 py-1 text-sm font-medium ${color}`}>{label}</span>
      <p className="mt-3 break-words text-sm leading-6 text-slate-600">{description}</p>
    </section>
  )
}
