// Original geometric sprout illustration created for this application.
export function Sprout({ small = false }: { small?: boolean }) {
  return <svg className={small ? 'brand-sprout' : 'hero-sprout'} viewBox="0 0 120 130" fill="none" aria-hidden="true">
    <ellipse cx="60" cy="116" rx="43" ry="7" fill="var(--color-sage)" opacity=".4" />
    <path d="M60 72V43" stroke="var(--color-ink)" strokeWidth="4" strokeLinecap="round" />
    <path d="M59 49C32 50 23 35 23 15c24 0 38 12 36 34Z" fill="var(--color-sage)" stroke="var(--color-ink)" strokeWidth="3" strokeLinejoin="round" />
    <path d="M61 40C60 19 75 8 96 8c0 23-12 34-35 32Z" fill="var(--color-leaf)" stroke="var(--color-ink)" strokeWidth="3" strokeLinejoin="round" />
    <path d="M31 66c0-12 58-12 58 0l-6 37c-2 15-44 15-46 0Z" fill="var(--color-butter)" stroke="var(--color-ink)" strokeWidth="3" />
    <path d="M31 67c14 7 44 7 58 0" stroke="var(--color-ink)" strokeWidth="3" />
    <circle cx="49" cy="85" r="3" fill="var(--color-ink)" /><circle cx="71" cy="85" r="3" fill="var(--color-ink)" />
    <path d="M54 94q6 7 12 0" stroke="var(--color-ink)" strokeWidth="3" strokeLinecap="round" />
  </svg>
}
